from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG
from app.signal_walk_forward import (
    DEFAULT_MANIFEST_NAME,
    SELECTION_POLICY,
    WalkForwardManifestOptions,
    _classify_generalization,
    _group_stats,
    _next_minute_strictly_after,
    _percentile,
    _spec_hash,
    _static_options_spec,
    compute_folds,
    validate_manifest_options,
)


def test_default_manifest_name_is_the_fixed_production_program() -> None:
    assert DEFAULT_MANIFEST_NAME == "pr11-fixed-kernel-v1"


def test_selection_policy_is_fixed_kernel_no_selection() -> None:
    assert SELECTION_POLICY == "fixed_kernel_no_selection_v1"


def test_valid_default_options_pass_validation() -> None:
    validate_manifest_options(WalkForwardManifestOptions())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"name": "PR11-Bad-Name"},
        {"name": "1-starts-with-digit"},
        {"name": "has spaces"},
        {"warmup_days": 0},
        {"test_days": 0},
        {"fold_count": 0},
        {"min_group_n": 0},
        {"horizons": ()},
        {"horizons": (1, 1)},
        {"horizons": (7,)},
        {"sampling_modes": ()},
        {"exchanges": ()},
        {"exchanges": ("okx",)},
        {"sizes_usd": ()},
        {"sizes_usd": (123.0,)},
        {"symbols": ("BTC", "BTC")},
        {"fee_bps_per_side": (("binance", -1.0),)},
        {"fee_bps_per_side": (("okx", 5.0),)},
        {"logic_version": "scalp-summary-v2"},
        {"evidence_version": 0},
    ],
)
def test_invalid_options_fail_closed(kwargs: dict) -> None:
    options = WalkForwardManifestOptions(**kwargs)
    with pytest.raises(ValueError):
        validate_manifest_options(options)


def test_no_cli_option_can_request_a_retroactive_cutoff() -> None:
    """WalkForwardManifestOptions has no cutoff/created_at field at all: the
    cutoff can only ever be derived from the live PostgreSQL clock inside
    freeze_walk_forward_manifest, never supplied by a caller."""

    field_names = WalkForwardManifestOptions.__dataclass_fields__.keys()
    assert "cutoff_at" not in field_names
    assert "created_at" not in field_names


def test_next_minute_strictly_after_always_moves_forward() -> None:
    exact_minute = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert _next_minute_strictly_after(exact_minute) == exact_minute + timedelta(minutes=1)

    mid_minute = datetime(2026, 1, 1, 0, 0, 30, 500000, tzinfo=UTC)
    result = _next_minute_strictly_after(mid_minute)
    assert result > mid_minute
    assert result.second == 0 and result.microsecond == 0


def test_compute_folds_are_expanding_discovery_contiguous_nonoverlapping_test() -> None:
    discovery_start = datetime(2026, 1, 1, tzinfo=UTC)
    cutoff_at = datetime(2026, 1, 8, tzinfo=UTC)
    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=7,
        fold_count=4,
        horizons=OUTCOME_HORIZONS_MINUTES,
    )
    assert len(folds) == 4

    for fold in folds:
        assert fold["discovery_start"] == discovery_start
        assert fold["discovery_end"] == fold["test_start"]
        assert fold["test_end"] == fold["test_start"] + timedelta(days=7)
        expected_maturity = (
            fold["test_end"] + timedelta(minutes=max(OUTCOME_HORIZONS_MINUTES)) + OUTCOME_SETTLEMENT_LAG
        )
        assert fold["test_maturity_at"] == expected_maturity

    # fold N's test window starts exactly where fold N-1's test window ended.
    for previous, current in zip(folds, folds[1:], strict=False):
        assert current["test_start"] == previous["test_end"]
        assert current["discovery_end"] == previous["test_end"]

    # No two test windows overlap.
    for previous, current in zip(folds, folds[1:], strict=False):
        assert previous["test_end"] <= current["test_start"]

    assert folds[0]["test_start"] == cutoff_at


def test_compute_folds_is_deterministic_given_the_same_inputs() -> None:
    kwargs = dict(
        discovery_start=datetime(2026, 3, 1, tzinfo=UTC),
        cutoff_at=datetime(2026, 3, 10, tzinfo=UTC),
        test_days=5,
        fold_count=3,
        horizons=(1, 240),
    )
    assert compute_folds(**kwargs) == compute_folds(**kwargs)


