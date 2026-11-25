# `GET /api/volume-profile`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `volume_profile_endpoint` · `app/api.py:2140` (cuerpo hasta la 2143) · decorador en la linea 2139.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

17 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3974 |
| `available` | literal en app/scalp_logic.py:3975 |
| `note` | literal en app/scalp_logic.py:3985 |
| `session` | literal en app/scalp_logic.py:3976 |
| `session.hvn` | literal en app/scalp_logic.py:3924 |
| `session.lvn` | literal en app/scalp_logic.py:3925 |
| `session.poc` | literal en app/scalp_logic.py:3921 |
| `session.vah` | literal en app/scalp_logic.py:3922 |
| `session.val` | literal en app/scalp_logic.py:3923 |
| `symbol` | literal en app/scalp_logic.py:3973 |
| `vwap` | literal en app/scalp_logic.py:3977 |
| `vwap.bands` | literal en app/scalp_logic.py:3980 |
| `vwap.distinct_from` | literal en app/scalp_logic.py:3983 |
| `vwap.market` | literal en app/scalp_logic.py:3981 |
| `vwap.session_convention` | literal en app/scalp_logic.py:3982 |
| `vwap.utc_day` | literal en app/scalp_logic.py:3978 |
| `vwap.weekly` | literal en app/scalp_logic.py:3979 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:156`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`

## Funciones que la componen

6 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:260`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3929`

<details><summary>Alcanzables de forma indirecta (4)</summary>

- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2591`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3892`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:925`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2597`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:262` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **tests** | `tests/js/mesa_f12a.test.js:153` | — |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`
- `vwap.distinct_from`
- `vwap.utc_day`

## Capa DECLARADA

**Declarada** en [`declarada/api-volume-profile.md`](../declarada/api-volume-profile.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 12 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._profile` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.volume_profile` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.volume_profile_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
