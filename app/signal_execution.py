from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

DENSE_PERIODIC = "dense_periodic"
UTC_NONOVERLAP = "utc_nonoverlap"
SAMPLING_MODES = (DENSE_PERIODIC, UTC_NONOVERLAP)

EXECUTION_SNAPSHOT_VERSION = 1
EXECUTION_COST_REPORT_VERSION = 1
EXECUTION_COST_MODEL_VERSION = 1

EXECUTION_EXCHANGES = ("binance", "bybit")
EXECUTION_SIZES_USD = (1_000.0, 10_000.0, 50_000.0, 100_000.0)

DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MIN_GROUP_N = 30

# Kept explicit to avoid a signal_ledger <-> signal_execution import cycle.
DEFAULT_EVIDENCE_VERSION = 1
DEFAULT_SAMPLING_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExecutionCostOptions:
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    symbols: tuple[str, ...] = ()
    horizons: tuple[int, ...] = OUTCOME_HORIZONS_MINUTES
    sizes_usd: tuple[float, ...] = EXECUTION_SIZES_USD
    sampling_modes: tuple[str, ...] = SAMPLING_MODES
    fee_bps_per_side: tuple[tuple[str, float], ...] = ()
    min_group_n: int = DEFAULT_MIN_GROUP_N
    logic_version: str = SCALP_SIGNAL_LOGIC_VERSION
    evidence_version: int = DEFAULT_EVIDENCE_VERSION
    sampling_version: int = DEFAULT_SAMPLING_VERSION
    context_version: int = REPLAY_CONTEXT_VERSION
    outcome_version: int = OUTCOME_VERSION
    execution_snapshot_version: int = EXECUTION_SNAPSHOT_VERSION


