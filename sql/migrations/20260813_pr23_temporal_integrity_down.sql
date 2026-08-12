-- PR23 rollback: restore PR22 constraints only when no PR23 evidence exists.
BEGIN;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM signal_observation WHERE evidence_version=4) THEN
    RAISE EXCEPTION 'PR23 down migration refuses to loosen v4 signal provenance';
  END IF;
  IF EXISTS (
    SELECT 1 FROM daily_verdict_snapshot WHERE logic_version='daily-verdict-v3'
  ) THEN
    RAISE EXCEPTION 'PR23 down migration refuses to loosen daily-verdict-v3 provenance';
  END IF;
END $$;

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr22_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr22_regime_provenance_check CHECK (
    evidence_version <> 3
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
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr22_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr22_regime_provenance_check CHECK (
    logic_version <> 'daily-verdict-v2'
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL
      AND regime_score IS NULL
      AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );

COMMIT;
