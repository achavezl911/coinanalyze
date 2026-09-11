# `GET /api/signals/outcomes`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `signals_outcomes` · `app/api.py:2679` (cuerpo hasta la 2751) · decorador en la linea 2678.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `since` | `str | None` | `None` | no |
| `until` | `str | None` | `None` | no |
| `horizon` | `Annotated[int | None, Query()]` | `None` | no |
| `limit` | `Annotated[int, Query(ge=1, le=5000)]` | `1000` | no |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `count` | literal en app/api.py:2748 |
| `horizon` | literal en app/api.py:2746 |
| `limit` | literal en app/api.py:2747 |
| `outcomes` | literal en app/api.py:2750 |
| `since` | literal en app/api.py:2744 |
| `symbol` | literal en app/api.py:2743 |
| `truncated` | literal en app/api.py:2749 |
| `until` | literal en app/api.py:2745 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `signal_observation` — `sql/schema.sql:415`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:371`
- `signal_outcome` — `sql/schema.sql:565`, 27 columnas
  - la llena `app.signal_outcomes.schedule_signal_outcomes` (INSERT) — `app/signal_outcomes.py:169`
  - la llena `app.signal_outcomes._finalize_not_evaluable` (UPDATE) — `app/signal_outcomes.py:199`
  - la llena `app.signal_outcomes._defer_missing_path` (UPDATE) — `app/signal_outcomes.py:226`
  - la llena `app.signal_outcomes._finalize_evaluated` (UPDATE) — `app/signal_outcomes.py:252`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2412`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2532`
- `app.api.records` — `app/api.py:242`
- `app.api.validate_symbol` — `app/api.py:229`

<details><summary>Llamadas que salen del arbol o no se resuelven (11)</summary>

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
- `list`
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |
| 422 | — | `app/api.py:2541` | una funcion de su cierre |
| 422 | — | `app/api.py:2700` | el propio handler |
| 422 | — | `app/api.py:2708` | el propio handler |
| 422 | since/until necesitan zona horaria explicita | `app/api.py:2710` | el propio handler |
| 422 | until tiene que ser posterior a since | `app/api.py:2712` | el propio handler |
| 422 | — | `app/api.py:2714` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K22-resultado-por-horizonte.sh:29` | `harness/checks/K31-cubos.py:145` |
| **tests** | — | `tests/test_dashboard_layout.py:223`, `tests/test_familia_demanda.py:126`, `tests/test_signals_outcomes.py:1` |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **3** — pide ['since']: el operador elige el momento.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `since`
- `until`

## Capa DECLARADA

**Declarada** en [`declarada/api-signals-outcomes.md`](../declarada/api-signals-outcomes.md) — pregunta del trader,
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
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.api._utc_iso` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-api.md) |
| `app.api.rechaza_parametros_desconocidos` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.signals_outcomes` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
