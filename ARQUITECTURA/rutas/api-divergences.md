# `GET /api/divergences`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `divergences_endpoint` · `app/api.py:1812` (cuerpo hasta la 1815) · decorador en la linea 1811.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/scalp_logic.py:2195 |
| `intraday` | literal en app/scalp_logic.py:2201 |
| `note` | literal en app/scalp_logic.py:2202 |
| `sessions` | literal en app/scalp_logic.py:2196 |
| `summary` | literal en app/scalp_logic.py:2198 |
| `sustained_windows_evaluated` | literal en app/scalp_logic.py:2200 |
| `symbol` | literal en app/scalp_logic.py:2194 |
| `windows` | literal en app/scalp_logic.py:2197 |
| `windows_confirming` | literal en app/scalp_logic.py:2199 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `spot_trades_agg` — `sql/schema.sql:198`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

7 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.divergence_scan` — `app/scalp_logic.py:2073`

<details><summary>Alcanzables de forma indirecta (5)</summary>

- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._intraday_divergences` — `app/scalp_logic.py:1958`
- `app.scalp_logic._return_stdev_pct` — `app/scalp_logic.py:1945`
- `app.scalp_logic._slope_pct` — `app/scalp_logic.py:1913`
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

Radio por tabla calculado **hasta k=2**; lo que este mas arriba **no se afirma**.

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | por tabla | total | detalle |
|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | 9 | **44** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._intraday_divergences` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._return_stdev_pct` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._slope_pct` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.divergence_scan` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.divergences_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
