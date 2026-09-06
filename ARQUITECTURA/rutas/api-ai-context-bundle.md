# `GET /api/ai/context/bundle`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `ai_context_bundle` · `app/api.py:2741` (cuerpo hasta la 2758) · decorador en la linea 2740.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbols` | `str | None` | `None` | no |
| `profile` | `str` | `'default'` | no |
| `bucket_bps` | `Annotated[int, Query(ge=1, le=100)]` | `10` | no |

## Campos que publica

6 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `generated_at` | literal en app/ai_context.py:992 |
| `interpretation_prompt` | literal en app/ai_context.py:991 |
| `local_alerts` | literal en app/ai_context.py:994 |
| `profile` | literal en app/ai_context.py:993 |
| `schema_version` | literal en app/ai_context.py:990 |
| `symbols` | literal en app/ai_context.py:995 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `daily_verdict_outcome` — `sql/schema.sql:2161`, 10 columnas
  - la llena `app.daily_agg.materialize_daily_verdict_outcomes` (INSERT) — `app/daily_agg.py:507`
- `daily_verdict_snapshot` — `sql/schema.sql:1099`, 26 columnas
  - la llena `app.daily_agg.persist_verdicts` (INSERT) — `app/daily_agg.py:418`
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
- `external_macro_observation` — `sql/schema.sql:1234`, 5 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:553`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:574`
- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:651`
- `futures_trades_agg` — `sql/schema.sql:273`, 11 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1538`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:802`
- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations` — `sql/schema.sql:174`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:657`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:316`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `long_short_ratio` — `sql/schema.sql:187`, 6 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:660`
  - la llena `app.ingest.upsert_long_short` (INSERT) — `app/ingest.py:357`
- `macro_event` — `sql/schema.sql:1245`, 6 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:564`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:576`
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
- `oi_bybit` — `sql/schema.sql:97`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:648`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `predicted_funding_rate` — `sql/schema.sql:160`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:654`
- `scalp_signal_snapshot` — `sql/schema.sql:381`, 16 columnas
  - la llena `app.scalp_collector.persist_scalp_signals` (INSERT) — `app/scalp_collector.py:1406`
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:376`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:393`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
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

166 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.ai_context.build_ai_context` — `app/ai_context.py:958`
- `app.ai_context.normalize_profile` — `app/ai_context.py:185`
- `app.api.validate_symbol` — `app/api.py:222`

<details><summary>Alcanzables de forma indirecta (163)</summary>

