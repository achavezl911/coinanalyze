"""PR26: confirmatory walk-forward spec v3 -- primary contract, clock/
direction-matched baseline, and deterministic block-bootstrap inference.

This module is a dependency-free (stdlib-only) leaf: it never imports
``asyncpg`` and never reads a wall clock. Everything here is a pure function
of caller-supplied values, which is what makes the block bootstrap
deterministic and reproducible for a frozen seed.

PR11 (``app/signal_walk_forward.py``) is the only caller. It owns all I/O:
fetching the OOS rows a matured fold makes available, then handing this
module plain values (bps floats, timestamps, contract fields) to validate,
group into calendar blocks, resample and decide.

Confirmatory vs exploratory (do not blur this line):

* Spec v1/v2 gross/execution views (``overall``/``state``/``regime``, other
  horizons/exchanges/sizes, ``positive_oos_gate_count``) remain exploratory.
  Nothing in this module reads or is read by those views.
* Spec v3 adds exactly ONE confirmatory primary hypothesis: one symbol, one
  horizon, one sampling mode (``utc_nonoverlap`` only), one exchange, one
  size. The ``ConfirmatoryContract`` shape enforces this structurally --
  every ``primary_*`` field is a scalar, so there is no way to express more
  than one primary hypothesis in this shape.

Baseline (``block_unconditional_direction_matched_baseline_v1``): the mean of
PR5's already-persisted, direction-agnostic ``signal_outcome.market_return_pct``
(see ``app.signal_outcomes.compute_path_metrics``) across every compatible
periodic *evaluated* observation in the same calendar block -- not merely the
signal's own row, and not restricted to actionable/long/short rows. This is a
real control: it is unconditional on the primary signal ever having fired at
all in that block, and is deliberately frictionless (no trading costs applied
to it), which makes comparing an actionable signal's modeled, cost-aware
return against it a conservative test. PR11 (``app.signal_walk_forward``)
computes the per-block mean from plain caller-supplied ``market_return_pct``
values and passes it here only to be sign-matched to one primary row's own
``direction`` (``+mean`` for ``long``, ``-mean`` for ``short``) -- this module
never recomputes the mean itself and never reads a bar. It is NEVER recomputed
from raw OHLCV bars -- PR11/PR26 read PR4-PR10's immutable output only, they
never re-derive it.

Block bootstrap (``block_bootstrap_v1``): rows are pre-grouped by caller into
whole, non-overlapping, epoch-anchored calendar blocks
(``confirmatory_block_key``) before any resampling happens. The resampler
(``block_bootstrap_v1``) only ever indexes a pre-built ``dict[str,
list[float]]`` and extends a pooled list with an entire block's values at
once -- there is no code path that can draw or drop an individual row inside
a block, so "a block never gets split across a resample" is a structural
property of the data shape consumed here, not merely a tested convention.
Resampling uses exactly one ``random.Random(seed)`` instance, created once
and advanced sequentially across every repetition, so a frozen seed always
reproduces the identical sequence of bootstrap means.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from typing import Any

from app.signal_execution import EXECUTION_EXCHANGES, EXECUTION_SIZES_USD, UTC_NONOVERLAP
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES

# ---------------------------------------------------------------------------
# Versions and fixed research policy. Every constant below is additive: it
# never changes the meaning of an already-frozen spec v1 or v2 manifest, and
# a future v4+ contract must define its OWN new constants rather than
# reinterpreting these.
# ---------------------------------------------------------------------------

CONFIRMATORY_PRIMARY_ENDPOINT_VERSION = 1
CONFIRMATORY_PRIMARY_ENDPOINT_NAME = (
    "measured_entry_modeled_exit_net_of_fees_stress_and_baseline_excess_v1"
)

BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION = 1
BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_NAME = (
    "block_unconditional_direction_matched_baseline_v1"
)

BLOCK_BOOTSTRAP_INFERENCE_VERSION = 1
BLOCK_BOOTSTRAP_INFERENCE_NAME = "block_bootstrap_v1"

CONFIRMATORY_DECISION_POLICY_V1 = "two_sided_block_bootstrap_ci_vs_minimum_effect_v1"

CONFIRMATORY_BLOCK_UNITS = ("hour", "day")
_BLOCK_UNIT_SECONDS = {"hour": 3600, "day": 86400}

CONFIRMATORY_STATE_NOT_READY = "not_ready"
CONFIRMATORY_STATE_PASS = "pass"
CONFIRMATORY_STATE_FAIL = "fail"
CONFIRMATORY_STATE_INCONCLUSIVE = "inconclusive"
CONFIRMATORY_STATES = (
    CONFIRMATORY_STATE_NOT_READY,
    CONFIRMATORY_STATE_PASS,
    CONFIRMATORY_STATE_FAIL,
    CONFIRMATORY_STATE_INCONCLUSIVE,
)

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ConfirmatoryContract:
    """PR26 spec v3's fully hashed confirmatory contract.

    Every field is caller-required: this dataclass has no default values, so
    a caller cannot construct one without supplying every field explicitly.
    No field may ever be silently derived from a "current/live" constant --
    see ``validate_confirmatory_contract`` for the fail-closed checks.
    """

    primary_endpoint_version: int
    primary_symbol: str
    primary_horizon_minutes: int
    primary_sampling_mode: str
    primary_exchange: str
    primary_size_usd: float
    primary_taker_fee_bps: float
    baseline_version: int
    unmodeled_execution_stress_bps: float
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
    confirmatory_decision_policy: str


_CONFIRMATORY_CONTRACT_FIELDS = tuple(field.name for field in fields(ConfirmatoryContract))


def confirmatory_contract_to_dict(contract: ConfirmatoryContract) -> dict[str, Any]:
    return {name: getattr(contract, name) for name in _CONFIRMATORY_CONTRACT_FIELDS}


def confirmatory_contract_from_dict(data: dict[str, Any]) -> ConfirmatoryContract:
    """Fail closed on any unknown OR missing key -- the key set must match
    ``ConfirmatoryContract``'s fields exactly, never a superset or subset."""

    if not isinstance(data, dict) or set(data) != set(_CONFIRMATORY_CONTRACT_FIELDS):
        raise ValueError(
            "confirmatory_contract has unknown or missing fields; expected exactly "
            f"{sorted(_CONFIRMATORY_CONTRACT_FIELDS)}"
        )
    return ConfirmatoryContract(
        primary_endpoint_version=int(data["primary_endpoint_version"]),
        primary_symbol=str(data["primary_symbol"]),
        primary_horizon_minutes=int(data["primary_horizon_minutes"]),
        primary_sampling_mode=str(data["primary_sampling_mode"]),
        primary_exchange=str(data["primary_exchange"]),
        primary_size_usd=float(data["primary_size_usd"]),
        primary_taker_fee_bps=float(data["primary_taker_fee_bps"]),
        baseline_version=int(data["baseline_version"]),
        unmodeled_execution_stress_bps=float(data["unmodeled_execution_stress_bps"]),
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
        confirmatory_decision_policy=str(data["confirmatory_decision_policy"]),
    )


