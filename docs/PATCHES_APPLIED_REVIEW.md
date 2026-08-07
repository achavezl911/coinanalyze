# Parches aplicados por revisión técnica

## Seguridad

- `API_INTERNAL_TOKEN` dejó de ser fail-open. Si no está configurado, los endpoints internos protegidos responden `503` y no quedan públicos.
- Se agregó restricción de origen por CIDR para `/api/*` y `/metrics` mediante `API_INTERNAL_ALLOWED_CIDRS`.
- Se agregó `PG_SSLMODE` configurable para no forzar siempre `sslmode=disable`.
- Se agregó cabecera `Content-Security-Policy` básica en la aplicación FastAPI.

## Correctitud de señales

- `app/ai_context.py::daily_data` ahora incluye `cumulative_diff`, alineando `/api/ai/context*` con `/api/setup`.
- `app/scalp_logic.py` calcula `first_px` con el primer precio cronológico de la ventana, no con `MIN(last_px)`.
- Las filas `combined` de realtime spot/futures usan `last_event_ms` para seleccionar precio determinístico.
- El `combined` de order book ya no marca `ts=now()`: propaga timestamp real desde los venues incluidos.
- `data_confidence` degrada el book combinado si no hay dos venues vivos.

## Optimización

- `ingest.py` paraleliza las seis llamadas históricas independientes con `asyncio.gather`, conservando el rate limiter del cliente Coinalyze.
- `scalp_logic.py` evita subconsultas escalares repetidas para precio spot/futures.
- Se agregaron índices compuestos por `(symbol, exchange, ts DESC)` para consultas realtime/orderbook.

## Tokens IA

- `rough_token_estimate` usa `tiktoken` con `cl100k_base` y conserva fallback local si la librería no está disponible.

## Infraestructura

- `.env.example`, `deploy/proxmox/install.sh`, `scripts/update.sh` y `scripts/configure_secrets.sh` documentan o escriben `PG_SSLMODE`, `API_INTERNAL_TOKEN` obligatorio y `API_INTERNAL_ALLOWED_CIDRS`.
- `deploy/proxmox/README_STATIC_NETWORK.md` documenta que la IP estática del LXC debe inyectarse desde Proxmox, no desde el servicio de aplicación.
