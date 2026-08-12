from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.signal_ledger import (
    classify_signal_observation,
    decision_fingerprint,
    select_reference_price,
    serialize_signal_evidence,
)


def _summary(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "long_score": 75.0,
        "short_score": 25.0,
        "state": "Long Momentum",
        "confidence": "alta",
        "reason": "measured evidence",
        "evidence_coverage_pct": 90.0,
        "book_status": "ok",
        "fut_price": 100.0,
        "basis_detail": {
            "fut_age_seconds": 2.0,
            "stale_after_seconds": 30.0,
        },
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("Long Momentum", ("evaluable", "long", True)),
        ("Long Pullback", ("evaluable", "long", True)),
        ("Short Momentum", ("evaluable", "short", True)),
        ("Short Rejection", ("evaluable", "short", True)),
        ("No Trade", ("evaluable", "neutral", False)),
    ],
)
def test_known_states_have_explicit_research_semantics(
    state: str,
    expected: tuple[str, str, bool],
) -> None:
    assert classify_signal_observation(_summary(state=state)) == expected


@pytest.mark.parametrize("book_status", ["missing", "stale"])
def test_fail_closed_no_trade_is_not_neutral(book_status: str) -> None:
    assert classify_signal_observation(
        _summary(state="No Trade", confidence="baja", book_status=book_status)
    ) == ("not_evaluable", "unavailable", False)


def test_insufficient_coverage_is_not_evaluable() -> None:
    assert classify_signal_observation(
        _summary(
            state="Sin datos suficientes",
            confidence="baja",
            evidence_coverage_pct=40.0,
        )
    ) == ("not_evaluable", "unavailable", False)


def test_unknown_future_state_fails_closed() -> None:
    assert classify_signal_observation(
        _summary(state="Future New State")
    ) == ("not_evaluable", "unavailable", False)


def test_reference_price_prefers_fresh_realtime_futures() -> None:
    ctx = {"ohlcv_price": 99.0, "fut_event_ms": 1_786_300_000_000}
    price, source, event_at = select_reference_price(ctx, _summary(fut_price=100.0))
    assert price == 100.0
    assert source == "futures_realtime_combined"
    assert event_at == datetime.fromtimestamp(1_786_300_000, UTC)


def test_reference_price_falls_back_only_to_explicit_closed_ohlcv() -> None:
    closed_at = datetime(2026, 8, 11, 12, 1, tzinfo=UTC)
    ctx = {
        "price": 100.5,
        "ohlcv_price": 99.0,
        "ohlcv_price_at": closed_at,
        "spot_price": 101.0,
    }
    assert select_reference_price(ctx, _summary(fut_price=None)) == (
        99.0,
        "ohlcv_1min_latest_closed",
        closed_at,
    )
    # A stale futures row can still occupy ctx["price"] via COALESCE. Never
    # relabel it as OHLCV.
    assert select_reference_price(
        ctx,
        _summary(
            fut_price=100.5,
            basis_detail={"fut_age_seconds": 120.0, "stale_after_seconds": 30.0},
        ),
    ) == (99.0, "ohlcv_1min_latest_closed", closed_at)
    assert select_reference_price(
        {"price": 100.5, "ohlcv_price": 99.0, "spot_price": 101.0},
        _summary(fut_price=None),
    ) == (None, None, None)


def test_evidence_preserves_null_and_serializes_timestamps() -> None:
    ts = datetime(2026, 8, 10, 1, 2, 3, tzinfo=UTC)
    payload = json.loads(
        serialize_signal_evidence(_summary(optional=None, nested={"at": ts}))
    )
    assert payload["optional"] is None
    assert payload["nested"]["at"] == ts.isoformat()


def test_evidence_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        serialize_signal_evidence(_summary(bad=float("nan")))


def test_fingerprint_tracks_semantics_not_score_noise() -> None:
    base = decision_fingerprint(
        "evaluable", "long", True, "Long Momentum", "alta"
    )
    same = decision_fingerprint(
        "evaluable", "long", True, "Long Momentum", "alta"
    )
    changed = decision_fingerprint(
        "evaluable", "short", True, "Short Momentum", "alta"
    )
    assert base == same
    assert base != changed
