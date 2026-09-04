# `GET /api/cross-asset`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `cross_asset_endpoint` · `app/api.py:1738` (cuerpo hasta la 1741) · decorador en la linea 1737.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3336 |
| `available` | literal en app/scalp_logic.py:3338 |
| `base` | literal en app/scalp_logic.py:3337 |
| `beta_vs_base` | literal en app/scalp_logic.py:3340 |
| `correlation` | literal en app/scalp_logic.py:3339 |
| `note` | literal en app/scalp_logic.py:3342 |
| `relative_strength_vs_base_pct` | literal en app/scalp_logic.py:3341 |
| `symbol` | literal en app/scalp_logic.py:3335 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`

## Funciones que la componen

9 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3304`

<details><summary>Alcanzables de forma indirecta (7)</summary>

- `app.scalp_logic._beta` — `app/scalp_logic.py:3269`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3283`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3256`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3248`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
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
