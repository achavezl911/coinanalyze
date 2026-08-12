from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

from app.scalp_collector import _write_combined_books
from app.scalp_logic import _binned, macro_context, scalp_context

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
UP_SQL = (
    ROOT / "sql/migrations/20260813_pr23_temporal_integrity.sql"
).read_text(encoding="utf-8")
DOWN_SQL = (
    ROOT / "sql/migrations/20260813_pr23_temporal_integrity_down.sql"
).read_text(encoding="utf-8")
SYMBOL = "BTCUSDT_PERP.A"


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _connect(prefix: str, *, full_schema: bool = False) -> tuple[asyncpg.Connection, str]:
    schema = f"{prefix}_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    if full_schema:
        await conn.execute(SCHEMA_SQL)
    return conn, schema


async def _drop(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


async def _insert_book(
    conn: asyncpg.Connection,
    *,
    exchange: str,
    ts: datetime,
    depth: float,
) -> None:
    await conn.execute(
        """
        INSERT INTO orderbook_snapshot(
          ts,symbol,exchange,venue_count,bid_px,ask_px,mid_px,spread_bps,
          bid_notional_l1,ask_notional_l1,bid_notional_l5,ask_notional_l5,
          bid_notional_l10,ask_notional_l10,imbalance_l1,imbalance_l5,imbalance_l10
        ) VALUES($1,$2,$3,1,99,101,100,200,$4,$4,$4,$4,$4,$4,0.5,0.5,0.5)
        """,
        ts,
        SYMBOL,
        exchange,
        depth,
    )


@pytest.mark.asyncio
async def test_future_venue_book_cannot_contaminate_combined() -> None:
    conn, schema = await _connect("test_pr23_combined_book", full_schema=True)
    try:
        now = await conn.fetchval("SELECT clock_timestamp()")
        await _insert_book(
            conn,
            exchange="binance",
            ts=now - timedelta(seconds=2),
            depth=10.0,
        )
        await _insert_book(
            conn,
            exchange="bybit",
            ts=now + timedelta(hours=1),
            depth=1_000.0,
        )

        await _write_combined_books(
            conn,
            [SimpleNamespace(symbol=SYMBOL)],  # type: ignore[list-item]
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM orderbook_snapshot WHERE exchange='combined'"
        ) == 0

        await _insert_book(
            conn,
            exchange="bybit",
            ts=now - timedelta(seconds=1),
            depth=20.0,
        )
        await _write_combined_books(
            conn,
            [SimpleNamespace(symbol=SYMBOL)],  # type: ignore[list-item]
        )
        combined = await conn.fetchrow(
            """
            SELECT venue_count,bid_notional_l1,ask_notional_l1
            FROM orderbook_snapshot WHERE exchange='combined'
            """
        )
        assert combined["venue_count"] == 2
        assert combined["bid_notional_l1"] == pytest.approx(30.0)
        assert combined["ask_notional_l1"] == pytest.approx(30.0)
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_scalp_context_excludes_every_row_after_as_of_and_future_book() -> None:
    conn, schema = await _connect("test_pr23_scalp_cutoff", full_schema=True)
    try:
        cutoff = await conn.fetchval("SELECT clock_timestamp()")
        cutoff_ms = int(cutoff.timestamp() * 1000)
        await conn.executemany(
            """
            INSERT INTO futures_trades_realtime(
              ts,symbol,exchange,venue_count,buy_vol_usd,sell_vol_usd,
              large_buy_usd,large_sell_usd,trade_count,last_px,last_event_ms
            ) VALUES($1,$2,'combined',2,$3,$4,0,0,1,$5,$6)
            """,
            [
                (cutoff - timedelta(seconds=10), SYMBOL, 70.0, 30.0, 100.0, cutoff_ms - 10_000),
                (cutoff + timedelta(seconds=1), SYMBOL, 1_000.0, 0.0, 999.0, cutoff_ms + 1_000),
            ],
        )
        await conn.executemany(
            """
            INSERT INTO spot_trades_realtime(
              ts,symbol,exchange,venue_count,buy_vol_usd,sell_vol_usd,
              inst_buy_usd,inst_sell_usd,trade_count,last_px,last_event_ms
            ) VALUES($1,'BTC','combined',2,$2,$3,0,0,1,$4,$5)
            """,
            [
                (cutoff - timedelta(seconds=10), 60.0, 40.0, 100.0, cutoff_ms - 10_000),
                (cutoff + timedelta(seconds=1), 2_000.0, 0.0, 999.0, cutoff_ms + 1_000),
            ],
        )
        await conn.executemany(
            """
            INSERT INTO ohlcv(
              ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
            ) VALUES($1,$2,'1min',$3,$3,$3,$3,10,5,1,1)
            """,
            [
                (cutoff - timedelta(minutes=1), SYMBOL, 100.0),
                (cutoff + timedelta(minutes=1), SYMBOL, 999.0),
            ],
        )
        await conn.executemany(
            """
            INSERT INTO liquidations_realtime(
              ts,symbol,exchange,side,notional_usd,price,qty,event_id
            ) VALUES($1,$2,'binance','long',$3,100,1,$4)
            """,
            [
                (cutoff - timedelta(seconds=30), SYMBOL, 10.0, "past"),
                (cutoff + timedelta(seconds=1), SYMBOL, 1_000.0, "future"),
            ],
        )
        await conn.execute(
            """
            INSERT INTO orderbook_snapshot(
              ts,symbol,exchange,venue_count,bid_px,ask_px,mid_px,spread_bps
            ) VALUES($1,$2,'combined',2,99,101,100,200)
            """,
            cutoff + timedelta(seconds=1),
            SYMBOL,
        )

        context = await scalp_context(conn, SYMBOL, cutoff)

        assert context["price"] == pytest.approx(100.0)
        assert context["fut_price"] == pytest.approx(100.0)
        assert context["spot_price"] == pytest.approx(100.0)
        assert context["fut_delta_1m"] == pytest.approx(40.0)
        assert context["fut_delta_3m"] == pytest.approx(40.0)
        assert context["spot_delta_3m"] == pytest.approx(20.0)
        assert context["long_liq"] == pytest.approx(10.0)
        assert context["book_status"] == "missing"
        assert context["book_lag_seconds"] is None
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_swing_intraday_and_daily_sources_stop_at_as_of() -> None:
    conn, schema = await _connect("test_pr23_swing_cutoff", full_schema=True)
    try:
        cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
        await conn.executemany(
            """
            INSERT INTO ohlcv(
              ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
            ) VALUES($1,$2,'1min',$3,$3,$3,$3,10,5,1,1)
            """,
            [
                (cutoff - timedelta(minutes=5), SYMBOL, 100.0),
                (cutoff + timedelta(minutes=5), SYMBOL, 999.0),
            ],
        )
        await conn.executemany(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,cvd_spot_usd,cvd_fut_usd,inst_delta_usd,
              price_open,price_close,oi_open,oi_close,fr_avg
            ) VALUES($1,$2,10,5,1,100,$3,1000,1010,0.01)
            """,
            [
                (datetime(2026, 8, 10, tzinfo=UTC).date(), SYMBOL, 101.0),
                (datetime(2026, 8, 11, tzinfo=UTC).date(), SYMBOL, 999.0),
            ],
        )

        intraday = await _binned(conn, SYMBOL, 3600, 300, cutoff)
        macro = await macro_context(conn, SYMBOL, as_of=cutoff)

        assert [close for _bucket, close in intraday] == [100.0]
        assert macro["session_date"] == "2026-08-10"
        assert macro["as_of"] == cutoff.isoformat()
    finally:
        await _drop(conn, schema)


PRE_PR23_SQL = """
CREATE TABLE signal_observation (
  observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  evidence_version smallint NOT NULL,
  regime_score double precision,
  regime_label text,
  metrics_snapshot_ts timestamptz,
  price_cutoff_at timestamptz,
  metrics_cutoff_at timestamptz,
  regime_logic_version smallint,
  CONSTRAINT signal_observation_pr22_regime_provenance_check CHECK (
    evidence_version <> 3 OR regime_logic_version IS NOT DISTINCT FROM 2 OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  )
);
CREATE TABLE daily_verdict_snapshot (
  snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  logic_version text NOT NULL,
  regime_score double precision,
  regime_label text,
  metrics_snapshot_ts timestamptz,
  regime_logic_version smallint,
  CONSTRAINT daily_verdict_snapshot_pr22_regime_provenance_check CHECK (
    logic_version <> 'daily-verdict-v2' OR regime_logic_version IS NOT DISTINCT FROM 2 OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  )
);
INSERT INTO signal_observation(evidence_version) VALUES(1),(2),(3);
INSERT INTO daily_verdict_snapshot(logic_version)
VALUES('daily-verdict-v1'),('daily-verdict-v2');
"""


@pytest.mark.asyncio
async def test_pr23_constraints_preserve_history_and_guard_new_versions() -> None:
    conn, schema = await _connect("test_pr23_versions")
    try:
        await conn.execute(PRE_PR23_SQL)
        before_signal = await conn.fetch(
            "SELECT evidence_version,regime_logic_version FROM signal_observation ORDER BY 1"
        )
        before_daily = await conn.fetch(
            "SELECT logic_version,regime_logic_version FROM daily_verdict_snapshot ORDER BY 1"
        )

        await conn.execute(UP_SQL)
        await conn.execute(UP_SQL)

        assert await conn.fetch(
            "SELECT evidence_version,regime_logic_version FROM signal_observation ORDER BY 1"
        ) == before_signal
        assert await conn.fetch(
            "SELECT logic_version,regime_logic_version FROM daily_verdict_snapshot ORDER BY 1"
        ) == before_daily
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO signal_observation(evidence_version,regime_logic_version) VALUES(4,1)"
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO daily_verdict_snapshot(logic_version,regime_logic_version) "
                "VALUES('daily-verdict-v3',1)"
            )
        await conn.execute(
            "INSERT INTO signal_observation(evidence_version,regime_logic_version) VALUES(4,2)"
        )
        await conn.execute(
            "INSERT INTO daily_verdict_snapshot(logic_version,regime_logic_version) "
            "VALUES('daily-verdict-v3',2)"
        )

        with pytest.raises(asyncpg.PostgresError, match="refuses to loosen"):
            await conn.execute(DOWN_SQL)
        await conn.execute("ROLLBACK")
        assert await conn.fetchval(
            "SELECT count(*) FROM signal_observation WHERE evidence_version=4"
        ) == 1
        assert await conn.fetchval(
            "SELECT count(*) FROM daily_verdict_snapshot "
            "WHERE logic_version='daily-verdict-v3'"
        ) == 1
    finally:
        await _drop(conn, schema)
