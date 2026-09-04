# `GET /api/scalp/summary`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_summary` · `app/api.py:1084` (cuerpo hasta la 1088) · decorador en la linea 1083.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

58 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `absorption` | literal en app/scalp_logic.py:914 |
| `absorption_context` | literal en app/scalp_logic.py:916 |
| `absorption_delta_ratio` | literal en app/scalp_logic.py:915 |
| `basis_bps` | literal en app/scalp_logic.py:866 |
| `basis_detail` | literal en app/scalp_logic.py:868 |
| `basis_status` | literal en app/scalp_logic.py:867 |
| `book_lag_seconds` | literal en app/scalp_logic.py:870 |
| `book_status` | literal en app/scalp_logic.py:869 |
| `confidence` | literal en app/scalp_logic.py:846 |
| `diff_3m` | literal en app/scalp_logic.py:854 |
| `evidence_coverage_pct` | literal en app/scalp_logic.py:862 |
| `expected_weight` | literal en app/scalp_logic.py:861 |
| `fut_delta_1m` | literal en app/scalp_logic.py:848 |
| `fut_delta_3m` | literal en app/scalp_logic.py:849 |
| `fut_price` | literal en app/scalp_logic.py:864 |
| `fut_volume_1m` | literal en app/scalp_logic.py:850 |
| `imbalance_l1` | literal en app/scalp_logic.py:873 |
| `imbalance_l10` | literal en app/scalp_logic.py:875 |
| `imbalance_l5` | literal en app/scalp_logic.py:874 |
| `liquidation_feed_health` | literal en app/scalp_logic.py:884 |
| `liquidations_measured` | literal en app/scalp_logic.py:882 |
| `liquidations_window` | literal en app/scalp_logic.py:883 |
| `long_liq_5m` | literal en app/scalp_logic.py:878 |
| `long_score` | literal en app/scalp_logic.py:843 |
| `measured_weight` | literal en app/scalp_logic.py:860 |
| `missing_components` | literal en app/scalp_logic.py:863 |
| `oi_chg_15m_pct` | literal en app/scalp_logic.py:893 |
| `oi_contributes_direction` | literal en app/scalp_logic.py:907 |
| `oi_directional_support` | literal en app/scalp_logic.py:904 |
| `oi_new_positioning` | literal en app/scalp_logic.py:905 |
| `oi_now` | literal en app/scalp_logic.py:895 |
| `oi_price_quadrant` | literal en app/scalp_logic.py:902 |
| `oi_price_status` | literal en app/scalp_logic.py:911 |
| `oi_reading` | literal en app/scalp_logic.py:903 |
| `oi_start` | literal en app/scalp_logic.py:894 |
| `oi_state` | literal en app/scalp_logic.py:901 |
| `oi_timeframe` | literal en app/scalp_logic.py:906 |
| `oi_window_end` | literal en app/scalp_logic.py:897 |
| `oi_window_samples` | literal en app/scalp_logic.py:898 |
| `oi_window_start` | literal en app/scalp_logic.py:896 |
| `oi_window_status` | literal en app/scalp_logic.py:899 |
| `price_move_15m_coverage` | literal en app/scalp_logic.py:910 |
| `price_move_15m_pct` | literal en app/scalp_logic.py:908 |
| `price_move_15m_status` | literal en app/scalp_logic.py:909 |
| `price_move_3m_pct` | literal en app/scalp_logic.py:871 |
| `reason` | literal en app/scalp_logic.py:847 |
| `session_vwap` | literal en app/scalp_logic.py:912 |
| `short_liq_5m` | literal en app/scalp_logic.py:879 |
| `short_score` | literal en app/scalp_logic.py:844 |
| `spot_delta_3m` | literal en app/scalp_logic.py:851 |
| `spot_fut_divergence_norm` | literal en app/scalp_logic.py:859 |
| `spot_price` | literal en app/scalp_logic.py:865 |
| `spread_bps` | literal en app/scalp_logic.py:872 |
| `state` | literal en app/scalp_logic.py:845 |
| `symbol` | literal en app/api.py:1088 |
| `vwap_dist_pct` | literal en app/scalp_logic.py:913 |
| `wall_down_pct` | literal en app/scalp_logic.py:877 |
| `wall_up_pct` | literal en app/scalp_logic.py:876 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:772`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - **PENDIENTE · ninguna funcion del arbol la escribe con SQL literal.**
    O la llena algo fuera de `app/` (migracion, colector externo, carga manual),
    o el SQL se construye en ejecucion y el analisis estatico no lo ve.
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:579`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:608`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:705`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:779`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:844`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:900`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:375`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:392`

## Funciones que la componen

24 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`

<details><summary>Alcanzables de forma indirecta (21)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.oi_price_reading` — `app/setups.py:228`

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
