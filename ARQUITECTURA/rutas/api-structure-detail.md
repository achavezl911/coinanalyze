# `GET /api/structure-detail`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `structure_detail_endpoint` · `app/api.py:1788` (cuerpo hasta la 1791) · decorador en la linea 1787.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

3 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:2318 |
| `horizons` | literal en app/scalp_logic.py:2318 |
| `symbol` | literal en app/scalp_logic.py:2318 |

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

## Funciones que la componen

11 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2283`

<details><summary>Alcanzables de forma indirecta (9)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2275`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2226`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2212`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`

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
| `app.scalp_logic.resolve_matrix_as_of` | 24 | 10 | **32** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 15 | 14 | **26** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 10 | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_from_swings` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._swings` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.structure_detail` | 7 | 3 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._dsr` | 7 | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.structure_detail_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
