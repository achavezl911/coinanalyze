# `GET /api/entradas`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `entradas` · `app/api.py:1297` (cuerpo hasta la 1323) · decorador en la linea 1296.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `lado` | `Annotated[str, Query(pattern='^(ambos|largo|corto)$')]` | `'ambos'` | no |
| `desde` | `datetime | None` | `None` | no |
| `hasta` | `datetime | None` | `None` | no |
| `version` | `Annotated[str | None, Query(max_length=64)]` | `None` | no |
| `symbol` | `str | None` | `None` | no |
| `limite` | `Annotated[int, Query(ge=1, le=1000)]` | `200` | no |
| `foto` | `bool` | `False` | no |

## Campos que publica

11 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `cuentas` | literal en app/entradas/ruta.py:293 |
| `disponible` | literal en app/entradas/ruta.py:286 |
| `generador` | literal en app/entradas/ruta.py:287 |
| `generador.motivo` | literal en app/entradas/ruta.py:289 |
| `generador.ultimos_latidos` | literal en app/entradas/ruta.py:288 |
| `motivo` | literal en app/entradas/ruta.py:192 |
| `por_lado` | literal en app/entradas/ruta.py:291 |
| `reglamento` | literal en app/entradas/ruta.py:292 |
| `reglamento.disponible` | literal en app/entradas/ruta.py:200 |
| `reglamento.motivo` | literal en app/entradas/ruta.py:200 |
| `reglamento.registro_en_base` | asignado en app/entradas/ruta.py:206 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **base, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `entrada_latido` — `sql/schema.sql:2702`, 8 columnas
  - la llena `app.entradas.registro.latir` (INSERT) — `app/entradas/registro.py:222`
- `entrada_registro` — `sql/schema.sql:2665`, 26 columnas
  - la llena `app.entradas.registro.insertar` (INSERT) — `app/entradas/registro.py:31`
- `entrada_reglamento` — `sql/schema.sql:2655`, 6 columnas
  - la llena `app.entradas.registro.registrar_reglamento` (INSERT) — `app/entradas/registro.py:85`

## Funciones que la componen

30 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2566`
- `app.api.validate_symbol` — `app/api.py:233`
- `app.entradas.ruta.construir` — `app/entradas/ruta.py:169`

<details><summary>Alcanzables de forma indirecta (27)</summary>

- `app.entradas.reglamento._texto` — `app/entradas/reglamento.py:127`
- `app.entradas.reglamento._valida_apuestas` — `app/entradas/reglamento.py:308`
- `app.entradas.reglamento._valida_bloque` — `app/entradas/reglamento.py:131`
- `app.entradas.reglamento._valida_calendario` — `app/entradas/reglamento.py:229`
- `app.entradas.reglamento._valida_version` — `app/entradas/reglamento.py:150`
- `app.entradas.reglamento.apuestas` — `app/entradas/reglamento.py:340`
- `app.entradas.reglamento.canonico` — `app/entradas/reglamento.py:57`
- `app.entradas.reglamento.cargar` — `app/entradas/reglamento.py:383`
- `app.entradas.reglamento.cargar_valido` — `app/entradas/reglamento.py:387`
- `app.entradas.reglamento.celdas` — `app/entradas/reglamento.py:302`
- `app.entradas.reglamento.contenido_bloque` — `app/entradas/reglamento.py:75`
- `app.entradas.reglamento.contenido_revision` — `app/entradas/reglamento.py:92`
- `app.entradas.reglamento.diferencia_con_padre` — `app/entradas/reglamento.py:418`
- `app.entradas.reglamento.huella` — `app/entradas/reglamento.py:64`
- `app.entradas.reglamento.huella_bloque` — `app/entradas/reglamento.py:88`
- `app.entradas.reglamento.huella_revision` — `app/entradas/reglamento.py:115`
- `app.entradas.reglamento.instante` — `app/entradas/reglamento.py:68`
- `app.entradas.reglamento.registros_esperados` — `app/entradas/reglamento.py:444`
- `app.entradas.reglamento.revision_vigente` — `app/entradas/reglamento.py:409`
- `app.entradas.reglamento.validar` — `app/entradas/reglamento.py:357`
- `app.entradas.reglamento.valores` — `app/entradas/reglamento.py:119`
- `app.entradas.reglamento.version` — `app/entradas/reglamento.py:405`
- `app.entradas.reglamento.version_activa` — `app/entradas/reglamento.py:400`
- `app.entradas.reglamento.versiones_en_curso` — `app/entradas/reglamento.py:395`
- `app.entradas.ruta._hipotesis` — `app/entradas/ruta.py:297`
- `app.entradas.ruta._reglamento` — `app/entradas/ruta.py:319`
- `app.entradas.ruta._resumen` — `app/entradas/ruta.py:128`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:235` | una funcion de su cierre |
| 422 | — | `app/api.py:2575` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:169` | `harness/checks/K43-foto-unica.sh:172` |
| **tests** | `tests/test_entradas_ruta.py:72` | `tests/test_entradas_ruta.py:1`, `tests/test_entradas_vista.py:10` |

**No la llama el panel**, pero si 2 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

## Ventana · con que clave la declara (derivado)

Familia **candidata** de K43: **sin decidir** — parametros ['desde', 'foto', 'hasta', 'lado', 'limite', 'symbol', 'version']: no encaja en 1/2/3 sin leerla.

K43 · (1) ventana de construccion de la foto · (2) coverage de su propia serie ·
(3) su propio `as_of` bajo demanda · (4) exenta con cita.

**Es una candidata derivada de la firma, no la declaracion.** La decide una persona
en el fichero de la capa declarada y puede corregirla con cita.

**Ninguna clave temporal entre los campos derivados.** O no publica marca de
tiempo, o sus campos no se pudieron derivar (mira arriba). Lo segundo NO es lo
mismo que lo primero: la foto de produccion lo decide, no este documento.

## Capa DECLARADA

**PENDIENTE de declaracion.** No existe `declarada/api-entradas.md`.

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
| `app.api.validate_symbol` | 66 | **0** | 0 | **66** | [impacto](../impacto/app-api.md) |
| `app.entradas.reglamento.cargar_valido` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.valores` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.versiones_en_curso` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.api.rechaza_parametros_desconocidos` | 9 | **0** | 0 | **9** | [impacto](../impacto/app-api.md) |
| `app.entradas.reglamento._texto` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_apuestas` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_bloque` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_calendario` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_version` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.apuestas` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.canonico` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.cargar` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.celdas` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.contenido_bloque` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.contenido_revision` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.diferencia_con_padre` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella_bloque` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella_revision` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.instante` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.registros_esperados` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.revision_vigente` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.validar` | 2 | **0** | 2 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.version` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| _… y 6 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
