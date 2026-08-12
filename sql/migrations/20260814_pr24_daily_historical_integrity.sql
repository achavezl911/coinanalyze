-- PR24: prospective daily projection provenance and immutable verdict outcomes.
-- No historical rows are rewritten or backfilled.
BEGIN;

ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS updated_at timestamptz;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at DROP DEFAULT;
COMMENT ON COLUMN daily_session_agg.updated_at IS
  'Prospective refresh time for the mutable daily projection; NULL on untouched legacy rows.';

ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_coverage_version smallint;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_observed_at timestamptz;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_source_start_at timestamptz;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_source_cutoff_at timestamptz;

ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr20_coverage_check;
ALTER TABLE daily_session_agg
  ADD CONSTRAINT daily_session_agg_pr20_coverage_check CHECK (
    session_coverage_version IS NULL OR (
      session_coverage_version IN (1,2)
      AND session_expected_minutes IS NOT NULL AND session_expected_minutes > 0
      AND futures_ohlcv_minutes IS NOT NULL
        AND futures_ohlcv_minutes BETWEEN 0 AND session_expected_minutes
      AND spot_2v_minutes IS NOT NULL
        AND spot_2v_minutes BETWEEN 0 AND session_expected_minutes
      AND cvd_fut_2v_minutes IS NOT NULL
        AND cvd_fut_2v_minutes BETWEEN 0 AND session_expected_minutes
      AND session_expected_5m_samples IS NOT NULL AND session_expected_5m_samples > 0
      AND session_expected_5m_samples * 5 = session_expected_minutes
      AND oi_5m_samples IS NOT NULL
        AND oi_5m_samples BETWEEN 0 AND session_expected_5m_samples
      AND funding_5m_samples IS NOT NULL
        AND funding_5m_samples BETWEEN 0 AND session_expected_5m_samples
    )
  ) NOT VALID;

ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr24_liquidation_coverage_check;
ALTER TABLE daily_session_agg
  ADD CONSTRAINT daily_session_agg_pr24_liquidation_coverage_check CHECK (
    session_coverage_version IS DISTINCT FROM 2 OR (
      (
        long_liq_usd IS NULL
        AND short_liq_usd IS NULL
        AND liquidation_coverage_version IS NULL
        AND liquidation_observed_at IS NULL
        AND liquidation_source_start_at IS NULL
        AND liquidation_source_cutoff_at IS NULL
      ) OR (
        long_liq_usd IS NOT NULL AND finite_float8(long_liq_usd) AND long_liq_usd >= 0
        AND short_liq_usd IS NOT NULL AND finite_float8(short_liq_usd) AND short_liq_usd >= 0
        AND liquidation_coverage_version = 1
        AND liquidation_observed_at IS NOT NULL
        AND liquidation_source_start_at IS NOT NULL
        AND liquidation_source_cutoff_at IS NOT NULL
        AND liquidation_source_start_at < liquidation_source_cutoff_at
        AND liquidation_source_cutoff_at <= liquidation_observed_at
      )
    )
  ) NOT VALID;
COMMENT ON COLUMN daily_session_agg.liquidation_coverage_version IS
  'NULL=unmeasured; 1=the published liquidation-history observation proves the whole session.';

CREATE TABLE IF NOT EXISTS daily_verdict_outcome (
    outcome_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_id bigint NOT NULL REFERENCES daily_verdict_snapshot(snapshot_id),
    outcome_version smallint NOT NULL CHECK (outcome_version = 1),
    horizon_sessions smallint NOT NULL CHECK (horizon_sessions IN (7,14)),
    target_session_date date NOT NULL,
    target_price_close double precision NOT NULL CHECK (
      finite_float8(target_price_close) AND target_price_close > 0
    ),
    target_session_coverage_version smallint NOT NULL CHECK (
      target_session_coverage_version = 2
    ),
    source_projection_updated_at timestamptz NOT NULL,
    return_pct double precision NOT NULL CHECK (finite_float8(return_pct)),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(snapshot_id,outcome_version,horizon_sessions),
    CHECK (source_projection_updated_at <= recorded_at)
);
CREATE INDEX IF NOT EXISTS daily_verdict_outcome_target_date_idx
  ON daily_verdict_outcome(target_session_date DESC);

CREATE OR REPLACE FUNCTION reject_daily_verdict_outcome_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'daily_verdict_outcome is append-only; % is not allowed', TG_OP
      USING ERRCODE = '55000';
    RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS daily_verdict_outcome_no_update_delete ON daily_verdict_outcome;
CREATE TRIGGER daily_verdict_outcome_no_update_delete
BEFORE UPDATE OR DELETE ON daily_verdict_outcome
FOR EACH ROW EXECUTE FUNCTION reject_daily_verdict_outcome_mutation();
DROP TRIGGER IF EXISTS daily_verdict_outcome_no_truncate ON daily_verdict_outcome;
CREATE TRIGGER daily_verdict_outcome_no_truncate
BEFORE TRUNCATE ON daily_verdict_outcome
FOR EACH STATEMENT EXECUTE FUNCTION reject_daily_verdict_outcome_mutation();

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr24_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4,5)
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  );
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_reference_time_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr24_reference_time_check CHECK (
    evidence_version <> 5 OR (
      (
        reference_price IS NULL AND reference_price_source IS NULL
        AND reference_price_at IS NULL
      ) OR (
        reference_price IS NOT NULL AND reference_price_source IS NOT NULL
        AND reference_price_at IS NOT NULL AND reference_price_at <= observed_at
      )
    )
  );

ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr24_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3','daily-verdict-v4')
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );

COMMENT ON CONSTRAINT signal_observation_pr24_regime_provenance_check
  ON signal_observation IS
  'Signal evidence v3/v4/v5 requires regime logic v2 or a completely NULL regime block';
COMMENT ON CONSTRAINT signal_observation_pr24_reference_time_check
  ON signal_observation IS
  'Signal evidence v5 reference prices require an exact source timestamp no later than observed_at';
COMMENT ON CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check
  ON daily_verdict_snapshot IS
  'Daily verdict v2/v3/v4 requires regime logic v2 or a completely NULL regime block';

COMMIT;
