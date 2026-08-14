"""PR27 corrected confirmatory endpoint and paired block inference.

This module is a stdlib-only scientific leaf.  It has no database or wall
clock access.  Spec v4 is its only caller; PR26's published spec-v3 module is
not imported or modified here.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime, timedelta
from typing import Any

# PR27_SCIENTIFIC_CONFIRMATORY_V2_BEGIN

CONFIRMATORY_PRIMARY_ENDPOINT_VERSION_V2 = 2
CONFIRMATORY_PRIMARY_ENDPOINT_NAME_V2 = (
    "binance_mid_control_measured_entry_opposite_book_exit_"
    "net_of_fees_and_stress_ex_funding_v2"
)

BLOCK_UNCONDITIONAL_VENUE_MID_BASELINE_VERSION_V2 = 2
BLOCK_UNCONDITIONAL_VENUE_MID_BASELINE_NAME_V2 = (
    "block_binance_mid_unconditional_direction_matched_baseline_v2"
)

PAIRED_BLOCK_BOOTSTRAP_INFERENCE_VERSION_V2 = 2
PAIRED_BLOCK_BOOTSTRAP_INFERENCE_NAME_V2 = "paired_block_bootstrap_v2"
PAIRED_BLOCK_BOOTSTRAP_DRAW_GENERATOR_V2 = "sha256_counter_rejection_v1"
CONFIRMATORY_AGGREGATION_SEMANTICS_V2 = "sorted_math_fsum_mean_v1"

CONJUNCTIVE_DECISION_POLICY_V2 = (
    "conjunctive_absolute_positive_and_excess_ci_v2"
)

CONFIRMATORY_RESULT_CONTRACT_VERSION_V1 = 1
CONFIRMATORY_RESULT_FLOAT_ENCODING_V1 = "binary64_hex_v1"
CONFIRMATORY_FUNDING_SEMANTICS_EXCLUDED_V1 = "excluded_v1"
CONFIRMATORY_OUTCOME_PRICE_VENUE_V1 = "binance"
CONFIRMATORY_OUTCOME_PRICE_SOURCE_V1 = "binance_perpetual_ohlcv_1min_v1"
CONFIRMATORY_PRIMARY_SAMPLING_MODE_V1 = "utc_nonoverlap"

# Frozen execution-snapshot-v1 and PR5 outcome-v1 shapes.  These are
# literals, never imports from a live/current constant: changing either set
# requires a new prospective scientific identity/spec.
CONFIRMATORY_SUPPORTED_HORIZONS_V2 = (1, 3, 5, 15, 30, 60, 120, 240)
CONFIRMATORY_SUPPORTED_EXECUTION_SIZES_V2 = (
    1_000.0,
    10_000.0,
    50_000.0,
    100_000.0,
)
CONFIRMATORY_PRIMARY_EXCHANGES_V2 = ("binance",)
CONFIRMATORY_BLOCK_UNITS_V2 = ("hour", "day")
_BLOCK_UNIT_SECONDS_V2 = {"hour": 3600, "day": 86400}
_EPOCH_V2 = datetime(1970, 1, 1, tzinfo=UTC)

CONFIRMATORY_STATE_NOT_READY = "not_ready"
CONFIRMATORY_STATE_PASS = "pass"
CONFIRMATORY_STATE_FAIL = "fail"
CONFIRMATORY_STATE_INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True, slots=True)
class ConfirmatoryContractV2:
    """Spec-v4 contract; every field is caller-required and hash-bound."""

    primary_endpoint_version: int
    primary_symbol: str
    primary_horizon_minutes: int
    primary_sampling_mode: str
    primary_exchange: str
    outcome_price_venue: str
    primary_size_usd: float
    primary_taker_fee_bps: float
    baseline_version: int
    unmodeled_execution_stress_bps: float
    funding_semantics: str
    inference_version: int
    block_unit: str
    block_length: int
    bootstrap_repetitions: int
    bootstrap_seed: int
    confidence_level: float
    minimum_effect_bps: float
    minimum_primary_blocks: int
    minimum_execution_data_coverage_pct: float
    minimum_research_data_coverage_pct: float
    evaluation_settlement_grace_seconds: int
    confirmatory_decision_policy: str


_CONTRACT_FIELDS_V2 = tuple(field.name for field in fields(ConfirmatoryContractV2))

_CONTRACT_INTEGER_FIELDS_V2 = frozenset(
    {
        "primary_endpoint_version",
        "primary_horizon_minutes",
        "baseline_version",
        "inference_version",
        "block_length",
        "bootstrap_repetitions",
        "bootstrap_seed",
        "minimum_primary_blocks",
        "evaluation_settlement_grace_seconds",
    }
)
_CONTRACT_NUMERIC_FIELDS_V2 = frozenset(
    {
        "primary_size_usd",
        "primary_taker_fee_bps",
        "unmodeled_execution_stress_bps",
        "confidence_level",
        "minimum_effect_bps",
        "minimum_execution_data_coverage_pct",
        "minimum_research_data_coverage_pct",
    }
)
_CONTRACT_STRING_FIELDS_V2 = frozenset(_CONTRACT_FIELDS_V2) - (
    _CONTRACT_INTEGER_FIELDS_V2 | _CONTRACT_NUMERIC_FIELDS_V2
)


def confirmatory_contract_v2_to_dict(
    contract: ConfirmatoryContractV2,
) -> dict[str, Any]:
    return {name: getattr(contract, name) for name in _CONTRACT_FIELDS_V2}


def confirmatory_contract_v2_from_dict(data: object) -> ConfirmatoryContractV2:
    if not isinstance(data, dict) or set(data) != set(_CONTRACT_FIELDS_V2):
        raise ValueError(
            "confirmatory_contract v2 has unknown or missing fields; expected exactly "
            f"{sorted(_CONTRACT_FIELDS_V2)}"
        )
    for name in _CONTRACT_INTEGER_FIELDS_V2:
        if isinstance(data[name], bool) or not isinstance(data[name], int):
            raise ValueError(f"confirmatory_contract v2 {name} must be an integer")
    for name in _CONTRACT_NUMERIC_FIELDS_V2:
        if isinstance(data[name], bool) or not isinstance(data[name], (int, float)):
            raise ValueError(f"confirmatory_contract v2 {name} must be numeric")
    for name in _CONTRACT_STRING_FIELDS_V2:
        if not isinstance(data[name], str):
            raise ValueError(f"confirmatory_contract v2 {name} must be text")
    return ConfirmatoryContractV2(
        primary_endpoint_version=int(data["primary_endpoint_version"]),
        primary_symbol=str(data["primary_symbol"]),
        primary_horizon_minutes=int(data["primary_horizon_minutes"]),
        primary_sampling_mode=str(data["primary_sampling_mode"]),
        primary_exchange=str(data["primary_exchange"]),
        outcome_price_venue=str(data["outcome_price_venue"]),
        primary_size_usd=float(data["primary_size_usd"]),
        primary_taker_fee_bps=float(data["primary_taker_fee_bps"]),
        baseline_version=int(data["baseline_version"]),
        unmodeled_execution_stress_bps=float(
            data["unmodeled_execution_stress_bps"]
        ),
        funding_semantics=str(data["funding_semantics"]),
        inference_version=int(data["inference_version"]),
        block_unit=str(data["block_unit"]),
        block_length=int(data["block_length"]),
        bootstrap_repetitions=int(data["bootstrap_repetitions"]),
        bootstrap_seed=int(data["bootstrap_seed"]),
        confidence_level=float(data["confidence_level"]),
        minimum_effect_bps=float(data["minimum_effect_bps"]),
        minimum_primary_blocks=int(data["minimum_primary_blocks"]),
        minimum_execution_data_coverage_pct=float(
            data["minimum_execution_data_coverage_pct"]
        ),
        minimum_research_data_coverage_pct=float(
            data["minimum_research_data_coverage_pct"]
        ),
        evaluation_settlement_grace_seconds=int(
            data["evaluation_settlement_grace_seconds"]
        ),
        confirmatory_decision_policy=str(data["confirmatory_decision_policy"]),
    )


def validate_confirmatory_contract_v2(
    contract: ConfirmatoryContractV2,
    *,
    symbols: tuple[str, ...],
    horizons: tuple[int, ...],
    sampling_modes: tuple[str, ...],
    exchanges: tuple[str, ...],
    sizes_usd: tuple[float, ...],
    fee_bps_per_side: tuple[tuple[str, float], ...],
) -> None:
    for int_field in (
        "block_length",
        "bootstrap_repetitions",
        "bootstrap_seed",
        "minimum_primary_blocks",
        "evaluation_settlement_grace_seconds",
    ):
        value = getattr(contract, int_field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"confirmatory v2 {int_field} must be an int")

    for numeric_field in _CONTRACT_NUMERIC_FIELDS_V2:
        value = getattr(contract, numeric_field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"confirmatory v2 {numeric_field} must be numeric")
    for string_field in _CONTRACT_STRING_FIELDS_V2:
        if not isinstance(getattr(contract, string_field), str):
            raise ValueError(f"confirmatory v2 {string_field} must be text")

    if contract.primary_endpoint_version != CONFIRMATORY_PRIMARY_ENDPOINT_VERSION_V2:
        raise ValueError("confirmatory v2 primary_endpoint_version must be 2")
    if not contract.primary_symbol.strip():
        raise ValueError("confirmatory v2 primary_symbol must be non-empty")
    if symbols and contract.primary_symbol not in symbols:
        raise ValueError("confirmatory v2 primary_symbol must be frozen in manifest symbols")

    if contract.primary_horizon_minutes not in CONFIRMATORY_SUPPORTED_HORIZONS_V2:
        raise ValueError("confirmatory v2 primary horizon is not outcome-v1 compatible")
    if contract.primary_horizon_minutes not in horizons:
        raise ValueError("confirmatory v2 primary horizon must be frozen in manifest horizons")

    if contract.primary_sampling_mode != CONFIRMATORY_PRIMARY_SAMPLING_MODE_V1:
        raise ValueError("confirmatory v2 primary sampling mode must be utc_nonoverlap")
    if contract.primary_sampling_mode not in sampling_modes:
        raise ValueError("confirmatory v2 primary sampling mode is absent from manifest")

    if contract.primary_exchange not in CONFIRMATORY_PRIMARY_EXCHANGES_V2:
        raise ValueError(
            "confirmatory v2 primary_exchange must be binance until a "
            "venue-specific outcome series exists"
        )
    if contract.primary_exchange not in exchanges:
        raise ValueError("confirmatory v2 primary exchange is absent from manifest")
    if contract.outcome_price_venue != CONFIRMATORY_OUTCOME_PRICE_VENUE_V1:
        raise ValueError("confirmatory v2 outcome_price_venue must be binance")
    if contract.outcome_price_venue != contract.primary_exchange:
        raise ValueError("confirmatory v2 entry and outcome venues must match")

    if contract.primary_size_usd not in CONFIRMATORY_SUPPORTED_EXECUTION_SIZES_V2:
        raise ValueError("confirmatory v2 primary size is not snapshot-v1 compatible")
    if contract.primary_size_usd not in sizes_usd:
        raise ValueError("confirmatory v2 primary size is absent from manifest")

    if not math.isfinite(contract.primary_taker_fee_bps) or not (
        0.0 <= contract.primary_taker_fee_bps <= 100.0
    ):
        raise ValueError("confirmatory v2 taker fee must be finite in [0,100]")
    if dict(fee_bps_per_side).get(contract.primary_exchange) != (
        contract.primary_taker_fee_bps
    ):
        raise ValueError("confirmatory v2 fee must equal the manifest's frozen venue fee")

    if (
        contract.baseline_version
        != BLOCK_UNCONDITIONAL_VENUE_MID_BASELINE_VERSION_V2
    ):
        raise ValueError("confirmatory v2 baseline_version must be 2")
    if not math.isfinite(contract.unmodeled_execution_stress_bps) or (
        contract.unmodeled_execution_stress_bps < 0.0
    ):
        raise ValueError("confirmatory v2 execution stress must be finite and >= 0")
    if contract.funding_semantics != CONFIRMATORY_FUNDING_SEMANTICS_EXCLUDED_V1:
        raise ValueError("confirmatory v2 funding_semantics must be excluded_v1")

    if contract.inference_version != PAIRED_BLOCK_BOOTSTRAP_INFERENCE_VERSION_V2:
        raise ValueError("confirmatory v2 inference_version must be 2")
    if contract.block_unit not in CONFIRMATORY_BLOCK_UNITS_V2:
        raise ValueError("confirmatory v2 block_unit must be hour or day")
    if contract.block_length < 1:
        raise ValueError("confirmatory v2 block_length must be >= 1")
    if contract.bootstrap_repetitions < 2:
        raise ValueError("confirmatory v2 bootstrap_repetitions must be >= 2")
    if not 0.0 < contract.confidence_level < 1.0:
        raise ValueError("confirmatory v2 confidence_level must be in (0,1)")
    if not math.isfinite(contract.minimum_effect_bps) or (
        contract.minimum_effect_bps < 0.0
    ):
        raise ValueError("confirmatory v2 minimum_effect_bps must be finite and >= 0")
    if contract.minimum_primary_blocks < 2:
        raise ValueError("confirmatory v2 minimum_primary_blocks must be >= 2")
    if not 0.0 < contract.minimum_execution_data_coverage_pct <= 100.0:
        raise ValueError("confirmatory v2 execution coverage must be in (0,100]")
    if not 0.0 < contract.minimum_research_data_coverage_pct <= 100.0:
        raise ValueError("confirmatory v2 research coverage must be in (0,100]")
    if contract.evaluation_settlement_grace_seconds <= 0:
        raise ValueError(
            "confirmatory v2 evaluation settlement grace must be positive; "
            "zero cannot close the certificate commit window"
        )
    if contract.confirmatory_decision_policy != CONJUNCTIVE_DECISION_POLICY_V2:
        raise ValueError("confirmatory v2 decision policy identifier is unsupported")


def _curve_at_frozen_size(
    snapshot: dict[str, Any], size_usd: float
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    curve: object = snapshot.get("cost_curve")
    if isinstance(curve, str):
        try:
            curve = json.loads(curve)
        except json.JSONDecodeError:
            return None
    if not isinstance(curve, dict):
        return None
    size_curve = curve.get(str(int(size_usd)))
    if not isinstance(size_curve, dict):
        return None
    buy = size_curve.get("buy")
    sell = size_curve.get("sell")
    if not isinstance(buy, dict) or not isinstance(sell, dict):
        return None
    return buy, sell


def _finite_float(value: object) -> float | None:
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return converted if math.isfinite(converted) else None


def snapshot_matches_observation_time_v2(
    row: dict[str, Any], snapshot: dict[str, Any]
) -> bool:
    observed_at = row.get("observed_at")
    captured_at = snapshot.get("captured_at")
    if not isinstance(observed_at, datetime) or not isinstance(captured_at, datetime):
        return False
    if (
        observed_at.tzinfo is None
        or observed_at.utcoffset() is None
        or captured_at.tzinfo is None
        or captured_at.utcoffset() is None
    ):
        return False
    return observed_at.astimezone(UTC) == captured_at.astimezone(UTC)


def venue_mid_market_return_bps_v2(*, venue_mid: float, outcome_price: float) -> float:
    if not (
        math.isfinite(venue_mid)
        and venue_mid > 0.0
        and math.isfinite(outcome_price)
        and outcome_price > 0.0
    ):
        raise ValueError("venue mid and outcome price must be finite and positive")
    return (outcome_price / venue_mid - 1.0) * 10_000.0


def direction_matched_venue_mid_baseline_bps_v2(
    block_unconditional_venue_mid_mean_bps: float,
    *,
    direction: str,
) -> float:
    if not math.isfinite(block_unconditional_venue_mid_mean_bps):
        raise ValueError("baseline block mean must be finite")
    if direction == "long":
        return block_unconditional_venue_mid_mean_bps
    if direction == "short":
        return -block_unconditional_venue_mid_mean_bps
    raise ValueError(f"unsupported confirmatory v2 direction: {direction!r}")


def venue_consistent_execution_measure_v2(
    row: dict[str, Any],
    snapshot: dict[str, Any] | None,
    *,
    size_usd: float,
    fee_bps_per_side: float,
    stress_bps: float,
) -> dict[str, Any]:
    """Compute endpoint-v2 without reading ``reference_price``.

    The actual entry uses the directional Binance VWAP.  The modeled exit
    applies the opposite-side market-cost rate frozen in the same Binance
    decision-time snapshot to the Binance outcome close.  Fees are charged
    once per side and the frozen non-funding stress is charged once.
    """

    direction = row.get("direction")
    status = None if snapshot is None else snapshot.get("status")
    result: dict[str, Any] = {
        "snapshot_missing": snapshot is None,
        "snapshot_nonvalid": snapshot is not None and status != "valid",
        "snapshot_time_mismatch": False,
        "snapshot_invalid_shape": False,
        "entry_insufficient_depth": False,
        "exit_model_insufficient_depth": False,
        "insufficient_depth": False,
        "cost_evaluable": False,
        "venue_mid_price": None,
        "entry_fill_price": None,
        "outcome_exit_reference_price": None,
        "entry_market_impact_bps": None,
        "modeled_exit_cost_bps": None,
        "modeled_fee_cost_bps": None,
        "modeled_net_after_fees_bps": None,
        "absolute_stressed_net_bps": None,
    }
    if direction not in ("long", "short"):
        result["snapshot_invalid_shape"] = True
        return result
    if snapshot is None or status != "valid":
        return result
    if not snapshot_matches_observation_time_v2(row, snapshot):
        result["snapshot_time_mismatch"] = True
        return result
    if not (
        math.isfinite(fee_bps_per_side)
        and 0.0 <= fee_bps_per_side <= 100.0
        and math.isfinite(stress_bps)
        and stress_bps >= 0.0
    ):
        raise ValueError("fee and stress must be finite and non-negative")

    curve = _curve_at_frozen_size(snapshot, size_usd)
    venue_mid = _finite_float(snapshot.get("mid_px"))
    outcome_price = _finite_float(row.get("end_price"))
    if curve is None or venue_mid is None or venue_mid <= 0.0:
        result["snapshot_invalid_shape"] = True
        return result
    if outcome_price is None or outcome_price <= 0.0:
        result["snapshot_invalid_shape"] = True
        return result

    buy, sell = curve
    entry_leg, exit_leg = (buy, sell) if direction == "long" else (sell, buy)
    entry_insufficient = bool(entry_leg.get("insufficient_depth"))
    exit_insufficient = bool(exit_leg.get("insufficient_depth"))
    result["entry_insufficient_depth"] = entry_insufficient
    result["exit_model_insufficient_depth"] = exit_insufficient
    result["insufficient_depth"] = entry_insufficient or exit_insufficient
    result["venue_mid_price"] = venue_mid
    result["outcome_exit_reference_price"] = outcome_price
    if result["insufficient_depth"]:
        return result

    buy_fill = _finite_float(buy.get("avg_price"))
    sell_fill = _finite_float(sell.get("avg_price"))
    buy_cost = _finite_float(buy.get("market_cost_bps_vs_mid"))
    sell_cost = _finite_float(sell.get("market_cost_bps_vs_mid"))
    if (
        buy_fill is None
        or sell_fill is None
        or buy_fill <= 0.0
        or sell_fill <= 0.0
        or buy_cost is None
        or sell_cost is None
        or not 0.0 <= buy_cost < 10_000.0
        or not 0.0 <= sell_cost < 10_000.0
    ):
        result["snapshot_invalid_shape"] = True
        return result

    derived_buy_cost = (buy_fill / venue_mid - 1.0) * 10_000.0
    derived_sell_cost = (venue_mid - sell_fill) / venue_mid * 10_000.0
    if (
        derived_buy_cost < -1e-9
        or derived_sell_cost < -1e-9
        or not math.isclose(derived_buy_cost, buy_cost, rel_tol=0.0, abs_tol=1e-6)
        or not math.isclose(derived_sell_cost, sell_cost, rel_tol=0.0, abs_tol=1e-6)
    ):
        result["snapshot_invalid_shape"] = True
        return result

    if direction == "long":
        entry_fill = buy_fill
        entry_impact = buy_cost
        exit_cost = sell_cost
        modeled_exit_fill = outcome_price * (1.0 - exit_cost / 10_000.0)
        exit_to_entry_ratio = modeled_exit_fill / entry_fill
        modeled_after_market = (exit_to_entry_ratio - 1.0) * 10_000.0
    else:
        entry_fill = sell_fill
        entry_impact = sell_cost
        exit_cost = buy_cost
        modeled_exit_fill = outcome_price * (1.0 + exit_cost / 10_000.0)
        exit_to_entry_ratio = modeled_exit_fill / entry_fill
        modeled_after_market = (1.0 - exit_to_entry_ratio) * 10_000.0

    fee_rate = fee_bps_per_side / 10_000.0
    # P&L / entry notional. Entry fee costs f; exit fee costs f times
    # exit-notional / entry-notional. This is the exact two-leg fee cash flow,
    # not the constant 2*f approximation.
    modeled_fee_cost = fee_rate * (1.0 + exit_to_entry_ratio) * 10_000.0
    modeled_after_fees = modeled_after_market - modeled_fee_cost
    absolute_stressed = modeled_after_fees - stress_bps
    if not (
        math.isfinite(modeled_fee_cost)
        and modeled_fee_cost >= 0.0
        and math.isfinite(modeled_after_fees)
        and math.isfinite(absolute_stressed)
    ):
        result["snapshot_invalid_shape"] = True
        return result

    result.update(
        {
            "cost_evaluable": True,
            "entry_fill_price": entry_fill,
            "entry_market_impact_bps": entry_impact,
            "modeled_exit_cost_bps": exit_cost,
            "modeled_fee_cost_bps": modeled_fee_cost,
            "modeled_net_after_fees_bps": modeled_after_fees,
            "absolute_stressed_net_bps": absolute_stressed,
        }
    )
    return result


def utc_nonoverlap_selected_v2(
    observed_minute: datetime, *, horizon_minutes: int
) -> bool:
    if horizon_minutes not in CONFIRMATORY_SUPPORTED_HORIZONS_V2:
        raise ValueError("unsupported confirmatory v2 horizon")
    if observed_minute.tzinfo is None or observed_minute.utcoffset() is None:
        raise ValueError("observed_minute must be timezone-aware")
    minute_index = math.floor(observed_minute.astimezone(UTC).timestamp() / 60.0)
    return minute_index % horizon_minutes == 0


def expected_utc_nonoverlap_slot_count_v2(
    *,
    test_start: datetime,
    test_end: datetime,
    horizon_minutes: int,
) -> int:
    if horizon_minutes not in CONFIRMATORY_SUPPORTED_HORIZONS_V2:
        raise ValueError("unsupported confirmatory v2 horizon")
    if (
        test_start.tzinfo is None
        or test_start.utcoffset() is None
        or test_end.tzinfo is None
        or test_end.utcoffset() is None
    ):
        raise ValueError("test boundaries must be timezone-aware")
    start = test_start.astimezone(UTC)
    end = test_end.astimezone(UTC)
    if end <= start:
        return 0

    first_minute = math.ceil(start.timestamp() / 60.0)
    remainder = first_minute % horizon_minutes
    if remainder:
        first_minute += horizon_minutes - remainder

    count = 0
    minute_index = first_minute
    while minute_index * 60.0 < end.timestamp():
        observed = datetime.fromtimestamp(minute_index * 60.0, tz=UTC)
        window_end = observed.replace(second=0, microsecond=0) + timedelta(
            minutes=1 + horizon_minutes
        )
        if window_end <= end:
            count += 1
        minute_index += horizon_minutes
    return count


def evaluation_not_before_v2(
    knowledge_cutoff: datetime, *, settlement_grace_seconds: int
) -> datetime:
    if knowledge_cutoff.tzinfo is None or knowledge_cutoff.utcoffset() is None:
        raise ValueError("knowledge cutoff must be timezone-aware")
    if isinstance(settlement_grace_seconds, bool) or not isinstance(
        settlement_grace_seconds, int
    ):
        raise ValueError("settlement grace seconds must be an int")
    if settlement_grace_seconds <= 0:
        raise ValueError("settlement grace seconds must be positive")
    return knowledge_cutoff.astimezone(UTC) + timedelta(
        seconds=settlement_grace_seconds
    )


def confirmatory_block_key_v2(
    observed_minute: datetime, *, block_unit: str, block_length: int
) -> str:
    if block_unit not in CONFIRMATORY_BLOCK_UNITS_V2:
        raise ValueError("unsupported confirmatory v2 block unit")
    if block_length < 1:
        raise ValueError("confirmatory v2 block length must be >= 1")
    if observed_minute.tzinfo is None or observed_minute.utcoffset() is None:
        raise ValueError("observed_minute must be timezone-aware")
    seconds = _BLOCK_UNIT_SECONDS_V2[block_unit] * block_length
    elapsed = (observed_minute.astimezone(UTC) - _EPOCH_V2).total_seconds()
    return f"{block_unit}:{block_length}:{math.floor(elapsed / seconds)}"


def deterministic_mean_v2(values: list[float]) -> float:
    """Order-invariant finite mean with an explicit aggregation contract."""

    normalized = [float(value) for value in values]
    if not normalized:
        raise ValueError("confirmatory v2 mean requires at least one value")
    if any(not math.isfinite(value) for value in normalized):
        raise ValueError("confirmatory v2 mean requires finite values")
    # PostgreSQL does not promise row order without ORDER BY.  Sorting before
    # fsum makes both the summation inputs and their binary result independent
    # of query/planner order while retaining accurate cancellation behavior.
    return math.fsum(sorted(normalized)) / len(normalized)


def paired_block_bootstrap_v2(
    block_pairs: dict[str, list[tuple[float, float]]],
    *,
    repetitions: int,
    seed: int,
) -> list[tuple[float, float]]:
    """Resample whole blocks once and compute paired absolute/excess means."""

    if repetitions < 1:
        raise ValueError("paired block bootstrap repetitions must be >= 1")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("paired block bootstrap seed must be an int")
    keys = sorted(block_pairs)
    if not keys:
        raise ValueError("paired block bootstrap requires at least one block")
    for key in keys:
        pairs = block_pairs[key]
        if not pairs:
            raise ValueError(f"paired block {key!r} is empty")
        if any(
            not (math.isfinite(absolute) and math.isfinite(excess))
            for absolute, excess in pairs
        ):
            raise ValueError(f"paired block {key!r} contains a non-finite value")

    result: list[tuple[float, float]] = []
    for repetition in range(repetitions):
        drawn_keys = [
            keys[
                _deterministic_block_index_v2(
                    seed=seed,
                    repetition=repetition,
                    draw=draw,
                    population_size=len(keys),
                )
            ]
            for draw in range(len(keys))
        ]
        pooled: list[tuple[float, float]] = []
        for key in drawn_keys:
            pooled.extend(block_pairs[key])
        result.append(
            (
                deterministic_mean_v2([pair[0] for pair in pooled]),
                deterministic_mean_v2([pair[1] for pair in pooled]),
            )
        )
    return result


def _deterministic_block_index_v2(
    *, seed: int, repetition: int, draw: int, population_size: int
) -> int:
    """Uniform index from a versioned SHA-256 counter stream.

    Rejection sampling avoids modulo bias.  Unlike ``random.Random``, this
    draw contract does not depend on a Python runtime's PRNG implementation.
    """

    if population_size < 1:
        raise ValueError("paired block bootstrap population must be non-empty")
    sample_space = 1 << 256
    acceptance_limit = sample_space - sample_space % population_size
    retry = 0
    while True:
        material = (
            f"{PAIRED_BLOCK_BOOTSTRAP_DRAW_GENERATOR_V2}\0"
            f"{seed}\0{repetition}\0{draw}\0{retry}"
        ).encode("ascii")
        candidate = int.from_bytes(hashlib.sha256(material).digest(), "big")
        if candidate < acceptance_limit:
            return candidate % population_size
        retry += 1


def _percentile_v2(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return ordered[lower_index]
    return (
        ordered[lower_index] * (upper_index - position)
        + ordered[upper_index] * (position - lower_index)
    )


def paired_block_bootstrap_ci_v2(
    paired_means: list[tuple[float, float]],
    *,
    confidence_level: float,
) -> dict[str, float]:
    if not paired_means:
        raise ValueError("paired block bootstrap CI requires resample means")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0,1)")
    alpha = 1.0 - confidence_level
    absolute = [pair[0] for pair in paired_means]
    excess = [pair[1] for pair in paired_means]
    return {
        "absolute_ci_lower_bps": _percentile_v2(absolute, alpha / 2.0),
        "absolute_ci_upper_bps": _percentile_v2(absolute, 1.0 - alpha / 2.0),
        "excess_ci_lower_bps": _percentile_v2(excess, alpha / 2.0),
        "excess_ci_upper_bps": _percentile_v2(excess, 1.0 - alpha / 2.0),
    }


def _component_decision_v2(
    *,
    point_estimate_bps: float,
    lower_ci_bps: float,
    upper_ci_bps: float,
    pass_threshold_bps: float,
) -> str:
    if not (
        math.isfinite(point_estimate_bps)
        and math.isfinite(lower_ci_bps)
        and math.isfinite(upper_ci_bps)
        and lower_ci_bps <= upper_ci_bps
        and math.isfinite(pass_threshold_bps)
        and pass_threshold_bps >= 0.0
    ):
        raise ValueError("invalid confirmatory v2 component CI or threshold")
    if upper_ci_bps <= pass_threshold_bps:
        return CONFIRMATORY_STATE_FAIL
    if (
        point_estimate_bps > pass_threshold_bps
        and lower_ci_bps > pass_threshold_bps
    ):
        return CONFIRMATORY_STATE_PASS
    return CONFIRMATORY_STATE_INCONCLUSIVE


def conjunctive_confirmatory_decision_v2(
    *,
    absolute_point_estimate_bps: float,
    absolute_ci_lower_bps: float,
    absolute_ci_upper_bps: float,
    excess_point_estimate_bps: float,
    excess_ci_lower_bps: float,
    excess_ci_upper_bps: float,
    minimum_effect_bps: float,
) -> dict[str, str]:
    """Intersection-union decision for one jointly resampled claim.

    A point estimate that does not clear its threshold can never PASS.  If
    its interval still crosses or clears the threshold, the scientifically
    conservative state is INCONCLUSIVE rather than a fabricated decisive
    FAIL.
    """

    absolute_state = _component_decision_v2(
        point_estimate_bps=absolute_point_estimate_bps,
        lower_ci_bps=absolute_ci_lower_bps,
        upper_ci_bps=absolute_ci_upper_bps,
        pass_threshold_bps=0.0,
    )
    excess_state = _component_decision_v2(
        point_estimate_bps=excess_point_estimate_bps,
        lower_ci_bps=excess_ci_lower_bps,
        upper_ci_bps=excess_ci_upper_bps,
        pass_threshold_bps=minimum_effect_bps,
    )
    if CONFIRMATORY_STATE_FAIL in (absolute_state, excess_state):
        joint_state = CONFIRMATORY_STATE_FAIL
    elif (
        absolute_state == CONFIRMATORY_STATE_PASS
        and excess_state == CONFIRMATORY_STATE_PASS
    ):
        joint_state = CONFIRMATORY_STATE_PASS
    else:
        joint_state = CONFIRMATORY_STATE_INCONCLUSIVE
    return {
        "absolute_component_state": absolute_state,
        "excess_component_state": excess_state,
        "confirmatory_state": joint_state,
    }


def _canonical_scientific_result_value_v1(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical scientific result contains non-finite float")
        return {CONFIRMATORY_RESULT_FLOAT_ENCODING_V1: value.hex()}
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("canonical result timestamp must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("canonical scientific result keys must be strings")
        return {
            key: _canonical_scientific_result_value_v1(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_scientific_result_value_v1(item) for item in value]
    raise TypeError(
        f"{type(value).__name__} is not a canonical scientific result value"
    )


def canonical_scientific_result_json(value: object) -> str:
    return json.dumps(
        _canonical_scientific_result_value_v1(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def scientific_result_hash(value: object) -> str:
    return hashlib.sha256(
        canonical_scientific_result_json(value).encode("utf-8")
    ).hexdigest()


# PR27_SCIENTIFIC_CONFIRMATORY_V2_END
