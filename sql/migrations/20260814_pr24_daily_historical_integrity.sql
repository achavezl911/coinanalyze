-- PR24: prospective immutable daily evidence and durable liquidation coverage.
-- No historical semantic backfill is performed. updated_at is initialized from
-- created_at only as legacy structural metadata; it is not a claim about prior updates.
BEGIN;

ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS updated_at timestamptz;
UPDATE daily_session_agg SET updated_at=created_at WHERE updated_at IS NULL;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at SET DEFAULT clock_timestamp();
COMMENT ON COLUMN daily_session_agg.updated_at IS
  'Mutable projection update time. Legacy rows were structurally initialized from created_at during PR24; that initialization is not historical update evidence.';

ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_coverage_version smallint;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_observed_start_at timestamptz;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_observed_end_at timestamptz;
ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr24_liquidation_coverage_check;
ALTER TABLE daily_session_agg
  ADD CONSTRAINT daily_session_agg_pr24_liquidation_coverage_check CHECK (
    liquidation_coverage_version IS NULL OR (
      liquidation_coverage_version = 1
      AND liquidation_observed_start_at IS NOT NULL
      AND liquidation_observed_end_at IS NOT NULL
      AND liquidation_observed_start_at < liquidation_observed_end_at
      AND long_liq_usd IS NOT NULL AND finite_float8(long_liq_usd) AND long_liq_usd >= 0
      AND short_liq_usd IS NOT NULL AND finite_float8(short_liq_usd) AND short_liq_usd >= 0
    )
  ) NOT VALID;
COMMENT ON COLUMN daily_session_agg.liquidation_coverage_version IS
  'NULL=coverage not demonstrated; 1=a COMPLETE liquidation-history observation covers the whole session';

CREATE TABLE IF NOT EXISTS liquidation_history_observation (
    observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol text NOT NULL REFERENCES symbols(symbol),
    source_start_at timestamptz NOT NULL,
    source_cutoff_at timestamptz NOT NULL,
    observed_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('COMPLETE','INCOMPLETE')),
    response_symbol_present boolean NOT NULL,
    returned_rows integer NOT NULL CHECK (returned_rows >= 0),
    accepted_rows integer NOT NULL CHECK (accepted_rows >= 0 AND accepted_rows <= returned_rows),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (source_start_at < source_cutoff_at),
    CHECK (observed_at >= source_cutoff_at),
    CHECK (
      (status='COMPLETE' AND response_symbol_present AND accepted_rows=returned_rows)
      OR
      (status='INCOMPLETE' AND (NOT response_symbol_present OR accepted_rows<>returned_rows))
    )
);
CREATE INDEX IF NOT EXISTS liquidation_history_observation_complete_idx
  ON liquidation_history_observation(
    symbol, source_start_at, source_cutoff_at, observed_at DESC
  ) WHERE status='COMPLETE';

