# `GET /api/oi-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `oi_context_endpoint` · `app/api.py:2331` (cuerpo hasta la 2334) · decorador en la linea 2330.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

16 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/scalp_logic.py:3426 |
| `by_venue` | literal en app/scalp_logic.py:3437 |
| `by_venue.binance_oi_usd` | literal en app/scalp_logic.py:3438 |
| `by_venue.bybit_oi_usd` | literal en app/scalp_logic.py:3439 |
| `by_venue.bybit_share_of_two_venues_pct` | literal en app/scalp_logic.py:3443 |
| `by_venue.note` | literal en app/scalp_logic.py:3446 |
| `by_venue.two_venue_total_usd` | literal en app/scalp_logic.py:3440 |
| `coverage` | literal en app/scalp_logic.py:3434 |
| `oi_latest_ts` | literal en app/scalp_logic.py:3431 |
| `oi_total_usd` | literal en app/scalp_logic.py:3427 |
| `percentile_1y` | literal en app/scalp_logic.py:3435 |
| `price_latest_ts` | literal en app/scalp_logic.py:3432 |
| `quadrant_note` | literal en app/scalp_logic.py:3450 |
| `symbol` | literal en app/scalp_logic.py:3425 |
| `windows` | literal en app/scalp_logic.py:3433 |
| `zscore_1y` | literal en app/scalp_logic.py:3436 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1123`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `oi_bybit` — `sql/schema.sql:198`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
- `open_interest` — `sql/schema.sql:184`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

## Funciones que la componen

12 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.oi_context` — `app/scalp_logic.py:3334`

<details><summary>Alcanzables de forma indirecta (10)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:72`
- `app.data_gaps._validated_window` — `app/data_gaps.py:78`
- `app.data_gaps.align_down` — `app/data_gaps.py:247`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:268`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:260`
- `app.scalp_logic._buckets_observados` — `app/scalp_logic.py:3291`
- `app.scalp_logic._oi_coverage` — `app/scalp_logic.py:3303`
- `app.scalp_logic._oi_quadrant` — `app/scalp_logic.py:3261`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1861`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K03-hueco-declarado.sh:47`, `harness/checks/K38-referencia-por-tiempo.sh:33`, `harness/checks/K38-referencia-por-tiempo.sh:34` | `harness/checks/K03-hueco-declarado.sh:30`, `harness/checks/K38-referencia-por-tiempo.sh:7`, `harness/checks/K43-control.bash:246` |
| **tests** | `tests/js/mesa_f12a.test.js:165` | `tests/test_oi_context_referencia.py:1` |

**No la llama el panel**, pero si 4 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `oi_latest_ts`
- `price_latest_ts`

## Capa DECLARADA

**Declarada** en [`declarada/api-oi-context.md`](../declarada/api-oi-context.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps._aware_utc` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.align_down` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._pct_rank` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._buckets_observados` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_coverage` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_quadrant` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.oi_context` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.oi_context_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
