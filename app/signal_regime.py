from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.metrics import REGIME_LOGIC_VERSION
from app.signal_attribution import (
    ATTRIBUTION_SPEC_VERSION,
    COMPONENT_WEIGHTS,
    SCALP_COMPONENTS,
    _component_values_sql,
)
from app.signal_backtest import (
    DENSE_PERIODIC,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
)
from app.signal_ledger import SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

REGIME_ANALYSIS_REPORT_VERSION = 1
REGIME_ANALYSIS_SPEC_VERSION = 1
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MIN_GROUP_N = 30
REGIME_DIRECTION_THRESHOLD = 20.0
DEFAULT_EVIDENCE_VERSION = 1

STRONG_BEARISH = "strong_bearish"
BEARISH = "bearish"
BALANCED = "balanced"
BULLISH = "bullish"
STRONG_BULLISH = "strong_bullish"


@dataclass(frozen=True, slots=True)
class RegimeAnalysisOptions:
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    symbols: tuple[str, ...] = ()
    horizons: tuple[int, ...] = OUTCOME_HORIZONS_MINUTES
    components: tuple[str, ...] = SCALP_COMPONENTS
    sampling_modes: tuple[str, ...] = SAMPLING_MODES
    min_group_n: int = DEFAULT_MIN_GROUP_N
    logic_version: str = SCALP_SIGNAL_LOGIC_VERSION
    evidence_version: int = DEFAULT_EVIDENCE_VERSION
    sampling_version: int = SIGNAL_SAMPLING_VERSION
    context_version: int = REPLAY_CONTEXT_VERSION
    outcome_version: int = OUTCOME_VERSION


def validate_regime_analysis_options(options: RegimeAnalysisOptions) -> None:
    if not 1 <= options.lookback_days <= 3650:
        raise ValueError("lookback_days must be between 1 and 3650")
    if not 1 <= options.min_group_n <= 1_000_000:
        raise ValueError("min_group_n must be between 1 and 1000000")

    # Regime analysis v1 is intentionally bound to the same immutable research
    # contracts as PR7/PR8. A future scoring kernel needs an explicit new spec.
    if options.logic_version != SCALP_SIGNAL_LOGIC_VERSION:
        raise ValueError(
            "unsupported regime-analysis logic_version; register a new regime spec"
        )
    if ATTRIBUTION_SPEC_VERSION != 1:
        raise RuntimeError(
            "PR9 regime analysis requires PR8 attribution spec version 1"
        )

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
    unsupported_horizons = sorted(
        set(options.horizons) - set(OUTCOME_HORIZONS_MINUTES)
    )
    if unsupported_horizons:
        raise ValueError(f"unsupported horizons: {unsupported_horizons}")

    if len(set(options.symbols)) != len(options.symbols):
        raise ValueError("duplicate symbols are not allowed")
    if any(not symbol.strip() for symbol in options.symbols):
        raise ValueError("symbols must be non-empty")

    if not options.components:
        raise ValueError("at least one component is required")
    if len(set(options.components)) != len(options.components):
        raise ValueError("duplicate components are not allowed")
    unsupported_components = sorted(set(options.components) - set(SCALP_COMPONENTS))
    if unsupported_components:
        raise ValueError(f"unsupported components: {unsupported_components}")

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


def _regime_status_sql(prefix: str = "obs") -> str:
    return f"""
    CASE
      WHEN {prefix}.evidence_version IN (3,4,5)
        AND {prefix}.regime_logic_version IS DISTINCT FROM {REGIME_LOGIC_VERSION}
      THEN 'unavailable'
      WHEN {prefix}.regime_score IS NULL
        OR {prefix}.regime_label IS NULL
        OR {prefix}.regime_label = 'Sin datos suficientes'
        OR {prefix}.metrics_snapshot_ts IS NULL
        OR {prefix}.price_cutoff_at IS NULL
        OR {prefix}.metrics_cutoff_at IS NULL
      THEN 'unavailable'
      WHEN {prefix}.metrics_snapshot_ts > {prefix}.observed_at
        OR {prefix}.price_cutoff_at > {prefix}.observed_at
        OR {prefix}.metrics_cutoff_at > {prefix}.observed_at
      THEN 'invalid_future_provenance'
      ELSE 'available'
    END
    """


