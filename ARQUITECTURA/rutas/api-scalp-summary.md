# `GET /api/scalp/summary`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_summary` · `app/api.py:1531` (cuerpo hasta la 1535) · decorador en la linea 1530.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

67 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `absorption` | literal en app/scalp_logic.py:919 |
| `absorption_context` | literal en app/scalp_logic.py:921 |
| `absorption_context.band` | literal en app/scalp_logic.py:155 |
| `absorption_context.reference` | literal en app/scalp_logic.py:159 |
| `absorption_context.robust_z` | literal en app/scalp_logic.py:156 |
| `absorption_context.sample_count` | literal en app/scalp_logic.py:158 |
| `absorption_context.status` | literal en app/scalp_logic.py:157 |
| `absorption_context.threshold_source` | asignado en app/scalp_logic.py:724 |
| `absorption_delta_ratio` | literal en app/scalp_logic.py:920 |
| `basis_bps` | literal en app/scalp_logic.py:871 |
| `basis_detail` | literal en app/scalp_logic.py:873 |
| `basis_detail.basis_bps` | asignado en app/scalp_logic.py:292 |
| `basis_detail.reason` | asignado en app/scalp_logic.py:287 |
| `basis_detail.status` | asignado en app/scalp_logic.py:286 |
| `basis_status` | literal en app/scalp_logic.py:872 |
| `book_lag_seconds` | literal en app/scalp_logic.py:875 |
| `book_status` | literal en app/scalp_logic.py:874 |
| `confidence` | literal en app/scalp_logic.py:851 |
| `diff_3m` | literal en app/scalp_logic.py:859 |
| `evidence_coverage_pct` | literal en app/scalp_logic.py:867 |
| `expected_weight` | literal en app/scalp_logic.py:866 |
| `fut_delta_1m` | literal en app/scalp_logic.py:853 |
| `fut_delta_3m` | literal en app/scalp_logic.py:854 |
| `fut_price` | literal en app/scalp_logic.py:869 |
| `fut_volume_1m` | literal en app/scalp_logic.py:855 |
| `imbalance_l1` | literal en app/scalp_logic.py:878 |
| `imbalance_l10` | literal en app/scalp_logic.py:880 |
| `imbalance_l5` | literal en app/scalp_logic.py:879 |
| `liquidation_feed_health` | literal en app/scalp_logic.py:889 |
| `liquidations_measured` | literal en app/scalp_logic.py:887 |
| `liquidations_window` | literal en app/scalp_logic.py:888 |
| `long_liq_5m` | literal en app/scalp_logic.py:883 |
| `long_score` | literal en app/scalp_logic.py:848 |
| `measured_weight` | literal en app/scalp_logic.py:865 |
| `missing_components` | literal en app/scalp_logic.py:868 |
| `oi_chg_15m_pct` | literal en app/scalp_logic.py:898 |
| `oi_contributes_direction` | literal en app/scalp_logic.py:912 |
| `oi_directional_support` | literal en app/scalp_logic.py:909 |
| `oi_new_positioning` | literal en app/scalp_logic.py:910 |
| `oi_now` | literal en app/scalp_logic.py:900 |
| `oi_price_quadrant` | literal en app/scalp_logic.py:907 |
| `oi_price_status` | literal en app/scalp_logic.py:916 |
| `oi_reading` | literal en app/scalp_logic.py:908 |
| `oi_start` | literal en app/scalp_logic.py:899 |
| `oi_state` | literal en app/scalp_logic.py:906 |
| `oi_timeframe` | literal en app/scalp_logic.py:911 |
| `oi_window_end` | literal en app/scalp_logic.py:902 |
| `oi_window_samples` | literal en app/scalp_logic.py:903 |
| `oi_window_start` | literal en app/scalp_logic.py:901 |
| `oi_window_status` | literal en app/scalp_logic.py:904 |
| `price_move_15m_coverage` | literal en app/scalp_logic.py:915 |
| `price_move_15m_pct` | literal en app/scalp_logic.py:913 |
| `price_move_15m_status` | literal en app/scalp_logic.py:914 |
| `price_move_3m_pct` | literal en app/scalp_logic.py:876 |
| `reason` | literal en app/scalp_logic.py:852 |
| `session_vwap` | literal en app/scalp_logic.py:917 |
| `short_liq_5m` | literal en app/scalp_logic.py:884 |
| `short_score` | literal en app/scalp_logic.py:849 |
| `spot_delta_3m` | literal en app/scalp_logic.py:856 |
| `spot_fut_divergence_norm` | literal en app/scalp_logic.py:864 |
| `spot_price` | literal en app/scalp_logic.py:870 |
| `spread_bps` | literal en app/scalp_logic.py:877 |
| `state` | literal en app/scalp_logic.py:850 |
| `symbol` | literal en app/api.py:1535 |
| `vwap_dist_pct` | literal en app/scalp_logic.py:918 |
| `wall_down_pct` | literal en app/scalp_logic.py:882 |
| `wall_up_pct` | literal en app/scalp_logic.py:881 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

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
- `spot_trades_realtime` — `sql/schema.sql:329`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:404`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:421`

## Funciones que la componen

24 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:633`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:330`

<details><summary>Alcanzables de forma indirecta (21)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:49`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:548`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:99`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:595`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:571`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:507`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:519`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:563`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:73`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:139`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:236`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:198`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:163`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:297`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:322`
- `app.setups._sign` — `app/setups.py:95`
- `app.setups.classify_oi` — `app/setups.py:162`
- `app.setups.oi_price_reading` — `app/setups.py:228`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K102-decide-lo-primero.sh:40`, `harness/checks/K102-mesa.py:884`, `harness/checks/K102-sobre-plantado.py:178` |

**Nadie la llama.** Sus 3 rastros son todos MENCION -comentario,
docstring o documento-. Es la forma del patron que en esta casa se ha repetido
nueve veces: algo de lo que se habla y nadie ejecuta. **Merece una mirada.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `book_lag_seconds`
- `liquidations_window`
- `oi_start`
- `oi_window_end`
- `oi_window_samples`
- `oi_window_start`
- `oi_window_status`

## Capa DECLARADA

**Declarada** en [`declarada/api-scalp-summary.md`](../declarada/api-scalp-summary.md) — pregunta del trader,
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
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 10 | **0** | 25 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
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
| `app.scalp_logic._as_utc_datetime` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._coverage_status` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._utc_now` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups._sign` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-setups.md) |
| `app.api.scalp_summary` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
