from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

from app.scalp_collector import LIQUIDATION_INSERT_SQL

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_SQL = (
    ROOT / "sql/migrations/20260809_partition_compatibility_bridge.sql"
).read_text(encoding="utf-8")
ROLLBACK_SQL = (
    ROOT / "sql/migrations/20260809_partition_compatibility_bridge.down.sql"
).read_text(encoding="utf-8")

LEGACY_SCHEMA_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT value NOT IN (
        'NaN'::double precision,
        'Infinity'::double precision,
        '-Infinity'::double precision
    )
$$;
CREATE TABLE symbols (symbol text PRIMARY KEY);
INSERT INTO symbols(symbol) VALUES ('BTCUSDT_PERP.A');
CREATE TABLE liquidations_realtime (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    side text NOT NULL CHECK (side IN ('long','short')),
    notional_usd double precision NOT NULL
        CHECK (finite_float8(notional_usd) AND notional_usd >= 0),
    price double precision NOT NULL CHECK (finite_float8(price) AND price > 0),
    qty double precision NOT NULL CHECK (finite_float8(qty) AND qty >= 0),
    event_id text NOT NULL,
    PRIMARY KEY (exchange, event_id)
);
CREATE INDEX liquidations_realtime_symbol_ts_idx
    ON liquidations_realtime(symbol, ts DESC);
"""

PARTITIONED_SCHEMA_SQL = """
CREATE TABLE symbols (symbol text PRIMARY KEY);
INSERT INTO symbols(symbol) VALUES ('BTCUSDT_PERP.A');
CREATE TABLE liquidations_realtime (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    side text NOT NULL CHECK (side IN ('long','short')),
    notional_usd double precision NOT NULL CHECK (notional_usd >= 0),
    price double precision NOT NULL CHECK (price > 0),
    qty double precision NOT NULL CHECK (qty >= 0),
    event_id text NOT NULL,
    PRIMARY KEY (exchange, event_id, ts)
) PARTITION BY RANGE (ts);
CREATE TABLE liquidations_realtime_20260809
    PARTITION OF liquidations_realtime
    FOR VALUES FROM ('2026-08-09 00:00:00+00') TO ('2026-08-10 00:00:00+00');
CREATE TABLE liquidations_realtime_20260810
    PARTITION OF liquidations_realtime
    FOR VALUES FROM ('2026-08-10 00:00:00+00') TO ('2026-08-11 00:00:00+00');
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_bridge_{uuid.uuid4().hex}"


