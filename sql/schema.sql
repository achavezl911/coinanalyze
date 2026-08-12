BEGIN;

CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
    SELECT value NOT IN ('NaN'::double precision, 'Infinity'::double precision, '-Infinity'::double precision)
$$;

CREATE TABLE IF NOT EXISTS market_assets (
    base_asset text PRIMARY KEY CHECK (length(base_asset) BETWEEN 1 AND 20),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO market_assets(base_asset) VALUES ('BTC'),('ETH'),('SOL')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS symbols (
    symbol text PRIMARY KEY,
    base_asset text NOT NULL REFERENCES market_assets(base_asset),
    quote_asset text NOT NULL DEFAULT 'USDT' CHECK (quote_asset = 'USDT'),
    is_perpetual boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE symbols DROP CONSTRAINT IF EXISTS symbols_base_asset_check;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'symbols_base_asset_fkey'
    ) THEN
        ALTER TABLE symbols ADD CONSTRAINT symbols_base_asset_fkey
            FOREIGN KEY (base_asset) REFERENCES market_assets(base_asset);
    END IF;
END $$;

INSERT INTO symbols(symbol, base_asset) VALUES
    ('BTCUSDT_PERP.A','BTC'),
    ('ETHUSDT_PERP.A','ETH'),
    ('SOLUSDT_PERP.A','SOL')
ON CONFLICT DO NOTHING;

-- v1.4.8: spot de Coinalyze del MISMO venue que el perp (.A = Binance). Solo existe como
-- destino de la FK de ohlcv; nada consulta esta tabla y `validate_symbol` sigue filtrando
-- contra SUPPORTED_SYMBOLS, asi que estas filas no aparecen en el selector del dashboard.
INSERT INTO symbols(symbol, base_asset, is_perpetual) VALUES
    ('BTCUSD.A','BTC',false),
    ('ETHUSD.A','ETH',false),
    ('SOLUSD.A','SOL',false)
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS ohlcv (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval IN ('1min','5min','4hour','daily')),
    open double precision NOT NULL CHECK (finite_float8(open) AND open > 0),
    high double precision NOT NULL CHECK (finite_float8(high) AND high > 0),
    low double precision NOT NULL CHECK (finite_float8(low) AND low > 0),
    close double precision NOT NULL CHECK (finite_float8(close) AND close > 0),
    volume double precision NOT NULL CHECK (finite_float8(volume) AND volume >= 0),
    buy_volume double precision NOT NULL CHECK (finite_float8(buy_volume) AND buy_volume >= 0 AND buy_volume <= volume),
    sell_volume double precision GENERATED ALWAYS AS (volume - buy_volume) STORED,
    delta double precision GENERATED ALWAYS AS ((2 * buy_volume) - volume) STORED,
    tx bigint NOT NULL CHECK (tx >= 0),
    btx bigint NOT NULL CHECK (btx >= 0 AND btx <= tx),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (high >= GREATEST(open, close, low)),
    CHECK (low <= LEAST(open, close, high))
);
CREATE INDEX IF NOT EXISTS ohlcv_ts_idx ON ohlcv(ts DESC);

-- Instalaciones anteriores solo aceptaban 1min/5min. El OHLCV diario permite conservar
-- dos años de memoria estructural con ~2,200 filas en vez de cientos de miles de velas 5m.
-- '4hour' se añadió en v1.3.9: Coinalyze sirve ese intervalo hasta ~300 días (medido: completo
-- a 300d, vacío a 365d), mientras que 5min solo llega a ~8-9 días. Los pivotes 4h de
-- price_barriers pedían 720 barras (120 días) y se estaban calculando sobre 48.
ALTER TABLE ohlcv DROP CONSTRAINT IF EXISTS ohlcv_interval_check;
ALTER TABLE ohlcv ADD CONSTRAINT ohlcv_interval_check
    CHECK (interval IN ('1min','5min','4hour','daily'));

CREATE TABLE IF NOT EXISTS open_interest (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    oi_open double precision NOT NULL CHECK (finite_float8(oi_open) AND oi_open >= 0),
    oi_high double precision NOT NULL CHECK (finite_float8(oi_high) AND oi_high >= 0),
    oi_low double precision NOT NULL CHECK (finite_float8(oi_low) AND oi_low >= 0),
    oi_close double precision NOT NULL CHECK (finite_float8(oi_close) AND oi_close >= 0),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (oi_high >= GREATEST(oi_open, oi_close, oi_low)),
    CHECK (oi_low <= LEAST(oi_open, oi_close, oi_high))
);
CREATE INDEX IF NOT EXISTS open_interest_ts_idx ON open_interest(ts DESC);

CREATE TABLE IF NOT EXISTS oi_bybit (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    oi_open double precision NOT NULL CHECK (finite_float8(oi_open) AND oi_open >= 0),
    oi_high double precision NOT NULL CHECK (finite_float8(oi_high) AND oi_high >= 0),
    oi_low double precision NOT NULL CHECK (finite_float8(oi_low) AND oi_low >= 0),
    oi_close double precision NOT NULL CHECK (finite_float8(oi_close) AND oi_close >= 0),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (oi_high >= GREATEST(oi_open, oi_close, oi_low)),
    CHECK (oi_low <= LEAST(oi_open, oi_close, oi_high))
);
CREATE INDEX IF NOT EXISTS oi_bybit_ts_idx ON oi_bybit(ts DESC);

CREATE TABLE IF NOT EXISTS funding_rate (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    fr_open double precision NOT NULL CHECK (finite_float8(fr_open)),
    fr_high double precision NOT NULL CHECK (finite_float8(fr_high)),
    fr_low double precision NOT NULL CHECK (finite_float8(fr_low)),
    fr_close double precision NOT NULL CHECK (finite_float8(fr_close)),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (fr_high >= GREATEST(fr_open, fr_close, fr_low)),
    CHECK (fr_low <= LEAST(fr_open, fr_close, fr_high))
);
CREATE INDEX IF NOT EXISTS funding_rate_ts_idx ON funding_rate(ts DESC);

CREATE TABLE IF NOT EXISTS predicted_funding_rate (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    pfr_open double precision NOT NULL CHECK (finite_float8(pfr_open)),
    pfr_high double precision NOT NULL CHECK (finite_float8(pfr_high)),
    pfr_low double precision NOT NULL CHECK (finite_float8(pfr_low)),
    pfr_close double precision NOT NULL CHECK (finite_float8(pfr_close)),
    PRIMARY KEY (symbol, interval, ts),
    CHECK (pfr_high >= GREATEST(pfr_open, pfr_close, pfr_low)),
    CHECK (pfr_low <= LEAST(pfr_open, pfr_close, pfr_high))
);
CREATE INDEX IF NOT EXISTS predicted_funding_rate_ts_idx ON predicted_funding_rate(ts DESC);

CREATE TABLE IF NOT EXISTS liquidations (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    long_liq double precision NOT NULL CHECK (finite_float8(long_liq) AND long_liq >= 0),
    short_liq double precision NOT NULL CHECK (finite_float8(short_liq) AND short_liq >= 0),
    PRIMARY KEY (symbol, interval, ts)
);
CREATE INDEX IF NOT EXISTS liquidations_ts_idx ON liquidations(ts DESC);

-- v1.4.9 (P2): posicionamiento. `/long-short-ratio-history` responde a 5min y no se estaba
-- ingiriendo; es informacion que NO se deduce de OI, funding ni CVD (esos dicen cuanto y a
-- que precio, no como esta repartida la multitud). l+s = 100 y r = l/s.
CREATE TABLE IF NOT EXISTS long_short_ratio (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    interval text NOT NULL CHECK (interval = '5min'),
    long_pct double precision NOT NULL CHECK (finite_float8(long_pct) AND long_pct BETWEEN 0 AND 100),
    short_pct double precision NOT NULL CHECK (finite_float8(short_pct) AND short_pct BETWEEN 0 AND 100),
    ratio double precision NOT NULL CHECK (finite_float8(ratio) AND ratio >= 0),
    PRIMARY KEY (symbol, interval, ts)
);
CREATE INDEX IF NOT EXISTS long_short_ratio_ts_idx ON long_short_ratio(symbol, ts DESC);

CREATE TABLE IF NOT EXISTS spot_trades_agg (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES market_assets(base_asset),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit','combined')),
    interval text NOT NULL CHECK (interval = '1min'),
    buy_vol_usd double precision NOT NULL CHECK (finite_float8(buy_vol_usd) AND buy_vol_usd >= 0),
    sell_vol_usd double precision NOT NULL CHECK (finite_float8(sell_vol_usd) AND sell_vol_usd >= 0),
    inst_buy_usd double precision NOT NULL CHECK (finite_float8(inst_buy_usd) AND inst_buy_usd >= 0),
    inst_sell_usd double precision NOT NULL CHECK (finite_float8(inst_sell_usd) AND inst_sell_usd >= 0),
    mid_buy_usd double precision NOT NULL CHECK (finite_float8(mid_buy_usd) AND mid_buy_usd >= 0),
    mid_sell_usd double precision NOT NULL CHECK (finite_float8(mid_sell_usd) AND mid_sell_usd >= 0),
    retail_buy_usd double precision NOT NULL CHECK (finite_float8(retail_buy_usd) AND retail_buy_usd >= 0),
    retail_sell_usd double precision NOT NULL CHECK (finite_float8(retail_sell_usd) AND retail_sell_usd >= 0),
    trade_count integer NOT NULL CHECK (trade_count >= 0),
    PRIMARY KEY (symbol, exchange, interval, ts),
    CHECK (inst_buy_usd + mid_buy_usd + retail_buy_usd <= buy_vol_usd + 0.01),
    CHECK (inst_sell_usd + mid_sell_usd + retail_sell_usd <= sell_vol_usd + 0.01)
);
ALTER TABLE spot_trades_agg DROP CONSTRAINT IF EXISTS spot_trades_agg_symbol_check;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'spot_trades_agg_symbol_fkey'
    ) THEN
        ALTER TABLE spot_trades_agg ADD CONSTRAINT spot_trades_agg_symbol_fkey
            FOREIGN KEY (symbol) REFERENCES market_assets(base_asset);
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS spot_trades_agg_ts_idx ON spot_trades_agg(ts DESC);