def _score_band_sql(score_expr: str, status_expr: str) -> str:
    return f"""
    CASE
      WHEN {status_expr} <> 'available' THEN 'unavailable'
      WHEN {score_expr} < -60.0 THEN '{STRONG_BEARISH}'
      WHEN {score_expr} < -20.0 THEN '{BEARISH}'
      WHEN {score_expr} <= 20.0 THEN '{BALANCED}'
      WHEN {score_expr} <= 60.0 THEN '{BULLISH}'
      ELSE '{STRONG_BULLISH}'
    END
    """


def _regime_direction_sql(score_expr: str, status_expr: str) -> str:
    return f"""
    CASE
      WHEN {status_expr} <> 'available' THEN 'unavailable'
      WHEN {score_expr} > {REGIME_DIRECTION_THRESHOLD} THEN 'bullish'
      WHEN {score_expr} < {-REGIME_DIRECTION_THRESHOLD} THEN 'bearish'
      ELSE 'balanced'
    END
    """


def _base_cte() -> str:
    status = _regime_status_sql("obs")
    score_band = _score_band_sql("raw.regime_score", "raw.regime_status")
    regime_direction = _regime_direction_sql(
        "raw.regime_score", "raw.regime_status"
    )

    return f"""
    WITH raw AS (
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
        obs.reference_price_source,
        obs.evidence_coverage_pct,
        obs.evidence,
        obs.evidence_version,
        obs.metrics_snapshot_ts,
        obs.regime_score,
        obs.regime_label,
        obs.regime_logic_version,
        obs.price_cutoff_at,
        obs.metrics_cutoff_at,
        frame.context,
        out.outcome_id,
        out.horizon_minutes,
        out.due_at,
        out.status AS outcome_status,
        out.directional_return_pct,
        out.mfe_pct,
        out.mae_pct,
        out.market_return_pct,
        {status} AS regime_status
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
    ),
    base AS (
      SELECT
        raw.*,
        {score_band} AS regime_score_band,
        {regime_direction} AS regime_direction,
        CASE
          WHEN raw.metrics_snapshot_ts IS NULL THEN NULL
          ELSE extract(epoch FROM raw.observed_at - raw.metrics_snapshot_ts)::float8
        END AS regime_snapshot_age_seconds,
        CASE
          WHEN raw.actionable
            AND raw.direction IN ('long','short')
            AND raw.regime_status='available'
          THEN
            (
              CASE raw.direction
                WHEN 'long' THEN 1.0::float8
                WHEN 'short' THEN -1.0::float8
              END
            ) * raw.regime_score / 100.0
          ELSE NULL
        END AS regime_alignment_strength
      FROM raw
    )
    """


_SIGNAL_AGG_SQL = """
    COUNT(*)::bigint AS mature_outcomes,
    COUNT(*) FILTER (WHERE outcome_status='evaluated')::bigint
      AS outcome_evaluated_n,
    COUNT(*) FILTER (WHERE outcome_status='pending')::bigint
      AS outcome_pending_n,
    COUNT(*) FILTER (WHERE outcome_status='not_evaluable')::bigint
      AS outcome_not_evaluable_n,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
        AND directional_return_pct IS NOT NULL
    )::bigint AS actionable_evaluated_n,

    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS gross_expectancy_pct,

    percentile_cont(0.50) WITHIN GROUP (
      ORDER BY directional_return_pct
    ) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS directional_return_median_pct,

    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND directional_return_pct > 0
      )
      /
      NULLIF(
        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND directional_return_pct IS NOT NULL
        ),
        0
      )
    )::float8 AS gross_hit_rate_pct,

    AVG(mfe_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS mfe_mean_pct,

    percentile_cont(0.90) WITHIN GROUP (
      ORDER BY mfe_pct
    ) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS mfe_p90_pct,

    AVG(mae_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS mae_mean_pct,

    percentile_cont(0.90) WITHIN GROUP (
      ORDER BY mae_pct
    ) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS mae_p90_pct,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND direction='neutral'
    )::bigint AS neutral_evaluated_n,

    AVG(ABS(market_return_pct)) FILTER (
      WHERE outcome_status='evaluated'
        AND direction='neutral'
    ) AS neutral_abs_market_return_mean_pct,

    percentile_cont(0.90) WITHIN GROUP (
      ORDER BY ABS(market_return_pct)
    ) FILTER (
      WHERE outcome_status='evaluated'
        AND direction='neutral'
    ) AS neutral_abs_market_return_p90_pct,

    percentile_cont(0.50) WITHIN GROUP (
      ORDER BY regime_snapshot_age_seconds
    ) FILTER (
      WHERE regime_snapshot_age_seconds IS NOT NULL
        AND regime_snapshot_age_seconds >= 0
    ) AS regime_snapshot_age_median_seconds,

    percentile_cont(0.90) WITHIN GROUP (
      ORDER BY regime_snapshot_age_seconds
    ) FILTER (
      WHERE regime_snapshot_age_seconds IS NOT NULL
        AND regime_snapshot_age_seconds >= 0
    ) AS regime_snapshot_age_p90_seconds
"""


