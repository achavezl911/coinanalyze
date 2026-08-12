from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

from app.signal_execution import (
    DENSE_PERIODIC,
    EXECUTION_EXCHANGES,
    EXECUTION_SIZES_USD,
    EXECUTION_SNAPSHOT_VERSION,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
)
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION
from app.signal_visibility import RESEARCH_VISIBILITY_VERSION

# ---------------------------------------------------------------------------
# Versions and fixed research policy.
#
# PR11 is a walk-forward / out-of-sample evaluation engine layered on top of
# the immutable PR4-PR10 research corpus. It never recomputes PR4-PR10
# results and never changes live scoring.
#
# PR25 adds a SECOND, explicit spec version (2) for the corrected,
# certificate-gated knowledge-time contract (A3-01). Spec v1 is frozen
# forever at its historical behavior: this file must never reinterpret an
# existing v1 manifest, never add a field to its hashed spec, and never
# change its hash. Spec v2 is additive: it requires the PR25 research
# visibility contract and a fully explicit scientific version tuple. No
# spec-v2 production manifest is created by this PR.
# ---------------------------------------------------------------------------

WALK_FORWARD_MANIFEST_VERSION = 1
WALK_FORWARD_SPEC_VERSION = 1
WALK_FORWARD_REPORT_VERSION = 1

WALK_FORWARD_SPEC_VERSION_V2 = 2
WALK_FORWARD_REPORT_VERSION_V2 = 2
SUPPORTED_WALK_FORWARD_SPEC_VERSIONS = (
    WALK_FORWARD_SPEC_VERSION,
    WALK_FORWARD_SPEC_VERSION_V2,
)

# The only supported prospective spec-v2 scientific version tuple for PR25.
# validate_manifest_options() fails closed unless every one of these values
# is supplied exactly -- there is no "latest/current" fallback and spec v1 is
# never silently mapped onto this tuple.
SPEC_V2_SUPPORTED_EVIDENCE_VERSION = 6
SPEC_V2_SUPPORTED_SAMPLING_VERSION = 1
SPEC_V2_SUPPORTED_CONTEXT_VERSION = REPLAY_CONTEXT_VERSION
SPEC_V2_SUPPORTED_OUTCOME_VERSION = OUTCOME_VERSION
SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION = EXECUTION_SNAPSHOT_VERSION
SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION = RESEARCH_VISIBILITY_VERSION

SELECTION_POLICY = "fixed_kernel_no_selection_v1"

DEFAULT_MANIFEST_NAME = "pr11-fixed-kernel-v1"
DEFAULT_WARMUP_DAYS = 7
DEFAULT_TEST_DAYS = 7
DEFAULT_FOLD_COUNT = 4
DEFAULT_MIN_GROUP_N = 30

GROSS_VIEWS = ("overall", "state", "regime")

# Kept explicit (like app/signal_execution.py) to avoid an import cycle with
# app/signal_ledger.py.
DEFAULT_EVIDENCE_VERSION = 1
DEFAULT_SAMPLING_VERSION = 1

_NAME_PATTERN_MSG = (
    "manifest name must match ^[a-z][a-z0-9_-]{0,63}$ (safe identifier characters only)"
)


def _valid_manifest_name(name: str) -> bool:
    if not name or not (1 <= len(name) <= 64):
        return False
    if not (name[0].isalpha() and name[0].islower()):
        return False
    return all(ch.islower() or ch.isdigit() or ch in "_-" for ch in name)


@dataclass(frozen=True, slots=True)
class WalkForwardManifestOptions:
    name: str = DEFAULT_MANIFEST_NAME
    warmup_days: int = DEFAULT_WARMUP_DAYS
    test_days: int = DEFAULT_TEST_DAYS
    fold_count: int = DEFAULT_FOLD_COUNT
    min_group_n: int = DEFAULT_MIN_GROUP_N
    horizons: tuple[int, ...] = OUTCOME_HORIZONS_MINUTES
    sampling_modes: tuple[str, ...] = SAMPLING_MODES
    symbols: tuple[str, ...] = ()
    exchanges: tuple[str, ...] = EXECUTION_EXCHANGES
    sizes_usd: tuple[float, ...] = EXECUTION_SIZES_USD
    fee_bps_per_side: tuple[tuple[str, float], ...] = ()
    logic_version: str = SCALP_SIGNAL_LOGIC_VERSION
    evidence_version: int = DEFAULT_EVIDENCE_VERSION
    sampling_version: int = DEFAULT_SAMPLING_VERSION
    context_version: int = REPLAY_CONTEXT_VERSION
    outcome_version: int = OUTCOME_VERSION
    execution_snapshot_version: int = EXECUTION_SNAPSHOT_VERSION
    spec_version: int = WALK_FORWARD_SPEC_VERSION
    research_visibility_version: int | None = None


def validate_manifest_options(options: WalkForwardManifestOptions) -> None:
    """Fail closed on any invalid or out-of-contract manifest option.

    No CLI option here can request a retroactive cutoff: the cutoff is always
    derived from the PostgreSQL clock at freeze time plus ``warmup_days``,
    never accepted as a caller-supplied timestamp.

    Spec v1 keeps its exact historical validation. Spec v2 additionally
    requires the exact PR25 supported prospective scientific version tuple,
    explicitly supplied -- never inferred, never defaulted, never mapped
    from spec v1.
    """

    if options.spec_version not in SUPPORTED_WALK_FORWARD_SPEC_VERSIONS:
        raise ValueError(f"unsupported walk-forward spec_version: {options.spec_version}")

    if not _valid_manifest_name(options.name):
        raise ValueError(_NAME_PATTERN_MSG)
    if not 1 <= options.warmup_days <= 3650:
        raise ValueError("warmup_days must be between 1 and 3650")
    if not 1 <= options.test_days <= 3650:
        raise ValueError("test_days must be between 1 and 3650")
    if not 1 <= options.fold_count <= 52:
        raise ValueError("fold_count must be between 1 and 52")
    if not 1 <= options.min_group_n <= 1_000_000:
        raise ValueError("min_group_n must be between 1 and 1000000")

    if options.logic_version != SCALP_SIGNAL_LOGIC_VERSION:
        raise ValueError(
            "unsupported walk-forward logic_version; register a version-specific kernel"
        )

    for label, value in (
        ("evidence_version", options.evidence_version),
        ("sampling_version", options.sampling_version),
        ("context_version", options.context_version),
        ("outcome_version", options.outcome_version),
        ("execution_snapshot_version", options.execution_snapshot_version),
    ):
        if value <= 0:
            raise ValueError(f"{label} must be positive")

    if options.spec_version == WALK_FORWARD_SPEC_VERSION:
        if options.research_visibility_version is not None:
            raise ValueError(
                "walk-forward spec v1 must not set research_visibility_version"
            )
    else:
        required_tuple = (
            ("evidence_version", options.evidence_version, SPEC_V2_SUPPORTED_EVIDENCE_VERSION),
            ("sampling_version", options.sampling_version, SPEC_V2_SUPPORTED_SAMPLING_VERSION),
            ("context_version", options.context_version, SPEC_V2_SUPPORTED_CONTEXT_VERSION),
            ("outcome_version", options.outcome_version, SPEC_V2_SUPPORTED_OUTCOME_VERSION),
            (
                "execution_snapshot_version",
                options.execution_snapshot_version,
                SPEC_V2_SUPPORTED_EXECUTION_SNAPSHOT_VERSION,
            ),
            (
                "research_visibility_version",
                options.research_visibility_version,
                SPEC_V2_SUPPORTED_RESEARCH_VISIBILITY_VERSION,
            ),
        )
        for label, actual, expected in required_tuple:
            if actual != expected:
                raise ValueError(
                    "walk-forward spec v2 requires the exact supported prospective "
                    f"scientific version tuple; {label}={actual!r} is not {expected!r}"
                )

    if not options.horizons:
        raise ValueError("at least one horizon is required")
    if len(set(options.horizons)) != len(options.horizons):
        raise ValueError("duplicate horizons are not allowed")
    unsupported_horizons = sorted(set(options.horizons) - set(OUTCOME_HORIZONS_MINUTES))
    if unsupported_horizons:
        raise ValueError(f"unsupported horizons: {unsupported_horizons}")

    if len(set(options.symbols)) != len(options.symbols):
        raise ValueError("duplicate symbols are not allowed")
    if any(not symbol.strip() for symbol in options.symbols):
        raise ValueError("symbols must be non-empty")

    if not options.sampling_modes:
        raise ValueError("at least one sampling mode is required")
    if len(set(options.sampling_modes)) != len(options.sampling_modes):
        raise ValueError("duplicate sampling modes are not allowed")
    unsupported_modes = sorted(set(options.sampling_modes) - set(SAMPLING_MODES))
    if unsupported_modes:
        raise ValueError(f"unsupported sampling modes: {unsupported_modes}")

    if not options.exchanges:
        raise ValueError("at least one execution exchange is required")
    if len(set(options.exchanges)) != len(options.exchanges):
        raise ValueError("duplicate execution exchanges are not allowed")
    unsupported_exchanges = sorted(set(options.exchanges) - set(EXECUTION_EXCHANGES))
    if unsupported_exchanges:
        raise ValueError(f"unsupported execution exchanges: {unsupported_exchanges}")

    if not options.sizes_usd:
        raise ValueError("at least one execution size is required")
    if len(set(options.sizes_usd)) != len(options.sizes_usd):
        raise ValueError("duplicate execution sizes are not allowed")
    unsupported_sizes = sorted(set(options.sizes_usd) - set(EXECUTION_SIZES_USD))
    if unsupported_sizes:
        raise ValueError(
            "unsupported execution sizes for snapshot version "
            f"{EXECUTION_SNAPSHOT_VERSION}: {unsupported_sizes}"
        )

    fee_exchanges = [exchange for exchange, _ in options.fee_bps_per_side]
    if len(set(fee_exchanges)) != len(fee_exchanges):
        raise ValueError("duplicate exchange fee inputs are not allowed")
    unsupported_fee_exchanges = sorted(set(fee_exchanges) - set(EXECUTION_EXCHANGES))
    if unsupported_fee_exchanges:
        raise ValueError(f"unsupported exchange fee inputs: {unsupported_fee_exchanges}")
    for exchange, fee in options.fee_bps_per_side:
        if not math.isfinite(fee) or not 0 <= fee <= 100:
            raise ValueError(
                f"fee_bps_per_side for {exchange} must be finite and between 0 and 100"
            )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
    )


