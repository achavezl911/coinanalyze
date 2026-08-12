-- PR22 rollback. Never discard provenance already referenced by research evidence.
BEGIN;

DO $$
DECLARE
  has_evidence boolean;
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=current_schema() AND table_name='signal_observation'
      AND column_name='regime_logic_version'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM signal_observation '
            'WHERE regime_logic_version IS NOT NULL OR evidence_version=3)'
      INTO has_evidence;
    IF has_evidence THEN
      RAISE EXCEPTION 'PR22 down migration refuses to destroy signal_observation regime provenance';
    END IF;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=current_schema() AND table_name='daily_verdict_snapshot'
      AND column_name='regime_logic_version'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM daily_verdict_snapshot '
            'WHERE regime_logic_version IS NOT NULL '
            'OR logic_version=''daily-verdict-v2'')'
      INTO has_evidence;
    IF has_evidence THEN
      RAISE EXCEPTION 'PR22 down migration refuses to destroy daily_verdict_snapshot regime provenance';
    END IF;
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema=current_schema() AND table_name='metrics_snapshot'
      AND column_name='regime_logic_version'
  ) THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM metrics_snapshot '
            'WHERE regime_logic_version IS NOT NULL)' INTO has_evidence;
    IF has_evidence THEN
      RAISE EXCEPTION 'PR22 down migration refuses to destroy metrics_snapshot regime provenance';
    END IF;
  END IF;
END $$;

ALTER TABLE IF EXISTS daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr22_regime_provenance_check,
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_regime_logic_version_check;
ALTER TABLE IF EXISTS signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr22_regime_provenance_check,
  DROP CONSTRAINT IF EXISTS signal_observation_regime_logic_version_check;
ALTER TABLE IF EXISTS metrics_snapshot
  DROP CONSTRAINT IF EXISTS metrics_snapshot_regime_logic_version_check,
  DROP CONSTRAINT IF EXISTS metrics_snapshot_cvd_fut_imbalance_24h_check,
  DROP CONSTRAINT IF EXISTS metrics_snapshot_cvd_spot_imbalance_24h_check,
  DROP CONSTRAINT IF EXISTS metrics_snapshot_spot_vol_24h_check;

ALTER TABLE IF EXISTS daily_verdict_snapshot DROP COLUMN IF EXISTS regime_logic_version;
ALTER TABLE IF EXISTS signal_observation DROP COLUMN IF EXISTS regime_logic_version;
ALTER TABLE IF EXISTS metrics_snapshot
  DROP COLUMN IF EXISTS regime_logic_version,
  DROP COLUMN IF EXISTS cvd_fut_imbalance_24h,
  DROP COLUMN IF EXISTS cvd_spot_imbalance_24h,
  DROP COLUMN IF EXISTS spot_vol_24h;

COMMIT;
