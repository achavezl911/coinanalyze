# `GET /`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `index` · `app/api.py:3323` (cuerpo hasta la 3324) · decorador en la linea 3322.

## Parametros de entrada

_ninguno_

## Campos que publica

**PENDIENTE · no se ha podido derivar ni un campo.**

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- la respuesta pasa por FileResponse(), que no se puede seguir
- el valor devuelto es un BinOp, que no se analiza estaticamente

Tipo declarado en la firma: `FileResponse`.

## Tablas que toca

_ninguna consulta SQL literal en el cierre de esta ruta._

## Funciones que la componen

0 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `FileResponse`

</details>

## Fallos que puede devolver

_no levanta HTTPException en su cierre. Un fallo aqui sale como 500 del framework._

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

**NO MEDIBLE con este metodo, y se declara en vez de rellenarse.**

`/` casa con cualquier barra. Con el detector general esta ficha llegaba a
acreditar **505 citas** —`PAGE_W / 2`, `REPO / 'app/api.py'`, `ROOT / "docs"`—
y no informaba de nada.

Se intento un criterio propio antes de rendirse: exigir la barra **entrecomillada
y sola** (`'/'`, `"/"`, `GET /`). Baja de 505 a **23**, y las 23 siguen siendo
ruido, contadas una a una: `"/".join(...)`, `parsed.path.lstrip("/")`,
`open(DIR + "/" + nombre)`, `pathname: '/'` en un stub del navegador,
`not name.startswith("/")`. **Cero de las 23 son una peticion HTTP a la raiz.**

La barra entrecomillada es tan comun como la division, asi que **no hay criterio
textual que las separe en este repo**. Para saber quien consume la raiz hay que
mirar el servidor, no el codigo fuente:

```sh
prod "grep -c ' / ' /var/log/nginx/access.log"
```

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **1** — solo pide symbol (o nada): estado ambiente.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**Declarada** en [`declarada/raiz.md`](../declarada/raiz.md) — pregunta del trader,
familia de ventana decidida, promesa y superficie, cada una con su cita.

## Radio de impacto

El radio por tabla va con **dos numeros**: `k=0` es lo que la funcion escribe ella
misma (**exacto**) y `k<=2` sube por los llamadores (**cota superior declarada**;
lo que este mas arriba no se afirma).

Las funciones de esta ruta, y a cuantas rutas MAS llega cada una. Un numero alto
significa que ese arreglo de dos lineas no es de dos lineas:

| funcion | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto | detalle |
|---|---|---|---|---|---|
| `app.api.index` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
