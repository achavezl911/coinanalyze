from __future__ import annotations

# PR27_SCIENTIFIC_VISIBILITY_CERTIFICATION_V1_BEGIN
from dataclasses import dataclass
from datetime import UTC, datetime

import asyncpg

from app.db import ServiceOwnership, fenced_transaction
from app.signal_scientific_identity import scientific_implementation_identity

# ---------------------------------------------------------------------------
# PR25: research knowledge-time visibility certification.
#
# A3-01 fix. PR11 must never treat a pre-commit timestamp (created_at,
# finalized_at) as proof that a row was historically knowable: those columns
# are populated with clock_timestamp() BEFORE the enclosing collector
# transaction commits, so a fixed historical cutoff can fall after the stored
# timestamp but before the actual COMMIT. This module adds a NEW, ADDITIVE,
# APPEND-ONLY certification contract instead of reinterpreting those columns.
#
# verified_visible_at means: "a later transaction successfully read the
# already-committed source state, and only AFTER that successful read
# obtained this PostgreSQL clock timestamp." It is a conservative upper bound
# proving the source was externally visible no later than verified_visible_at.
# It is NOT a PostgreSQL commit timestamp and must never be documented as one.
#
# The timestamp sequence is always:
#   1. a NEW transaction starts, strictly after the source-writing
#      transaction has already committed
#   2. SELECT and validate the committed source state (candidate selection)
#   3. SELECT clock_timestamp()
#   4. INSERT the append-only certificate
# Never the reverse: clock_timestamp() is never read before the source SELECT.
#
# RESEARCH_VISIBILITY_VERSION = 1 certifies exactly ONE frozen scientific
# tuple, hardcoded below rather than imported from each module's "current"
# constant. This is deliberate: if evidence_version, context_version,
# outcome_version, execution_snapshot_version, the outcome horizon grid or
# the execution exchange set advance again in a future PR, this module must
# NOT silently start certifying the new shape under the same
# visibility_version -- a new RESEARCH_VISIBILITY_VERSION and a new frozen
# shape must be defined explicitly, exactly like PR11 spec v2's tuple. There
# is no v1-v5 backfill: RESEARCH_VISIBILITY_VERSION=1 only ever applies to
# evidence_version=6, the frozen horizon grid and the frozen exchange set
# below.
# ---------------------------------------------------------------------------

RESEARCH_VISIBILITY_VERSION = 1

_CERTIFIED_EVIDENCE_VERSION = 6
_CERTIFIED_CONTEXT_VERSION = 1
_CERTIFIED_OUTCOME_VERSION = 1
_CERTIFIED_EXECUTION_SNAPSHOT_VERSION = 1

# Frozen v1 bundle-completeness shape. Literal, not imported from
# app.signal_outcomes.OUTCOME_HORIZONS_MINUTES / app.signal_execution.
# EXECUTION_EXCHANGES: a future horizon or exchange change must define a new
# visibility contract/version instead of silently changing what
# visibility_version=1 certifies.
_CERTIFIED_OUTCOME_HORIZONS: tuple[int, ...] = (1, 3, 5, 15, 30, 60, 120, 240)
_CERTIFIED_EXECUTION_EXCHANGES: tuple[str, ...] = ("binance", "bybit")

DEFAULT_CERTIFICATION_BATCH_SIZE = 500


@dataclass(frozen=True, slots=True)
class CertificationCycleResult:
    bundles_certified: int
    final_outcomes_certified: int


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _validate_batch_size(batch_size: int) -> None:
    if not 1 <= batch_size <= 10_000:
        raise ValueError("batch_size must be between 1 and 10000")


def _require_new_certification_transaction(conn: asyncpg.Connection) -> None:
    if conn.is_in_transaction():
        raise RuntimeError(
            "research visibility certification must own a new transaction"
        )


