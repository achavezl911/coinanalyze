# `GET /api/zone/analysis`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `zone_analysis_endpoint` · `app/api.py:1651` (cuerpo hasta la 1664) · decorador en la linea 1650.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `low` | `Annotated[float, Query(gt=0)]` | — | si |
| `high` | `Annotated[float, Query(gt=0)]` | — | si |
| `days` | `Annotated[int, Query(ge=7, le=365)]` | `365` | no |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `lookback_days` | literal en app/scalp_logic.py:1486 |
| `scored_visits` | literal en app/scalp_logic.py:1489 |
| `sources` | literal en app/scalp_logic.py:1495 |
| `summary` | literal en app/scalp_logic.py:1490 |
| `symbol` | literal en app/scalp_logic.py:1484 |
| `visit_count` | literal en app/scalp_logic.py:1488 |
| `visits` | literal en app/scalp_logic.py:1487 |
| `zone` | literal en app/scalp_logic.py:1485 |

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

12 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.zone_analysis` — `app/scalp_logic.py:1364`

<details><summary>Alcanzables de forma indirecta (10)</summary>

- `app.interpretation.number` — `app/interpretation.py:10`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.zones._atr_pct` — `app/zones.py:104`
- `app.zones._clamp` — `app/zones.py:100`
- `app.zones._effort_result` — `app/zones.py:128`
- `app.zones._narrative` — `app/zones.py:394`
- `app.zones._oi_behaviour` — `app/zones.py:208`
- `app.zones._percentile` — `app/zones.py:121`
- `app.zones._rejection` — `app/zones.py:194`
- `app.zones.zone_character_read` — `app/zones.py:220`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | low must be below high | `app/api.py:1660` | el propio handler |
| 422 | zone spans more than 3x; narrow it | `app/api.py:1662` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
