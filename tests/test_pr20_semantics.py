from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import app.daily_agg as daily_agg
import app.metrics as metrics
from app.daily_agg import (
    SESSION_MIN_COVERAGE_RATIO,
    _coverage_complete,
    _expected_session_samples,
    refresh_baselines,
)
from app.interpretation import evaluate_setups
from app.metrics import session_bounds
from app.scalp_logic import _resample_highs_lows

ROOT = Path(__file__).resolve().parents[1]


def test_pr20_session_coverage_uses_real_dst_duration() -> None:
    spring_start, spring_end = session_bounds(date(2026, 3, 8))
    fall_start, fall_end = session_bounds(date(2026, 11, 1))
    assert _expected_session_samples(spring_start, spring_end, 60) == 1380
    assert _expected_session_samples(fall_start, fall_end, 60) == 1500
    assert _expected_session_samples(spring_start, spring_end, 300) == 276
    assert _expected_session_samples(fall_start, fall_end, 300) == 300
    assert pytest.approx(0.95) == SESSION_MIN_COVERAGE_RATIO
    assert _coverage_complete(1311, 1380)
    assert not _coverage_complete(1310, 1380)
    assert _coverage_complete(1425, 1500)
    assert not _coverage_complete(1424, 1500)


def test_pr20_spot_absence_is_never_coalesced_to_zero() -> None:
    query = daily_agg.SESSION_QUERY
    assert "SUM(buy_vol_usd - sell_vol_usd) AS cvd_spot" in query
    assert "SUM(inst_buy_usd - inst_sell_usd) AS inst_delta" in query
    assert "spot.minutes AS spot_2v_minutes" in query
    assert "COALESCE(SUM(buy_vol_usd - sell_vol_usd),0)" not in query
    assert "COALESCE(SUM(inst_buy_usd - inst_sell_usd),0)" not in query


class _SessionConn:
    def __init__(self, row: dict) -> None:
        self.row = row
        self.executed: list[tuple[str, tuple]] = []

    async def fetchrow(self, _query, *_args):
        return self.row

    async def fetch(self, _query, *_args):
        return []

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "INSERT 0 1"


def _row(minutes: int = 1440) -> dict:
    samples5 = minutes // 5
    return {
        "samples": minutes, "spot_2v_minutes": minutes, "fut_2v_minutes": minutes,
        "oi_5m_samples": samples5, "funding_5m_samples": samples5,
        "cvd_fut": -5.0, "price_open": 100.0, "price_close": 101.0,
        "price_high": 102.0, "price_low": 99.0, "volume_usd": 1_000.0, "tx_count": 100,
        "cvd_fut_2v": -7.0, "cvd_spot": 10.0, "inst_delta": 2.0,
        "oi_open": 200.0, "oi_close": 210.0, "oi_high": 215.0, "oi_low": 195.0,
        "long_liq": None, "short_liq": None, "fr_avg": 0.01,
    }


@pytest.mark.asyncio
async def test_pr20_partial_spot_keeps_other_complete_legs_but_spot_is_null() -> None:
    row = _row()
    row["spot_2v_minutes"] = 1000
    conn = _SessionConn(row)
    assert await daily_agg.compute_session(conn, "BTCUSDT_PERP.A", "BTC", date(2026, 8, 10))
    args = conn.executed[0][1]
    assert args[2] is None  # cvd_spot_usd
    assert args[4] is None  # inst_delta_usd
    assert args[3] == -5.0  # futures leg remains measured
    assert args[6] == 101.0
    assert args[23] == 1000  # observed spot minutes remain explicit provenance


@pytest.mark.asyncio
async def test_pr20_partial_futures_does_not_fabricate_price_or_futures_cvd() -> None:
    row = _row()
    row["samples"] = 1000
    conn = _SessionConn(row)
    assert await daily_agg.compute_session(conn, "BTCUSDT_PERP.A", "BTC", date(2026, 8, 10))
    args = conn.executed[0][1]
    assert args[3] is None
    assert args[5] is None and args[6] is None
    assert args[2] == 10.0
    assert args[22] == 1000


class _MissingPriceConn:
    async def fetchrow(self, _query, *_args):
        return {
            "price": None, "price_ts": None, "price_1h": None,
            "oi_now": None, "oi_ts": None, "oi_old": None,
        }

    async def fetch(self, _query, *_args):
        return []


@pytest.mark.asyncio
async def test_pr20_missing_price_direction_is_null() -> None:
    snapshot = await metrics.compute_snapshot(
        _MissingPriceConn(), "BTCUSDT_PERP.A", "BTC",
        datetime(2026, 8, 11, 12, 5, tzinfo=UTC),
    )
    assert snapshot["price_dir_1h"] is None


def test_pr20_missing_price_does_not_match_lateral_setup_predicates() -> None:
    daily = [{"cvd_spot_usd": 10.0, "cumulative_spot": float(i)} for i in range(1, 5)]
    base = {"cvd_spot_24h": 10.0, "price_dir_1h": None, "fr_avg": 0.0, "oi_chg_24h_pct": 0.0}
    missing = {item["id"]: item for item in evaluate_setups(base, daily)["setups"]}
    measured = {item["id"]: item for item in evaluate_setups({**base, "price_dir_1h": 0}, daily)["setups"]}
    assert "Precio lateral o débil" not in missing["B"]["matched"]
    assert "Precio lateral o débil" in measured["B"]["matched"]
    assert measured["B"]["confidence"] == missing["B"]["confidence"] + 20


