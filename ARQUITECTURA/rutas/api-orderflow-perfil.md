# `GET /api/orderflow/perfil`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `orderflow_perfil` · `app/api.py:3759` (cuerpo hasta la 3771) · decorador en la linea 3758.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `desde` | `str | None` | `None` | no |
| `hasta` | `str | None` | `None` | no |
| `paso` | `str | None` | `None` | no |
| `venues` | `str | None` | `None` | no |
| `unidad` | `str | None` | `None` | no |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:3733 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **respuesta, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

_ninguna consulta SQL literal en el cierre de esta ruta._

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._orderflow` — `app/api.py:3724`

<details><summary>Alcanzables de forma indirecta (2)</summary>

- `app.api._utc_iso` — `app/api.py:2467`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2587`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 422 | — | `app/api.py:2596` | una funcion de su cierre |
| 422 | — | `app/api.py:3732` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K108-orderflow.py:718`, `harness/checks/K108-orderflow.py:720`, `harness/checks/K109-banco.py:74` | — |

**No la llama el panel**, pero si 3 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['desde', 'hasta', 'paso', 'symbol', 'unidad', 'venues']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**PENDIENTE de declaracion.** No existe `declarada/api-orderflow-perfil.md`.

Que pregunta del trader contesta, a que familia de ventana pertenece y que
promete NO se derivan del codigo: se escriben a mano. Mientras no esten, esta
ruta esta descrita pero **no declarada**, y K88 la cuenta.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api._utc_iso` | 21 | **0** | 0 | **21** | [impacto](../impacto/app-api.md) |
| `app.api.rechaza_parametros_desconocidos` | 21 | **0** | 0 | **21** | [impacto](../impacto/app-api.md) |
| `app.api._orderflow` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-api.md) |
| `app.api.orderflow_perfil` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
