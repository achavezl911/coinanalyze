# `GET /api/verdicts`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `verdicts` · `app/api.py:1849` (cuerpo hasta la 1935) · decorador en la linea 1848.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `limit` | `Annotated[int, Query(ge=1, le=730)]` | `90` | no |
| `logic_version` | `Annotated[str, Query(min_length=1, max_length=80)]` | `DAILY_VERDICT_LOGIC_VERSION` | no |

## Campos que publica

5 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:1928 |
| `logic_version` | literal en app/api.py:1926 |
| `note` | literal en app/api.py:1929 |
| `rows` | literal en app/api.py:1927 |
| `symbol` | literal en app/api.py:1925 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_verdict_outcome` — `sql/schema.sql:2290`, 10 columnas
  - la llena `app.daily_agg.materialize_daily_verdict_outcomes` (INSERT) — `app/daily_agg.py:507`
- `daily_verdict_snapshot` — `sql/schema.sql:1099`, 26 columnas
  - la llena `app.daily_agg.persist_verdicts` (INSERT) — `app/daily_agg.py:418`

## Funciones que la componen

7 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._session_window` — `app/api.py:448`
- `app.api.records` — `app/api.py:235`
- `app.api.validate_symbol` — `app/api.py:222`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.metrics.session_bounds` — `app/metrics.py:31`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `date.fromisoformat`
- `fila.get`
- `len`
- `max`
- `min`
- `str`

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
| **checks** | `harness/checks/K43-foto-unica.sh:103` | `harness/checks/K43-foto-unica.sh:195` |
| **panel** | `static/app.js:1642` | — |
| **readme** | — | `README.md:72`, `README.md:276`, `README.md:410` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['limit']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-verdicts.md`](../declarada/api-verdicts.md) — pregunta del trader,
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
| `app.metrics.session_bounds` | 2 | **0** | 51 ↑ | **2** | [impacto](../impacto/app-metrics.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.api._session_window` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-api.md) |
| `app.api.verdicts` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