def test_pr20_frontend_renders_missing_price_direction_as_nd() -> None:
    source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "function priceDirection1h(value)" in source
    assert "return '1 h N/D'" in source
    assert "priceDirection1h(s.price_dir_1h)" in source


class _ResampleConn:
    def __init__(self) -> None:
        self.query = ""
        self.args = ()

    async def fetch(self, query, *args):
        self.query = query
        self.args = args
        return []


@pytest.mark.asyncio
async def test_pr20_resample_filters_closed_target_before_limit() -> None:
    conn = _ResampleConn()
    cutoff = datetime(2026, 8, 11, 14, 18, tzinfo=UTC)
    await _resample_highs_lows(conn, "BTCUSDT_PERP.A", 14400, 30, "4hour", cutoff)
    assert "bucket + make_interval(secs => $2::int) <= $5" in conn.query
    assert "ORDER BY bucket DESC LIMIT $3" in conn.query
    assert conn.args[-1] == cutoff


class _BaselineConn:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch(self, query, *_args):
        self.queries.append(query)
        return []


@pytest.mark.asyncio
async def test_pr20_baselines_exclude_open_source_and_target_buckets() -> None:
    conn = _BaselineConn()
    assert await refresh_baselines(conn, ("BTCUSDT_PERP.A",)) == 0
    assert conn.queries
    assert all("ts + CASE WHEN $3='4hour' THEN interval '4 hours' ELSE interval '1 minute' END <= $5" in q for q in conn.queries)
    assert all("bucket + make_interval(secs => $2::int) <= $5" in q for q in conn.queries)



def test_pr20_known_raw_htf_consumers_have_close_gates() -> None:
    scalp = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    assert scalp.count("ts + interval '4 hours' <=") >= 4
    assert scalp.count("ts + interval '1 day' <=") >= 4
    assert "CASE WHEN $3='4hour' THEN interval '4 hours' ELSE interval '1 day' END <= $5" in scalp
    delta = (ROOT / "app" / "delta_profile.py").read_text(encoding="utf-8")
    assert "WHEN $2='4hour' THEN interval '4 hours'" in delta
    daily = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert "bucket + make_interval(secs => $2::int) <= $5" in daily
    # Collector behavior stays intentionally unchanged: the mutable edge is still refreshed.
    assert 'interval="4hour"' in daily
    assert 'interval="daily"' in daily


def test_pr20_schema_marks_old_coverage_as_unknown_and_allows_partial_values() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "ALTER COLUMN cvd_spot_usd DROP NOT NULL" in schema
    assert "ALTER COLUMN price_close DROP NOT NULL" in schema
    assert "NULL=legacy/unverified" in schema
    assert "session_expected_5m_samples * 5 = session_expected_minutes" in schema


def test_pr20_schema_preserves_inline_partition_migration_as_exact_prior_transaction() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    partition = (ROOT / "sql" / "migrations" / "20260809_temporal_partitioning.sql").read_text(encoding="utf-8").strip()
    assert partition in schema
    partition_start = schema.index(partition)
    partition_end = partition_start + len(partition)
    pr20_start = schema.index("-- PR20_F3_F4_F7_BEGIN")
    assert partition_end < pr20_start
    assert schema[partition_end:pr20_start].strip() == "BEGIN;"
    assert schema.count("-- PR20_F3_F4_F7_BEGIN") == 1
    assert schema.count("-- PR20_F3_F4_F7_END") == 1


def test_pr22_advances_live_evidence_without_changing_pr11_kernel() -> None:
    ledger = (ROOT / "app" / "signal_ledger.py").read_text(encoding="utf-8")
    walk = (ROOT / "app" / "signal_walk_forward.py").read_text(encoding="utf-8")
    assert "SIGNAL_EVIDENCE_VERSION = 5" in ledger
    assert 'DEFAULT_MANIFEST_NAME = "pr11-fixed-kernel-v1"' in walk
def test_pr20_f4_schema_accepts_unmeasurable_price_direction() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    up = (
        ROOT / "sql" / "migrations" / "20260811_pr20_semantics.sql"
    ).read_text(encoding="utf-8")
    down = (
        ROOT / "sql" / "migrations" / "20260811_pr20_semantics_down.sql"
    ).read_text(encoding="utf-8")

    nullable = "ALTER TABLE metrics_snapshot ALTER COLUMN price_dir_1h DROP NOT NULL;"
    restore = "ALTER TABLE metrics_snapshot ALTER COLUMN price_dir_1h SET NOT NULL;"

    assert nullable in schema
    assert nullable in up
    assert "SELECT 1 FROM metrics_snapshot WHERE price_dir_1h IS NULL" in down
    assert restore in down

    # F4's application contract is deliberately nullable:
    # None = not measurable, 0 = measured lateral.
    metrics_source = (ROOT / "app" / "metrics.py").read_text(encoding="utf-8")
    assert "price_dir: int | None = None" in metrics_source
    assert 'snap["price_dir_1h"]' in metrics_source