_BASELINE_AGG_SQL = """
    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
        AND directional_return_pct IS NOT NULL
    )::bigint AS baseline_actionable_evaluated_n,

    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
    ) AS baseline_gross_expectancy_pct,

    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND directional_return_pct > 0
      )
      /
      NULLIF(
        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND directional_return_pct IS NOT NULL
        ),
        0
      )
    )::float8 AS baseline_gross_hit_rate_pct
"""


def _signal_regime_query(mode: str, dimension: str) -> str:
    if dimension not in {"regime_label", "regime_score_band"}:
        raise ValueError("unsupported regime dimension")
    predicate = _sampling_predicate(mode)

    return (
        _base_cte()
        + f"""
    , sampled AS (
      SELECT *
      FROM base
      WHERE {predicate}
    ),
    grouped AS (
      SELECT
        symbol,
        {dimension},
        horizon_minutes,
        {_SIGNAL_AGG_SQL}
      FROM sampled
      WHERE regime_status='available'
      GROUP BY symbol,{dimension},horizon_minutes
    ),
    baseline AS (
      SELECT
        symbol,
        horizon_minutes,
        {_BASELINE_AGG_SQL}
      FROM sampled
      GROUP BY symbol,horizon_minutes
    )
    SELECT
      g.*,
      b.baseline_actionable_evaluated_n,
      b.baseline_gross_expectancy_pct,
      b.baseline_gross_hit_rate_pct,
      (
        g.gross_expectancy_pct - b.baseline_gross_expectancy_pct
      ) AS expectancy_lift_vs_symbol_pct,
      (
        g.gross_hit_rate_pct - b.baseline_gross_hit_rate_pct
      )::float8 AS hit_rate_lift_vs_symbol_pp
    FROM grouped AS g
    JOIN baseline AS b
      USING(symbol,horizon_minutes)
    ORDER BY symbol,{dimension},horizon_minutes
    """
    )


def _alignment_query(mode: str) -> str:
    predicate = _sampling_predicate(mode)
    return (
        _base_cte()
        + f"""
    , sampled AS (
      SELECT
        *,
        CASE
          WHEN NOT actionable OR direction NOT IN ('long','short')
            THEN 'not_applicable'
          WHEN regime_status <> 'available'
            THEN 'unavailable'
          WHEN regime_direction='balanced'
            THEN 'balanced_regime'
          WHEN (direction='long' AND regime_direction='bullish')
            OR (direction='short' AND regime_direction='bearish')
            THEN 'aligned'
          ELSE 'contrarian'
        END AS regime_alignment
      FROM base
      WHERE {predicate}
    ),
    grouped AS (
      SELECT
        symbol,
        regime_alignment,
        horizon_minutes,
        {_SIGNAL_AGG_SQL}
      FROM sampled
      WHERE actionable
        AND direction IN ('long','short')
      GROUP BY symbol,regime_alignment,horizon_minutes
    ),
    baseline AS (
      SELECT
        symbol,
        horizon_minutes,
        {_BASELINE_AGG_SQL}
      FROM sampled
      GROUP BY symbol,horizon_minutes
    )
    SELECT
      g.*,
      b.baseline_actionable_evaluated_n,
      b.baseline_gross_expectancy_pct,
      b.baseline_gross_hit_rate_pct,
      (
        g.gross_expectancy_pct - b.baseline_gross_expectancy_pct
      ) AS expectancy_lift_vs_symbol_pct,
      (
        g.gross_hit_rate_pct - b.baseline_gross_hit_rate_pct
      )::float8 AS hit_rate_lift_vs_symbol_pp
    FROM grouped AS g
    JOIN baseline AS b
      USING(symbol,horizon_minutes)
    ORDER BY symbol,regime_alignment,horizon_minutes
    """
    )


