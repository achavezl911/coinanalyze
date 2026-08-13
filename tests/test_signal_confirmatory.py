from __future__ import annotations

import math
from datetime import UTC, datetime

import pytest

from app.signal_confirmatory import (
    BLOCK_BOOTSTRAP_INFERENCE_VERSION,
    BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION,
    CONFIRMATORY_BLOCK_UNITS,
    CONFIRMATORY_DECISION_POLICY_V1,
    CONFIRMATORY_PRIMARY_ENDPOINT_VERSION,
    CONFIRMATORY_STATE_FAIL,
    CONFIRMATORY_STATE_INCONCLUSIVE,
    CONFIRMATORY_STATE_PASS,
    ConfirmatoryContract,
    block_bootstrap_ci,
    block_bootstrap_v1,
    block_unconditional_direction_matched_baseline_bps,
    confirmatory_block_key,
    confirmatory_decision,
    validate_confirmatory_contract,
)

# ---------------------------------------------------------------------------
# This module is dependency-free (stdlib only): confirm it never imports
# asyncpg -- a load-bearing property for "Python stdlib unless an existing
# dependency already provides the required primitive".
# ---------------------------------------------------------------------------


def test_module_has_no_asyncpg_dependency() -> None:
    import ast

    import app.signal_confirmatory as module

    source = module.__file__
    assert source is not None
    with open(source, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())

    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module.split(".")[0])

    assert "asyncpg" not in imported_names


def _contract_kwargs() -> dict[str, object]:
    return {
        "primary_endpoint_version": CONFIRMATORY_PRIMARY_ENDPOINT_VERSION,
        "primary_symbol": "BTCUSDT_PERP.A",
        "primary_horizon_minutes": 15,
        "primary_sampling_mode": "utc_nonoverlap",
        "primary_exchange": "binance",
        "primary_size_usd": 1_000.0,
        "primary_taker_fee_bps": 2.0,
        "baseline_version": BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION,
        "unmodeled_execution_stress_bps": 1.5,
        "inference_version": BLOCK_BOOTSTRAP_INFERENCE_VERSION,
        "block_unit": "day",
        "block_length": 1,
        "bootstrap_repetitions": 200,
        "bootstrap_seed": 12345,
        "confidence_level": 0.95,
        "minimum_effect_bps": 0.0,
        "minimum_primary_blocks": 5,
        "minimum_execution_data_coverage_pct": 50.0,
        "minimum_research_data_coverage_pct": 50.0,
        "confirmatory_decision_policy": CONFIRMATORY_DECISION_POLICY_V1,
    }


def test_validate_confirmatory_contract_accepts_a_valid_contract() -> None:
    contract = ConfirmatoryContract(**_contract_kwargs())
    validate_confirmatory_contract(
        contract,
        symbols=("BTCUSDT_PERP.A",),
        horizons=(15,),
        sampling_modes=("dense_periodic", "utc_nonoverlap"),
        exchanges=("binance", "bybit"),
        sizes_usd=(1_000.0, 10_000.0),
        fee_bps_per_side=(("binance", 2.0),),
    )


def test_validate_confirmatory_contract_allows_unrestricted_manifest_symbols() -> None:
    # An empty options.symbols tuple means "no symbol restriction" elsewhere
    # in this codebase (see app.signal_walk_forward's _fetch_discovery_start
    # SQL: cardinality($n::text[])=0 OR symbol=ANY(...)). The confirmatory
    # contract must honor that same convention rather than rejecting every
    # primary_symbol whenever the manifest itself is unrestricted.
    contract = ConfirmatoryContract(**_contract_kwargs())
    validate_confirmatory_contract(
        contract,
        symbols=(),
        horizons=(15,),
        sampling_modes=("utc_nonoverlap",),
        exchanges=("binance",),
        sizes_usd=(1_000.0,),
        fee_bps_per_side=(("binance", 2.0),),
    )


# ---------------------------------------------------------------------------
# Baseline: block_unconditional_direction_matched_baseline_v1.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("block_unconditional_market_mean_bps", "expected_bps"),
    [(0.0, 0.0), (150.0, 150.0), (-202.020202, -202.020202), (0.1, 0.1)],
)
def test_baseline_bps_matches_the_block_mean_unchanged_for_long(
    block_unconditional_market_mean_bps: float, expected_bps: float
) -> None:
    assert block_unconditional_direction_matched_baseline_bps(
        block_unconditional_market_mean_bps, direction="long"
    ) == pytest.approx(expected_bps)


