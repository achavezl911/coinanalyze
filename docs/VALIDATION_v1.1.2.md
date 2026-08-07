# Validación v1.1.2

Fecha: 2026-06-27

## Resultado

- `pytest`: 18/18 passed.
- `ruff check .`: passed.
- `python -m compileall -q app`: passed.
- `bash -n scripts/update.sh deploy/proxmox/install.sh scripts/backup.sh scripts/smoke_test.sh`: passed.
- `python -m build --wheel --no-isolation`: passed.

## Alcance de fixes

- Fixes B1-B6 de auditoría v1.1.1.
- Rebalanceo de scalp score con divergencia spot/futuros.
- `liq_norm` simétrico en regime score.
- VWAP anclado a sesión NYSE.
- FastAPI internal token opcional con inyección desde Nginx.
- Frontend sin `innerHTML`.
- Endpoints históricos sin intervalos sub-minuto.
- Hardening systemd unificado para scalp.
