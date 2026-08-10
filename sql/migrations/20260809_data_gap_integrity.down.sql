BEGIN;

-- Explicit rollback for the Phase A metadata only. No market-data table is altered or
-- deleted by this rollback.
DROP TABLE IF EXISTS data_gap;

COMMIT;