CREATE TABLE IF NOT EXISTS daily_session_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol text NOT NULL REFERENCES symbols(symbol),
    session_date date NOT NULL,
    snapshot_version smallint NOT NULL CHECK (snapshot_version >= 1),
    observed_at timestamptz NOT NULL,
    session_end_at timestamptz NOT NULL,
    cvd_spot_usd double precision CHECK (cvd_spot_usd IS NULL OR finite_float8(cvd_spot_usd)),
    cvd_fut_usd double precision CHECK (cvd_fut_usd IS NULL OR finite_float8(cvd_fut_usd)),
    cvd_diff_usd double precision CHECK (cvd_diff_usd IS NULL OR finite_float8(cvd_diff_usd)),
    cvd_fut_2v_usd double precision CHECK (cvd_fut_2v_usd IS NULL OR finite_float8(cvd_fut_2v_usd)),
    cvd_diff_2v_usd double precision CHECK (cvd_diff_2v_usd IS NULL OR finite_float8(cvd_diff_2v_usd)),
    inst_delta_usd double precision CHECK (inst_delta_usd IS NULL OR finite_float8(inst_delta_usd)),
    price_open double precision CHECK (price_open IS NULL OR (finite_float8(price_open) AND price_open > 0)),
    price_high double precision CHECK (price_high IS NULL OR (finite_float8(price_high) AND price_high > 0)),
    price_low double precision CHECK (price_low IS NULL OR (finite_float8(price_low) AND price_low > 0)),
    price_close double precision CHECK (price_close IS NULL OR (finite_float8(price_close) AND price_close > 0)),
    price_chg_pct double precision CHECK (price_chg_pct IS NULL OR finite_float8(price_chg_pct)),
    oi_open double precision CHECK (oi_open IS NULL OR (finite_float8(oi_open) AND oi_open >= 0)),
    oi_high double precision CHECK (oi_high IS NULL OR (finite_float8(oi_high) AND oi_high >= 0)),
    oi_low double precision CHECK (oi_low IS NULL OR (finite_float8(oi_low) AND oi_low >= 0)),
    oi_close double precision CHECK (oi_close IS NULL OR (finite_float8(oi_close) AND oi_close >= 0)),
    oi_chg_usd double precision CHECK (oi_chg_usd IS NULL OR finite_float8(oi_chg_usd)),
    fr_avg double precision CHECK (fr_avg IS NULL OR finite_float8(fr_avg)),
    volume_usd double precision CHECK (volume_usd IS NULL OR (finite_float8(volume_usd) AND volume_usd >= 0)),
    long_liq_usd double precision CHECK (long_liq_usd IS NULL OR (finite_float8(long_liq_usd) AND long_liq_usd >= 0)),
    short_liq_usd double precision CHECK (short_liq_usd IS NULL OR (finite_float8(short_liq_usd) AND short_liq_usd >= 0)),
    tx_count bigint CHECK (tx_count IS NULL OR tx_count >= 0),
    session_coverage_version smallint,
    session_expected_minutes integer,
    futures_ohlcv_minutes integer,
    spot_2v_minutes integer,
    cvd_fut_2v_minutes integer,
    session_expected_5m_samples integer,
    oi_5m_samples integer,
    funding_5m_samples integer,
    liquidation_coverage_version smallint,
    liquidation_observed_start_at timestamptz,
    liquidation_observed_end_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(symbol, session_date),
    CHECK (observed_at >= session_end_at),
    CHECK (
      session_coverage_version IS NULL OR (
        session_coverage_version = 1
        AND session_expected_minutes IS NOT NULL AND session_expected_minutes > 0
        AND futures_ohlcv_minutes BETWEEN 0 AND session_expected_minutes
        AND spot_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND cvd_fut_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND session_expected_5m_samples IS NOT NULL
        AND session_expected_5m_samples * 5 = session_expected_minutes
        AND oi_5m_samples BETWEEN 0 AND session_expected_5m_samples
        AND funding_5m_samples BETWEEN 0 AND session_expected_5m_samples
      )
    ),
    CHECK (
      (
        liquidation_coverage_version IS NULL
        AND liquidation_observed_start_at IS NULL
        AND liquidation_observed_end_at IS NULL
        AND long_liq_usd IS NULL
        AND short_liq_usd IS NULL
      ) OR (
        liquidation_coverage_version = 1
        AND liquidation_observed_start_at IS NOT NULL
        AND liquidation_observed_end_at IS NOT NULL
        AND liquidation_observed_start_at < liquidation_observed_end_at
        AND liquidation_observed_end_at >= session_end_at
        AND long_liq_usd IS NOT NULL
        AND short_liq_usd IS NOT NULL
      )
    )
);
CREATE INDEX IF NOT EXISTS daily_session_snapshot_date_idx
  ON daily_session_snapshot(session_date DESC);

CREATE OR REPLACE FUNCTION reject_pr24_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; % is not allowed', TG_TABLE_NAME, TG_OP
      USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS daily_session_snapshot_no_update_delete ON daily_session_snapshot;
CREATE TRIGGER daily_session_snapshot_no_update_delete
BEFORE UPDATE OR DELETE ON daily_session_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_pr24_append_only_mutation();
DROP TRIGGER IF EXISTS daily_session_snapshot_no_truncate ON daily_session_snapshot;
CREATE TRIGGER daily_session_snapshot_no_truncate
BEFORE TRUNCATE ON daily_session_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION reject_pr24_append_only_mutation();

DROP TRIGGER IF EXISTS liquidation_history_observation_no_update_delete
  ON liquidation_history_observation;
CREATE TRIGGER liquidation_history_observation_no_update_delete
BEFORE UPDATE OR DELETE ON liquidation_history_observation
FOR EACH ROW EXECUTE FUNCTION reject_pr24_append_only_mutation();
DROP TRIGGER IF EXISTS liquidation_history_observation_no_truncate
  ON liquidation_history_observation;
CREATE TRIGGER liquidation_history_observation_no_truncate
BEFORE TRUNCATE ON liquidation_history_observation
FOR EACH STATEMENT EXECUTE FUNCTION reject_pr24_append_only_mutation();

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
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

ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr24_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3','daily-verdict-v4')
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );

COMMENT ON CONSTRAINT signal_observation_pr24_regime_provenance_check
  ON signal_observation IS
  'Signal evidence v3/v4/v5 requires regime logic v2 or a completely NULL regime block';
COMMENT ON CONSTRAINT signal_observation_pr24_reference_time_check
  ON signal_observation IS
  'Signal evidence v5 reference prices require an exact source timestamp no later than observed_at';
COMMENT ON CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check
  ON daily_verdict_snapshot IS
  'Daily verdict v2/v3/v4 requires regime logic v2 or a completely NULL regime block';

COMMIT;
