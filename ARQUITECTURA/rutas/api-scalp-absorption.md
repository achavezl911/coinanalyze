# `GET /api/scalp/absorption`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_absorption` · `app/api.py:1480` (cuerpo hasta la 1485) · decorador en la linea 1479.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

**PENDIENTE · no se ha podido derivar ni un campo.**

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- lista vacia en el literal: no se puede derivar el elemento

Forma de la respuesta segun el AST: lista.

Tipo declarado en la firma: `list[dict[str, Any]]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:772`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:779`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `max`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.scalp_absorption` — `app/scalp_logic.py:5226`

<details><summary>Alcanzables de forma indirecta (6)</summary>

- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`

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
