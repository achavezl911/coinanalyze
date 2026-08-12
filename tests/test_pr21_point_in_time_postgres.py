from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
UP_SQL = (
    ROOT / "sql/migrations/20260811_pr21_point_in_time.sql"
).read_text(encoding="utf-8")
DOWN_SQL = (
    ROOT / "sql/migrations/20260811_pr21_point_in_time_down.sql"
).read_text(encoding="utf-8")
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

PRE_PR21_SQL = """
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
CREATE TABLE daily_verdict (
    session_date date NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    swing_score double precision,
    PRIMARY KEY(symbol,session_date)
);
INSERT INTO daily_verdict(session_date,symbol,swing_score)
VALUES ('2026-08-10','BTCUSDT_PERP.A',99);
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _connect_schema(prefix: str) -> tuple[asyncpg.Connection, str]:
    schema = f"{prefix}_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    return conn, schema


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


@pytest.fixture
async def conn():
    connection, schema = await _connect_schema("test_pr21_snapshot")
    await connection.execute(PRE_PR21_SQL)
    await connection.execute(UP_SQL)
    try:
        yield connection
    finally:
        await _drop_schema(connection, schema)


async def _insert_snapshot(
    conn: asyncpg.Connection,
    *,
    session_date: date = date(2026, 8, 11),
    swing_score: float = 1.0,
) -> str:
    return await conn.execute(
        """
        INSERT INTO daily_verdict_snapshot(
          session_date,symbol,snapshot_version,logic_version,
          observed_at,session_end_at,swing_score,session_price_close,
          reference_price,reference_price_at
        ) VALUES(
          $1,'BTCUSDT_PERP.A',1,'daily-verdict-v1',
          $2,$3,$4,101,100.5,$5
        )
        """,
        session_date,
        datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
        datetime(2026, 8, 11, 13, 30, tzinfo=UTC),
        swing_score,
        datetime(2026, 8, 11, 14, 59, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_pr21_first_daily_verdict_snapshot_is_immutable(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn, swing_score=1.0)
    await conn.execute(
        """
        INSERT INTO daily_verdict_snapshot(
          session_date,symbol,snapshot_version,logic_version,
          observed_at,session_end_at,swing_score
        ) VALUES(
          '2026-08-11','BTCUSDT_PERP.A',1,'daily-verdict-v1',
          '2026-08-11 16:00+00','2026-08-11 13:30+00',999
        )
        ON CONFLICT(symbol,session_date) DO NOTHING
        """
    )
    row = await conn.fetchrow(
        "SELECT swing_score,observed_at FROM daily_verdict_snapshot"
    )
    assert row["swing_score"] == 1.0
    assert row["observed_at"] == datetime(2026, 8, 11, 15, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_pr21_daily_verdict_snapshot_is_one_per_session(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn)
    with pytest.raises(asyncpg.UniqueViolationError):
        await _insert_snapshot(conn, swing_score=2.0)
    assert await conn.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 1


@pytest.mark.asyncio
async def test_pr21_daily_verdict_snapshot_rejects_update(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn)
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        await conn.execute("UPDATE daily_verdict_snapshot SET swing_score=2")


@pytest.mark.asyncio
async def test_pr21_daily_verdict_snapshot_rejects_delete(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn)
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        await conn.execute("DELETE FROM daily_verdict_snapshot")


@pytest.mark.asyncio
async def test_pr21_daily_verdict_snapshot_rejects_truncate(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn)
    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        await conn.execute("TRUNCATE daily_verdict_snapshot")
    assert await conn.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 1


@pytest.mark.asyncio
async def test_pr21_snapshot_rejects_pre_session_observation(
    conn: asyncpg.Connection,
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO daily_verdict_snapshot(
              session_date,symbol,snapshot_version,logic_version,
              observed_at,session_end_at
            ) VALUES(
              '2026-08-11','BTCUSDT_PERP.A',1,'daily-verdict-v1',
              '2026-08-11 13:29:59+00','2026-08-11 13:30+00'
            )
            """
        )


@pytest.mark.asyncio
async def test_pr21_snapshot_reference_price_pair_is_atomic(
    conn: asyncpg.Connection,
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO daily_verdict_snapshot(
              session_date,symbol,snapshot_version,logic_version,
              observed_at,session_end_at,reference_price
            ) VALUES(
              '2026-08-11','BTCUSDT_PERP.A',1,'daily-verdict-v1',
              '2026-08-11 15:00+00','2026-08-11 13:30+00',100
            )
            """
        )


@pytest.mark.asyncio
async def test_pr21_legacy_daily_verdict_is_not_backfilled_as_snapshot(
    conn: asyncpg.Connection,
) -> None:
    assert await conn.fetchval("SELECT count(*) FROM daily_verdict") == 1
    assert await conn.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 0
    assert "INSERT INTO daily_verdict_snapshot" not in UP_SQL


@pytest.mark.asyncio
async def test_pr21_down_migration_fails_closed_when_snapshot_contains_rows(
    conn: asyncpg.Connection,
) -> None:
    await _insert_snapshot(conn)
    with pytest.raises(asyncpg.PostgresError, match="refuses to destroy"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")
    assert await conn.fetchval("SELECT to_regclass('daily_verdict_snapshot') IS NOT NULL")
    assert await conn.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 1


@pytest.mark.asyncio
async def test_pr21_upgrade_up_down_empty_up_again_is_idempotent() -> None:
    connection, schema = await _connect_schema("test_pr21_upgrade")
    try:
        await connection.execute(PRE_PR21_SQL)
        await connection.execute(UP_SQL)
        await connection.execute(UP_SQL)
        assert await connection.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 0
        assert await connection.fetchval("SELECT count(*) FROM daily_verdict") == 1

        await connection.execute(DOWN_SQL)
        assert not await connection.fetchval(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_name='daily_verdict_snapshot')"
        )
        await connection.execute(UP_SQL)
        assert await connection.fetchval("SELECT to_regclass('daily_verdict_snapshot') IS NOT NULL")
    finally:
        await _drop_schema(connection, schema)


@pytest.mark.asyncio
async def test_pr21_fresh_schema_is_valid_and_idempotent() -> None:
    connection, schema = await _connect_schema("test_pr21_fresh")
    try:
        await connection.execute(SCHEMA_SQL)
        await connection.execute(SCHEMA_SQL)
        assert await connection.fetchval("SELECT to_regclass('daily_verdict_snapshot') IS NOT NULL")
        assert await connection.fetchval("SELECT count(*) FROM daily_verdict_snapshot") == 0
    finally:
        await _drop_schema(connection, schema)
