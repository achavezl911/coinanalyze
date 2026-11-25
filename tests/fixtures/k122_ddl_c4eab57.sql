CREATE TABLE IF NOT EXISTS libro_cobertura (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    segundos smallint NOT NULL CHECK (segundos BETWEEN 0 AND 60),
    fotos smallint NOT NULL CHECK (fotos >= 0),
    saltos smallint NOT NULL DEFAULT 0 CHECK (saltos >= 0),
    resincronizaciones smallint NOT NULL DEFAULT 0 CHECK (resincronizaciones >= 0),
    reconexiones smallint NOT NULL DEFAULT 0 CHECK (reconexiones >= 0),
    escrito timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, ts, venue)
);
CREATE INDEX IF NOT EXISTS libro_cobertura_ts_idx ON libro_cobertura (ts);
CREATE TABLE IF NOT EXISTS libro_foto (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    ts_libro timestamptz NOT NULL,
    compra numeric NOT NULL CHECK (compra > 0),
    venta numeric NOT NULL CHECK (venta > 0),
    paso numeric NOT NULL CHECK (paso > 0),
    compra_nivel numeric NOT NULL CHECK (compra_nivel >= 0),
    compras numeric[] NOT NULL CHECK (cardinality(compras) >= 1 AND 0 <= ALL (compras)),
    venta_nivel numeric NOT NULL CHECK (venta_nivel >= 0),
    ventas numeric[] NOT NULL CHECK (cardinality(ventas) >= 1 AND 0 <= ALL (ventas)),
    alcance_compra numeric NOT NULL CHECK (alcance_compra > 0),
    alcance_venta numeric NOT NULL CHECK (alcance_venta > 0),
    CHECK (compra < venta),
    PRIMARY KEY (symbol, ts, venue)
) PARTITION BY RANGE (ts);
CREATE TABLE libro_foto_banco PARTITION OF libro_foto DEFAULT;
CREATE TABLE IF NOT EXISTS libro_honda (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('okx_swap', 'okx_spot', 'bitget_usdt')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    ts_libro timestamptz NOT NULL,
    fuente text NOT NULL,
    paso numeric NOT NULL CHECK (paso > 0),
    cubo numeric NOT NULL CHECK (cubo > 0),
    precio numeric NOT NULL CHECK (precio > 0),
    vivo_compra numeric NOT NULL CHECK (vivo_compra > 0),
    vivo_venta numeric NOT NULL CHECK (vivo_venta > 0),
    compra_nivel numeric CHECK (compra_nivel >= 0),
    compras numeric[] CHECK (cardinality(compras) >= 1 AND 0 <= ALL (compras)),
    venta_nivel numeric CHECK (venta_nivel >= 0),
    ventas numeric[] CHECK (cardinality(ventas) >= 1 AND 0 <= ALL (ventas)),
    alcance_compra numeric CHECK (alcance_compra > 0),
    alcance_venta numeric CHECK (alcance_venta > 0),
    bytes_red integer NOT NULL CHECK (bytes_red >= 0),
    CHECK ((compra_nivel IS NULL) = (compras IS NULL) AND (venta_nivel IS NULL) = (ventas IS NULL)),
    PRIMARY KEY (symbol, ts, venue)
) PARTITION BY RANGE (ts);
CREATE TABLE libro_honda_banco PARTITION OF libro_honda DEFAULT;
CREATE TABLE IF NOT EXISTS orderflow_celda (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    nivel numeric NOT NULL CHECK (nivel >= 0),
    compra_base numeric NOT NULL CHECK (compra_base >= 0),
    venta_base numeric NOT NULL CHECK (venta_base >= 0),
    compra_usd numeric NOT NULL CHECK (compra_usd >= 0),
    venta_usd numeric NOT NULL CHECK (venta_usd >= 0),
    compras integer NOT NULL CHECK (compras >= 0),
    ventas integer NOT NULL CHECK (ventas >= 0),
    CHECK (compras + ventas > 0),
    PRIMARY KEY (symbol, ts, venue, nivel)
) PARTITION BY RANGE (ts);
CREATE TABLE orderflow_celda_banco PARTITION OF orderflow_celda DEFAULT;
CREATE TABLE IF NOT EXISTS orderflow_celda_hora (
    ts timestamptz NOT NULL CHECK (ts = date_bin(interval '1 hour', ts, timestamptz '2000-01-01 00:00:00+00')),
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    nivel numeric NOT NULL CHECK (nivel >= 0),
    compra_base numeric NOT NULL CHECK (compra_base >= 0),
    venta_base numeric NOT NULL CHECK (venta_base >= 0),
    compra_usd numeric NOT NULL CHECK (compra_usd >= 0),
    venta_usd numeric NOT NULL CHECK (venta_usd >= 0),
    compras bigint NOT NULL CHECK (compras >= 0),
    ventas bigint NOT NULL CHECK (ventas >= 0),
    CHECK (compras + ventas > 0),
    PRIMARY KEY (symbol, ts, venue, nivel)
) PARTITION BY RANGE (ts);
CREATE TABLE orderflow_celda_hora_banco PARTITION OF orderflow_celda_hora DEFAULT;
CREATE TABLE IF NOT EXISTS orderflow_cinta (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    precio numeric NOT NULL CHECK (precio > 0),
    base numeric NOT NULL CHECK (base > 0),
    usd numeric NOT NULL CHECK (usd > 0),
    compra boolean NOT NULL,
    id text NOT NULL
) PARTITION BY RANGE (ts);
CREATE TABLE orderflow_cinta_banco PARTITION OF orderflow_cinta DEFAULT;
CREATE INDEX IF NOT EXISTS orderflow_cinta_symbol_ts_idx ON orderflow_cinta (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS orderflow_cinta_liq_lado_ts_idx ON orderflow_cinta (symbol, venue, compra, ts)
    WHERE venue IN ('binance_usdm', 'bybit_linear');
CREATE TABLE IF NOT EXISTS orderflow_cobertura (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    segundos smallint NOT NULL CHECK (segundos BETWEEN 0 AND 60),
    operaciones integer NOT NULL CHECK (operaciones >= 0),
    tardias integer NOT NULL DEFAULT 0 CHECK (tardias >= 0),
    fuera integer NOT NULL DEFAULT 0 CHECK (fuera >= 0),
    reconexiones smallint NOT NULL DEFAULT 0 CHECK (reconexiones >= 0),
    definitivo boolean NOT NULL DEFAULT false,
    escrito timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, ts, venue)
);
CREATE INDEX IF NOT EXISTS orderflow_cobertura_ts_idx ON orderflow_cobertura (ts);
CREATE TABLE IF NOT EXISTS orderflow_grande (
    ts timestamptz NOT NULL,
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    precio numeric NOT NULL CHECK (precio > 0),
    base numeric NOT NULL CHECK (base > 0),
    usd numeric NOT NULL CHECK (usd > 0),
    compra boolean NOT NULL,
    id text NOT NULL,
    umbral_usd numeric NOT NULL CHECK (umbral_usd > 0),
    CHECK (usd >= umbral_usd),
    PRIMARY KEY (venue, symbol, id)
);
CREATE INDEX IF NOT EXISTS orderflow_grande_symbol_ts_idx ON orderflow_grande (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS orderflow_grande_ts_idx ON orderflow_grande (ts);
CREATE TABLE IF NOT EXISTS orderflow_hora_hecha (
    ts timestamptz NOT NULL CHECK (ts = date_bin(interval '1 hour', ts, timestamptz '2000-01-01 00:00:00+00')),
    venue text NOT NULL CHECK (venue IN ('binance_spot', 'binance_usdm', 'bybit_spot', 'bybit_linear',
                                         'okx_spot', 'okx_swap', 'coinbase_spot', 'bitget_usdt', 'deribit_perp')),
    symbol text NOT NULL CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    hecha timestamptz NOT NULL DEFAULT now(),
    
    lo numeric,
    hi numeric,
    CHECK ((lo IS NULL) = (hi IS NULL) AND lo <= hi),
    PRIMARY KEY (symbol, ts, venue)
);
CREATE INDEX IF NOT EXISTS orderflow_hora_hecha_ts_idx ON orderflow_hora_hecha (ts);
CREATE TABLE IF NOT EXISTS orderflow_paso (
    symbol text PRIMARY KEY CHECK (symbol IN ('BTC', 'ETH', 'SOL')),
    paso numeric NOT NULL CHECK (paso > 0)
);
