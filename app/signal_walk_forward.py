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
    EXECUTION_EXCHANGES,
    EXECUTION_SIZES_USD,
    EXECUTION_SNAPSHOT_VERSION,
    SAMPLING_MODES,
)
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

# ---------------------------------------------------------------------------
# Versions and fixed research policy.
#
# PR11 is a walk-forward / out-of-sample evaluation engine layered on top of
# the immutable PR4-PR10 research corpus. It never recomputes PR4-PR10
# results and never changes live scoring.
# ---------------------------------------------------------------------------

WALK_FORWARD_MANIFEST_VERSION = 1
WALK_FORWARD_SPEC_VERSION = 1
WALK_FORWARD_REPORT_VERSION = 1

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


def validate_manifest_options(options: WalkForwardManifestOptions) -> None:
    """Fail closed on any invalid or out-of-contract manifest option.

    No CLI option here can request a retroactive cutoff: the cutoff is always
    derived from the PostgreSQL clock at freeze time plus ``warmup_days``,
    never accepted as a caller-supplied timestamp.
    """

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

    return {
        "spec_version": WALK_FORWARD_SPEC_VERSION,
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
        "versions": {
            "logic_version": options.logic_version,
            "evidence_version": options.evidence_version,
            "sampling_version": options.sampling_version,
            "context_version": options.context_version,
            "outcome_version": options.outcome_version,
            "execution_snapshot_version": options.execution_snapshot_version,
        },
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


def _reuse_or_fail(
    existing_row: asyncpg.Record,
    static_spec: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    stored_spec = _load_spec(existing_row["spec"])
    stored_static = {key: stored_spec.get(key) for key in static_spec}
    if stored_static != static_spec:
        raise ValueError(
            f"walk-forward manifest {name!r} already exists with a different static "
            "spec; freeze fails closed instead of silently reusing or mutating it"
        )
    recomputed_hash = _spec_hash(stored_spec)
    if recomputed_hash != existing_row["manifest_hash"]:
        raise ValueError(
            f"walk-forward manifest {name!r} failed hash verification (tamper or "
            "corruption); refusing to reuse it"
        )
    return _manifest_record(existing_row, reused_existing=True)


async def load_walk_forward_manifest(
    conn: asyncpg.Connection,
    name: str,
) -> dict[str, Any]:
    """Load and hash-verify an existing manifest. Fails closed on mismatch."""

    row = await conn.fetchrow(
        "SELECT * FROM signal_walk_forward_manifest WHERE manifest_name=$1",
        name,
    )
    if row is None:
        raise ValueError(f"walk-forward manifest {name!r} does not exist")
    stored_spec = _load_spec(row["spec"])
    recomputed_hash = _spec_hash(stored_spec)
    if recomputed_hash != row["manifest_hash"]:
        raise ValueError(
            f"walk-forward manifest {name!r} failed hash verification (tamper or "
            "corruption); evaluation fails closed"
        )
    return _manifest_record(row, reused_existing=True)


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


def _clock_fold_state(fold: dict[str, Any], *, generated_at: datetime) -> str:
    if generated_at < fold["discovery_end"]:
        return "discovery_collecting"
    if generated_at < fold["test_end"]:
        return "test_collecting"
    if generated_at < fold["test_maturity_at"]:
        return "test_settling"
    return "ready_by_clock"


async def _fold_integrity_blockers(
    conn: asyncpg.Connection,
    *,
    fold: dict[str, Any],
    options: WalkForwardManifestOptions,
) -> dict[str, Any]:
    """Recovery/integrity checks that can keep a clock-mature fold from
    becoming ``evaluation_ready``.

    A fold that reached ``ready_by_clock`` is still not usable if PR5 rows
    covering its test window are stuck ``pending`` (outcome recovery still
    owed) or if a data-gap/version anomaly makes the window untrustworthy.
    """

    pending_row = await conn.fetchrow(
        """
        SELECT COUNT(*) AS pending_n
        FROM signal_outcome AS out
        JOIN signal_observation AS obs
          ON obs.observation_id = out.observation_id
        WHERE obs.signal_family='scalp'
          AND obs.is_periodic
          AND obs.observed_at >= $1 AND obs.observed_at < $2
          AND out.window_end <= $2
          AND out.horizon_minutes = ANY($3::int[])
          AND out.status='pending'
        """,
        fold["test_start"],
        fold["test_end"],
        list(options.horizons),
    )
    pending_n = int(pending_row["pending_n"]) if pending_row else 0
    if pending_n > 0:
        return {"state": "outcome_recovery_pending", "pending_outcome_rows": pending_n}
    return {"state": None, "pending_outcome_rows": 0}


def _fold_state_summary(
    *,
    fold: dict[str, Any],
    generated_at: datetime,
    blockers: dict[str, Any],
) -> dict[str, Any]:
    clock_state = _clock_fold_state(fold, generated_at=generated_at)
    final_state = clock_state
    if clock_state == "ready_by_clock" and blockers["state"] is not None:
        final_state = blockers["state"]
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
        "pending_outcome_rows": blockers["pending_outcome_rows"],
    }


async def _fetch_period_grid(
    conn: asyncpg.Connection,
    *,
    period_start: datetime,
    period_end: datetime,
    knowledge_cutoff: datetime,
    options: WalkForwardManifestOptions,
) -> list[dict[str, Any]]:
    """One row per (periodic observation x requested horizon) inside the
    period, left-joined to its PR5 outcome. This is the expected-rows grid
    used for both gross statistics and integrity counters.

    ``knowledge_cutoff`` encodes the knowledge-time rule: for discovery it is
    ``discovery_end`` (rule 5); for test it is the report's
    ``generated_at`` (rule 6). An outcome is only usable when
    ``window_end <= period_end`` (path never crosses the period boundary)
    AND ``due_at <= knowledge_cutoff``.
    """

    rows = await conn.fetch(
        """
        WITH periodic AS (
          SELECT obs.observation_id, obs.symbol, obs.state, obs.direction,
                 obs.regime_label, obs.actionable
          FROM signal_observation AS obs
          JOIN signal_replay_frame AS frame
            ON frame.observation_id = obs.observation_id
          WHERE obs.signal_family='scalp'
            AND obs.is_periodic
            AND obs.logic_version=$4
            AND obs.evidence_version=$5
            AND obs.sampling_version=$6
            AND frame.context_version=$7
            AND obs.observed_at >= $1 AND obs.observed_at < $2
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
          g.observation_id, g.symbol, g.state, g.direction, g.regime_label,
          g.actionable, g.horizon_minutes,
          out.outcome_version, out.status, out.window_end, out.due_at,
          out.directional_return_pct, out.mfe_pct, out.mae_pct,
          out.market_return_pct
        FROM grid AS g
        LEFT JOIN signal_outcome AS out
          ON out.observation_id = g.observation_id
         AND out.horizon_minutes = g.horizon_minutes
        """,
        period_start,
        period_end,
        list(options.horizons),
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
    )

    result: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        usable = (
            row["status"] is not None
            and row["outcome_version"] == options.outcome_version
            and row["window_end"] is not None
            and row["window_end"] <= period_end
            and row["due_at"] is not None
            and row["due_at"] <= knowledge_cutoff
        )
        row["usable"] = usable
        result.append(row)
    return result


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


def _integrity_counters(grid: list[dict[str, Any]], *, period_end: datetime) -> dict[str, Any]:
    periodic_ids = {row["observation_id"] for row in grid}
    expected = len(grid)
    requested = sum(1 for row in grid if row["status"] is not None)
    missing_or_wrong_version = sum(
        1
        for row in grid
        if row["status"] is None
        or row["outcome_version"] is None
    )
    boundary_purged = sum(
        1
        for row in grid
        if row["status"] is not None
        and row["window_end"] is not None
        and row["window_end"] > period_end
    )
    not_yet_eligible = sum(
        1
        for row in grid
        if row["status"] is not None
        and row["window_end"] is not None
        and row["window_end"] <= period_end
        and not row["usable"]
    )
    knowledge_eligible = sum(1 for row in grid if row["usable"])
    evaluated = sum(1 for row in grid if row["usable"] and row["status"] == "evaluated")
    pending = sum(1 for row in grid if row["usable"] and row["status"] == "pending")
    not_evaluable = sum(1 for row in grid if row["usable"] and row["status"] == "not_evaluable")
    anomalies = 0
    for row in grid:
        if not (row["usable"] and row["status"] == "evaluated"):
            continue
        directional = row["direction"] in ("long", "short")
        has_directional_metric = row["directional_return_pct"] is not None
        if directional != has_directional_metric:
            anomalies += 1

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
        "directional_metric_anomalies": anomalies,
    }


