# Registro de decisiones de arquitectura

**Append-only.** Una entrada nunca se edita ni se borra: si una decisión cambia, se añade
otra que la supersede y se marca la anterior como `SUPERSEDED por ADR-nnn`.

Estados: `CONFIRMED` · `DECIDED` · `PLANNED` · `BLOCKED` · `EXTERNAL_UNVERIFIED` ·
`MISSING_EXTERNAL_EVIDENCE`.

Formato: fecha · estado · decisión · consecuencias · SHA.

---

## ADR-001 — Fuente única e inmutable de ruteo de mercado

- **Fecha**: 2026-08-13
- **Estado**: `DECIDED` · implementación `CONFIRMED`
- **SHA**: `0496819a15699bae3b80fc92e803a50adf40df54` (R03),
  `ee3792ca9f26b1cc20f354e9eaf35332b8ce266e` (R04),
  `c879bdecf5eb453b5a91853e917be79d3df9042d` (R05 parcial)

**Decisión.** El ruteo de mercado result-material (`symbol`, `base_asset`, `futures_pair`,
`spot_pair`) se congela como *valores resueltos* en un contrato de runtime versionado, con
registro append-only, y se proyecta en un único objeto inmutable —`EffectiveMarketRouting`—
construido una sola vez por proceso desde el contrato **ya validado**. Los cuatro dicts de
`app/config.py` se conservan por compatibilidad operativa pero dejan de ser autoritativos.

**Consecuencias.**
- Un servicio cuyo ruteo no es el registrado no produce nada: correctitud por encima de
  disponibilidad. Una ventana ausente es visible como `data_gap`; la contaminación no lo es.
- El digest del contrato es independiente de cómo se escriba `SYMBOLS` (csv o json, orden,
  repeticiones): se ordena y de-duplica antes de hashear.
- Cambiar el ruteo legítimamente obliga a registrar una versión nueva de contrato.
- Digest vigente: `c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00`.

---

## ADR-002 — A-01 y A-02 son un solo problema y se cierran como una unidad

- **Fecha**: 2026-08-13
- **Estado**: `DECIDED`
- **SHA**: `c879bdecf5eb453b5a91853e917be79d3df9042d` (cierre parcial),
  `700f7695f97c1d094a2180b7a6916686429abda3` (cierre candidato)

**Decisión.** A-01 (la atestación validaba el catálogo mientras los productores aplicaban
otros objetos) y A-02 (la construcción y aplicación del ruteo estaban fuera de la identidad
científica) son la misma carencia: **el ruteo efectivo no era un objeto científico**. Se
cierran juntos y no se dan por cerrados por separado.

**Consecuencias.**
- Toda la cadena —proyecciones, endpoints, índice, URL/topics, conexión, despacho,
  conversión, inyección desde `main()`/`run()` y traspaso store → entrega— vive dentro de
  regiones de identidad.
- El índice de ruteo sólo se construye desde un ruteo atestiguado y valida cada conversión
  par-externo → clave-interna: un índice forjado falla cerrado antes de suscribirse.
- La validación de claves internas se declara **insuficiente por sí sola**: una clave puede
  ser legítima y su procedencia externa no serlo.
- Reconexión, backoff, logging, health y transporte quedan fuera y hay tests de mutación que
  fijan ambas direcciones.

---

## ADR-003 — Política de identity-v1 y ventana de sustitución

- **Fecha**: 2026-08-14
- **Estado**: `DECIDED` · la política sigue vigente; el **valor** del digest queda
  `SUPERSEDED por ADR-011`
- **SHA**: `700f7695f97c1d094a2180b7a6916686429abda3`

**Decisión.** El digest de identity-v1 puede recomputarse **sólo mientras** no exista ningún
manifest spec-v4 ni resultado autoritativo en el repositorio. Historial dentro de PR27:
`f696a268…` (R03) → `9749e643…` (R04) → `25f6c2e5…` (`c879bdec`) →
`5a5cb09f80ce17903409daf8fc90e7d05e060a578183aed629d680f37280f05f` (corrección de cierre).

**Consecuencias.**
- El valor actual es **candidato**, no definitivo. No se describe como final ni inmutable
  hasta que supere revisión independiente.