async def _certify_research_bundles_once(
    conn: asyncpg.Connection,
    *,
    batch_size: int,
) -> int:
    """One bounded, idempotent pass. Caller must already hold a NEW transaction.

    Selects complete v6 research bundles (observation + replay frame + every
    scheduled outcome horizon + both execution venues) not yet certified,
    reads the PostgreSQL clock only AFTER that read, then appends certificate
    rows. An incomplete bundle is silently skipped this pass -- it becomes
    eligible on a later run once the rest of the bundle has committed.
    """

    candidates = await conn.fetch(
        """
        SELECT obs.observation_id
        FROM signal_observation AS obs
        WHERE obs.signal_family='scalp'
          AND obs.is_periodic
          AND obs.evidence_version=$1
          AND NOT EXISTS (
            SELECT 1 FROM signal_research_bundle_visibility AS v
            WHERE v.observation_id=obs.observation_id
              AND v.visibility_version=$2
          )
          AND EXISTS (
            SELECT 1 FROM signal_replay_frame AS frame
            WHERE frame.observation_id=obs.observation_id
              AND frame.context_version=$3
          )
          AND (
            SELECT COUNT(DISTINCT out.horizon_minutes)
            FROM signal_outcome AS out
            WHERE out.observation_id=obs.observation_id
              AND out.outcome_version=$4
              AND out.horizon_minutes=ANY($5::integer[])
          ) = $6
          AND (
            SELECT COUNT(DISTINCT snap.exchange)
            FROM signal_execution_snapshot AS snap
            WHERE snap.observation_id=obs.observation_id
              AND snap.snapshot_version=$7
              AND snap.exchange=ANY($8::text[])
          ) = $9
        ORDER BY obs.observation_id
        LIMIT $10
        """,
        _CERTIFIED_EVIDENCE_VERSION,
        RESEARCH_VISIBILITY_VERSION,
        _CERTIFIED_CONTEXT_VERSION,
        _CERTIFIED_OUTCOME_VERSION,
        list(_CERTIFIED_OUTCOME_HORIZONS),
        len(_CERTIFIED_OUTCOME_HORIZONS),
        _CERTIFIED_EXECUTION_SNAPSHOT_VERSION,
        list(_CERTIFIED_EXECUTION_EXCHANGES),
        len(_CERTIFIED_EXECUTION_EXCHANGES),
        batch_size,
    )
    if not candidates:
        return 0
    observation_ids = [int(row["observation_id"]) for row in candidates]

    verified_visible_at = await conn.fetchval("SELECT clock_timestamp()")
    if not isinstance(verified_visible_at, datetime):
        raise RuntimeError("PostgreSQL did not return a timestamp")
    verified_visible_at = _aware_utc(verified_visible_at)

    inserted = await conn.fetch(
        """
        INSERT INTO signal_research_bundle_visibility(
          observation_id,visibility_version,evidence_version,context_version,
          outcome_version,execution_snapshot_version,verified_visible_at
        )
        SELECT t.observation_id,$2,$3,$4,$5,$6,$7::timestamptz
        FROM unnest($1::bigint[]) AS t(observation_id)
        ON CONFLICT (observation_id,visibility_version) DO NOTHING
        RETURNING bundle_visibility_id
        """,
        observation_ids,
        RESEARCH_VISIBILITY_VERSION,
        _CERTIFIED_EVIDENCE_VERSION,
        _CERTIFIED_CONTEXT_VERSION,
        _CERTIFIED_OUTCOME_VERSION,
        _CERTIFIED_EXECUTION_SNAPSHOT_VERSION,
        verified_visible_at,
    )
    return len(inserted)


