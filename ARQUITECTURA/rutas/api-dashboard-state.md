# `GET /api/dashboard/state`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `dashboard_state` · `app/api.py:3021` (cuerpo hasta la 3048) · decorador en la linea 3020.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

165 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `barriers` | literal en app/api.py:3046 |
| `barriers.active_zone` | literal en app/interpretation.py:1001 |
| `barriers.available` | literal en app/interpretation.py:998 |
| `barriers.current_price` | literal en app/interpretation.py:999 |
| `barriers.decision` | literal en app/interpretation.py:1000 |
| `barriers.intraday_source_interval` | literal en app/scalp_logic.py:1354 |
| `barriers.live_pressure` | literal en app/interpretation.py:1004 |
| `barriers.long_case` | literal en app/interpretation.py:1021 |
| `barriers.method` | literal en app/interpretation.py:1035 |
| `barriers.nearest_resistance` | literal en app/interpretation.py:1003 |
| `barriers.nearest_support` | literal en app/interpretation.py:1002 |
| `barriers.reason` | literal en app/interpretation.py:886 |
| `barriers.short_case` | literal en app/interpretation.py:1028 |
| `barriers.symbol` | literal en app/scalp_logic.py:1353 |
| `barriers.warning` | literal en app/interpretation.py:1057 |
| `barriers.warnings` | literal en app/interpretation.py:1048 |
| `cvd_swing` | literal en app/api.py:3045 |
| `cvd_swing.as_of` | literal en app/interpretation.py:643 |
| `cvd_swing.available` | literal en app/interpretation.py:642 |
| `cvd_swing.backtest` | literal en app/interpretation.py:661 |
| `cvd_swing.evidence` | literal en app/interpretation.py:650 |
| `cvd_swing.horizon` | literal en app/interpretation.py:647 |
| `cvd_swing.invalidation` | literal en app/interpretation.py:649 |
| `cvd_swing.method` | literal en app/interpretation.py:673 |
| `cvd_swing.reason` | literal en app/interpretation.py:591 |
| `cvd_swing.reference_levels` | literal en app/interpretation.py:660 |
| `cvd_swing.score` | literal en app/interpretation.py:645 |
| `cvd_swing.sessions` | literal en app/interpretation.py:592 |
| `cvd_swing.signal` | literal en app/interpretation.py:644 |
| `cvd_swing.strength` | literal en app/interpretation.py:646 |
| `cvd_swing.thesis` | literal en app/interpretation.py:648 |
| `cvd_swing.warning` | literal en app/interpretation.py:680 |
| `market_memory` | literal en app/api.py:3047 |
| `market_memory.analog_summary` | literal en app/interpretation.py:508 |
| `market_memory.analogs` | literal en app/interpretation.py:507 |
| `market_memory.available` | literal en app/interpretation.py:491 |
| `market_memory.coverage` | literal en app/interpretation.py:492 |
| `market_memory.current` | literal en app/interpretation.py:500 |
| `market_memory.historical_tilt` | literal en app/interpretation.py:499 |
| `market_memory.method` | literal en app/interpretation.py:515 |
| `market_memory.phase` | literal en app/interpretation.py:498 |
| `market_memory.reason` | literal en app/interpretation.py:412 |
| `market_memory.sessions` | literal en app/interpretation.py:411 |
| `market_memory.source` | literal en app/interpretation.py:516 |
| `market_memory.symbol` | literal en app/scalp_logic.py:1676 |
| `market_memory.warning` | literal en app/interpretation.py:517 |
| `scalp` | literal en app/api.py:3039 |
| `scalp.absorption` | literal en app/scalp_logic.py:914 |
| `scalp.absorption_context` | literal en app/scalp_logic.py:916 |
| `scalp.absorption_delta_ratio` | literal en app/scalp_logic.py:915 |
| `scalp.basis_bps` | literal en app/scalp_logic.py:866 |
| `scalp.basis_detail` | literal en app/scalp_logic.py:868 |
| `scalp.basis_status` | literal en app/scalp_logic.py:867 |
| `scalp.book_lag_seconds` | literal en app/scalp_logic.py:870 |
| `scalp.book_status` | literal en app/scalp_logic.py:869 |
| `scalp.confidence` | literal en app/scalp_logic.py:846 |
| `scalp.diff_3m` | literal en app/scalp_logic.py:854 |
| `scalp.evidence_coverage_pct` | literal en app/scalp_logic.py:862 |
| `scalp.expected_weight` | literal en app/scalp_logic.py:861 |
| `scalp.fut_delta_1m` | literal en app/scalp_logic.py:848 |
| `scalp.fut_delta_3m` | literal en app/scalp_logic.py:849 |
| `scalp.fut_price` | literal en app/scalp_logic.py:864 |
| `scalp.fut_volume_1m` | literal en app/scalp_logic.py:850 |
| `scalp.imbalance_l1` | literal en app/scalp_logic.py:873 |
| `scalp.imbalance_l10` | literal en app/scalp_logic.py:875 |
| `scalp.imbalance_l5` | literal en app/scalp_logic.py:874 |
| `scalp.liquidation_feed_health` | literal en app/scalp_logic.py:884 |
| `scalp.liquidations_measured` | literal en app/scalp_logic.py:882 |
| `scalp.liquidations_window` | literal en app/scalp_logic.py:883 |
| `scalp.long_liq_5m` | literal en app/scalp_logic.py:878 |
| `scalp.long_score` | literal en app/scalp_logic.py:843 |
| `scalp.measured_weight` | literal en app/scalp_logic.py:860 |
| `scalp.missing_components` | literal en app/scalp_logic.py:863 |
| `scalp.oi_chg_15m_pct` | literal en app/scalp_logic.py:893 |
| `scalp.oi_contributes_direction` | literal en app/scalp_logic.py:907 |
| `scalp.oi_directional_support` | literal en app/scalp_logic.py:904 |
| `scalp.oi_new_positioning` | literal en app/scalp_logic.py:905 |
| `scalp.oi_now` | literal en app/scalp_logic.py:895 |
| `scalp.oi_price_quadrant` | literal en app/scalp_logic.py:902 |
| `scalp.oi_price_status` | literal en app/scalp_logic.py:911 |
| `scalp.oi_reading` | literal en app/scalp_logic.py:903 |
| `scalp.oi_start` | literal en app/scalp_logic.py:894 |
| `scalp.oi_state` | literal en app/scalp_logic.py:901 |
| `scalp.oi_timeframe` | literal en app/scalp_logic.py:906 |
| `scalp.oi_window_end` | literal en app/scalp_logic.py:897 |
| `scalp.oi_window_samples` | literal en app/scalp_logic.py:898 |
| `scalp.oi_window_start` | literal en app/scalp_logic.py:896 |
| `scalp.oi_window_status` | literal en app/scalp_logic.py:899 |
| `scalp.price_move_15m_coverage` | literal en app/scalp_logic.py:910 |
| `scalp.price_move_15m_pct` | literal en app/scalp_logic.py:908 |
| `scalp.price_move_15m_status` | literal en app/scalp_logic.py:909 |
| `scalp.price_move_3m_pct` | literal en app/scalp_logic.py:871 |
| `scalp.reason` | literal en app/scalp_logic.py:847 |
| `scalp.session_vwap` | literal en app/scalp_logic.py:912 |
| `scalp.short_liq_5m` | literal en app/scalp_logic.py:879 |
| `scalp.short_score` | literal en app/scalp_logic.py:844 |
| `scalp.spot_delta_3m` | literal en app/scalp_logic.py:851 |
| `scalp.spot_fut_divergence_norm` | literal en app/scalp_logic.py:859 |
| `scalp.spot_price` | literal en app/scalp_logic.py:865 |
| `scalp.spread_bps` | literal en app/scalp_logic.py:872 |
| `scalp.state` | literal en app/scalp_logic.py:845 |
| `scalp.vwap_dist_pct` | literal en app/scalp_logic.py:913 |
| `scalp.wall_down_pct` | literal en app/scalp_logic.py:877 |
| `scalp.wall_up_pct` | literal en app/scalp_logic.py:876 |
| `scalp_persistence` | literal en app/api.py:3041 |
| `scalp_persistence.as_of` | literal en app/api.py:2716 |
| `scalp_persistence.available` | literal en app/api.py:2707 |
| `scalp_persistence.dias` | literal en app/api.py:2715 |
| `scalp_persistence.episodios` | literal en app/api.py:2711 |
| `scalp_persistence.etiqueta` | literal en app/api.py:2717 |
| `scalp_persistence.maximo_min` | literal en app/api.py:2710 |
| `scalp_persistence.mediana_min` | literal en app/api.py:2708 |
| `scalp_persistence.minutos_muestra` | literal en app/api.py:2712 |
| `scalp_persistence.p90_min` | literal en app/api.py:2709 |
| `scalp_persistence.p90_no_accionable_min` | literal en app/api.py:2713 |
| `setup` | literal en app/api.py:3044 |
| `setup.daily_flow_source` | literal en app/interpretation.py:201 |
| `setup.daily_slope` | literal en app/interpretation.py:200 |
| `setup.daily_streak` | literal en app/interpretation.py:199 |
| `setup.primary` | literal en app/interpretation.py:202 |
| `setup.setups` | literal en app/interpretation.py:203 |
| `setup.warning` | literal en app/interpretation.py:204 |
| `signal_base_rate` | literal en app/api.py:3043 |
| `signal_base_rate.as_of` | literal en app/api.py:2931 |
| `signal_base_rate.dias_pedidos` | literal en app/api.py:2927 |
| `signal_base_rate.horizonte_min` | literal en app/api.py:2928 |
| `signal_base_rate.ventana_pedida_desde` | literal en app/api.py:2929 |
| `signal_base_rate.ventana_pedida_hasta` | literal en app/api.py:2930 |
| `snapshot` | literal en app/api.py:3038 |
| `snapshot.btr_15m` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.btr_1h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.btr_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_diff_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_diff_ses` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_fut_imbalance_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_nyse_session` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_session` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_spot_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_spot_imbalance_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.cvd_spot_session` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.delta_3min` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.fr_avg` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.liq_ratio_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.long_liq_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.metrics_cutoff_at` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.oi` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.oi_bybit` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.oi_chg_24h_pct` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.oi_vol_24h_ratio` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.pfr_avg` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.pfr_fr_div` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.price` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.price_cutoff_at` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.price_dir_1h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.regime_label` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.regime_logic_version` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.regime_score` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.short_liq_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.spot_vol_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.symbol` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.ts` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.vol_24h` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.whale_intensity` | columna de metrics_snapshot (sql/schema.sql) |
| `snapshot.whale_label` | columna de metrics_snapshot (sql/schema.sql) |
| `symbol` | literal en app/api.py:3037 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `futures_trades_agg` — `sql/schema.sql:273`, 11 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1549`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:813`
- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:784`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:780`
- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:856`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:912`
- `signal_observation` — `sql/schema.sql:415`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:371`
- `signal_outcome` — `sql/schema.sql:565`, 27 columnas
  - la llena `app.signal_outcomes.schedule_signal_outcomes` (INSERT) — `app/signal_outcomes.py:169`
  - la llena `app.signal_outcomes._finalize_not_evaluable` (UPDATE) — `app/signal_outcomes.py:199`
  - la llena `app.signal_outcomes._defer_missing_path` (UPDATE) — `app/signal_outcomes.py:226`
  - la llena `app.signal_outcomes._finalize_evaluated` (UPDATE) — `app/signal_outcomes.py:252`
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:264`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:285`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:391`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:408`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `m`
- `o.window_start`
- `observed_minute`

## Funciones que la componen

44 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.daily_data` — `app/api.py:494`
- `app.api.latest_snapshot` — `app/api.py:467`
- `app.api.scalp_persistence` — `app/api.py:2681`
- `app.api.signal_base_rate` — `app/api.py:2896`
- `app.api.validate_symbol` — `app/api.py:222`
- `app.interpretation.cvd_swing_read` — `app/interpretation.py:578`
- `app.interpretation.evaluate_setups` — `app/interpretation.py:139`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.market_memory` — `app/scalp_logic.py:1660`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1235`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`

<details><summary>Alcanzables de forma indirecta (33)</summary>

- `app.api.records` — `app/api.py:235`
- `app.interpretation._barrier_candidates` — `app/interpretation.py:684`
- `app.interpretation._barrier_zones` — `app/interpretation.py:779`
- `app.interpretation._cvd_observation` — `app/interpretation.py:521`
- `app.interpretation._cvd_side` — `app/interpretation.py:570`
- `app.interpretation._memory_features` — `app/interpretation.py:372`
- `app.interpretation._percentile` — `app/interpretation.py:368`
- `app.interpretation.daily_flow_read` — `app/interpretation.py:208`
- `app.interpretation.market_memory_read` — `app/interpretation.py:400`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.interpretation.price_barrier_read` — `app/interpretation.py:877`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:99`, `harness/checks/K43-foto-unica.sh:159`, `harness/checks/K43-foto-unica.sh:160`, `harness/checks/K43-foto-unica.sh:161` _(+10)_ | `harness/checks/K43-foto-unica.sh:167`, `harness/checks/K90-la-senal-no-dura-su-rotulo.sh:13`, `harness/checks/K95-la-tasa-base-que-se-pinta.sh:25`, `harness/checks/K95-la-tasa-base-que-se-pinta.sh:62` _(+1)_ |
| **panel** | `static/app.js:1566` | `static/app.js:1379`, `static/app.js:1386` |
| **readme** | — | `README.md:195`, `README.md:488`, `README.md:502` |
| **tests** | `tests/test_metrics_endpoint.py:253`, `tests/test_v121_hardening.py:27`, `tests/test_v150_desk_snapshot.py:126` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `scalp.book_lag_seconds`
- `scalp.liquidations_window`
- `scalp.oi_start`
- `scalp.oi_window_end`
- `scalp.oi_window_samples`
- `scalp.oi_window_start`
- `scalp.oi_window_status`
- `snapshot.metrics_cutoff_at`
- `snapshot.price_cutoff_at`

## Capa DECLARADA

**Declarada** en [`declarada/api-dashboard-state.md`](../declarada/api-dashboard-state.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.interpretation.evaluate_setups` | 4 | **0** | 51 ↑ | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 11 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.metrics.current_nyse_start` | 15 | **0** | 14 ↑ | **15** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 9 | **0** | 24 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 9 | **0** | 24 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 14 | **0** | 10 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 13 | **0** | 10 ↑ | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.basis_quality` | 10 | **0** | 10 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 10 | **0** | 10 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-setups.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._as_utc_datetime` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 20 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