- Tras esa aprobación y **antes** del primer manifest spec-v4, identity-v1 queda congelada.
  Cualquier cambio posterior del código cubierto exige identity-v2 y un experimento
  prospectivo nuevo; el digest v1 nunca se reemplaza.
- El registro `identity_version -> digest` es append-only por política y por test.
- Los hashes legacy spec v1/v2/v3 (`e2f967bb…`, `2f21afe9…`, `7fd50764…`) no se tocan.

---

## ADR-004 — La región de identidad protege lógica, no valores operativos

- **Fecha**: 2026-08-14
- **Estado**: `DECIDED`
- **SHA**: `700f7695f97c1d094a2180b7a6916686429abda3`

**Decisión.** `PR27_SCIENTIFIC_MARKET_ROUTING_SOURCE_V1` cubre exclusivamente las cuatro
proyecciones de ruteo. El catálogo, su loader, `whale_threshold_usd`,
`large_trade_threshold_usd`, `bybit_oi_symbol` y `spot_history_symbol` quedan fuera.

**Motivo.** Una revisión independiente demostró que con la región ancha, cambiar
`whale_threshold_usd` de `5_000_000` a `5_000_001` movía el digest de `25f6c2e5…` a
`06da5f1f…`, contradiciendo la exclusión de esos umbrales documentada como no material.

**Consecuencias.**
- Los *valores resueltos* del ruteo siguen protegidos por el contrato de runtime, que es
  donde corresponde protegerlos.
- Un ajuste operativo de umbrales ya no invalida la identidad científica.
- Regla general: si una edición operativa mueve la identidad, o está mal clasificada o la
  región es demasiado ancha.

---

## ADR-005 — Evidencia legacy sin procedencia queda excluida, sin backfill

- **Fecha**: 2026-08-13
- **Estado**: `DECIDED`
- **SHA**: `0496819a15699bae3b80fc92e803a50adf40df54`

**Decisión.** Las observaciones anteriores a la procedencia de contrato (columnas
`runtime_contract_*` en NULL) **no son admisibles** como evidencia confirmatoria spec-v4.
No se realizará ningún backfill de procedencia.

**Consecuencias.**
- Se conservan como información histórica o diagnóstica, identificadas por sus columnas en
  NULL y por quedar fuera de cualquier población OOS spec-v4.
- El muestreo spec-v4 exige procedencia presente e igual a la del manifest congelado.
- **`MISSING_EXTERNAL_EVIDENCE`**: no existe en este repositorio una auditoría independiente
  de esas cohortes históricas. No se inventa.

---

## ADR-006 — Trade Tape / Footprint es una iniciativa posterior y separada

