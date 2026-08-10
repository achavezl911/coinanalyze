from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_attribution import (
    DENSE_PERIODIC,
    UTC_NONOVERLAP,
    AttributionOptions,
    build_signal_attribution_report,
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
    return f"test_signal_attribution_{uuid.uuid4().hex}"


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


def _evidence(
    *,
    imbalance_l5: float | None,
    missing_components: list[str] | None = None,
) -> dict[str, object]:
    return {
        "fut_delta_1m": 10.0,
        "fut_delta_3m": 20.0,
        "fut_volume_1m": 100.0,
        "spot_fut_divergence_norm": 0.2,
        "imbalance_l5": imbalance_l5,
        "absorption": "Neutra",
        "long_liq_5m": 0.0,
        "short_liq_5m": 0.0,
        "liquidations_measured": True,
        "oi_chg_15m_pct": 0.1,
        "price_move_15m_pct": 0.2,
        "oi_contributes_direction": True,
        "oi_directional_support": 1.0,
        "vwap_dist_pct": 0.05,
        "missing_components": missing_components or [],
    }


def _context() -> dict[str, object]:
    return {
        "now_ms": 1_700_000_000_000.0,
        "fut_volume_3m": 200.0,
    }


async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    symbol: str,
    state: str,
    direction: str,
    actionable: bool,
    evidence: dict[str, object],
    is_periodic: bool = True,
    is_transition: bool = False,
    logic_version: str = "scalp-summary-v1",
    confidence: str = "media",
) -> int:
    observed_minute = observed_at.replace(second=0, microsecond=0)
    import json

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
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,$2,$3,'scalp',
              $4,$5,
              $6,1,1,
              'evaluable',$7,$8,$9,$10,'test observation',
              100.0,'futures_realtime_combined',
              60.0,40.0,100.0,
              0,1,
              repeat('a',64),$11::jsonb
            )
            RETURNING observation_id
            """,
            observed_at,
            observed_minute,
            symbol,
            is_periodic,
            is_transition,
            logic_version,
            direction,
            actionable,
            state,
            confidence,
            json.dumps(evidence),
        )
    )


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    context: dict[str, object],
    context_version: int = 1,
) -> None:
    import json

    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context
        ) VALUES($1,$2,$3,repeat('b',64),$4::jsonb)
        """,
        observation_id,
        context_version,
        observed_at,
        json.dumps(context),
    )


