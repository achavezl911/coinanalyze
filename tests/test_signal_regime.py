from __future__ import annotations

import pytest

from app.signal_backtest import DENSE_PERIODIC, UTC_NONOVERLAP
from app.signal_regime import (
    RegimeAnalysisOptions,
    _alignment_query,
    _component_regime_query,
    _signal_regime_query,
    validate_regime_analysis_options,
)


def test_default_options_are_version_isolated() -> None:
    options = RegimeAnalysisOptions()
    validate_regime_analysis_options(options)

    assert options.logic_version == "scalp-summary-v1"
    assert options.evidence_version == 1
    assert options.sampling_version == 1
    assert options.context_version == 1
    assert options.outcome_version == 1
    assert options.sampling_modes == (DENSE_PERIODIC, UTC_NONOVERLAP)
    assert len(options.components) == 7


@pytest.mark.parametrize(
    "options",
    [
        RegimeAnalysisOptions(lookback_days=0),
        RegimeAnalysisOptions(horizons=()),
        RegimeAnalysisOptions(horizons=(15, 15)),
        RegimeAnalysisOptions(horizons=(2,)),
        RegimeAnalysisOptions(components=()),
        RegimeAnalysisOptions(components=("book", "book")),
        RegimeAnalysisOptions(components=("future_component",)),
        RegimeAnalysisOptions(sampling_modes=("future_mode",)),
        RegimeAnalysisOptions(min_group_n=0),
        RegimeAnalysisOptions(logic_version="scalp-summary-v2"),
    ],
)
def test_invalid_options_fail_closed(options: RegimeAnalysisOptions) -> None:
    with pytest.raises((ValueError, RuntimeError)):
        validate_regime_analysis_options(options)


def test_regime_queries_use_only_frozen_research_tables() -> None:
    queries = (
        _signal_regime_query(DENSE_PERIODIC, "regime_label"),
        _alignment_query(DENSE_PERIODIC),
        _component_regime_query(DENSE_PERIODIC),
    )
    for query in queries:
        lowered = query.lower()
        for forbidden in (
            " from metrics_snapshot",
            " from ohlcv",
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
        assert "obs.is_periodic" in lowered
        assert "out.due_at <= $2" in lowered


def test_score_band_and_label_views_are_distinct() -> None:
    label_query = _signal_regime_query(DENSE_PERIODIC, "regime_label")
    band_query = _signal_regime_query(DENSE_PERIODIC, "regime_score_band")
    assert "GROUP BY symbol,regime_label,horizon_minutes" in label_query
    assert "GROUP BY symbol,regime_score_band,horizon_minutes" in band_query


def test_utc_nonoverlap_selection_is_clock_only() -> None:
    query = _alignment_query(UTC_NONOVERLAP)
    sample_clause = query.split("WHERE mod(", 1)[1].split("),", 1)[0]
    assert "extract(epoch FROM observed_minute)" in query
    assert "regime_score" not in sample_clause
    assert "directional_return_pct" not in sample_clause


def test_component_regime_query_reuses_pr8_component_contract() -> None:
    query = _component_regime_query(DENSE_PERIODIC)
    assert "missing_components" in query
    for component in (
        "fut_delta",
        "spot_fut_divergence",
        "book",
        "absorption",
        "liquidations",
        "oi",
        "vwap",
    ):
        assert f"'{component}'::text" in query
