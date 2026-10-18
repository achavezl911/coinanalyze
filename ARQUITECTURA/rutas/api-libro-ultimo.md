# `GET /api/libro/ultimo`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `libro_ultimo` · `app/api.py:3927` (cuerpo hasta la 3940) · decorador en la linea 3926.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `venues` | `str | None` | `None` | no |
| `paso` | `str | None` | `None` | no |
| `niveles` | `str | None` | `None` | no |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:3940 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **respuesta, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `orderflow_paso` — `sql/schema.sql:2934`, 2 columnas
  - **PENDIENTE · ninguna funcion del arbol la escribe con SQL literal.**
    O la llena algo fuera de `app/` (migracion, colector externo, carga manual),
    o el SQL se construye en ejecucion y el analisis estatico no lo ve.

## Funciones que la componen

13 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2467`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2587`
- `app.libro_lectura.ultimo` — `app/libro_lectura.py:373`

<details><summary>Alcanzables de forma indirecta (10)</summary>

- `app.libro_lectura._escalera` — `app/libro_lectura.py:263`
- `app.libro_lectura.mensaje` — `app/libro_lectura.py:280`
- `app.libro_lectura.parametros` — `app/libro_lectura.py:291`
- `app.libro_lectura.paso_de` — `app/libro_lectura.py:58`
- `app.libro_lectura.reagrega` — `app/libro_lectura.py:70`
- `app.libro_lectura.venues_de` — `app/libro_lectura.py:48`
- `app.orderflow.nivel_de` — `app/orderflow.py:270`
- `app.orderflow_lectura.activo_de` — `app/orderflow_lectura.py:71`
- `app.orderflow_lectura.pasos` — `app/orderflow_lectura.py:96`
- `app.orderflow_lectura.texto` — `app/orderflow_lectura.py:49`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `datetime.now`
- `str`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 422 | — | `app/api.py:2596` | una funcion de su cierre |
| 422 | — | `app/api.py:3939` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K110-control.bash:178`, `harness/checks/K110-control.bash:182` | `harness/checks/K110-libro.py:561`, `harness/checks/K111-banco.py:21`, `harness/checks/K111-banco.py:183` |
| **tests** | `tests/test_libro.py:587` | — |

**No la llama el panel**, pero si 3 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['niveles', 'paso', 'symbol', 'venues']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**PENDIENTE de declaracion.** No existe `declarada/api-libro-ultimo.md`.

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
| `app.api._utc_iso` | 22 | **0** | 0 | **22** | [impacto](../impacto/app-api.md) |
| `app.api.rechaza_parametros_desconocidos` | 22 | **0** | 0 | **22** | [impacto](../impacto/app-api.md) |
| `app.api.libro_ultimo` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.libro_lectura._escalera` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.mensaje` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.parametros` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.paso_de` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.reagrega` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.ultimo` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.libro_lectura.venues_de` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-libro_lectura.md) |
| `app.orderflow.nivel_de` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-orderflow.md) |
| `app.orderflow_lectura.activo_de` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-orderflow_lectura.md) |
| `app.orderflow_lectura.pasos` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-orderflow_lectura.md) |
| `app.orderflow_lectura.texto` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-orderflow_lectura.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
