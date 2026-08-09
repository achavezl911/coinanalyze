-- Ejecutar solo después de detener collectors y respaldar PostgreSQL. El rollback se niega
-- si ya existen activos distintos de BTC/ETH/SOL para no convertir una vuelta de versión en
-- pérdida silenciosa de datos.
BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM symbols WHERE base_asset NOT IN ('BTC','ETH','SOL')
        UNION ALL
        SELECT 1 FROM spot_trades_agg WHERE symbol NOT IN ('BTC','ETH','SOL')
        UNION ALL
        SELECT 1 FROM spot_trades_realtime WHERE symbol NOT IN ('BTC','ETH','SOL')
    ) THEN
        RAISE EXCEPTION 'rollback blocked: non-default market assets contain data';
    END IF;
END $$;

ALTER TABLE symbols DROP CONSTRAINT IF EXISTS symbols_base_asset_fkey;
ALTER TABLE spot_trades_agg DROP CONSTRAINT IF EXISTS spot_trades_agg_symbol_fkey;
ALTER TABLE spot_trades_realtime DROP CONSTRAINT IF EXISTS spot_trades_realtime_symbol_fkey;

ALTER TABLE symbols DROP CONSTRAINT IF EXISTS symbols_base_asset_check;
ALTER TABLE symbols ADD CONSTRAINT symbols_base_asset_check
    CHECK (base_asset IN ('BTC','ETH','SOL'));
ALTER TABLE spot_trades_agg DROP CONSTRAINT IF EXISTS spot_trades_agg_symbol_check;
ALTER TABLE spot_trades_agg ADD CONSTRAINT spot_trades_agg_symbol_check
    CHECK (symbol IN ('BTC','ETH','SOL'));
ALTER TABLE spot_trades_realtime DROP CONSTRAINT IF EXISTS spot_trades_realtime_symbol_check;
ALTER TABLE spot_trades_realtime ADD CONSTRAINT spot_trades_realtime_symbol_check
    CHECK (symbol IN ('BTC','ETH','SOL'));

DELETE FROM pipeline_heartbeat
WHERE service ~ '^(ws|ws-binance|ws-bybit|scalp):[0-9]+/[0-9]+$';
ALTER TABLE pipeline_heartbeat DROP CONSTRAINT IF EXISTS pipeline_heartbeat_service_check;
ALTER TABLE pipeline_heartbeat ADD CONSTRAINT pipeline_heartbeat_service_check
    CHECK (service IN ('ingest','ws','ws-binance','ws-bybit','scalp','daily','api'));

DROP TABLE IF EXISTS external_api_rate_event;
DROP TABLE IF EXISTS market_feed_health_shard;
DROP TABLE IF EXISTS market_assets;

COMMIT;
