# VALIDATION v1.2.5

Validaciones ejecutadas para el paquete final:

```bash
find app scripts -name '*.py' -print0 | xargs -0 python3 -m py_compile
python3 -m pytest -q  # 38 passed
bash -n deploy/proxmox/install.sh scripts/update.sh scripts/configure_secrets.sh
```

Validación funcional en host de destino:

```bash
sudo nginx -t
sudo cat /etc/nginx/snippets/coinalyze-allowlist.conf
sudo bash -lc 'set -a; source /etc/coinalyze/coinalyze.env; set +a; curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" http://127.0.0.1:8000/api/healthz | python3 -m json.tool'
```

Criterio de seguridad:

- `/etc/nginx/snippets/coinalyze-allowlist.conf` debe contener al menos un `allow` CIDR y `deny all;`.
- Una IP fuera de `NGINX_ALLOWED_CIDRS` debe recibir `403` desde nginx.
