from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

import app.api as api
from app.ai_context import verdict_history
from app.daily_agg import compute_session, materialize_daily_verdict_outcomes
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


async def _publish_liquidation_observation(
    conn: asyncpg.Connection,
    session_date_value: date,
    *,
    status: str = "ok",
    requested: list[str] | None = None,
    observed: list[str] | None = None,
    returned_rows: int = 0,
    accepted_rows: int | None = None,
    start_shift: timedelta = timedelta(),
    cutoff_shift: timedelta = timedelta(),
    valid_detail: bool = True,
) -> tuple[datetime, datetime, datetime]:
    start, end = session_bounds(session_date_value)
    source_start = start + start_shift
    source_cutoff = end + cutoff_shift
    observed_at = max(end, source_cutoff) + timedelta(minutes=1)
    requested = requested if requested is not None else [SYMBOL]
    observed = observed if observed is not None else list(requested)
    accepted_rows = returned_rows if accepted_rows is None else accepted_rows
    detail: dict[str, object] = {
        "source_start_ts": int(source_start.timestamp()),
        "source_cutoff_ts": int(source_cutoff.timestamp()),
        "requested_symbols": len(requested),
        "observed_symbols": len(observed),
        "requested_symbol_names": requested,
        "observed_symbol_names": observed,
        "missing_symbols": sorted(set(requested) - set(observed)),
        "returned_rows": returned_rows,
        "accepted_rows": accepted_rows,
        "reason": "complete_observation",
    }
    if not valid_detail:
        detail.pop("observed_symbol_names")
    await conn.execute(
        """
        INSERT INTO pipeline_heartbeat(service,updated_at,status,detail)
        VALUES('ingest:liquidations_history',$1,$2,$3)
        ON CONFLICT(service) DO UPDATE SET
          updated_at=EXCLUDED.updated_at,status=EXCLUDED.status,detail=EXCLUDED.detail
        """,
        observed_at,
        status,
        json.dumps(detail, separators=(",", ":"), sort_keys=True),
    )
    return source_start, source_cutoff, observed_at


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


async def _projection(
    conn: asyncpg.Connection,
    session_date_value: date,
    price: float,
    *,
    coverage_version: int = 2,
) -> None:
    await conn.execute(
        """
        INSERT INTO daily_session_agg(
          session_date,symbol,price_open,price_close,session_coverage_version,
          session_expected_minutes,futures_ohlcv_minutes,spot_2v_minutes,
          cvd_fut_2v_minutes,session_expected_5m_samples,oi_5m_samples,
          funding_5m_samples,updated_at
        ) VALUES($1,$2,100,$3,$4,1440,1440,1440,1440,288,288,288,clock_timestamp())
        """,
        session_date_value,
        SYMBOL,
        price,
        coverage_version,
    )


async def _verdict(
    conn: asyncpg.Connection,
    session_date_value: date,
    logic_version: str,
    reference_price: float = 100,
) -> int:
    _, end = session_bounds(session_date_value)
    return await conn.fetchval(
        """
        INSERT INTO daily_verdict_snapshot(
          session_date,symbol,snapshot_version,logic_version,observed_at,
          session_end_at,reference_price,reference_price_at
        ) VALUES($1,$2,1,$3,$4,$4,$5,$4)
        RETURNING snapshot_id
        """,
        session_date_value,
        SYMBOL,
        logic_version,
        end + timedelta(minutes=1),
        reference_price,
    )