def _spec_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(spec).encode("utf-8")).hexdigest()


def _next_minute_strictly_after(value: datetime) -> datetime:
    truncated = value.replace(second=0, microsecond=0)
    return truncated + timedelta(minutes=1)


def compute_folds(
    *,
    discovery_start: datetime,
    cutoff_at: datetime,
    test_days: int,
    fold_count: int,
    horizons: tuple[int, ...],
) -> list[dict[str, Any]]:
    """Freeze expanding-discovery / contiguous-non-overlapping-test folds.

    Fold 1: [discovery_start, cutoff_1) -> [cutoff_1, cutoff_1 + test_days).
    Fold N: [discovery_start, cutoff_N) -> [cutoff_N, cutoff_N + test_days)
    where cutoff_N = fold(N-1).test_end.
    """

    max_horizon = max(horizons)
    folds: list[dict[str, Any]] = []
    test_start = cutoff_at
    for index in range(1, fold_count + 1):
        discovery_end = test_start
        test_end = test_start + timedelta(days=test_days)
        test_maturity_at = test_end + timedelta(minutes=max_horizon) + OUTCOME_SETTLEMENT_LAG
        folds.append(
            {
                "fold_index": index,
                "discovery_start": discovery_start,
                "discovery_end": discovery_end,
                "test_start": test_start,
                "test_end": test_end,
                "test_maturity_at": test_maturity_at,
            }
        )
        test_start = test_end
    return folds


def _static_options_spec(options: WalkForwardManifestOptions) -> dict[str, Any]:
    """The caller-controlled configuration portion of the manifest spec.

    Deliberately excludes server-computed, time-dependent fields
    (``created_at``, ``discovery_start``, ``cutoff_at``, ``folds``) so a
    repeated freeze call with the same name and the same *static* spec can be
    recognized as idempotent regardless of how much wall-clock time passed
    between calls.
    """

    versions: dict[str, Any] = {
        "logic_version": options.logic_version,
        "evidence_version": options.evidence_version,
        "sampling_version": options.sampling_version,
        "context_version": options.context_version,
        "outcome_version": options.outcome_version,
        "execution_snapshot_version": options.execution_snapshot_version,
    }
    # Spec v1's hashed shape must stay byte-for-byte what it always was: no
    # new key is ever added here for spec_version == WALK_FORWARD_SPEC_VERSION.
    if options.spec_version != WALK_FORWARD_SPEC_VERSION:
        versions["research_visibility_version"] = options.research_visibility_version

    return {
        "spec_version": options.spec_version,
        "manifest_version": WALK_FORWARD_MANIFEST_VERSION,
        "warmup_days": options.warmup_days,
        "test_days": options.test_days,
        "fold_count": options.fold_count,
        "min_group_n": options.min_group_n,
        "selection_policy": SELECTION_POLICY,
        "horizons_minutes": sorted(options.horizons),
        "symbols": sorted(options.symbols),
        "sampling_modes": sorted(options.sampling_modes),
        "gross_views": sorted(GROSS_VIEWS),
        "execution_exchanges": sorted(options.exchanges),
        "execution_sizes_usd": sorted(options.sizes_usd),
        "fee_bps_per_side": dict(sorted(options.fee_bps_per_side)),
        "outcome_settlement_lag_seconds": OUTCOME_SETTLEMENT_LAG.total_seconds(),
        "versions": versions,
    }


def _full_spec(
    options: WalkForwardManifestOptions,
    *,
    created_at: datetime,
    discovery_start: datetime,
    cutoff_at: datetime,
    folds: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **_static_options_spec(options),
        "name": options.name,
        "created_at": created_at,
        "discovery_start": discovery_start,
        "cutoff_at": cutoff_at,
        "folds": folds,
    }


def _load_spec(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict):
        return raw
    raise ValueError("stored manifest spec is not a JSON object")


def _manifest_record(row: asyncpg.Record | dict[str, Any], *, reused_existing: bool) -> dict[str, Any]:
    data = dict(row)
    spec = _load_spec(data["spec"])
    return {
        "manifest_id": data["manifest_id"],
        "manifest_version": data["manifest_version"],
        "manifest_name": data["manifest_name"],
        "created_at": data["created_at"],
        "cutoff_at": data["cutoff_at"],
        "warmup_days": data["warmup_days"],
        "test_days": data["test_days"],
        "fold_count": data["fold_count"],
        "min_group_n": data["min_group_n"],
        "selection_policy": data["selection_policy"],
        "manifest_hash": data["manifest_hash"],
        "spec": spec,
        "folds": spec.get("folds", []),
        "reused_existing": reused_existing,
    }


async def _fetch_discovery_start(
    conn: asyncpg.Connection,
    options: WalkForwardManifestOptions,
) -> datetime | None:
    """Earliest compatible periodic observation with a replay frame.

    Freeze may read only: the PostgreSQL clock, the earliest compatible
    periodic ``signal_observation`` and its matching ``signal_replay_frame``
    version. It must never read ``signal_outcome`` or any PR7-PR10
    performance table.
    """

    value = await conn.fetchval(
        """
        SELECT MIN(obs.observed_at)
        FROM signal_observation AS obs
        JOIN signal_replay_frame AS frame
          ON frame.observation_id = obs.observation_id
        WHERE obs.signal_family='scalp'
          AND obs.is_periodic
          AND obs.logic_version=$1
          AND obs.evidence_version=$2
          AND obs.sampling_version=$3
          AND frame.context_version=$4
          AND (
            cardinality($5::text[]) = 0
            OR obs.symbol = ANY($5::text[])
          )
        """,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
    )
    if value is None:
        return None
    return _aware_utc(value)


