# `GET /api/scalp/summary`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_summary` · `app/api.py:1085` (cuerpo hasta la 1089) · decorador en la linea 1084.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

58 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `absorption` | literal en app/scalp_logic.py:914 |
| `absorption_context` | literal en app/scalp_logic.py:916 |
| `absorption_delta_ratio` | literal en app/scalp_logic.py:915 |
| `basis_bps` | literal en app/scalp_logic.py:866 |
| `basis_detail` | literal en app/scalp_logic.py:868 |
| `basis_status` | literal en app/scalp_logic.py:867 |
| `book_lag_seconds` | literal en app/scalp_logic.py:870 |
| `book_status` | literal en app/scalp_logic.py:869 |
| `confidence` | literal en app/scalp_logic.py:846 |
| `diff_3m` | literal en app/scalp_logic.py:854 |
| `evidence_coverage_pct` | literal en app/scalp_logic.py:862 |
| `expected_weight` | literal en app/scalp_logic.py:861 |
| `fut_delta_1m` | literal en app/scalp_logic.py:848 |
| `fut_delta_3m` | literal en app/scalp_logic.py:849 |
| `fut_price` | literal en app/scalp_logic.py:864 |
| `fut_volume_1m` | literal en app/scalp_logic.py:850 |
| `imbalance_l1` | literal en app/scalp_logic.py:873 |
| `imbalance_l10` | literal en app/scalp_logic.py:875 |
| `imbalance_l5` | literal en app/scalp_logic.py:874 |
| `liquidation_feed_health` | literal en app/scalp_logic.py:884 |
| `liquidations_measured` | literal en app/scalp_logic.py:882 |
| `liquidations_window` | literal en app/scalp_logic.py:883 |
| `long_liq_5m` | literal en app/scalp_logic.py:878 |
| `long_score` | literal en app/scalp_logic.py:843 |
| `measured_weight` | literal en app/scalp_logic.py:860 |
| `missing_components` | literal en app/scalp_logic.py:863 |
| `oi_chg_15m_pct` | literal en app/scalp_logic.py:893 |
| `oi_contributes_direction` | literal en app/scalp_logic.py:907 |
| `oi_directional_support` | literal en app/scalp_logic.py:904 |
| `oi_new_positioning` | literal en app/scalp_logic.py:905 |
| `oi_now` | literal en app/scalp_logic.py:895 |
| `oi_price_quadrant` | literal en app/scalp_logic.py:902 |
| `oi_price_status` | literal en app/scalp_logic.py:911 |
| `oi_reading` | literal en app/scalp_logic.py:903 |
| `oi_start` | literal en app/scalp_logic.py:894 |
| `oi_state` | literal en app/scalp_logic.py:901 |
| `oi_timeframe` | literal en app/scalp_logic.py:906 |
| `oi_window_end` | literal en app/scalp_logic.py:897 |
| `oi_window_samples` | literal en app/scalp_logic.py:898 |
| `oi_window_start` | literal en app/scalp_logic.py:896 |
| `oi_window_status` | literal en app/scalp_logic.py:899 |
| `price_move_15m_coverage` | literal en app/scalp_logic.py:910 |
| `price_move_15m_pct` | literal en app/scalp_logic.py:908 |
| `price_move_15m_status` | literal en app/scalp_logic.py:909 |
| `price_move_3m_pct` | literal en app/scalp_logic.py:871 |
| `reason` | literal en app/scalp_logic.py:847 |
| `session_vwap` | literal en app/scalp_logic.py:912 |
| `short_liq_5m` | literal en app/scalp_logic.py:879 |
| `short_score` | literal en app/scalp_logic.py:844 |
| `spot_delta_3m` | literal en app/scalp_logic.py:851 |
| `spot_fut_divergence_norm` | literal en app/scalp_logic.py:859 |
| `spot_price` | literal en app/scalp_logic.py:865 |
| `spread_bps` | literal en app/scalp_logic.py:872 |
| `state` | literal en app/scalp_logic.py:845 |
| `symbol` | literal en app/api.py:1089 |
| `vwap_dist_pct` | literal en app/scalp_logic.py:913 |
| `wall_down_pct` | literal en app/scalp_logic.py:877 |
| `wall_up_pct` | literal en app/scalp_logic.py:876 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `market_feed_health` — `sql/schema.sql:1318`, 7 columnas
  - la llena `app.db.mark_feed_connected` (INSERT) — `app/db.py:580`
  - la llena `app.db._mark_feed_unhealthy` (INSERT) — `app/db.py:609`
  - la llena `app.db._mark_feed_shard_health` (INSERT) — `app/db.py:706`
- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:780`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:376`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:393`

## Funciones que la componen

24 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.compute_scalp_summary` — `app/scalp_logic.py:628`
- `app.scalp_logic.scalp_context` — `app/scalp_logic.py:325`

<details><summary>Alcanzables de forma indirecta (21)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._as_utc_datetime` — `app/scalp_logic.py:543`
- `app.scalp_logic._closed_5m_oi_bounds` — `app/scalp_logic.py:94`
- `app.scalp_logic._closed_window_move_pct` — `app/scalp_logic.py:590`
- `app.scalp_logic._coverage_status` — `app/scalp_logic.py:566`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._first_present` — `app/scalp_logic.py:502`
- `app.scalp_logic._liquidation_window_measured` — `app/scalp_logic.py:514`
- `app.scalp_logic._measured_event_sum` — `app/scalp_logic.py:558`
- `app.scalp_logic._utc_now` — `app/scalp_logic.py:68`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:134`
- `app.scalp_logic.basis_quality` — `app/scalp_logic.py:231`
- `app.scalp_logic.classify_absorption` — `app/scalp_logic.py:193`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.scalp_bias_label` — `app/scalp_logic.py:292`
- `app.scalp_logic.score_component` — `app/scalp_logic.py:317`
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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

**NINGUN rastro**, ni llamada ni mencion, en `static/app.js`, `static/index.html`,
`harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo, o una IA por su
nombre-, pero es la forma exacta del patron que en esta casa se ha repetido nueve
veces. **Merece una mirada, no una conclusion.**

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
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 11 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 15 | **0** | 14 ↑ | **15** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.compute_scalp_summary` | 9 | **0** | 24 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_context` | 9 | **0** | 24 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 14 | **0** | 10 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 13 | **0** | 10 ↑ | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.basis_quality` | 10 | **0** | 10 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.classify_absorption` | 10 | **0** | 10 ↑ | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_5m_oi_bounds` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._closed_window_move_pct` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._first_present` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._liquidation_window_measured` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._measured_event_sum` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.scalp_bias_label` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.score_component` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups.classify_oi` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-setups.md) |
| `app.setups.oi_price_reading` | 9 | **0** | 10 ↑ | **9** | [impacto](../impacto/app-setups.md) |
| `app.scalp_logic._as_utc_datetime` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._coverage_status` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._utc_now` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.setups._sign` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-setups.md) |
| `app.api.scalp_summary` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
