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
    parser = argparse.ArgumentParser(
        description="Backfill idempotente de OHLCV diario para memoria de mercado."
    )
    parser.add_argument("--days", type=int, default=730)
    args = parser.parse_args()
    if not 120 <= args.days <= 3650:
        parser.error("days=120..3650")

    settings = get_settings()
    symbols = tuple(settings.SYMBOLS)
    identity = {symbol: symbol for symbol in symbols}
    end = int(time.time())
    start = end - args.days * 86400
    pool = await create_pool(settings, application_name="coinalyze-backfill-daily")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    inserted = 0
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            for symbol in symbols:
                payload = await client.history(
                    "ohlcv-history",
                    [symbol],
                    interval="daily",
                    start_ts=start,
                    end_ts=end,
                )
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        count = await upsert_ohlcv(
                            conn,
                            payload,
                            identity,
                            start,
                            end,
                            "daily",
                        )
                inserted += count
                print(f"{symbol}: {count} días", flush=True)
    finally:
        await pool.close()
    print(f"Backfill diario terminado: {inserted} filas procesadas", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
