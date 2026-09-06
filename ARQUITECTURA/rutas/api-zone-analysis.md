# `GET /api/zone/analysis`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `zone_analysis_endpoint` · `app/api.py:1674` (cuerpo hasta la 1687) · decorador en la linea 1673.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `low` | `Annotated[float, Query(gt=0)]` | — | si |
| `high` | `Annotated[float, Query(gt=0)]` | — | si |
| `days` | `Annotated[int, Query(ge=7, le=365)]` | `365` | no |

## Campos que publica

13 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `lookback_days` | literal en app/scalp_logic.py:1486 |
| `scored_visits` | literal en app/scalp_logic.py:1489 |
| `sources` | literal en app/scalp_logic.py:1495 |
| `sources.cvd_spot` | literal en app/scalp_logic.py:1497 |
| `sources.delta_futuros` | literal en app/scalp_logic.py:1496 |
| `sources.no_disponible` | literal en app/scalp_logic.py:1498 |
| `summary` | literal en app/scalp_logic.py:1490 |
| `symbol` | literal en app/scalp_logic.py:1484 |
| `visit_count` | literal en app/scalp_logic.py:1488 |
| `visits` | literal en app/scalp_logic.py:1487 |
| `zone` | literal en app/scalp_logic.py:1485 |
| `zone.high` | literal en app/scalp_logic.py:1485 |
| `zone.low` | literal en app/scalp_logic.py:1485 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

12 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.zone_analysis` — `app/scalp_logic.py:1364`

<details><summary>Alcanzables de forma indirecta (10)</summary>

- `app.interpretation.number` — `app/interpretation.py:10`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.zones._atr_pct` — `app/zones.py:104`
- `app.zones._clamp` — `app/zones.py:100`
- `app.zones._effort_result` — `app/zones.py:128`
- `app.zones._narrative` — `app/zones.py:394`
- `app.zones._oi_behaviour` — `app/zones.py:208`
- `app.zones._percentile` — `app/zones.py:121`
- `app.zones._rejection` — `app/zones.py:194`
- `app.zones.zone_character_read` — `app/zones.py:220`

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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |
| 422 | low must be below high | `app/api.py:1683` | el propio handler |
| 422 | zone spans more than 3x; narrow it | `app/api.py:1685` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:61`, `harness/checks/K43-foto-unica.sh:104` | — |
| **panel** | `static/app.js:2863` | — |
| **tests** | — | `tests/test_p0_data_integrity.py:126` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['days']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/api-zone-analysis.md`](../declarada/api-zone-analysis.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 62 | **0** | 0 | **62** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.interpretation.number` | 13 | **0** | 3 ↑ | **13** | [impacto](../impacto/app-interpretation.md) |
| `app.api.zone_analysis_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.zone_analysis` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-scalp_logic.md) |
| `app.zones._atr_pct` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._clamp` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._effort_result` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._narrative` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._oi_behaviour` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._percentile` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones._rejection` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |
| `app.zones.zone_character_read` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-zones.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
