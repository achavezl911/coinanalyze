# `GET /api/ai/profiles`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `ai_profiles` · `app/api.py:2628` (cuerpo hasta la 2648) · decorador en la linea 2627.

## Parametros de entrada

_ninguno_

## Campos que publica

2 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `endpoints` | literal en app/api.py:2644 |
| `profiles` | literal en app/api.py:2630 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

_ninguna consulta SQL literal en el cierre de esta ruta._

## Funciones que la componen

0 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

## Fallos que puede devolver

_no levanta HTTPException en su cierre. Un fallo aqui sale como 500 del framework._

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

Radio por tabla calculado **hasta k=2**; lo que este mas arriba **no se afirma**.

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | por tabla | total | detalle |
|---|---|---|---|---|
| `app.api.ai_profiles` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
