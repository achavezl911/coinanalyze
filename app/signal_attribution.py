from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.signal_backtest import (
    ALLOWED_GROUP_DIMENSIONS,
    DENSE_PERIODIC,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
)
from app.signal_ledger import SIGNAL_EVIDENCE_VERSION, SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

ATTRIBUTION_REPORT_VERSION = 1
ATTRIBUTION_SPEC_VERSION = 1
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_MIN_GROUP_N = 30
DEFAULT_GROUP_BY = ("symbol",)

# These are the configured scalp-summary-v1 component weights. They are
# descriptive provenance, not fitted attribution coefficients and PR8 never
# changes them.
COMPONENT_WEIGHTS: dict[str, float] = {
    "fut_delta": 20.0,
    "spot_fut_divergence": 15.0,
    "book": 20.0,
    "absorption": 20.0,
    "liquidations": 10.0,
    "oi": 10.0,
    "vwap": 5.0,
}
SCALP_COMPONENTS = tuple(COMPONENT_WEIGHTS)


@dataclass(frozen=True, slots=True)
class AttributionOptions:
    lookback_days: int = DEFAULT_LOOKBACK_DAYS
    symbols: tuple[str, ...] = ()
    horizons: tuple[int, ...] = OUTCOME_HORIZONS_MINUTES
    components: tuple[str, ...] = SCALP_COMPONENTS
    group_by: tuple[str, ...] = DEFAULT_GROUP_BY
    sampling_modes: tuple[str, ...] = SAMPLING_MODES
    min_group_n: int = DEFAULT_MIN_GROUP_N
    logic_version: str = SCALP_SIGNAL_LOGIC_VERSION
    evidence_version: int = SIGNAL_EVIDENCE_VERSION
    sampling_version: int = SIGNAL_SAMPLING_VERSION
    context_version: int = REPLAY_CONTEXT_VERSION
    outcome_version: int = OUTCOME_VERSION


