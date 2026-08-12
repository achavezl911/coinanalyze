from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

import app.api as api
import app.daily_agg as daily_agg
from app.ai_context import verdict_history
from app.daily_agg import compute_session, persist_verdicts
from app.metrics import session_bounds
from app.scalp_logic import scalp_context
from app.signal_ledger import select_reference_price

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
UP_SQL = (
    ROOT / "sql/migrations/20260814_pr24_daily_historical_integrity.sql"
).read_text(encoding="utf-8")
DOWN_SQL = (
    ROOT / "sql/migrations/20260814_pr24_daily_historical_integrity_down.sql"
).read_text(encoding="utf-8")
SYMBOL = "BTCUSDT_PERP.A"


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _connect(prefix: str, *, full_schema: bool = True) -> tuple[asyncpg.Connection, str]:
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


async def _observation(
    conn: asyncpg.Connection,
    session_date_value: date,
    *,
    status: str = "COMPLETE",
    present: bool = True,
    returned: int = 0,
    accepted: int = 0,
    start_shift: timedelta = timedelta(),
    end_shift: timedelta = timedelta(),
) -> tuple[datetime, datetime]:
    start, end = session_bounds(session_date_value)
    source_start = start + start_shift
    source_end = end + end_shift
    await conn.execute(
        """
        INSERT INTO liquidation_history_observation(
          symbol,source_start_at,source_cutoff_at,observed_at,status,
          response_symbol_present,returned_rows,accepted_rows
        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        SYMBOL,
        source_start,
        source_end,
        max(source_end, end) + timedelta(minutes=1),
        status,
        present,
        returned,
        accepted,
    )
    return source_start, source_end


async def _partial_price(conn: asyncpg.Connection, session_date_value: date) -> None:
    start, _ = session_bounds(session_date_value)
    await conn.execute(
        """
        INSERT INTO ohlcv(
          ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
        ) VALUES($1,$2,'1min',100,101,99,100,1,0.5,1,1)
        """,
        start,
        SYMBOL,
    )


@pytest.mark.asyncio
async def test_daily_projection_preserves_created_at_and_advances_updated_at() -> None:
    conn, schema = await _connect("test_pr24_daily_metadata")
    try:
        session_date_value = date(2026, 8, 11)
        await _observation(conn, session_date_value)
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        first = await conn.fetchrow(
            "SELECT created_at,updated_at FROM daily_session_agg WHERE symbol=$1",
            SYMBOL,
        )
        await conn.execute("SELECT pg_sleep(0.01)")
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        second = await conn.fetchrow(
            "SELECT created_at,updated_at FROM daily_session_agg WHERE symbol=$1",
            SYMBOL,
        )
        assert second["created_at"] == first["created_at"]
        assert second["updated_at"] > first["updated_at"]
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("events", "expected"),
    [([], (0.0, 0.0)), ([(20.0, 30.0), (5.0, 7.0)], (25.0, 37.0))],
)
async def test_complete_liquidation_window_publishes_measured_total(
    events: list[tuple[float, float]], expected: tuple[float, float]
) -> None:
    conn, schema = await _connect("test_pr24_liq_complete")
    try:
        session_date_value = date(2026, 8, 11)
        start, _ = session_bounds(session_date_value)
        await _observation(
            conn,
            session_date_value,
            returned=len(events),
            accepted=len(events),
        )
        for offset, (long_liq, short_liq) in enumerate(events):
            await conn.execute(
                """
                INSERT INTO liquidations(ts,symbol,interval,long_liq,short_liq)
                VALUES($1,$2,'5min',$3,$4)
                """,
                start + timedelta(minutes=5 * offset),
                SYMBOL,
                long_liq,
                short_liq,
            )
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        row = await conn.fetchrow(
            """
            SELECT long_liq_usd,short_liq_usd,liquidation_coverage_version,
                   liquidation_observed_start_at,liquidation_observed_end_at
            FROM daily_session_agg WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        )
        assert (row["long_liq_usd"], row["short_liq_usd"]) == pytest.approx(expected)
        assert row["liquidation_coverage_version"] == 1
        assert row["liquidation_observed_start_at"] <= start
        assert row["liquidation_observed_end_at"] >= session_bounds(session_date_value)[1]
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_liquidation_history_observation_is_append_only() -> None:
    conn, schema = await _connect("test_pr24_liq_append_only")
    try:
        await _observation(conn, date(2026, 8, 11))
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute(
                "UPDATE liquidation_history_observation SET returned_rows=1"
            )
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("DELETE FROM liquidation_history_observation")
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observation",
    [
        {"end_shift": timedelta(minutes=-5)},
        {"status": "INCOMPLETE", "present": False},
        {"status": "INCOMPLETE", "present": True, "returned": 2, "accepted": 1},
    ],
)
async def test_unproven_liquidation_window_never_publishes_partial_sum(
    observation: dict[str, Any],
) -> None:
    conn, schema = await _connect("test_pr24_liq_incomplete")
    try:
        session_date_value = date(2026, 8, 11)
        start, _ = session_bounds(session_date_value)
        await _observation(conn, session_date_value, **observation)
        await _partial_price(conn, session_date_value)
        await conn.execute(
            """
            INSERT INTO liquidations(ts,symbol,interval,long_liq,short_liq)
            VALUES($1,$2,'5min',999,888)
            """,
            start,
            SYMBOL,
        )
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        row = await conn.fetchrow(
            """
            SELECT long_liq_usd,short_liq_usd,liquidation_coverage_version
            FROM daily_session_agg WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        )
        assert row["long_liq_usd"] is None
        assert row["short_liq_usd"] is None
        assert row["liquidation_coverage_version"] is None
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_liquidation_proof_must_cover_whole_dst_session() -> None:
    conn, schema = await _connect("test_pr24_liq_dst")
    try:
        session_date_value = date(2026, 11, 1)
        start, end = session_bounds(session_date_value)
        assert end - start == timedelta(hours=25)
        await _observation(
            conn,
            session_date_value,
            start_shift=timedelta(minutes=1),
        )
        await _partial_price(conn, session_date_value)
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        assert await conn.fetchval(
            """
            SELECT liquidation_coverage_version FROM daily_session_agg
            WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        ) is None
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_failed_refresh_does_not_degrade_previously_proven_liquidations() -> None:
    conn, schema = await _connect("test_pr24_liq_preserve")
    try:
        session_date_value = date(2026, 8, 11)
        start, end = session_bounds(session_date_value)
        await conn.execute(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,long_liq_usd,short_liq_usd,
              liquidation_coverage_version,liquidation_observed_start_at,
              liquidation_observed_end_at
            ) VALUES($1,$2,10,20,1,$3,$4)
            """,
            session_date_value,
            SYMBOL,
            start,
            end,
        )
        await _partial_price(conn, session_date_value)
        # No durable observation is available to this refresh, but the previously validated
        # projection already carries complete provenance and must not be degraded.
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        row = await conn.fetchrow(
            """
            SELECT long_liq_usd,short_liq_usd,liquidation_coverage_version,
                   liquidation_observed_start_at,liquidation_observed_end_at
            FROM daily_session_agg WHERE symbol=$1
            """,
            SYMBOL,
        )
        assert (row["long_liq_usd"], row["short_liq_usd"]) == pytest.approx((10, 20))
        assert row["liquidation_coverage_version"] == 1
        assert (row["liquidation_observed_start_at"], row["liquidation_observed_end_at"]) == (
            start,
            end,
        )
    finally:
        await _drop(conn, schema)


async def _no_swing(_conn: asyncpg.Connection, _symbol: str) -> dict[str, Any]:
    return {
        "bias": "NEUTRAL",
        "score": 0.0,
        "conviction": "baja",
        "long_share_pct": 50.0,
        "components": [],
    }


@pytest.mark.asyncio
async def test_session_and_verdict_snapshot_freeze_same_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr24_daily_snapshot")
    try:
        session_date_value = date(2026, 8, 11)
        start, end = session_bounds(session_date_value)
        await conn.execute(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,price_open,price_high,price_low,price_close,
              long_liq_usd,short_liq_usd,liquidation_coverage_version,
              liquidation_observed_start_at,liquidation_observed_end_at
            ) VALUES($1,$2,100,101,99,100,10,20,1,$3,$4)
            """,
            session_date_value,
            SYMBOL,
            start,
            end,
        )
        monkeypatch.setattr(daily_agg, "latest_closed_session_date", lambda: session_date_value)
        monkeypatch.setattr(daily_agg, "swing_score", _no_swing)
        assert await persist_verdicts(conn, (SYMBOL,)) == 1
        frozen = await conn.fetchrow(
            """
            SELECT s.observed_at,s.price_close,s.long_liq_usd,
                   s.liquidation_coverage_version,v.observed_at AS verdict_observed_at
            FROM daily_session_snapshot s
            JOIN daily_verdict_snapshot v USING(symbol,session_date)
            """
        )
        assert frozen["observed_at"] == frozen["verdict_observed_at"]
        assert frozen["price_close"] == 100
        assert frozen["long_liq_usd"] == 10
        assert frozen["liquidation_coverage_version"] == 1

        await conn.execute(
            """
            UPDATE daily_session_agg SET price_close=120,long_liq_usd=999,
              updated_at=clock_timestamp() WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        )
        assert await persist_verdicts(conn, (SYMBOL,)) == 1
        rerun = await conn.fetchrow(
            "SELECT price_close,long_liq_usd,observed_at FROM daily_session_snapshot"
        )
        assert (rerun["price_close"], rerun["long_liq_usd"]) == (100, 10)
        assert rerun["observed_at"] == frozen["observed_at"]
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("UPDATE daily_session_snapshot SET price_close=999")
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("DELETE FROM daily_session_snapshot")
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_daily_api_pit_statistics_and_streak_use_only_snapshot_cohort() -> None:
    conn, schema = await _connect("test_pr24_daily_api_pit")
    try:
        await conn.executemany(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,cvd_spot_usd,cvd_fut_usd,inst_delta_usd,
              price_open,price_close
            ) VALUES($1,$2,$3,$4,0,100,$5)
            """,
            [
                (date(2026, 7, 31), SYMBOL, -100.0, -100.0, 99.0),
                (date(2026, 8, 1), SYMBOL, 100.0, 100.0, 101.0),
            ],
        )
        for session_date_value, spot, futures, close in (
            (date(2026, 8, 1), 1.0, 1.0, 101.0),
            (date(2026, 8, 2), 2.0, 2.0, 102.0),
            (date(2026, 8, 3), 0.0, 0.0, 100.0),
        ):
            _, end = session_bounds(session_date_value)
            await conn.execute(
                """
                INSERT INTO daily_session_snapshot(
                  symbol,session_date,snapshot_version,observed_at,session_end_at,
                  cvd_spot_usd,cvd_fut_usd,cvd_diff_usd,inst_delta_usd,
                  price_open,price_high,price_low,price_close,price_chg_pct
                ) VALUES(
                  $1,$2,1,$3,$3,$4,$5,$4::float8-$5::float8,0,100,
                  $6,$6,$6,($6::float8-100)
                )
                """,
                SYMBOL,
                session_date_value,
                end + timedelta(minutes=1),
                spot,
                futures,
                close,
            )

        historical = await api.daily_data(conn, SYMBOL, 60, date(2026, 8, 2))
        assert [row["session_date"] for row in historical["rows"]] == [
            date(2026, 8, 1),
            date(2026, 8, 2),
        ]
        assert historical["streak"] == 2
        assert historical["rows"][0]["cvd_spot_percentile"] == 0
        assert historical["rows"][1]["cvd_spot_percentile"] == 100
        assert historical["semantics"] == "prospective_first_observation"

        with_zero = await api.daily_data(conn, SYMBOL, 60, date(2026, 8, 3))
        zero = with_zero["rows"][-1]
        assert zero["flow_direction"] == "neutral"
        assert zero["price_response"] == "neutral"

        mutable = await api.daily_data(conn, SYMBOL, 60)
        assert mutable["semantics"] == "mutable_latest_projection"
        assert [row["session_date"] for row in mutable["rows"]] == [
            date(2026, 7, 31),
            date(2026, 8, 1),
        ]
    finally:
        await _drop(conn, schema)


