# `GET /api/stream`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `stream` · `app/api.py:3314` (cuerpo hasta la 3319) · decorador en la linea 3313.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |

## Campos que publica

**PENDIENTE · no se ha podido derivar ni un campo.**

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por StreamingResponse(), que no se puede seguir
- la funcion no tiene ningun return explicito

Tipo declarado en la firma: `StreamingResponse`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:784`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:856`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:912`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:391`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:408`

## Funciones que la componen

2 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.stream_generator` — `app/api.py:3266`

<details><summary>Alcanzables de forma indirecta (1)</summary>

- `app.api.records` — `app/api.py:235`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `StreamingResponse`

</details>

## Fallos que puede devolver

_no levanta HTTPException en su cierre. Un fallo aqui sale como 500 del framework._

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K20-cincoxx.sh:126`, `harness/checks/K31-eslabon5.sh:60`, `harness/checks/K43-foto-unica.sh:106` | `harness/checks/K20-cincoxx.sh:124`, `harness/checks/K31-eslabon5.sh:57` |
| **panel** | `static/app.js:1741` | — |
| **readme** | — | `README.md:412` |

**La llama el panel: es superficie de producto.**

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

**Declarada** en [`declarada/api-stream.md`](../declarada/api-stream.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.api.stream` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.api.stream_generator` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
