# `GET /api/structure`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `structure` · `app/api.py:2502` (cuerpo hasta la 2505) · decorador en la linea 2501.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

6 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `alignment` | literal en app/scalp_logic.py:1201 |
| `as_of` | literal en app/scalp_logic.py:1199 |
| `bias_method` | literal en app/scalp_logic.py:1206 |
| `distinct_from` | literal en app/scalp_logic.py:1210 |
| `layers` | literal en app/scalp_logic.py:1200 |
| `symbol` | literal en app/scalp_logic.py:1198 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1123`, 14 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `futures_trades_realtime` — `sql/schema.sql:357`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:846`
- `liquidations` — `sql/schema.sql:275`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:675`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:317`
- `liquidations_realtime` — `sql/schema.sql:440`, 9 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:75`
- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
- `open_interest` — `sql/schema.sql:184`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`

## Funciones que la componen

11 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.market_structure` — `app/scalp_logic.py:1046`

<details><summary>Alcanzables de forma indirecta (9)</summary>

- `app.scalp_logic._complete_tail_values` — `app/scalp_logic.py:965`
- `app.scalp_logic._contiguous_measured_suffix` — `app/scalp_logic.py:975`
- `app.scalp_logic._cvd_fut_window` — `app/scalp_logic.py:1026`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._pivot_structure` — `app/scalp_logic.py:941`
- `app.scalp_logic._sign_vote` — `app/scalp_logic.py:959`
- `app.scalp_logic._structure_layer` — `app/scalp_logic.py:994`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:155`, `harness/checks/K43-foto-unica.sh:217` | — |
| **panel-sobre** | `static/js/07-decision-y-ciclos.js:352` | — |

**La llama el panel: es superficie de producto.**

**Pero NO con una peticion propia:** su dato llega dentro de `/api/ai/context`,
en la clave que `K43` le declara en su tabla `PAREJAS`. Al depurar eso importa:
**no busques una peticion suya en el log de nginx**, no la hay -la del sobre las
trae todas-, y su instante es el `generated_at` del sobre y no uno propio.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `distinct_from`

## Capa DECLARADA

**Declarada** en [`declarada/api-structure.md`](../declarada/api-structure.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._contiguous_measured_suffix` | 11 | **0** | 0 | **11** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._complete_tail_values` | 10 | **0** | 0 | **10** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._cvd_fut_window` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._pivot_structure` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._sign_vote` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._structure_layer` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.market_structure` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.structure` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
