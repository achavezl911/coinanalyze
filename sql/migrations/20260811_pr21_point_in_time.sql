-- PR21 F5: prospective first-observed daily verdict evidence.
-- Deliberately no INSERT ... SELECT from daily_verdict: legacy rows may have been rewritten.
BEGIN;
CREATE TABLE IF NOT EXISTS daily_verdict_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_date date NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    snapshot_version smallint NOT NULL CHECK (snapshot_version >= 1),
    logic_version text NOT NULL CHECK (length(logic_version) BETWEEN 1 AND 80),
    observed_at timestamptz NOT NULL,
    session_end_at timestamptz NOT NULL,
    metrics_snapshot_ts timestamptz,
    session_coverage_version smallint CHECK (
        session_coverage_version IS NULL OR session_coverage_version >= 1
    ),
    swing_bias text CHECK (
        swing_bias IS NULL OR swing_bias IN ('LONG','SHORT','NEUTRAL')
    ),
    swing_score double precision CHECK (
        swing_score IS NULL OR finite_float8(swing_score)
    ),
    swing_conviction text CHECK (
        swing_conviction IS NULL OR swing_conviction IN ('baja','media','alta')
    ),
    long_share_pct double precision CHECK (
        long_share_pct IS NULL
        OR (finite_float8(long_share_pct) AND long_share_pct BETWEEN 0 AND 100)
    ),
    swing_components jsonb CHECK (
        swing_components IS NULL OR jsonb_typeof(swing_components) = 'array'
    ),
    regime_score double precision CHECK (
        regime_score IS NULL
        OR (finite_float8(regime_score) AND regime_score BETWEEN -100 AND 100)
    ),
    regime_label text CHECK (
        regime_label IS NULL OR length(regime_label) BETWEEN 1 AND 100
    ),
    setup_id text CHECK (setup_id IS NULL OR length(setup_id) BETWEEN 1 AND 8),
    setup_name text CHECK (setup_name IS NULL OR length(setup_name) BETWEEN 1 AND 80),
    setup_state text CHECK (
        setup_state IS NULL OR setup_state IN ('activo','vigilancia','inactivo')
    ),
    setup_confidence integer CHECK (
        setup_confidence IS NULL OR setup_confidence BETWEEN 0 AND 100
    ),
    daily_streak integer,
    session_price_close double precision CHECK (
        session_price_close IS NULL
        OR (finite_float8(session_price_close) AND session_price_close > 0)
    ),
    reference_price double precision CHECK (
        reference_price IS NULL
        OR (finite_float8(reference_price) AND reference_price > 0)
    ),
    reference_price_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(symbol, session_date),
    CHECK (observed_at >= session_end_at),
    CHECK ((reference_price IS NULL) = (reference_price_at IS NULL)),
    CHECK (reference_price_at IS NULL OR reference_price_at <= observed_at)
);

CREATE INDEX IF NOT EXISTS daily_verdict_snapshot_date_idx
    ON daily_verdict_snapshot(session_date DESC);

CREATE OR REPLACE FUNCTION reject_daily_verdict_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'daily_verdict_snapshot is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS daily_verdict_snapshot_no_update_delete
    ON daily_verdict_snapshot;
CREATE TRIGGER daily_verdict_snapshot_no_update_delete
BEFORE UPDATE OR DELETE ON daily_verdict_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_daily_verdict_snapshot_mutation();

DROP TRIGGER IF EXISTS daily_verdict_snapshot_no_truncate
    ON daily_verdict_snapshot;
CREATE TRIGGER daily_verdict_snapshot_no_truncate
BEFORE TRUNCATE ON daily_verdict_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION reject_daily_verdict_snapshot_mutation();
COMMIT;
