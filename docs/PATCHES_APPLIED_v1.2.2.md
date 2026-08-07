# Patches aplicados v1.2.2

## Hardening del collector realtime

- Binance order book: detección de eventos tardíos, marcado stale y reconexión/resync programado.
- TradeStore: TTL/ring buffer en memoria para evitar crecimiento no limitado si PostgreSQL no confirma ACK.
- Health de scalp: incluye lag de book por exchange, tamaños de buckets, descartes de TradeStore y contadores Binance.
- Prometheus: expone contadores runtime del scalp desde el heartbeat.
- Config nueva: `TRADESTORE_MAX_BUCKET_MINUTES`, `TRADESTORE_MAX_BUCKETS_PER_KEY`, `BINANCE_BOOK_*`.

## Alcance no incluido

- Footprint/order-flow nativo y liquidity pressure map quedan para v1.3.0.
- Alert engine externo se entrega como `coinalyze-ai-telegram-bridge v0.1.1`.
