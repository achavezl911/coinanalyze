from __future__ import annotations

import dataclasses
import math
import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import signal_outcomes
from app.signal_confirmatory import (
    CONFIRMATORY_DECISION_POLICY_V1,
    ConfirmatoryContract,
    block_unconditional_direction_matched_baseline_bps,
    confirmatory_decision,
    validate_confirmatory_contract,
)
from app.signal_confirmatory_v2 import (
    CONJUNCTIVE_DECISION_POLICY_V2,
    PAIRED_BLOCK_BOOTSTRAP_DRAW_GENERATOR_V2,
    ConfirmatoryContractV2,
    canonical_scientific_result_json,
    confirmatory_contract_v2_from_dict,
    confirmatory_contract_v2_to_dict,
    conjunctive_confirmatory_decision_v2,
    deterministic_mean_v2,
    direction_matched_venue_mid_baseline_bps_v2,
    evaluation_not_before_v2,
    expected_utc_nonoverlap_slot_count_v2,
    paired_block_bootstrap_ci_v2,
    paired_block_bootstrap_v2,
    scientific_result_hash,
    validate_confirmatory_contract_v2,
    venue_consistent_execution_measure_v2,
    venue_mid_market_return_bps_v2,
)
from app.signal_scientific_identity import (
    REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS,
    SCIENTIFIC_IDENTITY_VERSION_V1,
    SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS,
    canonical_python_ast,
    canonical_sql_source_v1,
    compute_scientific_implementation_identity,
    scientific_implementation_identity,
    validate_scientific_implementation_identity,
)
from app.signal_walk_forward import (
    _confirmatory_v4_outcome_integrity_for_fold,
    _execution_measure,
)

_OBSERVED_AT = datetime(2026, 8, 13, 12, tzinfo=UTC)


def _contract_v2(**overrides: object) -> ConfirmatoryContractV2:
    values: dict[str, object] = {
        "primary_endpoint_version": 2,
        "primary_symbol": "BTCUSDT_PERP.A",
        "primary_horizon_minutes": 15,
        "primary_sampling_mode": "utc_nonoverlap",
        "primary_exchange": "binance",
        "outcome_price_venue": "binance",
        "primary_size_usd": 1_000.0,
        "primary_taker_fee_bps": 2.0,
        "baseline_version": 2,
        "unmodeled_execution_stress_bps": 3.0,
        "funding_semantics": "excluded_v1",
        "inference_version": 2,
        "block_unit": "day",
        "block_length": 1,
        "bootstrap_repetitions": 200,
        "bootstrap_seed": 7,
        "confidence_level": 0.95,
        "minimum_effect_bps": 5.0,
        "minimum_primary_blocks": 2,
        "minimum_execution_data_coverage_pct": 90.0,
        "minimum_research_data_coverage_pct": 90.0,
        "evaluation_settlement_grace_seconds": 30,
        "confirmatory_decision_policy": CONJUNCTIVE_DECISION_POLICY_V2,
    }
    values.update(overrides)
    return ConfirmatoryContractV2(**values)


def _snapshot(*, mid: float = 100.0, buy_cost: float = 0.0, sell_cost: float = 0.0):
    buy_fill = mid * (1.0 + buy_cost / 10_000.0)
    sell_fill = mid * (1.0 - sell_cost / 10_000.0)
    return {
        "status": "valid",
        "captured_at": _OBSERVED_AT,
        "mid_px": mid,
        "cost_curve": {
            "1000": {
                "buy": {
                    "avg_price": buy_fill,
                    "market_cost_bps_vs_mid": buy_cost,
                    "insufficient_depth": False,
                },
                "sell": {
                    "avg_price": sell_fill,
                    "market_cost_bps_vs_mid": sell_cost,
                    "insufficient_depth": False,
                },
            }
        },
    }


def _validate_v2(contract: ConfirmatoryContractV2) -> None:
    validate_confirmatory_contract_v2(
        contract,
        symbols=("BTCUSDT_PERP.A",),
        horizons=(15,),
        sampling_modes=("utc_nonoverlap",),
        exchanges=("binance", "bybit"),
        sizes_usd=(1_000.0,),
        fee_bps_per_side=(("binance", 2.0),),
    )


