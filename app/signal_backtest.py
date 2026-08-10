from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.signal_ledger import SIGNAL_EVIDENCE_VERSION, SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

BACKTEST_REPORT_VERSION = 1
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MIN_GROUP_N = 30

DENSE_PERIODIC = "dense_periodic"
UTC_NONOVERLAP = "utc_nonoverlap"
SAMPLING_MODES = (DENSE_PERIODIC, UTC_NONOVERLAP)

DEFAULT_GROUP_BY = ("symbol", "state", "confidence", "direction")
ALLOWED_GROUP_DIMENSIONS = frozenset(
    {
        "symbol",
        "state",
        "confidence",
        "direction",
        "decision_status",
        "regime_label",
        "reference_price_source",
        "coverage_band",
    }
)


@dataclass(frozen=True, slots=True)
class BacktestOptions:
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    symbols: tuple[str, ...] = ()
    horizons: tuple[int, ...] = OUTCOME_HORIZONS_MINUTES
    group_by: tuple[str, ...] = DEFAULT_GROUP_BY
    sampling_modes: tuple[str, ...] = SAMPLING_MODES
    min_group_n: int = DEFAULT_MIN_GROUP_N
    logic_version: str = SCALP_SIGNAL_LOGIC_VERSION
    evidence_version: int = SIGNAL_EVIDENCE_VERSION
    sampling_version: int = SIGNAL_SAMPLING_VERSION
    context_version: int = REPLAY_CONTEXT_VERSION
    outcome_version: int = OUTCOME_VERSION


