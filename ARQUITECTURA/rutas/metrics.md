# `GET /metrics`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `prometheus_metrics` · `app/api.py:2669` (cuerpo hasta la 2743) · decorador en la linea 2668.

## Parametros de entrada

_ninguno_

## Campos que publica

**PENDIENTE · no se ha podido derivar ni un campo.**

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por Response(), que no se puede seguir
- el valor devuelto es un BinOp, que no se analiza estaticamente

Tipo declarado en la firma: `Response`.

## Tablas que toca

LEE:

- `futures_trades_realtime` — `sql/schema.sql:256`, 10 columnas
  - la llena `app.scalp_collector._write_combined_realtime` (INSERT) — `app/scalp_collector.py:773`
- `liquidations_realtime` — `sql/schema.sql:339`, 8 columnas
  - la llena `app.scalp_collector.flush_liquidations` (INSERT) — `app/scalp_collector.py:74`
- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `orderbook_snapshot` — `sql/schema.sql:287`, 18 columnas
  - la llena `app.scalp_collector.flush_books` (INSERT) — `app/scalp_collector.py:845`
  - la llena `app.scalp_collector._write_combined_books` (INSERT) — `app/scalp_collector.py:901`
- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`
- `scalp_signal_snapshot` — `sql/schema.sql:381`, 16 columnas
  - la llena `app.scalp_collector.persist_scalp_signals` (INSERT) — `app/scalp_collector.py:1406`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`

## Funciones que la componen

1 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._parse_heartbeat_detail` — `app/api.py:2651`

<details><summary>Llamadas que salen del arbol o no se resuelven (11)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `<llamada dinamica>`
- `HTTPException`
- `Response`
- `app.state.pool.acquire`
- `conn.fetch`
- `float`
- `int`
- `lines.append`
- `lines.extend`
- `metric_keys.items`
- `next`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Metrics disabled | `app/api.py:2671` | el propio handler |

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
| `app.api._parse_heartbeat_detail` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.api.prometheus_metrics` | 1 | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
