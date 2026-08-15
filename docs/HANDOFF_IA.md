# Traspaso — coinanalyze

**Léelo entero antes de tocar nada.** Está escrito para que una persona o una IA retome el
proyecto desde cero sabiendo qué está hecho, qué no, qué está bloqueado y cuál es la
siguiente acción exacta.

Toda afirmación lleva estado explícito. Donde falta evidencia, se dice — no se inventa.

| Estado | Significado |
|---|---|
| `CONFIRMED` | Verificado aquí con evidencia reproducible (test, comando, SHA). |
| `DECIDED` | Decisión tomada y registrada; no es un hecho medido. |
| `PLANNED` | Acordado, no empezado. |
| `BLOCKED` | No avanza hasta resolver una dependencia declarada. |
| `EXTERNAL_UNVERIFIED` | Depende de un sistema fuera del repo; no verificado desde aquí. |
| `MISSING_EXTERNAL_EVIDENCE` | Se esperaría un artefacto externo y **no existe**. |

Revisión de este documento: **2026-08-15**. Supersede al handoff v1.3.7, cuyo contenido de
producto se conserva en §9.

---

## 1. Qué hace el proyecto

`CONFIRMED`

Dashboard interno de microestructura y scalping para perpetuos **BTC, ETH y SOL**, con una
capa científica encima cuyo objetivo es producir **un resultado confirmatorio auditable**:
si una señal funciona, poder demostrarlo con evidencia congelada de antemano.

Dos mitades que no deben confundirse:

- **Operación** — colectores, API FastAPI, dashboard, alertas. Cambia cuando hace falta.
- **Evidencia confirmatoria** — observaciones append-only, replay determinista, outcomes,
  visibilidad certificada, walk-forward y un resultado autoritativo único por manifest.
  Se congela **antes** de mirar los datos.

El detalle de arquitectura, con diagramas, está en
[`SCIENTIFIC_ARCHITECTURE.md`](SCIENTIFIC_ARCHITECTURE.md).

## 2. Roles — quién hace qué

`DECIDED`

| Rol | Puede | No puede |
|---|---|---|
| **ChatGPT Work** | Arquitecto y revisor: diseño, revisión adversarial, definición de criterios de cierre | Implementar en la rama, mergear, desplegar |
| **ChatGPT Chat** | Troubleshooting limitado y puntual | Decidir arquitectura, implementar cierres, aprobar revisiones |
| **Claude Code** | Implementador: analizar, implementar, tests, commit, push de **su** rama, crear/revisar PRs | Mergear, desplegar, tocar producción, `push --force`, crear otra rama o PR para esta tarea |
| **Humano** | Review, merge, deploy y producción | — |

### 2.1 Protocolo de validación adversarial

`DECIDED` — vinculante. Esta serie ya produjo **tres intentos de cierre autoafirmados y
refutados**, en cinco commits: `c879bdec`; `700f7695` + `450cf2fb`; `e84ebe81` + `9b2e082c`.
El protocolo existe porque la autoafirmación falló, y falló las tres veces con la suite en
verde.

- **ChatGPT Work siempre cuestiona y valida de forma independiente el código de Claude.** No
  revisa el informe: revisa el árbol, ejecuta sus propias mutaciones e intenta reproducir el
  bypass con vectores que **no** estén ya en la suite.
- **Un informe de Claude no es una aprobación. Un CI en verde tampoco.** Ambos son insumos de
  la revisión, no su resultado. Una suite verde sólo demuestra que las mutaciones *escritas*
  se detectan; el trabajo de Work es encontrar las que faltan.
- **Si Work refuta a Claude, entrega el veredicto y el prompt correctivo juntos**, en el mismo
  mensaje: hallazgos con severidad (P0/P1/P2), evidencia reproducible y el prompt completo que
  corrige. Un veredicto sin prompt correctivo bloquea el trabajo sin desbloquearlo.
- **Cada prompt futuro a Claude exige actualizar [`HANDOFF_IA.md`](HANDOFF_IA.md) en GitHub,
  sin excepción**, commiteado y pusheado en la misma rama. No es un extra ni una fase
  opcional: un entregable sin handoff actualizado está incompleto.
- **Todo prompt a Claude incluye, explícitamente**: HEAD esperado · alcance · invariantes ·
  pruebas rojas a reproducir primero · criterios de aceptación · validación exigida ·
  evidencia a entregar · prohibiciones.
- Este documento debe poder leerse **sin contexto de ningún chat**: propósito (§1), alcance y
  límites (§9), arquitectura (§4), estado (§3, §8) y siguiente paso (§11) viven aquí.

## 3. Estado exacto de PR27 y PR28

### PR #27 — `codex/pr27-confirmatory-endpoint-integrity` → `main`

`CONFIRMED: abierta, sin mergear`

Remediación de integridad del endpoint confirmatorio. Es la **base** de PR #28.

### PR #28 — `claude/pr27-r03-runtime-config-closure` → `codex/pr27-confirmatory-endpoint-integrity`

`CONFIRMED: abierta, apilada, NO mergeable todavía`

<https://github.com/achavezl911/coinanalyze/pull/28>

**Base: `codex/pr27-confirmatory-endpoint-integrity`, no `main`. DO NOT MERGE.** Orden
obligatorio: primero PR #27 → `main`, después PR #28.

**`mergeable=true` en GitHub no significa aprobado.** Es una afirmación sobre conflictos de
texto, no sobre revisión: dice que Git sabría fusionar, no que alguien haya validado nada. PR
#28 sigue marcada **DO NOT MERGE** hasta que (a) PR #27 entre en `main` y (b) exista una
revisión independiente con P0=0 y P1=0.

