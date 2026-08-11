-- PR20 F3/F4/F7: nullable daily evidence + prospective coverage provenance.
BEGIN;
ALTER TABLE metrics_snapshot ALTER COLUMN price_dir_1h DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN cvd_spot_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN cvd_fut_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN inst_delta_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_open DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_close DROP NOT NULL;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_coverage_version smallint;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_expected_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS futures_ohlcv_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS spot_2v_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_expected_5m_samples integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS oi_5m_samples integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS funding_5m_samples integer;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='daily_session_agg'::regclass
                 AND conname='daily_session_agg_pr20_coverage_check') THEN
    ALTER TABLE daily_session_agg ADD CONSTRAINT daily_session_agg_pr20_coverage_check CHECK (
      session_coverage_version IS NULL OR (
        session_coverage_version = 1
        AND session_expected_minutes IS NOT NULL AND session_expected_minutes > 0
        AND futures_ohlcv_minutes IS NOT NULL AND futures_ohlcv_minutes BETWEEN 0 AND session_expected_minutes
        AND spot_2v_minutes IS NOT NULL AND spot_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND cvd_fut_2v_minutes IS NOT NULL AND cvd_fut_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND session_expected_5m_samples IS NOT NULL AND session_expected_5m_samples > 0
        AND session_expected_5m_samples * 5 = session_expected_minutes
        AND oi_5m_samples IS NOT NULL AND oi_5m_samples BETWEEN 0 AND session_expected_5m_samples
        AND funding_5m_samples IS NOT NULL AND funding_5m_samples BETWEEN 0 AND session_expected_5m_samples
      )
    );
  END IF;
END $$;
COMMENT ON COLUMN daily_session_agg.session_coverage_version IS
  'NULL=legacy/unverified; 1=PR20 DST-aware metric-specific coverage';
COMMENT ON COLUMN daily_session_agg.session_expected_minutes IS
  'Expected 1-minute samples from exact NYSE session_bounds; naturally 1380/1440/1500 across DST';
COMMIT;
