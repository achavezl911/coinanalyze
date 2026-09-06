# `GET /api/funding-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `funding_context_endpoint` · `app/api.py:1625` (cuerpo hasta la 1628) · decorador en la linea 1624.

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

- `app.api.validate_symbol` — `app/api.py:222`
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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K03-hueco-declarado.sh:47`, `harness/checks/K43-foto-unica.sh:94`, `harness/checks/K43-foto-unica.sh:142` | `harness/checks/K03-hueco-declarado.sh:29` |
| **panel** | `static/app.js:1682` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `next_funding_time_utc`

## Capa DECLARADA

**Declarada** en [`declarada/api-funding-context.md`](../declarada/api-funding-context.md) — pregunta del trader,
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
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.data_gaps._aware_utc` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps._validated_window` | 14 | **0** | 21 ↑ | **14** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.expected_buckets` | 12 | **0** | 21 ↑ | **12** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.coverage_entry` | 13 | **0** | 0 | **13** | [impacto](../impacto/app-data_gaps.md) |
| `app.data_gaps.align_down` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-data_gaps.md) |
| `app.scalp_logic.funding_context` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.funding_context_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
