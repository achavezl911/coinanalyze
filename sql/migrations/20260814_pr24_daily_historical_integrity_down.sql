-- PR24 rollback fails closed instead of discarding prospective evidence.
BEGIN;

DO $$
DECLARE
  has_projection_evidence boolean := false;
BEGIN
  IF EXISTS (SELECT 1 FROM signal_observation WHERE evidence_version=5) THEN
    RAISE EXCEPTION 'PR24 down migration refuses to loosen signal evidence v5 provenance';
  END IF;
  IF EXISTS (
    SELECT 1 FROM daily_verdict_snapshot WHERE logic_version='daily-verdict-v4'
  ) THEN
    RAISE EXCEPTION 'PR24 down migration refuses to loosen daily-verdict-v4 provenance';
  END IF;
  IF EXISTS (
    SELECT 1 FROM daily_session_agg WHERE session_coverage_version=2
  ) THEN
    RAISE EXCEPTION 'PR24 down migration refuses to discard session coverage v2 evidence';
  END IF;
  IF to_regclass('daily_verdict_outcome') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM daily_verdict_outcome) THEN
      RAISE EXCEPTION 'PR24 down migration refuses to destroy daily_verdict_outcome evidence';
    END IF;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=current_schema() AND table_name='daily_session_agg'
      AND column_name='updated_at'
  ) THEN
    EXECUTE $query$
      SELECT EXISTS(
        SELECT 1 FROM daily_session_agg
        WHERE updated_at IS NOT NULL
           OR liquidation_coverage_version IS NOT NULL
           OR liquidation_observed_at IS NOT NULL
           OR liquidation_source_start_at IS NOT NULL
           OR liquidation_source_cutoff_at IS NOT NULL
      )
    $query$ INTO has_projection_evidence;
    IF has_projection_evidence THEN
      RAISE EXCEPTION 'PR24 down migration refuses to discard daily projection provenance';
    END IF;
  END IF;
END $$;

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_reference_time_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr23_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4)
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  );

ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr24_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3')
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );

DROP TABLE IF EXISTS daily_verdict_outcome;
DROP FUNCTION IF EXISTS reject_daily_verdict_outcome_mutation();

ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr24_liquidation_coverage_check;
ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr20_coverage_check;
ALTER TABLE daily_session_agg
  ADD CONSTRAINT daily_session_agg_pr20_coverage_check CHECK (
    session_coverage_version IS NULL OR (
      session_coverage_version = 1
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
  DROP COLUMN IF EXISTS liquidation_source_cutoff_at,
  DROP COLUMN IF EXISTS liquidation_source_start_at,
  DROP COLUMN IF EXISTS liquidation_observed_at,
  DROP COLUMN IF EXISTS liquidation_coverage_version,
  DROP COLUMN IF EXISTS updated_at;

COMMIT;
