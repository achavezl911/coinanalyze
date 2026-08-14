-- PR27: immutable authoritative results for corrected confirmatory spec v4.
-- Additive only: no manifest/result is created and no research row is changed.
BEGIN;

-- PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT_BEGIN
-- One immutable authoritative result for a corrected spec-v4 manifest.  No
-- row is created by schema deployment; insertion occurs only after the
-- frozen evaluation-not-before instant inside the serialized evaluator.
CREATE TABLE IF NOT EXISTS signal_walk_forward_confirmatory_result (
    result_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    result_version smallint NOT NULL CHECK (result_version = 1),
    manifest_id bigint NOT NULL UNIQUE
        REFERENCES signal_walk_forward_manifest(manifest_id) ON DELETE RESTRICT,
    manifest_hash text NOT NULL CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    scientific_implementation_digest text NOT NULL
        CHECK (scientific_implementation_digest ~ '^[0-9a-f]{64}$'),
    confirmatory_knowledge_cutoff timestamptz NOT NULL,
    evaluation_not_before timestamptz NOT NULL,
    evaluated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    canonical_result_json text NOT NULL
        CHECK ((jsonb_typeof(canonical_result_json::jsonb) = 'object') IS TRUE),
    result_hash text NOT NULL CHECK (result_hash ~ '^[0-9a-f]{64}$'),
    CHECK (
      result_hash = encode(
        sha256(convert_to(canonical_result_json, 'UTF8')),
        'hex'
      )
    ),
    CHECK (confirmatory_knowledge_cutoff < evaluation_not_before),
    CHECK (evaluated_at >= evaluation_not_before),
    CHECK (
      ((canonical_result_json::jsonb->>'result_contract_version')::integer = 1)
      IS TRUE
    ),
    CHECK (
      ((canonical_result_json::jsonb->>'manifest_id')::bigint = manifest_id)
      IS TRUE
    ),
    CHECK (
      (canonical_result_json::jsonb->>'manifest_hash' = manifest_hash) IS TRUE
    ),
    CHECK (
      (
        canonical_result_json::jsonb->'scientific_implementation'->>'digest'
        = scientific_implementation_digest
      ) IS TRUE
    ),
    CHECK (
      (
        canonical_result_json::jsonb#>>'{confirmatory_result,confirmatory_state}'
        IN ('pass','fail','inconclusive')
      ) IS TRUE
    ),
    CHECK (
      (
        (canonical_result_json::jsonb->>'confirmatory_knowledge_cutoff')::timestamptz
        = confirmatory_knowledge_cutoff
      ) IS TRUE
    ),
    CHECK (
      (
        (canonical_result_json::jsonb->>'evaluation_not_before')::timestamptz
        = evaluation_not_before
      ) IS TRUE
    )
);

CREATE INDEX IF NOT EXISTS signal_walk_forward_confirmatory_result_hash_idx
    ON signal_walk_forward_confirmatory_result(result_hash);

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

DROP TRIGGER IF EXISTS signal_walk_forward_confirmatory_result_validate_insert
    ON signal_walk_forward_confirmatory_result;
CREATE TRIGGER signal_walk_forward_confirmatory_result_validate_insert
BEFORE INSERT ON signal_walk_forward_confirmatory_result
FOR EACH ROW EXECUTE FUNCTION validate_signal_walk_forward_confirmatory_result_insert();

CREATE OR REPLACE FUNCTION reject_signal_walk_forward_confirmatory_result_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
      'signal_walk_forward_confirmatory_result is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS signal_walk_forward_confirmatory_result_no_update_delete
    ON signal_walk_forward_confirmatory_result;
CREATE TRIGGER signal_walk_forward_confirmatory_result_no_update_delete
BEFORE UPDATE OR DELETE ON signal_walk_forward_confirmatory_result
FOR EACH ROW EXECUTE FUNCTION reject_signal_walk_forward_confirmatory_result_mutation();

DROP TRIGGER IF EXISTS signal_walk_forward_confirmatory_result_no_truncate
    ON signal_walk_forward_confirmatory_result;
CREATE TRIGGER signal_walk_forward_confirmatory_result_no_truncate
BEFORE TRUNCATE ON signal_walk_forward_confirmatory_result
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_walk_forward_confirmatory_result_mutation();

-- No backfill and no production manifest/result creation in PR27.
-- PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT_END

COMMIT;
