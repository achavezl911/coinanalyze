# `GET /api/reference-levels`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `reference_levels_endpoint` · `app/api.py:2016` (cuerpo hasta la 2019) · decorador en la linea 2015.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

22 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `current_day` | literal en app/scalp_logic.py:3267 |
| `current_day.duracion_min` | literal en app/scalp_logic.py:3269 |
| `current_day.en_curso` | literal en app/scalp_logic.py:3269 |
| `current_day.high` | literal en app/scalp_logic.py:3267 |
| `current_day.low` | literal en app/scalp_logic.py:3267 |
| `current_day.open` | literal en app/scalp_logic.py:3267 |
| `current_day.velas` | literal en app/scalp_logic.py:3268 |
| `current_day.velas_posibles` | literal en app/scalp_logic.py:3268 |
| `note` | literal en app/scalp_logic.py:3281 |
| `opens` | literal en app/scalp_logic.py:3270 |
| `opens.daily` | literal en app/scalp_logic.py:3271 |
| `opens.monthly` | literal en app/scalp_logic.py:3273 |
| `opens.weekly` | literal en app/scalp_logic.py:3272 |
| `previous_day` | literal en app/scalp_logic.py:3265 |
| `previous_day.close` | literal en app/scalp_logic.py:3265 |
| `previous_day.en_curso` | literal en app/scalp_logic.py:3266 |
| `previous_day.high` | literal en app/scalp_logic.py:3265 |
| `previous_day.low` | literal en app/scalp_logic.py:3265 |
| `previous_day.velas` | literal en app/scalp_logic.py:3266 |
| `previous_day.velas_posibles` | literal en app/scalp_logic.py:3266 |
| `sessions_today_utc` | literal en app/scalp_logic.py:3275 |
| `symbol` | literal en app/scalp_logic.py:3264 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:229`
- `app.scalp_logic.reference_levels` — `app/scalp_logic.py:3196`

<details><summary>Alcanzables de forma indirecta (1)</summary>

- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:231` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **panel** | — | `static/app.js:2151` |

**Nadie la llama.** Sus 1 rastros son todos MENCION -comentario,
docstring o documento-. Es la forma del patron que en esta casa se ha repetido
nueve veces: algo de lo que se habla y nadie ejecuta. **Merece una mirada.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `current_day`
- `previous_day`

## Capa DECLARADA

**Declarada** en [`declarada/api-reference-levels.md`](../declarada/api-reference-levels.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 63 | **0** | 0 | **63** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 37 | **0** | 10 ↑ | **37** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.reference_levels` | 4 | **0** | 0 | **4** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.reference_levels_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