def validate_confirmatory_contract(
    contract: ConfirmatoryContract,
    *,
    symbols: tuple[str, ...],
    horizons: tuple[int, ...],
    sampling_modes: tuple[str, ...],
    exchanges: tuple[str, ...],
    sizes_usd: tuple[float, ...],
    fee_bps_per_side: tuple[tuple[str, float], ...],
) -> None:
    """Fail closed on any confirmatory field that is missing, out of range,
    inconsistent with the frozen version literals, or inconsistent with the
    manifest's own (already-validated) plural option fields.

    No bound here expresses a "recommended" scientific value -- only
    structural/type validity. Choosing what counts as economically relevant
    (``minimum_effect_bps``), how much stress to model
    (``unmodeled_execution_stress_bps``), how many repetitions/blocks are
    enough, etc. is deliberately left to the operator who freezes a future
    manifest; this PR must not bake in an opinion.
    """

    for int_field in (
        "block_length",
        "bootstrap_repetitions",
        "bootstrap_seed",
        "minimum_primary_blocks",
    ):
        value = getattr(contract, int_field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"confirmatory {int_field} must be an int")

    if contract.primary_endpoint_version != CONFIRMATORY_PRIMARY_ENDPOINT_VERSION:
        raise ValueError(
            "confirmatory primary_endpoint_version="
            f"{contract.primary_endpoint_version!r} is not "
            f"{CONFIRMATORY_PRIMARY_ENDPOINT_VERSION!r}"
        )

    if not contract.primary_symbol.strip():
        raise ValueError("confirmatory primary_symbol must be non-empty")
    if symbols and contract.primary_symbol not in symbols:
        raise ValueError(
            "confirmatory primary_symbol must be one of the manifest's symbols"
        )

    if contract.primary_horizon_minutes not in OUTCOME_HORIZONS_MINUTES:
        raise ValueError("confirmatory primary_horizon_minutes is not a supported horizon")
    if contract.primary_horizon_minutes not in horizons:
        raise ValueError(
            "confirmatory primary_horizon_minutes must be one of the manifest's horizons"
        )

    if contract.primary_sampling_mode != UTC_NONOVERLAP:
        raise ValueError(
            "confirmatory primary_sampling_mode must be "
            f"{UTC_NONOVERLAP!r}; dense_periodic is descriptive only"
        )
    if contract.primary_sampling_mode not in sampling_modes:
        raise ValueError(
            "confirmatory primary_sampling_mode must be one of the manifest's sampling modes"
        )

    if contract.primary_exchange not in EXECUTION_EXCHANGES:
        raise ValueError("confirmatory primary_exchange is not a supported exchange")
    if contract.primary_exchange not in exchanges:
        raise ValueError(
            "confirmatory primary_exchange must be one of the manifest's exchanges"
        )

    if contract.primary_size_usd not in EXECUTION_SIZES_USD:
        raise ValueError("confirmatory primary_size_usd is not a supported execution size")
    if contract.primary_size_usd not in sizes_usd:
        raise ValueError(
            "confirmatory primary_size_usd must be one of the manifest's execution sizes"
        )

    if not math.isfinite(contract.primary_taker_fee_bps) or not (
        0.0 <= contract.primary_taker_fee_bps <= 100.0
    ):
        raise ValueError("confirmatory primary_taker_fee_bps must be finite and between 0 and 100")
    frozen_fee = dict(fee_bps_per_side).get(contract.primary_exchange)
    if frozen_fee != contract.primary_taker_fee_bps:
        raise ValueError(
            "confirmatory primary_taker_fee_bps must equal the manifest's frozen "
            "fee_bps_per_side for primary_exchange -- no divergence between the fee "
            "actually applied and the fee the contract claims"
        )

    if contract.baseline_version != BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION:
        raise ValueError(
            f"confirmatory baseline_version={contract.baseline_version!r} is not "
            f"{BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION!r}"
        )

    if not math.isfinite(contract.unmodeled_execution_stress_bps) or (
        contract.unmodeled_execution_stress_bps < 0.0
    ):
        raise ValueError("confirmatory unmodeled_execution_stress_bps must be finite and >= 0")

    if contract.inference_version != BLOCK_BOOTSTRAP_INFERENCE_VERSION:
        raise ValueError(
            f"confirmatory inference_version={contract.inference_version!r} is not "
            f"{BLOCK_BOOTSTRAP_INFERENCE_VERSION!r}"
        )

    if contract.block_unit not in CONFIRMATORY_BLOCK_UNITS:
        raise ValueError(f"confirmatory block_unit must be one of {CONFIRMATORY_BLOCK_UNITS}")
    if contract.block_length < 1:
        raise ValueError("confirmatory block_length must be >= 1")

    if contract.bootstrap_repetitions < 2:
        # A single repetition cannot produce a percentile CI with any actual
        # spread -- structurally degenerate, never a real calibration value.
        raise ValueError("confirmatory bootstrap_repetitions must be >= 2")

    if not 0.0 < contract.confidence_level < 1.0:
        raise ValueError("confirmatory confidence_level must be between 0 and 1 exclusive")

    if not math.isfinite(contract.minimum_effect_bps):
        raise ValueError("confirmatory minimum_effect_bps must be finite")
    if contract.minimum_effect_bps < 0.0:
        # A negative threshold would let a partially- or wholly-negative CI
        # pass; economically-relevant effect sizes are never negative.
        raise ValueError("confirmatory minimum_effect_bps must be >= 0")

    if contract.minimum_primary_blocks < 2:
        # A single block can never be whole-block bootstrapped into a
        # non-degenerate resample (every repetition would just redraw the
        # same one block) -- structurally degenerate, never a real
        # calibration value.
        raise ValueError("confirmatory minimum_primary_blocks must be >= 2")

    if not 0.0 < contract.minimum_execution_data_coverage_pct <= 100.0:
        raise ValueError(
            "confirmatory minimum_execution_data_coverage_pct must be > 0 and <= 100"
        )

    if not 0.0 < contract.minimum_research_data_coverage_pct <= 100.0:
        raise ValueError(
            "confirmatory minimum_research_data_coverage_pct must be > 0 and <= 100"
        )

    if contract.confirmatory_decision_policy != CONFIRMATORY_DECISION_POLICY_V1:
        raise ValueError(
            "confirmatory confirmatory_decision_policy="
            f"{contract.confirmatory_decision_policy!r} is not "
            f"{CONFIRMATORY_DECISION_POLICY_V1!r}"
        )


