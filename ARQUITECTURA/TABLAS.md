# ARQUITECTURA · las tablas, y por donde viaja el impacto

> Generado por `harness/bin/arquitectura`. No editar a mano.

**El acoplamiento de este sistema NO viaja solo por la pila de llamadas: viaja por la**
**tabla.** Medido: `compute_snapshot` (`app/metrics.py:429`) no aparece en el cierre de
llamadas de ninguna de las 68 rutas, y aun asi tumbo el snapshot de los tres simbolos
durante 24 dias. El camino real es de dos saltos:

```
compute_snapshot --escribe--> metrics_snapshot --la leen--> N rutas
```

Un grafo de llamadas no ve esa arista porque no es una llamada. Esta tabla si.

## Tablas que alguna ruta lee o escribe

| tabla | escritores en el arbol | rutas que la leen | rutas que la escriben |
|---|---|---|---|
| [`daily_session_agg`](#daily-session-agg) | 2 | 20 | 0 |
| [`daily_verdict_outcome`](#daily-verdict-outcome) | 1 | 3 | 0 |
| [`daily_verdict_snapshot`](#daily-verdict-snapshot) | 1 | 3 | 0 |
| [`data_gap`](#data-gap) | 12 | 21 | 0 |
| [`external_macro_observation`](#external-macro-observation) | 2 | 3 | 0 |
| [`funding_rate`](#funding-rate) | 1 | 3 | 0 |
| [`futures_trades_agg`](#futures-trades-agg) | 2 | 6 | 0 |
| [`futures_trades_realtime`](#futures-trades-realtime) | 1 | 16 | 0 |
| [`liquidations`](#liquidations) | 2 | 4 | 0 |
| [`liquidations_realtime`](#liquidations-realtime) | 1 | 14 | 0 |
| [`long_short_ratio`](#long-short-ratio) | 2 | 3 | 0 |
| [`macro_event`](#macro-event) | 2 | 3 | 0 |
| [`market_feed_health`](#market-feed-health) | 3 | 9 | 0 |
| [`metric_baseline`](#metric-baseline) | 1 | 14 | 0 |
| [`metrics_snapshot`](#metrics-snapshot) | 2 | 8 | 0 |
| [`ohlcv`](#ohlcv) | 4 | 36 | 0 |
| [`oi_bybit`](#oi-bybit) | 1 | 3 | 0 |
| [`open_interest`](#open-interest) | 1 | 18 | 0 |
| [`orderbook_depth`](#orderbook-depth) | 1 | 1 | 0 |
| [`orderbook_snapshot`](#orderbook-snapshot) | 2 | 14 | 0 |
| [`pipeline_heartbeat`](#pipeline-heartbeat) | 3 | 7 | 1 |
| [`predicted_funding_rate`](#predicted-funding-rate) | 1 | 3 | 0 |
| [`scalp_signal_snapshot`](#scalp-signal-snapshot) | 1 | 4 | 0 |
| [`signal_execution_snapshot`](#signal-execution-snapshot) | 1 | 1 | 0 |
| [`signal_observation`](#signal-observation) | 1 | 5 | 0 |
| [`signal_outcome`](#signal-outcome) | 4 | 2 | 0 |
| [`signal_outcome_final_visibility`](#signal-outcome-final-visibility) | 1 | 1 | 0 |
| [`signal_replay_frame`](#signal-replay-frame) | 1 | 1 | 0 |
| [`spot_trades_agg`](#spot-trades-agg) | 3 | 10 | 0 |
| [`spot_trades_realtime`](#spot-trades-realtime) | 2 | 12 | 0 |

## Detalle · quien escribe cada una

### daily_session_agg

`sql/schema.sql:1032`, 14 columnas.

La escriben:

- `app.daily_agg.compute_session` — **INSERT** en `app/daily_agg.py:206`
- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:670`

**Si cambia el contenido o el esquema de `daily_session_agg`, estas 20 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/daily`](rutas/api-daily.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/divergences`](rutas/api-divergences.md)
- [`/api/external-macro`](rutas/api-external-macro.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/macro-context`](rutas/api-macro-context.md)
- [`/api/oi-context`](rutas/api-oi-context.md)
- [`/api/price-barriers`](rutas/api-price-barriers.md)
- [`/api/profile`](rutas/api-profile.md)
- [`/api/setup`](rutas/api-setup.md)
- [`/api/structure`](rutas/api-structure.md)
- [`/api/structure-detail`](rutas/api-structure-detail.md)
- [`/api/swing-score`](rutas/api-swing-score.md)
- [`/api/trend-matrix`](rutas/api-trend-matrix.md)
- [`/api/volatility`](rutas/api-volatility.md)
- [`/api/wyckoff`](rutas/api-wyckoff.md)
- [`/api/zone/analysis`](rutas/api-zone-analysis.md)

### daily_verdict_outcome

`sql/schema.sql:2290`, 10 columnas.

La escriben:

- `app.daily_agg.materialize_daily_verdict_outcomes` — **INSERT** en `app/daily_agg.py:507`

**Si cambia el contenido o el esquema de `daily_verdict_outcome`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](rutas/api-verdicts.md)

### daily_verdict_snapshot

`sql/schema.sql:1099`, 26 columnas.

La escriben:

- `app.daily_agg.persist_verdicts` — **INSERT** en `app/daily_agg.py:418`

**Si cambia el contenido o el esquema de `daily_verdict_snapshot`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/verdicts`](rutas/api-verdicts.md)

### data_gap

`sql/schema.sql:1412`, 22 columnas.

La escriben:

- `app.data_gaps.close_partitioned_gap` — **UPDATE** en `app/data_gaps.py:1092`
- `app.data_gaps._mark_unrecoverable` — **UPDATE** en `app/data_gaps.py:1243`
- `app.data_gaps._record_recovery_failure` — **UPDATE** en `app/data_gaps.py:1262`
- `app.data_gaps.recover_gap` — **UPDATE** en `app/data_gaps.py:1311`
- `app.data_gaps.record_data_gap` — **INSERT** en `app/data_gaps.py:322`
- `app.data_gaps.reconcile_cadence_coverage` — **UPDATE** en `app/data_gaps.py:584`
- `app.data_gaps.reconcile_cadence_coverage` — **UPDATE** en `app/data_gaps.py:663`
- `app.data_gaps.reconcile_cadence_coverage` — **UPDATE** en `app/data_gaps.py:687`
- `app.data_gaps.archive_beyond_source_horizon` — **UPDATE** en `app/data_gaps.py:764`
- `app.data_gaps.archive_beyond_source_horizon` — **UPDATE** en `app/data_gaps.py:764`
- `app.data_gaps.archive_source_response_absence` — **UPDATE** en `app/data_gaps.py:862`
- `app.data_gaps.archive_source_response_absence` — **UPDATE** en `app/data_gaps.py:862`

**Si cambia el contenido o el esquema de `data_gap`, estas 21 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/cvd`](rutas/api-cvd.md)
- [`/api/cvd-matrix`](rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](rutas/api-cvd-spot.md)
- [`/api/daily`](rutas/api-daily.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/external-macro`](rutas/api-external-macro.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/liquidations`](rutas/api-liquidations.md)
- [`/api/ohlcv`](rutas/api-ohlcv.md)
- [`/api/oi`](rutas/api-oi.md)
- [`/api/passive-flow`](rutas/api-passive-flow.md)
- [`/api/profile`](rutas/api-profile.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](rutas/api-swing-score.md)
- [`/api/trend-matrix`](rutas/api-trend-matrix.md)
- [`/api/whale/delta`](rutas/api-whale-delta.md)

### external_macro_observation

`sql/schema.sql:1234`, 5 columnas.

La escriben:

- `app.external_macro.refresh_external_macro` — **INSERT** en `app/external_macro.py:553`
- `app.external_macro.refresh_external_macro` — **DELETE** en `app/external_macro.py:574`

**Si cambia el contenido o el esquema de `external_macro_observation`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](rutas/api-external-macro.md)

### funding_rate

`sql/schema.sql:146`, 7 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:651`

**Si cambia el contenido o el esquema de `funding_rate`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/funding-context`](rutas/api-funding-context.md)

### futures_trades_agg

`sql/schema.sql:273`, 9 columnas.

La escriben:

- `app.scalp_collector.cleanup_expired_rows` — **DELETE** en `app/scalp_collector.py:1538`
- `app.scalp_collector._write_combined_minute` — **INSERT** en `app/scalp_collector.py:802`

**Si cambia el contenido o el esquema de `futures_trades_agg`, estas 6 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/price-barriers`](rutas/api-price-barriers.md)

### futures_trades_realtime

`sql/schema.sql:256`, 10 columnas.

La escriben:

- `app.scalp_collector._write_combined_realtime` — **INSERT** en `app/scalp_collector.py:773`

**Si cambia el contenido o el esquema de `futures_trades_realtime`, estas 16 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/stream`](rutas/api-stream.md)
- [`/api/structure`](rutas/api-structure.md)
- [`/metrics`](rutas/metrics.md)

### liquidations

`sql/schema.sql:174`, 5 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:657`
- `app.ingest.upsert_liquidations` — **INSERT** en `app/ingest.py:316`

**Si cambia el contenido o el esquema de `liquidations`, estas 4 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/liquidations`](rutas/api-liquidations.md)
- [`/api/structure`](rutas/api-structure.md)

### liquidations_realtime

`sql/schema.sql:339`, 8 columnas.

La escriben:

- `app.scalp_collector.flush_liquidations` — **INSERT** en `app/scalp_collector.py:74`

**Si cambia el contenido o el esquema de `liquidations_realtime`, estas 14 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/liquidation-map`](rutas/api-liquidation-map.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](rutas/api-scalp-liquidations.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/structure`](rutas/api-structure.md)
- [`/metrics`](rutas/metrics.md)

### long_short_ratio

`sql/schema.sql:187`, 6 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:660`
- `app.ingest.upsert_long_short` — **INSERT** en `app/ingest.py:357`

**Si cambia el contenido o el esquema de `long_short_ratio`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/positioning`](rutas/api-positioning.md)

### macro_event

`sql/schema.sql:1245`, 6 columnas.

La escriben:

- `app.external_macro.refresh_external_macro` — **INSERT** en `app/external_macro.py:564`
- `app.external_macro.refresh_external_macro` — **DELETE** en `app/external_macro.py:576`

**Si cambia el contenido o el esquema de `macro_event`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/external-macro`](rutas/api-external-macro.md)

### market_feed_health

`sql/schema.sql:1318`, 7 columnas.

La escriben:

- `app.db.mark_feed_connected` — **INSERT** en `app/db.py:580`
- `app.db._mark_feed_unhealthy` — **INSERT** en `app/db.py:609`
- `app.db._mark_feed_shard_health` — **INSERT** en `app/db.py:706`

**Si cambia el contenido o el esquema de `market_feed_health`, estas 9 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)

### metric_baseline

`sql/schema.sql:1265`, 14 columnas.

La escriben:

- `app.daily_agg._store_baseline` — **INSERT** en `app/daily_agg.py:780`

**Si cambia el contenido o el esquema de `metric_baseline`, estas 14 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/baselines`](rutas/api-baselines.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/market-impact`](rutas/api-market-impact.md)
- [`/api/profile`](rutas/api-profile.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)

### metrics_snapshot

`sql/schema.sql:945`, 35 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:666`
- `app.metrics.insert_snapshot` — **INSERT** en `app/metrics.py:683`

**Si cambia el contenido o el esquema de `metrics_snapshot`, estas 8 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/healthz`](rutas/api-healthz.md)
- [`/api/setup`](rutas/api-setup.md)
- [`/api/snapshot`](rutas/api-snapshot.md)
- [`/metrics`](rutas/metrics.md)

### ohlcv

`sql/schema.sql:54`, 13 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:637`
- `app.ingest.upsert_ohlcv` — **INSERT** en `app/ingest.py:154`
- `app.ingest.rollup_ohlcv_5m` — **INSERT** en `app/ingest.py:200`
- `app.ingest.rollup_ohlcv_5m` — **INSERT** en `app/ingest.py:200`

**Si cambia el contenido o el esquema de `ohlcv`, estas 36 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/cross-asset`](rutas/api-cross-asset.md)
- [`/api/cvd`](rutas/api-cvd.md)
- [`/api/cvd/divergence`](rutas/api-cvd-divergence.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/delta-profile`](rutas/api-delta-profile.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/divergences`](rutas/api-divergences.md)
- [`/api/external-macro`](rutas/api-external-macro.md)
- [`/api/flow/spot-vs-perp`](rutas/api-flow-spot-vs-perp.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/level/breakout`](rutas/api-level-breakout.md)
- [`/api/liquidation-map`](rutas/api-liquidation-map.md)
- [`/api/market-impact`](rutas/api-market-impact.md)
- [`/api/market-memory`](rutas/api-market-memory.md)
- [`/api/ohlcv`](rutas/api-ohlcv.md)
- [`/api/oi-context`](rutas/api-oi-context.md)
- [`/api/passive-flow`](rutas/api-passive-flow.md)
- [`/api/price-barriers`](rutas/api-price-barriers.md)
- [`/api/profile`](rutas/api-profile.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/range/validate`](rutas/api-range-validate.md)
- [`/api/reference-levels`](rutas/api-reference-levels.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/structure`](rutas/api-structure.md)
- [`/api/structure-detail`](rutas/api-structure-detail.md)
- [`/api/swing-score`](rutas/api-swing-score.md)
- [`/api/trend-matrix`](rutas/api-trend-matrix.md)
- [`/api/volatility`](rutas/api-volatility.md)
- [`/api/volume-profile`](rutas/api-volume-profile.md)
- [`/api/wyckoff`](rutas/api-wyckoff.md)
- [`/api/zone/analysis`](rutas/api-zone-analysis.md)

### oi_bybit

`sql/schema.sql:97`, 7 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:648`

**Si cambia el contenido o el esquema de `oi_bybit`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/oi-context`](rutas/api-oi-context.md)

### open_interest

`sql/schema.sql:83`, 7 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:645`

**Si cambia el contenido o el esquema de `open_interest`, estas 18 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/external-macro`](rutas/api-external-macro.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/oi`](rutas/api-oi.md)
- [`/api/oi-context`](rutas/api-oi-context.md)
- [`/api/passive-flow`](rutas/api-passive-flow.md)
- [`/api/profile`](rutas/api-profile.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/structure`](rutas/api-structure.md)
- [`/api/swing-score`](rutas/api-swing-score.md)
- [`/api/trend-matrix`](rutas/api-trend-matrix.md)

### orderbook_depth

`sql/schema.sql:329`, 6 columnas.

La escriben:

- `app.scalp_collector._write_ladders` — **INSERT** en `app/scalp_collector.py:877`

**Si cambia el contenido o el esquema de `orderbook_depth`, estas 1 rutas lo notan:**

- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)

### orderbook_snapshot

`sql/schema.sql:287`, 18 columnas.

La escriben:

- `app.scalp_collector.flush_books` — **INSERT** en `app/scalp_collector.py:845`
- `app.scalp_collector._write_combined_books` — **INSERT** en `app/scalp_collector.py:901`

**Si cambia el contenido o el esquema de `orderbook_snapshot`, estas 14 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/price-barriers`](rutas/api-price-barriers.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/orderbook`](rutas/api-scalp-orderbook.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/stream`](rutas/api-stream.md)
- [`/metrics`](rutas/metrics.md)

### pipeline_heartbeat

`sql/schema.sql:1284`, 4 columnas.

La escriben:

- `app.db.heartbeat` — **INSERT** en `app/db.py:418`
- `app.db.heartbeat_component` — **INSERT** en `app/db.py:472`
- `app.db.heartbeat_shard` — **INSERT** en `app/db.py:542`

**Si cambia el contenido o el esquema de `pipeline_heartbeat`, estas 7 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/healthz`](rutas/api-healthz.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/metrics`](rutas/metrics.md)

Rutas que ESCRIBEN en `pipeline_heartbeat`: `/api/healthz`

### predicted_funding_rate

`sql/schema.sql:160`, 7 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:654`

**Si cambia el contenido o el esquema de `predicted_funding_rate`, estas 3 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/funding-context`](rutas/api-funding-context.md)

### scalp_signal_snapshot

`sql/schema.sql:381`, 16 columnas.

La escriben:

- `app.scalp_collector.persist_scalp_signals` — **INSERT** en `app/scalp_collector.py:1406`

**Si cambia el contenido o el esquema de `scalp_signal_snapshot`, estas 4 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](rutas/api-scalp-signals.md)
- [`/metrics`](rutas/metrics.md)

### signal_execution_snapshot

`sql/schema.sql:793`, 21 columnas.

La escriben:

- `app.signal_execution.persist_signal_execution_snapshots` — **INSERT** en `app/signal_execution.py:452`

**Si cambia el contenido o el esquema de `signal_execution_snapshot`, estas 1 rutas lo notan:**

- [`/api/signals/execution`](rutas/api-signals-execution.md)

### signal_observation

`sql/schema.sql:415`, 34 columnas.

La escriben:

- `app.signal_ledger.persist_signal_observations` — **INSERT** en `app/signal_ledger.py:371`

**Si cambia el contenido o el esquema de `signal_observation`, estas 5 rutas lo notan:**

- [`/api/signals/execution`](rutas/api-signals-execution.md)
- [`/api/signals/ledger`](rutas/api-signals-ledger.md)
- [`/api/signals/outcomes`](rutas/api-signals-outcomes.md)
- [`/api/signals/replay`](rutas/api-signals-replay.md)
- [`/api/signals/visibility`](rutas/api-signals-visibility.md)

### signal_outcome

`sql/schema.sql:565`, 27 columnas.

La escriben:

- `app.signal_outcomes.schedule_signal_outcomes` — **INSERT** en `app/signal_outcomes.py:169`
- `app.signal_outcomes._finalize_not_evaluable` — **UPDATE** en `app/signal_outcomes.py:199`
- `app.signal_outcomes._defer_missing_path` — **UPDATE** en `app/signal_outcomes.py:226`
- `app.signal_outcomes._finalize_evaluated` — **UPDATE** en `app/signal_outcomes.py:252`

**Si cambia el contenido o el esquema de `signal_outcome`, estas 2 rutas lo notan:**

- [`/api/signals/outcomes`](rutas/api-signals-outcomes.md)
- [`/api/signals/visibility`](rutas/api-signals-visibility.md)

### signal_outcome_final_visibility

`sql/schema.sql:2477`, 8 columnas.

La escriben:

- `app.signal_visibility._certify_final_outcomes_once` — **INSERT** en `app/signal_visibility.py:308`

**Si cambia el contenido o el esquema de `signal_outcome_final_visibility`, estas 1 rutas lo notan:**

- [`/api/signals/visibility`](rutas/api-signals-visibility.md)

### signal_replay_frame

`sql/schema.sql:751`, 7 columnas.

La escriben:

- `app.signal_replay.persist_signal_replay_frame` — **INSERT** en `app/signal_replay.py:111`

**Si cambia el contenido o el esquema de `signal_replay_frame`, estas 1 rutas lo notan:**

- [`/api/signals/replay`](rutas/api-signals-replay.md)

### spot_trades_agg

`sql/schema.sql:198`, 13 columnas.

La escriben:

- `app.daily_agg.apply_retention` — **DELETE** en `app/daily_agg.py:663`
- `app.ws_collector._write_minute` — **INSERT** en `app/ws_collector.py:254`
- `app.ws_collector._write_minute` — **INSERT** en `app/ws_collector.py:275`

**Si cambia el contenido o el esquema de `spot_trades_agg`, estas 10 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/cvd/divergence`](rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/divergences`](rutas/api-divergences.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/price-barriers`](rutas/api-price-barriers.md)
- [`/api/whale/delta`](rutas/api-whale-delta.md)

### spot_trades_realtime

`sql/schema.sql:228`, 10 columnas.

La escriben:

- `app.ws_collector.flush_realtime` — **INSERT** en `app/ws_collector.py:376`
- `app.ws_collector.flush_realtime` — **INSERT** en `app/ws_collector.py:393`

**Si cambia el contenido o el esquema de `spot_trades_realtime`, estas 12 rutas lo notan:**

- [`/api/ai/context`](rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
- [`/api/data-confidence`](rutas/api-data-confidence.md)
- [`/api/desk/state`](rutas/api-desk-state.md)
- [`/api/hypothesis`](rutas/api-hypothesis.md)
- [`/api/quality/feeds`](rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](rutas/api-scalp-summary.md)
- [`/api/stream`](rutas/api-stream.md)

## Tablas que se escriben pero que ninguna ruta lee

Existen y se llenan, pero **no se publican por ninguna ruta**. No es
necesariamente un fallo -puede ser estado interno-, pero es exactamente la forma
del patron que en esta casa se ha repetido nueve veces: algo que existe, parece
completo, y no esta conectado a nada. Merece una mirada, no una conclusion.

- `daily_verdict` — la escriben 2: `app/daily_agg.py:459`, `app/daily_agg.py:674`
- `external_api_rate_event` — la escriben 2: `app/coinalyze.py:68`, `app/coinalyze.py:87`
- `market_assets` — la escriben 1: `app/db.py:247`
- `market_feed_health_shard` — la escriben 1: `app/db.py:672`
- `open_interest_daily` — la escriben 2: `app/daily_agg.py:582`, `app/daily_agg.py:582`
- `service_ownership` — la escriben 1: `app/db.py:283`
- `signal_research_bundle_visibility` — la escriben 1: `app/signal_visibility.py:229`
- `signal_walk_forward_manifest` — la escriben 1: `app/signal_walk_forward.py:596`
- `symbols` — la escriben 1: `app/db.py:252`