async def _connect_schema(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


def _row(
    ts: datetime,
    event_id: str,
    *,
    exchange: str = "bybit",
    side: str = "long",
) -> tuple[datetime, str, str, str, float, float, float, str]:
    return (ts, "BTCUSDT_PERP.A", exchange, side, 200.0, 100.0, 2.0, event_id)


async def _primary_key_columns(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT attribute.attname
        FROM pg_constraint AS constraint_definition
        JOIN LATERAL unnest(constraint_definition.conkey)
          WITH ORDINALITY AS key_column(attnum, ordinality) ON true
        JOIN pg_attribute AS attribute
          ON attribute.attrelid = constraint_definition.conrelid
         AND attribute.attnum = key_column.attnum
        WHERE constraint_definition.conrelid = 'liquidations_realtime'::regclass
          AND constraint_definition.contype = 'p'
        ORDER BY key_column.ordinality
        """
    )
    return [row["attname"] for row in rows]


def test_bridge_writer_declares_the_partition_compatible_conflict_target() -> None:
    compact_sql = " ".join(LIQUIDATION_INSERT_SQL.split())
    assert "ON CONFLICT(exchange,event_id,ts) DO NOTHING" in compact_sql
    assert "PARTITION BY" not in MIGRATION_SQL


@pytest.mark.asyncio
async def test_legacy_schema_migration_writer_duplicates_and_rollback() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    first_ts = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    later_ts = datetime(2026, 8, 9, 12, 1, tzinfo=UTC)
    try:
        await conn.execute(LEGACY_SCHEMA_SQL)
        await conn.execute(
            """
            INSERT INTO liquidations_realtime
                (ts,symbol,exchange,side,notional_usd,price,qty,event_id)
            VALUES ($1,'BTCUSDT_PERP.A','bybit','long',200,100,2,'existing')
            """,
            first_ts,
        )

        await conn.execute(MIGRATION_SQL)
        await conn.execute(MIGRATION_SQL)

        assert await conn.fetchval(
            "SELECT relkind = 'r' FROM pg_class WHERE oid = 'liquidations_realtime'::regclass"
        )
        assert await _primary_key_columns(conn) == ["exchange", "event_id"]
        assert await conn.fetchval(
            """
            SELECT indisunique AND indisvalid
            FROM pg_index
            WHERE indexrelid =
                'liquidations_realtime_exchange_event_ts_uidx'::regclass
            """
        )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM schema_migration
            WHERE name = '20260809_partition_compatibility_bridge'
            """
        ) == 1

        await conn.executemany(
            LIQUIDATION_INSERT_SQL,
            [
                _row(first_ts, "existing"),
                _row(later_ts, "existing"),
                _row(later_ts, "existing", exchange="binance", side="short"),
                _row(later_ts, "new"),
            ],
        )
        assert await conn.fetchval("SELECT count(*) FROM liquidations_realtime") == 3
        assert await conn.fetchval(
            """
            SELECT count(*) FROM liquidations_realtime
            WHERE exchange = 'bybit' AND event_id = 'existing'
            """
        ) == 1

        await conn.execute(ROLLBACK_SQL)
        await conn.execute(ROLLBACK_SQL)
        assert await _primary_key_columns(conn) == ["exchange", "event_id"]
        assert await conn.fetchval(
            "SELECT NOT EXISTS ("
            "  SELECT 1 FROM pg_index"
            "  JOIN pg_class AS idx ON idx.oid = pg_index.indexrelid"
            "  WHERE pg_index.indrelid = 'liquidations_realtime'::regclass"
            "    AND idx.relname = 'liquidations_realtime_exchange_event_ts_uidx'"
            ")"
        )
        assert await conn.fetchval("SELECT count(*) FROM liquidations_realtime") == 3
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_future_partitioned_schema_writer_is_globally_idempotent_and_down_refuses() -> None:
    schema = _schema_name()
    first = await _connect_schema(schema)
    second = await asyncpg.connect(_dsn())
    await second.execute(f'SET search_path TO "{schema}", public')
    first_ts = datetime(2026, 8, 9, 23, 59, tzinfo=UTC)
    next_ts = datetime(2026, 8, 10, 0, 0, tzinfo=UTC)
    try:
        await first.execute(PARTITIONED_SCHEMA_SQL)
        await first.execute(MIGRATION_SQL)
        assert await first.fetchval(
            "SELECT NOT EXISTS ("
            "  SELECT 1 FROM pg_index"
            "  JOIN pg_class AS idx ON idx.oid = pg_index.indexrelid"
            "  WHERE pg_index.indrelid = 'liquidations_realtime'::regclass"
            "    AND idx.relname = 'liquidations_realtime_exchange_event_ts_uidx'"
            ")"
        )

        first_transaction = first.transaction()
        await first_transaction.start()
        await first.execute(LIQUIDATION_INSERT_SQL, *_row(first_ts, "cross-partition"))

        second_insert = asyncio.create_task(
            second.execute(LIQUIDATION_INSERT_SQL, *_row(next_ts, "cross-partition"))
        )
        await asyncio.sleep(0.05)
        assert not second_insert.done()
        await first_transaction.commit()
        await second_insert

        assert await first.fetchval(
            """
            SELECT count(*) FROM liquidations_realtime
            WHERE exchange = 'bybit' AND event_id = 'cross-partition'
            """
        ) == 1
        assert await first.fetchval(
            """
            SELECT tableoid::regclass::text
            FROM liquidations_realtime
            WHERE event_id = 'cross-partition'
            """
        ) == "liquidations_realtime_20260809"

        with pytest.raises(asyncpg.RaiseError, match="not a legacy ordinary table"):
            await first.execute(ROLLBACK_SQL)
        await first.execute("ROLLBACK")
        assert await first.fetchval(
            "SELECT relkind = 'p' FROM pg_class WHERE oid = 'liquidations_realtime'::regclass"
        )
        assert await first.fetchval("SELECT count(*) FROM liquidations_realtime") == 1
    finally:
        await second.close()
        await _drop_schema(first, schema)
