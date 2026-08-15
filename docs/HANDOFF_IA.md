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

Revisión de este documento: **2026-08-14**. Supersede al handoff v1.3.7, cuyo contenido de
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

## 3. Estado exacto de PR27 y PR28

### PR #27 — `codex/pr27-confirmatory-endpoint-integrity` → `main`

`CONFIRMED: abierta, sin mergear`

Remediación de integridad del endpoint confirmatorio. Es la **base** de PR #28.

### PR #28 — `claude/pr27-r03-runtime-config-closure` → `codex/pr27-confirmatory-endpoint-integrity`

`CONFIRMED: abierta, apilada, NO mergeable todavía`

<https://github.com/achavezl911/coinanalyze/pull/28>

**Base: `codex/pr27-confirmatory-endpoint-integrity`, no `main`. Do not merge.** Orden
obligatorio: primero PR #27 → `main`, después PR #28.

### SHAs de la serie

| Rework | SHA | Estado |
|---|---|---|
| Implementación inicial | `5a99ab5371eca057afc7374ed8cbf544e558113e` | landed |
| R01 | `e58f1fab2b8ebfd158608805fafc87fc559211c7` | landed (HEAD de PR #27) |
| R02 | **no existe commit identificable** | declarado, no inventado |
| R03 | `0496819a15699bae3b80fc92e803a50adf40df54` | landed |
| R04 | `ee3792ca9f26b1cc20f354e9eaf35332b8ce266e` | landed, incompleto |
| **R05 candidato parcial** | `c879bdecf5eb453b5a91853e917be79d3df9042d` | **no superó revisión: A-02 abierto** |
| **R05 candidato de cierre (código)** | `700f7695f97c1d094a2180b7a6916686429abda3` | candidato, pendiente de revisión |
| **Continuidad documental** | el commit inmediatamente posterior a `700f7695` | HEAD de PR #28 |

`700f7695` es el commit de código, tests e identidad; el siguiente es documentación y handoff.
Esta corrección **no es R06**: es el cierre del mismo R05.

## 4. Arquitectura científica vigente

`CONFIRMED`

Dos identidades independientes, ambas con registro append-only:

| | Identidad científica | Contrato de runtime |
|---|---|---|
| Responde | qué calcula el código | qué insumos crudos seleccionó |
| Digest vigente | `5a5cb09f80ce17903409daf8fc90e7d05e060a578183aed629d680f37280f05f` (**candidato**) | `c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00` (sin cambios) |
| Componentes | 32 regiones AST/SQL | 4 campos resueltos por símbolo |

Hashes legacy spec v1/v2/v3, `CONFIRMED` sin cambios: `e2f967bb…`, `2f21afe9…`, `7fd50764…`.

**El ruteo atestiguado** es la parte que ha concentrado el trabajo. Cadena completa, toda
dentro de la identidad: cuatro proyecciones → contrato registrado → atestación (que además
exige que los mapas efectivos coincidan) → `EffectiveMarketRouting` congelado → índice de
ruteo que valida cada conversión → URL/topics → conexión → handler → store → entrega
guardada → SQL. Fuera de la identidad, a propósito y fijado por test: reconexión, backoff,
logging, health de feeds y parámetros de transporte WS.

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

## 7. Qué cierra la corrección

`CONFIRMED en esta rama · pendiente de revisión independiente`

1. **Sesiones conectadas dentro de la identidad.** Cada colector construye el índice desde
   el ruteo atestiguado, deriva URL/topics, abre la conexión y despacha al handler **dentro**
   de la región. El índice nunca sale: un bucle no puede sustituirlo porque no lo tiene.
2. **Inyección única del ruteo.** `scalp_routing_producers()` / `ws_routing_producers()`,
   dentro de la identidad, reciben un ruteo y devuelven todas las tareas ligadas a él. El
   entrypoint no elige por tarea.
3. **Traspaso store → entrega dentro de la identidad**: `flush_*_cycle()`.
4. **Índice inconstruible.** `FuturesRoutingIndex`/`SpotRoutingIndex` exigen el ruteo
   atestiguado y validan cada conversión en `__post_init__`
   (`require_routed_pair_origins`). La mutación de la revisión falla cerrada.
5. **Endpoints de venue dentro de la identidad**; transporte fuera.
6. **Región de `config.py` reducida** a las cuatro proyecciones.

Identidad recomputada: `25f6c2e5…` → `5a5cb09f…`. 30 → 32 componentes.

## 8. Confirmado / pendiente / bloqueado / no verificado

### CONFIRMED

- Suite completa con PostgreSQL 17.10: **1510 passed, 0 failed, 0 skipped** (15:13). Antes de
  la corrección eran 1468; los 42 nuevos son la suite de aplicación de ruteo.
- `ruff check .` limpio · `compileall` OK · `node --test tests/js/` 49 pass 0 skip ·
  `git diff --check` limpio.
- Runtime contract digest sin cambios; hashes legacy sin cambios.
- Los dos hallazgos de la revisión reproducidos y cerrados con tests que pasan de rojo a
  verde sin debilitar ninguno existente.

### PLANNED / BLOCKED

- Revisión independiente P0=0/P1=0 sobre `700f7695` — **bloquea todo lo demás**.
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

## 11. Próxima acción exacta

`BLOCKED — no la ejecuta una IA`

> **Solicitar una revisión independiente y adversarial de `700f7695f97c1d094a2180b7a6916686429abda3`** que intente reproducir
> el bypass de A-02 con mutaciones propias —no con las que ya están en la suite— y verificar
> que la región de `config.py` no arrastra valores no materiales. Criterio de salida:
> **P0=0 y P1=0**.

Hasta que eso ocurra:

- El digest `5a5cb09f…` es **candidato**, no definitivo. No lo describas como final ni
  inmutable.
- No se congela identity-v1.
- No se mergea nada.

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
11. Actualiza este documento, `ROADMAP.md` y `ARCHITECTURE_DECISIONS.md` si cambia el estado
    del proyecto. La continuidad es parte del entregable, no un extra.