def test_corrected_long_and_short_algebra_uses_opposite_side_exit_cost() -> None:
    snapshot = _snapshot(buy_cost=10.0, sell_cost=20.0)
    long = venue_consistent_execution_measure_v2(
        {
            "direction": "long",
            "observed_at": _OBSERVED_AT,
            "end_price": 101.0,
            "reference_price": 10_000.0,
        },
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=2.0,
        stress_bps=3.0,
    )
    long_ratio = 101.0 * 0.998 / 100.1
    expected_long = (long_ratio * 0.9998 - 1.0002) * 10_000.0 - 3.0
    assert long["cost_evaluable"] is True
    assert long["entry_market_impact_bps"] == pytest.approx(10.0)
    assert long["modeled_exit_cost_bps"] == pytest.approx(20.0)
    assert long["modeled_fee_cost_bps"] == pytest.approx(2.0 * (1.0 + long_ratio))
    assert long["absolute_stressed_net_bps"] == pytest.approx(expected_long)

    short = venue_consistent_execution_measure_v2(
        {
            "direction": "short",
            "observed_at": _OBSERVED_AT,
            "end_price": 99.0,
            "reference_price": 0.01,
        },
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=2.0,
        stress_bps=3.0,
    )
    short_ratio = 99.0 * 1.001 / 99.8
    expected_short = (0.9998 - short_ratio * 1.0002) * 10_000.0 - 3.0
    assert short["entry_market_impact_bps"] == pytest.approx(20.0)
    assert short["modeled_exit_cost_bps"] == pytest.approx(10.0)
    assert short["modeled_fee_cost_bps"] == pytest.approx(2.0 * (1.0 + short_ratio))
    assert short["absolute_stressed_net_bps"] == pytest.approx(expected_short)


@pytest.mark.parametrize(
    ("direction", "reference_price"),
    [("long", 101.0), ("short", 99.0)],
)
def test_p1_01_stale_reference_can_favor_v1_but_not_corrected_endpoint(
    direction: str,
    reference_price: float,
) -> None:
    snapshot = _snapshot()
    row = {
        "direction": direction,
        "observed_at": _OBSERVED_AT,
        "directional_return_pct": 0.0,
        "reference_price": reference_price,
        "end_price": 100.0,
    }
    old_measure = _execution_measure(
        row,
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=0.0,
    )
    reference_market_bps = (100.0 / reference_price - 1.0) * 10_000.0
    old_baseline = block_unconditional_direction_matched_baseline_bps(
        reference_market_bps,
        direction=direction,
    )
    old_excess = old_measure["modeled_net_after_fees_bps"] - old_baseline
    assert old_excess > 90.0
    assert (
        confirmatory_decision(
            lower_ci_bps=old_excess,
            upper_ci_bps=old_excess,
            minimum_effect_bps=10.0,
        )
        == "pass"
    )

    corrected = venue_consistent_execution_measure_v2(
        row,
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=0.0,
        stress_bps=0.0,
    )
    raw_control = venue_mid_market_return_bps_v2(
        venue_mid=100.0,
        outcome_price=100.0,
    )
    corrected_baseline = direction_matched_venue_mid_baseline_bps_v2(
        raw_control,
        direction=direction,
    )
    absolute = corrected["absolute_stressed_net_bps"]
    excess = absolute - corrected_baseline
    assert absolute == pytest.approx(0.0)
    assert excess == pytest.approx(0.0)
    decision = conjunctive_confirmatory_decision_v2(
        absolute_point_estimate_bps=absolute,
        absolute_ci_lower_bps=absolute,
        absolute_ci_upper_bps=absolute,
        excess_point_estimate_bps=excess,
        excess_ci_lower_bps=excess,
        excess_ci_upper_bps=excess,
        minimum_effect_bps=10.0,
    )
    assert decision["confirmatory_state"] == "fail"


def test_corrected_endpoint_is_invariant_to_reference_price() -> None:
    snapshot = _snapshot(buy_cost=1.0, sell_cost=2.0)
    values = []
    for reference in (1.0, 100.0, 1_000_000.0):
        values.append(
            venue_consistent_execution_measure_v2(
                {
                    "direction": "long",
                    "observed_at": _OBSERVED_AT,
                    "end_price": 100.5,
                    "reference_price": reference,
                },
                snapshot,
                size_usd=1_000.0,
                fee_bps_per_side=0.0,
                stress_bps=0.0,
            )["absolute_stressed_net_bps"]
        )
    assert values[0] == values[1] == values[2]