async def freeze_walk_forward_manifest(
    conn: asyncpg.Connection,
    options: WalkForwardManifestOptions | None = None,
) -> dict[str, Any]:
    """Stage A (Freeze): create or idempotently reuse an immutable manifest.

    Freeze reads only the PostgreSQL clock, the earliest compatible periodic
    observation and its replay-frame version. It never reads
    ``signal_outcome`` or any PR7-PR10 performance table, and it never
    accepts a caller-supplied retroactive cutoff.
    """

    opts = options or WalkForwardManifestOptions()
    validate_manifest_options(opts)
    static_spec = _static_options_spec(opts)

    existing = await conn.fetchrow(
        "SELECT * FROM signal_walk_forward_manifest WHERE manifest_name=$1",
        opts.name,
    )
    if existing is not None:
        return _reuse_or_fail(existing, static_spec, opts.name)

    created_at = _aware_utc(await conn.fetchval("SELECT clock_timestamp()"))
    cutoff_at = _next_minute_strictly_after(created_at + timedelta(days=opts.warmup_days))
    discovery_start = await _fetch_discovery_start(conn, opts)
    if discovery_start is None or discovery_start >= cutoff_at:
        discovery_start = created_at

    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=opts.test_days,
        fold_count=opts.fold_count,
        horizons=opts.horizons,
    )
    spec = _full_spec(
        opts,
        created_at=created_at,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        folds=folds,
    )
    manifest_hash = _spec_hash(spec)

    row = await conn.fetchrow(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version, manifest_name, created_at, cutoff_at, warmup_days,
          test_days, fold_count, min_group_n, selection_policy, manifest_hash, spec
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)
        ON CONFLICT (manifest_name) DO NOTHING
        RETURNING *
        """,
        WALK_FORWARD_MANIFEST_VERSION,
        opts.name,
        created_at,
        cutoff_at,
        opts.warmup_days,
        opts.test_days,
        opts.fold_count,
        opts.min_group_n,
        SELECTION_POLICY,
        manifest_hash,
        _canonical_json(spec),
    )
    if row is None:
        # Lost a concurrent freeze race; fall back to the idempotent path.
        existing = await conn.fetchrow(
            "SELECT * FROM signal_walk_forward_manifest WHERE manifest_name=$1",
            opts.name,
        )
        if existing is None:
            raise RuntimeError("walk-forward manifest freeze race left no row")
        return _reuse_or_fail(existing, static_spec, opts.name)

    return _manifest_record(row, reused_existing=False)


def _options_from_spec(
    manifest_name: str,
    spec: dict[str, Any],
) -> WalkForwardManifestOptions:
    versions = spec.get("versions")
    if not isinstance(versions, dict):
        raise ValueError("walk-forward manifest versions are missing")

    fees = spec.get("fee_bps_per_side", {})
    if not isinstance(fees, dict):
        raise ValueError("walk-forward manifest fee_bps_per_side must be an object")

    spec_version = int(spec.get("spec_version", 0))
    if spec_version not in SUPPORTED_WALK_FORWARD_SPEC_VERSIONS:
        raise ValueError(f"unsupported stored walk-forward spec_version: {spec_version}")

    research_visibility_version: int | None = None
    if spec_version != WALK_FORWARD_SPEC_VERSION:
        raw_research_visibility_version = versions.get("research_visibility_version")
        if raw_research_visibility_version is None:
            raise ValueError(
                "walk-forward manifest spec v2 is missing research_visibility_version"
            )
        research_visibility_version = int(raw_research_visibility_version)

    options = WalkForwardManifestOptions(
        name=manifest_name,
        warmup_days=int(spec["warmup_days"]),
        test_days=int(spec["test_days"]),
        fold_count=int(spec["fold_count"]),
        min_group_n=int(spec["min_group_n"]),
        horizons=tuple(int(value) for value in spec["horizons_minutes"]),
        sampling_modes=tuple(str(value) for value in spec["sampling_modes"]),
        symbols=tuple(str(value) for value in spec["symbols"]),
        exchanges=tuple(str(value) for value in spec["execution_exchanges"]),
        sizes_usd=tuple(float(value) for value in spec["execution_sizes_usd"]),
        fee_bps_per_side=tuple(
            sorted((str(exchange), float(fee)) for exchange, fee in fees.items())
        ),
        logic_version=str(versions["logic_version"]),
        evidence_version=int(versions["evidence_version"]),
        sampling_version=int(versions["sampling_version"]),
        context_version=int(versions["context_version"]),
        outcome_version=int(versions["outcome_version"]),
        execution_snapshot_version=int(versions["execution_snapshot_version"]),
        spec_version=spec_version,
        research_visibility_version=research_visibility_version,
    )
    validate_manifest_options(options)
    return options


def _parse_spec_timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    if not isinstance(value, str):
        raise ValueError(f"walk-forward manifest {field} must be an ISO timestamp")
    return _aware_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _validate_manifest_row(
    row: asyncpg.Record | dict[str, Any],
) -> tuple[dict[str, Any], WalkForwardManifestOptions]:
    data = dict(row)
    spec = _load_spec(data["spec"])

    recomputed_hash = _spec_hash(spec)
    if recomputed_hash != data["manifest_hash"]:
        raise ValueError(
            f"walk-forward manifest {data['manifest_name']!r} failed hash "
            "verification (tamper or corruption)"
        )

    if int(data["manifest_version"]) != WALK_FORWARD_MANIFEST_VERSION:
        raise ValueError("unsupported stored walk-forward manifest_version")
    stored_spec_version = int(spec.get("spec_version", 0))
    if stored_spec_version not in SUPPORTED_WALK_FORWARD_SPEC_VERSIONS:
        raise ValueError(f"unsupported stored walk-forward spec_version: {stored_spec_version}")
    if int(spec.get("manifest_version", 0)) != WALK_FORWARD_MANIFEST_VERSION:
        raise ValueError("manifest JSON version disagrees with table row")
    if spec.get("name") != data["manifest_name"]:
        raise ValueError("manifest name disagrees with hashed spec")
    if spec.get("selection_policy") != SELECTION_POLICY:
        raise ValueError("unsupported stored walk-forward selection policy")
    if data["selection_policy"] != SELECTION_POLICY:
        raise ValueError("manifest row selection policy is not fixed-kernel")
    if sorted(spec.get("gross_views", [])) != sorted(GROSS_VIEWS):
        raise ValueError("manifest gross views differ from the frozen contract")

    options = _options_from_spec(str(data["manifest_name"]), spec)
    static_expected = _static_options_spec(options)
    stored_static = {key: spec.get(key) for key in static_expected}
    if stored_static != static_expected:
        raise ValueError("manifest static spec is internally inconsistent")

    created_at = _parse_spec_timestamp(spec.get("created_at"), "created_at")
    discovery_start = _parse_spec_timestamp(
        spec.get("discovery_start"),
        "discovery_start",
    )
    cutoff_at = _parse_spec_timestamp(spec.get("cutoff_at"), "cutoff_at")

    if _aware_utc(data["created_at"]) != created_at:
        raise ValueError("manifest created_at column disagrees with hashed spec")
    if _aware_utc(data["cutoff_at"]) != cutoff_at:
        raise ValueError("manifest cutoff_at column disagrees with hashed spec")
    if int(data["warmup_days"]) != options.warmup_days:
        raise ValueError("manifest warmup_days column disagrees with hashed spec")
    if int(data["test_days"]) != options.test_days:
        raise ValueError("manifest test_days column disagrees with hashed spec")
    if int(data["fold_count"]) != options.fold_count:
        raise ValueError("manifest fold_count column disagrees with hashed spec")
    if int(data["min_group_n"]) != options.min_group_n:
        raise ValueError("manifest min_group_n column disagrees with hashed spec")

    expected_cutoff = _next_minute_strictly_after(
        created_at + timedelta(days=options.warmup_days)
    )
    if cutoff_at != expected_cutoff:
        raise ValueError("manifest cutoff is not the frozen prospective cutoff")
    if not created_at < cutoff_at:
        raise ValueError("manifest cutoff must be after manifest creation")
    if not discovery_start < cutoff_at:
        raise ValueError("manifest discovery_start must be before first OOS cutoff")

    stored_lag = float(spec.get("outcome_settlement_lag_seconds", -1))
    expected_lag = OUTCOME_SETTLEMENT_LAG.total_seconds()
    if not math.isclose(stored_lag, expected_lag, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("manifest PR5 settlement-lag contract changed")

    expected_folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=options.test_days,
        fold_count=options.fold_count,
        horizons=options.horizons,
    )
    if _canonical_json(spec.get("folds")) != _canonical_json(expected_folds):
        raise ValueError("manifest fold schedule does not match its frozen spec")

    return spec, options


def _reuse_or_fail(
    existing_row: asyncpg.Record,
    static_spec: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    stored_spec, _ = _validate_manifest_row(existing_row)
    stored_static = {key: stored_spec.get(key) for key in static_spec}
    if stored_static != static_spec:
        raise ValueError(
            f"walk-forward manifest {name!r} already exists with a different "
            "static spec; freeze fails closed instead of mutating it"
        )
    return _manifest_record(existing_row, reused_existing=True)


async def load_walk_forward_manifest(
    conn: asyncpg.Connection,
    name: str,
) -> tuple[dict[str, Any], WalkForwardManifestOptions]:
    """Load, hash-verify and schedule-verify an immutable manifest."""

    row = await conn.fetchrow(
        "SELECT * FROM signal_walk_forward_manifest WHERE manifest_name=$1",
        name,
    )
    if row is None:
        raise ValueError(f"walk-forward manifest {name!r} does not exist")
    _, options = _validate_manifest_row(row)
    return _manifest_record(row, reused_existing=True), options


# ---------------------------------------------------------------------------
# Stage B (Evaluate). Strictly REPEATABLE READ READ ONLY: no model, config or
# live-scoring writes ever originate from this module.
# ---------------------------------------------------------------------------

FOLD_STATES = (
    "discovery_collecting",
    "test_collecting",
    "test_settling",
    "ready_by_clock",
    "outcome_recovery_pending",
    "integrity_blocked",
)

GENERALIZATION_LABELS = (
    "positive_generalization_observed",
    "failed_to_generalize",
    "oos_positive_without_discovery_edge",
    "non_positive_both",
    "not_ready",
    "insufficient_sample",
    "integrity_blocked",
)

EXECUTION_GENERALIZATION_LABELS = (
    "positive_market_cost_generalization_observed",
    "market_cost_edge_failed_to_generalize",
    "oos_market_cost_positive_without_discovery_edge",
    "non_positive_after_market_cost_both",
    "not_ready",
    "insufficient_execution_sample",
    "integrity_blocked",
)


def _clock_fold_state(fold: dict[str, Any], *, generated_at: datetime) -> str:
    if generated_at < fold["discovery_end"]:
        return "discovery_collecting"
    if generated_at < fold["test_end"]:
        return "test_collecting"
    if generated_at < fold["test_maturity_at"]:
        return "test_settling"
    return "ready_by_clock"


def _sample_grid(
    grid: list[dict[str, Any]],
    mode: str,
) -> list[dict[str, Any]]:
    if mode == DENSE_PERIODIC:
        return list(grid)
    if mode != UTC_NONOVERLAP:
        raise ValueError(f"unsupported sampling mode: {mode}")

    sampled: list[dict[str, Any]] = []
    for row in grid:
        observed_minute = row.get("observed_minute")
        horizon = int(row["horizon_minutes"])
        if not isinstance(observed_minute, datetime):
            raise ValueError("utc_nonoverlap requires observed_minute")
        minute_index = math.floor(_aware_utc(observed_minute).timestamp() / 60.0)
        if minute_index % horizon == 0:
            sampled.append(row)
    return sampled


_OUTCOME_FINAL_VALUE_FIELDS = (
    "end_price",
    "directional_return_pct",
    "mfe_pct",
    "mae_pct",
    "market_return_pct",
)

_OUTCOME_JOIN_FIELDS = (
    "outcome_version",
    "status",
    "window_end",
    "due_at",
    "outcome_created_at",
    "finalized_at",
    *_OUTCOME_FINAL_VALUE_FIELDS,
)


def _project_outcome_as_of(
    row: dict[str, Any], knowledge_cutoff: datetime
) -> dict[str, Any]:
    """Project one current PR5 row to what was knowable at a closed cutoff."""

    projected = dict(row)
    cutoff = _aware_utc(knowledge_cutoff)
    outcome_created_at = projected.get("outcome_created_at")

    # The SQL join already applies this guard. Keep it here too so this helper remains the
    # single fail-closed projection surface if a caller supplies a materialized row directly.
    if (
        isinstance(outcome_created_at, datetime)
        and _aware_utc(outcome_created_at) > cutoff
    ):
        for field in _OUTCOME_JOIN_FIELDS:
            projected[field] = None
        return projected

    status = projected.get("status")
    finalized_at = projected.get("finalized_at")
    if status in ("evaluated", "not_evaluable") and (
        not isinstance(finalized_at, datetime)
        or _aware_utc(finalized_at) > cutoff
    ):
        projected["status"] = "pending"
        projected["finalized_at"] = None
        for field in _OUTCOME_FINAL_VALUE_FIELDS:
            projected[field] = None

    return projected


async def _fetch_period_grid(
    conn: asyncpg.Connection,
    *,
    period_start: datetime,
    period_end: datetime,
    knowledge_cutoff: datetime,
    options: WalkForwardManifestOptions,
) -> list[dict[str, Any]]:
    """Return the expected observation×horizon grid for one frozen period."""

    rows = await conn.fetch(
        """
        WITH periodic AS (
          SELECT
            obs.observation_id,
            obs.observed_at,
            obs.observed_minute,
            obs.symbol,
            obs.state,
            obs.direction,
            obs.regime_label,
            obs.actionable,
            obs.reference_price,
            obs.created_at AS observation_created_at,
            frame.created_at AS replay_frame_created_at
          FROM signal_observation AS obs
          JOIN signal_replay_frame AS frame
            ON frame.observation_id = obs.observation_id
          WHERE obs.signal_family='scalp'
            AND obs.is_periodic
            AND obs.logic_version=$4
            AND obs.evidence_version=$5
            AND obs.sampling_version=$6
            AND frame.context_version=$7
            AND obs.observed_at >= $1
            AND obs.observed_at < $2
            AND obs.created_at <= $9
            AND frame.created_at <= $9
            AND (
              cardinality($8::text[]) = 0
              OR obs.symbol = ANY($8::text[])
            )
        ),
        grid AS (
          SELECT p.*, h.horizon_minutes
          FROM periodic AS p
          CROSS JOIN unnest($3::int[]) AS h(horizon_minutes)
        )
        SELECT
          g.observation_id,
          g.observed_at,
          g.observed_minute,
          g.symbol,
          g.state,
          g.direction,
          g.regime_label,
          g.actionable,
          g.reference_price,
          g.observation_created_at,
          g.replay_frame_created_at,
          g.horizon_minutes,
          out.outcome_version,
          out.status,
          out.window_end,
          out.due_at,
          out.created_at AS outcome_created_at,
          out.finalized_at,
          out.end_price,
          out.directional_return_pct,
          out.mfe_pct,
          out.mae_pct,
          out.market_return_pct
        FROM grid AS g
        LEFT JOIN signal_outcome AS out
          ON out.observation_id = g.observation_id
         AND out.horizon_minutes = g.horizon_minutes
         AND out.created_at <= $9
        """,
        period_start,
        period_end,
        list(options.horizons),
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
        knowledge_cutoff,
    )

    result: list[dict[str, Any]] = []
    for record in rows:
        row = _project_outcome_as_of(dict(record), knowledge_cutoff)
        correct_version = row["outcome_version"] == options.outcome_version
        usable = (
            row["status"] is not None
            and correct_version
            and row["window_end"] is not None
            and row["window_end"] <= period_end
            and row["due_at"] is not None
            and row["due_at"] <= knowledge_cutoff
        )
        row["usable"] = usable
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Spec v2: certificate-gated knowledge time (A3-01).
#
# These mirror the v1 fetch/projection functions field-for-field so every
# downstream helper (_integrity_counters, _fold_state_summary,
# _build_gross_views, _build_execution_views, ...) is reused unchanged. The
# only difference is WHAT proves knowledge-time eligibility: a
# signal_research_bundle_visibility / signal_outcome_final_visibility
# certificate, never obs.created_at/frame.created_at/out.created_at/
# finalized_at. Those legacy columns remain present in the projected row as
# provenance only; they are never read for the eligibility decision.
# ---------------------------------------------------------------------------


def _project_outcome_as_of_v2(
    row: dict[str, Any], knowledge_cutoff: datetime
) -> dict[str, Any]:
    """Spec v2: project one row using the final-outcome visibility certificate.

    A missing or not-yet-in-cutoff certificate projects the row back to
    pending/null, exactly like v1's late-final projection -- but keyed on
    the certificate's verified_visible_at, never on finalized_at directly.
    """

    projected = dict(row)
    cutoff = _aware_utc(knowledge_cutoff)

    status = projected.get("status")
    final_verified_visible_at = projected.get("final_verified_visible_at")
    if status in ("evaluated", "not_evaluable") and (
        not isinstance(final_verified_visible_at, datetime)
        or _aware_utc(final_verified_visible_at) > cutoff
    ):
        projected["status"] = "pending"
        projected["finalized_at"] = None
        for field in _OUTCOME_FINAL_VALUE_FIELDS:
            projected[field] = None

    return projected


async def _fetch_period_grid_v2(
    conn: asyncpg.Connection,
    *,
    period_start: datetime,
    period_end: datetime,
    knowledge_cutoff: datetime,
    options: WalkForwardManifestOptions,
) -> list[dict[str, Any]]:
    """Spec v2 observation x horizon grid, gated by the visibility certificate.

    An observation with no signal_research_bundle_visibility certificate (or
    one whose verified_visible_at is after knowledge_cutoff) is absent from
    the grid entirely -- not merely nulled -- because it is not proven to
    have been historically knowledge-eligible at that cutoff.
    """

    rows = await conn.fetch(
        """
        WITH periodic AS (
          SELECT
            obs.observation_id,
            obs.observed_at,
            obs.observed_minute,
            obs.symbol,
            obs.state,
            obs.direction,
            obs.regime_label,
            obs.actionable,
            obs.reference_price,
            obs.created_at AS observation_created_at,
            frame.created_at AS replay_frame_created_at
          FROM signal_observation AS obs
          JOIN signal_replay_frame AS frame
            ON frame.observation_id = obs.observation_id
          JOIN signal_research_bundle_visibility AS bv
            ON bv.observation_id = obs.observation_id
           AND bv.visibility_version = $10
          WHERE obs.signal_family='scalp'
            AND obs.is_periodic
            AND obs.logic_version=$4
            AND obs.evidence_version=$5
            AND obs.sampling_version=$6
            AND frame.context_version=$7
            AND obs.observed_at >= $1
            AND obs.observed_at < $2
            AND bv.verified_visible_at <= $9
            AND (
              cardinality($8::text[]) = 0
              OR obs.symbol = ANY($8::text[])
            )
        ),
        grid AS (
          SELECT p.*, h.horizon_minutes
          FROM periodic AS p
          CROSS JOIN unnest($3::int[]) AS h(horizon_minutes)
        )
        SELECT
          g.observation_id,
          g.observed_at,
          g.observed_minute,
          g.symbol,
          g.state,
          g.direction,
          g.regime_label,
          g.actionable,
          g.reference_price,
          g.observation_created_at,
          g.replay_frame_created_at,
          g.horizon_minutes,
          out.outcome_version,
          out.status,
          out.window_end,
          out.due_at,
          out.created_at AS outcome_created_at,
          out.finalized_at,
          out.end_price,
          out.directional_return_pct,
          out.mfe_pct,
          out.mae_pct,
          out.market_return_pct,
          fv.verified_visible_at AS final_verified_visible_at
        FROM grid AS g
        LEFT JOIN signal_outcome AS out
          ON out.observation_id = g.observation_id
         AND out.horizon_minutes = g.horizon_minutes
        LEFT JOIN signal_outcome_final_visibility AS fv
          ON fv.outcome_id = out.outcome_id
         AND fv.visibility_version = $10
        """,
        period_start,
        period_end,
        list(options.horizons),
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
        knowledge_cutoff,
        options.research_visibility_version,
    )

    result: list[dict[str, Any]] = []
    for record in rows:
        row = _project_outcome_as_of_v2(dict(record), knowledge_cutoff)
        correct_version = row["outcome_version"] == options.outcome_version
        usable = (
            row["status"] is not None
            and correct_version
            and row["window_end"] is not None
            and row["window_end"] <= period_end
            and row["due_at"] is not None
            and row["due_at"] <= knowledge_cutoff
        )
        row["usable"] = usable
        result.append(row)
    return result


def _integrity_counters(
    grid: list[dict[str, Any]],
    *,
    period_end: datetime,
    expected_outcome_version: int,
) -> dict[str, Any]:
    periodic_ids = {row["observation_id"] for row in grid}
    expected = len(grid)
    requested = sum(1 for row in grid if row["status"] is not None)
    missing_or_wrong_version = sum(
        1
        for row in grid
        if row["status"] is None
        or row["outcome_version"] != expected_outcome_version
    )
    boundary_purged = sum(
        1
        for row in grid
        if row["status"] is not None
        and row["outcome_version"] == expected_outcome_version
        and row["window_end"] is not None
        and row["window_end"] > period_end
    )
    not_yet_eligible = sum(
        1
        for row in grid
        if row["status"] is not None
        and row["outcome_version"] == expected_outcome_version
        and row["window_end"] is not None
        and row["window_end"] <= period_end
        and not row["usable"]
    )
    knowledge_eligible = sum(1 for row in grid if row["usable"])
    evaluated = sum(
        1 for row in grid if row["usable"] and row["status"] == "evaluated"
    )
    pending = sum(
        1 for row in grid if row["usable"] and row["status"] == "pending"
    )
    not_evaluable = sum(
        1 for row in grid if row["usable"] and row["status"] == "not_evaluable"
    )

    directional_metric_anomalies = 0
    for row in grid:
        if not (row["usable"] and row["status"] == "evaluated"):
            continue
        directional = bool(
            row["actionable"] and row["direction"] in ("long", "short")
        )
        metrics_present = (
            row["directional_return_pct"] is not None
            and row["mfe_pct"] is not None
            and row["mae_pct"] is not None
        )
        if directional != metrics_present:
            directional_metric_anomalies += 1

    return {
        "periodic_observations": len(periodic_ids),
        "expected_outcome_rows": expected,
        "requested_outcome_rows": requested,
        "missing_or_wrong_version_outcome_rows": missing_or_wrong_version,
        "boundary_purged_outcome_rows": boundary_purged,
        "not_yet_knowledge_eligible_outcome_rows": not_yet_eligible,
        "knowledge_eligible_outcome_rows": knowledge_eligible,
        "evaluated_outcome_rows": evaluated,
        "pending_outcome_rows": pending,
        "not_evaluable_outcome_rows": not_evaluable,
        "directional_metric_anomalies": directional_metric_anomalies,
    }


async def _fetch_execution_integrity(
    conn: asyncpg.Connection,
    *,
    period_start: datetime,
    period_end: datetime,
    options: WalkForwardManifestOptions,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        WITH compatible AS (
          SELECT
            obs.observation_id,
            obs.observed_at
          FROM signal_observation AS obs
          JOIN signal_replay_frame AS frame
            ON frame.observation_id=obs.observation_id
          WHERE obs.signal_family='scalp'
            AND obs.is_periodic
            AND obs.observed_at >= $1
            AND obs.observed_at < $2
            AND obs.logic_version=$3
            AND obs.evidence_version=$4
            AND obs.sampling_version=$5
            AND frame.context_version=$6
            AND (
              cardinality($8::text[]) = 0
              OR obs.symbol=ANY($8::text[])
            )
        ),
        snapshot_counts AS (
          SELECT
            c.observation_id,
            c.observed_at,
            COUNT(s.execution_snapshot_id)::bigint AS snapshot_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7
            )::bigint AS compatible_snapshot_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7 AND s.exchange='binance'
            )::bigint AS binance_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7 AND s.exchange='bybit'
            )::bigint AS bybit_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7
                AND s.exchange NOT IN ('binance','bybit')
            )::bigint AS unknown_rows
          FROM compatible AS c
          LEFT JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
          GROUP BY c.observation_id,c.observed_at
        ),
        execution_cohort AS (
          SELECT *
          FROM snapshot_counts
          WHERE snapshot_rows=2
            AND compatible_snapshot_rows=2
            AND binance_rows=1
            AND bybit_rows=1
            AND unknown_rows=0
        ),
        first_execution AS (
          SELECT MIN(c.observed_at) AS execution_era_start
          FROM compatible AS c
          JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
          WHERE s.snapshot_version=$7
        )
        SELECT
          (SELECT COUNT(*) FROM compatible)::bigint
            AS compatible_periodic_observations,

          (SELECT COUNT(*) FROM snapshot_counts WHERE snapshot_rows=0)::bigint
            AS periodic_without_execution_snapshot,

          (SELECT COUNT(*) FROM execution_cohort)::bigint
            AS execution_covered_periodic_observations,

          (
            SELECT COUNT(*)
            FROM snapshot_counts
            WHERE snapshot_rows > 0
              AND (
                snapshot_rows <> 2
                OR compatible_snapshot_rows <> 2
                OR binance_rows <> 1
                OR bybit_rows <> 1
                OR unknown_rows <> 0
              )
          )::bigint AS execution_snapshot_cardinality_or_version_anomalies,

          (SELECT execution_era_start FROM first_execution)
            AS execution_era_start,

          (
            SELECT COUNT(*)
            FROM snapshot_counts, first_execution
            WHERE first_execution.execution_era_start IS NOT NULL
              AND snapshot_counts.observed_at >= first_execution.execution_era_start
              AND (
                snapshot_counts.snapshot_rows <> 2
                OR snapshot_counts.compatible_snapshot_rows <> 2
                OR snapshot_counts.binance_rows <> 1
                OR snapshot_counts.bybit_rows <> 1
                OR snapshot_counts.unknown_rows <> 0
              )
          )::bigint AS execution_era_observations_without_two_snapshots,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version <> $7
          )::bigint AS execution_snapshot_version_excluded_rows,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.status='error'
          )::bigint AS execution_snapshot_error_rows,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.reason='future_book_timestamp'
          )::bigint AS future_book_timestamp_anomalies,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.status='valid'
              AND (
                s.source_book_hash IS NULL
                OR length(s.source_book_hash) <> 64
                OR (
                  SELECT count(*)
                  FROM jsonb_object_keys(s.cost_curve)
                ) <> 4
              )
          )::bigint AS valid_snapshot_shape_anomalies,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.exchange NOT IN ('binance','bybit')
          )::bigint AS combined_or_unknown_exchange_rows
        """,
        period_start,
        period_end,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
    )
    return dict(row) if row else {}


