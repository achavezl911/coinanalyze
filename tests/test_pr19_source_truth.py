from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.data_gaps as data_gaps
import app.ingest as ingest
import app.scalp_collector as scalp_collector
from app.data_gaps import reconcile_cadence_coverage
from app.metrics import _liquidation_history_observed


class GapConn:
    def __init__(self, unresolved=None):
        self.unresolved = unresolved or []
        self.executed = []

    async def fetch(self, query, *_args):
        return self.unresolved if "FROM data_gap" in query else []

    async def execute(self, query, *args):
        self.executed.append((query, args))
        if "SET status='recovered'" in query:
            return "UPDATE 1"
        return "UPDATE 0"


@pytest.mark.asyncio
async def test_reconcile_cadence_detects_start_internal_end(monkeypatch):
    start = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=5)
    seen = [start + timedelta(minutes=1), start + timedelta(minutes=3)]
    recorded = []

    async def fake_record(_conn, **kw):
        recorded.append((kw["start"], kw["end"], kw["detection_source"]))
        return len(recorded)

    monkeypatch.setattr(data_gaps, "record_data_gap", fake_record)
    result = await reconcile_cadence_coverage(
        GapConn(), observations=seen, feed="ohlcv_1min", exchange="binance",
        market="perpetual", symbol="BTCUSDT_PERP.A", granularity="1min",
        start=start, end=end, cadence=timedelta(minutes=1), detection_source="response_test",
    )
    assert result.expected_buckets == 5
    assert result.observed_buckets == 2
    assert result.missing_buckets == 3
    assert [(a, b) for a, b, _ in recorded] == [
        (start, start + timedelta(minutes=1)),
        (start + timedelta(minutes=2), start + timedelta(minutes=3)),
        (start + timedelta(minutes=4), end),
    ]
    assert {source for _, _, source in recorded} == {"response_test"}


@pytest.mark.asyncio
async def test_reconcile_cadence_recovers_gap_found_by_other_detector(monkeypatch):
    start = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    end = start + timedelta(minutes=3)
    conn = GapConn([{"id": 7, "start_ts": start + timedelta(minutes=1), "end_ts": end}])

    async def no_record(_conn, **_kw):
        raise AssertionError("complete cadence must not create a gap")

    monkeypatch.setattr(data_gaps, "record_data_gap", no_record)
    result = await reconcile_cadence_coverage(
        conn,
        observations=[start, start + timedelta(minutes=1), start + timedelta(minutes=2)],
        feed="ohlcv_1min", exchange="binance", market="perpetual",
        symbol="BTCUSDT_PERP.A", granularity="1min",
        start=start, end=end, cadence=timedelta(minutes=1),
        detection_source="canonical_storage_after_response_detector",
    )
    assert result.complete
    assert result.recovered_gaps == 1


def test_liquidation_empty_event_history_is_healthy_observation():
    start = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    payload = {"BTCUSDT_PERP.A": [], "ETHUSDT_PERP.A": [], "SOLUSDT_PERP.A": []}
    status, detail_text = ingest._liquidation_history_observation(
        payload, tuple(payload), accepted_rows=0, source_start=start, source_cutoff=cutoff
    )
    detail = json.loads(detail_text)
    assert status == "ok"
    assert detail["returned_rows"] == 0
    assert detail["accepted_rows"] == 0
    assert detail["missing_symbols"] == []
    assert detail["requested_symbol_names"] == sorted(payload)
    assert detail["observed_symbol_names"] == sorted(payload)
    assert detail["source_cutoff_ts"] == int(cutoff.timestamp())


def test_liquidation_missing_symbol_is_degraded_not_zero():
    requested = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")
    payload = {"BTCUSDT_PERP.A": [], "ETHUSDT_PERP.A": []}
    status, detail_text = ingest._liquidation_history_observation(
        payload, requested, accepted_rows=0,
        source_start=datetime(2026, 8, 10, 10, tzinfo=UTC),
        source_cutoff=datetime(2026, 8, 11, 12, tzinfo=UTC),
    )
    assert status == "degraded"
    assert json.loads(detail_text)["missing_symbols"] == ["SOLUSDT_PERP.A"]