CREATE TABLE IF NOT EXISTS spot_trades_realtime (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES market_assets(base_asset),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit','combined')),
    buy_vol_usd double precision NOT NULL CHECK (finite_float8(buy_vol_usd) AND buy_vol_usd >= 0),
    sell_vol_usd double precision NOT NULL CHECK (finite_float8(sell_vol_usd) AND sell_vol_usd >= 0),
    inst_buy_usd double precision NOT NULL CHECK (finite_float8(inst_buy_usd) AND inst_buy_usd >= 0),
    inst_sell_usd double precision NOT NULL CHECK (finite_float8(inst_sell_usd) AND inst_sell_usd >= 0),
    trade_count integer NOT NULL CHECK (trade_count >= 0),
    last_px double precision NOT NULL CHECK (finite_float8(last_px) AND last_px > 0),
    last_event_ms bigint NOT NULL DEFAULT 0 CHECK (last_event_ms >= 0),
    PRIMARY KEY (symbol, exchange, ts)
) PARTITION BY RANGE (ts);
ALTER TABLE spot_trades_realtime DROP CONSTRAINT IF EXISTS spot_trades_realtime_symbol_check;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'spot_trades_realtime_symbol_fkey'
    ) THEN
        ALTER TABLE spot_trades_realtime ADD CONSTRAINT spot_trades_realtime_symbol_fkey
            FOREIGN KEY (symbol) REFERENCES market_assets(base_asset);
    END IF;
END $$;
ALTER TABLE spot_trades_realtime ADD COLUMN IF NOT EXISTS last_event_ms bigint NOT NULL DEFAULT 0 CHECK (last_event_ms >= 0);
CREATE INDEX IF NOT EXISTS spot_trades_realtime_ts_idx ON spot_trades_realtime(ts DESC);
CREATE INDEX IF NOT EXISTS spot_trades_realtime_symbol_exchange_ts_idx ON spot_trades_realtime(symbol, exchange, ts DESC);


CREATE TABLE IF NOT EXISTS futures_trades_realtime (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit','combined')),
    buy_vol_usd double precision NOT NULL CHECK (finite_float8(buy_vol_usd) AND buy_vol_usd >= 0),
    sell_vol_usd double precision NOT NULL CHECK (finite_float8(sell_vol_usd) AND sell_vol_usd >= 0),
    large_buy_usd double precision NOT NULL CHECK (finite_float8(large_buy_usd) AND large_buy_usd >= 0),
    large_sell_usd double precision NOT NULL CHECK (finite_float8(large_sell_usd) AND large_sell_usd >= 0),
    trade_count integer NOT NULL CHECK (trade_count >= 0),
    last_px double precision NOT NULL CHECK (finite_float8(last_px) AND last_px > 0),
    last_event_ms bigint NOT NULL DEFAULT 0 CHECK (last_event_ms >= 0),
    PRIMARY KEY (symbol, exchange, ts)
) PARTITION BY RANGE (ts);
ALTER TABLE futures_trades_realtime ADD COLUMN IF NOT EXISTS last_event_ms bigint NOT NULL DEFAULT 0 CHECK (last_event_ms >= 0);
CREATE INDEX IF NOT EXISTS futures_trades_realtime_ts_idx ON futures_trades_realtime(ts DESC);
CREATE INDEX IF NOT EXISTS futures_trades_realtime_symbol_exchange_ts_idx ON futures_trades_realtime(symbol, exchange, ts DESC);

CREATE TABLE IF NOT EXISTS futures_trades_agg (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit','combined')),
    interval text NOT NULL CHECK (interval = '1min'),
    buy_vol_usd double precision NOT NULL CHECK (finite_float8(buy_vol_usd) AND buy_vol_usd >= 0),
    sell_vol_usd double precision NOT NULL CHECK (finite_float8(sell_vol_usd) AND sell_vol_usd >= 0),
    large_buy_usd double precision NOT NULL CHECK (finite_float8(large_buy_usd) AND large_buy_usd >= 0),
    large_sell_usd double precision NOT NULL CHECK (finite_float8(large_sell_usd) AND large_sell_usd >= 0),
    trade_count integer NOT NULL CHECK (trade_count >= 0),
    PRIMARY KEY (symbol, exchange, interval, ts)
);
CREATE INDEX IF NOT EXISTS futures_trades_agg_ts_idx ON futures_trades_agg(ts DESC);

CREATE TABLE IF NOT EXISTS orderbook_snapshot (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit','combined')),
    bid_px double precision CHECK (bid_px IS NULL OR (finite_float8(bid_px) AND bid_px > 0)),
    ask_px double precision CHECK (ask_px IS NULL OR (finite_float8(ask_px) AND ask_px > 0)),
    mid_px double precision CHECK (mid_px IS NULL OR (finite_float8(mid_px) AND mid_px > 0)),
    spread_bps double precision CHECK (spread_bps IS NULL OR finite_float8(spread_bps)),
    bid_notional_l1 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(bid_notional_l1) AND bid_notional_l1 >= 0),
    ask_notional_l1 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(ask_notional_l1) AND ask_notional_l1 >= 0),
    bid_notional_l5 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(bid_notional_l5) AND bid_notional_l5 >= 0),
    ask_notional_l5 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(ask_notional_l5) AND ask_notional_l5 >= 0),
    bid_notional_l10 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(bid_notional_l10) AND bid_notional_l10 >= 0),
    ask_notional_l10 double precision NOT NULL DEFAULT 0 CHECK (finite_float8(ask_notional_l10) AND ask_notional_l10 >= 0),
    imbalance_l1 double precision CHECK (imbalance_l1 IS NULL OR (finite_float8(imbalance_l1) AND imbalance_l1 BETWEEN 0 AND 1)),
    imbalance_l5 double precision CHECK (imbalance_l5 IS NULL OR (finite_float8(imbalance_l5) AND imbalance_l5 BETWEEN 0 AND 1)),
    imbalance_l10 double precision CHECK (imbalance_l10 IS NULL OR (finite_float8(imbalance_l10) AND imbalance_l10 BETWEEN 0 AND 1)),
    wall_up_pct double precision CHECK (wall_up_pct IS NULL OR finite_float8(wall_up_pct)),
    wall_down_pct double precision CHECK (wall_down_pct IS NULL OR finite_float8(wall_down_pct)),
    PRIMARY KEY (symbol, exchange, ts)
) PARTITION BY RANGE (ts);
CREATE INDEX IF NOT EXISTS orderbook_snapshot_ts_idx ON orderbook_snapshot(ts DESC);
CREATE INDEX IF NOT EXISTS orderbook_snapshot_symbol_exchange_ts_idx ON orderbook_snapshot(symbol, exchange, ts DESC);

-- New rows must not persist crossed best bid/ask. Existing rows from older
-- versions are intentionally not validated during upgrade.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'orderbook_snapshot_non_crossed_check'
    ) THEN
        ALTER TABLE orderbook_snapshot
            ADD CONSTRAINT orderbook_snapshot_non_crossed_check
            CHECK (bid_px IS NULL OR ask_px IS NULL OR ask_px >= bid_px) NOT VALID;
    END IF;
END $$;

-- v1.4.8: escalera completa del libro, SOLO estado actual (una fila por symbol+exchange,
-- sobrescrita en cada flush). Bybit entrega 50 niveles (`orderbook.50`) que hasta ahora se
-- truncaban a 10 al persistir, asi que no habia forma de estimar el coste de ejecutar un
-- tamanio concreto. Se guarda la escalera cruda y no un slippage precalculado para que el
-- tamanio sea un parametro de consulta. Sin 'combined': una orden se ejecuta en UN venue.
CREATE TABLE IF NOT EXISTS orderbook_depth (
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    ts timestamptz NOT NULL,
    bids jsonb NOT NULL,
    asks jsonb NOT NULL,
    levels integer NOT NULL CHECK (levels >= 0),
    PRIMARY KEY (symbol, exchange)
);

CREATE TABLE IF NOT EXISTS liquidations_realtime (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    side text NOT NULL CHECK (side IN ('long','short')),
    notional_usd double precision NOT NULL CHECK (finite_float8(notional_usd) AND notional_usd >= 0),
    price double precision NOT NULL CHECK (finite_float8(price) AND price > 0),
    qty double precision NOT NULL CHECK (finite_float8(qty) AND qty >= 0),
    event_id text NOT NULL,
    -- PostgreSQL requires every partitioned unique key to include ts. Cross-partition
    -- event identity remains unique through liquidations_realtime_event_unique_trigger.
    PRIMARY KEY (exchange, event_id, ts)
) PARTITION BY RANGE (ts);
CREATE INDEX IF NOT EXISTS liquidations_realtime_symbol_ts_idx ON liquidations_realtime(symbol, ts DESC);

