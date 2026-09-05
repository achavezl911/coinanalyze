# `GET /api/macro-context`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `macro_context_endpoint` · `app/api.py:1795` (cuerpo hasta la 1798) · decorador en la linea 1794.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

7 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:1871 |
| `conditional_note` | literal en app/scalp_logic.py:1876 |
| `metrics` | literal en app/scalp_logic.py:1874 |
| `session_date` | literal en app/scalp_logic.py:1873 |
| `sessions` | literal en app/scalp_logic.py:1872 |
| `symbol` | literal en app/scalp_logic.py:1870 |
| `tension` | literal en app/scalp_logic.py:1875 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`

## Funciones que la componen

10 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.macro_context` — `app/scalp_logic.py:1820`

<details><summary>Alcanzables de forma indirecta (8)</summary>

- `app.metrics.current_nyse_start` — `app/metrics.py:20`
- `app.scalp_logic._conditional_outcome` — `app/scalp_logic.py:1780`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._forward_returns` — `app/scalp_logic.py:1770`
- `app.scalp_logic._pct_rank` — `app/scalp_logic.py:1742`
- `app.scalp_logic._regime` — `app/scalp_logic.py:1751`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`

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

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 9 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 10 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.metrics.current_nyse_start` | 15 | **0** | 14 ↑ | **15** | [impacto](../impacto/app-metrics.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._pct_rank` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.macro_context` | 5 | **0** | 3 ↑ | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._conditional_outcome` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._forward_returns` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._regime` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.macro_context_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
