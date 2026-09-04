# `GET /api/wyckoff`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `wyckoff_endpoint` · `app/api.py:1716` (cuerpo hasta la 1720) · decorador en la linea 1715.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

10 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/wyckoff.py:481 |
| `bias` | literal en app/wyckoff.py:483 |
| `chart_bars` | literal en app/wyckoff.py:505 |
| `current` | literal en app/wyckoff.py:486 |
| `events` | literal en app/wyckoff.py:485 |
| `method` | literal en app/wyckoff.py:506 |
| `phase` | literal en app/wyckoff.py:484 |
| `range` | literal en app/wyckoff.py:482 |
| `symbol` | literal en app/scalp_logic.py:1629 |
| `trade_map` | literal en app/wyckoff.py:491 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- por **wyckoff_auto_read: el objeto se expande con **expresion, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:205`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`

## Funciones que la componen

22 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.wyckoff_context` — `app/scalp_logic.py:1606`

<details><summary>Alcanzables de forma indirecta (20)</summary>

- `app.interpretation.number` — `app/interpretation.py:10`
- `app.wyckoff._atr_abs` — `app/wyckoff.py:183`
- `app.wyckoff._bar_date` — `app/wyckoff.py:42`
- `app.wyckoff._bias_read` — `app/wyckoff.py:263`
- `app.wyckoff._candidate_rank` — `app/wyckoff.py:83`
- `app.wyckoff._clamp` — `app/wyckoff.py:25`
- `app.wyckoff._clean_bars` — `app/wyckoff.py:54`
- `app.wyckoff._events` — `app/wyckoff.py:197`
- `app.wyckoff._phase` — `app/wyckoff.py:401`
- `app.wyckoff._quantile` — `app/wyckoff.py:29`
- `app.wyckoff._range_bounds` — `app/wyckoff.py:66`
- `app.wyckoff._session_date` — `app/wyckoff.py:251`
- `app.wyckoff._signed_balance` — `app/wyckoff.py:178`
- `app.wyckoff.detect_latest_range` — `app/wyckoff.py:99`
- `app.wyckoff.wyckoff_auto_read` — `app/wyckoff.py:447`
- `app.zones._atr_abs` — `app/zones.py:519`
- `app.zones._edge_episodes` — `app/zones.py:499`
- `app.zones._ols_slope` — `app/zones.py:471`
- `app.zones._rotations` — `app/zones.py:483`
- `app.zones.range_validate_read` — `app/zones.py:535`

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
