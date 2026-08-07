# Validación v1.2.0

Comandos ejecutados en entorno limpio del árbol fuente:

```bash
python -m pytest -q
ruff check app tests scripts/calibrate_signals.py
python -m compileall -q app scripts/calibrate_signals.py
for f in scripts/*.sh deploy/proxmox/install.sh; do bash -n "$f"; done
python -m build --wheel --no-isolation
```

Resultado:

```text
pytest: 20 passed
ruff: passed
compileall: passed
bash -n: passed
wheel build: passed
```

Notas:

- El endpoint directo `http://127.0.0.1:8000/api/*` requiere `X-Internal-Token` si `API_INTERNAL_TOKEN` está configurado.
- `/metrics` también requiere `X-Internal-Token`.
- `scalp_signal_snapshot` no guarda secretos; solo señales operativas calculadas.
