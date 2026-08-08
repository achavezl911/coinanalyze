# CLAUDE.md — instrucciones para Claude Code

**Antes de hacer cualquier cosa, lee y cumple [`docs/AI_ENGINEERING_RULES.md`](docs/AI_ENGINEERING_RULES.md).**
Ese es el documento maestro compartido entre Claude Code y Codex; estas notas no lo sustituyen.

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

Al terminar, informa: archivos modificados, tests ejecutados y su resultado. El merge a `main`
lo hace un humano tras la review y con CI en verde. Tú **no** mergeas.

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
