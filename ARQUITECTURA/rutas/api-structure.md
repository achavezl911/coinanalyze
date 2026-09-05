# `GET /api/structure`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `structure` · `app/api.py:1916` (cuerpo hasta la 1919) · decorador en la linea 1915.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

4 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `alignment` | literal en app/scalp_logic.py:1181 |
| `as_of` | literal en app/scalp_logic.py:1179 |
| `layers` | literal en app/scalp_logic.py:1180 |
| `symbol` | literal en app/scalp_logic.py:1178 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations` — `sql/schema.sql:174`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:657`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:316`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`

## Funciones que la componen

11 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.market_structure` — `app/scalp_logic.py:1026`

<details><summary>Alcanzables de forma indirecta (9)</summary>

- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._cvd_fut_window` — `app/scalp_logic.py:1006`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._pivot_structure` — `app/scalp_logic.py:936`
- `app.scalp_logic._sign_vote` — `app/scalp_logic.py:954`
- `app.scalp_logic._structure_layer` — `app/scalp_logic.py:982`
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
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 10 | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._cvd_fut_window` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._pivot_structure` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._sign_vote` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_layer` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.market_structure` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.structure` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
