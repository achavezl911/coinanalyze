# `GET /api/wyckoff`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `wyckoff_endpoint` · `app/api.py:1717` (cuerpo hasta la 1721) · decorador en la linea 1716.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

10 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/wyckoff.py:481 |
| `bias` | literal en app/wyckoff.py:483 |
| `chart_bars` | literal en app/wyckoff.py:505 |
| `current` | literal en app/wyckoff.py:486 |
| `events` | literal en app/wyckoff.py:485 |
| `method` | literal en app/wyckoff.py:506 |
| `phase` | literal en app/wyckoff.py:484 |
| `range` | literal en app/wyckoff.py:482 |
| `symbol` | literal en app/scalp_logic.py:1629 |
| `trade_map` | literal en app/wyckoff.py:491 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- por **wyckoff_auto_read: el objeto se expande con **expresion, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

22 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.wyckoff_context` — `app/scalp_logic.py:1606`

<details><summary>Alcanzables de forma indirecta (20)</summary>

- `app.interpretation.number` — `app/interpretation.py:10`
- `app.wyckoff._atr_abs` — `app/wyckoff.py:183`
- `app.wyckoff._bar_date` — `app/wyckoff.py:42`
- `app.wyckoff._bias_read` — `app/wyckoff.py:263`
- `app.wyckoff._candidate_rank` — `app/wyckoff.py:83`
- `app.wyckoff._clamp` — `app/wyckoff.py:25`
- `app.wyckoff._clean_bars` — `app/wyckoff.py:54`
- `app.wyckoff._events` — `app/wyckoff.py:197`
- `app.wyckoff._phase` — `app/wyckoff.py:401`
- `app.wyckoff._quantile` — `app/wyckoff.py:29`
- `app.wyckoff._range_bounds` — `app/wyckoff.py:66`
- `app.wyckoff._session_date` — `app/wyckoff.py:251`
- `app.wyckoff._signed_balance` — `app/wyckoff.py:178`
- `app.wyckoff.detect_latest_range` — `app/wyckoff.py:99`
- `app.wyckoff.wyckoff_auto_read` — `app/wyckoff.py:447`
- `app.zones._atr_abs` — `app/zones.py:519`
- `app.zones._edge_episodes` — `app/zones.py:499`
- `app.zones._ols_slope` — `app/zones.py:471`
- `app.zones._rotations` — `app/zones.py:483`
- `app.zones.range_validate_read` — `app/zones.py:535`

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
| **checks** | `harness/checks/K43-foto-unica.sh:101`, `harness/checks/K43-foto-unica.sh:155` | — |
| **panel** | `static/app.js:1493`, `static/app.js:1595` | — |
| **readme** | — | `README.md:149` |
| **tests** | `tests/test_wyckoff.py:106` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-wyckoff.md`](../declarada/api-wyckoff.md) — pregunta del trader,
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
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.zones._atr_abs` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-zones.md) |
| `app.zones._edge_episodes` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-zones.md) |
| `app.zones._ols_slope` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-zones.md) |
| `app.zones._rotations` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-zones.md) |
| `app.zones.range_validate_read` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-zones.md) |
| `app.scalp_logic.wyckoff_context` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.wyckoff._atr_abs` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._bar_date` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._bias_read` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._candidate_rank` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._clamp` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._clean_bars` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._events` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._phase` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._quantile` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._range_bounds` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._session_date` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff._signed_balance` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff.detect_latest_range` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.wyckoff.wyckoff_auto_read` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-wyckoff.md) |
| `app.api.wyckoff_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