def validate_execution_cost_options(options: ExecutionCostOptions) -> None:
    if not 1 <= options.lookback_days <= 3650:
        raise ValueError("lookback_days must be between 1 and 3650")
    if not 1 <= options.min_group_n <= 1_000_000:
        raise ValueError("min_group_n must be between 1 and 1000000")

    if options.logic_version != SCALP_SIGNAL_LOGIC_VERSION:
        raise ValueError(
            "unsupported execution-cost logic_version; register a version-specific model"
        )

    for name, value in (
        ("evidence_version", options.evidence_version),
        ("sampling_version", options.sampling_version),
        ("context_version", options.context_version),
        ("outcome_version", options.outcome_version),
        ("execution_snapshot_version", options.execution_snapshot_version),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    if not options.horizons:
        raise ValueError("at least one horizon is required")
    if len(set(options.horizons)) != len(options.horizons):
        raise ValueError("duplicate horizons are not allowed")
    unsupported_horizons = sorted(
        set(options.horizons) - set(OUTCOME_HORIZONS_MINUTES)
    )
    if unsupported_horizons:
        raise ValueError(f"unsupported horizons: {unsupported_horizons}")

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

    fee_exchanges = [exchange for exchange, _ in options.fee_bps_per_side]
    if len(set(fee_exchanges)) != len(fee_exchanges):
        raise ValueError("duplicate exchange fee inputs are not allowed")
    unsupported_fee_exchanges = sorted(set(fee_exchanges) - set(EXECUTION_EXCHANGES))
    if unsupported_fee_exchanges:
        raise ValueError(
            f"unsupported exchange fee inputs: {unsupported_fee_exchanges}"
        )
    for exchange, fee in options.fee_bps_per_side:
        if not math.isfinite(fee) or not 0 <= fee <= 100:
            raise ValueError(
                f"fee_bps_per_side for {exchange} must be finite and between 0 and 100"
            )


# PR27_SCIENTIFIC_EXECUTION_SNAPSHOT_V1_BEGIN

# Snapshot-v1 producer inputs are frozen locally.  A future public execution
# configuration change must not silently alter evidence generated under
# snapshot_version=1.
_EXECUTION_SNAPSHOT_EXCHANGES_V1 = ("binance", "bybit")
_EXECUTION_SNAPSHOT_VERSION_V1 = 1
_EXECUTION_SNAPSHOT_SIZES_USD_V1 = (
    1_000.0,
    10_000.0,
    50_000.0,
    100_000.0,
)
_EXECUTION_SNAPSHOT_CLOCK_TOLERANCE_SECONDS_V1 = 0.5
_EXECUTION_SNAPSHOT_REALTIME_STALE_SECONDS_V1 = 30.0


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


def _snapshot_finite_float_v1(value: object) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _snapshot_walk_book_v1(
    levels: list[list[float]], size_usd: float
) -> dict[str, Any]:
    if size_usd <= 0:
        raise ValueError("size_usd must be positive")
    valid = [
        (price, quantity)
        for price, quantity in levels
        if _snapshot_finite_float_v1(price) is not None
        and _snapshot_finite_float_v1(quantity) is not None
        and price > 0
        and quantity > 0
    ]
    best = valid[0][0] if valid else None
    remaining = size_usd
    base_quantity = 0.0
    used = 0
    for price, quantity in valid:
        available = price * quantity
        take = min(remaining, available)
        base_quantity += take / price
        used += 1
        remaining -= take
        if remaining <= 1e-6:
            remaining = 0.0
            break
    filled = size_usd - remaining
    average_price = filled / base_quantity if base_quantity > 0 else None
    slippage_bps = (
        (average_price - best) / best * 10_000
        if average_price is not None and best
        else None
    )
    return {
        "size_usd": size_usd,
        "best_price": best,
        "avg_price": average_price,
        "levels_used": used,
        "levels_available": len(valid),
        "levels_discarded": len(levels) - len(valid),
        "filled_usd": round(filled, 2),
        "shortfall_usd": round(remaining, 2),
        "insufficient_depth": remaining > 0,
        "slippage_bps": abs(slippage_bps) if slippage_bps is not None else None,
    }


def _hash_book_payload(
    *,
    exchange: str,
    book_ts: datetime,
    levels_reported: int,
    bids: object,
    asks: object,
) -> str:
    payload = {
        "exchange": exchange,
        "book_ts": _aware_utc(book_ts),
        "levels_reported": levels_reported,
        "bids": bids,
        "asks": asks,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _decode_depth_levels(raw: object) -> tuple[list[list[float]], int]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError("depth side is not a list")

    levels: list[list[float]] = []
    discarded = 0
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            discarded += 1
            continue
        price = _snapshot_finite_float_v1(item[0])
        qty = _snapshot_finite_float_v1(item[1])
        if price is None or qty is None or price <= 0 or qty <= 0:
            discarded += 1
            continue
        levels.append([price, qty])
    return levels, discarded


def _ordered_depth(bids: list[list[float]], asks: list[list[float]]) -> bool:
    bids_ordered = all(
        bids[index][0] >= bids[index + 1][0]
        for index in range(len(bids) - 1)
    )
    asks_ordered = all(
        asks[index][0] <= asks[index + 1][0]
        for index in range(len(asks) - 1)
    )
    return bids_ordered and asks_ordered


def _market_cost_bps(
    *,
    side: str,
    mid_price: float,
    avg_price: float | None,
    insufficient_depth: bool,
) -> float | None:
    if insufficient_depth or avg_price is None or mid_price <= 0:
        return None
    if side == "buy":
        value = (avg_price - mid_price) / mid_price * 10_000.0
    elif side == "sell":
        value = (mid_price - avg_price) / mid_price * 10_000.0
    else:
        raise ValueError(f"unsupported side: {side}")
    if value < -1e-9:
        raise ValueError("negative market cost from a non-crossed book")
    return max(0.0, value)


def _compact_walk(
    walk: dict[str, Any],
    *,
    side: str,
    mid_price: float,
) -> dict[str, Any]:
    insufficient = bool(walk["insufficient_depth"])
    return {
        "avg_price": walk["avg_price"],
        "levels_used": int(walk["levels_used"]),
        "levels_available": int(walk["levels_available"]),
        "filled_usd": walk["filled_usd"],
        "shortfall_usd": walk["shortfall_usd"],
        "insufficient_depth": insufficient,
        "slippage_bps_vs_best": walk["slippage_bps"],
        "market_cost_bps_vs_mid": _market_cost_bps(
            side=side,
            mid_price=mid_price,
            avg_price=_snapshot_finite_float_v1(walk["avg_price"]),
            insufficient_depth=insufficient,
        ),
    }


def _cost_curve(
    bids: list[list[float]],
    asks: list[list[float]],
    *,
    mid_price: float,
) -> dict[str, Any]:
    curve: dict[str, Any] = {}
    for size in _EXECUTION_SNAPSHOT_SIZES_USD_V1:
        buy = _snapshot_walk_book_v1(asks, size)
        sell = _snapshot_walk_book_v1(bids, size)
        key = str(int(size))
        curve[key] = {
            "buy": _compact_walk(buy, side="buy", mid_price=mid_price),
            "sell": _compact_walk(sell, side="sell", mid_price=mid_price),
        }
    return curve


def execution_snapshot_record(
    *,
    exchange: str,
    observed_at: datetime,
    row: dict[str, Any] | None,
) -> dict[str, Any]:
    """Freeze one venue's decision-time taker-cost evidence."""

    if exchange not in _EXECUTION_SNAPSHOT_EXCHANGES_V1:
        raise ValueError(f"unsupported execution exchange: {exchange}")

    observed_at = _aware_utc(observed_at)
    base: dict[str, Any] = {
        "exchange": exchange,
        "captured_at": observed_at,
        "book_ts": None,
        "book_age_seconds": None,
        "status": "unavailable",
        "reason": "no_current_orderbook_depth",
        "levels_reported": 0,
        "bid_levels_valid": 0,
        "ask_levels_valid": 0,
        "best_bid_px": None,
        "best_ask_px": None,
        "mid_px": None,
        "spread_bps": None,
        "bid_depth_usd": None,
        "ask_depth_usd": None,
        "source_book_hash": None,
        "cost_curve": {},
    }
    if row is None:
        return base

    book_ts = row.get("ts")
    if not isinstance(book_ts, datetime):
        return {**base, "status": "error", "reason": "invalid_book_timestamp"}
    book_ts = _aware_utc(book_ts)
    age = (observed_at - book_ts).total_seconds()

    try:
        levels_reported = int(row.get("levels") or 0)
    except (TypeError, ValueError):
        levels_reported = 0

    raw_bids = row.get("bids")
    raw_asks = row.get("asks")
    try:
        source_hash = _hash_book_payload(
            exchange=exchange,
            book_ts=book_ts,
            levels_reported=levels_reported,
            bids=raw_bids,
            asks=raw_asks,
        )
        bids, bid_discarded = _decode_depth_levels(raw_bids)
        asks, ask_discarded = _decode_depth_levels(raw_asks)
    except (TypeError, ValueError, json.JSONDecodeError, OverflowError):
        return {
            **base,
            "book_ts": book_ts,
            "book_age_seconds": age,
            "levels_reported": levels_reported,
            "status": "error",
            "reason": "invalid_depth_payload",
        }

    bid_depth = sum(price * qty for price, qty in bids)
    ask_depth = sum(price * qty for price, qty in asks)
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None

    enriched = {
        **base,
        "book_ts": book_ts,
        "book_age_seconds": age,
        "levels_reported": levels_reported,
        "bid_levels_valid": len(bids),
        "ask_levels_valid": len(asks),
        "best_bid_px": best_bid,
        "best_ask_px": best_ask,
        "bid_depth_usd": bid_depth,
        "ask_depth_usd": ask_depth,
        "source_book_hash": source_hash,
    }

    if age < -_EXECUTION_SNAPSHOT_CLOCK_TOLERANCE_SECONDS_V1:
        return {
            **enriched,
            "status": "error",
            "reason": "future_book_timestamp",
        }
    if age > _EXECUTION_SNAPSHOT_REALTIME_STALE_SECONDS_V1:
        return {
            **enriched,
            "status": "stale",
            "reason": "book_older_than_realtime_limit",
        }
    if (
        not bids
        or not asks
        or bid_discarded > 0
        or ask_discarded > 0
        or not _ordered_depth(bids, asks)
    ):
        return {
            **enriched,
            "status": "error",
            "reason": "invalid_or_unordered_depth",
        }
    if best_bid is None or best_ask is None or best_ask < best_bid:
        return {
            **enriched,
            "status": "error",
            "reason": "crossed_or_missing_best_quotes",
        }

    mid = (best_bid + best_ask) / 2.0
    spread_bps = (best_ask - best_bid) / mid * 10_000.0 if mid > 0 else None
    if spread_bps is None or not math.isfinite(spread_bps) or spread_bps < 0:
        return {
            **enriched,
            "status": "error",
            "reason": "invalid_spread",
        }

    try:
        curve = _cost_curve(bids, asks, mid_price=mid)
    except (TypeError, ValueError, OverflowError):
        return {
            **enriched,
            "mid_px": mid,
            "spread_bps": spread_bps,
            "status": "error",
            "reason": "cost_curve_calculation_failed",
        }

    return {
        **enriched,
        "mid_px": mid,
        "spread_bps": spread_bps,
        "status": "valid",
        "reason": None,
        "cost_curve": curve,
    }


async def load_signal_execution_inputs(
    conn: asyncpg.Connection,
    symbol: str,
) -> dict[str, dict[str, Any]]:
    """Read the committed order books before the observation knowledge timestamp."""
    rows = await conn.fetch(
        """
        SELECT exchange,ts,bids,asks,levels
        FROM orderbook_depth
        WHERE symbol=$1
          AND exchange=ANY($2::text[])
        ORDER BY exchange
        """,
        symbol,
        list(_EXECUTION_SNAPSHOT_EXCHANGES_V1),
    )
    return {str(row["exchange"]): dict(row) for row in rows}


async def persist_signal_execution_snapshots(
    conn: asyncpg.Connection,
    observation_id: int,
    symbol: str,
    observed_at: datetime,
    source_rows: dict[str, dict[str, Any]] | None = None,
) -> int:
    """Persist exactly one forward-only execution snapshot per venue."""
    by_exchange = (
        source_rows
        if source_rows is not None
        else await load_signal_execution_inputs(conn, symbol)
    )

    inserted = 0
    for exchange in _EXECUTION_SNAPSHOT_EXCHANGES_V1:
        snapshot = execution_snapshot_record(
            exchange=exchange,
            observed_at=observed_at,
            row=by_exchange.get(exchange),
        )
        result = await conn.execute(
            """
            INSERT INTO signal_execution_snapshot(
              observation_id,snapshot_version,exchange,captured_at,
              book_ts,book_age_seconds,status,reason,
              levels_reported,bid_levels_valid,ask_levels_valid,
              best_bid_px,best_ask_px,mid_px,spread_bps,
              bid_depth_usd,ask_depth_usd,
              source_book_hash,cost_curve
            ) VALUES(
              $1,$2,$3,$4,
              $5,$6,$7,$8,
              $9,$10,$11,
              $12,$13,$14,$15,
              $16,$17,
              $18,$19::jsonb
            )
            ON CONFLICT(observation_id,exchange) DO NOTHING
            """,
            observation_id,
            _EXECUTION_SNAPSHOT_VERSION_V1,
            exchange,
            snapshot["captured_at"],
            snapshot["book_ts"],
            snapshot["book_age_seconds"],
            snapshot["status"],
            snapshot["reason"],
            snapshot["levels_reported"],
            snapshot["bid_levels_valid"],
            snapshot["ask_levels_valid"],
            snapshot["best_bid_px"],
            snapshot["best_ask_px"],
            snapshot["mid_px"],
            snapshot["spread_bps"],
            snapshot["bid_depth_usd"],
            snapshot["ask_depth_usd"],
            snapshot["source_book_hash"],
            _canonical_json(snapshot["cost_curve"]),
        )
        if result.endswith("1"):
            inserted += 1
    return inserted


# PR27_SCIENTIFIC_EXECUTION_SNAPSHOT_V1_END


def _sampling_predicate(mode: str) -> str:
    if mode == DENSE_PERIODIC:
        return "TRUE"
    if mode == UTC_NONOVERLAP:
        return (
            "mod("
            "floor(extract(epoch FROM observed_minute) / 60)::bigint,"
            "horizon_minutes::bigint"
            ") = 0"
        )
    raise ValueError(f"unsupported sampling mode: {mode}")


def _compatible_observations_cte() -> str:
    return """
    WITH compatible AS (
      SELECT
        obs.observation_id,
        obs.observed_at,
        obs.observed_minute,
        obs.symbol,
        obs.direction,
        obs.actionable,
        obs.reference_price
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
        c.*,
        COUNT(s.execution_snapshot_id) AS snapshot_rows,
        COUNT(s.execution_snapshot_id) FILTER (
          WHERE s.snapshot_version=$7
        ) AS compatible_snapshot_rows
      FROM compatible AS c
      LEFT JOIN signal_execution_snapshot AS s
        ON s.observation_id=c.observation_id
      GROUP BY
        c.observation_id,c.observed_at,c.observed_minute,
        c.symbol,c.direction,c.actionable,c.reference_price
    ),
    execution_cohort AS (
      SELECT *
      FROM snapshot_counts
      WHERE snapshot_rows=2
        AND compatible_snapshot_rows=2
    )
    """


async def _fetch_corpus_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: ExecutionCostOptions,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        _compatible_observations_cte()
        + """
        , first_execution AS (
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
              AND (snapshot_rows <> 2 OR compatible_snapshot_rows <> 2)
          )::bigint AS execution_snapshot_cardinality_or_version_anomalies,

          (
            SELECT execution_era_start FROM first_execution
          ) AS execution_era_start,

          (
            SELECT COUNT(*)
            FROM snapshot_counts, first_execution
            WHERE first_execution.execution_era_start IS NOT NULL
              AND snapshot_counts.observed_at >= first_execution.execution_era_start
              AND (
                snapshot_counts.snapshot_rows <> 2
                OR snapshot_counts.compatible_snapshot_rows <> 2
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
            JOIN execution_cohort AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.status='error'
          )::bigint AS execution_snapshot_error_rows,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN execution_cohort AS c
              ON c.observation_id=s.observation_id
            WHERE s.snapshot_version=$7
              AND s.reason='future_book_timestamp'
          )::bigint AS future_book_timestamp_anomalies,

          (
            SELECT COUNT(*)
            FROM signal_execution_snapshot AS s
            JOIN execution_cohort AS c
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
          )::bigint AS valid_snapshot_shape_anomalies
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
    )
    return dict(row) if row else {}


async def _fetch_outcome_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: ExecutionCostOptions,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        _compatible_observations_cte()
        + """
        SELECT
          COUNT(out.outcome_id)::bigint AS requested_outcome_rows,
          COUNT(out.outcome_id) FILTER (
            WHERE out.due_at <= $2
          )::bigint AS mature_outcome_rows,
          COUNT(out.outcome_id) FILTER (
            WHERE out.due_at <= $2 AND out.status='evaluated'
          )::bigint AS mature_evaluated_rows,
          COUNT(out.outcome_id) FILTER (
            WHERE out.due_at <= $2 AND out.status='pending'
          )::bigint AS mature_pending_rows,
          COUNT(out.outcome_id) FILTER (
            WHERE out.due_at <= $2 AND out.status='not_evaluable'
          )::bigint AS mature_not_evaluable_rows
        FROM execution_cohort AS c
        LEFT JOIN signal_outcome AS out
          ON out.observation_id=c.observation_id
         AND out.outcome_version=$9
         AND out.horizon_minutes=ANY($10::integer[])
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
        options.outcome_version,
        list(options.horizons),
    )
    return dict(row) if row else {}


async def _fetch_snapshot_status(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: ExecutionCostOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _compatible_observations_cte()
        + """
        SELECT
          s.exchange,
          s.status,
          COUNT(*)::bigint AS snapshots,
          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY s.book_age_seconds
          ) FILTER (
            WHERE s.book_age_seconds IS NOT NULL
          ) AS book_age_median_seconds,
          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY s.book_age_seconds
          ) FILTER (
            WHERE s.book_age_seconds IS NOT NULL
          ) AS book_age_p90_seconds,
          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY s.spread_bps
          ) FILTER (
            WHERE s.status='valid' AND s.spread_bps IS NOT NULL
          ) AS spread_median_bps,
          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY s.spread_bps
          ) FILTER (
            WHERE s.status='valid' AND s.spread_bps IS NOT NULL
          ) AS spread_p90_bps
        FROM execution_cohort AS c
        JOIN signal_execution_snapshot AS s
          ON s.observation_id=c.observation_id
         AND s.snapshot_version=$7
        GROUP BY s.exchange,s.status
        ORDER BY s.exchange,s.status
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
    )
    return [dict(row) for row in rows]


async def _fetch_snapshot_cost_distribution(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: ExecutionCostOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _compatible_observations_cte()
        + """
        , cost_rows AS (
          SELECT
            c.symbol,
            s.exchange,
            (curve.key)::float8 AS size_usd,
            (curve.value->'buy'->>'market_cost_bps_vs_mid')::float8
              AS buy_market_cost_bps,
            (curve.value->'sell'->>'market_cost_bps_vs_mid')::float8
              AS sell_market_cost_bps,
            COALESCE(
              (curve.value->'buy'->>'insufficient_depth')::boolean,
              true
            ) AS buy_insufficient_depth,
            COALESCE(
              (curve.value->'sell'->>'insufficient_depth')::boolean,
              true
            ) AS sell_insufficient_depth,
            s.spread_bps,
            s.book_age_seconds
          FROM execution_cohort AS c
          JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
           AND s.snapshot_version=$7
          CROSS JOIN LATERAL jsonb_each(s.cost_curve) AS curve(key,value)
          WHERE s.status='valid'
            AND (curve.key)::float8=ANY($9::double precision[])
        )
        SELECT
          symbol,
          exchange,
          size_usd,
          COUNT(*)::bigint AS valid_snapshot_n,
          COUNT(*) FILTER (
            WHERE buy_insufficient_depth
          )::bigint AS buy_insufficient_depth_n,
          COUNT(*) FILTER (
            WHERE sell_insufficient_depth
          )::bigint AS sell_insufficient_depth_n,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY buy_market_cost_bps
          ) FILTER (
            WHERE NOT buy_insufficient_depth
              AND buy_market_cost_bps IS NOT NULL
          ) AS buy_market_cost_median_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY buy_market_cost_bps
          ) FILTER (
            WHERE NOT buy_insufficient_depth
              AND buy_market_cost_bps IS NOT NULL
          ) AS buy_market_cost_p90_bps,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY sell_market_cost_bps
          ) FILTER (
            WHERE NOT sell_insufficient_depth
              AND sell_market_cost_bps IS NOT NULL
          ) AS sell_market_cost_median_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY sell_market_cost_bps
          ) FILTER (
            WHERE NOT sell_insufficient_depth
              AND sell_market_cost_bps IS NOT NULL
          ) AS sell_market_cost_p90_bps,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY spread_bps
          ) AS spread_median_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY spread_bps
          ) AS spread_p90_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY book_age_seconds
          ) AS book_age_p90_seconds

        FROM cost_rows
        GROUP BY symbol,exchange,size_usd
        ORDER BY symbol,exchange,size_usd
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
        list(options.sizes_usd),
    )
    return [dict(row) for row in rows]


