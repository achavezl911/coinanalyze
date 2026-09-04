# `GET /api/passive-flow`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `passive_flow_endpoint` · `app/api.py:1773` (cuerpo hasta la 1776) · decorador en la linea 1772.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:5822 |
| `counts` | literal en app/scalp_logic.py:5828 |
| `horizons` | literal en app/scalp_logic.py:5826 |
| `location` | literal en app/scalp_logic.py:5824 |
| `note` | literal en app/scalp_logic.py:5829 |
| `price` | literal en app/scalp_logic.py:5823 |
| `summary` | literal en app/scalp_logic.py:5827 |
| `symbol` | literal en app/scalp_logic.py:5821 |
| `value_area` | literal en app/scalp_logic.py:5825 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1091`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1242`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1261`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1310`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:321`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:583`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:662`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:686`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:722`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:763`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:792`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:861`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `choice`
- `edges`
- `exchanges`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

20 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:5728`

<details><summary>Alcanzables de forma indirecta (18)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.scalp_logic._atr` — `app/scalp_logic.py:2926`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:5695`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2431`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4071`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4041`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4053`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4245`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3502`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4161`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:2915`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4419`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2609`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3539`

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
