BEGIN;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL lock_timeout = '10s';

-- Rollback is supported only while the untouched pre-migration copies and the logical
-- partitioned parents contain exactly the same rows. Any post-migration write or retention
-- change aborts the whole transaction rather than silently discarding data.
DO $$
DECLARE
    schema_name text := current_schema();
    managed constant text[] := ARRAY[
        'futures_trades_realtime',
        'spot_trades_realtime',
        'orderbook_snapshot',
        'liquidations_realtime',
        'scalp_signal_snapshot'
    ];
    source_name text;
    backup_name text;
    logical_partitioned integer;
    logical_ordinary integer;
    backup_ordinary integer;
    differs boolean;
BEGIN
    SELECT count(*) FILTER (WHERE logical.relkind = 'p'),
           count(*) FILTER (WHERE logical.relkind = 'r'),
           count(*) FILTER (WHERE backup.relkind = 'r')
    INTO logical_partitioned, logical_ordinary, backup_ordinary
    FROM unnest(managed) AS names(name)
    LEFT JOIN pg_class logical
      ON logical.oid = to_regclass(format('%I.%I', schema_name, names.name))
    LEFT JOIN pg_class backup
      ON backup.oid = to_regclass(
          format('%I.%I', schema_name, names.name || '_unpartitioned_backup')
      );

    IF logical_ordinary = cardinality(managed) AND backup_ordinary = 0 THEN
        RETURN;
    END IF;
    IF logical_partitioned <> cardinality(managed)
       OR backup_ordinary <> cardinality(managed)
    THEN
        RAISE EXCEPTION
            'safe rollback requires all five partitioned parents and all five legacy backups';
    END IF;

    EXECUTE format(
        'LOCK TABLE %I.futures_trades_realtime, '
        '%I.futures_trades_realtime_unpartitioned_backup, '
        '%I.spot_trades_realtime, %I.spot_trades_realtime_unpartitioned_backup, '
        '%I.orderbook_snapshot, %I.orderbook_snapshot_unpartitioned_backup, '
        '%I.liquidations_realtime, %I.liquidations_realtime_unpartitioned_backup, '
        '%I.scalp_signal_snapshot, %I.scalp_signal_snapshot_unpartitioned_backup '
        'IN ACCESS EXCLUSIVE MODE',
        schema_name, schema_name, schema_name, schema_name, schema_name,
        schema_name, schema_name, schema_name, schema_name, schema_name
    );

    FOREACH source_name IN ARRAY managed LOOP
        backup_name := source_name || '_unpartitioned_backup';
        EXECUTE format(
            'SELECT EXISTS ('
            '(SELECT * FROM %I.%I EXCEPT ALL SELECT * FROM %I.%I) '
            'UNION ALL '
            '(SELECT * FROM %I.%I EXCEPT ALL SELECT * FROM %I.%I)'
            ')',
            schema_name, source_name, schema_name, backup_name,
            schema_name, backup_name, schema_name, source_name
        ) INTO differs;
        IF differs THEN
            RAISE EXCEPTION
                'unsafe rollback refused: rows changed after migration in %', source_name;
        END IF;
    END LOOP;

    FOREACH source_name IN ARRAY managed LOOP
        backup_name := source_name || '_unpartitioned_backup';
        EXECUTE format('DROP TABLE %I.%I', schema_name, source_name);
        EXECUTE format('ALTER TABLE %I.%I RENAME TO %I',
                       schema_name, backup_name, source_name);
    END LOOP;
END
$$;

DROP FUNCTION IF EXISTS apply_temporal_retention(text, integer);
DROP FUNCTION IF EXISTS drop_expired_temporal_partitions(text, timestamptz);
DROP FUNCTION IF EXISTS ensure_temporal_partitions(timestamptz, integer, integer);

-- The supported rollback target is the compatibility bridge release. Its legacy
-- table still uses this function and trigger with the three-column writer.
DELETE FROM schema_migration
WHERE name = '20260809_temporal_partitioning';

COMMIT;
