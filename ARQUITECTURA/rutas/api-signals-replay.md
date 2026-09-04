# `GET /api/signals/replay`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `signals_replay` · `app/api.py:2347` (cuerpo hasta la 2417) · decorador en la linea 2346.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `since` | `str | None` | `None` | no |
| `until` | `str | None` | `None` | no |
| `limit` | `Annotated[int, Query(ge=1, le=1000)]` | `200` | no |

## Campos que publica

7 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `count` | literal en app/api.py:2414 |
| `frames` | literal en app/api.py:2416 |
| `limit` | literal en app/api.py:2413 |
| `since` | literal en app/api.py:2411 |
| `symbol` | literal en app/api.py:2410 |
| `truncated` | literal en app/api.py:2415 |
| `until` | literal en app/api.py:2412 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `signal_observation` — `sql/schema.sql:415`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:370`
- `signal_replay_frame` — `sql/schema.sql:751`, 7 columnas
  - la llena `app.signal_replay.persist_signal_replay_frame` (INSERT) — `app/signal_replay.py:110`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2045`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2073`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Llamadas que salen del arbol o no se resuelven (12)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `LEDGER_MAX_WINDOW.total_seconds`
- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `datetime.fromisoformat`
- `datetime.now`
- `int`
- `isinstance`
- `json.loads`
- `len`
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | — | `app/api.py:2082` | una funcion de su cierre |
| 422 | — | `app/api.py:2371` | el propio handler |
| 422 | since/until necesitan zona horaria explicita | `app/api.py:2373` | el propio handler |
| 422 | until tiene que ser posterior a since | `app/api.py:2375` | el propio handler |
| 422 | — | `app/api.py:2377` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
