# `GET /api/liquidations`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `liquidation_series` · `app/api.py:1283` (cuerpo hasta la 1331) · decorador en la linea 1282.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'1hour'` | no |
| `limit` | `Annotated[int, Query(ge=10, le=1000)]` | `336` | no |

## Campos que publica

19 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:678 |
| `coverage.served_window` | literal en app/api.py:678 |
| `coverage.unit` | literal en app/api.py:603 |
| `data_gaps` | literal en app/api.py:679 |
| `data_gaps.age_seconds` | literal en app/api.py:690 |
| `data_gaps.as_of` | literal en app/api.py:689 |
| `data_gaps.declared` | literal en app/api.py:687 |
| `data_gaps.exchanges` | literal en app/api.py:681 |
| `data_gaps.feed` | literal en app/api.py:680 |
| `data_gaps.market` | literal en app/api.py:682 |
| `data_gaps.requested_window` | literal en app/api.py:691 |
| `data_gaps.status` | literal en app/api.py:686 |
| `data_gaps.symbol` | literal en app/api.py:683 |
| `data_gaps.undeclared_buckets` | literal en app/api.py:688 |
| `data_gaps.window_end` | literal en app/api.py:685 |
| `data_gaps.window_start` | literal en app/api.py:684 |
| `interval` | literal en app/api.py:676 |
| `rows` | literal en app/api.py:677 |
| `symbol` | literal en app/api.py:675 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

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
- `liquidations` — `sql/schema.sql:275`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:675`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:317`
- `pipeline_heartbeat` — `sql/schema.sql:1370`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `required`

## Funciones que la componen

16 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.declared_series_response` — `app/api.py:557`
- `app.api.historical_interval_value` — `app/api.py:266`
- `app.api.mask_gapped_series_rows` — `app/api.py:296`
- `app.api.records` — `app/api.py:273`
- `app.api.validate_symbol` — `app/api.py:260`

<details><summary>Alcanzables de forma indirecta (11)</summary>

- `app.api.cubos_tolerados` — `app/api.py:428`
- `app.api.lo_pedido` — `app/api.py:476`
- `app.api.minutos_de_las_filas` — `app/api.py:436`
- `app.data_gaps._aware_utc` — `app/data_gaps.py:72`
- `app.data_gaps._validated_window` — `app/data_gaps.py:78`
- `app.data_gaps.align_down` — `app/data_gaps.py:247`
- `app.data_gaps.blocking_requirement_keys` — `app/data_gaps.py:123`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:268`
- `app.data_gaps.declared_gap_windows` — `app/data_gaps.py:212`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:260`
- `app.orderflow_lectura._barrido_liquidaciones` — `app/orderflow_lectura.py:986`

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
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |
| 422 | Invalid interval for historical endpoint | `app/api.py:269` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K02-cobertura-hueco.sh:81`, `harness/checks/K03-hueco-declarado.sh:46` | `harness/checks/K31-cubos.py:41` |
| **tests** | — | `tests/test_sobre_lo_pedido.py:134` |

**No la llama el panel**, pero si 2 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['interval', 'limit']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `coverage.served_window`
- `data_gaps.requested_window`
- `data_gaps.window_end`
- `data_gaps.window_start`

## Capa DECLARADA

**Declarada** en [`declarada/api-liquidations.md`](../declarada/api-liquidations.md) — pregunta del trader,
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
| `app.data_gaps.blocking_requirement_keys` | 19 | **0** | 15 ↑ | **19** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.records` | 22 | **0** | 14 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.data_gaps._aware_utc` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 15 | **0** | 21 ↑ | **15** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 14 | **0** | 0 | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.align_down` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.historical_interval_value` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.mask_gapped_series_rows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.data_gaps.declared_gap_windows` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.cubos_tolerados` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.declared_series_response` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.lo_pedido` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.minutos_de_las_filas` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.orderflow_lectura._barrido_liquidaciones` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-orderflow_lectura.md) |
| `app.api.liquidation_series` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
