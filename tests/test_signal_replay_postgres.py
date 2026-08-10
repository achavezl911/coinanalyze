from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

from app.scalp_logic import compute_scalp_summary
from app.signal_ledger import persist_signal_observations
from app.signal_replay import (
    REPLAY_CONTEXT_VERSION,
    replay_context_as_of,
    replay_signal_observation,
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

CREATE TABLE metrics_snapshot (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    regime_score double precision,
    regime_label text,
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    PRIMARY KEY(symbol, ts)
);
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_signal_replay_{uuid.uuid4().hex}"


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


def _ctx() -> dict[str, object]:
    now_ms = datetime.now(UTC).timestamp() * 1000.0
    return {
        "now_ms": now_ms,
        "price": 100.0,
        "ohlcv_price": 99.9,
        "fut_price": 100.0,
        "spot_price": 99.9,
        "fut_event_ms": now_ms - 1_000,
        "spot_event_ms": now_ms - 1_200,
        "fut_delta_1m": 100.0,
        "fut_volume_1m": 1_000.0,
        "fut_delta_3m": 150.0,
        "fut_volume_3m": 3_000.0,
        "spot_delta_3m": 50.0,
        "spot_volume_3m": 2_000.0,
        "imbalance_l1": 0.05,
        "imbalance_l5": 0.10,
        "imbalance_l10": 0.08,
        "spread_bps": 1.5,
        "book_status": "ok",
        "book_lag_seconds": 1.0,
        "first_px_3m": 99.8,
        "last_px_3m": 100.0,
        "bars_15m": 0,
        "price_move_15m_coverage": "none",
        "oi_window_status": "unavailable",
        "optional": None,
    }


async def _persist_consistent(
    conn: asyncpg.Connection,
) -> tuple[int, dict[str, object], dict[str, object]]:
    ctx = _ctx()
    summary = compute_scalp_summary(ctx)
    inserted = await persist_signal_observations(
        conn,
        "BTCUSDT_PERP.A",
        ctx,
        summary,
        collector_generation=1,
        collector_shard_index=0,
        collector_shard_count=1,
    )
    assert inserted == 1
    observation_id = int(
        await conn.fetchval(
            "SELECT observation_id FROM signal_observation ORDER BY observation_id DESC LIMIT 1"
        )
    )
    return observation_id, ctx, summary


@pytest.mark.asyncio
async def test_frame_is_ordinary_one_to_one_and_schema_is_idempotent() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        assert await conn.fetchval(
            "SELECT relkind FROM pg_class WHERE oid='signal_replay_frame'::regclass"
        ) == b"r"

        observation_id, _ctx_row, _summary = await _persist_consistent(conn)
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_replay_frame WHERE observation_id=$1",
            observation_id,
        ) == 1

        await conn.execute(REPLAY_DDL)
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_replay_frame WHERE observation_id=$1",
            observation_id,
        ) == 1
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_replay_recomputes_exact_immutable_evidence() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        observation_id, ctx, summary = await _persist_consistent(conn)
        result = await replay_signal_observation(conn, observation_id)

        assert result.observation_id == observation_id
        assert result.context_version == REPLAY_CONTEXT_VERSION
        assert result.context_hash_valid is True
        assert result.evidence_match is True
        assert result.expected_evidence_hash == result.replayed_evidence_hash
        assert result.replayed_summary == summary

        frame = await conn.fetchrow(
            """
            SELECT context_as_of,context
            FROM signal_replay_frame
            WHERE observation_id=$1
            """,
            observation_id,
        )
        assert frame["context_as_of"] == replay_context_as_of(ctx)
        payload = frame["context"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["optional"] is None
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_replay_frame_rejects_update_delete_and_truncate() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        await _persist_consistent(conn)
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE signal_replay_frame SET context_version=2"
            )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("DELETE FROM signal_replay_frame")
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("TRUNCATE signal_replay_frame")
        assert await conn.fetchval("SELECT count(*) FROM signal_replay_frame") == 1
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_schema_never_backfills_old_observation_context() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        observation_id = int(
            await conn.fetchval(
                """
                INSERT INTO signal_observation(
                  observed_at,observed_minute,symbol,signal_family,
                  is_periodic,is_transition,
                  logic_version,evidence_version,sampling_version,
                  decision_status,direction,actionable,state,confidence,reason,
                  long_score,short_score,evidence_coverage_pct,
                  collector_shard_index,collector_shard_count,
                  decision_fingerprint,evidence
                ) VALUES(
                  clock_timestamp(),date_trunc('minute',clock_timestamp()),
                  'BTCUSDT_PERP.A','scalp',
                  true,false,
                  'scalp-summary-v1',1,1,
                  'evaluable','neutral',false,'No Trade','baja','pre-PR6 observation',
                  50,50,80,
                  0,1,repeat('a',64),'{}'::jsonb
                )
                RETURNING observation_id
                """
            )
        )
        await conn.execute(REPLAY_DDL)
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_replay_frame WHERE observation_id=$1",
            observation_id,
        ) == 0
        with pytest.raises(LookupError, match="no replay frame"):
            await replay_signal_observation(conn, observation_id)
    finally:
        await _drop_schema(conn, schema)
