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

## Superficie · quien la consume (medido)

| donde | sitios |
|---|---|
| **checks** | `harness/checks/K76-la-ventana-que-pides.sh:163` |
| **readme** | `README.md:171` |

**No la consume el panel.** Con consumidor solo en checks/tests/tools, es
**instrumento interno** — o una ruta que alguien dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-market-memory.md`](../declarada/api-market-memory.md) — pregunta del trader,
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
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation._memory_features` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.interpretation.market_memory_read` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-interpretation.md) |
| `app.scalp_logic.market_memory` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.market_memory_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
