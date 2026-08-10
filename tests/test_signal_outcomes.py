from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.cutoffs import OHLCV_1M_REFRESH_LOOKBACK_SECONDS
from app.signal_outcomes import (
    OUTCOME_SETTLEMENT_LAG,
    compute_path_metrics,
    expected_bar_timestamps,
    outcome_window,
)


def test_settlement_waits_until_ohlcv_revision_window_is_closed() -> None:
    assert timedelta(
        seconds=OHLCV_1M_REFRESH_LOOKBACK_SECONDS
    ) < OUTCOME_SETTLEMENT_LAG


def test_outcome_window_starts_at_first_full_minute_after_observation() -> None:
    observed = datetime(2026, 8, 10, 15, 22, 17, 250000, tzinfo=UTC)
    window = outcome_window(observed, 3)
    assert window.start == datetime(2026, 8, 10, 15, 23, tzinfo=UTC)
    assert window.end == datetime(2026, 8, 10, 15, 26, tzinfo=UTC)
    assert window.due_at == window.end + OUTCOME_SETTLEMENT_LAG
    assert window.start_delay_seconds == pytest.approx(42.75)


def test_exact_timestamp_grid_has_one_bar_per_minute() -> None:
    start = datetime(2026, 8, 10, 15, 23, tzinfo=UTC)
    assert expected_bar_timestamps(start, 3) == (
        start,
        start + timedelta(minutes=1),
        start + timedelta(minutes=2),
    )


@pytest.mark.parametrize("horizon", [0, 2, 7, 1440])
def test_unknown_horizon_fails_closed(horizon: int) -> None:
    with pytest.raises(ValueError):
        outcome_window(datetime.now(UTC), horizon)


def test_long_path_metrics() -> None:
    metrics = compute_path_metrics(
        100.0,
        "long",
        [
            {"high": 103.0, "low": 99.0, "close": 102.0},
            {"high": 104.0, "low": 98.0, "close": 101.0},
        ],
    )
    assert metrics.market_return_pct == pytest.approx(1.0)
    assert metrics.directional_return_pct == pytest.approx(1.0)
    assert metrics.mfe_pct == pytest.approx(4.0)
    assert metrics.mae_pct == pytest.approx(2.0)


def test_short_path_metrics_are_direction_adjusted() -> None:
    metrics = compute_path_metrics(
        100.0,
        "short",
        [{"high": 103.0, "low": 97.0, "close": 98.0}],
    )
    assert metrics.market_return_pct == pytest.approx(-2.0)
    assert metrics.directional_return_pct == pytest.approx(2.0)
    assert metrics.mfe_pct == pytest.approx(3.0)
    assert metrics.mae_pct == pytest.approx(3.0)


@pytest.mark.parametrize("direction", ["neutral", "unavailable"])
def test_non_directional_path_keeps_no_fake_trade_metrics(direction: str) -> None:
    metrics = compute_path_metrics(
        100.0,
        direction,
        [{"high": 101.0, "low": 99.0, "close": 100.5}],
    )
    assert metrics.market_return_pct == pytest.approx(0.5)
    assert metrics.directional_return_pct is None
    assert metrics.mfe_pct is None
    assert metrics.mae_pct is None