CREATE OR REPLACE FUNCTION enforce_liquidation_event_unique()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Serialize equal source identities before searching all daily partitions. Returning
    -- NULL preserves the collector's historical duplicate-is-a-no-op behavior.
    PERFORM pg_advisory_xact_lock(
        hashtextextended('liquidation-event:' || NEW.exchange || ':' || NEW.event_id, 0)
    );
    IF EXISTS (
        SELECT 1
        FROM liquidations_realtime
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

CREATE TABLE IF NOT EXISTS scalp_signal_snapshot (
    ts timestamptz NOT NULL DEFAULT now(),
    symbol text NOT NULL REFERENCES symbols(symbol),
    long_score double precision NOT NULL CHECK (finite_float8(long_score) AND long_score BETWEEN 0 AND 100),
    short_score double precision NOT NULL CHECK (finite_float8(short_score) AND short_score BETWEEN 0 AND 100),
    state text NOT NULL CHECK (length(state) BETWEEN 1 AND 80),
    confidence text NOT NULL CHECK (confidence IN ('baja','media','alta')),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    fut_delta_1m double precision CHECK (fut_delta_1m IS NULL OR finite_float8(fut_delta_1m)),
    fut_delta_3m double precision CHECK (fut_delta_3m IS NULL OR finite_float8(fut_delta_3m)),
    spot_delta_3m double precision CHECK (spot_delta_3m IS NULL OR finite_float8(spot_delta_3m)),
    diff_3m double precision CHECK (diff_3m IS NULL OR finite_float8(diff_3m)),
    spot_fut_divergence_norm double precision CHECK (spot_fut_divergence_norm IS NULL OR (finite_float8(spot_fut_divergence_norm) AND spot_fut_divergence_norm BETWEEN -1 AND 1)),
    book_status text CHECK (book_status IS NULL OR book_status IN ('ok','stale','missing')),
    book_lag_seconds double precision CHECK (book_lag_seconds IS NULL OR (finite_float8(book_lag_seconds) AND book_lag_seconds >= 0)),
    basis_bps double precision CHECK (basis_bps IS NULL OR finite_float8(basis_bps)),
    absorption text CHECK (absorption IS NULL OR length(absorption) BETWEEN 1 AND 80),
    PRIMARY KEY (symbol, ts)
) PARTITION BY RANGE (ts);
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS fut_delta_1m double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS fut_delta_3m double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS spot_delta_3m double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS diff_3m double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS spot_fut_divergence_norm double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS book_status text;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS book_lag_seconds double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS basis_bps double precision;
ALTER TABLE scalp_signal_snapshot ADD COLUMN IF NOT EXISTS absorption text;
CREATE INDEX IF NOT EXISTS scalp_signal_snapshot_latest_idx ON scalp_signal_snapshot(symbol, ts DESC);
CREATE INDEX IF NOT EXISTS scalp_signal_snapshot_state_idx ON scalp_signal_snapshot(symbol, state, ts DESC);

-- PR4_SIGNAL_OBSERVATION_LEDGER_BEGIN
-- Investigación forward-only: congela lo que el sistema sabía EN VIVO. Nunca se
-- reconstruye después con datos recuperados o lógica nueva.
CREATE TABLE IF NOT EXISTS signal_observation (
    observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observed_at timestamptz NOT NULL,
    observed_minute timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    signal_family text NOT NULL CHECK (signal_family = 'scalp'),
    is_periodic boolean NOT NULL,
    is_transition boolean NOT NULL,
    logic_version text NOT NULL CHECK (length(logic_version) BETWEEN 1 AND 80),
    evidence_version smallint NOT NULL CHECK (evidence_version >= 1),
    sampling_version smallint NOT NULL CHECK (sampling_version >= 1),
    decision_status text NOT NULL
        CHECK (decision_status IN ('evaluable','not_evaluable')),
    direction text NOT NULL
        CHECK (direction IN ('long','short','neutral','unavailable')),
    actionable boolean NOT NULL,
    state text NOT NULL CHECK (length(state) BETWEEN 1 AND 80),
    confidence text NOT NULL CHECK (confidence IN ('baja','media','alta')),
    reason text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    reference_price double precision
        CHECK (reference_price IS NULL OR
               (finite_float8(reference_price) AND reference_price > 0)),
    reference_price_source text
        CHECK (reference_price_source IS NULL OR
               length(reference_price_source) BETWEEN 1 AND 80),
    reference_price_at timestamptz,
    long_score double precision NOT NULL
        CHECK (finite_float8(long_score) AND long_score BETWEEN 0 AND 100),
    short_score double precision NOT NULL
        CHECK (finite_float8(short_score) AND short_score BETWEEN 0 AND 100),
    evidence_coverage_pct double precision NOT NULL
        CHECK (finite_float8(evidence_coverage_pct) AND
               evidence_coverage_pct BETWEEN 0 AND 100),
    metrics_snapshot_ts timestamptz,
    regime_score double precision
        CHECK (regime_score IS NULL OR
               (finite_float8(regime_score) AND regime_score BETWEEN -100 AND 100)),
    regime_label text
        CHECK (regime_label IS NULL OR length(regime_label) BETWEEN 1 AND 100),
    regime_logic_version smallint
        CONSTRAINT signal_observation_regime_logic_version_check
        CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1),
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    collector_generation bigint
        CHECK (collector_generation IS NULL OR collector_generation > 0),
    collector_shard_index integer NOT NULL CHECK (collector_shard_index >= 0),
    collector_shard_count integer NOT NULL CHECK (collector_shard_count > 0),
    decision_fingerprint text NOT NULL CHECK (length(decision_fingerprint) = 64),
    evidence jsonb NOT NULL CHECK (jsonb_typeof(evidence) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (is_periodic OR is_transition),
    CHECK (collector_shard_index < collector_shard_count),
    CHECK (
        (decision_status='not_evaluable' AND
         direction='unavailable' AND NOT actionable)
        OR
        (
            decision_status='evaluable'
            AND (
                (direction IN ('long','short') AND actionable)
                OR (direction='neutral' AND NOT actionable)
            )
        )
    ),
    CONSTRAINT signal_observation_pr23_regime_provenance_check CHECK (
        evidence_version NOT IN (3,4)
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
            regime_logic_version IS NULL
            AND regime_score IS NULL
            AND regime_label IS NULL
            AND metrics_snapshot_ts IS NULL
            AND price_cutoff_at IS NULL
            AND metrics_cutoff_at IS NULL
        )
    )
);
ALTER TABLE signal_observation
    ADD COLUMN IF NOT EXISTS regime_logic_version smallint;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_observation'::regclass
      AND conname='signal_observation_regime_logic_version_check'
  ) THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
  ALTER TABLE signal_observation
    DROP CONSTRAINT IF EXISTS signal_observation_pr22_regime_provenance_check;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='signal_observation'::regclass
      AND conname='signal_observation_pr23_regime_provenance_check'
  ) THEN
    ALTER TABLE signal_observation
      ADD CONSTRAINT signal_observation_pr23_regime_provenance_check
      CHECK (
        evidence_version NOT IN (3,4)
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
          regime_logic_version IS NULL
          AND regime_score IS NULL
          AND regime_label IS NULL
          AND metrics_snapshot_ts IS NULL
          AND price_cutoff_at IS NULL
          AND metrics_cutoff_at IS NULL
        )
      );
  END IF;
END $$;
CREATE UNIQUE INDEX IF NOT EXISTS signal_observation_periodic_slot_uidx
    ON signal_observation(symbol, signal_family, observed_minute)
    WHERE is_periodic;
CREATE INDEX IF NOT EXISTS signal_observation_symbol_ts_idx
    ON signal_observation(symbol, observed_at DESC);
CREATE INDEX IF NOT EXISTS signal_observation_state_ts_idx
    ON signal_observation(signal_family, state, observed_at DESC);
CREATE INDEX IF NOT EXISTS signal_observation_actionable_idx
    ON signal_observation(symbol, direction, observed_at DESC)
    WHERE actionable;
CREATE INDEX IF NOT EXISTS signal_observation_ts_brin_idx
    ON signal_observation USING brin(observed_at);

CREATE OR REPLACE FUNCTION reject_signal_observation_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'signal_observation is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;
DROP TRIGGER IF EXISTS signal_observation_no_update_delete ON signal_observation;
CREATE TRIGGER signal_observation_no_update_delete
BEFORE UPDATE OR DELETE ON signal_observation
FOR EACH ROW EXECUTE FUNCTION reject_signal_observation_mutation();
DROP TRIGGER IF EXISTS signal_observation_no_truncate ON signal_observation;
CREATE TRIGGER signal_observation_no_truncate
BEFORE TRUNCATE ON signal_observation
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_observation_mutation();
-- PR4_SIGNAL_OBSERVATION_LEDGER_END

