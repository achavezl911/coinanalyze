# `GET /api/dashboard/state`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `dashboard_state` · `app/api.py:3718` (cuerpo hasta la 3745) · decorador en la linea 3717.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

165 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `barriers` | literal en app/api.py:3743 |
| `barriers.active_zone` | literal en app/interpretation.py:1001 |
| `barriers.available` | literal en app/interpretation.py:998 |
| `barriers.current_price` | literal en app/interpretation.py:999 |
| `barriers.decision` | literal en app/interpretation.py:1000 |
| `barriers.intraday_source_interval` | literal en app/scalp_logic.py:1428 |
| `barriers.live_pressure` | literal en app/interpretation.py:1004 |
| `barriers.long_case` | literal en app/interpretation.py:1021 |
| `barriers.method` | literal en app/interpretation.py:1035 |
| `barriers.nearest_resistance` | literal en app/interpretation.py:1003 |
| `barriers.nearest_support` | literal en app/interpretation.py:1002 |
| `barriers.reason` | literal en app/interpretation.py:886 |
| `barriers.short_case` | literal en app/interpretation.py:1028 |
| `barriers.symbol` | literal en app/scalp_logic.py:1427 |
| `barriers.warning` | literal en app/interpretation.py:1057 |
| `barriers.warnings` | literal en app/interpretation.py:1048 |
| `cvd_swing` | literal en app/api.py:3742 |
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
| `market_memory` | literal en app/api.py:3744 |
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
| `market_memory.symbol` | literal en app/scalp_logic.py:1755 |
| `market_memory.warning` | literal en app/interpretation.py:517 |
| `scalp` | literal en app/api.py:3736 |
| `scalp.absorption` | literal en app/scalp_logic.py:919 |
| `scalp.absorption_context` | literal en app/scalp_logic.py:921 |
| `scalp.absorption_delta_ratio` | literal en app/scalp_logic.py:920 |
| `scalp.basis_bps` | literal en app/scalp_logic.py:871 |
| `scalp.basis_detail` | literal en app/scalp_logic.py:873 |
| `scalp.basis_status` | literal en app/scalp_logic.py:872 |
| `scalp.book_lag_seconds` | literal en app/scalp_logic.py:875 |
| `scalp.book_status` | literal en app/scalp_logic.py:874 |
| `scalp.confidence` | literal en app/scalp_logic.py:851 |
| `scalp.diff_3m` | literal en app/scalp_logic.py:859 |
| `scalp.evidence_coverage_pct` | literal en app/scalp_logic.py:867 |
| `scalp.expected_weight` | literal en app/scalp_logic.py:866 |
| `scalp.fut_delta_1m` | literal en app/scalp_logic.py:853 |
| `scalp.fut_delta_3m` | literal en app/scalp_logic.py:854 |
| `scalp.fut_price` | literal en app/scalp_logic.py:869 |
| `scalp.fut_volume_1m` | literal en app/scalp_logic.py:855 |
| `scalp.imbalance_l1` | literal en app/scalp_logic.py:878 |
| `scalp.imbalance_l10` | literal en app/scalp_logic.py:880 |
| `scalp.imbalance_l5` | literal en app/scalp_logic.py:879 |
| `scalp.liquidation_feed_health` | literal en app/scalp_logic.py:889 |
| `scalp.liquidations_measured` | literal en app/scalp_logic.py:887 |
| `scalp.liquidations_window` | literal en app/scalp_logic.py:888 |
| `scalp.long_liq_5m` | literal en app/scalp_logic.py:883 |
| `scalp.long_score` | literal en app/scalp_logic.py:848 |
| `scalp.measured_weight` | literal en app/scalp_logic.py:865 |
| `scalp.missing_components` | literal en app/scalp_logic.py:868 |
| `scalp.oi_chg_15m_pct` | literal en app/scalp_logic.py:898 |
| `scalp.oi_contributes_direction` | literal en app/scalp_logic.py:912 |
| `scalp.oi_directional_support` | literal en app/scalp_logic.py:909 |
| `scalp.oi_new_positioning` | literal en app/scalp_logic.py:910 |
| `scalp.oi_now` | literal en app/scalp_logic.py:900 |
| `scalp.oi_price_quadrant` | literal en app/scalp_logic.py:907 |
| `scalp.oi_price_status` | literal en app/scalp_logic.py:916 |
| `scalp.oi_reading` | literal en app/scalp_logic.py:908 |
| `scalp.oi_start` | literal en app/scalp_logic.py:899 |
| `scalp.oi_state` | literal en app/scalp_logic.py:906 |
| `scalp.oi_timeframe` | literal en app/scalp_logic.py:911 |
| `scalp.oi_window_end` | literal en app/scalp_logic.py:902 |
| `scalp.oi_window_samples` | literal en app/scalp_logic.py:903 |
| `scalp.oi_window_start` | literal en app/scalp_logic.py:901 |
| `scalp.oi_window_status` | literal en app/scalp_logic.py:904 |
| `scalp.price_move_15m_coverage` | literal en app/scalp_logic.py:915 |
| `scalp.price_move_15m_pct` | literal en app/scalp_logic.py:913 |
| `scalp.price_move_15m_status` | literal en app/scalp_logic.py:914 |
| `scalp.price_move_3m_pct` | literal en app/scalp_logic.py:876 |
| `scalp.reason` | literal en app/scalp_logic.py:852 |
| `scalp.session_vwap` | literal en app/scalp_logic.py:917 |
| `scalp.short_liq_5m` | literal en app/scalp_logic.py:884 |
| `scalp.short_score` | literal en app/scalp_logic.py:849 |
| `scalp.spot_delta_3m` | literal en app/scalp_logic.py:856 |
| `scalp.spot_fut_divergence_norm` | literal en app/scalp_logic.py:864 |
| `scalp.spot_price` | literal en app/scalp_logic.py:870 |
| `scalp.spread_bps` | literal en app/scalp_logic.py:877 |
| `scalp.state` | literal en app/scalp_logic.py:850 |
| `scalp.vwap_dist_pct` | literal en app/scalp_logic.py:918 |
| `scalp.wall_down_pct` | literal en app/scalp_logic.py:882 |
| `scalp.wall_up_pct` | literal en app/scalp_logic.py:881 |
| `scalp_persistence` | literal en app/api.py:3738 |
| `scalp_persistence.as_of` | literal en app/api.py:3413 |
| `scalp_persistence.available` | literal en app/api.py:3404 |
| `scalp_persistence.dias` | literal en app/api.py:3412 |
| `scalp_persistence.episodios` | literal en app/api.py:3408 |
| `scalp_persistence.etiqueta` | literal en app/api.py:3414 |
| `scalp_persistence.maximo_min` | literal en app/api.py:3407 |
| `scalp_persistence.mediana_min` | literal en app/api.py:3405 |
| `scalp_persistence.minutos_muestra` | literal en app/api.py:3409 |
| `scalp_persistence.p90_min` | literal en app/api.py:3406 |
| `scalp_persistence.p90_no_accionable_min` | literal en app/api.py:3410 |
| `setup` | literal en app/api.py:3741 |
| `setup.daily_flow_source` | literal en app/interpretation.py:201 |
| `setup.daily_slope` | literal en app/interpretation.py:200 |
| `setup.daily_streak` | literal en app/interpretation.py:199 |
| `setup.primary` | literal en app/interpretation.py:202 |
| `setup.setups` | literal en app/interpretation.py:203 |
| `setup.warning` | literal en app/interpretation.py:204 |
| `signal_base_rate` | literal en app/api.py:3740 |
| `signal_base_rate.as_of` | literal en app/api.py:3628 |
| `signal_base_rate.dias_pedidos` | literal en app/api.py:3624 |
| `signal_base_rate.horizonte_min` | literal en app/api.py:3625 |
| `signal_base_rate.ventana_pedida_desde` | literal en app/api.py:3626 |
| `signal_base_rate.ventana_pedida_hasta` | literal en app/api.py:3627 |
| `snapshot` | literal en app/api.py:3735 |
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
| `symbol` | literal en app/api.py:3734 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1123`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `futures_trades_agg` — `sql/schema.sql:374`, 9 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1629`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:875`
- `futures_trades_realtime` — `sql/schema.sql:357`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:846`
- `liquidations_realtime` — `sql/schema.sql:440`, 9 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:75`
- `market_feed_health` — `sql/schema.sql:1402`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1351`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:824`
- `metrics_snapshot` — `sql/schema.sql:1036`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:684`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:748`
- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:184`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
- `orderbook_snapshot` — `sql/schema.sql:388`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:918`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:974`
- `signal_observation` — `sql/schema.sql:521`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:371`
- `signal_outcome` — `sql/schema.sql:668`, 27 columnas
  - la llena `app.signal_outcomes.schedule_signal_outcomes` (INSERT) — `app/signal_outcomes.py:169`
  - la llena `app.signal_outcomes._finalize_not_evaluable` (UPDATE) — `app/signal_outcomes.py:199`
  - la llena `app.signal_outcomes._defer_missing_path` (UPDATE) — `app/signal_outcomes.py:226`
  - la llena `app.signal_outcomes._finalize_evaluated` (UPDATE) — `app/signal_outcomes.py:252`
- `spot_trades_agg` — `sql/schema.sql:299`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:681`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:277`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:298`
- `spot_trades_realtime` — `sql/schema.sql:329`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:404`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:421`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `m`
- `o.window_start`
- `observed_minute`

