# `GET /api/ai/context/bundle`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `ai_context_bundle` · `app/api.py:3715` (cuerpo hasta la 3732) · decorador en la linea 3714.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbols` | `str | None` | `None` | no |
| `profile` | `str` | `'default'` | no |
| `bucket_bps` | `Annotated[int, Query(ge=1, le=100)]` | `10` | no |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `build_finished_at` | asignado en app/ai_context.py:1127 |
| `build_started_at` | asignado en app/ai_context.py:1126 |
| `generated_at` | literal en app/ai_context.py:1121 |
| `interpretation_prompt` | literal en app/ai_context.py:1119 |
| `local_alerts` | literal en app/ai_context.py:1123 |
| `profile` | literal en app/ai_context.py:1122 |
| `rough_token_estimate` | asignado en app/ai_context.py:1128 |
| `schema_version` | literal en app/ai_context.py:1118 |
| `symbols` | literal en app/ai_context.py:1124 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- una clave del objeto es una expresion, no un literal

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1039`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `daily_verdict_outcome` — `sql/schema.sql:2307`, 10 columnas
  - la llena `app.daily_agg.materialize_daily_verdict_outcomes` (INSERT) — `app/daily_agg.py:525`
- `daily_verdict_snapshot` — `sql/schema.sql:1106`, 26 columnas
  - la llena `app.daily_agg.persist_verdicts` (INSERT) — `app/daily_agg.py:436`
- `data_gap` — `sql/schema.sql:1419`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1109`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1260`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1279`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1334`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:337`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:599`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:678`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:702`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:779`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:779`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:877`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:877`
  - la llena `app.libro.declara_hueco` (UPDATE) — `app/libro.py:792`
  - la llena `app.orderflow.declara_hueco` (UPDATE) — `app/orderflow.py:508`
- `external_macro_observation` — `sql/schema.sql:1241`, 5 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:553`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:574`
- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:669`
- `futures_trades_agg` — `sql/schema.sql:273`, 11 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1585`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:831`
- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:802`
- `liquidations` — `sql/schema.sql:174`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:675`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:317`
- `liquidations_realtime` — `sql/schema.sql:339`, 9 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:75`
- `long_short_ratio` — `sql/schema.sql:187`, 6 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:678`
  - la llena `app.ingest.upsert_long_short` (INSERT) — `app/ingest.py:358`
- `macro_event` — `sql/schema.sql:1252`, 6 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:564`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:576`
- `market_feed_health` — `sql/schema.sql:1325`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1272`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:824`
- `metrics_snapshot` — `sql/schema.sql:952`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:684`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `oi_bybit` — `sql/schema.sql:97`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:874`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:930`
- `pipeline_heartbeat` — `sql/schema.sql:1291`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `predicted_funding_rate` — `sql/schema.sql:160`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:672`
- `scalp_signal_snapshot` — `sql/schema.sql:388`, 16 columnas
  - la llena `app.scalp_collector.persist_scalp_signals` (INSERT) — `app/scalp_collector.py:1453`
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:681`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:277`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:298`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:404`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:421`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `c0.agg_hi`
- `choice`
- `edges`
- `exchanges`
- `max`
- `now`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

