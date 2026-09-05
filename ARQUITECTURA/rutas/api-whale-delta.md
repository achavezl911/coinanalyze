# `GET /api/whale/delta`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `whale_delta` · `app/api.py:1014` (cuerpo hasta la 1080) · decorador en la linea 1013.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'15min'` | no |
| `limit` | `Annotated[int, Query(ge=10, le=2000)]` | `384` | no |

## Campos que publica

5 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:428 |
| `data_gaps` | literal en app/api.py:433 |
| `interval` | literal en app/api.py:426 |
| `rows` | literal en app/api.py:427 |
| `symbol` | literal en app/api.py:425 |

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
- `spot_trades_agg` — `sql/schema.sql:198`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`

## Funciones que la componen

9 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.declared_series_response` — `app/api.py:348`
- `app.api.historical_interval_value` — `app/api.py:227`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Alcanzables de forma indirecta (5)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.declared_gap_windows` — `app/data_gaps.py:197`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `conn.fetch`

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

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.historical_interval_value` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.declared_gap_windows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.declared_series_response` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.whale_delta` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
