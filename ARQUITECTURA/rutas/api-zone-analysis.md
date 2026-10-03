# `GET /api/zone/analysis`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `zone_analysis_endpoint` · `app/api.py:1994` (cuerpo hasta la 2016) · decorador en la linea 1993.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |
| `low` | `Annotated[float, Query(gt=0)]` | — | si |
| `high` | `Annotated[float, Query(gt=0)]` | — | si |
| `days` | `Annotated[int, Query(ge=7, le=365)]` | `365` | no |
| `desde` | `str | None` | `None` | no |
| `hasta` | `str | None` | `None` | no |

## Campos que publica

1 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | asignado en app/api.py:1989 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- devuelve la variable 'payload', cuyo contenido no se resuelve estaticamente

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:688`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`

## Funciones que la componen

16 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.declara_ventana` — `app/api.py:1732`
- `app.api.sella_respuesta` — `app/api.py:1977`
- `app.api.validate_symbol` — `app/api.py:232`
- `app.api.ventana_pedida` — `app/api.py:1699`
- `app.scalp_logic.zone_analysis` — `app/scalp_logic.py:1433`

<details><summary>Alcanzables de forma indirecta (11)</summary>

- `app.api._utc_iso` — `app/api.py:2445`
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
| 404 | Unknown symbol | `app/api.py:234` | una funcion de su cierre |
| 422 | hace falta «desde» | `app/api.py:1716` | una funcion de su cierre |
| 422 | «hasta» sin «desde» no acota nada | `app/api.py:1719` | una funcion de su cierre |
| 422 | — | `app/api.py:1724` | una funcion de su cierre |
| 422 | desde/hasta necesitan zona horaria explicita | `app/api.py:1726` | una funcion de su cierre |
| 422 | hasta tiene que ser posterior a desde | `app/api.py:1728` | una funcion de su cierre |
| 422 | low must be below high | `app/api.py:2009` | el propio handler |
| 422 | zone spans more than 3x; narrow it | `app/api.py:2011` | el propio handler |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K31-eslabon5.sh:66`, `harness/checks/K43-control.bash:138`, `harness/checks/K43-foto-unica.sh:162`, `harness/checks/K43-foto-unica.sh:458` | `harness/checks/K43-foto-unica.sh:106` |
| **panel** | `static/js/10-contexto-y-estructura.js:319` | — |
| **tests** | — | `tests/test_p0_data_integrity.py:130` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **2** — pide ['days']: coverage de su propia serie.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

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
| `app.api.validate_symbol` | 65 | **0** | 0 | **65** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.interpretation.number` | 14 | **0** | 3 ↑ | **14** | [impacto](../impacto/app-interpretation.md) |
| `app.api._utc_iso` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-api.md) |
| `app.api.ventana_pedida` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-api.md) |
| `app.api.declara_ventana` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
| `app.api.sella_respuesta` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-api.md) |
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