def _execution_outcome_query(mode: str) -> str:
    predicate = _sampling_predicate(mode)
    return (
        _compatible_observations_cte()
        + f"""
        , matured AS (
          SELECT
            c.observation_id,
            c.observed_at,
            c.observed_minute,
            c.symbol,
            c.direction,
            c.actionable,
            c.reference_price,
            out.horizon_minutes,
            out.status AS outcome_status,
            out.end_price,
            out.directional_return_pct,
            out.mfe_pct,
            out.mae_pct,
            s.exchange,
            s.status AS snapshot_status,
            s.book_age_seconds,
            s.spread_bps,
            s.cost_curve
          FROM execution_cohort AS c
          JOIN signal_outcome AS out
            ON out.observation_id=c.observation_id
           AND out.outcome_version=$9
           AND out.horizon_minutes=ANY($10::integer[])
           AND out.due_at <= $2
          JOIN signal_execution_snapshot AS s
            ON s.observation_id=c.observation_id
           AND s.snapshot_version=$7
          WHERE c.actionable
            AND c.direction IN ('long','short')
        ),
        expanded AS (
          SELECT
            matured.*,
            requested.size_usd,
            CASE matured.direction
              WHEN 'long'
                THEN (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'buy'
                  ->> 'avg_price'
                )::float8
              WHEN 'short'
                THEN (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'sell'
                  ->> 'avg_price'
                )::float8
            END AS entry_fill_price,
            CASE matured.direction
              WHEN 'long'
                THEN (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'buy'
                  ->> 'market_cost_bps_vs_mid'
                )::float8
              WHEN 'short'
                THEN (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'sell'
                  ->> 'market_cost_bps_vs_mid'
                )::float8
            END AS entry_market_cost_bps,
            CASE
              WHEN matured.snapshot_status <> 'valid' THEN NULL
              WHEN matured.direction='long' THEN COALESCE(
                (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'buy'
                  ->> 'insufficient_depth'
                )::boolean,
                true
              )
              WHEN matured.direction='short' THEN COALESCE(
                (
                  matured.cost_curve
                  -> ((requested.size_usd::bigint)::text)
                  -> 'sell'
                  ->> 'insufficient_depth'
                )::boolean,
                true
              )
              ELSE NULL
            END AS insufficient_depth,
            CASE
              WHEN ($11::jsonb ? matured.exchange)
              THEN ($11::jsonb ->> matured.exchange)::float8
              ELSE NULL
            END AS fee_bps_per_side
          FROM matured
          CROSS JOIN LATERAL unnest($12::double precision[])
            AS requested(size_usd)
        ),
        sampled AS (
          SELECT
            *,
            directional_return_pct * 100.0 AS gross_directional_return_bps,

            CASE
              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND reference_price IS NOT NULL
                AND reference_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND insufficient_depth IS FALSE
                AND direction='long'
              THEN (entry_fill_price/reference_price - 1.0) * 10000.0

              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND reference_price IS NOT NULL
                AND reference_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND insufficient_depth IS FALSE
                AND direction='short'
              THEN (reference_price-entry_fill_price)/reference_price * 10000.0

              ELSE NULL
            END AS entry_implementation_shortfall_bps,

            CASE
              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND end_price IS NOT NULL
                AND end_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND insufficient_depth IS FALSE
                AND direction='long'
              THEN (end_price/entry_fill_price - 1.0) * 10000.0

              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND end_price IS NOT NULL
                AND end_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND insufficient_depth IS FALSE
                AND direction='short'
              THEN (entry_fill_price-end_price)/entry_fill_price * 10000.0

              ELSE NULL
            END AS entry_only_market_net_bps,

            CASE
              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND end_price IS NOT NULL
                AND end_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND entry_market_cost_bps IS NOT NULL
                AND insufficient_depth IS FALSE
                AND direction='long'
              THEN (
                (
                  end_price * (1.0-entry_market_cost_bps/10000.0)
                ) / entry_fill_price - 1.0
              ) * 10000.0

              WHEN snapshot_status='valid'
                AND outcome_status='evaluated'
                AND end_price IS NOT NULL
                AND end_price > 0
                AND entry_fill_price IS NOT NULL
                AND entry_fill_price > 0
                AND entry_market_cost_bps IS NOT NULL
                AND insufficient_depth IS FALSE
                AND direction='short'
              THEN (
                entry_fill_price
                - end_price * (1.0+entry_market_cost_bps/10000.0)
              ) / entry_fill_price * 10000.0

              ELSE NULL
            END AS symmetric_market_net_bps

          FROM expanded
          WHERE {predicate}
        ),
        fee_adjusted AS (
          SELECT
            *,
            CASE
              WHEN symmetric_market_net_bps IS NOT NULL
                AND fee_bps_per_side IS NOT NULL
              THEN symmetric_market_net_bps - 2.0*fee_bps_per_side
              ELSE NULL
            END AS modeled_net_after_fees_bps
          FROM sampled
        )
        SELECT
          symbol,
          exchange,
          size_usd,
          horizon_minutes,

          COUNT(*)::bigint AS actionable_mature_rows,
          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
          )::bigint AS actionable_evaluated_n,

          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND snapshot_status <> 'valid'
          )::bigint AS snapshot_not_valid_n,

          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND snapshot_status='valid'
              AND insufficient_depth IS TRUE
          )::bigint AS insufficient_depth_n,

          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND snapshot_status='valid'
              AND insufficient_depth IS FALSE
              AND entry_fill_price IS NOT NULL
              AND entry_market_cost_bps IS NOT NULL
          )::bigint AS cost_evaluable_n,

          (
            100.0 * COUNT(*) FILTER (
              WHERE outcome_status='evaluated'
                AND snapshot_status='valid'
                AND insufficient_depth IS FALSE
                AND entry_fill_price IS NOT NULL
                AND entry_market_cost_bps IS NOT NULL
            )
            /
            NULLIF(
              COUNT(*) FILTER (WHERE outcome_status='evaluated'),
              0
            )
          )::float8 AS cost_evaluable_pct,

          AVG(gross_directional_return_bps) FILTER (
            WHERE outcome_status='evaluated'
          ) AS gross_expectancy_bps,

          (
            100.0 * COUNT(*) FILTER (
              WHERE outcome_status='evaluated'
                AND gross_directional_return_bps > 0
            )
            /
            NULLIF(
              COUNT(*) FILTER (
                WHERE outcome_status='evaluated'
                  AND gross_directional_return_bps IS NOT NULL
              ),
              0
            )
          )::float8 AS gross_hit_rate_pct,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY entry_market_cost_bps
          ) FILTER (
            WHERE outcome_status='evaluated'
              AND snapshot_status='valid'
              AND insufficient_depth IS FALSE
              AND entry_market_cost_bps IS NOT NULL
          ) AS entry_market_cost_median_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY entry_market_cost_bps
          ) FILTER (
            WHERE outcome_status='evaluated'
              AND snapshot_status='valid'
              AND insufficient_depth IS FALSE
              AND entry_market_cost_bps IS NOT NULL
          ) AS entry_market_cost_p90_bps,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY entry_implementation_shortfall_bps
          ) FILTER (
            WHERE entry_implementation_shortfall_bps IS NOT NULL
          ) AS entry_implementation_shortfall_median_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY entry_implementation_shortfall_bps
          ) FILTER (
            WHERE entry_implementation_shortfall_bps IS NOT NULL
          ) AS entry_implementation_shortfall_p90_bps,

          AVG(entry_only_market_net_bps)
            AS entry_only_market_net_expectancy_bps,

          AVG(symmetric_market_net_bps)
            AS symmetric_market_net_expectancy_bps,

          (
            100.0 * COUNT(*) FILTER (
              WHERE symmetric_market_net_bps > 0
            )
            /
            NULLIF(COUNT(symmetric_market_net_bps),0)
          )::float8 AS symmetric_market_net_hit_rate_pct,

          MAX(fee_bps_per_side) AS fee_bps_per_side,

          COUNT(modeled_net_after_fees_bps)::bigint
            AS modeled_net_after_fees_n,

          AVG(modeled_net_after_fees_bps)
            AS modeled_net_after_fees_expectancy_bps,

          (
            100.0 * COUNT(*) FILTER (
              WHERE modeled_net_after_fees_bps > 0
            )
            /
            NULLIF(COUNT(modeled_net_after_fees_bps),0)
          )::float8 AS modeled_net_after_fees_hit_rate_pct,

          COUNT(*) FILTER (
            WHERE gross_directional_return_bps > 0
              AND symmetric_market_net_bps IS NOT NULL
          )::bigint AS gross_positive_cost_evaluable_n,

          COUNT(*) FILTER (
            WHERE gross_directional_return_bps > 0
              AND symmetric_market_net_bps > 0
          )::bigint AS gross_positive_survives_market_cost_n,

          (
            100.0 * COUNT(*) FILTER (
              WHERE gross_directional_return_bps > 0
                AND symmetric_market_net_bps > 0
            )
            /
            NULLIF(
              COUNT(*) FILTER (
                WHERE gross_directional_return_bps > 0
                  AND symmetric_market_net_bps IS NOT NULL
              ),
              0
            )
          )::float8 AS gross_positive_survives_market_cost_pct,

          percentile_cont(0.50) WITHIN GROUP (
            ORDER BY symmetric_market_net_bps/2.0
          ) FILTER (
            WHERE gross_directional_return_bps > 0
              AND symmetric_market_net_bps IS NOT NULL
          ) AS break_even_fee_per_side_median_bps,

          percentile_cont(0.10) WITHIN GROUP (
            ORDER BY symmetric_market_net_bps/2.0
          ) FILTER (
            WHERE gross_directional_return_bps > 0
              AND symmetric_market_net_bps IS NOT NULL
          ) AS break_even_fee_per_side_p10_bps,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY book_age_seconds
          ) FILTER (
            WHERE book_age_seconds IS NOT NULL
          ) AS book_age_p90_seconds,

          percentile_cont(0.90) WITHIN GROUP (
            ORDER BY spread_bps
          ) FILTER (
            WHERE spread_bps IS NOT NULL
          ) AS spread_p90_bps

        FROM fee_adjusted
        GROUP BY symbol,exchange,size_usd,horizon_minutes
        ORDER BY symbol,exchange,size_usd,horizon_minutes
        """
    )


