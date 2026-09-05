# `GET /api/data-confidence`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `data_confidence` · `app/api.py:2557` (cuerpo hasta la 2561) · decorador en la linea 2556.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str | None` | `None` | no |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `rows` | literal en app/api.py:2561 |

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
- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `spot_trades_realtime` — `sql/schema.sql:228`, 10 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:376`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:393`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `agg_span`
- `choice`
- `exchanges`
- `now`
- `parts`
- `requested`
- `required`
- `rt_span`

## Funciones que la componen

10 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.ai_context.data_confidence_row` — `app/ai_context.py:497`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Alcanzables de forma indirecta (8)</summary>

- `app.ai_context.quality_score` — `app/ai_context.py:585`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.db.required_heartbeat_failures` — `app/db.py:110`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._flow_windows` — `app/scalp_logic.py:2431`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`
- `app.scalp_logic.spot_flow_windows` — `app/scalp_logic.py:2609`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`
- `list`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
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
| `app.scalp_logic.as_float` | 37 | 9 | **44** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | 10 | **32** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | 14 | **31** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._flow_windows` | 13 | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.spot_flow_windows` | 13 | 0 | **13** | [impacto](../impacto/app-scalp_logic.md) |
| `app.db.required_heartbeat_failures` | 4 | 7 | **7** | [impacto](../impacto/app-db.md) |
| `app.ai_context.data_confidence_row` | 3 | 0 | **3** | [impacto](../impacto/app-ai_context.md) |
| `app.ai_context.quality_score` | 3 | 0 | **3** | [impacto](../impacto/app-ai_context.md) |
| `app.api.data_confidence` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
