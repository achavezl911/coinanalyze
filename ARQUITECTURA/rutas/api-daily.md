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
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:205`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1091`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1242`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1261`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1310`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:321`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:583`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:662`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:686`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:722`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:763`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:792`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:861`

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

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