def _alignment_strength_query(mode: str) -> str:
    predicate = _sampling_predicate(mode)
    return (
        _base_cte()
        + f"""
    , sampled AS (
      SELECT *
      FROM base
      WHERE {predicate}
    )
    SELECT
      symbol,
      horizon_minutes,
      COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND regime_alignment_strength IS NOT NULL
          AND directional_return_pct IS NOT NULL
      )::bigint AS regime_alignment_strength_n,
      corr(
        regime_alignment_strength,
        directional_return_pct
      ) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND regime_alignment_strength IS NOT NULL
          AND directional_return_pct IS NOT NULL
      ) AS regime_alignment_strength_return_corr,
      AVG(regime_alignment_strength) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND regime_alignment_strength IS NOT NULL
      ) AS regime_alignment_strength_mean,
      AVG(ABS(regime_alignment_strength)) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND direction IN ('long','short')
          AND regime_alignment_strength IS NOT NULL
      ) AS regime_alignment_strength_abs_mean
    FROM sampled
    GROUP BY symbol,horizon_minutes
    ORDER BY symbol,horizon_minutes
    """
    )


def _component_regime_query(mode: str) -> str:
    predicate = _sampling_predicate(mode)
    component_sql = _component_values_sql()

    return (
        _base_cte()
        + f"""
    , sampled AS (
      SELECT *
      FROM base
      WHERE {predicate}
    ),
    component_rows AS (
      SELECT
        b.*,
        c.component,
        c.configured_weight,
        c.component_value,
        COALESCE(
          (b.evidence->'missing_components') ? c.component,
          false
        ) AS declared_missing,
        CASE
          WHEN b.outcome_status='evaluated'
            AND b.market_return_pct IS NOT NULL
            AND c.component_value > 0
          THEN b.market_return_pct
          WHEN b.outcome_status='evaluated'
            AND b.market_return_pct IS NOT NULL
            AND c.component_value < 0
          THEN -b.market_return_pct
          ELSE NULL
        END AS standalone_directional_return_pct,
        CASE
          WHEN b.direction='long' THEN c.component_value
          WHEN b.direction='short' THEN -c.component_value
          ELSE NULL
        END AS aligned_component_strength
      FROM sampled AS b
      CROSS JOIN LATERAL (
        {component_sql}
      ) AS c(component,configured_weight,component_value)
      WHERE c.component=ANY($10::text[])
    ),
    grouped AS (
      SELECT
        symbol,
        regime_label,
        component,
        configured_weight,
        horizon_minutes,

        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
        )::bigint AS outcome_evaluated_n,

        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND component_value IS NOT NULL
        )::bigint AS component_measured_evaluated_n,

        COUNT(DISTINCT observation_id) FILTER (
          WHERE (component_value IS NULL) <> declared_missing
        )::bigint AS missing_semantics_mismatch_observations,

        COUNT(standalone_directional_return_pct)::bigint
          AS standalone_directional_n,

        AVG(standalone_directional_return_pct)
          AS standalone_directional_expectancy_pct,

        (
          100.0 * COUNT(*) FILTER (
            WHERE standalone_directional_return_pct > 0
          )
          /
          NULLIF(COUNT(standalone_directional_return_pct),0)
        )::float8 AS standalone_directional_hit_rate_pct,

        corr(component_value,market_return_pct) FILTER (
          WHERE outcome_status='evaluated'
            AND component_value IS NOT NULL
            AND market_return_pct IS NOT NULL
        ) AS component_market_return_corr,

        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND aligned_component_strength > 0
            AND directional_return_pct IS NOT NULL
        )::bigint AS supports_decision_n,

        AVG(directional_return_pct) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND aligned_component_strength > 0
        ) AS supports_decision_expectancy_pct,

        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND aligned_component_strength < 0
            AND directional_return_pct IS NOT NULL
        )::bigint AS opposes_decision_n,

        AVG(directional_return_pct) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND direction IN ('long','short')
            AND aligned_component_strength < 0
        ) AS opposes_decision_expectancy_pct

      FROM component_rows
      WHERE regime_status='available'
      GROUP BY
        symbol,regime_label,component,configured_weight,horizon_minutes
    ),
    baseline AS (
      SELECT
        symbol,
        component,
        horizon_minutes,

        COUNT(standalone_directional_return_pct)::bigint
          AS baseline_standalone_directional_n,

        AVG(standalone_directional_return_pct)
          AS baseline_standalone_directional_expectancy_pct

      FROM component_rows
      WHERE regime_status='available'
      GROUP BY symbol,component,horizon_minutes
    )
    SELECT
      g.*,
      b.baseline_standalone_directional_n,
      b.baseline_standalone_directional_expectancy_pct,
      (
        g.standalone_directional_expectancy_pct
        - b.baseline_standalone_directional_expectancy_pct
      ) AS standalone_expectancy_lift_vs_available_regimes_pct,
      (
        g.supports_decision_expectancy_pct
        - g.opposes_decision_expectancy_pct
      ) AS support_minus_oppose_expectancy_pct
    FROM grouped AS g
    JOIN baseline AS b
      USING(symbol,component,horizon_minutes)
    ORDER BY symbol,regime_label,component,horizon_minutes
    """
    )


