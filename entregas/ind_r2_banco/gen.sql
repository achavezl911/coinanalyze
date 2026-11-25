-- cinta sintetica de BTC con rafagas y liquidaciones agrupadas en ellas (banco IND R2)
-- 11-24 05:00Z .. 11-25 06:00Z (25 h). Base 90 impresiones/s, rafagas de 600/s (~13 % del tiempo).
SELECT setseed(0.42);
CREATE TEMP TABLE rafaga AS
SELECT timestamptz '2026-11-24 05:00Z' + (random() * 89000)::int * interval '1 s' AS c,
       (30 + random() * 180)::int * interval '1 s' AS dur
  FROM generate_series(1, 100);
CREATE TEMP TABLE seg AS
SELECT s, CASE WHEN EXISTS (SELECT 1 FROM rafaga r WHERE s >= r.c AND s < r.c + r.dur) THEN 600 ELSE 90 END AS n
  FROM generate_series(timestamptz '2026-11-24 05:00Z', timestamptz '2026-11-25 05:59:59Z', interval '1 s') s;
SELECT count(*) AS segundos, sum(n) AS impresiones, count(*) FILTER (WHERE n = 600) AS seg_rafaga FROM seg;

INSERT INTO orderflow_cinta(ts, venue, symbol, precio, base, usd, compra, id)
SELECT ts, venue, 'BTC', precio, round(usd / precio, 8), usd, compra, id
  FROM (SELECT date_trunc('milliseconds', s + random() * interval '1 s') AS ts,
               CASE WHEN r < 0.35 THEN 'binance_usdm' WHEN r < 0.55 THEN 'bybit_linear' WHEN r < 0.65 THEN 'okx_swap'
                    WHEN r < 0.75 THEN 'binance_spot' WHEN r < 0.83 THEN 'coinbase_spot' WHEN r < 0.90 THEN 'bybit_spot'
                    WHEN r < 0.95 THEN 'okx_spot' WHEN r < 0.98 THEN 'bitget_usdt' ELSE 'deribit_perp' END AS venue,
               round((90000 + random() * 200)::numeric, 1) AS precio,
               round((exp(random() * 12) + 5)::numeric, 2) AS usd,
               random() < 0.5 AS compra,
               (extract(epoch FROM s)::bigint * 1000 + g)::text AS id
          FROM seg, LATERAL (SELECT g, random() AS r FROM generate_series(1, seg.n) g) x) y;

INSERT INTO liquidations_realtime(ts, symbol, exchange, side, notional_usd, price, qty, event_id, avg_price)
SELECT ts, 'BTCUSDT_PERP.A', ex, side, notional, 90000.0, notional / 90000.0, 'e' || g,
       CASE WHEN ex = 'binance' AND random() < 0.6 THEN 89950.0 + random() * 100 END
  FROM (SELECT g, ts, CASE WHEN random() < 0.6 THEN 'binance' ELSE 'bybit' END AS ex,
               CASE WHEN random() < 0.5 THEN 'long' ELSE 'short' END AS side,
               round((exp(random() * 11) + 100)::numeric, 2)::float8 AS notional
          FROM (SELECT g, CASE WHEN g <= 2400
                       THEN (SELECT date_trunc('milliseconds', r.c + random() * r.dur) FROM rafaga r
                              OFFSET (g * 7919) % 100 LIMIT 1)
                       ELSE date_trunc('milliseconds', timestamptz '2026-11-24 05:00Z' + random() * interval '25 h') END AS ts
                  FROM generate_series(1, 3500) g) z) w;
VACUUM ANALYZE orderflow_cinta;
VACUUM ANALYZE liquidations_realtime;
SELECT count(*) AS cinta FROM orderflow_cinta;
SELECT count(*) AS liq, count(*) FILTER (WHERE avg_price IS NULL) AS sin_ap FROM liquidations_realtime;
SELECT pg_size_pretty(pg_database_size(current_database()));
