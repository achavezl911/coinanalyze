# `GET /api/cross-asset`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `cross_asset_endpoint` · `app/api.py:1761` (cuerpo hasta la 1764) · decorador en la linea 1760.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/scalp_logic.py:3336 |
| `available` | literal en app/scalp_logic.py:3338 |
| `base` | literal en app/scalp_logic.py:3337 |
| `beta_vs_base` | literal en app/scalp_logic.py:3340 |
| `correlation` | literal en app/scalp_logic.py:3339 |
| `note` | literal en app/scalp_logic.py:3342 |
| `relative_strength_vs_base_pct` | literal en app/scalp_logic.py:3341 |
| `symbol` | literal en app/scalp_logic.py:3335 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:637`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:154`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:200`

## Funciones que la componen

9 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.cross_asset` — `app/scalp_logic.py:3304`

<details><summary>Alcanzables de forma indirecta (7)</summary>

- `app.scalp_logic._beta` — `app/scalp_logic.py:3269`
- `app.scalp_logic._binned` — `app/scalp_logic.py:3283`
- `app.scalp_logic._explicit_as_of` — `app/scalp_logic.py:2398`
- `app.scalp_logic._pearson` — `app/scalp_logic.py:3256`
- `app.scalp_logic._returns` — `app/scalp_logic.py:3248`
- `app.scalp_logic.as_float` — `app/scalp_logic.py:920`
- `app.scalp_logic.resolve_matrix_as_of` — `app/scalp_logic.py:2404`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

**NINGUN rastro**, ni llamada ni mencion, en `static/app.js`, `static/index.html`,
`harness/checks`, `tests`, `tools` ni `README.md`.

No prueba que este muerta -puede llamarla algo fuera del repo, o una IA por su
nombre-, pero es la forma exacta del patron que en esta casa se ha repetido nueve
veces. **Merece una mirada, no una conclusion.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**Declarada** en [`declarada/api-cross-asset.md`](../declarada/api-cross-asset.md) — pregunta del trader,
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
| `app.scalp_logic.resolve_matrix_as_of` | 24 | **0** | 11 ↑ | **24** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._explicit_as_of` | 25 | **0** | 0 | **25** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic.cross_asset` | 5 | **0** | 3 ↑ | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._beta` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._binned` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._pearson` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.scalp_logic._returns` | 5 | **0** | 0 | **5** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.cross_asset_endpoint` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
