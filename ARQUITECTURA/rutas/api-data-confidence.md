# `GET /api/data-confidence`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `data_confidence` · `app/api.py:3169` (cuerpo hasta la 3173) · decorador en la linea 3168.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str | None` | `None` | no |

## Campos que publica

6 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `rows` | literal en app/api.py:3173 |
| `rows.collectors_stale` | asignado en app/ai_context.py:603 |
| `rows.flow_8h_complete` | asignado en app/ai_context.py:572 |
| `rows.quality_score` | asignado en app/ai_context.py:615 |
| `rows.quality_score_basis` | asignado en app/ai_context.py:616 |
| `rows.status` | asignado en app/ai_context.py:606 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 11 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:802`
- `metrics_snapshot` — `sql/schema.sql:952`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:684`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `orderbook_snapshot` — `sql/schema.sql:287`, 19 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:874`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:930`
- `pipeline_heartbeat` — `sql/schema.sql:1291`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `spot_trades_realtime` — `sql/schema.sql:228`, 11 columnas
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:404`
  - la llena `app.ws_collector.flush_realtime` (INSERT) — `app/ws_collector.py:421`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

5 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.ai_context.data_confidence_row` — `app/ai_context.py:532`
- `app.api.validate_symbol` — `app/api.py:259`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.ai_context.quality_score` — `app/ai_context.py:623`
- `app.db.required_heartbeat_failures` — `app/db.py:110`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`
- `list`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:261` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:151`, `harness/checks/K43-foto-unica.sh:207` | — |
| **panel-sobre** | `static/js/02-canal.js:72` | — |

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

- `rows.collectors_stale`

## Capa DECLARADA

**Declarada** en [`declarada/api-data-confidence.md`](../declarada/api-data-confidence.md) — pregunta del trader,
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
| `app.db.required_heartbeat_failures` | 5 | **0** | 8 ↑ | **5** | [impacto](../impacto/app-db.md) |
| `app.ai_context.data_confidence_row` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-ai_context.md) |
| `app.ai_context.quality_score` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-ai_context.md) |
| `app.api.data_confidence` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