def _group_stats(rows: list[dict[str, Any]], *, min_group_n: int) -> dict[str, Any]:
    returns = [r["directional_return_pct"] for r in rows if r["directional_return_pct"] is not None]
    mfe = [r["mfe_pct"] for r in rows if r["mfe_pct"] is not None]
    mae = [r["mae_pct"] for r in rows if r["mae_pct"] is not None]
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
    fold_evaluation_ready: bool,
) -> str:
    if not fold_evaluation_ready:
        return "not_ready"
    if not discovery["meets_min_group_n"] or not test["meets_min_group_n"]:
        return "insufficient_sample"
    d = discovery["expectancy_gross_pct"]
    t = test["expectancy_gross_pct"]
    if d is None or t is None:
        return "insufficient_sample"
    if d > 0 and t > 0:
        return "positive_generalization_observed"
    if d > 0 and t <= 0:
        return "failed_to_generalize"
    if d <= 0 and t > 0:
        return "oos_positive_without_discovery_edge"
    return "non_positive_both"


def _group_key(row: dict[str, Any], view: str) -> tuple:
    if view == "overall":
        return (row["symbol"], row["horizon_minutes"])
    if view == "state":
        return (row["symbol"], row["state"], row["direction"], row["horizon_minutes"])
    if view == "regime":
        return (row["symbol"], row["regime_label"], row["direction"], row["horizon_minutes"])
    raise ValueError(f"unsupported gross view: {view}")