class _PoolContext:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    def acquire(self) -> _PoolContext:
        return self

    async def __aenter__(self) -> asyncpg.Connection:
        return self.conn

    async def __aexit__(self, *_args: object) -> None:
        return None


async def _daily_snapshot(
    conn: asyncpg.Connection, session_date_value: date, price: float
) -> None:
    _, end = session_bounds(session_date_value)
    await conn.execute(
        """
        INSERT INTO daily_session_snapshot(
          symbol,session_date,snapshot_version,observed_at,session_end_at,price_close
        ) VALUES($1,$2,1,$3,$3,$4)
        """,
        SYMBOL,
        session_date_value,
        end + timedelta(minutes=1),
        price,
    )


@pytest.mark.asyncio
async def test_forward_returns_require_exact_immutable_calendar_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr24_returns")
    try:
        origin = date(2026, 8, 1)
        _, origin_end = session_bounds(origin)
        await conn.execute(
            """
            INSERT INTO daily_verdict_snapshot(
              session_date,symbol,snapshot_version,logic_version,observed_at,
              session_end_at,reference_price,reference_price_at
            ) VALUES($1,$2,1,'daily-verdict-v4',$3,$4,100,$4)
            """,
            origin,
            SYMBOL,
            origin_end + timedelta(minutes=1),
            origin_end,
        )
        await _daily_snapshot(conn, origin + timedelta(days=7), 107)
        await _daily_snapshot(conn, origin + timedelta(days=15), 999)
        await conn.execute(
            """
            INSERT INTO daily_session_agg(session_date,symbol,price_open,price_close)
            VALUES($1,$2,100,500)
            """,
            origin + timedelta(days=7),
            SYMBOL,
        )
        monkeypatch.setattr(api.app.state, "pool", _PoolContext(conn), raising=False)
        result = await api.verdicts(SYMBOL, 10, "daily-verdict-v4")
        row = result["rows"][0]
        assert row["fwd_return_7s_pct"] == pytest.approx(7.0)
        assert row["fwd_return_14s_pct"] is None

        await conn.execute(
            "UPDATE daily_session_agg SET price_close=900 WHERE symbol=$1",
            SYMBOL,
        )
        unchanged = (await api.verdicts(SYMBOL, 10, "daily-verdict-v4"))["rows"][0]
        assert unchanged["fwd_return_7s_pct"] == pytest.approx(7.0)
        await _daily_snapshot(conn, origin + timedelta(days=14), 114)
        complete = (await api.verdicts(SYMBOL, 10, "daily-verdict-v4"))["rows"][0]
        assert complete["fwd_return_14s_pct"] == pytest.approx(14.0)
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_verdict_consumers_never_mix_logic_cohorts(monkeypatch: pytest.MonkeyPatch) -> None:
    conn, schema = await _connect("test_pr24_cohorts")
    try:
        for offset, version in enumerate(("daily-verdict-v1", "daily-verdict-v4")):
            session_date_value = date(2026, 8, 1 + offset)
            _, end = session_bounds(session_date_value)
            await conn.execute(
                """
                INSERT INTO daily_verdict_snapshot(
                  session_date,symbol,snapshot_version,logic_version,observed_at,session_end_at
                ) VALUES($1,$2,1,$3,$4,$4)
                """,
                session_date_value,
                SYMBOL,
                version,
                end + timedelta(minutes=1),
            )
        monkeypatch.setattr(api.app.state, "pool", _PoolContext(conn), raising=False)
        current = await api.verdicts(SYMBOL, 90, "daily-verdict-v4")
        old = await api.verdicts(SYMBOL, 90, "daily-verdict-v1")
        ai_current = await verdict_history(conn, SYMBOL, 90)
        assert {row["logic_version"] for row in current["rows"]} == {"daily-verdict-v4"}
        assert {row["logic_version"] for row in old["rows"]} == {"daily-verdict-v1"}
        assert {row["logic_version"] for row in ai_current["series"]} == {
            "daily-verdict-v4"
        }
        assert await conn.fetchval(
            "SELECT count(*) FROM daily_verdict_snapshot WHERE logic_version='daily-verdict-v1'"
        ) == 1
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_scalp_ohlcv_fallback_excludes_open_bar_and_carries_close_time() -> None:
    conn, schema = await _connect("test_pr24_ohlcv_reference")
    try:
        cutoff = datetime(2026, 8, 11, 12, 5, tzinfo=UTC)
        await conn.executemany(
            """
            INSERT INTO ohlcv(
              ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
            ) VALUES($1,$2,'1min',$3,$3,$3,$3,1,0.5,1,1)
            """,
            [
                (cutoff - timedelta(minutes=1), SYMBOL, 100.0),
                (cutoff, SYMBOL, 999.0),
            ],
        )
        context = await scalp_context(conn, SYMBOL, cutoff)
        assert context["ohlcv_price"] == 100
        assert context["ohlcv_price_at"] == cutoff
        price, source, reference_at = select_reference_price(
            context,
            {
                "fut_price": None,
                "basis_detail": {
                    "fut_age_seconds": None,
                    "stale_after_seconds": 30.0,
                },
            },
        )
        assert (price, source, reference_at) == (
            100,
            "ohlcv_1min_latest_closed",
            cutoff,
        )
        assert reference_at <= datetime.fromtimestamp(context["now_ms"] / 1000, UTC)
    finally:
        await _drop(conn, schema)


