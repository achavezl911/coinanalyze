# Índice de documentación — coinanalyze

Punto de entrada único a la documentación. Si retomas el proyecto (persona o IA),
**empieza por [`HANDOFF_IA.md`](HANDOFF_IA.md)**: dice en qué estado exacto está todo y cuál
es la siguiente acción.

## Empezar aquí

| Documento | Para qué |
|---|---|
| [`HANDOFF_IA.md`](HANDOFF_IA.md) | Estado exacto, SHAs, qué está confirmado/pendiente/bloqueado, próxima acción, roles, protocolo de validación adversarial (§2.1) y prohibiciones. **Léelo primero.** Actualizarlo es obligatorio en todo entregable, sin excepción. |
| [`AI_ENGINEERING_RULES.md`](AI_ENGINEERING_RULES.md) | Documento maestro compartido por Codex y Claude Code. Las 20 reglas. Gana sobre cualquier otra instrucción. |
| [`SCIENTIFIC_ARCHITECTURE.md`](SCIENTIFIC_ARCHITECTURE.md) | Cómo encaja el sistema científico, con diagramas: exchanges, colectores, ruteo atestiguado, crudo, observaciones, replay, outcomes, visibilidad, contrato, identidad, walk-forward, manifest, resultado autoritativo. |
| [`ROADMAP.md`](ROADMAP.md) | Las etapas hasta el resultado autoritativo, en orden, con lo que bloquea cada una. |
| [`ARCHITECTURE_DECISIONS.md`](ARCHITECTURE_DECISIONS.md) | Registro append-only de decisiones con fecha, estado, consecuencias y SHA. |

## Trabajo en curso (PR27 / PR28)

| Documento | Para qué |
|---|---|
| [`PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md`](PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md) | Endpoint confirmatorio corregido, contrato de runtime, identidad científica, cierre R05 y su corrección. |
| [`PR26_CONFIRMATORY_WALK_FORWARD.md`](PR26_CONFIRMATORY_WALK_FORWARD.md) | Walk-forward confirmatorio spec v3. |
| [`PR25_RESEARCH_KNOWLEDGE_TIME.md`](PR25_RESEARCH_KNOWLEDGE_TIME.md) | Knowledge-time de investigación y visibilidad certificada. |
| [`PR23_TEMPORAL_INTEGRITY.md`](PR23_TEMPORAL_INTEGRITY.md) | Integridad temporal y particionado. |

## Capa científica (referencia por tema)

| Documento | Tema |
|---|---|
| [`SIGNAL_OBSERVATION_LEDGER.md`](SIGNAL_OBSERVATION_LEDGER.md) | Ledger append-only de observaciones. |
| [`SIGNAL_OUTCOMES.md`](SIGNAL_OUTCOMES.md) | Materialización de outcomes y su ventana. |
| [`SIGNAL_REPLAY.md`](SIGNAL_REPLAY.md) | Replay determinista de contexto y evidencia. |
| [`SIGNAL_WALK_FORWARD.md`](SIGNAL_WALK_FORWARD.md) | Walk-forward, folds y manifest. |
| [`SIGNAL_EXECUTION_COSTS.md`](SIGNAL_EXECUTION_COSTS.md) | Snapshot de ejecución y curva de costes. |
| [`SIGNAL_BACKTESTING.md`](SIGNAL_BACKTESTING.md) · [`SIGNAL_ATTRIBUTION.md`](SIGNAL_ATTRIBUTION.md) · [`SIGNAL_REGIMES.md`](SIGNAL_REGIMES.md) | Backtesting, atribución y regímenes. |
| [`TEMPORAL_PARTITIONING.md`](TEMPORAL_PARTITIONING.md) | Particionado temporal. |

## Operación

| Documento | Tema |
|---|---|
| [`DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md) | Worktrees, ramas, PRs. |
| [`GITHUB_ACTIONS.md`](GITHUB_ACTIONS.md) | CI y despliegue por `workflow_dispatch`. |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) · [`ROLLBACK.md`](ROLLBACK.md) | Despliegue y vuelta atrás. **Sólo humanos.** |
| [`OPERATIONS.md`](OPERATIONS.md) · [`PROMETHEUS.md`](PROMETHEUS.md) | Operación diaria y métricas. |
| [`HORIZONTAL_COLLECTORS.md`](HORIZONTAL_COLLECTORS.md) | Sharding de colectores. |
| [`GRAPHIFY.md`](GRAPHIFY.md) | Grafo de conocimiento del repositorio. |

## Producto y uso

[`ARCHITECTURE.md`](ARCHITECTURE.md) · [`USO_DASHBOARD.md`](USO_DASHBOARD.md) ·
[`MANUAL_INTERPRETACION.md`](MANUAL_INTERPRETACION.md) ·
[`AI_DEVELOPMENT_BRIEF.md`](AI_DEVELOPMENT_BRIEF.md)

## Histórico

`CHANGES_v*.md`, `VALIDATION*.md`, `PATCHES_APPLIED*.md` y `AUDIT_v1.3.8.md` son registros de
versiones anteriores. No describen el estado actual; consúltalos sólo para arqueología.

---

## Qué constituye una aprobación

Ni un informe de Claude ni un CI en verde. Sólo una revisión independiente y adversarial de
ChatGPT Work con **P0=0 y P1=0**, que cuestione el código en el árbol y ejecute sus propias
mutaciones. Si Work refuta, entrega veredicto y prompt correctivo juntos. Detalle en
[`HANDOFF_IA.md`](HANDOFF_IA.md) §2.1 y [`AI_ENGINEERING_RULES.md`](AI_ENGINEERING_RULES.md).

**`mergeable=true` en GitHub tampoco es una aprobación**: sólo dice que no hay conflicto de
texto. PR #28 sigue **DO NOT MERGE**.

---

**Convención de estados.** En `HANDOFF_IA.md`, `ROADMAP.md` y `ARCHITECTURE_DECISIONS.md`
toda afirmación lleva estado explícito:

| Estado | Significado |
|---|---|
| `CONFIRMED` | Verificado en este repositorio con evidencia reproducible (test, comando, SHA). |
| `DECIDED` | Decisión tomada y registrada; no es un hecho medido. |
| `PLANNED` | Trabajo acordado pero no empezado. |
| `BLOCKED` | No puede avanzar hasta que se resuelva una dependencia declarada. |
| `EXTERNAL_UNVERIFIED` | Depende de un sistema fuera de este repositorio y no se ha verificado desde aquí. |
| `MISSING_EXTERNAL_EVIDENCE` | Se esperaría una auditoría o artefacto externo y **no existe**. No se inventa. |
