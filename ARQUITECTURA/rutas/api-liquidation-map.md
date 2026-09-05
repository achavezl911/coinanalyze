# `GET /api/liquidation-map`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `liquidation_map_endpoint` · `app/api.py:1609` (cuerpo hasta la 1612) · decorador en la linea 1608.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

16 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3482 |
| `atr_1h` | literal en app/scalp_logic.py:3481 |
| `available` | literal en app/scalp_logic.py:3478 |
| `bucket_size` | literal en app/scalp_logic.py:3486 |
| `buckets_total` | literal en app/scalp_logic.py:3491 |
| `cumulative_within_band` | literal en app/scalp_logic.py:3495 |
| `current_price` | literal en app/scalp_logic.py:3480 |
| `levels` | literal en app/scalp_logic.py:3494 |
| `levels_shown` | literal en app/scalp_logic.py:3492 |
| `note` | literal en app/scalp_logic.py:3496 |
| `symbol` | literal en app/scalp_logic.py:3477 |
| `type` | literal en app/scalp_logic.py:3479 |
| `window_end` | literal en app/scalp_logic.py:3484 |
| `window_minutes` | literal en app/scalp_logic.py:3485 |
| `window_notional` | literal en app/scalp_logic.py:3493 |
| `window_start` | literal en app/scalp_logic.py:3483 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

6 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.liquidation_map` — `app/scalp_logic.py:3420`

<details><summary>Alcanzables de forma indirecta (4)</summary>

- `app.scalp_logic._atr` — `app/scalp_logic.py:2926`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:2915`
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
| `app.scalp_logic._resample_highs_lows` | 14 | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._atr` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._tr_series` | 9 | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.liquidation_map` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.liquidation_map_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
