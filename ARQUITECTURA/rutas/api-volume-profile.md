# `GET /api/volume-profile`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `volume_profile_endpoint` · `app/api.py:1904` (cuerpo hasta la 1907) · decorador en la linea 1903.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

17 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3889 |
| `available` | literal en app/scalp_logic.py:3890 |
| `note` | literal en app/scalp_logic.py:3900 |
| `session` | literal en app/scalp_logic.py:3891 |
| `session.hvn` | literal en app/scalp_logic.py:3839 |
| `session.lvn` | literal en app/scalp_logic.py:3840 |
| `session.poc` | literal en app/scalp_logic.py:3836 |
| `session.vah` | literal en app/scalp_logic.py:3837 |
| `session.val` | literal en app/scalp_logic.py:3838 |
| `symbol` | literal en app/scalp_logic.py:3888 |
| `vwap` | literal en app/scalp_logic.py:3892 |
| `vwap.bands` | literal en app/scalp_logic.py:3895 |
| `vwap.distinct_from` | literal en app/scalp_logic.py:3898 |
| `vwap.market` | literal en app/scalp_logic.py:3896 |
| `vwap.session_convention` | literal en app/scalp_logic.py:3897 |
| `vwap.utc_day` | literal en app/scalp_logic.py:3893 |
| `vwap.weekly` | literal en app/scalp_logic.py:3894 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`

## Funciones que la componen

6 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:231`
- `app.scalp_logic.volume_profile` — `app/scalp_logic.py:3844`

<details><summary>Alcanzables de forma indirecta (4)</summary>

- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2586`
- `app.scalp_logic._profile` — `app/scalp_logic.py:3807`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2592`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:233` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **readme** | — | `README.md:121` |

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
| `app.api.validate_symbol` | 64 | **0** | 0 | **64** | [impacto](../impacto/app-api.md) |
| `app.scalp_logic.as_float` | 38 | **0** | 11 ↑ | **38** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.resolve_matrix_as_of` | 25 | **0** | 12 ↑ | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._explicit_as_of` | 26 | **0** | 0 | **26** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._profile` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.volume_profile` | 6 | **0** | 0 | **6** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.volume_profile_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
