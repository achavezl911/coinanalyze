from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import asyncpg
import pytest

from app.db import ServiceOwnership, ServiceOwnershipLost, fenced_transaction
from app.signal_ledger import persist_signal_observations

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
BEGIN_MARKER = "-- PR4_SIGNAL_OBSERVATION_LEDGER_BEGIN"
END_MARKER = "-- PR4_SIGNAL_OBSERVATION_LEDGER_END"
LEDGER_DDL = SCHEMA_SQL.split(BEGIN_MARKER, 1)[1].split(END_MARKER, 1)[0]

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
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    PRIMARY KEY(symbol, ts)
);

CREATE TABLE service_ownership (
    service text NOT NULL,
    shard_index integer NOT NULL,
    shard_count integer NOT NULL,
    generation bigint NOT NULL,
    acquired_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(service, shard_index, shard_count)
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
    return f"test_signal_ledger_{uuid.uuid4().hex}"


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


def _summary(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "long_score": 75.0,
        "short_score": 25.0,
        "state": "Long Momentum",
        "confidence": "alta",
        "reason": "measured evidence",
        "evidence_coverage_pct": 90.0,
        "book_status": "ok",
        "fut_price": 100.0,
        "basis_detail": {
            "fut_age_seconds": 2.0,
            "stale_after_seconds": 30.0,
        },
        "missing_components": [],
    }
    row.update(overrides)
    return row


async def _persist(
    conn: asyncpg.Connection,
    *,
    symbol: str = "BTCUSDT_PERP.A",
    summary: dict[str, object] | None = None,
    generation: int | None = 1,
) -> int:
    return await persist_signal_observations(
        conn,
        symbol,
        {
            "now_ms": 1_786_300_001_000.0,
            "price": 100.0,
            "ohlcv_price": 99.0,
            "fut_event_ms": 1_786_300_000_000,
        },
        summary or _summary(),
        collector_generation=generation,
        collector_shard_index=0,
        collector_shard_count=1,
    )


@pytest.mark.asyncio
async def test_schema_is_ordinary_idempotent_and_preserves_rows() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        # asyncpg maps PostgreSQL's internal pg_catalog "char" type (used by
        # pg_class.relkind) to raw bytes, not str.
        assert await conn.fetchval(
            "SELECT relkind FROM pg_class WHERE oid='signal_observation'::regclass"
        ) == b"r"
        assert await _persist(conn) == 1
        before = await conn.fetchval("SELECT count(*) FROM signal_observation")
        replay_before = await conn.fetchval("SELECT count(*) FROM signal_replay_frame")
        execution_before = await conn.fetchval(
            "SELECT count(*) FROM signal_execution_snapshot"
        )

        await conn.execute(LEDGER_DDL)
        await conn.execute(REPLAY_DDL)
        await conn.execute(EXECUTION_DDL)

        assert await conn.fetchval("SELECT count(*) FROM signal_observation") == before
        assert await conn.fetchval("SELECT count(*) FROM signal_replay_frame") == replay_before
        assert (
            await conn.fetchval("SELECT count(*) FROM signal_execution_snapshot")
            == execution_before
        )
        assert await conn.fetchval(
            """
            SELECT count(*) = 1
            FROM pg_indexes
            WHERE schemaname=current_schema()
              AND indexname='signal_observation_periodic_slot_uidx'
            """
        )
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_periodic_first_write_wins_and_transition_is_captured() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        assert await _persist(conn) == 1
        first = await conn.fetchrow(
            """
            SELECT is_periodic,is_transition,state,direction,actionable,evidence
            FROM signal_observation ORDER BY observation_id
            """
        )
        assert first["is_periodic"] is True
        assert first["is_transition"] is False
        assert first["state"] == "Long Momentum"
        assert first["direction"] == "long"
        assert first["actionable"] is True

        # Same semantic decision in the same minute: no second periodic sample
        # and no transition merely because scores moved.
        assert await _persist(
            conn,
            summary=_summary(long_score=76.0, short_score=24.0),
        ) == 0

        assert await _persist(
            conn,
            summary=_summary(
                long_score=20.0,
                short_score=80.0,
                state="Short Momentum",
            ),
        ) == 1
        rows = await conn.fetch(
            """
            SELECT is_periodic,is_transition,state,direction
            FROM signal_observation ORDER BY observation_id
            """
        )
        assert [
            (r["is_periodic"], r["is_transition"], r["state"], r["direction"])
            for r in rows
        ] == [
            (True, False, "Long Momentum", "long"),
            (False, True, "Short Momentum", "short"),
        ]
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_latest_non_future_metrics_snapshot_is_frozen() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await conn.execute(
            """
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,price_cutoff_at,metrics_cutoff_at
            ) VALUES
              (clock_timestamp()-interval '1 minute','BTCUSDT_PERP.A',-40,'bearish',
               clock_timestamp()-interval '2 minutes',clock_timestamp()-interval '5 minutes'),
              (clock_timestamp()+interval '1 hour','BTCUSDT_PERP.A',80,'future',
               clock_timestamp()+interval '1 hour',clock_timestamp()+interval '1 hour')
            """
        )
        await _persist(conn)
        row = await conn.fetchrow(
            """
            SELECT regime_score,regime_label,metrics_snapshot_ts,
                   price_cutoff_at,metrics_cutoff_at,observed_at
            FROM signal_observation
            """
        )
        assert row["regime_score"] == -40
        assert row["regime_label"] == "bearish"
        assert row["metrics_snapshot_ts"] <= row["observed_at"]
        assert row["price_cutoff_at"] < row["observed_at"]
        assert row["metrics_cutoff_at"] < row["observed_at"]
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_evidence_and_reference_provenance_are_frozen() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await _persist(conn, summary=_summary(optional=None))
        row = await conn.fetchrow(
            """
            SELECT reference_price,reference_price_source,reference_price_at,evidence
            FROM signal_observation
            """
        )
        assert row["reference_price"] == 100.0
        assert row["reference_price_source"] == "futures_realtime_combined"
        assert row["reference_price_at"] is not None
        evidence = row["evidence"]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        assert evidence["optional"] is None
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_ledger_rejects_update_delete_and_truncate() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await _persist(conn)
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("UPDATE signal_observation SET reason='rewritten'")
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("DELETE FROM signal_observation")
        # PR5 added signal_outcome as a FK child of signal_observation. CASCADE
        # is required so PostgreSQL's dependency check does not short-circuit
        # before this table's own append-only BEFORE TRUNCATE trigger fires.
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("TRUNCATE signal_observation CASCADE")
        assert await conn.fetchval("SELECT count(*) FROM signal_observation") == 1
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_stale_service_generation_cannot_write_research_history() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await conn.execute(
            """
            INSERT INTO service_ownership(
              service,shard_index,shard_count,generation,acquired_at
            ) VALUES('scalp',0,1,2,clock_timestamp())
            """
        )
        stale = ServiceOwnership(conn, "scalp", 0, 1, 1)
        with pytest.raises(ServiceOwnershipLost):
            async with fenced_transaction(conn, stale):
                await _persist(conn, generation=1)
        assert await conn.fetchval("SELECT count(*) FROM signal_observation") == 0
        assert await conn.fetchval("SELECT count(*) FROM signal_replay_frame") == 0

        current = ServiceOwnership(conn, "scalp", 0, 1, 2)
        async with fenced_transaction(conn, current):
            assert await _persist(conn, generation=2) == 1
        assert await conn.fetchval("SELECT count(*) FROM signal_observation") == 1
        assert await conn.fetchval("SELECT count(*) FROM signal_replay_frame") == 1
    finally:
        await _drop_schema(conn, schema)
