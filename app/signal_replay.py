from __future__ import annotations

import hashlib
import hmac
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from app.scalp_logic import compute_scalp_summary

# PR27_SCIENTIFIC_SIGNAL_REPLAY_V1_BEGIN

SCALP_SIGNAL_LOGIC_VERSION = "scalp-summary-v1"
REPLAY_CONTEXT_VERSION = 1

_LONG_STATES = frozenset({"Long Momentum", "Long Pullback"})
_SHORT_STATES = frozenset({"Short Momentum", "Short Rejection"})
_NEUTRAL_STATES = frozenset({"No Trade"})


class ReplayIntegrityError(RuntimeError):
    pass


class ReplayUnsupportedLogicVersion(RuntimeError):
    pass


class ReplayUnsupportedContextVersion(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReplayResult:
    observation_id: int
    logic_version: str
    context_version: int
    context_hash_valid: bool
    evidence_match: bool
    observation_fields_match: bool
    mismatched_observation_fields: tuple[str, ...]
    expected_evidence_hash: str
    replayed_evidence_hash: str
    replayed_summary: dict[str, Any]


def _decision_finite(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) else None


def classify_signal_observation(
    summary: dict[str, Any],
) -> tuple[str, str, bool]:
    """Map one replayable scalp verdict to its persisted research label."""

    state = str(summary.get("state") or "").strip()
    book_status = str(summary.get("book_status") or "missing").strip()
    coverage = _decision_finite(summary.get("evidence_coverage_pct"))

    if (
        state == "Sin datos suficientes"
        or book_status != "ok"
        or coverage is None
        or coverage < 50.0
    ):
        return "not_evaluable", "unavailable", False
    if state in _LONG_STATES:
        return "evaluable", "long", True
    if state in _SHORT_STATES:
        return "evaluable", "short", True
    if state in _NEUTRAL_STATES:
        return "evaluable", "neutral", False
    return "not_evaluable", "unavailable", False


def validated_signal_observation_fields(
    summary: dict[str, Any],
) -> tuple[str, str, str, float, float, float]:
    """Validate the summary fields copied into ``signal_observation``."""

    state = str(summary.get("state") or "").strip()
    confidence = str(summary.get("confidence") or "").strip()
    reason = str(summary.get("reason") or "").strip()
    long_score = _decision_finite(summary.get("long_score"))
    short_score = _decision_finite(summary.get("short_score"))
    coverage = _decision_finite(summary.get("evidence_coverage_pct"))

    if not state or len(state) > 80:
        raise ValueError("signal state is missing or too long")
    if confidence not in {"baja", "media", "alta"}:
        raise ValueError("signal confidence is invalid")
    if not reason or len(reason) > 500:
        raise ValueError("signal reason is missing or too long")
    if long_score is None or not 0 <= long_score <= 100:
        raise ValueError("long_score is invalid")
    if short_score is None or not 0 <= short_score <= 100:
        raise ValueError("short_score is invalid")
    if coverage is None or not 0 <= coverage <= 100:
        raise ValueError("evidence_coverage_pct is invalid")

    return state, confidence, reason, long_score, short_score, coverage


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def canonical_json_object(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise TypeError("canonical replay payload must be a JSON object")
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
    )


def canonical_json_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json_object(payload).encode("utf-8")).hexdigest()


def _decode_json_object(value: object, name: str) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (str, bytes, bytearray)):
        decoded = json.loads(value)
        if isinstance(decoded, dict):
            return decoded
    raise ReplayIntegrityError(f"{name} is not a JSON object")


def replay_context_as_of(context: dict[str, Any]) -> datetime:
    value = context.get("now_ms")
    try:
        milliseconds = float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        milliseconds = None
    if milliseconds is None or not math.isfinite(milliseconds) or milliseconds < 0:
        raise ValueError("replay context requires finite non-negative now_ms")
    try:
        return datetime.fromtimestamp(milliseconds / 1000.0, UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise ValueError("replay context now_ms is outside datetime range") from exc


async def persist_signal_replay_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    context: dict[str, Any],
) -> int:
    """Freeze the exact decision inputs for one immutable PR4 observation.

    The caller owns the transaction. A frame failure is therefore allowed to
    roll back the research observation/savepoint while leaving the operational
    scalp snapshot isolated by the collector's outer savepoint policy.
    """

    if observation_id <= 0:
        raise ValueError("observation_id must be positive")

    context_as_of = replay_context_as_of(context)
    payload = canonical_json_object(context)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    row = await conn.fetchrow(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context
        ) VALUES($1,$2,$3,$4,$5::jsonb)
        ON CONFLICT(observation_id) DO NOTHING
        RETURNING frame_id
        """,
        observation_id,
        REPLAY_CONTEXT_VERSION,
        context_as_of,
        digest,
        payload,
    )
    if row is not None:
        return 1

    existing = await conn.fetchrow(
        """
        SELECT context_version,context_hash
        FROM signal_replay_frame
        WHERE observation_id=$1
        """,
        observation_id,
    )
    if (
        existing is None
        or int(existing["context_version"]) != REPLAY_CONTEXT_VERSION
        or not hmac.compare_digest(str(existing["context_hash"]), digest)
    ):
        raise ReplayIntegrityError(
            "observation_id already has a different replay frame"
        )
    return 0


def replay_summary_for_logic(
    logic_version: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Replay only explicitly supported decision kernels.

    PR6 intentionally supports the current v1 kernel. A future material change
    must preserve/register the old implementation or fail closed rather than
    silently relabel historical frames with new logic.
    """

    if logic_version != SCALP_SIGNAL_LOGIC_VERSION:
        raise ReplayUnsupportedLogicVersion(
            f"unsupported replay logic version: {logic_version}"
        )
    return compute_scalp_summary(context)