173 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.ai_context.build_ai_context` — `app/ai_context.py:1083`
- `app.ai_context.normalize_profile` — `app/ai_context.py:220`
- `app.api.validate_symbol` — `app/api.py:260`

<details><summary>Alcanzables de forma indirecta (170)</summary>

- `app.ai_context._armar_sobre` — `app/ai_context.py:913`
- `app.ai_context._corte_unico` — `app/ai_context.py:859`
- `app.ai_context._round_number` — `app/ai_context.py:227`
- `app.ai_context.build_ai_symbol_context` — `app/ai_context.py:895`
- `app.ai_context.build_operator_read` — `app/ai_context.py:751`
- `app.ai_context.compact_dict` — `app/ai_context.py:254`
- `app.ai_context.compact_value` — `app/ai_context.py:238`
- `app.ai_context.daily_data` — `app/ai_context.py:306`
- `app.ai_context.daily_history` — `app/ai_context.py:395`
- `app.ai_context.data_confidence_row` — `app/ai_context.py:532`
- `app.ai_context.field_disambiguation` — `app/ai_context.py:75`
- `app.ai_context.latest_orderbook` — `app/ai_context.py:684`
- `app.ai_context.latest_snapshot` — `app/ai_context.py:299`
- `app.ai_context.liquidation_levels` — `app/ai_context.py:712`
- `app.ai_context.local_alerts` — `app/ai_context.py:801`
- `app.ai_context.orderbook_freshness` — `app/ai_context.py:672`
- `app.ai_context.quality_score` — `app/ai_context.py:623`
- `app.ai_context.recent_signals` — `app/ai_context.py:696`
- `app.ai_context.rough_token_estimate` — `app/ai_context.py:284`
- `app.ai_context.sin_perder_los_nulos` — `app/ai_context.py:265`
- `app.ai_context.verdict_history` — `app/ai_context.py:487`
- `app.config.get_settings` — `app/config.py:308`
- `app.data_gaps._aware_utc` — `app/data_gaps.py:72`
- `app.data_gaps._validated_window` — `app/data_gaps.py:78`
- `app.data_gaps.align_down` — `app/data_gaps.py:247`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:268`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:260`
- `app.db.required_heartbeat_failures` — `app/db.py:110`
- `app.external_macro._direction` — `app/external_macro.py:190`
- `app.external_macro._metric` — `app/external_macro.py:205`
- `app.external_macro._pct_change` — `app/external_macro.py:184`
- `app.external_macro._pillar` — `app/external_macro.py:232`
- `app.external_macro._state` — `app/external_macro.py:197`
- `app.external_macro.align_with_internal` — `app/external_macro.py:415`
- `app.external_macro.build_external_macro_context` — `app/external_macro.py:237`
- `app.external_macro.external_macro_context` — `app/external_macro.py:437`
- `app.field_disambiguation.build` — `app/field_disambiguation.py:72`
- `app.interpretation._barrier_candidates` — `app/interpretation.py:684`
- `app.interpretation._barrier_zones` — `app/interpretation.py:779`
- `app.interpretation._cvd_observation` — `app/interpretation.py:521`
- `app.interpretation._cvd_side` — `app/interpretation.py:570`
- `app.interpretation._memory_features` — `app/interpretation.py:372`
- `app.interpretation._percentile` — `app/interpretation.py:368`
- `app.interpretation.cvd_swing_read` — `app/interpretation.py:578`
- `app.interpretation.evaluate_setups` — `app/interpretation.py:139`
- `app.interpretation.market_memory_read` — `app/interpretation.py:400`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.interpretation.price_barrier_read` — `app/interpretation.py:877`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._atr` — `app/scalp_logic.py:3240`
- `app.scalp_logic._beta` — `app/scalp_logic.py:3620`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3634`
- `app.scalp_logic._buckets_observados` — `app/scalp_logic.py:3292`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:6159`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._closes_1min` — `app/scalp_logic.py:3219`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1894`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._cvd_fut_window` — `app/scalp_logic.py:1021`
- `app.scalp_logic._cvd_src` — `app/scalp_logic.py:2935`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2421`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2586`
- `app.scalp_logic._feed_status` — `app/scalp_logic.py:4224`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2619`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2604`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2612`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2644`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1884`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4445`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4415`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4427`
- `app.scalp_logic._intraday_divergences` — `app/scalp_logic.py:2072`
- `app.scalp_logic._liquidation_feed_quality_status` — `app/scalp_logic.py:4189`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4626`
- `app.scalp_logic._oi_coverage` — `app/scalp_logic.py:3304`
- `app.scalp_logic._oi_quadrant` — `app/scalp_logic.py:3262`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1856`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3607`
- `app.scalp_logic._pivot_structure` — `app/scalp_logic.py:936`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3876`
- `app.scalp_logic._realized_vol` — `app/scalp_logic.py:3248`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4542`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1865`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1227`
- `app.scalp_logic._return_stdev_pct` — `app/scalp_logic.py:2059`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3599`
- `app.scalp_logic._sign_vote` — `app/scalp_logic.py:954`
- `app.scalp_logic._slope_pct` — `app/scalp_logic.py:2027`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2372`
- `app.scalp_logic._structure_layer` — `app/scalp_logic.py:989`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2358`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:3229`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.bars_incomplete_inside` — `app/scalp_logic.py:1298`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.compute_swing_score` — `app/scalp_logic.py:6494`
- `app.scalp_logic.context_metadata` — `app/scalp_logic.py:3973`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3655`
- `app.scalp_logic.cvd_matrix` — `app/scalp_logic.py:2994`
- `app.scalp_logic.data_quality` — `app/scalp_logic.py:4347`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4658`
- `app.scalp_logic.divergence_scan` — `app/scalp_logic.py:2200`
- `app.scalp_logic.feed_quality` — `app/scalp_logic.py:4064`
- `app.scalp_logic.feed_quality_view` — `app/scalp_logic.py:5640`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4794`
- `app.scalp_logic.funding_context` — `app/scalp_logic.py:3698`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2914`
- `app.scalp_logic.horizon_structure` — `app/scalp_logic.py:1753`
- `app.scalp_logic.liquidation_burst` — `app/scalp_logic.py:1810`
- `app.scalp_logic.liquidation_map` — `app/scalp_logic.py:3771`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1934`
- `app.scalp_logic.market_impact` — `app/scalp_logic.py:5877`
- `app.scalp_logic.market_memory` — `app/scalp_logic.py:1734`
- `app.scalp_logic.market_structure` — `app/scalp_logic.py:1041`
- `app.scalp_logic.max_internal_gap` — `app/scalp_logic.py:4498`
- `app.scalp_logic.metric_quality` — `app/scalp_logic.py:4253`
- `app.scalp_logic.oi_context` — `app/scalp_logic.py:3335`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:6192`
- `app.scalp_logic.positioning_context` — `app/scalp_logic.py:5982`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1304`
- `app.scalp_logic.reference_levels` — `app/scalp_logic.py:3505`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2592`
- `app.scalp_logic.scalp_absorption` — `app/scalp_logic.py:5683`
- `app.scalp_logic.scalp_basis` — `app/scalp_logic.py:5839`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`
- `app.scalp_logic.scalp_liquidations` — `app/scalp_logic.py:5778`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2853`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2843`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2429`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6320`
- `app.scalp_logic.volatility_context` — `app/scalp_logic.py:3455`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3913`
- `app.scalp_logic.wyckoff_context` — `app/scalp_logic.py:1680`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.oi_price_reading` — `app/setups.py:228`
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
- `app.zones._atr_abs` — `app/zones.py:545`
- `app.zones._edge_episodes` — `app/zones.py:525`
- `app.zones._ols_slope` — `app/zones.py:497`
- `app.zones._rotations` — `app/zones.py:509`
- `app.zones.range_validate_read` — `app/zones.py:561`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (7)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`
- `list`
- `part.strip`
- `str`
- `symbols.split`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |
| 422 | — | `app/api.py:3728` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:65` | — |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['bucket_bps', 'profile', 'symbols']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `build_finished_at`
- `build_started_at`
- `generated_at`

## Capa DECLARADA

**Declarada** en [`declarada/api-ai-context-bundle.md`](../declarada/api-ai-context-bundle.md) — pregunta del trader,
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
| `app.config.get_settings` | 3 | **0** | 50 ↑ | **3** | [impacto](../impacto/app-config.md) |
| `app.interpretation.evaluate_setups` | 4 | **0** | 48 ↑ | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 19 | **0** | 15 ↑ | **19** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps._aware_utc` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
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
| _… y 149 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
