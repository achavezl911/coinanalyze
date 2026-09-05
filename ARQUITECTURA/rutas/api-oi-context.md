# `GET /api/oi-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `oi_context_endpoint` · `app/api.py:1745` (cuerpo hasta la 1748) · decorador en la linea 1744.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

11 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/scalp_logic.py:3113 |
| `by_venue` | literal en app/scalp_logic.py:3124 |
| `coverage` | literal en app/scalp_logic.py:3121 |
| `oi_latest_ts` | literal en app/scalp_logic.py:3118 |
| `oi_total_usd` | literal en app/scalp_logic.py:3114 |
| `percentile_1y` | literal en app/scalp_logic.py:3122 |
| `price_latest_ts` | literal en app/scalp_logic.py:3119 |
| `quadrant_note` | literal en app/scalp_logic.py:3137 |
| `symbol` | literal en app/scalp_logic.py:3112 |
| `windows` | literal en app/scalp_logic.py:3120 |
| `zscore_1y` | literal en app/scalp_logic.py:3123 |

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
- `oi_bybit` — `sql/schema.sql:97`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:648`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`

## Funciones que la componen

12 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.oi_context` — `app/scalp_logic.py:3021`

<details><summary>Alcanzables de forma indirecta (10)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.align_down` — `app/data_gaps.py:232`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`
- `app.scalp_logic._buckets_observados` — `app/scalp_logic.py:2978`
- `app.scalp_logic._oi_coverage` — `app/scalp_logic.py:2990`
- `app.scalp_logic._oi_quadrant` — `app/scalp_logic.py:2948`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1742`
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
| `app.data_gaps._aware_utc` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | 21 | **24** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._pct_rank` | 7 | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.align_down` | 4 | 0 | **4** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._buckets_observados` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_coverage` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_quadrant` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.oi_context` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.oi_context_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
