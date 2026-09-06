# Impacto · `app/scalp_collector.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

27 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`owns_global_cleanup`](#owns-global-cleanup) | 1535 | 0 | **0** | 25 ↑ | **0** |
| [`persist_scalp_signals`](#persist-scalp-signals) | 1358 | 0 | **4** | 24 ↑ | **4** |
| [`_write_combined_minute`](#-write-combined-minute) | 806 | 0 | **6** | 21 ↑ | **6** |
| [`_write_combined_realtime`](#-write-combined-realtime) | 777 | 0 | **16** | 21 ↑ | **16** |
| [`_write_trade_rows`](#-write-trade-rows) | 720 | 0 | **0** | 21 ↑ | **0** |
| [`flush_trades`](#flush-trades) | 637 | 0 | **0** | 21 ↑ | **0** |
| [`all_expected_fresh`](#all-expected-fresh) | 629 | 0 | **0** | 20 ↑ | **0** |
| [`monitor`](#monitor) | 1463 | 0 | **0** | 20 ↑ | **0** |
| [`persist_liquidation_health_snapshot`](#persist-liquidation-health-snapshot) | 525 | 0 | **0** | 20 ↑ | **0** |
| [`_write_combined_books`](#-write-combined-books) | 907 | 0 | **14** | 19 ↑ | **14** |
| [`_write_ladders`](#-write-ladders) | 875 | 0 | **1** | 19 ↑ | **1** |
| [`binance_loop`](#binance-loop) | 999 | 0 | **0** | 19 ↑ | **0** |
| [`binance_market_loop`](#binance-market-loop) | 1109 | 0 | **0** | 19 ↑ | **0** |
| [`bybit_loop`](#bybit-loop) | 1161 | 0 | **0** | 19 ↑ | **0** |
| [`cleanup`](#cleanup) | 1570 | 0 | **0** | 19 ↑ | **0** |
| [`cleanup_expired_rows`](#cleanup-expired-rows) | 1539 | 0 | **6** | 19 ↑ | **6** |
| [`drenar_minutos`](#drenar-minutos) | 691 | 0 | **0** | 19 ↑ | **0** |
| [`flush_books`](#flush-books) | 832 | 0 | **14** | 19 ↑ | **14** |
| [`flush_liquidations`](#flush-liquidations) | 965 | 0 | **14** | 19 ↑ | **14** |
| [`handle_binance`](#handle-binance) | 1055 | 0 | **0** | 19 ↑ | **0** |
| [`handle_bybit`](#handle-bybit) | 1247 | 0 | **0** | 19 ↑ | **0** |
| [`main`](#main) | 1586 | 0 | **0** | 19 ↑ | **0** |
| [`mark_exchange_disconnected`](#mark-exchange-disconnected) | 624 | 0 | **0** | 19 ↑ | **0** |
| [`persist_liquidation_feed_state`](#persist-liquidation-feed-state) | 463 | 0 | **0** | 19 ↑ | **0** |
| [`reset_liquidation_feed_health`](#reset-liquidation-feed-health) | 604 | 0 | **0** | 19 ↑ | **0** |
| [`segundos_cubiertos`](#segundos-cubiertos) | 673 | 0 | **0** | 17 ↑ | **0** |
| [`persist_liquidation_event_loss`](#persist-liquidation-event-loss) | 580 | 0 | **0** | 7 ↑ | **0** |

## owns_global_cleanup

`app/scalp_collector.py:1535` · clave completa `app.scalp_collector.owns_global_cleanup`

**Radio exacto: 0 rutas** de 68 · **cota superior: 25** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 25 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (25 contra 0). Parte de la diferencia puede entrar por un bucle
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
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
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

**25 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
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

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_scalp_signals

`app/scalp_collector.py:1358` · clave completa `app.scalp_collector.persist_scalp_signals`

**Radio exacto: 4 rutas** de 68 · **cota superior: 24** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 4 rutas · **exacto**

Escribe **ella misma**: `scalp_signal_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/scalp/signals`](../rutas/api-scalp-signals.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 24 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (24 contra 4). Parte de la diferencia puede entrar por un bucle
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

**24 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_combined_minute

`app/scalp_collector.py:806` · clave completa `app.scalp_collector._write_combined_minute`

**Radio exacto: 6 rutas** de 68 · **cota superior: 21** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 6 rutas · **exacto**

Escribe **ella misma**: `futures_trades_agg`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla · k<=2 — 21 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (21 contra 6). Parte de la diferencia puede entrar por un bucle
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

**21 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
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

`app/scalp_collector.py:777` · clave completa `app.scalp_collector._write_combined_realtime`

**Radio exacto: 16 rutas** de 68 · **cota superior: 21** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 16 rutas · **exacto**

Escribe **ella misma**: `futures_trades_realtime`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
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

### Por tabla · k<=2 — 21 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (21 contra 16). Parte de la diferencia puede entrar por un bucle
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

**21 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
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

`app/scalp_collector.py:720` · clave completa `app.scalp_collector._write_trade_rows`

**Radio exacto: 0 rutas** de 68 · **cota superior: 21** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 21 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (21 contra 0). Parte de la diferencia puede entrar por un bucle
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

**21 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
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

`app/scalp_collector.py:637` · clave completa `app.scalp_collector.flush_trades`

**Radio exacto: 0 rutas** de 68 · **cota superior: 21** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 21 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (21 contra 0). Parte de la diferencia puede entrar por un bucle
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

**21 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
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

## all_expected_fresh

`app/scalp_collector.py:629` · clave completa `app.scalp_collector.all_expected_fresh`

**Radio exacto: 0 rutas** de 68 · **cota superior: 20** (mas ancha)

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
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## monitor

`app/scalp_collector.py:1463` · clave completa `app.scalp_collector.monitor`

**Radio exacto: 0 rutas** de 68 · **cota superior: 20** (mas ancha)

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
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_liquidation_health_snapshot

`app/scalp_collector.py:525` · clave completa `app.scalp_collector.persist_liquidation_health_snapshot`

**Radio exacto: 0 rutas** de 68 · **cota superior: 20** (mas ancha)

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
- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`
- `scalp_signal_snapshot` — la escribe `app.scalp_collector.persist_scalp_signals`
- `service_ownership` — la escribe `app.db.acquire_service_lock`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/healthz`](../rutas/api-healthz.md)
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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_combined_books

`app/scalp_collector.py:907` · clave completa `app.scalp_collector._write_combined_books`

**Radio exacto: 14 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 14 rutas · **exacto**

Escribe **ella misma**: `orderbook_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 14). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _write_ladders

`app/scalp_collector.py:875` · clave completa `app.scalp_collector._write_ladders`

**Radio exacto: 1 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 1 rutas · **exacto**

Escribe **ella misma**: `orderbook_depth`

Y esas tablas las leen:

- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 1). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## binance_loop

`app/scalp_collector.py:999` · clave completa `app.scalp_collector.binance_loop`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## binance_market_loop

`app/scalp_collector.py:1109` · clave completa `app.scalp_collector.binance_market_loop`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## bybit_loop

`app/scalp_collector.py:1161` · clave completa `app.scalp_collector.bybit_loop`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cleanup

`app/scalp_collector.py:1570` · clave completa `app.scalp_collector.cleanup`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cleanup_expired_rows

`app/scalp_collector.py:1539` · clave completa `app.scalp_collector.cleanup_expired_rows`

**Radio exacto: 6 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 6 rutas · **exacto**

Escribe **ella misma**: `futures_trades_agg`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 6). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## drenar_minutos

`app/scalp_collector.py:691` · clave completa `app.scalp_collector.drenar_minutos`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flush_books

`app/scalp_collector.py:832` · clave completa `app.scalp_collector.flush_books`

**Radio exacto: 14 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 14 rutas · **exacto**

Escribe **ella misma**: `orderbook_snapshot`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/price-barriers`](../rutas/api-price-barriers.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/orderbook`](../rutas/api-scalp-orderbook.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/stream`](../rutas/api-stream.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 14). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flush_liquidations

`app/scalp_collector.py:965` · clave completa `app.scalp_collector.flush_liquidations`

**Radio exacto: 14 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 14 rutas · **exacto**

Escribe **ella misma**: `liquidations_realtime`

Y esas tablas las leen:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
- [`/api/liquidation-map`](../rutas/api-liquidation-map.md)
- [`/api/quality/feeds`](../rutas/api-quality-feeds.md)
- [`/api/scalp/alerts`](../rutas/api-scalp-alerts.md)
- [`/api/scalp/execution-cost`](../rutas/api-scalp-execution-cost.md)
- [`/api/scalp/liquidation-levels`](../rutas/api-scalp-liquidation-levels.md)
- [`/api/scalp/liquidations`](../rutas/api-scalp-liquidations.md)
- [`/api/scalp/summary`](../rutas/api-scalp-summary.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 14). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## handle_binance

`app/scalp_collector.py:1055` · clave completa `app.scalp_collector.handle_binance`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## handle_bybit

`app/scalp_collector.py:1247` · clave completa `app.scalp_collector.handle_bybit`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## main

`app/scalp_collector.py:1586` · clave completa `app.scalp_collector.main`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 0 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## mark_exchange_disconnected

`app/scalp_collector.py:624` · clave completa `app.scalp_collector.mark_exchange_disconnected`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## persist_liquidation_feed_state

`app/scalp_collector.py:463` · clave completa `app.scalp_collector.persist_liquidation_feed_state`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## reset_liquidation_feed_health

`app/scalp_collector.py:604` · clave completa `app.scalp_collector.reset_liquidation_feed_health`

**Radio exacto: 0 rutas** de 68 · **cota superior: 19** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 19 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (19 contra 0). Parte de la diferencia puede entrar por un bucle
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

**19 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

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
- [`/api/stream`](../rutas/api-stream.md)
- [`/api/structure`](../rutas/api-structure.md)
- [`/metrics`](../rutas/metrics.md)

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## segundos_cubiertos

`app/scalp_collector.py:673` · clave completa `app.scalp_collector.segundos_cubiertos`

**Radio exacto: 0 rutas** de 68 · **cota superior: 17** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 17 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (17 contra 0). Parte de la diferencia puede entrar por un bucle
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

**17 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/ai/context`](../rutas/api-ai-context.md)
- [`/api/ai/context/bundle`](../rutas/api-ai-context-bundle.md)
- [`/api/dashboard/state`](../rutas/api-dashboard-state.md)
- [`/api/data-confidence`](../rutas/api-data-confidence.md)
- [`/api/desk/state`](../rutas/api-desk-state.md)
- [`/api/hypothesis`](../rutas/api-hypothesis.md)
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

`app/scalp_collector.py:580` · clave completa `app.scalp_collector.persist_liquidation_event_loss`

**Radio exacto: 0 rutas** de 68 · **cota superior: 7** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 7 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (7 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `pipeline_heartbeat` — la escribe `app.db.heartbeat_shard`

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

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

