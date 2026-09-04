# `GET /api/positioning`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `positioning` · `app/api.py:1127` (cuerpo hasta la 1131) · decorador en la linea 1126.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

17 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `age_seconds` | literal en app/scalp_logic.py:5599 |
| `limitations` | literal en app/scalp_logic.py:5600 |
| `long_pct` | literal en app/scalp_logic.py:5585 |
| `median_sample` | literal en app/scalp_logic.py:5593 |
| `percentile_sample` | literal en app/scalp_logic.py:5594 |
| `ratio` | literal en app/scalp_logic.py:5587 |
| `ratio_24h_ago` | literal en app/scalp_logic.py:5588 |
| `ratio_change_24h` | literal en app/scalp_logic.py:5590 |
| `reason` | literal en app/scalp_logic.py:5562 |
| `sample_count` | literal en app/scalp_logic.py:5595 |
| `sample_days` | literal en app/scalp_logic.py:5596 |
| `sample_is_full_month` | literal en app/scalp_logic.py:5597 |
| `short_pct` | literal en app/scalp_logic.py:5586 |
| `status` | literal en app/scalp_logic.py:5583 |
| `symbol` | literal en app/scalp_logic.py:5582 |
| `ts` | literal en app/scalp_logic.py:5598 |
| `unit` | literal en app/scalp_logic.py:5584 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `long_short_ratio` — `sql/schema.sql:187`, 6 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:660`
  - la llena `app.ingest.upsert_long_short` (INSERT) — `app/ingest.py:356`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `max`
- `now`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.positioning_context` — `app/scalp_logic.py:5525`

<details><summary>Alcanzables de forma indirecta (1)</summary>

- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

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
