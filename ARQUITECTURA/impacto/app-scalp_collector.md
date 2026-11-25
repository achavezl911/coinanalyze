# Impacto · `app/scalp_collector.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

30 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_restore_liquidation_heartbeat`](#-restore-liquidation-heartbeat) | 709 | 0 | **11** | 36 ↑ | **11** |
| [`declare_liquidation_silence`](#declare-liquidation-silence) | 487 | 0 | **21** | 36 ↑ | **21** |
| [`reset_liquidation_feed_health`](#reset-liquidation-feed-health) | 673 | 0 | **0** | 36 ↑ | **0** |
| [`owns_global_cleanup`](#owns-global-cleanup) | 1667 | 0 | **0** | 32 ↑ | **0** |
| [`all_expected_fresh`](#all-expected-fresh) | 736 | 0 | **0** | 27 ↑ | **0** |
| [`monitor`](#monitor) | 1595 | 0 | **0** | 27 ↑ | **0** |
| [`persist_liquidation_health_snapshot`](#persist-liquidation-health-snapshot) | 612 | 0 | **0** | 27 ↑ | **0** |
| [`_write_liquidation_health`](#-write-liquidation-health) | 542 | 0 | **0** | 26 ↑ | **0** |
| [`persist_scalp_signals`](#persist-scalp-signals) | 1490 | 0 | **5** | 25 ↑ | **5** |
| [`_write_combined_minute`](#-write-combined-minute) | 920 | 0 | **7** | 22 ↑ | **7** |
| [`_write_combined_realtime`](#-write-combined-realtime) | 891 | 0 | **17** | 22 ↑ | **17** |
| [`_write_trade_rows`](#-write-trade-rows) | 834 | 0 | **0** | 22 ↑ | **0** |
| [`flush_trades`](#flush-trades) | 744 | 0 | **0** | 22 ↑ | **0** |
| [`_write_combined_books`](#-write-combined-books) | 1021 | 0 | **15** | 20 ↑ | **15** |
| [`_write_ladders`](#-write-ladders) | 989 | 0 | **1** | 20 ↑ | **1** |
| [`binance_loop`](#binance-loop) | 1113 | 0 | **0** | 20 ↑ | **0** |
| [`binance_market_loop`](#binance-market-loop) | 1233 | 0 | **0** | 20 ↑ | **0** |
| [`bybit_loop`](#bybit-loop) | 1285 | 0 | **0** | 20 ↑ | **0** |
| [`cleanup`](#cleanup) | 1702 | 0 | **0** | 20 ↑ | **0** |
| [`cleanup_expired_rows`](#cleanup-expired-rows) | 1671 | 0 | **7** | 20 ↑ | **7** |
| [`drenar_minutos`](#drenar-minutos) | 805 | 0 | **0** | 20 ↑ | **0** |
| [`flush_books`](#flush-books) | 946 | 0 | **15** | 20 ↑ | **15** |
| [`flush_liquidations`](#flush-liquidations) | 1079 | 0 | **15** | 20 ↑ | **15** |
| [`handle_binance`](#handle-binance) | 1172 | 0 | **0** | 20 ↑ | **0** |
| [`handle_bybit`](#handle-bybit) | 1374 | 0 | **0** | 20 ↑ | **0** |
| [`main`](#main) | 1718 | 0 | **0** | 20 ↑ | **0** |
| [`mark_exchange_disconnected`](#mark-exchange-disconnected) | 731 | 0 | **0** | 20 ↑ | **0** |
| [`persist_liquidation_feed_state`](#persist-liquidation-feed-state) | 583 | 0 | **0** | 20 ↑ | **0** |
| [`segundos_cubiertos`](#segundos-cubiertos) | 782 | 0 | **0** | 18 ↑ | **0** |
| [`persist_liquidation_event_loss`](#persist-liquidation-event-loss) | 649 | 0 | **0** | 14 ↑ | **0** |

## _restore_liquidation_heartbeat

`app/scalp_collector.py:709` · clave completa `app.scalp_collector._restore_liquidation_heartbeat`

**Radio exacto: 11 rutas** de 94 · **cota superior: 36** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 11 rutas · **exacto**

Escribe **ella misma**: `market_feed_health`, `market_feed_health_shard`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)

### Por tabla · k<=2 — 36 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (36 contra 11). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `data_gap` — la escribe `app.scalp_collector.declare_liquidation_silence`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `market_feed_health` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `market_feed_health_shard` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

**36 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## declare_liquidation_silence

`app/scalp_collector.py:487` · clave completa `app.scalp_collector.declare_liquidation_silence`

**Radio exacto: 21 rutas** de 94 · **cota superior: 36** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 21 rutas · **exacto**

Escribe **ella misma**: `data_gap`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)

### Por tabla · k<=2 — 36 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (36 contra 21). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `data_gap` — la escribe `app.scalp_collector.declare_liquidation_silence`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `market_feed_health` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `market_feed_health_shard` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

**36 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 5 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## reset_liquidation_feed_health

`app/scalp_collector.py:673` · clave completa `app.scalp_collector.reset_liquidation_feed_health`

**Radio exacto: 0 rutas** de 94 · **cota superior: 36** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 36 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (36 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `data_gap` — la escribe `app.scalp_collector.declare_liquidation_silence`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `market_feed_health` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `market_feed_health_shard` — la escribe `app.scalp_collector._restore_liquidation_heartbeat`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

**36 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## owns_global_cleanup

`app/scalp_collector.py:1667` · clave completa `app.scalp_collector.owns_global_cleanup`

**Radio exacto: 0 rutas** de 94 · **cota superior: 32** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 32 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (32 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`
- `signal_observation` — la escribe `app.signal_ledger.persist_signal_observations`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
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
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**32 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
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
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## all_expected_fresh

