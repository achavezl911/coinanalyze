from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.calibrate_signals import select_samples

ROOT = Path(__file__).resolve().parents[1]


def test_scalp_collector_does_not_import_api_layer() -> None:
    source = (ROOT / "app" / "scalp_collector.py").read_text(encoding="utf-8")
    assert "from app.api" not in source
    assert "from app.scalp_logic import" in source


def test_scalp_logic_is_pure_of_fastapi_static_mounts() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    assert "FastAPI" not in source
    assert "StaticFiles" not in source
    assert "app.mount" not in source


def test_frontend_wires_v120_backend_endpoints() -> None:
    source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    for endpoint in (
        "/api/dashboard/state",
        "/api/scalp/basis",
        "/api/scalp/liquidation-levels",
    ):
        assert endpoint in source
    markup = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "basis-details" in markup
    assert "market-memory" in markup
    assert "signals-body" not in markup
    assert "liq-levels-body" in markup


def test_frontend_discards_stale_symbol_responses_and_clears_old_data() -> None:
    source = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
    assert "const symbol = state.symbol" in source
    assert "if (symbol !== state.symbol) return" in source
    assert "clearSymbolView();" in source
    assert "await refreshOverview(true)" in source
    assert "else clearSnapshotView();" in source
    assert "Datos no disponibles" in source


def test_calibration_episode_sampling_deduplicates_stable_state() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        {"ts": base + timedelta(seconds=i * 10), "symbol": "BTCUSDT_PERP.A", "state": "Long Momentum", "confidence": "alta", "long_score": 75.0, "short_score": 25.0}
        for i in range(5)
    ]
    rows.append({"ts": base + timedelta(minutes=1), "symbol": "BTCUSDT_PERP.A", "state": "Short Rejection", "confidence": "media", "long_score": 35.0, "short_score": 65.0})
    selected = select_samples(rows, "episode", non_overlap_minutes=60)
    assert len(selected) == 2
    assert selected[0]["state"] == "Long Momentum"
    assert selected[1]["state"] == "Short Rejection"


def test_calibration_non_overlap_sampling_deduplicates_by_spacing() -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        {"ts": base, "symbol": "BTCUSDT_PERP.A", "state": "Long Momentum", "confidence": "alta", "long_score": 75.0, "short_score": 25.0},
        {"ts": base + timedelta(minutes=30), "symbol": "BTCUSDT_PERP.A", "state": "Long Momentum", "confidence": "alta", "long_score": 75.0, "short_score": 25.0},
        {"ts": base + timedelta(minutes=61), "symbol": "BTCUSDT_PERP.A", "state": "Long Momentum", "confidence": "alta", "long_score": 75.0, "short_score": 25.0},
    ]
    selected = select_samples(rows, "non_overlap", non_overlap_minutes=60)
    assert [row["ts"] for row in selected] == [rows[0]["ts"], rows[2]["ts"]]
