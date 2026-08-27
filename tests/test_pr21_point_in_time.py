from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import app.daily_agg as daily_agg
from app.ai_context import verdict_history

ROOT = Path(__file__).resolve().parents[1]


class _VerdictWriterConnection:
    def __init__(self, *, reference: dict | None, metrics: dict | None = None) -> None:
        self.reference = reference
        self.metrics = metrics
        self.observed_at = datetime(2026, 8, 11, 15, 7, 31, tzinfo=UTC)
        self.queries: list[tuple[str, tuple]] = []

    async def fetchrow(self, query: str, *args):
        self.queries.append((query, args))
        if "FROM daily_session_agg" in query:
            return {"price_close": 101.0, "session_coverage_version": 1}
        if "FROM metrics_snapshot" in query:
            assert args[1] == daily_agg.REGIME_LOGIC_VERSION
            if (
                self.metrics is not None
                and self.metrics.get("regime_logic_version") == args[1]
            ):
                return self.metrics
            return None
        if "FROM ohlcv" in query:
            return self.reference
        raise AssertionError(f"unexpected fetchrow query: {query}")

    async def fetch(self, query: str, *args):
        self.queries.append((query, args))
        return []

    async def fetchval(self, query: str, *args):
        self.queries.append((query, args))
        assert "clock_timestamp()" in query
        return self.observed_at

    async def execute(self, query: str, *args):
        self.queries.append((query, args))
        return "INSERT 0 1"


async def _no_signal(_conn, _symbol):
    return {
        "bias": "NEUTRAL",
        "score": 0.0,
        "conviction": "baja",
        "long_share_pct": 50.0,
        "components": [],
    }


@pytest.mark.asyncio
async def test_pr21_reference_price_requires_closed_1m_candle(monkeypatch) -> None:
    reference_at = datetime(2026, 8, 11, 15, 7, tzinfo=UTC)
    conn = _VerdictWriterConnection(
        reference={"reference_price": 100.5, "reference_price_at": reference_at}
    )
    monkeypatch.setattr(daily_agg, "latest_closed_session_date", lambda: date(2026, 8, 11))
    monkeypatch.setattr(daily_agg, "swing_score", _no_signal)

    assert await daily_agg.persist_verdicts(conn, ("BTCUSDT_PERP.A",)) == 1

    reference_query, reference_args = next(
        (query, args) for query, args in conn.queries if "FROM ohlcv" in query
    )
    assert "ts + interval '1 minute' AS reference_price_at" in reference_query
    assert "ts + interval '1 minute' <= $2" in reference_query
    assert "ORDER BY ts DESC" in reference_query
    assert reference_args == ("BTCUSDT_PERP.A", conn.observed_at)

    snapshot_query, snapshot_args = next(
        (query, args)
        for query, args in conn.queries
        if "INSERT INTO daily_verdict_snapshot" in query
    )
    assert "ON CONFLICT(symbol,session_date) DO NOTHING" in snapshot_query
    assert snapshot_args[22] == 100.5
    assert snapshot_args[23] == reference_at
    assert snapshot_args[4] >= snapshot_args[5]

    executed_sql = [query for query, _args in conn.queries]
    snapshot_index = next(
        index
        for index, query in enumerate(executed_sql)
        if "INSERT INTO daily_verdict_snapshot" in query
    )
    projection_index = next(
        index
        for index, query in enumerate(executed_sql)
        if "INSERT INTO daily_verdict(" in query
    )
    assert snapshot_index < projection_index
    assert "ON CONFLICT(symbol,session_date) DO UPDATE" in executed_sql[projection_index]