@pytest.mark.parametrize(
    (
        "absolute_interval",
        "absolute_point",
        "excess_interval",
        "excess_point",
        "expected_absolute",
        "expected_excess",
        "expected_joint",
    ),
    [
        ((-20.0, -10.0), -15.0, (20.0, 40.0), 30.0, "fail", "pass", "fail"),
        ((5.0, 10.0), 7.0, (20.0, 40.0), 30.0, "pass", "pass", "pass"),
        ((-1.0, 3.0), 1.0, (20.0, 40.0), 30.0, "inconclusive", "pass", "inconclusive"),
        ((5.0, 10.0), 7.0, (8.0, 12.0), 11.0, "pass", "inconclusive", "inconclusive"),
        ((5.0, 10.0), 7.0, (8.0, 12.0), 9.0, "pass", "inconclusive", "inconclusive"),
        ((5.0, 10.0), 7.0, (2.0, 8.0), 5.0, "pass", "fail", "fail"),
        ((5.0, 10.0), 7.0, (-8.0, -2.0), -5.0, "pass", "fail", "fail"),
    ],
)
def test_p1_02_conjunctive_decision_matrix(
    absolute_interval: tuple[float, float],
    absolute_point: float,
    excess_interval: tuple[float, float],
    excess_point: float,
    expected_absolute: str,
    expected_excess: str,
    expected_joint: str,
) -> None:
    result = conjunctive_confirmatory_decision_v2(
        absolute_point_estimate_bps=absolute_point,
        absolute_ci_lower_bps=absolute_interval[0],
        absolute_ci_upper_bps=absolute_interval[1],
        excess_point_estimate_bps=excess_point,
        excess_ci_lower_bps=excess_interval[0],
        excess_ci_upper_bps=excess_interval[1],
        minimum_effect_bps=10.0,
    )
    assert result == {
        "absolute_component_state": expected_absolute,
        "excess_component_state": expected_excess,
        "confirmatory_state": expected_joint,
    }


def test_negative_absolute_point_estimate_cannot_pass_even_with_positive_ci() -> None:
    result = conjunctive_confirmatory_decision_v2(
        absolute_point_estimate_bps=-1.0,
        absolute_ci_lower_bps=5.0,
        absolute_ci_upper_bps=10.0,
        excess_point_estimate_bps=30.0,
        excess_ci_lower_bps=20.0,
        excess_ci_upper_bps=40.0,
        minimum_effect_bps=10.0,
    )
    assert result == {
        "absolute_component_state": "inconclusive",
        "excess_component_state": "pass",
        "confirmatory_state": "inconclusive",
    }


def test_paired_bootstrap_preserves_component_dependency_and_whole_rows() -> None:
    blocks = {
        "a": [(1.0, 10.0), (3.0, 30.0)],
        "b": [(5.0, 50.0)],
        "c": [(7.0, 70.0), (9.0, 90.0)],
    }
    first = paired_block_bootstrap_v2(blocks, repetitions=100, seed=123)
    second = paired_block_bootstrap_v2(
        {
            key: list(reversed(values))
            for key, values in reversed(list(blocks.items()))
        },
        repetitions=100,
        seed=123,
    )
    assert first == second
    assert all(excess == pytest.approx(absolute * 10.0) for absolute, excess in first)
    intervals = paired_block_bootstrap_ci_v2(first, confidence_level=0.95)
    assert intervals["excess_ci_lower_bps"] == pytest.approx(
        intervals["absolute_ci_lower_bps"] * 10.0
    )
    assert intervals["excess_ci_upper_bps"] == pytest.approx(
        intervals["absolute_ci_upper_bps"] * 10.0
    )


def test_scientific_mean_is_exactly_invariant_to_database_row_order() -> None:
    values = [1e16, 1.0, -1e16, 3.0, -2.0, 0.125]
    expected = deterministic_mean_v2(values)
    assert deterministic_mean_v2(list(reversed(values))) == expected
    assert deterministic_mean_v2(sorted(values, key=abs)) == expected


def test_outcome_window_v1_does_not_read_reinterpretable_live_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed = datetime(2026, 8, 13, 12, tzinfo=UTC)
    monkeypatch.setattr(signal_outcomes, "OUTCOME_HORIZONS_MINUTES", (999,))
    monkeypatch.setattr(signal_outcomes, "OUTCOME_SETTLEMENT_LAG", timedelta(days=99))
    window = signal_outcomes.outcome_window(observed, 15)
    assert window.start == observed + timedelta(minutes=1)
    assert window.end == observed + timedelta(minutes=16)
    assert window.due_at == window.end + timedelta(minutes=42)