async def _fetch_execution_outcomes(
    conn: asyncpg.Connection,
    *,
    mode: str,
    window_start: datetime,
    snapshot_at: datetime,
    options: ExecutionCostOptions,
) -> list[dict[str, Any]]:
    fees = {exchange: fee for exchange, fee in options.fee_bps_per_side}
    rows = await conn.fetch(
        _execution_outcome_query(mode),
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.execution_snapshot_version,
        list(options.symbols),
        options.outcome_version,
        list(options.horizons),
        json.dumps(fees, sort_keys=True, separators=(",", ":")),
        list(options.sizes_usd),
    )
    result: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        n = int(row.get("cost_evaluable_n") or 0)
        fee_n = int(row.get("modeled_net_after_fees_n") or 0)
        row["meets_min_group_n"] = n >= options.min_group_n
        row["fee_model_meets_min_group_n"] = fee_n >= options.min_group_n
        result.append(row)
    return result


async def build_execution_cost_report(
    conn: asyncpg.Connection,
    options: ExecutionCostOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only execution-cost overlay over immutable research data."""

    opts = options or ExecutionCostOptions()
    validate_execution_cost_options(opts)

    snapshot_at = await conn.fetchval("SELECT clock_timestamp()")
    if not isinstance(snapshot_at, datetime):
        raise RuntimeError("PostgreSQL did not return a timestamp")
    snapshot_at = _aware_utc(snapshot_at)
    window_start = snapshot_at - timedelta(days=opts.lookback_days)

    corpus = await _fetch_corpus_summary(
        conn,
        window_start=window_start,
        snapshot_at=snapshot_at,
        options=opts,
    )
    outcome_summary = await _fetch_outcome_summary(
        conn,
        window_start=window_start,
        snapshot_at=snapshot_at,
        options=opts,
    )

    covered = int(corpus.get("execution_covered_periodic_observations") or 0)
    expected_outcomes = covered * len(opts.horizons)
    actual_outcomes = int(outcome_summary.get("requested_outcome_rows") or 0)
    outcome_summary["expected_outcome_rows"] = expected_outcomes
    outcome_summary["missing_or_wrong_version_outcome_rows"] = max(
        0,
        expected_outcomes - actual_outcomes,
    )

    snapshot_status = await _fetch_snapshot_status(
        conn,
        window_start=window_start,
        snapshot_at=snapshot_at,
        options=opts,
    )
    snapshot_cost_distribution = await _fetch_snapshot_cost_distribution(
        conn,
        window_start=window_start,
        snapshot_at=snapshot_at,
        options=opts,
    )

    views: dict[str, Any] = {}
    for mode in opts.sampling_modes:
        views[mode] = {
            "execution_by_symbol_venue_size_horizon": (
                await _fetch_execution_outcomes(
                    conn,
                    mode=mode,
                    window_start=window_start,
                    snapshot_at=snapshot_at,
                    options=opts,
                )
            )
        }

    fee_map = {exchange: fee for exchange, fee in opts.fee_bps_per_side}
    return {
        "report_version": EXECUTION_COST_REPORT_VERSION,
        "execution_cost_model_version": EXECUTION_COST_MODEL_VERSION,
        "execution_snapshot_version": opts.execution_snapshot_version,
        "generated_at": snapshot_at,
        "window_start": window_start,
        "window_end": snapshot_at,
        "lookback_days": opts.lookback_days,
        "symbols": list(opts.symbols),
        "horizons_minutes": list(opts.horizons),
        "sizes_usd": list(opts.sizes_usd),
        "exchanges": list(EXECUTION_EXCHANGES),
        "fee_bps_per_side": fee_map,
        "fees_complete_for_all_venues": all(
            exchange in fee_map for exchange in EXECUTION_EXCHANGES
        ),
        "min_group_n": opts.min_group_n,
        "versions": {
            "logic_version": opts.logic_version,
            "evidence_version": opts.evidence_version,
            "sampling_version": opts.sampling_version,
            "context_version": opts.context_version,
            "outcome_version": opts.outcome_version,
        },
        "execution_contract": {
            "order_type": "taker_market",
            "venue_model": "single_venue_only",
            "combined_orderbook_allowed": False,
            "entry_cost_source": (
                "venue-specific orderbook_depth frozen prospectively into "
                "signal_execution_snapshot at observation persistence"
            ),
            "entry_market_cost_definition": (
                "directional VWAP fill versus the same venue's frozen mid price; "
                "includes spread crossing and book-walk impact"
            ),
            "partial_depth_policy": (
                "insufficient depth is not extrapolated; cost is non-evaluable "
                "for that size"
            ),
            "round_trip_market_model": (
                "symmetric_entry_book_v1: modeled exit market cost equals the "
                "observed entry market cost because future exit depth is not frozen"
            ),
            "fee_policy": (
                "no fee is invented; caller-supplied fee_bps_per_side is applied "
                "twice for round trip"
            ),
            "funding_modeled": False,
            "funding_note": (
                "funding/carry is excluded from PR10 v1 and must not be hidden "
                "inside execution-cost estimates"
            ),
            "return_overlay": (
                "costs are subtracted additively in basis points from PR5 gross "
                "directional return; this is a research cost overlay, not an "
                "accounting ledger or realized PnL"
            ),
            "old_observation_backfill": False,
        },
        "methodology": {
            "signal_family": "scalp",
            "primary_grid": "is_periodic=true only",
            "replay_frame_required": True,
            "two_execution_snapshot_rows_required": True,
            "mature_outcome_rule": "signal_outcome.due_at <= generated_at",
            "dense_periodic_warning": (
                "forward windows can overlap; observations are not independent trades"
            ),
            "utc_nonoverlap_rule": (
                "Unix-epoch UTC minute index modulo horizon_minutes = 0"
            ),
            "live_scoring_changes": False,
            "automatic_trade_veto": False,
            "causal_claims": False,
        },
        "corpus": {
            **corpus,
            **outcome_summary,
        },
        "snapshot_status": snapshot_status,
        "snapshot_cost_distribution": snapshot_cost_distribution,
        "views": views,
    }
