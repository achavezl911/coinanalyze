# Despliegue a producción

Producción es el **LXC 140 `coinalyze-final`** (`10.151.1.6`). El despliegue es **manual y con
guardas**, disparado desde GitHub Actions (`workflow_dispatch`), y ejecutado a través del wrapper
root que constituye el límite de confianza.

## Modelo de releases

```
/opt/coinalyze/
├── releases/
│   ├── <commit-sha>/           # código + .venv propio, inmutable
│   ├── <commit-sha>/
│   └── legacy-<ts>/            # snapshot de la instalación previa (rollback del 1er deploy)
├── current -> releases/<sha activo>
└── (árbol legacy original, conservado; no se borra)
```

Los servicios systemd usan `WorkingDirectory=/opt/coinalyze/current` y
`ExecStart=/opt/coinalyze/current/.venv/bin/...`. El estado activo se registra en
`/var/lib/coinalyze/deployment.json`:

```json
{ "commit": "...", "branch": "main", "deployed_at": "...",
  "previous_commit": "...", "deployment_source": "github-actions" }
```

## Cómo desplegar

1. Asegúrate de que el cambio está **mergeado a `main`** y CI está verde.
2. En GitHub → Actions → **Deploy production** → *Run workflow* (o CLI):

```bash
gh workflow run "Deploy production" -f action=deploy -f confirm="deploy production" --ref main
gh run watch
```

El workflow (en el runner self-hosted) hace:

1. Guarda: solo `main` + texto de confirmación exacto.
2. Checkout del commit de `main`.
3. Construye `coinalyze-<sha>.tgz` (excluye `.git`, `.github`, `.venv`, caches, `graphify-out`).
4. Calcula **SHA256**.
5. Carga la clave de deploy desde el secret `DEPLOY_SSH_KEY`; host key de prod embebida.
6. `scp` del artefacto a `coinalyze-deploy@10.151.1.6:incoming/`.
7. `ssh ... sudo -n /usr/local/sbin/deploy-coinalyze deploy <artefacto> <sha256> <commit>`.
8. Limpia el artefacto remoto y la clave local.

## Qué hace el wrapper (trust boundary)

`/usr/local/sbin/deploy-coinalyze` (root:root 0750, **no está en el repo**):

1. Valida que el artefacto esté bajo `incoming/` y que su **SHA256 coincida**.
2. Extrae a `releases/<sha>` y valida rutas requeridas (pyproject, requirements.lock,
   sql/schema.sql, app, static, scripts/smoke_test.sh).
3. Construye un `.venv` aislado del release.
4. **Backup de BD** (`pg_dump | gzip` en `/var/backups/coinalyze`) — dentro del boundary,
   sin ejecutar scripts del repo como root.
5. Primer deploy: **snapshot de la instalación previa** como `releases/legacy-<ts>` (rollback).
6. Aplica `schema.sql` (idempotente) como el rol `coinalyze` (no superusuario).
7. Cambia `current` → `releases/<sha>` de forma atómica; repunta los units si hace falta.
8. `systemctl restart` de los 5 servicios.
9. **Smoke test propio** (`/api/healthz`, `/api/symbols`, `/api/ai/profiles`).
10. Si el smoke pasa: escribe `deployment.json`, conserva los últimos 5 releases (nunca borra
    `legacy-*`). Si falla: **rollback automático** al release anterior.

## Seguridad clave

- Los agentes IA pueden editar el repo, **pero no** el wrapper ni el sudoers (root, fuera del repo).
- `coinalyze-deploy` solo puede `sudo` ese wrapper (NOPASSWD, un único binario).
- Los secretos productivos viven solo en `/etc/coinalyze/coinalyze.env`; el wrapper los lee como
  root únicamente para backup/schema/smoke.
- La clave privada de deploy vive en GitHub Secrets, no en disco de forma persistente.

Ver rollback en [ROLLBACK.md](ROLLBACK.md).
