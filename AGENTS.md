# AGENTS.md — instrucciones para Codex CLI

**Antes de hacer cualquier cosa, lee y cumple [`docs/AI_ENGINEERING_RULES.md`](docs/AI_ENGINEERING_RULES.md).**
Ese es el documento maestro compartido entre Codex y Claude Code; estas notas no lo sustituyen.

**Después, lee [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md)**: estado exacto del proyecto, SHAs
relevantes, qué está bloqueado y cuál es la próxima acción.

## Documentación canónica

| Documento | Cuándo |
|---|---|
| [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md) | Siempre, al empezar. |
| [`docs/SCIENTIFIC_ARCHITECTURE.md`](docs/SCIENTIFIC_ARCHITECTURE.md) | Antes de tocar ruteo, identidad, contrato, observaciones o walk-forward. |
| [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) | Antes de proponer un cambio de diseño. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Para saber qué bloquea qué. |
| [`docs/README.md`](docs/README.md) | Índice del resto. |

**Actualizar [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md) en GitHub es obligatorio en todo
entregable, sin excepción**, commiteado y pusheado en tu rama. Si además tu cambio altera el
estado del proyecto, el roadmap y el ADR entran también en el entregable. La continuidad no es
un extra: un entregable sin handoff actualizado está incompleto.

El handoff debe dejar comprensibles, sin contexto de ningún chat: propósito, alcance,
limitaciones, arquitectura, estado y siguiente paso.

## Dónde trabajas

- Tu área de trabajo es un **worktree propio** bajo `/srv/coinanalyze/worktrees/codex/<tarea>`.
- Crea la tarea con: `coin-worktree-create codex <slug-de-la-tarea>` (parte de `origin/main`,
  crea la rama `codex/<slug>`). Lista con `coin-worktree-list`, elimina con
  `coin-worktree-remove codex <slug>`.
- **Nunca** trabajes en `/srv/coinanalyze/repo` (es el clon base de `main`, solo lectura para ti).

## Qué puedes hacer

Leer y modificar código, ejecutar `pytest` y `ruff check .`, usar Git en tu rama, hacer
commits, `git push` de **tu** rama, consultar GitHub con `gh` y crear Pull Requests (`gh pr create`).

## Qué NO puedes hacer

- `git push --force`, modificar `main`, mergear a `main`, borrar ramas protegidas.
- Modificar producción por SSH ni tocar `/etc/coinalyze` o cualquier secreto productivo.
- Commitear secretos.

## Antes de cada push (obligatorio)

```bash
ruff check .
pytest -q
git diff            # revisa lo que vas a commitear
```

Para la capa científica, `pytest -q` debe correr contra **PostgreSQL 17** con
`TEST_DATABASE_URL` exportada (clúster aislado como en `.github/workflows/ci.yml`) y terminar
con **0 failed y 0 skipped**.

Al terminar, informa: archivos modificados, tests ejecutados y su resultado. El merge a `main`
lo hace un humano tras la review y con CI en verde. Tú **no** mergeas.

## Cómo se cierra un hallazgo

Reproduce el defecto con un test rojo y guarda su salida exacta; corrige la arquitectura;
demuestra que la mutación mueve la identidad científica o queda estructuralmente impedida
antes de escribir; ancla la mutación por AST en el **punto de llamada real**, nunca en la
primera aparición textual; no debilites tests existentes. Una afirmación documental no cierra
nada.

## Qué constituye una aprobación

**ChatGPT Work siempre cuestiona y valida de forma independiente el código de Claude**, y lo
mismo aplica a tus PRs. Un informe propio no es una aprobación; **un CI en verde tampoco**.
Sólo lo es una revisión independiente y adversarial con **P0=0 y P1=0**. Si Work refuta,
entrega veredicto y prompt correctivo juntos. `mergeable=true` en GitHub no significa
aprobado. Detalle en [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md) §2.1.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
