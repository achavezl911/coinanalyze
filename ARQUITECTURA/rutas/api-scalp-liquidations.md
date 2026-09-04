# `GET /api/scalp/liquidations`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_liquidations` · `app/api.py:1489` (cuerpo hasta la 1492) · decorador en la linea 1488.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

3 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `matrix` | literal en app/scalp_logic.py:5379 |
| `recent` | literal en app/scalp_logic.py:5379 |
| `symbol` | literal en app/scalp_logic.py:5379 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - **PENDIENTE · ninguna funcion del arbol la escribe con SQL literal.**
    O la llena algo fuera de `app/` (migracion, colector externo, carga manual),
    o el SQL se construye en ejecucion y el analisis estatico no lo ve.

## Funciones que la componen

2 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.scalp_liquidations` — `app/scalp_logic.py:5321`

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

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

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
