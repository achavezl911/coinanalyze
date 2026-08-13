-- PR25 rollback fails closed instead of discarding prospective visibility evidence.
BEGIN;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM signal_observation WHERE evidence_version=6) THEN
    RAISE EXCEPTION 'PR25 down migration refuses to discard signal evidence v6 provenance';
  END IF;

  IF to_regclass('signal_research_bundle_visibility') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM signal_research_bundle_visibility) THEN
      RAISE EXCEPTION
        'PR25 down migration refuses to destroy research bundle visibility certificates';
    END IF;
  END IF;

  IF to_regclass('signal_outcome_final_visibility') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM signal_outcome_final_visibility) THEN
      RAISE EXCEPTION
        'PR25 down migration refuses to destroy final outcome visibility certificates';
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM signal_walk_forward_manifest
    WHERE (spec->>'spec_version')::int = 2
  ) THEN
    RAISE EXCEPTION
      'PR25 down migration refuses to loosen a stored spec-v2 walk-forward manifest';
  END IF;

  IF EXISTS (
    SELECT 1 FROM signal_walk_forward_manifest
    WHERE (spec->'versions'->>'research_visibility_version')::int = 1
  ) THEN
    RAISE EXCEPTION
      'PR25 down migration refuses to loosen a manifest referring to research_visibility_version=1';
  END IF;
END $$;

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr25_reference_time_check;
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

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr25_regime_provenance_check;
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

COMMENT ON CONSTRAINT signal_observation_pr24_regime_provenance_check
  ON signal_observation IS
  'Signal evidence v3/v4/v5 requires regime logic v2 or a completely NULL regime block';
COMMENT ON CONSTRAINT signal_observation_pr24_reference_time_check
  ON signal_observation IS
  'Signal evidence v5 reference prices require an exact source timestamp no later than observed_at';

DROP TABLE IF EXISTS signal_outcome_final_visibility;
DROP FUNCTION IF EXISTS reject_signal_outcome_final_visibility_mutation();

DROP TABLE IF EXISTS signal_research_bundle_visibility;
DROP FUNCTION IF EXISTS reject_signal_research_bundle_visibility_mutation();

COMMIT;
