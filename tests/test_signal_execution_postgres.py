from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_execution import (
    DENSE_PERIODIC,
    UTC_NONOVERLAP,
    ExecutionCostOptions,
    build_execution_cost_report,
)
from app.signal_ledger import persist_signal_observations

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
EXECUTION_DDL = (
    SCHEMA_SQL.split("-- PR10_SIGNAL_EXECUTION_BEGIN", 1)[1]
    .split("-- PR10_SIGNAL_EXECUTION_END", 1)[0]
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

CREATE TABLE metrics_snapshot (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    regime_score double precision,
    regime_label text,
    regime_logic_version smallint,
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    PRIMARY KEY(symbol, ts)
);

CREATE TABLE orderbook_depth (
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    ts timestamptz NOT NULL,
    bids jsonb NOT NULL,
    asks jsonb NOT NULL,
    levels integer NOT NULL CHECK (levels >= 0),
    PRIMARY KEY(symbol,exchange)
);
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_signal_execution_{uuid.uuid4().hex}"


async def _connect_schema(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(BASE_SQL)
    await conn.execute(LEDGER_DDL)
    await conn.execute(OUTCOME_DDL)
    await conn.execute(REPLAY_DDL)
    await conn.execute(EXECUTION_DDL)
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


def _summary() -> dict[str, object]:
    return {
        "long_score": 75.0,
        "short_score": 25.0,
        "state": "Long Momentum",
        "confidence": "alta",
        "reason": "measured evidence",
        "evidence_coverage_pct": 90.0,
        "book_status": "ok",
        "fut_price": 100.0,
        "basis_detail": {
            "fut_age_seconds": 1.0,
            "stale_after_seconds": 30.0,
        },
        "missing_components": [],
    }


async def _insert_current_books(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO orderbook_depth(symbol,exchange,ts,bids,asks,levels)
        VALUES
          (
            'BTCUSDT_PERP.A','binance',
            clock_timestamp()-interval '1 second',
            $1::jsonb,$2::jsonb,2
          ),
          (
            'BTCUSDT_PERP.A','bybit',
            clock_timestamp()-interval '1 second',
            $3::jsonb,$4::jsonb,2
          )
        ON CONFLICT(symbol,exchange) DO UPDATE SET
          ts=EXCLUDED.ts,bids=EXCLUDED.bids,asks=EXCLUDED.asks,levels=EXCLUDED.levels
        """,
        json.dumps([[99.9, 2000.0], [99.8, 2000.0]]),
        json.dumps([[100.1, 2000.0], [100.2, 2000.0]]),
        json.dumps([[99.85, 2000.0], [99.75, 2000.0]]),
        json.dumps([[100.15, 2000.0], [100.25, 2000.0]]),
    )


async def _persist_live_observation(conn: asyncpg.Connection) -> int:
    now_ms = datetime.now(UTC).timestamp() * 1000.0
    inserted = await persist_signal_observations(
        conn,
        "BTCUSDT_PERP.A",
        {
            "now_ms": now_ms,
            "price": 100.0,
            "ohlcv_price": 99.9,
            "fut_event_ms": now_ms - 1_000,
        },
        _summary(),
        collector_generation=1,
        collector_shard_index=0,
        collector_shard_count=1,
    )
    assert inserted == 1
    return int(await conn.fetchval("SELECT max(observation_id) FROM signal_observation"))


async def _insert_manual_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    direction: str,
    state: str,
) -> int:
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
              $1,date_trunc('minute',$1::timestamptz),'BTCUSDT_PERP.A','scalp',
              true,false,
              'scalp-summary-v1',1,1,
              'evaluable',$2,true,$3,'media','test',
              100.0,'futures_realtime_combined',
              70,30,90,
              0,1,
              repeat('a',64),'{}'::jsonb
            )
            RETURNING observation_id
            """,
            observed_at,
            direction,
            state,
        )
    )


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context
        ) VALUES(
          $1,1,$2,repeat('b',64),'{"now_ms":1}'::jsonb
        )
        """,
        observation_id,
        observed_at,
    )


def _curve(
    *,
    buy_cost_bps: float,
    sell_cost_bps: float,
    insufficient: bool = False,
) -> dict[str, object]:
    buy_fill = 100.0 * (1.0 + buy_cost_bps / 10000.0)
    sell_fill = 100.0 * (1.0 - sell_cost_bps / 10000.0)
    return {
        "1000": {
            "buy": {
                "avg_price": buy_fill,
                "levels_used": 1,
                "levels_available": 2,
                "filled_usd": 1000.0 if not insufficient else 500.0,
                "shortfall_usd": 0.0 if not insufficient else 500.0,
                "insufficient_depth": insufficient,
                "slippage_bps_vs_best": 0.0,
                "market_cost_bps_vs_mid": None if insufficient else buy_cost_bps,
            },
            "sell": {
                "avg_price": sell_fill,
                "levels_used": 1,
                "levels_available": 2,
                "filled_usd": 1000.0 if not insufficient else 500.0,
                "shortfall_usd": 0.0 if not insufficient else 500.0,
                "insufficient_depth": insufficient,
                "slippage_bps_vs_best": 0.0,
                "market_cost_bps_vs_mid": None if insufficient else sell_cost_bps,
            },
        }
    }


async def _insert_snapshot(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    observed_at: datetime,
    exchange: str,
    curve: dict[str, object],
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_execution_snapshot(
          observation_id,snapshot_version,exchange,captured_at,
          book_ts,book_age_seconds,status,reason,
          levels_reported,bid_levels_valid,ask_levels_valid,
          best_bid_px,best_ask_px,mid_px,spread_bps,
          bid_depth_usd,ask_depth_usd,source_book_hash,cost_curve
        ) VALUES(
          $1,1,$2,$3::timestamptz,
          $3::timestamptz-interval '1 second',1,'valid',NULL,
          2,2,2,
          99.9,100.1,100.0,20.0,
          200000,200000,repeat('c',64),$4::jsonb
        )
        """,
        observation_id,
        exchange,
        observed_at,
        json.dumps(curve),
    )


