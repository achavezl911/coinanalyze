# `GET /api/desk/state`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `desk_state` · `app/api.py:1216` (cuerpo hasta la 1314) · decorador en la linea 1215.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `profile` | `str` | `'intradia'` | no |
| `direction` | `str | None` | `None` | no |
| `setup` | `str` | `'ninguno'` | no |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:1288 |
| `components` | literal en app/api.py:1292 |
| `direction` | literal en app/api.py:1290 |
| `note` | literal en app/api.py:1309 |
| `partial` | literal en app/api.py:1303 |
| `profile` | literal en app/api.py:1289 |
| `setup` | literal en app/api.py:1291 |
| `source_timestamps` | literal en app/api.py:1293 |
| `symbol` | literal en app/api.py:1287 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1092`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1243`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1262`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1311`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:322`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:584`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:663`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:687`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
- `futures_trades_agg` — `sql/schema.sql:273`, 9 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1538`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:802`
- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:780`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `spot_trades_agg` — `sql/schema.sql:198`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:376`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:393`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `choice`
- `edges`
- `exchanges`
- `now`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

76 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.data_quality` — `app/scalp_logic.py:3973`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4277`
- `app.scalp_logic.hypothesis_evidence` — `app/scalp_logic.py:4690`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1235`
- `app.scalp_logic.profile_view` — `app/scalp_logic.py:4498`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`
- `app.scalp_logic.setup_confirmation_bundle` — `app/scalp_logic.py:2330`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2283`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:5846`
- `app.setups.build_setup_context` — `app/setups.py:1100`

<details><summary>Alcanzables de forma indirecta (63)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.interpretation._barrier_candidates` — `app/interpretation.py:684`
- `app.interpretation._barrier_zones` — `app/interpretation.py:779`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.interpretation.price_barrier_read` — `app/interpretation.py:877`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._atr` — `app/scalp_logic.py:2926`
- `app.scalp_logic._banda` — `app/scalp_logic.py:4963`
- `app.scalp_logic._bps` — `app/scalp_logic.py:4956`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2275`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._flow_bias` — `app/scalp_logic.py:4485`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2416`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2424`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2431`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4071`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4041`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4053`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4245`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4161`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2226`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2212`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:2915`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.execution_assessment` — `app/scalp_logic.py:4972`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4419`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2619`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2609`
- `app.setups._bars_closed_beyond` — `app/setups.py:805`
- `app.setups._breakout_frontier` — `app/setups.py:741`
- `app.setups._gap_in` — `app/setups.py:798`
- `app.setups._last_pivots` — `app/setups.py:927`
- `app.setups._level_defended` — `app/setups.py:1003`
- `app.setups._norm_bars` — `app/setups.py:777`
- `app.setups._obs` — `app/setups.py:716`
- `app.setups._pullback` — `app/setups.py:934`
- `app.setups._retest_done` — `app/setups.py:891`
- `app.setups._returned_inside` — `app/setups.py:844`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups._structure_event` — `app/setups.py:665`
- `app.setups._tolerance` — `app/setups.py:762`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.evaluate_setup` — `app/setups.py:1218`
- `app.setups.oi_price_reading` — `app/setups.py:228`
- `app.setups.setup_observables` — `app/setups.py:1057`
- `app.setups.split_hypothesis` — `app/setups.py:88`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `app.state.pool.acquire`
- `as_of.isoformat`
- `componentes.values`
- `isinstance`
- `quality.get`
- `scalp.get`
- `view.get`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | — | `app/api.py:1236` | el propio handler |
| 422 | — | `app/api.py:1240` | el propio handler |
| 422 | — | `app/api.py:1244` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

Radio por tabla calculado **hasta k=2**; lo que este mas arriba **no se afirma**.

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | por tabla | total | detalle |
|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | 9 | **44** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | 10 | **32** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | 14 | **31** | [impacto](../impacto/app-data_gaps.md) |
| `app.metrics.current_nyse_start` | 15 | 14 | **26** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 9 | 24 | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 9 | 24 | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 14 | 9 | **21** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 13 | 9 | **20** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.basis_quality` | 10 | 9 | **17** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 10 | 9 | **17** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 9 | 9 | **16** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 9 | 9 | **16** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 9 | 9 | **16** | [impacto](../impacto/app-setups.md) |
| `app.interpretation.number` | 13 | 3 | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 13 | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 13 | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 52 mas_ | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
