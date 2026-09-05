# `GET /api/scalp/signals`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_signals` · `app/api.py:2023` (cuerpo hasta la 2042) · decorador en la linea 2022.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `limit` | `Annotated[int, Query(ge=1, le=1000)]` | `200` | no |

## Campos que publica

2 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `rows` | literal en app/api.py:2042 |
| `symbol` | literal en app/api.py:2042 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `scalp_signal_snapshot` — `sql/schema.sql:381`, 16 columnas
  - la llena `app.scalp_collector.persist_scalp_signals` (INSERT) — `app/scalp_collector.py:1406`

## Funciones que la componen

2 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `conn.fetch`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

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
| `app.api.scalp_signals` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