def _actionable_evaluated(grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    fold_evaluation_ready: bool,
) -> dict[str, list[dict[str, Any]]]:
    discovery_rows = _actionable_evaluated(discovery_grid)
    test_rows = _actionable_evaluated(test_grid)

    views: dict[str, list[dict[str, Any]]] = {}
    for view in GROSS_VIEWS:
        discovery_groups: dict[tuple, list[dict[str, Any]]] = {}
        for row in discovery_rows:
            discovery_groups.setdefault(_group_key(row, view), []).append(row)
        test_groups: dict[tuple, list[dict[str, Any]]] = {}
        for row in test_rows:
            test_groups.setdefault(_group_key(row, view), []).append(row)

        keys = sorted(set(discovery_groups) | set(test_groups), key=lambda item: [str(part) for part in item])
        group_rows: list[dict[str, Any]] = []
        for key in keys:
            discovery_stats = _group_stats(discovery_groups.get(key, []), min_group_n=min_group_n)
            test_stats = _group_stats(test_groups.get(key, []), min_group_n=min_group_n)
            label = _classify_generalization(
                discovery=discovery_stats,
                test=test_stats,
                min_group_n=min_group_n,
                fold_evaluation_ready=fold_evaluation_ready,
            )
            expectancy_diff = None
            retention_ratio = None
            hit_rate_diff = None
            sign_preserved = None
            if (
                discovery_stats["expectancy_gross_pct"] is not None
                and test_stats["expectancy_gross_pct"] is not None
            ):
                expectancy_diff = (
                    test_stats["expectancy_gross_pct"] - discovery_stats["expectancy_gross_pct"]
                )
                if discovery_stats["expectancy_gross_pct"] != 0:
                    retention_ratio = (
                        test_stats["expectancy_gross_pct"] / discovery_stats["expectancy_gross_pct"]
                    )
                sign_preserved = (
                    discovery_stats["expectancy_gross_pct"] > 0
                ) == (test_stats["expectancy_gross_pct"] > 0)
            if (
                discovery_stats["hit_rate_pct"] is not None
                and test_stats["hit_rate_pct"] is not None
            ):
                hit_rate_diff = test_stats["hit_rate_pct"] - discovery_stats["hit_rate_pct"]

            dims = dict(zip(_dimension_names(view), key, strict=True))
            group_rows.append(
                {
                    **dims,
                    "discovery": discovery_stats,
                    "test": test_stats,
                    "expectancy_diff_pct": expectancy_diff,
                    "expectancy_retention_ratio": retention_ratio,
                    "hit_rate_diff_pct": hit_rate_diff,
                    "sign_preserved": sign_preserved,
                    "label": label,
                }
            )
        views[view] = group_rows
    return views


