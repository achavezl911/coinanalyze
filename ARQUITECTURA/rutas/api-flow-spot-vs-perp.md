# `GET /api/flow/spot-vs-perp`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `flow_spot_vs_perp` · `app/api.py:1447` (cuerpo hasta la 1460) · decorador en la linea 1446.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `interval` | `str` | `'4hour'` | no |
| `days` | `Annotated[int, Query(ge=1, le=730)]` | `90` | no |

## Campos que publica

12 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `buckets` | literal en app/scalp_logic.py:5686 |
| `buckets_with_both_legs` | literal en app/scalp_logic.py:5687 |
| `coverage_pct` | literal en app/scalp_logic.py:5688 |
| `interval` | literal en app/scalp_logic.py:5684 |
| `reason` | literal en app/scalp_logic.py:5620 |
| `rows` | literal en app/scalp_logic.py:5691 |
| `spot_symbol` | literal en app/scalp_logic.py:5682 |
| `state_counts` | literal en app/scalp_logic.py:5690 |
| `status` | literal en app/scalp_logic.py:5689 |
| `symbol` | literal en app/scalp_logic.py:5681 |
| `unit` | literal en app/scalp_logic.py:5685 |
| `venue` | literal en app/scalp_logic.py:5683 |

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

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.spot_perp_flow` — `app/scalp_logic.py:5604`

<details><summary>Alcanzables de forma indirecta (2)</summary>

- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.flow_confirmation` — `app/scalp_logic.py:4419`

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
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | interval debe ser 4hour o daily: son los que Coinalyze sirve con historia | `app/api.py:1455` | el propio handler |

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
| `app.scalp_logic.as_float` | 37 | **0** | 9 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.flow_confirmation` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.flow_spot_vs_perp` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.spot_perp_flow` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-scalp_logic.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