-- PR5_SIGNAL_OUTCOMES_BEGIN
-- Derived forward outcomes. Each path starts at the first full 1-minute candle
-- strictly after observed_at, so MFE/MAE never use pre-signal price action.
CREATE TABLE IF NOT EXISTS signal_outcome (
    outcome_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint NOT NULL
        REFERENCES signal_observation(observation_id) ON DELETE RESTRICT,
    horizon_minutes integer NOT NULL
        CHECK (horizon_minutes IN (1,3,5,15,30,60,120,240)),
    window_start timestamptz NOT NULL,
    window_end timestamptz NOT NULL,
    due_at timestamptz NOT NULL,
    next_attempt_at timestamptz NOT NULL,
    path_start_delay_seconds double precision NOT NULL
        CHECK (finite_float8(path_start_delay_seconds)
               AND path_start_delay_seconds >= 0
               AND path_start_delay_seconds <= 60),
    bars_expected integer NOT NULL CHECK (bars_expected = horizon_minutes),
    bars_found integer NOT NULL DEFAULT 0
        CHECK (bars_found >= 0 AND bars_found <= bars_expected),
    outcome_version smallint NOT NULL DEFAULT 1 CHECK (outcome_version >= 1),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','evaluated','not_evaluable')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_attempt_at timestamptz,
    finalized_at timestamptz,
    final_reason text CHECK (
        final_reason IS NULL OR length(final_reason) BETWEEN 1 AND 120
    ),
    entry_reference_price double precision CHECK (
        entry_reference_price IS NULL
        OR (finite_float8(entry_reference_price) AND entry_reference_price > 0)
    ),
    end_price double precision CHECK (
        end_price IS NULL OR (finite_float8(end_price) AND end_price > 0)
    ),
    max_high double precision CHECK (
        max_high IS NULL OR (finite_float8(max_high) AND max_high > 0)
    ),
    min_low double precision CHECK (
        min_low IS NULL OR (finite_float8(min_low) AND min_low > 0)
    ),
    market_return_pct double precision CHECK (
        market_return_pct IS NULL OR finite_float8(market_return_pct)
    ),
    up_excursion_pct double precision CHECK (
        up_excursion_pct IS NULL OR finite_float8(up_excursion_pct)
    ),
    down_excursion_pct double precision CHECK (
        down_excursion_pct IS NULL OR finite_float8(down_excursion_pct)
    ),
    directional_return_pct double precision CHECK (
        directional_return_pct IS NULL OR finite_float8(directional_return_pct)
    ),
    mfe_pct double precision CHECK (
        mfe_pct IS NULL OR (finite_float8(mfe_pct) AND mfe_pct >= 0)
    ),
    mae_pct double precision CHECK (
        mae_pct IS NULL OR (finite_float8(mae_pct) AND mae_pct >= 0)
    ),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(observation_id,horizon_minutes),
    CHECK (window_start < window_end),
    CHECK (window_end = window_start + make_interval(mins => horizon_minutes)),
    CHECK (due_at > window_end),
    CHECK (
        (status='pending'
         AND finalized_at IS NULL
         AND final_reason IS NULL
         AND entry_reference_price IS NULL
         AND end_price IS NULL
         AND max_high IS NULL
         AND min_low IS NULL
         AND market_return_pct IS NULL
         AND up_excursion_pct IS NULL
         AND down_excursion_pct IS NULL
         AND directional_return_pct IS NULL
         AND mfe_pct IS NULL
         AND mae_pct IS NULL)
        OR
        (status='evaluated'
         AND finalized_at IS NOT NULL
         AND final_reason IS NULL
         AND bars_found = bars_expected
         AND entry_reference_price IS NOT NULL
         AND end_price IS NOT NULL
         AND max_high IS NOT NULL
         AND min_low IS NOT NULL
         AND market_return_pct IS NOT NULL
         AND up_excursion_pct IS NOT NULL
         AND down_excursion_pct IS NOT NULL)
        OR
        (status='not_evaluable'
         AND finalized_at IS NOT NULL
         AND final_reason IS NOT NULL
         AND entry_reference_price IS NULL
         AND end_price IS NULL
         AND max_high IS NULL
         AND min_low IS NULL
         AND market_return_pct IS NULL
         AND up_excursion_pct IS NULL
         AND down_excursion_pct IS NULL
         AND directional_return_pct IS NULL
         AND mfe_pct IS NULL
         AND mae_pct IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS signal_outcome_due_idx
    ON signal_outcome(next_attempt_at,due_at,outcome_id)
    WHERE status='pending';
CREATE INDEX IF NOT EXISTS signal_outcome_observation_idx
    ON signal_outcome(observation_id,horizon_minutes);
CREATE INDEX IF NOT EXISTS signal_outcome_status_finalized_idx
    ON signal_outcome(status,finalized_at DESC);
CREATE INDEX IF NOT EXISTS signal_outcome_horizon_status_idx
    ON signal_outcome(horizon_minutes,status,finalized_at DESC);

CREATE OR REPLACE FUNCTION guard_signal_outcome_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP IN ('DELETE','TRUNCATE') THEN
        RAISE EXCEPTION 'signal_outcome is durable; % is not allowed', TG_OP
            USING ERRCODE = '55000';
    END IF;

    IF OLD.status <> 'pending' THEN
        RAISE EXCEPTION 'final signal_outcome rows are immutable'
            USING ERRCODE = '55000';
    END IF;

    IF NEW.observation_id IS DISTINCT FROM OLD.observation_id
       OR NEW.horizon_minutes IS DISTINCT FROM OLD.horizon_minutes
       OR NEW.window_start IS DISTINCT FROM OLD.window_start
       OR NEW.window_end IS DISTINCT FROM OLD.window_end
       OR NEW.due_at IS DISTINCT FROM OLD.due_at
       OR NEW.path_start_delay_seconds IS DISTINCT FROM OLD.path_start_delay_seconds
       OR NEW.bars_expected IS DISTINCT FROM OLD.bars_expected
       OR NEW.outcome_version IS DISTINCT FROM OLD.outcome_version
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'signal_outcome scheduling identity is immutable'
            USING ERRCODE = '55000';
    END IF;

    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS signal_outcome_guard_update_delete ON signal_outcome;
CREATE TRIGGER signal_outcome_guard_update_delete
BEFORE UPDATE OR DELETE ON signal_outcome
FOR EACH ROW EXECUTE FUNCTION guard_signal_outcome_mutation();

DROP TRIGGER IF EXISTS signal_outcome_no_truncate ON signal_outcome;
CREATE TRIGGER signal_outcome_no_truncate
BEFORE TRUNCATE ON signal_outcome
FOR EACH STATEMENT EXECUTE FUNCTION guard_signal_outcome_mutation();

INSERT INTO signal_outcome(
  observation_id,horizon_minutes,window_start,window_end,due_at,next_attempt_at,
  path_start_delay_seconds,bars_expected,outcome_version
)
SELECT
  obs.observation_id,
  horizon.minutes,
  date_trunc('minute',obs.observed_at) + interval '1 minute',
  date_trunc('minute',obs.observed_at) + interval '1 minute'
      + make_interval(mins => horizon.minutes),
  date_trunc('minute',obs.observed_at) + interval '43 minutes'
      + make_interval(mins => horizon.minutes),
  date_trunc('minute',obs.observed_at) + interval '43 minutes'
      + make_interval(mins => horizon.minutes),
  EXTRACT(EPOCH FROM (
      date_trunc('minute',obs.observed_at) + interval '1 minute' - obs.observed_at
  )),
  horizon.minutes,
  1
FROM signal_observation AS obs
CROSS JOIN (VALUES (1),(3),(5),(15),(30),(60),(120),(240))
    AS horizon(minutes)
WHERE obs.is_periodic OR (obs.is_transition AND obs.actionable)
ON CONFLICT(observation_id,horizon_minutes) DO NOTHING;
-- PR5_SIGNAL_OUTCOMES_END

-- PR6_SIGNAL_REPLAY_BEGIN
-- Decision-time inputs for deterministic signal replay. This is deliberately
-- forward-only: historical context is never reconstructed after the fact from
-- corrected/recovered market data or current-state health tables.
CREATE TABLE IF NOT EXISTS signal_replay_frame (
    frame_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint NOT NULL UNIQUE
        REFERENCES signal_observation(observation_id) ON DELETE RESTRICT,
    context_version smallint NOT NULL CHECK (context_version >= 1),
    context_as_of timestamptz NOT NULL,
    context_hash text NOT NULL
        CHECK (context_hash ~ '^[0-9a-f]{64}$'),
    context jsonb NOT NULL CHECK (jsonb_typeof(context) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS signal_replay_frame_asof_idx
    ON signal_replay_frame(context_as_of DESC);
CREATE INDEX IF NOT EXISTS signal_replay_frame_asof_brin_idx
    ON signal_replay_frame USING brin(context_as_of);

CREATE OR REPLACE FUNCTION reject_signal_replay_frame_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'signal_replay_frame is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS signal_replay_frame_no_update_delete ON signal_replay_frame;
CREATE TRIGGER signal_replay_frame_no_update_delete
BEFORE UPDATE OR DELETE ON signal_replay_frame
FOR EACH ROW EXECUTE FUNCTION reject_signal_replay_frame_mutation();

DROP TRIGGER IF EXISTS signal_replay_frame_no_truncate ON signal_replay_frame;
CREATE TRIGGER signal_replay_frame_no_truncate
BEFORE TRUNCATE ON signal_replay_frame
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_replay_frame_mutation();

-- No INSERT ... SELECT backfill belongs here. A replay frame is truthful only
-- when the exact live scalp_context was captured at decision time.
-- PR6_SIGNAL_REPLAY_END

-- PR10_SIGNAL_EXECUTION_BEGIN
CREATE TABLE IF NOT EXISTS signal_execution_snapshot (
    execution_snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint NOT NULL
        REFERENCES signal_observation(observation_id) ON DELETE RESTRICT,
    snapshot_version smallint NOT NULL CHECK (snapshot_version >= 1),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    captured_at timestamptz NOT NULL,
    book_ts timestamptz,
    book_age_seconds double precision CHECK (
        book_age_seconds IS NULL OR finite_float8(book_age_seconds)
    ),
    status text NOT NULL
        CHECK (status IN ('valid','stale','unavailable','error')),
    reason text CHECK (
        reason IS NULL OR length(reason) BETWEEN 1 AND 120
    ),
    levels_reported integer NOT NULL DEFAULT 0 CHECK (levels_reported >= 0),
    bid_levels_valid integer NOT NULL DEFAULT 0 CHECK (bid_levels_valid >= 0),
    ask_levels_valid integer NOT NULL DEFAULT 0 CHECK (ask_levels_valid >= 0),
    best_bid_px double precision CHECK (
        best_bid_px IS NULL OR (finite_float8(best_bid_px) AND best_bid_px > 0)
    ),
    best_ask_px double precision CHECK (
        best_ask_px IS NULL OR (finite_float8(best_ask_px) AND best_ask_px > 0)
    ),
    mid_px double precision CHECK (
        mid_px IS NULL OR (finite_float8(mid_px) AND mid_px > 0)
    ),
    spread_bps double precision CHECK (
        spread_bps IS NULL OR (finite_float8(spread_bps) AND spread_bps >= 0)
    ),
    bid_depth_usd double precision CHECK (
        bid_depth_usd IS NULL OR
        (finite_float8(bid_depth_usd) AND bid_depth_usd >= 0)
    ),
    ask_depth_usd double precision CHECK (
        ask_depth_usd IS NULL OR
        (finite_float8(ask_depth_usd) AND ask_depth_usd >= 0)
    ),
    source_book_hash text CHECK (
        source_book_hash IS NULL OR source_book_hash ~ '^[0-9a-f]{64}$'
    ),
    cost_curve jsonb NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(cost_curve) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(observation_id,exchange),
    CHECK (
        status <> 'valid'
        OR (
            book_ts IS NOT NULL
            AND source_book_hash IS NOT NULL
            AND best_bid_px IS NOT NULL
            AND best_ask_px IS NOT NULL
            AND mid_px IS NOT NULL
            AND spread_bps IS NOT NULL
            AND best_ask_px >= best_bid_px
            AND cost_curve <> '{}'::jsonb
        )
    ),
    CHECK (
        status = 'valid' OR cost_curve = '{}'::jsonb
    )
);

CREATE INDEX IF NOT EXISTS signal_execution_snapshot_observation_idx
    ON signal_execution_snapshot(observation_id,exchange);
CREATE INDEX IF NOT EXISTS signal_execution_snapshot_book_ts_idx
    ON signal_execution_snapshot(book_ts DESC);
CREATE INDEX IF NOT EXISTS signal_execution_snapshot_book_ts_brin_idx
    ON signal_execution_snapshot USING brin(book_ts);

CREATE OR REPLACE FUNCTION reject_signal_execution_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'signal_execution_snapshot is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS signal_execution_snapshot_no_update_delete
    ON signal_execution_snapshot;
CREATE TRIGGER signal_execution_snapshot_no_update_delete
BEFORE UPDATE OR DELETE ON signal_execution_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_signal_execution_snapshot_mutation();

DROP TRIGGER IF EXISTS signal_execution_snapshot_no_truncate
    ON signal_execution_snapshot;
CREATE TRIGGER signal_execution_snapshot_no_truncate
BEFORE TRUNCATE ON signal_execution_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_execution_snapshot_mutation();

-- No historical backfill: orderbook_depth is overwritten current state.
-- PR10_SIGNAL_EXECUTION_END

-- PR11_SIGNAL_WALK_FORWARD_BEGIN
-- Walk-forward / out-of-sample evaluation engine. This table records only
-- the prospective, immutable research manifest that freezes a walk-forward
-- program before its first OOS cutoff. Deploying this schema block must
-- never itself create a manifest row and must never backfill one.
CREATE TABLE IF NOT EXISTS signal_walk_forward_manifest (
    manifest_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    manifest_version smallint NOT NULL CHECK (manifest_version >= 1),
    manifest_name text NOT NULL UNIQUE
        CHECK (manifest_name ~ '^[a-z][a-z0-9_-]{0,63}$'),
    created_at timestamptz NOT NULL,
    cutoff_at timestamptz NOT NULL,
    warmup_days integer NOT NULL CHECK (warmup_days >= 1),
    test_days integer NOT NULL CHECK (test_days >= 1),
    fold_count integer NOT NULL CHECK (fold_count >= 1),
    min_group_n integer NOT NULL CHECK (min_group_n >= 1),
    selection_policy text NOT NULL
        CHECK (selection_policy = 'fixed_kernel_no_selection_v1'),
    manifest_hash text NOT NULL UNIQUE
        CHECK (manifest_hash ~ '^[0-9a-f]{64}$'),
    spec jsonb NOT NULL CHECK (jsonb_typeof(spec) = 'object'),
    CHECK (created_at < cutoff_at)
);

CREATE INDEX IF NOT EXISTS signal_walk_forward_manifest_cutoff_idx
    ON signal_walk_forward_manifest(cutoff_at);

CREATE OR REPLACE FUNCTION reject_signal_walk_forward_manifest_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'signal_walk_forward_manifest is append-only; % is not allowed', TG_OP
        USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS signal_walk_forward_manifest_no_update_delete
    ON signal_walk_forward_manifest;
CREATE TRIGGER signal_walk_forward_manifest_no_update_delete
BEFORE UPDATE OR DELETE ON signal_walk_forward_manifest
FOR EACH ROW EXECUTE FUNCTION reject_signal_walk_forward_manifest_mutation();

DROP TRIGGER IF EXISTS signal_walk_forward_manifest_no_truncate
    ON signal_walk_forward_manifest;
CREATE TRIGGER signal_walk_forward_manifest_no_truncate
BEFORE TRUNCATE ON signal_walk_forward_manifest
FOR EACH STATEMENT EXECUTE FUNCTION reject_signal_walk_forward_manifest_mutation();

-- No INSERT ... SELECT here: freezing a manifest is an explicit application
-- action (scripts/freeze_walk_forward_manifest.py), never a schema-deploy
-- side effect, and there is no backfill of a retroactive cutoff.
-- PR11_SIGNAL_WALK_FORWARD_END

CREATE TABLE IF NOT EXISTS metrics_snapshot (
    ts timestamptz NOT NULL DEFAULT now(),
    symbol text NOT NULL REFERENCES symbols(symbol),
    price double precision CHECK (price IS NULL OR (finite_float8(price) AND price > 0)),
    oi double precision CHECK (oi IS NULL OR (finite_float8(oi) AND oi >= 0)),
    oi_chg_24h_pct double precision CHECK (oi_chg_24h_pct IS NULL OR finite_float8(oi_chg_24h_pct)),
    oi_vol_24h_ratio double precision CHECK (oi_vol_24h_ratio IS NULL OR (finite_float8(oi_vol_24h_ratio) AND oi_vol_24h_ratio >= 0)),
    vol_24h double precision CHECK (vol_24h IS NULL OR (finite_float8(vol_24h) AND vol_24h >= 0)),
    spot_vol_24h double precision
        CONSTRAINT metrics_snapshot_spot_vol_24h_check
        CHECK (spot_vol_24h IS NULL OR (finite_float8(spot_vol_24h) AND spot_vol_24h >= 0)),
    delta_3min double precision CHECK (delta_3min IS NULL OR finite_float8(delta_3min)),
    cvd_session double precision CHECK (cvd_session IS NULL OR finite_float8(cvd_session)),
    cvd_nyse_session double precision CHECK (cvd_nyse_session IS NULL OR finite_float8(cvd_nyse_session)),
    cvd_spot_24h double precision CHECK (cvd_spot_24h IS NULL OR finite_float8(cvd_spot_24h)),
    cvd_spot_session double precision CHECK (cvd_spot_session IS NULL OR finite_float8(cvd_spot_session)),
    cvd_spot_imbalance_24h double precision
        CONSTRAINT metrics_snapshot_cvd_spot_imbalance_24h_check
        CHECK (cvd_spot_imbalance_24h IS NULL OR (finite_float8(cvd_spot_imbalance_24h) AND cvd_spot_imbalance_24h BETWEEN -1 AND 1)),
    cvd_fut_imbalance_24h double precision
        CONSTRAINT metrics_snapshot_cvd_fut_imbalance_24h_check
        CHECK (cvd_fut_imbalance_24h IS NULL OR (finite_float8(cvd_fut_imbalance_24h) AND cvd_fut_imbalance_24h BETWEEN -1 AND 1)),
    oi_bybit double precision CHECK (oi_bybit IS NULL OR (finite_float8(oi_bybit) AND oi_bybit >= 0)),
    liq_ratio_24h double precision CHECK (liq_ratio_24h IS NULL OR (finite_float8(liq_ratio_24h) AND liq_ratio_24h >= 0)),
    cvd_diff_24h double precision CHECK (cvd_diff_24h IS NULL OR finite_float8(cvd_diff_24h)),
    cvd_diff_ses double precision CHECK (cvd_diff_ses IS NULL OR finite_float8(cvd_diff_ses)),
    fr_avg double precision CHECK (fr_avg IS NULL OR finite_float8(fr_avg)),
    pfr_avg double precision CHECK (pfr_avg IS NULL OR finite_float8(pfr_avg)),
    long_liq_24h double precision CHECK (long_liq_24h IS NULL OR (finite_float8(long_liq_24h) AND long_liq_24h >= 0)),
    short_liq_24h double precision CHECK (short_liq_24h IS NULL OR (finite_float8(short_liq_24h) AND short_liq_24h >= 0)),
    whale_intensity double precision NOT NULL CHECK (finite_float8(whale_intensity) AND whale_intensity BETWEEN -1 AND 1),
    whale_label text NOT NULL CHECK (length(whale_label) BETWEEN 1 AND 80),
    regime_score double precision NOT NULL CHECK (finite_float8(regime_score) AND regime_score BETWEEN -100 AND 100),
    regime_label text NOT NULL CHECK (length(regime_label) BETWEEN 1 AND 100),
    regime_logic_version smallint
        CONSTRAINT metrics_snapshot_regime_logic_version_check
        CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1),
    price_dir_1h smallint NOT NULL CHECK (price_dir_1h IN (-1,0,1)),
    btr_15m double precision CHECK (btr_15m IS NULL OR (finite_float8(btr_15m) AND btr_15m BETWEEN 0 AND 1)),
    btr_1h double precision CHECK (btr_1h IS NULL OR (finite_float8(btr_1h) AND btr_1h BETWEEN 0 AND 1)),
    btr_24h double precision CHECK (btr_24h IS NULL OR (finite_float8(btr_24h) AND btr_24h BETWEEN 0 AND 1)),
    pfr_fr_div double precision CHECK (pfr_fr_div IS NULL OR finite_float8(pfr_fr_div)),
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    PRIMARY KEY (symbol, ts)
);
-- v1.5.0: ausencia != cero. whale_intensity y regime_score se escribian como 0.0 cuando la
-- fuente faltaba, asi que el historico contiene "flujo institucional neutro" y "regimen
-- lateral" que en realidad eran ausencia de dato. A partir de aqui se guarda NULL.
-- Las etiquetas siguen siendo NOT NULL porque siempre hay texto ("Sin datos").
-- Las filas antiguas NO se reescriben: no hay forma de distinguir retroactivamente un cero
-- medido de un cero fabricado.
ALTER TABLE metrics_snapshot ALTER COLUMN whale_intensity DROP NOT NULL;
ALTER TABLE metrics_snapshot ALTER COLUMN regime_score DROP NOT NULL;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS price_cutoff_at timestamptz;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS metrics_cutoff_at timestamptz;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS spot_vol_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS cvd_spot_imbalance_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS cvd_fut_imbalance_24h double precision;
ALTER TABLE metrics_snapshot ADD COLUMN IF NOT EXISTS regime_logic_version smallint;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_spot_vol_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_spot_vol_24h_check
      CHECK (spot_vol_24h IS NULL OR (finite_float8(spot_vol_24h) AND spot_vol_24h >= 0));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_cvd_spot_imbalance_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_cvd_spot_imbalance_24h_check
      CHECK (cvd_spot_imbalance_24h IS NULL OR (finite_float8(cvd_spot_imbalance_24h) AND cvd_spot_imbalance_24h BETWEEN -1 AND 1));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_cvd_fut_imbalance_24h_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_cvd_fut_imbalance_24h_check
      CHECK (cvd_fut_imbalance_24h IS NULL OR (finite_float8(cvd_fut_imbalance_24h) AND cvd_fut_imbalance_24h BETWEEN -1 AND 1));
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='metrics_snapshot'::regclass
                 AND conname='metrics_snapshot_regime_logic_version_check') THEN
    ALTER TABLE metrics_snapshot ADD CONSTRAINT metrics_snapshot_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS metrics_snapshot_latest_idx ON metrics_snapshot(symbol, ts DESC);
CREATE INDEX IF NOT EXISTS metrics_snapshot_ts_idx ON metrics_snapshot(ts DESC);

CREATE TABLE IF NOT EXISTS daily_session_agg (
    session_date date NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    cvd_spot_usd double precision NOT NULL CHECK (finite_float8(cvd_spot_usd)),
    cvd_fut_usd double precision NOT NULL CHECK (finite_float8(cvd_fut_usd)),
    cvd_diff_usd double precision GENERATED ALWAYS AS (cvd_spot_usd - cvd_fut_usd) STORED,
    inst_delta_usd double precision NOT NULL CHECK (finite_float8(inst_delta_usd)),
    price_open double precision NOT NULL CHECK (finite_float8(price_open) AND price_open > 0),
    price_close double precision NOT NULL CHECK (finite_float8(price_close) AND price_close > 0),
    price_chg_pct double precision GENERATED ALWAYS AS ((price_close - price_open) / price_open * 100) STORED,
    oi_open double precision CHECK (oi_open IS NULL OR (finite_float8(oi_open) AND oi_open >= 0)),
    oi_close double precision CHECK (oi_close IS NULL OR (finite_float8(oi_close) AND oi_close >= 0)),
    oi_chg_usd double precision GENERATED ALWAYS AS (oi_close - oi_open) STORED,
    fr_avg double precision CHECK (fr_avg IS NULL OR finite_float8(fr_avg)),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, session_date)
);

-- v1.3.3: cvd_fut_usd sale de ohlcv = perp de BINANCE (el sufijo .A de Coinalyze es
-- Binance, no un agregado multi-venue), mientras cvd_spot_usd tiene Binance+Bybit spot.
-- El perp mueve ~10x el spot, asi que el "diferencial" acaba siendo el CVD de futuros con
-- el signo invertido. cvd_fut_2v_usd mide la pata de futuros en Binance+Bybit para alinear
-- venues; no corrige la asimetria de escala. Solo se puebla hacia adelante: depende de
-- futures_trades_agg, que se retiene horas, no meses.
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS cvd_fut_2v_usd double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS cvd_fut_2v_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS cvd_diff_2v_usd double precision
    GENERATED ALWAYS AS (cvd_spot_usd - cvd_fut_2v_usd) STORED;
-- Rollup ampliado: lo granular muere a los 14 dias, esto construye historia hacia adelante.
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS volume_usd double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS price_high double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS price_low double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS long_liq_usd double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS short_liq_usd double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS oi_high double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS oi_low double precision;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS tx_count bigint;

-- El sistema calculaba swing_score, regime y setups al vuelo y los tiraba: no habia forma
-- de preguntar despues "?acerto?". Una fila por sesion y simbolo, retenida como el resto
-- de daily_session_agg, hace evaluable el modelo a partir de hoy.
CREATE TABLE IF NOT EXISTS daily_verdict (
    session_date date NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    swing_bias text CHECK (swing_bias IS NULL OR swing_bias IN ('LONG','SHORT','NEUTRAL')),
    swing_score double precision CHECK (swing_score IS NULL OR finite_float8(swing_score)),
    swing_conviction text CHECK (swing_conviction IS NULL OR swing_conviction IN ('baja','media','alta')),
    long_share_pct double precision CHECK (long_share_pct IS NULL OR (finite_float8(long_share_pct) AND long_share_pct BETWEEN 0 AND 100)),
    swing_components jsonb,
    regime_score double precision CHECK (regime_score IS NULL OR (finite_float8(regime_score) AND regime_score BETWEEN -100 AND 100)),
    regime_label text CHECK (regime_label IS NULL OR length(regime_label) BETWEEN 1 AND 100),
    setup_id text CHECK (setup_id IS NULL OR length(setup_id) BETWEEN 1 AND 8),
    setup_name text CHECK (setup_name IS NULL OR length(setup_name) BETWEEN 1 AND 80),
    setup_state text CHECK (setup_state IS NULL OR setup_state IN ('activo','vigilancia','inactivo')),
    setup_confidence integer CHECK (setup_confidence IS NULL OR setup_confidence BETWEEN 0 AND 100),
    daily_streak integer,
    price_close double precision CHECK (price_close IS NULL OR (finite_float8(price_close) AND price_close > 0)),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, session_date)
);
CREATE INDEX IF NOT EXISTS daily_verdict_date_idx ON daily_verdict(session_date DESC);

-- PR21_DAILY_VERDICT_SNAPSHOT_BEGIN
-- Durable point-in-time evidence starts prospectively with PR21. daily_verdict remains
-- the mutable latest operational projection; this table keeps only the first emission
-- actually observed for each session and must never be backfilled from that projection.
CREATE TABLE IF NOT EXISTS daily_verdict_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_date date NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    snapshot_version smallint NOT NULL CHECK (snapshot_version >= 1),
    logic_version text NOT NULL CHECK (length(logic_version) BETWEEN 1 AND 80),
    observed_at timestamptz NOT NULL,
    session_end_at timestamptz NOT NULL,
    metrics_snapshot_ts timestamptz,
    regime_logic_version smallint
        CONSTRAINT daily_verdict_snapshot_regime_logic_version_check
        CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1),
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
    CHECK (reference_price_at IS NULL OR reference_price_at <= observed_at),
    CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check CHECK (
        logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3')
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
            regime_logic_version IS NULL
            AND regime_score IS NULL
            AND regime_label IS NULL
            AND metrics_snapshot_ts IS NULL
        )
    )
);
ALTER TABLE daily_verdict_snapshot
    ADD COLUMN IF NOT EXISTS regime_logic_version smallint;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='daily_verdict_snapshot'::regclass
      AND conname='daily_verdict_snapshot_regime_logic_version_check'
  ) THEN
    ALTER TABLE daily_verdict_snapshot
      ADD CONSTRAINT daily_verdict_snapshot_regime_logic_version_check
      CHECK (regime_logic_version IS NULL OR regime_logic_version >= 1);
  END IF;
  ALTER TABLE daily_verdict_snapshot
    DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr22_regime_provenance_check;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='daily_verdict_snapshot'::regclass
      AND conname='daily_verdict_snapshot_pr23_regime_provenance_check'
  ) THEN
    ALTER TABLE daily_verdict_snapshot
      ADD CONSTRAINT daily_verdict_snapshot_pr23_regime_provenance_check
      CHECK (
        logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3')
        OR regime_logic_version IS NOT DISTINCT FROM 2
        OR (
          regime_logic_version IS NULL
          AND regime_score IS NULL
          AND regime_label IS NULL
          AND metrics_snapshot_ts IS NULL
        )
      );
  END IF;
