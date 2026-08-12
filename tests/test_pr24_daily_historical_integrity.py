from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

import app.api as api
from app.ai_context import verdict_history
from app.daily_agg import (
    DAILY_SESSION_SNAPSHOT_VERSION,
    DAILY_VERDICT_LOGIC_VERSION,
    LIQUIDATION_COVERAGE_VERSION,
)
from app.ingest import persist_liquidation_history_observations
from app.metrics import REGIME_LOGIC_VERSION
from app.signal_execution import EXECUTION_SNAPSHOT_VERSION
from app.signal_ledger import (
    SIGNAL_EVIDENCE_VERSION,
    SIGNAL_SAMPLING_VERSION,
    select_reference_price,
)
from app.signal_outcomes import OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

SYMBOL = "BTCUSDT_PERP.A"


class CaptureConnection:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows or []
        self.query = ""
        self.args: tuple[object, ...] = ()

    async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
        self.query = query
        self.args = args
        return self.rows


@pytest.mark.asyncio
async def test_daily_without_as_of_uses_only_mutable_projection() -> None:
    conn = CaptureConnection()
    result = await api.daily_data(conn, SYMBOL, 60)
    assert "FROM daily_session_agg" in conn.query
    assert "FROM daily_session_snapshot" not in conn.query
    assert result["semantics"] == "mutable_latest_projection"
    assert result["snapshot_version"] is None


@pytest.mark.asyncio
async def test_daily_as_of_uses_only_prospective_immutable_universe() -> None:
    conn = CaptureConnection()
    cutoff = date(2026, 8, 11)
    result = await api.daily_data(conn, SYMBOL, 60, cutoff)
    assert "FROM daily_session_snapshot" in conn.query
    assert "FROM daily_session_agg" not in conn.query
    assert "WHERE snapshot_version=1" in conn.query
    assert conn.query.count("FROM source") == 3
    assert conn.args == (SYMBOL, 60, cutoff)
    assert result["semantics"] == "prospective_first_observation"
    assert result["snapshot_version"] == 1
    assert result["rows"] == []  # no fallback for sessions before prospective capture


def test_daily_zero_classification_precedes_directional_branches() -> None:
    text = Path(api.__file__).read_text(encoding="utf-8")
    start = text.index("async def daily_data")
    body = text[start : text.index("@app.get(\"/api/snapshot\")", start)]
    null_guard = "WHEN s.cvd_spot_usd IS NULL OR s.cvd_fut_usd IS NULL THEN 'sin_dato'"
    zero_guard = "WHEN s.cvd_spot_usd = 0 OR s.cvd_fut_usd = 0 THEN 'neutral'"
    assert body.index(null_guard) < body.index(zero_guard) < body.index("'ambos_compran'")
    assert body.count(zero_guard) == 2  # flow_direction and price_response