def block_unconditional_direction_matched_baseline_bps(
    block_unconditional_market_mean_bps: float,
    *,
    direction: str,
) -> float:
    """``block_unconditional_direction_matched_baseline_v1``.

    Sign-matches an already-computed, per-block, direction-*agnostic* control
    mean (``mean(market_return_pct * 100)`` over ALL compatible periodic
    evaluated observations in one calendar block -- see
    ``app.signal_walk_forward._compute_confirmatory_result``, which owns that
    aggregation) to one primary row's own stated ``direction``: a "long" row
    is compared against the block's unconditional market drift as-is (a
    bullish block should look easy for a long signal to beat); a "short" row
    is compared against the negated drift (a bearish block should look easy
    for a short signal to beat). This function performs only that sign
    matching -- it never computes the block mean itself, never restricts
    which rows fed into it, and never reads a bar.
    """

    if direction == "long":
        return block_unconditional_market_mean_bps
    if direction == "short":
        return -block_unconditional_market_mean_bps
    raise ValueError(f"unsupported confirmatory baseline direction: {direction!r}")


def confirmatory_block_key(observed_minute: datetime, *, block_unit: str, block_length: int) -> str:
    """Deterministic, epoch-anchored calendar bucket for one row.

    A pure function of ``(observed_minute, block_unit, block_length)`` only
    -- it never reads a wall clock and is independent of fold boundaries, so
    the exact same row always maps to the exact same block key regardless of
    when this function is called.
    """

    if block_unit not in CONFIRMATORY_BLOCK_UNITS:
        raise ValueError(f"unsupported confirmatory block_unit: {block_unit!r}")
    if block_length < 1:
        raise ValueError("confirmatory block_length must be >= 1")
    if observed_minute.tzinfo is None or observed_minute.utcoffset() is None:
        raise ValueError("observed_minute must be timezone-aware")

    aware = observed_minute.astimezone(UTC)
    bucket_seconds = _BLOCK_UNIT_SECONDS[block_unit] * block_length
    elapsed_seconds = (aware - _EPOCH).total_seconds()
    bucket_index = math.floor(elapsed_seconds / bucket_seconds)
    return f"{block_unit}:{block_length}:{bucket_index}"


