# `GET /api/scalp/delta-matrix`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `scalp_delta_matrix` · `app/api.py:1488` (cuerpo hasta la 1513) · decorador en la linea 1487.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

**PENDIENTE · no se ha podido derivar ni un campo.**

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- lista vacia en el literal: no se puede derivar el elemento

Forma de la respuesta segun el AST: lista.

Tipo declarado en la firma: `list[dict[str, Any]]`.

## Tablas que toca

LEE:

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

22 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.delta_matrix` — `app/scalp_logic.py:4657`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`

<details><summary>Alcanzables de forma indirecta (19)</summary>

- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.metrics.cobertura_suficiente` — `app/metrics.py:41`
- `app.metrics.optional_finite` — `app/metrics.py:79`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._flow_coverage_reason` — `app/scalp_logic.py:2624`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2609`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2617`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2654`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4444`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4414`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4426`
- `app.scalp_logic._oi_change_pct` — `app/scalp_logic.py:4625`
- `app.scalp_logic._realtime_flow` — `app/scalp_logic.py:4541`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.baseline_band` — `app/scalp_logic.py:139`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2915`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:163`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2854`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2844`

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
| **checks** | `harness/checks/K43-foto-unica.sh:154`, `harness/checks/K43-foto-unica.sh:214`, `harness/checks/K44-control.bash:113`, `harness/checks/K44-control.bash:279` _(+15)_ | `harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh:79`, `harness/checks/K84-dos-matrices-una-cifra.sh:13` |
| **panel** | `static/js/07-decision-y-ciclos.js:326` | — |
| **tests** | `tests/js/mesa_f12a.test.js:124` | — |

**La llama el panel: es superficie de producto.**

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

**Declarada** en [`declarada/api-scalp-delta-matrix.md`](../declarada/api-scalp-delta-matrix.md) — pregunta del trader,
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
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 15 | **0** | 11 ↑ | **15** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.baseline_band` | 14 | **0** | 11 ↑ | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.cobertura_suficiente` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
| `app.metrics.optional_finite` | 12 | **0** | 9 ↑ | **12** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._flow_coverage_reason` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_and_baseline` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_threshold_seconds` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_too_large` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._oi_change_pct` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._realtime_flow` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_imbalance` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_rate` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.futures_flow_windows` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_con_guarda` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.delta_matrix` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.scalp_delta_matrix` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
