# Validación v1.2.1

Validación ejecutada en entorno limpio del paquete.

```text
pytest: 25/25 passed
ruff check app tests scripts/calibrate_signals.py: passed
compileall app scripts: passed
bash -n scripts/backup.sh scripts/calibrate_signals.py scripts/smoke_test.sh scripts/update.sh deploy/proxmox/install.sh: passed
node --check static/app.js: passed
wheel build: passed
```

## Notas

- `curl http://127.0.0.1:8000/api/healthz` sin `X-Internal-Token` debe devolver `403` si `API_INTERNAL_TOKEN` está configurado.
- Validación directa correcta:

```bash
sudo bash -lc '
set -a
source /etc/coinalyze/coinalyze.env
set +a
curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" http://127.0.0.1:8000/api/healthz
'
```

- Validación por Nginx correcta:

```bash
curl -sk -u operator:"$DASH_PASS" https://127.0.0.1:8443/api/healthz
```
