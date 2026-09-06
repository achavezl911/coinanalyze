# `GET /api/scalp/orderbook`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_orderbook` · `app/api.py:1487` (cuerpo hasta la 1499) · decorador en la linea 1486.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

7 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `freshness` | literal en app/api.py:1498 |
| `freshness.age_seconds` | literal en app/ai_context.py:641 |
| `freshness.as_of` | literal en app/ai_context.py:640 |
| `freshness.max_age_seconds` | literal en app/ai_context.py:642 |
| `freshness.status` | literal en app/ai_context.py:639 |
| `rows` | literal en app/api.py:1497 |
| `symbol` | literal en app/api.py:1496 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.ai_context.orderbook_freshness` — `app/ai_context.py:634`
- `app.api.records` — `app/api.py:235`
- `app.api.validate_symbol` — `app/api.py:222`

<details><summary>Llamadas que salen del arbol o no se resuelven (4)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`
- `bool`
- `conn.fetch`
- `conn.fetchval`

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
| **checks** | `harness/checks/K13-vacio-o-rancio.sh:32`, `harness/checks/K13-vacio-o-rancio.sh:33`, `harness/checks/K13-vacio-o-rancio.sh:92`, `harness/checks/K13-vacio-o-rancio.sh:94` _(+4)_ | `harness/checks/K13-vacio-o-rancio.sh:2`, `harness/checks/K43-foto-unica.sh:44`, `harness/checks/K79-el-coste-calla-lo-que-le-falta.sh:71` |
| **panel** | `static/app.js:1576` | — |
| **tests** | — | `tests/js/libro_vacio_o_rancio.test.js:4`, `tests/test_orderbook_frescura.py:1`, `tests/test_orderbook_frescura.py:119` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `freshness.max_age_seconds`

## Capa DECLARADA

**Declarada** en [`declarada/api-scalp-orderbook.md`](../declarada/api-scalp-orderbook.md) — pregunta del trader,
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
| `app.ai_context.orderbook_freshness` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-ai_context.md) |
| `app.api.scalp_orderbook` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
