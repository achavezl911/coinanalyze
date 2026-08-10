from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from app.scalp_logic import compute_scalp_summary

SCALP_SIGNAL_LOGIC_VERSION = "scalp-summary-v1"
REPLAY_CONTEXT_VERSION = 1


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
    expected_evidence_hash: str
    replayed_evidence_hash: str
    replayed_summary: dict[str, Any]


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


async def replay_signal_observation(
    conn: asyncpg.Connection,
    observation_id: int,
) -> ReplayResult:
    """Recompute one historical live decision from its frozen input frame."""

    row = await conn.fetchrow(
        """
        SELECT
          obs.observation_id,
          obs.logic_version,
          obs.evidence,
          frame.frame_id,
          frame.context_version,
          frame.context_hash,
          frame.context
        FROM signal_observation AS obs
        LEFT JOIN signal_replay_frame AS frame
          ON frame.observation_id=obs.observation_id
        WHERE obs.observation_id=$1
        """,
        observation_id,
    )
    if row is None:
        raise LookupError(f"signal observation {observation_id} does not exist")
    if row["frame_id"] is None:
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
    context_hash_valid = hmac.compare_digest(
        stored_context_hash,
        computed_context_hash,
    )
    if not context_hash_valid:
        raise ReplayIntegrityError(
            f"replay context hash mismatch for observation {observation_id}"
        )

    logic_version = str(row["logic_version"])
    replayed = replay_summary_for_logic(logic_version, context)
    expected = _decode_json_object(row["evidence"], "signal evidence")

    expected_hash = canonical_json_hash(expected)
    replayed_hash = canonical_json_hash(replayed)

    return ReplayResult(
        observation_id=int(row["observation_id"]),
        logic_version=logic_version,
        context_version=context_version,
        context_hash_valid=True,
        evidence_match=hmac.compare_digest(expected_hash, replayed_hash),
        expected_evidence_hash=expected_hash,
        replayed_evidence_hash=replayed_hash,
        replayed_summary=replayed,
    )