## Funciones que la componen

44 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.daily_data` — `app/api.py:742`
- `app.api.latest_snapshot` — `app/api.py:715`
- `app.api.scalp_persistence` — `app/api.py:3378`
- `app.api.signal_base_rate` — `app/api.py:3593`
- `app.api.validate_symbol` — `app/api.py:260`
- `app.interpretation.cvd_swing_read` — `app/interpretation.py:578`
- `app.interpretation.evaluate_setups` — `app/interpretation.py:139`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:633`
- `app.scalp_logic.market_memory` — `app/scalp_logic.py:1739`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1309`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:330`

<details><summary>Alcanzables de forma indirecta (33)</summary>

- `app.api.records` — `app/api.py:273`
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
- `app.metrics.current_nyse_start` — `app/metrics.py:49`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:548`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:99`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:595`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:571`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:507`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:519`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:563`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1232`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:73`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:139`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:236`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:198`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:163`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:297`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:322`
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
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:157`, `harness/checks/K43-foto-unica.sh:228`, `harness/checks/K43-foto-unica.sh:229`, `harness/checks/K43-foto-unica.sh:230` _(+20)_ | `harness/checks/K43-foto-unica.sh:236`, `harness/checks/K44-control.bash:254`, `harness/checks/K44-control.bash:628`, `harness/checks/K44-control.bash:720` _(+7)_ |
| **panel** | `static/js/07-decision-y-ciclos.js:243` | `static/js/07-decision-y-ciclos.js:26`, `static/js/07-decision-y-ciclos.js:33`, `static/js/07-decision-y-ciclos.js:235` |
| **tests** | `tests/test_deploy_wrapper.py:268`, `tests/test_metrics_endpoint.py:253`, `tests/test_v121_hardening.py:35`, `tests/test_v150_desk_snapshot.py:130` | — |

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
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.interpretation.evaluate_setups` | 4 | **0** | 48 ↑ | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.records` | 22 | **0** | 14 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.basis_quality` | 11 | **0** | 11 ↑ | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 11 | **0** | 11 ↑ | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-setups.md) |
| `app.interpretation.number` | 14 | **0** | 3 ↑ | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic._resample_highs_lows` | 15 | **0** | 0 | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._as_utc_datetime` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 20 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
