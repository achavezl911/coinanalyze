# Impacto · `app/cutoffs.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

1 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA se calcula subiendo llamadores hasta **k=2**; lo que este mas arriba **no se afirma**.

| funcion | linea | por llamada | por tabla | total |
|---|---|---|---|---|
| [`at`](#at) | 22 | 0 | 43 | **43** |

## at

`app/cutoffs.py:22` · clave completa `app.cutoffs.ClosedCutoff.at`

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
- `service_ownership` — la escribe `app.db.acquire_service_lock`

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

<sub>Radio por tabla hasta k=2. Lo que este mas arriba no se afirma. Llamadores considerados: 6.</sub>

