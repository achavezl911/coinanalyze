-- Use only together with an application rollback to 5ed802f. The legacy
-- two-column primary key is required before this compatibility layer is removed.
BEGIN;

DO $$
DECLARE
    relation_kind "char";
    primary_key_columns text[];
BEGIN
    IF to_regclass('schema_migration') IS NULL OR NOT EXISTS (
        SELECT 1
        FROM schema_migration
        WHERE name = '20260809_partition_compatibility_bridge'
    ) THEN
        RETURN;
    END IF;

    SELECT relkind
    INTO relation_kind
    FROM pg_class
    WHERE oid = 'liquidations_realtime'::regclass;

    IF relation_kind IS DISTINCT FROM 'r'::"char" THEN
        RAISE EXCEPTION
            'bridge rollback blocked: liquidations_realtime is not a legacy ordinary table';
    END IF;

    SELECT array_agg(attribute.attname ORDER BY key_column.ordinality)
    INTO primary_key_columns
    FROM pg_constraint AS constraint_definition
    JOIN LATERAL unnest(constraint_definition.conkey)
      WITH ORDINALITY AS key_column(attnum, ordinality) ON true
    JOIN pg_attribute AS attribute
      ON attribute.attrelid = constraint_definition.conrelid
     AND attribute.attnum = key_column.attnum
    WHERE constraint_definition.conrelid = 'liquidations_realtime'::regclass
      AND constraint_definition.contype = 'p';

    IF primary_key_columns IS DISTINCT FROM ARRAY['exchange', 'event_id']::text[] THEN
        RAISE EXCEPTION
            'bridge rollback blocked: legacy liquidation primary key is not intact';
    END IF;

    LOCK TABLE liquidations_realtime IN ACCESS EXCLUSIVE MODE;
    DROP TRIGGER IF EXISTS liquidations_realtime_event_unique_trigger
        ON liquidations_realtime;
    DROP FUNCTION IF EXISTS enforce_liquidation_event_unique();
    DROP INDEX IF EXISTS liquidations_realtime_exchange_event_ts_uidx;
    DELETE FROM schema_migration
    WHERE name = '20260809_partition_compatibility_bridge';
END $$;

COMMIT;
