# `GET /api/external-macro`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `external_macro_endpoint` · `app/api.py:2388` (cuerpo hasta la 2394) · decorador en la linea 2387.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `alignment` | asignado en app/external_macro.py:481 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por dict(), que no se puede seguir
- devuelve la variable 'context', cuyo contenido no se resuelve estaticamente

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
- `external_macro_observation` — `sql/schema.sql:1320`, 5 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:601`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:622`
- `macro_event` — `sql/schema.sql:1331`, 6 columnas
  - la llena `app.external_macro.refresh_external_macro` (INSERT) — `app/external_macro.py:612`
  - la llena `app.external_macro.refresh_external_macro` (DELETE) — `app/external_macro.py:624`
- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:184`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_cov`
- `agg_span`
- `c0.agg_hi`
- `choice`
- `choice1`
- `edges`
- `exchanges`
- `parts`
- `requested`
- `required`
- `rt_span`
- `source`
- `ts`

## Funciones que la componen

52 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.external_macro.align_with_internal` — `app/external_macro.py:463`
- `app.external_macro.external_macro_context` — `app/external_macro.py:485`
- `app.scalp_logic.swing_score` — `app/scalp_logic.py:6644`

<details><summary>Alcanzables de forma indirecta (48)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.external_macro._direction` — `app/external_macro.py:204`
- `app.external_macro._metric` — `app/external_macro.py:219`
- `app.external_macro._pct_change` — `app/external_macro.py:198`
- `app.external_macro._pillar` — `app/external_macro.py:266`
- `app.external_macro._state` — `app/external_macro.py:211`
- `app.external_macro.build_external_macro_context` — `app/external_macro.py:271`
- `app.metrics.cobertura_suficiente` — `app/metrics.py:44`
- `app.metrics.current_nyse_start` — `app/metrics.py:52`
- `app.metrics.optional_finite` — `app/metrics.py:82`
- `app.scalp_logic._atr` — `app/scalp_logic.py:3239`
- `app.scalp_logic._beta` — `app/scalp_logic.py:3619`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3633`
- `app.scalp_logic._classify_passive` — `app/scalp_logic.py:6158`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:965`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1899`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:975`
- `app.scalp_logic._dsr` — `app/scalp_logic.py:2426`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2624`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2654`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1889`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4444`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4414`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4426`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4625`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1861`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3606`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3875`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4541`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1870`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1232`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3598`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2377`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2363`
- `app.scalp_logic._tr_series` — `app/scalp_logic.py:3228`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.bars_incomplete_inside` — `app/scalp_logic.py:1303`
- `app.scalp_logic.compute_swing_score` — `app/scalp_logic.py:6493`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3654`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4793`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1939`
- `app.scalp_logic.passive_flow` — `app/scalp_logic.py:6191`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2844`
- `app.scalp_logic.structure_detail` — `app/scalp_logic.py:2434`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6319`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3912`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`
- `bool`

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
| **checks** | `harness/checks/K43-foto-unica.sh:151`, `harness/checks/K43-foto-unica.sh:209` | `harness/checks/K20-cincoxx.sh:2` |
| **panel-sobre** | `static/js/07-decision-y-ciclos.js:220`, `static/js/07-decision-y-ciclos.js:433` | — |
| **tests** | `tests/js/mesa_f12a.test.js:174`, `tests/test_dashboard_layout.py:134`, `tests/test_deploy_wrapper.py:268` | `tests/test_dashboard_layout.py:130` |

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
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.swing_score` | 2 | **0** | 48 ↑ | **2** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 19 | **0** | 15 ↑ | **19** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 16 | **0** | 15 ↑ | **16** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.cobertura_suficiente` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
| `app.metrics.optional_finite` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
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
| _… y 28 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
