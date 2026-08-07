# Validación v1.2.2

```bash
pytest
ruff check app tests scripts/calibrate_signals.py
python -m compileall app scripts
bash -n scripts/*.sh deploy/proxmox/install.sh
node --check static/app.js
python -m build --wheel
```

Resultado local:

```text
pytest: 29/29 passed
ruff: passed
compileall: passed
bash -n: passed
node --check: passed
wheel build: passed
```

Casos nuevos:

- `TradeStore` descarta buckets antiguos.
- `TradeStore` descarta overflow por símbolo/exchange.
- `BookStore.exchange_lags()` reporta lag de Binance.
- Evento tardío de Binance depth fuerza stale/reconnect.
