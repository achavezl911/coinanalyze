# `GET /api/range/validate`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `range_validate_endpoint` · `app/api.py:1691` (cuerpo hasta la 1721) · decorador en la linea 1690.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `low` | `Annotated[float, Query(gt=0)]` | — | si |
| `high` | `Annotated[float, Query(gt=0)]` | — | si |
| `days` | `Annotated[int, Query(ge=40, le=730)]` | `180` | no |
| `end_days_ago` | `Annotated[int, Query(ge=0, le=690)]` | `0` | no |
| `start_date` | `date | None` | `None` | no |
| `end_date` | `date | None` | `None` | no |

## Campos que publica

5 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `from` | literal en app/scalp_logic.py:1599 |
| `prior_bars` | literal en app/scalp_logic.py:1601 |
| `symbol` | literal en app/scalp_logic.py:1596 |
| `to` | literal en app/scalp_logic.py:1600 |
| `window_days` | literal en app/scalp_logic.py:1598 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **window, que no se resuelve en el arbol: sus campos no se pueden derivar
- el objeto se expande con **result, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.range_validate` — `app/scalp_logic.py:1507`

<details><summary>Alcanzables de forma indirecta (6)</summary>

- `app.interpretation.number` — `app/interpretation.py:10`
- `app.zones._atr_abs` — `app/zones.py:519`
- `app.zones._edge_episodes` — `app/zones.py:499`
- `app.zones._ols_slope` — `app/zones.py:471`
- `app.zones._rotations` — `app/zones.py:483`
- `app.zones.range_validate_read` — `app/zones.py:535`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | low must be below high | `app/api.py:1706` | el propio handler |
| 422 | range spans more than 3x; narrow it | `app/api.py:1708` | el propio handler |
| 422 | start_date and end_date must come together | `app/api.py:1710` | el propio handler |
| 422 | start_date must be before end_date | `app/api.py:1713` | el propio handler |
| 422 | span exceeds the 730 days of history | `app/api.py:1715` | el propio handler |
| 422 | days + end_days_ago exceeds daily history | `app/api.py:1717` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:61`, `harness/checks/K43-foto-unica.sh:104`, `harness/checks/K76-la-ventana-que-pides.sh:97` | — |
| **panel** | `static/app.js:2902` | — |
| **tests** | — | `tests/test_p0_data_integrity.py:126` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['days']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `from`
- `to`
- `window_days`

## Capa DECLARADA

**Declarada** en [`declarada/api-range-validate.md`](../declarada/api-range-validate.md) — pregunta del trader,
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
| `app.api.range_validate_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.range_validate` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-scalp_logic.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
