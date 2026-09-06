# `GET /api/ai/profiles`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `ai_profiles` · `app/api.py:2762` (cuerpo hasta la 2782) · decorador en la linea 2761.

## Parametros de entrada

_ninguno_

## Campos que publica

14 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `endpoints` | literal en app/api.py:2778 |
| `profiles` | literal en app/api.py:2764 |
| `profiles.default` | literal en app/api.py:2766 |
| `profiles.default.purpose` | literal en app/api.py:2766 |
| `profiles.default.recommended_for` | literal en app/api.py:2766 |
| `profiles.lite` | literal en app/api.py:2765 |
| `profiles.lite.purpose` | literal en app/api.py:2765 |
| `profiles.lite.recommended_for` | literal en app/api.py:2765 |
| `profiles.max` | literal en app/api.py:2771 |
| `profiles.max.purpose` | literal en app/api.py:2772 |
| `profiles.max.recommended_for` | literal en app/api.py:2775 |
| `profiles.pro` | literal en app/api.py:2767 |
| `profiles.pro.purpose` | literal en app/api.py:2768 |
| `profiles.pro.recommended_for` | literal en app/api.py:2769 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

_ninguna consulta SQL literal en el cierre de esta ruta._

## Funciones que la componen

0 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

## Fallos que puede devolver

_no levanta HTTPException en su cierre. Un fallo aqui sale como 500 del framework._

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:60` | — |
| **readme** | — | `README.md:416`, `README.md:520` |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

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

**Declarada** en [`declarada/api-ai-profiles.md`](../declarada/api-ai-profiles.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.ai_profiles` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
