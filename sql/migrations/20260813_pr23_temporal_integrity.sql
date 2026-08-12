-- PR23: prospective temporal-integrity provenance constraints. No backfill.
BEGIN;

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr22_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr23_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4)
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL
      AND regime_score IS NULL
      AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
      AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  );

ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr22_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3')
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL
      AND regime_score IS NULL
      AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );

COMMENT ON CONSTRAINT signal_observation_pr23_regime_provenance_check
  ON signal_observation IS
  'Evidence v3/v4 must reference regime logic v2 or carry a completely NULL regime block';
COMMENT ON CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check
  ON daily_verdict_snapshot IS
  'Daily verdict v2/v3 must reference regime logic v2 or carry a completely NULL regime block';

COMMIT;