def test_paired_bootstrap_sha256_draw_stream_has_a_golden_result() -> None:
    blocks = {
        "a": [(1.0, 10.0)],
        "b": [(2.0, 20.0)],
        "c": [(3.0, 30.0)],
    }
    assert PAIRED_BLOCK_BOOTSTRAP_DRAW_GENERATOR_V2 == (
        "sha256_counter_rejection_v1"
    )
    assert paired_block_bootstrap_v2(blocks, repetitions=5, seed=123) == [
        (2.0, 20.0),
        (2.3333333333333335, 23.333333333333332),
        (2.0, 20.0),
        (1.3333333333333333, 13.333333333333334),
        (2.3333333333333335, 23.333333333333332),
    ]


def test_corrected_contract_is_binance_only_while_v1_still_allows_bybit() -> None:
    _validate_v2(_contract_v2())
    with pytest.raises(ValueError, match="must be binance"):
        _validate_v2(
            _contract_v2(primary_exchange="bybit", outcome_price_venue="binance")
        )

    legacy = ConfirmatoryContract(
        primary_endpoint_version=1,
        primary_symbol="BTCUSDT_PERP.A",
        primary_horizon_minutes=15,
        primary_sampling_mode="utc_nonoverlap",
        primary_exchange="bybit",
        primary_size_usd=1_000.0,
        primary_taker_fee_bps=2.0,
        baseline_version=1,
        unmodeled_execution_stress_bps=0.0,
        inference_version=1,
        block_unit="day",
        block_length=1,
        bootstrap_repetitions=10,
        bootstrap_seed=1,
        confidence_level=0.95,
        minimum_effect_bps=0.0,
        minimum_primary_blocks=2,
        minimum_execution_data_coverage_pct=50.0,
        minimum_research_data_coverage_pct=50.0,
        confirmatory_decision_policy=CONFIRMATORY_DECISION_POLICY_V1,
    )
    validate_confirmatory_contract(
        legacy,
        symbols=("BTCUSDT_PERP.A",),
        horizons=(15,),
        sampling_modes=("utc_nonoverlap",),
        exchanges=("binance", "bybit"),
        sizes_usd=(1_000.0,),
        fee_bps_per_side=(("bybit", 2.0),),
    )


def test_v2_contract_requires_explicit_ex_funding_and_positive_grace() -> None:
    with pytest.raises(ValueError, match="funding_semantics"):
        _validate_v2(_contract_v2(funding_semantics="modeled"))
    with pytest.raises(ValueError, match="must be positive"):
        _validate_v2(_contract_v2(evaluation_settlement_grace_seconds=0))
    assert all(field.default is dataclasses.MISSING for field in dataclasses.fields(ConfirmatoryContractV2))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("bootstrap_seed", True),
        ("primary_taker_fee_bps", False),
        ("minimum_effect_bps", True),
        ("minimum_research_data_coverage_pct", True),
        ("primary_symbol", 123),
    ],
)
def test_v2_contract_parser_rejects_json_type_coercion(
    field: str, invalid: object
) -> None:
    raw = confirmatory_contract_v2_to_dict(_contract_v2())
    raw[field] = invalid
    with pytest.raises(ValueError):
        confirmatory_contract_v2_from_dict(raw)


def test_valid_snapshot_missing_frozen_size_is_explicit_invalid_shape() -> None:
    snapshot = _snapshot()
    snapshot["cost_curve"] = {}
    result = venue_consistent_execution_measure_v2(
        {"direction": "long", "observed_at": _OBSERVED_AT, "end_price": 101.0},
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=0.0,
        stress_bps=0.0,
    )
    assert result["snapshot_invalid_shape"] is True
    assert result["cost_evaluable"] is False


def test_snapshot_from_a_different_decision_instant_is_not_evaluable() -> None:
    snapshot = _snapshot()
    snapshot["captured_at"] = _OBSERVED_AT + timedelta(microseconds=1)
    result = venue_consistent_execution_measure_v2(
        {"direction": "long", "observed_at": _OBSERVED_AT, "end_price": 101.0},
        snapshot,
        size_usd=1_000.0,
        fee_bps_per_side=0.0,
        stress_bps=0.0,
    )
    assert result["snapshot_time_mismatch"] is True
    assert result["cost_evaluable"] is False


