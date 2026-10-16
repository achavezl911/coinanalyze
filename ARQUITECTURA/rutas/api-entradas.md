# `GET /api/entradas`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `entradas` · `app/api.py:1317` (cuerpo hasta la 1343) · decorador en la linea 1316.

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

19 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `cuentas` | literal en app/entradas/ruta.py:332 |
| `disponible` | literal en app/entradas/ruta.py:325 |
| `generador` | literal en app/entradas/ruta.py:326 |
| `generador.motivo` | literal en app/entradas/ruta.py:328 |
| `generador.ultimos_latidos` | literal en app/entradas/ruta.py:327 |
| `motivo` | literal en app/entradas/ruta.py:219 |
| `papel` | literal en app/entradas/ruta.py:341 |
| `por_lado` | literal en app/entradas/ruta.py:330 |
| `reglamento` | literal en app/entradas/ruta.py:331 |
| `reglamento.disponible` | literal en app/entradas/ruta.py:227 |
| `reglamento.motivo` | literal en app/entradas/ruta.py:227 |
| `reglamento.registro_en_base` | asignado en app/entradas/ruta.py:233 |
| `resultados` | literal en app/entradas/ruta.py:333 |
| `resultados.barrido_emparejado` | literal en app/entradas/ruta.py:339 |
| `resultados.cambios_e3` | literal en app/entradas/ruta.py:338 |
| `resultados.convenciones` | literal en app/entradas/ruta.py:337 |
| `resultados.huella_convenciones` | literal en app/entradas/ruta.py:336 |
| `resultados.que_es` | literal en app/entradas/ruta.py:334 |
| `resultados.resolutor` | literal en app/entradas/ruta.py:335 |

**Lo que de esta respuesta NO se sabe** (y por eso no se rellena):

- el objeto se expande con **base, que no se resuelve en el arbol: sus campos no se pueden derivar

Forma de la respuesta segun el AST: objeto.

Tipo declarado en la firma: `dict[str, Any]`.

## Tablas que toca

LEE:

- `data_gap` — `sql/schema.sql:1412`, 22 columnas
  - la llena `app.data_gaps.close_partitioned_gap` (UPDATE) — `app/data_gaps.py:1092`
  - la llena `app.data_gaps._mark_unrecoverable` (UPDATE) — `app/data_gaps.py:1243`
  - la llena `app.data_gaps._record_recovery_failure` (UPDATE) — `app/data_gaps.py:1262`
  - la llena `app.data_gaps.recover_gap` (UPDATE) — `app/data_gaps.py:1311`
  - la llena `app.data_gaps.record_data_gap` (INSERT) — `app/data_gaps.py:322`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:584`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:663`
  - la llena `app.data_gaps.reconcile_cadence_coverage` (UPDATE) — `app/data_gaps.py:687`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_beyond_source_horizon` (UPDATE) — `app/data_gaps.py:764`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
  - la llena `app.data_gaps.archive_source_response_absence` (UPDATE) — `app/data_gaps.py:862`
- `entrada_latido` — `sql/schema.sql:2702`, 8 columnas
  - la llena `app.entradas.registro.latir` (INSERT) — `app/entradas/registro.py:222`
- `entrada_registro` — `sql/schema.sql:2665`, 26 columnas
  - la llena `app.entradas.registro.insertar` (INSERT) — `app/entradas/registro.py:31`
- `entrada_reglamento` — `sql/schema.sql:2655`, 6 columnas
  - la llena `app.entradas.registro.registrar_reglamento` (INSERT) — `app/entradas/registro.py:85`
- `entrada_resultado` — `sql/schema.sql:2843`, 12 columnas
  - la llena `app.entradas.resultados.guardar` (INSERT) — `app/entradas/resultados.py:55`
- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:669`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`

**ESCRIBE** (una ruta de lectura que escribe merece mirarse):

- `entrada_resultado` — `sql/schema.sql:2843`, 12 columnas

## Funciones que la componen

49 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2586`
- `app.api.validate_symbol` — `app/api.py:253`
- `app.entradas.ruta.construir` — `app/entradas/ruta.py:196`

<details><summary>Alcanzables de forma indirecta (46)</summary>

- `app.entradas.papel._pendiente` — `app/entradas/papel.py:46`
- `app.entradas.papel._usd` — `app/entradas/papel.py:42`
- `app.entradas.papel.cuenta` — `app/entradas/papel.py:56`
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
- `app.entradas.resolutor._cero` — `app/entradas/resolutor.py:433`
- `app.entradas.resolutor._cobros` — `app/entradas/resolutor.py:418`
- `app.entradas.resolutor._minuto` — `app/entradas/resolutor.py:127`
- `app.entradas.resolutor._pata` — `app/entradas/resolutor.py:157`
- `app.entradas.resolutor._t` — `app/entradas/resolutor.py:115`
- `app.entradas.resolutor._t23` — `app/entradas/resolutor.py:411`
- `app.entradas.resolutor.cobros_funding` — `app/entradas/resolutor.py:147`
- `app.entradas.resolutor.entrada_t` — `app/entradas/resolutor.py:136`
- `app.entradas.resolutor.foto_de` — `app/entradas/resolutor.py:131`
- `app.entradas.resolutor.iso` — `app/entradas/resolutor.py:123`
- `app.entradas.resolutor.resolver` — `app/entradas/resolutor.py:168`
- `app.entradas.resolutor.ventana` — `app/entradas/resolutor.py:141`
- `app.entradas.resultados.barrido` — `app/entradas/resultados.py:129`
- `app.entradas.resultados.de_filas` — `app/entradas/resultados.py:110`
- `app.entradas.resultados.guardar` — `app/entradas/resultados.py:97`
- `app.entradas.resultados.resolver_fila` — `app/entradas/resultados.py:82`
- `app.entradas.ruta._hipotesis` — `app/entradas/ruta.py:346`
- `app.entradas.ruta._reglamento` — `app/entradas/ruta.py:368`
- `app.entradas.ruta._resumen` — `app/entradas/ruta.py:153`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (2)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `Query`
- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:255` | una funcion de su cierre |
| 422 | — | `app/api.py:2595` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | `harness/checks/K106-banco.py:52`, `harness/checks/K107-control.bash:70`, `harness/checks/K107-el-resultado-que-sale-de-su-plan.sh:35`, `harness/checks/K107-el-resultado-que-sale-de-su-plan.sh:37` _(+2)_ | `harness/checks/K107-control.bash:9`, `harness/checks/K107-el-resultado-que-sale-de-su-plan.sh:5`, `harness/checks/K107-el-resultado-que-sale-de-su-plan.sh:11`, `harness/checks/K107-el-resultado-que-sale-de-su-plan.sh:13` _(+3)_ |
| **tests** | `tests/test_entradas_ruta.py:72` | `tests/test_entradas_resultados_postgres.py:246`, `tests/test_entradas_ruta.py:1`, `tests/test_entradas_vista.py:10` |

**No la llama el panel**, pero si 7 linea(s) de codigo fuera de el.
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
| `app.entradas.papel._pendiente` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-papel.md) |
| `app.entradas.papel._usd` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-papel.md) |
| `app.entradas.papel.cuenta` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-papel.md) |
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
| _… y 25 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
