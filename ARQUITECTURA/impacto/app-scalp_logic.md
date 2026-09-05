# Impacto · `app/scalp_logic.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

109 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`swing_score`](#swing-score) | 6152 | 2 | 51 | **51** |
| [`as_float`](#as-float) | 920 | 37 | 9 | **44** |
| [`resolve_matrix_as_of`](#resolve-matrix-as-of) | 2404 | 24 | 10 | **32** |
| [`_explicit_as_of`](#-explicit-as-of) | 2398 | 25 | 0 | **25** |
| [`compute_scalp_summary`](#compute-scalp-summary) | 628 | 9 | 24 | **24** |
| [`scalp_context`](#scalp-context) | 325 | 9 | 24 | **24** |
| [`load_baselines`](#load-baselines) | 158 | 14 | 9 | **21** |
| [`baseline_band`](#baseline-band) | 134 | 13 | 9 | **20** |
| [`basis_quality`](#basis-quality) | 231 | 10 | 9 | **17** |
| [`classify_absorption`](#classify-absorption) | 193 | 10 | 9 | **17** |
| [`_closed_5m_oi_bounds`](#-closed-5m-oi-bounds) | 94 | 9 | 9 | **16** |
| [`_closed_window_move_pct`](#-closed-window-move-pct) | 590 | 9 | 9 | **16** |
| [`_first_present`](#-first-present) | 502 | 9 | 9 | **16** |
| [`_liquidation_window_measured`](#-liquidation-window-measured) | 514 | 9 | 9 | **16** |
| [`_measured_event_sum`](#-measured-event-sum) | 558 | 9 | 9 | **16** |
| [`scalp_bias_label`](#scalp-bias-label) | 292 | 9 | 9 | **16** |
| [`score_component`](#score-component) | 317 | 9 | 9 | **16** |
| [`_resample_highs_lows`](#-resample-highs-lows) | 1197 | 14 | 0 | **14** |
| [`_flow_windows`](#-flow-windows) | 2431 | 13 | 0 | **13** |
| [`spot_flow_windows`](#spot-flow-windows) | 2609 | 13 | 0 | **13** |
| [`_gap_and_baseline`](#-gap-and-baseline) | 4071 | 12 | 0 | **12** |
| [`_gap_threshold_seconds`](#-gap-threshold-seconds) | 4041 | 12 | 0 | **12** |
| [`_gap_too_large`](#-gap-too-large) | 4053 | 12 | 0 | **12** |
| [`_oi_change_pct`](#-oi-change-pct) | 4245 | 11 | 0 | **11** |
| [`_realtime_flow`](#-realtime-flow) | 4161 | 11 | 0 | **11** |
| [`_complete_tail_values`](#-complete-tail-values) | 960 | 10 | 0 | **10** |
| [`_contiguous_measured_suffix`](#-contiguous-measured-suffix) | 970 | 10 | 0 | **10** |
| [`flow_confirmation`](#flow-confirmation) | 4419 | 10 | 0 | **10** |
| [`_as_utc_datetime`](#-as-utc-datetime) | 543 | 9 | 0 | **9** |
| [`_atr`](#-atr) | 2926 | 9 | 0 | **9** |
| [`_coverage_status`](#-coverage-status) | 566 | 9 | 0 | **9** |
| [`_structure_from_swings`](#-structure-from-swings) | 2226 | 9 | 0 | **9** |
| [`_swings`](#-swings) | 2212 | 9 | 0 | **9** |
| [`_tr_series`](#-tr-series) | 2915 | 9 | 0 | **9** |
| [`_utc_now`](#-utc-now) | 68 | 9 | 0 | **9** |
| [`trend_matrix`](#trend-matrix) | 5846 | 8 | 3 | **9** |
| [`_flow_imbalance`](#-flow-imbalance) | 2416 | 8 | 0 | **8** |
| [`_flow_rate`](#-flow-rate) | 2424 | 8 | 0 | **8** |
| [`futures_flow_windows`](#futures-flow-windows) | 2619 | 8 | 0 | **8** |
| [`structure_detail`](#structure-detail) | 2283 | 7 | 3 | **8** |
| [`_dsr`](#-dsr) | 2275 | 7 | 0 | **7** |
| [`_pct_rank`](#-pct-rank) | 1742 | 7 | 0 | **7** |
| [`delta_matrix`](#delta-matrix) | 4277 | 7 | 0 | **7** |
| [`_profile`](#-profile) | 3502 | 6 | 0 | **6** |
| [`cross_asset`](#cross-asset) | 3304 | 5 | 3 | **6** |
| [`macro_context`](#macro-context) | 1820 | 5 | 3 | **6** |
| [`passive_flow`](#passive-flow) | 5728 | 5 | 3 | **6** |
| [`price_barriers`](#price-barriers) | 1235 | 6 | 0 | **6** |
| [`volume_profile`](#volume-profile) | 3539 | 6 | 0 | **6** |
| [`_beta`](#-beta) | 3269 | 5 | 0 | **5** |
| [`_binned`](#-binned) | 3283 | 5 | 0 | **5** |
| [`_classify_passive`](#-classify-passive) | 5695 | 5 | 0 | **5** |
| [`_conditional_outcome`](#-conditional-outcome) | 1780 | 5 | 0 | **5** |
| [`_forward_returns`](#-forward-returns) | 1770 | 5 | 0 | **5** |
| [`_pearson`](#-pearson) | 3256 | 5 | 0 | **5** |
| [`_regime`](#-regime) | 1751 | 5 | 0 | **5** |
| [`_returns`](#-returns) | 3248 | 5 | 0 | **5** |
| [`compute_swing_score`](#compute-swing-score) | 6001 | 4 | 3 | **5** |
| [`data_quality`](#data-quality) | 3973 | 4 | 0 | **4** |
| [`market_impact`](#market-impact) | 5420 | 4 | 0 | **4** |
| [`market_memory`](#market-memory) | 1660 | 4 | 0 | **4** |
| [`_banda`](#-banda) | 4963 | 3 | 0 | **3** |
| [`_bps`](#-bps) | 4956 | 3 | 0 | **3** |
| [`_buckets_observados`](#-buckets-observados) | 2978 | 3 | 0 | **3** |
| [`_closes_1min`](#-closes-1min) | 2905 | 3 | 0 | **3** |
| [`_cvd_fut_window`](#-cvd-fut-window) | 1006 | 3 | 0 | **3** |
| [`_cvd_src`](#-cvd-src) | 2640 | 3 | 0 | **3** |
| [`_feed_status`](#-feed-status) | 3850 | 3 | 0 | **3** |
| [`_flow_bias`](#-flow-bias) | 4485 | 3 | 0 | **3** |
| [`_intraday_divergences`](#-intraday-divergences) | 1958 | 3 | 0 | **3** |
| [`_liquidation_feed_quality_status`](#-liquidation-feed-quality-status) | 3815 | 3 | 0 | **3** |
| [`_oi_coverage`](#-oi-coverage) | 2990 | 3 | 0 | **3** |
| [`_oi_quadrant`](#-oi-quadrant) | 2948 | 3 | 0 | **3** |
| [`_pivot_structure`](#-pivot-structure) | 936 | 3 | 0 | **3** |
| [`_realized_vol`](#-realized-vol) | 2934 | 3 | 0 | **3** |
| [`_return_stdev_pct`](#-return-stdev-pct) | 1945 | 3 | 0 | **3** |
| [`_sign_vote`](#-sign-vote) | 954 | 3 | 0 | **3** |
| [`_slope_pct`](#-slope-pct) | 1913 | 3 | 0 | **3** |
| [`_structure_layer`](#-structure-layer) | 982 | 3 | 0 | **3** |
| [`context_metadata`](#context-metadata) | 3599 | 3 | 0 | **3** |
| [`cvd_matrix`](#cvd-matrix) | 2699 | 3 | 0 | **3** |
| [`divergence_scan`](#divergence-scan) | 2073 | 3 | 0 | **3** |
| [`execution_assessment`](#execution-assessment) | 4972 | 3 | 0 | **3** |
| [`feed_quality`](#feed-quality) | 3690 | 3 | 0 | **3** |
| [`feed_quality_view`](#feed-quality-view) | 5183 | 3 | 0 | **3** |
| [`funding_context`](#funding-context) | 3347 | 3 | 0 | **3** |
| [`liquidation_map`](#liquidation-map) | 3420 | 3 | 0 | **3** |
| [`market_structure`](#market-structure) | 1026 | 3 | 0 | **3** |
| [`max_internal_gap`](#max-internal-gap) | 4117 | 3 | 0 | **3** |
| [`metric_quality`](#metric-quality) | 3879 | 3 | 0 | **3** |
| [`oi_context`](#oi-context) | 3021 | 3 | 0 | **3** |
| [`positioning_context`](#positioning-context) | 5525 | 3 | 0 | **3** |
| [`profile_view`](#profile-view) | 4498 | 3 | 0 | **3** |
| [`reference_levels`](#reference-levels) | 3191 | 3 | 0 | **3** |
| [`scalp_absorption`](#scalp-absorption) | 5226 | 3 | 0 | **3** |
| [`scalp_basis`](#scalp-basis) | 5382 | 3 | 0 | **3** |
| [`scalp_liquidations`](#scalp-liquidations) | 5321 | 3 | 0 | **3** |
| [`volatility_context`](#volatility-context) | 3141 | 3 | 0 | **3** |
| [`wyckoff_context`](#wyckoff-context) | 1606 | 3 | 0 | **3** |
| [`horizon_structure`](#horizon-structure) | 1679 | 2 | 0 | **2** |
| [`hypothesis_evidence`](#hypothesis-evidence) | 4690 | 2 | 0 | **2** |
| [`liquidation_burst`](#liquidation-burst) | 1696 | 2 | 0 | **2** |
| [`setup_confirmation_bundle`](#setup-confirmation-bundle) | 2330 | 2 | 0 | **2** |
| [`execution_cost`](#execution-cost) | 5100 | 1 | 0 | **1** |
| [`level_breakout`](#level-breakout) | 1632 | 1 | 0 | **1** |
| [`range_validate`](#range-validate) | 1507 | 1 | 0 | **1** |
| [`spot_perp_flow`](#spot-perp-flow) | 5604 | 1 | 0 | **1** |
| [`walk_book`](#walk-book) | 4878 | 1 | 0 | **1** |
| [`zone_analysis`](#zone-analysis) | 1364 | 1 | 0 | **1** |

## swing_score

`app/scalp_logic.py:6152` · clave completa `app.scalp_logic.swing_score`

**Radio total: 51 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 51 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_session_agg` — la escribe `app.daily_agg.apply_retention`
- `daily_verdict` — la escribe `app.daily_agg.apply_retention`, `app.daily_agg.persist_verdicts`
- `daily_verdict_outcome` — la escribe `app.daily_agg.materialize_daily_verdict_outcomes`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`
- `funding_rate` — la escribe `app.daily_agg.apply_retention`
- `liquidations` — la escribe `app.daily_agg.apply_retention`
- `long_short_ratio` — la escribe `app.daily_agg.apply_retention`
- `metrics_snapshot` — la escribe `app.daily_agg.apply_retention`
- `ohlcv` — la escribe `app.daily_agg.apply_retention`, `app.ingest.rollup_ohlcv_5m`, `app.ingest.upsert_ohlcv`
- `oi_bybit` — la escribe `app.daily_agg.apply_retention`
- `open_interest` — la escribe `app.daily_agg.apply_retention`
- `open_interest_daily` — la escribe `app.daily_agg.rollup_open_interest_daily`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`
- `predicted_funding_rate` — la escribe `app.daily_agg.apply_retention`
- `spot_trades_agg` — la escribe `app.daily_agg.apply_retention`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/funding-context`](../rutas/api-funding-context.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/market-memory`](../rutas/api-market-memory.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)
- [`/metrics`](../rutas/metrics.md)

**49 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/funding-context`](../rutas/api-funding-context.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/market-memory`](../rutas/api-market-memory.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## as_float

`app/scalp_logic.py:920` · clave completa `app.scalp_logic.as_float`

**Radio total: 44 rutas** de 68.

### Por llamada — 37 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/funding-context`](../rutas/api-funding-context.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 106.</sub>

## resolve_matrix_as_of

`app/scalp_logic.py:2404` · clave completa `app.scalp_logic.resolve_matrix_as_of`

**Radio total: 32 rutas** de 68.

### Por llamada — 24 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla — 10 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 51.</sub>

## _explicit_as_of

`app/scalp_logic.py:2398` · clave completa `app.scalp_logic._explicit_as_of`

**Radio total: 25 rutas** de 68.

### Por llamada — 25 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/baselines`](../rutas/api-baselines.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 31.</sub>

## compute_scalp_summary

`app/scalp_logic.py:628` · clave completa `app.scalp_logic.compute_scalp_summary`

**Radio total: 24 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 24 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**15 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 15.</sub>

## scalp_context

`app/scalp_logic.py:325` · clave completa `app.scalp_logic.scalp_context`

**Radio total: 24 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 24 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**15 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 13.</sub>

## load_baselines

`app/scalp_logic.py:158` · clave completa `app.scalp_logic.load_baselines`

**Radio total: 21 rutas** de 68.

### Por llamada — 14 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/baselines`](../rutas/api-baselines.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 18.</sub>

## baseline_band

`app/scalp_logic.py:134` · clave completa `app.scalp_logic.baseline_band`

**Radio total: 20 rutas** de 68.

### Por llamada — 13 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 18.</sub>

## basis_quality

`app/scalp_logic.py:231` · clave completa `app.scalp_logic.basis_quality`

**Radio total: 17 rutas** de 68.

### Por llamada — 10 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 13.</sub>

## classify_absorption

`app/scalp_logic.py:193` · clave completa `app.scalp_logic.classify_absorption`

**Radio total: 17 rutas** de 68.

### Por llamada — 10 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 13.</sub>

## _closed_5m_oi_bounds

`app/scalp_logic.py:94` · clave completa `app.scalp_logic._closed_5m_oi_bounds`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 10.</sub>

## _closed_window_move_pct

`app/scalp_logic.py:590` · clave completa `app.scalp_logic._closed_window_move_pct`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _first_present

`app/scalp_logic.py:502` · clave completa `app.scalp_logic._first_present`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _liquidation_window_measured

`app/scalp_logic.py:514` · clave completa `app.scalp_logic._liquidation_window_measured`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _measured_event_sum

`app/scalp_logic.py:558` · clave completa `app.scalp_logic._measured_event_sum`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## scalp_bias_label

`app/scalp_logic.py:292` · clave completa `app.scalp_logic.scalp_bias_label`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## score_component

`app/scalp_logic.py:317` · clave completa `app.scalp_logic.score_component`

**Radio total: 16 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 9 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _resample_highs_lows

`app/scalp_logic.py:1197` · clave completa `app.scalp_logic._resample_highs_lows`

**Radio total: 14 rutas** de 68.

### Por llamada — 14 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 20.</sub>

## _flow_windows

`app/scalp_logic.py:2431` · clave completa `app.scalp_logic._flow_windows`

**Radio total: 13 rutas** de 68.

### Por llamada — 13 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## spot_flow_windows

`app/scalp_logic.py:2609` · clave completa `app.scalp_logic.spot_flow_windows`

**Radio total: 13 rutas** de 68.

### Por llamada — 13 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 16.</sub>

## _gap_and_baseline

`app/scalp_logic.py:4071` · clave completa `app.scalp_logic._gap_and_baseline`

**Radio total: 12 rutas** de 68.

### Por llamada — 12 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 12.</sub>

## _gap_threshold_seconds

`app/scalp_logic.py:4041` · clave completa `app.scalp_logic._gap_threshold_seconds`

**Radio total: 12 rutas** de 68.

### Por llamada — 12 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 14.</sub>

## _gap_too_large

`app/scalp_logic.py:4053` · clave completa `app.scalp_logic._gap_too_large`

**Radio total: 12 rutas** de 68.

### Por llamada — 12 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 13.</sub>

## _oi_change_pct

`app/scalp_logic.py:4245` · clave completa `app.scalp_logic._oi_change_pct`

**Radio total: 11 rutas** de 68.

### Por llamada — 11 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 12.</sub>

## _realtime_flow

`app/scalp_logic.py:4161` · clave completa `app.scalp_logic._realtime_flow`

**Radio total: 11 rutas** de 68.

### Por llamada — 11 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 12.</sub>

## _complete_tail_values

`app/scalp_logic.py:960` · clave completa `app.scalp_logic._complete_tail_values`

**Radio total: 10 rutas** de 68.

### Por llamada — 10 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _contiguous_measured_suffix

`app/scalp_logic.py:970` · clave completa `app.scalp_logic._contiguous_measured_suffix`

**Radio total: 10 rutas** de 68.

### Por llamada — 10 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 12.</sub>

## flow_confirmation

`app/scalp_logic.py:4419` · clave completa `app.scalp_logic.flow_confirmation`

**Radio total: 10 rutas** de 68.

### Por llamada — 10 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 13.</sub>

## _as_utc_datetime

`app/scalp_logic.py:543` · clave completa `app.scalp_logic._as_utc_datetime`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _atr

`app/scalp_logic.py:2926` · clave completa `app.scalp_logic._atr`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _coverage_status

`app/scalp_logic.py:566` · clave completa `app.scalp_logic._coverage_status`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _structure_from_swings

`app/scalp_logic.py:2226` · clave completa `app.scalp_logic._structure_from_swings`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 10.</sub>

## _swings

`app/scalp_logic.py:2212` · clave completa `app.scalp_logic._swings`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 6.</sub>

## _tr_series

`app/scalp_logic.py:2915` · clave completa `app.scalp_logic._tr_series`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## _utc_now

`app/scalp_logic.py:68` · clave completa `app.scalp_logic._utc_now`

**Radio total: 9 rutas** de 68.

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## trend_matrix

`app/scalp_logic.py:5846` · clave completa `app.scalp_logic.trend_matrix`

**Radio total: 9 rutas** de 68.

### Por llamada — 8 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _flow_imbalance

`app/scalp_logic.py:2416` · clave completa `app.scalp_logic._flow_imbalance`

**Radio total: 8 rutas** de 68.

### Por llamada — 8 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 9.</sub>

## _flow_rate

`app/scalp_logic.py:2424` · clave completa `app.scalp_logic._flow_rate`

**Radio total: 8 rutas** de 68.

### Por llamada — 8 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 9.</sub>

## futures_flow_windows

`app/scalp_logic.py:2619` · clave completa `app.scalp_logic.futures_flow_windows`

**Radio total: 8 rutas** de 68.

### Por llamada — 8 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 9.</sub>

## structure_detail

`app/scalp_logic.py:2283` · clave completa `app.scalp_logic.structure_detail`

**Radio total: 8 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 11.</sub>

## _dsr

`app/scalp_logic.py:2275` · clave completa `app.scalp_logic._dsr`

**Radio total: 7 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## _pct_rank

`app/scalp_logic.py:1742` · clave completa `app.scalp_logic._pct_rank`

**Radio total: 7 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 9.</sub>

## delta_matrix

`app/scalp_logic.py:4277` · clave completa `app.scalp_logic.delta_matrix`

**Radio total: 7 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 9.</sub>

## _profile

`app/scalp_logic.py:3502` · clave completa `app.scalp_logic._profile`

**Radio total: 6 rutas** de 68.

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## cross_asset

`app/scalp_logic.py:3304` · clave completa `app.scalp_logic.cross_asset`

**Radio total: 6 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 8.</sub>

## macro_context

`app/scalp_logic.py:1820` · clave completa `app.scalp_logic.macro_context`

**Radio total: 6 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 8.</sub>

## passive_flow

`app/scalp_logic.py:5728` · clave completa `app.scalp_logic.passive_flow`

**Radio total: 6 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 8.</sub>

## price_barriers

`app/scalp_logic.py:1235` · clave completa `app.scalp_logic.price_barriers`

**Radio total: 6 rutas** de 68.

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## volume_profile

`app/scalp_logic.py:3539` · clave completa `app.scalp_logic.volume_profile`

**Radio total: 6 rutas** de 68.

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## _beta

`app/scalp_logic.py:3269` · clave completa `app.scalp_logic._beta`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _binned

`app/scalp_logic.py:3283` · clave completa `app.scalp_logic._binned`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _classify_passive

`app/scalp_logic.py:5695` · clave completa `app.scalp_logic._classify_passive`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _conditional_outcome

`app/scalp_logic.py:1780` · clave completa `app.scalp_logic._conditional_outcome`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _forward_returns

`app/scalp_logic.py:1770` · clave completa `app.scalp_logic._forward_returns`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _pearson

`app/scalp_logic.py:3256` · clave completa `app.scalp_logic._pearson`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _regime

`app/scalp_logic.py:1751` · clave completa `app.scalp_logic._regime`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _returns

`app/scalp_logic.py:3248` · clave completa `app.scalp_logic._returns`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## compute_swing_score

`app/scalp_logic.py:6001` · clave completa `app.scalp_logic.compute_swing_score`

**Radio total: 5 rutas** de 68.

### Por llamada — 4 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 3 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_verdict` — la escribe `app.daily_agg.persist_verdicts`
- `daily_verdict_snapshot` — la escribe `app.daily_agg.persist_verdicts`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

**1 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/verdicts`](../rutas/api-verdicts.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## data_quality

`app/scalp_logic.py:3973` · clave completa `app.scalp_logic.data_quality`

**Radio total: 4 rutas** de 68.

### Por llamada — 4 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 6.</sub>

## market_impact

`app/scalp_logic.py:5420` · clave completa `app.scalp_logic.market_impact`

**Radio total: 4 rutas** de 68.

### Por llamada — 4 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 5.</sub>

## market_memory

`app/scalp_logic.py:1660` · clave completa `app.scalp_logic.market_memory`

**Radio total: 4 rutas** de 68.

### Por llamada — 4 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/market-memory`](../rutas/api-market-memory.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 5.</sub>

## _banda

`app/scalp_logic.py:4963` · clave completa `app.scalp_logic._banda`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _bps

`app/scalp_logic.py:4956` · clave completa `app.scalp_logic._bps`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _buckets_observados

`app/scalp_logic.py:2978` · clave completa `app.scalp_logic._buckets_observados`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _closes_1min

`app/scalp_logic.py:2905` · clave completa `app.scalp_logic._closes_1min`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _cvd_fut_window

`app/scalp_logic.py:1006` · clave completa `app.scalp_logic._cvd_fut_window`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _cvd_src

`app/scalp_logic.py:2640` · clave completa `app.scalp_logic._cvd_src`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _feed_status

`app/scalp_logic.py:3850` · clave completa `app.scalp_logic._feed_status`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _flow_bias

`app/scalp_logic.py:4485` · clave completa `app.scalp_logic._flow_bias`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _intraday_divergences

`app/scalp_logic.py:1958` · clave completa `app.scalp_logic._intraday_divergences`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _liquidation_feed_quality_status

`app/scalp_logic.py:3815` · clave completa `app.scalp_logic._liquidation_feed_quality_status`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _oi_coverage

`app/scalp_logic.py:2990` · clave completa `app.scalp_logic._oi_coverage`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _oi_quadrant

`app/scalp_logic.py:2948` · clave completa `app.scalp_logic._oi_quadrant`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _pivot_structure

`app/scalp_logic.py:936` · clave completa `app.scalp_logic._pivot_structure`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _realized_vol

`app/scalp_logic.py:2934` · clave completa `app.scalp_logic._realized_vol`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _return_stdev_pct

`app/scalp_logic.py:1945` · clave completa `app.scalp_logic._return_stdev_pct`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _sign_vote

`app/scalp_logic.py:954` · clave completa `app.scalp_logic._sign_vote`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _slope_pct

`app/scalp_logic.py:1913` · clave completa `app.scalp_logic._slope_pct`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _structure_layer

`app/scalp_logic.py:982` · clave completa `app.scalp_logic._structure_layer`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## context_metadata

`app/scalp_logic.py:3599` · clave completa `app.scalp_logic.context_metadata`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/context-metadata`](../rutas/api-context-metadata.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## cvd_matrix

`app/scalp_logic.py:2699` · clave completa `app.scalp_logic.cvd_matrix`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## divergence_scan

`app/scalp_logic.py:2073` · clave completa `app.scalp_logic.divergence_scan`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## execution_assessment

`app/scalp_logic.py:4972` · clave completa `app.scalp_logic.execution_assessment`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## feed_quality

`app/scalp_logic.py:3690` · clave completa `app.scalp_logic.feed_quality`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## feed_quality_view

`app/scalp_logic.py:5183` · clave completa `app.scalp_logic.feed_quality_view`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## funding_context

`app/scalp_logic.py:3347` · clave completa `app.scalp_logic.funding_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/funding-context`](../rutas/api-funding-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## liquidation_map

`app/scalp_logic.py:3420` · clave completa `app.scalp_logic.liquidation_map`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## market_structure

`app/scalp_logic.py:1026` · clave completa `app.scalp_logic.market_structure`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## max_internal_gap

`app/scalp_logic.py:4117` · clave completa `app.scalp_logic.max_internal_gap`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## metric_quality

`app/scalp_logic.py:3879` · clave completa `app.scalp_logic.metric_quality`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## oi_context

`app/scalp_logic.py:3021` · clave completa `app.scalp_logic.oi_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## positioning_context

`app/scalp_logic.py:5525` · clave completa `app.scalp_logic.positioning_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/positioning`](../rutas/api-positioning.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## profile_view

`app/scalp_logic.py:4498` · clave completa `app.scalp_logic.profile_view`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/profile`](../rutas/api-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## reference_levels

`app/scalp_logic.py:3191` · clave completa `app.scalp_logic.reference_levels`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## scalp_absorption

`app/scalp_logic.py:5226` · clave completa `app.scalp_logic.scalp_absorption`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## scalp_basis

`app/scalp_logic.py:5382` · clave completa `app.scalp_logic.scalp_basis`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## scalp_liquidations

`app/scalp_logic.py:5321` · clave completa `app.scalp_logic.scalp_liquidations`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## volatility_context

`app/scalp_logic.py:3141` · clave completa `app.scalp_logic.volatility_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## wyckoff_context

`app/scalp_logic.py:1606` · clave completa `app.scalp_logic.wyckoff_context`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## horizon_structure

`app/scalp_logic.py:1679` · clave completa `app.scalp_logic.horizon_structure`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## hypothesis_evidence

`app/scalp_logic.py:4690` · clave completa `app.scalp_logic.hypothesis_evidence`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## liquidation_burst

`app/scalp_logic.py:1696` · clave completa `app.scalp_logic.liquidation_burst`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## setup_confirmation_bundle

`app/scalp_logic.py:2330` · clave completa `app.scalp_logic.setup_confirmation_bundle`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## execution_cost

`app/scalp_logic.py:5100` · clave completa `app.scalp_logic.execution_cost`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## level_breakout

`app/scalp_logic.py:1632` · clave completa `app.scalp_logic.level_breakout`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/level/breakout`](../rutas/api-level-breakout.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## range_validate

`app/scalp_logic.py:1507` · clave completa `app.scalp_logic.range_validate`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/range/validate`](../rutas/api-range-validate.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## spot_perp_flow

`app/scalp_logic.py:5604` · clave completa `app.scalp_logic.spot_perp_flow`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## walk_book

`app/scalp_logic.py:4878` · clave completa `app.scalp_logic.walk_book`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## zone_analysis

`app/scalp_logic.py:1364` · clave completa `app.scalp_logic.zone_analysis`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

