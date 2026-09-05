# `GET /api/price-barriers`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `price_barriers_endpoint` · `app/api.py:1644` (cuerpo hasta la 1647) · decorador en la linea 1643.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

15 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `active_zone` | literal en app/interpretation.py:1001 |
| `available` | literal en app/interpretation.py:998 |
| `current_price` | literal en app/interpretation.py:999 |
| `decision` | literal en app/interpretation.py:1000 |
| `intraday_source_interval` | literal en app/scalp_logic.py:1354 |
| `live_pressure` | literal en app/interpretation.py:1004 |
| `long_case` | literal en app/interpretation.py:1021 |
| `method` | literal en app/interpretation.py:1035 |
| `nearest_resistance` | literal en app/interpretation.py:1003 |
| `nearest_support` | literal en app/interpretation.py:1002 |
| `reason` | literal en app/interpretation.py:886 |
| `short_case` | literal en app/interpretation.py:1028 |
| `symbol` | literal en app/scalp_logic.py:1353 |
| `warning` | literal en app/interpretation.py:1057 |
| `warnings` | literal en app/interpretation.py:1048 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `futures_trades_agg` — `sql/schema.sql:273`, 9 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1538`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:802`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `spot_trades_agg` — `sql/schema.sql:198`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1235`

<details><summary>Alcanzables de forma indirecta (6)</summary>

- `app.interpretation._barrier_candidates` — `app/interpretation.py:684`
- `app.interpretation._barrier_zones` — `app/interpretation.py:779`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.interpretation.price_barrier_read` — `app/interpretation.py:877`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

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

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 9 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.interpretation._barrier_candidates` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation._barrier_zones` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation.price_barrier_read` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.price_barriers` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.price_barriers_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
