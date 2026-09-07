# `GET /api/rango/estructura`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `rango_estructura` · `app/api.py:1906` (cuerpo hasta la 1929) · decorador en la linea 1905.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |
| `desde` | `str` | — | si |
| `hasta` | `str | None` | `None` | no |

## Campos que publica

51 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/rango.py:247 |
| `control` | literal en app/rango.py:243 |
| `control.ballena_spot_usd` | literal en app/rango.py:91 |
| `control.cvd_spot_usd` | literal en app/rango.py:90 |
| `control.desde` | literal en app/rango.py:84 |
| `control.funding_medio_pct` | literal en app/rango.py:95 |
| `control.hasta` | literal en app/rango.py:85 |
| `control.horas` | literal en app/rango.py:86 |
| `control.liq_cortos_usd` | literal en app/rango.py:97 |
| `control.liq_largos_usd` | literal en app/rango.py:97 |
| `control.minutos_spot` | literal en app/rango.py:90 |
| `control.muestras_funding` | literal en app/rango.py:96 |
| `control.muestras_liq` | literal en app/rango.py:98 |
| `control.muestras_oi` | literal en app/rango.py:94 |
| `control.oi_fin` | literal en app/rango.py:92 |
| `control.oi_inicio` | literal en app/rango.py:92 |
| `control.oi_pct` | literal en app/rango.py:93 |
| `control.precio_fin` | literal en app/rango.py:88 |
| `control.precio_inicio` | literal en app/rango.py:88 |
| `control.precio_pct` | literal en app/rango.py:89 |
| `control.velas_1min` | literal en app/rango.py:87 |
| `fin_abierto` | literal en app/rango.py:244 |
| `pruebas` | literal en app/rango.py:245 |
| `symbol` | literal en app/rango.py:241 |
| `ventana` | literal en app/rango.py:242 |
| `ventana.ballena_spot_usd` | literal en app/rango.py:91 |
| `ventana.cvd_spot_usd` | literal en app/rango.py:90 |
| `ventana.desde` | literal en app/rango.py:84 |
| `ventana.funding_medio_pct` | literal en app/rango.py:95 |
| `ventana.hasta` | literal en app/rango.py:85 |
| `ventana.horas` | literal en app/rango.py:86 |
| `ventana.liq_cortos_usd` | literal en app/rango.py:97 |
| `ventana.liq_largos_usd` | literal en app/rango.py:97 |
| `ventana.minutos_spot` | literal en app/rango.py:90 |
| `ventana.muestras_funding` | literal en app/rango.py:96 |
| `ventana.muestras_liq` | literal en app/rango.py:98 |
| `ventana.muestras_oi` | literal en app/rango.py:94 |
| `ventana.oi_fin` | literal en app/rango.py:92 |
| `ventana.oi_inicio` | literal en app/rango.py:92 |
| `ventana.oi_pct` | literal en app/rango.py:93 |
| `ventana.precio_fin` | literal en app/rango.py:88 |
| `ventana.precio_inicio` | literal en app/rango.py:88 |
| `ventana.precio_pct` | literal en app/rango.py:89 |
| `ventana.velas_1min` | literal en app/rango.py:87 |
| `veredicto` | literal en app/rango.py:246 |
| `veredicto.estructura` | literal en app/rango.py:216 |
| `veredicto.no_es_prediccion` | literal en app/rango.py:223 |
| `veredicto.porque` | literal en app/rango.py:217 |
| `veredicto.pruebas_que_votan` | literal en app/rango.py:218 |
| `veredicto.pruebas_totales` | literal en app/rango.py:219 |
| `veredicto.reparto` | literal en app/rango.py:220 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:651`
- `liquidations` — `sql/schema.sql:174`, 5 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:657`
  - la llena `app.ingest.upsert_liquidations` (INSERT) — `app/ingest.py:316`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
- `open_interest` — `sql/schema.sql:83`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:645`
- `spot_trades_agg` — `sql/schema.sql:198`, 15 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:663`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:264`
  - la llena `app.ws_collector._write_minute` (INSERT) — `app/ws_collector.py:285`

## Funciones que la componen

8 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2306`
- `app.api.validate_symbol` — `app/api.py:228`
- `app.api.ventana_pedida` — `app/api.py:1538`
- `app.rango.estructura_de_rango` — `app/rango.py:228`

<details><summary>Alcanzables de forma indirecta (4)</summary>

- `app.rango._prueba` — `app/rango.py:102`
- `app.rango._pruebas` — `app/rango.py:106`
- `app.rango._ventana` — `app/rango.py:51`
- `app.rango._veredicto` — `app/rango.py:183`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `WS_SYMBOL_MAP.get`
- `app.state.pool.acquire`
- `selected.split`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:230` | una funcion de su cierre |
| 422 | hace falta `desde` | `app/api.py:1555` | una funcion de su cierre |
| 422 | `hasta` sin `desde` no acota nada | `app/api.py:1558` | una funcion de su cierre |
| 422 | — | `app/api.py:1563` | una funcion de su cierre |
| 422 | desde/hasta necesitan zona horaria explicita | `app/api.py:1565` | una funcion de su cierre |
| 422 | hasta tiene que ser posterior a desde | `app/api.py:1567` | una funcion de su cierre |
| 422 | — | `app/api.py:2315` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **panel** | `static/app.js:3083` | — |
| **tests** | — | `tests/test_ventana_elegible.py:71` |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['desde', 'hasta', 'symbol']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**PENDIENTE de declaracion.** No existe `declarada/api-rango-estructura.md`.

Que pregunta del trader contesta, a que familia de ventana pertenece y que
promete NO se derivan del codigo: se escriben a mano. Mientras no esten, esta
ruta esta descrita pero **no declarada**, y K88 la cuenta.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 63 | **0** | 0 | **63** | [impacto](../impacto/app-api.md) |
| `app.api.rechaza_parametros_desconocidos` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-api.md) |
| `app.api.ventana_pedida` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-api.md) |
| `app.api.rango_estructura` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.rango._prueba` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-rango.md) |
| `app.rango._pruebas` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-rango.md) |
| `app.rango._ventana` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-rango.md) |
| `app.rango._veredicto` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-rango.md) |
| `app.rango.estructura_de_rango` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-rango.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
