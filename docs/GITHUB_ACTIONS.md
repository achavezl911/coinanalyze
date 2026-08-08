# GitHub Actions y runner self-hosted

## Workflows

| Workflow | Trigger | Runner | Qué hace |
|---|---|---|---|
| `ci.yml` (CI) | `pull_request`, `push` a `main` | self-hosted | venv + `ruff check .` + `compileall app` + `pytest -q` |
| `deploy-production.yml` (Deploy production) | `workflow_dispatch` (deploy/rollback) | self-hosted | build+sha256+scp+wrapper (ver [DEPLOYMENT.md](DEPLOYMENT.md)) |

CI usa `python3` del sistema (3.13) creando un venv; instala `requirements.lock` + `.[dev]`.
Falla ante tests rotos, lint sucio, dependencias que no instalan o errores de importación.

## Runner self-hosted

- **Ubicación:** `/opt/actions-runner` en el LXC 143 `coin-cicd` (NO en producción).
- **Usuario:** `github-runner` (uid 1001, solo su grupo, **sin sudo**, sin grupos privilegiados).
- **Servicio:** `github-runner.service` (systemd), `User=github-runner`,
  `ExecStart=/opt/actions-runner/run.sh`, `Restart=always`, `NoNewPrivileges`, `PrivateTmp`.
- **Nombre/labels:** `coin-cicd-runner` · `self-hosted, linux, coinanalyze`.
- **Versión:** actions/runner 2.336.0.

### Operación

```bash
# estado / logs
systemctl status github-runner
journalctl -u github-runner -f

# detener / arrancar / deshabilitar
sudo systemctl stop github-runner
sudo systemctl start github-runner
sudo systemctl disable --now github-runner        # deshabilitar del arranque

# actualizar el runner (self-update automático; para forzar):
sudo systemctl stop github-runner
sudo -u github-runner bash -lc 'cd /opt/actions-runner && ./config.sh remove --token <REMOVE_TOKEN>'
#   descargar nueva versión, extraer, reconfigurar (ver más abajo) y start
```

### Retirar el runner de GitHub

```bash
# obtener token de remoción (requiere gh autenticado con scope repo):
gh api -X POST repos/achavezl911/coinanalyze/actions/runners/remove-token -q .token
# luego, como github-runner:
cd /opt/actions-runner && ./config.sh remove --token <REMOVE_TOKEN>
sudo systemctl disable --now github-runner
```

### Registro (referencia)

```bash
REG=$(gh api -X POST repos/achavezl911/coinanalyze/actions/runners/registration-token -q .token)
sudo -u github-runner bash -lc "cd /opt/actions-runner && ./config.sh \
  --url https://github.com/achavezl911/coinanalyze --token $REG \
  --labels self-hosted,linux,coinanalyze --name coin-cicd-runner --unattended --replace"
```

## Branch protection en `main`

Aplicada vía API:

- **Require pull request before merging** (1 review, `dismiss_stale_reviews`).
- **Require status checks** (strict): contexto `lint-and-test`.
- **Block force pushes**, **block deletions**, **required linear history**,
  **required conversation resolution**.
- `enforce_admins: false` — permite al owner (único humano) mergear PRs de agentes que él no
  puede auto-aprobar. Con un segundo revisor, subir a `true`.

## Secrets

- `DEPLOY_SSH_KEY` — clave **privada** ed25519 del usuario `coinalyze-deploy` en prod. Se define
  con `gh secret set DEPLOY_SSH_KEY < ~/.ssh/coinalyze_deploy_ed25519`. La pública está en
  `~coinalyze-deploy/.ssh/authorized_keys` en prod. La host key de prod está embebida en el
  workflow (es pública).
- Considera un **Environment `production`** con *required reviewers* para un gate manual extra
  en el deploy.
