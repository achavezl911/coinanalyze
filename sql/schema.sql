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
);
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
);
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
);
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
    PRIMARY KEY (exchange, event_id)
);
CREATE INDEX IF NOT EXISTS liquidations_realtime_symbol_ts_idx ON liquidations_realtime(symbol, ts DESC);

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
);
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

CREATE TABLE IF NOT EXISTS metrics_snapshot (
    ts timestamptz NOT NULL DEFAULT now(),
    symbol text NOT NULL REFERENCES symbols(symbol),
    price double precision CHECK (price IS NULL OR (finite_float8(price) AND price > 0)),
    oi double precision CHECK (oi IS NULL OR (finite_float8(oi) AND oi >= 0)),
    oi_chg_24h_pct double precision CHECK (oi_chg_24h_pct IS NULL OR finite_float8(oi_chg_24h_pct)),
    oi_vol_24h_ratio double precision CHECK (oi_vol_24h_ratio IS NULL OR (finite_float8(oi_vol_24h_ratio) AND oi_vol_24h_ratio >= 0)),
    vol_24h double precision CHECK (vol_24h IS NULL OR (finite_float8(vol_24h) AND vol_24h >= 0)),
    delta_3min double precision CHECK (delta_3min IS NULL OR finite_float8(delta_3min)),
    cvd_session double precision CHECK (cvd_session IS NULL OR finite_float8(cvd_session)),
    cvd_nyse_session double precision CHECK (cvd_nyse_session IS NULL OR finite_float8(cvd_nyse_session)),
    cvd_spot_24h double precision CHECK (cvd_spot_24h IS NULL OR finite_float8(cvd_spot_24h)),
    cvd_spot_session double precision CHECK (cvd_spot_session IS NULL OR finite_float8(cvd_spot_session)),
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
    price_dir_1h smallint NOT NULL CHECK (price_dir_1h IN (-1,0,1)),
    btr_15m double precision CHECK (btr_15m IS NULL OR (finite_float8(btr_15m) AND btr_15m BETWEEN 0 AND 1)),
    btr_1h double precision CHECK (btr_1h IS NULL OR (finite_float8(btr_1h) AND btr_1h BETWEEN 0 AND 1)),
    btr_24h double precision CHECK (btr_24h IS NULL OR (finite_float8(btr_24h) AND btr_24h BETWEEN 0 AND 1)),
    pfr_fr_div double precision CHECK (pfr_fr_div IS NULL OR finite_float8(pfr_fr_div)),
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

COMMIT;
