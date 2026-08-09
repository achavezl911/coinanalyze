BEGIN;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL lock_timeout = '10s';

-- Online safety is deliberate: all five sources are locked before the first copy, every
-- replacement is verified, and only then are names swapped in this same transaction.
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
    replacement_name text;
    partition_day date;
    first_day date;
    last_day date;
    source_count bigint;
    replacement_count bigint;
    source_min timestamptz;
    replacement_min timestamptz;
    source_max timestamptz;
    replacement_max timestamptz;
    mismatch_count integer;
    partitioned_count integer;
    ordinary_count integer;
BEGIN
    SELECT count(*) FILTER (WHERE c.relkind = 'p'),
           count(*) FILTER (WHERE c.relkind = 'r')
    INTO partitioned_count, ordinary_count
    FROM unnest(managed) AS names(name)
    LEFT JOIN pg_class c
      ON c.oid = to_regclass(format('%I.%I', schema_name, names.name));

    IF partitioned_count = cardinality(managed) THEN
        RETURN;
    END IF;
    IF ordinary_count <> cardinality(managed) OR partitioned_count <> 0 THEN
        RAISE EXCEPTION
            'temporal partition migration requires all five logical parents to be ordinary tables';
    END IF;
    FOREACH source_name IN ARRAY managed LOOP
        IF to_regclass(format('%I.%I', schema_name, source_name || '_unpartitioned_backup'))
            IS NOT NULL
        THEN
            RAISE EXCEPTION 'backup relation already exists for %', source_name;
        END IF;
        IF to_regclass(format('%I.%I', schema_name, source_name || '__partitioned'))
            IS NOT NULL
        THEN
            RAISE EXCEPTION 'replacement relation already exists for %', source_name;
        END IF;
    END LOOP;

    EXECUTE format(
        'LOCK TABLE %I.futures_trades_realtime, %I.spot_trades_realtime, '
        '%I.orderbook_snapshot, %I.liquidations_realtime, '
        '%I.scalp_signal_snapshot IN ACCESS EXCLUSIVE MODE',
        schema_name, schema_name, schema_name, schema_name, schema_name
    );

    EXECUTE format(
        'CREATE TABLE %I.futures_trades_realtime__partitioned '
        '(LIKE %I.futures_trades_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        'INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION '
        'INCLUDING COMMENTS) PARTITION BY RANGE (ts)', schema_name, schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.futures_trades_realtime__partitioned '
        'ADD CONSTRAINT futures_trades_realtime__partitioned_pkey '
        'PRIMARY KEY (symbol, exchange, ts)', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.futures_trades_realtime__partitioned '
        'ADD CONSTRAINT futures_trades_realtime__partitioned_symbol_fkey '
        'FOREIGN KEY (symbol) REFERENCES %I.symbols(symbol)', schema_name, schema_name
    );
    EXECUTE format(
        'CREATE INDEX futures_trades_realtime__partitioned_ts_idx '
        'ON %I.futures_trades_realtime__partitioned(ts DESC)', schema_name
    );
    EXECUTE format(
        'CREATE INDEX futures_trades_realtime__partitioned_symbol_exchange_ts_idx '
        'ON %I.futures_trades_realtime__partitioned(symbol, exchange, ts DESC)', schema_name
    );

    EXECUTE format(
        'CREATE TABLE %I.spot_trades_realtime__partitioned '
        '(LIKE %I.spot_trades_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        'INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION '
        'INCLUDING COMMENTS) PARTITION BY RANGE (ts)', schema_name, schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.spot_trades_realtime__partitioned '
        'ADD CONSTRAINT spot_trades_realtime__partitioned_pkey '
        'PRIMARY KEY (symbol, exchange, ts)', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.spot_trades_realtime__partitioned '
        'ADD CONSTRAINT spot_trades_realtime__partitioned_symbol_fkey '
        'FOREIGN KEY (symbol) REFERENCES %I.market_assets(base_asset)', schema_name, schema_name
    );
    EXECUTE format(
        'CREATE INDEX spot_trades_realtime__partitioned_ts_idx '
        'ON %I.spot_trades_realtime__partitioned(ts DESC)', schema_name
    );
    EXECUTE format(
        'CREATE INDEX spot_trades_realtime__partitioned_symbol_exchange_ts_idx '
        'ON %I.spot_trades_realtime__partitioned(symbol, exchange, ts DESC)', schema_name
    );

    EXECUTE format(
        'CREATE TABLE %I.orderbook_snapshot__partitioned '
        '(LIKE %I.orderbook_snapshot INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        'INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION '
        'INCLUDING COMMENTS) PARTITION BY RANGE (ts)', schema_name, schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.orderbook_snapshot__partitioned '
        'DROP CONSTRAINT IF EXISTS orderbook_snapshot_non_crossed_check', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.orderbook_snapshot__partitioned '
        'ADD CONSTRAINT orderbook_snapshot__partitioned_pkey '
        'PRIMARY KEY (symbol, exchange, ts)', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.orderbook_snapshot__partitioned '
        'ADD CONSTRAINT orderbook_snapshot__partitioned_symbol_fkey '
        'FOREIGN KEY (symbol) REFERENCES %I.symbols(symbol)', schema_name, schema_name
    );
    EXECUTE format(
        'CREATE INDEX orderbook_snapshot__partitioned_ts_idx '
        'ON %I.orderbook_snapshot__partitioned(ts DESC)', schema_name
    );
    EXECUTE format(
        'CREATE INDEX orderbook_snapshot__partitioned_symbol_exchange_ts_idx '
        'ON %I.orderbook_snapshot__partitioned(symbol, exchange, ts DESC)', schema_name
    );

    EXECUTE format(
        'CREATE TABLE %I.liquidations_realtime__partitioned '
        '(LIKE %I.liquidations_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        'INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION '
        'INCLUDING COMMENTS) PARTITION BY RANGE (ts)', schema_name, schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.liquidations_realtime__partitioned '
        'ADD CONSTRAINT liquidations_realtime__partitioned_pkey '
        'PRIMARY KEY (exchange, event_id, ts)', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.liquidations_realtime__partitioned '
        'ADD CONSTRAINT liquidations_realtime__partitioned_symbol_fkey '
        'FOREIGN KEY (symbol) REFERENCES %I.symbols(symbol)', schema_name, schema_name
    );
    EXECUTE format(
        'CREATE INDEX liquidations_realtime__partitioned_symbol_ts_idx '
        'ON %I.liquidations_realtime__partitioned(symbol, ts DESC)', schema_name
    );

    EXECUTE format(
        'CREATE TABLE %I.scalp_signal_snapshot__partitioned '
        '(LIKE %I.scalp_signal_snapshot INCLUDING DEFAULTS INCLUDING CONSTRAINTS '
        'INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION '
        'INCLUDING COMMENTS) PARTITION BY RANGE (ts)', schema_name, schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.scalp_signal_snapshot__partitioned '
        'ADD CONSTRAINT scalp_signal_snapshot__partitioned_pkey '
        'PRIMARY KEY (symbol, ts)', schema_name
    );
    EXECUTE format(
        'ALTER TABLE %I.scalp_signal_snapshot__partitioned '
        'ADD CONSTRAINT scalp_signal_snapshot__partitioned_symbol_fkey '
        'FOREIGN KEY (symbol) REFERENCES %I.symbols(symbol)', schema_name, schema_name
    );
    EXECUTE format(
        'CREATE INDEX scalp_signal_snapshot__partitioned_latest_idx '
        'ON %I.scalp_signal_snapshot__partitioned(symbol, ts DESC)', schema_name
    );
    EXECUTE format(
        'CREATE INDEX scalp_signal_snapshot__partitioned_state_idx '
        'ON %I.scalp_signal_snapshot__partitioned(symbol, state, ts DESC)', schema_name
    );

    -- Every source receives daily partitions spanning all existing rows plus two future UTC
    -- days. Child names already use the final logical-parent prefix, so lifecycle functions
    -- do not depend on migration-only names after the swap.
    FOREACH source_name IN ARRAY managed LOOP
        replacement_name := source_name || '__partitioned';
        EXECUTE format(
            'SELECT COALESCE(min(ts)::date, (now() AT TIME ZONE ''UTC'')::date - 1), '
            'GREATEST(COALESCE(max(ts)::date, (now() AT TIME ZONE ''UTC'')::date), '
            '(now() AT TIME ZONE ''UTC'')::date + 2) FROM %I.%I',
            schema_name, source_name
        ) INTO first_day, last_day;
        FOR partition_day IN
            SELECT day_value::date
            FROM generate_series(
                first_day::timestamp,
                last_day::timestamp,
                interval '1 day'
            ) AS day_value
        LOOP
            EXECUTE format(
                'CREATE TABLE %I.%I PARTITION OF %I.%I '
                'FOR VALUES FROM (%L) TO (%L)',
                schema_name,
                source_name || '_p' || to_char(partition_day, 'YYYYMMDD'),
                schema_name,
                replacement_name,
                partition_day::timestamp AT TIME ZONE 'UTC',
                (partition_day + 1)::timestamp AT TIME ZONE 'UTC'
            );
        END LOOP;
        EXECUTE format('INSERT INTO %I.%I SELECT * FROM %I.%I',
                       schema_name, replacement_name, schema_name, source_name);
    END LOOP;

    EXECUTE format(
        'ALTER TABLE %I.orderbook_snapshot__partitioned '
        'ADD CONSTRAINT orderbook_snapshot_non_crossed_check '
        'CHECK (bid_px IS NULL OR ask_px IS NULL OR ask_px >= bid_px) NOT VALID', schema_name
    );

    -- Verify rows, timestamp extent, column definitions, checks/FKs, primary-key partition
    -- compatibility, and expected index cardinality before any logical name can change.
    FOREACH source_name IN ARRAY managed LOOP
        replacement_name := source_name || '__partitioned';
        EXECUTE format('SELECT count(*), min(ts), max(ts) FROM %I.%I',
                       schema_name, source_name)
            INTO source_count, source_min, source_max;
        EXECUTE format('SELECT count(*), min(ts), max(ts) FROM %I.%I',
                       schema_name, replacement_name)
            INTO replacement_count, replacement_min, replacement_max;
        IF (source_count, source_min, source_max) IS DISTINCT FROM
           (replacement_count, replacement_min, replacement_max)
        THEN
            RAISE EXCEPTION 'COUNT/MIN/MAX verification failed for %', source_name;
        END IF;

        SELECT count(*) INTO mismatch_count
        FROM (
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   a.attidentity, a.attgenerated, pg_get_expr(d.adbin, d.adrelid) AS default_expr
            FROM pg_attribute a
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = to_regclass(format('%I.%I', schema_name, source_name))
              AND a.attnum > 0 AND NOT a.attisdropped
            EXCEPT
            SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull,
                   a.attidentity, a.attgenerated, pg_get_expr(d.adbin, d.adrelid) AS default_expr
            FROM pg_attribute a
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = to_regclass(format('%I.%I', schema_name, replacement_name))
              AND a.attnum > 0 AND NOT a.attisdropped
        ) differences;
        IF mismatch_count <> 0 THEN
            RAISE EXCEPTION 'column verification failed for %', source_name;
        END IF;

        SELECT count(*) INTO mismatch_count
        FROM (
            SELECT contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = to_regclass(format('%I.%I', schema_name, source_name))
              AND contype IN ('c', 'f')
            EXCEPT
            SELECT contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = to_regclass(format('%I.%I', schema_name, replacement_name))
              AND contype IN ('c', 'f')
        ) differences;
        IF mismatch_count <> 0 THEN
            RAISE EXCEPTION 'constraint verification failed for %', source_name;
        END IF;

        SELECT count(*) INTO mismatch_count
        FROM pg_constraint c
        WHERE c.conrelid = to_regclass(format('%I.%I', schema_name, replacement_name))
          AND c.contype = 'p'
          AND NOT EXISTS (
              SELECT 1
              FROM unnest(c.conkey) AS key(attnum)
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = key.attnum
              WHERE a.attname = 'ts'
          );
        IF mismatch_count <> 0 OR NOT EXISTS (
            SELECT 1 FROM pg_constraint c
            WHERE c.conrelid = to_regclass(format('%I.%I', schema_name, replacement_name))
              AND c.contype = 'p'
        ) THEN
            RAISE EXCEPTION 'partition-compatible primary key verification failed for %', source_name;
        END IF;

        IF (SELECT count(*) FROM pg_index
            WHERE indrelid = to_regclass(format('%I.%I', schema_name, replacement_name)))
           <
           (SELECT count(*) FROM pg_index
            WHERE indrelid = to_regclass(format('%I.%I', schema_name, source_name)))
        THEN
            RAISE EXCEPTION 'index verification failed for %', source_name;
        END IF;
    END LOOP;

    FOREACH source_name IN ARRAY managed LOOP
        replacement_name := source_name || '__partitioned';
        EXECUTE format('ALTER TABLE %I.%I RENAME TO %I',
                       schema_name, source_name, source_name || '_unpartitioned_backup');
        EXECUTE format('ALTER TABLE %I.%I RENAME TO %I',
                       schema_name, replacement_name, source_name);
    END LOOP;
