# `GET /api/delta-profile`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `delta_profile_endpoint` · `app/api.py:1646` (cuerpo hasta la 1663) · decorador en la linea 1645.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'4hour'` | no |
| `days` | `Annotated[int, Query(ge=1, le=400)]` | `90` | no |
| `price` | `Annotated[float | None, Query(gt=0)]` | `None` | no |

## Campos que publica

4 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/delta_profile.py:269 |
| `coverage.served_window` | literal en app/delta_profile.py:269 |
| `requested_days` | literal en app/delta_profile.py:268 |
| `symbol` | literal en app/delta_profile.py:267 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **result, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

11 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.delta_profile.delta_profile` — `app/delta_profile.py:222`

<details><summary>Alcanzables de forma indirecta (9)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`
- `app.delta_profile._floor_log10` — `app/delta_profile.py:79`
- `app.delta_profile.bucket_index` — `app/delta_profile.py:69`
- `app.delta_profile.bucket_size` — `app/delta_profile.py:56`
- `app.delta_profile.profile_read` — `app/delta_profile.py:115`
- `app.delta_profile.value_area` — `app/delta_profile.py:92`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (4)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`
- `sorted`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | — | `app/api.py:1658` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:120` | — |
| **panel** | `static/app.js:1137` | — |
| **readme** | — | `README.md:111` |
| **tests** | `tests/test_dashboard_presentation.py:122` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['days', 'interval']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `coverage.served_window`

## Capa DECLARADA

**Declarada** en [`declarada/api-delta-profile.md`](../declarada/api-delta-profile.md) — pregunta del trader,
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
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.api.delta_profile_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.delta_profile._floor_log10` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |
| `app.delta_profile.bucket_index` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |
| `app.delta_profile.bucket_size` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |
| `app.delta_profile.delta_profile` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |
| `app.delta_profile.profile_read` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |
| `app.delta_profile.value_area` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-delta_profile.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