`app/scalp_collector.py:736` · clave completa `app.scalp_collector.all_expected_fresh`

**Radio exacto: 0 rutas** de 94 · **cota superior: 27** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 27 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (27 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**27 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## monitor

`app/scalp_collector.py:1595` · clave completa `app.scalp_collector.monitor`

**Radio exacto: 0 rutas** de 94 · **cota superior: 27** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 27 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (27 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**27 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_liquidation_health_snapshot

`app/scalp_collector.py:612` · clave completa `app.scalp_collector.persist_liquidation_health_snapshot`

**Radio exacto: 0 rutas** de 94 · **cota superior: 27** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 27 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (27 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**27 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_liquidation_health

`app/scalp_collector.py:542` · clave completa `app.scalp_collector._write_liquidation_health`

**Radio exacto: 0 rutas** de 94 · **cota superior: 26** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 26 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (26 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `data_gap` — la escribe `app.scalp_collector.declare_liquidation_silence`
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**26 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd-matrix`](../rutas/api-cvd-matrix.md)
- [`/api/cvd/divergence`](../rutas/api-cvd-divergence.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/daily`](../rutas/api-daily.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/external-macro`](../rutas/api-external-macro.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/passive-flow`](../rutas/api-passive-flow.md)
- [`/api/profile`](../rutas/api-profile.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/delta-matrix`](../rutas/api-scalp-delta-matrix.md)
- [`/api/swing-score`](../rutas/api-swing-score.md)
- [`/api/trend-matrix`](../rutas/api-trend-matrix.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 5 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_scalp_signals

`app/scalp_collector.py:1490` · clave completa `app.scalp_collector.persist_scalp_signals`

**Radio exacto: 5 rutas** de 94 · **cota superior: 25** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 5 rutas · **exacto**

Escribe **ella misma**: `scalp_signal_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 25 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (25 contra 5). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

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
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
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

**25 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
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

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_combined_minute

`app/scalp_collector.py:920` · clave completa `app.scalp_collector._write_combined_minute`

**Radio exacto: 7 rutas** de 94 · **cota superior: 22** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 7 rutas · **exacto**

Escribe **ella misma**: `futures_trades_agg`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla · k<=2 — 22 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (22 contra 7). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `futures_trades_realtime` — la escribe `app.scalp_collector._write_combined_realtime`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**22 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_combined_realtime

`app/scalp_collector.py:891` · clave completa `app.scalp_collector._write_combined_realtime`

**Radio exacto: 17 rutas** de 94 · **cota superior: 22** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 17 rutas · **exacto**

Escribe **ella misma**: `futures_trades_realtime`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 22 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (22 contra 17). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `futures_trades_realtime` — la escribe `app.scalp_collector._write_combined_realtime`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**22 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_trade_rows

`app/scalp_collector.py:834` · clave completa `app.scalp_collector._write_trade_rows`

**Radio exacto: 0 rutas** de 94 · **cota superior: 22** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 22 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (22 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `futures_trades_realtime` — la escribe `app.scalp_collector._write_combined_realtime`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**22 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flush_trades

`app/scalp_collector.py:744` · clave completa `app.scalp_collector.flush_trades`

**Radio exacto: 0 rutas** de 94 · **cota superior: 22** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 22 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (22 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `futures_trades_realtime` — la escribe `app.scalp_collector._write_combined_realtime`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**22 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_combined_books

`app/scalp_collector.py:1021` · clave completa `app.scalp_collector._write_combined_books`

**Radio exacto: 15 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 15 rutas · **exacto**

Escribe **ella misma**: `orderbook_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 15). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_depth` — la escribe `app.scalp_collector._write_ladders`
- `orderbook_snapshot` — la escribe `app.scalp_collector._write_combined_books`, `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_ladders

`app/scalp_collector.py:989` · clave completa `app.scalp_collector._write_ladders`

**Radio exacto: 1 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 1 rutas · **exacto**

Escribe **ella misma**: `orderbook_depth`

Y esas tablas las leen:

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 1). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_depth` — la escribe `app.scalp_collector._write_ladders`
- `orderbook_snapshot` — la escribe `app.scalp_collector._write_combined_books`, `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## binance_loop

`app/scalp_collector.py:1113` · clave completa `app.scalp_collector.binance_loop`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## binance_market_loop

`app/scalp_collector.py:1233` · clave completa `app.scalp_collector.binance_market_loop`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## bybit_loop

`app/scalp_collector.py:1285` · clave completa `app.scalp_collector.bybit_loop`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cleanup

`app/scalp_collector.py:1702` · clave completa `app.scalp_collector.cleanup`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector.cleanup_expired_rows`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cleanup_expired_rows

`app/scalp_collector.py:1671` · clave completa `app.scalp_collector.cleanup_expired_rows`

**Radio exacto: 7 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 7 rutas · **exacto**

Escribe **ella misma**: `futures_trades_agg`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 7). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector.cleanup_expired_rows`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## drenar_minutos

`app/scalp_collector.py:805` · clave completa `app.scalp_collector.drenar_minutos`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flush_books

`app/scalp_collector.py:946` · clave completa `app.scalp_collector.flush_books`

**Radio exacto: 15 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 15 rutas · **exacto**

Escribe **ella misma**: `orderbook_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 15). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_depth` — la escribe `app.scalp_collector._write_ladders`
- `orderbook_snapshot` — la escribe `app.scalp_collector._write_combined_books`, `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flush_liquidations

`app/scalp_collector.py:1079` · clave completa `app.scalp_collector.flush_liquidations`

**Radio exacto: 15 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 15 rutas · **exacto**

Escribe **ella misma**: `liquidations_realtime`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 15). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## handle_binance

`app/scalp_collector.py:1172` · clave completa `app.scalp_collector.handle_binance`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## handle_bybit

`app/scalp_collector.py:1374` · clave completa `app.scalp_collector.handle_bybit`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## main

`app/scalp_collector.py:1718` · clave completa `app.scalp_collector.main`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mark_exchange_disconnected

`app/scalp_collector.py:731` · clave completa `app.scalp_collector.mark_exchange_disconnected`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_liquidation_feed_state

`app/scalp_collector.py:583` · clave completa `app.scalp_collector.persist_liquidation_feed_state`

**Radio exacto: 0 rutas** de 94 · **cota superior: 20** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 20 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (20 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `liquidations_realtime` — la escribe `app.scalp_collector.flush_liquidations`
- `orderbook_snapshot` — la escribe `app.scalp_collector.flush_books`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**20 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## segundos_cubiertos

`app/scalp_collector.py:782` · clave completa `app.scalp_collector.segundos_cubiertos`

**Radio exacto: 0 rutas** de 94 · **cota superior: 18** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 18 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (18 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `futures_trades_agg` — la escribe `app.scalp_collector._write_combined_minute`
- `futures_trades_realtime` — la escribe `app.scalp_collector._write_combined_realtime`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

**18 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/absorption`](../rutas/api-scalp-absorption.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/basis`](../rutas/api-scalp-basis.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_liquidation_event_loss

`app/scalp_collector.py:649` · clave completa `app.scalp_collector.persist_liquidation_event_loss`

**Radio exacto: 0 rutas** de 94 · **cota superior: 14** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 14 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (14 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

**14 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/cvd`](../rutas/api-cvd.md)
- [`/api/cvd/spot`](../rutas/api-cvd-spot.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
- [`/api/liquidations`](../rutas/api-liquidations.md)
- [`/api/mesa/decide`](../rutas/api-mesa-decide.md)
- [`/api/ohlcv`](../rutas/api-ohlcv.md)
- [`/api/oi`](../rutas/api-oi.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/whale/delta`](../rutas/api-whale-delta.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