def test_evaluated_but_not_knowledge_usable_outcome_is_incomplete() -> None:
    window = signal_outcomes.outcome_window(_OBSERVED_AT, 15)
    counters = _confirmatory_v4_outcome_integrity_for_fold(
        [
            {
                "observed_minute": _OBSERVED_AT,
                "horizon_minutes": 15,
                "window_end": window.end,
                "due_at": window.due_at,
                "outcome_version": 1,
                "status": "evaluated",
                "usable": False,
                "market_return_pct": 1.0,
                "end_price": 101.0,
                "actionable": True,
                "direction": "long",
            }
        ],
        period_end=_OBSERVED_AT + timedelta(days=1),
        outcome_version=1,
    )
    assert counters["evaluated_periodic_n"] == 0
    assert counters["missing_or_wrong_version_n"] == 1
    assert counters["unresolved_actionable_n"] == 1


def test_settlement_boundary_is_exact_and_does_not_move_knowledge_cutoff() -> None:
    cutoff = datetime(2026, 8, 13, 12, tzinfo=UTC)
    assert evaluation_not_before_v2(
        cutoff, settlement_grace_seconds=37
    ) == cutoff + timedelta(seconds=37)


def test_expected_slot_count_uses_epoch_alignment_and_boundary_safe_windows() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=1)
    count = expected_utc_nonoverlap_slot_count_v2(
        test_start=start,
        test_end=end,
        horizon_minutes=15,
    )
    # 00:00, 00:15, 00:30 are safe; 00:45 ends at 01:01 and is purged.
    assert count == 3


def test_canonical_ast_ignores_comments_docstrings_and_formatting() -> None:
    first = '''
def f(value):
    """documentation"""
    # comment
    return value + 1
'''
    second = '''
def f( value ):
  """changed docs"""
  return value+1  # changed comment
'''
    changed = '''
def f(value):
    return value - 1
'''
    assert canonical_python_ast(first) == canonical_python_ast(second)
    assert canonical_python_ast(first) != canonical_python_ast(changed)


def test_canonical_ast_normalizes_sql_layout_but_preserves_literal_spaces() -> None:
    first = '''
query = """SELECT value
             FROM evidence
            WHERE label = 'a  b'"""
'''
    reformatted = '''
query = """SELECT value FROM evidence WHERE label = 'a  b'"""
'''
    changed_literal = '''
query = """SELECT value FROM evidence WHERE label = 'a b'"""
'''
    assert canonical_python_ast(first) == canonical_python_ast(reformatted)
    assert canonical_python_ast(first) != canonical_python_ast(changed_literal)


def test_sql_canonicalizer_preserves_line_comment_termination_semantics() -> None:
    executable = "-- guard\nCREATE TABLE evidence(id bigint);\n"
    commented_out = "-- guard CREATE TABLE evidence(id bigint);\n"
    assert canonical_sql_source_v1(executable) != canonical_sql_source_v1(
        commented_out
    )
    assert canonical_sql_source_v1(executable.replace("\n", "\r\n")) == (
        canonical_sql_source_v1(executable)
    )


def test_scientific_identity_is_registered_and_names_every_critical_component() -> None:
    identity = scientific_implementation_identity()
    assert identity["digest"] == (
        "c939add3055ea2a8b0edd1ea93630682043a2b98b4ac33425bc49acc47cf156c"
    )
    assert identity["digest"] == REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS[
        SCIENTIFIC_IDENTITY_VERSION_V1
    ]
    assert {component["name"] for component in identity["components"]} == {
        "scientific_identity_mechanics",
        "scientific_runtime_contract_mechanics",
        "market_routing_construction",
        "scalp_routing_application",
        "scalp_routing_entrypoint",
        "scalp_raw_delivery",
        "ws_routing_application",
        "ws_routing_entrypoint",
        "ws_raw_delivery",
        "signal_summary_decision_kernel",
        "signal_summary_oi_helpers",
        "signal_context_session_boundary",
        "signal_context_cutoff",
        "signal_observation_generation",
        "signal_replay_integrity",
        "visibility_transaction_boundary",
        "visibility_certificate_production",
        "outcome_data_gap_blocking",
        "knowledge_time_projection_and_grid",
        "outcome_materialization_semantics",
        "execution_snapshot_semantics",
        "corrected_endpoint_and_paired_inference",
        "confirmatory_v4_fetch_coverage_and_persistence",
        "authoritative_transaction_and_serialization",
        "signal_observation_database_boundary",
        "signal_outcome_database_boundary",
        "signal_replay_database_boundary",
        "signal_execution_database_boundary",
        "outcome_data_gap_database_boundary",
        "research_bundle_visibility_database_boundary",
        "outcome_final_visibility_database_boundary",
        "authoritative_result_database_boundary",
    }


