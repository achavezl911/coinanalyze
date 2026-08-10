from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_outcomes import (
    MISSING_DATA_FINAL_GRACE,
    OUTCOME_HORIZONS_MINUTES,
    materialize_due_signal_outcomes,
    outcome_window,
    schedule_signal_outcomes,
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

BASE_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
SELECT value NOT IN (
  'NaN'::double precision,'Infinity'::double precision,'-Infinity'::double precision
) $$;

CREATE TABLE symbols(symbol text PRIMARY KEY);
INSERT INTO symbols VALUES ('BTCUSDT_PERP.A'),('ETHUSDT_PERP.A');

CREATE TABLE metrics_snapshot(
 ts timestamptz NOT NULL,
 symbol text NOT NULL REFERENCES symbols(symbol),
 regime_score double precision,regime_label text,
 price_cutoff_at timestamptz,metrics_cutoff_at timestamptz,
 PRIMARY KEY(symbol,ts)
);

CREATE TABLE ohlcv(
 ts timestamptz NOT NULL,
 symbol text NOT NULL REFERENCES symbols(symbol),
 interval text NOT NULL,
 open double precision NOT NULL,high double precision NOT NULL,
 low double precision NOT NULL,close double precision NOT NULL,
 volume double precision NOT NULL DEFAULT 0,
 buy_volume double precision NOT NULL DEFAULT 0,
 tx bigint NOT NULL DEFAULT 0,btx bigint NOT NULL DEFAULT 0,
 PRIMARY KEY(symbol,interval,ts)
);

CREATE TABLE data_gap(
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 feed text NOT NULL,
 feed_class text NOT NULL,
 exchange text NOT NULL,
 market text NOT NULL,
 symbol text NOT NULL,
 granularity text NOT NULL,
 start_ts timestamptz NOT NULL,
 end_ts timestamptz NOT NULL,
 expected_cadence interval,
 evidence_type text NOT NULL,
 detection_reason text NOT NULL,
 detection_source text NOT NULL,
 status text NOT NULL DEFAULT 'unresolved',
 detected_at timestamptz NOT NULL DEFAULT now(),
 resolved_at timestamptz,
 recovered_at timestamptz,
 recovered_by text,
 recovery_attempts integer NOT NULL DEFAULT 0
);
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _setup() -> tuple[asyncpg.Connection, str]:
    schema = f"test_signal_outcome_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(BASE_SQL)
    await conn.execute(LEDGER_DDL)
    await conn.execute(OUTCOME_DDL)
    return conn, schema


async def _teardown(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


async def _obs(
    conn: asyncpg.Connection,
    observed_at: datetime,
    *,
    direction: str = "long",
    reference_price: float | None = 100.0,
) -> int:
    if direction == "long":
        decision_status, actionable, state = "evaluable", True, "Long Momentum"
    elif direction == "short":
        decision_status, actionable, state = "evaluable", True, "Short Momentum"
    elif direction == "neutral":
        decision_status, actionable, state = "evaluable", False, "No Trade"
    else:
        decision_status, actionable, state = "not_evaluable", False, "Sin datos suficientes"
        direction = "unavailable"
    return int(await conn.fetchval(
        """
        INSERT INTO signal_observation(
          observed_at,observed_minute,symbol,signal_family,is_periodic,is_transition,
          logic_version,evidence_version,sampling_version,
          decision_status,direction,actionable,state,confidence,reason,
          reference_price,reference_price_source,reference_price_at,
          long_score,short_score,evidence_coverage_pct,
          collector_shard_index,collector_shard_count,
          decision_fingerprint,evidence
        ) VALUES(
          $1,date_trunc('minute',$1::timestamptz),'BTCUSDT_PERP.A','scalp',false,true,
          'scalp-summary-v1',1,1,$2,$3,$4,$5,'media','test',
          $6,'futures_realtime_combined',$1,
          75,25,80,0,1,repeat('a',64),'{}'::jsonb
        ) RETURNING observation_id
        """,
        observed_at,decision_status,direction,actionable,state,reference_price
    ))


async def _bars(
    conn: asyncpg.Connection,
    start: datetime,
    count: int,
    *,
    skip: int | None = None,
    include_giant_previous: bool = False,
) -> None:
    if include_giant_previous:
        await conn.execute(
            """INSERT INTO ohlcv VALUES(
            $1,'BTCUSDT_PERP.A','1min',100,1000,1,100,1,0.5,1,0)""",
            start - timedelta(minutes=1),
        )
    for i in range(count):
        if i == skip:
            continue
        await conn.execute(
            """INSERT INTO ohlcv VALUES(
            $1,'BTCUSDT_PERP.A','1min',100,$2,$3,$4,1,0.5,1,0)""",
            start + timedelta(minutes=i),102.0+i,98.0-i*0.1,101.0+i,
        )


@pytest.mark.asyncio
async def test_schema_backfill_and_scheduler_are_idempotent() -> None:
    conn, schema = await _setup()
    try:
        observed = datetime.now(UTC) - timedelta(minutes=10)
        oid = await _obs(conn, observed)
        await conn.execute(OUTCOME_DDL)
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_outcome WHERE observation_id=$1", oid
        ) == len(OUTCOME_HORIZONS_MINUTES)
        await conn.execute(OUTCOME_DDL)
        assert await schedule_signal_outcomes(conn, oid, observed) == 0
    finally:
        await _teardown(conn, schema)


@pytest.mark.asyncio
async def test_exact_path_evaluates_and_ignores_containing_minute() -> None:
    conn, schema = await _setup()
    try:
        observed = datetime.now(UTC) - timedelta(hours=2, seconds=17)
        oid = await _obs(conn, observed)
        assert await schedule_signal_outcomes(conn, oid, observed) == 8
        window = outcome_window(observed, 3)
        await _bars(conn, window.start, 3, include_giant_previous=True)
        result = await materialize_due_signal_outcomes(conn)
        assert result.evaluated >= 1
        row = await conn.fetchrow(
            """SELECT status,bars_found,max_high,min_low,directional_return_pct,mfe_pct,mae_pct
               FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=3""", oid
        )
        assert row["status"] == "evaluated"
        assert row["bars_found"] == 3
        assert row["max_high"] < 1000
        assert row["min_low"] > 1
        assert row["directional_return_pct"] is not None
        assert row["mfe_pct"] >= 0 and row["mae_pct"] >= 0
    finally:
        await _teardown(conn, schema)


@pytest.mark.asyncio
async def test_missing_interior_bar_retries_then_finalizes_fail_closed_after_grace() -> None:
    conn, schema = await _setup()
    try:
        recent = datetime.now(UTC) - timedelta(hours=2)
        recent_id = await _obs(conn, recent)
        await schedule_signal_outcomes(conn, recent_id, recent)
        recent_window = outcome_window(recent, 3)
        await _bars(conn, recent_window.start, 3, skip=1)
        await materialize_due_signal_outcomes(conn)
        row = await conn.fetchrow(
            """SELECT status,bars_found,attempts,finalized_at
               FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=3""",
            recent_id,
        )
        assert row["status"] == "pending"
        assert row["bars_found"] == 2
        assert row["attempts"] == 1
        assert row["finalized_at"] is None

        old = datetime.now(UTC) - MISSING_DATA_FINAL_GRACE - timedelta(hours=5)
        old_id = await _obs(conn, old, direction="short")
        await schedule_signal_outcomes(conn, old_id, old)
        await materialize_due_signal_outcomes(conn)
        old_row = await conn.fetchrow(
            """SELECT status,final_reason,market_return_pct,mfe_pct,mae_pct
               FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=3""",
            old_id,
        )
        assert old_row["status"] == "not_evaluable"
        assert old_row["final_reason"] == "incomplete_exact_ohlcv_path_after_grace"
        assert old_row["market_return_pct"] is None
        assert old_row["mfe_pct"] is None and old_row["mae_pct"] is None
    finally:
        await _teardown(conn, schema)


@pytest.mark.asyncio
async def test_missing_reference_never_looks_up_replacement_and_neutral_has_no_trade_metrics() -> None:
    conn, schema = await _setup()
    try:
        observed = datetime.now(UTC) - timedelta(hours=2)
        missing_id = await _obs(conn, observed, reference_price=None)
        await schedule_signal_outcomes(conn, missing_id, observed)
        await _bars(conn, outcome_window(observed, 3).start, 3)
        await materialize_due_signal_outcomes(conn)
        missing = await conn.fetchrow(
            """SELECT status,final_reason,entry_reference_price
               FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=3""",
            missing_id,
        )
        assert missing["status"] == "not_evaluable"
        assert missing["final_reason"] == "missing_reference_price"
        assert missing["entry_reference_price"] is None

        observed2 = observed + timedelta(minutes=20)
        neutral_id = await _obs(conn, observed2, direction="neutral")
        await schedule_signal_outcomes(conn, neutral_id, observed2)
        await _bars(conn, outcome_window(observed2, 3).start, 3)
        await materialize_due_signal_outcomes(conn)
        neutral = await conn.fetchrow(
            """SELECT status,market_return_pct,directional_return_pct,mfe_pct,mae_pct
               FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=3""",
            neutral_id,
        )
        assert neutral["status"] == "evaluated"
        assert neutral["market_return_pct"] is not None
        assert neutral["directional_return_pct"] is None
        assert neutral["mfe_pct"] is None and neutral["mae_pct"] is None
    finally:
        await _teardown(conn, schema)


async def _gap(
    conn: asyncpg.Connection,
    start: datetime,
    end: datetime,
    *,
    status: str = "unresolved",
    exchange: str = "binance",
    market: str = "perpetual",
    symbol: str = "BTCUSDT_PERP.A",
) -> None:
    resolved_at = datetime.now(UTC) if status != "unresolved" else None
    recovered_at = datetime.now(UTC) if status == "recovered" else None
    await conn.execute(
        """
        INSERT INTO data_gap(
          feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,
          expected_cadence,evidence_type,detection_reason,detection_source,
          status,resolved_at,recovered_at
        ) VALUES(
          'ohlcv_1min','cadence',$1,$2,$3,'1min',$4,$5,interval '1 minute',
          'missing_interval','test','test',$6,$7,$8
        )
        """,
        exchange,market,symbol,start,end,status,resolved_at,recovered_at,
    )


@pytest.mark.asyncio
async def test_exact_pr3_gap_blocks_only_matching_source_and_recovered_gap_unblocks() -> None:
    conn, schema = await _setup()
    try:
        observed = datetime.now(UTC) - timedelta(hours=2)
        oid = await _obs(conn, observed)
        await schedule_signal_outcomes(conn, oid, observed)
        window = outcome_window(observed, 3)
        await _bars(conn, window.start, 3)

        # Unrelated exchange gap must not contaminate the Binance futures outcome.
        await _gap(conn, window.start, window.end, exchange="bybit")
        await materialize_due_signal_outcomes(conn)
        row = await conn.fetchrow(
            """SELECT status FROM signal_outcome
               WHERE observation_id=$1 AND horizon_minutes=3""", oid
        )
        assert row["status"] == "evaluated"

        observed2 = observed + timedelta(minutes=20)
        oid2 = await _obs(conn, observed2)
        await schedule_signal_outcomes(conn, oid2, observed2)
        window2 = outcome_window(observed2, 3)
        await _bars(conn, window2.start, 3)
        await _gap(conn, window2.start, window2.end, status="unresolved")
        await materialize_due_signal_outcomes(conn)
        blocked = await conn.fetchrow(
            """SELECT status,attempts FROM signal_outcome
               WHERE observation_id=$1 AND horizon_minutes=3""", oid2
        )
        assert blocked["status"] == "pending"
        assert blocked["attempts"] == 1

        await conn.execute(
            """UPDATE data_gap SET status='recovered',resolved_at=now(),recovered_at=now()
               WHERE start_ts=$1 AND exchange='binance'""",
            window2.start,
        )
        await conn.execute(
            """UPDATE signal_outcome SET next_attempt_at=clock_timestamp()
               WHERE observation_id=$1 AND horizon_minutes=3 AND status='pending'""",
            oid2,
        )
        await materialize_due_signal_outcomes(conn)
        recovered = await conn.fetchrow(
            """SELECT status FROM signal_outcome
               WHERE observation_id=$1 AND horizon_minutes=3""", oid2
        )
        assert recovered["status"] == "evaluated"
    finally:
        await _teardown(conn, schema)


@pytest.mark.asyncio
async def test_final_outcome_is_immutable_and_durable() -> None:
    conn, schema = await _setup()
    try:
        observed = datetime.now(UTC) - timedelta(hours=2)
        oid = await _obs(conn, observed)
        await schedule_signal_outcomes(conn, oid, observed)
        await _bars(conn, outcome_window(observed, 1).start, 1)
        await materialize_due_signal_outcomes(conn)
        outcome_id = await conn.fetchval(
            """SELECT outcome_id FROM signal_outcome
               WHERE observation_id=$1 AND horizon_minutes=1""", oid
        )
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await conn.execute(
                "UPDATE signal_outcome SET bars_found=0 WHERE outcome_id=$1", outcome_id
            )
        with pytest.raises(asyncpg.PostgresError, match="durable"):
            await conn.execute(
                "DELETE FROM signal_outcome WHERE outcome_id=$1", outcome_id
            )
        with pytest.raises(asyncpg.PostgresError, match="durable"):
            await conn.execute("TRUNCATE signal_outcome")
    finally:
        await _teardown(conn, schema)