def test_liquidation_rejected_returned_row_is_degraded():
    payload = {"BTCUSDT_PERP.A": [{"t": 1, "l": -1, "s": 2}]}
    status, detail_text = ingest._liquidation_history_observation(
        payload, ("BTCUSDT_PERP.A",), accepted_rows=0,
        source_start=datetime(2026, 8, 10, 10, tzinfo=UTC),
        source_cutoff=datetime(2026, 8, 11, 12, tzinfo=UTC),
    )
    assert status == "degraded"
    assert json.loads(detail_text)["reason"] == "rejected_rows"


class HeartbeatConn:
    def __init__(self, rows):
        self.rows = rows

    async def fetch(self, _query, *_args):
        return self.rows


@pytest.mark.asyncio
async def test_liquidation_history_health_requires_exact_source_cutoff():
    required_end = datetime(2026, 8, 11, 12, 5, tzinfo=UTC)
    required_start = required_end - timedelta(hours=24)
    now = required_end + timedelta(seconds=30)
    detail = json.dumps({
        "source_start_ts": int((required_start - timedelta(hours=2)).timestamp()),
        "source_cutoff_ts": int(required_end.timestamp()),
        "requested_symbols": 1,
        "observed_symbols": 1,
        "requested_symbol_names": ["BTCUSDT_PERP.A"],
        "observed_symbol_names": ["BTCUSDT_PERP.A"],
        "missing_symbols": [],
        "returned_rows": 0,
        "accepted_rows": 0,
        "reason": "complete_observation",
    })
    conn = HeartbeatConn([{"status": "ok", "updated_at": now, "detail": detail}])
    assert await _liquidation_history_observed(
        conn, symbol="BTCUSDT_PERP.A", required_start=required_start,
        required_end=required_end, now_utc=now,
    )

    behind = json.dumps({
        "source_start_ts": int((required_start - timedelta(hours=2)).timestamp()),
        "source_cutoff_ts": int((required_end - timedelta(minutes=5)).timestamp()),
        "requested_symbols": 1,
        "observed_symbols": 1,
        "requested_symbol_names": ["BTCUSDT_PERP.A"],
        "observed_symbol_names": ["BTCUSDT_PERP.A"],
        "missing_symbols": [],
        "returned_rows": 0,
        "accepted_rows": 0,
        "reason": "complete_observation",
    })
    conn = HeartbeatConn([{"status": "ok", "updated_at": now, "detail": behind}])
    assert not await _liquidation_history_observed(
        conn, symbol="BTCUSDT_PERP.A", required_start=required_start,
        required_end=required_end, now_utc=now,
    )


@pytest.mark.asyncio
async def test_liquidation_history_health_rejects_stale_or_degraded():
    end = datetime(2026, 8, 11, 12, 5, tzinfo=UTC)
    start = end - timedelta(hours=24)
    now = end + timedelta(minutes=8)
    detail = json.dumps({
        "source_start_ts": int((start - timedelta(hours=2)).timestamp()),
        "source_cutoff_ts": int(end.timestamp()),
        "requested_symbols": 1,
        "observed_symbols": 1,
        "requested_symbol_names": ["BTCUSDT_PERP.A"],
        "observed_symbol_names": ["BTCUSDT_PERP.A"],
        "missing_symbols": [],
        "returned_rows": 0,
        "accepted_rows": 0,
        "reason": "complete_observation",
    })
    stale = HeartbeatConn([{"status": "ok", "updated_at": end, "detail": detail}])
    assert not await _liquidation_history_observed(
        stale, symbol="BTCUSDT_PERP.A", required_start=start,
        required_end=end, now_utc=now,
    )
    degraded = HeartbeatConn([{"status": "degraded", "updated_at": now, "detail": detail}])
    assert not await _liquidation_history_observed(
        degraded, symbol="BTCUSDT_PERP.A", required_start=start,
        required_end=end, now_utc=now,
    )


def test_liquidations_are_not_declared_dense_cadence():
    root = Path(__file__).resolve().parents[1]
    ingest_src = (root / "app" / "ingest.py").read_text()
    metrics_src = (root / "app" / "metrics.py").read_text()
    cadence_block = ingest_src.split("_CADENCE_TABLES =", 1)[1].split("})", 1)[0]
    assert '"liquidations"' not in cadence_block
    assert '"liquidations_24h", "liquidations_5min"' not in metrics_src
    assert "ingest:liquidations_history" in ingest_src
    assert "ingest:liquidations_history" in metrics_src


