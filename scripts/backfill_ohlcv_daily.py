#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import time

import asyncpg

from app.coinalyze import CoinalyzeClient
from app.config import get_settings
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
    conn = await asyncpg.connect(settings.pg_dsn)
    inserted = 0
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            settings.COINALYZE_RATE_LIMIT_UNITS,
        ) as client:
            for symbol in symbols:
                payload = await client.history(
                    "ohlcv-history",
                    [symbol],
                    interval="daily",
                    start_ts=start,
                    end_ts=end,
                )
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
        await conn.close()
    print(f"Backfill diario terminado: {inserted} filas procesadas", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
