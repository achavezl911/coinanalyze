# Patches aplicados — v1.2.0

Alcance: mejoras de retroalimentación, observabilidad y cierre de residuales posteriores a v1.1.2. No se modificó el manual/PDF.

## Cambios funcionales

1. Activación de `scalp_signal_snapshot`.
   - `coinalyze-scalp` persiste señales cada `SCALP_SIGNAL_INTERVAL_SECONDS`.
   - Nuevos campos: delta futures, delta spot, diff, divergencia spot/futuros, estado del book, basis y absorción.

2. Nuevos endpoints:
   - `/api/scalp/signals`
   - `/api/scalp/basis`
   - `/api/scalp/liquidation-levels`
   - `/api/data-confidence`
   - `/api/dashboard/state`
   - `/metrics`

3. Calibración offline.
   - `scripts/calibrate_signals.py` calcula forward returns T+1h/T+4h/T+1d por símbolo, estado, confianza y lado.

4. Observabilidad Prometheus.
   - Exposición de heartbeat lag, estado de servicios, lag de snapshots y conteo de tablas realtime.
   - Protegido por `X-Internal-Token`.

5. Data confidence.
   - Estado por símbolo basado en edad de `metrics_snapshot`, cobertura spot/futures por venue y book combinado.

6. Liquidation levels.
   - Agregación de liquidaciones realtime por bucket de precio en bps.

7. Basis perp-spot.
   - Cálculo con último precio futures combinado y spot combinado.

## Hardening adicional

- `hmac.compare_digest` para comparar `API_INTERNAL_TOKEN`.
- `smoke_test.sh` inyecta token cuando valida contra `127.0.0.1:8000`.
- `monitor()` de scalp degrada si hay feed vivo pero flush de trades/books/signals detenido.
- Limpieza de símbolos muertos (`REALTIME_INTERVALS`, `INTERVALS`, `interval_value`).
- Corrección de doble `create_pool()` accidental en `ingest.py`.
- Retención configurable para señales scalp.
- `daily_session_agg` conserva indefinidamente por default; se puede limitar con `DAILY_SESSION_RETENTION_DAYS`.

## Validación

- `pytest`: 20/20 passed.
- `ruff check app tests scripts/calibrate_signals.py`: passed.
- `compileall app scripts/calibrate_signals.py`: passed.
- `bash -n` en scripts de shell: passed.
- `python -m build --wheel --no-isolation`: passed.
