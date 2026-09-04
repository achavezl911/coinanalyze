# `GET /api/level/breakout`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `level_breakout_endpoint` · `app/api.py:1702` (cuerpo hasta la 1712) · decorador en la linea 1701.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `level` | `Annotated[float, Query(gt=0)]` | — | si |
| `direction` | `str` | `'up'` | no |

## Campos que publica

11 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `available` | literal en app/breakout.py:295 |
| `base_rate` | literal en app/breakout.py:299 |
| `conditional_rates` | literal en app/breakout.py:300 |
| `confirmation` | literal en app/breakout.py:301 |
| `direction` | literal en app/breakout.py:297 |
| `level` | literal en app/breakout.py:296 |
| `method` | literal en app/breakout.py:307 |
| `reason` | literal en app/breakout.py:224 |
| `setup` | literal en app/breakout.py:298 |
| `symbol` | literal en app/scalp_logic.py:1657 |
| `warning` | literal en app/breakout.py:320 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:153`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:184`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:199`

## Funciones que la componen

13 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:221`
- `app.scalp_logic.level_breakout` — `app/scalp_logic.py:1632`

<details><summary>Alcanzables de forma indirecta (11)</summary>

- `app.breakout._atr` — `app/breakout.py:58`
- `app.breakout._confirmation_checks` — `app/breakout.py:330`
- `app.breakout._delta_usd` — `app/breakout.py:77`
- `app.breakout._rate` — `app/breakout.py:187`
- `app.breakout.attempt_features` — `app/breakout.py:149`
- `app.breakout.breakout_read` — `app/breakout.py:215`
- `app.breakout.build_corpus` — `app/breakout.py:173`
- `app.breakout.classify_outcome` — `app/breakout.py:125`
- `app.breakout.find_attempts` — `app/breakout.py:90`
- `app.breakout.wilson_ci` — `app/breakout.py:46`
- `app.interpretation.number` — `app/interpretation.py:10`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `HTTPException`
- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:223` | una funcion de su cierre |
| 422 | direction must be 'up' or 'down' | `app/api.py:1710` | el propio handler |

## Capa DECLARADA

**PENDIENTE · F3.** Que pregunta del trader contesta, a que familia de ventana
pertenece (K43), que promete, y si es superficie de producto o instrumento interno.
Esto NO se puede derivar del codigo: se escribe a mano una vez y se mantiene.

## Radio de impacto

**PENDIENTE · F2.** El sentido inverso -que otras rutas caen si tocas una funcion de
las de arriba- se genera en F2 y se enlaza aqui.
