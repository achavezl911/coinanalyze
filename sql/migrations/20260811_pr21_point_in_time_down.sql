-- PR21 rollback is allowed only before durable research evidence has accumulated.
BEGIN;
DO $$
DECLARE
    snapshot_has_rows boolean;
BEGIN
    IF to_regclass('daily_verdict_snapshot') IS NOT NULL THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM daily_verdict_snapshot)'
            INTO snapshot_has_rows;
        IF snapshot_has_rows THEN
            RAISE EXCEPTION
                'PR21 down migration refuses to destroy daily_verdict_snapshot research evidence'
                USING ERRCODE = '55000';
        END IF;
    END IF;
END
$$;

DROP TABLE IF EXISTS daily_verdict_snapshot;
DROP FUNCTION IF EXISTS reject_daily_verdict_snapshot_mutation();
COMMIT;
