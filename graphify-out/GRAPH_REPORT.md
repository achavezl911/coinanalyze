# Graph Report - horizontal-safe-collectors  (2026-08-09)

## Corpus Check
- 141 files · ~174,021 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2351 nodes · 5272 edges · 152 communities (129 shown, 23 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 125 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `462701f2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_ingest.py
- api.py
- evaluate_setup
- zone_character_read
- hypothesis_evidence
- timedelta
- number
- app.js
- scalp_logic.py
- test_db.py
- setups.py
- test_breakout.py
- _Connection
- setup_observables
- ingest.py
- test_v150_setups.py
- metrics.py
- scalp_collector.py
- divergence_scan
- CoinalyzeClient
- build_setup_context
- as_float
- test_setup_breakout_boundary.py
- test_p1_timeframes_and_spot.py
- number
- test_wyckoff.py
- Graphify — knowledge graph del repositorio
- test_flow_semantics.py
- Parte II — Cada indicador, individualmente
- Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada
- Collectors horizontales
- test_forward_returns
- BucketStore
- delta_matrix
- profile_read
- test_v150_calidad.py
- Manual de interpretación — Coinalyze Derivatives Dashboard
- compute_scalp_summary
- Parte IV — Lecturas combinadas (setups)
- external_macro.py
- profile_view
- Guia de uso - Coinalyze Operator Dashboard v1.2.5
- asNumber
- test_daily_history_only_ships_on_the_expensive_profiles
- test_daily_semantics.py
- LocalBook
- test_no_module_still_claims_the_futures_leg_is_a_multi_venue_aggregate
- test_daily_chart_axis_shows_dates_without_a_meaningless_hour
- test_render_functions_replace_their_container_instead_of_appending
- test_session_bars_never_build_markup_from_api_strings
- test_partial_sessions_never_overwrite_a_good_two_venue_value
- calibrate_signals.py
- BookStore
- test_dashboard_layout.py
- 20260809_horizontal_safe_collectors.sql
- test_v150_desk_snapshot.py
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- TradeStore
- interpretation.py
- refreshOverview
- test_market_feed_health.py
- test_market_data_integrity_collector.py
- test_ai_context.py
- handle_bybit
- _FakeBybitSocket
- flush_books
- basis_quality
- assigned_symbols
- test_p2_baselines.py
- FakeConnection
- walk_book
- FakePool
- test_5m_no_es_a_la_vez_entrada_y_referencia_secundaria
- Parte VII — Modo Scalping / Ejecución rápida
- test_las_capas_de_cada_perfil_son_disjuntas
- test_dashboard_presentation.py
- test_p0_regresion_auditoria.py
- v1.5.0 — corrección de la reorganización
- Coinalyze Derivatives Operator
- Coinalyze Operator Dashboard v1.5.0
- Node
- _IntradayConnection
- Settings
- asyncio
- Traspaso para IA — Coinalyze Operator Dashboard v1.3.7
- test_metrics_endpoint.py
- test_v150_topbar.py
- renderDaily
- test_absorption_requires_meaningful_magnitude
- Despliegue en Proxmox VE
- generate_dashboard_usage_pdf.py
- configure_secrets.sh
- schema.sql
- test_v150_version_docs.py
- trend_matrix
- Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge
- Patches aplicados — v1.1.2
- huecos.test.js
- daily_agg.py
- Coinalyze v1.4.5 — presentación del operador
- renderDeltaProfile
- ejecucion.test.js
- harness.js
- CLAUDE.md — instrucciones para Claude Code
- install.sh
- Coinalyze v1.4.6 — perfil de volumen y delta por nivel de precio
- GitHub Actions y runner self-hosted
- Operaciones
- update.sh
- navegacion.test.js
- AGENTS.md — instrucciones para Codex CLI
- AI Engineering Rules — coinanalyze
- Flujo de desarrollo
- Parches aplicados por revisión técnica
- ClassList
- Parche del bridge de Telegram — v1.3.4
- Coinalyze v1.4.8 — lectura rápida del flujo
- asnumber.test.js
- Path
- Coinalyze v1.4.4 — Wyckoff automático y auditoría de v1.4.3
- Segunda ronda (2026-08-07): cuatro correcciones previas al gap recovery
- Despliegue a producción
- Patches aplicados — v1.2.0
- Patches aplicados — v1.2.1
- PATCHES_APPLIED v1.2.4
- PATCHES_APPLIED v1.2.5
- Rollback
- backup.sh
- _DailyReplayConnection
- Arquitectura DEV / CI-CD / Producción
- Coinalyze v1.4.7 — flujo ejecutado y reacción del precio
- Patches aplicados v1.2.2
- Patches applied v1.2.3
- Prometheus scraping
- Validación v1.1.2
- Validación v1.2.1
- app/__init__.py
- README_STATIC_NETWORK.md
- VALIDATION.md
- VALIDATION_v1.2.0.md
- VALIDATION_v1.2.2.md
- VALIDATION_v1.2.3.md
- VALIDATION_v1.2.4.md
- VALIDATION_v1.2.5.md
- smoke_test.sh
- coinalyze-operator-dashboard

## God Nodes (most connected - your core abstractions)
1. `_Connection` - 102 edges
2. `_get()` - 70 edges
3. `compute_scalp_summary()` - 64 edges
4. `validate_symbol()` - 58 edges
5. `as_float()` - 56 edges
6. `build_ai_symbol_context()` - 48 edges
7. `asNumber()` - 46 edges
8. `number()` - 45 edges
9. `Settings` - 43 edges
10. `safeArray()` - 42 edges

## Surprising Connections (you probably didn't know these)
- `test_normalize_profile()` --calls--> `normalize_profile()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py
- `test_compact_dict_filters_and_rounds()` --calls--> `compact_dict()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py
- `test_compact_dict_preserves_boolean_types()` --calls--> `compact_dict()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py
- `test_rough_token_estimate_positive()` --calls--> `rough_token_estimate()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py
- `test_quality_score_degraded_when_feeds_missing()` --calls--> `quality_score()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py

## Import Cycles
- None detected.

## Communities (152 total, 23 thin omitted)

### Community 0 - "test_ingest.py"
Cohesion: 0.12
Nodes (10): seconds_until_aligned_run(), _CycleClient, _CycleConnection, _CyclePool, FakeConnection, FakeRollupConnection, test_feed_schedules_align_after_closed_buckets(), test_one_minute_cycle_refreshes_metrics_snapshots() (+2 more)

### Community 1 - "api.py"
Cohesion: 0.05
Nodes (118): normalize_profile(), ai_context(), ai_context_bundle(), ai_profiles(), client_ip_allowed(), context_metadata_endpoint(), cross_asset_endpoint(), cvd() (+110 more)

### Community 2 - "evaluate_setup"
Cohesion: 0.11
Nodes (34): classify_oi(), evaluate_setup(), oi_price_reading(), Evalua UN setup contra los observables disponibles. Pura y fail-closed., Clasifica el Open Interest como ESTADO de posicionamiento, sin direccion. El…, Lectura CONTEXTUAL de precio + OI + flujo. No es una relacion causal…, ctx_rico(), parametrize (+26 more)

### Community 3 - "zone_character_read"
Cohesion: 0.06
Nodes (77): _atr_abs(), _atr_pct(), _clamp(), _edge_episodes(), _effort_result(), _narrative(), _oi_behaviour(), _ols_slope() (+69 more)

### Community 4 - "hypothesis_evidence"
Cohesion: 0.05
Nodes (58): _banda(), _bps(), execution_assessment(), hypothesis_evidence(), Etiqueta de sesgo por BALANCE DE EVIDENCIA, sin mirar el coste de ejecucion. Ya…, Reparte la evidencia disponible respecto de la tesis que pone el OPERADOR.…, Distancia entre dos precios en puntos basicos, o None si falta alguno., ¿Cuanto se come la ejecucion del objetivo y del riesgo de ESTA operacion? PURA.… (+50 more)

### Community 5 - "timedelta"
Cohesion: 0.20
Nodes (15): _as_utc_datetime(), _closed_1m_window_bounds(), _closed_5m_oi_bounds(), _liquidation_feed_quality_status(), _liquidation_window_measured(), datetime, Evaluate operational state and continuity across the displayed quality window., ¿Se estaba ESCUCHANDO el feed de liquidaciones durante la ventana? Las… (+7 more)

### Community 6 - "number"
Cohesion: 0.27
Nodes (20): number(), _atr_abs(), _bar_date(), _bias_read(), _candidate_rank(), _clamp(), _clean_bars(), detect_latest_range() (+12 more)

### Community 7 - "app.js"
Cohesion: 0.06
Nodes (52): ANALYZER_INPUTS, ANALYZER_TABS, axisMoney(), axisPrice(), chartOptions(), clearBreakout(), clearRange(), clearSnapshotView() (+44 more)

### Community 8 - "scalp_logic.py"
Cohesion: 0.10
Nodes (35): _atr(), _beta(), _binned(), _closes_1min(), _conditional_outcome(), cross_asset(), _dsr(), _forward_returns() (+27 more)

### Community 9 - "test_db.py"
Cohesion: 0.12
Nodes (14): MarketSymbol, sync_market_catalog(), _CatalogConnection, _CatalogPool, _HeartbeatConnection, _LockConnection, _LostLockConnection, asyncio (+6 more)

### Community 10 - "setups.py"
Cohesion: 0.10
Nodes (41): _bars_closed_beyond(), _beyond(), _breakout_frontier(), _eval_continuacion(), _eval_rechazo(), _eval_reversion(), _eval_ruptura(), _flow_check() (+33 more)

### Community 11 - "test_breakout.py"
Cohesion: 0.10
Nodes (48): _atr(), attempt_features(), breakout_read(), build_corpus(), classify_outcome(), _confirmation_checks(), _delta_usd(), find_attempts() (+40 more)

### Community 12 - "_Connection"
Cohesion: 0.13
Nodes (33): AIProfile, build_ai_context(), build_ai_symbol_context(), build_operator_read(), compact_dict(), compact_value(), daily_data(), daily_history() (+25 more)

### Community 13 - "setup_observables"
Cohesion: 0.23
Nodes (26): Mide los cinco observables reales desde velas CERRADAS y estructura. Devuelve,…, setup_observables(), _bars(), _bundle(), Observables MEDIDOS sobre velas cerradas: bars_closed_beyond, returned_inside,…, Velas cerradas ascendentes; high/low se derivan del cierre salvo override por…, test_build_setup_context_con_bundle_mide_los_observables(), test_bundle_ausente_deja_bars_en_none() (+18 more)

### Community 14 - "ingest.py"
Cohesion: 0.12
Nodes (28): finite(), ingest_cycle(), ingest_metrics_cycle(), ingest_ohlcv_cycle(), Any, datetime, Build recent 5-minute candles locally without spending API quota., Posicionamiento: l/s son porcentajes que suman 100 y r es su cociente. (+20 more)

### Community 15 - "test_v150_setups.py"
Cohesion: 0.12
Nodes (24): ctx_rico(), parametrize, v1.5.0 — direccion y setup son cosas distintas, y cada setup tiene logica…, Observables suficientes para que los cuatro setups tengan algo que decir., Lo que mata a una ruptura no es lo que mata a una continuacion., Tendencia alcista previa: continuacion viable, reversion imposible., El precio aceptado por encima del nivel confirma la ruptura y mata el rechazo., test_build_setup_context_elige_la_barrera_segun_direccion_y_setup() (+16 more)

### Community 16 - "metrics.py"
Cohesion: 0.17
Nodes (21): compute_and_store_all(), compute_regime(), compute_snapshot(), current_nyse_start(), insert_snapshot(), optional_finite(), date, datetime (+13 more)

### Community 17 - "scalp_collector.py"
Cohesion: 0.18
Nodes (18): mark_feed_shard_connected(), mark_feed_shard_degraded(), mark_feed_shard_error(), _mark_feed_shard_health(), Persist one shard and refresh the fail-closed feed/exchange aggregate., binance_market_loop(), bybit_loop(), cleanup() (+10 more)

### Community 18 - "divergence_scan"
Cohesion: 0.33
Nodes (7): divergence_scan(), _intraday_divergences(), Pendiente por minimos cuadrados, normalizada por la escala de la serie., Mismo contraste que en sesiones, pero sobre velas de 1 minuto. Precio desde…, Precio subiendo mientras el CVD spot acumulado baja (o al reves), sostenido.…, _return_stdev_pct(), _slope_pct()

### Community 19 - "CoinalyzeClient"
Cohesion: 0.09
Nodes (28): lifespan(), CoinalyzeClient, CoinalyzeError, CoinalyzeRateBudget, PostgresSlidingWindowRateLimiter, Any, RuntimeError, RateLimiter (+20 more)

### Community 20 - "build_setup_context"
Cohesion: 0.34
Nodes (13): build_setup_context(), Traduce los bloques ya publicados a los observables que pide cada setup. Solo…, test_build_setup_context_sin_bundle_mantiene_none(), _bars(), _bundle(), El camino REAL de produccion: datos OHLCV/barreras -> build_setup_context ->…, _scalp(), test_continuacion_es_fail_closed_sin_bundle() (+5 more)

### Community 21 - "as_float"
Cohesion: 0.09
Nodes (34): as_float(), _cvd_fut_window(), execution_cost(), _flow_bias(), flow_confirmation(), level_breakout(), market_structure(), _measured_event_sum() (+26 more)

### Community 22 - "test_setup_breakout_boundary.py"
Cohesion: 0.22
Nodes (12): _bundle(), _estado_cierre(), La ruptura se decide contra la FRONTERA de la zona (breakout_boundary), nunca…, Estado del requisito critico 'cierre mas alla de la barrera'., test_build_setup_context_ruptura_long_frontera_es_resistance_high(), test_build_setup_context_ruptura_short_frontera_es_support_low(), test_hypothesis_evidence_publica_setup_zone_y_observables(), test_hypothesis_evidence_sin_setup_context_no_rompe() (+4 more)

### Community 23 - "test_p1_timeframes_and_spot.py"
Cohesion: 0.11
Nodes (17): parametrize, P1: vela de 18 m determinista y pata spot del mismo venue. Coinalyze NO sirve…, La asimetria de v1.3.4 era perp de Binance contra spot de Binance+Bybit., validate_symbol filtra contra SUPPORTED_SYMBOLS: el spot solo existe como dato., spot_perp_flow vota con flow_confirmation, que mira el signo de AMBAS patas.…, 1440/18 = 80 exacto: ninguna vela queda a caballo entre dos dias UTC., date_bin ancla en 1970-01-01T00:00:00Z; hay que probar que eso alinea con…, El prompt maestro lo marca como requisito: 18m no es 15m ni 20m. (+9 more)

### Community 24 - "number"
Cohesion: 0.20
Nodes (34): externalMetricValue(), imbalanceCell(), liqProfileMark(), liqProfileRow(), loadSection(), money(), nd(), number() (+26 more)

### Community 25 - "test_wyckoff.py"
Cohesion: 0.44
Nodes (8): _range_bars(), _sessions(), test_bearish_flow_is_compatible_with_distribution(), test_bullish_flow_is_compatible_with_accumulation(), test_dashboard_exposes_automatic_module_and_daily_chart_mode(), test_detects_range_without_user_supplied_boundaries(), test_output_contains_chart_and_actionable_boundaries(), test_trend_is_not_forced_into_a_range()

### Community 26 - "Graphify — knowledge graph del repositorio"
Cohesion: 0.15
Nodes (12): Consultar (query-first), Freshness en CI, Generar / actualizar el grafo, Graphify — knowledge graph del repositorio, Hooks y worktrees (decisión de diseño), Merge driver para `graph.json`, Política de actualización, Qué se versiona y qué no (+4 more)

### Community 27 - "test_flow_semantics.py"
Cohesion: 0.09
Nodes (32): _classify_passive(), compute_swing_score(), Detecta absorcion por limites pasivos y la mapea a…, Puro: lee los bloques ya calculados y sintetiza sesgo largo plazo. NO es…, _bars(), _blocks(), Regresiones de la auditoria v1.3.8. Cada test fija una conclusion que se…, Medido en vivo (BTC): score 45 con 4 de 7 componentes mudos se publicaba como… (+24 more)

### Community 28 - "Parte II — Cada indicador, individualmente"
Cohesion: 0.18
Nodes (11): 10. Histórico diario y CVD spot acumulado, 1. CVD de futuros (cvd_session / cvd_nyse_session), 2. CVD de spot (cvd_spot_24h / cvd_spot_session), 3. CVD diferencial (cvd_diff_24h / cvd_diff_ses) — comparación de magnitud, 4. Whale delta / intensidad institucional (whale_intensity, whale_label), 5. Funding rate (fr_avg) y divergencia PFR-FR (pfr_fr_div), 6. Open Interest (oi, oi_chg_24h_pct, oi_vol_24h_ratio), 7. Liquidaciones (long_liq_24h, short_liq_24h, liq_ratio_24h) (+3 more)

### Community 29 - "Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada"
Cohesion: 0.06
Nodes (31): 1. P0 — El diferencial spot−futuros votaba dirección, 2. P1 — El componente "absorción CVD" del score de barreras estaba muerto, 3. P1 — "100% long" con la mitad de la evidencia muda, 4. P1 — Pivotes 4h sobre el 6.7% de la historia pedida, 5-6. P2 — Ceros silenciosos y doble conteo, Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada, Causa raíz, Causa raíz (+23 more)

### Community 30 - "Collectors horizontales"
Cohesion: 0.29
Nodes (6): Catálogo, Collectors horizontales, Dos shards, Migración y rollback, Tres shards, Un shard

### Community 32 - "BucketStore"
Cohesion: 0.13
Nodes (15): binance_consumer(), binance_url(), Bucket, BucketStore, bybit_consumer(), RtBucket, spot_pairs(), valid_trade() (+7 more)

### Community 33 - "delta_matrix"
Cohesion: 0.13
Nodes (20): desk_state(), hypothesis(), quality_feeds(), Clasifica la evidencia disponible frente a la tesis del operador. `direction` y…, Snapshot COHERENTE de la Mesa: un solo calculo, un solo ancla temporal. La Mesa…, Calidad de los FEEDS de mercado y de cada METRICA publicada. La pestana de…, baseline_band(), data_quality() (+12 more)

### Community 34 - "profile_read"
Cohesion: 0.15
Nodes (25): bucket_index(), bucket_size(), delta_profile(), _floor_log10(), profile_read(), Any, Perfil de volumen y delta por nivel de precio. Responde a "en esta zona, ¿hubo…, Construye el perfil. `bars` necesita low, high, volume, buy_volume y close. (+17 more)

### Community 35 - "test_v150_calidad.py"
Cohesion: 0.09
Nodes (22): feed_quality(), _feed_status(), metric_quality(), Estado real de cada FEED de mercado, uno por uno. Distinto de `data_quality()`,…, Estado del feed y su ultimo error, sin confundir calma con caida. Las…, Calidad POR METRICA publicada, no por feed ni por proceso. PURA: recibe bloques…, _hb(), metricas() (+14 more)

### Community 36 - "Manual de interpretación — Coinalyze Derivatives Dashboard"
Cohesion: 0.25
Nodes (8): Anexo — Cambios operativos v1.2.1, Manual de interpretación — Coinalyze Derivatives Dashboard, Parte I — El marco mental, Parte III — Cómo se relacionan (mapa de dependencias), Parte IX — Errores de scalping a evitar, Parte V — Rutina de lectura sugerida, Parte VI — Errores de interpretación a evitar, Parte VIII — Rutina específica para scalping

### Community 37 - "compute_scalp_summary"
Cohesion: 0.07
Nodes (58): _closed_window_move_pct(), compute_scalp_summary(), _coverage_status(), _first_present(), Primer valor NO nulo. Sustituye a `a or b`, que en Python descarta tambien el…, Cobertura estricta de una ventana temporal. complete = exactamente todas las…, Movimiento de precio sólo cuando la ventana está completamente cubierta.…, score_component() (+50 more)

### Community 38 - "Parte IV — Lecturas combinadas (setups)"
Cohesion: 0.33
Nodes (6): Parte IV — Lecturas combinadas (setups), Setup A — Distribución encubierta (sesgo SHORT de mediano plazo), Setup B — Acumulación silenciosa (sesgo LONG de mediano plazo), Setup C — Squeeze de shorts inminente (sesgo LONG de corto plazo), Setup D — Euforia / techo de corto plazo (sesgo SHORT / reducir longs), Setup E — Capitulación / suelo de corto plazo (sesgo LONG contrarian)

### Community 39 - "external_macro.py"
Cohesion: 0.22
Nodes (22): align_with_internal(), build_external_macro_context(), _direction(), external_macro_context(), _metric(), parse_bls_calendar(), parse_coinglass_etf(), parse_fomc_calendar() (+14 more)

### Community 40 - "profile_view"
Cohesion: 0.18
Nodes (22): profile_view(), Compone trend_matrix y delta_matrix en la jerarquia del perfil elegido. PURA a…, matrix(), P1: selector intradia/swing con jerarquia explicita de temporalidades.…, Regla del proyecto: se renormaliza sobre lo medible, nunca se suma 0., Sin caja negra: cada capa publica peso, score y aportacion., v1.5.0: 30s/1m tienen capa propia en swing, con PESO CERO. Antes vivian en…, Requisito explicito del prompt maestro: 30s/1m no invalidan varios dias. (+14 more)

### Community 41 - "Guia de uso - Coinalyze Operator Dashboard v1.2.5"
Cohesion: 0.08
Nodes (25): 10. Absorcion, 11. Order book, 12. Liquidaciones RT, 13. Basis perp-spot, 14. Senales recientes, 15. Niveles de liquidacion, 16. Graficas principales, 17. Lecturas combinadas (+17 more)

### Community 42 - "asNumber"
Cohesion: 0.13
Nodes (26): asNumber(), card(), dailySeries(), dateTime(), deltaFlowQuadrant(), deltaShare(), flowQuadrant(), fundingClass() (+18 more)

### Community 44 - "test_daily_semantics.py"
Cohesion: 0.10
Nodes (8): El CVD por sesión describe agresión ejecutada, no inventario institucional.…, El formateador del motor solo pone fecha al cambiar de dia: 48 h de velas de 5…, Sin grid-column caia a span 1 de 12 y la tabla salia aplastada., test_conditional_outcome_needs_a_real_sample(), test_divergence_panel_spans_the_full_grid_width(), test_minute_retention_covers_a_full_nyse_session(), test_slope_sign_detects_direction(), test_time_axis_labels_always_carry_the_date()

### Community 45 - "LocalBook"
Cohesion: 0.13
Nodes (14): LocalBook, owns_global_cleanup(), datetime, safe_liq_put(), parametrize, test_local_book_rejects_missing_duplicate_prior_and_skipped_updates(), test_local_book_tracks_update_id_separately_from_cross_sequence(), _CleanupConnection (+6 more)

### Community 52 - "calibrate_signals.py"
Cohesion: 0.21
Nodes (12): SamplingMode, fetch_rows(), main(), pct(), Any, sample_key(), select_samples(), signal_side() (+4 more)

### Community 53 - "BookStore"
Cohesion: 0.27
Nodes (14): all_expected_fresh(), BookStore, mark_exchange_disconnected(), LogCaptureFixture, asyncio, MonkeyPatch, test_binance_late_orderbook_event_forces_stale(), test_binance_trade_event_is_recorded() (+6 more)

### Community 54 - "test_dashboard_layout.py"
Cohesion: 0.14
Nodes (17): HTMLParser, DashboardParser, function_source(), parsed_dashboard(), No encabeza la tabla, no lleva color de signo y viene oculta por defecto., test_cvd_90_session_read_has_a_full_width_safe_panel(), test_dashboard_has_unique_ids_and_market_reading_order(), test_decision_board_is_dom_safe_and_covers_three_horizons() (+9 more)

### Community 56 - "test_v150_desk_snapshot.py"
Cohesion: 0.13
Nodes (18): _ConnFalsa, desk(), _PoolFalso, Any, fixture, MonkeyPatch, parametrize, v1.5.0 — la Mesa se sirve de UN snapshot con un solo ancla temporal. Antes cada… (+10 more)

### Community 57 - "Manual — Coinalyze Operator Dashboard v1.2.5 final"
Cohesion: 0.09
Nodes (21): 10. Configuración del Bridge, 11. Validación del Bridge, 12. Comandos Telegram, 13. Operación diaria, 14. Actualización controlada, 15. Rotación de secretos antes de producción, 16. Controles de seguridad finales, 17. Troubleshooting mínimo (+13 more)

### Community 58 - "Manual — Coinalyze Operator Dashboard v1.2.5 final"
Cohesion: 0.09
Nodes (21): 10. Configuración del Bridge, 11. Validación del Bridge, 12. Comandos Telegram, 13. Operación diaria, 14. Actualización controlada, 15. Rotación de secretos antes de producción, 16. Controles de seguridad finales, 17. Troubleshooting mínimo (+13 more)

### Community 60 - "TradeStore"
Cohesion: 0.25
Nodes (7): floor_ts_seconds(), flush_trades(), TradeBucket, TradeStore, _write_combined_minute(), _write_combined_realtime(), _write_trade_rows()

### Community 61 - "interpretation.py"
Cohesion: 0.13
Nodes (32): _barrier_candidates(), _barrier_zones(), Condition, _cvd_observation(), _cvd_side(), cvd_swing_read(), daily_flow_read(), evaluate_setups() (+24 more)

### Community 62 - "refreshOverview"
Cohesion: 0.14
Nodes (21): api(), boot(), breakoutEmpty(), connectStream(), initDeltaProfile(), initDiffToggle(), initHypothesis(), initSectionNav() (+13 more)

### Community 63 - "test_market_feed_health.py"
Cohesion: 0.15
Nodes (13): mark_feed_connected(), mark_feed_degraded(), mark_feed_error(), _mark_feed_unhealthy(), Mark a market feed healthy without resetting an existing healthy period., Any, asyncio, parametrize (+5 more)

### Community 64 - "test_market_data_integrity_collector.py"
Cohesion: 0.31
Nodes (13): bybit_liquidated_position_side(), Break persisted continuity before any stream can reconnect after process start., reset_liquidation_feed_health(), asyncio, MonkeyPatch, test_binance_force_order_semantics_remain_order_side_based(), test_bybit_gap_removes_book_until_a_new_snapshot(), test_bybit_health_waits_for_positive_subscription_confirmation() (+5 more)

### Community 65 - "test_ai_context.py"
Cohesion: 0.17
Nodes (11): test_ai_context_includes_external_macro_filter(), test_ai_context_includes_price_barriers(), test_ai_context_includes_the_cvd_90_session_read(), test_compact_dict_filters_and_rounds(), test_compact_dict_preserves_boolean_types(), test_daily_data_selects_cumulative_diff(), test_normalize_profile(), test_quality_score_degraded_when_feeds_missing() (+3 more)

### Community 66 - "handle_bybit"
Cohesion: 0.31
Nodes (9): binance_loop(), BookResyncRequired, handle_binance(), handle_bybit(), now_ms(), parse_sequence(), Any, RuntimeError (+1 more)

### Community 67 - "_FakeBybitSocket"
Cohesion: 0.24
Nodes (3): _FakeBybitSocket, _FakeConnect, Any

### Community 68 - "flush_books"
Cohesion: 0.28
Nodes (6): BookStats, flush_books(), Escalera completa por venue, para calcular slippage de cualquier tamanio.…, Estado ACTUAL del libro por venue: una fila por (symbol,exchange), sobrescrita.…, _write_combined_books(), _write_ladders()

### Community 69 - "basis_quality"
Cohesion: 0.16
Nodes (17): basis_quality(), Basis perp-spot con puerta de frescura: devuelve None cuando no se sostiene. El…, parametrize, P0: el dashboard no debe publicar como fiable un dato que no lo es. Dos…, Un collector caido al PRINCIPIO de la ventana no lo ve un lag() a secas., El caso que motiva el P0: una pata congelada y la otra viva., Medido: el skew esta acotado por la rejilla de 5 s (p50 0.4-0.8 s, maximo 4.8…, Regla del proyecto: ausencia de dato es None, jamas 0. (+9 more)

### Community 70 - "assigned_symbols"
Cohesion: 0.62
Nodes (5): assigned_symbols(), symbol_shard(), test_default_single_shard_preserves_order_and_all_symbols(), test_invalid_shard_arguments_fail_explicitly(), test_shards_are_deterministic_disjoint_and_complete_with_fourth_asset()

### Community 71 - "test_p2_baselines.py"
Cohesion: 0.09
Nodes (23): classify_absorption(), Clasifica absorcion desde el delta agresivo y el movimiento de precio. Fuente…, parametrize, P2: los umbrales salen de la distribucion medida, no de una constante. Medicion…, Una muestra corta no es una distribucion: mejor sin baseline que con una…, El ratio long/short reparte CUENTAS: leerlo como dinero es el error tipico., La serie empieza vacia: llamar '30 dias' a 26 horas de historia es precision…, (x - mediana) / (1.4826 * MAD): la cola de esta distribucion rompe media y… (+15 more)

### Community 72 - "FakeConnection"
Cohesion: 0.29
Nodes (4): dict, FakeConnection, FakeRecord, dict lanza KeyError igual que asyncpg.Record ante una columna no pedida.

### Community 73 - "walk_book"
Cohesion: 0.18
Nodes (16): Consume la escalera hasta cubrir size_usd y devuelve el precio medio de…, walk_book(), parametrize, P1: coste de ejecucion recorriendo la escalera real del libro. Bybit entrega 50…, Ejecutar 201 USD toma los 100 del primer nivel y 101 del segundo = 1 unidad a…, Pedir mas de lo publicado devuelve el faltante, no un precio inventado., En el bid se recorre hacia abajo: el signo se reporta positivo, es coste igual., Monotonia: el precio medio de compra no puede mejorar al crecer el tamanio. (+8 more)

### Community 74 - "FakePool"
Cohesion: 0.29
Nodes (6): FakePool, asyncio, MonkeyPatch, test_prometheus_metrics_renders_scalp_runtime_values(), asyncio, test_la_matriz_no_pide_ventanas_que_la_retencion_no_cubre()

### Community 76 - "Parte VII — Modo Scalping / Ejecución rápida"
Cohesion: 0.12
Nodes (16): 11. Delta matrix 15s–15m, 12. Futures tape real-time, 13. Order book imbalance, 14. Absorption matrix, 15. Liquidation tape real-time, 16. OI microdelta, 17. VWAP y niveles intradía, 18. Scalp score (+8 more)

### Community 78 - "test_dashboard_presentation.py"
Cohesion: 0.21
Nodes (12): Contratos de presentacion introducidos en v1.4.5. Cubren lo que la vista…, slice_js(), test_absent_whale_activity_is_counted_not_drawn_as_zero(), test_analyzer_prefill_never_overwrites_a_typed_value(), test_delta_profile_offers_the_windows_that_have_coverage(), test_delta_profile_panel_is_svg_and_declares_its_limits(), test_liquidation_profile_is_dom_safe_and_declares_realized_density(), test_liquidation_profile_orders_by_price_and_marks_the_current_one() (+4 more)

### Community 80 - "test_p0_regresion_auditoria.py"
Cohesion: 0.13
Nodes (17): _ctx_base(), Pruebas de regresión propuestas para Coinalyze v1.4.9-P0-P3. Origen: auditoría…, El §6.2 original repetía 8h/4h en contexto y confirmación, y 1h en dos capas., optional_finite conserva la ausencia; _safe solo vale donde el default es…, test_basis_rejects_future_timestamps(), test_frontend_surfaces_endpoint_error(), test_liquidation_null_is_not_zero(), test_missing_price_does_not_create_absorption() (+9 more)

### Community 82 - "v1.5.0 — corrección de la reorganización"
Cohesion: 0.13
Nodes (15): Backend (`app/scalp_logic.py`), Frontend (`static/app.js`), Lo que NO entra en esta versión, P0 — la ausencia de dato ya no vale cero, P1 — dirección y setup separados, P1 — el perfil cambia la jerarquía visual, P1 — fin del umbral universal de 5 bps, P1 — la pestaña Calidad, en tres niveles (+7 more)

### Community 83 - "Coinalyze Derivatives Operator"
Cohesion: 0.14
Nodes (14): API, Arquitectura, Coinalyze Derivatives Operator, Decisiones de consumo, Instalación en Proxmox, Instalación manual para desarrollo, Limitaciones explícitas, Operación (+6 more)

### Community 84 - "Coinalyze Operator Dashboard v1.5.0"
Cohesion: 0.14
Nodes (14): Coinalyze Operator Dashboard v1.5.0, v1.3.2 — correcciones de la auditoría, v1.3.3 — el diferencial spot/futuros dejaba de ser comparable, v1.3.4 — corrección de procedencia y contexto completo para IA por web, v1.3.5 — lectura CVD de 90 sesiones para operaciones de dos sesiones, v1.3.6 — barreras de precio y esfuerzo de ruptura, v1.3.7 — cockpit por horizonte y memoria de mercado de dos años, v1.4.4 — rango Wyckoff automático (+6 more)

### Community 89 - "_IntradayConnection"
Cohesion: 0.21
Nodes (10): _bar(), _IntradayConnection, fetch() distingue la consulta intradia de la de sesiones por su texto., 4 min de retraso son media ventana en 9m e irrelevantes en 16h., Precio plano con ruido: no hay movimiento que divergir aunque la pendiente…, test_intraday_block_can_be_omitted_for_cheap_ai_profiles(), test_intraday_freshness_degrades_on_short_windows(), test_intraday_ignores_moves_inside_their_own_noise() (+2 more)

### Community 90 - "Settings"
Cohesion: 0.14
Nodes (14): load_market_catalog(), resolve_market_catalog_path(), resolve_project_root(), Settings, BaseSettings, field_validator, model_validator, PathLike (+6 more)

### Community 91 - "asyncio"
Cohesion: 0.21
Nodes (11): _DivergenceConnection, asyncio, Solo sesiones: la consulta intradia (spot_trades_agg) devuelve vacio., La ventana de n sesiones compara el cierre actual contra n sesiones atras., BTC marcaba 'bajista' en 1d con el precio en +0.0003%: cruzar el cero no basta., test_divergence_flags_price_up_with_spot_cvd_down(), test_divergence_reports_unavailable_without_history(), test_divergence_uses_spot_cvd_not_the_mixed_diff() (+3 more)

### Community 92 - "Traspaso para IA — Coinalyze Operator Dashboard v1.3.7"
Cohesion: 0.15
Nodes (12): 1. Qué es, 2. De dónde salen los datos — **léelo, aquí se equivocó ya una IA**, 3. Retención — condiciona qué se puede calcular, 4. Qué se hizo en esta ronda (v1.3.1 → v1.3.7), 5. Trampas ya pisadas — no las repitas, 6. Límites duros — no se pueden salvar sin feeds nuevos, 7. Pendiente / ofrecido y no hecho, 8. Cómo desplegar y verificar (+4 more)

### Community 94 - "test_metrics_endpoint.py"
Cohesion: 0.15
Nodes (11): Regresiones de la auditoria v1.3.1. /metrics devolvia 500 (KeyError: 'detail')…, El endpoint y el resumen de scalp usaban umbrales distintos (0.02 vs 0.04).…, 1d/3d median el OI sobre n sesiones, no sobre toda la ventana cargada., rsync --delete con un paquete solo-app borraba sql/, scripts/ y deploy/., SHA256SUMS traia la ruta absoluta de la maquina de build; no verificaba nada., EXTRACT(EPOCH ...) devuelve numeric -> asyncpg da Decimal -> el JSON sale como…, test_absorption_has_a_single_definition(), test_lag_columns_are_cast_to_float8_so_json_stays_numeric() (+3 more)

### Community 95 - "test_v150_topbar.py"
Cohesion: 0.18
Nodes (9): bloques_topbar(), v1.5.0 — la barra superior reparte por AREAS, no por columnas implícitas. La…, Cada declaración de `grid-template-areas` que afecta a `.topbar`., Un área que falta en una rejilla deja ese control en una columna implícita., Filas de distinta longitud son `grid-template-areas` inválido y el navegador la…, Si viviera dentro de una sección, no se vería en las otras siete pestañas., test_el_selector_de_setup_esta_en_la_barra_permanente(), test_las_rejillas_son_rectangulares() (+1 more)

### Community 98 - "renderDaily"
Cohesion: 0.26
Nodes (12): rate(), renderDaily(), renderFlowCharts(), renderGapNote(), renderOiChart(), renderQuickRead(), renderWhaleActivity(), seriesSegments() (+4 more)

### Community 99 - "test_absorption_requires_meaningful_magnitude"
Cohesion: 0.50
Nodes (4): parametrize, 1 USD de delta neto sobre 10M de volumen es ruido de redondeo, no absorcion.…, test_absorption_requires_meaningful_magnitude(), test_classify_absorption()

### Community 100 - "Despliegue en Proxmox VE"
Cohesion: 0.18
Nodes (7): Creación de referencia, Despliegue en Proxmox VE, Exposición, Instalación, Perfil del contenedor, TLS, Verificación

### Community 102 - "generate_dashboard_usage_pdf.py"
Cohesion: 0.35
Nodes (10): ParagraphStyle, body_page(), build_pdf(), cover(), flush_list(), flush_paragraph(), make_styles(), markdown_to_story() (+2 more)

### Community 103 - "configure_secrets.sh"
Cohesion: 0.33
Nodes (10): ask_secret(), ask_value(), generate_if_empty(), NGINX_ALLOWED_CIDRS, remove_key(), render_nginx_allowlist(), set_kv(), set_raw_kv() (+2 more)

### Community 105 - "schema.sql"
Cohesion: 0.08
Nodes (23): daily_session_agg, daily_verdict, external_macro_observation, funding_rate, futures_trades_agg, futures_trades_realtime, liquidations, liquidations_realtime (+15 more)

### Community 106 - "test_v150_version_docs.py"
Cohesion: 0.18
Nodes (7): v1.5.0 — la versión declarada y lo que la documentación promete., El User-Agent tambien identifica la version: si no se actualiza, miente., Requisito explicito: no se implementó ni se simuló, y hay que decirlo., La documentación dice que no existe: se comprueba que efectivamente no existe., test_el_recuperador_de_huecos_no_esta_implementado(), test_no_queda_ninguna_referencia_a_la_version_anterior_en_el_codigo(), test_se_declara_que_el_recuperador_de_huecos_NO_entra()

### Community 107 - "trend_matrix"
Cohesion: 0.14
Nodes (15): cvd_matrix(), _cvd_src(), _oi_change_pct(), Estructura auditable: swings, estado, BOS/CHoCH e invalidación con distancias %., Rolling spot flow with a complete 1-minute history plus a non-overlapping live…, Delta por exchange y ventana desde una tabla de trades, con ts min/max…, CVD por ventana (1m-7d) spot/fut/diff por-venue. Ventanas cortas desde…, spot_flow_windows() (+7 more)

### Community 108 - "Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge"
Cohesion: 0.20
Nodes (9): Aplicaciones, Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge, Criterios de implementación sin código, Datos y procesamiento, IA, Modelo de despliegue, Objetivo del sistema, Seguridad (+1 more)

### Community 109 - "Patches aplicados — v1.1.2"
Cohesion: 0.20
Nodes (9): Bugs corregidos, Cambios funcionales, Patches aplicados — v1.1.1, Patches aplicados — v1.1.2, Patches correctivos, Tests agregados, v1.2.1 — cierre de residuales, Validación esperada post-upgrade (+1 more)

### Community 112 - "huecos.test.js"
Cohesion: 0.22
Nodes (6): app, assert, { cargarApp }, f(), T(), test

### Community 113 - "daily_agg.py"
Cohesion: 0.13
Nodes (28): apply_retention(), backfill(), compute_session(), cycle(), latest_closed_session_date(), persist_verdicts(), date, datetime (+20 more)

### Community 117 - "Coinalyze v1.4.5 — presentación del operador"
Cohesion: 0.22
Nodes (8): Analizadores en un solo panel, con los campos precargados, Ausencia de whale: contada, no dibujada como cero, Coinalyze v1.4.5 — presentación del operador, Densidad, Ejes en dinero, no en floats crudos, Perfil de liquidaciones por nivel, Sparklines en las tarjetas de cabecera, Verificación

### Community 118 - "renderDeltaProfile"
Cohesion: 0.28
Nodes (9): executionClass(), profileRowY(), renderDeltaProfile(), renderExecutionRows(), renderHypothesis(), renderSetupRows(), rowDL(), spreadWarning() (+1 more)

### Community 120 - "ejecucion.test.js"
Cohesion: 0.22
Nodes (7): app, assert, { cargarApp, APP_JS }, fs, FUENTE, SIN_EVALUAR, test

### Community 121 - "harness.js"
Cohesion: 0.28
Nodes (8): cargarApp(), crearDocumento(), fs, INDEX_HTML, leerIndexHtml(), path, RAIZ, vm

### Community 124 - "CLAUDE.md — instrucciones para Claude Code"
Cohesion: 0.25
Nodes (7): Antes de cada push (obligatorio), CLAUDE.md — instrucciones para Claude Code, Comportamiento como reviewer, Dónde trabajas, graphify, Qué NO puedes hacer, Qué puedes hacer

### Community 125 - "install.sh"
Cohesion: 0.32
Nodes (7): DEBIAN_FRONTEND, LANG, LC_ALL, PGPASSWORD, render_nginx_allowlist(), install.sh script, write_nginx_allowlist()

### Community 126 - "Coinalyze v1.4.6 — perfil de volumen y delta por nivel de precio"
Cohesion: 0.25
Nodes (7): `/api/delta-profile`, Coinalyze v1.4.6 — perfil de volumen y delta por nivel de precio, Defecto corregido al escribir las pruebas, Dos límites que el panel declara, Qué responde, Ventanas, según la cobertura que existe de verdad, Verificación

### Community 127 - "GitHub Actions y runner self-hosted"
Cohesion: 0.25
Nodes (8): Branch protection en `main`, GitHub Actions y runner self-hosted, Operación, Registro (referencia), Retirar el runner de GitHub, Runner self-hosted, Secrets, Workflows

### Community 129 - "Operaciones"
Cohesion: 0.25
Nodes (7): Comandos frecuentes, Estado y logs de producción, Inventario, Mantenimiento del LXC DEV, Operaciones, Troubleshooting, Usuarios y privilegios

### Community 130 - "update.sh"
Cohesion: 0.32
Nodes (6): LANG, LC_ALL, PGPASSWORD, render_nginx_allowlist(), update.sh script, write_nginx_allowlist()

### Community 135 - "navegacion.test.js"
Cohesion: 0.25
Nodes (7): APP_JS, assert, { cargarApp, leerIndexHtml, APP_JS }, fs, { sectionIds, navLinks }, test, { todosLosIds }

### Community 137 - "AGENTS.md — instrucciones para Codex CLI"
Cohesion: 0.29
Nodes (6): AGENTS.md — instrucciones para Codex CLI, Antes de cada push (obligatorio), Dónde trabajas, graphify, Qué NO puedes hacer, Qué puedes hacer

### Community 138 - "AI Engineering Rules — coinanalyze"
Cohesion: 0.25
Nodes (8): AI Engineering Rules — coinanalyze, Colaboración Codex + Claude, Contexto de la plataforma, Entorno y comandos del proyecto, Flujo de trabajo (resumen), GRAPH-FIRST POLICY (Graphify), Las 20 reglas, Restricciones específicas de Git para agentes

### Community 139 - "Flujo de desarrollo"
Cohesion: 0.29
Nodes (7): Acceso desde Windows, Ciclo por tarea, Colaboración Codex ↔ Claude, Crear / listar / eliminar worktrees, Ejecutar Codex / Claude, Estructura, Flujo de desarrollo

### Community 140 - "Parches aplicados por revisión técnica"
Cohesion: 0.29
Nodes (6): Correctitud de señales, Infraestructura, Optimización, Parches aplicados por revisión técnica, Seguridad, Tokens IA

### Community 145 - "Parche del bridge de Telegram — v1.3.4"
Cohesion: 0.33
Nodes (5): Aplicar, Dependencia, Parche del bridge de Telegram — v1.3.4, Qué hace, Verificar sin publicar en el canal

### Community 148 - "Coinalyze v1.4.8 — lectura rápida del flujo"
Cohesion: 0.33
Nodes (5): Coinalyze v1.4.8 — lectura rápida del flujo, Método, Objetivo, Presentación, Replay sin información futura

### Community 151 - "asnumber.test.js"
Cohesion: 0.33
Nodes (4): app, assert, { cargarApp }, test

### Community 152 - "Path"
Cohesion: 0.15
Nodes (17): Path, test_backup_excludes_python_build_artifacts(), test_full_backup_is_encrypted_complete_and_excludes_its_key(), test_horizontal_rollback_removes_shard_heartbeats_before_legacy_check(), test_schema_removes_literal_asset_checks_and_adds_foreign_keys(), test_install_scripts_write_nginx_allowlist(), test_nginx_template_includes_server_allowlist(), Sin saber de cuándo es el libro, el coste calculado sobre él no significa nada. (+9 more)

### Community 153 - "Coinalyze v1.4.4 — Wyckoff automático y auditoría de v1.4.3"
Cohesion: 0.40
Nodes (4): Coinalyze v1.4.4 — Wyckoff automático y auditoría de v1.4.3, Defecto corregido durante la auditoría, Verificación, Wyckoff automático

### Community 154 - "Segunda ronda (2026-08-07): cuatro correcciones previas al gap recovery"
Cohesion: 0.40
Nodes (5): 1. El umbral de 5 bps desaparece también de la capa visual, 2. Un setup no se CONFIRMA con requisitos críticos sin evaluar, 3. El signo del Open Interest deja de votar dirección, 4. Los huecos se dibujan como huecos, Segunda ronda (2026-08-07): cuatro correcciones previas al gap recovery

### Community 155 - "Despliegue a producción"
Cohesion: 0.40
Nodes (5): Cómo desplegar, Despliegue a producción, Modelo de releases, Qué hace el wrapper (trust boundary), Seguridad clave

### Community 156 - "Patches aplicados — v1.2.0"
Cohesion: 0.40
Nodes (4): Cambios funcionales, Hardening adicional, Patches aplicados — v1.2.0, Validación

### Community 157 - "Patches aplicados — v1.2.1"
Cohesion: 0.40
Nodes (4): Cambios aplicados, Fuera de alcance, Objetivo, Patches aplicados — v1.2.1

### Community 158 - "PATCHES_APPLIED v1.2.4"
Cohesion: 0.40
Nodes (4): Cambios, Compatibilidad, Objetivo, PATCHES_APPLIED v1.2.4

### Community 159 - "PATCHES_APPLIED v1.2.5"
Cohesion: 0.40
Nodes (4): Alcance, Cambios, Decisión, PATCHES_APPLIED v1.2.5

### Community 160 - "Rollback"
Cohesion: 0.40
Nodes (5): Base de datos (IMPORTANTE), Cómo hacer rollback, Rollback, Rollback automático en un deploy fallido, Verificación tras rollback

### Community 161 - "backup.sh"
Cohesion: 0.60
Nodes (4): copy_path(), copy_tree(), PGPASSWORD, backup.sh script

### Community 163 - "_DailyReplayConnection"
Cohesion: 0.40
Nodes (3): _DailyReplayConnection, Un replay antiguo no puede calcular percentiles con sesiones que aún no…, test_daily_replay_applies_as_of_to_history_and_selected_rows()

### Community 170 - "Arquitectura DEV / CI-CD / Producción"
Cohesion: 0.50
Nodes (4): Arquitectura DEV / CI-CD / Producción, Diagrama, Principios, Red (verificada)

### Community 171 - "Coinalyze v1.4.7 — flujo ejecutado y reacción del precio"
Cohesion: 0.50
Nodes (3): Cambio, Coinalyze v1.4.7 — flujo ejecutado y reacción del precio, Problema

### Community 172 - "Patches aplicados v1.2.2"
Cohesion: 0.50
Nodes (3): Alcance no incluido, Hardening del collector realtime, Patches aplicados v1.2.2

### Community 173 - "Patches applied v1.2.3"
Cohesion: 0.50
Nodes (3): AI context API, Goal, Patches applied v1.2.3

### Community 174 - "Prometheus scraping"
Cohesion: 0.50
Nodes (3): Opción A — Scrape vía Nginx, Opción B — Scrape directo con header interno, Prometheus scraping

### Community 175 - "Validación v1.1.2"
Cohesion: 0.50
Nodes (3): Alcance de fixes, Resultado, Validación v1.1.2

## Knowledge Gaps
- **401 isolated node(s):** `Condition`, `LANG`, `LC_ALL`, `DEBIAN_FRONTEND`, `PGPASSWORD` (+396 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_Connection` connect `_Connection` to `api.py`, `timedelta`, `scalp_logic.py`, `ingest.py`, `metrics.py`, `scalp_collector.py`, `divergence_scan`, `CoinalyzeClient`, `as_float`, `delta_matrix`, `profile_read`, `test_v150_calidad.py`, `external_macro.py`, `calibrate_signals.py`, `TradeStore`, `test_market_feed_health.py`, `test_market_data_integrity_collector.py`, `flush_books`, `trend_matrix`, `daily_agg.py`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Why does `Settings` connect `Settings` to `test_ingest.py`, `_DailyReplayConnection`, `external_macro.py`, `test_db.py`, `test_daily_semantics.py`, `ingest.py`, `daily_agg.py`, `CoinalyzeClient`, `_IntradayConnection`, `asyncio`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `range_validate_read()` connect `zone_character_read` to `scalp_logic.py`, `as_float`, `number`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `_Connection` (e.g. with `CoinalyzeClient` and `PostgresSlidingWindowRateLimiter`) actually correct?**
  _`_Connection` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Condition`, `LANG`, `LC_ALL` to the rest of the system?**
  _401 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_ingest.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12380952380952381 - nodes in this community are weakly interconnected._
- **Should `api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05384512861522058 - nodes in this community are weakly interconnected._