async def _certify_final_outcomes_once(
    conn: asyncpg.Connection,
    *,
    batch_size: int,
) -> int:
    """One bounded, idempotent pass. Caller must already hold a NEW transaction.

    Only certifies final state (evaluated/not_evaluable) for outcomes owned
    by an evidence_version=6 observation. Never certifies v1-v5 outcomes.
    """

    candidates = await conn.fetch(
        """
        SELECT out.outcome_id, out.status, out.finalized_at
        FROM signal_outcome AS out
        JOIN signal_observation AS obs
          ON obs.observation_id=out.observation_id
        WHERE out.outcome_version=$1
          AND out.status IN ('evaluated','not_evaluable')
          AND obs.evidence_version=$2
          AND NOT EXISTS (
            SELECT 1 FROM signal_outcome_final_visibility AS v
            WHERE v.outcome_id=out.outcome_id
              AND v.visibility_version=$3
          )
        ORDER BY out.outcome_id
        LIMIT $4
        """,
        _CERTIFIED_OUTCOME_VERSION,
        _CERTIFIED_EVIDENCE_VERSION,
        RESEARCH_VISIBILITY_VERSION,
        batch_size,
    )
    if not candidates:
        return 0

    outcome_ids: list[int] = []
    statuses: list[str] = []
    finalized_ats: list[datetime] = []
    for row in candidates:
        finalized_at = row["finalized_at"]
        if not isinstance(finalized_at, datetime):
            # The signal_outcome CHECK constraint guarantees evaluated/
            # not_evaluable rows always carry finalized_at. Never certify on
            # an assumption if that ever fails to hold -- skip, retry later.
            continue
        outcome_ids.append(int(row["outcome_id"]))
        statuses.append(str(row["status"]))
        finalized_ats.append(_aware_utc(finalized_at))
    if not outcome_ids:
        return 0

    verified_visible_at = await conn.fetchval("SELECT clock_timestamp()")
    if not isinstance(verified_visible_at, datetime):
        raise RuntimeError("PostgreSQL did not return a timestamp")
    verified_visible_at = _aware_utc(verified_visible_at)

    inserted = await conn.fetch(
        """
        INSERT INTO signal_outcome_final_visibility(
          outcome_id,visibility_version,outcome_version,source_status,
          source_finalized_at,verified_visible_at
        )
        SELECT t.outcome_id,$2,$3,t.source_status,t.source_finalized_at,$4::timestamptz
        FROM unnest($1::bigint[],$5::text[],$6::timestamptz[])
          AS t(outcome_id,source_status,source_finalized_at)
        ON CONFLICT (outcome_id,visibility_version) DO NOTHING
        RETURNING final_visibility_id
        """,
        outcome_ids,
        RESEARCH_VISIBILITY_VERSION,
        _CERTIFIED_OUTCOME_VERSION,
        verified_visible_at,
        statuses,
        finalized_ats,
    )
    return len(inserted)


async def certify_research_bundles(
    conn: asyncpg.Connection,
    *,
    ownership: ServiceOwnership | None = None,
    batch_size: int = DEFAULT_CERTIFICATION_BATCH_SIZE,
) -> int:
    """Certify a bounded batch of complete v6 research bundles.

    Opens exactly one NEW transaction here -- the caller must invoke this
    only after any source-writing transaction has already exited/committed.
    Safe to retry: unqualified/incomplete bundles are simply skipped, and
    ON CONFLICT DO NOTHING makes a repeated pass over the same rows a no-op.
    """

    _validate_batch_size(batch_size)
    _require_new_certification_transaction(conn)
    scientific_implementation_identity()
    async with fenced_transaction(conn, ownership):
        return await _certify_research_bundles_once(conn, batch_size=batch_size)


async def certify_final_outcomes(
    conn: asyncpg.Connection,
    *,
    ownership: ServiceOwnership | None = None,
    batch_size: int = DEFAULT_CERTIFICATION_BATCH_SIZE,
) -> int:
    """Certify a bounded batch of final (evaluated/not_evaluable) v6 outcomes.

    Same transaction/idempotency contract as certify_research_bundles.
    """

    _validate_batch_size(batch_size)
    _require_new_certification_transaction(conn)
    scientific_implementation_identity()
    async with fenced_transaction(conn, ownership):
        return await _certify_final_outcomes_once(conn, batch_size=batch_size)


async def run_certification_cycle(
    conn: asyncpg.Connection,
    *,
    ownership: ServiceOwnership | None = None,
    batch_size: int = DEFAULT_CERTIFICATION_BATCH_SIZE,
) -> CertificationCycleResult:
    """Run one bundle-certification pass and one final-outcome-certification pass.

    Each pass is its own distinct transaction (see certify_research_bundles /
    certify_final_outcomes). A failure in one pass does not roll back the
    other, and neither pass ever touches already-committed source evidence --
    only this module's own append-only certificate tables.
    """

    bundles = await certify_research_bundles(
        conn, ownership=ownership, batch_size=batch_size
    )
    final_outcomes = await certify_final_outcomes(
        conn, ownership=ownership, batch_size=batch_size
    )
    return CertificationCycleResult(
        bundles_certified=bundles,
        final_outcomes_certified=final_outcomes,
    )


# PR27_SCIENTIFIC_VISIBILITY_CERTIFICATION_V1_END