async def _fetch_execution_integrity_v2(
    conn: asyncpg.Connection,
    *,
    period_start: datetime,
    period_end: datetime,
    knowledge_cutoff: datetime,
    options: WalkForwardManifestOptions,
) -> dict[str, Any]:
    """Spec v2 execution integrity: identical accounting to v1, restricted to
    the same certified research bundle (A3-01). An observation without an
    in-cutoff signal_research_bundle_visibility certificate never enters the
    ``compatible`` cohort here, so its execution snapshots (if any exist at
    all) are never examined -- there is no path from an uncertified bundle
    into a spec-v2 execution metric.
    """

    row = await conn.fetchrow(
        """
        WITH compatible AS (
          SELECT
            obs.observation_id,
            obs.observed_at
          FROM signal_observation AS obs
          JOIN signal_replay_frame AS frame
            ON frame.observation_id=obs.observation_id
          JOIN signal_research_bundle_visibility AS bv
            ON bv.observation_id=obs.observation_id
           AND bv.visibility_version=$9
          WHERE obs.signal_family='scalp'
            AND obs.is_periodic
            AND obs.observed_at >= $1
            AND obs.observed_at < $2
            AND obs.logic_version=$3
            AND obs.evidence_version=$4
            AND obs.sampling_version=$5
            AND frame.context_version=$6
            AND bv.verified_visible_at <= $10
            AND (
              cardinality($8::text[]) = 0
              OR obs.symbol=ANY($8::text[])
            )
        ),
        snapshot_counts AS (
          SELECT
            c.observation_id,
            c.observed_at,
            COUNT(s.execution_snapshot_id)::bigint AS snapshot_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7
            )::bigint AS compatible_snapshot_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7 AND s.exchange='binance'
            )::bigint AS binance_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7 AND s.exchange='bybit'
            )::bigint AS bybit_rows,
            COUNT(s.execution_snapshot_id) FILTER (
              WHERE s.snapshot_version=$7
                AND s.exchange NOT IN ('binance','bybit')
            )::bigint AS unknown_rows
          FROM compatible AS c
          LEFT JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
          GROUP BY c.observation_id,c.observed_at
        ),
        execution_cohort AS (
          SELECT *
          FROM snapshot_counts
          WHERE snapshot_rows=2
            AND compatible_snapshot_rows=2
            AND binance_rows=1
            AND bybit_rows=1
            AND unknown_rows=0
        ),
        first_execution AS (
          SELECT MIN(c.observed_at) AS execution_era_start
          FROM compatible AS c
          JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
          WHERE s.snapshot_version=$7
        )
        SELECT
          (SELECT COUNT(*) FROM compatible)::bigint
            AS compatible_periodic_observations,

          (SELECT COUNT(*) FROM snapshot_counts WHERE snapshot_rows=0)::bigint
            AS periodic_without_execution_snapshot,

          (SELECT COUNT(*) FROM execution_cohort)::bigint
            AS execution_covered_periodic_observations,

          (
            SELECT COUNT(*)
            FROM snapshot_counts
            WHERE snapshot_rows > 0
              AND (
                snapshot_rows <> 2
                OR compatible_snapshot_rows <> 2
                OR binance_rows <> 1
                OR bybit_rows <> 1
                OR unknown_rows <> 0
              )
          )::bigint AS execution_snapshot_cardinality_or_version_anomalies,

          (SELECT execution_era_start FROM first_execution)
            AS execution_era_start,

          (
            SELECT COUNT(*)
            FROM snapshot_counts, first_execution
            WHERE first_execution.execution_era_start IS NOT NULL
              AND snapshot_counts.observed_at >= first_execution.execution_era_start
              AND (
                snapshot_counts.snapshot_rows <> 2
                OR snapshot_counts.compatible_snapshot_rows <> 2
                OR snapshot_counts.binance_rows <> 1
                OR snapshot_counts.bybit_rows <> 1
                OR snapshot_counts.unknown_rows <> 0
              )
          )::bigint AS execution_era_observations_without_two_snapshots,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version <> $7
          )::bigint AS execution_snapshot_version_excluded_rows,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.status='error'
          )::bigint AS execution_snapshot_error_rows,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.reason='future_book_timestamp'
          )::bigint AS future_book_timestamp_anomalies,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.status='valid'
              AND (
                s.source_book_hash IS NULL
                OR length(s.source_book_hash) <> 64
                OR (
                  SELECT count(*)
                  FROM jsonb_object_keys(s.cost_curve)
                ) <> 4
              )
          )::bigint AS valid_snapshot_shape_anomalies,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN compatible AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.exchange NOT IN ('binance','bybit')
          )::bigint AS combined_or_unknown_exchange_rows
        """,
        period_start,
        period_end,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
        options.research_visibility_version,
        knowledge_cutoff,
    )
    return dict(row) if row else {}


