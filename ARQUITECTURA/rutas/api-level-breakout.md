# `GET /api/level/breakout`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `level_breakout_endpoint` · `app/api.py:2021` (cuerpo hasta la 2033) · decorador en la linea 2020.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `level` | `Annotated[float, Query(gt=0)]` | — | si |
| `direction` | `str` | `'up'` | no |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | asignado en app/api.py:1956 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- devuelve la variable 'payload', cuyo contenido no se resuelve estaticamente

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

15 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.sella_respuesta` — `app/api.py:1944`
- `app.api.validate_symbol` — `app/api.py:229`
- `app.scalp_logic.level_breakout` — `app/scalp_logic.py:1637`

<details><summary>Alcanzables de forma indirecta (12)</summary>

- `app.api._utc_iso` — `app/api.py:2412`
- `app.breakout._atr` — `app/breakout.py:58`
- `app.breakout._confirmation_checks` — `app/breakout.py:330`
- `app.breakout._delta_usd` — `app/breakout.py:77`
- `app.breakout._rate` — `app/breakout.py:187`
- `app.breakout.attempt_features` — `app/breakout.py:149`
- `app.breakout.breakout_read` — `app/breakout.py:215`
- `app.breakout.build_corpus` — `app/breakout.py:173`
- `app.breakout.classify_outcome` — `app/breakout.py:125`
- `app.breakout.find_attempts` — `app/breakout.py:90`
- `app.breakout.wilson_ci` — `app/breakout.py:46`
- `app.interpretation.number` — `app/interpretation.py:10`

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
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |
| 422 | direction must be 'up' or 'down' | `app/api.py:2029` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:61`, `harness/checks/K43-foto-unica.sh:153`, `harness/checks/K43-foto-unica.sh:398` | `harness/checks/K43-foto-unica.sh:97` |
| **panel** | `static/app.js:3546` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['direction', 'level', 'symbol']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**Declarada** en [`declarada/api-level-breakout.md`](../declarada/api-level-breakout.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 63 | **0** | 0 | **63** | [impacto](../impacto/app-api.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.api._utc_iso` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-api.md) |
| `app.api.sella_respuesta` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.api.level_breakout_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.breakout._atr` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout._confirmation_checks` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout._delta_usd` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout._rate` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.attempt_features` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.breakout_read` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.build_corpus` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.classify_outcome` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.find_attempts` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.breakout.wilson_ci` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-breakout.md) |
| `app.scalp_logic.level_breakout` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-scalp_logic.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