END
$$;

-- The old liquidation key could be global without ts. The partitioned primary key must
-- include ts, so this trigger preserves the stronger cross-partition (exchange,event_id)
-- identity under a transaction advisory lock.
CREATE OR REPLACE FUNCTION enforce_liquidation_event_unique()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtextextended('liquidation-event:' || NEW.exchange || ':' || NEW.event_id, 0)
    );
    IF EXISTS (
        SELECT 1 FROM liquidations_realtime
        WHERE exchange = NEW.exchange AND event_id = NEW.event_id
    ) THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS liquidations_realtime_event_unique_trigger
    ON liquidations_realtime;
CREATE TRIGGER liquidations_realtime_event_unique_trigger
BEFORE INSERT ON liquidations_realtime
FOR EACH ROW EXECUTE FUNCTION enforce_liquidation_event_unique();

CREATE OR REPLACE FUNCTION ensure_temporal_partitions(
    reference_ts timestamptz DEFAULT now(),
    days_before integer DEFAULT 1,
    days_after integer DEFAULT 2
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    managed_table text;
    partition_day date;
    child_name text;
    schema_name text := current_schema();
    parent_oid regclass;
    child_oid regclass;
    created_count integer := 0;
BEGIN
    IF days_before < 0 OR days_after < 0 THEN
        RAISE EXCEPTION 'partition lookaround must be non-negative';
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended(schema_name || ':ensure_temporal_partitions', 0)
    );
    FOREACH managed_table IN ARRAY ARRAY[
        'futures_trades_realtime', 'spot_trades_realtime', 'orderbook_snapshot',
        'liquidations_realtime', 'scalp_signal_snapshot'
    ] LOOP
        parent_oid := to_regclass(format('%I.%I', schema_name, managed_table));
        IF parent_oid IS NULL OR NOT EXISTS (
            SELECT 1 FROM pg_class WHERE oid = parent_oid AND relkind = 'p'
        ) THEN
            CONTINUE;
        END IF;
        FOR partition_day IN
            SELECT (reference_ts AT TIME ZONE 'UTC')::date + day_offset
            FROM generate_series(-days_before, days_after) AS day_offset
        LOOP
            child_name := managed_table || '_p' || to_char(partition_day, 'YYYYMMDD');
            child_oid := to_regclass(format('%I.%I', schema_name, child_name));
            IF child_oid IS NULL THEN
                EXECUTE format(
                    'CREATE TABLE %I.%I PARTITION OF %I.%I FOR VALUES FROM (%L) TO (%L)',
                    schema_name, child_name, schema_name, managed_table,
                    partition_day::timestamp AT TIME ZONE 'UTC',
                    (partition_day + 1)::timestamp AT TIME ZONE 'UTC'
                );
                created_count := created_count + 1;
                child_oid := to_regclass(format('%I.%I', schema_name, child_name));
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_inherits
                WHERE inhparent = parent_oid AND inhrelid = child_oid
            ) THEN
                RAISE EXCEPTION '% exists but is not a partition of %', child_name, managed_table;
            END IF;
        END LOOP;
    END LOOP;
    RETURN created_count;
