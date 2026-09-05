# `GET /api/setup`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `setup` · `app/api.py:2008` (cuerpo hasta la 2019) · decorador en la linea 2007.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `daily_flow_source` | literal en app/interpretation.py:201 |
| `daily_slope` | literal en app/interpretation.py:200 |
| `daily_streak` | literal en app/interpretation.py:199 |
| `primary` | literal en app/interpretation.py:202 |
| `setups` | literal en app/interpretation.py:203 |
| `snapshot_ts` | literal en app/api.py:2017 |
| `symbol` | literal en app/api.py:2016 |
| `warning` | literal en app/interpretation.py:204 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.daily_data` — `app/api.py:493`
- `app.api.latest_snapshot` — `app/api.py:466`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.interpretation.evaluate_setups` — `app/interpretation.py:139`

<details><summary>Alcanzables de forma indirecta (4)</summary>

- `app.api.records` — `app/api.py:234`
- `app.interpretation.daily_flow_read` — `app/interpretation.py:208`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | No data | `app/api.py:2013` | el propio handler |
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K88-control.bash:139`, `harness/checks/K88-control.bash:140`, `harness/checks/K88-control.bash:397` |
| **readme** | — | `README.md:411` |

**Nadie la llama.** Sus 4 rastros son todos MENCION -comentario,
docstring o documento-. Es la forma del patron que en esta casa se ha repetido
nueve veces: algo de lo que se habla y nadie ejecuta. **Merece una mirada.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `snapshot_ts`

## Capa DECLARADA

**Declarada** en [`declarada/api-setup.md`](../declarada/api-setup.md) — pregunta del trader,
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
| `app.interpretation.evaluate_setups` | 4 | **0** | 51 ↑ | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 9 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.api.daily_data` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.api.latest_snapshot` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.interpretation.daily_flow_read` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-interpretation.md) |
| `app.api.setup` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