@pytest.mark.asyncio
async def test_pr21_missing_reference_price_keeps_returns_null(monkeypatch) -> None:
    conn = _VerdictWriterConnection(reference=None)
    monkeypatch.setattr(daily_agg, "latest_closed_session_date", lambda: date(2026, 8, 11))
    monkeypatch.setattr(daily_agg, "swing_score", _no_signal)

    await daily_agg.persist_verdicts(conn, ("BTCUSDT_PERP.A",))
    _, snapshot_args = next(
        (query, args)
        for query, args in conn.queries
        if "INSERT INTO daily_verdict_snapshot" in query
    )
    assert snapshot_args[22] is None
    assert snapshot_args[23] is None

    api = (ROOT / "app/api.py").read_text(encoding="utf-8")
    body = api[api.index("async def verdicts(") : api.index("async def structure", api.index("async def verdicts("))]
    assert "d7.return_pct AS fwd_return_7s_pct" in body
    assert "d14.return_pct AS fwd_return_14s_pct" in body
    materializer = (ROOT / "app/daily_agg.py").read_text(encoding="utf-8")
    assert "verdict.reference_price IS NOT NULL" in materializer


class _HistoryConnection:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple = ()

    async def fetch(self, query: str, *args):
        self.query = query
        self.args = args
        return []


@pytest.mark.asyncio
async def test_pr21_verdict_history_reads_snapshot_not_mutable_projection() -> None:
    conn = _HistoryConnection()
    result = await verdict_history(conn, "BTCUSDT_PERP.A", 12)
    assert "FROM daily_verdict_snapshot" in conn.query
    assert "FROM daily_verdict WHERE" not in conn.query
    assert conn.args == ("BTCUSDT_PERP.A", 12, "daily-verdict-v4", 1)
    assert result["available"] is False
    assert "first immutable observed verdict snapshot" in result["note"]


def test_pr21_forward_return_uses_observation_reference_price() -> None:
    for path, start_marker, end_marker in (
        ("app/api.py", "async def verdicts(", "async def structure"),
        ("app/ai_context.py", "async def verdict_history", "async def data_confidence_row"),
    ):
        source = (ROOT / path).read_text(encoding="utf-8")
        start = source.index(start_marker)
        body = source[start : source.index(end_marker, start)]
        assert "d7.return_pct" in body
        assert "d14.return_pct" in body
        assert "daily_verdict_outcome" in body
        assert "FROM daily_session_agg" not in body
        assert "OFFSET" not in body
        assert "/v.reference_price" not in body


def test_pr21_verdict_api_exposes_snapshot_provenance() -> None:
    source = (ROOT / "app/api.py").read_text(encoding="utf-8")
    start = source.index("async def verdicts(")
    body = source[start : source.index("async def structure", start)]
    for field in (
        "observed_at",
        "session_end_at",
        "snapshot_version",
        "logic_version",
        "reference_price",
        "reference_price_at",
        "session_price_close",
        "metrics_snapshot_ts",
        "session_coverage_version",
        "regime_logic_version",
    ):
        assert f"v.{field}" in body


class _RetentionConnection:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def execute(self, query: str, *_args):
        self.queries.append(query)
        return "DELETE 0"


@pytest.mark.asyncio
async def test_pr21_snapshot_not_subject_to_daily_retention(monkeypatch) -> None:
    async def _no_temporal_retention(*_args, **_kwargs):
        return 0

    monkeypatch.setattr(daily_agg, "apply_temporal_retention", _no_temporal_retention)
    conn = _RetentionConnection()
    await daily_agg.apply_retention(conn, 14, 400, 30, 6, 30)
    executed = "\n".join(conn.queries)
    assert "DELETE FROM daily_verdict WHERE" in executed
    assert "DELETE FROM daily_verdict_snapshot" not in executed


def test_pr21_daily_verdict_versions_are_domain_specific() -> None:
    assert daily_agg.DAILY_VERDICT_SNAPSHOT_VERSION == 1
    assert daily_agg.DAILY_VERDICT_LOGIC_VERSION == "daily-verdict-v4"
    source = (ROOT / "app/daily_agg.py").read_text(encoding="utf-8")
    for unrelated in (
        "SIGNAL_EVIDENCE_VERSION",
        "SIGNAL_SAMPLING_VERSION",
        "REPLAY_CONTEXT_VERSION",
    ):
        assert unrelated not in source