def test_dense_metrics_use_current_response_proof_not_only_persisted_rows():
    root = Path(__file__).resolve().parents[1]
    src = (root / "app" / "ingest.py").read_text()
    assert "metric_observations" in src
    assert "_reconcile_response_cadence" in src
    assert "historical_ingest_response_cadence_v2" in src
    assert "ohlcv_1min@binance:persisted24h" in src
    assert "ohlcv_1min@binance:response40m" in src


class CaptureConn:
    def __init__(self):
        self.sql = []

    async def executemany(self, query, _rows):
        self.sql.append(query)

    async def execute(self, query, *_args):
        self.sql.append(query)


@pytest.mark.asyncio
async def test_futures_combined_materializers_require_two_venues():
    conn = CaptureConn()
    touched = [(("BTCUSDT_PERP.A", "binance", 1_700_000_000), None)]
    await scalp_collector._write_combined_realtime(conn, touched)  # type: ignore[arg-type]
    await scalp_collector._write_combined_minute(conn, touched)  # type: ignore[arg-type]
    for query in conn.sql:
        assert "HAVING COUNT(DISTINCT exchange)=2" in query
        assert "venue_count" in query
        assert "'combined',2" in query


@pytest.mark.asyncio
async def test_combined_orderbook_requires_two_venues():
    conn = CaptureConn()
    await scalp_collector._write_combined_books(
        conn, [SimpleNamespace(symbol="BTCUSDT_PERP.A")]  # type: ignore[list-item]
    )
    assert "HAVING COUNT(DISTINCT exchange)=2" in conn.sql[0]
    assert "2::smallint AS venue_count" in conn.sql[0]


def test_spot_combined_writers_require_two_venues():
    src = (Path(__file__).resolve().parents[1] / "app" / "ws_collector.py").read_text()
    assert src.count("HAVING COUNT(DISTINCT exchange)=2") >= 2
    assert "SELECT ts,symbol,'combined',2,'1min'" in src
    assert "SELECT ts,symbol,'combined',2,SUM(buy_vol_usd)" in src


def test_combined_consumers_reject_legacy_rows():
    root = Path(__file__).resolve().parents[1]
    for rel in ("app/api.py", "app/scalp_logic.py", "app/daily_agg.py"):
        src = (root / rel).read_text()
        assert not re.search(r"exchange='combined'(?! AND venue_count=2)", src)
        assert "exchange='combined' AND venue_count=2" in src
    metrics = (root / "app" / "metrics.py").read_text()
    assert not re.search(r"exchange = 'combined'(?! AND venue_count = 2)", metrics)
    assert "exchange = 'combined' AND venue_count = 2" in metrics


def test_pr19_evidence_version_boundary():
    from app.signal_attribution import AttributionOptions
    from app.signal_backtest import BacktestOptions
    from app.signal_ledger import SIGNAL_EVIDENCE_VERSION, SIGNAL_SAMPLING_VERSION
    from app.signal_regime import RegimeAnalysisOptions
    from app.signal_replay import REPLAY_CONTEXT_VERSION

    assert SIGNAL_EVIDENCE_VERSION == 6
    assert SIGNAL_SAMPLING_VERSION == 1
    assert REPLAY_CONTEXT_VERSION == 1
    assert BacktestOptions().evidence_version == 1
    assert AttributionOptions().evidence_version == 1
    assert RegimeAnalysisOptions().evidence_version == 1


def test_v1_research_cli_defaults_do_not_follow_live_writer_version():
    root = Path(__file__).resolve().parents[1]
    expected = {
        "scripts/backtest_signals.py": "default=DEFAULT_EVIDENCE_VERSION",
        "scripts/attribute_signals.py": "default=DEFAULT_EVIDENCE_VERSION",
        "scripts/analyze_signal_regimes.py": "default=DEFAULT_EVIDENCE_VERSION",
    }
    for rel, marker in expected.items():
        src = (root / rel).read_text()
        assert "default=SIGNAL_EVIDENCE_VERSION" not in src
        assert marker in src