def _execution_integrity_blocked(summary: dict[str, Any]) -> bool:
    blocking_fields = (
        "execution_snapshot_cardinality_or_version_anomalies",
        "execution_era_observations_without_two_snapshots",
        "execution_snapshot_version_excluded_rows",
        "future_book_timestamp_anomalies",
        "valid_snapshot_shape_anomalies",
        "combined_or_unknown_exchange_rows",
    )
    return any(int(summary.get(field) or 0) > 0 for field in blocking_fields)


def _period_integrity_blocked(summary: dict[str, Any]) -> bool:
    return (
        int(summary.get("missing_or_wrong_version_outcome_rows") or 0) > 0
        or int(summary.get("directional_metric_anomalies") or 0) > 0
    )


def _fold_state_summary(
    *,
    fold: dict[str, Any],
    generated_at: datetime,
    discovery_integrity: dict[str, Any],
    test_integrity: dict[str, Any],
    execution_integrity: dict[str, Any],
) -> dict[str, Any]:
    clock_state = _clock_fold_state(fold, generated_at=generated_at)
    integrity_blocked = (
        _period_integrity_blocked(discovery_integrity)
        or _period_integrity_blocked(test_integrity)
        or _execution_integrity_blocked(execution_integrity)
    )

    outcome_recovery_pending = bool(
        int(discovery_integrity.get("pending_outcome_rows") or 0) > 0
        or int(test_integrity.get("pending_outcome_rows") or 0) > 0
    )

    final_state = clock_state
    if clock_state == "ready_by_clock":
        if integrity_blocked:
            final_state = "integrity_blocked"
        elif outcome_recovery_pending:
            final_state = "outcome_recovery_pending"

    return {
        "fold_index": fold["fold_index"],
        "discovery_start": fold["discovery_start"],
        "discovery_end": fold["discovery_end"],
        "test_start": fold["test_start"],
        "test_end": fold["test_end"],
        "test_maturity_at": fold["test_maturity_at"],
        "clock_state": clock_state,
        "state": final_state,
        "evaluation_ready": final_state == "ready_by_clock",
        "integrity_blocked": integrity_blocked,
        "outcome_recovery_pending": outcome_recovery_pending,
    }


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * pct
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] * (hi - k) + ordered[hi] * (k - lo)


