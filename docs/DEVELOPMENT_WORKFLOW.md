# Flujo de desarrollo

Todo el desarrollo ocurre en el **LXC 143 `coin-cicd`** como usuario `devops`. Nunca en producción.

## Acceso desde Windows

```bash
ssh coin-cicd        # alias en ~/.ssh/config -> devops@<IP_DEV>, clave coin-cicd_ed25519
```

En VS Code: **Remote-SSH → Connect to Host → coin-cicd**, y abre la carpeta del worktree
correspondiente, p. ej. `/srv/coinanalyze/worktrees/<agente>/<tarea>`.

## Estructura

```
/srv/coinanalyze/
├── repo/                       # clon base, sigue a origin/main (NO trabajar aquí)
└── worktrees/
    ├── <agente>/<tarea>/       # rama <agente>/<tarea>
    └── claude/<tarea>/         # rama claude/<tarea>
```

## Crear / listar / eliminar worktrees

```bash
coin-worktree-create <agente> issue-42-gap-recovery  # crea rama <agente>/issue-42-gap-recovery
coin-worktree-create claude issue-43-api-refactor     # crea rama claude/issue-43-api-refactor
coin-worktree-list
coin-worktree-remove <agente> issue-42-gap-recovery [--force] [--delete-branch]
```

Cada `create` hace `git fetch origin`, parte de `origin/main`, crea la rama y el worktree, y
rechaza sobrescribir uno existente o una rama ya usada.

## Ciclo por tarea

```
coin-worktree-create <agent> <slug>
        ↓
cd /srv/coinanalyze/worktrees/<agent>/<slug>
        ↓
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock && pip install -e '.[dev]'
        ↓
<editar código con el asistente>
        ↓
ruff check .        # lint
pytest -q           # tests (498 baseline)
git diff            # revisar
        ↓
git add -A && git commit -m "..."
git push -u origin <agent>/<slug>
gh pr create --fill --base main
        ↓
CI (self-hosted runner) valida el PR
        ↓
review (el otro agente o un humano) → merge por un humano → main
```

Los agentes **no** mergean. El merge lo hace un humano tras review + CI verde (ver
branch protection en [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md)).

## Colaboración entre asistentes

- Un worktree por agente y tarea; nunca dos agentes en el mismo worktree.
- Un agente implementa; el otro puede revisar el PR (`gh pr review`).
- GitHub (PRs/reviews/checks) es el único canal de coordinación.

## Ejecutar el asistente

```bash
# el otro asistente: su propio CLI y su propio login
claude       # primera vez: login por navegador (cuenta Pro/Max/Team/Enterprise)
```

Todos deben leer `docs/AI_ENGINEERING_RULES.md` (referenciado desde `AGENTS.md` y `CLAUDE.md`).
