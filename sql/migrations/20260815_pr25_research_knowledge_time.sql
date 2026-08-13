-- PR25: append-only research knowledge-time visibility certification.
-- No historical rows are rewritten or backfilled. No v1-v5 certification.
BEGIN;

-- PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY_BEGIN
-- Proves a v6 signal_observation research bundle (observation + replay frame
-- + every scheduled outcome horizon + both execution venues) was already
-- committed and externally visible no later than verified_visible_at. The
-- certificate itself may commit after verified_visible_at: that timestamp
-- attests only to the SOURCE STATE the certifying transaction already
-- successfully read, never to this row's own commit time.
CREATE TABLE IF NOT EXISTS signal_research_bundle_visibility (
    bundle_visibility_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint NOT NULL
        REFERENCES signal_observation(observation_id) ON DELETE RESTRICT,
    visibility_version smallint NOT NULL CHECK (visibility_version >= 1),
    evidence_version smallint NOT NULL CHECK (evidence_version >= 1),
    context_version smallint NOT NULL CHECK (context_version >= 1),
    outcome_version smallint NOT NULL CHECK (outcome_version >= 1),
    execution_snapshot_version smallint NOT NULL
        CHECK (execution_snapshot_version >= 1),
    verified_visible_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(observation_id,visibility_version),
    CONSTRAINT signal_research_bundle_visibility_pr25_frozen_tuple_check CHECK (
        visibility_version <> 1
        OR (
            evidence_version = 6
            AND context_version = 1
            AND outcome_version = 1
            AND execution_snapshot_version = 1
        )
    )
);
CREATE INDEX IF NOT EXISTS signal_research_bundle_visibility_observation_idx
    ON signal_research_bundle_visibility(observation_id);
CREATE INDEX IF NOT EXISTS signal_research_bundle_visibility_verified_idx
    ON signal_research_bundle_visibility(verified_visible_at);

CREATE OR REPLACE FUNCTION reject_signal_research_bundle_visibility_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
      'signal_research_bundle_visibility is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS signal_research_bundle_visibility_no_update_delete
    ON signal_research_bundle_visibility;
CREATE TRIGGER signal_research_bundle_visibility_no_update_delete
BEFORE UPDATE OR DELETE ON signal_research_bundle_visibility
FOR EACH ROW EXECUTE FUNCTION reject_signal_research_bundle_visibility_mutation();
DROP TRIGGER IF EXISTS signal_research_bundle_visibility_no_truncate
    ON signal_research_bundle_visibility;
CREATE TRIGGER signal_research_bundle_visibility_no_truncate
BEFORE TRUNCATE ON signal_research_bundle_visibility
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_research_bundle_visibility_mutation();

-- No INSERT ... SELECT backfill here: a certificate is only ever produced by
-- app/signal_visibility.py reading already-committed source state.
-- PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY_END

-- PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY_BEGIN
-- Proves a signal_outcome final state (evaluated/not_evaluable) was already
-- committed and externally visible no later than verified_visible_at. Only
-- outcomes owned by an evidence_version=6 observation may be certified.
CREATE TABLE IF NOT EXISTS signal_outcome_final_visibility (
    final_visibility_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    outcome_id bigint NOT NULL
        REFERENCES signal_outcome(outcome_id) ON DELETE RESTRICT,
    visibility_version smallint NOT NULL CHECK (visibility_version >= 1),
    outcome_version smallint NOT NULL CHECK (outcome_version >= 1),
    source_status text NOT NULL
        CHECK (source_status IN ('evaluated','not_evaluable')),
    source_finalized_at timestamptz NOT NULL,
    verified_visible_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(outcome_id,visibility_version),
    CHECK (source_finalized_at <= verified_visible_at),
    CONSTRAINT signal_outcome_final_visibility_pr25_frozen_tuple_check CHECK (
        visibility_version <> 1 OR outcome_version = 1
    )
);
CREATE INDEX IF NOT EXISTS signal_outcome_final_visibility_outcome_idx
    ON signal_outcome_final_visibility(outcome_id);
CREATE INDEX IF NOT EXISTS signal_outcome_final_visibility_verified_idx
    ON signal_outcome_final_visibility(verified_visible_at);

CREATE OR REPLACE FUNCTION reject_signal_outcome_final_visibility_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
      'signal_outcome_final_visibility is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS signal_outcome_final_visibility_no_update_delete
    ON signal_outcome_final_visibility;
CREATE TRIGGER signal_outcome_final_visibility_no_update_delete
BEFORE UPDATE OR DELETE ON signal_outcome_final_visibility
FOR EACH ROW EXECUTE FUNCTION reject_signal_outcome_final_visibility_mutation();
DROP TRIGGER IF EXISTS signal_outcome_final_visibility_no_truncate
    ON signal_outcome_final_visibility;
CREATE TRIGGER signal_outcome_final_visibility_no_truncate
BEFORE TRUNCATE ON signal_outcome_final_visibility
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_outcome_final_visibility_mutation();

-- No INSERT ... SELECT backfill here either.
-- PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY_END

-- Prospective evidence v6 inherits the PR23/PR24 regime-provenance and
-- PR24 reference-time contracts unchanged; only the evidence_version sets
-- widen to admit 6. No existing row (evidence 1-5) is reinterpreted.
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr25_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr25_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4,5,6)
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
  DROP CONSTRAINT IF EXISTS signal_observation_pr25_reference_time_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr25_reference_time_check CHECK (
    evidence_version NOT IN (5,6) OR (
      (
        reference_price IS NULL AND reference_price_source IS NULL
        AND reference_price_at IS NULL
      ) OR (
        reference_price IS NOT NULL AND reference_price_source IS NOT NULL
        AND reference_price_at IS NOT NULL AND reference_price_at <= observed_at
      )
    )
  );

COMMENT ON CONSTRAINT signal_observation_pr25_regime_provenance_check
  ON signal_observation IS
  'Signal evidence v3/v4/v5/v6 requires regime logic v2 or a completely NULL regime block';
COMMENT ON CONSTRAINT signal_observation_pr25_reference_time_check
  ON signal_observation IS
  'Signal evidence v5/v6 reference prices require an exact source timestamp no later than observed_at';

COMMIT;
