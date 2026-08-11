-- PR20 rollback. Restoring NOT NULL is safe only if no PR20 partial rows remain.
BEGIN;
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM daily_session_agg
    WHERE cvd_spot_usd IS NULL OR cvd_fut_usd IS NULL OR inst_delta_usd IS NULL
       OR price_open IS NULL OR price_close IS NULL
  ) THEN
    RAISE EXCEPTION 'PR20 down migration requires removal/repair of partial daily_session_agg rows before restoring NOT NULL';
  END IF;
END $$;
ALTER TABLE daily_session_agg DROP CONSTRAINT IF EXISTS daily_session_agg_pr20_coverage_check;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS funding_5m_samples;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS oi_5m_samples;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS session_expected_5m_samples;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS spot_2v_minutes;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS futures_ohlcv_minutes;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS session_expected_minutes;
ALTER TABLE daily_session_agg DROP COLUMN IF EXISTS session_coverage_version;
ALTER TABLE daily_session_agg ALTER COLUMN cvd_spot_usd SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN cvd_fut_usd SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN inst_delta_usd SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_open SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_close SET NOT NULL;
COMMIT;
