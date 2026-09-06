# ARQUITECTURA · IMPACTO · si toco esto, que rutas cambian

> Generado por `harness/bin/arquitectura`. No editar a mano.

## Los dos caminos, y por que van separados

| camino | que significa | exactitud |
|---|---|---|
| **por llamada** | la ruta **ejecuta** esta funcion | **exacto**: esta en su cierre o no |
| **por tabla · k=0** | la funcion **escribe ella misma** una tabla que la ruta **lee** | **exacto** |
| **por tabla · k<=2** | ella *o quien la llama hasta k=2* escribe una tabla que la ruta lee | **cota superior** |

La ruta no ejecuta nada del camino por tabla: **se entera por el dato**. Fundir
cualquiera de estos en un solo numero ocultaria justo la mitad que importa.

```
compute_snapshot   por llamada:      0 rutas   <- un grafo de llamadas diria 'no afecta a nada'
                   por tabla k=0:    0 rutas   <- no escribe nada: es una funcion pura
                   por tabla k<=2:   8 rutas   <- y tumbo el snapshot 24 dias
```

## Por que DOS numeros, y no uno · una correccion de F2

F2 publicaba solo el `k<=2` y afirmaba que el corte era **un limite estructural del**
**codigo, porque a k=3 aparece el orquestador**. Era falso, y estaba ajustado a UN
caso. El segundo caso lo tira:

```
ws_collector._write_minute escribe spot_trades_agg ELLA MISMA (INSERT :254 y :275)
   k=0   -> 10 rutas   exacto, y lo confirma un grep de fichas independiente
   k<=2  -> 17 rutas   las 7 de mas entran por ws_collector.run, el bucle del colector
```

El **mismo tipo de orquestador** que para `compute_snapshot` quedaba fuera a k=3, aqui
esta **dentro a k=2**, porque la cadena de llamadas es mas corta. El corte no depende
de la estructura del sistema sino de **la profundidad de cada cadena**, y eso no es un
limite: es un numero que acierta en el caso con el que se ajusto.

**Sobre las 480 funciones con radio, 196 tienen la cota mas ancha que su k=0.** El 17 no era
falso -es una cota verdadera-: lo que faltaba era **decir que es una cota**.

Solo **46** de las 480 escriben alguna tabla
ellas mismas. Para el resto -las funciones puras- la cota es lo unico que hay, y por
eso se sigue publicando: sin ella, `compute_snapshot` tendria radio cero.

## A · si toco una TABLA

