# `GET /api/profile`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `trading_profile` · `app/api.py:1759` (cuerpo hasta la 1775) · decorador en la linea 1758.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `profile` | `str` | `'intradia'` | no |

## Campos que publica

14 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/api.py:1773 |
| `bias` | literal en app/scalp_logic.py:5027 |
| `confidence` | literal en app/scalp_logic.py:5029 |
| `contradictions` | literal en app/scalp_logic.py:5033 |
| `coverage_pct` | literal en app/scalp_logic.py:5030 |
| `invalidation` | literal en app/scalp_logic.py:5039 |
| `layers` | literal en app/scalp_logic.py:5031 |
| `missing_data` | literal en app/scalp_logic.py:5034 |
| `net_score` | literal en app/scalp_logic.py:5028 |
| `profile` | literal en app/scalp_logic.py:5025 |
| `profile_label` | literal en app/scalp_logic.py:5026 |
| `reference_only` | literal en app/scalp_logic.py:5032 |
| `symbol` | literal en app/api.py:1772 |
| `weights_note` | literal en app/scalp_logic.py:5035 |

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
- `metric_baseline` — `sql/schema.sql:1351`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:824`
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

32 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4657`
- `app.scalp_logic.profile_view` — `app/scalp_logic.py:4872`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`
- `app.scalp_logic.trend_matrix` — `app/scalp_logic.py:6319`

<details><summary>Alcanzables de forma indirecta (27)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.metrics.cobertura_suficiente` — `app/metrics.py:44`
- `app.metrics.current_nyse_start` — `app/metrics.py:52`
- `app.metrics.optional_finite` — `app/metrics.py:82`
- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:965`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:975`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._flow_bias` — `app/scalp_logic.py:4859`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2624`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2609`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2617`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2654`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4444`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4414`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4426`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4625`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4541`
- `app.scalp_logic._resample_highs_lows` — `app/scalp_logic.py:1232`
- `app.scalp_logic._structure_from_swings` — `app/scalp_logic.py:2377`
- `app.scalp_logic._swings` — `app/scalp_logic.py:2363`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:139`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4793`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2915`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:163`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2854`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2844`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (4)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `app.state.pool.acquire`
- `as_of.isoformat`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |
| 422 | — | `app/api.py:1763` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K31-cubos.py:62`, `harness/checks/K43-foto-unica.sh:44`, `harness/checks/K43-foto-unica.sh:118`, `harness/checks/K43-foto-unica.sh:251` _(+2)_ |
| **panel** | — | `static/js/04-flujo-y-libro.js:111` |
| **tests** | `tests/test_v150_desk_snapshot.py:130` | — |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['profile', 'symbol']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**Declarada** en [`declarada/api-profile.md`](../declarada/api-profile.md) — pregunta del trader,
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
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
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
| `app.scalp_logic.trend_matrix` | 8 | **0** | 3 ↑ | **8** | [impacto](../impacto/app-scalp_logic.md) |
| _… y 8 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
