# `GET /api/divergences`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `divergences_endpoint` · `app/api.py:1835` (cuerpo hasta la 1838) · decorador en la linea 1834.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

9 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/scalp_logic.py:2195 |
| `intraday` | literal en app/scalp_logic.py:2201 |
| `note` | literal en app/scalp_logic.py:2202 |
| `sessions` | literal en app/scalp_logic.py:2196 |
| `summary` | literal en app/scalp_logic.py:2198 |
| `sustained_windows_evaluated` | literal en app/scalp_logic.py:2200 |
| `symbol` | literal en app/scalp_logic.py:2194 |
| `windows` | literal en app/scalp_logic.py:2197 |
| `windows_confirming` | literal en app/scalp_logic.py:2199 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:254`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:275`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

7 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.divergence_scan` — `app/scalp_logic.py:2073`

<details><summary>Alcanzables de forma indirecta (5)</summary>

- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:960`
- `app.scalp_logic._intraday_divergences` — `app/scalp_logic.py:1958`
- `app.scalp_logic._return_stdev_pct` — `app/scalp_logic.py:1945`
- `app.scalp_logic._slope_pct` — `app/scalp_logic.py:1913`
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
| **checks** | `harness/checks/K43-foto-unica.sh:93`, `harness/checks/K43-foto-unica.sh:140` | `harness/checks/K43-foto-unica.sh:193` |
| **panel** | `static/app.js:1650` | — |
| **readme** | — | `README.md:281` |

**La llama el panel: es superficie de producto.**

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

**Declarada** en [`declarada/api-divergences.md`](../declarada/api-divergences.md) — pregunta del trader,
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
| `app.scalp_logic._complete_tail_values` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._intraday_divergences` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._return_stdev_pct` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._slope_pct` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.divergence_scan` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.divergences_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
