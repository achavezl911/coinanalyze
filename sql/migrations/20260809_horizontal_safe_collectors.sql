BEGIN;

CREATE TABLE IF NOT EXISTS market_assets (
    base_asset text PRIMARY KEY CHECK (length(base_asset) BETWEEN 1 AND 20),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO market_assets(base_asset)
SELECT DISTINCT base_asset FROM symbols
ON CONFLICT DO NOTHING;
INSERT INTO market_assets(base_asset) VALUES ('BTC'),('ETH'),('SOL')
ON CONFLICT DO NOTHING;

ALTER TABLE symbols DROP CONSTRAINT IF EXISTS symbols_base_asset_check;
ALTER TABLE spot_trades_agg DROP CONSTRAINT IF EXISTS spot_trades_agg_symbol_check;
ALTER TABLE spot_trades_realtime DROP CONSTRAINT IF EXISTS spot_trades_realtime_symbol_check;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'symbols_base_asset_fkey') THEN
        ALTER TABLE symbols ADD CONSTRAINT symbols_base_asset_fkey
            FOREIGN KEY (base_asset) REFERENCES market_assets(base_asset);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'spot_trades_agg_symbol_fkey') THEN
        ALTER TABLE spot_trades_agg ADD CONSTRAINT spot_trades_agg_symbol_fkey
            FOREIGN KEY (symbol) REFERENCES market_assets(base_asset);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'spot_trades_realtime_symbol_fkey'
    ) THEN
        ALTER TABLE spot_trades_realtime ADD CONSTRAINT spot_trades_realtime_symbol_fkey
            FOREIGN KEY (symbol) REFERENCES market_assets(base_asset);
    END IF;
END $$;

ALTER TABLE pipeline_heartbeat DROP CONSTRAINT IF EXISTS pipeline_heartbeat_service_check;
ALTER TABLE pipeline_heartbeat ADD CONSTRAINT pipeline_heartbeat_service_check
    CHECK (length(service) BETWEEN 1 AND 100);

CREATE TABLE IF NOT EXISTS external_api_rate_event (
    provider text NOT NULL,
    ts timestamptz NOT NULL DEFAULT now(),
    units integer NOT NULL CHECK (units > 0)
);
CREATE INDEX IF NOT EXISTS external_api_rate_event_provider_ts_idx
    ON external_api_rate_event(provider, ts);

CREATE TABLE IF NOT EXISTS market_feed_health_shard (
    feed text NOT NULL,
    exchange text NOT NULL,
    shard_index integer NOT NULL CHECK (shard_index >= 0),
    shard_count integer NOT NULL CHECK (shard_count > 0 AND shard_index < shard_count),
    status text NOT NULL CHECK (status IN ('ok','degraded','error')),
    healthy_since timestamptz,
    last_loss_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    detail text CHECK (detail IS NULL OR length(detail) <= 500),
    PRIMARY KEY (feed, exchange, shard_index, shard_count)
);
CREATE INDEX IF NOT EXISTS market_feed_health_shard_updated_idx
    ON market_feed_health_shard(feed, exchange, shard_count, updated_at DESC);

COMMIT;
