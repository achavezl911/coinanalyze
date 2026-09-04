# `GET /api/scalp/execution-cost`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_execution_cost` · `app/api.py:1372` (cuerpo hasta la 1425) · decorador en la linea 1371.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `sizes` | `str` | `'1000,5000,10000,25000,50000'` | no |
| `profile` | `str` | `'intradia'` | no |
| `entry` | `float | None` | `None` | no |
| `target` | `float | None` | `None` | no |
| `stop` | `float | None` | `None` | no |
| `size_usd` | `float | None` | `None` | no |
| `fee_bps_per_side` | `float | None` | `None` | no |
| `order_type` | `str | None` | `None` | no |
| `exchange` | `str | None` | `None` | no |
| `funding_bps` | `float | None` | `None` | no |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:5154 |
| `note` | literal en app/scalp_logic.py:5156 |
| `sizes_usd` | literal en app/scalp_logic.py:5153 |
| `stale_after_seconds` | literal en app/scalp_logic.py:5155 |
| `status` | literal en app/scalp_logic.py:5158 |
| `symbol` | literal en app/scalp_logic.py:5151 |
| `unit` | literal en app/scalp_logic.py:5152 |
| `venues` | literal en app/scalp_logic.py:5157 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:772`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - **PENDIENTE · ninguna funcion del arbol la escribe con SQL literal.**
    O la llena algo fuera de `app/` (migracion, colector externo, carga manual),
    o el SQL se construye en ejecucion y el analisis estatico no lo ve.
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:579`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:608`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:705`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:779`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_depth` — `sql/schema.sql:329`, 6 columnas
  - la llena `app.scalp_collector._write_ladders` (INSERT) — `app/scalp_collector.py:876`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:844`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:900`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:375`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:392`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

30 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._slippage_para` — `app/api.py:1428`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.execution_assessment` — `app/scalp_logic.py:4972`
- `app.scalp_logic.execution_cost` — `app/scalp_logic.py:5100`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`

<details><summary>Alcanzables de forma indirecta (23)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._banda` — `app/scalp_logic.py:4963`
- `app.scalp_logic._bps` — `app/scalp_logic.py:4956`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.scalp_logic.walk_book` — `app/scalp_logic.py:4878`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.oi_price_reading` — `app/setups.py:228`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `any`
- `app.state.pool.acquire`
- `float`
- `len`
- `part.strip`
- `sizes.split`
- `summary.get`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | — | `app/api.py:1393` | el propio handler |
| 422 | sizes debe ser una lista de numeros | `app/api.py:1399` | el propio handler |
| 422 | hasta 8 tamanios, cada uno entre 0 y 5.000.000 USD | `app/api.py:1401` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
