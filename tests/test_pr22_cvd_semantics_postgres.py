from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.scalp_logic import (
    _CVD_WINDOWS,
    _cvd_fut_window,
    _cvd_src,
    cvd_matrix,
    delta_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
UP_SQL = (
    ROOT / "sql/migrations/20260812_pr22_cvd_semantics.sql"
).read_text(encoding="utf-8")
DOWN_SQL = (
    ROOT / "sql/migrations/20260812_pr22_cvd_semantics_down.sql"
).read_text(encoding="utf-8")
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

PRE_PR22_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
    SELECT value NOT IN (
        'NaN'::double precision,
        'Infinity'::double precision,
        '-Infinity'::double precision
    )
$$;
CREATE TABLE metrics_snapshot (
    ts timestamptz NOT NULL,
    symbol text NOT NULL,
    regime_score double precision,
    regime_label text,
    PRIMARY KEY(symbol,ts)
);
CREATE TABLE signal_observation (
    observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    evidence_version smallint NOT NULL,
    regime_score double precision,
    regime_label text,
    metrics_snapshot_ts timestamptz,
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz
);
CREATE TABLE daily_verdict_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    logic_version text NOT NULL,
    regime_score double precision,
    regime_label text,
    metrics_snapshot_ts timestamptz
);
INSERT INTO metrics_snapshot(ts,symbol,regime_score,regime_label)
VALUES ('2026-08-11 12:00+00','BTCUSDT_PERP.A',10,'legacy');
INSERT INTO signal_observation(evidence_version) VALUES (2);
INSERT INTO daily_verdict_snapshot(logic_version) VALUES ('daily-verdict-v1');
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _connect(prefix: str) -> tuple[asyncpg.Connection, str]:
    schema = f"{prefix}_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    return conn, schema


