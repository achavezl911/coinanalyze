# Graph Report - setup-observables-oi  (2026-08-08)

## Corpus Check
- 130 files · ~167,161 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2176 nodes · 4711 edges · 142 communities (123 shown, 19 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `717fab5d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- scalp_logic.py
- api.py
- test_v150_criticos_y_oi.py
- zone_character_read
- records
- hypothesis_evidence
- structure_detail
- app.js
- as_float
- TASK.md
- setups.py
- test_breakout.py
- ai_context.py
- setup_observables
- test_wyckoff.py
- evaluate_setup
- scalp_context
- daily_agg.py
- divergence_scan
- ws_collector.py
- build_setup_context
- prometheus_metrics
- test_v150_oi_scoring.py
- interpretation.py
- number
- _first_present
- Graphify — knowledge graph del repositorio
- test_flow_semantics.py
- Parte II — Cada indicador, individualmente
- Auditoría v1.3.8 — semántica de flujo, componentes muertos y cobertura declarada
- test_scalp_summary_exposes_basis_bps
- test_scalp_summary_no_publica_basis_sin_marca_de_tiempo
- BucketStore
- delta_matrix
- profile_read
- test_v150_calidad.py
- Manual de interpretación — Coinalyze Derivatives Dashboard
- compute_scalp_summary
- Parte IV — Lecturas combinadas (setups)
- timedelta
- profile_view
- Guia de uso - Coinalyze Operator Dashboard v1.2.5
- asNumber
- cvd_matrix
- test_daily_semantics.py
- scalp_collector.py
- _coverage_status
- test_las_ventanas_largas_no_se_miden_sobre_1min
- external_macro.py
- test_dashboard_layout.py
- test_v150_desk_snapshot.py
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- Manual — Coinalyze Operator Dashboard v1.2.5 final
- test_p3_impact_and_alerts.py
- number
- refreshOverview
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
- trend_matrix
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
- coinalyze-operator-dashboard

## God Nodes (most connected - your core abstractions)
1. `_get()` - 70 edges
2. `compute_scalp_summary()` - 62 edges
3. `validate_symbol()` - 58 edges
4. `as_float()` - 56 edges
5. `build_ai_symbol_context()` - 48 edges
6. `asNumber()` - 46 edges
7. `number()` - 45 edges
8. `safeArray()` - 42 edges
9. `loadSection()` - 41 edges
10. `evaluate_setup()` - 35 edges

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

## Communities (142 total, 19 thin omitted)

### Community 0 - "scalp_logic.py"
Cohesion: 0.09
Nodes (43): _atr(), _beta(), _binned(), _closes_1min(), _conditional_outcome(), cross_asset(), _forward_returns(), level_breakout() (+35 more)

### Community 1 - "api.py"
Cohesion: 0.11
Nodes (53): ai_profiles(), context_metadata_endpoint(), cross_asset_endpoint(), cvd_matrix_endpoint(), data_confidence(), desk_state(), divergences_endpoint(), external_macro_endpoint() (+45 more)

### Community 2 - "test_v150_criticos_y_oi.py"
Cohesion: 0.10
Nodes (32): classify_oi(), oi_price_reading(), Clasifica el Open Interest como ESTADO de posicionamiento, sin direccion. El…, Lectura CONTEXTUAL de precio + OI + flujo. No es una relacion causal…, ctx_rico(), parametrize, Un setup no se CONFIRMA con requisitos críticos sin evaluar, y ΔOI no es…, Cada evaluador explica en su docstring cuales son sus criticos. (+24 more)

### Community 3 - "zone_character_read"
Cohesion: 0.06
Nodes (77): _atr_abs(), _atr_pct(), _clamp(), _edge_episodes(), _effort_result(), _narrative(), _oi_behaviour(), _ols_slope() (+69 more)

### Community 4 - "records"
Cohesion: 0.17
Nodes (31): normalize_profile(), ai_context(), ai_context_bundle(), cvd(), cvd_divergence(), cvd_spot(), delta_profile_endpoint(), flow_spot_vs_perp() (+23 more)

### Community 5 - "hypothesis_evidence"
Cohesion: 0.05
Nodes (58): _banda(), _bps(), execution_assessment(), hypothesis_evidence(), Etiqueta de sesgo por BALANCE DE EVIDENCIA, sin mirar el coste de ejecucion. Ya…, Reparte la evidencia disponible respecto de la tesis que pone el OPERADOR.…, Distancia entre dos precios en puntos basicos, o None si falta alguno., ¿Cuanto se come la ejecucion del objetivo y del riesgo de ESTA operacion? PURA.… (+50 more)

### Community 6 - "structure_detail"
Cohesion: 0.33
Nodes (6): _dsr(), horizon_structure(), Bias por horizonte DERIVADO de structure_detail (fuente unica de pivotes), para…, Downsample de filas (mas reciente primero) tomando cada n-esima, anclado al…, Estructura por horizonte con pivotes reales (reemplaza la etiqueta HH/HL por…, structure_detail()

### Community 7 - "app.js"
Cohesion: 0.06
Nodes (52): ANALYZER_INPUTS, ANALYZER_TABS, axisMoney(), axisPrice(), chartOptions(), clearBreakout(), clearRange(), clearSnapshotView() (+44 more)

### Community 8 - "as_float"
Cohesion: 0.09
Nodes (33): as_float(), _cvd_fut_window(), data_quality(), execution_cost(), _flow_bias(), flow_confirmation(), liquidation_burst(), _liquidation_window_measured() (+25 more)

### Community 9 - "TASK.md"
Cohesion: 0.04
Nodes (44): 1.1 NO UTILIZAR EL CENTRO DE LA BARRERA COMO FRONTERA DE RUPTURA, 1.2 `bars_closed_beyond`, 1.3 `returned_inside`, 1.4 `retest_done`, 1.5 `pullback_pct`, 1.6 `level_defended`, 1.7 Estados, 1. IMPLEMENTAR LOS OBSERVABLES REALES QUE TODAVÍA ESTÁN FIJADOS A `None` (+36 more)

### Community 10 - "setups.py"
Cohesion: 0.10
Nodes (41): _bars_closed_beyond(), _beyond(), _breakout_frontier(), _eval_continuacion(), _eval_rechazo(), _eval_reversion(), _eval_ruptura(), _flow_check() (+33 more)

### Community 11 - "test_breakout.py"
Cohesion: 0.10
Nodes (48): _atr(), attempt_features(), breakout_read(), build_corpus(), classify_outcome(), _confirmation_checks(), _delta_usd(), find_attempts() (+40 more)

### Community 12 - "ai_context.py"
Cohesion: 0.12
Nodes (33): AIProfile, build_ai_context(), build_ai_symbol_context(), build_operator_read(), compact_dict(), compact_value(), daily_data(), daily_history() (+25 more)

### Community 13 - "setup_observables"
Cohesion: 0.23
Nodes (26): Mide los cinco observables reales desde velas CERRADAS y estructura. Devuelve,…, setup_observables(), _bars(), _bundle(), Observables MEDIDOS sobre velas cerradas: bars_closed_beyond, returned_inside,…, Velas cerradas ascendentes; high/low se derivan del cierre salvo override por…, test_build_setup_context_con_bundle_mide_los_observables(), test_bundle_ausente_deja_bars_en_none() (+18 more)

### Community 14 - "test_wyckoff.py"
Cohesion: 0.44
Nodes (7): _range_bars(), _sessions(), test_bearish_flow_is_compatible_with_distribution(), test_bullish_flow_is_compatible_with_accumulation(), test_detects_range_without_user_supplied_boundaries(), test_output_contains_chart_and_actionable_boundaries(), test_trend_is_not_forced_into_a_range()

### Community 15 - "evaluate_setup"
Cohesion: 0.16
Nodes (23): evaluate_setup(), Evalua UN setup contra los observables disponibles. Pura y fail-closed., ctx_rico(), parametrize, v1.5.0 — direccion y setup son cosas distintas, y cada setup tiene logica…, Observables suficientes para que los cuatro setups tengan algo que decir., Lo que mata a una ruptura no es lo que mata a una continuacion., Tendencia alcista previa: continuacion viable, reversion imposible. (+15 more)

### Community 16 - "scalp_context"
Cohesion: 0.18
Nodes (14): daily(), daily_data(), dashboard_state(), latest_snapshot(), Connection, date, quality_feeds(), Calidad de los FEEDS de mercado y de cada METRICA publicada. La pestana de… (+6 more)

### Community 17 - "daily_agg.py"
Cohesion: 0.28
Nodes (14): apply_retention(), backfill(), compute_session(), cycle(), latest_closed_session_date(), persist_verdicts(), Connection, date (+6 more)

### Community 18 - "divergence_scan"
Cohesion: 0.33
Nodes (7): divergence_scan(), _intraday_divergences(), Pendiente por minimos cuadrados, normalizada por la escala de la serie., Mismo contraste que en sesiones, pero sobre velas de 1 minuto. Precio desde…, Precio subiendo mientras el CVD spot acumulado baja (o al reves), sostenido.…, _return_stdev_pct(), _slope_pct()

### Community 19 - "ws_collector.py"
Cohesion: 0.19
Nodes (17): lifespan(), run(), create_pool(), heartbeat(), Pool, run(), configure_logging(), binance_consumer() (+9 more)

### Community 20 - "build_setup_context"
Cohesion: 0.25
Nodes (16): build_setup_context(), Traduce los bloques ya publicados a los observables que pide cada setup. Solo…, test_build_setup_context_sin_bundle_mantiene_none(), _bars(), _bundle(), El camino REAL de produccion: datos OHLCV/barreras -> build_setup_context ->…, _scalp(), test_continuacion_es_fail_closed_sin_bundle() (+8 more)

### Community 21 - "prometheus_metrics"
Cohesion: 0.67
Nodes (3): _parse_heartbeat_detail(), prometheus_metrics(), Response

### Community 22 - "test_v150_oi_scoring.py"
Cohesion: 0.33
Nodes (15): ctx(), _oi(), _px15(), Open Interest en `compute_scalp_summary()`: ya NO vota direccion por el signo…, Contexto minimo y NEUTRO salvo el OI y su ventana de 15 m, para aislar la…, oi_now/oi_start que producen un Δ% dado., test_cobertura_15m_parcial_se_publica(), test_expansion_pero_flujo_contradice_no_vota_direccion() (+7 more)

### Community 23 - "interpretation.py"
Cohesion: 0.13
Nodes (32): _barrier_candidates(), _barrier_zones(), Condition, _cvd_observation(), _cvd_side(), cvd_swing_read(), daily_flow_read(), evaluate_setups() (+24 more)

### Community 24 - "number"
Cohesion: 0.20
Nodes (34): externalMetricValue(), imbalanceCell(), liqProfileMark(), liqProfileRow(), loadSection(), money(), nd(), number() (+26 more)

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

### Community 32 - "BucketStore"
Cohesion: 0.17
Nodes (7): Bucket, BucketStore, RtBucket, asyncio, test_ack_does_not_drop_bucket_changed_during_flush(), test_bucketstore_caps_realtime_buckets_during_database_outage(), test_whale_trade_threshold_is_asset_specific()

### Community 33 - "delta_matrix"
Cohesion: 0.31
Nodes (9): delta_matrix(), feed_quality(), _gap_too_large(), max_internal_gap(), Estado real de cada FEED de mercado, uno por uno. Distinto de `data_quality()`,…, Mayor hueco entre buckets consecutivos DENTRO de la ventana, en segundos. La…, _realtime_flow(), Cazado en producción: `feed_quality` decidía por el sufijo `_realtime` y… (+1 more)

### Community 34 - "profile_read"
Cohesion: 0.15
Nodes (26): bucket_index(), bucket_size(), delta_profile(), _floor_log10(), profile_read(), Any, Connection, Perfil de volumen y delta por nivel de precio. Responde a "en esta zona, ¿hubo… (+18 more)

### Community 35 - "test_v150_calidad.py"
Cohesion: 0.10
Nodes (16): _feed_status(), Estado del feed y su ultimo error, sin confundir calma con caida. Las…, _hb(), metricas(), fixture, v1.5.0 — la pestaña Calidad separa servicios, feeds y métricas., Liquidaciones: colector vivo y cero eventos es CALMA, no fallo., Su estado depende de la EDAD de cada pata, no de que las dos existan. (+8 more)

### Community 36 - "Manual de interpretación — Coinalyze Derivatives Dashboard"
Cohesion: 0.25
Nodes (8): Anexo — Cambios operativos v1.2.1, Manual de interpretación — Coinalyze Derivatives Dashboard, Parte I — El marco mental, Parte III — Cómo se relacionan (mapa de dependencias), Parte IX — Errores de scalping a evitar, Parte V — Rutina de lectura sugerida, Parte VI — Errores de interpretación a evitar, Parte VIII — Rutina específica para scalping

### Community 37 - "compute_scalp_summary"
Cohesion: 0.18
Nodes (24): compute_scalp_summary(), score_component(), ctx_completo(), parametrize, v1.5.0 — la ausencia de dato NO se convierte en cero en…, Colector vivo y ninguna liquidacion = mercado en calma, no falta de dato., `missing_components` no puede ser decorativo: debe cuadrar con el peso medido., Contexto con los 7 componentes medibles. `None` explicito retira un insumo. (+16 more)

### Community 38 - "Parte IV — Lecturas combinadas (setups)"
Cohesion: 0.33
Nodes (6): Parte IV — Lecturas combinadas (setups), Setup A — Distribución encubierta (sesgo SHORT de mediano plazo), Setup B — Acumulación silenciosa (sesgo LONG de mediano plazo), Setup C — Squeeze de shorts inminente (sesgo LONG de corto plazo), Setup D — Euforia / techo de corto plazo (sesgo SHORT / reducir longs), Setup E — Capitulación / suelo de corto plazo (sesgo LONG contrarian)

### Community 39 - "timedelta"
Cohesion: 0.05
Nodes (55): compute_and_store_all(), compute_regime(), compute_snapshot(), current_nyse_start(), insert_snapshot(), optional_finite(), Connection, date (+47 more)

### Community 40 - "profile_view"
Cohesion: 0.13
Nodes (28): profile_view(), Compone trend_matrix y delta_matrix en la jerarquia del perfil elegido. PURA a…, test_profile_coverage_scales_with_each_timeframe(), test_profile_does_not_count_same_timeframe_twice(), matrix(), P1: selector intradia/swing con jerarquia explicita de temporalidades.…, Regla del proyecto: se renormaliza sobre lo medible, nunca se suma 0., Sin caja negra: cada capa publica peso, score y aportacion. (+20 more)

### Community 41 - "Guia de uso - Coinalyze Operator Dashboard v1.2.5"
Cohesion: 0.08
Nodes (25): 10. Absorcion, 11. Order book, 12. Liquidaciones RT, 13. Basis perp-spot, 14. Senales recientes, 15. Niveles de liquidacion, 16. Graficas principales, 17. Lecturas combinadas (+17 more)

### Community 42 - "asNumber"
Cohesion: 0.13
Nodes (26): asNumber(), card(), dailySeries(), dateTime(), deltaFlowQuadrant(), deltaShare(), flowQuadrant(), fundingClass() (+18 more)

### Community 43 - "cvd_matrix"
Cohesion: 0.50
Nodes (4): cvd_matrix(), _cvd_src(), Delta por exchange y ventana desde una tabla de trades, con ts min/max…, CVD por ventana (1m-7d) spot/fut/diff por-venue. Ventanas cortas desde…

### Community 44 - "test_daily_semantics.py"
Cohesion: 0.06
Nodes (21): parametrize, El CVD por sesión describe agresión ejecutada, no inventario institucional.…, La serie sesion a sesion es lo que deja al modelo ver estructura, pero pesa., `.A` en Coinalyze es Binance: verificado contra su catalogo y contra el OI real., El formateador del motor solo pone fecha al cambiar de dia: 48 h de velas de 5…, daily_session_agg se grafica a las 12:00Z: mostrar la hora seria ruido., refresh() repinta cada 15 s: quien solo hace append apila una copia por ciclo.…, Las fechas vienen de la API y acaban dentro del SVG: nada de innerHTML aqui. (+13 more)

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

### Community 69 - "basis_quality"
Cohesion: 0.15
Nodes (18): basis_quality(), Basis perp-spot con puerta de frescura: devuelve None cuando no se sostiene. El…, parametrize, P0: el dashboard no debe publicar como fiable un dato que no lo es. Dos…, Un collector caido al PRINCIPIO de la ventana no lo ve un lag() a secas., El caso que motiva el P0: una pata congelada y la otra viva., Medido: el skew esta acotado por la rejilla de 5 s (p50 0.4-0.8 s, maximo 4.8…, Regla del proyecto: ausencia de dato es None, jamas 0. (+10 more)

### Community 71 - "test_p2_baselines.py"
Cohesion: 0.14
Nodes (15): baseline_band(), Situa un valor en su distribucion historica: banda + z-score robusto. Robusto =…, parametrize, P2: los umbrales salen de la distribucion medida, no de una constante. Medicion…, Una muestra corta no es una distribucion: mejor sin baseline que con una…, El ratio long/short reparte CUENTAS: leerlo como dinero es el error tipico., La serie empieza vacia: llamar '30 dias' a 26 horas de historia es precision…, (x - mediana) / (1.4826 * MAD): la cola de esta distribucion rompe media y… (+7 more)

### Community 73 - "walk_book"
Cohesion: 0.16
Nodes (17): Consume la escalera hasta cubrir size_usd y devuelve el precio medio de…, walk_book(), test_walk_book_uses_first_valid_level_as_best_price(), parametrize, P1: coste de ejecucion recorriendo la escalera real del libro. Bybit entrega 50…, Ejecutar 201 USD toma los 100 del primer nivel y 101 del segundo = 1 unidad a…, Pedir mas de lo publicado devuelve el faltante, no un precio inventado., En el bid se recorre hacia abajo: el signo se reporta positivo, es coste igual. (+9 more)

### Community 76 - "Parte VII — Modo Scalping / Ejecución rápida"
Cohesion: 0.12
Nodes (16): 11. Delta matrix 15s–15m, 12. Futures tape real-time, 13. Order book imbalance, 14. Absorption matrix, 15. Liquidation tape real-time, 16. OI microdelta, 17. VWAP y niveles intradía, 18. Scalp score (+8 more)

### Community 78 - "test_dashboard_presentation.py"
Cohesion: 0.21
Nodes (12): Contratos de presentacion introducidos en v1.4.5. Cubren lo que la vista…, slice_js(), test_absent_whale_activity_is_counted_not_drawn_as_zero(), test_analyzer_prefill_never_overwrites_a_typed_value(), test_delta_profile_offers_the_windows_that_have_coverage(), test_delta_profile_panel_is_svg_and_declares_its_limits(), test_liquidation_profile_is_dom_safe_and_declares_realized_density(), test_liquidation_profile_orders_by_price_and_marks_the_current_one() (+4 more)

### Community 79 - "test_ohlcv_4h.py"
Cohesion: 0.12
Nodes (13): asyncio, v1.3.9 — velas 4h nativas como fuente de los pivotes de barreras. Medido contra…, Una vela se etiqueta con el inicio de su bucket. Con la tolerancia fija de 300…, Sin regla propia las velas 4h crecerian sin limite., El backfill las trae una vez; el borde necesita reescribirse cada ciclo., 5min solo llega a ~8-9 dias; preferirlo dejaba los pivotes en el 6.7% del…, Pedir 365 dias devuelve chunks vacios que se leen como un backfill exitoso., test_backfill_script_caps_at_the_measured_horizon() (+5 more)

### Community 80 - "test_p0_regresion_auditoria.py"
Cohesion: 0.18
Nodes (10): _ctx_base(), Pruebas de regresión propuestas para Coinalyze v1.4.9-P0-P3. Origen: auditoría…, El §6.2 original repetía 8h/4h en contexto y confirmación, y 1h en dos capas., Sin saber de cuándo es el libro, el coste calculado sobre él no significa nada., test_execution_cost_unknown_age_is_not_valid(), test_missing_price_does_not_create_absorption(), test_missing_spot_does_not_create_divergence_or_difference(), test_numeric_parser_rejects_non_finite_values() (+2 more)

### Community 82 - "v1.5.0 — corrección de la reorganización"
Cohesion: 0.14
Nodes (14): Backend (`app/scalp_logic.py`), Frontend (`static/app.js`), Lo que NO entra en esta versión, P0 — la ausencia de dato ya no vale cero, P1 — dirección y setup separados, P1 — el perfil cambia la jerarquía visual, P1 — fin del umbral universal de 5 bps, P1 — la pestaña Calidad, en tres niveles (+6 more)

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
Cohesion: 0.23
Nodes (6): Settings, BaseSettings, field_validator, test_csv_settings_parsing(), test_security_settings_parse_cidrs_and_sslmode(), test_minute_retention_covers_a_full_nyse_session()

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
Cohesion: 0.18
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

### Community 107 - "trend_matrix"
Cohesion: 0.20
Nodes (11): _oi_change_pct(), Estructura auditable: swings, estado, BOS/CHoCH e invalidación con distancias %., Rolling spot flow with a complete 1-minute history plus a non-overlapping live…, spot_flow_windows(), _structure_from_swings(), trend_matrix(), FlowConnection, asyncio (+3 more)

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
Cohesion: 0.18
Nodes (10): CoinalyzeClient, CoinalyzeError, Any, RuntimeError, Counts Coinalyze billing units, where each requested symbol consumes one unit., SlidingWindowRateLimiter, get_settings(), main() (+2 more)

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
Cohesion: 0.19
Nodes (19): finite(), ingest_cycle(), Any, Connection, datetime, Pool, Build recent 5-minute candles locally without spending API quota., Posicionamiento: l/s son porcentajes que suman 100 y r es su cociente. (+11 more)

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
Cohesion: 0.25
Nodes (6): FakePool, asyncio, MonkeyPatch, test_prometheus_metrics_renders_scalp_runtime_values(), asyncio, test_la_matriz_no_pide_ventanas_que_la_retencion_no_cubre()

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
- **417 isolated node(s):** `Condition`, `LANG`, `LC_ALL`, `DEBIAN_FRONTEND`, `PGPASSWORD` (+412 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `compute_scalp_summary()` connect `compute_scalp_summary` to `scalp_logic.py`, `api.py`, `test_v150_criticos_y_oi.py`, `hypothesis_evidence`, `as_float`, `ai_context.py`, `scalp_context`, `test_v150_oi_scoring.py`, `_first_present`, `test_scalp_summary_exposes_basis_bps`, `test_scalp_summary_no_publica_basis_sin_marca_de_tiempo`, `scalp_collector.py`, `_coverage_status`, `test_p3_impact_and_alerts.py`, `test_scalp_summary_degrades_when_book_is_not_fresh`, `basis_quality`, `test_p2_baselines.py`, `test_p0_regresion_auditoria.py`, `classify_absorption`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `breakout_read()` connect `test_breakout.py` to `scalp_logic.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `evaluate_setup()` connect `evaluate_setup` to `scalp_logic.py`, `test_v150_criticos_y_oi.py`, `hypothesis_evidence`, `setups.py`, `build_setup_context`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **What connects `Condition`, `LANG`, `LC_ALL` to the rest of the system?**
  _417 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `scalp_logic.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08985200845665962 - nodes in this community are weakly interconnected._
- **Should `api.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11250873515024458 - nodes in this community are weakly interconnected._
- **Should `test_v150_criticos_y_oi.py` be split into smaller, more focused modules?**
  _Cohesion score 0.09803921568627451 - nodes in this community are weakly interconnected._