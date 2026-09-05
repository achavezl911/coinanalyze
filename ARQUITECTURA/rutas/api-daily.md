# `GET /api/daily`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `daily` · `app/api.py:1923` (cuerpo hasta la 2004) · decorador en la linea 1922.

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
| `coverage_note` | literal en app/api.py:599 |
| `knowledge_time_replay` | literal en app/api.py:596 |
| `projection_latest_session_date` | literal en app/api.py:592 |
| `quick_read` | literal en app/api.py:597 |
| `rows` | literal en app/api.py:588 |
| `sources` | literal en app/api.py:598 |
| `streak` | literal en app/api.py:586 |
| `streak_source` | literal en app/api.py:587 |
| `symbol` | literal en app/api.py:585 |
| `temporal_semantics` | literal en app/api.py:595 |
| `through_session_date` | literal en app/api.py:589 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
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

- `app.api._session_window` — `app/api.py:447`
- `app.api.daily_data` — `app/api.py:493`
- `app.api.mask_gapped_series_rows` — `app/api.py:238`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.data_gaps.declared_gap_windows` — `app/data_gaps.py:197`

<details><summary>Alcanzables de forma indirecta (8)</summary>

- `app.api.records` — `app/api.py:234`
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
| 400 | PIT replay is not supported by /api/daily; use through_session_date to limit the current mutable projection | `app/api.py:1930` | el propio handler |
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

Radio por tabla calculado **hasta k=2**; lo que este mas arriba **no se afirma**.

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | por tabla | total | detalle |
|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.metrics.session_bounds` | 2 | 51 | **51** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic.as_float` | 37 | 9 | **44** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | 14 | **31** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | 7 | **28** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.interpretation.number` | 13 | 3 | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.api.mask_gapped_series_rows` | 7 | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.declared_gap_windows` | 7 | 0 | **7** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.daily_data` | 3 | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.interpretation.daily_flow_read` | 3 | 0 | **3** | [impacto](../impacto/app-interpretation.md) |
| `app.api._session_window` | 2 | 0 | **2** | [impacto](../impacto/app-api.md) |
| `app.api.daily` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
