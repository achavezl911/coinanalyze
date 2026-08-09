BEGIN;

ALTER TABLE metrics_snapshot
    ADD COLUMN IF NOT EXISTS price_cutoff_at timestamptz;
ALTER TABLE metrics_snapshot
    ADD COLUMN IF NOT EXISTS metrics_cutoff_at timestamptz;

CREATE TABLE IF NOT EXISTS service_ownership (
    service text NOT NULL CHECK (length(service) BETWEEN 1 AND 100),
    shard_index integer NOT NULL CHECK (shard_index >= 0),
    shard_count integer NOT NULL CHECK (shard_count > 0 AND shard_index < shard_count),
    generation bigint NOT NULL CHECK (generation > 0),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (service, shard_index, shard_count)
);

COMMIT;