def _group_stats(
    rows: list[dict[str, Any]],
    *,
    min_group_n: int,
) -> dict[str, Any]:
    returns = [
        float(row["directional_return_pct"])
        for row in rows
        if row["directional_return_pct"] is not None
    ]
    mfe = [float(row["mfe_pct"]) for row in rows if row["mfe_pct"] is not None]
    mae = [float(row["mae_pct"]) for row in rows if row["mae_pct"] is not None]
    n = len(returns)
    if n == 0:
        return {
            "n": 0,
            "expectancy_gross_pct": None,
            "hit_rate_pct": None,
            "median_return_pct": None,
            "p10_return_pct": None,
            "p90_return_pct": None,
            "mfe_mean_pct": None,
            "mae_mean_pct": None,
            "meets_min_group_n": False,
        }

    hits = sum(1 for value in returns if value > 0)
    return {
        "n": n,
        "expectancy_gross_pct": statistics.fmean(returns),
        "hit_rate_pct": hits / n * 100.0,
        "median_return_pct": statistics.median(returns),
        "p10_return_pct": _percentile(returns, 0.10),
        "p90_return_pct": _percentile(returns, 0.90),
        "mfe_mean_pct": statistics.fmean(mfe) if mfe else None,
        "mae_mean_pct": statistics.fmean(mae) if mae else None,
        "meets_min_group_n": n >= min_group_n,
    }


def _classify_generalization(
    *,
    discovery: dict[str, Any],
    test: dict[str, Any],
    min_group_n: int,
    fold_state: str,
) -> tuple[str, bool | None]:
    del min_group_n
    if fold_state == "integrity_blocked":
        return "integrity_blocked", None
    if fold_state != "ready_by_clock":
        return "not_ready", None
    if not discovery["meets_min_group_n"] or not test["meets_min_group_n"]:
        return "insufficient_sample", None

    discovery_expectancy = discovery["expectancy_gross_pct"]
    test_expectancy = test["expectancy_gross_pct"]
    if discovery_expectancy is None or test_expectancy is None:
        return "insufficient_sample", None
    if discovery_expectancy > 0 and test_expectancy > 0:
        return "positive_generalization_observed", True
    if discovery_expectancy > 0 and test_expectancy <= 0:
        return "failed_to_generalize", False
    if discovery_expectancy <= 0 and test_expectancy > 0:
        return "oos_positive_without_discovery_edge", False
    return "non_positive_both", False


def _group_key(row: dict[str, Any], view: str) -> tuple[Any, ...]:
    if view == "overall":
        return (row["symbol"], row["horizon_minutes"])
    if view == "state":
        return (
            row["symbol"],
            row["state"],
            row["direction"],
            row["horizon_minutes"],
        )
    if view == "regime":
        return (
            row["symbol"],
            row["regime_label"],
            row["direction"],
            row["horizon_minutes"],
        )
    raise ValueError(f"unsupported gross view: {view}")


def _dimension_names(view: str) -> tuple[str, ...]:
    if view == "overall":
        return ("symbol", "horizon_minutes")
    if view == "state":
        return ("symbol", "state", "direction", "horizon_minutes")
    if view == "regime":
        return ("symbol", "regime_label", "direction", "horizon_minutes")
    raise ValueError(f"unsupported gross view: {view}")


def _actionable_evaluated(
    grid: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        row
        for row in grid
        if row["usable"]
        and row["status"] == "evaluated"
        and row["actionable"]
        and row["direction"] in ("long", "short")
    ]


def _build_gross_views(
    *,
    discovery_grid: list[dict[str, Any]],
    test_grid: list[dict[str, Any]],
    min_group_n: int,
    fold_state: str,
) -> dict[str, list[dict[str, Any]]]:
    discovery_rows = _actionable_evaluated(discovery_grid)
    test_rows = _actionable_evaluated(test_grid)

    views: dict[str, list[dict[str, Any]]] = {}
    for view in GROSS_VIEWS:
        discovery_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in discovery_rows:
            discovery_groups.setdefault(_group_key(row, view), []).append(row)

        test_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in test_rows:
            test_groups.setdefault(_group_key(row, view), []).append(row)

        keys = sorted(
            set(discovery_groups) | set(test_groups),
            key=lambda item: tuple("" if part is None else str(part) for part in item),
        )
        result: list[dict[str, Any]] = []
        for key in keys:
            discovery_stats = _group_stats(
                discovery_groups.get(key, []),
                min_group_n=min_group_n,
            )
            test_stats = _group_stats(
                test_groups.get(key, []),
                min_group_n=min_group_n,
            )
            label, positive_gate = _classify_generalization(
                discovery=discovery_stats,
                test=test_stats,
                min_group_n=min_group_n,
                fold_state=fold_state,
            )

            discovery_expectancy = discovery_stats["expectancy_gross_pct"]
            test_expectancy = test_stats["expectancy_gross_pct"]
            expectancy_diff = None
            retention_ratio = None
            sign_preserved = None
            if discovery_expectancy is not None and test_expectancy is not None:
                expectancy_diff = test_expectancy - discovery_expectancy
                if discovery_expectancy != 0:
                    retention_ratio = test_expectancy / discovery_expectancy
                sign_preserved = (discovery_expectancy > 0) == (
                    test_expectancy > 0
                )

            hit_rate_diff = None
            if (
                discovery_stats["hit_rate_pct"] is not None
                and test_stats["hit_rate_pct"] is not None
            ):
                hit_rate_diff = (
                    test_stats["hit_rate_pct"] - discovery_stats["hit_rate_pct"]
                )

            result.append(
                {
                    **dict(zip(_dimension_names(view), key, strict=True)),
                    "discovery": discovery_stats,
                    "test": test_stats,
                    "expectancy_diff_pct": expectancy_diff,
                    "expectancy_retention_ratio": retention_ratio,
                    "hit_rate_diff_pct": hit_rate_diff,
                    "sign_preserved": sign_preserved,
                    "label": label,
                    "positive_oos_gate_passed": positive_gate,
                }
            )
        views[view] = result
    return views


async def _fetch_execution_snapshots(
    conn: asyncpg.Connection,
    observation_ids: list[int],
    *,
    execution_snapshot_version: int,
) -> dict[int, dict[str, dict[str, Any]]]:
    if not observation_ids:
        return {}

    rows = await conn.fetch(
        """
        SELECT
          observation_id,
          exchange,
          snapshot_version,
          status,
          reason,
          mid_px,
          cost_curve
        FROM signal_execution_snapshot
        WHERE observation_id = ANY($1::bigint[])
          AND snapshot_version = $2
        """,
        observation_ids,
        execution_snapshot_version,
    )
    result: dict[int, dict[str, dict[str, Any]]] = {}
    for record in rows:
        row = dict(record)
        result.setdefault(int(row["observation_id"]), {})[
            str(row["exchange"])
        ] = row
    return result


def _curve_leg(
    snapshot: dict[str, Any] | None,
    *,
    size_usd: float,
    side: str,
) -> dict[str, Any] | None:
    if snapshot is None or snapshot["status"] != "valid":
        return None

    curve = snapshot["cost_curve"]
    if isinstance(curve, str):
        curve = json.loads(curve)
    if not isinstance(curve, dict):
        return None

    entry = curve.get(str(int(size_usd)))
    if not isinstance(entry, dict):
        return None
    leg = entry.get(side)
    return leg if isinstance(leg, dict) else None


