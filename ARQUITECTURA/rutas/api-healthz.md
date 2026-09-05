# `GET /api/healthz`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `health` · `app/api.py:2747` (cuerpo hasta la 2801) · decorador en la linea 2746.

## Parametros de entrada

_ninguno_

## Campos que publica

7 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `database` | literal en app/api.py:2795 |
| `governed_services` | literal en app/api.py:2798 |
| `missing_services` | literal en app/api.py:2796 |
| `missing_symbols` | literal en app/api.py:2797 |
| `services` | literal en app/api.py:2799 |
| `status` | literal en app/api.py:2790 |
| `symbols` | literal en app/api.py:2800 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `metrics_snapshot` — `sql/schema.sql:945`, 35 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:666`
  - la llena `app.metrics.insert_snapshot` (INSERT) — `app/metrics.py:683`
- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas
  - la llena `app.db.heartbeat` (INSERT) — `app/db.py:418`
  - la llena `app.db.heartbeat_component` (INSERT) — `app/db.py:472`
  - la llena `app.db.heartbeat_shard` (INSERT) — `app/db.py:542`

**ESCRIBE** (una ruta de lectura que escribe merece mirarse):

- `pipeline_heartbeat` — `sql/schema.sql:1284`, 4 columnas

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `now`
- `set`

## Funciones que la componen

5 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.records` — `app/api.py:234`
- `app.db.db_identity` — `app/db.py:64`
- `app.db.heartbeat` — `app/db.py:409`
- `app.db.heartbeat_max_age` — `app/db.py:95`
- `app.db.required_heartbeat_failures` — `app/db.py:110`

<details><summary>Llamadas que salen del arbol o no se resuelven (13)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `INGEST_COMPONENT_MAX_AGES.items`
- `INGEST_COMPONENT_MAX_AGES.values`
- `any`
- `app.state.pool.acquire`
- `bool`
- `conn.fetch`
- `conn.fetchval`
- `float`
- `max`
- `set`
- `sorted`
- `str`
- `thresholds.update`

</details>

## Fallos que puede devolver

_no levanta HTTPException en su cierre. Un fallo aqui sale como 500 del framework._

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
| `app.db.heartbeat` | 1 | 53 | **53** | [impacto](../impacto/app-db.md) |
| `app.api.records` | 22 | 7 | **28** | [impacto](../impacto/app-api.md) |
| `app.api.health` | 1 | 7 | **7** | [impacto](../impacto/app-api.md) |
| `app.db.db_identity` | 1 | 7 | **7** | [impacto](../impacto/app-db.md) |
| `app.db.heartbeat_max_age` | 1 | 7 | **7** | [impacto](../impacto/app-db.md) |
| `app.db.required_heartbeat_failures` | 4 | 7 | **7** | [impacto](../impacto/app-db.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