class _PoolContext:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self.conn = conn

    def acquire(self) -> _PoolContext:
        return self

    async def __aenter__(self) -> asyncpg.Connection:
        return self.conn

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_daily_projection_preserves_created_at_and_advances_updated_at() -> None:
    conn, schema = await _connect("test_pr24_daily_metadata")
    try:
        session_date_value = date(2026, 8, 11)
        await _publish_liquidation_observation(conn, session_date_value)
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
async def test_complete_liquidation_observation_publishes_measured_total(
    events: list[tuple[float, float]], expected: tuple[float, float]
) -> None:
    conn, schema = await _connect("test_pr24_liq_complete")
    try:
        session_date_value = date(2026, 8, 11)
        start, _ = session_bounds(session_date_value)
        await _publish_liquidation_observation(
            conn, session_date_value, returned_rows=len(events)
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
            SELECT session_coverage_version,long_liq_usd,short_liq_usd,
                   liquidation_coverage_version,liquidation_observed_at,
                   liquidation_source_start_at,liquidation_source_cutoff_at
            FROM daily_session_agg WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        )
        assert row["session_coverage_version"] == 2
        assert (row["long_liq_usd"], row["short_liq_usd"]) == pytest.approx(expected)
        assert row["liquidation_coverage_version"] == 1
        assert row["liquidation_source_start_at"] <= start
        assert row["liquidation_source_cutoff_at"] >= session_bounds(session_date_value)[1]
        assert row["liquidation_observed_at"] >= row["liquidation_source_cutoff_at"]
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "observation",
    [
        {"cutoff_shift": timedelta(minutes=-5)},
        {"status": "degraded", "observed": []},
        {"status": "ok", "valid_detail": False},
    ],
)
async def test_unproven_liquidation_observation_publishes_null_not_partial_sum(
    observation: dict[str, object],
) -> None:
    conn, schema = await _connect("test_pr24_liq_incomplete")
    try:
        session_date_value = date(2026, 8, 11)
        start, _ = session_bounds(session_date_value)
        await _publish_liquidation_observation(conn, session_date_value, **observation)
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
            SELECT long_liq_usd,short_liq_usd,liquidation_coverage_version,
                   liquidation_observed_at,liquidation_source_start_at,
                   liquidation_source_cutoff_at
            FROM daily_session_agg WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            session_date_value,
        )
        assert tuple(row.values()) == (None, None, None, None, None, None)
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_v2_recompute_drops_unproved_legacy_liquidation_values() -> None:
    conn, schema = await _connect("test_pr24_liq_legacy_drop")
    try:
        session_date_value = date(2026, 8, 11)
        await conn.execute(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,long_liq_usd,short_liq_usd,session_coverage_version,
              session_expected_minutes,futures_ohlcv_minutes,spot_2v_minutes,
              cvd_fut_2v_minutes,session_expected_5m_samples,oi_5m_samples,
              funding_5m_samples
            ) VALUES($1,$2,10,20,1,1440,0,0,0,288,0,0)
            """,
            session_date_value,
            SYMBOL,
        )
        await _partial_price(conn, session_date_value)
        assert await compute_session(conn, SYMBOL, "BTC", session_date_value)
        row = await conn.fetchrow(
            """
            SELECT session_coverage_version,long_liq_usd,short_liq_usd,
                   liquidation_coverage_version
            FROM daily_session_agg WHERE symbol=$1
            """,
            SYMBOL,
        )
        assert tuple(row.values()) == (2, None, None, None)
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_legacy_v1_liquidation_shape_remains_valid() -> None:
    conn, schema = await _connect("test_pr24_liq_legacy_valid")
    try:
        await conn.execute(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,long_liq_usd,short_liq_usd,session_coverage_version,
              session_expected_minutes,futures_ohlcv_minutes,spot_2v_minutes,
              cvd_fut_2v_minutes,session_expected_5m_samples,oi_5m_samples,
              funding_5m_samples
            ) VALUES('2026-08-01',$1,10,20,1,1440,0,0,0,288,0,0)
            """,
            SYMBOL,
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM daily_session_agg WHERE session_coverage_version=1"
        ) == 1
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_v2_liquidation_constraint_rejects_false_or_partial_coverage() -> None:
    conn, schema = await _connect("test_pr24_liq_constraint")
    try:
        base = """
          INSERT INTO daily_session_agg(
            session_date,symbol,long_liq_usd,short_liq_usd,
            liquidation_coverage_version,liquidation_observed_at,
            liquidation_source_start_at,liquidation_source_cutoff_at,
            session_coverage_version,session_expected_minutes,futures_ohlcv_minutes,
            spot_2v_minutes,cvd_fut_2v_minutes,session_expected_5m_samples,
            oi_5m_samples,funding_5m_samples
          ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,2,1440,0,0,0,288,0,0)
        """
        start, end = session_bounds(date(2026, 8, 1))
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                base,
                date(2026, 8, 1),
                SYMBOL,
                10,
                None,
                1,
                end + timedelta(minutes=1),
                start,
                end,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                base,
                date(2026, 8, 2),
                SYMBOL,
                10,
                20,
                None,
                None,
                None,
                None,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                base,
                date(2026, 8, 3),
                SYMBOL,
                None,
                None,
                1,
                end + timedelta(minutes=1),
                start,
                end,
            )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_daily_api_date_limit_and_measured_zero_semantics() -> None:
    conn, schema = await _connect("test_pr24_daily_api")
    try:
        await conn.executemany(
            """
            INSERT INTO daily_session_agg(
              session_date,symbol,cvd_spot_usd,cvd_fut_usd,inst_delta_usd,
              price_open,price_close
            ) VALUES($1,$2,$3,$4,0,$5,$6)
            """,
            [
                (date(2026, 8, 1), SYMBOL, 0.0, 10.0, None, None),
                (date(2026, 8, 2), SYMBOL, None, 10.0, 100.0, 101.0),
                (date(2026, 8, 3), SYMBOL, 10.0, 10.0, 100.0, 102.0),
            ],
        )
        limited = await api.daily_data(conn, SYMBOL, 60, date(2026, 8, 2))
        assert [row["session_date"] for row in limited["rows"]] == [
            date(2026, 8, 1),
            date(2026, 8, 2),
        ]
        assert limited["rows"][0]["flow_direction"] == "neutral"
        assert limited["rows"][0]["price_response"] == "neutral"
        assert limited["rows"][1]["flow_direction"] == "sin_dato"
        assert limited["rows"][1]["price_response"] == "sin_dato"
        assert limited["temporal_semantics"] == "mutable_current_projection"
        assert limited["knowledge_time_replay"] is False
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_outcomes_require_exact_v2_targets_and_only_v4_snapshots() -> None:
    conn, schema = await _connect("test_pr24_outcome_targets")
    try:
        origin = date(2026, 8, 1)
        v4_snapshot = await _verdict(conn, origin, "daily-verdict-v4")
        for offset, logic_version in enumerate(
            ("daily-verdict-v3", "daily-verdict-v2", "daily-verdict-v1"), start=1
        ):
            await _verdict(conn, origin + timedelta(days=offset), logic_version)
            await _projection(
                conn,
                origin + timedelta(days=offset + 7),
                200 + offset,
            )
        await _projection(conn, origin + timedelta(days=7), 107)
        await _projection(conn, origin + timedelta(days=14), 114, coverage_version=1)
        await _projection(conn, origin + timedelta(days=15), 999)
        assert await materialize_daily_verdict_outcomes(conn) == 1
        rows = await conn.fetch(
            """
            SELECT snapshot_id,outcome_version,horizon_sessions,target_session_date,
                   target_price_close,target_session_coverage_version,
                   source_projection_updated_at,return_pct,recorded_at
            FROM daily_verdict_outcome ORDER BY horizon_sessions
            """
        )
        assert len(rows) == 1
        assert rows[0]["snapshot_id"] == v4_snapshot
        assert rows[0]["horizon_sessions"] == 7
        assert rows[0]["target_session_date"] == origin + timedelta(days=7)
        assert rows[0]["return_pct"] == pytest.approx(7.0)
        assert rows[0]["target_session_coverage_version"] == 2
        assert rows[0]["source_projection_updated_at"] <= rows[0]["recorded_at"]

        await conn.execute(
            """
            UPDATE daily_session_agg SET session_coverage_version=2
            WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            origin + timedelta(days=14),
        )
        assert await materialize_daily_verdict_outcomes(conn) == 1
        outcome_14 = await conn.fetchrow(
            "SELECT * FROM daily_verdict_outcome WHERE horizon_sessions=14"
        )
        assert outcome_14["target_session_date"] == origin + timedelta(days=14)
        assert outcome_14["return_pct"] == pytest.approx(14.0)
        assert await conn.fetchval(
            """
            SELECT count(*) FROM daily_verdict_outcome o
            JOIN daily_verdict_snapshot v USING(snapshot_id)
            WHERE v.logic_version<>'daily-verdict-v4'
            """
        ) == 0
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_outcome_is_frozen_and_rejects_update_delete_truncate() -> None:
    conn, schema = await _connect("test_pr24_outcome_immutable")
    try:
        origin = date(2026, 8, 1)
        await _verdict(conn, origin, "daily-verdict-v4")
        target = origin + timedelta(days=7)
        await _projection(conn, target, 107)
        assert await materialize_daily_verdict_outcomes(conn) == 1
        frozen = await conn.fetchrow("SELECT * FROM daily_verdict_outcome")
        await conn.execute(
            """
            UPDATE daily_session_agg SET price_close=900,updated_at=clock_timestamp()
            WHERE symbol=$1 AND session_date=$2
            """,
            SYMBOL,
            target,
        )
        assert await materialize_daily_verdict_outcomes(conn) == 0
        unchanged = await conn.fetchrow("SELECT * FROM daily_verdict_outcome")
        assert unchanged == frozen
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("UPDATE daily_verdict_outcome SET return_pct=999")
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("DELETE FROM daily_verdict_outcome")
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await conn.execute("TRUNCATE daily_verdict_outcome")
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_verdict_api_and_ai_never_mix_logic_cohorts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr24_verdict_cohorts")
    try:
        await _verdict(conn, date(2026, 8, 1), "daily-verdict-v1")
        await _verdict(conn, date(2026, 8, 2), "daily-verdict-v4")
        monkeypatch.setattr(api.app.state, "pool", _PoolContext(conn), raising=False)
        current = await api.verdicts(SYMBOL, 90)
        old = await api.verdicts(SYMBOL, 90, "daily-verdict-v1")
        ai_current = await verdict_history(conn, SYMBOL, 90)
        assert current["logic_version"] == "daily-verdict-v4"
        assert {row["logic_version"] for row in current["rows"]} == {
            "daily-verdict-v4"
        }
        assert {row["logic_version"] for row in old["rows"]} == {
            "daily-verdict-v1"
        }
        assert {row["logic_version"] for row in ai_current["series"]} == {
            "daily-verdict-v4"
        }
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
        assert select_reference_price(
            context,
            {
                "fut_price": None,
                "basis_detail": {
                    "fut_age_seconds": None,
                    "stale_after_seconds": 30.0,
                },
            },
        ) == (100, "ohlcv_1min_latest_closed", cutoff)
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
  cvd_fut_2v_minutes int,session_coverage_version smallint,
  session_expected_minutes int,futures_ohlcv_minutes int,spot_2v_minutes int,
  session_expected_5m_samples int,oi_5m_samples int,funding_5m_samples int,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(symbol,session_date),
  CONSTRAINT daily_session_agg_pr20_coverage_check CHECK (
    session_coverage_version IS NULL OR session_coverage_version=1
  )
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
async def test_pr24_migration_up_twice_down_empty_reup_without_backfill() -> None:
    conn, schema = await _connect("test_pr24_migration_cycle", full_schema=False)
    try:
        await conn.execute(PRE_PR24_SQL)
        await conn.execute(
            "INSERT INTO daily_session_agg(symbol,session_date) VALUES($1,'2026-08-01')",
            SYMBOL,
        )
        await conn.execute(UP_SQL)
        await conn.execute(UP_SQL)
        assert await conn.fetchval("SELECT updated_at FROM daily_session_agg") is None
        assert await conn.fetchval(
            "SELECT to_regclass('daily_verdict_outcome') IS NOT NULL"
        )
        assert await conn.fetchval("SELECT count(*) FROM daily_verdict_outcome") == 0
        await conn.execute(DOWN_SQL)
        await conn.execute(DOWN_SQL)
        assert not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='daily_session_agg' "
            "AND column_name='updated_at')"
        )
        await conn.execute(UP_SQL)
        assert await conn.fetchval("SELECT updated_at FROM daily_session_agg") is None
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
                WHERE table_schema=current_schema() AND table_name='daily_verdict_outcome'
                """
            )
        }
        assert {
            "snapshot_id",
            "outcome_version",
            "horizon_sessions",
            "target_session_date",
            "target_price_close",
            "target_session_coverage_version",
            "source_projection_updated_at",
            "return_pct",
            "recorded_at",
        } <= columns
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence_version", [3, 4, 5])
async def test_v3_v4_v5_regime_provenance_is_protected(evidence_version: int) -> None:
    conn, schema = await _connect("test_pr24_regime_guard")
    try:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                """
                INSERT INTO signal_observation(
                  observed_at,observed_minute,symbol,signal_family,sampling_version,
                  evidence_version,logic_version,decision_status,direction,state,
                  actionable,confidence,reason,long_score,short_score,evidence_coverage_pct,
                  is_periodic,is_transition,collector_shard_index,collector_shard_count,
                  decision_fingerprint,evidence,regime_score
                ) VALUES(
                  now(),date_trunc('minute',now()),$1,'scalp',1,$2,
                  'scalp-summary-v1','not_evaluable','unavailable','SIN_DATOS',
                  false,'baja','missing',0,0,0,true,false,0,1,
                  repeat('a',64),'{}'::jsonb,1
                )
                """,
                SYMBOL,
                evidence_version,
            )
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence_kind", ["signal", "verdict", "outcome", "session"])
async def test_pr24_down_refuses_each_incompatible_evidence_kind(
    evidence_kind: str,
) -> None:
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
        elif evidence_kind == "outcome":
            snapshot_id = await conn.fetchval(
                """
                INSERT INTO daily_verdict_snapshot(logic_version)
                VALUES('daily-verdict-v1') RETURNING snapshot_id
                """
            )
            await conn.execute(
                """
                INSERT INTO daily_verdict_outcome(
                  snapshot_id,outcome_version,horizon_sessions,target_session_date,
                  target_price_close,target_session_coverage_version,
                  source_projection_updated_at,return_pct,recorded_at
                ) VALUES($1,1,7,'2026-08-08',107,2,now(),7,clock_timestamp())
                """,
                snapshot_id,
            )
        else:
            await conn.execute(
                """
                INSERT INTO daily_session_agg(
                  symbol,session_date,session_coverage_version,session_expected_minutes,
                  futures_ohlcv_minutes,spot_2v_minutes,cvd_fut_2v_minutes,
                  session_expected_5m_samples,oi_5m_samples,funding_5m_samples
                ) VALUES($1,'2026-08-01',2,1440,0,0,0,288,0,0)
                """,
                SYMBOL,
            )
        with pytest.raises(asyncpg.PostgresError, match="PR24 down migration refuses"):
            await conn.execute(DOWN_SQL)
        await conn.execute("ROLLBACK")
        assert await conn.fetchval(
            "SELECT to_regclass('daily_verdict_outcome') IS NOT NULL"
        )
    finally:
        await _drop(conn, schema)
