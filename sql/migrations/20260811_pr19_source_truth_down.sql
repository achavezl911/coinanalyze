-- PR19 rollback helper. Normal app rollback does not require schema rollback.
BEGIN;
ALTER TABLE spot_trades_agg DROP CONSTRAINT IF EXISTS spot_trades_agg_venue_count_provenance_check;
ALTER TABLE spot_trades_realtime DROP CONSTRAINT IF EXISTS spot_trades_realtime_venue_count_provenance_check;
ALTER TABLE futures_trades_agg DROP CONSTRAINT IF EXISTS futures_trades_agg_venue_count_provenance_check;
ALTER TABLE futures_trades_realtime DROP CONSTRAINT IF EXISTS futures_trades_realtime_venue_count_provenance_check;
ALTER TABLE orderbook_snapshot DROP CONSTRAINT IF EXISTS orderbook_snapshot_venue_count_provenance_check;
ALTER TABLE spot_trades_agg DROP COLUMN IF EXISTS venue_count;
ALTER TABLE spot_trades_realtime DROP COLUMN IF EXISTS venue_count;
ALTER TABLE futures_trades_agg DROP COLUMN IF EXISTS venue_count;
ALTER TABLE futures_trades_realtime DROP COLUMN IF EXISTS venue_count;
ALTER TABLE orderbook_snapshot DROP COLUMN IF EXISTS venue_count;
COMMIT;