PRE_PR24_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
  SELECT value NOT IN ('NaN'::float8,'Infinity'::float8,'-Infinity'::float8)
$$;
CREATE TABLE symbols(symbol text PRIMARY KEY);
INSERT INTO symbols VALUES('BTCUSDT_PERP.A');
CREATE TABLE daily_session_agg(
  symbol text NOT NULL REFERENCES symbols(symbol), session_date date NOT NULL,
  long_liq_usd float8, short_liq_usd float8,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(symbol,session_date)
);
CREATE TABLE signal_observation(
  observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  evidence_version smallint NOT NULL, observed_at timestamptz,
  reference_price float8,reference_price_source text,reference_price_at timestamptz,
  regime_logic_version smallint,
  regime_score float8,regime_label text,metrics_snapshot_ts timestamptz,
  price_cutoff_at timestamptz,metrics_cutoff_at timestamptz,
  CONSTRAINT signal_observation_pr23_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4) OR regime_logic_version IS NOT DISTINCT FROM 2 OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  )
);
CREATE TABLE daily_verdict_snapshot(
  snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  logic_version text NOT NULL,regime_logic_version smallint,
  regime_score float8,regime_label text,metrics_snapshot_ts timestamptz,
  CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3')
    OR regime_logic_version IS NOT DISTINCT FROM 2 OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  )
);
"""


@pytest.mark.asyncio
async def test_pr24_migration_up_twice_down_empty_and_reup() -> None:
    conn, schema = await _connect("test_pr24_migration_cycle", full_schema=False)
    try:
        await conn.execute(PRE_PR24_SQL)
        await conn.execute(
            "INSERT INTO daily_session_agg(symbol,session_date) VALUES($1,'2026-08-01')",
            SYMBOL,
        )
        created = await conn.fetchval("SELECT created_at FROM daily_session_agg")
        await conn.execute(UP_SQL)
        await conn.execute(UP_SQL)
        assert await conn.fetchval("SELECT updated_at FROM daily_session_agg") == created
        assert await conn.fetchval("SELECT to_regclass('daily_session_snapshot') IS NOT NULL")
        assert await conn.fetchval(
            "SELECT to_regclass('liquidation_history_observation') IS NOT NULL"
        )
        await conn.execute(DOWN_SQL)
        await conn.execute(DOWN_SQL)
        assert not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='daily_session_agg' "
            "AND column_name='updated_at')"
        )
        await conn.execute(UP_SQL)
        assert await conn.fetchval("SELECT updated_at FROM daily_session_agg") == created
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_pr24_fresh_schema_and_up_are_idempotent() -> None:
    conn, schema = await _connect("test_pr24_fresh_schema")
    try:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(UP_SQL)
        await conn.execute(UP_SQL)
        columns = {
            row["column_name"]
            for row in await conn.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema=current_schema() AND table_name='daily_session_snapshot'
                """
            )
        }
        assert {
            "cvd_diff_2v_usd",
            "price_chg_pct",
            "oi_chg_usd",
            "funding_5m_samples",
            "liquidation_coverage_version",
        } <= columns
        assert await conn.fetchval(
            "SELECT to_regclass('liquidation_history_observation') IS NOT NULL"
        )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_v5_reference_constraint_rejects_missing_or_future_timestamp() -> None:
    conn, schema = await _connect("test_pr24_v5_reference_guard", full_schema=False)
    try:
        await conn.execute(PRE_PR24_SQL)
        await conn.execute(UP_SQL)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO signal_observation(
                  evidence_version,observed_at,reference_price,reference_price_source
                ) VALUES(5,'2026-08-01 00:01+00',100,'ohlcv_1min_latest_closed')
                """
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO signal_observation(
                  evidence_version,observed_at,reference_price,reference_price_source,
                  reference_price_at
                ) VALUES(
                  5,'2026-08-01 00:01+00',100,'ohlcv_1min_latest_closed',
                  '2026-08-01 00:02+00'
                )
                """
            )
        await conn.execute(
            """
            INSERT INTO signal_observation(
              evidence_version,observed_at,reference_price,reference_price_source,
              reference_price_at
            ) VALUES(
              5,'2026-08-01 00:01+00',100,'ohlcv_1min_latest_closed',
              '2026-08-01 00:01+00'
            )
            """
        )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence_kind", ["signal", "verdict", "session", "liquidation"])