END $$;
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
-- PR21_DAILY_VERDICT_SNAPSHOT_END

-- Contexto externo diario: 800 dias cubren dos años completos con margen para fines de
-- semana. Son pocas filas y evitan confundir los percentiles internos con datos macro.
CREATE TABLE IF NOT EXISTS external_macro_observation (
    series text NOT NULL CHECK (length(series) BETWEEN 1 AND 80),
    observed_on date NOT NULL,
    value double precision NOT NULL CHECK (finite_float8(value)),
    source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series, observed_on)
);
CREATE INDEX IF NOT EXISTS external_macro_observation_latest_idx
    ON external_macro_observation(series, observed_on DESC);

CREATE TABLE IF NOT EXISTS macro_event (
    event_key text NOT NULL CHECK (length(event_key) BETWEEN 1 AND 100),
    event_at timestamptz NOT NULL,
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    importance smallint NOT NULL CHECK (importance BETWEEN 1 AND 3),
    source text NOT NULL CHECK (length(source) BETWEEN 1 AND 100),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (event_key, event_at)
);
CREATE INDEX IF NOT EXISTS macro_event_upcoming_idx ON macro_event(event_at);

-- v1.4.9 (P2): distribucion medida de cada metrica por simbolo y ventana, para que los
-- umbrales salgan de los datos y no de una constante inventada.
--
-- Motivo concreto: ABSORPTION_MIN_RATIO=0.10 se aplicaba igual a 1m y a 4h. Medido sobre
-- 20 021 velas de 1 min, |delta|/volumen tiene p50 = 0.34 en 1 m y 0.045 en 4 h, asi que ese
-- 0.10 dejaba pasar el 78 % de las ventanas de 3 m y rechazaba el 87 % de las de 4 h. El ratio
-- decae al alargar la ventana (cancelacion), asi que el umbral TIENE que depender de ella.
--
-- Son ~30 filas (3 simbolos x 10 ventanas) y las refresca el job diario.
CREATE TABLE IF NOT EXISTS metric_baseline (
    symbol text NOT NULL REFERENCES symbols(symbol),
    metric text NOT NULL CHECK (length(metric) BETWEEN 1 AND 40),
    window_label text NOT NULL CHECK (length(window_label) BETWEEN 1 AND 10),
    window_seconds integer NOT NULL CHECK (window_seconds > 0),
    source_interval text NOT NULL CHECK (source_interval IN ('1min','5min','4hour','daily')),
    sample_count integer NOT NULL CHECK (sample_count >= 0),
    p50 double precision NOT NULL CHECK (finite_float8(p50)),
    p75 double precision NOT NULL CHECK (finite_float8(p75)),
    p90 double precision NOT NULL CHECK (finite_float8(p90)),
    p95 double precision NOT NULL CHECK (finite_float8(p95)),
    -- MAD, no desviacion tipica: la distribucion tiene cola y la media no la representa.
    mad double precision NOT NULL CHECK (finite_float8(mad) AND mad >= 0),
    sample_start timestamptz,
    sample_end timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, metric, window_label)
);

