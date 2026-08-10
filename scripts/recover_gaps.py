#!/usr/bin/env python3
"""Constrained data-gap recovery.

Only adapters registered for the exact feed/exchange/market/granularity identity may
recover rows. This repository currently has no historical source with exact semantics for
the realtime event streams or order-book state, so those gaps are explicitly classified
as unrecoverable instead of being synthesized or substituted from another venue.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.data_gaps import (
    DataGap,
    RecoveryAdapter,
    RecoveryObservation,
    RecoveryValidationError,
    recover_unresolved_gaps,
)
from app.db import create_pool
from app.ingest import upsert_ohlcv


class CoinalyzeOhlcv1mAdapter:
    """Exact Binance perpetual 1-minute OHLCV recovery from the existing provider."""

    name = "coinalyze.ohlcv-history"
    feed = "ohlcv_1min"
    exchange = "binance"
    market = "perpetual"
    granularity = "1min"

    def __init__(self, client: CoinalyzeClient) -> None:
        self.client = client

    async def fetch(self, gap: DataGap) -> list[RecoveryObservation]:
        payload = await self.client.history(
            "ohlcv-history",
            [gap.symbol],
            interval="1min",
            start_ts=int(gap.start.timestamp()),
            end_ts=int(gap.end.timestamp()) - 1,
        )
        observations: list[RecoveryObservation] = []
        for row in payload.get(gap.symbol, []):
            try:
                timestamp = datetime.fromtimestamp(int(row["t"]), UTC)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RecoveryValidationError("invalid OHLCV recovery timestamp") from exc
            observations.append(
                RecoveryObservation(
                    timestamp=timestamp,
                    key=f"{gap.symbol}:1min:{int(timestamp.timestamp())}",
                    feed=self.feed,
                    exchange=self.exchange,
                    market=self.market,
                    symbol=gap.symbol,
                    granularity=self.granularity,
                    payload=row,
                )
            )
        return sorted(observations, key=lambda item: item.timestamp)

    async def persist(self, conn, observations) -> None:
        if not observations:
            raise RecoveryValidationError("no validated OHLCV observations to persist")
        symbol = observations[0].symbol
        payload = {symbol: [item.payload for item in observations]}
        count = await upsert_ohlcv(
            conn,
            payload,
            {symbol: symbol},
            int(observations[0].timestamp.timestamp()),
            int(observations[-1].timestamp.timestamp()),
            "1min",
        )
        if count != len(observations):
            raise RecoveryValidationError("validated OHLCV rows were not all persistable")


def exact_adapter_for(
    gap: DataGap,
    adapter: CoinalyzeOhlcv1mAdapter,
    allowed_symbols: frozenset[str],
) -> RecoveryAdapter | None:
    """Return only an adapter with identical source semantics and symbol identity.

    Falling through to ``None`` marks the gap unrecoverable; it never substitutes OHLCV
    for trades, another venue, another market, another granularity, or historical
    order-book synthesis.
    """
    identity = (gap.feed, gap.exchange, gap.market, gap.granularity)
    exact = (adapter.feed, adapter.exchange, adapter.market, adapter.granularity)
    return adapter if identity == exact and gap.symbol in allowed_symbols else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover explicit market-data gaps safely")
    parser.add_argument("--gap-id", type=int, help="recover one unresolved gap")
    parser.add_argument("--limit", type=int, default=100, help="maximum gaps to process")
    return parser.parse_args()


async def run(gap_id: int | None, limit: int) -> dict[str, int]:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-recover-gaps")
    limiter = PostgresSlidingWindowRateLimiter(
        pool,
        settings.COINALYZE_RATE_LIMIT_UNITS,
    )
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            adapter = CoinalyzeOhlcv1mAdapter(client)
            allowed_symbols = frozenset(settings.SYMBOLS)
            async with pool.acquire() as conn:
                counts = await recover_unresolved_gaps(
                    conn,
                    lambda gap: exact_adapter_for(gap, adapter, allowed_symbols),
                    gap_id=gap_id,
                    limit=limit,
                )
            return dict(counts)
    finally:
        await pool.close()


def main() -> None:
    args = parse_args()
    print(json.dumps(asyncio.run(run(args.gap_id, args.limit)), sort_keys=True))


if __name__ == "__main__":
    main()
