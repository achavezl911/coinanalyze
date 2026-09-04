# `GET /api/scalp/basis`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_basis` · `app/api.py:2510` (cuerpo hasta la 2513) · decorador en la linea 2509.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `symbol` | literal en app/scalp_logic.py:5414 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **item, que no se resuelve en el arbol: sus campos no se pueden derivar
- el objeto se expande con **quality, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:772`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:375`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:392`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.scalp_basis` — `app/scalp_logic.py:5382`

<details><summary>Alcanzables de forma indirecta (2)</summary>

- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`

</details>

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
