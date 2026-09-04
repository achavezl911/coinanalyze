# `GET /api/funding-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `funding_context_endpoint` · `app/api.py:1602` (cuerpo hasta la 1605) · decorador en la linea 1601.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

10 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `annualized_pct` | literal en app/scalp_logic.py:3405 |
| `coverage` | literal en app/scalp_logic.py:3407 |
| `current_pct` | literal en app/scalp_logic.py:3400 |
| `divergence_pred_minus_current` | literal en app/scalp_logic.py:3402 |
| `history_avg_pct` | literal en app/scalp_logic.py:3406 |
| `next_funding_time_utc` | literal en app/scalp_logic.py:3408 |
| `note` | literal en app/scalp_logic.py:3416 |
| `predicted_pct` | literal en app/scalp_logic.py:3401 |
| `regime` | literal en app/scalp_logic.py:3409 |
| `symbol` | literal en app/scalp_logic.py:3399 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:651`
- `predicted_funding_rate` — `sql/schema.sql:160`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:654`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.funding_context` — `app/scalp_logic.py:3347`

<details><summary>Alcanzables de forma indirecta (6)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.align_down` — `app/data_gaps.py:232`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`
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
