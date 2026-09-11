# `GET /api/ohlcv`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `ohlcv` · `app/api.py:685` (cuerpo hasta la 745) · decorador en la linea 684.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'5min'` | no |
| `limit` | `Annotated[int, Query(ge=10, le=2000)]` | `288` | no |

## Campos que publica

16 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:478 |
| `coverage.served_window` | literal en app/api.py:479 |
| `coverage.unit` | literal en app/api.py:424 |
| `data_gaps` | literal en app/api.py:484 |
| `data_gaps.declared` | literal en app/api.py:492 |
| `data_gaps.exchanges` | literal en app/api.py:486 |
| `data_gaps.feed` | literal en app/api.py:485 |
| `data_gaps.market` | literal en app/api.py:487 |
| `data_gaps.status` | literal en app/api.py:491 |
| `data_gaps.symbol` | literal en app/api.py:488 |
| `data_gaps.undeclared_buckets` | literal en app/api.py:493 |
| `data_gaps.window_end` | literal en app/api.py:490 |
| `data_gaps.window_start` | literal en app/api.py:489 |
| `interval` | literal en app/api.py:476 |
| `rows` | literal en app/api.py:477 |
| `symbol` | literal en app/api.py:475 |

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
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `required`

## Funciones que la componen

12 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.declared_series_response` — `app/api.py:396`
- `app.api.historical_interval_value` — `app/api.py:235`
- `app.api.mask_gapped_series_rows` — `app/api.py:246`
- `app.api.records` — `app/api.py:242`
- `app.api.validate_symbol` — `app/api.py:229`

<details><summary>Alcanzables de forma indirecta (7)</summary>

- `app.api.minutos_de_las_filas` — `app/api.py:356`
- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:108`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.declared_gap_windows` — `app/data_gaps.py:197`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (5)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `bucket.total_seconds`
- `conn.fetch`
- `int`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |
| 422 | Invalid interval for historical endpoint | `app/api.py:238` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K02-cobertura-hueco.sh:81`, `harness/checks/K03-hueco-declarado.sh:46`, `harness/checks/K20-cincoxx.sh:68`, `harness/checks/K20-cincoxx.sh:83` _(+7)_ | `harness/checks/K02-cobertura-hueco.sh:78`, `harness/checks/K03-hueco-declarado.sh:7`, `harness/checks/K43-foto-unica.sh:511` |
| **panel** | `static/app.js:1599` | — |
| **readme** | — | `README.md:402` |
| **tests** | — | `tests/test_p1_timeframes_and_spot.py:52` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['interval', 'limit']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `coverage.served_window`
- `data_gaps.window_end`
- `data_gaps.window_start`

## Capa DECLARADA

**Declarada** en [`declarada/api-ohlcv.md`](../declarada/api-ohlcv.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 63 | **0** | 0 | **63** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.blocking_requirement_keys` | 20 | **0** | 14 ↑ | **20** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.historical_interval_value` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.mask_gapped_series_rows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.declared_gap_windows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.declared_series_response` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.minutos_de_las_filas` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.ohlcv` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