def _execution_measure(
    row: dict[str, Any],
    snapshot: dict[str, Any] | None,
    *,
    size_usd: float,
    fee_bps_per_side: float | None,
) -> dict[str, Any]:
    side = "buy" if row["direction"] == "long" else "sell"
    status = None if snapshot is None else snapshot.get("status")
    result: dict[str, Any] = {
        "snapshot_missing": snapshot is None,
        "snapshot_nonvalid": snapshot is not None and status != "valid",
        "insufficient_depth": False,
        "cost_evaluable": False,
        "gross_directional_return_bps": (
            None
            if row["directional_return_pct"] is None
            else float(row["directional_return_pct"]) * 100.0
        ),
        "entry_market_cost_bps": None,
        "entry_implementation_shortfall_bps": None,
        "entry_only_market_net_bps": None,
        "symmetric_market_net_bps": None,
        "modeled_net_after_fees_bps": None,
    }

    if snapshot is None or status != "valid":
        return result

    leg = _curve_leg(snapshot, size_usd=size_usd, side=side)
    if leg is None:
        return result

    insufficient = bool(leg.get("insufficient_depth"))
    result["insufficient_depth"] = insufficient
    if insufficient:
        return result

    entry_fill = leg.get("avg_price")
    entry_cost = leg.get("market_cost_bps_vs_mid")
    reference_price = row.get("reference_price")
    end_price = row.get("end_price")

    try:
        entry_fill = None if entry_fill is None else float(entry_fill)
        entry_cost = None if entry_cost is None else float(entry_cost)
        reference_price = (
            None if reference_price is None else float(reference_price)
        )
        end_price = None if end_price is None else float(end_price)
    except (TypeError, ValueError, OverflowError):
        return result

    if (
        entry_fill is None
        or entry_fill <= 0
        or entry_cost is None
        or not math.isfinite(entry_cost)
        or end_price is None
        or end_price <= 0
    ):
        return result

    result["entry_market_cost_bps"] = entry_cost
    result["cost_evaluable"] = True

    if reference_price is not None and reference_price > 0:
        if row["direction"] == "long":
            result["entry_implementation_shortfall_bps"] = (
                entry_fill / reference_price - 1.0
            ) * 10_000.0
        else:
            result["entry_implementation_shortfall_bps"] = (
                reference_price - entry_fill
            ) / reference_price * 10_000.0

    if row["direction"] == "long":
        result["entry_only_market_net_bps"] = (
            end_price / entry_fill - 1.0
        ) * 10_000.0
        symmetric = (
            (end_price * (1.0 - entry_cost / 10_000.0)) / entry_fill - 1.0
        ) * 10_000.0
    else:
        result["entry_only_market_net_bps"] = (
            entry_fill - end_price
        ) / entry_fill * 10_000.0
        symmetric = (
            entry_fill - end_price * (1.0 + entry_cost / 10_000.0)
        ) / entry_fill * 10_000.0

    result["symmetric_market_net_bps"] = symmetric
    if fee_bps_per_side is not None:
        result["modeled_net_after_fees_bps"] = (
            symmetric - 2.0 * fee_bps_per_side
        )
    return result


def _execution_bucket_summary(
    bucket: dict[str, Any] | None,
    *,
    min_group_n: int,
) -> dict[str, Any]:
    if bucket is None:
        return {
            "n_evaluated_actionable": 0,
            "snapshot_missing_n": 0,
            "snapshot_nonvalid_n": 0,
            "insufficient_depth_n": 0,
            "n_cost_evaluable": 0,
            "cost_evaluable_pct": None,
            "gross_expectancy_bps": None,
            "entry_market_cost_mean_bps": None,
            "entry_implementation_shortfall_mean_bps": None,
            "entry_only_market_net_expectancy_bps": None,
            "symmetric_market_net_expectancy_bps": None,
            "symmetric_market_net_hit_rate_pct": None,
            "modeled_net_after_fees_n": 0,
            "modeled_net_after_fees_expectancy_bps": None,
            "modeled_net_after_fees_hit_rate_pct": None,
            "meets_min_group_n": False,
        }

    n_eval = int(bucket["n_evaluated_actionable"])
    symmetric = bucket["symmetric_market_net_bps"]
    after_fees = bucket["modeled_net_after_fees_bps"]
    n_cost = len(symmetric)

    return {
        "n_evaluated_actionable": n_eval,
        "snapshot_missing_n": int(bucket["snapshot_missing_n"]),
        "snapshot_nonvalid_n": int(bucket["snapshot_nonvalid_n"]),
        "insufficient_depth_n": int(bucket["insufficient_depth_n"]),
        "n_cost_evaluable": n_cost,
        "cost_evaluable_pct": (
            None if n_eval == 0 else n_cost / n_eval * 100.0
        ),
        "gross_expectancy_bps": (
            statistics.fmean(bucket["gross_bps"])
            if bucket["gross_bps"]
            else None
        ),
        "entry_market_cost_mean_bps": (
            statistics.fmean(bucket["entry_market_cost_bps"])
            if bucket["entry_market_cost_bps"]
            else None
        ),
        "entry_implementation_shortfall_mean_bps": (
            statistics.fmean(bucket["entry_implementation_shortfall_bps"])
            if bucket["entry_implementation_shortfall_bps"]
            else None
        ),
        "entry_only_market_net_expectancy_bps": (
            statistics.fmean(bucket["entry_only_market_net_bps"])
            if bucket["entry_only_market_net_bps"]
            else None
        ),
        "symmetric_market_net_expectancy_bps": (
            statistics.fmean(symmetric) if symmetric else None
        ),
        "symmetric_market_net_hit_rate_pct": (
            None
            if not symmetric
            else sum(value > 0 for value in symmetric) / len(symmetric) * 100.0
        ),
        "modeled_net_after_fees_n": len(after_fees),
        "modeled_net_after_fees_expectancy_bps": (
            statistics.fmean(after_fees) if after_fees else None
        ),
        "modeled_net_after_fees_hit_rate_pct": (
            None
            if not after_fees
            else sum(value > 0 for value in after_fees)
            / len(after_fees)
            * 100.0
        ),
        "meets_min_group_n": n_cost >= min_group_n,
    }


def _classify_execution_generalization(
    *,
    discovery: dict[str, Any],
    test: dict[str, Any],
    fold_state: str,
) -> tuple[str, bool | None]:
    if fold_state == "integrity_blocked":
        return "integrity_blocked", None
    if fold_state != "ready_by_clock":
        return "not_ready", None
    if not discovery["meets_min_group_n"] or not test["meets_min_group_n"]:
        return "insufficient_execution_sample", None

    discovery_net = discovery["symmetric_market_net_expectancy_bps"]
    test_net = test["symmetric_market_net_expectancy_bps"]
    if discovery_net is None or test_net is None:
        return "insufficient_execution_sample", None
    if discovery_net > 0 and test_net > 0:
        return "positive_market_cost_generalization_observed", True
    if discovery_net > 0 and test_net <= 0:
        return "market_cost_edge_failed_to_generalize", False
    if discovery_net <= 0 and test_net > 0:
        return "oos_market_cost_positive_without_discovery_edge", False
    return "non_positive_after_market_cost_both", False


def _build_execution_views(
    *,
    discovery_grid: list[dict[str, Any]],
    test_grid: list[dict[str, Any]],
    discovery_snapshots: dict[int, dict[str, dict[str, Any]]],
    test_snapshots: dict[int, dict[str, dict[str, Any]]],
    options: WalkForwardManifestOptions,
    fold_state: str,
) -> list[dict[str, Any]]:
    discovery_rows = _actionable_evaluated(discovery_grid)
    test_rows = _actionable_evaluated(test_grid)
    fee_map = dict(options.fee_bps_per_side)

    def period_groups(
        rows: list[dict[str, Any]],
        snapshots: dict[int, dict[str, dict[str, Any]]],
    ) -> dict[tuple[Any, ...], dict[str, Any]]:
        groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in rows:
            snapshot_by_exchange = snapshots.get(row["observation_id"], {})
            for exchange in options.exchanges:
                snapshot = snapshot_by_exchange.get(exchange)
                for size_usd in options.sizes_usd:
                    key = (
                        row["symbol"],
                        exchange,
                        size_usd,
                        row["horizon_minutes"],
                    )
                    bucket = groups.setdefault(
                        key,
                        {
                            "n_evaluated_actionable": 0,
                            "snapshot_missing_n": 0,
                            "snapshot_nonvalid_n": 0,
                            "insufficient_depth_n": 0,
                            "gross_bps": [],
                            "entry_market_cost_bps": [],
                            "entry_implementation_shortfall_bps": [],
                            "entry_only_market_net_bps": [],
                            "symmetric_market_net_bps": [],
                            "modeled_net_after_fees_bps": [],
                        },
                    )
                    bucket["n_evaluated_actionable"] += 1
                    gross = (
                        None
                        if row["directional_return_pct"] is None
                        else float(row["directional_return_pct"]) * 100.0
                    )
                    if gross is not None:
                        bucket["gross_bps"].append(gross)

                    measure = _execution_measure(
                        row,
                        snapshot,
                        size_usd=size_usd,
                        fee_bps_per_side=fee_map.get(exchange),
                    )
                    if measure["snapshot_missing"]:
                        bucket["snapshot_missing_n"] += 1
                    if measure["snapshot_nonvalid"]:
                        bucket["snapshot_nonvalid_n"] += 1
                    if measure["insufficient_depth"]:
                        bucket["insufficient_depth_n"] += 1
                    if not measure["cost_evaluable"]:
                        continue

                    for field in (
                        "entry_market_cost_bps",
                        "entry_implementation_shortfall_bps",
                        "entry_only_market_net_bps",
                        "symmetric_market_net_bps",
                        "modeled_net_after_fees_bps",
                    ):
                        value = measure[field]
                        if value is not None:
                            bucket[field].append(value)
        return groups

    discovery_groups = period_groups(discovery_rows, discovery_snapshots)
    test_groups = period_groups(test_rows, test_snapshots)
    keys = sorted(
        set(discovery_groups) | set(test_groups),
        key=lambda item: tuple(str(part) for part in item),
    )

    result: list[dict[str, Any]] = []
    for key in keys:
        symbol, exchange, size_usd, horizon = key
        discovery_stats = _execution_bucket_summary(
            discovery_groups.get(key),
            min_group_n=options.min_group_n,
        )
        test_stats = _execution_bucket_summary(
            test_groups.get(key),
            min_group_n=options.min_group_n,
        )
        label, positive_gate = _classify_execution_generalization(
            discovery=discovery_stats,
            test=test_stats,
            fold_state=fold_state,
        )

        discovery_net = discovery_stats[
            "symmetric_market_net_expectancy_bps"
        ]
        test_net = test_stats["symmetric_market_net_expectancy_bps"]
        net_diff = None
        retention_ratio = None
        if discovery_net is not None and test_net is not None:
            net_diff = test_net - discovery_net
            if discovery_net != 0:
                retention_ratio = test_net / discovery_net

        result.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "size_usd": size_usd,
                "horizon_minutes": horizon,
                "fee_bps_per_side_applied": fee_map.get(exchange),
                "discovery": discovery_stats,
                "test": test_stats,
                "net_expectancy_diff_bps": net_diff,
                "net_expectancy_retention_ratio": retention_ratio,
                "label": label,
                "positive_market_cost_oos_gate_passed": positive_gate,
            }
        )
    return result


