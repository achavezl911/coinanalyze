from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.data_gaps import GapRequirement, blocking_requirement_keys

OUTCOME_HORIZONS_MINUTES = (1, 3, 5, 15, 30, 60, 120, 240)
OUTCOME_VERSION = 1
OUTCOME_SETTLEMENT_LAG = timedelta(minutes=2)
MISSING_DATA_FINAL_GRACE = timedelta(days=7)
MISSING_DATA_RETRY = timedelta(minutes=15)
DEFAULT_BATCH_LIMIT = 128


@dataclass(frozen=True, slots=True)
class OutcomeWindow:
    start: datetime
    end: datetime
    due_at: datetime
    horizon_minutes: int
    start_delay_seconds: float


@dataclass(frozen=True, slots=True)
class PathMetrics:
    end_price: float
    max_high: float
    min_low: float
    market_return_pct: float
    up_excursion_pct: float
    down_excursion_pct: float
    directional_return_pct: float | None
    mfe_pct: float | None
    mae_pct: float | None


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    selected: int = 0
    evaluated: int = 0
    finalized_not_evaluable: int = 0
    deferred: int = 0


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _finite_positive(value: object) -> float | None:
    try:
        if value is None:
            return None
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if math.isfinite(parsed) and parsed > 0 else None


def outcome_window(observed_at: datetime, horizon_minutes: int) -> OutcomeWindow:
    if horizon_minutes not in OUTCOME_HORIZONS_MINUTES:
        raise ValueError("unsupported signal outcome horizon")
    observed_at = _aware_utc(observed_at)
    minute_floor = observed_at.replace(second=0, microsecond=0)
    start = minute_floor + timedelta(minutes=1)
    end = start + timedelta(minutes=horizon_minutes)
    return OutcomeWindow(
        start=start,
        end=end,
        due_at=end + OUTCOME_SETTLEMENT_LAG,
        horizon_minutes=horizon_minutes,
        start_delay_seconds=(start - observed_at).total_seconds(),
    )


def expected_bar_timestamps(start: datetime, horizon_minutes: int) -> tuple[datetime, ...]:
    start = _aware_utc(start)
    if horizon_minutes not in OUTCOME_HORIZONS_MINUTES:
        raise ValueError("unsupported signal outcome horizon")
    return tuple(start + timedelta(minutes=i) for i in range(horizon_minutes))


def compute_path_metrics(
    entry_price: float,
    direction: str,
    bars: Sequence[dict[str, Any] | asyncpg.Record],
) -> PathMetrics:
    entry = _finite_positive(entry_price)
    if entry is None:
        raise ValueError("entry price must be finite and positive")
    if not bars:
        raise ValueError("outcome path requires at least one bar")

    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    for bar in bars:
        high = _finite_positive(bar["high"])
        low = _finite_positive(bar["low"])
        close = _finite_positive(bar["close"])
        if high is None or low is None or close is None or high < low:
            raise ValueError("invalid OHLCV outcome bar")
        highs.append(high)
        lows.append(low)
        closes.append(close)

    end_price = closes[-1]
    max_high = max(highs)
    min_low = min(lows)
    market_return = (end_price - entry) / entry * 100.0
    up_excursion = (max_high - entry) / entry * 100.0
    down_excursion = (min_low - entry) / entry * 100.0

    if direction == "long":
        directional_return = market_return
        mfe = max(0.0, up_excursion)
        mae = max(0.0, -down_excursion)
    elif direction == "short":
        directional_return = -market_return
        mfe = max(0.0, -down_excursion)
        mae = max(0.0, up_excursion)
    elif direction in {"neutral", "unavailable"}:
        directional_return = None
        mfe = None
        mae = None
    else:
        raise ValueError(f"unsupported signal direction: {direction}")

    return PathMetrics(
        end_price=end_price,
        max_high=max_high,
        min_low=min_low,
        market_return_pct=market_return,
        up_excursion_pct=up_excursion,
        down_excursion_pct=down_excursion,
        directional_return_pct=directional_return,
        mfe_pct=mfe,
        mae_pct=mae,
    )


