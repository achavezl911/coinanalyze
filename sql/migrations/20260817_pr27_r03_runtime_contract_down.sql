-- PR27-R03 rollback. Sólo es seguro mientras no exista evidencia científica que
-- dependa de la procedencia del contrato de runtime. Si existe, falla cerrado.
--
-- Las columnas de signal_observation son append-only por trigger: nunca se
-- reescriben, sólo se descartan si ninguna fila las usa todavía.
BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM signal_walk_forward_manifest
     WHERE (spec->>'spec_version')::integer = 4
  ) THEN
    RAISE EXCEPTION
      'PR27-R03 down migration refuses to discard a frozen spec-v4 runtime contract';
  END IF;

  IF to_regclass('signal_walk_forward_confirmatory_result') IS NOT NULL THEN
    IF EXISTS (SELECT 1 FROM signal_walk_forward_confirmatory_result) THEN
      RAISE EXCEPTION
        'PR27-R03 down migration refuses to rewrite authoritative confirmatory results';
    END IF;
  END IF;

  IF EXISTS (
    SELECT 1 FROM signal_observation WHERE runtime_contract_digest IS NOT NULL
  ) THEN
    RAISE EXCEPTION
      'PR27-R03 down migration refuses to drop runtime contract provenance already recorded';
  END IF;
END $$;

ALTER TABLE signal_observation
    DROP CONSTRAINT IF EXISTS signal_observation_runtime_contract_pairing_check;
ALTER TABLE signal_observation
    DROP CONSTRAINT IF EXISTS signal_observation_runtime_contract_digest_check;
ALTER TABLE signal_observation
    DROP CONSTRAINT IF EXISTS signal_observation_runtime_contract_version_check;
ALTER TABLE signal_observation
    DROP COLUMN IF EXISTS runtime_contract_digest;
ALTER TABLE signal_observation
    DROP COLUMN IF EXISTS runtime_contract_version;

ALTER TABLE signal_walk_forward_confirmatory_result
    DROP CONSTRAINT IF EXISTS swfcr_runtime_contract_digest_json_check;
ALTER TABLE signal_walk_forward_confirmatory_result
    DROP CONSTRAINT IF EXISTS swfcr_runtime_contract_digest_shape_check;
ALTER TABLE signal_walk_forward_confirmatory_result
    DROP COLUMN IF EXISTS scientific_runtime_contract_digest;

-- Restaura el trigger PR27 sin la comprobación del contrato de runtime.
CREATE OR REPLACE FUNCTION validate_signal_walk_forward_confirmatory_result_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    frozen_manifest_hash text;
    frozen_spec jsonb;
BEGIN
    SELECT manifest_hash,spec
      INTO frozen_manifest_hash,frozen_spec
      FROM signal_walk_forward_manifest
     WHERE manifest_id=NEW.manifest_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'authoritative result references an unknown manifest'
            USING ERRCODE = '23503';
    END IF;
    IF (frozen_spec->>'spec_version')::integer IS DISTINCT FROM 4 THEN
        RAISE EXCEPTION 'authoritative confirmatory results require walk-forward spec v4'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.manifest_hash IS DISTINCT FROM frozen_manifest_hash THEN
        RAISE EXCEPTION 'authoritative result manifest hash disagrees with frozen manifest'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.scientific_implementation_digest IS DISTINCT FROM
       frozen_spec->'scientific_implementation'->>'digest' THEN
        RAISE EXCEPTION 'authoritative result implementation digest disagrees with manifest'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.confirmatory_knowledge_cutoff IS DISTINCT FROM
       (frozen_spec->>'confirmatory_knowledge_cutoff')::timestamptz THEN
        RAISE EXCEPTION 'authoritative result knowledge cutoff disagrees with manifest'
            USING ERRCODE = '55000';
    END IF;
    IF NEW.evaluation_not_before IS DISTINCT FROM
       (frozen_spec->>'evaluation_not_before')::timestamptz THEN
        RAISE EXCEPTION 'authoritative result settlement boundary disagrees with manifest'
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END
$$;

COMMIT;
