from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_backtest import (
    DENSE_PERIODIC,
    UTC_NONOVERLAP,
    BacktestOptions,
    build_signal_backtest_report,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

LEDGER_DDL = (
    SCHEMA_SQL.split("-- PR4_SIGNAL_OBSERVATION_LEDGER_BEGIN", 1)[1]
    .split("-- PR4_SIGNAL_OBSERVATION_LEDGER_END", 1)[0]
)
OUTCOME_DDL = (
    SCHEMA_SQL.split("-- PR5_SIGNAL_OUTCOMES_BEGIN", 1)[1]
    .split("-- PR5_SIGNAL_OUTCOMES_END", 1)[0]
)
REPLAY_DDL = (
    SCHEMA_SQL.split("-- PR6_SIGNAL_REPLAY_BEGIN", 1)[1]
    .split("-- PR6_SIGNAL_REPLAY_END", 1)[0]
)

BASE_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT value NOT IN (
        'NaN'::double precision,
        'Infinity'::double precision,
        '-Infinity'::double precision
    )
$$;

CREATE TABLE symbols (
    symbol text PRIMARY KEY
);

INSERT INTO symbols(symbol)
VALUES ('BTCUSDT_PERP.A'),('ETHUSDT_PERP.A');
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_signal_backtest_{uuid.uuid4().hex}"


async def _connect_schema(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(BASE_SQL)
    await conn.execute(LEDGER_DDL)
    await conn.execute(OUTCOME_DDL)
    await conn.execute(REPLAY_DDL)
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    symbol: str,
    state: str,
    direction: str,
    actionable: bool,
    is_periodic: bool = True,
    is_transition: bool = False,
    logic_version: str = "scalp-summary-v1",
    confidence: str = "media",
    decision_status: str = "evaluable",
    regime_label: str | None = "test-regime",
) -> int:
    observed_minute = observed_at.replace(second=0, microsecond=0)
    return int(
        await conn.fetchval(
            """
            INSERT INTO signal_observation(
              observed_at,observed_minute,symbol,signal_family,
              is_periodic,is_transition,
              logic_version,evidence_version,sampling_version,
              decision_status,direction,actionable,state,confidence,reason,
              reference_price,reference_price_source,
              long_score,short_score,evidence_coverage_pct,
              regime_label,
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,$2,$3,'scalp',
              $4,$5,
              $6,1,1,
              $7,$8,$9,$10,$11,'test observation',
              100.0,'futures_realtime_combined',
              60.0,40.0,80.0,
              $12,
              0,1,
              repeat('a',64),'{}'::jsonb
            )
            RETURNING observation_id
            """,
            observed_at,
            observed_minute,
            symbol,
            is_periodic,
            is_transition,
            logic_version,
            decision_status,
            direction,
            actionable,
            state,
            confidence,
            regime_label,
        )
    )


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    context_version: int = 1,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context
        ) VALUES($1,$2,$3,repeat('b',64),'{"now_ms": 1}'::jsonb)
        """,
        observation_id,
        context_version,
        observed_at,
    )


async def _insert_evaluated_outcome(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    horizon: int,
    directional_return: float | None,
    mfe: float | None,
    mae: float | None,
    market_return: float,
    outcome_version: int = 1,
) -> None:
    start = observed_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = start + timedelta(minutes=horizon)
    due = end + timedelta(minutes=42)
    await conn.execute(
        """
        INSERT INTO signal_outcome(
          observation_id,horizon_minutes,window_start,window_end,due_at,
          next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
          outcome_version,status,attempts,last_attempt_at,finalized_at,
          entry_reference_price,end_price,max_high,min_low,
          market_return_pct,up_excursion_pct,down_excursion_pct,
          directional_return_pct,mfe_pct,mae_pct
        ) VALUES(
          $1,$2,$3,$4,$5,
          $5,30,$2,$2,
          $6,'evaluated',1,$5,$5,
          100,101,102,99,
          $7,2,-1,
          $8,$9,$10
        )
        """,
        observation_id,
        horizon,
        start,
        end,
        due,
        outcome_version,
        market_return,
        directional_return,
        mfe,
        mae,
    )


def _quarter_hour_anchor(now: datetime) -> datetime:
    ref = now.astimezone(UTC) - timedelta(days=2)
    return ref.replace(
        minute=(ref.minute // 15) * 15,
        second=0,
        microsecond=0,
    )


@pytest.mark.asyncio
async def test_backtest_uses_only_replayable_periodic_versioned_mature_rows() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        now = datetime.now(UTC)
        anchor = _quarter_hour_anchor(now)

        # Dense actionable sample 1: selected by UTC 15m non-overlap grid.
        long_win = await _insert_observation(
            conn,
            observed_at=anchor + timedelta(seconds=30),
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
        )
        await _insert_frame(conn, long_win, anchor + timedelta(seconds=30))
        await _insert_evaluated_outcome(
            conn,
            long_win,
            anchor + timedelta(seconds=30),
            horizon=15,
            directional_return=1.0,
            mfe=1.5,
            mae=0.2,
            market_return=1.0,
        )

        # Dense actionable sample 2: overlaps the first and is excluded only
        # from utc_nonoverlap.
        long_loss_at = anchor + timedelta(minutes=1, seconds=30)
        long_loss = await _insert_observation(
            conn,
            observed_at=long_loss_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
        )
        await _insert_frame(conn, long_loss, long_loss_at)
        await _insert_evaluated_outcome(
            conn,
            long_loss,
            long_loss_at,
            horizon=15,
            directional_return=-0.5,
            mfe=0.8,
            mae=0.6,
            market_return=-0.5,
        )

        # Neutral sample remains directionless and is selected independently on ETH.
        neutral = await _insert_observation(
            conn,
            observed_at=anchor + timedelta(seconds=30),
            symbol="ETHUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
        )
        await _insert_frame(conn, neutral, anchor + timedelta(seconds=30))
        await _insert_evaluated_outcome(
            conn,
            neutral,
            anchor + timedelta(seconds=30),
            horizon=15,
            directional_return=None,
            mfe=None,
            mae=None,
            market_return=0.4,
        )

        # Pre-PR6 periodic row: visible in corpus diagnostics, never backfilled.
        await _insert_observation(
            conn,
            observed_at=anchor - timedelta(hours=1),
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
        )

        # Version-incompatible frame: excluded rather than mixed.
        wrong_version_at = anchor - timedelta(minutes=30) + timedelta(seconds=30)
        wrong_version = await _insert_observation(
            conn,
            observed_at=wrong_version_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Momentum",
            direction="long",
            actionable=True,
        )
        await _insert_frame(
            conn,
            wrong_version,
            wrong_version_at,
            context_version=2,
        )
        await _insert_evaluated_outcome(
            conn,
            wrong_version,
            wrong_version_at,
            horizon=15,
            directional_return=9.0,
            mfe=9.0,
            mae=0.1,
            market_return=9.0,
        )

        # Transition-only frame is not part of the regular PR7 grid.
        transition_at = anchor - timedelta(minutes=45) + timedelta(seconds=30)
        transition = await _insert_observation(
            conn,
            observed_at=transition_at,
            symbol="BTCUSDT_PERP.A",
            state="Short Momentum",
            direction="short",
            actionable=True,
            is_periodic=False,
            is_transition=True,
        )
        await _insert_frame(conn, transition, transition_at)
        await _insert_evaluated_outcome(
            conn,
            transition,
            transition_at,
            horizon=15,
            directional_return=5.0,
            mfe=6.0,
            mae=0.1,
            market_return=-5.0,
        )

        options = BacktestOptions(
            lookback_days=30,
            horizons=(15,),
            group_by=("symbol", "state", "direction"),
            sampling_modes=(DENSE_PERIODIC, UTC_NONOVERLAP),
            min_group_n=2,
        )

        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_backtest_report(conn, options)

        corpus = report["corpus"]
        assert corpus["periodic_observations"] == 5
        assert corpus["periodic_without_replay_frame"] == 1
        assert corpus["version_excluded_periodic_observations"] == 1
        assert corpus["compatible_periodic_observations"] == 3
        assert corpus["transition_only_observations_excluded"] == 1
        assert corpus["expected_outcome_rows"] == 3
        assert corpus["requested_outcome_rows"] == 3
        assert corpus["missing_or_wrong_version_outcome_rows"] == 0
        assert corpus["mature_outcome_rows"] == 3

        dense = report["views"][DENSE_PERIODIC]["overall_by_horizon"]
        assert len(dense) == 1
        dense_row = dense[0]
        assert dense_row["horizon_minutes"] == 15
        assert dense_row["mature_outcomes"] == 3
        assert dense_row["actionable_evaluated_n"] == 2
        assert dense_row["gross_hit_rate_pct"] == pytest.approx(50.0)
        assert dense_row["gross_expectancy_pct"] == pytest.approx(0.25)
        assert dense_row["average_winner_pct"] == pytest.approx(1.0)
        assert dense_row["average_loser_pct"] == pytest.approx(-0.5)
        assert dense_row["payoff_ratio"] == pytest.approx(2.0)
        assert dense_row["observation_profit_factor"] == pytest.approx(2.0)
        assert dense_row["mfe_median_pct"] == pytest.approx(1.15)
        assert dense_row["mae_median_pct"] == pytest.approx(0.4)
        assert dense_row["neutral_evaluated_n"] == 1
        assert dense_row["neutral_abs_market_return_median_pct"] == pytest.approx(0.4)
        assert dense_row["directional_metric_anomalies"] == 0
        assert dense_row["nondirectional_metric_anomalies"] == 0
        assert dense_row["actionable_meets_min_group_n"] is True

        sparse = report["views"][UTC_NONOVERLAP]["overall_by_horizon"]
        assert len(sparse) == 1
        sparse_row = sparse[0]
        # BTC aligned winner + ETH aligned neutral. The 1-minute-shifted BTC
        # observation is excluded by clock only, not because it lost.
        assert sparse_row["mature_outcomes"] == 2
        assert sparse_row["actionable_evaluated_n"] == 1
        assert sparse_row["gross_hit_rate_pct"] == pytest.approx(100.0)
        assert sparse_row["gross_expectancy_pct"] == pytest.approx(1.0)
        assert sparse_row["neutral_evaluated_n"] == 1

        groups = report["views"][DENSE_PERIODIC]["groups"]
        btc_long = next(
            row
            for row in groups
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["state"] == "Long Pullback"
            and row["direction"] == "long"
        )
        assert btc_long["actionable_evaluated_n"] == 2
        assert btc_long["gross_expectancy_pct"] == pytest.approx(0.25)
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_not_yet_due_outcome_is_not_in_mature_denominator() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        now = datetime.now(UTC)
        observed_at = now - timedelta(minutes=2)

        observation_id = await _insert_observation(
            conn,
            observed_at=observed_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Momentum",
            direction="long",
            actionable=True,
        )
        await _insert_frame(conn, observation_id, observed_at)

        start = observed_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
        end = start + timedelta(minutes=15)
        due = end + timedelta(minutes=42)
        assert due > now

        await conn.execute(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,
              outcome_version,status
            ) VALUES($1,15,$2,$3,$4,$4,30,15,1,'pending')
            """,
            observation_id,
            start,
            end,
            due,
        )

        options = BacktestOptions(
            lookback_days=1,
            horizons=(15,),
            sampling_modes=(DENSE_PERIODIC,),
        )
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_backtest_report(conn, options)

        assert report["corpus"]["compatible_periodic_observations"] == 1
        assert report["corpus"]["requested_outcome_rows"] == 1
        assert report["corpus"]["mature_outcome_rows"] == 0
        assert report["views"][DENSE_PERIODIC]["overall_by_horizon"] == []
    finally:
        await _drop_schema(conn, schema)
