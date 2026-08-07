from datetime import UTC, date, datetime

import pytest

from app.metrics import compute_regime, current_nyse_start, session_bounds, whale_classification


def test_current_nyse_start_before_open_uses_previous_calendar_day():
    # Crypto opera 24/7: lunes 08:00 ET -> domingo 09:30 ET, no viernes.
    now = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)
    result = current_nyse_start(now)
    assert result == datetime(2026, 6, 21, 13, 30, tzinfo=UTC)


def test_current_nyse_start_does_not_merge_weekend_sessions():
    # Domingo 12:00 ET empieza el mismo domingo a las 09:30 ET.
    now = datetime(2026, 6, 21, 16, 0, tzinfo=UTC)
    assert current_nyse_start(now) == datetime(2026, 6, 21, 13, 30, tzinfo=UTC)


def test_session_bounds_follow_dst():
    start, end = session_bounds(date(2026, 3, 8))
    assert start < end
    # DST changed on March 8; calendar session is 23 hours in UTC.
    assert (end - start).total_seconds() == 23 * 3600


@pytest.mark.parametrize(
    ("buy", "sell", "asset", "expected_label", "sign"),
    [
        (4_000_000, 500_000, "BTC", "Sin operaciones spot de gran tamaño relevantes", 0),
        (5_000_000, 500_000, "ETH", "Acumulación agresiva", 1),
        (100_000, 900_000, "SOL", "Distribución agresiva", -1),
        (600_000, 400_000, "SOL", "Neutro", 1),
    ],
)
def test_whale_classification(buy, sell, asset, expected_label, sign):
    intensity, label = whale_classification(buy, sell, asset)
    assert label == expected_label
    assert (intensity > 0) - (intensity < 0) == sign


def test_compute_regime_organic_bullish():
    score, label = compute_regime(
        {
            "vol_24h": 100_000_000,
            "cvd_diff_24h": 10_000_000,
            "oi_chg_24h_pct": 5,
            "fr_avg": -0.001,
            "liq_ratio_24h": 0,
            "whale_intensity": 1,
            "whale_label": "Acumulación agresiva",
        }
    )
    assert score > 60
    assert label == "Continuación alcista orgánica"
