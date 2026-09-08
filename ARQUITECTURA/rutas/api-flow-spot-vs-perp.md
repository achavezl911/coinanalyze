# `GET /api/flow/spot-vs-perp`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `flow_spot_vs_perp` · `app/api.py:1616` (cuerpo hasta la 1638) · decorador en la linea 1615.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'4hour'` | no |
| `days` | `Annotated[int, Query(ge=1, le=730)]` | `90` | no |
| `desde` | `str | None` | `None` | no |
| `hasta` | `str | None` | `None` | no |

## Campos que publica

12 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `buckets` | literal en app/scalp_logic.py:5817 |
| `buckets_with_both_legs` | literal en app/scalp_logic.py:5818 |
| `coverage_pct` | literal en app/scalp_logic.py:5819 |
| `interval` | literal en app/scalp_logic.py:5815 |
| `reason` | literal en app/scalp_logic.py:5749 |
| `rows` | literal en app/scalp_logic.py:5822 |
| `spot_symbol` | literal en app/scalp_logic.py:5813 |
| `state_counts` | literal en app/scalp_logic.py:5821 |
| `status` | literal en app/scalp_logic.py:5820 |
| `symbol` | literal en app/scalp_logic.py:5812 |
| `unit` | literal en app/scalp_logic.py:5816 |
| `venue` | literal en app/scalp_logic.py:5814 |

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

6 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.declara_ventana` — `app/api.py:1591`
- `app.api.validate_symbol` — `app/api.py:229`
- `app.api.ventana_pedida` — `app/api.py:1558`
- `app.scalp_logic.spot_perp_flow` — `app/scalp_logic.py:5728`

<details><summary>Alcanzables de forma indirecta (2)</summary>

- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4461`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |
| 422 | hace falta `desde` | `app/api.py:1575` | una funcion de su cierre |
| 422 | `hasta` sin `desde` no acota nada | `app/api.py:1578` | una funcion de su cierre |
| 422 | — | `app/api.py:1583` | una funcion de su cierre |
| 422 | desde/hasta necesitan zona horaria explicita | `app/api.py:1585` | una funcion de su cierre |
| 422 | hasta tiene que ser posterior a desde | `app/api.py:1587` | una funcion de su cierre |
| 422 | interval debe ser 4hour o daily: son los que Coinalyze sirve con historia | `app/api.py:1630` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **tests** | — | `tests/test_p0_data_integrity.py:126` |

**Nadie la llama.** Sus 1 rastros son todos MENCION -comentario,
docstring o documento-. Es la forma del patron que en esta casa se ha repetido
nueve veces: algo de lo que se habla y nadie ejecuta. **Merece una mirada.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['days', 'interval']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-flow-spot-vs-perp.md`](../declarada/api-flow-spot-vs-perp.md) — pregunta del trader,
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
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.flow_confirmation` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.ventana_pedida` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-api.md) |
| `app.api.declara_ventana` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.api.flow_spot_vs_perp` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.spot_perp_flow` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-scalp_logic.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