async def _insert_evaluated_outcome(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    observed_at: datetime,
    directional_return_pct: float,
) -> None:
    direction = await conn.fetchval(
        "SELECT direction FROM signal_observation WHERE observation_id=$1",
        observation_id,
    )
    if direction == "long":
        market_return_pct = directional_return_pct
    elif direction == "short":
        market_return_pct = -directional_return_pct
    else:
        raise ValueError("fixture requires long/short")
    end_price = 100.0 * (1.0 + market_return_pct / 100.0)

    start = observed_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = start + timedelta(minutes=15)
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
          $1,15,$2,$3,$4,
          $4,30,15,15,
          1,'evaluated',1,$4,$4,
          100,$5,102,99,
          $6,2,-1,
          $7,1.5,0.4
        )
        """,
        observation_id,
        start,
        end,
        due,
        end_price,
        market_return_pct,
        directional_return_pct,
    )


def _quarter_hour_anchor() -> datetime:
    ref = datetime.now(UTC) - timedelta(days=2)
    return ref.replace(
        minute=(ref.minute // 15) * 15,
        second=0,
        microsecond=0,
    )


@pytest.mark.asyncio
async def test_live_ledger_write_freezes_two_venue_execution_rows() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await _insert_current_books(conn)
        observation_id = await _persist_live_observation(conn)

        rows = await conn.fetch(
            """
            SELECT exchange,status,source_book_hash,cost_curve
            FROM signal_execution_snapshot
            WHERE observation_id=$1
            ORDER BY exchange
            """,
            observation_id,
        )
        assert [row["exchange"] for row in rows] == ["binance", "bybit"]
        assert [row["status"] for row in rows] == ["valid", "valid"]
        assert all(len(row["source_book_hash"]) == 64 for row in rows)

        for row in rows:
            curve = (
                json.loads(row["cost_curve"])
                if isinstance(row["cost_curve"], str)
                else row["cost_curve"]
            )
            assert set(curve) == {"1000", "10000", "50000", "100000"}

        assert await conn.fetchval(
            "SELECT count(*) FROM signal_replay_frame WHERE observation_id=$1",
            observation_id,
        ) == 1
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_execution_snapshot WHERE observation_id=$1",
            observation_id,
        ) == 2
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_outcome WHERE observation_id=$1",
            observation_id,
        ) == 8
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_missing_venue_is_preserved_without_cost_curve() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await conn.execute(
            """
            INSERT INTO orderbook_depth(symbol,exchange,ts,bids,asks,levels)
            VALUES(
              'BTCUSDT_PERP.A','binance',
              clock_timestamp()-interval '1 second',
              $1::jsonb,$2::jsonb,1
            )
            """,
            json.dumps([[99.9, 2000.0]]),
            json.dumps([[100.1, 2000.0]]),
        )
        observation_id = await _persist_live_observation(conn)

        rows = {
            row["exchange"]: row
            for row in await conn.fetch(
                """
                SELECT exchange,status,reason,cost_curve
                FROM signal_execution_snapshot
                WHERE observation_id=$1
                """,
                observation_id,
            )
        }
        assert rows["binance"]["status"] == "valid"
        assert rows["bybit"]["status"] == "unavailable"
        assert rows["bybit"]["reason"] == "no_current_orderbook_depth"
        bybit_curve = (
            json.loads(rows["bybit"]["cost_curve"])
            if isinstance(rows["bybit"]["cost_curve"], str)
            else rows["bybit"]["cost_curve"]
        )
        assert bybit_curve == {}
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_execution_snapshot_schema_is_append_only_and_no_backfill() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        assert await conn.fetchval(
            "SELECT relkind FROM pg_class WHERE oid='signal_execution_snapshot'::regclass"
        ) == b"r"

        observed_at = datetime.now(UTC) - timedelta(days=1)
        observation_id = await _insert_manual_observation(
            conn,
            observed_at=observed_at,
            direction="long",
            state="Long Momentum",
        )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM signal_execution_snapshot
            WHERE observation_id=$1
            """,
            observation_id,
        ) == 0

        await _insert_snapshot(
            conn,
            observation_id=observation_id,
            observed_at=observed_at,
            exchange="binance",
            curve=_curve(buy_cost_bps=2.0, sell_cost_bps=2.0),
        )

        for statement in (
            "UPDATE signal_execution_snapshot SET status='stale'",
            "DELETE FROM signal_execution_snapshot",
            "TRUNCATE signal_execution_snapshot",
        ):
            with pytest.raises(asyncpg.PostgresError) as exc:
                await conn.execute(statement)
            assert exc.value.sqlstate == "55000"
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_nonvalid_snapshot_remains_in_cost_coverage_denominator() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        observed_at = _quarter_hour_anchor() + timedelta(seconds=30)
        observation_id = await _insert_manual_observation(
            conn,
            observed_at=observed_at,
            direction="long",
            state="Long Momentum",
        )
        await _insert_frame(conn, observation_id, observed_at)

        await _insert_snapshot(
            conn,
            observation_id=observation_id,
            observed_at=observed_at,
            exchange="binance",
            curve=_curve(buy_cost_bps=2.0, sell_cost_bps=2.0),
        )
        await conn.execute(
            """
            INSERT INTO signal_execution_snapshot(
              observation_id,snapshot_version,exchange,captured_at,
              status,reason,levels_reported,bid_levels_valid,ask_levels_valid,
              cost_curve
            ) VALUES(
              $1,1,'bybit',$2,
              'unavailable','no_current_orderbook_depth',0,0,0,'{}'::jsonb
            )
            """,
            observation_id,
            observed_at,
        )
        await _insert_evaluated_outcome(
            conn,
            observation_id=observation_id,
            observed_at=observed_at,
            directional_return_pct=0.10,
        )

        options = ExecutionCostOptions(
            lookback_days=30,
            horizons=(15,),
            sizes_usd=(1000.0,),
            sampling_modes=(DENSE_PERIODIC,),
        )
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_execution_cost_report(conn, options)

        rows = report["views"][DENSE_PERIODIC][
            "execution_by_symbol_venue_size_horizon"
        ]
        bybit = next(row for row in rows if row["exchange"] == "bybit")

        assert bybit["actionable_evaluated_n"] == 1
        assert bybit["snapshot_not_valid_n"] == 1
        assert bybit["cost_evaluable_n"] == 0
        assert bybit["cost_evaluable_pct"] == pytest.approx(0.0)
        assert bybit["gross_expectancy_bps"] == pytest.approx(10.0)
        assert bybit["symmetric_market_net_expectancy_bps"] is None
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_report_applies_directional_book_side_and_explicit_fee_only() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        anchor = _quarter_hour_anchor()

        a_at = anchor + timedelta(seconds=30)
        a = await _insert_manual_observation(
            conn,
            observed_at=a_at,
            direction="long",
            state="Long Momentum",
        )
        await _insert_frame(conn, a, a_at)
        await _insert_snapshot(
            conn,
            observation_id=a,
            observed_at=a_at,
            exchange="binance",
            curve=_curve(buy_cost_bps=2.0, sell_cost_bps=7.0),
        )
        await _insert_snapshot(
            conn,
            observation_id=a,
            observed_at=a_at,
            exchange="bybit",
            curve=_curve(buy_cost_bps=4.0, sell_cost_bps=6.0),
        )
        await _insert_evaluated_outcome(
            conn,
            observation_id=a,
            observed_at=a_at,
            directional_return_pct=0.10,
        )

        b_at = anchor + timedelta(minutes=1, seconds=30)
        b = await _insert_manual_observation(
            conn,
            observed_at=b_at,
            direction="short",
            state="Short Momentum",
        )
        await _insert_frame(conn, b, b_at)
        await _insert_snapshot(
            conn,
            observation_id=b,
            observed_at=b_at,
            exchange="binance",
            curve=_curve(buy_cost_bps=2.0, sell_cost_bps=3.0),
        )
        await _insert_snapshot(
            conn,
            observation_id=b,
            observed_at=b_at,
            exchange="bybit",
            curve=_curve(buy_cost_bps=4.0, sell_cost_bps=5.0),
        )
        await _insert_evaluated_outcome(
            conn,
            observation_id=b,
            observed_at=b_at,
            directional_return_pct=-0.04,
        )

        options = ExecutionCostOptions(
            lookback_days=30,
            horizons=(15,),
            sizes_usd=(1000.0,),
            sampling_modes=(DENSE_PERIODIC, UTC_NONOVERLAP),
            fee_bps_per_side=(("binance", 1.0),),
            min_group_n=2,
        )
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_execution_cost_report(conn, options)

        corpus = report["corpus"]
        assert corpus["compatible_periodic_observations"] == 2
        assert corpus["execution_covered_periodic_observations"] == 2
        assert corpus["execution_era_observations_without_two_snapshots"] == 0
        assert corpus["expected_outcome_rows"] == 2
        assert corpus["requested_outcome_rows"] == 2
        assert corpus["missing_or_wrong_version_outcome_rows"] == 0

        dense = report["views"][DENSE_PERIODIC][
            "execution_by_symbol_venue_size_horizon"
        ]
        binance = next(
            row
            for row in dense
            if row["exchange"] == "binance"
            and row["size_usd"] == 1000.0
            and row["horizon_minutes"] == 15
        )
        assert binance["entry_market_cost_median_bps"] == pytest.approx(2.5)
        assert binance["gross_expectancy_bps"] == pytest.approx(3.0)
        assert binance["entry_implementation_shortfall_median_bps"] == pytest.approx(
            2.5,
            abs=0.01,
        )
        assert binance["symmetric_market_net_expectancy_bps"] == pytest.approx(
            -2.0,
            abs=0.02,
        )
        assert binance["modeled_net_after_fees_expectancy_bps"] == pytest.approx(
            -4.0,
            abs=0.02,
        )
        assert binance["modeled_net_after_fees_n"] == 2
        assert binance["meets_min_group_n"] is True

        bybit = next(
            row
            for row in dense
            if row["exchange"] == "bybit"
            and row["size_usd"] == 1000.0
            and row["horizon_minutes"] == 15
        )
        assert bybit["cost_evaluable_n"] == 2
        assert bybit["modeled_net_after_fees_n"] == 0
        assert bybit["modeled_net_after_fees_expectancy_bps"] is None

        sparse = report["views"][UTC_NONOVERLAP][
            "execution_by_symbol_venue_size_horizon"
        ]
        sparse_binance = next(
            row for row in sparse if row["exchange"] == "binance"
        )
        assert sparse_binance["actionable_evaluated_n"] == 1
        assert sparse_binance["gross_expectancy_bps"] == pytest.approx(10.0)
        assert sparse_binance["entry_market_cost_median_bps"] == pytest.approx(2.0)
    finally:
        await _drop_schema(conn, schema)
