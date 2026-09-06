# `GET /api/cvd/divergence`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `cvd_divergence` · `app/api.py:820` (cuerpo hasta la 934) · decorador en la linea 819.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'5min'` | no |
| `limit` | `Annotated[int, Query(ge=10, le=3000)]` | `576` | no |

## Campos que publica

12 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:933 |
| `coverage.served_window` | literal en app/api.py:933 |
| `coverage.served_window.complete` | literal en app/data_gaps.py:279 |
| `coverage.served_window.expected_buckets` | literal en app/data_gaps.py:277 |
| `coverage.served_window.observed_buckets` | literal en app/data_gaps.py:278 |
| `coverage.served_window.sources` | literal en app/data_gaps.py:280 |
| `coverage.served_window.window_end` | literal en app/data_gaps.py:276 |
| `coverage.served_window.window_start` | literal en app/data_gaps.py:275 |
| `coverage.status` | literal en app/api.py:933 |
| `interval` | literal en app/api.py:931 |
| `rows` | literal en app/api.py:932 |
| `symbol` | literal en app/api.py:930 |

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
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:264`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:285`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `required`

## Funciones que la componen

9 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.historical_interval_value` — `app/api.py:228`
- `app.api.mask_gapped_series_rows` — `app/api.py:239`
- `app.api.records` — `app/api.py:235`
- `app.api.validate_symbol` — `app/api.py:222`
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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | Invalid interval for historical endpoint | `app/api.py:231` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:102` | — |
| **panel** | `static/app.js:1622` | — |
| **readme** | — | `README.md:405` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['interval', 'limit']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `coverage.served_window`
- `coverage.served_window.window_end`
- `coverage.served_window.window_start`

## Capa DECLARADA

**Declarada** en [`declarada/api-cvd-divergence.md`](../declarada/api-cvd-divergence.md) — pregunta del trader,
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
| `app.data_gaps.blocking_requirement_keys` | 20 | **0** | 14 ↑ | **20** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.historical_interval_value` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.mask_gapped_series_rows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.cvd_divergence` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
