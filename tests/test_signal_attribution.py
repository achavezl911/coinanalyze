from __future__ import annotations

import pytest

from app.signal_attribution import (
    SCALP_COMPONENTS,
    AttributionOptions,
    _aggregate_query,
    validate_attribution_options,
)
from app.signal_backtest import DENSE_PERIODIC, UTC_NONOVERLAP


def test_default_options_are_version_isolated_and_cover_all_v1_components() -> None:
    options = AttributionOptions()
    validate_attribution_options(options)

    assert options.components == SCALP_COMPONENTS
    assert options.logic_version == "scalp-summary-v1"
    assert options.evidence_version == 1
    assert options.sampling_version == 1
    assert options.context_version == 1
    assert options.outcome_version == 1
    assert options.sampling_modes == (DENSE_PERIODIC, UTC_NONOVERLAP)


@pytest.mark.parametrize(
    "options",
    [
        AttributionOptions(lookback_days=0),
        AttributionOptions(horizons=()),
        AttributionOptions(horizons=(15, 15)),
        AttributionOptions(horizons=(2,)),
        AttributionOptions(components=()),
        AttributionOptions(components=("book", "book")),
        AttributionOptions(components=("future_component",)),
        AttributionOptions(group_by=("symbol", "symbol")),
        AttributionOptions(group_by=("future_dimension",)),
        AttributionOptions(sampling_modes=("future_mode",)),
        AttributionOptions(min_group_n=0),
        AttributionOptions(logic_version="scalp-summary-v2"),
    ],
)
def test_invalid_options_fail_closed(options: AttributionOptions) -> None:
    with pytest.raises(ValueError):
        validate_attribution_options(options)


def test_component_and_horizon_are_always_group_dimensions() -> None:
    query = _aggregate_query(DENSE_PERIODIC, ("symbol", "regime_label"))
    assert (
        "GROUP BY symbol, regime_label, component, configured_weight, horizon_minutes"
        in query
    )


def test_utc_nonoverlap_selection_is_clock_only() -> None:
    query = _aggregate_query(UTC_NONOVERLAP, ("symbol",))
    tail = query.split("WHERE mod(", 1)[1].split("GROUP BY", 1)[0]
    assert "extract(epoch FROM observed_minute)" in query
    assert "component_value" not in tail
    assert "directional_return_pct" not in tail
    assert "state" not in tail


def test_attribution_never_queries_later_market_state() -> None:
    query = _aggregate_query(DENSE_PERIODIC, ("symbol",)).lower()

    for forbidden in (
        " from ohlcv",
        "futures_trades_realtime",
        "spot_trades_realtime",
        "orderbook_snapshot",
        "market_feed_health",
        "data_gap",
        "futures_trades_agg",
        "spot_trades_agg",
    ):
        assert forbidden not in query

    assert "signal_observation" in query
    assert "signal_replay_frame" in query
    assert "signal_outcome" in query
    assert "obs.is_periodic" in query
    assert "out.due_at <= $2" in query


def test_all_v1_components_are_extracted_from_frozen_material() -> None:
    query = _aggregate_query(DENSE_PERIODIC, ("symbol",))
    for component in SCALP_COMPONENTS:
        assert f"'{component}'::text" in query
    assert "b.evidence" in query
    assert "b.context" in query
    assert "missing_components" in query