async def _persist_pr22_daily_snapshot(monkeypatch: pytest.MonkeyPatch):
    metrics_at = datetime(2026, 8, 11, 15, 0, tzinfo=UTC)
    conn = _VerdictWriterConnection(
        reference=None,
        metrics={
            "ts": metrics_at,
            "regime_score": 12.0,
            "regime_label": "v2",
            # La fila tiene que llevar la version VIVA, no un 2 literal: daily_agg pide
            # WHERE regime_logic_version=$2 con la constante del modulo, asi que un
            # literal aqui hace que el fixture deje de representar "hay un snapshot
            # compatible" en cuanto la constante sube, y el test pasa a medir la
            # ausencia de snapshot -que es justo lo que cubre el test de al lado,
            # test_pr23_daily_v3_does_not_copy_legacy_regime-. K62.
            "regime_logic_version": daily_agg.REGIME_LOGIC_VERSION,
        },
    )
    monkeypatch.setattr(daily_agg, "latest_closed_session_date", lambda: date(2026, 8, 11))
    monkeypatch.setattr(daily_agg, "swing_score", _no_signal)
    monkeypatch.setattr(
        daily_agg,
        "evaluate_setups",
        lambda _snapshot, _rows: {"primary": None, "daily_streak": None},
    )
    await daily_agg.persist_verdicts(conn, ("BTCUSDT_PERP.A",))
    return next(
        (query, args)
        for query, args in conn.queries
        if "INSERT INTO daily_verdict_snapshot" in query
    )


@pytest.mark.asyncio
async def test_pr23_new_daily_snapshot_uses_daily_verdict_v3(monkeypatch) -> None:
    query, args = await _persist_pr22_daily_snapshot(monkeypatch)
    assert "regime_logic_version" in query
    assert args[3] == "daily-verdict-v4"


@pytest.mark.asyncio
async def test_pr22_daily_snapshot_copies_regime_logic_version(monkeypatch) -> None:
    _, args = await _persist_pr22_daily_snapshot(monkeypatch)
    assert args[7] == daily_agg.REGIME_LOGIC_VERSION


@pytest.mark.asyncio
async def test_pr23_daily_v3_does_not_copy_legacy_regime(monkeypatch) -> None:
    conn = _VerdictWriterConnection(
        reference=None,
        metrics={
            "ts": datetime(2026, 8, 11, 15, 0, tzinfo=UTC),
            "regime_score": 55.0,
            "regime_label": "legacy",
            "regime_logic_version": None,
        },
    )
    monkeypatch.setattr(daily_agg, "latest_closed_session_date", lambda: date(2026, 8, 11))
    monkeypatch.setattr(daily_agg, "swing_score", _no_signal)

    def reject_legacy_setup(*_args, **_kwargs):
        raise AssertionError("daily-verdict-v4 must not evaluate a legacy metrics snapshot")

    monkeypatch.setattr(daily_agg, "evaluate_setups", reject_legacy_setup)
    await daily_agg.persist_verdicts(conn, ("BTCUSDT_PERP.A",))
    query, args = next(
        (query, args)
        for query, args in conn.queries
        if "INSERT INTO daily_verdict_snapshot" in query
    )
    assert "logic_version" in query
    assert args[3] == "daily-verdict-v4"
    for index in (6, 7, 14, 15, 16, 17, 18, 19, 20):
        assert args[index] is None


@pytest.mark.asyncio
async def test_pr23_daily_v3_uses_regime_v2_when_available(monkeypatch) -> None:
    _, args = await _persist_pr22_daily_snapshot(monkeypatch)
    assert args[3] == "daily-verdict-v4"
    assert args[6] == datetime(2026, 8, 11, 15, 0, tzinfo=UTC)
    assert args[7] == daily_agg.REGIME_LOGIC_VERSION
    assert args[14] == 12.0
    assert args[15] == "v2"
