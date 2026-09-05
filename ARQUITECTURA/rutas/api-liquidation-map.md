# `GET /api/liquidation-map`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `liquidation_map_endpoint` · `app/api.py:1610` (cuerpo hasta la 1613) · decorador en la linea 1609.

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

- `app.api.validate_symbol` — `app/api.py:222`
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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K42-mapa-liquidaciones-cuadra.sh:43`, `harness/checks/K42-mapa-liquidaciones-cuadra.sh:44` | `harness/checks/K42-mapa-liquidaciones-cuadra.sh:8`, `harness/checks/K80-la-matriz-cambia-de-universo.sh:31` |
| **tests** | — | `tests/test_liquidation_map_ventana.py:1` |

**No la llama el panel**, pero si 2 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `window_end`
- `window_minutes`
- `window_notional`
- `window_start`

## Capa DECLARADA

**Declarada** en [`declarada/api-liquidation-map.md`](../declarada/api-liquidation-map.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._atr` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._tr_series` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.liquidation_map` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.liquidation_map_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
