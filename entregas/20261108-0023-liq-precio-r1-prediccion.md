# Campana 150 · remate 1 · la liquidacion donde se ejecuto · criterio escrito ANTES de medir (2026-11-08 00:23Z)

Hallazgo de partida (del operador, auditoria de la 150, clon de 5fd23b5, 00:03-00:30Z): `price` es la `p` de la
orden forzada (limite / quiebra), ~0.4 % mas alla del mercado; en /flujo 1m ninguno de los 19 circulos >= 10 k se
dibuja. Sus tres casos dan 38.7, 39.0 y 32.4 bps entre p y la venta de la cinta.

Antes de medir solo he contado, en 140, las filas de orderflow_cinta de BTC entre 20:00 y 21:00Z del 07-11 (90 982),
para saber que la ventana de P1 sigue dentro de las 48 h de la cinta (sale el 09-11 ~20:00Z).

## P1 · BTC /flujo 1m, hasta = 2026-11-07T21:00:00Z, las 10 >= 10 k
Como: banco de K120 con las liquidaciones de 140 de esa ventana y la cinta de 140 de [ts - 1 s, ts + 1 s] de cada una
(140 no tiene `avg_price`: todas van por 'cinta'). Cuento los circulos de window.LIQ_PINTADAS >= 10 k.
Prediccion: 10 de 10 (antes 0). Aceptable 9: una puede caer fuera del eje si la vela de 1 m no llega a la venta.
Si salen < 9, el emparejamiento esta mal o el eje recorta: se dice cual.

## P2 · las >= 10 k de BTC, ETH y SOL de las ultimas 24 h de 140
Como: la MISMA consulta de la ruta (la de la rama), contra 140 por prodsql, solo lectura.
Prediccion por exchange: 'cinta' >= 95 %, 'sin_dato' <= 5 % en binance y en bybit ('ap' 0 %: 140 no tiene la
columna). Mediana de |p - ejecucion| / ejecucion: binance 30-45 bps, bybit 25-40 bps. Si alguna mediana sale < 5 bps
o > 100 bps, el emparejamiento coge otra impresion: se mira antes de publicar.

## P3 · tiempo de /api/orderflow/indicadores, BTC 4 h y 3 d
Como: 140 no tiene la rama y el banco no cabe la cinta de 48 h de BTC (~91 k filas/h, ~4.4 M filas): la ruta
ANTES (5fd23b5) y DESPUES se cronometran en el banco con los mismos datos (mediana de 5), y la consulta NUEVA de la
cinta se cronometra aparte en 140 con EXPLAIN ANALYZE (mediana de 3), que es donde esta la cinta entera.
Prediccion: en el banco, despues - antes <= 20 ms en 4 h y en 3 d. En 140, la consulta de la cinta <= 50 ms en
4 h y <= 300 ms en 3 d (una busqueda por indice (symbol, ts) de 2 s por liquidacion sin ap).
Si la de 3 d pasa de 1 s: se dice y se propone indice, no se crea en este remate.
