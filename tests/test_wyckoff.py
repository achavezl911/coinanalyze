from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from app.wyckoff import detect_latest_range, wyckoff_auto_read


def _range_bars(count: int = 240, buy_share: float = 0.5) -> list[dict]:
    start = datetime(2025, 12, 1, tzinfo=UTC)
    rows = []
    for index in range(count):
        centre = 100 + 8 * math.sin(index * 2 * math.pi / 14)
        open_px = centre - 0.8 * math.sin(index * 2 * math.pi / 7)
        rows.append(
            {
                "ts": start + timedelta(days=index),
                "open": open_px,
                "high": centre + 2,
                "low": centre - 2,
                "close": centre,
                "volume": 1_000 + index % 9 * 20,
                "buy_volume": (1_000 + index % 9 * 20) * buy_share,
            }
        )
    return rows


def _sessions(bars: list[dict], cvd: float) -> list[dict]:
    return [
        {
            "session_date": row["ts"].date(),
            "cvd_spot_usd": cvd,
            "oi_close": 1_000_000 + index * 100,
            "fr_avg": 0.01,
        }
        for index, row in enumerate(bars)
    ]


def test_detects_range_without_user_supplied_boundaries() -> None:
    result = detect_latest_range(_range_bars())
    assert result["available"] is True
    assert result["low"] < 100 < result["high"]
    assert result["validation"]["passed"] >= 3
    assert "percentil 5" in result["bounds_method"]


def test_bullish_flow_is_compatible_with_accumulation() -> None:
    bars = _range_bars(buy_share=0.68)
    result = wyckoff_auto_read(bars, _sessions(bars, 2_000_000))
    assert result["available"] is True
    assert result["bias"]["bias"] == "bullish"
    assert result["bias"]["reading"] == "compatible_con_acumulacion"
    assert result["bias"]["score"] >= 25


def test_bearish_flow_is_compatible_with_distribution() -> None:
    bars = _range_bars(buy_share=0.32)
    result = wyckoff_auto_read(bars, _sessions(bars, -2_000_000))
    assert result["available"] is True
    assert result["bias"]["bias"] == "bearish"
    assert result["bias"]["reading"] == "compatible_con_distribucion"
    assert result["bias"]["score"] <= -25


def test_trend_is_not_forced_into_a_range() -> None:
    start = datetime(2025, 12, 1, tzinfo=UTC)
    bars = []
    for index in range(240):
        close = 100 + index * 1.5
        bars.append(
            {
                "ts": start + timedelta(days=index),
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": 1_000,
                "buy_volume": 600,
            }
        )
    result = wyckoff_auto_read(bars, _sessions(bars, 1_000_000))
    assert result["available"] is False
    assert "rango" in result["reason"].lower()


def test_output_contains_chart_and_actionable_boundaries() -> None:
    bars = _range_bars()
    result = wyckoff_auto_read(bars, _sessions(bars, 0))
    assert result["available"] is True
    assert len(result["chart_bars"]) >= result["range"]["bars"]
    assert result["range"]["low"] < result["range"]["mid"] < result["range"]["high"]
    assert "cierres diarios" in result["trade_map"]["long_confirmation"].lower()
    assert "retest" in result["trade_map"]["short_confirmation"].lower()


def test_dashboard_exposes_automatic_module_and_daily_chart_mode() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "app.js").read_text(encoding="utf-8")
    assert 'id="wyckoff-body"' in html
    assert 'id="price-mode-wyckoff"' in html
    assert "/api/wyckoff?symbol=" in js
    assert "WYK soporte" in js and "WYK resistencia" in js