def test_manifest_hash_is_stable_for_the_same_static_options() -> None:
    options = WalkForwardManifestOptions()
    spec_a = _static_options_spec(options)
    spec_b = _static_options_spec(options)
    assert _spec_hash(spec_a) == _spec_hash(spec_b)


def test_manifest_hash_changes_when_a_material_field_changes() -> None:
    base = _static_options_spec(WalkForwardManifestOptions())
    changed = _static_options_spec(WalkForwardManifestOptions(fold_count=3))
    assert _spec_hash(base) != _spec_hash(changed)


def test_manifest_hash_covers_versions_and_execution_grid() -> None:
    base_options = WalkForwardManifestOptions()
    base_hash = _spec_hash(_static_options_spec(base_options))

    for kwargs in (
        {"evidence_version": 2},
        {"outcome_version": 2},
        {"context_version": 2},
        {"execution_snapshot_version": 2},
        {"sizes_usd": (1_000.0, 10_000.0)},
        {"exchanges": ("binance",)},
        {"horizons": (1, 3, 5)},
        {"fee_bps_per_side": (("binance", 5.0),)},
    ):
        other_hash = _spec_hash(_static_options_spec(WalkForwardManifestOptions(**kwargs)))
        assert other_hash != base_hash, f"hash did not change for {kwargs}"


def test_percentile_matches_known_values() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert _percentile(values, 0.5) == 30.0
    assert _percentile(values, 0.0) == 10.0
    assert _percentile(values, 1.0) == 50.0
    assert _percentile([], 0.5) is None
    assert _percentile([7.0], 0.9) == 7.0


def _rows(returns: list[float]) -> list[dict]:
    return [
        {"directional_return_pct": value, "mfe_pct": abs(value), "mae_pct": abs(value)}
        for value in returns
    ]


def test_group_stats_empty_group() -> None:
    stats = _group_stats([], min_group_n=30)
    assert stats["n"] == 0
    assert stats["expectancy_gross_pct"] is None
    assert stats["meets_min_group_n"] is False


def test_group_stats_computes_expectancy_and_hit_rate() -> None:
    stats = _group_stats(_rows([1.0, -0.5, 2.0, -1.0]), min_group_n=2)
    assert stats["n"] == 4
    assert math.isclose(stats["expectancy_gross_pct"], 0.375)
    assert stats["hit_rate_pct"] == 50.0
    assert stats["meets_min_group_n"] is True


@pytest.mark.parametrize(
    ("discovery_expectancy", "test_expectancy", "expected_label"),
    [
        (1.0, 1.0, "positive_generalization_observed"),
        (1.0, -1.0, "failed_to_generalize"),
        (1.0, 0.0, "failed_to_generalize"),
        (-1.0, 1.0, "oos_positive_without_discovery_edge"),
        (0.0, 1.0, "oos_positive_without_discovery_edge"),
        (-1.0, -1.0, "non_positive_both"),
        (0.0, 0.0, "non_positive_both"),
    ],
)
def test_classify_generalization_labels(
    discovery_expectancy: float, test_expectancy: float, expected_label: str
) -> None:
    discovery = {"expectancy_gross_pct": discovery_expectancy, "meets_min_group_n": True}
    test = {"expectancy_gross_pct": test_expectancy, "meets_min_group_n": True}
    label = _classify_generalization(
        discovery=discovery, test=test, min_group_n=30, fold_evaluation_ready=True
    )
    assert label == expected_label


def test_classify_generalization_not_ready_overrides_everything() -> None:
    discovery = {"expectancy_gross_pct": 5.0, "meets_min_group_n": True}
    test = {"expectancy_gross_pct": 5.0, "meets_min_group_n": True}
    label = _classify_generalization(
        discovery=discovery, test=test, min_group_n=30, fold_evaluation_ready=False
    )
    assert label == "not_ready"


def test_classify_generalization_insufficient_sample() -> None:
    discovery = {"expectancy_gross_pct": 5.0, "meets_min_group_n": False}
    test = {"expectancy_gross_pct": 5.0, "meets_min_group_n": True}
    label = _classify_generalization(
        discovery=discovery, test=test, min_group_n=30, fold_evaluation_ready=True
    )
    assert label == "insufficient_sample"