async def _insert_evaluated_outcome(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    horizon: int,
    market_return: float,
    directional_return: float | None,
    mfe: float | None,
    mae: float | None,
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
          1,'evaluated',1,$5,$5,
          100,101,102,99,
          $6,2,-1,
          $7,$8,$9
        )
        """,
        observation_id,
        horizon,
        start,
        end,
        due,
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
async def test_attribution_separates_standalone_prediction_from_decision_agreement() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        now = datetime.now(UTC)
        anchor = _quarter_hour_anchor(now)

        # A: long winner; book vote +0.5 supports the final long and predicts up.
        a_at = anchor + timedelta(seconds=30)
        a = await _insert_observation(
            conn,
            observed_at=a_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.75),
        )
        await _insert_frame(conn, a, a_at, context=_context())
        await _insert_evaluated_outcome(
            conn,
            a,
            a_at,
            horizon=15,
            market_return=1.0,
            directional_return=1.0,
            mfe=1.5,
            mae=0.2,
        )

        # B: one minute later, final decision is still long but book is bearish.
        # Market falls. The book standalone direction is right, while it opposes
        # the losing final long. Dense includes it; utc_nonoverlap excludes it.
        b_at = anchor + timedelta(minutes=1, seconds=30)
        b = await _insert_observation(
            conn,
            observed_at=b_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.25),
        )
        await _insert_frame(conn, b, b_at, context=_context())
        await _insert_evaluated_outcome(
            conn,
            b,
            b_at,
            horizon=15,
            market_return=-0.5,
            directional_return=-0.5,
            mfe=0.8,
            mae=0.6,
        )

        # C: neutral final model decision. Book is measured neutral and must not
        # become a fake directional standalone call.
        c_at = anchor + timedelta(seconds=30)
        c = await _insert_observation(
            conn,
            observed_at=c_at,
            symbol="ETHUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            evidence=_evidence(imbalance_l5=0.5),
            confidence="baja",
        )
        await _insert_frame(conn, c, c_at, context=_context())
        await _insert_evaluated_outcome(
            conn,
            c,
            c_at,
            horizon=15,
            market_return=0.4,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        # D: missing book; missing_components agrees with extractor NULL.
        d_at = anchor - timedelta(minutes=15) + timedelta(seconds=30)
        d = await _insert_observation(
            conn,
            observed_at=d_at,
            symbol="ETHUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            evidence=_evidence(
                imbalance_l5=None,
                missing_components=["book"],
            ),
            confidence="baja",
        )
        await _insert_frame(conn, d, d_at, context=_context())
        await _insert_evaluated_outcome(
            conn,
            d,
            d_at,
            horizon=15,
            market_return=-0.2,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        # Transition-only: huge favorable outcome must never enter regular grid.
        t_at = anchor - timedelta(minutes=30) + timedelta(seconds=30)
        t = await _insert_observation(
            conn,
            observed_at=t_at,
            symbol="BTCUSDT_PERP.A",
            state="Short Momentum",
            direction="short",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.0),
            is_periodic=False,
            is_transition=True,
        )
        await _insert_frame(conn, t, t_at, context=_context())
        await _insert_evaluated_outcome(
            conn,
            t,
            t_at,
            horizon=15,
            market_return=-9.0,
            directional_return=9.0,
            mfe=9.0,
            mae=0.1,
        )

        # Pre-PR6 periodic row is diagnostic-only.
        await _insert_observation(
            conn,
            observed_at=anchor - timedelta(hours=1),
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            evidence=_evidence(imbalance_l5=0.9),
            confidence="baja",
        )

        options = AttributionOptions(
            lookback_days=30,
            horizons=(15,),
            components=("book",),
            group_by=(),
            sampling_modes=(DENSE_PERIODIC, UTC_NONOVERLAP),
            min_group_n=2,
        )

        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_attribution_report(conn, options)

        corpus = report["corpus"]
        assert corpus["periodic_observations"] == 5
        assert corpus["periodic_without_replay_frame"] == 1
        assert corpus["compatible_periodic_observations"] == 4
        assert corpus["transition_only_observations_excluded"] == 1
        assert corpus["expected_outcome_rows"] == 4
        assert corpus["requested_outcome_rows"] == 4
        assert corpus["missing_or_wrong_version_outcome_rows"] == 0
        assert corpus["mature_outcome_rows"] == 4

        dense = report["views"][DENSE_PERIODIC]["overall_by_component_horizon"]
        assert len(dense) == 1
        row = dense[0]
        assert row["component"] == "book"
        assert row["configured_weight"] == pytest.approx(20.0)
        assert row["outcome_evaluated_n"] == 4
        assert row["component_measured_evaluated_n"] == 3
        assert row["component_missing_evaluated_n"] == 1
        assert row["missing_semantics_mismatch_observations"] == 0

        # A (+book,+market) and B (-book,-market) both count as correct
        # standalone directional predictions; C is measured neutral and excluded.
        assert row["standalone_directional_n"] == 2
        assert row["standalone_directional_expectancy_pct"] == pytest.approx(0.75)
        assert row["standalone_directional_hit_rate_pct"] == pytest.approx(100.0)
        assert row["bullish_component_n"] == 1
        assert row["bearish_component_n"] == 1
        assert row["neutral_component_n"] == 1

        # Decision-conditioned: A supports winning long, B opposes losing long.
        assert row["actionable_evaluated_n"] == 2
        assert row["decision_component_measured_n"] == 2
        assert row["supports_decision_n"] == 1
        assert row["supports_decision_expectancy_pct"] == pytest.approx(1.0)
        assert row["opposes_decision_n"] == 1
        assert row["opposes_decision_expectancy_pct"] == pytest.approx(-0.5)
        assert row["support_minus_oppose_expectancy_pct"] == pytest.approx(1.5)
        assert row["support_minus_oppose_hit_rate_pp"] == pytest.approx(100.0)
        assert row["standalone_meets_min_group_n"] is True
        assert row["support_vs_oppose_meets_min_group_n"] is False

        sparse = report["views"][UTC_NONOVERLAP]["overall_by_component_horizon"]
        assert len(sparse) == 1
        sparse_row = sparse[0]
        # A + C are aligned to the quarter-hour; B is excluded by clock.
        # D is also aligned to a quarter hour and missing book.
        assert sparse_row["outcome_evaluated_n"] == 3
        assert sparse_row["standalone_directional_n"] == 1
        assert sparse_row["standalone_directional_expectancy_pct"] == pytest.approx(1.0)
        assert sparse_row["supports_decision_n"] == 1
        assert sparse_row["opposes_decision_n"] == 0
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_missing_semantics_mismatch_is_reported_not_hidden() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        now = datetime.now(UTC) - timedelta(days=2)
        observed_at = now.replace(second=30, microsecond=0)

        # Evidence says book is not missing, but the frozen value is NULL.
        observation_id = await _insert_observation(
            conn,
            observed_at=observed_at,
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            evidence=_evidence(
                imbalance_l5=None,
                missing_components=[],
            ),
            confidence="baja",
        )
        await _insert_frame(
            conn,
            observation_id,
            observed_at,
            context=_context(),
        )
        await _insert_evaluated_outcome(
            conn,
            observation_id,
            observed_at,
            horizon=15,
            market_return=0.1,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        options = AttributionOptions(
            lookback_days=30,
            horizons=(15,),
            components=("book",),
            group_by=(),
            sampling_modes=(DENSE_PERIODIC,),
        )
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_attribution_report(conn, options)

        row = report["views"][DENSE_PERIODIC]["overall_by_component_horizon"][0]
        assert row["missing_semantics_mismatch_observations"] == 1
        assert row["component_missing_evaluated_n"] == 1
    finally:
        await _drop_schema(conn, schema)
