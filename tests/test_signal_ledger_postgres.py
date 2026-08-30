from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import asyncpg
import pytest

from app.db import ServiceOwnership, ServiceOwnershipLost, fenced_transaction

# K62: persist_signal_observations filtra WHERE regime_logic_version=$3 con la constante
# viva, asi que un literal en el fixture deja de significar "hay un snapshot compatible"
# en cuanto la constante sube: el snapshot no se encuentra y el test pasa a medir la
# AUSENCIA, que es lo que cubre test_pr24_v5_signal_does_not_copy_legacy_regime.
from app.metrics import REGIME_LOGIC_VERSION
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
    regime_logic_version smallint,
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
    context_as_of = await conn.fetchval("SELECT clock_timestamp()")
    return await persist_signal_observations(
        conn,
        symbol,
        {
            "now_ms": context_as_of.timestamp() * 1000.0,
            "price": 100.0,
            "ohlcv_price": 99.0,
            "ohlcv_price_at": context_as_of,
            "fut_event_ms": int(context_as_of.timestamp() * 1000.0) - 1_000,
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
            f"""
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,regime_logic_version,
              price_cutoff_at,metrics_cutoff_at
            ) VALUES
              (clock_timestamp()-interval '1 minute','BTCUSDT_PERP.A',-40,'bearish',
               {REGIME_LOGIC_VERSION},
               clock_timestamp()-interval '2 minutes',clock_timestamp()-interval '5 minutes'),
              (clock_timestamp()+interval '1 hour','BTCUSDT_PERP.A',80,'future',
               {REGIME_LOGIC_VERSION},
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
async def test_metrics_snapshot_knowledge_time_uses_committed_visibility_before_observed_at() -> None:
    schema = _schema_name()
    writer = await _connect_schema(schema)
    observer = await asyncpg.connect(_dsn())
    await observer.execute(f'SET search_path TO "{schema}", public')
    await observer.execute("SET TIME ZONE 'UTC'")
    metrics_read = asyncio.Event()
    allow_observation_clock = asyncio.Event()

    class PausedConnection:
        def __init__(self, raw: asyncpg.Connection) -> None:
            self.raw = raw
            self.provenance_read_at: list[datetime] = []

        def __getattr__(self, name: str):
            return getattr(self.raw, name)

        async def fetchrow(self, query: str, *args):
            row = await self.raw.fetchrow(query, *args)
            if "FROM metrics_snapshot" in query:
                self.provenance_read_at.append(
                    await self.raw.fetchval("SELECT clock_timestamp()")
                )
                if len(self.provenance_read_at) == 1:
                    metrics_read.set()
                    await allow_observation_clock.wait()
            return row

        async def fetch(self, query: str, *args):
            return await self.raw.fetch(query, *args)

        async def fetchval(self, query: str, *args):
            return await self.raw.fetchval(query, *args)

        async def execute(self, query: str, *args):
            return await self.raw.execute(query, *args)

    paused = PausedConnection(observer)
    transaction = writer.transaction()
    transaction_active = False
    try:
        await transaction.start()
        transaction_active = True
        await writer.execute(
            f"""
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,regime_logic_version,
              price_cutoff_at,metrics_cutoff_at
            ) VALUES(
              clock_timestamp()-interval '1 minute','BTCUSDT_PERP.A',42,'committed-v2',
              {REGIME_LOGIC_VERSION},
              clock_timestamp()-interval '2 minutes',clock_timestamp()-interval '3 minutes'
            )
            """
        )

        first_task = asyncio.create_task(_persist(paused))  # type: ignore[arg-type]
        await asyncio.wait_for(metrics_read.wait(), timeout=5)
        await transaction.commit()
        transaction_active = False
        allow_observation_clock.set()
        assert await first_task == 1

        first = await observer.fetchrow(
            """
            SELECT observed_at,metrics_snapshot_ts,regime_score
            FROM signal_observation ORDER BY observation_id LIMIT 1
            """
        )
        assert first["metrics_snapshot_ts"] is None
        assert first["regime_score"] is None
        assert first["observed_at"] >= paused.provenance_read_at[0]

        assert await _persist(
            paused,  # type: ignore[arg-type]
            summary=_summary(
                long_score=20.0,
                short_score=80.0,
                state="Short Momentum",
            ),
        ) == 1
        second = await observer.fetchrow(
            """
            SELECT observed_at,metrics_snapshot_ts,regime_score
            FROM signal_observation ORDER BY observation_id DESC LIMIT 1
            """
        )
        assert second["metrics_snapshot_ts"] is not None
        assert second["regime_score"] == 42
        assert second["observed_at"] >= paused.provenance_read_at[1]
    finally:
        allow_observation_clock.set()
        if transaction_active:
            await transaction.rollback()
        await observer.close()
        await _drop_schema(writer, schema)


@pytest.mark.asyncio
async def test_pr24_v5_signal_does_not_copy_legacy_regime() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await conn.execute(
            """
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,regime_logic_version,
              price_cutoff_at,metrics_cutoff_at
            ) VALUES(
              clock_timestamp()-interval '2 minutes','BTCUSDT_PERP.A',55,'legacy',NULL,
              clock_timestamp()-interval '3 minutes',clock_timestamp()-interval '4 minutes'
            )
            """
        )
        assert await _persist(conn) == 1
        legacy_only = await conn.fetchrow(
            """
            SELECT evidence_version,regime_score,regime_label,regime_logic_version,
                   metrics_snapshot_ts,price_cutoff_at,metrics_cutoff_at
            FROM signal_observation ORDER BY observation_id
            """
        )
        assert legacy_only["evidence_version"] == 7
        for field in (
            "regime_score",
            "regime_label",
            "regime_logic_version",
            "metrics_snapshot_ts",
            "price_cutoff_at",
            "metrics_cutoff_at",
        ):
            assert legacy_only[field] is None

        await conn.execute(
            f"""
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,regime_logic_version,
              price_cutoff_at,metrics_cutoff_at
            ) VALUES(
              clock_timestamp()-interval '1 minute','BTCUSDT_PERP.A',25,'v2',
              {REGIME_LOGIC_VERSION},
              clock_timestamp()-interval '2 minutes',clock_timestamp()-interval '3 minutes'
            )
            """
        )
        assert await _persist(
            conn,
            summary=_summary(
                long_score=20.0,
                short_score=80.0,
                state="Short Momentum",
            ),
        ) == 1
        v2 = await conn.fetchrow(
            """
            SELECT regime_score,regime_label,regime_logic_version,metrics_snapshot_ts
            FROM signal_observation ORDER BY observation_id DESC LIMIT 1
            """
        )
        assert (v2["regime_score"], v2["regime_label"], v2["regime_logic_version"]) == (
            25,
            "v2",
            REGIME_LOGIC_VERSION,
        )
        assert v2["metrics_snapshot_ts"] is not None
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_pr22_signal_observation_copies_regime_logic_version() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await conn.execute(
            f"""
            INSERT INTO metrics_snapshot(
              ts,symbol,regime_score,regime_label,regime_logic_version
            ) VALUES(
              clock_timestamp()-interval '1 minute','BTCUSDT_PERP.A',25,'v2',
              {REGIME_LOGIC_VERSION}
            )
            """
        )
        await _persist(conn)
        row = await conn.fetchrow(
            "SELECT evidence_version,regime_logic_version FROM signal_observation"
        )
        assert row["evidence_version"] == 7
        assert row["regime_logic_version"] == REGIME_LOGIC_VERSION
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
            SELECT observed_at,evidence_version,reference_price,reference_price_source,
                   reference_price_at,evidence
            FROM signal_observation
            """
        )
        assert row["reference_price"] == 100.0
        assert row["reference_price_source"] == "futures_realtime_combined"
        assert row["reference_price_at"] is not None
        assert row["reference_price_at"] <= row["observed_at"]
        assert row["evidence_version"] == 7
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