def validate_attribution_options(options: AttributionOptions) -> None:
    if not 1 <= options.lookback_days <= 3650:
        raise ValueError("lookback_days must be between 1 and 3650")
    if not 1 <= options.min_group_n <= 1_000_000:
        raise ValueError("min_group_n must be between 1 and 1000000")

    # The component extractor below is deliberately tied to the v1 decision
    # kernel. A future material kernel change needs a separately registered
    # attribution spec; silently applying this extractor to v2 would be wrong.
    if options.logic_version != SCALP_SIGNAL_LOGIC_VERSION:
        raise ValueError(
            "unsupported attribution logic_version; register a version-specific extractor"
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
    unsupported_horizons = sorted(set(options.horizons) - set(OUTCOME_HORIZONS_MINUTES))
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


def _clamp(expression: str) -> str:
    return f"GREATEST(-1.0::float8, LEAST(1.0::float8, ({expression})::float8))"


def _component_values_sql() -> str:
    """Version-specific SQL extractor for the seven scalp-summary-v1 votes.

    The returned value is the exact signed component vote after the same
    [-1, +1] clamp used by score_component(). Positive is bullish, negative is
    bearish, zero is a measured neutral vote and NULL means not measured.
    """

    fut_delta = f"""
    CASE
      WHEN NULLIF((b.evidence->>'fut_volume_1m')::float8, 0.0) IS NULL
        OR (b.evidence->>'fut_delta_1m') IS NULL
      THEN NULL
      ELSE {_clamp('''
        (
          (b.evidence->>'fut_delta_1m')::float8
          / NULLIF((b.evidence->>'fut_volume_1m')::float8, 0.0)
        ) * 0.65
        +
        (
          CASE
            WHEN NULLIF((b.context->>'fut_volume_3m')::float8, 0.0) IS NULL
              OR (b.evidence->>'fut_delta_3m') IS NULL
            THEN 0.0
            ELSE
              (b.evidence->>'fut_delta_3m')::float8
              / NULLIF((b.context->>'fut_volume_3m')::float8, 0.0)
          END
        ) * 0.35
    ''')}
    END
    """

    spot_fut = "(b.evidence->>'spot_fut_divergence_norm')::float8"

    book = f"""
    CASE
      WHEN (b.evidence->>'imbalance_l5') IS NULL THEN NULL
      ELSE {_clamp("(((b.evidence->>'imbalance_l5')::float8 - 0.5) * 2.0)")}
    END
    """

    absorption = """
    CASE b.evidence->>'absorption'
      WHEN 'Absorción de ventas' THEN 1.0::float8
      WHEN 'Absorción fuerte de ventas' THEN 1.0::float8
      WHEN 'Absorción de compras' THEN -1.0::float8
      WHEN 'Absorción fuerte de compras' THEN -1.0::float8
      WHEN 'Neutra' THEN 0.0::float8
      WHEN 'Sin señal' THEN 0.0::float8
      ELSE NULL
    END
    """

    liquidations = """
    CASE
      WHEN COALESCE((b.evidence->>'liquidations_measured')::boolean, false) IS NOT TRUE
      THEN NULL
      ELSE
        CASE
          WHEN (
            COALESCE((b.evidence->>'long_liq_5m')::float8, 0.0)
            + COALESCE((b.evidence->>'short_liq_5m')::float8, 0.0)
          ) = 0.0
          THEN 0.0::float8
          ELSE
            (
              COALESCE((b.evidence->>'short_liq_5m')::float8, 0.0)
              - COALESCE((b.evidence->>'long_liq_5m')::float8, 0.0)
            )
            /
            NULLIF(
              COALESCE((b.evidence->>'short_liq_5m')::float8, 0.0)
              + COALESCE((b.evidence->>'long_liq_5m')::float8, 0.0),
              0.0
            )
        END
    END
    """

    oi = f"""
    CASE
      WHEN (b.evidence->>'oi_chg_15m_pct') IS NULL
        OR (b.evidence->>'price_move_15m_pct') IS NULL
      THEN NULL
      WHEN COALESCE((b.evidence->>'oi_contributes_direction')::boolean, false)
        AND (b.evidence->>'oi_directional_support') IS NOT NULL
      THEN {_clamp('''
        (b.evidence->>'oi_directional_support')::float8
        * LEAST(
            1.0::float8,
            ABS((b.evidence->>'oi_chg_15m_pct')::float8) / 0.5
          )
      ''')}
      ELSE 0.0::float8
    END
    """

    vwap = f"""
    CASE
      WHEN (b.evidence->>'vwap_dist_pct') IS NULL THEN NULL
      ELSE {_clamp("((b.evidence->>'vwap_dist_pct')::float8 / 0.25)")}
    END
    """

    return f"""
    VALUES
      ('fut_delta'::text, {COMPONENT_WEIGHTS['fut_delta']}::float8, ({fut_delta})::float8),
      ('spot_fut_divergence'::text, {COMPONENT_WEIGHTS['spot_fut_divergence']}::float8, ({spot_fut})::float8),
      ('book'::text, {COMPONENT_WEIGHTS['book']}::float8, ({book})::float8),
      ('absorption'::text, {COMPONENT_WEIGHTS['absorption']}::float8, ({absorption})::float8),
      ('liquidations'::text, {COMPONENT_WEIGHTS['liquidations']}::float8, ({liquidations})::float8),
      ('oi'::text, {COMPONENT_WEIGHTS['oi']}::float8, ({oi})::float8),
      ('vwap'::text, {COMPONENT_WEIGHTS['vwap']}::float8, ({vwap})::float8)
    """


def _attribution_cte() -> str:
    return f"""
    WITH b AS (
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
        obs.evidence,
        frame.context,
        out.outcome_id,
        out.horizon_minutes,
        out.due_at,
        out.status AS outcome_status,
        out.directional_return_pct,
        out.mfe_pct,
        out.mae_pct,
        out.market_return_pct
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
    component_rows AS (
      SELECT
        b.*,
        c.component,
        c.configured_weight,
        c.component_value,
        COALESCE(
          (b.evidence->'missing_components') ? c.component,
          false
        ) AS declared_missing
      FROM b
      CROSS JOIN LATERAL (
        {_component_values_sql()}
      ) AS c(component, configured_weight, component_value)
      WHERE c.component=ANY($10::text[])
    ),
    scored AS (
      SELECT
        component_rows.*,
        CASE direction
          WHEN 'long' THEN 1.0::float8
          WHEN 'short' THEN -1.0::float8
          ELSE NULL
        END AS decision_sign,
        CASE
          WHEN outcome_status='evaluated'
            AND market_return_pct IS NOT NULL
            AND component_value > 0
          THEN market_return_pct
          WHEN outcome_status='evaluated'
            AND market_return_pct IS NOT NULL
            AND component_value < 0
          THEN -market_return_pct
          ELSE NULL
        END AS standalone_directional_return_pct,
        CASE
          WHEN direction='long' THEN component_value
          WHEN direction='short' THEN -component_value
          ELSE NULL
        END AS aligned_strength
      FROM component_rows
    )
    """


_AGGREGATES_SQL = """
    COUNT(*)::bigint AS mature_outcomes,
    COUNT(*) FILTER (WHERE outcome_status='evaluated')::bigint
      AS outcome_evaluated_n,
    COUNT(*) FILTER (WHERE outcome_status='pending')::bigint
      AS outcome_pending_n,
    COUNT(*) FILTER (WHERE outcome_status='not_evaluable')::bigint
      AS outcome_not_evaluable_n,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value IS NOT NULL
    )::bigint AS component_measured_evaluated_n,
    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value IS NULL
    )::bigint AS component_missing_evaluated_n,
    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND component_value IS NOT NULL
      )
      /
      NULLIF(
        COUNT(*) FILTER (WHERE outcome_status='evaluated'),
        0
      )
    )::float8 AS component_measured_pct,

    COUNT(DISTINCT observation_id) FILTER (
      WHERE (component_value IS NULL) <> declared_missing
    )::bigint AS missing_semantics_mismatch_observations,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value > 0
    )::bigint AS bullish_component_n,
    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value < 0
    )::bigint AS bearish_component_n,
    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value = 0
    )::bigint AS neutral_component_n,

    COUNT(standalone_directional_return_pct)::bigint AS standalone_directional_n,
    AVG(standalone_directional_return_pct)
      AS standalone_directional_expectancy_pct,
    percentile_cont(0.10) WITHIN GROUP (
      ORDER BY standalone_directional_return_pct
    ) FILTER (
      WHERE standalone_directional_return_pct IS NOT NULL
    ) AS standalone_directional_p10_pct,
    percentile_cont(0.50) WITHIN GROUP (
      ORDER BY standalone_directional_return_pct
    ) FILTER (
      WHERE standalone_directional_return_pct IS NOT NULL
    ) AS standalone_directional_median_pct,
    percentile_cont(0.90) WITHIN GROUP (
      ORDER BY standalone_directional_return_pct
    ) FILTER (
      WHERE standalone_directional_return_pct IS NOT NULL
    ) AS standalone_directional_p90_pct,
    (
      100.0 * COUNT(*) FILTER (
        WHERE standalone_directional_return_pct > 0
      )
      /
      NULLIF(COUNT(standalone_directional_return_pct), 0)
    )::float8 AS standalone_directional_hit_rate_pct,

    corr(component_value, market_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND component_value IS NOT NULL
        AND market_return_pct IS NOT NULL
    ) AS component_market_return_corr,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
        AND directional_return_pct IS NOT NULL
    )::bigint AS actionable_evaluated_n,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
        AND directional_return_pct IS NOT NULL
        AND aligned_strength IS NOT NULL
    )::bigint AS decision_component_measured_n,

    corr(aligned_strength, directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND direction IN ('long','short')
        AND aligned_strength IS NOT NULL
        AND directional_return_pct IS NOT NULL
    ) AS aligned_strength_directional_return_corr,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength > 0
    )::bigint AS supports_decision_n,
    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength > 0
    ) AS supports_decision_expectancy_pct,
    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct > 0
          AND aligned_strength > 0
      )
      /
      NULLIF(
        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND directional_return_pct IS NOT NULL
            AND aligned_strength > 0
        ),
        0
      )
    )::float8 AS supports_decision_hit_rate_pct,
    AVG(mfe_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND aligned_strength > 0
    ) AS supports_decision_mfe_mean_pct,
    AVG(mae_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND aligned_strength > 0
    ) AS supports_decision_mae_mean_pct,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength < 0
    )::bigint AS opposes_decision_n,
    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength < 0
    ) AS opposes_decision_expectancy_pct,
    (
      100.0 * COUNT(*) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct > 0
          AND aligned_strength < 0
      )
      /
      NULLIF(
        COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND directional_return_pct IS NOT NULL
            AND aligned_strength < 0
        ),
        0
      )
    )::float8 AS opposes_decision_hit_rate_pct,
    AVG(mfe_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND aligned_strength < 0
    ) AS opposes_decision_mfe_mean_pct,
    AVG(mae_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND aligned_strength < 0
    ) AS opposes_decision_mae_mean_pct,

    COUNT(*) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength = 0
    )::bigint AS neutral_to_decision_n,
    AVG(directional_return_pct) FILTER (
      WHERE outcome_status='evaluated'
        AND actionable
        AND directional_return_pct IS NOT NULL
        AND aligned_strength = 0
    ) AS neutral_to_decision_expectancy_pct,

    (
      AVG(directional_return_pct) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct IS NOT NULL
          AND aligned_strength > 0
      )
      -
      AVG(directional_return_pct) FILTER (
        WHERE outcome_status='evaluated'
          AND actionable
          AND directional_return_pct IS NOT NULL
          AND aligned_strength < 0
      )
    ) AS support_minus_oppose_expectancy_pct,

    (
      (
        100.0 * COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND directional_return_pct > 0
            AND aligned_strength > 0
        )
        /
        NULLIF(
          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND actionable
              AND directional_return_pct IS NOT NULL
              AND aligned_strength > 0
          ),
          0
        )
      )
      -
      (
        100.0 * COUNT(*) FILTER (
          WHERE outcome_status='evaluated'
            AND actionable
            AND directional_return_pct > 0
            AND aligned_strength < 0
        )
        /
        NULLIF(
          COUNT(*) FILTER (
            WHERE outcome_status='evaluated'
              AND actionable
              AND directional_return_pct IS NOT NULL
              AND aligned_strength < 0
          ),
          0
        )
      )
    )::float8 AS support_minus_oppose_hit_rate_pp
"""


def _aggregate_query(mode: str, dimensions: tuple[str, ...]) -> str:
    predicate = _sampling_predicate(mode)
    columns = (*dimensions, "component", "configured_weight", "horizon_minutes")
    select_prefix = ",\n    ".join(columns)
    group_clause = ", ".join(columns)
    order_clause = ", ".join(columns)
    return (
        _attribution_cte()
        + "\nSELECT\n    "
        + select_prefix
        + ",\n"
        + _AGGREGATES_SQL
        + "\nFROM scored\n"
        + f"WHERE {predicate}\n"
        + f"GROUP BY {group_clause}\n"
        + f"ORDER BY {order_clause}\n"
    )


async def _fetch_corpus_summary(
    conn: asyncpg.Connection,
    *,
    window_start: datetime,
    snapshot_at: datetime,
    options: AttributionOptions,
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
          ) AS compatible_observed_at_max
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
    options: AttributionOptions,
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


def _decorate_rows(
    rows: list[asyncpg.Record],
    *,
    min_group_n: int,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for record in rows:
        row = dict(record)
        standalone_n = int(row.get("standalone_directional_n") or 0)
        measured_n = int(row.get("component_measured_evaluated_n") or 0)
        decision_n = int(row.get("decision_component_measured_n") or 0)
        support_n = int(row.get("supports_decision_n") or 0)
        oppose_n = int(row.get("opposes_decision_n") or 0)
        row["standalone_meets_min_group_n"] = standalone_n >= min_group_n
        row["market_corr_meets_min_group_n"] = measured_n >= min_group_n
        row["decision_lens_meets_min_group_n"] = decision_n >= min_group_n
        row["support_meets_min_group_n"] = support_n >= min_group_n
        row["oppose_meets_min_group_n"] = oppose_n >= min_group_n
        row["support_vs_oppose_meets_min_group_n"] = (
            support_n >= min_group_n and oppose_n >= min_group_n
        )
        decorated.append(row)
    return decorated


async def _fetch_aggregate_rows(
    conn: asyncpg.Connection,
    *,
    mode: str,
    dimensions: tuple[str, ...],
    window_start: datetime,
    snapshot_at: datetime,
    options: AttributionOptions,
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
        list(options.components),
    )
    return _decorate_rows(rows, min_group_n=options.min_group_n)


async def build_signal_attribution_report(
    conn: asyncpg.Connection,
    options: AttributionOptions | None = None,
) -> dict[str, Any]:
    """Build a read-only univariate attribution report from frozen research data.

    PR8 measures associations. It does not infer causality, fit weights, alter
    live scoring, create a trading PnL curve, or read later market-state tables.
    """

    opts = options or AttributionOptions()
    validate_attribution_options(opts)

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
            "overall_by_component_horizon": overall,
            "groups": groups,
        }

    return {
        "report_version": ATTRIBUTION_REPORT_VERSION,
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
            "component_value_semantics": (
                "normalized signed scalp-summary-v1 vote after score clamp; "
                "+1 bullish, -1 bearish, 0 measured neutral, null missing"
            ),
            "standalone_lens": (
                "all evaluated periodic rows: component sign is compared with "
                "future market_return_pct; this is association, not a simulated trade"
            ),
            "decision_conditioned_lens": (
                "actionable long/short evaluated rows: component vote is aligned "
                "to the final decision and compared with directional_return_pct"
            ),
            "causal_claims": False,
            "automatic_weight_changes": False,
            "automatic_component_ranking": False,
            "p_values_computed": False,
            "fees_slippage_included": False,
            "equity_curve_computed": False,
            "dense_periodic_warning": (
                "forward windows can overlap; observations are not independent trades"
            ),
            "utc_nonoverlap_rule": (
                "Unix-epoch UTC minute index modulo horizon_minutes = 0; "
                "selection is independent of component value, state and outcome"
            ),
        },
        "corpus": {
            **corpus,
            **outcome_summary,
        },
        "views": views,
    }
