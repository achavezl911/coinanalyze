-- PR24 rollback fails closed rather than destroying prospective evidence.
BEGIN;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM signal_observation WHERE evidence_version=5) THEN
    RAISE EXCEPTION 'PR24 down migration refuses to loosen signal evidence v5 provenance';
  END IF;
  IF EXISTS (
    SELECT 1 FROM daily_verdict_snapshot WHERE logic_version='daily-verdict-v4'
  ) THEN
    RAISE EXCEPTION 'PR24 down migration refuses to loosen daily-verdict-v4 provenance';
  END IF;
  IF to_regclass('daily_session_snapshot') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM daily_session_snapshot) THEN
      RAISE EXCEPTION 'PR24 down migration refuses to destroy daily_session_snapshot evidence';
    END IF;
  END IF;
  IF to_regclass('liquidation_history_observation') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM liquidation_history_observation) THEN
      RAISE EXCEPTION 'PR24 down migration refuses to destroy liquidation history observations';
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

DROP TABLE IF EXISTS daily_session_snapshot;
DROP TABLE IF EXISTS liquidation_history_observation;
DROP FUNCTION IF EXISTS reject_pr24_append_only_mutation();

ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr24_liquidation_coverage_check;
ALTER TABLE daily_session_agg
  DROP COLUMN IF EXISTS liquidation_observed_end_at,
  DROP COLUMN IF EXISTS liquidation_observed_start_at,
  DROP COLUMN IF EXISTS liquidation_coverage_version,
  DROP COLUMN IF EXISTS updated_at;

COMMIT;