async def _evaluate_fold(
    conn: asyncpg.Connection,
    *,
    fold: dict[str, Any],
    generated_at: datetime,
    options: WalkForwardManifestOptions,
) -> dict[str, Any]:
    is_spec_v1 = options.spec_version == WALK_FORWARD_SPEC_VERSION
    fetch_period_grid = _fetch_period_grid if is_spec_v1 else _fetch_period_grid_v2

    discovery_end = fold["discovery_end"]
    discovery_grid = await fetch_period_grid(
        conn,
        period_start=fold["discovery_start"],
        period_end=discovery_end,
        knowledge_cutoff=min(generated_at, discovery_end),
        options=options,
    )
    test_grid = await fetch_period_grid(
        conn,
        period_start=fold["test_start"],
        period_end=fold["test_end"],
        knowledge_cutoff=generated_at,
        options=options,
    )

    discovery_integrity = _integrity_counters(
        discovery_grid,
        period_end=discovery_end,
        expected_outcome_version=options.outcome_version,
    )
    test_integrity = _integrity_counters(
        test_grid,
        period_end=fold["test_end"],
        expected_outcome_version=options.outcome_version,
    )

    execution_end = min(generated_at, fold["test_end"])
    if is_spec_v1:
        execution_integrity = await _fetch_execution_integrity(
            conn,
            period_start=fold["discovery_start"],
            period_end=execution_end,
            options=options,
        )
    else:
        execution_integrity = await _fetch_execution_integrity_v2(
            conn,
            period_start=fold["discovery_start"],
            period_end=execution_end,
            knowledge_cutoff=execution_end,
            options=options,
        )

    summary = _fold_state_summary(
        fold=fold,
        generated_at=generated_at,
        discovery_integrity=discovery_integrity,
        test_integrity=test_integrity,
        execution_integrity=execution_integrity,
    )

    all_discovery_ids = list(
        {
            int(row["observation_id"])
            for row in _actionable_evaluated(discovery_grid)
        }
    )
    all_test_ids = list(
        {
            int(row["observation_id"])
            for row in _actionable_evaluated(test_grid)
        }
    )
    discovery_snapshots = await _fetch_execution_snapshots(
        conn,
        all_discovery_ids,
        execution_snapshot_version=options.execution_snapshot_version,
    )
    test_snapshots = await _fetch_execution_snapshots(
        conn,
        all_test_ids,
        execution_snapshot_version=options.execution_snapshot_version,
    )

    gross_by_mode: dict[str, Any] = {}
    execution_by_mode: dict[str, Any] = {}
    for mode in options.sampling_modes:
        sampled_discovery = _sample_grid(discovery_grid, mode)
        sampled_test = _sample_grid(test_grid, mode)

        gross_by_mode[mode] = _build_gross_views(
            discovery_grid=sampled_discovery,
            test_grid=sampled_test,
            min_group_n=options.min_group_n,
            fold_state=summary["state"],
        )
        execution_by_mode[mode] = _build_execution_views(
            discovery_grid=sampled_discovery,
            test_grid=sampled_test,
            discovery_snapshots=discovery_snapshots,
            test_snapshots=test_snapshots,
            options=options,
            fold_state=summary["state"],
        )

    return {
        **summary,
        "integrity": {
            "discovery": discovery_integrity,
            "test": test_integrity,
            "execution": execution_integrity,
        },
        "gross_views": gross_by_mode,
        "execution_views": execution_by_mode,
    }


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    if not isinstance(value, str):
        raise ValueError("manifest fold timestamp is not ISO text")
    return _aware_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


async def evaluate_walk_forward(
    conn: asyncpg.Connection,
    manifest_name: str,
) -> dict[str, Any]:
    """Stage B: hash/schedule-verified read-only walk-forward evaluation."""

    manifest, options = await load_walk_forward_manifest(conn, manifest_name)
    generated_at = _aware_utc(await conn.fetchval("SELECT clock_timestamp()"))

    fold_specs: list[dict[str, Any]] = []
    for fold in manifest["folds"]:
        fold_specs.append(
            {
                "fold_index": int(fold["fold_index"]),
                "discovery_start": _parse_iso(fold["discovery_start"]),
                "discovery_end": _parse_iso(fold["discovery_end"]),
                "test_start": _parse_iso(fold["test_start"]),
                "test_end": _parse_iso(fold["test_end"]),
                "test_maturity_at": _parse_iso(fold["test_maturity_at"]),
            }
        )

    folds = [
        await _evaluate_fold(
            conn,
            fold=fold,
            generated_at=generated_at,
            options=options,
        )
        for fold in fold_specs
    ]

    ready_by_clock_fold_count = sum(
        fold["clock_state"] == "ready_by_clock" for fold in folds
    )
    evaluation_ready_fold_count = sum(
        bool(fold["evaluation_ready"]) for fold in folds
    )

    positive_oos_gate_count = 0
    positive_execution_oos_gate_count = 0
    for fold in folds:
        for mode_views in fold["gross_views"].values():
            for rows in mode_views.values():
                positive_oos_gate_count += sum(
                    row["positive_oos_gate_passed"] is True for row in rows
                )
        for rows in fold["execution_views"].values():
            positive_execution_oos_gate_count += sum(
                row["positive_market_cost_oos_gate_passed"] is True
                for row in rows
            )

    is_spec_v1 = options.spec_version == WALK_FORWARD_SPEC_VERSION
    global_execution_end = min(
        generated_at,
        fold_specs[-1]["test_end"],
    )
    if is_spec_v1:
        execution_integrity = await _fetch_execution_integrity(
            conn,
            period_start=_parse_iso(manifest["spec"]["discovery_start"]),
            period_end=global_execution_end,
            options=options,
        )
    else:
        execution_integrity = await _fetch_execution_integrity_v2(
            conn,
            period_start=_parse_iso(manifest["spec"]["discovery_start"]),
            period_end=global_execution_end,
            knowledge_cutoff=global_execution_end,
            options=options,
        )

    first_oos_cutoff_in_future = _aware_utc(manifest["cutoff_at"]) > generated_at

    report_version = (
        WALK_FORWARD_REPORT_VERSION if is_spec_v1 else WALK_FORWARD_REPORT_VERSION_V2
    )

    report: dict[str, Any] = {
        "report_version": report_version,
        "walk_forward_spec_version": options.spec_version,
        "manifest_version": WALK_FORWARD_MANIFEST_VERSION,
        "generated_at": generated_at,
        "manifest": {
            "manifest_id": manifest["manifest_id"],
            "manifest_name": manifest["manifest_name"],
            "manifest_hash": manifest["manifest_hash"],
            "created_at": manifest["created_at"],
            "cutoff_at": manifest["cutoff_at"],
            "selection_policy": manifest["selection_policy"],
            "warmup_days": manifest["warmup_days"],
            "test_days": manifest["test_days"],
            "fold_count": manifest["fold_count"],
            "min_group_n": manifest["min_group_n"],
            "spec": manifest["spec"],
        },
        "gates": {
            "manifest_hash_valid": True,
            "schedule_valid": True,
            "selection_policy_is_fixed_no_selection": True,
            "first_oos_boundary_frozen_before_start": (
                _aware_utc(manifest["created_at"])
                < _aware_utc(manifest["cutoff_at"])
            ),
            "automatic_parameter_selection": False,
            "automatic_live_model_changes": False,
            "ready_by_clock_fold_count": ready_by_clock_fold_count,
            "evaluation_ready_fold_count": evaluation_ready_fold_count,
            "positive_oos_gate_count": positive_oos_gate_count,
            "positive_execution_oos_gate_count": (
                positive_execution_oos_gate_count
            ),
        },
        "first_oos_cutoff_in_future": first_oos_cutoff_in_future,
        "ready_by_clock_fold_count": ready_by_clock_fold_count,
        "evaluation_ready_fold_count": evaluation_ready_fold_count,
        "execution_integrity": execution_integrity,
        "folds": folds,
        "execution_contract": {
            "source": "signal_execution_snapshot (PR10 immutable)",
            "reads_current_orderbook_depth": False,
            "round_trip_market_model": "symmetric_entry_book_v1",
            "funding_modeled": False,
            "min_execution_coverage_pct": None,
        },
        "methodology": {
            "sampling_modes": list(options.sampling_modes),
            "gross_views": list(GROSS_VIEWS),
            "no_ranking_or_winner_selection": True,
            "live_scoring_changes": False,
        },
    }

    if not is_spec_v1:
        # Additive-only metadata: never removes/changes a v1 field, and v1's
        # output path above is untouched, so this branch cannot affect it.
        report["knowledge_visibility_contract"] = {
            "research_visibility_version": options.research_visibility_version,
            "certificate_dominates_created_at_and_finalized_at": True,
            "uncertified_observation_excluded_from_grid": True,
            "final_outcome_requires_final_visibility_certificate": True,
            "execution_snapshots_restricted_to_certified_bundle": True,
        }

    return report