| tabla | la escriben | rutas que la leen | rutas que la escriben |
|---|---|---|---|
| [`daily_session_agg`](TABLAS.md#daily-session-agg) | 2 | **20** | 0 |
| [`daily_verdict_outcome`](TABLAS.md#daily-verdict-outcome) | 1 | **3** | 0 |
| [`daily_verdict_snapshot`](TABLAS.md#daily-verdict-snapshot) | 1 | **3** | 0 |
| [`data_gap`](TABLAS.md#data-gap) | 12 | **21** | 0 |
| [`external_macro_observation`](TABLAS.md#external-macro-observation) | 2 | **3** | 0 |
| [`funding_rate`](TABLAS.md#funding-rate) | 1 | **3** | 0 |
| [`futures_trades_agg`](TABLAS.md#futures-trades-agg) | 2 | **6** | 0 |
| [`futures_trades_realtime`](TABLAS.md#futures-trades-realtime) | 1 | **16** | 0 |
| [`liquidations`](TABLAS.md#liquidations) | 2 | **4** | 0 |
| [`liquidations_realtime`](TABLAS.md#liquidations-realtime) | 1 | **14** | 0 |
| [`long_short_ratio`](TABLAS.md#long-short-ratio) | 2 | **3** | 0 |
| [`macro_event`](TABLAS.md#macro-event) | 2 | **3** | 0 |
| [`market_feed_health`](TABLAS.md#market-feed-health) | 3 | **9** | 0 |
| [`metric_baseline`](TABLAS.md#metric-baseline) | 1 | **14** | 0 |
| [`metrics_snapshot`](TABLAS.md#metrics-snapshot) | 2 | **8** | 0 |
| [`ohlcv`](TABLAS.md#ohlcv) | 4 | **36** | 0 |
| [`oi_bybit`](TABLAS.md#oi-bybit) | 1 | **3** | 0 |
| [`open_interest`](TABLAS.md#open-interest) | 1 | **18** | 0 |
| [`orderbook_depth`](TABLAS.md#orderbook-depth) | 1 | **1** | 0 |
| [`orderbook_snapshot`](TABLAS.md#orderbook-snapshot) | 2 | **14** | 0 |
| [`pipeline_heartbeat`](TABLAS.md#pipeline-heartbeat) | 3 | **7** | 1 |
| [`predicted_funding_rate`](TABLAS.md#predicted-funding-rate) | 1 | **3** | 0 |
| [`scalp_signal_snapshot`](TABLAS.md#scalp-signal-snapshot) | 1 | **4** | 0 |
| [`signal_execution_snapshot`](TABLAS.md#signal-execution-snapshot) | 1 | **1** | 0 |
| [`signal_observation`](TABLAS.md#signal-observation) | 1 | **6** | 0 |
| [`signal_outcome`](TABLAS.md#signal-outcome) | 4 | **3** | 0 |
| [`signal_outcome_final_visibility`](TABLAS.md#signal-outcome-final-visibility) | 1 | **1** | 0 |
| [`signal_replay_frame`](TABLAS.md#signal-replay-frame) | 1 | **1** | 0 |
| [`spot_trades_agg`](TABLAS.md#spot-trades-agg) | 3 | **10** | 0 |
| [`spot_trades_realtime`](TABLAS.md#spot-trades-realtime) | 2 | **12** | 0 |

## B · si toco una FUNCION

480 funciones alcanzan alguna ruta. Ordenadas por radio total. **Abre solo el
fichero de su modulo**: `impacto/<modulo>.md`.

| funcion | sitio | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`app.api.validate_symbol`](impacto/app-api.md) | `app/api.py:222` | 62 | **0** | 0 | **62** |
| [`app.daily_agg.apply_retention`](impacto/app-daily_agg.md) | `app/daily_agg.py:627` | 0 | **50** | 51 ↑ | **50** |
| [`app.scalp_logic.as_float`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:920` | 37 | **0** | 10 ↑ | **37** |
| [`app.ingest.rollup_ohlcv_5m`](impacto/app-ingest.md) | `app/ingest.py:184` | 0 | **36** | 51 ↑ | **36** |
| [`app.ingest.upsert_ohlcv`](impacto/app-ingest.md) | `app/ingest.py:101` | 0 | **36** | 51 ↑ | **36** |
| [`app.scalp_logic._explicit_as_of`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2398` | 25 | **0** | 0 | **25** |
| [`app.scalp_logic.resolve_matrix_as_of`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2404` | 24 | **0** | 11 ↑ | **24** |
| [`app.api.records`](impacto/app-api.md) | `app/api.py:235` | 22 | **0** | 7 ↑ | **22** |
| [`app.data_gaps.reconcile_cadence_coverage`](impacto/app-data_gaps.md) | `app/data_gaps.py:474` | 0 | **21** | 47 ↑ | **21** |
| [`app.data_gaps._mark_unrecoverable`](impacto/app-data_gaps.md) | `app/data_gaps.py:1230` | 0 | **21** | 21 | **21** |
| [`app.data_gaps._record_recovery_failure`](impacto/app-data_gaps.md) | `app/data_gaps.py:1255` | 0 | **21** | 21 | **21** |
| [`app.data_gaps.archive_beyond_source_horizon`](impacto/app-data_gaps.md) | `app/data_gaps.py:722` | 0 | **21** | 21 | **21** |
| [`app.data_gaps.archive_source_response_absence`](impacto/app-data_gaps.md) | `app/data_gaps.py:792` | 0 | **21** | 21 | **21** |
| [`app.data_gaps.close_partitioned_gap`](impacto/app-data_gaps.md) | `app/data_gaps.py:1045` | 0 | **21** | 21 | **21** |
| [`app.data_gaps.record_data_gap`](impacto/app-data_gaps.md) | `app/data_gaps.py:287` | 0 | **21** | 21 | **21** |
| [`app.data_gaps.recover_gap`](impacto/app-data_gaps.md) | `app/data_gaps.py:1272` | 0 | **21** | 21 | **21** |
| [`app.daily_agg.compute_session`](impacto/app-daily_agg.md) | `app/daily_agg.py:141` | 0 | **20** | 51 ↑ | **20** |
| [`app.data_gaps.blocking_requirement_keys`](impacto/app-data_gaps.md) | `app/data_gaps.py:108` | 20 | **0** | 14 ↑ | **20** |
| [`app.scalp_collector._write_combined_realtime`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:766` | 0 | **16** | 21 ↑ | **16** |
| [`app.metrics.current_nyse_start`](impacto/app-metrics.md) | `app/metrics.py:20` | 15 | **0** | 14 ↑ | **15** |
| [`app.daily_agg._store_baseline`](impacto/app-daily_agg.md) | `app/daily_agg.py:727` | 0 | **14** | 53 ↑ | **14** |
| [`app.data_gaps._aware_utc`](impacto/app-data_gaps.md) | `app/data_gaps.py:67` | 14 | **0** | 21 ↑ | **14** |
| [`app.data_gaps._validated_window`](impacto/app-data_gaps.md) | `app/data_gaps.py:73` | 14 | **0** | 21 ↑ | **14** |
| [`app.scalp_logic.load_baselines`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:158` | 14 | **0** | 10 ↑ | **14** |
| [`app.scalp_collector._write_combined_books`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:896` | 0 | **14** | 19 ↑ | **14** |
| [`app.scalp_collector.flush_books`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:821` | 0 | **14** | 19 ↑ | **14** |
| [`app.scalp_collector.flush_liquidations`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:954` | 0 | **14** | 19 ↑ | **14** |
| [`app.scalp_logic._resample_highs_lows`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1197` | 14 | **0** | 0 | **14** |
| [`app.scalp_logic.baseline_band`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:134` | 13 | **0** | 10 ↑ | **13** |
| [`app.interpretation.number`](impacto/app-interpretation.md) | `app/interpretation.py:10` | 13 | **0** | 3 ↑ | **13** |
| [`app.data_gaps.coverage_entry`](impacto/app-data_gaps.md) | `app/data_gaps.py:253` | 13 | **0** | 0 | **13** |
| [`app.scalp_logic._flow_windows`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2431` | 13 | **0** | 0 | **13** |
| [`app.scalp_logic.spot_flow_windows`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2609` | 13 | **0** | 0 | **13** |
| [`app.data_gaps.expected_buckets`](impacto/app-data_gaps.md) | `app/data_gaps.py:245` | 12 | **0** | 21 ↑ | **12** |
| [`app.scalp_logic._gap_and_baseline`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4071` | 12 | **0** | 0 | **12** |
| [`app.scalp_logic._gap_threshold_seconds`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4041` | 12 | **0** | 0 | **12** |
| [`app.scalp_logic._gap_too_large`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4053` | 12 | **0** | 0 | **12** |
| [`app.ws_collector.flush_realtime`](impacto/app-ws_collector.md) | `app/ws_collector.py:350` | 0 | **12** | 12 | **12** |
| [`app.scalp_logic._oi_change_pct`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4245` | 11 | **0** | 0 | **11** |
| [`app.scalp_logic._realtime_flow`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4161` | 11 | **0** | 0 | **11** |
| [`app.scalp_logic.basis_quality`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:231` | 10 | **0** | 10 ↑ | **10** |
| [`app.scalp_logic.classify_absorption`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:193` | 10 | **0** | 10 ↑ | **10** |
| [`app.ws_collector._write_minute`](impacto/app-ws_collector.md) | `app/ws_collector.py:230` | 0 | **10** | 17 ↑ | **10** |
| [`app.scalp_logic._complete_tail_values`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:960` | 10 | **0** | 0 | **10** |
| [`app.scalp_logic._contiguous_measured_suffix`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:970` | 10 | **0** | 0 | **10** |
| [`app.scalp_logic.flow_confirmation`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4419` | 10 | **0** | 0 | **10** |
| [`app.scalp_logic.compute_scalp_summary`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:628` | 9 | **0** | 24 ↑ | **9** |
| [`app.scalp_logic.scalp_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:325` | 9 | **0** | 24 ↑ | **9** |
| [`app.scalp_logic._closed_5m_oi_bounds`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:94` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic._closed_window_move_pct`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:590` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic._first_present`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:502` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic._liquidation_window_measured`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:514` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic._measured_event_sum`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:558` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic.scalp_bias_label`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:292` | 9 | **0** | 10 ↑ | **9** |
| [`app.scalp_logic.score_component`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:317` | 9 | **0** | 10 ↑ | **9** |
| [`app.setups.classify_oi`](impacto/app-setups.md) | `app/setups.py:162` | 9 | **0** | 10 ↑ | **9** |
| [`app.setups.oi_price_reading`](impacto/app-setups.md) | `app/setups.py:228` | 9 | **0** | 10 ↑ | **9** |
| [`app.db._mark_feed_shard_health`](impacto/app-db.md) | `app/db.py:649` | 0 | **9** | 9 | **9** |
| [`app.db._mark_feed_unhealthy`](impacto/app-db.md) | `app/db.py:599` | 0 | **9** | 9 | **9** |
| [`app.db.mark_feed_connected`](impacto/app-db.md) | `app/db.py:571` | 0 | **9** | 9 | **9** |
| [`app.scalp_logic._as_utc_datetime`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:543` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._atr`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2926` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._coverage_status`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:566` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._structure_from_swings`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2226` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._swings`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2212` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._tr_series`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2915` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic._utc_now`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:68` | 9 | **0** | 0 | **9** |
| [`app.setups._sign`](impacto/app-setups.md) | `app/setups.py:95` | 9 | **0** | 0 | **9** |
| [`app.scalp_logic.trend_matrix`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5928` | 8 | **0** | 3 ↑ | **8** |
| [`app.metrics.insert_snapshot`](impacto/app-metrics.md) | `app/metrics.py:676` | 0 | **8** | 8 | **8** |
| [`app.scalp_logic._flow_imbalance`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2416` | 8 | **0** | 0 | **8** |
| [`app.scalp_logic._flow_rate`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2424` | 8 | **0** | 0 | **8** |
| [`app.scalp_logic.futures_flow_windows`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2619` | 8 | **0** | 0 | **8** |
| [`app.db.heartbeat`](impacto/app-db.md) | `app/db.py:409` | 1 | **7** | 53 ↑ | **7** |
| [`app.db.heartbeat_component`](impacto/app-db.md) | `app/db.py:443` | 0 | **7** | 41 ↑ | **7** |
| [`app.db.heartbeat_shard`](impacto/app-db.md) | `app/db.py:522` | 0 | **7** | 21 ↑ | **7** |
| [`app.scalp_logic.structure_detail`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2283` | 7 | **0** | 3 ↑ | **7** |
| [`app.api.historical_interval_value`](impacto/app-api.md) | `app/api.py:228` | 7 | **0** | 0 | **7** |
| [`app.api.mask_gapped_series_rows`](impacto/app-api.md) | `app/api.py:239` | 7 | **0** | 0 | **7** |
| [`app.data_gaps.declared_gap_windows`](impacto/app-data_gaps.md) | `app/data_gaps.py:197` | 7 | **0** | 0 | **7** |
| [`app.scalp_logic._dsr`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2275` | 7 | **0** | 0 | **7** |
| [`app.scalp_logic._pct_rank`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1742` | 7 | **0** | 0 | **7** |
| [`app.scalp_logic.delta_matrix`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4277` | 7 | **0** | 0 | **7** |
| [`app.signal_ledger.persist_signal_observations`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:227` | 0 | **6** | 24 ↑ | **6** |
| [`app.scalp_collector._write_combined_minute`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:795` | 0 | **6** | 21 ↑ | **6** |
| [`app.scalp_collector.cleanup_expired_rows`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1528` | 0 | **6** | 19 ↑ | **6** |
| [`app.api._utc_iso`](impacto/app-api.md) | `app/api.py:2086` | 6 | **0** | 0 | **6** |
| [`app.api.declared_series_response`](impacto/app-api.md) | `app/api.py:349` | 6 | **0** | 0 | **6** |
| [`app.interpretation._barrier_candidates`](impacto/app-interpretation.md) | `app/interpretation.py:684` | 6 | **0** | 0 | **6** |
| [`app.interpretation._barrier_zones`](impacto/app-interpretation.md) | `app/interpretation.py:779` | 6 | **0** | 0 | **6** |
| [`app.interpretation.price_barrier_read`](impacto/app-interpretation.md) | `app/interpretation.py:877` | 6 | **0** | 0 | **6** |
| [`app.scalp_logic._profile`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3502` | 6 | **0** | 0 | **6** |
| [`app.scalp_logic.price_barriers`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1235` | 6 | **0** | 0 | **6** |
| [`app.scalp_logic.volume_profile`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3539` | 6 | **0** | 0 | **6** |
| [`app.scalp_logic.cross_asset`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3304` | 5 | **0** | 3 ↑ | **5** |
| [`app.scalp_logic.macro_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1820` | 5 | **0** | 3 ↑ | **5** |
| [`app.scalp_logic.passive_flow`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5810` | 5 | **0** | 3 ↑ | **5** |
| [`app.api.rechaza_parametros_desconocidos`](impacto/app-api.md) | `app/api.py:2120` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._beta`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3269` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._binned`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3283` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._classify_passive`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5777` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._conditional_outcome`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1780` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._forward_returns`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1770` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._pearson`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3256` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._regime`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1751` | 5 | **0** | 0 | **5** |
| [`app.scalp_logic._returns`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3248` | 5 | **0** | 0 | **5** |
| [`app.interpretation.evaluate_setups`](impacto/app-interpretation.md) | `app/interpretation.py:139` | 4 | **0** | 51 ↑ | **4** |
| [`app.scalp_collector.persist_scalp_signals`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1347` | 0 | **4** | 24 ↑ | **4** |
| [`app.ingest.upsert_liquidations`](impacto/app-ingest.md) | `app/ingest.py:293` | 0 | **4** | 11 ↑ | **4** |
| [`app.db.required_heartbeat_failures`](impacto/app-db.md) | `app/db.py:110` | 4 | **0** | 7 ↑ | **4** |
| [`app.scalp_logic.compute_swing_score`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:6083` | 4 | **0** | 3 ↑ | **4** |
| [`app.data_gaps.align_down`](impacto/app-data_gaps.md) | `app/data_gaps.py:232` | 4 | **0** | 0 | **4** |
| [`app.interpretation._memory_features`](impacto/app-interpretation.md) | `app/interpretation.py:372` | 4 | **0** | 0 | **4** |
| [`app.interpretation.market_memory_read`](impacto/app-interpretation.md) | `app/interpretation.py:400` | 4 | **0** | 0 | **4** |
| [`app.scalp_logic.data_quality`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3973` | 4 | **0** | 0 | **4** |
| [`app.scalp_logic.market_impact`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5502` | 4 | **0** | 0 | **4** |
| [`app.scalp_logic.market_memory`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1660` | 4 | **0** | 0 | **4** |
| [`app.zones._atr_abs`](impacto/app-zones.md) | `app/zones.py:519` | 4 | **0** | 0 | **4** |
| [`app.zones._edge_episodes`](impacto/app-zones.md) | `app/zones.py:499` | 4 | **0** | 0 | **4** |
| [`app.zones._ols_slope`](impacto/app-zones.md) | `app/zones.py:471` | 4 | **0** | 0 | **4** |
| [`app.zones._rotations`](impacto/app-zones.md) | `app/zones.py:483` | 4 | **0** | 0 | **4** |
| [`app.zones.range_validate_read`](impacto/app-zones.md) | `app/zones.py:535` | 4 | **0** | 0 | **4** |
| [`app.config.get_settings`](impacto/app-config.md) | `app/config.py:291` | 3 | **0** | 53 ↑ | **3** |
| [`app.daily_agg.materialize_daily_verdict_outcomes`](impacto/app-daily_agg.md) | `app/daily_agg.py:503` | 0 | **3** | 51 ↑ | **3** |
| [`app.daily_agg.persist_verdicts`](impacto/app-daily_agg.md) | `app/daily_agg.py:335` | 0 | **3** | 51 ↑ | **3** |
| [`app.external_macro.refresh_external_macro`](impacto/app-external_macro.md) | `app/external_macro.py:478` | 0 | **3** | 11 ↑ | **3** |
| [`app.ingest.upsert_long_short`](impacto/app-ingest.md) | `app/ingest.py:326` | 0 | **3** | 11 ↑ | **3** |
| [`app.signal_outcomes._defer_missing_path`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:217` | 0 | **3** | 10 ↑ | **3** |
| [`app.signal_outcomes._finalize_evaluated`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:241` | 0 | **3** | 10 ↑ | **3** |
| [`app.signal_outcomes._finalize_not_evaluable`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:189` | 0 | **3** | 10 ↑ | **3** |
| [`app.signal_outcomes.schedule_signal_outcomes`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:155` | 0 | **3** | 10 ↑ | **3** |
| [`app.ai_context.data_confidence_row`](impacto/app-ai_context.md) | `app/ai_context.py:497` | 3 | **0** | 0 | **3** |
| [`app.ai_context.orderbook_freshness`](impacto/app-ai_context.md) | `app/ai_context.py:634` | 3 | **0** | 0 | **3** |
| [`app.ai_context.quality_score`](impacto/app-ai_context.md) | `app/ai_context.py:585` | 3 | **0** | 0 | **3** |
| [`app.api.daily_data`](impacto/app-api.md) | `app/api.py:494` | 3 | **0** | 0 | **3** |
| [`app.api.latest_snapshot`](impacto/app-api.md) | `app/api.py:467` | 3 | **0** | 0 | **3** |
| [`app.external_macro._direction`](impacto/app-external_macro.md) | `app/external_macro.py:190` | 3 | **0** | 0 | **3** |
| [`app.external_macro._metric`](impacto/app-external_macro.md) | `app/external_macro.py:205` | 3 | **0** | 0 | **3** |
| [`app.external_macro._pct_change`](impacto/app-external_macro.md) | `app/external_macro.py:184` | 3 | **0** | 0 | **3** |
| [`app.external_macro._pillar`](impacto/app-external_macro.md) | `app/external_macro.py:232` | 3 | **0** | 0 | **3** |
| [`app.external_macro._state`](impacto/app-external_macro.md) | `app/external_macro.py:197` | 3 | **0** | 0 | **3** |
| [`app.external_macro.align_with_internal`](impacto/app-external_macro.md) | `app/external_macro.py:415` | 3 | **0** | 0 | **3** |
| [`app.external_macro.build_external_macro_context`](impacto/app-external_macro.md) | `app/external_macro.py:237` | 3 | **0** | 0 | **3** |
| [`app.external_macro.external_macro_context`](impacto/app-external_macro.md) | `app/external_macro.py:437` | 3 | **0** | 0 | **3** |
| [`app.interpretation._cvd_observation`](impacto/app-interpretation.md) | `app/interpretation.py:521` | 3 | **0** | 0 | **3** |
| [`app.interpretation._cvd_side`](impacto/app-interpretation.md) | `app/interpretation.py:570` | 3 | **0** | 0 | **3** |
| [`app.interpretation._percentile`](impacto/app-interpretation.md) | `app/interpretation.py:368` | 3 | **0** | 0 | **3** |
| [`app.interpretation.cvd_swing_read`](impacto/app-interpretation.md) | `app/interpretation.py:578` | 3 | **0** | 0 | **3** |
| [`app.interpretation.daily_flow_read`](impacto/app-interpretation.md) | `app/interpretation.py:208` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._banda`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5030` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._bps`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4956` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._buckets_observados`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2978` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._closes_1min`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2905` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._cvd_fut_window`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1006` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._cvd_src`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2640` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._feed_status`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3850` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._flow_bias`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4485` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._intraday_divergences`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1958` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._liquidation_feed_quality_status`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3815` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._oi_coverage`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2990` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._oi_quadrant`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2948` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._pivot_structure`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:936` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._realized_vol`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2934` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._return_stdev_pct`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1945` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._sign_vote`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:954` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._slope_pct`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1913` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic._structure_layer`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:982` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.coherencia_del_plan`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4963` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.context_metadata`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3599` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.cvd_matrix`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2699` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.divergence_scan`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2073` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.execution_assessment`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5039` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.feed_quality`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3690` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.feed_quality_view`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5265` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.funding_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3347` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.liquidation_map`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3420` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.market_structure`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1026` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.max_internal_gap`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4117` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.metric_quality`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3879` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.oi_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3021` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.positioning_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5607` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.profile_view`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4498` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.reference_levels`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3191` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.scalp_absorption`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5308` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.scalp_basis`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5464` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.scalp_liquidations`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5403` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.volatility_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:3141` | 3 | **0** | 0 | **3** |
| [`app.scalp_logic.wyckoff_context`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1606` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._atr_abs`](impacto/app-wyckoff.md) | `app/wyckoff.py:183` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._bar_date`](impacto/app-wyckoff.md) | `app/wyckoff.py:42` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._bias_read`](impacto/app-wyckoff.md) | `app/wyckoff.py:263` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._candidate_rank`](impacto/app-wyckoff.md) | `app/wyckoff.py:83` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._clamp`](impacto/app-wyckoff.md) | `app/wyckoff.py:25` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._clean_bars`](impacto/app-wyckoff.md) | `app/wyckoff.py:54` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._events`](impacto/app-wyckoff.md) | `app/wyckoff.py:197` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._phase`](impacto/app-wyckoff.md) | `app/wyckoff.py:401` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._quantile`](impacto/app-wyckoff.md) | `app/wyckoff.py:29` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._range_bounds`](impacto/app-wyckoff.md) | `app/wyckoff.py:66` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._session_date`](impacto/app-wyckoff.md) | `app/wyckoff.py:251` | 3 | **0** | 0 | **3** |
| [`app.wyckoff._signed_balance`](impacto/app-wyckoff.md) | `app/wyckoff.py:178` | 3 | **0** | 0 | **3** |
| [`app.wyckoff.detect_latest_range`](impacto/app-wyckoff.md) | `app/wyckoff.py:99` | 3 | **0** | 0 | **3** |
| [`app.wyckoff.wyckoff_auto_read`](impacto/app-wyckoff.md) | `app/wyckoff.py:447` | 3 | **0** | 0 | **3** |
| [`app.metrics.session_bounds`](impacto/app-metrics.md) | `app/metrics.py:31` | 2 | **0** | 51 ↑ | **2** |
| [`app.scalp_logic.swing_score`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:6234` | 2 | **0** | 51 ↑ | **2** |
| [`app.ai_context._round_number`](impacto/app-ai_context.md) | `app/ai_context.py:192` | 2 | **0** | 0 | **2** |
| [`app.ai_context.build_ai_symbol_context`](impacto/app-ai_context.md) | `app/ai_context.py:820` | 2 | **0** | 0 | **2** |
| [`app.ai_context.build_operator_read`](impacto/app-ai_context.md) | `app/ai_context.py:713` | 2 | **0** | 0 | **2** |
| [`app.ai_context.compact_dict`](impacto/app-ai_context.md) | `app/ai_context.py:219` | 2 | **0** | 0 | **2** |
| [`app.ai_context.compact_value`](impacto/app-ai_context.md) | `app/ai_context.py:203` | 2 | **0** | 0 | **2** |
| [`app.ai_context.daily_data`](impacto/app-ai_context.md) | `app/ai_context.py:271` | 2 | **0** | 0 | **2** |
| [`app.ai_context.daily_history`](impacto/app-ai_context.md) | `app/ai_context.py:360` | 2 | **0** | 0 | **2** |
| [`app.ai_context.latest_orderbook`](impacto/app-ai_context.md) | `app/ai_context.py:646` | 2 | **0** | 0 | **2** |
| [`app.ai_context.latest_snapshot`](impacto/app-ai_context.md) | `app/ai_context.py:264` | 2 | **0** | 0 | **2** |
| [`app.ai_context.liquidation_levels`](impacto/app-ai_context.md) | `app/ai_context.py:674` | 2 | **0** | 0 | **2** |
| [`app.ai_context.local_alerts`](impacto/app-ai_context.md) | `app/ai_context.py:763` | 2 | **0** | 0 | **2** |
| [`app.ai_context.normalize_profile`](impacto/app-ai_context.md) | `app/ai_context.py:185` | 2 | **0** | 0 | **2** |
| [`app.ai_context.recent_signals`](impacto/app-ai_context.md) | `app/ai_context.py:658` | 2 | **0** | 0 | **2** |
| [`app.ai_context.rough_token_estimate`](impacto/app-ai_context.md) | `app/ai_context.py:249` | 2 | **0** | 0 | **2** |
| [`app.ai_context.sin_perder_los_nulos`](impacto/app-ai_context.md) | `app/ai_context.py:230` | 2 | **0** | 0 | **2** |
| [`app.ai_context.verdict_history`](impacto/app-ai_context.md) | `app/ai_context.py:452` | 2 | **0** | 0 | **2** |
| [`app.api._session_window`](impacto/app-api.md) | `app/api.py:448` | 2 | **0** | 0 | **2** |
| [`app.scalp_logic.horizon_structure`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1679` | 2 | **0** | 0 | **2** |
| [`app.scalp_logic.hypothesis_evidence`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4690` | 2 | **0** | 0 | **2** |
| [`app.scalp_logic.liquidation_burst`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1696` | 2 | **0** | 0 | **2** |
| [`app.scalp_logic.setup_confirmation_bundle`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:2330` | 2 | **0** | 0 | **2** |
| [`app.setups._bars_closed_beyond`](impacto/app-setups.md) | `app/setups.py:805` | 2 | **0** | 0 | **2** |
| [`app.setups._breakout_frontier`](impacto/app-setups.md) | `app/setups.py:741` | 2 | **0** | 0 | **2** |
| [`app.setups._gap_in`](impacto/app-setups.md) | `app/setups.py:798` | 2 | **0** | 0 | **2** |
| [`app.setups._last_pivots`](impacto/app-setups.md) | `app/setups.py:927` | 2 | **0** | 0 | **2** |
| [`app.setups._level_defended`](impacto/app-setups.md) | `app/setups.py:1003` | 2 | **0** | 0 | **2** |
| [`app.setups._norm_bars`](impacto/app-setups.md) | `app/setups.py:777` | 2 | **0** | 0 | **2** |
| [`app.setups._obs`](impacto/app-setups.md) | `app/setups.py:716` | 2 | **0** | 0 | **2** |
| [`app.setups._pullback`](impacto/app-setups.md) | `app/setups.py:934` | 2 | **0** | 0 | **2** |
| [`app.setups._retest_done`](impacto/app-setups.md) | `app/setups.py:891` | 2 | **0** | 0 | **2** |
| [`app.setups._returned_inside`](impacto/app-setups.md) | `app/setups.py:844` | 2 | **0** | 0 | **2** |
| [`app.setups._structure_event`](impacto/app-setups.md) | `app/setups.py:665` | 2 | **0** | 0 | **2** |
| [`app.setups._tolerance`](impacto/app-setups.md) | `app/setups.py:762` | 2 | **0** | 0 | **2** |
| [`app.setups.build_setup_context`](impacto/app-setups.md) | `app/setups.py:1100` | 2 | **0** | 0 | **2** |
| [`app.setups.evaluate_setup`](impacto/app-setups.md) | `app/setups.py:1218` | 2 | **0** | 0 | **2** |
| [`app.setups.setup_observables`](impacto/app-setups.md) | `app/setups.py:1057` | 2 | **0** | 0 | **2** |
| [`app.setups.split_hypothesis`](impacto/app-setups.md) | `app/setups.py:88` | 2 | **0** | 0 | **2** |
| [`app.scalp_collector._write_ladders`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:864` | 0 | **1** | 19 ↑ | **1** |
| [`app.signal_execution.persist_signal_execution_snapshots`](impacto/app-signal_execution.md) | `app/signal_execution.py:429` | 0 | **1** | 10 ↑ | **1** |
| [`app.signal_replay.persist_signal_replay_frame`](impacto/app-signal_replay.md) | `app/signal_replay.py:90` | 0 | **1** | 10 ↑ | **1** |
| [`app.api.health`](impacto/app-api.md) | `app/api.py:3209` | 1 | **0** | 7 ↑ | **1** |
| [`app.db.db_identity`](impacto/app-db.md) | `app/db.py:64` | 1 | **0** | 7 ↑ | **1** |
| [`app.db.heartbeat_max_age`](impacto/app-db.md) | `app/db.py:95` | 1 | **0** | 7 ↑ | **1** |
| [`app.ai_context.build_ai_context`](impacto/app-ai_context.md) | `app/ai_context.py:958` | 1 | **0** | 0 | **1** |
| [`app.api._parse_heartbeat_detail`](impacto/app-api.md) | `app/api.py:3113` | 1 | **0** | 0 | **1** |
| [`app.api._slippage_para`](impacto/app-api.md) | `app/api.py:1451` | 1 | **0** | 0 | **1** |
| [`app.api.ai_context`](impacto/app-api.md) | `app/api.py:3052` | 1 | **0** | 0 | **1** |
| [`app.api.ai_context_bundle`](impacto/app-api.md) | `app/api.py:3069` | 1 | **0** | 0 | **1** |
| [`app.api.ai_profiles`](impacto/app-api.md) | `app/api.py:3090` | 1 | **0** | 0 | **1** |
| [`app.api.context_metadata_endpoint`](impacto/app-api.md) | `app/api.py:1747` | 1 | **0** | 0 | **1** |
| [`app.api.cross_asset_endpoint`](impacto/app-api.md) | `app/api.py:1761` | 1 | **0** | 0 | **1** |
| [`app.api.cvd`](impacto/app-api.md) | `app/api.py:699` | 1 | **0** | 0 | **1** |
| [`app.api.cvd_divergence`](impacto/app-api.md) | `app/api.py:820` | 1 | **0** | 0 | **1** |
| [`app.api.cvd_matrix_endpoint`](impacto/app-api.md) | `app/api.py:1803` | 1 | **0** | 0 | **1** |
| [`app.api.cvd_spot`](impacto/app-api.md) | `app/api.py:747` | 1 | **0** | 0 | **1** |
| [`app.api.daily`](impacto/app-api.md) | `app/api.py:1946` | 1 | **0** | 0 | **1** |
| [`app.api.dashboard_state`](impacto/app-api.md) | `app/api.py:3021` | 1 | **0** | 0 | **1** |
| [`app.api.data_confidence`](impacto/app-api.md) | `app/api.py:2628` | 1 | **0** | 0 | **1** |
| [`app.api.delta_profile_endpoint`](impacto/app-api.md) | `app/api.py:1646` | 1 | **0** | 0 | **1** |
| [`app.api.desk_state`](impacto/app-api.md) | `app/api.py:1239` | 1 | **0** | 0 | **1** |
| [`app.api.divergences_endpoint`](impacto/app-api.md) | `app/api.py:1835` | 1 | **0** | 0 | **1** |
| [`app.api.external_macro_endpoint`](impacto/app-api.md) | `app/api.py:1825` | 1 | **0** | 0 | **1** |
| [`app.api.flow_spot_vs_perp`](impacto/app-api.md) | `app/api.py:1470` | 1 | **0** | 0 | **1** |
| [`app.api.funding_context_endpoint`](impacto/app-api.md) | `app/api.py:1625` | 1 | **0** | 0 | **1** |
| [`app.api.hypothesis`](impacto/app-api.md) | `app/api.py:1158` | 1 | **0** | 0 | **1** |
| [`app.api.index`](impacto/app-api.md) | `app/api.py:3323` | 1 | **0** | 0 | **1** |
| [`app.api.level_breakout_endpoint`](impacto/app-api.md) | `app/api.py:1725` | 1 | **0** | 0 | **1** |
| [`app.api.liquidation_levels`](impacto/app-api.md) | `app/api.py:2568` | 1 | **0** | 0 | **1** |
| [`app.api.liquidation_map_endpoint`](impacto/app-api.md) | `app/api.py:1632` | 1 | **0** | 0 | **1** |
| [`app.api.liquidation_series`](impacto/app-api.md) | `app/api.py:987` | 1 | **0** | 0 | **1** |
| [`app.api.macro_context_endpoint`](impacto/app-api.md) | `app/api.py:1818` | 1 | **0** | 0 | **1** |
| [`app.api.market_impact_endpoint`](impacto/app-api.md) | `app/api.py:1142` | 1 | **0** | 0 | **1** |
| [`app.api.market_memory_endpoint`](impacto/app-api.md) | `app/api.py:1842` | 1 | **0** | 0 | **1** |
| [`app.api.metric_baselines`](impacto/app-api.md) | `app/api.py:1357` | 1 | **0** | 0 | **1** |
| [`app.api.ohlcv`](impacto/app-api.md) | `app/api.py:635` | 1 | **0** | 0 | **1** |
| [`app.api.oi`](impacto/app-api.md) | `app/api.py:938` | 1 | **0** | 0 | **1** |
| [`app.api.oi_context_endpoint`](impacto/app-api.md) | `app/api.py:1768` | 1 | **0** | 0 | **1** |
| [`app.api.passive_flow_endpoint`](impacto/app-api.md) | `app/api.py:1796` | 1 | **0** | 0 | **1** |
| [`app.api.positioning`](impacto/app-api.md) | `app/api.py:1150` | 1 | **0** | 0 | **1** |
| [`app.api.price_barriers_endpoint`](impacto/app-api.md) | `app/api.py:1667` | 1 | **0** | 0 | **1** |
| [`app.api.prometheus_metrics`](impacto/app-api.md) | `app/api.py:3131` | 1 | **0** | 0 | **1** |
| [`app.api.quality_feeds`](impacto/app-api.md) | `app/api.py:1341` | 1 | **0** | 0 | **1** |
| [`app.api.range_validate_endpoint`](impacto/app-api.md) | `app/api.py:1691` | 1 | **0** | 0 | **1** |
| [`app.api.reference_levels_endpoint`](impacto/app-api.md) | `app/api.py:1754` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_absorption`](impacto/app-api.md) | `app/api.py:1503` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_alerts`](impacto/app-api.md) | `app/api.py:1519` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_basis`](impacto/app-api.md) | `app/api.py:2561` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_delta_matrix`](impacto/app-api.md) | `app/api.py:1115` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_execution_cost`](impacto/app-api.md) | `app/api.py:1395` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_liquidations`](impacto/app-api.md) | `app/api.py:1512` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_orderbook`](impacto/app-api.md) | `app/api.py:1487` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_persistence`](impacto/app-api.md) | `app/api.py:2681` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_signals`](impacto/app-api.md) | `app/api.py:2046` | 1 | **0** | 0 | **1** |
| [`app.api.scalp_summary`](impacto/app-api.md) | `app/api.py:1107` | 1 | **0** | 0 | **1** |
| [`app.api.setup`](impacto/app-api.md) | `app/api.py:2031` | 1 | **0** | 0 | **1** |
| [`app.api.signal_base_rate`](impacto/app-api.md) | `app/api.py:2896` | 1 | **0** | 0 | **1** |
| [`app.api.signals_execution`](impacto/app-api.md) | `app/api.py:2309` | 1 | **0** | 0 | **1** |
| [`app.api.signals_ledger`](impacto/app-api.md) | `app/api.py:2136` | 1 | **0** | 0 | **1** |
| [`app.api.signals_outcomes`](impacto/app-api.md) | `app/api.py:2223` | 1 | **0** | 0 | **1** |
| [`app.api.signals_replay`](impacto/app-api.md) | `app/api.py:2396` | 1 | **0** | 0 | **1** |
| [`app.api.signals_visibility`](impacto/app-api.md) | `app/api.py:2479` | 1 | **0** | 0 | **1** |
| [`app.api.snapshot`](impacto/app-api.md) | `app/api.py:615` | 1 | **0** | 0 | **1** |
| [`app.api.statistical_alerts`](impacto/app-api.md) | `app/api.py:1583` | 1 | **0** | 0 | **1** |
| [`app.api.stream`](impacto/app-api.md) | `app/api.py:3314` | 1 | **0** | 0 | **1** |
| [`app.api.stream_generator`](impacto/app-api.md) | `app/api.py:3266` | 1 | **0** | 0 | **1** |
| [`app.api.structure`](impacto/app-api.md) | `app/api.py:1939` | 1 | **0** | 0 | **1** |
| [`app.api.structure_detail_endpoint`](impacto/app-api.md) | `app/api.py:1811` | 1 | **0** | 0 | **1** |
| [`app.api.swing_score_endpoint`](impacto/app-api.md) | `app/api.py:1782` | 1 | **0** | 0 | **1** |
| [`app.api.symbols`](impacto/app-api.md) | `app/api.py:610` | 1 | **0** | 0 | **1** |
| [`app.api.trading_profile`](impacto/app-api.md) | `app/api.py:1375` | 1 | **0** | 0 | **1** |
| [`app.api.trend_matrix_endpoint`](impacto/app-api.md) | `app/api.py:1789` | 1 | **0** | 0 | **1** |
| [`app.api.verdicts`](impacto/app-api.md) | `app/api.py:1849` | 1 | **0** | 0 | **1** |
| [`app.api.volatility_endpoint`](impacto/app-api.md) | `app/api.py:1775` | 1 | **0** | 0 | **1** |
| [`app.api.volume_profile_endpoint`](impacto/app-api.md) | `app/api.py:1639` | 1 | **0** | 0 | **1** |
| [`app.api.whale_delta`](impacto/app-api.md) | `app/api.py:1037` | 1 | **0** | 0 | **1** |
| [`app.api.wyckoff_endpoint`](impacto/app-api.md) | `app/api.py:1739` | 1 | **0** | 0 | **1** |
| [`app.api.zone_analysis_endpoint`](impacto/app-api.md) | `app/api.py:1674` | 1 | **0** | 0 | **1** |
| [`app.breakout._atr`](impacto/app-breakout.md) | `app/breakout.py:58` | 1 | **0** | 0 | **1** |
| [`app.breakout._confirmation_checks`](impacto/app-breakout.md) | `app/breakout.py:330` | 1 | **0** | 0 | **1** |
| [`app.breakout._delta_usd`](impacto/app-breakout.md) | `app/breakout.py:77` | 1 | **0** | 0 | **1** |
| [`app.breakout._rate`](impacto/app-breakout.md) | `app/breakout.py:187` | 1 | **0** | 0 | **1** |
| [`app.breakout.attempt_features`](impacto/app-breakout.md) | `app/breakout.py:149` | 1 | **0** | 0 | **1** |
| [`app.breakout.breakout_read`](impacto/app-breakout.md) | `app/breakout.py:215` | 1 | **0** | 0 | **1** |
| [`app.breakout.build_corpus`](impacto/app-breakout.md) | `app/breakout.py:173` | 1 | **0** | 0 | **1** |
| [`app.breakout.classify_outcome`](impacto/app-breakout.md) | `app/breakout.py:125` | 1 | **0** | 0 | **1** |
| [`app.breakout.find_attempts`](impacto/app-breakout.md) | `app/breakout.py:90` | 1 | **0** | 0 | **1** |
| [`app.breakout.wilson_ci`](impacto/app-breakout.md) | `app/breakout.py:46` | 1 | **0** | 0 | **1** |
| [`app.delta_profile._floor_log10`](impacto/app-delta_profile.md) | `app/delta_profile.py:79` | 1 | **0** | 0 | **1** |
| [`app.delta_profile.bucket_index`](impacto/app-delta_profile.md) | `app/delta_profile.py:69` | 1 | **0** | 0 | **1** |
| [`app.delta_profile.bucket_size`](impacto/app-delta_profile.md) | `app/delta_profile.py:56` | 1 | **0** | 0 | **1** |
| [`app.delta_profile.delta_profile`](impacto/app-delta_profile.md) | `app/delta_profile.py:222` | 1 | **0** | 0 | **1** |
| [`app.delta_profile.profile_read`](impacto/app-delta_profile.md) | `app/delta_profile.py:115` | 1 | **0** | 0 | **1** |
| [`app.delta_profile.value_area`](impacto/app-delta_profile.md) | `app/delta_profile.py:92` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.execution_cost`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5182` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.level_breakout`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1632` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.range_validate`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1507` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.spot_perp_flow`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:5686` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.walk_book`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:4878` | 1 | **0** | 0 | **1** |
| [`app.scalp_logic.zone_analysis`](impacto/app-scalp_logic.md) | `app/scalp_logic.py:1364` | 1 | **0** | 0 | **1** |
| [`app.signal_visibility._certify_final_outcomes_once`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:249` | 0 | **1** | 1 | **1** |
| [`app.zones._atr_pct`](impacto/app-zones.md) | `app/zones.py:104` | 1 | **0** | 0 | **1** |
| [`app.zones._clamp`](impacto/app-zones.md) | `app/zones.py:100` | 1 | **0** | 0 | **1** |
| [`app.zones._effort_result`](impacto/app-zones.md) | `app/zones.py:128` | 1 | **0** | 0 | **1** |
| [`app.zones._narrative`](impacto/app-zones.md) | `app/zones.py:394` | 1 | **0** | 0 | **1** |
| [`app.zones._oi_behaviour`](impacto/app-zones.md) | `app/zones.py:208` | 1 | **0** | 0 | **1** |
| [`app.zones._percentile`](impacto/app-zones.md) | `app/zones.py:121` | 1 | **0** | 0 | **1** |
| [`app.zones._rejection`](impacto/app-zones.md) | `app/zones.py:194` | 1 | **0** | 0 | **1** |
| [`app.zones.zone_character_read`](impacto/app-zones.md) | `app/zones.py:220` | 1 | **0** | 0 | **1** |
| [`app.db.assert_service_ownership`](impacto/app-db.md) | `app/db.py:301` | 0 | **0** | 62 ↑ | **0** |
| [`app.db.fenced_transaction`](impacto/app-db.md) | `app/db.py:333` | 0 | **0** | 62 ↑ | **0** |
| [`app.daily_agg.refresh_baselines`](impacto/app-daily_agg.md) | `app/daily_agg.py:713` | 0 | **0** | 53 ↑ | **0** |
| [`app.db.heartbeat_owned`](impacto/app-db.md) | `app/db.py:431` | 0 | **0** | 53 ↑ | **0** |
| [`app.ingest._reconcile_persisted_cadence`](impacto/app-ingest.md) | `app/ingest.py:453` | 0 | **0** | 52 ↑ | **0** |
| [`app.daily_agg.backfill`](impacto/app-daily_agg.md) | `app/daily_agg.py:299` | 0 | **0** | 51 ↑ | **0** |
| [`app.daily_agg.cycle`](impacto/app-daily_agg.md) | `app/daily_agg.py:799` | 0 | **0** | 51 ↑ | **0** |
| [`app.daily_agg.latest_closed_session_date`](impacto/app-daily_agg.md) | `app/daily_agg.py:45` | 0 | **0** | 51 ↑ | **0** |
| [`app.daily_agg.rollup_open_interest_daily`](impacto/app-daily_agg.md) | `app/daily_agg.py:558` | 0 | **0** | 51 ↑ | **0** |
| [`app.daily_agg.ventana_barrido_5m`](impacto/app-daily_agg.md) | `app/daily_agg.py:613` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest.barrido_cadencia_persistido`](impacto/app-ingest.md) | `app/ingest.py:568` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest.finite`](impacto/app-ingest.md) | `app/ingest.py:46` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest.rows_for`](impacto/app-ingest.md) | `app/ingest.py:89` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest.valid_ts`](impacto/app-ingest.md) | `app/ingest.py:59` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest.ventana_barrido_cadencia`](impacto/app-ingest.md) | `app/ingest.py:538` | 0 | **0** | 51 ↑ | **0** |
| [`app.partitioning.apply_temporal_retention`](impacto/app-partitioning.md) | `app/partitioning.py:25` | 0 | **0** | 51 ↑ | **0** |
| [`app.ingest._reconcile_response_cadence`](impacto/app-ingest.md) | `app/ingest.py:619` | 0 | **0** | 47 ↑ | **0** |
| [`app.cutoffs.ClosedCutoff.at`](impacto/app-cutoffs.md) | `app/cutoffs.py:22` | 0 | **0** | 43 ↑ | **0** |
| [`app.metrics.compute_and_store_all`](impacto/app-metrics.md) | `app/metrics.py:711` | 0 | **0** | 43 ↑ | **0** |
| [`app.ingest._coverage_heartbeat_detail`](impacto/app-ingest.md) | `app/ingest.py:687` | 0 | **0** | 41 ↑ | **0** |
| [`app.ingest.publish_snapshot`](impacto/app-ingest.md) | `app/ingest.py:367` | 0 | **0** | 41 ↑ | **0** |
| [`app.ingest.ingest_ohlcv_cycle`](impacto/app-ingest.md) | `app/ingest.py:746` | 0 | **0** | 39 ↑ | **0** |
| [`app.scalp_collector.owns_global_cleanup`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1524` | 0 | **0** | 25 ↑ | **0** |
| [`app.signal_outcomes.materialize_due_signal_outcomes`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:289` | 0 | **0** | 24 ↑ | **0** |
| [`app.signal_visibility.run_certification_cycle`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:363` | 0 | **0** | 24 ↑ | **0** |
| [`app.data_gaps.DataGap.from_record`](impacto/app-data_gaps.md) | `app/data_gaps.py:1140` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps._cubierto_por_otro_detector`](impacto/app-data_gaps.md) | `app/data_gaps.py:439` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps._load_gap`](impacto/app-data_gaps.md) | `app/data_gaps.py:1220` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.missing_cadence_windows`](impacto/app-data_gaps.md) | `app/data_gaps.py:378` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.partition_gap_by_source_coverage`](impacto/app-data_gaps.md) | `app/data_gaps.py:967` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.partition_runs`](impacto/app-data_gaps.md) | `app/data_gaps.py:922` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.record_event_stream_loss`](impacto/app-data_gaps.md) | `app/data_gaps.py:348` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.recover_unresolved_gaps`](impacto/app-data_gaps.md) | `app/data_gaps.py:1333` | 0 | **0** | 21 ↑ | **0** |
| [`app.data_gaps.validate_recovery`](impacto/app-data_gaps.md) | `app/data_gaps.py:1176` | 0 | **0** | 21 ↑ | **0** |
| [`app.db.acquire_service_lock`](impacto/app-db.md) | `app/db.py:262` | 0 | **0** | 21 ↑ | **0** |
| [`app.db.create_pool`](impacto/app-db.md) | `app/db.py:162` | 0 | **0** | 21 ↑ | **0** |
| [`app.db.monitor_service_lock`](impacto/app-db.md) | `app/db.py:343` | 0 | **0** | 21 ↑ | **0** |
| [`app.db.read_db_identity`](impacto/app-db.md) | `app/db.py:69` | 0 | **0** | 21 ↑ | **0** |
| [`app.db.sync_market_catalog`](impacto/app-db.md) | `app/db.py:235` | 0 | **0** | 21 ↑ | **0** |
| [`app.partitioning.ensure_temporal_partitions`](impacto/app-partitioning.md) | `app/partitioning.py:20` | 0 | **0** | 21 ↑ | **0** |
| [`app.scalp_collector._write_trade_rows`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:710` | 0 | **0** | 21 ↑ | **0** |
| [`app.scalp_collector.flush_trades`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:637` | 0 | **0** | 21 ↑ | **0** |
| [`app.daily_agg._coverage_complete`](impacto/app-daily_agg.md) | `app/daily_agg.py:73` | 0 | **0** | 20 ↑ | **0** |
| [`app.daily_agg._expected_session_samples`](impacto/app-daily_agg.md) | `app/daily_agg.py:64` | 0 | **0** | 20 ↑ | **0** |
| [`app.db.mark_feed_shard_degraded`](impacto/app-db.md) | `app/db.py:792` | 0 | **0** | 20 ↑ | **0** |
| [`app.metrics.liquidation_history_observation`](impacto/app-metrics.md) | `app/metrics.py:252` | 0 | **0** | 20 ↑ | **0** |
| [`app.scalp_collector.all_expected_fresh`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:629` | 0 | **0** | 20 ↑ | **0** |
| [`app.scalp_collector.monitor`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1452` | 0 | **0** | 20 ↑ | **0** |
| [`app.scalp_collector.persist_liquidation_health_snapshot`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:525` | 0 | **0** | 20 ↑ | **0** |
| [`app.scalp_collector.binance_loop`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:988` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.binance_market_loop`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1098` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.bybit_loop`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1150` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.cleanup`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1559` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.drenar_minutos`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:682` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.handle_binance`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1044` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.handle_bybit`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1236` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.main`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:1575` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.mark_exchange_disconnected`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:624` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.persist_liquidation_feed_state`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:463` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.reset_liquidation_feed_health`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:604` | 0 | **0** | 19 ↑ | **0** |
| [`app.scalp_collector.segundos_cubiertos`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:673` | 0 | **0** | 17 ↑ | **0** |
| [`app.ws_collector.drain_closed_minutes`](impacto/app-ws_collector.md) | `app/ws_collector.py:323` | 0 | **0** | 17 ↑ | **0** |
| [`app.ws_collector.flush_minute`](impacto/app-ws_collector.md) | `app/ws_collector.py:311` | 0 | **0** | 17 ↑ | **0** |
| [`app.db.wait_for_stop_or_lock_loss`](impacto/app-db.md) | `app/db.py:374` | 0 | **0** | 14 ↑ | **0** |
| [`app.logging_setup.configure_logging`](impacto/app-logging_setup.md) | `app/logging_setup.py:7` | 0 | **0** | 14 ↑ | **0** |
| [`app.ws_collector.heartbeat_loop`](impacto/app-ws_collector.md) | `app/ws_collector.py:515` | 0 | **0** | 14 ↑ | **0** |
| [`app.db.mark_feed_shard_connected`](impacto/app-db.md) | `app/db.py:768` | 0 | **0** | 12 ↑ | **0** |
| [`app.sharding.assigned_symbols`](impacto/app-sharding.md) | `app/sharding.py:13` | 0 | **0** | 12 ↑ | **0** |
| [`app.sharding.symbol_shard`](impacto/app-sharding.md) | `app/sharding.py:6` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.binance_consumer`](impacto/app-ws_collector.md) | `app/ws_collector.py:424` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.binance_url`](impacto/app-ws_collector.md) | `app/ws_collector.py:208` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.bybit_consumer`](impacto/app-ws_collector.md) | `app/ws_collector.py:466` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.run`](impacto/app-ws_collector.md) | `app/ws_collector.py:575` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.spot_pairs`](impacto/app-ws_collector.md) | `app/ws_collector.py:204` | 0 | **0** | 12 ↑ | **0** |
| [`app.ws_collector.valid_trade`](impacto/app-ws_collector.md) | `app/ws_collector.py:213` | 0 | **0** | 12 ↑ | **0** |
| [`app.external_macro._get`](impacto/app-external_macro.md) | `app/external_macro.py:472` | 0 | **0** | 11 ↑ | **0** |
| [`app.external_macro.parse_bls_calendar`](impacto/app-external_macro.md) | `app/external_macro.py:113` | 0 | **0** | 11 ↑ | **0** |
| [`app.external_macro.parse_coinglass_etf`](impacto/app-external_macro.md) | `app/external_macro.py:88` | 0 | **0** | 11 ↑ | **0** |
| [`app.external_macro.parse_fomc_calendar`](impacto/app-external_macro.md) | `app/external_macro.py:150` | 0 | **0** | 11 ↑ | **0** |
| [`app.external_macro.parse_fred_csv`](impacto/app-external_macro.md) | `app/external_macro.py:58` | 0 | **0** | 11 ↑ | **0** |
| [`app.external_macro.parse_stablecoin_history`](impacto/app-external_macro.md) | `app/external_macro.py:74` | 0 | **0** | 11 ↑ | **0** |
| [`app.ingest._liquidation_history_observation`](impacto/app-ingest.md) | `app/ingest.py:649` | 0 | **0** | 11 ↑ | **0** |
| [`app.ingest.ingest_metrics_cycle`](impacto/app-ingest.md) | `app/ingest.py:814` | 0 | **0** | 11 ↑ | **0** |
| [`app.ingest.source_response_buckets`](impacto/app-ingest.md) | `app/ingest.py:66` | 0 | **0** | 11 ↑ | **0** |
| [`app.ingest.upsert_ohlc_metric`](impacto/app-ingest.md) | `app/ingest.py:240` | 0 | **0** | 11 ↑ | **0** |
| [`app.signal_execution.load_signal_execution_inputs`](impacto/app-signal_execution.md) | `app/signal_execution.py:410` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_ledger._validated_required_fields`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:201` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_ledger.classify_signal_observation`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:62` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_ledger.decision_fingerprint`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:179` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_ledger.select_reference_price`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:95` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_ledger.serialize_signal_evidence`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:166` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_outcomes._aware_utc`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:57` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_outcomes._finite_positive`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:63` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_outcomes.compute_path_metrics`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:96` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_outcomes.expected_bar_timestamps`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:89` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_replay.replay_context_as_of`](impacto/app-signal_replay.md) | `app/signal_replay.py:76` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_visibility.certify_final_outcomes`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:347` | 0 | **0** | 10 ↑ | **0** |
| [`app.signal_visibility.certify_research_bundles`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:328` | 0 | **0** | 10 ↑ | **0** |
| [`app.ws_collector.segundos_cubiertos`](impacto/app-ws_collector.md) | `app/ws_collector.py:46` | 0 | **0** | 10 ↑ | **0** |
| [`app.db.mark_feed_degraded`](impacto/app-db.md) | `app/db.py:629` | 0 | **0** | 9 ↑ | **0** |
| [`app.db.mark_feed_error`](impacto/app-db.md) | `app/db.py:639` | 0 | **0** | 9 ↑ | **0** |
| [`app.db.mark_feed_shard_error`](impacto/app-db.md) | `app/db.py:817` | 0 | **0** | 9 ↑ | **0** |
| [`app.metrics._liquidation_history_observed`](impacto/app-metrics.md) | `app/metrics.py:315` | 0 | **0** | 8 ↑ | **0** |
| [`app.metrics.compute_regime`](impacto/app-metrics.md) | `app/metrics.py:166` | 0 | **0** | 8 ↑ | **0** |
| [`app.metrics.compute_snapshot`](impacto/app-metrics.md) | `app/metrics.py:429` | 0 | **0** | 8 ↑ | **0** |
| [`app.metrics.normalized_cvd_imbalance`](impacto/app-metrics.md) | `app/metrics.py:146` | 0 | **0** | 8 ↑ | **0** |
| [`app.metrics.optional_finite`](impacto/app-metrics.md) | `app/metrics.py:50` | 0 | **0** | 8 ↑ | **0** |
| [`app.metrics.whale_classification`](impacto/app-metrics.md) | `app/metrics.py:66` | 0 | **0** | 8 ↑ | **0** |
| [`app.api.lifespan`](impacto/app-api.md) | `app/api.py:144` | 0 | **0** | 7 ↑ | **0** |
| [`app.coinalyze.validate_rate_budget`](impacto/app-coinalyze.md) | `app/coinalyze.py:116` | 0 | **0** | 7 ↑ | **0** |
| [`app.ingest.run`](impacto/app-ingest.md) | `app/ingest.py:1032` | 0 | **0** | 7 ↑ | **0** |
| [`app.ingest.run_aligned_feed`](impacto/app-ingest.md) | `app/ingest.py:1006` | 0 | **0** | 7 ↑ | **0** |
| [`app.ingest.seconds_until_aligned_run`](impacto/app-ingest.md) | `app/ingest.py:997` | 0 | **0** | 7 ↑ | **0** |
| [`app.scalp_collector.persist_liquidation_event_loss`](impacto/app-scalp_collector.md) | `app/scalp_collector.py:580` | 0 | **0** | 7 ↑ | **0** |
| [`app.signal_execution._canonical_json`](impacto/app-signal_execution.md) | `app/signal_execution.py:139` | 0 | **0** | 6 ↑ | **0** |
| [`app.signal_execution.execution_snapshot_record`](impacto/app-signal_execution.md) | `app/signal_execution.py:263` | 0 | **0** | 6 ↑ | **0** |
| [`app.signal_ledger._finite`](impacto/app-signal_ledger.md) | `app/signal_ledger.py:52` | 0 | **0** | 6 ↑ | **0** |
| [`app.signal_outcomes.outcome_window`](impacto/app-signal_outcomes.md) | `app/signal_outcomes.py:73` | 0 | **0** | 6 ↑ | **0** |
| [`app.signal_replay.canonical_json_object`](impacto/app-signal_replay.md) | `app/signal_replay.py:49` | 0 | **0** | 6 ↑ | **0** |
| [`app.external_macro._plain_html`](impacto/app-external_macro.md) | `app/external_macro.py:146` | 0 | **0** | 3 ↑ | **0** |
| [`app.external_macro._unfold_ics`](impacto/app-external_macro.md) | `app/external_macro.py:103` | 0 | **0** | 3 ↑ | **0** |
| [`app.signal_execution._aware_utc`](impacto/app-signal_execution.md) | `app/signal_execution.py:127` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_execution._cost_curve`](impacto/app-signal_execution.md) | `app/signal_execution.py:245` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_execution._decode_depth_levels`](impacto/app-signal_execution.md) | `app/signal_execution.py:168` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_execution._hash_book_payload`](impacto/app-signal_execution.md) | `app/signal_execution.py:150` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_execution._ordered_depth`](impacto/app-signal_execution.md) | `app/signal_execution.py:189` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_visibility._aware_utc`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:141` | 0 | **0** | 1 ↑ | **0** |
| [`app.signal_visibility._validate_batch_size`](impacto/app-signal_visibility.md) | `app/signal_visibility.py:147` | 0 | **0** | 1 ↑ | **0** |

La flecha ↑ marca las funciones cuya cota es mas ancha que su dato exacto: ahi el
numero de la cota **es un techo**, no una lista de afectadas.

## C · los tres controles de respuesta conocida

Un grafo de impacto es facil de mirar y dificil de creer: sale un numero y no hay con
que contrastarlo. Estos tres tienen respuesta conocida de antes, y los mide el propio
generador en cada corrida, asi que K88 los compara sin que nadie se acuerde de nada.

| control | esperado | cuadra |
|---|---|---|
| `compute_snapshot` | por_llamada vacio; por_tabla == las lectoras de metrics_snapshot | **si** |
| `spot_trades_agg` | 2 INSERT en app/ws_collector.py y 1 DELETE en app/daily_agg.py | **si** |
| `liquidations_realtime` | 1 escritor en app/scalp_collector.py:74 y 14 rutas lectoras | **si** |

Los tres cuadran: **True**.
