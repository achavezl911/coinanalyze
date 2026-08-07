# Patches aplicados — v1.1.1

Versión de respaldo funcional basada en la instalación validada en LXC Proxmox.

## Cambios funcionales

- Agregado modo **Scalp** con servicio `coinalyze-scalp`.
- Agregada ingesta WebSocket de futuros Binance USD-M y Bybit Linear.
- Agregado order book realtime Binance/Bybit y vista combinada.
- Agregadas tablas:
  - `futures_trades_realtime`
  - `futures_trades_agg`
  - `orderbook_snapshot`
  - `liquidations_realtime`
  - `scalp_signal_snapshot`
- Agregados endpoints:
  - `/api/scalp/summary`
  - `/api/scalp/delta-matrix`
  - `/api/scalp/orderbook`
  - `/api/scalp/absorption`
  - `/api/scalp/liquidations`
  - `/api/scalp/alerts`
- Agregado layout frontend orientado a scalping.
- Agregado manual de interpretación del modo scalping.

## Patches correctivos

- `TRUSTED_HOSTS` y `SYMBOLS` ahora usan `NoDecode` en `pydantic-settings` para aceptar CSV y JSON sin romper por decodificación prematura.
- `.env.example`, `install.sh` y `update.sh` normalizan `TRUSTED_HOSTS` y `SYMBOLS` como JSON entrecomillado compatible con `systemd` y `bash source`.
- `INTERVALS` usa `datetime.timedelta`, no strings como `'5 minutes'`, para evitar errores `asyncpg.exceptions.DataError` al enviar parámetros PostgreSQL `interval`.
- `schema.sql` actualiza explícitamente `pipeline_heartbeat_service_check` para incluir `scalp` en instalaciones existentes. `CREATE TABLE IF NOT EXISTS` no modifica constraints ya existentes.
- `update.sh` ya no falla si `coinalyze-scalp.service` todavía no existe antes del upgrade.
- `update.sh` espera hasta 60 segundos a que la API responda antes del smoke test final.
- El manual HTML está actualizado junto con el Markdown.

## Validación esperada post-upgrade

```bash
curl -i http://127.0.0.1:8000/api/healthz
```

Debe reportar:

```json
{
  "status": "ok",
  "missing_services": [],
  "missing_symbols": []
}
```

Validar tablas scalp:

```sql
select 'futures_trades_realtime' as table_name, count(*) rows, max(ts) latest from futures_trades_realtime
union all
select 'futures_trades_agg', count(*), max(ts) from futures_trades_agg
union all
select 'orderbook_snapshot', count(*), max(ts) from orderbook_snapshot
union all
select 'liquidations_realtime', count(*), max(ts) from liquidations_realtime
union all
select 'scalp_signal_snapshot', count(*), max(ts) from scalp_signal_snapshot;
```

`scalp_signal_snapshot` puede permanecer en cero; los endpoints calculan señales on-demand desde las tablas realtime.

# Patches aplicados — v1.1.2

Versión de hardening posterior a auditoría manual del árbol v1.1.1.

## Bugs corregidos

- `scalp_context` ya no colapsa a `{}` cuando falta el libro combinado. Se reemplazó el `CROSS JOIN` por `LEFT JOIN ... ON true` contra una fila base y se agregaron `book_status` y `book_lag_seconds`.
- El `scalp_score` integra divergencia spot/futuros como componente explícito. Pesos nuevos: futures delta 20%, spot/fut divergence 15%, book 20%, absorption 20%, liquidations 10%, OI 10%, VWAP 5%.
- El heartbeat de `scalp` queda bajo control del monitor. Los flushers ya no sobrescriben `degraded` con `ok` por temporizador.
- El libro combinado evita el estado cruzado entre venues. La profundidad se agrega, pero bid/ask/mid/spread se toman de un venue válido no cruzado.
- Bybit orderbook valida secuencia monotónica y fuerza reconexión/resync ante delta no monotónico o delta sin snapshot local.
- La cola de liquidaciones ya no descarta eventos en silencio: cuenta `liq_dropped` y registra overflow con rate-limit.
- `liq_norm` del regime score ahora usa `(short_liq - long_liq) / (short_liq + long_liq)`, balanceado en `[-1,1]`.
- VWAP de scalp usa el inicio de sesión NYSE, no medianoche UTC.
- Endpoints históricos rechazan intervalos sub-minuto; 15s/30s quedan reservados para endpoints realtime de scalp.
- Se eliminó el único uso de `innerHTML` en el frontend.
- Se agregó defensa en profundidad con `API_INTERNAL_TOKEN` opcional: Nginx inyecta `X-Internal-Token` y FastAPI lo exige si está configurado.
- Se subió `limit_req` de Nginx a `30r/s` para reducir falsos positivos con el dashboard multipanel.
- Se unificó el hardening de `coinalyze-scalp.service` con el resto de unidades systemd.

## Tests agregados

- `test_scalp_score_uses_spot_futures_divergence`
- `test_scalp_summary_degrades_when_book_missing`
- `test_local_book_rejects_non_monotonic_sequence`
- `test_liquidation_queue_overflow_is_counted`

## Validación local

- `pytest`: 18/18 passed.
- `ruff check`: passed.
- `compileall app`: passed.
- `bash -n` sobre scripts de despliegue: passed.
- `python -m build --wheel`: passed.


## v1.2.1 — cierre de residuales

- Separación de lógica scalp en `app/scalp_logic.py`.
- Frontend cableado a basis, señales persistidas, niveles de liquidación y `/api/dashboard/state`.
- Calibración con modos `episode` y `non_overlap`.
- Documentación de Prometheus protegida por token/Basic Auth.
- Validación: 25/25 tests.
