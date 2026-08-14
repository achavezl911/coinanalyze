from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.scalp_logic import compute_scalp_summary
from app.signal_replay import (
    REPLAY_CONTEXT_VERSION,
    SCALP_SIGNAL_LOGIC_VERSION,
    ReplayUnsupportedLogicVersion,
    canonical_json_hash,
    canonical_json_object,
    classify_signal_observation,
    replay_context_as_of,
    replay_summary_for_logic,
    validate_replay_observation_record,
    validated_signal_observation_fields,
)


def _ctx(**overrides: object) -> dict[str, object]:
    now_ms = 1_786_300_000_000.0
    row: dict[str, object] = {
        "now_ms": now_ms,
        "price": 100.0,
        "ohlcv_price": 99.9,
        "fut_price": 100.0,
        "spot_price": 99.9,
        "fut_event_ms": now_ms - 1_000,
        "spot_event_ms": now_ms - 1_200,
        "fut_delta_1m": 100.0,
        "fut_volume_1m": 1_000.0,
        "fut_delta_3m": 150.0,
        "fut_volume_3m": 3_000.0,
        "spot_delta_3m": 50.0,
        "spot_volume_3m": 2_000.0,
        "imbalance_l1": 0.05,
        "imbalance_l5": 0.10,
        "imbalance_l10": 0.08,
        "spread_bps": 1.5,
        "book_status": "ok",
        "book_lag_seconds": 1.0,
        "first_px_3m": 99.8,
        "last_px_3m": 100.0,
        "bars_15m": 0,
        "price_move_15m_coverage": "none",
        "oi_window_status": "unavailable",
        "optional": None,
    }
    row.update(overrides)
    return row


def test_context_serialization_is_canonical_and_preserves_null_and_timestamp() -> None:
    ts = datetime(2026, 8, 10, 12, 34, 56, tzinfo=UTC)
    left = _ctx(nested={"at": ts, "value": None})
    right = dict(reversed(list(left.items())))

    assert canonical_json_object(left) == canonical_json_object(right)
    decoded = json.loads(canonical_json_object(left))
    assert decoded["nested"]["at"] == ts.isoformat()
    assert decoded["nested"]["value"] is None
    assert canonical_json_hash(left) == canonical_json_hash(right)


def test_context_serialization_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_json_object(_ctx(bad=float("nan")))


def test_context_as_of_comes_from_live_now_ms() -> None:
    ctx = _ctx(now_ms=1_786_300_000_123.0)
    assert replay_context_as_of(ctx) == datetime.fromtimestamp(
        1_786_300_000.123,
        UTC,
    )


@pytest.mark.parametrize("value", [None, -1, float("nan"), "not-a-number"])
def test_context_as_of_fails_closed(value: object) -> None:
    with pytest.raises(ValueError):
        replay_context_as_of(_ctx(now_ms=value))


def test_current_logic_replay_is_exact_pure_function() -> None:
    ctx = _ctx()
    assert REPLAY_CONTEXT_VERSION == 1
    assert replay_summary_for_logic(
        SCALP_SIGNAL_LOGIC_VERSION,
        ctx,
    ) == compute_scalp_summary(ctx)


def test_unknown_logic_version_fails_closed() -> None:
    with pytest.raises(ReplayUnsupportedLogicVersion):
        replay_summary_for_logic("scalp-summary-v999", _ctx())


def _replay_record(**overrides: object) -> dict[str, object]:
    context = _ctx()
    summary = compute_scalp_summary(context)
    decision_status, direction, actionable = classify_signal_observation(summary)
    state, confidence, reason, long_score, short_score, coverage = (
        validated_signal_observation_fields(summary)
    )
    record: dict[str, object] = {
        "observation_id": 7,
        "logic_version": SCALP_SIGNAL_LOGIC_VERSION,
        "decision_status": decision_status,
        "direction": direction,
        "actionable": actionable,
        "state": state,
        "confidence": confidence,
        "reason": reason,
        "long_score": long_score,
        "short_score": short_score,
        "evidence_coverage_pct": coverage,
        "evidence": canonical_json_object(summary),
        "frame_id": 9,
        "context_version": REPLAY_CONTEXT_VERSION,
        "context_hash": canonical_json_hash(context),
        "context": canonical_json_object(context),
    }
    record.update(overrides)
    return record


def test_pure_replay_record_validates_evidence_and_population_fields() -> None:
    result = validate_replay_observation_record(_replay_record())
    assert result.evidence_match is True
    assert result.observation_fields_match is True
    assert result.mismatched_observation_fields == ()


def test_pure_replay_record_detects_direction_population_mismatch() -> None:
    result = validate_replay_observation_record(
        _replay_record(direction="long", actionable=True)
    )
    assert result.evidence_match is True
    assert result.observation_fields_match is False
    assert result.mismatched_observation_fields == ("direction",)


def test_pure_replay_record_detects_stored_evidence_mismatch() -> None:
    expected = json.loads(str(_replay_record()["evidence"]))
    expected["kernel_b_only"] = True
    result = validate_replay_observation_record(
        _replay_record(evidence=canonical_json_object(expected))
    )
    assert result.evidence_match is False
    assert result.observation_fields_match is True