END
$$;

CREATE OR REPLACE FUNCTION drop_expired_temporal_partitions(
    parent_name text,
    cutoff timestamptz
)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    allowed constant text[] := ARRAY[
        'futures_trades_realtime', 'spot_trades_realtime', 'orderbook_snapshot',
        'liquidations_realtime', 'scalp_signal_snapshot'
    ];
    schema_name text := current_schema();
    parent_oid regclass;
    child record;
    partition_day date;
    dropped_count integer := 0;
BEGIN
    IF NOT parent_name = ANY(allowed) THEN
        RAISE EXCEPTION 'table is not managed by temporal partitioning: %', parent_name;
    END IF;
    parent_oid := to_regclass(format('%I.%I', schema_name, parent_name));
    IF parent_oid IS NULL OR NOT EXISTS (
        SELECT 1 FROM pg_class WHERE oid = parent_oid AND relkind = 'p'
    ) THEN
        RAISE EXCEPTION '% is not a partitioned table', parent_name;
    END IF;
    PERFORM pg_advisory_xact_lock(
        hashtextextended(schema_name || ':retention:' || parent_name, 0)
    );
    FOR child IN
        SELECT c.relname
        FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
        WHERE i.inhparent = parent_oid
          AND c.relname ~ ('^' || parent_name || '_p[0-9]{8}$')
        ORDER BY c.relname
    LOOP
        partition_day := to_date(right(child.relname, 8), 'YYYYMMDD');
        IF (partition_day + 1)::timestamp AT TIME ZONE 'UTC' <= cutoff THEN
            EXECUTE format('DROP TABLE %I.%I', schema_name, child.relname);
            dropped_count := dropped_count + 1;
        END IF;
    END LOOP;
    RETURN dropped_count;
END
$$;

CREATE OR REPLACE FUNCTION apply_temporal_retention(
    parent_name text,
    retention_hours integer
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
    cutoff timestamptz;
    deleted_count bigint;
BEGIN
    IF retention_hours <= 0 THEN
        RAISE EXCEPTION 'retention_hours must be positive';
    END IF;
    cutoff := statement_timestamp() - make_interval(hours => retention_hours);
    PERFORM ensure_temporal_partitions();
    PERFORM drop_expired_temporal_partitions(parent_name, cutoff);
    EXECUTE format('DELETE FROM %I.%I WHERE ts < $1', current_schema(), parent_name)
        USING cutoff;
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END
$$;

SELECT ensure_temporal_partitions();
COMMIT;
