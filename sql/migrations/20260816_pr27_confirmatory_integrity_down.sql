-- PR27 rollback is destructive only when no spec-v4 contract/result exists.
-- Once scientific evidence exists, fail closed and preserve it.
BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM signal_walk_forward_manifest
     WHERE (spec->>'spec_version')::integer = 4
  ) THEN
    RAISE EXCEPTION
      'PR27 down migration refuses to discard a stored spec-v4 manifest contract';
  END IF;

  IF to_regclass('signal_walk_forward_confirmatory_result') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM signal_walk_forward_confirmatory_result) THEN
      RAISE EXCEPTION
        'PR27 down migration refuses to destroy authoritative confirmatory results';
    END IF;
  END IF;
END $$;

DROP TABLE IF EXISTS signal_walk_forward_confirmatory_result;
DROP FUNCTION IF EXISTS validate_signal_walk_forward_confirmatory_result_insert();
DROP FUNCTION IF EXISTS reject_signal_walk_forward_confirmatory_result_mutation();

COMMIT;
