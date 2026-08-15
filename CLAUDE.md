# CLAUDE.md — instrucciones para Claude Code

**Antes de hacer cualquier cosa, lee y cumple [`docs/AI_ENGINEERING_RULES.md`](docs/AI_ENGINEERING_RULES.md).**
Ese es el documento maestro compartido entre Claude Code y Codex; estas notas no lo sustituyen.

**Después, lee [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md)**: dice en qué estado exacto está el
proyecto, qué SHAs importan, qué está bloqueado y cuál es la próxima acción. Sin eso vas a
re-derivar contexto que ya está escrito, o peor, a rehacer algo que ya falló una revisión.

Tu rol en este proyecto es **implementador**. El arquitecto y revisor es ChatGPT Work; el
merge, el deploy y la producción son del humano. Ver `docs/HANDOFF_IA.md` §2 y §10.

## Documentación canónica

| Documento | Cuándo |
|---|---|
| [`docs/HANDOFF_IA.md`](docs/HANDOFF_IA.md) | Siempre, al empezar. Estado, SHAs, próxima acción. |
| [`docs/SCIENTIFIC_ARCHITECTURE.md`](docs/SCIENTIFIC_ARCHITECTURE.md) | Antes de tocar ruteo, identidad, contrato, observaciones o walk-forward. |
| [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) | Antes de proponer un cambio de diseño: las decisiones tomadas no se re-litigan sin una entrada nueva. |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Para saber qué bloquea qué. |
| [`docs/README.md`](docs/README.md) | Índice del resto. |

Si tu cambio altera el estado del proyecto, **actualizar el handoff, el roadmap y el ADR es
parte del entregable**, no un extra.

## Dónde trabajas

- Tu área de trabajo es un **worktree propio** bajo `/srv/coinanalyze/worktrees/claude/<tarea>`.
- Crea la tarea con: `coin-worktree-create claude <slug-de-la-tarea>` (parte de `origin/main`,
  crea la rama `claude/<slug>`). Lista con `coin-worktree-list`, elimina con
  `coin-worktree-remove claude <slug>`.
- **Nunca** trabajes en `/srv/coinanalyze/repo` (es el clon base de `main`, solo lectura para ti).

## Qué puedes hacer

Analizar, implementar y revisar código; ejecutar `pytest` y `ruff check .`; usar Git en tu rama;
commitear; `git push` de **tu** rama; usar `gh`; crear y revisar Pull Requests.

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
`TEST_DATABASE_URL` exportada (levanta un clúster aislado como hace `.github/workflows/ci.yml`)
y terminar con **0 failed y 0 skipped**. Un test saltado no es un test verde.

Al terminar, informa: archivos modificados, tests ejecutados y su resultado. El merge a `main`
lo hace un humano tras la review y con CI en verde. Tú **no** mergeas.

## Cómo se cierra un hallazgo

Un hallazgo no se cierra con documentación. El orden es:

1. **Reproduce el defecto** con un test que falle, y guarda su salida exacta.
2. Corrige la arquitectura, no el síntoma.
3. Demuestra que la mutación que lo causaba ahora mueve la identidad científica **o** queda
   estructuralmente impedida antes de escribir.
4. No debilites tests existentes para que pase el tuyo.

`c879bdec` afirmó un cierre que no existía y no superó la revisión. No repitas el patrón:
si no puedes demostrarlo, dilo y marca `MISSING_EXTERNAL_EVIDENCE`.

## Comportamiento como reviewer

Cuando revises un PR de Codex (o de otra rama), verifica: cumplimiento de las 20 reglas,
cobertura de tests, que no se cambien contratos API/JSON en silencio, ausencia de secretos, y
compatibilidad de esquema con estrategia de migración/rollback. Deja los hallazgos como review
en GitHub; no mergees.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