def _copy_scientific_identity_surface(destination: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    for relative_path in {
        component.relative_path
        for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS
    }:
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative_path, target)


def test_scientific_dependency_mutation_changes_aggregate_identity(
    tmp_path: Path,
) -> None:
    _copy_scientific_identity_surface(tmp_path)
    baseline = compute_scientific_implementation_identity(root=tmp_path)
    dependency = tmp_path / "app/data_gaps.py"
    source = dependency.read_text(encoding="utf-8")
    original = "gap.start_ts < required.end_ts"
    changed = "gap.start_ts <= required.end_ts"
    assert original in source
    dependency.write_text(source.replace(original, changed, 1), encoding="utf-8")

    mutated = compute_scientific_implementation_identity(root=tmp_path)
    assert mutated["digest"] != baseline["digest"]
    baseline_components = {
        component["name"]: component["digest"]
        for component in baseline["components"]
    }
    mutated_components = {
        component["name"]: component["digest"]
        for component in mutated["components"]
    }
    assert mutated_components["outcome_data_gap_blocking"] != (
        baseline_components["outcome_data_gap_blocking"]
    )


def test_scientific_identity_ignores_allowed_python_comment_change(
    tmp_path: Path,
) -> None:
    _copy_scientific_identity_surface(tmp_path)
    baseline = compute_scientific_implementation_identity(root=tmp_path)
    dependency = tmp_path / "app/data_gaps.py"
    source = dependency.read_text(encoding="utf-8")
    marker = "# PR27_SCIENTIFIC_OUTCOME_GAP_BLOCKING_V1_BEGIN\n"
    assert marker in source
    dependency.write_text(
        source.replace(
            marker,
            marker + "# Formatting-only audit note; no executable semantics.\n\n",
            1,
        ),
        encoding="utf-8",
    )

    reformatted = compute_scientific_implementation_identity(root=tmp_path)
    assert reformatted == baseline


def test_scientific_identity_rejects_boolean_version_coercion() -> None:
    stored = scientific_implementation_identity()
    stored["identity_version"] = True
    with pytest.raises(ValueError, match="must be an integer"):
        validate_scientific_implementation_identity(stored)


def test_canonical_result_hash_is_key_order_and_timezone_stable() -> None:
    instant_utc = datetime(2026, 8, 13, 12, tzinfo=UTC)
    instant_offset = instant_utc.astimezone(timezone(timedelta(hours=-6)))
    first = {"b": 2, "a": instant_utc, "nested": {"x": 1.5}}
    second = {"nested": {"x": 1.5}, "a": instant_offset, "b": 2}
    assert canonical_scientific_result_json(first) == canonical_scientific_result_json(
        second
    )
    assert scientific_result_hash(first) == scientific_result_hash(second)
    assert len(scientific_result_hash(first)) == 64
    assert '"binary64_hex_v1":"0x1.8000000000000p+0"' in (
        canonical_scientific_result_json(first)
    )
    with pytest.raises(ValueError, match="non-finite"):
        canonical_scientific_result_json({"value": math.nan})


def test_no_reference_price_name_exists_in_corrected_endpoint_function_code() -> None:
    # The adversarial input may carry the field, but endpoint-v2 never reads it.
    import inspect

    source = inspect.getsource(venue_consistent_execution_measure_v2)
    assert 'row.get("reference_price")' not in source
    assert math.isfinite(
        venue_consistent_execution_measure_v2(
            {"direction": "long", "observed_at": _OBSERVED_AT, "end_price": 100.0},
            _snapshot(),
            size_usd=1_000.0,
            fee_bps_per_side=0.0,
            stress_bps=0.0,
        )["absolute_stressed_net_bps"]
    )
