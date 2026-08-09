#!/usr/bin/env python3
"""Backfill idempotente de OHLCV 4h.

Existe porque el 5min de Coinalyze solo llega a ~8-9 dias, asi que los pivotes 4h de
price_barriers (720 barras = 120 dias) se estaban calculando sobre ~48. Medido contra la API
el 2026-08-04: el intervalo `4hour` responde completo a 30, 120, 200 y 300 dias, y vacio a
365. A diferencia de una fuente externa de precio, estas velas traen `bv`/`btx`, o sea que
conservan el reparto comprador/vendedor y el delta sigue siendo real.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import SPOT_HISTORY_MAP, get_settings
from app.db import create_pool
from app.ingest import upsert_ohlcv

MAX_SUPPORTED_DAYS = 300


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill idempotente de OHLCV 4h.")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--chunk-days", type=int, default=60)
    parser.add_argument(
        "--spot",
        action="store_true",
        help="rellena el spot del mismo venue (BTCUSD.A etc.) en vez del perp",
    )
    args = parser.parse_args()
    if not 1 <= args.days <= MAX_SUPPORTED_DAYS or not 1 <= args.chunk_days <= 120:
        parser.error(f"days=1..{MAX_SUPPORTED_DAYS} y chunk-days=1..120")

    settings = get_settings()
    # El spot recorre la MISMA rejilla y el mismo upsert: solo cambia el conjunto de simbolos.
    symbols = (
        tuple(SPOT_HISTORY_MAP[s] for s in settings.SYMBOLS if s in SPOT_HISTORY_MAP)
        if args.spot
        else tuple(settings.SYMBOLS)
    )
    if not symbols:
        parser.error("no hay simbolos que rellenar")
    identity = {symbol: symbol for symbol in symbols}
    end = int(time.time())
    start = end - args.days * 86400
    step = args.chunk_days * 86400
    pool = await create_pool(settings, application_name="coinalyze-backfill-4h")
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
                # Una peticion por simbolo evita que un hueco de 1-2 unidades en la cuota
                # global rechace el lote completo de tres activos.
                for symbol in symbols:
                    payload.update(
                        await client.history(
                            "ohlcv-history",
                            [symbol],
                            interval="4hour",
                            start_ts=cursor,
                            end_ts=chunk_end,
                        )
                    )
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        count = await upsert_ohlcv(
                            conn, payload, identity, cursor, chunk_end, "4hour"
                        )
                inserted += count
                if count and oldest_with_data is None:
                    oldest_with_data = cursor
                print(f"{cursor}..{chunk_end}: {count} filas", flush=True)
                cursor = chunk_end
        async with pool.acquire() as conn:
            covered = await conn.fetch(
                "SELECT symbol, count(*) AS bars, min(ts)::date AS oldest "
                "FROM ohlcv WHERE interval='4hour' GROUP BY symbol ORDER BY symbol"
            )
    finally:
        await pool.close()

    print(f"Backfill terminado: {inserted} filas procesadas", flush=True)
    for row in covered:
        print(f"  {row['symbol']}: {row['bars']} barras 4h desde {row['oldest']}", flush=True)
    if oldest_with_data is None:
        print("AVISO: ningun chunk devolvio datos.", flush=True)
        return
    horizon_days = (end - oldest_with_data) / 86400
    print(f"Horizonte real servido: ~{horizon_days:.0f} dias (se pidieron {args.days}).", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
