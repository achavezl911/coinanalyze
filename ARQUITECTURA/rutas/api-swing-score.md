# `GET /api/swing-score`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `swing_score_endpoint` · `app/api.py:2294` (cuerpo hasta la 2297) · decorador en la linea 2293.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

16 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:6660 |
| `as_of_semantics` | literal en app/scalp_logic.py:6661 |
| `bias` | literal en app/scalp_logic.py:6625 |
| `components` | literal en app/scalp_logic.py:6635 |
| `conflicts` | literal en app/scalp_logic.py:6634 |
| `conviction` | literal en app/scalp_logic.py:6627 |
| `evidence_coverage_pct` | literal en app/scalp_logic.py:6631 |
| `horizon` | literal en app/scalp_logic.py:6636 |
| `long_share_pct` | literal en app/scalp_logic.py:6628 |
| `measured_weight` | literal en app/scalp_logic.py:6632 |
| `neutral_share_pct` | literal en app/scalp_logic.py:6630 |
| `note` | literal en app/scalp_logic.py:6637 |
| `score` | literal en app/scalp_logic.py:6626 |
| `short_share_pct` | literal en app/scalp_logic.py:6629 |
| `symbol` | literal en app/scalp_logic.py:6659 |
| `total_weight` | literal en app/scalp_logic.py:6633 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1039`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `data_gap` — `sql/schema.sql:1419`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1104`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1255`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1274`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1323`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:332`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:594`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:673`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:697`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:774`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:774`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:872`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:872`
  - la llena `app.libro.declara_hueco` (UPDATE) — `app/libro.py:792`
  - la llena `app.orderflow.declara_hueco` (UPDATE) — `app/orderflow.py:508`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `c0.agg_hi`
- `choice`
- `edges`
- `exchanges`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

42 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.swing_score` — `app/scalp_logic.py:6645`

<details><summary>Alcanzables de forma indirecta (40)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:118`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._atr` — `app/scalp_logic.py:3240`
- `app.scalp_logic._beta` — `app/scalp_logic.py:3620`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3634`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:6159`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1894`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2421`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2586`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2619`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2644`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1884`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4445`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4415`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4427`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4626`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1856`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3607`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3876`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4542`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1865`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1227`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3599`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2372`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2358`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:3229`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.bars_incomplete_inside` — `app/scalp_logic.py:1298`
- `app.scalp_logic.compute_swing_score` — `app/scalp_logic.py:6494`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3655`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4794`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1934`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:6192`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2592`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2843`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2429`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6320`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3913`

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
| **checks** | `harness/checks/K43-foto-unica.sh:156`, `harness/checks/K43-foto-unica.sh:219` | — |
| **panel-sobre** | `static/js/07-decision-y-ciclos.js:216`, `static/js/07-decision-y-ciclos.js:356` | — |

**La llama el panel: es superficie de producto.**

**Pero NO con una peticion propia:** su dato llega dentro de `/api/ai/context`,
en la clave que `K43` le declara en su tabla `PAREJAS`. Al depurar eso importa:
**no busques una peticion suya en el log de nginx**, no la hay -la del sobre las
trae todas-, y su instante es el `generated_at` del sobre y no uno propio.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `as_of_semantics`

## Capa DECLARADA

**Declarada** en [`declarada/api-swing-score.md`](../declarada/api-swing-score.md) — pregunta del trader,
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
| `app.scalp_logic.swing_score` | 2 | **0** | 48 ↑ | **2** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 19 | **0** | 15 ↑ | **19** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._resample_highs_lows` | 15 | **0** | 0 | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_coverage_reason` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_and_baseline` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_threshold_seconds` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_too_large` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_change_pct` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._realtime_flow` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_from_swings` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._swings` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.flow_confirmation` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._atr` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._tr_series` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.structure_detail` | 8 | **0** | 3 ↑ | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.trend_matrix` | 8 | **0** | 3 ↑ | **8** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 18 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
