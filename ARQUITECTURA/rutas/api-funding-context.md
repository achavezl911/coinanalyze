# `GET /api/funding-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `funding_context_endpoint` · `app/api.py:1602` (cuerpo hasta la 1605) · decorador en la linea 1601.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

10 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `annualized_pct` | literal en app/scalp_logic.py:3405 |
| `coverage` | literal en app/scalp_logic.py:3407 |
| `current_pct` | literal en app/scalp_logic.py:3400 |
| `divergence_pred_minus_current` | literal en app/scalp_logic.py:3402 |
| `history_avg_pct` | literal en app/scalp_logic.py:3406 |
| `next_funding_time_utc` | literal en app/scalp_logic.py:3408 |
| `note` | literal en app/scalp_logic.py:3416 |
| `predicted_pct` | literal en app/scalp_logic.py:3401 |
| `regime` | literal en app/scalp_logic.py:3409 |
| `symbol` | literal en app/scalp_logic.py:3399 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:651`
- `predicted_funding_rate` — `sql/schema.sql:160`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:654`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.funding_context` — `app/scalp_logic.py:3347`

<details><summary>Alcanzables de forma indirecta (6)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.data_gaps.align_down` — `app/data_gaps.py:232`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`
- `app.data_gaps.expected_buckets` — `app/data_gaps.py:245`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

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
| `app.data_gaps._aware_utc` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | 21 | **25** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | 21 | **24** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.align_down` | 4 | 0 | **4** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.funding_context` | 3 | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.funding_context_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
