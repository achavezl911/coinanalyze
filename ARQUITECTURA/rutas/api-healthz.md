# `GET /api/healthz`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `health` · `app/api.py:3181` (cuerpo hasta la 3235) · decorador en la linea 3180.

## Parametros de entrada

_ninguno_

## Campos que publica

7 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `database` | literal en app/api.py:3229 |
| `governed_services` | literal en app/api.py:3232 |
| `missing_services` | literal en app/api.py:3230 |
| `missing_symbols` | literal en app/api.py:3231 |
| `services` | literal en app/api.py:3233 |
| `status` | literal en app/api.py:3224 |
| `symbols` | literal en app/api.py:3234 |

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

- `app.api.records` — `app/api.py:235`
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

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K03-hueco-declarado.sh:55`, `harness/checks/K05-control.bash:307`, `harness/checks/K05-latidos.sh:127`, `harness/checks/K05-latidos.sh:388` _(+3)_ | `harness/checks/K05-latidos.sh:2`, `harness/checks/K08-que-base.sh:8` |
| **panel** | `static/app.js:1569`, `static/app.js:1697` | — |
| **readme** | — | `README.md:413`, `README.md:436` |
| **tests** | — | `tests/test_cobertura_proveedor.py:7`, `tests/test_deploy_health_gate.py:38`, `tests/test_deploy_health_gate.py:154`, `tests/test_ingest_health.py:232` |

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

**Declarada** en [`declarada/api-healthz.md`](../declarada/api-healthz.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.db.heartbeat` | 1 | **7** | 53 ↑ | **7** | [impacto](../impacto/app-db.md) |
| `app.api.records` | 22 | **0** | 7 ↑ | **22** | [impacto](../impacto/app-api.md) |
| `app.api.health` | 1 | **0** | 7 ↑ | **1** | [impacto](../impacto/app-api.md) |
| `app.db.db_identity` | 1 | **0** | 7 ↑ | **1** | [impacto](../impacto/app-db.md) |
| `app.db.heartbeat_max_age` | 1 | **0** | 7 ↑ | **1** | [impacto](../impacto/app-db.md) |
| `app.db.required_heartbeat_failures` | 4 | **0** | 7 ↑ | **4** | [impacto](../impacto/app-db.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
