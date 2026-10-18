# `GET /api/mesa/entradas`

> CAPA DERIVADA · **generada** por `harness/bin/arquitectura` desde el AST. No editar a mano:
> el proximo `arquitectura` lo pisa y K88 se pone ROJO. Lo que falte aqui se arregla
> en el generador, no en el fichero.

Handler `mesa_entradas` · `app/api.py:4098` (cuerpo hasta la 4111) · decorador en la linea 4097.

## Parametros de entrada

| nombre | tipo | por defecto | obligatorio |
|---|---|---|---|
| `request` | `Request` | — | lo pone el framework |
| `symbol` | `str` | — | si |

## Campos que publica

8 campos derivados. La procedencia dice de donde sale cada uno.

| campo | de donde sale |
|---|---|
| `disponible` | literal en app/entradas/vista.py:722 |
| `generador` | literal en app/entradas/vista.py:725 |
| `marco` | literal en app/entradas/vista.py:745 |
| `motivo` | literal en app/entradas/vista.py:723 |
| `papel` | literal en app/entradas/vista.py:765 |
| `precio` | literal en app/entradas/vista.py:724 |
| `reciente` | literal en app/entradas/vista.py:738 |
| `vivo` | literal en app/entradas/vista.py:737 |

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
  - la llena `app.libro.declara_hueco` (UPDATE) — `app/libro.py:792`
  - la llena `app.orderflow.declara_hueco` (UPDATE) — `app/orderflow.py:411`
- `entrada_latido` — `sql/schema.sql:2708`, 8 columnas
  - la llena `app.entradas.registro.latir` (INSERT) — `app/entradas/registro.py:222`
- `entrada_registro` — `sql/schema.sql:2671`, 26 columnas
  - la llena `app.entradas.registro.insertar` (INSERT) — `app/entradas/registro.py:31`
- `entrada_reglamento` — `sql/schema.sql:2661`, 6 columnas
  - la llena `app.entradas.registro.registrar_reglamento` (INSERT) — `app/entradas/registro.py:85`
- `entrada_resultado` — `sql/schema.sql:2849`, 12 columnas
  - la llena `app.entradas.resultados.guardar` (INSERT) — `app/entradas/resultados.py:62`
- `funding_rate` — `sql/schema.sql:146`, 7 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:669`
- `ohlcv` — `sql/schema.sql:54`, 13 columnas
  - la llena `app.daily_agg.apply_retention` (DELETE) — `app/daily_agg.py:655`
  - la llena `app.ingest.upsert_ohlcv` (INSERT) — `app/ingest.py:155`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`
  - la llena `app.ingest.rollup_ohlcv_5m` (INSERT) — `app/ingest.py:201`

**ESCRIBE** (una ruta de lectura que escribe merece mirarse):

- `entrada_resultado` — `sql/schema.sql:2849`, 12 columnas

## Funciones que la componen

78 funciones del arbol son alcanzables desde este handler. **Tocar cualquiera
de ellas puede cambiar esta ruta**; es la mitad de abajo del radio de impacto.

Llamadas directas del handler:

- `app.api.rechaza_parametros_desconocidos` — `app/api.py:2587`
- `app.api.validate_symbol` — `app/api.py:254`
- `app.entradas.vista.construir` — `app/entradas/vista.py:603`

<details><summary>Alcanzables de forma indirecta (75)</summary>

