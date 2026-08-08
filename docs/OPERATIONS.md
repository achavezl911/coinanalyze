# Operaciones

Referencia operativa del entorno DEV/CI-CD (LXC 143) y del deploy a producción (LXC 140).

## Inventario

| Recurso | Valor |
|---|---|
| Proxmox | `prox` 150.1.7.13 (PVE 9.2.2, Debian 13) |
| DEV/CI-CD | LXC **143** `coin-cicd`, `10.10.100.2/28` vlan10, gw `10.10.100.1`, DNS `10.10.100.4,1.1.1.1` |
| DEV recursos | 4 vCPU / 4 GB / 2 GB swap / rootfs 30 GB en storage `local` |
| Producción | LXC **140** `coinalyze-final`, `10.151.1.6` vlan151 |
| Repo | github.com/achavezl911/coinanalyze (default `main`) |

## Usuarios y privilegios

| Usuario | Host | Rol | Privilegio |
|---|---|---|---|
| `devops` | LXC 143 | desarrollo, Codex/Claude, git/gh | login por clave; en grupo sudo (sin NOPASSWD) |
| `github-runner` | LXC 143 | CI runner | sin sudo, solo su grupo |
| `coinalyze` | LXC 140 | runtime de la app | dueño de servicios; sin sudo |
| `coinalyze-deploy` | LXC 140 | recibe artefacto y llama al wrapper | sudo SOLO a `/usr/local/sbin/deploy-coinalyze` |

Claves SSH:
- `~/.ssh/coin-cicd_ed25519` (Windows) → `devops@10.10.100.2`.
- `~devops/.ssh/coinalyze_deploy_ed25519` (LXC 143) → `coinalyze-deploy@10.151.1.6`; la privada
  también en el secret `DEPLOY_SSH_KEY`.

## Comandos frecuentes

```bash
# --- DEV (ssh coin-cicd) ---
coin-worktree-create <codex|claude> <slug>     # nueva tarea/rama
coin-worktree-list
cd /srv/coinanalyze/repo && git fetch origin && git -C . log --oneline -3

# --- CI runner ---
systemctl status github-runner ; journalctl -u github-runner -f

# --- Deploy / rollback (GitHub Actions) ---
gh workflow run "Deploy production" -f action=deploy   -f confirm="deploy production" --ref main
gh workflow run "Deploy production" -f action=rollback --ref main
gh run watch

# --- ¿Qué commit corre producción? ---
#   (en prod, vía consola Proxmox o SSH como coinalyze-deploy)
sudo -n /usr/local/sbin/deploy-coinalyze status
cat /var/lib/coinalyze/deployment.json
```

## Estado y logs de producción

| Qué | Dónde |
|---|---|
| Release activo | `/opt/coinalyze/current` → `releases/<sha>` |
| Estado del deploy | `/var/lib/coinalyze/deployment.json` |
| Log del wrapper | `/var/log/coinalyze/deploy.log` |
| Backups pre-deploy (BD) | `/var/backups/coinalyze/predeploy-<sha>-<ts>.sql.gz` (retención 14 d) |
| Servicios | `systemctl status coinalyze-api|-ingest|-ws|-scalp|-daily|-ai-bridge` |
| Smoke manual | `sudo -n /usr/local/sbin/deploy-coinalyze status` |

## Mantenimiento del LXC DEV

- Actualizaciones: `sudo apt update && sudo apt upgrade` (Claude Code se actualiza por apt;
  Codex con `npm install -g @openai/codex@latest` como devops).
- Timezone: `America/Mexico_City`. onboot=1.
- Backup del contenedor: `vzdump 143` desde Proxmox (storage `local`).

## Troubleshooting

- **CI en cola y no arranca:** el runner está caído → `systemctl status github-runner` en LXC 143.
- **Deploy falla en smoke:** el wrapper ya hizo rollback; revisa `/var/log/coinalyze/deploy.log`
  y `journalctl -u coinalyze-api -n 120` en prod.
- **`gh`/git “not logged in” como devops:** la config vive en `~devops/.config/gh`; re-`gh auth login`.
- **`~/.ssh/config` roto tras editar desde PowerShell:** casi siempre es un **BOM UTF-8**;
  reescribir el archivo sin BOM.
- **El clasificador de auto-mode** bloquea acciones salientes/mutaciones (git push, gh api,
  deploy): ejecútalas tú en `ssh coin-cicd` o añade una regla de permiso.
