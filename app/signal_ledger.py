from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, date, datetime
from typing import Any

import asyncpg

from app.metrics import REGIME_LOGIC_VERSION
from app.signal_execution import (
    load_signal_execution_inputs,
    persist_signal_execution_snapshots,
)
from app.signal_outcomes import schedule_signal_outcomes
from app.signal_replay import (
    SCALP_SIGNAL_LOGIC_VERSION,
    persist_signal_replay_frame,
    replay_context_as_of,
)

SIGNAL_FAMILY = "scalp"
# PR25: v6 is the first evidence cohort eligible for the post-commit research
# visibility contract (app.signal_visibility.RESEARCH_VISIBILITY_VERSION=1).
# v1-v5 remain historical under their original publication-time semantics;
# this bump is prospective only, no existing row is reinterpreted.
# K64, 2026-08-30: v7 es la primera cohorte escrita con la logica de regimen 3 -- el
# componente whale ABSTENIENDOSE en vez de votar cero, que cambio lo que el score
# significa el 2026-08-27T04:43:05Z. Sube la EVIDENCIA y no solo el regimen porque el
# mapa congelado de signal_regime.py:40 clava 6 -> 2, y tiene que seguir clavandolo: v6
# se publico bajo la regla vieja y reinterpretarla seria mentir sobre 129252 filas.
# Prospectivo: ninguna fila existente se reinterpreta.
#
# LO QUE NO SUBE, Y NO ES UN OLVIDO. Dos contratos siguen en 6 porque su propio
# comentario dice que NO deben moverse:
#   signal_walk_forward.SPEC_V2_SUPPORTED_EVIDENCE_VERSION -- una semantica cientifica
#     nueva exige una spec v3 explicita, no heredar la constante viva. La v7 no se
#     evaluara con spec v2 hasta que exista esa spec, y eso es la garantia, no el fallo.
#   signal_visibility._CERTIFIED_EVIDENCE_VERSION -- su tupla congelada es la que el
#     CHECK signal_research_bundle_visibility_pr25_frozen_tuple_check exige. K25 pide
#     literalmente "0 certificados apuntando a evidence_version<>6", asi que dejarla
#     quieta lo mantiene coherente. Las observaciones de v7 NO se certificaran todavia.
SIGNAL_EVIDENCE_VERSION = 7
SIGNAL_SAMPLING_VERSION = 1

_LONG_STATES = frozenset({"Long Momentum", "Long Pullback"})
_SHORT_STATES = frozenset({"Short Momentum", "Short Rejection"})
_NEUTRAL_STATES = frozenset({"No Trade"})


def _finite(value: object) -> float | None:
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
    """Map the live verdict to explicit research semantics.

    ``No Trade`` is not always a measured neutral decision: the current scalp
    logic also uses it as a fail-closed result when the order book is stale or
    missing. Research must keep those cases separate.
    """

    state = str(summary.get("state") or "").strip()
    book_status = str(summary.get("book_status") or "missing").strip()
    coverage = _finite(summary.get("evidence_coverage_pct"))

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

    # Future states must never silently become neutral training labels.
    return "not_evaluable", "unavailable", False


