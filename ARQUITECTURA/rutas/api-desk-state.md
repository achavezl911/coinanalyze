# `GET /api/desk/state`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `desk_state` · `app/api.py:1665` (cuerpo hasta la 1772) · decorador en la linea 1664.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `profile` | `str` | `'intradia'` | no |
| `direction` | `str | None` | `None` | no |
| `setup` | `str` | `'ninguno'` | no |

## Campos que publica

26 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:1746 |
| `components` | literal en app/api.py:1750 |
| `components.data_quality` | literal en app/api.py:1731 |
| `components.delta_matrix` | literal en app/api.py:1727 |
| `components.hypothesis` | literal en app/api.py:1729 |
| `components.profile` | literal en app/api.py:1728 |
| `components.reference_levels` | literal en app/api.py:1736 |
| `components.scalp` | literal en app/api.py:1730 |
| `components.trend_matrix` | literal en app/api.py:1726 |
| `direction` | literal en app/api.py:1748 |
| `note` | literal en app/api.py:1767 |
| `partial` | literal en app/api.py:1761 |
| `partial.profile_coverage_pct` | literal en app/api.py:1765 |
| `partial.profile_missing_data` | literal en app/api.py:1763 |
| `partial.scalp_coverage_pct` | literal en app/api.py:1764 |
| `partial.scalp_missing_components` | literal en app/api.py:1762 |
| `profile` | literal en app/api.py:1747 |
| `setup` | literal en app/api.py:1749 |
| `source_timestamps` | literal en app/api.py:1751 |
| `source_timestamps.basis_status` | literal en app/api.py:1754 |
| `source_timestamps.book_lag_seconds` | literal en app/api.py:1752 |
| `source_timestamps.book_status` | literal en app/api.py:1753 |
| `source_timestamps.collectors` | literal en app/api.py:1756 |
| `source_timestamps.liquidations_last_event_age_s` | literal en app/api.py:1757 |
| `source_timestamps.liquidations_measured` | literal en app/api.py:1755 |
| `symbol` | literal en app/api.py:1745 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1123`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `data_gap` — `sql/schema.sql:1496`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1109`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1260`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1279`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1334`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:337`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:599`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:678`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:702`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:779`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:779`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:877`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:877`
  - la llena `app.libro.declara_hueco` (UPDATE) — `app/libro.py:792`
  - la llena `app.orderflow.declara_hueco` (UPDATE) — `app/orderflow.py:508`
- `futures_trades_agg` — `sql/schema.sql:374`, 9 columnas
  - la llena `app.scalp_collector.cleanup_expired_rows` (DELETE) — `app/scalp_collector.py:1629`
  - la llena `app.scalp_collector._write_combined_minute` (INSERT) — `app/scalp_collector.py:875`
- `futures_trades_realtime` — `sql/schema.sql:357`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:846`
- `liquidations_realtime` — `sql/schema.sql:440`, 9 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:75`
- `market_feed_health` — `sql/schema.sql:1402`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1351`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:824`
- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:184`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
- `orderbook_snapshot` — `sql/schema.sql:388`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:918`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:974`
- `pipeline_heartbeat` — `sql/schema.sql:1370`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `spot_trades_agg` — `sql/schema.sql:299`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:681`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:277`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:298`
- `spot_trades_realtime` — `sql/schema.sql:329`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:404`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:421`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_cov`
- `agg_span`
- `c0.agg_hi`
- `choice`
- `choice1`
- `edges`
- `exchanges`
- `now`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

