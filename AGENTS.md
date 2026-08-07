# AGENTS.md — instrucciones para Codex CLI

**Antes de hacer cualquier cosa, lee y cumple [`docs/AI_ENGINEERING_RULES.md`](docs/AI_ENGINEERING_RULES.md).**
Ese es el documento maestro compartido entre Codex y Claude Code; estas notas no lo sustituyen.

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

Al terminar, informa: archivos modificados, tests ejecutados y su resultado. El merge a `main`
lo hace un humano tras la review y con CI en verde. Tú **no** mergeas.
