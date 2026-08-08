# Graph Report - graphify-integration  (2026-08-08)

## Corpus Check
- 125 files · ~158,590 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2037 nodes · 4407 edges · 144 communities (119 shown, 25 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8f9f415d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- scalp_logic.py
- api.py
- evaluate_setup
- zone_character_read
- records
- hypothesis_evidence
- Connection
- app.js
- as_float
- calibrate_signals.py
- volatility_context
- test_breakout.py
- ai_context.py
- test_ingest.py
- test_wyckoff.py
- compute_regime
- daily_data
- daily_agg.py
- divergence_scan
- quality_feeds
- prometheus_metrics
- P0 — la ausencia de dato ya no vale cero
- interpretation.py
- number
- _first_present
- test_forward_returns
- test_flow_semantics.py
- test_el_percentil_no_dice_30_dias_si_no_los_tiene
- Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada
- test_scalp_summary_exposes_basis_bps
- test_scalp_summary_no_publica_basis_sin_marca_de_tiempo
- ws_collector.py
- profile_read
- test_v150_calidad.py
- compute_scalp_summary
- metrics.py
- profile_view
- Guia de uso - Coinalyze Operator Dashboard v1.2.5
- asNumber
- test_daily_semantics.py
- scalp_collector.py
- external_macro.py
- test_dashboard_layout.py
- test_v150_desk_snapshot.py
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- test_p3_impact_and_alerts.py
- number
- refreshOverview
- timedelta
- test_p1_timeframes_and_spot.py
- test_scalp_summary_degrades_when_book_is_not_fresh
- basis_quality
- test_p2_baselines.py
- walk_book
- Parte VII — Modo Scalping / Ejecución rápida
- test_dashboard_presentation.py
- test_ohlcv_4h.py
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
- response_headers
- renderDaily
- classify_absorption
- Despliegue en Proxmox VE
- generate_dashboard_usage_pdf.py
- configure_secrets.sh
- schema.sql
- test_v150_version_docs.py
- delta_matrix
- Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge
- Patches aplicados — v1.1.2
- huecos.test.js
- get_settings
- Coinalyze v1.4.5 — presentación del operador
- renderDeltaProfile
- ejecucion.test.js
- harness.js
- ingest.py
- CLAUDE.md — instrucciones para Claude Code
- install.sh
- Coinalyze v1.4.6 — perfil de volumen y delta por nivel de precio
- GitHub Actions y runner self-hosted
- Operaciones
- update.sh
- navegacion.test.js
- FakePool
- AGENTS.md — instrucciones para Codex CLI
- AI Engineering Rules — coinanalyze
- Flujo de desarrollo
- Parches aplicados por revisión técnica
- ClassList
- Parche del bridge de Telegram — v1.3.4
- FakeConnection
- Coinalyze v1.4.8 — lectura rápida del flujo
- asnumber.test.js
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
- test_daily_history_only_ships_on_the_expensive_profiles
- test_no_module_still_claims_the_futures_leg_is_a_multi_venue_aggregate
- test_render_functions_replace_their_container_instead_of_appending
- coinalyze-operator-dashboard
- test_time_axis_labels_always_carry_the_date
- test_session_bars_never_build_markup_from_api_strings
- test_partial_sessions_never_overwrite_a_good_two_venue_value

## God Nodes (most connected - your core abstractions)
1. `_get()` - 70 edges
2. `validate_symbol()` - 58 edges
3. `as_float()` - 55 edges
4. `compute_scalp_summary()` - 49 edges
5. `build_ai_symbol_context()` - 48 edges
6. `asNumber()` - 46 edges
7. `number()` - 45 edges
8. `safeArray()` - 42 edges
9. `loadSection()` - 41 edges
10. `number()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `test_normalize_profile()` --calls--> `normalize_profile()`  [EXTRACTED]
  tests/test_ai_context.py → app/ai_context.py
- `test_no_queda_ningun_umbral_universal_de_5_bps_en_el_backend()` --indirect_call--> `ai_context()`  [INFERRED]
  tests/test_v150_ejecucion.py → app/api.py
- `_DailyReplayConnection` --uses--> `Settings`  [INFERRED]
  tests/test_daily_semantics.py → app/config.py
- `_DivergenceConnection` --uses--> `Settings`  [INFERRED]
  tests/test_daily_semantics.py → app/config.py
- `_IntradayConnection` --uses--> `Settings`  [INFERRED]
  tests/test_daily_semantics.py → app/config.py

## Import Cycles
- None detected.

## Communities (144 total, 25 thin omitted)

### Community 0 - "scalp_logic.py"
Cohesion: 0.09
Nodes (41): _beta(), _binned(), _conditional_outcome(), cross_asset(), _flow_bias(), flow_confirmation(), _forward_returns(), level_breakout() (+33 more)

### Community 1 - "api.py"
Cohesion: 0.11
Nodes (54): ai_profiles(), context_metadata_endpoint(), cross_asset_endpoint(), cvd_matrix_endpoint(), dashboard_state(), data_confidence(), divergences_endpoint(), external_macro_endpoint() (+46 more)

### Community 2 - "evaluate_setup"
Cohesion: 0.05
Nodes (80): _beyond(), build_setup_context(), classify_oi(), _eval_continuacion(), _eval_rechazo(), _eval_reversion(), _eval_ruptura(), evaluate_setup() (+72 more)

### Community 3 - "zone_character_read"
Cohesion: 0.06
Nodes (77): _atr_abs(), _atr_pct(), _clamp(), _edge_episodes(), _effort_result(), _narrative(), _oi_behaviour(), _ols_slope() (+69 more)

### Community 4 - "records"
Cohesion: 0.19
Nodes (29): normalize_profile(), ai_context(), ai_context_bundle(), cvd(), cvd_divergence(), cvd_spot(), delta_profile_endpoint(), flow_spot_vs_perp() (+21 more)

### Community 5 - "hypothesis_evidence"
Cohesion: 0.05
Nodes (58): _banda(), _bps(), execution_assessment(), hypothesis_evidence(), Etiqueta de sesgo por BALANCE DE EVIDENCIA, sin mirar el coste de ejecucion. Ya…, Reparte la evidencia disponible respecto de la tesis que pone el OPERADOR.…, Distancia entre dos precios en puntos basicos, o None si falta alguno., ¿Cuanto se come la ejecucion del objetivo y del riesgo de ESTA operacion? PURA.… (+50 more)

### Community 6 - "Connection"
Cohesion: 0.14
Nodes (20): desk_state(), Snapshot COHERENTE de la Mesa: un solo calculo, un solo ancla temporal. La Mesa…, data_quality(), _dsr(), horizon_structure(), liquidation_map(), price_barriers(), Connection (+12 more)

### Community 7 - "app.js"
Cohesion: 0.06
Nodes (52): ANALYZER_INPUTS, ANALYZER_TABS, axisMoney(), axisPrice(), chartOptions(), clearBreakout(), clearRange(), clearSnapshotView() (+44 more)

### Community 8 - "as_float"
Cohesion: 0.12
Nodes (19): as_float(), _cvd_fut_window(), cvd_matrix(), _cvd_src(), execution_cost(), liquidation_burst(), market_structure(), _measured_event_sum() (+11 more)

### Community 9 - "calibrate_signals.py"
Cohesion: 0.40
Nodes (9): fetch_rows(), main(), pct(), Any, Connection, sample_key(), signal_side(), stats() (+1 more)

### Community 10 - "volatility_context"
Cohesion: 0.25
Nodes (9): _atr(), _closes_1min(), oi_context(), _oi_quadrant(), Volatilidad realizada anualizada (%), sobre retornos log de velas 1min, cripto…, Interpretacion probable (no certeza: cada contrato nuevo tiene un long y un…, _realized_vol(), _tr_series() (+1 more)

### Community 11 - "test_breakout.py"
Cohesion: 0.10
Nodes (48): _atr(), attempt_features(), breakout_read(), build_corpus(), classify_outcome(), _confirmation_checks(), _delta_usd(), find_attempts() (+40 more)

### Community 12 - "ai_context.py"
Cohesion: 0.11
Nodes (34): AIProfile, build_ai_context(), build_ai_symbol_context(), build_operator_read(), compact_dict(), compact_value(), daily_data(), daily_history() (+26 more)

### Community 13 - "test_ingest.py"
Cohesion: 0.28
Nodes (4): FakeConnection, FakeRollupConnection, test_rollup_ohlcv_5m_uses_local_one_minute_bars(), test_upsert_ohlcv_skips_invalid_candles()

### Community 14 - "test_wyckoff.py"
Cohesion: 0.44
Nodes (7): _range_bars(), _sessions(), test_bearish_flow_is_compatible_with_distribution(), test_bullish_flow_is_compatible_with_accumulation(), test_detects_range_without_user_supplied_boundaries(), test_output_contains_chart_and_actionable_boundaries(), test_trend_is_not_forced_into_a_range()

### Community 15 - "compute_regime"
Cohesion: 0.25
Nodes (8): compute_regime(), optional_finite(), float finito o None. La ausencia se propaga; nunca se convierte en cero. Un 0.0…, Balance de evidencia del regimen, renormalizado sobre los componentes MEDIBLES.…, test_compute_regime_organic_bullish(), optional_finite conserva la ausencia; _safe solo vale donde el default es…, test_regime_without_components_is_unavailable(), test_snapshot_missing_source_stays_null()

### Community 16 - "daily_data"
Cohesion: 0.38
Nodes (7): daily(), daily_data(), latest_snapshot(), Connection, date, setup(), snapshot()

### Community 17 - "daily_agg.py"
Cohesion: 0.25
Nodes (16): apply_retention(), backfill(), compute_session(), cycle(), latest_closed_session_date(), persist_verdicts(), Connection, date (+8 more)

### Community 18 - "divergence_scan"
Cohesion: 0.33
Nodes (7): divergence_scan(), _intraday_divergences(), Pendiente por minimos cuadrados, normalizada por la escala de la serie., Mismo contraste que en sesiones, pero sobre velas de 1 minuto. Precio desde…, Precio subiendo mientras el CVD spot acumulado baja (o al reves), sostenido.…, _return_stdev_pct(), _slope_pct()

### Community 19 - "quality_feeds"
Cohesion: 0.50
Nodes (4): quality_feeds(), Calidad de los FEEDS de mercado y de cada METRICA publicada. La pestana de…, metric_quality(), Calidad POR METRICA publicada, no por feed ni por proceso. PURA: recibe bloques…

### Community 21 - "prometheus_metrics"
Cohesion: 0.67
Nodes (3): _parse_heartbeat_detail(), prometheus_metrics(), Response

### Community 22 - "P0 — la ausencia de dato ya no vale cero"
Cohesion: 0.67
Nodes (3): Backend (`app/scalp_logic.py`), Frontend (`static/app.js`), P0 — la ausencia de dato ya no vale cero

### Community 23 - "interpretation.py"
Cohesion: 0.13
Nodes (32): _barrier_candidates(), _barrier_zones(), Condition, _cvd_observation(), _cvd_side(), cvd_swing_read(), daily_flow_read(), evaluate_setups() (+24 more)

### Community 24 - "number"
Cohesion: 0.20
Nodes (34): externalMetricValue(), imbalanceCell(), liqProfileMark(), liqProfileRow(), loadSection(), money(), nd(), number() (+26 more)

### Community 27 - "test_flow_semantics.py"
Cohesion: 0.09
Nodes (32): _classify_passive(), compute_swing_score(), Detecta absorcion por limites pasivos y la mapea a…, Puro: lee los bloques ya calculados y sintetiza sesgo largo plazo. NO es…, _bars(), _blocks(), Regresiones de la auditoria v1.3.8. Cada test fija una conclusion que se…, Medido en vivo (BTC): score 45 con 4 de 7 componentes mudos se publicaba como… (+24 more)

### Community 29 - "Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada"
Cohesion: 0.06
Nodes (31): 1. P0 — El diferencial spot−futuros votaba dirección, 2. P1 — El componente "absorción CVD" del score de barreras estaba muerto, 3. P1 — "100% long" con la mitad de la evidencia muda, 4. P1 — Pivotes 4h sobre el 6.7% de la historia pedida, 5-6. P2 — Ceros silenciosos y doble conteo, Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada, Causa raíz, Causa raíz (+23 more)

### Community 32 - "ws_collector.py"
Cohesion: 0.13
Nodes (17): configure_logging(), binance_consumer(), Bucket, BucketStore, bybit_consumer(), flush_minute(), flush_realtime(), heartbeat_loop() (+9 more)

### Community 34 - "profile_read"
Cohesion: 0.15
Nodes (26): bucket_index(), bucket_size(), delta_profile(), _floor_log10(), profile_read(), Any, Connection, Perfil de volumen y delta por nivel de precio. Responde a "en esta zona, ¿hubo… (+18 more)

### Community 35 - "test_v150_calidad.py"
Cohesion: 0.09
Nodes (20): feed_quality(), _feed_status(), Estado real de cada FEED de mercado, uno por uno. Distinto de `data_quality()`,…, Estado del feed y su ultimo error, sin confundir calma con caida. Las…, _hb(), metricas(), fixture, v1.5.0 — la pestaña Calidad separa servicios, feeds y métricas. (+12 more)

### Community 37 - "compute_scalp_summary"
Cohesion: 0.18
Nodes (24): compute_scalp_summary(), score_component(), ctx_completo(), parametrize, v1.5.0 — la ausencia de dato NO se convierte en cero en…, Colector vivo y ninguna liquidacion = mercado en calma, no falta de dato., `missing_components` no puede ser decorativo: debe cuadrar con el peso medido., Contexto con los 7 componentes medibles. `None` explicito retira un insumo. (+16 more)

### Community 39 - "metrics.py"
Cohesion: 0.22
Nodes (16): compute_and_store_all(), compute_snapshot(), current_nyse_start(), insert_snapshot(), Connection, date, datetime, Convierte a float con un default. SOLO donde ese default es legitimo. No usar… (+8 more)

### Community 40 - "profile_view"
Cohesion: 0.14
Nodes (26): profile_view(), Compone trend_matrix y delta_matrix en la jerarquia del perfil elegido. PURA a…, matrix(), P1: selector intradia/swing con jerarquia explicita de temporalidades.…, Regla del proyecto: se renormaliza sobre lo medible, nunca se suma 0., Sin caja negra: cada capa publica peso, score y aportacion., v1.5.0: 30s/1m tienen capa propia en swing, con PESO CERO. Antes vivian en…, Describirla en las dos capas era una contradiccion de la propia jerarquia. (+18 more)

### Community 41 - "Guia de uso - Coinalyze Operator Dashboard v1.2.5"
Cohesion: 0.08
Nodes (25): 10. Absorcion, 11. Order book, 12. Liquidaciones RT, 13. Basis perp-spot, 14. Senales recientes, 15. Niveles de liquidacion, 16. Graficas principales, 17. Lecturas combinadas (+17 more)

### Community 42 - "asNumber"
Cohesion: 0.13
Nodes (26): asNumber(), card(), dailySeries(), dateTime(), deltaFlowQuadrant(), deltaShare(), flowQuadrant(), fundingClass() (+18 more)

### Community 44 - "test_daily_semantics.py"
Cohesion: 0.11
Nodes (7): El CVD por sesión describe agresión ejecutada, no inventario institucional.…, daily_session_agg se grafica a las 12:00Z: mostrar la hora seria ruido., Sin grid-column caia a span 1 de 12 y la tabla salia aplastada., test_conditional_outcome_needs_a_real_sample(), test_daily_chart_axis_shows_dates_without_a_meaningless_hour(), test_divergence_panel_spans_the_full_grid_width(), test_slope_sign_detects_direction()

### Community 45 - "scalp_collector.py"
Cohesion: 0.06
Nodes (54): all_expected_fresh(), binance_loop(), binance_market_loop(), BookResyncRequired, BookStats, BookStore, bybit_loop(), cleanup() (+46 more)

### Community 48 - "external_macro.py"
Cohesion: 0.20
Nodes (24): align_with_internal(), build_external_macro_context(), _direction(), external_macro_context(), _metric(), parse_bls_calendar(), parse_coinglass_etf(), parse_fomc_calendar() (+16 more)

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

### Community 60 - "test_p3_impact_and_alerts.py"
Cohesion: 0.13
Nodes (18): Avisos que solo tienen sentido contra la distribucion historica, no contra un…, scalp_alerts(), statistical_alerts(), impacto(), parametrize, P3: impacto de mercado realizado y alertas contra la distribucion, no contra un…, El feed no da profundidad que abarque precio: no se puede sostener esa…, alto' aparece por definicion el 5-10% del tiempo: alertarlo seria ruido… (+10 more)

### Community 61 - "number"
Cohesion: 0.27
Nodes (20): number(), _atr_abs(), _bar_date(), _bias_read(), _candidate_rank(), _clamp(), _clean_bars(), detect_latest_range() (+12 more)

### Community 62 - "refreshOverview"
Cohesion: 0.14
Nodes (21): api(), boot(), breakoutEmpty(), connectStream(), initDeltaProfile(), initDiffToggle(), initHypothesis(), initSectionNav() (+13 more)

### Community 64 - "timedelta"
Cohesion: 0.23
Nodes (7): SamplingMode, select_samples(), date_bin ancla en 1970-01-01T00:00:00Z; hay que probar que eso alinea con…, test_el_anclaje_en_1970_cae_en_medianoche_utc(), test_calibration_episode_sampling_deduplicates_stable_state(), test_calibration_non_overlap_sampling_deduplicates_by_spacing(), timedelta

### Community 67 - "test_p1_timeframes_and_spot.py"
Cohesion: 0.11
Nodes (17): asyncio, parametrize, P1: vela de 18 m determinista y pata spot del mismo venue. Coinalyze NO sirve…, La asimetria de v1.3.4 era perp de Binance contra spot de Binance+Bybit., validate_symbol filtra contra SUPPORTED_SYMBOLS: el spot solo existe como dato., spot_perp_flow vota con flow_confirmation, que mira el signo de AMBAS patas.…, 1440/18 = 80 exacto: ninguna vela queda a caballo entre dos dias UTC., El prompt maestro lo marca como requisito: 18m no es 15m ni 20m. (+9 more)

### Community 69 - "basis_quality"
Cohesion: 0.16
Nodes (17): basis_quality(), Basis perp-spot con puerta de frescura: devuelve None cuando no se sostiene. El…, parametrize, P0: el dashboard no debe publicar como fiable un dato que no lo es. Dos…, Un collector caido al PRINCIPIO de la ventana no lo ve un lag() a secas., El caso que motiva el P0: una pata congelada y la otra viva., Medido: el skew esta acotado por la rejilla de 5 s (p50 0.4-0.8 s, maximo 4.8…, Regla del proyecto: ausencia de dato es None, jamas 0. (+9 more)

### Community 71 - "test_p2_baselines.py"
Cohesion: 0.14
Nodes (15): baseline_band(), Situa un valor en su distribucion historica: banda + z-score robusto. Robusto =…, parametrize, P2: los umbrales salen de la distribucion medida, no de una constante. Medicion…, Una muestra corta no es una distribucion: mejor sin baseline que con una…, El ratio long/short reparte CUENTAS: leerlo como dinero es el error tipico., (x - mediana) / (1.4826 * MAD): la cola de esta distribucion rompe media y…, A 4 h sobre 14 dias de 1min saldrian ~80 observaciones: se usa el 4hour (300… (+7 more)

### Community 73 - "walk_book"
Cohesion: 0.16
Nodes (17): Consume la escalera hasta cubrir size_usd y devuelve el precio medio de…, walk_book(), test_walk_book_uses_first_valid_level_as_best_price(), parametrize, P1: coste de ejecucion recorriendo la escalera real del libro. Bybit entrega 50…, Ejecutar 201 USD toma los 100 del primer nivel y 101 del segundo = 1 unidad a…, Pedir mas de lo publicado devuelve el faltante, no un precio inventado., En el bid se recorre hacia abajo: el signo se reporta positivo, es coste igual. (+9 more)

### Community 76 - "Parte VII — Modo Scalping / Ejecución rápida"
Cohesion: 0.05
Nodes (41): 10. Histórico diario y CVD spot acumulado, 11. Delta matrix 15s–15m, 12. Futures tape real-time, 13. Order book imbalance, 14. Absorption matrix, 15. Liquidation tape real-time, 16. OI microdelta, 17. VWAP y niveles intradía (+33 more)

### Community 78 - "test_dashboard_presentation.py"
Cohesion: 0.21
Nodes (12): Contratos de presentacion introducidos en v1.4.5. Cubren lo que la vista…, slice_js(), test_absent_whale_activity_is_counted_not_drawn_as_zero(), test_analyzer_prefill_never_overwrites_a_typed_value(), test_delta_profile_offers_the_windows_that_have_coverage(), test_delta_profile_panel_is_svg_and_declares_its_limits(), test_liquidation_profile_is_dom_safe_and_declares_realized_density(), test_liquidation_profile_orders_by_price_and_marks_the_current_one() (+4 more)

### Community 79 - "test_ohlcv_4h.py"
Cohesion: 0.12
Nodes (13): asyncio, v1.3.9 — velas 4h nativas como fuente de los pivotes de barreras. Medido contra…, Una vela se etiqueta con el inicio de su bucket. Con la tolerancia fija de 300…, Sin regla propia las velas 4h crecerian sin limite., El backfill las trae una vez; el borde necesita reescribirse cada ciclo., 5min solo llega a ~8-9 dias; preferirlo dejaba los pivotes en el 6.7% del…, Pedir 365 dias devuelve chunks vacios que se leen como un backfill exitoso., test_backfill_script_caps_at_the_measured_horizon() (+5 more)

### Community 80 - "test_p0_regresion_auditoria.py"
Cohesion: 0.14
Nodes (13): _ctx_base(), Pruebas de regresión propuestas para Coinalyze v1.4.9-P0-P3. Origen: auditoría…, El §6.2 original repetía 8h/4h en contexto y confirmación, y 1h en dos capas., Sin saber de cuándo es el libro, el coste calculado sobre él no significa nada., test_basis_rejects_future_timestamps(), test_execution_cost_unknown_age_is_not_valid(), test_missing_price_does_not_create_absorption(), test_missing_spot_does_not_create_divergence_or_difference() (+5 more)

### Community 82 - "v1.5.0 — corrección de la reorganización"
Cohesion: 0.18
Nodes (11): Lo que NO entra en esta versión, P1 — dirección y setup separados, P1 — el perfil cambia la jerarquía visual, P1 — fin del umbral universal de 5 bps, P1 — la pestaña Calidad, en tres niveles, P1 — navegación interna, P1 — presentación del flujo, P2 — barra superior (+3 more)

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
Cohesion: 0.16
Nodes (10): lifespan(), Settings, create_pool(), Pool, BaseSettings, FastAPI, field_validator, test_csv_settings_parsing() (+2 more)

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

### Community 96 - "response_headers"
Cohesion: 0.23
Nodes (12): client_ip_allowed(), response_headers(), stream(), stream_generator(), valid_internal_token(), validation_error(), exception_handler, JSONResponse (+4 more)

### Community 98 - "renderDaily"
Cohesion: 0.26
Nodes (12): rate(), renderDaily(), renderFlowCharts(), renderGapNote(), renderOiChart(), renderQuickRead(), renderWhaleActivity(), seriesSegments() (+4 more)

### Community 99 - "classify_absorption"
Cohesion: 0.20
Nodes (11): classify_absorption(), Clasifica absorcion desde el delta agresivo y el movimiento de precio. Fuente…, parametrize, 1 USD de delta neto sobre 10M de volumen es ruido de redondeo, no absorcion.…, test_absorption_requires_meaningful_magnitude(), test_classify_absorption(), El caso concreto que motiva P2: 0.10 en 3 m no filtraba practicamente nada., A 4 h el p75 medido es ~0.07: la constante 0.10 habria tirado lecturas validas. (+3 more)

### Community 100 - "Despliegue en Proxmox VE"
Cohesion: 0.29
Nodes (7): Creación de referencia, Despliegue en Proxmox VE, Exposición, Instalación, Perfil del contenedor, TLS, Verificación

### Community 102 - "generate_dashboard_usage_pdf.py"
Cohesion: 0.35
Nodes (9): ParagraphStyle, body_page(), build_pdf(), cover(), flush_list(), flush_paragraph(), make_styles(), markdown_to_story() (+1 more)

### Community 103 - "configure_secrets.sh"
Cohesion: 0.36
Nodes (9): ask_secret(), ask_value(), generate_if_empty(), NGINX_ALLOWED_CIDRS, render_nginx_allowlist(), set_kv(), set_raw_kv(), configure_secrets.sh script (+1 more)

### Community 105 - "schema.sql"
Cohesion: 0.17
Nodes (10): daily_session_agg, daily_verdict, external_macro_observation, liquidations_realtime, macro_event, metric_baseline, metrics_snapshot, orderbook_depth (+2 more)

### Community 106 - "test_v150_version_docs.py"
Cohesion: 0.18
Nodes (7): v1.5.0 — la versión declarada y lo que la documentación promete., El User-Agent tambien identifica la version: si no se actualiza, miente., Requisito explicito: no se implementó ni se simuló, y hay que decirlo., La documentación dice que no existe: se comprueba que efectivamente no existe., test_el_recuperador_de_huecos_no_esta_implementado(), test_no_queda_ninguna_referencia_a_la_version_anterior_en_el_codigo(), test_se_declara_que_el_recuperador_de_huecos_NO_entra()

### Community 107 - "delta_matrix"
Cohesion: 0.18
Nodes (14): delta_matrix(), _gap_too_large(), max_internal_gap(), _oi_change_pct(), passive_flow(), Rolling spot flow with a complete 1-minute history plus a non-overlapping live…, Mayor hueco entre buckets consecutivos DENTRO de la ventana, en segundos. La…, _realtime_flow() (+6 more)

### Community 108 - "Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge"
Cohesion: 0.20
Nodes (9): Aplicaciones, Brief técnico para IA — Coinalyze Operator Dashboard y AI Telegram Bridge, Criterios de implementación sin código, Datos y procesamiento, IA, Modelo de despliegue, Objetivo del sistema, Seguridad (+1 more)

### Community 109 - "Patches aplicados — v1.1.2"
Cohesion: 0.20
Nodes (9): Bugs corregidos, Cambios funcionales, Patches aplicados — v1.1.1, Patches aplicados — v1.1.2, Patches correctivos, Tests agregados, v1.2.1 — cierre de residuales, Validación esperada post-upgrade (+1 more)

### Community 112 - "huecos.test.js"
Cohesion: 0.22
Nodes (6): app, assert, { cargarApp }, f(), T(), test

### Community 113 - "get_settings"
Cohesion: 0.17
Nodes (11): CoinalyzeClient, CoinalyzeError, Any, RuntimeError, Counts Coinalyze billing units, where each requested symbol consumes one unit., SlidingWindowRateLimiter, get_settings(), run() (+3 more)

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

### Community 122 - "ingest.py"
Cohesion: 0.34
Nodes (15): finite(), ingest_cycle(), Any, Connection, datetime, Pool, Build recent 5-minute candles locally without spending API quota., Posicionamiento: l/s son porcentajes que suman 100 y r es su cociente. (+7 more)

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

### Community 136 - "FakePool"
Cohesion: 0.33
Nodes (4): FakePool, asyncio, MonkeyPatch, test_prometheus_metrics_renders_scalp_runtime_values()

### Community 137 - "AGENTS.md — instrucciones para Codex CLI"
Cohesion: 0.29
Nodes (6): AGENTS.md — instrucciones para Codex CLI, Antes de cada push (obligatorio), Dónde trabajas, graphify, Qué NO puedes hacer, Qué puedes hacer

### Community 138 - "AI Engineering Rules — coinanalyze"
Cohesion: 0.29
Nodes (7): AI Engineering Rules — coinanalyze, Colaboración Codex + Claude, Contexto de la plataforma, Entorno y comandos del proyecto, Flujo de trabajo (resumen), Las 20 reglas, Restricciones específicas de Git para agentes

### Community 139 - "Flujo de desarrollo"
Cohesion: 0.29
Nodes (7): Acceso desde Windows, Ciclo por tarea, Colaboración Codex ↔ Claude, Crear / listar / eliminar worktrees, Ejecutar Codex / Claude, Estructura, Flujo de desarrollo

### Community 140 - "Parches aplicados por revisión técnica"
Cohesion: 0.29
Nodes (6): Correctitud de señales, Infraestructura, Optimización, Parches aplicados por revisión técnica, Seguridad, Tokens IA

### Community 145 - "Parche del bridge de Telegram — v1.3.4"
Cohesion: 0.33
Nodes (5): Aplicar, Dependencia, Parche del bridge de Telegram — v1.3.4, Qué hace, Verificar sin publicar en el canal

### Community 146 - "FakeConnection"
Cohesion: 0.33
Nodes (4): dict, FakeConnection, FakeRecord, dict lanza KeyError igual que asyncpg.Record ante una columna no pedida.

### Community 148 - "Coinalyze v1.4.8 — lectura rápida del flujo"
Cohesion: 0.33
Nodes (5): Coinalyze v1.4.8 — lectura rápida del flujo, Método, Objetivo, Presentación, Replay sin información futura

### Community 151 - "asnumber.test.js"
Cohesion: 0.33
Nodes (4): app, assert, { cargarApp }, test

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
- **369 isolated node(s):** `Condition`, `LANG`, `LC_ALL`, `DEBIAN_FRONTEND`, `PGPASSWORD` (+364 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compute_scalp_summary()` connect `compute_scalp_summary` to `scalp_logic.py`, `api.py`, `classify_absorption`, `test_scalp_summary_degrades_when_book_is_not_fresh`, `basis_quality`, `Connection`, `test_p2_baselines.py`, `as_float`, `hypothesis_evidence`, `ai_context.py`, `scalp_collector.py`, `test_p0_regresion_auditoria.py`, `quality_feeds`, `_first_present`, `test_p3_impact_and_alerts.py`, `test_scalp_summary_exposes_basis_bps`, `test_scalp_summary_no_publica_basis_sin_marca_de_tiempo`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `breakout_read()` connect `test_breakout.py` to `scalp_logic.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `zone_character_read()` connect `zone_character_read` to `scalp_logic.py`, `Connection`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **What connects `Condition`, `LANG`, `LC_ALL` to the rest of the system?**
  _369 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `scalp_logic.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08710801393728224 - nodes in this community are weakly interconnected._
- **Should `api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11447811447811448 - nodes in this community are weakly interconnected._
- **Should `evaluate_setup` be split into smaller, more focused modules?**
  _Cohesion score 0.050980392156862744 - nodes in this community are weakly interconnected._