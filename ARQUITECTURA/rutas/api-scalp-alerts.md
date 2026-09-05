# `GET /api/scalp/alerts`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_alerts` · `app/api.py:1496` (cuerpo hasta la 1557) · decorador en la linea 1495.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

2 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `alerts` | literal en app/api.py:1557 |
| `symbol` | literal en app/api.py:1557 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:780`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:376`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:393`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `max`

## Funciones que la componen

26 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.statistical_alerts` — `app/api.py:1560`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.market_impact` — `app/scalp_logic.py:5420`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`

<details><summary>Alcanzables de forma indirecta (20)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.oi_price_reading` — `app/setups.py:228`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (6)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `alerts.append`
- `alerts.extend`
- `app.state.pool.acquire`
- `str`
- `summary.get`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

Radio por tabla calculado **hasta k=2**; lo que este mas arriba **no se afirma**.

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | por tabla | total | detalle |
|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | 9 | **44** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | 10 | **32** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 15 | 14 | **26** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 9 | 24 | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 9 | 24 | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 14 | 9 | **21** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 13 | 9 | **20** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.basis_quality` | 10 | 9 | **17** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 10 | 9 | **17** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 9 | 9 | **16** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 9 | 9 | **16** | [impacto](../impacto/app-setups.md) |
| `app.scalp_logic._as_utc_datetime` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._coverage_status` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._utc_now` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups._sign` | 9 | 0 | **9** | [impacto](../impacto/app-setups.md) |
| `app.scalp_logic.market_impact` | 4 | 0 | **4** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 2 mas_ | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
