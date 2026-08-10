from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.signal_execution import (
    DENSE_PERIODIC,
    EXECUTION_SIZES_USD,
    UTC_NONOVERLAP,
    ExecutionCostOptions,
    _execution_outcome_query,
    execution_snapshot_record,
    validate_execution_cost_options,
)


def _book_row(
    *,
    ts: datetime,
    bids: list[list[float]] | None = None,
    asks: list[list[float]] | None = None,
) -> dict[str, object]:
    return {
        "exchange": "binance",
        "ts": ts,
        "bids": bids or [[99.9, 2_000.0], [99.8, 2_000.0]],
        "asks": asks or [[100.1, 2_000.0], [100.2, 2_000.0]],
        "levels": 2,
    }


def test_valid_snapshot_builds_exact_versioned_cost_grid() -> None:
    observed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    snapshot = execution_snapshot_record(
        exchange="binance",
        observed_at=observed,
        row=_book_row(ts=observed - timedelta(seconds=2)),
    )

    assert snapshot["status"] == "valid"
    assert snapshot["reason"] is None
    assert snapshot["best_bid_px"] == pytest.approx(99.9)
    assert snapshot["best_ask_px"] == pytest.approx(100.1)
    assert snapshot["mid_px"] == pytest.approx(100.0)
    assert snapshot["spread_bps"] == pytest.approx(20.0)
    assert len(snapshot["source_book_hash"]) == 64
    assert sorted(float(key) for key in snapshot["cost_curve"]) == list(
        EXECUTION_SIZES_USD
    )

    first = snapshot["cost_curve"]["1000"]
    assert first["buy"]["insufficient_depth"] is False
    assert first["sell"]["insufficient_depth"] is False
    assert first["buy"]["market_cost_bps_vs_mid"] == pytest.approx(10.0)
    assert first["sell"]["market_cost_bps_vs_mid"] == pytest.approx(10.0)


def test_insufficient_depth_is_not_extrapolated() -> None:
    observed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    snapshot = execution_snapshot_record(
        exchange="binance",
        observed_at=observed,
        row=_book_row(
            ts=observed - timedelta(seconds=1),
            bids=[[99.9, 1.0]],
            asks=[[100.1, 1.0]],
        ),
    )

    assert snapshot["status"] == "valid"
    large = snapshot["cost_curve"]["100000"]
    assert large["buy"]["insufficient_depth"] is True
    assert large["buy"]["market_cost_bps_vs_mid"] is None
    assert large["sell"]["insufficient_depth"] is True
    assert large["sell"]["market_cost_bps_vs_mid"] is None


@pytest.mark.parametrize(
    ("age_seconds", "expected_status", "expected_reason"),
    [
        (31.0, "stale", "book_older_than_realtime_limit"),
        (-1.0, "error", "future_book_timestamp"),
    ],
)
def test_snapshot_fails_closed_on_time_integrity(
    age_seconds: float,
    expected_status: str,
    expected_reason: str,
) -> None:
    observed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    snapshot = execution_snapshot_record(
        exchange="binance",
        observed_at=observed,
        row=_book_row(ts=observed - timedelta(seconds=age_seconds)),
    )

    assert snapshot["status"] == expected_status
    assert snapshot["reason"] == expected_reason
    assert snapshot["cost_curve"] == {}


def test_missing_venue_is_explicit_unavailable() -> None:
    observed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
    snapshot = execution_snapshot_record(
        exchange="bybit",
        observed_at=observed,
        row=None,
    )

    assert snapshot["status"] == "unavailable"
    assert snapshot["reason"] == "no_current_orderbook_depth"
    assert snapshot["cost_curve"] == {}


def test_crossed_or_unordered_book_is_not_used() -> None:
    observed = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

    crossed = execution_snapshot_record(
        exchange="binance",
        observed_at=observed,
        row=_book_row(
            ts=observed,
            bids=[[100.2, 1_000.0]],
            asks=[[100.1, 1_000.0]],
        ),
    )
    assert crossed["status"] == "error"
    assert crossed["reason"] == "crossed_or_missing_best_quotes"
    assert crossed["cost_curve"] == {}

    unordered = execution_snapshot_record(
        exchange="binance",
        observed_at=observed,
        row=_book_row(
            ts=observed,
            bids=[[99.8, 1_000.0], [99.9, 1_000.0]],
            asks=[[100.1, 1_000.0], [100.2, 1_000.0]],
        ),
    )
    assert unordered["status"] == "error"
    assert unordered["reason"] == "invalid_or_unordered_depth"
    assert unordered["cost_curve"] == {}


@pytest.mark.parametrize(
    "options",
    [
        ExecutionCostOptions(lookback_days=0),
        ExecutionCostOptions(horizons=()),
        ExecutionCostOptions(horizons=(15, 15)),
        ExecutionCostOptions(horizons=(2,)),
        ExecutionCostOptions(sizes_usd=()),
        ExecutionCostOptions(sizes_usd=(1234.0,)),
        ExecutionCostOptions(sampling_modes=("future_mode",)),
        ExecutionCostOptions(fee_bps_per_side=(("binance", -1.0),)),
        ExecutionCostOptions(fee_bps_per_side=(("future", 1.0),)),
        ExecutionCostOptions(logic_version="scalp-summary-v2"),
    ],
)
def test_invalid_options_fail_closed(options: ExecutionCostOptions) -> None:
    with pytest.raises(ValueError):
        validate_execution_cost_options(options)


def test_report_query_uses_frozen_snapshots_not_current_book() -> None:
    query = _execution_outcome_query(DENSE_PERIODIC).lower()

    assert "signal_execution_snapshot" in query
    assert "signal_observation" in query
    assert "signal_replay_frame" in query
    assert "signal_outcome" in query

    for forbidden in (
        "orderbook_depth",
        "orderbook_snapshot",
        "futures_trades_realtime",
        "spot_trades_realtime",
        "market_feed_health",
        "data_gap",
    ):
        assert forbidden not in query


def test_utc_nonoverlap_remains_clock_only() -> None:
    query = _execution_outcome_query(UTC_NONOVERLAP)
    sample_clause = query.split("WHERE mod(", 1)[1].split("),", 1)[0]
    assert "extract(epoch FROM observed_minute)" in query
    assert "entry_market_cost_bps" not in sample_clause
    assert "directional_return_pct" not in sample_clause
