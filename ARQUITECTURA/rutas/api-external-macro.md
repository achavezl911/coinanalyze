# `GET /api/external-macro`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `external_macro_endpoint` · `app/api.py:2150` (cuerpo hasta la 2156) · decorador en la linea 2149.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `alignment` | asignado en app/external_macro.py:433 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por dict(), que no se puede seguir
- devuelve la variable 'context', cuyo contenido no se resuelve estaticamente

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1092`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1243`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1262`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1311`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:322`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:584`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:663`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:687`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
- `external_macro_observation` — `sql/schema.sql:1234`, 5 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:553`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:574`
- `macro_event` — `sql/schema.sql:1245`, 6 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:564`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:576`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
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

48 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:229`
- `app.external_macro.align_with_internal` — `app/external_macro.py:415`
- `app.external_macro.external_macro_context` — `app/external_macro.py:437`
- `app.scalp_logic.swing_score` — `app/scalp_logic.py:6283`

<details><summary>Alcanzables de forma indirecta (44)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.external_macro._direction` — `app/external_macro.py:190`
- `app.external_macro._metric` — `app/external_macro.py:205`
- `app.external_macro._pct_change` — `app/external_macro.py:184`
- `app.external_macro._pillar` — `app/external_macro.py:232`
- `app.external_macro._state` — `app/external_macro.py:197`
- `app.external_macro.build_external_macro_context` — `app/external_macro.py:237`
- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._atr` — `app/scalp_logic.py:2931`
- `app.scalp_logic._beta` — `app/scalp_logic.py:3311`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3325`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:5826`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1785`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:970`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2280`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2403`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2436`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1775`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4113`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4083`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4095`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4287`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1747`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3298`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3544`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4203`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1756`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1197`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3290`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2231`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2217`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:2920`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.compute_swing_score` — `app/scalp_logic.py:6132`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3346`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4461`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1825`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:5859`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2409`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2614`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2288`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:5977`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3581`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`
- `bool`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:142`, `harness/checks/K43-foto-unica.sh:195` | `harness/checks/K20-cincoxx.sh:2` |
| **panel-sobre** | `static/app.js:1637`, `static/app.js:1843` | — |
| **tests** | `tests/test_dashboard_layout.py:121` | `tests/test_dashboard_layout.py:117` |

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

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-external-macro.md`](../declarada/api-external-macro.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 63 | **0** | 0 | **63** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.swing_score` | 2 | **0** | 53 ↑ | **2** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 11 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | **0** | 14 ↑ | **20** | [impacto](../impacto/app-data_gaps.md) |
| `app.metrics.current_nyse_start` | 15 | **0** | 14 ↑ | **15** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._resample_highs_lows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_and_baseline` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_threshold_seconds` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_too_large` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_change_pct` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._realtime_flow` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.flow_confirmation` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._atr` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_from_swings` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._swings` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._tr_series` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.trend_matrix` | 8 | **0** | 3 ↑ | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.structure_detail` | 7 | **0** | 3 ↑ | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._dsr` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 24 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
