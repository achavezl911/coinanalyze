# `GET /api/market-memory`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `market_memory_endpoint` · `app/api.py:1819` (cuerpo hasta la 1822) · decorador en la linea 1818.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

13 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `analog_summary` | literal en app/interpretation.py:508 |
| `analogs` | literal en app/interpretation.py:507 |
| `available` | literal en app/interpretation.py:491 |
| `coverage` | literal en app/interpretation.py:492 |
| `current` | literal en app/interpretation.py:500 |
| `historical_tilt` | literal en app/interpretation.py:499 |
| `method` | literal en app/interpretation.py:515 |
| `phase` | literal en app/interpretation.py:498 |
| `reason` | literal en app/interpretation.py:412 |
| `sessions` | literal en app/interpretation.py:411 |
| `source` | literal en app/interpretation.py:516 |
| `symbol` | literal en app/scalp_logic.py:1676 |
| `warning` | literal en app/interpretation.py:517 |

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

5 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.market_memory` — `app/scalp_logic.py:1660`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.interpretation._memory_features` — `app/interpretation.py:372`
- `app.interpretation.market_memory_read` — `app/interpretation.py:400`
- `app.interpretation.number` — `app/interpretation.py:10`

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
| `app.interpretation.number` | 13 | 3 | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation._memory_features` | 4 | 0 | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation.market_memory_read` | 4 | 0 | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.market_memory` | 4 | 0 | **4** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.market_memory_endpoint` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