def validate_backtest_options(options: BacktestOptions) -> None:
    if not 1 <= options.lookback_days <= 3650:
        raise ValueError("lookback_days must be between 1 and 3650")
    if not 1 <= options.min_group_n <= 1_000_000:
        raise ValueError("min_group_n must be between 1 and 1000000")
    if not options.logic_version.strip():
        raise ValueError("logic_version must be non-empty")
    for name, value in (
        ("evidence_version", options.evidence_version),
        ("sampling_version", options.sampling_version),
        ("context_version", options.context_version),
        ("outcome_version", options.outcome_version),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be positive")

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

    if len(set(options.group_by)) != len(options.group_by):
        raise ValueError("duplicate group dimensions are not allowed")
    unsupported_dimensions = sorted(set(options.group_by) - ALLOWED_GROUP_DIMENSIONS)
    if unsupported_dimensions:
        raise ValueError(f"unsupported group dimensions: {unsupported_dimensions}")

    if not options.sampling_modes:
        raise ValueError("at least one sampling mode is required")
    if len(set(options.sampling_modes)) != len(options.sampling_modes):
        raise ValueError("duplicate sampling modes are not allowed")
    unsupported_modes = sorted(set(options.sampling_modes) - set(SAMPLING_MODES))
    if unsupported_modes:
        raise ValueError(f"unsupported sampling modes: {unsupported_modes}")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _coverage_band_sql() -> str:
    return """
    CASE
      WHEN obs.evidence_coverage_pct < 50 THEN '<50'
      WHEN obs.evidence_coverage_pct < 60 THEN '50-60'
      WHEN obs.evidence_coverage_pct < 70 THEN '60-70'
      WHEN obs.evidence_coverage_pct < 80 THEN '70-80'
      WHEN obs.evidence_coverage_pct < 90 THEN '80-90'
      ELSE '90-100'
    END
    """


def _cohort_cte() -> str:
    return f"""
    WITH cohort AS (
      SELECT
        obs.observation_id,
        obs.observed_at,
        obs.observed_minute,
        obs.symbol,
        obs.state,
        obs.confidence,
        obs.direction,
        obs.decision_status,
        obs.actionable,
        obs.regime_label,
        obs.reference_price_source,
        {_coverage_band_sql()} AS coverage_band,
        out.outcome_id,
        out.horizon_minutes,
        out.window_start,
        out.window_end,
        out.due_at,
        out.status AS outcome_status,
        out.final_reason,
        out.directional_return_pct,
        out.mfe_pct,
        out.mae_pct,
        out.market_return_pct,
        out.up_excursion_pct,
        out.down_excursion_pct
      FROM signal_observation AS obs
      JOIN signal_replay_frame AS frame
        ON frame.observation_id=obs.observation_id
      JOIN signal_outcome AS out
        ON out.observation_id=obs.observation_id
      WHERE obs.signal_family='scalp'
        AND obs.is_periodic
        AND obs.observed_at >= $1
        AND obs.observed_at < $2
        AND obs.logic_version=$3
        AND obs.evidence_version=$4
        AND obs.sampling_version=$5
        AND frame.context_version=$6
        AND out.outcome_version=$7
        AND out.horizon_minutes=ANY($9::integer[])
        AND out.due_at <= $2
        AND (
          cardinality($8::text[]) = 0
          OR obs.symbol=ANY($8::text[])
        )
    )
    """


def _sampling_predicate(mode: str) -> str:
    if mode == DENSE_PERIODIC:
        return "TRUE"
    if mode == UTC_NONOVERLAP:
        # The anchor is the Unix-epoch UTC minute grid, independent of signal
        # state or outcome. For an N-minute horizon this chooses one periodic
        # sample every N minutes, so same-symbol forward windows do not overlap.
        return (
            "mod("
            "floor(extract(epoch FROM observed_minute) / 60)::bigint,"
            "horizon_minutes::bigint"
            ") = 0"
        )
    raise ValueError(f"unsupported sampling mode: {mode}")


_AGGREGATES_SQL = """
    COUNT(*)::bigint AS mature_outcomes,
    COUNT(*) FILTER (WHERE outcome_status='evaluated')::bigint
      AS outcome_evaluated_n,
    COUNT(*) FILTER (WHERE outcome_status='pending')::bigint
      AS outcome_pending_n,
    COUNT(*) FILTER (WHERE outcome_status='not_evaluable')::bigint
      AS outcome_not_evaluable_n,
    (
      100.0 * COUNT(*) FILTER (WHERE outcome_status='evaluated')
      / NULLIF(COUNT(*),0)
    )::float8 AS outcome_evaluated_pct,

    COUNT(*) FILTER (WHERE decision_status='evaluable')::bigint
      AS decision_evaluable_n,
    COUNT(*) FILTER (WHERE decision_status='not_evaluable')::bigint
      AS decision_not_evaluable_n,
    (
      100.0 * COUNT(*) FILTER (WHERE decision_status='evaluable')
      / NULLIF(COUNT(*),0)
    )::float8 AS decision_evaluable_pct,

    COUNT(*) FILTER (WHERE actionable)::bigint AS actionable_mature_n,
    COUNT(*) FILTER (
      WHERE actionable AND outcome_status='evaluated'
    )::bigint AS actionable_evaluated_n,
    (
      100.0 * COUNT(*) FILTER (
        WHERE actionable AND outcome_status='evaluated'
      )
      / NULLIF(COUNT(*) FILTER (WHERE actionable),0)
    )::float8 AS actionable_outcome_coverage_pct,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND (
          directional_return_pct IS NULL
          OR mfe_pct IS NULL
          OR mae_pct IS NULL
        )
    )::bigint AS directional_metric_anomalies,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND direction IN ('neutral','unavailable')
        AND (
          directional_return_pct IS NOT NULL
          OR mfe_pct IS NOT NULL
          OR mae_pct IS NOT NULL
        )
    )::bigint AS nondirectional_metric_anomalies,

    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS gross_expectancy_pct,
    percentile_cont(0.10) WITHIN GROUP (ORDER BY directional_return_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS directional_return_p10_pct,
    percentile_cont(0.25) WITHIN GROUP (ORDER BY directional_return_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS directional_return_p25_pct,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY directional_return_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS directional_return_median_pct,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY directional_return_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS directional_return_p75_pct,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY directional_return_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS directional_return_p90_pct,
    MIN(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS directional_return_min_pct,
    MAX(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS directional_return_max_pct,
    STDDEV_SAMP(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS directional_return_stddev_pct,

    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct > 0
      )
      / NULLIF(
          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND actionable
              AND directional_return_pct IS NOT NULL
          ),
          0
        )
    )::float8 AS gross_hit_rate_pct,

    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct > 0
    ) AS average_winner_pct,
    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct < 0
    ) AS average_loser_pct,
    (
      AVG(directional_return_pct) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct > 0
      )
      /
      NULLIF(
        ABS(
          AVG(directional_return_pct) FILTER (
            WHERE outcome_status='evaluated'
              AND actionable
              AND directional_return_pct < 0
          )
        ),
        0.0
      )
    )::float8 AS payoff_ratio,

    (
      COALESCE(
        SUM(directional_return_pct) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND directional_return_pct > 0
        ),
        0.0
      )
      /
      NULLIF(
        ABS(
          COALESCE(
            SUM(directional_return_pct) FILTER (
              WHERE outcome_status='evaluated'
                AND actionable
                AND directional_return_pct < 0
            ),
            0.0
          )
        ),
        0.0
      )
    )::float8 AS observation_profit_factor,

    AVG(mfe_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS mfe_mean_pct,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY mfe_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mfe_median_pct,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY mfe_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mfe_p75_pct,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY mfe_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mfe_p90_pct,

    AVG(mae_pct) FILTER (
      WHERE outcome_status='evaluated' AND actionable
    ) AS mae_mean_pct,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY mae_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mae_median_pct,
    percentile_cont(0.75) WITHIN GROUP (ORDER BY mae_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mae_p75_pct,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY mae_pct)
      FILTER (WHERE outcome_status='evaluated' AND actionable)
      AS mae_p90_pct,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated' AND direction='neutral'
    )::bigint AS neutral_evaluated_n,
    AVG(ABS(market_return_pct)) FILTER (
      WHERE outcome_status='evaluated' AND direction='neutral'
    ) AS neutral_abs_market_return_mean_pct,
    percentile_cont(0.50) WITHIN GROUP (ORDER BY ABS(market_return_pct))
      FILTER (WHERE outcome_status='evaluated' AND direction='neutral')
      AS neutral_abs_market_return_median_pct,
    percentile_cont(0.90) WITHIN GROUP (ORDER BY ABS(market_return_pct))
      FILTER (WHERE outcome_status='evaluated' AND direction='neutral')
      AS neutral_abs_market_return_p90_pct
"""


def _aggregate_query(mode: str, dimensions: tuple[str, ...]) -> str:
    predicate = _sampling_predicate(mode)
    columns = (*dimensions, "horizon_minutes")
    select_prefix = ",\n    ".join(columns)
    group_clause = ", ".join(columns)
    order_clause = ", ".join(columns)
    return (
        _cohort_cte()
        + "\nSELECT\n    "
        + select_prefix
        + ",\n"
        + _AGGREGATES_SQL
        + "\nFROM cohort\n"
        + f"WHERE {predicate}\n"
        + f"GROUP BY {group_clause}\n"
        + f"ORDER BY {order_clause}\n"
    )


async def _fetch_corpus_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: BacktestOptions,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        WITH scoped AS (
          SELECT
            obs.observation_id,
            obs.observed_at,
            obs.is_periodic,
            obs.is_transition,
            obs.logic_version,
            obs.evidence_version,
            obs.sampling_version,
            frame.frame_id,
            frame.context_version
          FROM signal_observation AS obs
          LEFT JOIN signal_replay_frame AS frame
            ON frame.observation_id=obs.observation_id
          WHERE obs.signal_family='scalp'
            AND obs.observed_at >= $1
            AND obs.observed_at < $2
            AND (
              cardinality($7::text[]) = 0
              OR obs.symbol=ANY($7::text[])
            )
        )
        SELECT
          COUNT(*)::bigint AS all_observations,
          COUNT(*) FILTER (WHERE is_periodic)::bigint AS periodic_observations,
          COUNT(*) FILTER (
            WHERE is_transition AND NOT is_periodic
          )::bigint AS transition_only_observations_excluded,
          COUNT(*) FILTER (
            WHERE is_periodic AND frame_id IS NULL
          )::bigint AS periodic_without_replay_frame,
          COUNT(*) FILTER (
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND logic_version=$3
              AND evidence_version=$4
              AND sampling_version=$5
              AND context_version=$6
          )::bigint AS compatible_periodic_observations,
          COUNT(*) FILTER (
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND NOT (
                logic_version=$3
                AND evidence_version=$4
                AND sampling_version=$5
                AND context_version=$6
              )
          )::bigint AS version_excluded_periodic_observations,
          MIN(observed_at) FILTER (
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND logic_version=$3
              AND evidence_version=$4
              AND sampling_version=$5
              AND context_version=$6
          ) AS compatible_observed_at_min,
          MAX(observed_at) FILTER (
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND logic_version=$3
              AND evidence_version=$4
              AND sampling_version=$5
              AND context_version=$6
          ) AS compatible_observed_at_max,
          MAX(observation_id) FILTER (
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND logic_version=$3
              AND evidence_version=$4
              AND sampling_version=$5
              AND context_version=$6
          ) AS compatible_max_observation_id
        FROM scoped
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
    )
    return dict(row) if row else {}


