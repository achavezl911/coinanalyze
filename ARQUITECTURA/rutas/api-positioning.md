# `GET /api/positioning`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `positioning` · `app/api.py:1128` (cuerpo hasta la 1132) · decorador en la linea 1127.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `symbol` | `str` | — | si |

## Campos que publica

17 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `age_seconds` | literal en app/scalp_logic.py:5599 |
| `limitations` | literal en app/scalp_logic.py:5600 |
| `long_pct` | literal en app/scalp_logic.py:5585 |
| `median_sample` | literal en app/scalp_logic.py:5593 |
| `percentile_sample` | literal en app/scalp_logic.py:5594 |
| `ratio` | literal en app/scalp_logic.py:5587 |
| `ratio_24h_ago` | literal en app/scalp_logic.py:5588 |
| `ratio_change_24h` | literal en app/scalp_logic.py:5590 |
| `reason` | literal en app/scalp_logic.py:5562 |
| `sample_count` | literal en app/scalp_logic.py:5595 |
| `sample_days` | literal en app/scalp_logic.py:5596 |
| `sample_is_full_month` | literal en app/scalp_logic.py:5597 |
| `short_pct` | literal en app/scalp_logic.py:5586 |
| `status` | literal en app/scalp_logic.py:5583 |
| `symbol` | literal en app/scalp_logic.py:5582 |
| `ts` | literal en app/scalp_logic.py:5598 |
| `unit` | literal en app/scalp_logic.py:5584 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `long_short_ratio` — `sql/schema.sql:187`, 6 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:660`
  - la llena `app.ingest.upsert_long_short` (INSERT) — `app/ingest.py:357`

Identificadores detras de FROM/JOIN que **no** estan en `sql/schema.sql` y que por
tanto NO se afirman como tabla (pueden ser CTE, alias, funcion o particion):

- `max`
- `now`

## Funciones que la componen

3 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.validate_symbol` — `app/api.py:222`
- `app.scalp_logic.positioning_context` — `app/scalp_logic.py:5525`

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
| 404 | Unknown symbol | `app/api.py:224` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:99`, `harness/checks/K43-foto-unica.sh:154` | — |
| **panel** | `static/app.js:1620` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `age_seconds`
- `ts`

## Capa DECLARADA

**Declarada** en [`declarada/api-positioning.md`](../declarada/api-positioning.md) — pregunta del trader,
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
| `app.scalp_logic.positioning_context` | 3 | **0** | 0 | **3** | [impacto](../impacto/app-scalp_logic.md) |
| `app.api.positioning` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