async def _drop(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


@pytest.mark.asyncio
async def test_pr22_legacy_metrics_rows_are_not_backfilled() -> None:
    conn, schema = await _connect("test_pr22_legacy_metrics")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        assert await conn.fetchval(
            "SELECT regime_logic_version FROM metrics_snapshot"
        ) is None
        assert await conn.fetchval("SELECT spot_vol_24h FROM metrics_snapshot") is None
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_existing_signal_observations_remain_unchanged() -> None:
    conn, schema = await _connect("test_pr22_legacy_signal")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        row = await conn.fetchrow(
            "SELECT evidence_version,regime_logic_version FROM signal_observation"
        )
        assert (row["evidence_version"], row["regime_logic_version"]) == (2, None)
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_existing_daily_verdict_v1_snapshot_remains_immutable() -> None:
    conn, schema = await _connect("test_pr22_legacy_daily")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        row = await conn.fetchrow(
            "SELECT logic_version,regime_logic_version FROM daily_verdict_snapshot"
        )
        assert (row["logic_version"], row["regime_logic_version"]) == (
            "daily-verdict-v1",
            None,
        )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_upgrade_up_twice_down_empty_up_again_is_idempotent() -> None:
    conn, schema = await _connect("test_pr22_upgrade")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        await conn.execute(UP_SQL)
        assert await conn.fetchval(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND column_name='regime_logic_version'"
        ) == 3
        await conn.execute(DOWN_SQL)
        assert await conn.fetchval(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND column_name='regime_logic_version'"
        ) == 0
        assert await conn.fetchval(
            "SELECT count(*) FROM pg_constraint "
            "WHERE conname IN ("
            "'signal_observation_pr22_regime_provenance_check',"
            "'daily_verdict_snapshot_pr22_regime_provenance_check')"
        ) == 0
        await conn.execute(DOWN_SQL)
        await conn.execute(UP_SQL)
        assert await conn.fetchval(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND column_name='regime_logic_version'"
        ) == 3
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_down_migration_fails_closed_with_new_research_evidence() -> None:
    conn, schema = await _connect("test_pr22_down_guard")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        await conn.execute(
            "INSERT INTO signal_observation(evidence_version,regime_logic_version) VALUES(3,2)"
        )
        with pytest.raises(asyncpg.PostgresError, match="refuses to destroy"):
            await conn.execute(DOWN_SQL)
        await conn.execute("ROLLBACK")
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_observation WHERE regime_logic_version=2"
        ) == 1
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_database_guards_reject_mixed_provenance() -> None:
    conn, schema = await _connect("test_pr22_integrity_guards")
    try:
        await conn.execute(PRE_PR22_SQL)
        await conn.execute(UP_SQL)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO signal_observation(
                  evidence_version,regime_score,regime_label,metrics_snapshot_ts
                ) VALUES(3,55,'legacy','2026-08-11 12:00+00')
                """
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO daily_verdict_snapshot(
                  logic_version,regime_score,regime_label,metrics_snapshot_ts
                ) VALUES('daily-verdict-v2',55,'legacy','2026-08-11 12:00+00')
                """
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO signal_observation(evidence_version,regime_logic_version) "
                "VALUES(3,1)"
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO daily_verdict_snapshot(logic_version,regime_logic_version) "
                "VALUES('daily-verdict-v2',1)"
            )
        await conn.execute("INSERT INTO signal_observation(evidence_version) VALUES(3)")
        await conn.execute(
            "INSERT INTO daily_verdict_snapshot(logic_version) "
            "VALUES('daily-verdict-v2')"
        )
        await conn.execute(
            "INSERT INTO signal_observation(evidence_version,regime_logic_version) "
            "VALUES(3,2)"
        )
        await conn.execute(
            "INSERT INTO daily_verdict_snapshot(logic_version,regime_logic_version) "
            "VALUES('daily-verdict-v2',2)"
        )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_fresh_schema_is_valid_and_idempotent() -> None:
    conn, schema = await _connect("test_pr22_fresh")
    try:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(SCHEMA_SQL)
        for table in (
            "metrics_snapshot",
            "signal_observation",
            "daily_verdict_snapshot",
        ):
            assert await conn.fetchval(
                "SELECT count(*)=1 FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name=$1 "
                "AND column_name='regime_logic_version'",
                table,
            )
        assert await conn.fetchval(
            "SELECT count(*) FROM metrics_snapshot WHERE regime_logic_version IS NOT NULL"
        ) == 0
        for table, constraint in (
            (
                "signal_observation",
                "signal_observation_pr24_regime_provenance_check",
            ),
            (
                "daily_verdict_snapshot",
                "daily_verdict_snapshot_pr24_regime_provenance_check",
            ),
        ):
            assert await conn.fetchval(
                "SELECT count(*)=1 FROM pg_constraint "
                "WHERE conrelid=$1::regclass AND conname=$2",
                table,
                constraint,
            )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_postgres_cvd_cutoff_excludes_later_trade_from_all_windows() -> None:
    conn, schema = await _connect("test_pr22_cvd_cutoff")
    try:
        await conn.execute(SCHEMA_SQL)
        cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        await conn.executemany(
            """
            INSERT INTO futures_trades_realtime(
              ts,symbol,exchange,buy_vol_usd,sell_vol_usd,
              large_buy_usd,large_sell_usd,trade_count,last_px,venue_count
            ) VALUES($1,'BTCUSDT_PERP.A','combined',$2,$3,0,0,1,100,2)
            """,
            [
                (cutoff - timedelta(seconds=10), 70.0, 30.0),
                (cutoff + timedelta(seconds=1), 1_000.0, 0.0),
            ],
        )
        values, lo, hi = await _cvd_src(
            conn, "futures_trades_realtime", "BTCUSDT_PERP.A", False, cutoff
        )
        assert lo == cutoff - timedelta(seconds=10)
        assert hi == cutoff - timedelta(seconds=10)
        for label, _seconds in _CVD_WINDOWS:
            assert values["combined"][label] == {
                "delta": 40.0,
                "volume": 100.0,
                "n": 1,
            }
        cvd_result = await cvd_matrix(conn, "BTCUSDT_PERP.A", cutoff)
        delta_result = await delta_matrix(
            conn, "BTCUSDT_PERP.A", [("30s", 30), ("1m", 60)], cutoff
        )
        assert cvd_result["as_of"] == cutoff.isoformat()
        assert {row["as_of"] for row in delta_result} == {cutoff.isoformat()}
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr22_market_structure_query_excludes_trade_after_as_of() -> None:
    conn, schema = await _connect("test_pr22_market_structure_cutoff")
    try:
        await conn.execute(SCHEMA_SQL)
        cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        await conn.executemany(
            """
            INSERT INTO futures_trades_realtime(
              ts,symbol,exchange,buy_vol_usd,sell_vol_usd,
              large_buy_usd,large_sell_usd,trade_count,last_px,venue_count
            ) VALUES($1,'BTCUSDT_PERP.A','combined',$2,$3,0,0,1,100,2)
            """,
            [
                (cutoff - timedelta(seconds=10), 70.0, 30.0),
                (cutoff + timedelta(seconds=1), 1_000.0, 0.0),
            ],
        )
        assert await _cvd_fut_window(
            conn, "BTCUSDT_PERP.A", 60, cutoff
        ) == pytest.approx(40.0)
    finally:
        await _drop(conn, schema)