- `app.ai_context._round_number` — `app/ai_context.py:192`
- `app.ai_context.build_ai_symbol_context` — `app/ai_context.py:820`
- `app.ai_context.build_operator_read` — `app/ai_context.py:713`
- `app.ai_context.compact_dict` — `app/ai_context.py:219`
- `app.ai_context.compact_value` — `app/ai_context.py:203`
- `app.ai_context.daily_data` — `app/ai_context.py:271`
- `app.ai_context.daily_history` — `app/ai_context.py:360`
- `app.ai_context.data_confidence_row` — `app/ai_context.py:497`
- `app.ai_context.latest_orderbook` — `app/ai_context.py:646`
- `app.ai_context.latest_snapshot` — `app/ai_context.py:264`
- `app.ai_context.liquidation_levels` — `app/ai_context.py:674`
- `app.ai_context.local_alerts` — `app/ai_context.py:763`
- `app.ai_context.orderbook_freshness` — `app/ai_context.py:634`
- `app.ai_context.quality_score` — `app/ai_context.py:585`
- `app.ai_context.recent_signals` — `app/ai_context.py:658`
- `app.ai_context.rough_token_estimate` — `app/ai_context.py:249`
- `app.ai_context.sin_perder_los_nulos` — `app/ai_context.py:230`
- `app.ai_context.verdict_history` — `app/ai_context.py:452`
- `app.config.get_settings` — `app/config.py:291`
- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.align_down` — `app/data_gaps.py:232`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`
- `app.db.required_heartbeat_failures` — `app/db.py:110`
- `app.external_macro._direction` — `app/external_macro.py:190`
- `app.external_macro._metric` — `app/external_macro.py:205`
- `app.external_macro._pct_change` — `app/external_macro.py:184`
- `app.external_macro._pillar` — `app/external_macro.py:232`
- `app.external_macro._state` — `app/external_macro.py:197`
- `app.external_macro.align_with_internal` — `app/external_macro.py:415`
- `app.external_macro.build_external_macro_context` — `app/external_macro.py:237`
- `app.external_macro.external_macro_context` — `app/external_macro.py:437`
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
- `app.scalp_logic._atr` — `app/scalp_logic.py:2926`
- `app.scalp_logic._beta` — `app/scalp_logic.py:3269`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3283`
- `app.scalp_logic._buckets_observados` — `app/scalp_logic.py:2978`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:5695`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._closes_1min` — `app/scalp_logic.py:2905`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1780`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._cvd_fut_window` — `app/scalp_logic.py:1006`
- `app.scalp_logic._cvd_src` — `app/scalp_logic.py:2640`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2275`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._feed_status` — `app/scalp_logic.py:3850`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2416`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2424`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2431`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1770`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4071`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4041`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4053`
- `app.scalp_logic._intraday_divergences` — `app/scalp_logic.py:1958`
- `app.scalp_logic._liquidation_feed_quality_status` — `app/scalp_logic.py:3815`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4245`
- `app.scalp_logic._oi_coverage` — `app/scalp_logic.py:2990`
- `app.scalp_logic._oi_quadrant` — `app/scalp_logic.py:2948`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1742`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3256`
- `app.scalp_logic._pivot_structure` — `app/scalp_logic.py:936`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3502`
- `app.scalp_logic._realized_vol` — `app/scalp_logic.py:2934`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4161`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1751`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._return_stdev_pct` — `app/scalp_logic.py:1945`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3248`
- `app.scalp_logic._sign_vote` — `app/scalp_logic.py:954`
- `app.scalp_logic._slope_pct` — `app/scalp_logic.py:1913`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2226`
- `app.scalp_logic._structure_layer` — `app/scalp_logic.py:982`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2212`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:2915`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.compute_swing_score` — `app/scalp_logic.py:6001`
- `app.scalp_logic.context_metadata` — `app/scalp_logic.py:3599`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3304`
- `app.scalp_logic.cvd_matrix` — `app/scalp_logic.py:2699`
- `app.scalp_logic.data_quality` — `app/scalp_logic.py:3973`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4277`
- `app.scalp_logic.divergence_scan` — `app/scalp_logic.py:2073`
- `app.scalp_logic.feed_quality` — `app/scalp_logic.py:3690`
- `app.scalp_logic.feed_quality_view` — `app/scalp_logic.py:5183`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4419`
- `app.scalp_logic.funding_context` — `app/scalp_logic.py:3347`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2619`
- `app.scalp_logic.horizon_structure` — `app/scalp_logic.py:1679`
- `app.scalp_logic.liquidation_burst` — `app/scalp_logic.py:1696`
- `app.scalp_logic.liquidation_map` — `app/scalp_logic.py:3420`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1820`
- `app.scalp_logic.market_impact` — `app/scalp_logic.py:5420`
- `app.scalp_logic.market_memory` — `app/scalp_logic.py:1660`
- `app.scalp_logic.market_structure` — `app/scalp_logic.py:1026`
- `app.scalp_logic.max_internal_gap` — `app/scalp_logic.py:4117`
- `app.scalp_logic.metric_quality` — `app/scalp_logic.py:3879`
- `app.scalp_logic.oi_context` — `app/scalp_logic.py:3021`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:5728`
- `app.scalp_logic.positioning_context` — `app/scalp_logic.py:5525`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1235`
- `app.scalp_logic.reference_levels` — `app/scalp_logic.py:3191`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_absorption` — `app/scalp_logic.py:5226`
- `app.scalp_logic.scalp_basis` — `app/scalp_logic.py:5382`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`
- `app.scalp_logic.scalp_liquidations` — `app/scalp_logic.py:5321`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2609`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2283`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:5846`
- `app.scalp_logic.volatility_context` — `app/scalp_logic.py:3141`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3539`
- `app.scalp_logic.wyckoff_context` — `app/scalp_logic.py:1606`
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
- `app.zones._atr_abs` — `app/zones.py:519`
- `app.zones._edge_episodes` — `app/zones.py:499`
- `app.zones._ols_slope` — `app/zones.py:471`
- `app.zones._rotations` — `app/zones.py:483`
- `app.zones.range_validate_read` — `app/zones.py:535`

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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | — | `app/api.py:2754` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:60` | — |
| **readme** | — | `README.md:415`, `README.md:519` |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['bucket_bps', 'profile', 'symbols']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

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
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.config.get_settings` | 3 | **0** | 53 ↑ | **3** | [impacto](../impacto/app-config.md) |
| `app.interpretation.evaluate_setups` | 4 | **0** | 51 ↑ | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 11 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | **0** | 14 ↑ | **20** | [impacto](../impacto/app-data_gaps.md) |
| `app.metrics.current_nyse_start` | 15 | **0** | 14 ↑ | **15** | [impacto](../impacto/app-metrics.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
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
| _… y 142 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