CREATE TABLE IF NOT EXISTS pipeline_heartbeat (
    service text PRIMARY KEY CHECK (length(service) BETWEEN 1 AND 100),
    updated_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('ok','degraded','error')),
    detail text CHECK (detail IS NULL OR length(detail) <= 500)
);

CREATE TABLE IF NOT EXISTS service_ownership (
    service text NOT NULL CHECK (length(service) BETWEEN 1 AND 100),
    shard_index integer NOT NULL CHECK (shard_index >= 0),
    shard_count integer NOT NULL CHECK (shard_count > 0 AND shard_index < shard_count),
    generation bigint NOT NULL CHECK (generation > 0),
    acquired_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (service, shard_index, shard_count)
);

-- Upgrade existing v1.0/v1.1.0 installations where the CHECK constraint
-- did not include the scalp collector. CREATE TABLE IF NOT EXISTS does not
-- update constraints on an existing table, so this is intentionally explicit.
ALTER TABLE pipeline_heartbeat
    DROP CONSTRAINT IF EXISTS pipeline_heartbeat_service_check;
ALTER TABLE pipeline_heartbeat
    ADD CONSTRAINT pipeline_heartbeat_service_check
    CHECK (length(service) BETWEEN 1 AND 100);

CREATE TABLE IF NOT EXISTS external_api_rate_event (
    provider text NOT NULL,
    ts timestamptz NOT NULL DEFAULT now(),
    units integer NOT NULL CHECK (units > 0)
);