85 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:633`
- `app.scalp_logic.data_quality` — `app/scalp_logic.py:4363`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4674`
- `app.scalp_logic.hypothesis_evidence` — `app/scalp_logic.py:5081`
- `app.scalp_logic.price_barriers` — `app/scalp_logic.py:1309`
- `app.scalp_logic.profile_view` — `app/scalp_logic.py:4889`
- `app.scalp_logic.reference_levels` — `app/scalp_logic.py:3521`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:330`
- `app.scalp_logic.setup_confirmation_bundle` — `app/scalp_logic.py:2523`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2434`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6336`
- `app.setups.build_setup_context` — `app/setups.py:1174`

<details><summary>Alcanzables de forma indirecta (71)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.interpretation._barrier_candidates` — `app/interpretation.py:684`
- `app.interpretation._barrier_zones` — `app/interpretation.py:779`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.interpretation.price_barrier_read` — `app/interpretation.py:877`
- `app.metrics.cobertura_suficiente` — `app/metrics.py:44`
- `app.metrics.current_nyse_start` — `app/metrics.py:52`
- `app.metrics.optional_finite` — `app/metrics.py:82`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:548`
- `app.scalp_logic._atr` — `app/scalp_logic.py:3256`
- `app.scalp_logic._banda` — `app/scalp_logic.py:5421`
- `app.scalp_logic._bps` — `app/scalp_logic.py:5347`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:99`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:595`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:965`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:975`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:571`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2426`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:507`
- `app.scalp_logic._flow_bias` — `app/scalp_logic.py:4876`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2624`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2609`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2617`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2654`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4461`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4431`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4443`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:519`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:563`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4642`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4558`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1232`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2377`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2363`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:3245`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:73`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.bars_incomplete_inside` — `app/scalp_logic.py:1303`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:139`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:236`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:198`
- `app.scalp_logic.coherencia_del_plan` — `app/scalp_logic.py:5354`
- `app.scalp_logic.execution_assessment` — `app/scalp_logic.py:5430`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4810`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2932`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:163`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:297`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:322`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2871`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2861`
- `app.setups._apertura` — `app/setups.py:814`
- `app.setups._bars_closed_beyond` — `app/setups.py:872`
- `app.setups._breakout_frontier` — `app/setups.py:757`
- `app.setups._gap_in` — `app/setups.py:865`
- `app.setups._last_pivots` — `app/setups.py:991`
- `app.setups._level_defended` — `app/setups.py:1067`
- `app.setups._norm_bars` — `app/setups.py:793`
- `app.setups._obs` — `app/setups.py:732`
- `app.setups._pullback` — `app/setups.py:998`
- `app.setups._retest_done` — `app/setups.py:955`
- `app.setups._returned_inside` — `app/setups.py:911`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups._structure_event` — `app/setups.py:674`
- `app.setups._tolerance` — `app/setups.py:778`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.episodio` — `app/setups.py:842`
- `app.setups.evaluate_setup` — `app/setups.py:1312`
- `app.setups.oi_price_reading` — `app/setups.py:228`
- `app.setups.setup_observables` — `app/setups.py:1130`
- `app.setups.split_hypothesis` — `app/setups.py:88`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `app.state.pool.acquire`
- `as_of.isoformat`
- `componentes.values`
- `isinstance`
- `quality.get`
- `scalp.get`
- `view.get`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |
| 422 | — | `app/api.py:1685` | el propio handler |
| 422 | — | `app/api.py:1689` | el propio handler |
| 422 | — | `app/api.py:1693` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:165` | — |
| **panel** | `static/js/07-decision-y-ciclos.js:231` | — |
| **tests** | `tests/test_v150_desk_snapshot.py:132` | `tests/test_pr22_cvd_semantics.py:177` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['direction', 'profile', 'setup', 'symbol']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `source_timestamps.book_lag_seconds`
- `source_timestamps.liquidations_last_event_age_s`

## Capa DECLARADA

**Declarada** en [`declarada/api-desk-state.md`](../declarada/api-desk-state.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 19 | **0** | 15 ↑ | **19** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.cobertura_suficiente` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
| `app.metrics.optional_finite` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic.basis_quality` | 11 | **0** | 11 ↑ | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 11 | **0** | 11 ↑ | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 10 | **0** | 11 ↑ | **10** | [impacto](../impacto/app-setups.md) |
| `app.interpretation.number` | 14 | **0** | 3 ↑ | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic._resample_highs_lows` | 15 | **0** | 0 | **15** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 61 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
