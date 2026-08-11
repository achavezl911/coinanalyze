-- PR19 / F2: strict combined provenance.
-- Existing rows remain NULL/unverified; no historical rewrite.
BEGIN;

-- PR19: provenance for materialized two-venue rows.
-- NULL = legacy/unverified. Old rows are not rewritten.
ALTER TABLE spot_trades_agg ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE spot_trades_realtime ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE futures_trades_agg ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE futures_trades_realtime ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE orderbook_snapshot ADD COLUMN IF NOT EXISTS venue_count smallint;

DO $$
DECLARE
    table_name text;
    constraint_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'spot_trades_agg','spot_trades_realtime','futures_trades_agg',
        'futures_trades_realtime','orderbook_snapshot'
    ] LOOP
        constraint_name := table_name || '_venue_count_provenance_check';
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid=to_regclass(format('%I.%I', current_schema(), table_name))
              AND conname=constraint_name
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I CHECK ('
                'venue_count IS NULL OR '
                '(exchange = ''combined'' AND venue_count = 2) OR '
                '(exchange IN (''binance'',''bybit'') AND venue_count = 1)'
                ')',
                table_name, constraint_name
            );
        END IF;
    END LOOP;
END
$$;

COMMENT ON COLUMN spot_trades_agg.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN spot_trades_realtime.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN futures_trades_agg.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN futures_trades_realtime.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN orderbook_snapshot.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';

COMMIT;
