# VALIDATION v1.2.4

Fecha de build: 2026-06-28

Validaciones ejecutadas en entorno de build:

```text
python3 -m compileall -q app scripts: OK
bash -n scripts/*.sh deploy/proxmox/install.sh: OK
python3 -m pip wheel --no-deps . -w dist: OK
```

Limitación: las pruebas pytest completas requieren dependencias runtime (`asyncpg`, FastAPI, etc.) y/o una instalación del entorno. Validar en runtime con:

```bash
sudo bash -lc '
set -a
source /etc/coinalyze/coinalyze.env
set +a
curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" \
  http://127.0.0.1:8000/api/healthz | python3 -m json.tool
curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" \
  "http://127.0.0.1:8000/api/ai/context?symbol=ETHUSDT_PERP.A&profile=default" | python3 -m json.tool
'
```
