# Impacto · `app/api.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

97 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`validate_symbol`](#validate-symbol) | 233 | 66 | **0** | 0 | **66** |
| [`records`](#records) | 246 | 22 | **0** | 8 ↑ | **22** |
| [`_utc_iso`](#-utc-iso) | 2446 | 9 | **0** | 0 | **9** |
| [`rechaza_parametros_desconocidos`](#rechaza-parametros-desconocidos) | 2566 | 9 | **0** | 0 | **9** |
| [`health`](#health) | 3702 | 1 | **0** | 8 ↑ | **1** |
| [`lifespan`](#lifespan) | 155 | 0 | **0** | 8 ↑ | **0** |
| [`historical_interval_value`](#historical-interval-value) | 239 | 7 | **0** | 0 | **7** |
| [`mask_gapped_series_rows`](#mask-gapped-series-rows) | 250 | 7 | **0** | 0 | **7** |
| [`declared_series_response`](#declared-series-response) | 400 | 6 | **0** | 0 | **6** |
| [`minutos_de_las_filas`](#minutos-de-las-filas) | 360 | 6 | **0** | 0 | **6** |
| [`ventana_pedida`](#ventana-pedida) | 1700 | 4 | **0** | 0 | **4** |
| [`daily_data`](#daily-data) | 548 | 3 | **0** | 0 | **3** |
| [`declara_ventana`](#declara-ventana) | 1733 | 3 | **0** | 0 | **3** |
| [`latest_snapshot`](#latest-snapshot) | 521 | 3 | **0** | 0 | **3** |
| [`sella_respuesta`](#sella-respuesta) | 1978 | 3 | **0** | 0 | **3** |
| [`_session_window`](#-session-window) | 502 | 2 | **0** | 0 | **2** |
| [`scalp_persistence`](#scalp-persistence) | 3174 | 2 | **0** | 0 | **2** |
| [`_parse_heartbeat_detail`](#-parse-heartbeat-detail) | 3606 | 1 | **0** | 0 | **1** |
| [`_slippage_para`](#-slippage-para) | 1682 | 1 | **0** | 0 | **1** |
| [`ai_context`](#ai-context) | 3545 | 1 | **0** | 0 | **1** |
| [`ai_context_bundle`](#ai-context-bundle) | 3562 | 1 | **0** | 0 | **1** |
| [`ai_profiles`](#ai-profiles) | 3583 | 1 | **0** | 0 | **1** |
| [`carry_matriz`](#carry-matriz) | 1278 | 1 | **0** | 0 | **1** |
| [`context_metadata_endpoint`](#context-metadata-endpoint) | 2079 | 1 | **0** | 0 | **1** |
| [`cross_asset_endpoint`](#cross-asset-endpoint) | 2120 | 1 | **0** | 0 | **1** |
| [`cvd`](#cvd) | 753 | 1 | **0** | 0 | **1** |
| [`cvd_divergence`](#cvd-divergence) | 915 | 1 | **0** | 0 | **1** |
| [`cvd_matrix_endpoint`](#cvd-matrix-endpoint) | 2162 | 1 | **0** | 0 | **1** |
| [`cvd_spot`](#cvd-spot) | 814 | 1 | **0** | 0 | **1** |
| [`daily`](#daily) | 2305 | 1 | **0** | 0 | **1** |
| [`dashboard_state`](#dashboard-state) | 3514 | 1 | **0** | 0 | **1** |
| [`data_confidence`](#data-confidence) | 3121 | 1 | **0** | 0 | **1** |
| [`declarar_tramo_no_medible`](#declarar-tramo-no-medible) | 1131 | 1 | **0** | 0 | **1** |
| [`delta_profile_endpoint`](#delta-profile-endpoint) | 1943 | 1 | **0** | 0 | **1** |
| [`desk_state`](#desk-state) | 1461 | 1 | **0** | 0 | **1** |
| [`divergences_endpoint`](#divergences-endpoint) | 2194 | 1 | **0** | 0 | **1** |
| [`entradas`](#entradas) | 1297 | 1 | **0** | 0 | **1** |
| [`external_macro_endpoint`](#external-macro-endpoint) | 2184 | 1 | **0** | 0 | **1** |
| [`flow_spot_vs_perp`](#flow-spot-vs-perp) | 1758 | 1 | **0** | 0 | **1** |
| [`funding_context_endpoint`](#funding-context-endpoint) | 1922 | 1 | **0** | 0 | **1** |
| [`hypothesis`](#hypothesis) | 1380 | 1 | **0** | 0 | **1** |
| [`index`](#index) | 3888 | 1 | **0** | 0 | **1** |
| [`level_breakout_endpoint`](#level-breakout-endpoint) | 2055 | 1 | **0** | 0 | **1** |
| [`liquidation_levels`](#liquidation-levels) | 3061 | 1 | **0** | 0 | **1** |
| [`liquidation_map_endpoint`](#liquidation-map-endpoint) | 1929 | 1 | **0** | 0 | **1** |
| [`liquidation_series`](#liquidation-series) | 1082 | 1 | **0** | 0 | **1** |
| [`macro_context_endpoint`](#macro-context-endpoint) | 2177 | 1 | **0** | 0 | **1** |
| [`market_impact_endpoint`](#market-impact-endpoint) | 1364 | 1 | **0** | 0 | **1** |
| [`market_memory_endpoint`](#market-memory-endpoint) | 2201 | 1 | **0** | 0 | **1** |
| [`mesa`](#mesa) | 3872 | 1 | **0** | 0 | **1** |
| [`mesa_decide`](#mesa-decide) | 3816 | 1 | **0** | 0 | **1** |
| [`mesa_entradas`](#mesa-entradas) | 3855 | 1 | **0** | 0 | **1** |
| [`metric_baselines`](#metric-baselines) | 1588 | 1 | **0** | 0 | **1** |
| [`ohlcv`](#ohlcv) | 689 | 1 | **0** | 0 | **1** |
| [`oi`](#oi) | 1033 | 1 | **0** | 0 | **1** |
| [`oi_context_endpoint`](#oi-context-endpoint) | 2127 | 1 | **0** | 0 | **1** |
| [`panel`](#panel) | 3882 | 1 | **0** | 0 | **1** |
| [`passive_flow_endpoint`](#passive-flow-endpoint) | 2155 | 1 | **0** | 0 | **1** |
| [`positioning`](#positioning) | 1372 | 1 | **0** | 0 | **1** |
| [`price_barriers_endpoint`](#price-barriers-endpoint) | 1972 | 1 | **0** | 0 | **1** |
| [`prometheus_metrics`](#prometheus-metrics) | 3624 | 1 | **0** | 0 | **1** |
| [`quality_feeds`](#quality-feeds) | 1572 | 1 | **0** | 0 | **1** |
| [`range_validate_endpoint`](#range-validate-endpoint) | 2021 | 1 | **0** | 0 | **1** |
| [`rango_estructura`](#rango-estructura) | 2086 | 1 | **0** | 0 | **1** |
| [`reference_levels_endpoint`](#reference-levels-endpoint) | 2113 | 1 | **0** | 0 | **1** |
| [`scalp_absorption`](#scalp-absorption) | 1800 | 1 | **0** | 0 | **1** |
| [`scalp_alerts`](#scalp-alerts) | 1816 | 1 | **0** | 0 | **1** |
| [`scalp_basis`](#scalp-basis) | 3054 | 1 | **0** | 0 | **1** |
| [`scalp_delta_matrix`](#scalp-delta-matrix) | 1335 | 1 | **0** | 0 | **1** |
| [`scalp_execution_cost`](#scalp-execution-cost) | 1626 | 1 | **0** | 0 | **1** |
| [`scalp_liquidations`](#scalp-liquidations) | 1809 | 1 | **0** | 0 | **1** |
| [`scalp_orderbook`](#scalp-orderbook) | 1784 | 1 | **0** | 0 | **1** |
| [`scalp_signals`](#scalp-signals) | 2405 | 1 | **0** | 0 | **1** |
| [`scalp_summary`](#scalp-summary) | 1327 | 1 | **0** | 0 | **1** |
| [`setup`](#setup) | 2390 | 1 | **0** | 0 | **1** |
| [`signal_base_rate`](#signal-base-rate) | 3389 | 1 | **0** | 0 | **1** |
| [`signals_execution`](#signals-execution) | 2799 | 1 | **0** | 0 | **1** |
| [`signals_ledger`](#signals-ledger) | 2582 | 1 | **0** | 0 | **1** |
| [`signals_outcomes`](#signals-outcomes) | 2713 | 1 | **0** | 0 | **1** |
| [`signals_replay`](#signals-replay) | 2887 | 1 | **0** | 0 | **1** |
| [`signals_visibility`](#signals-visibility) | 2971 | 1 | **0** | 0 | **1** |
| [`snapshot`](#snapshot) | 669 | 1 | **0** | 0 | **1** |
| [`statistical_alerts`](#statistical-alerts) | 1880 | 1 | **0** | 0 | **1** |
| [`stream`](#stream) | 3807 | 1 | **0** | 0 | **1** |
| [`stream_generator`](#stream-generator) | 3759 | 1 | **0** | 0 | **1** |
| [`structure`](#structure) | 2298 | 1 | **0** | 0 | **1** |
| [`structure_detail_endpoint`](#structure-detail-endpoint) | 2170 | 1 | **0** | 0 | **1** |
| [`swing_score_endpoint`](#swing-score-endpoint) | 2141 | 1 | **0** | 0 | **1** |
| [`symbols`](#symbols) | 664 | 1 | **0** | 0 | **1** |
| [`trading_profile`](#trading-profile) | 1606 | 1 | **0** | 0 | **1** |
| [`trend_matrix_endpoint`](#trend-matrix-endpoint) | 2148 | 1 | **0** | 0 | **1** |
| [`verdicts`](#verdicts) | 2208 | 1 | **0** | 0 | **1** |
| [`volatility_endpoint`](#volatility-endpoint) | 2134 | 1 | **0** | 0 | **1** |
| [`volume_profile_endpoint`](#volume-profile-endpoint) | 1936 | 1 | **0** | 0 | **1** |
| [`whale_delta`](#whale-delta) | 1184 | 1 | **0** | 0 | **1** |
| [`wyckoff_endpoint`](#wyckoff-endpoint) | 2071 | 1 | **0** | 0 | **1** |
| [`zone_analysis_endpoint`](#zone-analysis-endpoint) | 1995 | 1 | **0** | 0 | **1** |

## validate_symbol

`app/api.py:233` · clave completa `app.api.validate_symbol`

**Radio exacto: 66 rutas** de 75 · **cota superior: 66** (igual al exacto)

### Por llamada — 66 rutas

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
- [`/api/entradas`](../rutas/api-entradas.md)
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
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/rango/estructura`](../rutas/api-rango-estructura.md)
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

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 66 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## records

`app/api.py:246` · clave completa `app.api.records`

**Radio exacto: 22 rutas** de 75 · **cota superior: 29** (mas ancha)

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

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 8 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (8 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 24 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _utc_iso

`app/api.py:2446` · clave completa `app.api._utc_iso`

**Radio exacto: 9 rutas** de 75 · **cota superior: 9** (igual al exacto)

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 10 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## rechaza_parametros_desconocidos

`app/api.py:2566` · clave completa `app.api.rechaza_parametros_desconocidos`

**Radio exacto: 9 rutas** de 75 · **cota superior: 9** (igual al exacto)

### Por llamada — 9 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/carry/matriz`](../rutas/api-carry-matriz.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/rango/estructura`](../rutas/api-rango-estructura.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 9 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## health

`app/api.py:3702` · clave completa `app.api.health`

**Radio exacto: 1 rutas** de 75 · **cota superior: 8** (mas ancha)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/healthz`](../rutas/api-healthz.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 8 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (8 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**7 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## lifespan

`app/api.py:155` · clave completa `app.api.lifespan`

**Radio exacto: 0 rutas** de 75 · **cota superior: 8** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 8 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (8 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## historical_interval_value

`app/api.py:239` · clave completa `app.api.historical_interval_value`

**Radio exacto: 7 rutas** de 75 · **cota superior: 7** (igual al exacto)

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 7 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mask_gapped_series_rows

`app/api.py:250` · clave completa `app.api.mask_gapped_series_rows`

**Radio exacto: 7 rutas** de 75 · **cota superior: 7** (igual al exacto)

### Por llamada — 7 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 7 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## declared_series_response

`app/api.py:400` · clave completa `app.api.declared_series_response`

**Radio exacto: 6 rutas** de 75 · **cota superior: 6** (igual al exacto)

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 6 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## minutos_de_las_filas

`app/api.py:360` · clave completa `app.api.minutos_de_las_filas`

**Radio exacto: 6 rutas** de 75 · **cota superior: 6** (igual al exacto)

### Por llamada — 6 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 7 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ventana_pedida

`app/api.py:1700` · clave completa `app.api.ventana_pedida`

**Radio exacto: 4 rutas** de 75 · **cota superior: 4** (igual al exacto)

### Por llamada — 4 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/rango/estructura`](../rutas/api-rango-estructura.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## daily_data

`app/api.py:548` · clave completa `app.api.daily_data`

**Radio exacto: 3 rutas** de 75 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/setup`](../rutas/api-setup.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## declara_ventana

`app/api.py:1733` · clave completa `app.api.declara_ventana`

**Radio exacto: 3 rutas** de 75 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## latest_snapshot

`app/api.py:521` · clave completa `app.api.latest_snapshot`

**Radio exacto: 3 rutas** de 75 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## sella_respuesta

`app/api.py:1978` · clave completa `app.api.sella_respuesta`

**Radio exacto: 3 rutas** de 75 · **cota superior: 3** (igual al exacto)

### Por llamada — 3 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _session_window

`app/api.py:502` · clave completa `app.api._session_window`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_persistence

`app/api.py:3174` · clave completa `app.api.scalp_persistence`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _parse_heartbeat_detail

`app/api.py:3606` · clave completa `app.api._parse_heartbeat_detail`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/metrics`](../rutas/metrics.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _slippage_para

`app/api.py:1682` · clave completa `app.api._slippage_para`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ai_context

`app/api.py:3545` · clave completa `app.api.ai_context`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ai_context_bundle

`app/api.py:3562` · clave completa `app.api.ai_context_bundle`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ai_profiles

`app/api.py:3583` · clave completa `app.api.ai_profiles`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/profiles`](../rutas/api-ai-profiles.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## carry_matriz

`app/api.py:1278` · clave completa `app.api.carry_matriz`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/carry/matriz`](../rutas/api-carry-matriz.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## context_metadata_endpoint

`app/api.py:2079` · clave completa `app.api.context_metadata_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/context-metadata`](../rutas/api-context-metadata.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cross_asset_endpoint

`app/api.py:2120` · clave completa `app.api.cross_asset_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cross-asset`](../rutas/api-cross-asset.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cvd

`app/api.py:753` · clave completa `app.api.cvd`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd`](../rutas/api-cvd.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cvd_divergence

`app/api.py:915` · clave completa `app.api.cvd_divergence`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cvd_matrix_endpoint

`app/api.py:2162` · clave completa `app.api.cvd_matrix_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cvd_spot

`app/api.py:814` · clave completa `app.api.cvd_spot`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## daily

`app/api.py:2305` · clave completa `app.api.daily`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## dashboard_state

`app/api.py:3514` · clave completa `app.api.dashboard_state`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## data_confidence

`app/api.py:3121` · clave completa `app.api.data_confidence`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/data-confidence`](../rutas/api-data-confidence.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## declarar_tramo_no_medible

`app/api.py:1131` · clave completa `app.api.declarar_tramo_no_medible`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## delta_profile_endpoint

`app/api.py:1943` · clave completa `app.api.delta_profile_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/delta-profile`](../rutas/api-delta-profile.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## desk_state

`app/api.py:1461` · clave completa `app.api.desk_state`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/desk/state`](../rutas/api-desk-state.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## divergences_endpoint

`app/api.py:2194` · clave completa `app.api.divergences_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/divergences`](../rutas/api-divergences.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## entradas

`app/api.py:1297` · clave completa `app.api.entradas`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## external_macro_endpoint

`app/api.py:2184` · clave completa `app.api.external_macro_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/external-macro`](../rutas/api-external-macro.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flow_spot_vs_perp

`app/api.py:1758` · clave completa `app.api.flow_spot_vs_perp`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## funding_context_endpoint

`app/api.py:1922` · clave completa `app.api.funding_context_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/funding-context`](../rutas/api-funding-context.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## hypothesis

`app/api.py:1380` · clave completa `app.api.hypothesis`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/hypothesis`](../rutas/api-hypothesis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## index

`app/api.py:3888` · clave completa `app.api.index`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/`](../rutas/raiz.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## level_breakout_endpoint

`app/api.py:2055` · clave completa `app.api.level_breakout_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/level/breakout`](../rutas/api-level-breakout.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## liquidation_levels

`app/api.py:3061` · clave completa `app.api.liquidation_levels`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## liquidation_map_endpoint

`app/api.py:1929` · clave completa `app.api.liquidation_map_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## liquidation_series

`app/api.py:1082` · clave completa `app.api.liquidation_series`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/liquidations`](../rutas/api-liquidations.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## macro_context_endpoint

`app/api.py:2177` · clave completa `app.api.macro_context_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/macro-context`](../rutas/api-macro-context.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## market_impact_endpoint

`app/api.py:1364` · clave completa `app.api.market_impact_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/market-impact`](../rutas/api-market-impact.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## market_memory_endpoint

`app/api.py:2201` · clave completa `app.api.market_memory_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/market-memory`](../rutas/api-market-memory.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mesa

`app/api.py:3872` · clave completa `app.api.mesa`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/mesa`](../rutas/mesa.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mesa_decide

`app/api.py:3816` · clave completa `app.api.mesa_decide`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mesa_entradas

`app/api.py:3855` · clave completa `app.api.mesa_entradas`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## metric_baselines

`app/api.py:1588` · clave completa `app.api.metric_baselines`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/baselines`](../rutas/api-baselines.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ohlcv

`app/api.py:689` · clave completa `app.api.ohlcv`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ohlcv`](../rutas/api-ohlcv.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## oi

`app/api.py:1033` · clave completa `app.api.oi`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/oi`](../rutas/api-oi.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## oi_context_endpoint

`app/api.py:2127` · clave completa `app.api.oi_context_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/oi-context`](../rutas/api-oi-context.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## panel

`app/api.py:3882` · clave completa `app.api.panel`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/panel`](../rutas/panel.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## passive_flow_endpoint

`app/api.py:2155` · clave completa `app.api.passive_flow_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/passive-flow`](../rutas/api-passive-flow.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## positioning

`app/api.py:1372` · clave completa `app.api.positioning`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/positioning`](../rutas/api-positioning.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## price_barriers_endpoint

`app/api.py:1972` · clave completa `app.api.price_barriers_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## prometheus_metrics

`app/api.py:3624` · clave completa `app.api.prometheus_metrics`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/metrics`](../rutas/metrics.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## quality_feeds

`app/api.py:1572` · clave completa `app.api.quality_feeds`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## range_validate_endpoint

`app/api.py:2021` · clave completa `app.api.range_validate_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/range/validate`](../rutas/api-range-validate.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## rango_estructura

`app/api.py:2086` · clave completa `app.api.rango_estructura`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/rango/estructura`](../rutas/api-rango-estructura.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## reference_levels_endpoint

`app/api.py:2113` · clave completa `app.api.reference_levels_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/reference-levels`](../rutas/api-reference-levels.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_absorption

`app/api.py:1800` · clave completa `app.api.scalp_absorption`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_alerts

`app/api.py:1816` · clave completa `app.api.scalp_alerts`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_basis

`app/api.py:3054` · clave completa `app.api.scalp_basis`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_delta_matrix

`app/api.py:1335` · clave completa `app.api.scalp_delta_matrix`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_execution_cost

`app/api.py:1626` · clave completa `app.api.scalp_execution_cost`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_liquidations

`app/api.py:1809` · clave completa `app.api.scalp_liquidations`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_orderbook

`app/api.py:1784` · clave completa `app.api.scalp_orderbook`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_signals

`app/api.py:2405` · clave completa `app.api.scalp_signals`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## scalp_summary

`app/api.py:1327` · clave completa `app.api.scalp_summary`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## setup

`app/api.py:2390` · clave completa `app.api.setup`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/setup`](../rutas/api-setup.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signal_base_rate

`app/api.py:3389` · clave completa `app.api.signal_base_rate`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signals_execution

`app/api.py:2799` · clave completa `app.api.signals_execution`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/execution`](../rutas/api-signals-execution.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signals_ledger

`app/api.py:2582` · clave completa `app.api.signals_ledger`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signals_outcomes

`app/api.py:2713` · clave completa `app.api.signals_outcomes`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signals_replay

`app/api.py:2887` · clave completa `app.api.signals_replay`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/replay`](../rutas/api-signals-replay.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## signals_visibility

`app/api.py:2971` · clave completa `app.api.signals_visibility`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## snapshot

`app/api.py:669` · clave completa `app.api.snapshot`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/snapshot`](../rutas/api-snapshot.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## statistical_alerts

`app/api.py:1880` · clave completa `app.api.statistical_alerts`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## stream

`app/api.py:3807` · clave completa `app.api.stream`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/stream`](../rutas/api-stream.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## stream_generator

`app/api.py:3759` · clave completa `app.api.stream_generator`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/stream`](../rutas/api-stream.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## structure

`app/api.py:2298` · clave completa `app.api.structure`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/structure`](../rutas/api-structure.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## structure_detail_endpoint

`app/api.py:2170` · clave completa `app.api.structure_detail_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/structure-detail`](../rutas/api-structure-detail.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## swing_score_endpoint

`app/api.py:2141` · clave completa `app.api.swing_score_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/swing-score`](../rutas/api-swing-score.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## symbols

`app/api.py:664` · clave completa `app.api.symbols`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/symbols`](../rutas/api-symbols.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## trading_profile

`app/api.py:1606` · clave completa `app.api.trading_profile`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/profile`](../rutas/api-profile.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## trend_matrix_endpoint

`app/api.py:2148` · clave completa `app.api.trend_matrix_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## verdicts

`app/api.py:2208` · clave completa `app.api.verdicts`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/verdicts`](../rutas/api-verdicts.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## volatility_endpoint

`app/api.py:2134` · clave completa `app.api.volatility_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/volatility`](../rutas/api-volatility.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## volume_profile_endpoint

`app/api.py:1936` · clave completa `app.api.volume_profile_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/volume-profile`](../rutas/api-volume-profile.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## whale_delta

`app/api.py:1184` · clave completa `app.api.whale_delta`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/whale/delta`](../rutas/api-whale-delta.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## wyckoff_endpoint

`app/api.py:2071` · clave completa `app.api.wyckoff_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/wyckoff`](../rutas/api-wyckoff.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## zone_analysis_endpoint

`app/api.py:1995` · clave completa `app.api.zone_analysis_endpoint`

**Radio exacto: 1 rutas** de 75 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