- `app.entradas.papel._pendiente` — `app/entradas/papel.py:63`
- `app.entradas.papel._sin_resultado` — `app/entradas/papel.py:74`
- `app.entradas.papel._usd` — `app/entradas/papel.py:59`
- `app.entradas.papel.cuenta` — `app/entradas/papel.py:87`
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
- `app.entradas.resolutor._cero` — `app/entradas/resolutor.py:488`
- `app.entradas.resolutor._cobros` — `app/entradas/resolutor.py:473`
- `app.entradas.resolutor._minuto` — `app/entradas/resolutor.py:182`
- `app.entradas.resolutor._pata` — `app/entradas/resolutor.py:212`
- `app.entradas.resolutor._t` — `app/entradas/resolutor.py:170`
- `app.entradas.resolutor._t23` — `app/entradas/resolutor.py:466`
- `app.entradas.resolutor.cobros_funding` — `app/entradas/resolutor.py:202`
- `app.entradas.resolutor.entrada_t` — `app/entradas/resolutor.py:191`
- `app.entradas.resolutor.foto_de` — `app/entradas/resolutor.py:186`
- `app.entradas.resolutor.iso` — `app/entradas/resolutor.py:178`
- `app.entradas.resolutor.resolver` — `app/entradas/resolutor.py:223`
- `app.entradas.resolutor.ventana` — `app/entradas/resolutor.py:196`
- `app.entradas.resultados.barrido` — `app/entradas/resultados.py:138`
- `app.entradas.resultados.de_filas` — `app/entradas/resultados.py:119`
- `app.entradas.resultados.guardar` — `app/entradas/resultados.py:104`
- `app.entradas.resultados.resolver_fila` — `app/entradas/resultados.py:89`
- `app.entradas.ruta._hipotesis` — `app/entradas/ruta.py:349`
- `app.entradas.ruta._reglamento` — `app/entradas/ruta.py:371`
- `app.entradas.ruta._resumen` — `app/entradas/ruta.py:156`
- `app.entradas.ruta.construir` — `app/entradas/ruta.py:199`
- `app.entradas.vista._ancla_no_puede` — `app/entradas/vista.py:580`
- `app.entradas.vista._base` — `app/entradas/vista.py:335`
- `app.entradas.vista._de` — `app/entradas/vista.py:514`
- `app.entradas.vista._decide` — `app/entradas/vista.py:250`
- `app.entradas.vista._disparado` — `app/entradas/vista.py:463`
- `app.entradas.vista._distancia` — `app/entradas/vista.py:322`
- `app.entradas.vista._fila_corta` — `app/entradas/vista.py:420`
- `app.entradas.vista._firmeza` — `app/entradas/vista.py:371`
- `app.entradas.vista._fraccion` — `app/entradas/vista.py:188`
- `app.entradas.vista._hora` — `app/entradas/vista.py:361`
- `app.entradas.vista._muestra` — `app/entradas/vista.py:545`
- `app.entradas.vista._orden` — `app/entradas/vista.py:520`
- `app.entradas.vista._papel` — `app/entradas/vista.py:427`
- `app.entradas.vista._papeles` — `app/entradas/vista.py:529`
- `app.entradas.vista._precio` — `app/entradas/vista.py:175`
- `app.entradas.vista._r` — `app/entradas/vista.py:184`
- `app.entradas.vista._requisitos` — `app/entradas/vista.py:347`
- `app.entradas.vista._resolutor` — `app/entradas/vista.py:769`
- `app.entradas.vista._resultado` — `app/entradas/vista.py:379`
- `app.entradas.vista._rotulo_de` — `app/entradas/vista.py:366`
- `app.entradas.vista._significado` — `app/entradas/vista.py:201`
- `app.entradas.vista._sombra` — `app/entradas/vista.py:504`
- `app.entradas.vista._vigilando` — `app/entradas/vista.py:355`
- `app.entradas.vista._zona` — `app/entradas/vista.py:317`
- `app.entradas.vista.componer` — `app/entradas/vista.py:631`
- `app.entradas.vista.pasada_en_curso` — `app/entradas/vista.py:560`
- `app.entradas.vista.precio_ahora` — `app/entradas/vista.py:165`

</details>

<details><summary>Llamadas que salen del arbol o no se resuelven (1)</summary>

Libreria de terceros, builtins o despacho dinamico. El analisis estatico se para aqui.

- `app.state.pool.acquire`

</details>

## Fallos que puede devolver

| codigo | detalle | donde | de quien |
|---|---|---|---|
| 404 | Unknown symbol | `app/api.py:256` | una funcion de su cierre |
| 422 | — | `app/api.py:2596` | una funcion de su cierre |

## Superficie · quien la consume (medido)

**LLAMADA** es una linea de codigo que la usa; **MENCION** es un comentario, un
docstring o un `.md` que la nombra. No pesan igual: una ruta cuyo unico rastro es un
comentario no tiene consumidor, tiene quien habla de ella.

| donde | llamadas | menciones |
|---|---|---|
| **checks** | — | `harness/checks/K102-mesa.py:481`, `harness/checks/K106-plantados.py:549` |
| **tests** | `tests/test_entradas_vista.py:148` | `tests/test_entradas_vista.py:1` |

**No la llama el panel**, pero si 1 linea(s) de codigo fuera de el.
Es **instrumento interno** — o una ruta que el panel dejo de usar y nadie retiro.

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

**PENDIENTE de declaracion.** No existe `declarada/api-mesa-entradas.md`.

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
| `app.api.rechaza_parametros_desconocidos` | 21 | **0** | 0 | **21** | [impacto](../impacto/app-api.md) |
| `app.entradas.reglamento.cargar_valido` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.valores` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.reglamento.versiones_en_curso` | 2 | **0** | 10 ↑ | **2** | [impacto](../impacto/app-entradas-reglamento.md) |
| `app.entradas.papel._pendiente` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-papel.md) |
| `app.entradas.papel._sin_resultado` | 2 | **0** | 0 | **2** | [impacto](../impacto/app-entradas-papel.md) |
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
| _… y 54 mas_ | | | | | [IMPACTO.md](../IMPACTO.md) |

**El inverso completo -si toco X, que rutas cambian- esta en**
[`IMPACTO.md`](../IMPACTO.md), con X funcion o tabla.
