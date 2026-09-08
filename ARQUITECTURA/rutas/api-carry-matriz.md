# `GET /api/carry/matriz`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `carry_matriz` · `app/api.py:1168` (cuerpo hasta la 1183) · decorador en la linea 1167.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `dias` | `Annotated[int, Query(ge=2, le=90)]` | `15` | no |

## Campos que publica

15 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `as_of` | literal en app/carry.py:157 |
| `cobertura` | literal en app/carry.py:144 |
| `cobertura.celdas_esperadas` | literal en app/carry.py:145 |
| `cobertura.celdas_sin_funding` | literal en app/carry.py:146 |
| `cobertura.celdas_sin_oi` | literal en app/carry.py:147 |
| `cobertura.nota` | literal en app/carry.py:150 |
| `coste` | literal en app/carry.py:141 |
| `desde` | literal en app/carry.py:139 |
| `dias_pedidos` | literal en app/carry.py:137 |
| `dias_servidos` | literal en app/carry.py:138 |
| `funding_por_dia` | literal en app/carry.py:142 |
| `hasta` | literal en app/carry.py:140 |
| `oi_por_dia` | literal en app/carry.py:143 |
| `simbolos` | literal en app/carry.py:136 |
| `unidades` | literal en app/carry.py:156 |

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `daily_session_agg` — `sql/schema.sql:1032`, 37 columnas
  - la llena `app.daily_agg.compute_session` (INSERT) — `app/daily_agg.py:206`
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:670`

## Funciones que la componen

5 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2326`
- `app.carry.matriz_de_carry` — `app/carry.py:73`

<details><summary>Alcanzables de forma indirecta (3)</summary>

- `app.carry._pct` — `app/carry.py:41`
- `app.carry.coste_de_carry` — `app/carry.py:45`
- `app.carry.quien_paga` — `app/carry.py:62`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (3)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`
- `list`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 422 | — | `app/api.py:2335` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **panel** | `static/app.js:1589` | — |
| **panel-html** | `static/index.html:219` | — |

**La llama el panel: es superficie de producto.**

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['dias']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

Claves temporales entre los campos que publica:

- `as_of`

## Capa DECLARADA

**PENDIENTE de declaracion.** No existe `declarada/api-carry-matriz.md`.

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
| `app.api.rechaza_parametros_desconocidos` | 7 | **0** | 0 | **7** | [impacto](../impacto/app-api.md) |
| `app.api.carry_matriz` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.carry._pct` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-carry.md) |
| `app.carry.coste_de_carry` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-carry.md) |
| `app.carry.matriz_de_carry` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-carry.md) |
| `app.carry.quien_paga` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-carry.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