async def test_pr24_down_refuses_each_kind_of_evidence(evidence_kind: str) -> None:
    conn, schema = await _connect("test_pr24_migration_guard", full_schema=False)
    try:
        await conn.execute(PRE_PR24_SQL)
        await conn.execute(UP_SQL)
        if evidence_kind == "signal":
            await conn.execute("INSERT INTO signal_observation(evidence_version) VALUES(5)")
        elif evidence_kind == "verdict":
            await conn.execute(
                "INSERT INTO daily_verdict_snapshot(logic_version) VALUES('daily-verdict-v4')"
            )
        elif evidence_kind == "session":
            await conn.execute(
                """
                INSERT INTO daily_session_snapshot(
                  symbol,session_date,snapshot_version,observed_at,session_end_at
                ) VALUES($1,'2026-08-01',1,'2026-08-02 00:00+00','2026-08-01 00:00+00')
                """,
                SYMBOL,
            )
        else:
            await conn.execute(
                """
                INSERT INTO liquidation_history_observation(
                  symbol,source_start_at,source_cutoff_at,observed_at,status,
                  response_symbol_present,returned_rows,accepted_rows
                ) VALUES(
                  $1,'2026-08-01 00:00+00','2026-08-02 00:00+00',
                  '2026-08-02 00:01+00','COMPLETE',true,0,0
                )
                """,
                SYMBOL,
            )
        with pytest.raises(asyncpg.PostgresError, match="PR24 down migration refuses"):
            await conn.execute(DOWN_SQL)
        await conn.execute("ROLLBACK")
        assert await conn.fetchval("SELECT to_regclass('daily_session_snapshot') IS NOT NULL")
    finally:
        await _drop(conn, schema)