def validate_replay_observation_record(
    record: asyncpg.Record | dict[str, Any],
) -> ReplayResult:
    """Validate one already-fetched immutable observation and replay frame."""

    row = dict(record)
    observation_id = int(row["observation_id"])
    if row.get("frame_id") is None:
        raise LookupError(
            f"signal observation {observation_id} has no replay frame"
        )

    context_version = int(row["context_version"])
    if context_version != REPLAY_CONTEXT_VERSION:
        raise ReplayUnsupportedContextVersion(
            f"unsupported replay context version: {context_version}"
        )

    context = _decode_json_object(row["context"], "replay context")
    stored_context_hash = str(row["context_hash"])
    computed_context_hash = canonical_json_hash(context)
    if not hmac.compare_digest(stored_context_hash, computed_context_hash):
        raise ReplayIntegrityError(
            f"replay context hash mismatch for observation {observation_id}"
        )

    logic_version = str(row["logic_version"])
    replayed = replay_summary_for_logic(logic_version, context)
    expected = _decode_json_object(row["evidence"], "signal evidence")
    expected_hash = canonical_json_hash(expected)
    replayed_hash = canonical_json_hash(replayed)

    decision_status, direction, actionable = classify_signal_observation(replayed)
    state, confidence, reason, long_score, short_score, coverage = (
        validated_signal_observation_fields(replayed)
    )
    expected_fields: tuple[tuple[str, object], ...] = (
        ("decision_status", decision_status),
        ("direction", direction),
        ("actionable", actionable),
        ("state", state),
        ("confidence", confidence),
        ("reason", reason),
        ("long_score", long_score),
        ("short_score", short_score),
        ("evidence_coverage_pct", coverage),
    )
    mismatches: list[str] = []
    for field, expected_value in expected_fields:
        actual_value = row.get(field)
        if isinstance(expected_value, float):
            actual_value = _decision_finite(actual_value)
        if actual_value != expected_value:
            mismatches.append(field)

    return ReplayResult(
        observation_id=observation_id,
        logic_version=logic_version,
        context_version=context_version,
        context_hash_valid=True,
        evidence_match=hmac.compare_digest(expected_hash, replayed_hash),
        observation_fields_match=not mismatches,
        mismatched_observation_fields=tuple(mismatches),
        expected_evidence_hash=expected_hash,
        replayed_evidence_hash=replayed_hash,
        replayed_summary=replayed,
    )


async def replay_signal_observations(
    conn: asyncpg.Connection,
    observation_ids: Sequence[int],
) -> list[ReplayResult]:
    """Batch-replay observations without one query per scientific row."""

    normalized_ids = sorted({int(value) for value in observation_ids})
    if any(value <= 0 for value in normalized_ids):
        raise ValueError("observation ids must be positive")
    if not normalized_ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
          obs.observation_id,
          obs.logic_version,
          obs.decision_status,
          obs.direction,
          obs.actionable,
          obs.state,
          obs.confidence,
          obs.reason,
          obs.long_score,
          obs.short_score,
          obs.evidence_coverage_pct,
          obs.evidence,
          frame.frame_id,
          frame.context_version,
          frame.context_hash,
          frame.context
        FROM signal_observation AS obs
        LEFT JOIN signal_replay_frame AS frame
          ON frame.observation_id=obs.observation_id
        WHERE obs.observation_id=ANY($1::bigint[])
        ORDER BY obs.observation_id
        """,
        normalized_ids,
    )
    found_ids = {int(row["observation_id"]) for row in rows}
    missing_ids = sorted(set(normalized_ids) - found_ids)
    if missing_ids:
        raise LookupError(
            f"signal observations do not exist: {missing_ids}"
        )
    return [validate_replay_observation_record(row) for row in rows]


async def replay_signal_observation(
    conn: asyncpg.Connection,
    observation_id: int,
) -> ReplayResult:
    """Recompute one historical live decision from its frozen input frame."""
    results = await replay_signal_observations(conn, [observation_id])
    return results[0]


# PR27_SCIENTIFIC_SIGNAL_REPLAY_V1_END