@pytest.mark.parametrize(
    ("block_unconditional_market_mean_bps", "expected_bps"),
    [(0.0, 0.0), (150.0, -150.0), (-202.020202, 202.020202), (0.1, -0.1)],
)
def test_baseline_bps_negates_the_block_mean_for_short(
    block_unconditional_market_mean_bps: float, expected_bps: float
) -> None:
    assert block_unconditional_direction_matched_baseline_bps(
        block_unconditional_market_mean_bps, direction="short"
    ) == pytest.approx(expected_bps)


@pytest.mark.parametrize("direction", ["neutral", "unavailable", "", "LONG"])
def test_baseline_bps_rejects_any_direction_other_than_long_or_short(direction: str) -> None:
    with pytest.raises(ValueError):
        block_unconditional_direction_matched_baseline_bps(100.0, direction=direction)


# ---------------------------------------------------------------------------
# confirmatory_block_key: pure, epoch-anchored, deterministic.
# ---------------------------------------------------------------------------


def test_block_key_is_pure_and_repeatable() -> None:
    ts = datetime(2026, 3, 15, 13, 37, tzinfo=UTC)
    first = confirmatory_block_key(ts, block_unit="hour", block_length=1)
    second = confirmatory_block_key(ts, block_unit="hour", block_length=1)
    assert first == second


def test_block_key_groups_by_calendar_day_when_block_unit_is_day() -> None:
    early = datetime(2026, 3, 15, 0, 0, tzinfo=UTC)
    late = datetime(2026, 3, 15, 23, 59, tzinfo=UTC)
    next_day = datetime(2026, 3, 16, 0, 0, tzinfo=UTC)

    assert confirmatory_block_key(early, block_unit="day", block_length=1) == (
        confirmatory_block_key(late, block_unit="day", block_length=1)
    )
    assert confirmatory_block_key(early, block_unit="day", block_length=1) != (
        confirmatory_block_key(next_day, block_unit="day", block_length=1)
    )


def test_block_key_groups_by_calendar_hour_when_block_unit_is_hour() -> None:
    start_of_hour = datetime(2026, 3, 15, 13, 0, tzinfo=UTC)
    end_of_hour = datetime(2026, 3, 15, 13, 59, 59, tzinfo=UTC)
    next_hour = datetime(2026, 3, 15, 14, 0, tzinfo=UTC)

    assert confirmatory_block_key(start_of_hour, block_unit="hour", block_length=1) == (
        confirmatory_block_key(end_of_hour, block_unit="hour", block_length=1)
    )
    assert confirmatory_block_key(start_of_hour, block_unit="hour", block_length=1) != (
        confirmatory_block_key(next_hour, block_unit="hour", block_length=1)
    )


def test_block_key_respects_block_length_multiplier() -> None:
    ts_a = datetime(2026, 3, 15, 1, 0, tzinfo=UTC)
    ts_b = datetime(2026, 3, 15, 3, 0, tzinfo=UTC)
    # 4-hour blocks: both timestamps fall in the same block even though they
    # differ by more than one "hour" block_unit.
    assert confirmatory_block_key(ts_a, block_unit="hour", block_length=4) == (
        confirmatory_block_key(ts_b, block_unit="hour", block_length=4)
    )


def test_block_key_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        confirmatory_block_key(datetime(2026, 3, 15), block_unit="day", block_length=1)


def test_block_key_rejects_unsupported_unit_or_length() -> None:
    ts = datetime(2026, 3, 15, tzinfo=UTC)
    with pytest.raises(ValueError):
        confirmatory_block_key(ts, block_unit="week", block_length=1)
    with pytest.raises(ValueError):
        confirmatory_block_key(ts, block_unit="day", block_length=0)


def test_confirmatory_block_units_are_hour_and_day_only() -> None:
    assert CONFIRMATORY_BLOCK_UNITS == ("hour", "day")


# ---------------------------------------------------------------------------
# block_bootstrap_v1: deterministic, whole-block resampling.
# ---------------------------------------------------------------------------


def test_block_bootstrap_is_deterministic_for_a_frozen_seed() -> None:
    block_values = {"day:1:0": [1.0, 2.0], "day:1:1": [3.0], "day:1:2": [-1.0, 0.0]}
    first = block_bootstrap_v1(block_values, repetitions=500, seed=42)
    second = block_bootstrap_v1(block_values, repetitions=500, seed=42)
    assert first == second