def _distribution_query() -> str:
    status = _regime_status_sql("obs")
    score_band = _score_band_sql("scoped.regime_score", "scoped.regime_status")

    return f"""
    WITH scoped AS (
      SELECT
        obs.observation_id,
        obs.symbol,
        obs.observed_at,
        obs.evidence_version,
        obs.regime_score,
        obs.regime_label,
        obs.regime_logic_version,
        obs.metrics_snapshot_ts,
        obs.price_cutoff_at,
        obs.metrics_cutoff_at,
        {status} AS regime_status
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
          cardinality($7::text[]) = 0
          OR obs.symbol=ANY($7::text[])
        )
    ),
    enriched AS (
      SELECT
        scoped.*,
        {score_band} AS regime_score_band,
        CASE
          WHEN metrics_snapshot_ts IS NULL THEN NULL
          ELSE extract(epoch FROM observed_at-metrics_snapshot_ts)::float8
        END AS regime_snapshot_age_seconds
      FROM scoped
    ),
    grouped AS (
      SELECT
        symbol,
        regime_status,
        COALESCE(regime_label,'<NULL>') AS regime_label,
        regime_score_band,
        COUNT(*)::bigint AS observations,
        percentile_cont(0.50) WITHIN GROUP (
          ORDER BY regime_snapshot_age_seconds
        ) FILTER (
          WHERE regime_snapshot_age_seconds IS NOT NULL
            AND regime_snapshot_age_seconds >= 0
        ) AS regime_snapshot_age_median_seconds,
        percentile_cont(0.90) WITHIN GROUP (
          ORDER BY regime_snapshot_age_seconds
        ) FILTER (
          WHERE regime_snapshot_age_seconds IS NOT NULL
            AND regime_snapshot_age_seconds >= 0
        ) AS regime_snapshot_age_p90_seconds
      FROM enriched
      GROUP BY symbol,regime_status,COALESCE(regime_label,'<NULL>'),regime_score_band
    )
    SELECT
      grouped.*,
      (
        100.0 * observations
        / NULLIF(SUM(observations) OVER (PARTITION BY symbol),0)
      )::float8 AS observation_share_pct
    FROM grouped
    ORDER BY symbol,regime_status,regime_label,regime_score_band
    """


