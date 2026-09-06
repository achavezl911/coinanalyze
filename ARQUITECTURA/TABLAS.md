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
| [`signal_observation`](#signal-observation) | 1 | 6 | 0 |
| [`signal_outcome`](#signal-outcome) | 4 | 3 | 0 |
| [`signal_outcome_final_visibility`](#signal-outcome-final-visibility) | 1 | 1 | 0 |
| [`signal_replay_frame`](#signal-replay-frame) | 1 | 1 | 0 |
| [`spot_trades_agg`](#spot-trades-agg) | 3 | 10 | 0 |
| [`spot_trades_realtime`](#spot-trades-realtime) | 2 | 12 | 0 |

## LA COBERTURA · que tablas dicen CUANTO del periodo se observo

**Un lector no puede juzgar una fila sin saber cada cuanto deberia haberla, ni cuanto
del periodo se llego a medir.** Una serie con huecos y una completa se leen igual si la
tabla no lo declara.

Definiciones, escritas antes del recuento:

- **tabla de serie**: su clave incluye una columna de tiempo por bucket (`ts`,
  `bucket`, `observed_minute`, `session_date`).
- **declara cobertura**: tiene una columna que dice **cuanto** del periodo se observo.
- **cuantitativa**: esa columna es un numero, no un booleano. Solo asi se separa
  *"periodo medido a medias"* de *"periodo no medido"*.

| | de 40 tablas del esquema |
|---|---|
| de SERIE | **22** |
| de serie que DECLARAN cobertura cuantitativa | **7** |
| de serie que NO declaran ninguna | **15** |

| tabla | columnas de cobertura |
|---|---|
| `daily_session_agg` | `cvd_fut_2v_minutes`, `session_expected_minutes`, `futures_ohlcv_minutes`, `spot_2v_minutes`, `session_expected_5m_samples`, `oi_5m_samples`, `funding_5m_samples` |
| `futures_trades_agg` | `covered_seconds`, `venue_count` |
| `futures_trades_realtime` | `venue_count` |
| `orderbook_snapshot` | `venue_count` |
| `signal_observation` | `evidence_coverage_pct` |
| `spot_trades_agg` | `covered_seconds`, `venue_count` |
| `spot_trades_realtime` | `venue_count` |

**Las 15 de serie SIN cobertura declarada.** No es un defecto por si mismo
—una tabla de eventos periodicos puede no necesitarla—, pero es lo que impide
distinguir un periodo vacio de uno no medido:

- `daily_verdict`
- `daily_verdict_snapshot`
- `external_api_rate_event`
- `funding_rate`
- `liquidations`
- `liquidations_realtime`
- `long_short_ratio`
- `metrics_snapshot`
- `ohlcv`
- `oi_bybit`
- `open_interest`
- `open_interest_daily`
- `orderbook_depth`
- `predicted_funding_rate`
- `scalp_signal_snapshot`

### Columnas que NO estan en su `CREATE TABLE`

**30 columnas en 6 tablas** se añaden con
`ALTER TABLE ... ADD COLUMN`. Un instrumento que lea solo los `CREATE` no las ve — y
**este generador no las veia hasta F4**: `daily_session_agg` figuraba con 14 columnas
y tiene 37, y entre las que faltaban estaba **`covered_seconds`**, que es justamente
la columna con la que el sistema declara si un minuto se midio entero.

- `daily_session_agg` — 23: `cvd_fut_2v_usd`, `cvd_fut_2v_minutes`, `cvd_diff_2v_usd`, `volume_usd`, `price_high`, `price_low` _(+17)_
- `futures_trades_agg` — 2: `covered_seconds`, `venue_count`
- `futures_trades_realtime` — 1: `venue_count`
- `orderbook_snapshot` — 1: `venue_count`
- `spot_trades_agg` — 2: `covered_seconds`, `venue_count`
- `spot_trades_realtime` — 1: `venue_count`

## LA CADENCIA · cada cuanto escribe quien escribe

**Ninguna tabla de SERIE guarda su cadencia esperada.** Pero *"hay que salir de la
base para averiguarlo"* —que es lo que decia la version anterior de esta seccion— **es
falso, y hay contraejemplo medido**:

```sql
-- sql/schema.sql:1422
expected_cadence interval,          -- en data_gap

-- medido en 140 por el operador:
00:05:00  en 816 filas / 5 feeds
00:01:00  en 435 filas / 1 feed
total 1251 = TODAS las filas de data_gap
```

**`data_gap.expected_cadence` es una fuente de cadencia que ya existe dentro de la**
**base**, y ademas el esquema la usa en una restriccion: `feed_class = 'cadence'` exige
`expected_cadence > 0` y `feed_class = 'event_stream'` exige que sea NULL
(`sql/schema.sql:1443-1446`). O sea que el sistema **ya distingue** un feed con ritmo de
uno de eventos, y lo guarda.

**Su limite, que es lo que la hace parcial y no total:** solo aparecen ahi **los feeds
que han tenido hueco**. Un feed que nunca fallo no tiene fila en `data_gap`, asi que su
cadencia no esta. Por eso las constantes de abajo siguen haciendo falta.

| constante | valor | de `app/config.py` |
|---|---|---|
| `BINANCE_BOOK_FORCE_RECONNECT_SECONDS` | 3600 | |
| `BINANCE_BOOK_MAX_EVENT_LAG_SECONDS` | 10 | |
| `BINANCE_BOOK_STALE_SECONDS` | 15 | |
| `EXTERNAL_MACRO_REFRESH_SECONDS` | 3600 | |
| `INGEST_INTERVAL_SECONDS` | 60 | |
| `SCALP_FLUSH_SECONDS` | 2 | |
| `SCALP_ORDERBOOK_FLUSH_SECONDS` | 2 | |
| `SCALP_SIGNAL_INTERVAL_SECONDS` | 10 | |
| `TRADESTORE_MAX_BUCKET_MINUTES` | 20 | |

Y que bucle duerme con cual:

| funcion | constante | valor | sitio |
|---|---|---|---|
| `app.scalp_collector.flush_books` | `SCALP_ORDERBOOK_FLUSH_SECONDS` | 2 | `app/scalp_collector.py:826` |
| `app.scalp_collector.flush_trades` | `SCALP_FLUSH_SECONDS` | 2 | `app/scalp_collector.py:642` |
| `app.scalp_collector.persist_scalp_signals` | `SCALP_SIGNAL_INTERVAL_SECONDS` | 10 | `app/scalp_collector.py:1352` |

## EL BUCKET CORTO DEL LADO DE LA PARADA · el mismo patron en DOS tablas

**Defecto abierto y medido, y aparece en dos sitios.** Va con su reproduccion y
**no se abre desde aqui**: el sujeto es de produccion.

```
spot_trades_agg, minuto 17:17  ->  covered_seconds = 45   correcto (60 - 15)
spot_trades_agg, minuto 17:16  ->  covered_seconds = 60   y el colector estuvo
                                                          parado sus ultimos 5 s
```

El bucket **AUSENTE** ya se arreglo. El bucket **CORTO del lado de la PARADA** se
sigue escribiendo como completo, y **ese es el caso peor**: la fila existe, K37 la
cuenta como presente, y las derivadas de ese minuto no saben que van cortas. Un
hueco que se ve es un hueco; un minuto que miente que esta completo no lo ve nadie.

**Y afecta a las 2 tablas que declaran cobertura por segundo**: `futures_trades_agg`, `spot_trades_agg`.

`_write_combined_minute` (`app/scalp_collector.py:801-812`) construye la fila
`combined` con **`MIN(covered_seconds)`** de sus dos patas, y `ws_collector.py:284`
hace lo mismo para spot. **El `MIN` es la eleccion correcta** —el minuto combinado
no puede estar mejor cubierto que su peor pata— pero **hereda el defecto**: si una
pata escribe 60 cuando fueron 55, el combinado escribe 60.

**No se arregla en el agregador: se arregla en quien escribe la pata.**

**Reproduccion:** cualquier reinicio cuya **parada** caiga en un minuto distinto al
del **arranque**. El minuto del arranque se cubre bien; el de la parada no.

**Criterio ejecutable, si se decide abrirlo:**

> ROJO si existe algun minuto con `covered_seconds = 60` cuyo intervalo contenga el
> instante de una parada del colector.
> **Control en la misma consulta**: el minuto *siguiente* a esa parada tiene que
> estar ausente o con cobertura baja. Si los dos salieran completos, el sujeto seria
> el registro de paradas y no la cobertura.
> El elegible sale de un instrumento externo: los `Stopped` del journal, no de la
> propia tabla.

## Detalle · quien escribe cada una

### daily_session_agg

`sql/schema.sql:1032`, 37 columnas.

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

`sql/schema.sql:273`, 11 columnas.

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

`sql/schema.sql:256`, 11 columnas.

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

`sql/schema.sql:287`, 19 columnas.

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

**Si cambia el contenido o el esquema de `signal_observation`, estas 6 rutas lo notan:**

- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
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

**Si cambia el contenido o el esquema de `signal_outcome`, estas 3 rutas lo notan:**

- [`/api/dashboard/state`](rutas/api-dashboard-state.md)
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

`sql/schema.sql:198`, 15 columnas.

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

`sql/schema.sql:228`, 11 columnas.

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

