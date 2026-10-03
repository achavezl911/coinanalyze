# `GET /api/entradas`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `entradas` · `app/api.py:1296` (cuerpo hasta la 1322) · decorador en la linea 1295.

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
| `cuentas` | literal en app/entradas/ruta.py:282 |
| `disponible` | literal en app/entradas/ruta.py:275 |
| `generador` | literal en app/entradas/ruta.py:276 |
| `generador.motivo` | literal en app/entradas/ruta.py:278 |
| `generador.ultimos_latidos` | literal en app/entradas/ruta.py:277 |
| `motivo` | literal en app/entradas/ruta.py:181 |
| `por_lado` | literal en app/entradas/ruta.py:280 |
| `reglamento` | literal en app/entradas/ruta.py:281 |
| `reglamento.disponible` | literal en app/entradas/ruta.py:189 |
| `reglamento.motivo` | literal en app/entradas/ruta.py:189 |
| `reglamento.registro_en_base` | asignado en app/entradas/ruta.py:195 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **base, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `entrada_latido` — `sql/schema.sql:2702`, 8 columnas
  - la llena `app.entradas.registro.latir` (INSERT) — `app/entradas/registro.py:201`
- `entrada_registro` — `sql/schema.sql:2665`, 26 columnas
  - la llena `app.entradas.registro.insertar` (INSERT) — `app/entradas/registro.py:30`
- `entrada_reglamento` — `sql/schema.sql:2655`, 6 columnas
  - la llena `app.entradas.registro.registrar_reglamento` (INSERT) — `app/entradas/registro.py:74`

## Funciones que la componen

25 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2565`
- `app.api.validate_symbol` — `app/api.py:232`
- `app.entradas.ruta.construir` — `app/entradas/ruta.py:158`

<details><summary>Alcanzables de forma indirecta (22)</summary>

- `app.entradas.reglamento._texto` — `app/entradas/reglamento.py:118`
- `app.entradas.reglamento._valida_bloque` — `app/entradas/reglamento.py:122`
- `app.entradas.reglamento._valida_calendario` — `app/entradas/reglamento.py:220`
- `app.entradas.reglamento._valida_version` — `app/entradas/reglamento.py:141`
- `app.entradas.reglamento.canonico` — `app/entradas/reglamento.py:48`
- `app.entradas.reglamento.cargar` — `app/entradas/reglamento.py:318`
- `app.entradas.reglamento.cargar_valido` — `app/entradas/reglamento.py:322`
- `app.entradas.reglamento.contenido_bloque` — `app/entradas/reglamento.py:66`
- `app.entradas.reglamento.contenido_revision` — `app/entradas/reglamento.py:83`
- `app.entradas.reglamento.diferencia_con_padre` — `app/entradas/reglamento.py:353`
- `app.entradas.reglamento.huella` — `app/entradas/reglamento.py:55`
- `app.entradas.reglamento.huella_bloque` — `app/entradas/reglamento.py:79`
- `app.entradas.reglamento.huella_revision` — `app/entradas/reglamento.py:106`
- `app.entradas.reglamento.instante` — `app/entradas/reglamento.py:59`
- `app.entradas.reglamento.registros_esperados` — `app/entradas/reglamento.py:379`
- `app.entradas.reglamento.revision_vigente` — `app/entradas/reglamento.py:344`
- `app.entradas.reglamento.validar` — `app/entradas/reglamento.py:293`
- `app.entradas.reglamento.version` — `app/entradas/reglamento.py:340`
- `app.entradas.reglamento.version_activa` — `app/entradas/reglamento.py:335`
- `app.entradas.reglamento.versiones_en_curso` — `app/entradas/reglamento.py:330`
- `app.entradas.ruta._reglamento` — `app/entradas/ruta.py:286`
- `app.entradas.ruta._resumen` — `app/entradas/ruta.py:117`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:234` | una funcion de su cierre |
| 422 | — | `app/api.py:2574` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K43-foto-unica.sh:169` | `harness/checks/K43-foto-unica.sh:172` |
| **tests** | `tests/test_entradas_ruta.py:72` | `tests/test_entradas_ruta.py:1` |

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
| `app.api.validate_symbol` | 65 | **0** | 0 | **65** | [impacto](../impacto/app-api.md) |
| `app.entradas.reglamento.cargar_valido` | 1 | **0** | 9 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.versiones_en_curso` | 1 | **0** | 9 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.api.rechaza_parametros_desconocidos` | 8 | **0** | 0 | **8** | [impacto](../impacto/app-api.md) |
| `app.api.entradas` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-api.md) |
| `app.entradas.reglamento._texto` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_bloque` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_calendario` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento._valida_version` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.canonico` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.cargar` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.contenido_bloque` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.contenido_revision` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.diferencia_con_padre` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella_bloque` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.huella_revision` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.instante` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.registros_esperados` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.revision_vigente` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.validar` | 1 | **0** | 1 ↑ | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.version` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.version_activa` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.ruta._reglamento` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-ruta.md) |
| `app.entradas.ruta._resumen` | 1 | **0** | 0 | **1** | [impacto](../impacto/app-entradas-ruta.md) |
| _… y 1 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