class PoolContext:
    def __init__(self, conn: CaptureConnection) -> None:
        self.conn = conn

    def acquire(self) -> PoolContext:
        return self

    async def __aenter__(self) -> CaptureConnection:
        return self.conn

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_verdict_api_defaults_to_current_logic_cohort(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = CaptureConnection()
    monkeypatch.setattr(api.app.state, "pool", PoolContext(conn), raising=False)
    result = await api.verdicts(SYMBOL, 25, DAILY_VERDICT_LOGIC_VERSION)
    assert "logic_version=$2" in conn.query
    assert "daily_session_agg" not in conn.query
    assert "session_date=v.session_date+7" in conn.query
    assert "session_date=v.session_date+14" in conn.query
    assert "OFFSET" not in conn.query
    assert conn.args == (SYMBOL, DAILY_VERDICT_LOGIC_VERSION, 25)
    assert result["logic_version"] == "daily-verdict-v4"


@pytest.mark.asyncio
async def test_verdict_api_explicit_version_is_one_cohort(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = CaptureConnection()
    monkeypatch.setattr(api.app.state, "pool", PoolContext(conn), raising=False)
    result = await api.verdicts(SYMBOL, 25, "daily-verdict-v2")
    assert conn.args == (SYMBOL, "daily-verdict-v2", 25)
    assert result["logic_version"] == "daily-verdict-v2"


@pytest.mark.asyncio
async def test_ai_verdict_history_is_current_cohort_and_immutable_targets() -> None:
    conn = CaptureConnection()
    result = await verdict_history(conn, SYMBOL, 90)
    assert conn.args == (SYMBOL, 90, DAILY_VERDICT_LOGIC_VERSION)
    assert "logic_version=$3" in conn.query
    assert "daily_session_agg" not in conn.query
    assert "session_date=v.session_date+7" in conn.query
    assert "session_date=v.session_date+14" in conn.query
    assert result["logic_version"] == "daily-verdict-v4"


def test_pr24_version_tuple_changes_only_requested_boundaries() -> None:
    assert SIGNAL_EVIDENCE_VERSION == 5
    assert DAILY_VERDICT_LOGIC_VERSION == "daily-verdict-v4"
    assert DAILY_SESSION_SNAPSHOT_VERSION == 1
    assert LIQUIDATION_COVERAGE_VERSION == 1


class ObservationCapture:
    def __init__(self, observed_at: datetime) -> None:
        self.observed_at = observed_at
        self.rows: list[tuple[object, ...]] = []

    async def fetchval(self, _query: str) -> datetime:
        return self.observed_at

    async def executemany(
        self, _query: str, rows: list[tuple[object, ...]]
    ) -> None:
        self.rows = rows


@pytest.mark.asyncio
async def test_liquidation_observations_distinguish_zero_missing_and_rejected() -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conn = ObservationCapture(cutoff + timedelta(seconds=1))
    await persist_liquidation_history_observations(
        conn,  # type: ignore[arg-type]
        {SYMBOL: [], "ETHUSDT_PERP.A": [{"t": 1}]},
        (SYMBOL, "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"),
        accepted_by_symbol={SYMBOL: 0, "ETHUSDT_PERP.A": 0},
        source_start=cutoff - timedelta(hours=26),
        source_cutoff=cutoff,
    )
    by_symbol = {str(row[0]): row for row in conn.rows}
    assert by_symbol[SYMBOL][4:] == ("COMPLETE", True, 0, 0)
    assert by_symbol["ETHUSDT_PERP.A"][4:] == ("INCOMPLETE", True, 1, 0)
    assert by_symbol["SOLUSDT_PERP.A"][4:] == ("INCOMPLETE", False, 0, 0)


def test_ohlcv_reference_fails_closed_without_exact_close_timestamp() -> None:
    summary = {
        "fut_price": None,
        "basis_detail": {"fut_age_seconds": None, "stale_after_seconds": 30.0},
    }
    assert select_reference_price({"ohlcv_price": 100.0}, summary) == (None, None, None)
    closed_at = datetime(2026, 8, 11, 12, 1, tzinfo=UTC)
    future_context = {
        "ohlcv_price": 100.0,
        "ohlcv_price_at": closed_at,
        "now_ms": datetime(2026, 8, 11, 12, 0, tzinfo=UTC).timestamp() * 1000,
    }
    assert select_reference_price(future_context, summary) == (None, None, None)


def test_pr24_regime_guards_cover_new_versions_without_changing_old_defaults() -> None:
    schema = Path("sql/schema.sql").read_text(encoding="utf-8")
    assert "evidence_version NOT IN (3,4,5)" in schema
    assert "'daily-verdict-v2','daily-verdict-v3','daily-verdict-v4'" in schema
    assert SCALP_SIGNAL_LOGIC_VERSION == "scalp-summary-v1"
    assert SIGNAL_SAMPLING_VERSION == 1
    assert REPLAY_CONTEXT_VERSION == 1
    assert REGIME_LOGIC_VERSION == 2
    assert OUTCOME_VERSION == 1
    assert EXECUTION_SNAPSHOT_VERSION == 1