def select_reference_price(
    ctx: dict[str, Any],
    summary: dict[str, Any],
) -> tuple[float | None, str | None, datetime | None]:
    """Choose a truthful futures-signal reference price.

    A realtime futures price is usable only when the already-published
    ``basis_detail`` says that futures leg is fresh. If it is absent/stale, the
    fallback is the explicit latest closed futures OHLCV leg exposed by
    ``scalp_context``. Spot is never substituted.
    """

    futures_price = _finite(summary.get("fut_price"))
    basis_detail = summary.get("basis_detail")
    fut_age = (
        _finite(basis_detail.get("fut_age_seconds"))
        if isinstance(basis_detail, dict)
        else None
    )
    stale_after = (
        _finite(basis_detail.get("stale_after_seconds"))
        if isinstance(basis_detail, dict)
        else None
    )
    futures_fresh = (
        fut_age is not None
        and stale_after is not None
        and stale_after > 0
        and -0.5 <= fut_age <= stale_after
    )
    if futures_price is not None and futures_price > 0 and futures_fresh:
        event_ms = _finite(ctx.get("fut_event_ms"))
        event_at = (
            datetime.fromtimestamp(event_ms / 1000.0, UTC)
            if event_ms is not None and event_ms >= 0
            else None
        )
        if event_at is not None:
            return futures_price, "futures_realtime_combined", event_at

    # ctx["price"] is COALESCE(realtime futures, OHLCV). If a stale futures row
    # exists, using that field here would relabel stale realtime as closed OHLCV.
    closed_price = _finite(ctx.get("ohlcv_price"))
    closed_at = ctx.get("ohlcv_price_at")
    if isinstance(closed_at, datetime) and closed_at.tzinfo is not None:
        closed_at = closed_at.astimezone(UTC)
    else:
        closed_at = None
    context_ms = _finite(ctx.get("now_ms"))
    context_as_of = (
        datetime.fromtimestamp(context_ms / 1000.0, UTC)
        if context_ms is not None and context_ms >= 0
        else None
    )
    if (
        closed_price is not None
        and closed_price > 0
        and closed_at is not None
        and (context_as_of is None or closed_at <= context_as_of)
    ):
        return closed_price, "ohlcv_1min_latest_closed", closed_at

    return None, None, None


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def serialize_signal_evidence(summary: dict[str, Any]) -> str:
    """Canonical JSON for immutable decision-time evidence."""

    return json.dumps(
        summary,
        ensure_ascii=False,
        allow_nan=False,
        default=_json_default,
        sort_keys=True,
        separators=(",", ":"),
    )


