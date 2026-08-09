-- Compatibility release prerequisite for temporal partitioning.
-- Safe on the legacy ordinary table and on the future partitioned parent.
BEGIN;

DO $$
DECLARE
    has_three_column_arbiter boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_index AS index_definition
        WHERE index_definition.indrelid = 'liquidations_realtime'::regclass
          AND index_definition.indisunique
          AND index_definition.indisvalid
          AND index_definition.indpred IS NULL
          AND index_definition.indexprs IS NULL
          AND (
              SELECT array_agg(attribute.attname::text ORDER BY key_column.ordinality)
              FROM unnest(index_definition.indkey)
                WITH ORDINALITY AS key_column(attnum, ordinality)
              JOIN pg_attribute AS attribute
                ON attribute.attrelid = index_definition.indrelid
               AND attribute.attnum = key_column.attnum
          ) = ARRAY['exchange', 'event_id', 'ts']::text[]
    ) INTO has_three_column_arbiter;

    IF NOT has_three_column_arbiter THEN
        CREATE UNIQUE INDEX liquidations_realtime_exchange_event_ts_uidx
            ON liquidations_realtime(exchange, event_id, ts);
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_index AS index_definition
        WHERE index_definition.indrelid = 'liquidations_realtime'::regclass
          AND index_definition.indisunique
          AND index_definition.indisvalid
          AND index_definition.indpred IS NULL
          AND index_definition.indexprs IS NULL
          AND (
              SELECT array_agg(attribute.attname::text ORDER BY key_column.ordinality)
              FROM unnest(index_definition.indkey)
                WITH ORDINALITY AS key_column(attnum, ordinality)
              JOIN pg_attribute AS attribute
                ON attribute.attrelid = index_definition.indrelid
               AND attribute.attnum = key_column.attnum
          ) = ARRAY['exchange', 'event_id', 'ts']::text[]
    ) INTO has_three_column_arbiter;

    IF NOT has_three_column_arbiter THEN
        RAISE EXCEPTION
            'bridge migration blocked: liquidation three-column unique index is invalid';
    END IF;
END $$;

CREATE OR REPLACE FUNCTION enforce_liquidation_event_unique()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended(NEW.exchange || E'\x1f' || NEW.event_id, 0)
    );
    IF EXISTS (
        SELECT 1
        FROM liquidations_realtime
        WHERE exchange = NEW.exchange
          AND event_id = NEW.event_id
    ) THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS liquidations_realtime_event_unique_trigger
    ON liquidations_realtime;
CREATE TRIGGER liquidations_realtime_event_unique_trigger
BEFORE INSERT ON liquidations_realtime
FOR EACH ROW EXECUTE FUNCTION enforce_liquidation_event_unique();

CREATE TABLE IF NOT EXISTS schema_migration (
    name text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO schema_migration(name)
VALUES ('20260809_partition_compatibility_bridge')
ON CONFLICT (name) DO NOTHING;

COMMIT;
