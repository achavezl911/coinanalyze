# `GET /api/signals/outcomes`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `signals_outcomes` · `app/api.py:2175` (cuerpo hasta la 2247) · decorador en la linea 2174.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `since` | `str | None` | `None` | no |
| `until` | `str | None` | `None` | no |
| `horizon` | `Annotated[int | None, Query()]` | `None` | no |
| `limit` | `Annotated[int, Query(ge=1, le=5000)]` | `1000` | no |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `count` | literal en app/api.py:2244 |
| `horizon` | literal en app/api.py:2242 |
| `limit` | literal en app/api.py:2243 |
| `outcomes` | literal en app/api.py:2246 |
| `since` | literal en app/api.py:2240 |
| `symbol` | literal en app/api.py:2239 |
| `truncated` | literal en app/api.py:2245 |
| `until` | literal en app/api.py:2241 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `signal_observation` — `sql/schema.sql:415`, 34 columnas
  - la llena `app.signal_ledger.persist_signal_observations` (INSERT) — `app/signal_ledger.py:370`
- `signal_outcome` — `sql/schema.sql:565`, 27 columnas
  - la llena `app.signal_outcomes.schedule_signal_outcomes` (INSERT) — `app/signal_outcomes.py:168`
  - la llena `app.signal_outcomes._finalize_not_evaluable` (UPDATE) — `app/signal_outcomes.py:198`
  - la llena `app.signal_outcomes._defer_missing_path` (UPDATE) — `app/signal_outcomes.py:225`
  - la llena `app.signal_outcomes._finalize_evaluated` (UPDATE) — `app/signal_outcomes.py:251`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2045`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2073`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Llamadas que salen del arbol o no se resuelven (11)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `LEDGER_MAX_WINDOW.total_seconds`
- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `datetime.fromisoformat`
- `datetime.now`
- `int`
- `len`
- `list`
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | — | `app/api.py:2082` | una funcion de su cierre |
| 422 | — | `app/api.py:2196` | el propio handler |
| 422 | — | `app/api.py:2204` | el propio handler |
| 422 | since/until necesitan zona horaria explicita | `app/api.py:2206` | el propio handler |
| 422 | until tiene que ser posterior a since | `app/api.py:2208` | el propio handler |
| 422 | — | `app/api.py:2210` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
