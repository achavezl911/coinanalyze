# `GET /api/baselines`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `metric_baselines` · `app/api.py:1334` (cuerpo hasta la 1348) · decorador en la linea 1333.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `metric` | `str` | `'delta_ratio'` | no |

## Campos que publica

5 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `fallback_min_ratio` | literal en app/api.py:1342 |
| `metric` | literal en app/api.py:1341 |
| `note` | literal en app/api.py:1343 |
| `symbol` | literal en app/api.py:1340 |
| `windows` | literal en app/api.py:1347 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `metric_baseline` — `sql/schema.sql:1265`, 14 columnas
  - la llena `app.daily_agg._store_baseline` (INSERT) — `app/daily_agg.py:780`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.load_baselines` — `app/scalp_logic.py:158`

<details><summary>Alcanzables de forma indirecta (1)</summary>

- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`

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
| `app.scalp_logic._explicit_as_of` | 25 | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.load_baselines` | 14 | 9 | **21** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.metric_baselines` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
