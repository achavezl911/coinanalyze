from datetime import UTC, datetime, timedelta

import pytest

import app.api as api
from app.api import mask_gapped_series_rows
from app.data_gaps import (
    DataGap,
    RecoveryObservation,
    RecoveryValidationError,
    missing_cadence_windows,
    record_data_gap,
    validate_recovery,
)


def test_missing_cadence_windows_use_the_supplied_feed_cadence() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    assert missing_cadence_windows(
        [start, start + timedelta(minutes=3)],
        start=start,
        end=start + timedelta(minutes=4),
        cadence=timedelta(minutes=1),
    ) == [(start + timedelta(minutes=1), start + timedelta(minutes=3))]


async def test_event_stream_silence_cannot_be_recorded_as_missing_cadence() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)

    class NoQueryConnection:
        async def fetchval(self, *_args):
            raise AssertionError("invalid event-stream evidence must fail before SQL")

    with pytest.raises(ValueError, match="silence"):
        await record_data_gap(
            NoQueryConnection(),  # type: ignore[arg-type]
            feed="liquidations",
            feed_class="event_stream",
            exchange="binance",
            market="perpetual",
            symbol="BTCUSDT_PERP.A",
            granularity="event",
            start=start,
            end=start + timedelta(minutes=5),
            evidence_type="missing_interval",
            detection_reason="no events arrived",
            detection_source="silence detector",
        )


class _Adapter:
    name = "exact"
    feed = "ohlcv_1min"
    exchange = "binance"
    market = "perpetual"
    granularity = "1min"


def test_recovery_rejects_wrong_symbol_even_when_http_source_fields_match() -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    gap = DataGap(
        1,
        "ohlcv_1min",
        "cadence",
        "binance",
        "perpetual",
        "BTCUSDT_PERP.A",
        "1min",
        start,
        start + timedelta(minutes=1),
        timedelta(minutes=1),
        "unresolved",
    )
    observation = RecoveryObservation(
        start,
        "one",
        "ohlcv_1min",
        "binance",
        "perpetual",
        "ETHUSDT_PERP.A",
        "1min",
        {},
    )
    with pytest.raises(RecoveryValidationError, match="identity"):
        validate_recovery(gap, _Adapter(), [observation])  # type: ignore[arg-type]


async def test_chart_gap_nulls_the_bucket_and_all_later_cumulative_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start = datetime(2026, 8, 9, 12, tzinfo=UTC)
    rows = [
        {"bucket": start + timedelta(minutes=index), "delta": 1.0, "cvd": index + 1.0}
        for index in range(3)
    ]

    async def blocked(_conn, _requirements):
        return {"value:1", "cumulative:1", "cumulative:2"}

    monkeypatch.setattr(api, "blocking_requirement_keys", blocked)
    await mask_gapped_series_rows(
        object(),  # type: ignore[arg-type]
        rows,
        bucket=timedelta(minutes=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("delta",),
        cumulative_keys=("cvd",),
    )

    assert rows == [
        {"bucket": start, "delta": 1.0, "cvd": 1.0},
        {"bucket": start + timedelta(minutes=1), "delta": None, "cvd": None},
        {"bucket": start + timedelta(minutes=2), "delta": 1.0, "cvd": None},
    ]