def test_block_bootstrap_differs_for_a_different_seed() -> None:
    block_values = {"day:1:0": [1.0, 2.0], "day:1:1": [3.0], "day:1:2": [-1.0, 0.0]}
    first = block_bootstrap_v1(block_values, repetitions=500, seed=42)
    second = block_bootstrap_v1(block_values, repetitions=500, seed=43)
    assert first != second


def test_block_bootstrap_samples_whole_blocks_not_individual_rows() -> None:
    # Block "hot" only ever appears as a WHOLE pair (100.0, -100.0), whose
    # mean contribution when drawn is always the pair average, 0.0. If the
    # resampler ever split a block and drew rows individually, some
    # repetition's pooled mean would be pulled toward +100 or -100 by a lone
    # 100.0/-100.0 value instead of the pair always canceling together.
    block_values = {
        "cold_a": [1.0],
        "cold_b": [1.0],
        "hot": [100.0, -100.0],
    }
    means = block_bootstrap_v1(block_values, repetitions=2000, seed=7)

    # Every possible repetition draws 3 blocks (with replacement) from
    # {cold_a, cold_b, hot}. "hot" always contributes exactly 100.0 AND
    # -100.0 together (sum 0, two rows) whenever it is drawn -- never one
    # without the other -- so the maximum possible pooled sum magnitude a
    # single repetition can reach, if "hot" is drawn all 3 times, is a
    # pooled list of six values: three 100.0 and three -100.0, whose mean is
    # exactly 0.0, not skewed toward +/-100.
    for mean in means:
        assert -100.0 < mean < 100.0


def test_block_bootstrap_cross_row_observations_inside_a_block_stay_together() -> None:
    # A block whose two values are annotated with a shared marker (encoded
    # as identical magnitude, opposite sign) must always appear together:
    # sum of any drawn multiset of this single block is always an exact
    # multiple of (value_a + value_b).
    block_values = {"only_block": [5.0, 7.0]}
    means = block_bootstrap_v1(block_values, repetitions=100, seed=1)
    # With exactly one block, every repetition draws that one block exactly
    # once (k=1 draw from a 1-element population) -- so every resampled mean
    # must equal the block's own mean.
    expected = (5.0 + 7.0) / 2.0
    assert all(mean == pytest.approx(expected) for mean in means)


def test_block_bootstrap_requires_at_least_one_block() -> None:
    with pytest.raises(ValueError):
        block_bootstrap_v1({}, repetitions=10, seed=1)


def test_block_bootstrap_rejects_empty_block_values() -> None:
    with pytest.raises(ValueError):
        block_bootstrap_v1({"day:1:0": []}, repetitions=10, seed=1)


def test_block_bootstrap_rejects_zero_repetitions() -> None:
    with pytest.raises(ValueError):
        block_bootstrap_v1({"day:1:0": [1.0]}, repetitions=0, seed=1)


def test_block_bootstrap_key_order_does_not_affect_determinism() -> None:
    # dict insertion order must not matter -- block_bootstrap_v1 sorts keys
    # internally before drawing.
    a = block_bootstrap_v1({"day:1:0": [1.0], "day:1:1": [2.0]}, repetitions=50, seed=9)
    b = block_bootstrap_v1({"day:1:1": [2.0], "day:1:0": [1.0]}, repetitions=50, seed=9)
    assert a == b


# ---------------------------------------------------------------------------
# block_bootstrap_ci: percentile-method CI over bootstrap means.
# ---------------------------------------------------------------------------


def test_block_bootstrap_ci_matches_percentile_bounds() -> None:
    means = [float(i) for i in range(1, 101)]  # 1..100
    lower, upper = block_bootstrap_ci(means, confidence_level=0.98)
    assert lower == pytest.approx(1.99, abs=0.5)
    assert upper == pytest.approx(99.01, abs=0.5)
    assert lower < upper


def test_block_bootstrap_ci_rejects_out_of_range_confidence_level() -> None:
    with pytest.raises(ValueError):
        block_bootstrap_ci([1.0, 2.0], confidence_level=0.0)
    with pytest.raises(ValueError):
        block_bootstrap_ci([1.0, 2.0], confidence_level=1.0)


def test_block_bootstrap_ci_rejects_empty_means() -> None:
    with pytest.raises(ValueError):
        block_bootstrap_ci([], confidence_level=0.95)


# ---------------------------------------------------------------------------
# confirmatory_decision: two_sided_block_bootstrap_ci_vs_minimum_effect_v1.
# ---------------------------------------------------------------------------


