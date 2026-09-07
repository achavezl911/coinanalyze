# `GET /api/signals/ledger`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `signals_ledger` · `app/api.py:2143` (cuerpo hasta la 2207) · decorador en la linea 2142.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `since` | `str | None` | `None` | no |
| `until` | `str | None` | `None` | no |
| `limit` | `Annotated[int, Query(ge=1, le=5000)]` | `1000` | no |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:2202 |
| `count` | literal en app/api.py:2204 |
| `limit` | literal en app/api.py:2203 |
| `observations` | literal en app/api.py:2206 |
| `since` | literal en app/api.py:2199 |
| `symbol` | literal en app/api.py:2198 |
| `truncated` | literal en app/api.py:2205 |
| `until` | literal en app/api.py:2200 |
| `ventana_maxima_h` | literal en app/api.py:2201 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `signal_observation` — `sql/schema.sql:415`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:371`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2087`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2127`
- `app.api.records` — `app/api.py:235`
- `app.api.validate_symbol` — `app/api.py:222`

<details><summary>Llamadas que salen del arbol o no se resuelven (10)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `LEDGER_MAX_WINDOW.total_seconds`
- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `datetime.fromisoformat`
- `datetime.now`
- `int`
- `len`
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | — | `app/api.py:2136` | una funcion de su cierre |
| 422 | — | `app/api.py:2164` | el propio handler |
| 422 | since/until necesitan zona horaria explicita | `app/api.py:2166` | el propio handler |
| 422 | until tiene que ser posterior a since | `app/api.py:2168` | el propio handler |
| 422 | — | `app/api.py:2170` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K21-ledger-de-senales.sh:32`, `harness/checks/K24-replay-del-contexto.sh:88`, `harness/checks/K43-control.bash:80`, `harness/checks/K43-foto-unica.sh:122` | `harness/checks/K24-replay-del-contexto.sh:19`, `harness/checks/K31-cubos.py:145`, `harness/checks/K88-control.bash:477` |
| **panel** | `static/app.js:1710` | — |
| **tests** | — | `tests/test_signals_ledger.py:1` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **3** — pide ['since']: el operador elige el momento.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `since`
- `until`

## Capa DECLARADA

**Declarada** en [`declarada/api-signals-ledger.md`](../declarada/api-signals-ledger.md) — pregunta del trader,
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
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.api._utc_iso` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.rechaza_parametros_desconocidos` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-api.md) |
| `app.api.signals_ledger` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
