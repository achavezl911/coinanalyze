# Impacto · `app/api.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

83 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`validate_symbol`](#validate-symbol) | 221 | 62 | 0 | **62** |
| [`records`](#records) | 234 | 22 | 7 | **28** |
| [`health`](#health) | 2747 | 1 | 7 | **7** |
| [`historical_interval_value`](#historical-interval-value) | 227 | 7 | 0 | **7** |
| [`lifespan`](#lifespan) | 143 | 0 | 7 | **7** |
| [`mask_gapped_series_rows`](#mask-gapped-series-rows) | 238 | 7 | 0 | **7** |
| [`declared_series_response`](#declared-series-response) | 348 | 6 | 0 | **6** |
| [`_utc_iso`](#-utc-iso) | 2045 | 5 | 0 | **5** |
| [`rechaza_parametros_desconocidos`](#rechaza-parametros-desconocidos) | 2073 | 5 | 0 | **5** |
| [`daily_data`](#daily-data) | 493 | 3 | 0 | **3** |
| [`latest_snapshot`](#latest-snapshot) | 466 | 3 | 0 | **3** |
| [`_session_window`](#-session-window) | 447 | 2 | 0 | **2** |
| [`_parse_heartbeat_detail`](#-parse-heartbeat-detail) | 2651 | 1 | 0 | **1** |
| [`_slippage_para`](#-slippage-para) | 1428 | 1 | 0 | **1** |
| [`ai_context`](#ai-context) | 2590 | 1 | 0 | **1** |
| [`ai_context_bundle`](#ai-context-bundle) | 2607 | 1 | 0 | **1** |
| [`ai_profiles`](#ai-profiles) | 2628 | 1 | 0 | **1** |
| [`context_metadata_endpoint`](#context-metadata-endpoint) | 1724 | 1 | 0 | **1** |
| [`cross_asset_endpoint`](#cross-asset-endpoint) | 1738 | 1 | 0 | **1** |
| [`cvd`](#cvd) | 698 | 1 | 0 | **1** |
| [`cvd_divergence`](#cvd-divergence) | 797 | 1 | 0 | **1** |
| [`cvd_matrix_endpoint`](#cvd-matrix-endpoint) | 1780 | 1 | 0 | **1** |
| [`cvd_spot`](#cvd-spot) | 746 | 1 | 0 | **1** |
| [`daily`](#daily) | 1923 | 1 | 0 | **1** |
| [`dashboard_state`](#dashboard-state) | 2565 | 1 | 0 | **1** |
| [`data_confidence`](#data-confidence) | 2557 | 1 | 0 | **1** |
| [`delta_profile_endpoint`](#delta-profile-endpoint) | 1623 | 1 | 0 | **1** |
| [`desk_state`](#desk-state) | 1216 | 1 | 0 | **1** |
| [`divergences_endpoint`](#divergences-endpoint) | 1812 | 1 | 0 | **1** |
| [`external_macro_endpoint`](#external-macro-endpoint) | 1802 | 1 | 0 | **1** |
| [`flow_spot_vs_perp`](#flow-spot-vs-perp) | 1447 | 1 | 0 | **1** |
| [`funding_context_endpoint`](#funding-context-endpoint) | 1602 | 1 | 0 | **1** |
| [`hypothesis`](#hypothesis) | 1135 | 1 | 0 | **1** |
| [`index`](#index) | 2861 | 1 | 0 | **1** |
| [`level_breakout_endpoint`](#level-breakout-endpoint) | 1702 | 1 | 0 | **1** |
| [`liquidation_levels`](#liquidation-levels) | 2517 | 1 | 0 | **1** |
| [`liquidation_map_endpoint`](#liquidation-map-endpoint) | 1609 | 1 | 0 | **1** |
| [`liquidation_series`](#liquidation-series) | 964 | 1 | 0 | **1** |
| [`macro_context_endpoint`](#macro-context-endpoint) | 1795 | 1 | 0 | **1** |
| [`market_impact_endpoint`](#market-impact-endpoint) | 1119 | 1 | 0 | **1** |
| [`market_memory_endpoint`](#market-memory-endpoint) | 1819 | 1 | 0 | **1** |
| [`metric_baselines`](#metric-baselines) | 1334 | 1 | 0 | **1** |
| [`ohlcv`](#ohlcv) | 634 | 1 | 0 | **1** |
| [`oi`](#oi) | 915 | 1 | 0 | **1** |
| [`oi_context_endpoint`](#oi-context-endpoint) | 1745 | 1 | 0 | **1** |
| [`passive_flow_endpoint`](#passive-flow-endpoint) | 1773 | 1 | 0 | **1** |
| [`positioning`](#positioning) | 1127 | 1 | 0 | **1** |
| [`price_barriers_endpoint`](#price-barriers-endpoint) | 1644 | 1 | 0 | **1** |
| [`prometheus_metrics`](#prometheus-metrics) | 2669 | 1 | 0 | **1** |
| [`quality_feeds`](#quality-feeds) | 1318 | 1 | 0 | **1** |
| [`range_validate_endpoint`](#range-validate-endpoint) | 1668 | 1 | 0 | **1** |
| [`reference_levels_endpoint`](#reference-levels-endpoint) | 1731 | 1 | 0 | **1** |
| [`scalp_absorption`](#scalp-absorption) | 1480 | 1 | 0 | **1** |
| [`scalp_alerts`](#scalp-alerts) | 1496 | 1 | 0 | **1** |
| [`scalp_basis`](#scalp-basis) | 2510 | 1 | 0 | **1** |
| [`scalp_delta_matrix`](#scalp-delta-matrix) | 1092 | 1 | 0 | **1** |
| [`scalp_execution_cost`](#scalp-execution-cost) | 1372 | 1 | 0 | **1** |
| [`scalp_liquidations`](#scalp-liquidations) | 1489 | 1 | 0 | **1** |
| [`scalp_orderbook`](#scalp-orderbook) | 1464 | 1 | 0 | **1** |
| [`scalp_signals`](#scalp-signals) | 2023 | 1 | 0 | **1** |
| [`scalp_summary`](#scalp-summary) | 1084 | 1 | 0 | **1** |
| [`setup`](#setup) | 2008 | 1 | 0 | **1** |
| [`signals_execution`](#signals-execution) | 2261 | 1 | 0 | **1** |
| [`signals_ledger`](#signals-ledger) | 2089 | 1 | 0 | **1** |
| [`signals_outcomes`](#signals-outcomes) | 2175 | 1 | 0 | **1** |
| [`signals_replay`](#signals-replay) | 2347 | 1 | 0 | **1** |
| [`signals_visibility`](#signals-visibility) | 2429 | 1 | 0 | **1** |
| [`snapshot`](#snapshot) | 614 | 1 | 0 | **1** |
| [`statistical_alerts`](#statistical-alerts) | 1560 | 1 | 0 | **1** |
| [`stream`](#stream) | 2852 | 1 | 0 | **1** |
| [`stream_generator`](#stream-generator) | 2804 | 1 | 0 | **1** |
| [`structure`](#structure) | 1916 | 1 | 0 | **1** |
| [`structure_detail_endpoint`](#structure-detail-endpoint) | 1788 | 1 | 0 | **1** |
| [`swing_score_endpoint`](#swing-score-endpoint) | 1759 | 1 | 0 | **1** |
| [`symbols`](#symbols) | 609 | 1 | 0 | **1** |
| [`trading_profile`](#trading-profile) | 1352 | 1 | 0 | **1** |
| [`trend_matrix_endpoint`](#trend-matrix-endpoint) | 1766 | 1 | 0 | **1** |
| [`verdicts`](#verdicts) | 1826 | 1 | 0 | **1** |
| [`volatility_endpoint`](#volatility-endpoint) | 1752 | 1 | 0 | **1** |
| [`volume_profile_endpoint`](#volume-profile-endpoint) | 1616 | 1 | 0 | **1** |
| [`whale_delta`](#whale-delta) | 1014 | 1 | 0 | **1** |
| [`wyckoff_endpoint`](#wyckoff-endpoint) | 1716 | 1 | 0 | **1** |
| [`zone_analysis_endpoint`](#zone-analysis-endpoint) | 1651 | 1 | 0 | **1** |

## validate_symbol

`app/api.py:221` · clave completa `app.api.validate_symbol`

**Radio total: 62 rutas** de 68.

### Por llamada — 62 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/baselines`](../rutas/api-baselines.md)
- [`/api/context-metadata`](../rutas/api-context-metadata.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
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
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
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

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 62.</sub>

## records

`app/api.py:234` · clave completa `app.api.records`

**Radio total: 28 rutas** de 68.

### Por llamada — 22 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla — 7 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**6 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 24.</sub>

## health

`app/api.py:2747` · clave completa `app.api.health`

**Radio total: 7 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/healthz`](../rutas/api-healthz.md)

### Por tabla — 7 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**6 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## historical_interval_value

`app/api.py:227` · clave completa `app.api.historical_interval_value`

**Radio total: 7 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## lifespan

`app/api.py:143` · clave completa `app.api.lifespan`

**Radio total: 7 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 7 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## mask_gapped_series_rows

`app/api.py:238` · clave completa `app.api.mask_gapped_series_rows`

**Radio total: 7 rutas** de 68.

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## declared_series_response

`app/api.py:348` · clave completa `app.api.declared_series_response`

**Radio total: 6 rutas** de 68.

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 6.</sub>

## _utc_iso

`app/api.py:2045` · clave completa `app.api._utc_iso`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 5.</sub>

## rechaza_parametros_desconocidos

`app/api.py:2073` · clave completa `app.api.rechaza_parametros_desconocidos`

**Radio total: 5 rutas** de 68.

### Por llamada — 5 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 5.</sub>

## daily_data

`app/api.py:493` · clave completa `app.api.daily_data`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/setup`](../rutas/api-setup.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## latest_snapshot

`app/api.py:466` · clave completa `app.api.latest_snapshot`

**Radio total: 3 rutas** de 68.

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## _session_window

`app/api.py:447` · clave completa `app.api._session_window`

**Radio total: 2 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## _parse_heartbeat_detail

`app/api.py:2651` · clave completa `app.api._parse_heartbeat_detail`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/metrics`](../rutas/metrics.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## _slippage_para

`app/api.py:1428` · clave completa `app.api._slippage_para`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## ai_context

`app/api.py:2590` · clave completa `app.api.ai_context`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## ai_context_bundle

`app/api.py:2607` · clave completa `app.api.ai_context_bundle`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## ai_profiles

`app/api.py:2628` · clave completa `app.api.ai_profiles`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/profiles`](../rutas/api-ai-profiles.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## context_metadata_endpoint

`app/api.py:1724` · clave completa `app.api.context_metadata_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/context-metadata`](../rutas/api-context-metadata.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## cross_asset_endpoint

`app/api.py:1738` · clave completa `app.api.cross_asset_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cross-asset`](../rutas/api-cross-asset.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## cvd

`app/api.py:698` · clave completa `app.api.cvd`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## cvd_divergence

`app/api.py:797` · clave completa `app.api.cvd_divergence`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## cvd_matrix_endpoint

`app/api.py:1780` · clave completa `app.api.cvd_matrix_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## cvd_spot

`app/api.py:746` · clave completa `app.api.cvd_spot`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## daily

`app/api.py:1923` · clave completa `app.api.daily`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## dashboard_state

`app/api.py:2565` · clave completa `app.api.dashboard_state`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## data_confidence

`app/api.py:2557` · clave completa `app.api.data_confidence`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/data-confidence`](../rutas/api-data-confidence.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## delta_profile_endpoint

`app/api.py:1623` · clave completa `app.api.delta_profile_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/delta-profile`](../rutas/api-delta-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## desk_state

`app/api.py:1216` · clave completa `app.api.desk_state`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## divergences_endpoint

`app/api.py:1812` · clave completa `app.api.divergences_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## external_macro_endpoint

`app/api.py:1802` · clave completa `app.api.external_macro_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## flow_spot_vs_perp

`app/api.py:1447` · clave completa `app.api.flow_spot_vs_perp`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## funding_context_endpoint

`app/api.py:1602` · clave completa `app.api.funding_context_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/funding-context`](../rutas/api-funding-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## hypothesis

`app/api.py:1135` · clave completa `app.api.hypothesis`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## index

`app/api.py:2861` · clave completa `app.api.index`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/`](../rutas/raiz.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## level_breakout_endpoint

`app/api.py:1702` · clave completa `app.api.level_breakout_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/level/breakout`](../rutas/api-level-breakout.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## liquidation_levels

`app/api.py:2517` · clave completa `app.api.liquidation_levels`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## liquidation_map_endpoint

`app/api.py:1609` · clave completa `app.api.liquidation_map_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## liquidation_series

`app/api.py:964` · clave completa `app.api.liquidation_series`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/liquidations`](../rutas/api-liquidations.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## macro_context_endpoint

`app/api.py:1795` · clave completa `app.api.macro_context_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/macro-context`](../rutas/api-macro-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## market_impact_endpoint

`app/api.py:1119` · clave completa `app.api.market_impact_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/market-impact`](../rutas/api-market-impact.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## market_memory_endpoint

`app/api.py:1819` · clave completa `app.api.market_memory_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/market-memory`](../rutas/api-market-memory.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## metric_baselines

`app/api.py:1334` · clave completa `app.api.metric_baselines`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/baselines`](../rutas/api-baselines.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## ohlcv

`app/api.py:634` · clave completa `app.api.ohlcv`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ohlcv`](../rutas/api-ohlcv.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## oi

`app/api.py:915` · clave completa `app.api.oi`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/oi`](../rutas/api-oi.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## oi_context_endpoint

`app/api.py:1745` · clave completa `app.api.oi_context_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## passive_flow_endpoint

`app/api.py:1773` · clave completa `app.api.passive_flow_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/passive-flow`](../rutas/api-passive-flow.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## positioning

`app/api.py:1127` · clave completa `app.api.positioning`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/positioning`](../rutas/api-positioning.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## price_barriers_endpoint

`app/api.py:1644` · clave completa `app.api.price_barriers_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## prometheus_metrics

`app/api.py:2669` · clave completa `app.api.prometheus_metrics`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/metrics`](../rutas/metrics.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## quality_feeds

`app/api.py:1318` · clave completa `app.api.quality_feeds`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## range_validate_endpoint

`app/api.py:1668` · clave completa `app.api.range_validate_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/range/validate`](../rutas/api-range-validate.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## reference_levels_endpoint

`app/api.py:1731` · clave completa `app.api.reference_levels_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/reference-levels`](../rutas/api-reference-levels.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_absorption

`app/api.py:1480` · clave completa `app.api.scalp_absorption`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_alerts

`app/api.py:1496` · clave completa `app.api.scalp_alerts`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_basis

`app/api.py:2510` · clave completa `app.api.scalp_basis`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_delta_matrix

`app/api.py:1092` · clave completa `app.api.scalp_delta_matrix`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_execution_cost

`app/api.py:1372` · clave completa `app.api.scalp_execution_cost`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_liquidations

`app/api.py:1489` · clave completa `app.api.scalp_liquidations`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_orderbook

`app/api.py:1464` · clave completa `app.api.scalp_orderbook`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_signals

`app/api.py:2023` · clave completa `app.api.scalp_signals`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## scalp_summary

`app/api.py:1084` · clave completa `app.api.scalp_summary`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## setup

`app/api.py:2008` · clave completa `app.api.setup`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/setup`](../rutas/api-setup.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## signals_execution

`app/api.py:2261` · clave completa `app.api.signals_execution`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## signals_ledger

`app/api.py:2089` · clave completa `app.api.signals_ledger`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## signals_outcomes

`app/api.py:2175` · clave completa `app.api.signals_outcomes`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## signals_replay

`app/api.py:2347` · clave completa `app.api.signals_replay`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/replay`](../rutas/api-signals-replay.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## signals_visibility

`app/api.py:2429` · clave completa `app.api.signals_visibility`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## snapshot

`app/api.py:614` · clave completa `app.api.snapshot`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/snapshot`](../rutas/api-snapshot.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## statistical_alerts

`app/api.py:1560` · clave completa `app.api.statistical_alerts`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## stream

`app/api.py:2852` · clave completa `app.api.stream`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/stream`](../rutas/api-stream.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## stream_generator

`app/api.py:2804` · clave completa `app.api.stream_generator`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/stream`](../rutas/api-stream.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 1.</sub>

## structure

`app/api.py:1916` · clave completa `app.api.structure`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/structure`](../rutas/api-structure.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## structure_detail_endpoint

`app/api.py:1788` · clave completa `app.api.structure_detail_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/structure-detail`](../rutas/api-structure-detail.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## swing_score_endpoint

`app/api.py:1759` · clave completa `app.api.swing_score_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## symbols

`app/api.py:609` · clave completa `app.api.symbols`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/symbols`](../rutas/api-symbols.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## trading_profile

`app/api.py:1352` · clave completa `app.api.trading_profile`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/profile`](../rutas/api-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## trend_matrix_endpoint

`app/api.py:1766` · clave completa `app.api.trend_matrix_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## verdicts

`app/api.py:1826` · clave completa `app.api.verdicts`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/verdicts`](../rutas/api-verdicts.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## volatility_endpoint

`app/api.py:1752` · clave completa `app.api.volatility_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## volume_profile_endpoint

`app/api.py:1616` · clave completa `app.api.volume_profile_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## whale_delta

`app/api.py:1014` · clave completa `app.api.whale_delta`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## wyckoff_endpoint

`app/api.py:1716` · clave completa `app.api.wyckoff_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/wyckoff`](../rutas/api-wyckoff.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

## zone_analysis_endpoint

`app/api.py:1651` · clave completa `app.api.zone_analysis_endpoint`

**Radio total: 1 rutas** de 68.

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla — 0 rutas · k=2

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 0.</sub>

