# `GET /api/signals/visibility`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `signals_visibility` · `app/api.py:2429` (cuerpo hasta la 2506) · decorador en la linea 2428.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `since` | `str | None` | `None` | no |
| `until` | `str | None` | `None` | no |
| `status` | `str | None` | `None` | no |
| `limit` | `Annotated[int, Query(ge=1, le=5000)]` | `1000` | no |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `certificates` | literal en app/api.py:2505 |
| `count` | literal en app/api.py:2503 |
| `limit` | literal en app/api.py:2502 |
| `since` | literal en app/api.py:2499 |
| `status` | literal en app/api.py:2501 |
| `symbol` | literal en app/api.py:2498 |
| `truncated` | literal en app/api.py:2504 |
| `until` | literal en app/api.py:2500 |

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
- `signal_outcome_final_visibility` — `sql/schema.sql:2477`, 8 columnas
  - la llena `app.signal_visibility._certify_final_outcomes_once` (INSERT) — `app/signal_visibility.py:307`

## Funciones que la componen

4 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._utc_iso` — `app/api.py:2045`
- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2073`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`

<details><summary>Llamadas que salen del arbol o no se resuelven (10)</summary>

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
- `timedelta`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | — | `app/api.py:2082` | una funcion de su cierre |
| 422 | status tiene que ser evaluated o not_evaluable | `app/api.py:2454` | el propio handler |
| 422 | — | `app/api.py:2462` | el propio handler |
| 422 | since/until necesitan zona horaria explicita | `app/api.py:2464` | el propio handler |
| 422 | until tiene que ser posterior a since | `app/api.py:2466` | el propio handler |
| 422 | — | `app/api.py:2468` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