`CONFIRMED 2026-08-15` — consultado con `gh pr view 28`: `state=OPEN`,
`mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`. Es decir: **técnicamente mergeable, pero
bloqueado — DO NOT MERGE.**

### SHAs de la serie

| Rework | SHA | Estado |
|---|---|---|
| Implementación inicial | `5a99ab5371eca057afc7374ed8cbf544e558113e` | landed |
| R01 | `e58f1fab2b8ebfd158608805fafc87fc559211c7` | landed (HEAD de PR #27) |
| R02 | **no existe commit identificable** | declarado, no inventado |
| R03 | `0496819a15699bae3b80fc92e803a50adf40df54` | landed |
| R04 | `ee3792ca9f26b1cc20f354e9eaf35332b8ce266e` | landed, incompleto |
| **R05 candidato parcial** | `c879bdecf5eb453b5a91853e917be79d3df9042d` | **REFUTADO: A-02 abierto** |
| **R05 candidato de cierre** | `700f7695f97c1d094a2180b7a6916686429abda3` | **REFUTADO: mutaciones por primera aparición textual** |
| **R05 continuidad documental** | `450cf2fb5633779755f3d7db4069fc86a800eb8b` | **REFUTADO junto con `700f7695`** |
| **R05 cierre de wiring (código)** | `e84ebe8140c8393ea2ef3447d8c165d32b594917` | **REFUTADO: cinco mutaciones conservaban el digest** |
| **R05 continuidad documental** | `9b2e082c46d432ee4e4727fb5e9e18feba414b63` | **REFUTADO junto con `e84ebe81`** |
| **R05 cierre por módulo (código)** | `f83a468a2d30854f4cad5f96d4b85d0ad50daaf6` | **CANDIDATO**, pendiente de revisión |
| **Continuidad documental** | el commit inmediatamente posterior a `f83a468a` | HEAD de PR #28 |

El primero es el commit de código, tests e identidad; el segundo es documentación y handoff y
cita el SHA del primero. Esta corrección **no es R06**: sigue siendo el cierre del mismo R05,
en su **cuarto** intento.

### 3.1 Serie de identidad científica — bitácora

`CONFIRMED` — una entrada por commit, con el recuento de escapes medido, no declarado. La
reescritura completa de este documento corresponde al commit 4 de la serie.

| Fecha | Commit | Alcance | Escapes al cierre |
|---|---|---|---|
| 2026-08-15 | `de80d856` | Matriz de mutación permanente y evidencia roja sobre `c60e2ee6`. No toca `app/`. | 12 (vocabulario antiguo, 23 mutaciones, 1 `SKIPPED`) |
| 2026-08-15 | `e874927` | Corrección del instrumento: `MUST_MOVE_AND_REJECT`, M-07 por `file_create`, M-16 sin `skip`, M-24..M-31, canal de ancla externo. No toca `app/`. | 30 de 31 |
| 2026-08-15 | `a5893c7` (3.1) | **Primer commit que toca `app/`.** Superficie descubierta (`app/**/*.py`, `sql/schema.sql`, `pyproject.toml`, `requirements.lock`, `config/**/*.json`), rechazo de symlinks, canonicalización por lista explícita de campos AST, docstrings materiales, entorno con intérprete y `Settings` de cobertura, registro declarativo `identity/registry.json` con perfiles enumerados, punto de entrada combinado `validate_scientific_identity()`. Repara H-1 y H-2. M-32, M-33. | 8 de 33 |
| 2026-08-15 | **este commit (3.2)** | **Verificación post-import.** C.1 procedencia de `sys.modules`; C.2 hash del objeto enlazado en tiempo de evaluación; lógica del registro movida a `app/` (B-8); `requires-python` estrechado a `>=3.13,<3.14` (B-6); caché de componentes acotada (B-7); `provisioning_problems()` falla cerrado si el árbol alcanza un fallback poblado (B-10); clase `RESIDUAL`; M-34, M-35, M-38; manifiesto de marcadores (D-1). | **4 de 36, más 2 `RESIDUAL`** |

Estado medido al cierre de 3.2, **no declarado**:

- **`GUARD` (30).** C.1 cerró `M-06` y `M-27`; C.2 cerró `M-05` y `M-31`; mover el generador del
  registro a `app/` cerró `M-35`. Las 25 filas cerradas en 3.1 siguen `GUARD`; `M-26`, `M-32` y
  `M-33` no regresan.
- **`ESCAPE` (4): `M-02`, `M-28`, `M-29`** — los tres de D, que cierra el ancla del commit 3.3 —
  **y `M-01`**, que **no** cerró. Ver §6.3: la mutación es detectada, y lo que mantiene la fila
  abierta es una conjunción del instrumento, no un fallo del código.
- **`RESIDUAL` (2): `M-34`, `M-38`.** No son escapes perdonados: son escapes que se cierran
  **fuera** del proceso. Argumento escrito y controles compensatorios en
  `tests/identity_mutation/known_escapes.json`, sección `residual`, y exigidos por test sobre
  `deploy/systemd/*.service`.

## 6.3 Hallazgo abierto de este commit: `M-01` no cierra, y la causa es el instrumento

`CONFIRMED — medido, no argumentado`

C.2 **sí** detecta M-01. La prueba es una comparación controlada dentro de la misma corrida:

| Fila | Mutación | `code_digest` | `rejection_kind` | `combined_validation_accepted` | Clase |
|---|---|---|---|---|---|
| `M-01` | reasigna `validate_scientific_implementation_identity` en runtime | `c9e9b5a5…` | `exception` | `False` | **ESCAPE** |
| `M-31` | lo mismo, instalado por `sitecustomize` antes del import | `c9e9b5a5…` | `exception` | `False` | **GUARD** |

Las dos filas producen **la misma medición**: el mismo digest, el mismo rechazo. Difieren en una
sola cosa: `M-01` lleva `REQUIRE_FORGED_REJECTED` en `also_requires`, y esa conjunción pregunta
**al medio validador que la propia mutación reemplazó** si acepta un objeto forjado. Un `lambda
stored: stored` escrito para aceptar cualquier cosa, acepta. La conjunción es por tanto
insatisfacible para cualquier mutación cuyo payload sea reemplazar ese símbolo, y ninguna
cantidad de ingeniería sobre `app/` la puede cerrar.

Es una inconsistencia interna del instrumento, introducida en 3.1 y no migrada entonces: el
propio `probe.py` documenta que el medio validador «decide nada por sí solo» y que **el validador
combinado es lo que decide cada efecto del catálogo**, pero `REQUIRE_FORGED_REJECTED` sigue
interrogando al medio validador.

**No se ha tocado.** El prompt de este commit prohíbe explícitamente ajustar el test al
resultado, así que `EXPECTED_OPEN_ESCAPES` conserva el conjunto mandado `{M-02, M-28, M-29}` y la
divergencia queda **roja y visible** en `test_the_declared_escape_set_is_exactly_the_expected_one_for_this_commit`
y en `test_the_findings_this_commit_closes_are_guards_by_name[M-01]`. La corrección propuesta —
que `REQUIRE_FORGED_REJECTED` interrogue al validador combinado, que es donde ya vive la pregunta
— es de una línea y **requiere autorización de la revisión independiente**, no de quien
implementa.

Consecuencia operativa introducida aquí, que el commit 4 documenta en detalle: cualquier
cambio a `app/**/*.py`, `sql/schema.sql`, `pyproject.toml`, `requirements.lock` o
`config/**/*.json` — **incluido un docstring** — obliga a regenerar el registro con
`python scripts/register_identity.py` y a commitear `identity/registry.json`. El CI lo
verifica con `--check`, así que un registro obsoleto es rojo, no un aviso.

## 4. Arquitectura científica vigente

`CONFIRMED`

Dos identidades independientes, ambas con registro append-only:

| | Identidad científica | Contrato de runtime |
|---|---|---|
| Responde | qué calcula el código | qué insumos crudos seleccionó |
| Digest vigente | `451f49552b732bd829a72c10fb2a615cd9d74e0a2a471f677cbd7642975ac378` (**candidato**) | `c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00` (sin cambios) |
| Componentes | 42: la superficie **descubierta** entera (`app/**/*.py`, `sql/schema.sql`, `pyproject.toml`, `requirements.lock`, `config/**/*.json`) | 4 campos resueltos por símbolo |

**El valor autoritativo es `identity/registry.json`, no esta tabla.** Cualquier digest citado en
prosa es una instantánea de un commit y envejece; el registro es lo que el runtime compara. Desde
3.2 el digest lleva además dos bloques de verificación post-import, `module_provenance` y
`bound_objects`, vacíos en un proceso honesto y por tanto constantes entre despliegues.

Desde esta corrección la identidad tiene **dos formas de componente** (ADR-012):

- **Región** (`python` / `sql`) — hashea el texto entre dos marcadores `BEGIN/END`. Es la
  forma correcta para un fichero grande cuya parte científica es una minoría bien delimitada.
- **Módulo** (`python_module`) — hashea el **AST completo del fichero**, sin marcadores y sin
  lista de símbolos. Se aplica a `app/scalp_collector.py`, `app/ws_collector.py` y
  `app/signal_runtime_contract.py`, los tres ficheros donde cualquier cosa ejecutable puede
  cambiar lo que observan los colectores crudos.

En ambas formas la canonicalización es la misma: comentarios, docstrings, líneas en blanco,
ancho de indentación y posiciones de origen **no** mueven el digest; lo ejecutable sí.

Hashes legacy spec v1/v2/v3, `CONFIRMED` sin cambios: `e2f967bb…`, `2f21afe9…`, `7fd50764…`.

**El ruteo atestiguado** es la parte que ha concentrado el trabajo. Cadena completa, toda
dentro de la identidad: cuatro proyecciones → contrato registrado → atestación (que además
exige que los mapas efectivos coincidan) → `EffectiveMarketRouting` congelado → **reatestación
de procedencia al construir el índice** → índice de ruteo que valida cada conversión →
URL/topics → conexión → handler → store → entrega guardada → SQL. La inyección de ese único
ruteo y la **creación de las tareas materiales** también viven dentro de la identidad. Fuera
de la identidad, a propósito y fijado por test en ambas direcciones: reconexión, backoff,
logging, health de feeds, sleeps y parámetros de transporte WS.

El invariante que sostiene todo esto, y que las tres iteraciones anteriores enunciaron sin
hacerlo cumplir:

> Todo cambio capaz de alterar venue, suscripción, sesión, par externo, conversión a clave
> interna, entrada al store, ruteo por tarea o entrega raw debe **mover la identidad
> científica** o quedar **estructuralmente impedido** antes de suscribirse o escribir.

## 5. Qué resolvió R05 (`c879bdec`) — y qué no

### Resolvió: A-01

`CONFIRMED`

La atestación de R04 recomputaba el contrato desde `MARKET_SYMBOL_CATALOG`, pero los
productores aplicaban `WS_SYMBOL_MAP`, `FUTURES_PAIR_MAP`, `SPOT_PAIR_MAP` y
`PAIR_SYMBOL_MAP`: cuatro dicts mutables derivados al importar. Con cualquiera divergido, el
contrato seguía coincidiendo con su digest y todo pasaba mientras los colectores escribían
bajo el ruteo divergente.

R05 lo cerró: la atestación valida también los mapas y devuelve un `EffectiveMarketRouting`
congelado que el productor aplica explícitamente.

### No resolvió: A-02

`CONFIRMED como defecto abierto en c879bdec`

Las regiones cubrían los *builders* y los *handlers*, pero no los puntos donde el ruteo se
aplica: `binance_loop`, `binance_market_loop`, `bybit_loop`, `binance_consumer`,
`bybit_consumer`, `main` y `run`.

## 6. Hallazgos de la revisión independiente sobre `c879bdec`

`CONFIRMED — reproducidos aquí antes de tocar código`

**Hallazgo 1 — el bypass de ruteo no movía la identidad.** Sustituyendo, fuera de toda
región protegida, `routing.futures_index(ACTIVE_SYMBOLS)` por
`FuturesRoutingIndex(pairs=("ETHUSDT",), symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"})`
—y la mutación análoga con `SpotRoutingIndex`— el digest permanecía en `25f6c2e5…`. El
handler convertía datos ETH en la clave interna BTC y, como la entrega sólo validaba la
*clave interna* (que es legítima), el bypass alcanzaba el store y la escritura.

**Hallazgo 2 — la región de `config.py` era demasiado ancha.** `whale_threshold_usd`
`5_000_000 → 5_000_001` movía el digest de `25f6c2e5…` a `06da5f1f…`, contradiciendo la
exclusión documentada de esos umbrales.

**Hallazgo 3 — afirmación documental falsa.** `PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md`
afirmaba que «un bypass que evite las regiones no puede alcanzar la ruta de escritura».
Eliminada.

Evidencia roja: `tests/test_pr27_r05_routing_application_closure.py` sobre `c879bdec` →
**31 fallos, 11 pasos**.

Lo que `700f7695`/`450cf2fb` hicieron con estos hallazgos fue **insuficiente**, y por eso una
segunda revisión los refutó. Ver §6.1.

## 6.1 Hallazgos de la segunda revisión, sobre `700f7695`/`450cf2fb`

`CONFIRMED — reproducidos aquí antes de tocar código`

La causa raíz es metodológica: el helper `_mutate` de
`test_pr27_r05_routing_application_closure.py` reescribe la **primera aparición textual** de
cada expresión. Tras aquella corrección, la primera aparición siempre quedaba *dentro* de una
región —`routing.futures_index(ACTIVE_SYMBOLS)` en `scalp_futures_index()`,
`binance_loop(routing=routing)` en `scalp_routing_producers()`— así que el digest se movía, la
suite se ponía verde y **los puntos de llamada reales seguían desprotegidos**.

**Hallazgo P1-1 — la inyección real del ruteo estaba fuera de la identidad.** Las invocaciones
reales son `scalp_routing_producers(pool, service_lock, routing)` en `main()` y
`ws_routing_producers(pool, service_lock, symbols, routing)` en `run()`. Sustituirlas por
wiring directo con un ruteo falso para el productor y el correcto para el flusher dejaba el
digest en `5a5cb09f…`.

**Hallazgo P1-2 — la selección real de sesión estaba fuera de la identidad.**
`binance_futures_session → binance_market_session` dentro de `binance_loop()`, y
`binance_spot_session → bybit_spot_session` dentro de `binance_consumer()`: ambas mutaciones
dejaban el digest en `5a5cb09f…`.

**Hallazgo P1-3 — `EffectiveMarketRouting` es construible a mano.** Un ruteo forjado con
`symbol="BTCUSDT_PERP.A", futures_pair="ETHUSDT"` es autoconsistente y puede llevar el digest
registrado como simple cadena de texto, así que producía `FuturesRoutingIndex`/`SpotRoutingIndex`
ETHUSDT→BTC sin objeción. La entrega, sosteniendo el ruteo **correcto**, aceptaba la clave
resultante porque esa clave sí está ruteada.

**Hallazgo P2-4 — trailing whitespace.** El rango `700f7695..450cf2fb` introdujo trailing
whitespace en `.github/pull_request_template.md` (líneas 64, 65, 67, 68, 69 y 87) pese a que el
informe anterior afirmó que `git diff --check` estaba limpio.

Evidencia roja: `tests/test_pr27_r05_routing_wiring_closure.py` sobre `450cf2fb` →
**25 failed, 6 passed**.

## 6.2 Hallazgos de la tercera revisión, sobre `e84ebe81`/`9b2e082c`

`CONFIRMED — reproducidos aquí en rojo antes de tocar código`

La causa raíz vuelve a ser metodológica, un nivel más arriba: la identidad seguía apoyándose
en **regiones parciales más `MATERIAL_SYMBOLS`**, es decir en una **enumeración**. Una
enumeración sólo puede sostener la propiedad «lo enumerado no cambió», y eso es lo que rodean
tanto un ataque como un error honesto. Cinco mutaciones conservaron indebidamente el digest
`c939add3…`:

1. **Escritura directa en `TRADE_STORE` fuera de toda región protegida.** `TRADE_STORE` se
   define en `app/scalp_collector.py:442` y `monitor()` está fuera de las tres regiones, así
   que fabricar buckets ahí no llega al digest.
2. **Un helper nuevo que escribe en el store, lanzado desde `main()`.** `main()`
   (`app/scalp_collector.py:1817`) está íntegramente fuera de la identidad, de modo que tanto
   el helper como su `create_task` son invisibles.
3. **Invertir la clasificación buy/sell en `TradeBucket.add`** (`app/scalp_collector.py:125`).
   La agresión es de donde sale todo el resultado de microestructura.
4. **Ampliar el bucket realtime de 5 a 10 segundos** (`app/scalp_collector.py:149`). Cambia la
   rejilla de observación sin mover el digest.
5. **Sustituir `from functools import partial`** (`app/scalp_collector.py:12`) por una
   implementación que descarta el último argumento ligado — que es el `routing` atestiguado
   en cada binding de productor.

Ninguna se corrige añadiendo nombres a `MATERIAL_SYMBOLS`: 1 y 2 son código nuevo, 3 y 4 son
aritmética dentro de código existente, y 5 sustituye un builtin del lenguaje.

Evidencia roja: `tests/test_pr27_r05_module_identity_closure.py` sobre `9b2e082c` →
**12 failed, 8 passed**. Las cinco mutaciones canónicas fallan con el mensaje «the mutation
left the scientific identity at c939add3…»; las pruebas de neutralidad y determinismo ya
pasaban en rojo, que es lo que se espera de un control negativo.

## 7. Qué cierra esta corrección (cierre por módulo completo)

`CONFIRMED en esta rama · pendiente de revisión independiente`

**La decisión de fondo: dejar de enumerar.** Se añade a la identidad un tipo de componente
`python_module` que canonicaliza el **AST completo** de un fichero, sin marcadores `BEGIN/END`
y sin lista de símbolos, y se aplica a los tres módulos que deciden qué observan los
colectores crudos — `app/scalp_collector.py`, `app/ws_collector.py` y
`app/signal_runtime_contract.py`. Los **siete** componentes parciales que se solapaban con
esos ficheros quedan **sustituidos** por los tres de módulo: 32 → **28** componentes.

La cobertura de módulo incluye, por construcción y sin tener que enumerarlo: imports, parsing,
clasificación de agresión, cálculo de buckets, stores, colas, sesiones, loops, flush, delivery,
creación de tareas y entrypoints. No hay superficie que recordar y por tanto no hay superficie
que olvidar.

**Coste aceptado, explícito y provisional.** Backoff, logging, health de feeds, sleeps y
parámetros de transporte WS en los dos colectores **dejan de ser neutrales**: cualquier cambio
ejecutable en esos tres módulos mueve identity-v1. Los tests que fijaban esa neutralidad se
**invierten** en vez de borrarse, para que el precio quede medido y no supuesto. Recuperar la
neutralidad exigiría reintroducir una enumeración, que es justo lo refutado tres veces.

**Lo que se conserva de la iteración anterior**, sin cambios: `require_attested_routing()` y
toda la cadena de procedencia de ADR-011; `MATERIAL_SYMBOLS` y los barridos estructurales,
ahora **sólo como defensa adicional**; los marcadores `BEGIN/END` en el código, como
comentarios inertes que esos barridos siguen leyendo. Los helpers de spans se re-anclaron a
los marcadores del **fichero** en vez de al registro de componentes, así que ya no se pueden
desactivar editando la lista de componentes — es más estricto que antes, no menos.

Identidad recomputada: `c939add3…` → `c7bf8e5b…`, 28 componentes.

Lo que sigue, del cierre de wiring anterior, y que esta corrección no toca:

**1. Procedencia — el índice sólo existe donde el registro está de acuerdo.**
`require_attested_routing()` **re-deriva** el contrato desde el catálogo, los settings y los
mapas efectivos vivos, y exige que reproduzca exactamente las filas del ruteo en uso. Ambos
índices lo llaman en `__post_init__`. Un ruteo forjado —o uno atestiguado que después haya
divergido— falla cerrado **antes** de suscribirse, antes del store y antes de escribir. La
autoconsistencia y una cadena de digest dejan de ser evidencia.

**2. Estructura — no queda nada material fuera que mutar.** Los bucles de reconexión y los de
flush reciben un `connect`/`cycle` **ya ligado**, construido dentro de la identidad: no nombran
venue, ni sesión, ni store, ni entrega, ni ruteo. `main()`/`run()` llaman
`require_attested_*_routing()` y `start_*_routing_producers()`; esta última atestigua, cablea y
**crea las tareas materiales** dentro de la identidad, de modo que el entrypoint nunca sostiene
un `EffectiveMarketRouting` que pudiera redirigir. Un barrido AST endurecido exige que
**ningún símbolo material se lea fuera de una región** en ninguno de los dos colectores.

**3. Anclaje — las mutaciones apuntan al sitio real.** Localizan cada referencia por AST, no
por desplazamiento textual, así que una expresión duplicada dentro de una región no puede
hacerse pasar por la real. Las cinco mutaciones nuevas siguen la misma regla: se anclan en el
nodo (`ast.If` dentro de `TradeBucket.add`, `ast.Constant` dentro de la asignación de `rt_ts`,
el propio `ast.ImportFrom`) y reescriben en los desplazamientos de byte de ese nodo.

Se conserva también: sesiones, endpoints de venue, construcción del índice, URL/topics,
conexión, despacho y traspaso store → entrega dentro de la identidad; región de `config.py`
reducida a las cuatro proyecciones.

## 8. Confirmado / pendiente / bloqueado / no verificado

### CONFIRMED

- Línea base sobre `9b2e082c` con PostgreSQL 17.10: **1545 passed, 0 failed, 0 skipped**.
- Suite completa sobre esta corrección con PostgreSQL 17.10 (`TEST_DATABASE_URL` exportada,
  clúster aislado como el del CI): **1565 passed, 0 failed, 0 skipped** (959 s). Los 20 nuevos
  son `tests/test_pr27_r05_module_identity_closure.py`; la línea base eran 1545.
- `ruff check .` limpio · `compileall` OK · `node --test tests/js/` 49 pass 0 skip ·
  `git diff --check` limpio.
- Runtime contract digest `c9cbe967…` **sin cambios**; hashes legacy spec v1/v2/v3
  (`e2f967bb…`, `2f21afe9…`, `7fd50764…`) **sin cambios**. Sólo se mueve identity-v1, que es
  precisamente lo que la corrección amplía.
- Las cinco mutaciones reproducidas en rojo **antes** de tocar código (§6.2) y cerradas con
  tests que pasan de rojo a verde.
- **Ningún test se debilitó.** Los que cambiaron lo hicieron en una de dos direcciones, ambas
  declaradas:
  - **Más estrictos**: los barridos estructurales leen ahora los marcadores del fichero en vez
    del registro de componentes, así que no se pueden desactivar editando la lista;
    `test_contract_mechanics_are_covered_by_the_scientific_identity` y
    `test_guard_is_frozen_by_the_scientific_identity` exigen cobertura de módulo completo en
    lugar de una región.
  - **Invertidos a propósito**: los tres tests de neutralidad operativa
    (`test_operational_collector_plumbing_now_moves_the_identity`,
    `test_operational_plumbing_now_moves_the_identity`,
    `test_the_plumbing_left_outside_now_moves_the_identity`) ahora **exigen** que backoff,
    logging, health y sleeps muevan el digest. Se invierten en vez de borrarse para que el
    coste quede medido.
- Neutralidad que **sí** se conserva y está fijada por test: comentarios, docstrings, líneas en
  blanco y formato en los tres módulos; y en el contrato de runtime, umbrales,
  `bybit_oi_symbol` y `spot_history_symbol`.
- Trailing whitespace corregido en `.github/pull_request_template.md` (el que introdujo
  `700f7695..450cf2fb`) y en `scripts/configure_secrets.sh:107`. Barrido del árbol rastreado:
  queda **una** línea, `deploy/ai-bridge/v1.3.4-preview-max.patch:8`, y se deja
  deliberadamente — es un espacio único que en formato *unified diff* representa la línea de
  contexto en blanco del hunk. Quitarlo corrompería el parche.

### 8.1 Riesgos y limitaciones que quedan abiertos

`CONFIRMED` — declarados, no resueltos.

- **La identidad es ahora sensible a edits operativos** en los tres módulos cubiertos. Un
  cambio de backoff o de nivel de log obliga a recomputar y re-registrar identity-v1 mientras
  la ventana de sustitución siga abierta; después de la congelación spec-v4 obligaría a una
  **identidad nueva**. Es el precio explícito de ADR-012 y hay que planificarlo antes de
  congelar.
- **La cobertura por módulo no dice nada sobre el resto del árbol.** Sigue siendo enumerada
  para los otros 15 ficheros con regiones. Esta corrección no afirma que ahí no exista el
  mismo defecto; sólo cierra los tres módulos que el hallazgo señaló.
- **`app/config.py` sigue cubierto por región**, deliberadamente: su parte científica son las
  cuatro proyecciones y los umbrales de al lado los congela el contrato de runtime. Es una
  enumeración que sobrevive, y por tanto una superficie a revisar.
- **`MATERIAL_SYMBOLS` y los marcadores permanecen** como defensa adicional. No sostienen la
  propiedad de cierre, pero si alguien los borra los barridos dejan de proteger sin que el
  digest lo note.
- La ventana de sustitución de identity-v1 sigue abierta **sólo** porque no existe manifest
  spec-v4 ni resultado autoritativo. En cuanto exista uno, esta libertad desaparece.

Añadidos por el commit 3.2, todos declarados y ninguno resuelto:

- **La verificación en proceso no derrota a un atacante en proceso.** M-38 es `RESIDUAL` y lo
  seguirá siendo: quien ejecuta código antes de que el intérprete importe el guardián controla
  al guardián. Se mitiga fuera del proceso — `PYTHONNOUSERSITE=1`, árbol y venv de sólo lectura
  para el usuario del servicio, `NoNewPrivileges`, propietario del árbol distinto del ejecutor —
  y el commit 4 lo documenta en la ADR. **Que el producto se venda con este riesgo declarado y
  mitigado es defendible; que se venda con la impresión contraria, no.**
- **La caché de componentes es necesaria y envenenable.** M-34 es `RESIDUAL` por medición, no
  por comodidad: 744 ms por cómputo sin caché contra un techo de 990 ms para los tres que hace
  una evaluación autoritativa. Está acotada a la superficie vigente. Si algún día el techo o el
  tamaño de la superficie cambian, esta fila debe reevaluarse — no heredarse.
- **C.2 cubre los módulos cargados, y sólo ésos.** Es correcto por construcción —no se puede
  fingerprintear el objeto enlazado de un módulo que nadie importó— pero significa que la
  cobertura de C.2 en un proceso es la de su working set. Lo no importado sigue cubierto por el
  hash de su fuente.
- **Símbolos decorados cuyo binding no resuelve a una función plana quedan fuera de C.2.** Son
  los validadores de pydantic en `app/config.py`. No quedan desprotegidos: la lista de
  decoradores es parte del AST canónico, así que nada puede meter un símbolo en ese cubo sin
  mover el digest de código. Es un hueco acotado y nombrado, no un descuido.
- **El coste en frío del primer cómputo de identidad subió a ~1,4 s** (antes ~0,79 s). No afecta
  al camino autoritativo, que va caliente; afecta al arranque de los colectores.

### PLANNED / BLOCKED

- Revisión independiente P0=0/P1=0 sobre `f83a468a2d30854f4cad5f96d4b85d0ad50daaf6` — **bloquea todo lo demás**.
- Deuda spec-v1, cohorte legacy y pivotes.
- Merge humano de PR #27 y luego PR #28.
- Calibración pre-OOS, congelación spec-v4, recolección y evaluación autoritativa.
- Trade Tape/Footprint: posterior, PR propio.

Detalle y orden en [`ROADMAP.md`](ROADMAP.md).

### EXTERNAL_UNVERIFIED

- Estado real de producción (LXC 140). No se ha tocado ni consultado.
- Historial de GitHub Actions sobre `main` y salud del runner self-hosted.

### MISSING_EXTERNAL_EVIDENCE

- Auditoría independiente de las cohortes históricas anteriores a la procedencia de
  contrato. **No existe. No se inventa. No habrá backfill.**
- Manifest spec-v4 y resultado autoritativo: no existen todavía — por eso la ventana de
  sustitución de identity-v1 sigue abierta.

## 9. Contexto de producto que sigue vigente

`CONFIRMED` — heredado del handoff v1.3.7, verificado contra datos reales en su momento.

**Procedencia de los datos.** `.A` en Coinalyze **es Binance**, no un agregado multi-venue
(`/v1/exchanges`: `.A=Binance, .3=OKX, .4=Huobi, .6=Bybit`). Hay un test que falla si alguien
vuelve a escribir "agregado" o "todos los venues" en `app/`.

**El sesgo del diferencial spot−futuros.** `cvd_diff_usd = cvd_spot_usd − cvd_fut_usd` resta
spot de 2 venues menos futuros de Binance. La pata de futuros pesa 4.8–5.9× más porque el
perp mueve ~10× el spot. **Nunca lo leas como "acumulación spot".**

**Retención** (condiciona qué se puede calcular): `daily_session_agg` infinita (~390 sesiones
desde 2025-07-09, la única historia larga) · `ohlcv` diario 730 días · `ohlcv` 5min 400 días ·
`futures_trades_agg` 36 h · realtime 12 h · `spot_trades_realtime` 2 h · `orderbook_snapshot`
6 h · `scalp_signal_snapshot` 72 h → **la capa scalp no es backtesteable**.

**Trampas ya pisadas.** (1) El `update.sh` que se ejecuta es el de `/opt/coinalyze`, no el del
paquete: una corrección al propio `update.sh` surte efecto una versión después. (2) Editar
`.py` desde Windows los convierte a CRLF. (3) `.context-grid` es de 12 columnas: todo panel
nuevo debe declarar `grid-column`. (4) Toda función `render*` debe **reemplazar** su
contenedor, no hacer `append`. (5) El bridge se instala como copia en site-packages. (6) No
pongas texto dentro del SVG de las barras. (7) **Verifica antes de afirmar** — el comentario
`coinalyze_aggregate` llevaba versiones siendo falso.

**Límites duros.** Solo 2 venues · trades agregados a 1 min → sin footprint · libro L1/L5/L10 ·
sin opciones/gamma ni on-chain · backtest del scalp imposible · `inst_delta_usd` (whale) está
prácticamente vacía, no la uses.

## 10. Prohibiciones operativas

`DECIDED` — vinculantes para cualquier IA que retome esto.

| Prohibido | Por qué |
|---|---|
| Mergear a `main` | Regla 13. Lo aprueba una persona tras review y CI verde. |
| Desplegar o tocar producción | Regla 14. Sólo `workflow_dispatch` desde `main`, por un humano. |
| Modificar `/etc/coinalyze` o secretos productivos | Regla 10. |
| `git push --force` (ni `--force-with-lease`) | Regla 12. |
| Crear otra rama u otro PR para esta tarea | Se trabaja en `claude/pr27-r03-runtime-config-closure` / PR #28. |
| `reset`, `rebase`, reescribir historia compartida | Rompe la trazabilidad por SHA. |
| Crear manifest spec-v4 o kernel-v2 | Requiere calibración pre-OOS previa. |
| Migraciones, cambios de esquema o backfill | Regla 16; y no hay backfill de procedencia. |
| Calibrar o seleccionar parámetros | PR27 instala maquinaria, no elige valores. |
| Trade Tape/Footprint | Fuera de PR27 (ADR-006). |
| Sustituir evidencia ausente por afirmaciones | Usa `MISSING_EXTERNAL_EVIDENCE`. |
| Debilitar un test para que pase | Reproduce el defecto primero (regla 19). |
| Declarar un cierre por informe propio o CI verde | No son aprobación. Sólo lo es una revisión independiente P0=0/P1=0 (§2.1). |
| Entregar sin actualizar `HANDOFF_IA.md` en GitHub | Obligatorio en todo prompt, sin excepción (§2.1). |

## 11. Próxima acción exacta

`BLOCKED — no la ejecuta una IA`

> **Decisión requerida sobre `M-01` antes que ninguna otra cosa.** Ver §6.3. La medición
> demuestra que C.2 detecta la mutación —`M-01` y `M-31` producen la misma medición exacta y
> `M-31` es `GUARD`— y lo que mantiene la fila abierta es que `REQUIRE_FORGED_REJECTED`
> interroga al símbolo que la propia mutación reemplaza. La corrección propuesta es de una
> línea y **no se ha aplicado**, porque aplicarla es ajustar el test al resultado y eso lo
> decide la revisión, no quien implementa. La suite tiene 4 fallos, todos de esa fila.
>
> Autorizar la corrección, o rechazarla y declarar `M-01` un residual del instrumento. Las dos
> respuestas son defendibles; lo que no lo es es dejarla en rojo sin decidir.

Después de eso, y sólo después:

> **Solicitar a ChatGPT Work una revisión independiente y adversarial del commit 3.2.** Debe
> intentar el bypass con mutaciones **propias**, no con las que ya están en la suite. Vectores
> obligatorios, porque son los que fallaron antes:
>
> 0. **Nuevos de 3.2**: intentar que un módulo `app.*` cargado desde fuera de la superficie no
>    aparezca en `module_provenance`; intentar reemplazar un símbolo material sin que
>    `bound_objects` lo note (los símbolos decorados cuyo binding no resuelve a una función
>    plana son el hueco declarado, ver §8.1); y envenenar la caché por una vía distinta de
>    M-34.
>
> 1. Intentar cambiar algo ejecutable en `app/scalp_collector.py`, `app/ws_collector.py` o
>    `app/signal_runtime_contract.py` **sin** mover identity-v1. La cobertura de módulo dice
>    que es imposible; el trabajo de la revisión es demostrar lo contrario. Vectores obvios:
>    código generado en `exec`/`eval`, un `.pth`, un `sitecustomize`, monkeypatching desde
>    otro módulo, o un fichero nuevo que los colectores importen.
> 2. Buscar el mismo defecto **fuera** de los tres módulos cubiertos: cualquier ruta que
>    alcance el store, la clasificación o la entrega desde uno de los 15 ficheros que siguen
>    cubiertos por región, o desde uno que no está cubierto en absoluto.
> 3. Mutar el **punto de llamada real** de cada símbolo, localizado por AST, nunca su primera
>    aparición textual.
> 4. Intentar construir un `EffectiveMarketRouting`, un `FuturesRoutingIndex` o un
>    `SpotRoutingIndex` que alcance el store o la escritura sin pasar por
>    `require_attested_routing()`.
> 5. Verificar la neutralidad que **sí** se afirma: que comentarios, docstrings y formato en
>    los tres módulos sigan sin mover el digest, y que el contrato de runtime y los hashes
>    legacy sigan quietos.
>
> Criterio de salida: **P0=0 y P1=0**. Si refuta, entregar veredicto y prompt correctivo
> juntos (§2.1).

Hasta que eso ocurra:

- El digest `c7bf8e5b…` es **candidato**, no definitivo. No lo describas como final ni
  inmutable.
- **R05 no está cerrado.** Esta es su cuarta iteración y las tres anteriores también se
  presentaron con la suite en verde.
- No se congela identity-v1.
- No se mergea nada. `mergeable=true` en GitHub no es una aprobación.

## 12. Checklist para retomar el proyecto

Si acabas de llegar, en este orden:

1. Lee [`AI_ENGINEERING_RULES.md`](AI_ENGINEERING_RULES.md) (las 20 reglas) y, según quién
   seas, [`CLAUDE.md`](../CLAUDE.md) o [`AGENTS.md`](../AGENTS.md).
2. Lee este documento entero y [`ROADMAP.md`](ROADMAP.md) §1–2 para saber qué bloquea qué.
3. Lee [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md): las decisiones ya tomadas no
   se re-litigan sin una entrada nueva que las supersede.
4. Crea tu worktree: `coin-worktree-create claude <slug>`. **Nunca** trabajes en
   `/srv/coinanalyze/repo`. Para continuar *esta* tarea, usa la rama existente.
5. Verifica rama, HEAD y árbol limpio. Si el HEAD no coincide con lo esperado o hay cambios
   ajenos, **detente y pregunta**.
6. Levanta un PostgreSQL 17 aislado como hace el CI (ver `.github/workflows/ci.yml`) y
   exporta `TEST_DATABASE_URL`.
7. Línea base antes de tocar nada:
   ```bash
   . .venv/bin/activate
   ruff check . && python -m compileall -q app scripts tests && pytest -q -rs
   node --test tests/js/
   ```
   Debe dar **0 failed y 0 skipped**. Si no, ese es tu primer problema.
8. Ejecuta `graphify query "<pregunta>"` antes de explorar código a mano.
9. Si vas a corregir un defecto: **reprodúcelo primero** con un test rojo y guarda su salida
   exacta. Un cierre no se declara con documentación.
10. Antes de cada push: `ruff check .`, `pytest -q`, `git diff`. Informa ficheros
    modificados, tests ejecutados y resultado real.
11. **Actualiza este documento en GitHub, sin excepción**, y con él `ROADMAP.md` y
    `ARCHITECTURE_DECISIONS.md` si cambia el estado del proyecto. La continuidad es parte del
    entregable, no un extra: una entrega sin handoff commiteado y pusheado está incompleta.
12. No declares cerrado nada por tu propio informe. Entrega la evidencia y espera la revisión
    independiente (§2.1).
