# `GET /api/cvd-matrix`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `cvd_matrix_endpoint` · `app/api.py:2130` (cuerpo hasta la 2134) · decorador en la linea 2129.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

18 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3151 |
| `symbol` | literal en app/scalp_logic.py:3150 |
| `window_meta` | literal en app/scalp_logic.py:3153 |
| `window_meta.acceleration_measured` | literal en app/scalp_logic.py:3158 |
| `window_meta.as_of` | literal en app/scalp_logic.py:3154 |
| `window_meta.as_of_semantics` | literal en app/scalp_logic.py:3167 |
| `window_meta.definition` | literal en app/scalp_logic.py:3161 |
| `window_meta.freshness_rule` | literal en app/scalp_logic.py:3165 |
| `window_meta.futures_agg_retention_hours` | literal en app/scalp_logic.py:3164 |
| `window_meta.futures_realtime_retention_hours` | literal en app/scalp_logic.py:3163 |
| `window_meta.independent_confirmations` | literal en app/scalp_logic.py:3157 |
| `window_meta.null_reasons` | literal en app/scalp_logic.py:3166 |
| `window_meta.reset_timezone` | literal en app/scalp_logic.py:3159 |
| `window_meta.sources` | literal en app/scalp_logic.py:3162 |
| `window_meta.venues` | literal en app/scalp_logic.py:3160 |
| `window_meta.window_type` | literal en app/scalp_logic.py:3155 |
| `window_meta.windows_are_nested` | literal en app/scalp_logic.py:3156 |
| `windows` | literal en app/scalp_logic.py:3152 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

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
- `ts`

## Funciones que la componen

17 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:231`
- `app.scalp_logic.cvd_matrix` — `app/scalp_logic.py:2948`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2592`

<details><summary>Alcanzables de forma indirecta (14)</summary>

- `app.config.get_settings` — `app/config.py:291`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.scalp_logic._cvd_src` — `app/scalp_logic.py:2889`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2586`
- `app.scalp_logic._flow_imbalance` — `app/scalp_logic.py:2604`
- `app.scalp_logic._flow_rate` — `app/scalp_logic.py:2612`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2619`
- `app.scalp_logic._gap_and_baseline` — `app/scalp_logic.py:4376`
- `app.scalp_logic._gap_threshold_seconds` — `app/scalp_logic.py:4346`
- `app.scalp_logic._gap_too_large` — `app/scalp_logic.py:4358`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.futures_flow_windows` — `app/scalp_logic.py:2868`
- `app.scalp_logic.spot_con_guarda` — `app/scalp_logic.py:2807`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2797`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:233` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh:170`, `harness/checks/K83-la-ventana-pide-la-fuente-que-no-tiene-el-dato.sh:171` | `harness/checks/K84-dos-matrices-una-cifra.sh:5` |

**No la llama el panel**, pero si 2 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `window_meta`
- `window_meta.acceleration_measured`
- `window_meta.as_of`
- `window_meta.as_of_semantics`
- `window_meta.definition`
- `window_meta.freshness_rule`
- `window_meta.futures_agg_retention_hours`
- `window_meta.futures_realtime_retention_hours`
- `window_meta.independent_confirmations`
- `window_meta.null_reasons`
- `window_meta.reset_timezone`
- `window_meta.sources`
- `window_meta.venues`
- `window_meta.window_type`
- `window_meta.windows_are_nested`

## Capa DECLARADA

**Declarada** en [`declarada/api-cvd-matrix.md`](../declarada/api-cvd-matrix.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 64 | **0** | 0 | **64** | [impacto](../impacto/app-api.md) |
| `app.config.get_settings` | 3 | **0** | 56 ↑ | **3** | [impacto](../impacto/app-config.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 25 | **0** | 12 ↑ | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 21 | **0** | 15 ↑ | **21** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._explicit_as_of` | 26 | **0** | 0 | **26** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_and_baseline` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_threshold_seconds` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._gap_too_large` | 12 | **0** | 0 | **12** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_imbalance` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_rate` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.futures_flow_windows` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_con_guarda` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._cvd_src` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.cvd_matrix` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.cvd_matrix_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