CREATE INDEX IF NOT EXISTS external_api_rate_event_provider_ts_idx
    ON external_api_rate_event(provider, ts);

CREATE TABLE IF NOT EXISTS market_feed_health (
    feed text NOT NULL,
    exchange text NOT NULL,
    status text NOT NULL CHECK (status IN ('ok','degraded','error')),
    healthy_since timestamptz,
    last_loss_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    detail text CHECK (detail IS NULL OR length(detail) <= 500),
    PRIMARY KEY (feed, exchange)
);

CREATE INDEX IF NOT EXISTS market_feed_health_updated_idx
    ON market_feed_health(feed, updated_at DESC);

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

-- PR19: provenance for materialized two-venue rows.
-- NULL = legacy/unverified. Old rows are not rewritten.
ALTER TABLE spot_trades_agg ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE spot_trades_realtime ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE futures_trades_agg ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE futures_trades_realtime ADD COLUMN IF NOT EXISTS venue_count smallint;
ALTER TABLE orderbook_snapshot ADD COLUMN IF NOT EXISTS venue_count smallint;

DO $$
DECLARE
    table_name text;
    constraint_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'spot_trades_agg','spot_trades_realtime','futures_trades_agg',
        'futures_trades_realtime','orderbook_snapshot'
    ] LOOP
        constraint_name := table_name || '_venue_count_provenance_check';
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid=to_regclass(format('%I.%I', current_schema(), table_name))
              AND conname=constraint_name
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I ADD CONSTRAINT %I CHECK ('
                'venue_count IS NULL OR '
                '(exchange = ''combined'' AND venue_count = 2) OR '
                '(exchange IN (''binance'',''bybit'') AND venue_count = 1)'
                ')',
                table_name, constraint_name
            );
        END IF;
    END LOOP;
END
$$;

COMMENT ON COLUMN spot_trades_agg.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN spot_trades_realtime.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN futures_trades_agg.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN futures_trades_realtime.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';
COMMENT ON COLUMN orderbook_snapshot.venue_count IS
    'NULL=legacy/unverified; 1=explicit venue; 2=verified Binance+Bybit combined';

-- Explicit continuity failures. Intervals are half-open [start_ts,end_ts): a gap ending
-- exactly when a metric window starts does not overlap it, while one starting exactly at
-- the window start does. Event streams may only use positive loss evidence; silence is
-- deliberately absent from the allowed evidence values.
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

-- Daily UTC partitions balance the realtime retention horizons with a small, predictable
-- object count. Startup calls this function; the advisory transaction lock makes concurrent
-- service starts idempotent.
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
        'futures_trades_realtime',
        'spot_trades_realtime',
        'orderbook_snapshot',
        'liquidations_realtime',
        'scalp_signal_snapshot'
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
                    'CREATE TABLE %I.%I PARTITION OF %I.%I '
                    'FOR VALUES FROM (%L) TO (%L)',
                    schema_name,
                    child_name,
                    schema_name,
                    managed_table,
                    partition_day::timestamp AT TIME ZONE 'UTC',
                    (partition_day + 1)::timestamp AT TIME ZONE 'UTC'
                );
                created_count := created_count + 1;
                child_oid := to_regclass(format('%I.%I', schema_name, child_name));
            END IF;
            IF NOT EXISTS (
                SELECT 1
                FROM pg_inherits
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
        'futures_trades_realtime',
        'spot_trades_realtime',
        'orderbook_snapshot',
        'liquidations_realtime',
        'scalp_signal_snapshot'
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
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
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

-- psql deployment entry point: CREATE TABLE IF NOT EXISTS cannot convert legacy
-- ordinary tables. This include executes the verified transactional conversion.
-- Inlined from sql/migrations/20260809_temporal_partitioning.sql.
-- schema.sql must be self-contained: the production deploy wrapper
-- (deploy-coinalyze, outside the repo) copies ONLY this file to a scratch
-- path before running psql -f on it, so a relative \ir include silently
-- fails to find sql/migrations/ there (psql exits 0 on a missing \ir
-- target, which would make the deploy wrapper report success while the
-- actual partition migration never ran). The migration below is
-- idempotent (verified: safe to run on every deploy).
BEGIN;
SET LOCAL TIME ZONE 'UTC';
SET LOCAL lock_timeout = '10s';

CREATE TABLE IF NOT EXISTS schema_migration (
    name text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

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
    bridge_recorded boolean;
    liquidation_arbiter_ready boolean;
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

    SELECT EXISTS (
        SELECT 1 FROM schema_migration
        WHERE name = '20260809_partition_compatibility_bridge'
    ) INTO bridge_recorded;
    IF NOT bridge_recorded THEN
        RAISE EXCEPTION
            'temporal partition migration requires the partition compatibility bridge release';
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM pg_index AS index_definition
        WHERE index_definition.indrelid =
              to_regclass(format('%I.liquidations_realtime', schema_name))
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
    ) INTO liquidation_arbiter_ready;
    IF NOT liquidation_arbiter_ready THEN
        RAISE EXCEPTION
            'temporal partition migration requires the bridge liquidation conflict arbiter';
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

        IF (SELECT count(*) FROM pg_index AS replacement_index
            WHERE replacement_index.indrelid =
                  to_regclass(format('%I.%I', schema_name, replacement_name))
              AND NOT replacement_index.indisprimary)
           <
           (SELECT count(*) FROM pg_index AS source_index
            JOIN pg_class AS source_index_relation
              ON source_index_relation.oid = source_index.indexrelid
            WHERE source_index.indrelid =
                  to_regclass(format('%I.%I', schema_name, source_name))
              AND NOT source_index.indisprimary
              AND NOT (
                  source_name = 'liquidations_realtime'
                  AND source_index_relation.relname =
                      'liquidations_realtime_exchange_event_ts_uidx'
              ))
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

INSERT INTO schema_migration(name)
VALUES ('20260809_temporal_partitioning')
ON CONFLICT (name) DO NOTHING;
COMMIT;

BEGIN;
-- PR20_F3_F4_F7_BEGIN
-- F4: NULL means price direction was not measurable. Zero is reserved for a real
-- measured lateral move inside +/-20 bps.
ALTER TABLE metrics_snapshot ALTER COLUMN price_dir_1h DROP NOT NULL;
-- F3: partial daily sessions must preserve absence. Existing rows are legacy/unverified
-- until prospectively recalculated by the v1 coverage contract.
ALTER TABLE daily_session_agg ALTER COLUMN cvd_spot_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN cvd_fut_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN inst_delta_usd DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_open DROP NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN price_close DROP NOT NULL;

ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_coverage_version smallint;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_expected_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS futures_ohlcv_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS spot_2v_minutes integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS session_expected_5m_samples integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS oi_5m_samples integer;
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS funding_5m_samples integer;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='daily_session_agg'::regclass
      AND conname='daily_session_agg_pr20_coverage_check'
  ) THEN
    ALTER TABLE daily_session_agg ADD CONSTRAINT daily_session_agg_pr20_coverage_check CHECK (
      session_coverage_version IS NULL OR (
        session_coverage_version = 1
        AND session_expected_minutes IS NOT NULL AND session_expected_minutes > 0
        AND futures_ohlcv_minutes IS NOT NULL
          AND futures_ohlcv_minutes BETWEEN 0 AND session_expected_minutes
        AND spot_2v_minutes IS NOT NULL
          AND spot_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND cvd_fut_2v_minutes IS NOT NULL
          AND cvd_fut_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND session_expected_5m_samples IS NOT NULL AND session_expected_5m_samples > 0
        AND session_expected_5m_samples * 5 = session_expected_minutes
        AND oi_5m_samples IS NOT NULL
          AND oi_5m_samples BETWEEN 0 AND session_expected_5m_samples
        AND funding_5m_samples IS NOT NULL
          AND funding_5m_samples BETWEEN 0 AND session_expected_5m_samples
      )
    );
  END IF;
END $$;

COMMENT ON COLUMN daily_session_agg.session_coverage_version IS
  'NULL=legacy/unverified; 1=PR20 DST-aware metric-specific coverage';
COMMENT ON COLUMN daily_session_agg.session_expected_minutes IS
  'Expected 1-minute samples from exact NYSE session_bounds; naturally 1380/1440/1500 across DST';
-- PR20_F3_F4_F7_END
COMMIT;

BEGIN;
-- PR24_DAILY_HISTORICAL_INTEGRITY_BEGIN
-- daily_session_agg stays mutable. updated_at is structural metadata; for legacy rows only,
-- initialization from created_at does not claim to reconstruct their true update history.
ALTER TABLE daily_session_agg ADD COLUMN IF NOT EXISTS updated_at timestamptz;
UPDATE daily_session_agg SET updated_at=created_at WHERE updated_at IS NULL;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at SET NOT NULL;
ALTER TABLE daily_session_agg ALTER COLUMN updated_at SET DEFAULT clock_timestamp();
COMMENT ON COLUMN daily_session_agg.updated_at IS
  'Mutable projection update time. Legacy rows were structurally initialized from created_at during PR24; that initialization is not historical update evidence.';

ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_coverage_version smallint;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_observed_start_at timestamptz;
ALTER TABLE daily_session_agg
  ADD COLUMN IF NOT EXISTS liquidation_observed_end_at timestamptz;
ALTER TABLE daily_session_agg
  DROP CONSTRAINT IF EXISTS daily_session_agg_pr24_liquidation_coverage_check;
