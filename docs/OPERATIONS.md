# Runbook operativo

## Estado normal

- `coinalyze-ingest`: heartbeat menor a 180 segundos.
- `coinalyze-ws`: heartbeat menor a 90 segundos.
- `coinalyze-daily`: heartbeat menor a 3900 segundos.
- Snapshots por símbolo: lag menor a 180 segundos.
- `/api/healthz`: `status=ok`.

## Fallo de ingest

```bash
journalctl -u coinalyze-ingest --since '-30 min' --no-pager
systemctl restart coinalyze-ingest
```

Validar API key, DNS, reloj del sistema, respuesta 429 y conectividad HTTPS hacia
`api.coinalyze.net`. Un 429 sostenido requiere reducir frecuencia o símbolos, no
incrementar reintentos.

## Fallo WebSocket

```bash
journalctl -u coinalyze-ws --since '-30 min' --no-pager
getent ahosts stream.binance.com
getent ahosts stream.bybit.com
systemctl restart coinalyze-ws
```

Las desconexiones temporales se recuperan con backoff. Los buckets no confirmados se
mantienen en memoria y se reintentan tras recuperar PostgreSQL.

## Fallo PostgreSQL

```bash
systemctl status postgresql
sudo -u postgres pg_isready
journalctl -u postgresql --since '-30 min' --no-pager
```

Después de restaurar PostgreSQL no es necesario reiniciar en orden estricto; systemd
reintentará los procesos. Verifique después `/api/healthz`.

## Capacidad

```bash
sudo -u postgres psql -d coinalyze -c "SELECT pg_size_pretty(pg_database_size('coinalyze'));"
df -h /var/lib/postgresql /var/backups/coinalyze
free -h
```

La tarea daily elimina datos por retención cada hora. Si el disco crece de forma
anormal, verifique que `coinalyze-daily` esté activo y que no se hayan elevado las
ventanas de retención sin ampliar almacenamiento.

## Cambio de contraseña web

```bash
htpasswd /etc/nginx/coinalyze.htpasswd operator
nginx -t && systemctl reload nginx
```

## Rotación de API key

Edite `/etc/coinalyze/coinalyze.env`, cambie `API_KEY` y ejecute:

```bash
systemctl restart coinalyze-ingest
```

No es necesario reiniciar API, WS ni daily.