async def _fetch_outcome_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: BacktestOptions,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        WITH compatible AS (
          SELECT obs.observation_id
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
        )
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
          )::bigint AS mature_not_evaluable_rows,
          MAX(out.outcome_id) AS max_outcome_id
        FROM compatible AS c
        LEFT JOIN signal_outcome AS out
          ON out.observation_id=c.observation_id
         AND out.outcome_version=$7
         AND out.horizon_minutes=ANY($9::integer[])
        """,
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.outcome_version,
        list(options.symbols),
        list(options.horizons),
    )
    return dict(row) if row else {}


def _decorate_rows(
    rows: list[asyncpg.Record],
    *,
    min_group_n: int,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        actionable_n = int(row.get("actionable_evaluated_n") or 0)
        neutral_n = int(row.get("neutral_evaluated_n") or 0)
        row["actionable_meets_min_group_n"] = actionable_n >= min_group_n
        row["neutral_meets_min_group_n"] = neutral_n >= min_group_n
        decorated.append(row)
    return decorated


async def _fetch_aggregate_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    dimensions: tuple[str, ...],
    window_start: datetime,
    snapshot_at: datetime,
    options: BacktestOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _aggregate_query(mode, dimensions),
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.outcome_version,
        list(options.symbols),
        list(options.horizons),
    )
    return _decorate_rows(rows, min_group_n=options.min_group_n)


async def build_signal_backtest_report(
    conn: asyncpg.Connection,
    options: BacktestOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only research report from immutable PR4/PR5/PR6 artifacts.

    This does not reconstruct historical market state, does not create trades,
    and does not compound overlapping observations into an equity curve.
    """

    opts = options or BacktestOptions()
    validate_backtest_options(opts)

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

    compatible = int(corpus.get("compatible_periodic_observations") or 0)
    expected_outcomes = compatible * len(opts.horizons)
    actual_outcomes = int(outcome_summary.get("requested_outcome_rows") or 0)
    outcome_summary["expected_outcome_rows"] = expected_outcomes
    outcome_summary["missing_or_wrong_version_outcome_rows"] = max(
        0,
        expected_outcomes - actual_outcomes,
    )

    views: dict[str, Any] = {}
    for mode in opts.sampling_modes:
        overall = await _fetch_aggregate_rows(
            conn,
            mode=mode,
            dimensions=(),
            window_start=window_start,
            snapshot_at=snapshot_at,
            options=opts,
        )
        groups = (
            await _fetch_aggregate_rows(
                conn,
                mode=mode,
                dimensions=opts.group_by,
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            )
            if opts.group_by
            else overall
        )
        views[mode] = {
            "overall_by_horizon": overall,
            "groups": groups,
        }

    return {
        "report_version": BACKTEST_REPORT_VERSION,
        "generated_at": snapshot_at,
        "window_start": window_start,
        "window_end": snapshot_at,
        "lookback_days": opts.lookback_days,
        "symbols": list(opts.symbols),
        "horizons_minutes": list(opts.horizons),
        "group_by": list(opts.group_by),
        "min_group_n": opts.min_group_n,
        "versions": {
            "logic_version": opts.logic_version,
            "evidence_version": opts.evidence_version,
            "sampling_version": opts.sampling_version,
            "context_version": opts.context_version,
            "outcome_version": opts.outcome_version,
        },
        "methodology": {
            "signal_family": "scalp",
            "primary_grid": "is_periodic=true only",
            "transition_only_rows_excluded": True,
            "replay_frame_required": True,
            "mature_outcome_rule": "signal_outcome.due_at <= generated_at",
            "dense_periodic_warning": (
                "Forward windows can overlap; rows are observations, not independent trades."
            ),
            "utc_nonoverlap_rule": (
                "Unix-epoch UTC minute index modulo horizon_minutes = 0; "
                "selection is independent of signal state and outcome."
            ),
            "gross_returns_only": True,
            "fees_slippage_included": False,
            "equity_curve_computed": False,
            "sharpe_computed": False,
            "compounding_computed": False,
        },
        "corpus": {
            **corpus,
            **outcome_summary,
        },
        "views": views,
    }