def _dimension_names(view: str) -> tuple[str, ...]:
    if view == "overall":
        return ("symbol", "horizon_minutes")
    if view == "state":
        return ("symbol", "state", "direction", "horizon_minutes")
    if view == "regime":
        return ("symbol", "regime_label", "direction", "horizon_minutes")
    raise ValueError(f"unsupported gross view: {view}")


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
        SELECT observation_id, exchange, status, cost_curve
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
        result.setdefault(row["observation_id"], {})[row["exchange"]] = row
    return result


def _execution_cost_bps(
    snapshot: dict[str, Any] | None,
    *,
    size_usd: float,
    side: str,
) -> tuple[float | None, bool]:
    """Returns (market_cost_bps_vs_mid, insufficient_depth)."""

    if snapshot is None or snapshot["status"] != "valid":
        return None, True
    curve = snapshot["cost_curve"]
    if isinstance(curve, str):
        curve = json.loads(curve)
    entry = (curve or {}).get(str(int(size_usd)))
    if not entry:
        return None, True
    leg = entry.get(side)
    if not leg:
        return None, True
    cost = leg.get("market_cost_bps_vs_mid")
    insufficient = bool(leg.get("insufficient_depth"))
    return (cost if cost is not None else None), insufficient


def _build_execution_views(
    *,
    discovery_grid: list[dict[str, Any]],
    test_grid: list[dict[str, Any]],
    discovery_snapshots: dict[int, dict[str, dict[str, Any]]],
    test_snapshots: dict[int, dict[str, dict[str, Any]]],
    options: WalkForwardManifestOptions,
    fold_evaluation_ready: bool,
) -> list[dict[str, Any]]:
    discovery_rows = _actionable_evaluated(discovery_grid)
    test_rows = _actionable_evaluated(test_grid)

    def _period_groups(
        rows: list[dict[str, Any]],
        snapshots: dict[int, dict[str, dict[str, Any]]],
    ) -> dict[tuple, dict[str, Any]]:
        groups: dict[tuple, dict[str, Any]] = {}
        for row in rows:
            snap_by_exchange = snapshots.get(row["observation_id"], {})
            side = "buy" if row["direction"] == "long" else "sell"
            for exchange in options.exchanges:
                snapshot = snap_by_exchange.get(exchange)
                for size_usd in options.sizes_usd:
                    key = (row["symbol"], exchange, size_usd, row["horizon_minutes"])
                    bucket = groups.setdefault(
                        key,
                        {
                            "n_evaluated_actionable": 0,
                            "n_snapshot_present_valid": 0,
                            "n_insufficient_depth": 0,
                            "gross_returns": [],
                            "net_returns": [],
                        },
                    )
                    bucket["n_evaluated_actionable"] += 1
                    cost_bps, insufficient = _execution_cost_bps(
                        snapshot, size_usd=size_usd, side=side
                    )
                    if snapshot is not None and snapshot["status"] == "valid":
                        bucket["n_snapshot_present_valid"] += 1
                    if insufficient or cost_bps is None:
                        bucket["n_insufficient_depth"] += 1
                        continue
                    gross_bps = row["directional_return_pct"] * 100.0
                    bucket["gross_returns"].append(gross_bps)
                    bucket["net_returns"].append(gross_bps - 2.0 * cost_bps)
        return groups

    discovery_groups = _period_groups(discovery_rows, discovery_snapshots)
    test_groups = _period_groups(test_rows, test_snapshots)

    keys = sorted(
        set(discovery_groups) | set(test_groups),
        key=lambda item: (item[0], item[1], item[2], item[3]),
    )
    result: list[dict[str, Any]] = []
    for key in keys:
        symbol, exchange, size_usd, horizon = key

        def _summarize(bucket: dict[str, Any] | None) -> dict[str, Any]:
            if bucket is None:
                return {
                    "n_evaluated_actionable": 0,
                    "n_snapshot_present_valid": 0,
                    "n_insufficient_depth": 0,
                    "n_cost_evaluable": 0,
                    "gross_expectancy_bps": None,
                    "net_expectancy_bps": None,
                    "meets_min_group_n": False,
                }
            n_cost_evaluable = len(bucket["net_returns"])
            return {
                "n_evaluated_actionable": bucket["n_evaluated_actionable"],
                "n_snapshot_present_valid": bucket["n_snapshot_present_valid"],
                "n_insufficient_depth": bucket["n_insufficient_depth"],
                "n_cost_evaluable": n_cost_evaluable,
                "gross_expectancy_bps": (
                    statistics.fmean(bucket["gross_returns"]) if bucket["gross_returns"] else None
                ),
                "net_expectancy_bps": (
                    statistics.fmean(bucket["net_returns"]) if bucket["net_returns"] else None
                ),
                "meets_min_group_n": n_cost_evaluable >= options.min_group_n,
            }

        discovery_stats = _summarize(discovery_groups.get(key))
        test_stats = _summarize(test_groups.get(key))
        net_diff = None
        retention_ratio = None
        if (
            discovery_stats["net_expectancy_bps"] is not None
            and test_stats["net_expectancy_bps"] is not None
        ):
            net_diff = test_stats["net_expectancy_bps"] - discovery_stats["net_expectancy_bps"]
            if discovery_stats["net_expectancy_bps"] != 0:
                retention_ratio = (
                    test_stats["net_expectancy_bps"] / discovery_stats["net_expectancy_bps"]
                )

        result.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "size_usd": size_usd,
                "horizon_minutes": horizon,
                "discovery": discovery_stats,
                "test": test_stats,
                "net_expectancy_diff_bps": net_diff,
                "net_expectancy_retention_ratio": retention_ratio,
                "fee_bps_per_side_applied": None,
                "not_ready": not fold_evaluation_ready,
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
    blockers = await _fold_integrity_blockers(conn, fold=fold, options=options)
    summary = _fold_state_summary(fold=fold, generated_at=generated_at, blockers=blockers)

    discovery_end = fold["discovery_end"]
    discovery_grid = await _fetch_period_grid(
        conn,
        period_start=fold["discovery_start"],
        period_end=discovery_end,
        knowledge_cutoff=min(generated_at, discovery_end),
        options=options,
    )
    test_grid = await _fetch_period_grid(
        conn,
        period_start=fold["test_start"],
        period_end=fold["test_end"],
        knowledge_cutoff=generated_at,
        options=options,
    )

    discovery_integrity = _integrity_counters(discovery_grid, period_end=discovery_end)
    test_integrity = _integrity_counters(test_grid, period_end=fold["test_end"])

    gross_views = _build_gross_views(
        discovery_grid=discovery_grid,
        test_grid=test_grid,
        min_group_n=options.min_group_n,
        fold_evaluation_ready=summary["evaluation_ready"],
    )

    discovery_ids = [row["observation_id"] for row in _actionable_evaluated(discovery_grid)]
    test_ids = [row["observation_id"] for row in _actionable_evaluated(test_grid)]
    discovery_snapshots = await _fetch_execution_snapshots(
        conn, discovery_ids, execution_snapshot_version=options.execution_snapshot_version
    )
    test_snapshots = await _fetch_execution_snapshots(
        conn, test_ids, execution_snapshot_version=options.execution_snapshot_version
    )
    execution_view = _build_execution_views(
        discovery_grid=discovery_grid,
        test_grid=test_grid,
        discovery_snapshots=discovery_snapshots,
        test_snapshots=test_snapshots,
        options=options,
        fold_evaluation_ready=summary["evaluation_ready"],
    )

    return {
        **summary,
        "integrity": {
            "discovery": discovery_integrity,
            "test": test_integrity,
        },
        "gross_views": gross_views,
        "execution_view": execution_view,
    }


