# Impacto · `app/metrics.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

11 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`session_bounds`](#session-bounds) | 31 | 2 | 51 | **51** |
| [`compute_and_store_all`](#compute-and-store-all) | 711 | 0 | 43 | **43** |
| [`current_nyse_start`](#current-nyse-start) | 20 | 15 | 14 | **26** |
| [`liquidation_history_observation`](#liquidation-history-observation) | 252 | 0 | 20 | **20** |
| [`_liquidation_history_observed`](#-liquidation-history-observed) | 315 | 0 | 8 | **8** |
| [`compute_regime`](#compute-regime) | 166 | 0 | 8 | **8** |
| [`compute_snapshot`](#compute-snapshot) | 429 | 0 | 8 | **8** |
| [`insert_snapshot`](#insert-snapshot) | 676 | 0 | 8 | **8** |
| [`normalized_cvd_imbalance`](#normalized-cvd-imbalance) | 146 | 0 | 8 | **8** |
| [`optional_finite`](#optional-finite) | 50 | 0 | 8 | **8** |
| [`whale_classification`](#whale-classification) | 66 | 0 | 8 | **8** |

## session_bounds

`app/metrics.py:31` · clave completa `app.metrics.session_bounds`

**Radio total: 51 rutas** de 68.

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/daily`](../rutas/api-daily.md)
- [`/api/verdicts`](../rutas/api-verdicts.md)

### Por tabla — 51 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_session_agg` — la escribe `app.daily_agg.apply_retention`, `app.daily_agg.compute_session`
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
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 7.</sub>

## compute_and_store_all

`app/metrics.py:711` · clave completa `app.metrics.compute_and_store_all`

**Radio total: 43 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 43 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `external_macro_observation` — la escribe `app.external_macro.refresh_external_macro`
- `liquidations` — la escribe `app.ingest.upsert_liquidations`
- `long_short_ratio` — la escribe `app.ingest.upsert_long_short`
- `macro_event` — la escribe `app.external_macro.refresh_external_macro`
- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`
- `ohlcv` — la escribe `app.ingest.rollup_ohlcv_5m`, `app.ingest.upsert_ohlcv`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat`, `app.db.heartbeat_component`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/market-memory`](../rutas/api-market-memory.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)
- [`/metrics`](../rutas/metrics.md)

**43 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](../rutas/api-cross-asset.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/delta-profile`](../rutas/api-delta-profile.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](../rutas/api-flow-spot-vs-perp.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/level/breakout`](../rutas/api-level-breakout.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/market-impact`](../rutas/api-market-impact.md)
- [`/api/market-memory`](../rutas/api-market-memory.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/positioning`](../rutas/api-positioning.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/range/validate`](../rutas/api-range-validate.md)
- [`/api/reference-levels`](../rutas/api-reference-levels.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/volume-profile`](../rutas/api-volume-profile.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 3.</sub>

## current_nyse_start

`app/metrics.py:20` · clave completa `app.metrics.current_nyse_start`

**Radio total: 26 rutas** de 68.

### Por llamada — 15 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla — 14 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**11 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/signals/execution`](../rutas/api-signals-execution.md)
- [`/api/signals/ledger`](../rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](../rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](../rutas/api-signals-replay.md)
- [`/api/signals/visibility`](../rutas/api-signals-visibility.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 21.</sub>

## liquidation_history_observation

`app/metrics.py:252` · clave completa `app.metrics.liquidation_history_observation`

**Radio total: 20 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 20 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `daily_session_agg` — la escribe `app.daily_agg.compute_session`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/divergences`](../rutas/api-divergences.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/macro-context`](../rutas/api-macro-context.md)
- [`/api/oi-context`](../rutas/api-oi-context.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/structure-detail`](../rutas/api-structure-detail.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/volatility`](../rutas/api-volatility.md)
- [`/api/wyckoff`](../rutas/api-wyckoff.md)
- [`/api/zone/analysis`](../rutas/api-zone-analysis.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 4.</sub>

## _liquidation_history_observed

`app/metrics.py:315` · clave completa `app.metrics._liquidation_history_observed`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## compute_regime

`app/metrics.py:166` · clave completa `app.metrics.compute_regime`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## compute_snapshot

`app/metrics.py:429` · clave completa `app.metrics.compute_snapshot`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## insert_snapshot

`app/metrics.py:676` · clave completa `app.metrics.insert_snapshot`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## normalized_cvd_imbalance

`app/metrics.py:146` · clave completa `app.metrics.normalized_cvd_imbalance`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

## optional_finite

`app/metrics.py:50` · clave completa `app.metrics.optional_finite`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 5.</sub>

## whale_classification

`app/metrics.py:66` · clave completa `app.metrics.whale_classification`

**Radio total: 8 rutas** de 68.

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla — 8 rutas · k=2

Esta funcion, o alguien que la llama hasta k=2, escribe:

- `metrics_snapshot` — la escribe `app.metrics.insert_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

**8 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/setup`](../rutas/api-setup.md)
- [`/api/snapshot`](../rutas/api-snapshot.md)
- [`/metrics`](../rutas/metrics.md)

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 2.</sub>

