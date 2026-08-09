#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import time

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.db import create_pool
from app.ingest import upsert_ohlcv


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill idempotente de OHLCV 5min.")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--chunk-days", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.days <= 3650 or not 1 <= args.chunk_days <= 5:
        parser.error("days=1..3650 y chunk-days=1..5")

    settings = get_settings()
    symbols = tuple(settings.SYMBOLS)
    identity = {symbol: symbol for symbol in symbols}
    end = int(time.time())
    start = end - args.days * 86400
    step = args.chunk_days * 86400
    pool = await create_pool(settings, application_name="coinalyze-backfill-5m")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    inserted = 0
    oldest_with_data: int | None = None
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            cursor = start
            while cursor < end:
                chunk_end = min(cursor + step, end)
                payload = {}
                # Una peticion por simbolo evita que un hueco de solo 1-2 unidades en la
                # cuota global rechace el lote completo de tres activos.
                for symbol in symbols:
                    payload.update(
                        await client.history(
                            "ohlcv-history",
                            [symbol],
                            interval="5min",
                            start_ts=cursor,
                            end_ts=chunk_end,
                        )
                    )
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        count = await upsert_ohlcv(
                            conn,
                            payload,
                            identity,
                            cursor,
                            chunk_end,
                            "5min",
                        )
                inserted += count
                if count and oldest_with_data is None:
                    oldest_with_data = cursor
                print(f"{cursor}..{chunk_end}: {count} filas", flush=True)
                cursor = chunk_end
    finally:
        await pool.close()
    print(f"Backfill terminado: {inserted} filas procesadas", flush=True)
    # Medido el 2026-08-04 contra la API: ohlcv-history a 5min solo sirve ~8-9 dias hacia
    # atras (a 10 dias devuelve una ventana parcial, a 20 y 60 devuelve cero). Pedir 180 dias
    # no falla: devuelve chunks vacios y el total de filas son re-upserts de lo ya presente,
    # lo que se lee como un backfill exitoso que no amplio nada.
    if oldest_with_data is None:
        print("AVISO: ningun chunk devolvio datos.", flush=True)
        return
    horizon_days = (end - oldest_with_data) / 86400
    print(
        f"Horizonte real servido por Coinalyze: ~{horizon_days:.1f} dias "
        f"(se pidieron {args.days}).",
        flush=True,
    )
    if horizon_days < args.days * 0.9:
        print(
            "El proveedor no tiene 5min mas alla de ese punto: la profundidad de 5min solo "
            "puede crecer hacia adelante (rollup_ohlcv_5m, ~1 dia por dia de uptime). "
            "price_barriers declara la cobertura real en method.intraday_coverage_pct.",
            flush=True,
        )


if __name__ == "__main__":
    asyncio.run(main())
