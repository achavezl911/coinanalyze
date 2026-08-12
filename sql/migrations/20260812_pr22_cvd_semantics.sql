-- PR22: normalized CVD semantics and prospective regime provenance. No backfill.
BEGIN;

ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS spot_vol_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS cvd_spot_imbalance_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS cvd_fut_imbalance_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS regime_logic_version smallint;
ALTER TABLE signal_observation ADD COLUMN IF NOT EXISTS regime_logic_version smallint;
ALTER TABLE daily_verdict_snapshot ADD COLUMN IF NOT EXISTS regime_logic_version smallint;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_spot_vol_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_spot_vol_24h_check
      CHECK (spot_vol_24h IS NULL OR (finite_float8(spot_vol_24h) AND spot_vol_24h >= 0));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_cvd_spot_imbalance_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_cvd_spot_imbalance_24h_check
      CHECK (cvd_spot_imbalance_24h IS NULL OR (finite_float8(cvd_spot_imbalance_24h)
             AND cvd_spot_imbalance_24h BETWEEN -1 AND 1));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_cvd_fut_imbalance_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_cvd_fut_imbalance_24h_check
      CHECK (cvd_fut_imbalance_24h IS NULL OR (finite_float8(cvd_fut_imbalance_24h)
             AND cvd_fut_imbalance_24h BETWEEN -1 AND 1));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_regime_logic_version_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='signal_observation'::regclass
                 AND conname='signal_observation_regime_logic_version_check') THEN
    ALTER TABLE signal_observation ADD CONSTRAINT signal_observation_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='daily_verdict_snapshot'::regclass
                 AND conname='daily_verdict_snapshot_regime_logic_version_check') THEN
    ALTER TABLE daily_verdict_snapshot
      ADD CONSTRAINT daily_verdict_snapshot_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='signal_observation'::regclass
                 AND conname='signal_observation_pr22_regime_provenance_check') THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_pr22_regime_provenance_check
      CHECK (
        evidence_version <> 3
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
          regime_logic_version IS NULL
          AND regime_score IS NULL
          AND regime_label IS NULL
          AND metrics_snapshot_ts IS NULL
          AND price_cutoff_at IS NULL
          AND metrics_cutoff_at IS NULL
        )
      );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='daily_verdict_snapshot'::regclass
                 AND conname='daily_verdict_snapshot_pr22_regime_provenance_check') THEN
    ALTER TABLE daily_verdict_snapshot
      ADD CONSTRAINT daily_verdict_snapshot_pr22_regime_provenance_check
      CHECK (
        logic_version <> 'daily-verdict-v2'
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
          regime_logic_version IS NULL
          AND regime_score IS NULL
          AND regime_label IS NULL
          AND metrics_snapshot_ts IS NULL
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN metrics_snapshot.regime_logic_version IS
  'NULL=legacy/unversioned; 2=PR22 normalized same-window spot/futures CVD regime logic';
COMMENT ON COLUMN signal_observation.regime_logic_version IS
  'Copied prospectively from the selected metrics_snapshot; NULL remains legacy/unavailable';
COMMENT ON COLUMN daily_verdict_snapshot.regime_logic_version IS
  'Copied prospectively from metrics_snapshot; immutable legacy snapshots remain NULL';

COMMIT;