ALTER TABLE daily_session_agg
  ADD CONSTRAINT daily_session_agg_pr24_liquidation_coverage_check CHECK (
    liquidation_coverage_version IS NULL OR (
      liquidation_coverage_version = 1
      AND liquidation_observed_start_at IS NOT NULL
      AND liquidation_observed_end_at IS NOT NULL
      AND liquidation_observed_start_at < liquidation_observed_end_at
      AND long_liq_usd IS NOT NULL AND finite_float8(long_liq_usd) AND long_liq_usd >= 0
      AND short_liq_usd IS NOT NULL AND finite_float8(short_liq_usd) AND short_liq_usd >= 0
    )
  ) NOT VALID;
COMMENT ON COLUMN daily_session_agg.liquidation_coverage_version IS
  'NULL=coverage not demonstrated; 1=a COMPLETE liquidation-history observation covers the whole session';

CREATE TABLE IF NOT EXISTS liquidation_history_observation (
    observation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol text NOT NULL REFERENCES symbols(symbol),
    source_start_at timestamptz NOT NULL,
    source_cutoff_at timestamptz NOT NULL,
    observed_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('COMPLETE','INCOMPLETE')),
    response_symbol_present boolean NOT NULL,
    returned_rows integer NOT NULL CHECK (returned_rows >= 0),
    accepted_rows integer NOT NULL CHECK (accepted_rows >= 0 AND accepted_rows <= returned_rows),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (source_start_at < source_cutoff_at),
    CHECK (observed_at >= source_cutoff_at),
    CHECK (
      (status='COMPLETE' AND response_symbol_present AND accepted_rows=returned_rows)
      OR
      (status='INCOMPLETE' AND (NOT response_symbol_present OR accepted_rows<>returned_rows))
    )
);
CREATE INDEX IF NOT EXISTS liquidation_history_observation_complete_idx
  ON liquidation_history_observation(
    symbol, source_start_at, source_cutoff_at, observed_at DESC
  ) WHERE status='COMPLETE';

CREATE TABLE IF NOT EXISTS daily_session_snapshot (
    snapshot_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol text NOT NULL REFERENCES symbols(symbol),
    session_date date NOT NULL,
    snapshot_version smallint NOT NULL CHECK (snapshot_version >= 1),
    observed_at timestamptz NOT NULL,
    session_end_at timestamptz NOT NULL,
    cvd_spot_usd double precision CHECK (cvd_spot_usd IS NULL OR finite_float8(cvd_spot_usd)),
    cvd_fut_usd double precision CHECK (cvd_fut_usd IS NULL OR finite_float8(cvd_fut_usd)),
    cvd_diff_usd double precision CHECK (cvd_diff_usd IS NULL OR finite_float8(cvd_diff_usd)),
    cvd_fut_2v_usd double precision CHECK (cvd_fut_2v_usd IS NULL OR finite_float8(cvd_fut_2v_usd)),
    cvd_diff_2v_usd double precision CHECK (cvd_diff_2v_usd IS NULL OR finite_float8(cvd_diff_2v_usd)),
    inst_delta_usd double precision CHECK (inst_delta_usd IS NULL OR finite_float8(inst_delta_usd)),
    price_open double precision CHECK (price_open IS NULL OR (finite_float8(price_open) AND price_open > 0)),
    price_high double precision CHECK (price_high IS NULL OR (finite_float8(price_high) AND price_high > 0)),
    price_low double precision CHECK (price_low IS NULL OR (finite_float8(price_low) AND price_low > 0)),
    price_close double precision CHECK (price_close IS NULL OR (finite_float8(price_close) AND price_close > 0)),
    price_chg_pct double precision CHECK (price_chg_pct IS NULL OR finite_float8(price_chg_pct)),
    oi_open double precision CHECK (oi_open IS NULL OR (finite_float8(oi_open) AND oi_open >= 0)),
    oi_high double precision CHECK (oi_high IS NULL OR (finite_float8(oi_high) AND oi_high >= 0)),
    oi_low double precision CHECK (oi_low IS NULL OR (finite_float8(oi_low) AND oi_low >= 0)),
    oi_close double precision CHECK (oi_close IS NULL OR (finite_float8(oi_close) AND oi_close >= 0)),
    oi_chg_usd double precision CHECK (oi_chg_usd IS NULL OR finite_float8(oi_chg_usd)),
    fr_avg double precision CHECK (fr_avg IS NULL OR finite_float8(fr_avg)),
    volume_usd double precision CHECK (volume_usd IS NULL OR (finite_float8(volume_usd) AND volume_usd >= 0)),
    long_liq_usd double precision CHECK (long_liq_usd IS NULL OR (finite_float8(long_liq_usd) AND long_liq_usd >= 0)),
    short_liq_usd double precision CHECK (short_liq_usd IS NULL OR (finite_float8(short_liq_usd) AND short_liq_usd >= 0)),
    tx_count bigint CHECK (tx_count IS NULL OR tx_count >= 0),
    session_coverage_version smallint,
    session_expected_minutes integer,
    futures_ohlcv_minutes integer,
    spot_2v_minutes integer,
    cvd_fut_2v_minutes integer,
    session_expected_5m_samples integer,
    oi_5m_samples integer,
    funding_5m_samples integer,
    liquidation_coverage_version smallint,
    liquidation_observed_start_at timestamptz,
    liquidation_observed_end_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE(symbol, session_date),
    CHECK (observed_at >= session_end_at),
    CHECK (
      session_coverage_version IS NULL OR (
        session_coverage_version = 1
        AND session_expected_minutes IS NOT NULL AND session_expected_minutes > 0
        AND futures_ohlcv_minutes BETWEEN 0 AND session_expected_minutes
        AND spot_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND cvd_fut_2v_minutes BETWEEN 0 AND session_expected_minutes
        AND session_expected_5m_samples IS NOT NULL
        AND session_expected_5m_samples * 5 = session_expected_minutes
        AND oi_5m_samples BETWEEN 0 AND session_expected_5m_samples
        AND funding_5m_samples BETWEEN 0 AND session_expected_5m_samples
      )
    ),
    CHECK (
      (
        liquidation_coverage_version IS NULL
        AND liquidation_observed_start_at IS NULL
        AND liquidation_observed_end_at IS NULL
        AND long_liq_usd IS NULL
        AND short_liq_usd IS NULL
      ) OR (
        liquidation_coverage_version = 1
        AND liquidation_observed_start_at IS NOT NULL
        AND liquidation_observed_end_at IS NOT NULL
        AND liquidation_observed_start_at < liquidation_observed_end_at
        AND liquidation_observed_end_at >= session_end_at
        AND long_liq_usd IS NOT NULL
        AND short_liq_usd IS NOT NULL
      )
    )
);
CREATE INDEX IF NOT EXISTS daily_session_snapshot_date_idx
  ON daily_session_snapshot(session_date DESC);

CREATE OR REPLACE FUNCTION reject_pr24_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; % is not allowed', TG_TABLE_NAME, TG_OP
      USING ERRCODE = '55000';
    RETURN NULL;
END
$$;

DROP TRIGGER IF EXISTS daily_session_snapshot_no_update_delete ON daily_session_snapshot;
CREATE TRIGGER daily_session_snapshot_no_update_delete
BEFORE UPDATE OR DELETE ON daily_session_snapshot
FOR EACH ROW EXECUTE FUNCTION reject_pr24_append_only_mutation();
DROP TRIGGER IF EXISTS daily_session_snapshot_no_truncate ON daily_session_snapshot;
CREATE TRIGGER daily_session_snapshot_no_truncate
BEFORE TRUNCATE ON daily_session_snapshot
FOR EACH STATEMENT EXECUTE FUNCTION reject_pr24_append_only_mutation();
DROP TRIGGER IF EXISTS liquidation_history_observation_no_update_delete
  ON liquidation_history_observation;
CREATE TRIGGER liquidation_history_observation_no_update_delete
BEFORE UPDATE OR DELETE ON liquidation_history_observation
FOR EACH ROW EXECUTE FUNCTION reject_pr24_append_only_mutation();
DROP TRIGGER IF EXISTS liquidation_history_observation_no_truncate
  ON liquidation_history_observation;
CREATE TRIGGER liquidation_history_observation_no_truncate
BEFORE TRUNCATE ON liquidation_history_observation
FOR EACH STATEMENT EXECUTE FUNCTION reject_pr24_append_only_mutation();

ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr23_regime_provenance_check;
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_regime_provenance_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr24_regime_provenance_check CHECK (
    evidence_version NOT IN (3,4,5)
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL AND price_cutoff_at IS NULL
      AND metrics_cutoff_at IS NULL
    )
  );
ALTER TABLE signal_observation
  DROP CONSTRAINT IF EXISTS signal_observation_pr24_reference_time_check;
ALTER TABLE signal_observation
  ADD CONSTRAINT signal_observation_pr24_reference_time_check CHECK (
    evidence_version <> 5 OR (
      (
        reference_price IS NULL AND reference_price_source IS NULL
        AND reference_price_at IS NULL
      ) OR (
        reference_price IS NOT NULL AND reference_price_source IS NOT NULL
        AND reference_price_at IS NOT NULL AND reference_price_at <= observed_at
      )
    )
  );
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr23_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  DROP CONSTRAINT IF EXISTS daily_verdict_snapshot_pr24_regime_provenance_check;
ALTER TABLE daily_verdict_snapshot
  ADD CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check CHECK (
    logic_version NOT IN ('daily-verdict-v2','daily-verdict-v3','daily-verdict-v4')
    OR regime_logic_version IS NOT DISTINCT FROM 2
    OR (
      regime_logic_version IS NULL AND regime_score IS NULL AND regime_label IS NULL
      AND metrics_snapshot_ts IS NULL
    )
  );
COMMENT ON CONSTRAINT signal_observation_pr24_regime_provenance_check
  ON signal_observation IS
  'Signal evidence v3/v4/v5 requires regime logic v2 or a completely NULL regime block';
COMMENT ON CONSTRAINT signal_observation_pr24_reference_time_check
  ON signal_observation IS
  'Signal evidence v5 reference prices require an exact source timestamp no later than observed_at';
COMMENT ON CONSTRAINT daily_verdict_snapshot_pr24_regime_provenance_check
  ON daily_verdict_snapshot IS
  'Daily verdict v2/v3/v4 requires regime logic v2 or a completely NULL regime block';
-- PR24_DAILY_HISTORICAL_INTEGRITY_END
COMMIT;
