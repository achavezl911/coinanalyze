-- Ejecutar solo con todos los collectors detenidos. El rollback elimina únicamente
-- metadata de fencing y de cutoffs; no elimina datos de mercado.
BEGIN;

DROP TABLE IF EXISTS service_ownership;

ALTER TABLE metrics_snapshot DROP COLUMN IF EXISTS metrics_cutoff_at;
ALTER TABLE metrics_snapshot DROP COLUMN IF EXISTS price_cutoff_at;

COMMIT;
