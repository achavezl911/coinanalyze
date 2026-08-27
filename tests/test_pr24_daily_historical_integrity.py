from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

import app.api as api
from app.ai_context import verdict_history
from app.daily_agg import (
    DAILY_VERDICT_LOGIC_VERSION,
    DAILY_VERDICT_OUTCOME_HORIZONS,
    DAILY_VERDICT_OUTCOME_VERSION,
    LIQUIDATION_COVERAGE_VERSION,
    SESSION_COVERAGE_VERSION,
    materialize_daily_verdict_outcomes,
)
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

    async def fetchval(self, query: str, *args: object) -> int:
        self.query = query
        self.args = args
        return 0


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
async def test_daily_is_current_mutable_projection_with_optional_date_limit() -> None:
    conn = CaptureConnection()
    cutoff = date(2026, 8, 11)
    result = await api.daily_data(conn, SYMBOL, 60, cutoff)
    assert conn.query.count("FROM daily_session_agg") == 3
    assert "daily_session_snapshot" not in conn.query
    assert conn.args == (SYMBOL, 60, cutoff)
    assert result["through_session_date"] == cutoff.isoformat()
    assert result["temporal_semantics"] == "mutable_current_projection"
    assert result["knowledge_time_replay"] is False


@pytest.mark.asyncio
async def test_daily_as_of_fails_explicitly_instead_of_claiming_pit() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await api.daily(SYMBOL, 60, None, date(2026, 8, 11))
    assert exc_info.value.status_code == 400
    assert "PIT replay is not supported" in str(exc_info.value.detail)
    assert "through_session_date" in str(exc_info.value.detail)


def test_daily_zero_classification_precedes_price_missing_and_direction() -> None:
    text = Path(api.__file__).read_text(encoding="utf-8")
    start = text.index("async def daily_data")
    body = text[start : text.index('@app.get("/api/snapshot")', start)]
    null_guard = "WHEN s.cvd_spot_usd IS NULL OR s.cvd_fut_usd IS NULL THEN 'sin_dato'"
    zero_guard = "WHEN s.cvd_spot_usd = 0 OR s.cvd_fut_usd = 0 THEN 'neutral'"
    assert body.index(null_guard) < body.index(zero_guard) < body.index("'ambos_compran'")
    price_case = body.index("END AS price_response")
    price_start = body.rfind("CASE", 0, price_case)
    price_body = body[price_start:price_case]
    assert price_body.index(null_guard) < price_body.index(zero_guard)
    assert price_body.index(zero_guard) < price_body.index("s.price_chg_pct IS NULL")


@pytest.mark.asyncio
async def test_verdict_api_defaults_to_current_logic_cohort(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = CaptureConnection()
    monkeypatch.setattr(api.app.state, "pool", PoolContext(conn), raising=False)
    result = await api.verdicts(SYMBOL, 25)
    assert "logic_version=$2" in conn.query
    assert "daily_verdict_outcome" in conn.query
    assert "daily_session_agg" not in conn.query
    assert "OFFSET" not in conn.query
    assert conn.args == (SYMBOL, DAILY_VERDICT_LOGIC_VERSION, 25, 1)
    assert result["logic_version"] == "daily-verdict-v4"


@pytest.mark.asyncio
async def test_verdict_api_explicit_version_is_exactly_one_cohort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = CaptureConnection()
    monkeypatch.setattr(api.app.state, "pool", PoolContext(conn), raising=False)
    result = await api.verdicts(SYMBOL, 25, "daily-verdict-v2")
    assert conn.args == (SYMBOL, "daily-verdict-v2", 25, 1)
    assert result["logic_version"] == "daily-verdict-v2"


@pytest.mark.asyncio
async def test_ai_verdict_history_uses_only_current_cohort_and_outcomes() -> None:
    conn = CaptureConnection()
    result = await verdict_history(conn, SYMBOL, 90)
    assert conn.args == (SYMBOL, 90, DAILY_VERDICT_LOGIC_VERSION, 1)
    assert "logic_version=$3" in conn.query
    assert "daily_verdict_outcome" in conn.query
    assert "daily_session_agg" not in conn.query
    assert result["logic_version"] == "daily-verdict-v4"


@pytest.mark.asyncio
async def test_outcome_materializer_uses_exact_calendar_targets_and_v2_projection() -> None:
    conn = CaptureConnection()
    assert await materialize_daily_verdict_outcomes(conn) == 0
    assert "verdict.session_date+horizon.horizon_sessions" in conn.query
    assert "verdict.logic_version=$1" in conn.query
    assert "target.session_coverage_version=2" in conn.query
    assert "target.updated_at IS NOT NULL" in conn.query
    assert "OFFSET" not in conn.query
    assert conn.args == ("daily-verdict-v4", 1, [7, 14])


def test_daily_cycle_attempts_outcomes_after_projection_refresh() -> None:
    source = Path("app/daily_agg.py").read_text(encoding="utf-8")
    cycle = source[source.index("async def cycle(") : source.index("async def run()")]
    assert cycle.index("await backfill(") < cycle.index("materialize_daily_verdict_outcomes(")


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


def test_pr24_version_boundaries_and_regime_guards() -> None:
    schema = Path("sql/schema.sql").read_text(encoding="utf-8")
    assert SESSION_COVERAGE_VERSION == 2
    assert LIQUIDATION_COVERAGE_VERSION == 1
    assert DAILY_VERDICT_LOGIC_VERSION == "daily-verdict-v4"
    assert DAILY_VERDICT_OUTCOME_VERSION == 1
    assert DAILY_VERDICT_OUTCOME_HORIZONS == (7, 14)
    # PR25 advanced the live writer to evidence_version=6; the historical
    # PR24 constraint text below remains verbatim in schema.sql (superseded
    # by the PR25 block appended after it, never rewritten in place).
    assert SIGNAL_EVIDENCE_VERSION == 6
    assert "evidence_version NOT IN (3,4,5)" in schema
    assert "'daily-verdict-v2','daily-verdict-v3','daily-verdict-v4'" in schema
    assert SCALP_SIGNAL_LOGIC_VERSION == "scalp-summary-v1"
    assert SIGNAL_SAMPLING_VERSION == 1
    assert REPLAY_CONTEXT_VERSION == 1
    # K62: el escritor cambio de regla el 2026-08-27T04:43:05Z (K59) y esta
    # constante DEBERIA ir por 3, pero subirla sola rompe produccion: el CHECK
    # signal_observation_pr25_regime_provenance_check (sql/schema.sql:2476) exige
    # regimen 2 para evidencia 3/4/5/6. Probado y revertido, 302 s sin escribir.
    # Se mueve con la evidencia 7, que es K64. Ver app/metrics.py.
    assert REGIME_LOGIC_VERSION == 2
    assert OUTCOME_VERSION == 1
    assert EXECUTION_SNAPSHOT_VERSION == 1
