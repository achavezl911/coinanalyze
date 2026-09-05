# `GET /api/cvd/divergence`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `cvd_divergence` · `app/api.py:797` (cuerpo hasta la 911) · decorador en la linea 796.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'5min'` | no |
| `limit` | `Annotated[int, Query(ge=10, le=3000)]` | `576` | no |

## Campos que publica

4 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:910 |
| `interval` | literal en app/api.py:908 |
| `rows` | literal en app/api.py:909 |
| `symbol` | literal en app/api.py:907 |

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
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `spot_trades_agg` — `sql/schema.sql:198`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `required`

## Funciones que la componen

9 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.historical_interval_value` — `app/api.py:227`
- `app.api.mask_gapped_series_rows` — `app/api.py:238`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (5)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `conn.fetchrow`
- `int`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | Invalid interval for historical endpoint | `app/api.py:230` | una funcion de su cierre |

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
| `app.data_gaps.blocking_requirement_keys` | 20 | 14 | **31** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | 7 | **28** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | 21 | **24** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.historical_interval_value` | 7 | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.mask_gapped_series_rows` | 7 | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.cvd_divergence` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
