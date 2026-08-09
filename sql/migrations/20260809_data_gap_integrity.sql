BEGIN;

CREATE TABLE IF NOT EXISTS data_gap (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    feed text NOT NULL CHECK (length(feed) BETWEEN 1 AND 80),
    feed_class text NOT NULL CHECK (feed_class IN ('cadence','event_stream')),
    exchange text NOT NULL CHECK (length(exchange) BETWEEN 1 AND 40),
    market text NOT NULL CHECK (length(market) BETWEEN 1 AND 40),
    symbol text NOT NULL CHECK (length(symbol) BETWEEN 1 AND 80),
    granularity text NOT NULL CHECK (length(granularity) BETWEEN 1 AND 40),
    start_ts timestamptz NOT NULL,
    end_ts timestamptz NOT NULL,
    expected_cadence interval,
    evidence_type text NOT NULL CHECK (
        evidence_type IN (
            'missing_interval', 'queue_full', 'disconnect',
            'sequence_discontinuity', 'collector_outage', 'source_failure'
        )
    ),
    detection_reason text NOT NULL CHECK (length(detection_reason) BETWEEN 1 AND 500),
    detection_source text NOT NULL CHECK (length(detection_source) BETWEEN 1 AND 120),
    status text NOT NULL DEFAULT 'unresolved'
        CHECK (status IN ('unresolved','recovered','unrecoverable')),
    detected_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz,
    recovered_at timestamptz,
    recovered_by text,
    recovery_attempts integer NOT NULL DEFAULT 0 CHECK (recovery_attempts >= 0),
    last_recovery_attempt_at timestamptz,
    resolution_reason text,
    recovery_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (start_ts < end_ts),
    CHECK (
        (feed_class = 'cadence' AND expected_cadence > interval '0 seconds'
         AND evidence_type = 'missing_interval')
        OR
        (feed_class = 'event_stream' AND expected_cadence IS NULL
         AND evidence_type <> 'missing_interval')
    ),
    CHECK (
        (status = 'unresolved' AND resolved_at IS NULL AND recovered_at IS NULL)
        OR
        (status = 'recovered' AND resolved_at IS NOT NULL AND recovered_at IS NOT NULL)
        OR
        (status = 'unrecoverable' AND resolved_at IS NOT NULL AND recovered_at IS NULL)
    ),
    UNIQUE (
        feed, exchange, market, symbol, granularity,
        start_ts, end_ts, evidence_type, detection_source
    )
);

CREATE INDEX IF NOT EXISTS data_gap_overlap_idx
    ON data_gap(feed, exchange, market, symbol, start_ts, end_ts)
    WHERE status IN ('unresolved','unrecoverable');
CREATE INDEX IF NOT EXISTS data_gap_status_detected_idx
    ON data_gap(status, detected_at DESC);

COMMIT;