def test_confirmatory_decision_pass_when_lower_bound_exceeds_minimum_effect() -> None:
    state = confirmatory_decision(lower_ci_bps=5.0, upper_ci_bps=10.0, minimum_effect_bps=2.0)
    assert state == CONFIRMATORY_STATE_PASS


def test_confirmatory_decision_fail_when_upper_bound_is_non_positive() -> None:
    state = confirmatory_decision(lower_ci_bps=-10.0, upper_ci_bps=-1.0, minimum_effect_bps=2.0)
    assert state == CONFIRMATORY_STATE_FAIL


def test_confirmatory_decision_inconclusive_when_ci_straddles_the_threshold() -> None:
    state = confirmatory_decision(lower_ci_bps=-1.0, upper_ci_bps=5.0, minimum_effect_bps=2.0)
    assert state == CONFIRMATORY_STATE_INCONCLUSIVE


def test_confirmatory_decision_boundary_lower_equal_to_minimum_is_not_pass() -> None:
    # Strict ">" per the frozen decision policy: equality is not enough.
    state = confirmatory_decision(lower_ci_bps=2.0, upper_ci_bps=5.0, minimum_effect_bps=2.0)
    assert state != CONFIRMATORY_STATE_PASS


def test_confirmatory_decision_boundary_upper_equal_to_zero_is_fail() -> None:
    state = confirmatory_decision(lower_ci_bps=-5.0, upper_ci_bps=0.0, minimum_effect_bps=2.0)
    assert state == CONFIRMATORY_STATE_FAIL


def test_confirmatory_decision_wholly_negative_ci_is_never_pass_even_with_permissive_minimum() -> None:
    # Defensive ordering (FAIL checked before PASS), independent of contract
    # validation: this function itself takes raw floats, so it can still be
    # called with a negative minimum_effect_bps directly, and must still
    # never PASS a wholly-negative CI.
    state = confirmatory_decision(lower_ci_bps=-50.0, upper_ci_bps=-10.0, minimum_effect_bps=-100.0)
    assert state == CONFIRMATORY_STATE_FAIL


# ---------------------------------------------------------------------------
# Contract field validation: exhaustive per-field failure coverage
# complementing tests/test_signal_walk_forward.py's manifest-level wiring
# tests.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "int_field",
    ["block_length", "bootstrap_repetitions", "bootstrap_seed", "minimum_primary_blocks"],
)
def test_validate_confirmatory_contract_rejects_non_int_count_fields(int_field: str) -> None:
    kwargs = _contract_kwargs()
    kwargs[int_field] = float(kwargs[int_field]) + 0.5
    contract = ConfirmatoryContract(**kwargs)
    with pytest.raises(ValueError):
        validate_confirmatory_contract(
            contract,
            symbols=("BTCUSDT_PERP.A",),
            horizons=(15,),
            sampling_modes=("utc_nonoverlap",),
            exchanges=("binance",),
            sizes_usd=(1_000.0,),
            fee_bps_per_side=(("binance", 2.0),),
        )


def test_validate_confirmatory_contract_rejects_dense_periodic_as_primary() -> None:
    kwargs = _contract_kwargs()
    kwargs["primary_sampling_mode"] = "dense_periodic"
    contract = ConfirmatoryContract(**kwargs)
    with pytest.raises(ValueError):
        validate_confirmatory_contract(
            contract,
            symbols=("BTCUSDT_PERP.A",),
            horizons=(15,),
            sampling_modes=("dense_periodic", "utc_nonoverlap"),
            exchanges=("binance",),
            sizes_usd=(1_000.0,),
            fee_bps_per_side=(("binance", 2.0),),
        )


def test_no_default_values_exist_on_confirmatory_contract() -> None:
    # Every field is caller-required: constructing a ConfirmatoryContract
    # with any field omitted must raise TypeError, never silently fall back
    # to a value.
    for field_name in _contract_kwargs():
        kwargs = _contract_kwargs()
        del kwargs[field_name]
        with pytest.raises(TypeError):
            ConfirmatoryContract(**kwargs)


def test_confirmatory_contract_is_frozen() -> None:
    contract = ConfirmatoryContract(**_contract_kwargs())
    with pytest.raises((AttributeError, Exception)):
        contract.primary_symbol = "ETHUSDT_PERP.A"  # type: ignore[misc]