def block_bootstrap_v1(
    block_values: dict[str, list[float]],
    *,
    repetitions: int,
    seed: int,
) -> list[float]:
    """``block_bootstrap_v1``: deterministic ordinary block bootstrap.

    Resamples whole calendar blocks (never raw rows) with replacement,
    drawing ``len(block_values)`` blocks per repetition, ``repetitions``
    times, using a single ``random.Random(seed)`` instance created here and
    advanced sequentially -- never reseeded mid-run, never falling back to
    the global ``random`` module. Two calls with the same ``block_values``
    and ``seed`` always return the identical list.

    Every row inside a drawn block is copied into the pooled sample as a
    unit (``pooled.extend(block_values[key])``) -- there is no code path
    that can select a subset of a block's rows.
    """

    if repetitions < 1:
        raise ValueError("bootstrap repetitions must be >= 1")
    keys = sorted(block_values)
    if not keys:
        raise ValueError("block bootstrap requires at least one non-empty block")
    for key in keys:
        if not block_values[key]:
            raise ValueError(f"block {key!r} has no values")

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(repetitions):
        drawn_keys = rng.choices(keys, k=len(keys))
        pooled: list[float] = []
        for key in drawn_keys:
            pooled.extend(block_values[key])
        means.append(statistics.fmean(pooled))
    return means


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def block_bootstrap_ci(
    bootstrap_means: list[float],
    *,
    confidence_level: float,
) -> tuple[float, float]:
    """Percentile-method confidence interval over bootstrap resample means."""

    if not bootstrap_means:
        raise ValueError("block bootstrap CI requires at least one bootstrap mean")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1 exclusive")

    alpha = 1.0 - confidence_level
    lower = _percentile(bootstrap_means, alpha / 2.0)
    upper = _percentile(bootstrap_means, 1.0 - alpha / 2.0)
    return lower, upper


def confirmatory_decision(
    *,
    lower_ci_bps: float,
    upper_ci_bps: float,
    minimum_effect_bps: float,
) -> str:
    """``two_sided_block_bootstrap_ci_vs_minimum_effect_v1``.

    Must only be called once coverage/minimum-block requirements are already
    known to be satisfied (an inadequate-precision/sample/coverage case is
    ``inconclusive`` by construction, before this function is ever reached --
    see ``app.signal_walk_forward._compute_confirmatory_result``).

    Defensive ordering: FAIL is checked before PASS. Combined with
    ``validate_confirmatory_contract`` requiring ``minimum_effect_bps >= 0``,
    a wholly non-positive CI (``upper_ci_bps <= 0.0``) can never reach the
    PASS branch even if that validation were ever bypassed -- ``lower_ci_bps
    <= upper_ci_bps <= 0.0`` can only satisfy ``lower_ci_bps >
    minimum_effect_bps`` for a negative ``minimum_effect_bps``, and checking
    FAIL first forecloses that path regardless.
    """

    if upper_ci_bps <= 0.0:
        return CONFIRMATORY_STATE_FAIL
    if lower_ci_bps > minimum_effect_bps:
        return CONFIRMATORY_STATE_PASS
    return CONFIRMATORY_STATE_INCONCLUSIVE
