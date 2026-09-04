# `GET /api/verdicts`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `verdicts` · `app/api.py:1826` (cuerpo hasta la 1912) · decorador en la linea 1825.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `limit` | `Annotated[int, Query(ge=1, le=730)]` | `90` | no |
| `logic_version` | `Annotated[str, Query(min_length=1, max_length=80)]` | `DAILY_VERDICT_LOGIC_VERSION` | no |

## Campos que publica

5 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `coverage` | literal en app/api.py:1905 |
| `logic_version` | literal en app/api.py:1903 |
| `note` | literal en app/api.py:1906 |
| `rows` | literal en app/api.py:1904 |
| `symbol` | literal en app/api.py:1902 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_verdict_outcome` — `sql/schema.sql:2290`, 10 columnas
  - la llena `app.daily_agg.materialize_daily_verdict_outcomes` (INSERT) — `app/daily_agg.py:506`
- `daily_verdict_snapshot` — `sql/schema.sql:1099`, 26 columnas
  - la llena `app.daily_agg.persist_verdicts` (INSERT) — `app/daily_agg.py:417`

## Funciones que la componen

7 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api._session_window` — `app/api.py:447`
- `app.api.records` — `app/api.py:234`
- `app.api.validate_symbol` — `app/api.py:221`
- `app.data_gaps.coverage_entry` — `app/data_gaps.py:253`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.data_gaps._aware_utc` — `app/data_gaps.py:67`
- `app.data_gaps._validated_window` — `app/data_gaps.py:73`
- `app.metrics.session_bounds` — `app/metrics.py:31`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (9)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `conn.fetch`
- `date.fromisoformat`
- `fila.get`
- `len`
- `max`
- `min`
- `str`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
