# `GET /api/daily`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `daily` · `app/api.py:1946` (cuerpo hasta la 2027) · decorador en la linea 1945.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `days` | `Annotated[int, Query(ge=2, le=730)]` | `60` | no |
| `through_session_date` | `date | None` | `None` | no |
| `as_of` | `Annotated[date | None, Query(deprecated=True)]` | `None` | no |

## Campos que publica

11 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage_note` | literal en app/api.py:600 |
| `knowledge_time_replay` | literal en app/api.py:597 |
| `projection_latest_session_date` | literal en app/api.py:593 |
| `quick_read` | literal en app/api.py:598 |
| `rows` | literal en app/api.py:589 |
| `sources` | literal en app/api.py:599 |
| `streak` | literal en app/api.py:587 |
| `streak_source` | literal en app/api.py:588 |
| `symbol` | literal en app/api.py:586 |
| `temporal_semantics` | literal en app/api.py:596 |
| `through_session_date` | literal en app/api.py:590 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
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

- `required`

## Funciones que la componen

13 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._session_window` — `app/api.py:448`
- `app.api.daily_data` — `app/api.py:494`
- `app.api.mask_gapped_series_rows` — `app/api.py:239`
- `app.api.validate_symbol` — `app/api.py:222`
- `app.data_gaps.declared_gap_windows` — `app/data_gaps.py:197`

<details><summary>Alcanzables de forma indirecta (8)</summary>

- `app.api.records` — `app/api.py:235`
- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.interpretation.daily_flow_read` — `app/interpretation.py:208`
- `app.interpretation.number` — `app/interpretation.py:10`
- `app.metrics.session_bounds` — `app/metrics.py:31`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `Query`
- `app.state.pool.acquire`
- `fin.astimezone`
- `inicio.astimezone`
- `max`
- `min`
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 400 | PIT replay is not supported by /api/daily; use through_session_date to limit the current mutable projection | `app/api.py:1953` | el propio handler |
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K02-cobertura-hueco.sh:66`, `harness/checks/K03-hueco-declarado.sh:161`, `harness/checks/K03-hueco-declarado.sh:164`, `harness/checks/K43-foto-unica.sh:119` _(+1)_ | `harness/checks/K03-hueco-declarado.sh:8`, `harness/checks/K03-hueco-declarado.sh:15`, `harness/checks/K03-hueco-declarado.sh:153`, `harness/checks/K03-hueco-declarado.sh:165` _(+1)_ |
| **panel** | `static/app.js:1557`, `static/app.js:1625`, `static/app.js:1722` | — |
| **readme** | — | `README.md:70`, `README.md:90`, `README.md:409` |
| **tests** | `tests/test_dashboard_presentation.py:83` | `tests/test_data_gaps.py:128` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **3** — pide ['as_of']: el operador elige el momento.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `knowledge_time_replay`
- `projection_latest_session_date`
- `through_session_date`

## Capa DECLARADA

**Declarada** en [`declarada/api-daily.md`](../declarada/api-daily.md) — pregunta del trader,
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
| `app.metrics.session_bounds` | 2 | **0** | 51 ↑ | **2** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | **0** | 14 ↑ | **20** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.api.mask_gapped_series_rows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.declared_gap_windows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.daily_data` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.interpretation.daily_flow_read` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-interpretation.md) |
| `app.api._session_window` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-api.md) |
| `app.api.daily` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
