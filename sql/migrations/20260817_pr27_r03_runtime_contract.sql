-- PR27-R03: congela la configuración científica resuelta en runtime.
--
-- Aditiva y prospectiva. No reescribe ni reinterpreta ninguna fila histórica:
-- signal_observation gana dos columnas nullable y las filas existentes se quedan
-- en NULL. Ningún CHECK ata esas columnas a evidence_version, porque eso
-- reinterpretaría evidence-v6. La exigencia es del evaluador spec-v4.
BEGIN;

-- PR27_R03_SIGNAL_OBSERVATION_RUNTIME_CONTRACT_BEGIN
ALTER TABLE signal_observation
    ADD COLUMN IF NOT EXISTS runtime_contract_version smallint;
ALTER TABLE signal_observation
    ADD COLUMN IF NOT EXISTS runtime_contract_digest text;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_observation'::regclass
      AND conname='signal_observation_runtime_contract_version_check'
  ) THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_runtime_contract_version_check
      CHECK (runtime_contract_version IS NULL OR runtime_contract_version >= 1);
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_observation'::regclass
      AND conname='signal_observation_runtime_contract_digest_check'
  ) THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_runtime_contract_digest_check
      CHECK (runtime_contract_digest IS NULL
             OR runtime_contract_digest ~ '^[0-9a-f]{64}$');
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_observation'::regclass
      AND conname='signal_observation_runtime_contract_pairing_check'
  ) THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_runtime_contract_pairing_check
      CHECK ((runtime_contract_version IS NULL) = (runtime_contract_digest IS NULL));
  END IF;
END $$;
-- PR27_R03_SIGNAL_OBSERVATION_RUNTIME_CONTRACT_END

-- PR27_R03_CONFIRMATORY_RESULT_RUNTIME_CONTRACT_BEGIN
-- El resultado autoritativo lleva las dos mitades de la clausura científica.
-- La columna es NOT NULL: no existe un digest que rellenar retroactivamente,
-- así que una tabla con filas hace fallar la migración en vez de inventarlo.
DO $$
BEGIN
  IF to_regclass('signal_walk_forward_confirmatory_result') IS NULL THEN
    RAISE EXCEPTION
      'PR27-R03 requires the PR27 confirmatory result table to exist first';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='signal_walk_forward_confirmatory_result'
      AND column_name='scientific_runtime_contract_digest'
  ) THEN
    IF EXISTS (SELECT 1 FROM signal_walk_forward_confirmatory_result) THEN
      RAISE EXCEPTION
        'PR27-R03 cannot add runtime contract provenance to existing authoritative results';
    END IF;
    ALTER TABLE signal_walk_forward_confirmatory_result
      ADD COLUMN scientific_runtime_contract_digest text NOT NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_walk_forward_confirmatory_result'::regclass
      AND conname='swfcr_runtime_contract_digest_shape_check'
  ) THEN
    ALTER TABLE signal_walk_forward_confirmatory_result
      ADD CONSTRAINT swfcr_runtime_contract_digest_shape_check
      CHECK (scientific_runtime_contract_digest ~ '^[0-9a-f]{64}$');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_walk_forward_confirmatory_result'::regclass
      AND conname='swfcr_runtime_contract_digest_json_check'
  ) THEN
    ALTER TABLE signal_walk_forward_confirmatory_result
      ADD CONSTRAINT swfcr_runtime_contract_digest_json_check
      CHECK (
        (
          canonical_result_json::jsonb->'scientific_runtime_contract'->>'digest'
          = scientific_runtime_contract_digest
        ) IS TRUE
      );
  END IF;
END $$;

-- El trigger vuelve a exigir que el digest coincida con el manifest congelado,
-- igual que ya hacía con el digest de implementación.
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
    IF NEW.scientific_runtime_contract_digest IS DISTINCT FROM
       frozen_spec->'scientific_runtime_contract'->>'digest' THEN
        RAISE EXCEPTION 'authoritative result runtime contract digest disagrees with manifest'
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
-- PR27_R03_CONFIRMATORY_RESULT_RUNTIME_CONTRACT_END

COMMIT;