async def _fetch_corpus_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> dict[str, Any]:
    status = _regime_status_sql("obs")
    row = await conn.fetchrow(
        f"""
        WITH scoped AS (
          SELECT
            obs.observation_id,
            obs.observed_at,
            obs.is_periodic,
            obs.is_transition,
            obs.logic_version,
            obs.evidence_version,
            obs.sampling_version,
            obs.regime_logic_version,
            obs.metrics_snapshot_ts,
            obs.regime_score,
            obs.regime_label,
            obs.price_cutoff_at,
            obs.metrics_cutoff_at,
            frame.frame_id,
            frame.context_version,
            {status} AS regime_status
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
        ),
        compatible AS (
          SELECT *
          FROM scoped
          WHERE is_periodic
            AND frame_id IS NOT NULL
            AND logic_version=$3
            AND evidence_version=$4
            AND sampling_version=$5
            AND context_version=$6
        )
        SELECT
          (SELECT COUNT(*) FROM scoped)::bigint AS all_observations,
          (SELECT COUNT(*) FROM scoped WHERE is_periodic)::bigint
            AS periodic_observations,
          (
            SELECT COUNT(*) FROM scoped
            WHERE is_transition AND NOT is_periodic
          )::bigint AS transition_only_observations_excluded,
          (
            SELECT COUNT(*) FROM scoped
            WHERE is_periodic AND frame_id IS NULL
          )::bigint AS periodic_without_replay_frame,
          (
            SELECT COUNT(*) FROM compatible
          )::bigint AS compatible_periodic_observations,
          (
            SELECT COUNT(*) FROM scoped
            WHERE is_periodic
              AND frame_id IS NOT NULL
              AND NOT (
                logic_version=$3
                AND evidence_version=$4
                AND sampling_version=$5
                AND context_version=$6
              )
          )::bigint AS version_excluded_periodic_observations,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_status='available'
          )::bigint AS regime_available_periodic_observations,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_status='unavailable'
          )::bigint AS regime_unavailable_periodic_observations,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_status='invalid_future_provenance'
          )::bigint AS regime_invalid_future_provenance_observations,

          (
            SELECT COUNT(*) FROM compatible
            WHERE metrics_snapshot_ts > observed_at
          )::bigint AS future_metrics_snapshot_anomalies,

          (
            SELECT COUNT(*) FROM compatible
            WHERE price_cutoff_at > observed_at
          )::bigint AS future_price_cutoff_anomalies,

          (
            SELECT COUNT(*) FROM compatible
            WHERE metrics_cutoff_at > observed_at
          )::bigint AS future_metrics_cutoff_anomalies,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_score IS NOT NULL
              AND (regime_score < -100.0 OR regime_score > 100.0)
          )::bigint AS regime_score_range_anomalies,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_score IS NULL
              AND regime_label IS NOT NULL
              AND regime_label <> 'Sin datos suficientes'
          )::bigint AS regime_label_without_score_anomalies,

          (
            SELECT COUNT(*) FROM compatible
            WHERE regime_score IS NOT NULL
              AND (
                regime_label IS NULL
                OR regime_label = 'Sin datos suficientes'
              )
          )::bigint AS regime_score_without_label_anomalies,

          (
            SELECT MIN(observed_at) FROM compatible
          ) AS compatible_observed_at_min,

          (
            SELECT MAX(observed_at) FROM compatible
          ) AS compatible_observed_at_max

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
    options: RegimeAnalysisOptions,
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
          )::bigint AS mature_not_evaluable_rows
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


def _decorate_signal_rows(
    rows: list[asyncpg.Record],
    *,
    min_group_n: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        n = int(row.get("actionable_evaluated_n") or 0)
        baseline_n = int(row.get("baseline_actionable_evaluated_n") or 0)
        row["meets_min_group_n"] = n >= min_group_n
        row["baseline_meets_min_group_n"] = baseline_n >= min_group_n
        result.append(row)
    return result


def _decorate_component_rows(
    rows: list[asyncpg.Record],
    *,
    min_group_n: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        standalone_n = int(row.get("standalone_directional_n") or 0)
        baseline_n = int(row.get("baseline_standalone_directional_n") or 0)
        support_n = int(row.get("supports_decision_n") or 0)
        oppose_n = int(row.get("opposes_decision_n") or 0)
        row["standalone_meets_min_group_n"] = standalone_n >= min_group_n
        row["baseline_meets_min_group_n"] = baseline_n >= min_group_n
        row["support_meets_min_group_n"] = support_n >= min_group_n
        row["oppose_meets_min_group_n"] = oppose_n >= min_group_n
        row["support_vs_oppose_meets_min_group_n"] = (
            support_n >= min_group_n and oppose_n >= min_group_n
        )
        result.append(row)
    return result


async def _fetch_signal_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    dimension: str,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _signal_regime_query(mode, dimension),
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
    return _decorate_signal_rows(rows, min_group_n=options.min_group_n)


async def _fetch_alignment_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _alignment_query(mode),
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
    return _decorate_signal_rows(rows, min_group_n=options.min_group_n)


async def _fetch_alignment_strength_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _alignment_strength_query(mode),
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
    result: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        row["meets_min_group_n"] = (
            int(row.get("regime_alignment_strength_n") or 0)
            >= options.min_group_n
        )
        result.append(row)
    return result


async def _fetch_component_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _component_regime_query(mode),
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        options.outcome_version,
        list(options.symbols),
        list(options.horizons),
        list(options.components),
    )
    return _decorate_component_rows(rows, min_group_n=options.min_group_n)


async def _fetch_distribution(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: RegimeAnalysisOptions,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _distribution_query(),
        window_start,
        snapshot_at,
        options.logic_version,
        options.evidence_version,
        options.sampling_version,
        options.context_version,
        list(options.symbols),
    )
    return [dict(row) for row in rows]


async def build_signal_regime_report(
    conn: asyncpg.Connection,
    options: RegimeAnalysisOptions | None = None,
) -> dict[str, Any]:
    """Build read-only regime-dependence research from immutable decision-time data."""

    opts = options or RegimeAnalysisOptions()
    validate_regime_analysis_options(opts)

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

    distribution = await _fetch_distribution(
        conn,
        window_start=window_start,
        snapshot_at=snapshot_at,
        options=opts,
    )

    views: dict[str, Any] = {}
    for mode in opts.sampling_modes:
        views[mode] = {
            "signal_by_regime_label": await _fetch_signal_rows(
                conn,
                mode=mode,
                dimension="regime_label",
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            ),
            "signal_by_regime_score_band": await _fetch_signal_rows(
                conn,
                mode=mode,
                dimension="regime_score_band",
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            ),
            "signal_regime_alignment": await _fetch_alignment_rows(
                conn,
                mode=mode,
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            ),
            "alignment_strength": await _fetch_alignment_strength_rows(
                conn,
                mode=mode,
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            ),
            "component_by_regime_label": await _fetch_component_rows(
                conn,
                mode=mode,
                window_start=window_start,
                snapshot_at=snapshot_at,
                options=opts,
            ),
        }

    return {
        "report_version": REGIME_ANALYSIS_REPORT_VERSION,
        "regime_analysis_spec_version": REGIME_ANALYSIS_SPEC_VERSION,
        "attribution_spec_version": ATTRIBUTION_SPEC_VERSION,
        "generated_at": snapshot_at,
        "window_start": window_start,
        "window_end": snapshot_at,
        "lookback_days": opts.lookback_days,
        "symbols": list(opts.symbols),
        "horizons_minutes": list(opts.horizons),
        "components": list(opts.components),
        "component_weights": {
            component: COMPONENT_WEIGHTS[component]
            for component in opts.components
        },
        "min_group_n": opts.min_group_n,
        "versions": {
            "logic_version": opts.logic_version,
            "evidence_version": opts.evidence_version,
            "sampling_version": opts.sampling_version,
            "context_version": opts.context_version,
            "outcome_version": opts.outcome_version,
        },
        "regime_contract": {
            "source": (
                "immutable signal_observation regime_score/regime_label and "
                "metrics snapshot provenance captured by PR4"
            ),
            "future_market_state_queries": False,
            "regime_direction_threshold_abs_score": REGIME_DIRECTION_THRESHOLD,
            "score_bands": {
                STRONG_BEARISH: "score < -60",
                BEARISH: "-60 <= score < -20",
                BALANCED: "-20 <= score <= 20",
                BULLISH: "20 < score <= 60",
                STRONG_BULLISH: "score > 60",
            },
            "available_requires": [
                "regime_score present",
                "regime_label present and not Sin datos suficientes",
                "metrics_snapshot_ts present and <= observed_at",
                "price_cutoff_at present and <= observed_at",
                "metrics_cutoff_at present and <= observed_at",
            ],
            "stale_snapshot_hard_exclusion": False,
            "stale_snapshot_note": (
                "snapshot age is reported, not hidden; PR9 does not invent an "
                "unvalidated age threshold after the fact"
            ),
        },
        "methodology": {
            "signal_family": "scalp",
            "primary_grid": "is_periodic=true only",
            "transition_only_rows_excluded": True,
            "replay_frame_required": True,
            "mature_outcome_rule": "signal_outcome.due_at <= generated_at",
            "signal_lift_baseline": (
                "same symbol/horizon/sampling mode over all compatible mature "
                "actionable observations, including unavailable regime rows"
            ),
            "component_lift_baseline": (
                "same symbol/component/horizon/sampling mode over available regimes"
            ),
            "alignment": (
                "long with bullish or short with bearish = aligned; inverse = "
                "contrarian; abs(regime_score)<=20 = balanced_regime"
            ),
            "dense_periodic_warning": (
                "forward windows can overlap; observations are not independent trades"
            ),
            "utc_nonoverlap_rule": (
                "Unix-epoch UTC minute index modulo horizon_minutes = 0"
            ),
            "causal_claims": False,
            "automatic_weight_changes": False,
            "p_values_computed": False,
            "fees_slippage_included": False,
            "equity_curve_computed": False,
        },
        "corpus": {
            **corpus,
            **outcome_summary,
        },
        "regime_distribution": distribution,
        "views": views,
    }
