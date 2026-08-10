from __future__ import annotations

import pytest

from app.signal_backtest import (
    DENSE_PERIODIC,
    UTC_NONOVERLAP,
    BacktestOptions,
    _aggregate_query,
    validate_backtest_options,
)


def test_default_options_are_version_isolated_and_use_both_sampling_views() -> None:
    options = BacktestOptions()
    validate_backtest_options(options)

    assert options.logic_version
    assert options.evidence_version == 1
    assert options.sampling_version == 1
    assert options.context_version == 1
    assert options.outcome_version == 1
    assert options.sampling_modes == (DENSE_PERIODIC, UTC_NONOVERLAP)


@pytest.mark.parametrize(
    "options",
    [
        BacktestOptions(lookback_days=0),
        BacktestOptions(horizons=()),
        BacktestOptions(horizons=(15, 15)),
        BacktestOptions(horizons=(2,)),
        BacktestOptions(group_by=("symbol", "symbol")),
        BacktestOptions(group_by=("future_unknown_dimension",)),
        BacktestOptions(sampling_modes=("future_unknown_mode",)),
        BacktestOptions(min_group_n=0),
    ],
)
def test_invalid_options_fail_closed(options: BacktestOptions) -> None:
    with pytest.raises(ValueError):
        validate_backtest_options(options)


def test_horizon_is_always_grouped_even_when_not_requested_explicitly() -> None:
    query = _aggregate_query(DENSE_PERIODIC, ("symbol", "state"))
    assert "GROUP BY symbol, state, horizon_minutes" in query
    assert "ORDER BY symbol, state, horizon_minutes" in query


def test_utc_nonoverlap_selection_is_clock_based_not_signal_based() -> None:
    query = _aggregate_query(UTC_NONOVERLAP, ("symbol",))
    assert "extract(epoch FROM observed_minute)" in query
    assert "horizon_minutes::bigint" in query
    assert "directional_return_pct" not in query.split("WHERE mod(", 1)[1].split("GROUP BY", 1)[0]
    assert "state" not in query.split("WHERE mod(", 1)[1].split("GROUP BY", 1)[0]


def test_backtest_never_queries_live_market_tables() -> None:
    query = _aggregate_query(DENSE_PERIODIC, ("symbol",))
    lowered = query.lower()
    for forbidden in (
        "ohlcv",
        "futures_trades_realtime",
        "spot_trades_realtime",
        "orderbook_snapshot",
        "market_feed_health",
        "data_gap",
    ):
        assert forbidden not in lowered

    assert "signal_observation" in lowered
    assert "signal_replay_frame" in lowered
    assert "signal_outcome" in lowered