def decision_fingerprint(
    decision_status: str,
    direction: str,
    actionable: bool,
    state: str,
    confidence: str,
) -> str:
    """Fingerprint semantic transitions, not score/evidence noise."""

    material = "\x1f".join(
        (
            SCALP_SIGNAL_LOGIC_VERSION,
            decision_status,
            direction,
            "1" if actionable else "0",
            state,
            confidence,
        )
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _validated_required_fields(
    summary: dict[str, Any],
) -> tuple[str, str, str, float, float, float]:
    state = str(summary.get("state") or "").strip()
    confidence = str(summary.get("confidence") or "").strip()
    reason = str(summary.get("reason") or "").strip()
    long_score = _finite(summary.get("long_score"))
    short_score = _finite(summary.get("short_score"))
    coverage = _finite(summary.get("evidence_coverage_pct"))

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


async def persist_signal_observations(
    conn: asyncpg.Connection,
    symbol: str,
    ctx: dict[str, Any],
    summary: dict[str, Any],
    *,
    collector_generation: int | None,
    collector_shard_index: int,
    collector_shard_count: int,
) -> int:
    """Append durable research evidence for one live scalp evaluation.

    Sampling is hybrid:
      * periodic: at most one row/symbol/UTC minute, including neutral and
        non-evaluable states, to avoid selection bias;
      * transition: a row when the semantic decision fingerprint changes, so a
        short-lived signal is not lost between minute samples.

    One row may satisfy both reasons. No UPDATE or historical backfill occurs.
    The caller is expected to run inside the existing ServiceOwnership-fenced
    transaction.
    """

    if collector_shard_index < 0 or collector_shard_count <= 0:
        raise ValueError("collector shard metadata is invalid")
    if collector_shard_index >= collector_shard_count:
        raise ValueError("collector shard index must be below shard count")
    if collector_generation is not None and collector_generation <= 0:
        raise ValueError("collector generation must be positive")

    state, confidence, reason, long_score, short_score, coverage = (
        _validated_required_fields(summary)
    )
    decision_status, direction, actionable = classify_signal_observation(summary)
    fingerprint = decision_fingerprint(
        decision_status,
        direction,
        actionable,
        state,
        confidence,
    )
    reference_price, reference_source, reference_at = select_reference_price(ctx, summary)
    evidence = serialize_signal_evidence(summary)

    # Freeze every committed DB input first. The observation clock is read only
    # after these statements, so a row committed between the provenance read
    # and observed_at cannot be retroactively associated with this observation.
    context_as_of = replay_context_as_of(ctx)
    metrics = await conn.fetchrow(
        """
        SELECT ts,regime_score,regime_label,regime_logic_version,
               price_cutoff_at,metrics_cutoff_at
        FROM metrics_snapshot
        WHERE symbol=$1 AND ts <= $2
          AND regime_logic_version=$3
        ORDER BY ts DESC
        LIMIT 1
        """,
        symbol,
        context_as_of,
        REGIME_LOGIC_VERSION,
    )
    execution_inputs = await load_signal_execution_inputs(conn, symbol)

    # PostgreSQL is the sampling and knowledge clock. Host clock skew cannot
    # create minute slots or provenance timestamps that disagree with DB state.
    observed_at = await conn.fetchval("SELECT clock_timestamp()")
    if not isinstance(observed_at, datetime):
        raise RuntimeError("PostgreSQL did not return a timestamp")
    observed_at = (
        observed_at.replace(tzinfo=UTC)
        if observed_at.tzinfo is None
        else observed_at.astimezone(UTC)
    )
    observed_minute = observed_at.replace(second=0, microsecond=0)

    sampling_state = await conn.fetchrow(
        """
        SELECT
          EXISTS(
            SELECT 1
            FROM signal_observation
            WHERE symbol=$1
              AND signal_family=$2
              AND is_periodic
              AND observed_minute=$3
          ) AS periodic_exists,
          (
            SELECT decision_fingerprint
            FROM signal_observation
            WHERE symbol=$1 AND signal_family=$2
            ORDER BY observed_at DESC, observation_id DESC
            LIMIT 1
          ) AS latest_fingerprint
        """,
        symbol,
        SIGNAL_FAMILY,
        observed_minute,
    )
    periodic_exists = bool(sampling_state and sampling_state["periodic_exists"])
    latest_fingerprint = (
        str(sampling_state["latest_fingerprint"])
        if sampling_state and sampling_state["latest_fingerprint"] is not None
        else None
    )
    write_periodic = not periodic_exists
    write_transition = latest_fingerprint is not None and latest_fingerprint != fingerprint

    if not write_periodic and not write_transition:
        return 0

    common = (
        observed_at,
        observed_minute,
        symbol,
        SIGNAL_FAMILY,
        SCALP_SIGNAL_LOGIC_VERSION,
        SIGNAL_EVIDENCE_VERSION,
        SIGNAL_SAMPLING_VERSION,
        decision_status,
        direction,
        actionable,
        state,
        confidence,
        reason,
        reference_price,
        reference_source,
        reference_at,
        long_score,
        short_score,
        coverage,
        metrics["ts"] if metrics else None,
        metrics["regime_score"] if metrics else None,
        metrics["regime_label"] if metrics else None,
        metrics["regime_logic_version"] if metrics else None,
        metrics["price_cutoff_at"] if metrics else None,
        metrics["metrics_cutoff_at"] if metrics else None,
        collector_generation,
        collector_shard_index,
        collector_shard_count,
        fingerprint,
    )
    row = await conn.fetchrow(
        """
        INSERT INTO signal_observation(
          observed_at,observed_minute,symbol,signal_family,is_periodic,is_transition,
          logic_version,evidence_version,sampling_version,
          decision_status,direction,actionable,state,confidence,reason,
          reference_price,reference_price_source,reference_price_at,
          long_score,short_score,evidence_coverage_pct,
          metrics_snapshot_ts,regime_score,regime_label,regime_logic_version,
          price_cutoff_at,metrics_cutoff_at,
          collector_generation,collector_shard_index,collector_shard_count,
          decision_fingerprint,evidence
        ) VALUES(
          $1,$2,$3,$4,$30,$31,
          $5,$6,$7,
          $8,$9,$10,$11,$12,$13,
          $14,$15,$16,
          $17,$18,$19,
          $20,$21,$22,$23,$24,$25,
          $26,$27,$28,$29,$32::jsonb
        )
        ON CONFLICT DO NOTHING
        RETURNING observation_id
        """,
        *common,
        write_periodic,
        write_transition,
        evidence,
    )
    if row is None:
        return 0
    observation_id = int(row["observation_id"])
    await persist_signal_replay_frame(conn, observation_id, ctx)
    execution_rows = await persist_signal_execution_snapshots(
        conn,
        observation_id,
        symbol,
        observed_at,
        execution_inputs,
    )
    if execution_rows != 2:
        raise RuntimeError(
            "signal execution snapshot capture did not persist both venues"
        )
    if write_periodic or (write_transition and actionable):
        await schedule_signal_outcomes(conn, observation_id, observed_at)
    return 1