def test_finiteness_checks_reject_nan_and_inf() -> None:
    for field, bad_value in (
        ("unmodeled_execution_stress_bps", math.nan),
        ("unmodeled_execution_stress_bps", math.inf),
        ("minimum_effect_bps", math.nan),
        ("minimum_effect_bps", math.inf),
        ("primary_taker_fee_bps", math.nan),
    ):
        kwargs = _contract_kwargs()
        kwargs[field] = bad_value
        contract = ConfirmatoryContract(**kwargs)
        with pytest.raises(ValueError):
            validate_confirmatory_contract(
                contract,
                symbols=("BTCUSDT_PERP.A",),
                horizons=(15,),
                sampling_modes=("utc_nonoverlap",),
                exchanges=("binance",),
                sizes_usd=(1_000.0,),
                fee_bps_per_side=(("binance", bad_value if field == "primary_taker_fee_bps" else 2.0),),
            )


# ---------------------------------------------------------------------------
# P1-03 / P2-01: negative minimum_effect_bps and degenerate structural
# minimums are all rejected at contract-validation time, fail closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("minimum_effect_bps", -100.0),
        ("minimum_effect_bps", -0.0000001),
        ("bootstrap_repetitions", 1),
        ("minimum_primary_blocks", 1),
        ("minimum_execution_data_coverage_pct", 0.0),
        ("minimum_research_data_coverage_pct", 0.0),
    ],
)
def test_validate_confirmatory_contract_rejects_degenerate_values(
    field: str, bad_value: object
) -> None:
    kwargs = _contract_kwargs()
    kwargs[field] = bad_value
    contract = ConfirmatoryContract(**kwargs)
    with pytest.raises(ValueError):
        validate_confirmatory_contract(
            contract,
            symbols=("BTCUSDT_PERP.A",),
            horizons=(15,),
            sampling_modes=("utc_nonoverlap",),
            exchanges=("binance",),
            sizes_usd=(1_000.0,),
            fee_bps_per_side=(("binance", 2.0),),
        )


def test_validate_confirmatory_contract_accepts_the_minimum_non_degenerate_values() -> None:
    # The boundary values just above each newly-tightened bound must still
    # be accepted -- these are not "recommended" values, just proof the
    # bounds are exactly where P1-03/P2-01 specify, not off by one further.
    kwargs = _contract_kwargs()
    kwargs["minimum_effect_bps"] = 0.0
    kwargs["bootstrap_repetitions"] = 2
    kwargs["minimum_primary_blocks"] = 2
    kwargs["minimum_execution_data_coverage_pct"] = 100.0
    kwargs["minimum_research_data_coverage_pct"] = 100.0
    contract = ConfirmatoryContract(**kwargs)
    validate_confirmatory_contract(
        contract,
        symbols=("BTCUSDT_PERP.A",),
        horizons=(15,),
        sampling_modes=("utc_nonoverlap",),
        exchanges=("binance",),
        sizes_usd=(1_000.0,),
        fee_bps_per_side=(("binance", 2.0),),
    )


# ---------------------------------------------------------------------------
# A4-08: minimum_research_data_coverage_pct -- 0 < x <= 100, caller-required,
# separate from minimum_execution_data_coverage_pct.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [0.0, -0.0000001, -100.0, 100.0000001, 101.0])
def test_validate_confirmatory_contract_rejects_research_coverage_out_of_range(
    bad_value: float,
) -> None:
    kwargs = _contract_kwargs()
    kwargs["minimum_research_data_coverage_pct"] = bad_value
    contract = ConfirmatoryContract(**kwargs)
    with pytest.raises(ValueError):
        validate_confirmatory_contract(
            contract,
            symbols=("BTCUSDT_PERP.A",),
            horizons=(15,),
            sampling_modes=("utc_nonoverlap",),
            exchanges=("binance",),
            sizes_usd=(1_000.0,),
            fee_bps_per_side=(("binance", 2.0),),
        )


@pytest.mark.parametrize("good_value", [0.0000001, 1.0, 50.0, 100.0])
def test_validate_confirmatory_contract_accepts_research_coverage_in_range(
    good_value: float,
) -> None:
    kwargs = _contract_kwargs()
    kwargs["minimum_research_data_coverage_pct"] = good_value
    contract = ConfirmatoryContract(**kwargs)
    validate_confirmatory_contract(
        contract,
        symbols=("BTCUSDT_PERP.A",),
        horizons=(15,),
        sampling_modes=("utc_nonoverlap",),
        exchanges=("binance",),
        sizes_usd=(1_000.0,),
        fee_bps_per_side=(("binance", 2.0),),
    )