async def schedule_signal_outcomes(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
) -> int:
    """Create all deterministic pending horizon jobs idempotently."""

    if observation_id <= 0:
        raise ValueError("observation_id must be positive")
    inserted = 0
    for horizon in OUTCOME_HORIZONS_MINUTES:
        window = outcome_window(observed_at, horizon)
        row = await conn.fetchrow(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,outcome_version
            ) VALUES($1,$2,$3,$4,$5,$5,$6,$2,$7)
            ON CONFLICT(observation_id,horizon_minutes) DO NOTHING
            RETURNING outcome_id
            """,
            observation_id,
            horizon,
            window.start,
            window.end,
            window.due_at,
            window.start_delay_seconds,
            OUTCOME_VERSION,
        )
        if row is not None:
            inserted += 1
    return inserted


async def _finalize_not_evaluable(
    conn: asyncpg.Connection,
    outcome_id: int,
    *,
    now: datetime,
    reason: str,
    bars_found: int,
) -> bool:
    result = await conn.execute(
        """
        UPDATE signal_outcome
        SET status='not_evaluable',
            attempts=attempts+1,
            last_attempt_at=$2,
            finalized_at=$2,
            bars_found=$3,
            final_reason=$4,
            next_attempt_at=$2
        WHERE outcome_id=$1 AND status='pending'
        """,
        outcome_id,
        now,
        bars_found,
        reason[:120],
    )
    return result.endswith("1")


async def _defer_missing_path(
    conn: asyncpg.Connection,
    outcome_id: int,
    *,
    now: datetime,
    bars_found: int,
) -> bool:
    result = await conn.execute(
        """
        UPDATE signal_outcome
        SET attempts=attempts+1,
            last_attempt_at=$2,
            bars_found=$3,
            next_attempt_at=$2::timestamptz + $4::interval
        WHERE outcome_id=$1 AND status='pending'
        """,
        outcome_id,
        now,
        bars_found,
        MISSING_DATA_RETRY,
    )
    return result.endswith("1")


async def _finalize_evaluated(
    conn: asyncpg.Connection,
    outcome_id: int,
    *,
    now: datetime,
    entry_price: float,
    bars_found: int,
    metrics: PathMetrics,
) -> bool:
    result = await conn.execute(
        """
        UPDATE signal_outcome
        SET status='evaluated',
            attempts=attempts+1,
            last_attempt_at=$2,
            finalized_at=$2,
            bars_found=$3,
            entry_reference_price=$4,
            end_price=$5,
            max_high=$6,
            min_low=$7,
            market_return_pct=$8,
            up_excursion_pct=$9,
            down_excursion_pct=$10,
            directional_return_pct=$11,
            mfe_pct=$12,
            mae_pct=$13,
            final_reason=NULL,
            next_attempt_at=$2
        WHERE outcome_id=$1 AND status='pending'
        """,
        outcome_id,
        now,
        bars_found,
        entry_price,
        metrics.end_price,
        metrics.max_high,
        metrics.min_low,
        metrics.market_return_pct,
        metrics.up_excursion_pct,
        metrics.down_excursion_pct,
        metrics.directional_return_pct,
        metrics.mfe_pct,
        metrics.mae_pct,
    )
    return result.endswith("1")


async def materialize_due_signal_outcomes(
    conn: asyncpg.Connection,
    *,
    limit: int = DEFAULT_BATCH_LIMIT,
) -> MaterializationResult:
    """Finalize a bounded batch from exact closed 1-minute futures bars.

    Missing bars are never interpolated/zero-filled. They remain pending for
    seven days so delayed exact ingest/recovery can complete the path.
    """

    if limit <= 0 or limit > 10_000:
        raise ValueError("outcome batch limit must be between 1 and 10000")

    now = await conn.fetchval("SELECT clock_timestamp()")
    if not isinstance(now, datetime):
        raise RuntimeError("PostgreSQL did not return a timestamp")
    now = _aware_utc(now)

    jobs = await conn.fetch(
        """
        SELECT
          out.outcome_id,out.horizon_minutes,out.window_start,out.window_end,
          out.due_at,out.bars_expected,
          obs.symbol,obs.direction,obs.reference_price
        FROM signal_outcome AS out
        JOIN signal_observation AS obs
          ON obs.observation_id=out.observation_id
        WHERE out.status='pending'
          AND out.due_at <= $1
          AND out.next_attempt_at <= $1
        ORDER BY out.due_at,out.outcome_id
        FOR UPDATE OF out SKIP LOCKED
        LIMIT $2
        """,
        now,
        limit,
    )

    evaluated = 0
    finalized_not_evaluable = 0
    deferred = 0

    for job in jobs:
        outcome_id = int(job["outcome_id"])
        horizon = int(job["horizon_minutes"])
        start = _aware_utc(job["window_start"])
        end = _aware_utc(job["window_end"])
        due_at = _aware_utc(job["due_at"])
        bars_expected = int(job["bars_expected"])
        direction = str(job["direction"])
        entry = _finite_positive(job["reference_price"])

        if horizon != bars_expected:
            raise RuntimeError("signal_outcome horizon/bars_expected invariant violated")

        if entry is None:
            if await _finalize_not_evaluable(
                conn,
                outcome_id,
                now=now,
                reason="missing_reference_price",
                bars_found=0,
            ):
                finalized_not_evaluable += 1
            continue

        bars = await conn.fetch(
            """
            SELECT ts,high,low,close
            FROM ohlcv
            WHERE symbol=$1
              AND interval='1min'
              AND ts >= $2
              AND ts < $3
            ORDER BY ts
            """,
            str(job["symbol"]),
            start,
            end,
        )

        actual_ts = tuple(_aware_utc(row["ts"]) for row in bars)
        expected_ts = expected_bar_timestamps(start, horizon)
        exact_path = len(bars) == horizon and actual_ts == expected_ts

        blocked = bool(
            await blocking_requirement_keys(
                conn,
                [
                    GapRequirement(
                        key=f"outcome:{outcome_id}",
                        feed="ohlcv_1min",
                        exchange="binance",
                        market="perpetual",
                        symbol=str(job["symbol"]),
                        start=start,
                        end=end,
                    )
                ],
            )
        )

        if blocked or not exact_path:
            reason = (
                "blocking_ohlcv_gap_after_grace"
                if blocked
                else "incomplete_exact_ohlcv_path_after_grace"
            )
            if now >= due_at + MISSING_DATA_FINAL_GRACE:
                if await _finalize_not_evaluable(
                    conn,
                    outcome_id,
                    now=now,
                    reason=reason,
                    bars_found=len(bars),
                ):
                    finalized_not_evaluable += 1
            else:
                if await _defer_missing_path(
                    conn,
                    outcome_id,
                    now=now,
                    bars_found=len(bars),
                ):
                    deferred += 1
            continue

        metrics = compute_path_metrics(entry, direction, bars)
        if await _finalize_evaluated(
            conn,
            outcome_id,
            now=now,
            entry_price=entry,
            bars_found=len(bars),
            metrics=metrics,
        ):
            evaluated += 1

    return MaterializationResult(
        selected=len(jobs),
        evaluated=evaluated,
        finalized_not_evaluable=finalized_not_evaluable,
        deferred=deferred,
    )
