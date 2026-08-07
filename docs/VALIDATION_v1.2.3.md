# Validation v1.2.3

Local validation performed during package build:

- `pytest`: 33 passed
- `python -m compileall app scripts`: passed
- `ruff check app tests scripts`: passed
- `bash -n scripts/*.sh`: passed
- `python -m build --wheel`: passed

Runtime smoke commands after install:

```bash
sudo bash -lc '
set -a
source /etc/coinalyze/coinalyze.env
set +a
curl -fsS -H "X-Internal-Token: $API_INTERNAL_TOKEN" \
  "http://127.0.0.1:8000/api/ai/context?symbol=ETHUSDT_PERP.A&profile=default" \
  | python3 -m json.tool
'
```