async def evaluate_walk_forward(
    conn: asyncpg.Connection,
    manifest_name: str,
    options: WalkForwardManifestOptions | None = None,
) -> dict[str, Any]:
    """Stage B (Evaluate): read-only, hash-verified walk-forward report.

    Caller must run this inside a ``REPEATABLE READ READ ONLY`` transaction.
    This function performs no INSERT/UPDATE/DELETE/DDL of its own.
    """

    manifest = await load_walk_forward_manifest(conn, manifest_name)
    spec = manifest["spec"]
    opts = options or WalkForwardManifestOptions(
        name=manifest["manifest_name"],
        warmup_days=manifest["warmup_days"],
        test_days=manifest["test_days"],
        fold_count=manifest["fold_count"],
        min_group_n=manifest["min_group_n"],
        horizons=tuple(spec["horizons_minutes"]),
        sampling_modes=tuple(spec["sampling_modes"]),
        symbols=tuple(spec["symbols"]),
        exchanges=tuple(spec["execution_exchanges"]),
        sizes_usd=tuple(spec["execution_sizes_usd"]),
        fee_bps_per_side=tuple(sorted(spec["fee_bps_per_side"].items())),
        logic_version=spec["versions"]["logic_version"],
        evidence_version=spec["versions"]["evidence_version"],
        sampling_version=spec["versions"]["sampling_version"],
        context_version=spec["versions"]["context_version"],
        outcome_version=spec["versions"]["outcome_version"],
        execution_snapshot_version=spec["versions"]["execution_snapshot_version"],
    )

    generated_at = _aware_utc(await conn.fetchval("SELECT clock_timestamp()"))

    folds = []
    for fold in manifest["folds"]:
        fold_dt = {
            "fold_index": fold["fold_index"],
            "discovery_start": _parse_iso(fold["discovery_start"]),
            "discovery_end": _parse_iso(fold["discovery_end"]),
            "test_start": _parse_iso(fold["test_start"]),
            "test_end": _parse_iso(fold["test_end"]),
            "test_maturity_at": _parse_iso(fold["test_maturity_at"]),
        }
        folds.append(await _evaluate_fold(conn, fold=fold_dt, generated_at=generated_at, options=opts))

    ready_by_clock_fold_count = sum(1 for fold in folds if fold["clock_state"] == "ready_by_clock")
    evaluation_ready_fold_count = sum(1 for fold in folds if fold["evaluation_ready"])
    first_oos_cutoff_in_future = manifest["cutoff_at"] > generated_at

    return {
        "report_version": WALK_FORWARD_REPORT_VERSION,
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
        },
        "first_oos_cutoff_in_future": first_oos_cutoff_in_future,
        "ready_by_clock_fold_count": ready_by_clock_fold_count,
        "evaluation_ready_fold_count": evaluation_ready_fold_count,
        "folds": folds,
        "execution_contract": {
            "source": "signal_execution_snapshot (PR10 immutable)",
            "reads_current_orderbook_depth": False,
            "round_trip_market_model": "symmetric_entry_book_v1",
            "funding_modeled": False,
            "min_execution_coverage_pct": None,
        },
        "methodology": {
            "gross_views": list(GROSS_VIEWS),
            "no_ranking_or_winner_selection": True,
            "live_scoring_changes": False,
        },
    }


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _aware_utc(value)
    return _aware_utc(datetime.fromisoformat(value))