- **Fecha**: 2026-08-14
- **Estado**: `DECIDED` · trabajo `PLANNED`
- **SHA**: commit documental de la corrección de cierre R05 (HEAD de PR #28)

**Decisión.** La persistencia tick a tick (Trade Tape / Footprint) queda **fuera de PR27** y
fuera de la evidencia confirmatoria spec-v4. Se aborda después del resultado autoritativo,
en un PR propio.

**Consecuencias.**
- Hoy los trades se agregan a 1 minuto y 5 segundos, y el libro llega a L1/L5/L10: no hay
  footprint, volumen-a-precio real ni clusters de órdenes. Es un límite declarado, no un
  defecto pendiente.
- Necesitará su propio esquema, su propia retención y su propia identidad científica.
- Ver [`ROADMAP.md`](ROADMAP.md) §11 y [`SCIENTIFIC_ARCHITECTURE.md`](SCIENTIFIC_ARCHITECTURE.md) §8.

---

## ADR-007 — Ninguna IA mergea, despliega ni toca producción

- **Fecha**: 2026-08-13
- **Estado**: `DECIDED` · vigente

**Decisión.** Codex y Claude Code pueden analizar, implementar, testear, commitear, hacer
push de **su propia rama** y crear/revisar PRs. No pueden mergear a `main`, desplegar, tocar
producción por SSH, modificar `/etc/coinalyze`, hacer `push --force` ni reescribir historia
compartida.

**Consecuencias.**
- El merge lo aprueba una persona tras la review y con CI en verde.
- El despliegue se hace **exclusivamente** desde `main` por `workflow_dispatch` → artefacto
  por SHA → wrapper root.
- Fuente: [`AI_ENGINEERING_RULES.md`](AI_ENGINEERING_RULES.md), reglas 3, 12, 13, 14.

---

## ADR-008 — `c879bdec` es una implementación R05 parcial que no superó revisión

- **Fecha**: 2026-08-14
- **Estado**: `CONFIRMED`
- **SHA**: `c879bdecf5eb453b5a91853e917be79d3df9042d`

**Decisión.** Se registra explícitamente que `c879bdec` cerró A-01 pero **no** A-02, y que
su documentación afirmaba incorrectamente que un bypass de las regiones no podía alcanzar la
ruta de escritura. Esa afirmación se ha eliminado.

**Evidencia reproducida antes de corregir.**
- Sustituir `routing.futures_index(ACTIVE_SYMBOLS)` por
  `FuturesRoutingIndex(pairs=("ETHUSDT",), symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"})`
  fuera de las regiones dejaba el digest en `25f6c2e5…`. Ídem con `SpotRoutingIndex` en spot.
- `whale_threshold_usd 5_000_000 → 5_000_001` movía el digest a `06da5f1f…`.
- `tests/test_pr27_r05_routing_application_closure.py` sobre `c879bdec`: **31 fallos,
  11 pasos**.

**Consecuencias.**
- No se llama R06 a la corrección: es el cierre del mismo R05.
- Un cierre no se declara por autoafirmación documental; hace falta reproducir el defecto y
  después demostrar que la mutación mueve la identidad o queda estructuralmente impedida.

---

## ADR-009 — El commit de código de la corrección es el SHA de cierre candidato

- **Fecha**: 2026-08-14
- **Estado**: `SUPERSEDED por ADR-011`
- **SHA**: `700f7695f97c1d094a2180b7a6916686429abda3` (código) y el commit documental inmediatamente posterior

**Decisión.** `700f7695f97c1d094a2180b7a6916686429abda3` es el **candidato de cierre R05**. El commit
documental posterior registra ese SHA exacto y es el HEAD de PR #28.

**Consecuencias.**
- `c879bdec`: candidato R05 parcial, rechazado en revisión.
- `700f7695`: candidato de cierre R05 (código, tests, identidad recomputada).
- El commit siguiente: continuidad documental y handoff; HEAD de PR #28.
- El candidato sólo se promueve a cierre efectivo con una revisión independiente P0=0/P1=0
  ([`ROADMAP.md`](ROADMAP.md) §2).

**Superseded.** Una segunda revisión independiente refutó `700f7695` y su commit documental
`450cf2fb`. Ver ADR-010 y ADR-011.

---

## ADR-010 — Una mutación vale por su punto de llamada, no por su primera aparición textual

- **Fecha**: 2026-08-14
- **Estado**: `CONFIRMED`
- **SHA**: `700f7695f97c1d094a2180b7a6916686429abda3`, `450cf2fb5633779755f3d7db4069fc86a800eb8b`

**Decisión.** Un mutation test que reescribe la **primera aparición textual** de una expresión
no prueba nada sobre el código que de verdad se ejecuta. Toda mutación de identidad debe
localizar sus objetivos por **AST**, sobre los sitios reales de lectura del símbolo.

**Motivo.** El helper `_mutate` de `test_pr27_r05_routing_application_closure.py` usa
`source.replace(old, new, 1)`. Tras la corrección de `700f7695`, la primera aparición de cada
expresión de ruteo quedó siempre *dentro* de una región —`routing.futures_index(ACTIVE_SYMBOLS)`
en `scalp_futures_index()`, `binance_loop(routing=routing)` en `scalp_routing_producers()`— de
modo que el digest se movía y la suite pasaba, mientras los puntos de llamada reales seguían
desprotegidos. Una segunda revisión independiente lo demostró con tres hallazgos P1:

- Sustituir la invocación real de `scalp_routing_producers()` en `main()` y de
  `ws_routing_producers()` en `run()` por wiring directo —ruteo falso para el productor,
  correcto para el flusher— dejaba el digest en `5a5cb09f…`.
- `binance_futures_session → binance_market_session` dentro de `binance_loop()`, y
  `binance_spot_session → bybit_spot_session` dentro de `binance_consumer()`, dejaban el
  digest en `5a5cb09f…`.
- Un `EffectiveMarketRouting` construido a mano, autoconsistente y portando el digest
  registrado como texto, producía índices ETHUSDT→BTC que la entrega aceptaba.

**Consecuencias.**
- `700f7695` y `450cf2fb` quedan registrados como **candidatos refutados**, igual que
  `c879bdec`.
- Las mutaciones nuevas viven en `tests/test_pr27_r05_routing_wiring_closure.py` y anclan por
  AST. El fichero anterior se conserva, con su limitación documentada en su docstring.
- Un cierre no se declara con un informe propio ni con CI en verde
  ([`HANDOFF_IA.md`](HANDOFF_IA.md) §2.1).

---

## ADR-011 — La procedencia del ruteo se prueba re-derivando el registro, no comparando el objeto consigo mismo

- **Fecha**: 2026-08-14
- **Estado**: `DECIDED` · pendiente de revisión independiente (`BLOCKED` para promoción)
- **SHA**: `e84ebe8140c8393ea2ef3447d8c165d32b594917` (código) y el commit documental inmediatamente posterior

**Decisión.** `FuturesRoutingIndex` y `SpotRoutingIndex` sólo aceptan un
`EffectiveMarketRouting` **reatestiguado contra el contrato registrado**:
`require_attested_routing()` recomputa el contrato desde el catálogo, los settings y los mapas
efectivos vivos y exige que reproduzca exactamente las filas del ruteo en uso. La
autoconsistencia del objeto y una cadena de digest **no** son evidencia de procedencia.

Complementariamente, se cierra la vía estructural: los bucles de reconexión y de flush reciben
un `connect`/`cycle` ya ligado dentro de la identidad; `main()`/`run()` no sostienen ningún
ruteo y sólo pueden llamar a dos funciones exportadas por la región, que atestiguan, cablean y
**crean las tareas materiales** dentro de la identidad. Un barrido AST endurecido exige que
ningún símbolo material se lea fuera de una región en ninguno de los dos colectores.

**Consecuencias.**
- Un ruteo forjado, o uno atestiguado que después haya divergido, falla cerrado **antes** de
  suscribirse, antes del store y antes de escribir.
- Las sustituciones que la revisión ejecutó ya no tienen forma expresable fuera de la
  identidad: el código externo no nombra venue, sesión, store, entrega ni ruteo.
- Se mantiene la neutralidad en la otra dirección, fijada por test: umbrales,
  `bybit_oi_symbol`, `spot_history_symbol`, backoff, logging, health, sleeps y la invocación
  opaca `connect`/`cycle` no mueven la identidad.
- Identity-v1 recomputada: `5a5cb09f…` → `c939add3…`, 32 componentes. Contrato de runtime y
  hashes legacy spec v1/v2/v3 **sin cambios**.
- `e84ebe81` es un **candidato**. Sólo se promueve a cierre efectivo con una revisión
  independiente P0=0/P1=0 ([`ROADMAP.md`](ROADMAP.md) §2).

---

## ADR-012 — La identidad científica cubre módulos Python completos, no regiones enumeradas

- **Fecha**: 2026-08-15
- **Estado**: `DECIDED` · pendiente de revisión independiente (`BLOCKED` para promoción)
- **SHA**: `f83a468a2d30854f4cad5f96d4b85d0ad50daaf6` (código, pruebas e identidad) y el commit documental inmediatamente posterior
- **Supersede parcialmente**: ADR-008 y ADR-011 en cuanto al *método* de cobertura de
  `app/scalp_collector.py`, `app/ws_collector.py` y `app/signal_runtime_contract.py`. Las
  decisiones de procedencia y atestación de ADR-011 siguen vigentes sin cambios.

**Decisión.** La identidad científica incorpora un tipo de componente nuevo,
`python_module`, que canonicaliza el **AST completo de un fichero** sin marcadores
`BEGIN/END` y sin lista de símbolos. Se aplica a los tres módulos que deciden qué observan
los colectores crudos:

- `app/scalp_collector.py`
- `app/ws_collector.py`
- `app/signal_runtime_contract.py`

Los **siete** componentes parciales que se solapaban con esos ficheros —el de mecánica del
contrato y tres regiones en cada colector— quedan **sustituidos** por los tres componentes de
módulo. La identidad pasa de **32 a 28 componentes**.

**Motivo.** Una región más una lista de símbolos sólo puede sostener la propiedad «lo
enumerado no cambió», y una enumeración es exactamente lo que rodean tanto un ataque como un
error honesto. Tres cierres consecutivos —`c879bdec`, `700f7695`/`450cf2fb` y
`e84ebe81`/`9b2e082c`— fueron refutados por ese mismo motivo. Sobre `9b2e082c` se
reprodujeron cinco mutaciones que **conservaban el digest** `c939add3…`:

1. Escritura directa en `TRADE_STORE` desde código fuera de toda región
   (`TRADE_STORE` se define en `app/scalp_collector.py:442`; `monitor()` está fuera).
2. Un helper nuevo que escribe en el store y se lanza como tarea desde `main()`
   (`app/scalp_collector.py:1817`, íntegramente fuera de la identidad).
3. Invertir la clasificación buy/sell en `TradeBucket.add` (`app/scalp_collector.py:125`).
4. Ampliar el bucket realtime de 5 a 10 segundos (`app/scalp_collector.py:149`).
5. Sustituir `from functools import partial` (`app/scalp_collector.py:12`) por una
   implementación que descarta silenciosamente el último argumento ligado —que es el
   `routing` atestiguado en cada binding de productor.

Ninguna se corrige añadiendo nombres a `MATERIAL_SYMBOLS`: dos son código nuevo, dos son
aritmética dentro de código existente y una sustituye un builtin del lenguaje.

**Consecuencias.**

- La propiedad de cierre pasa de **curada** a **estructural**: cualquier cambio ejecutable en
  esos tres módulos mueve identity-v1, sin superficie que enumerar y sin nada que olvidar.
- **Coste aceptado y provisional**: backoff, logging, health de feeds, sleeps y parámetros de
  transporte WS en los dos colectores **dejan de ser neutrales**. Los tests que fijaban esa
  neutralidad se **invierten** en vez de borrarse —`test_operational_collector_plumbing_now_moves_the_identity`,
  `test_operational_plumbing_now_moves_the_identity`,
  `test_the_plumbing_left_outside_now_moves_the_identity`— para que el precio quede medido y
  no supuesto. Recuperar esa neutralidad exigiría reintroducir una enumeración, que es lo
  refutado tres veces; si alguna corrección futura la recupera, deberá declarar qué
  enumeración compra.
- Comentarios, docstrings, líneas en blanco, ancho de indentación y posiciones de origen
  **siguen siendo neutrales**: la canonicalización es la misma AST que usan las regiones.
- `MATERIAL_SYMBOLS` y los barridos estructurales **se conservan como defensa adicional**, no
  como base de la propiedad. Los marcadores `BEGIN/END` permanecen en el código como
  comentarios inertes para que esos barridos sigan funcionando; ya no deciden qué se hashea.
  Los helpers de spans se re-anclaron a los marcadores del **fichero** en lugar de al registro
  de componentes, de modo que ya no se pueden desactivar editando la lista de componentes.
- `require_attested_routing()` y toda la cadena de procedencia de ADR-011 **se mantienen sin
  cambios**.
- Identity-v1 recomputada: `c939add3…` → `c7bf8e5b4f5280ff767e4e07e573b4c9a51e18011ebcaf8bc4b26a04c4b49c04`,
  **28** componentes. Contrato de runtime (`c9cbe967…`) y hashes legacy spec v1/v2/v3
  (`e2f967bb…`, `2f21afe9…`, `7fd50764…`) **sin cambios**.
- La ventana de sustitución de identity-v1 sigue abierta: no existe manifest spec-v4 ni
  resultado autoritativo que hubiera congelado un valor anterior, así que recomputar no
  invalida evidencia.
- Este commit es un **candidato**. Sólo se promueve a cierre efectivo con una revisión
  independiente P0=0/P1=0. No se declara R05 cerrado.
