from __future__ import annotations

import asyncio
import json
import logging
import math
import signal
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime

import asyncpg
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from app.config import SPOT_PAIR_MAP, get_settings
from app.db import create_pool, heartbeat
from app.logging_setup import configure_logging

LOGGER = logging.getLogger(__name__)
BINANCE_URL = (
    "wss://stream.binance.com:9443/stream?streams="
    "btcusdt@aggTrade/ethusdt@aggTrade/solusdt@aggTrade"
)
BYBIT_URL = "wss://stream.bybit.com/v5/public/spot"
MAX_NOTIONAL_USD = 1_000_000_000_000.0
MAX_MESSAGE_TRADES = 1_000
WHALE_TRADE_THRESHOLD = {'BTC': 5_000_000.0, 'ETH': 1_000_000.0, 'SOL': 200_000.0}
LATE_TRADE_GRACE_SECONDS = 125.0
REALTIME_MAX_EVENT_AGE_SECONDS = 15.0


@dataclass
class Bucket:
    buy_vol_usd: float = 0.0
    sell_vol_usd: float = 0.0
    inst_buy_usd: float = 0.0
    inst_sell_usd: float = 0.0
    mid_buy_usd: float = 0.0
    mid_sell_usd: float = 0.0
    retail_buy_usd: float = 0.0
    retail_sell_usd: float = 0.0
    trade_count: int = 0
    revision: int = 0

    def add(self, usd_value: float, is_buy: bool, whale_threshold: float) -> None:
        if is_buy:
            self.buy_vol_usd += usd_value
        else:
            self.sell_vol_usd += usd_value
        if usd_value >= whale_threshold:
            field = "inst_buy_usd" if is_buy else "inst_sell_usd"
        elif usd_value >= 10_000:
            field = "mid_buy_usd" if is_buy else "mid_sell_usd"
        else:
            field = "retail_buy_usd" if is_buy else "retail_sell_usd"
        setattr(self, field, getattr(self, field) + usd_value)
        self.trade_count += 1
        self.revision += 1


@dataclass
class RtBucket:
    buy_vol_usd: float = 0.0
    sell_vol_usd: float = 0.0
    inst_buy_usd: float = 0.0
    inst_sell_usd: float = 0.0
    trade_count: int = 0
    last_px: float = 0.0
    last_event_ms: int = 0
    revision: int = 0

    def add(
        self, usd_value: float, is_buy: bool, price: float, event_ms: int, whale_threshold: float
    ) -> None:
        if is_buy:
            self.buy_vol_usd += usd_value
        else:
            self.sell_vol_usd += usd_value
        if usd_value >= whale_threshold:
            if is_buy:
                self.inst_buy_usd += usd_value
            else:
                self.inst_sell_usd += usd_value
        if event_ms >= self.last_event_ms:
            self.last_event_ms = event_ms
            self.last_px = price
        self.trade_count += 1
        self.revision += 1


class BucketStore:
    def __init__(self, max_bucket_minutes: int = 20, max_buckets_per_key: int = 30) -> None:
        self.minute: dict[tuple[str, str, int], Bucket] = {}
        self.realtime: dict[tuple[str, str, int], RtBucket] = {}
        self.lock = asyncio.Lock()
        self.max_bucket_minutes = max_bucket_minutes
        self.max_buckets_per_key = max_buckets_per_key
        self.dropped_buckets = 0
        self.dropped_trades = 0

    async def add(
        self, symbol: str, exchange: str, event_ms: int, price: float, qty: float, is_buy: bool
    ) -> None:
        usd_value = price * qty
        minute_ts = (event_ms // 60_000) * 60
        rt_ts = (event_ms // 5_000) * 5
        async with self.lock:
            self.minute.setdefault((symbol, exchange, minute_ts), Bucket()).add(
                usd_value, is_buy, WHALE_TRADE_THRESHOLD[symbol]
            )
            if event_ms >= int((time.time() - REALTIME_MAX_EVENT_AGE_SECONDS) * 1000):
                self.realtime.setdefault((symbol, exchange, rt_ts), RtBucket()).add(
                    usd_value, is_buy, price, event_ms, WHALE_TRADE_THRESHOLD[symbol]
                )
            self._prune_locked()

    def _prune_locked(self) -> None:
        cutoff = int(time.time()) - (self.max_bucket_minutes * 60)
        for store in (self.minute, self.realtime):
            stale_keys = [key for key in store if key[2] < cutoff]
            for key in stale_keys:
                bucket = store.pop(key)
                self.dropped_buckets += 1
                self.dropped_trades += bucket.trade_count
            grouped: dict[tuple[str, str], list[tuple[int, tuple[str, str, int]]]] = {}
            for key in store:
                grouped.setdefault((key[0], key[1]), []).append((key[2], key))
            for items in grouped.values():
                overflow = len(items) - self.max_buckets_per_key
                for _, key in sorted(items)[:max(0, overflow)]:
                    bucket = store.pop(key)
                    self.dropped_buckets += 1
                    self.dropped_trades += bucket.trade_count

    async def prune(self) -> None:
        async with self.lock:
            self._prune_locked()

    async def minute_snapshot(self) -> list[tuple[tuple[str, str, int], Bucket]]:
        cutoff = time.time() - LATE_TRADE_GRACE_SECONDS
        async with self.lock:
            return [
                (key, replace(bucket))
                for key, bucket in self.minute.items()
                if key[2] + 60 <= cutoff
            ]

    async def realtime_snapshot(self) -> list[tuple[tuple[str, str, int], RtBucket]]:
        cutoff = time.time() - 3.0
        async with self.lock:
            return [
                (key, replace(bucket))
                for key, bucket in self.realtime.items()
                if key[2] + 5 <= cutoff
            ]

    async def ack_minute(self, snapshots: list[tuple[tuple[str, str, int], Bucket]]) -> None:
        async with self.lock:
            for key, snapshot in snapshots:
                current = self.minute.get(key)
                if current and current.revision == snapshot.revision:
                    self.minute.pop(key, None)

    async def ack_realtime(self, snapshots: list[tuple[tuple[str, str, int], RtBucket]]) -> None:
        async with self.lock:
            for key, snapshot in snapshots:
                current = self.realtime.get(key)
                if current and current.revision == snapshot.revision:
                    self.realtime.pop(key, None)


STORE = BucketStore()
LAST_EVENT_MONOTONIC = {"binance": 0.0, "bybit": 0.0}


def valid_trade(price_raw: object, qty_raw: object, ts_raw: object) -> tuple[float, float, int] | None:
    try:
        price = float(price_raw)  # type: ignore[arg-type]
        qty = float(qty_raw)  # type: ignore[arg-type]
        ts_ms = int(ts_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(price) or not math.isfinite(qty) or price <= 0 or qty <= 0:
        return None
    if price > 10_000_000 or qty > 100_000_000 or price * qty > MAX_NOTIONAL_USD:
        return None
    now_ms = int(time.time() * 1000)
    if ts_ms < now_ms - 120_000 or ts_ms > now_ms + 30_000:
        return None
    return price, qty, ts_ms


async def flush_minute(pool: asyncpg.Pool) -> None:
    while True:
        await asyncio.sleep(5)
        snapshots = await STORE.minute_snapshot()
        if not snapshots:
            continue
        records = []
        touched: set[tuple[str, int]] = set()
        for (symbol, exchange, ts), bucket in snapshots:
            touched.add((symbol, ts))
            records.append(
                (
                    datetime.fromtimestamp(ts, UTC), symbol, exchange, "1min",
                    bucket.buy_vol_usd, bucket.sell_vol_usd,
                    bucket.inst_buy_usd, bucket.inst_sell_usd,
                    bucket.mid_buy_usd, bucket.mid_sell_usd,
                    bucket.retail_buy_usd, bucket.retail_sell_usd, bucket.trade_count,
                )
            )
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(
                        """
                        INSERT INTO spot_trades_agg(
                          ts,symbol,exchange,interval,buy_vol_usd,sell_vol_usd,
                          inst_buy_usd,inst_sell_usd,mid_buy_usd,mid_sell_usd,
                          retail_buy_usd,retail_sell_usd,trade_count
                        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                        ON CONFLICT(symbol,exchange,interval,ts) DO UPDATE SET
                          buy_vol_usd=EXCLUDED.buy_vol_usd,
                          sell_vol_usd=EXCLUDED.sell_vol_usd,
                          inst_buy_usd=EXCLUDED.inst_buy_usd,
                          inst_sell_usd=EXCLUDED.inst_sell_usd,
                          mid_buy_usd=EXCLUDED.mid_buy_usd,
                          mid_sell_usd=EXCLUDED.mid_sell_usd,
                          retail_buy_usd=EXCLUDED.retail_buy_usd,
                          retail_sell_usd=EXCLUDED.retail_sell_usd,
                          trade_count=EXCLUDED.trade_count
                        """,
                        records,
                    )
                    await conn.executemany(
                        """
                        INSERT INTO spot_trades_agg(
                          ts,symbol,exchange,interval,buy_vol_usd,sell_vol_usd,
                          inst_buy_usd,inst_sell_usd,mid_buy_usd,mid_sell_usd,
                          retail_buy_usd,retail_sell_usd,trade_count
                        )
                        SELECT ts,symbol,'combined','1min',
                          SUM(buy_vol_usd),SUM(sell_vol_usd),SUM(inst_buy_usd),SUM(inst_sell_usd),
                          SUM(mid_buy_usd),SUM(mid_sell_usd),SUM(retail_buy_usd),SUM(retail_sell_usd),
                          SUM(trade_count)::integer
                        FROM spot_trades_agg
                        WHERE symbol=$1 AND ts=$2 AND exchange IN ('binance','bybit')
                        GROUP BY ts,symbol
                        ON CONFLICT(symbol,exchange,interval,ts) DO UPDATE SET
                          buy_vol_usd=EXCLUDED.buy_vol_usd,
                          sell_vol_usd=EXCLUDED.sell_vol_usd,
                          inst_buy_usd=EXCLUDED.inst_buy_usd,
                          inst_sell_usd=EXCLUDED.inst_sell_usd,
                          mid_buy_usd=EXCLUDED.mid_buy_usd,
                          mid_sell_usd=EXCLUDED.mid_sell_usd,
                          retail_buy_usd=EXCLUDED.retail_buy_usd,
                          retail_sell_usd=EXCLUDED.retail_sell_usd,
                          trade_count=EXCLUDED.trade_count
                        """,
                        [(symbol, datetime.fromtimestamp(ts, UTC)) for symbol, ts in touched],
                    )
            await STORE.ack_minute(snapshots)
        except Exception:
            LOGGER.exception("minute_flush_failed retained_buckets=%d", len(snapshots))


async def flush_realtime(pool: asyncpg.Pool) -> None:
    while True:
        await asyncio.sleep(2)
        snapshots = await STORE.realtime_snapshot()
        if not snapshots:
            continue
        records = []
        touched: set[tuple[str, int]] = set()
        for (symbol, exchange, ts), bucket in snapshots:
            touched.add((symbol, ts))
            records.append(
                (
                    datetime.fromtimestamp(ts, UTC), symbol, exchange,
                    bucket.buy_vol_usd, bucket.sell_vol_usd,
                    bucket.inst_buy_usd, bucket.inst_sell_usd,
                    bucket.trade_count, bucket.last_px, bucket.last_event_ms,
                )
            )
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.executemany(
                        """
                        INSERT INTO spot_trades_realtime(
                          ts,symbol,exchange,buy_vol_usd,sell_vol_usd,
                          inst_buy_usd,inst_sell_usd,trade_count,last_px,last_event_ms
                        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        ON CONFLICT(symbol,exchange,ts) DO UPDATE SET
                          buy_vol_usd=EXCLUDED.buy_vol_usd,
                          sell_vol_usd=EXCLUDED.sell_vol_usd,
                          inst_buy_usd=EXCLUDED.inst_buy_usd,
                          inst_sell_usd=EXCLUDED.inst_sell_usd,
                          trade_count=EXCLUDED.trade_count,
                          last_px=EXCLUDED.last_px,
                          last_event_ms=EXCLUDED.last_event_ms
                        """,
                        records,
                    )
                    await conn.executemany(
                        """
                        INSERT INTO spot_trades_realtime(
                          ts,symbol,exchange,buy_vol_usd,sell_vol_usd,
                          inst_buy_usd,inst_sell_usd,trade_count,last_px,last_event_ms
                        )
                        SELECT ts,symbol,'combined',SUM(buy_vol_usd),SUM(sell_vol_usd),
                          SUM(inst_buy_usd),SUM(inst_sell_usd),SUM(trade_count)::integer,
                          (array_agg(last_px ORDER BY last_event_ms DESC, exchange))[1],
                          MAX(last_event_ms)
                        FROM spot_trades_realtime
                        WHERE symbol=$1 AND ts=$2 AND exchange IN ('binance','bybit')
                        GROUP BY ts,symbol
                        ON CONFLICT(symbol,exchange,ts) DO UPDATE SET
                          buy_vol_usd=EXCLUDED.buy_vol_usd,
                          sell_vol_usd=EXCLUDED.sell_vol_usd,
                          inst_buy_usd=EXCLUDED.inst_buy_usd,
                          inst_sell_usd=EXCLUDED.inst_sell_usd,
                          trade_count=EXCLUDED.trade_count,
                          last_px=EXCLUDED.last_px,
                          last_event_ms=EXCLUDED.last_event_ms
                        """,
                        [(symbol, datetime.fromtimestamp(ts, UTC)) for symbol, ts in touched],
                    )
            await STORE.ack_realtime(snapshots)
        except Exception:
            LOGGER.exception("realtime_flush_failed retained_buckets=%d", len(snapshots))


async def binance_consumer() -> None:
    backoff = 1.0
    while True:
        try:
            async with connect(
                BINANCE_URL, open_timeout=10, close_timeout=5, ping_interval=20,
                ping_timeout=20, max_size=1_048_576, max_queue=64,
            ) as websocket:
                LOGGER.info("binance_connected")
                backoff = 1.0
                while True:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=60)
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        continue
                    data = message.get("data", {})
                    if not isinstance(data, dict):
                        continue
                    pair = str(data.get("s", ""))
                    symbol = pair.removesuffix("USDT")
                    if symbol not in SPOT_PAIR_MAP:
                        continue
                    trade = valid_trade(data.get("p"), data.get("q"), data.get("T"))
                    if trade is None:
                        continue
                    price, qty, ts_ms = trade
                    is_buy = not bool(data.get("m"))  # buyer-is-maker => aggressive sell
                    await STORE.add(symbol, "binance", ts_ms, price, qty, is_buy)
                    LAST_EVENT_MONOTONIC["binance"] = time.monotonic()
        except asyncio.CancelledError:
            raise
        except (ConnectionClosed, TimeoutError, OSError, json.JSONDecodeError):
            LOGGER.warning("binance_disconnected retry=%.1fs", backoff)
        except Exception:
            LOGGER.exception("binance_consumer_failed retry=%.1fs", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


async def bybit_consumer() -> None:
    backoff = 1.0
    args = [f"publicTrade.{pair}" for pair in SPOT_PAIR_MAP.values()]
    while True:
        try:
            async with connect(
                BYBIT_URL, open_timeout=10, close_timeout=5, ping_interval=20,
                ping_timeout=20, max_size=1_048_576, max_queue=64,
            ) as websocket:
                await websocket.send(json.dumps({"op": "subscribe", "args": args}))
                LOGGER.info("bybit_connected")
                backoff = 1.0
                while True:
                    raw = await asyncio.wait_for(websocket.recv(), timeout=60)
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        continue
                    if not str(message.get("topic", "")).startswith("publicTrade."):
                        continue
                    trades = message.get("data", [])
                    if not isinstance(trades, list) or len(trades) > MAX_MESSAGE_TRADES:
                        continue
                    default_ts = message.get("ts")
                    for data in trades:
                        if not isinstance(data, dict):
                            continue
                        pair = str(data.get("s", ""))
                        symbol = pair.removesuffix("USDT")
                        if symbol not in SPOT_PAIR_MAP:
                            continue
                        trade = valid_trade(data.get("p"), data.get("v"), data.get("T", default_ts))
                        if trade is None:
                            continue
                        price, qty, ts_ms = trade
                        is_buy = str(data.get("S", "")).lower() == "buy"
                        await STORE.add(symbol, "bybit", ts_ms, price, qty, is_buy)
                        LAST_EVENT_MONOTONIC["bybit"] = time.monotonic()
        except asyncio.CancelledError:
            raise
        except (ConnectionClosed, TimeoutError, OSError, json.JSONDecodeError):
            LOGGER.warning("bybit_disconnected retry=%.1fs", backoff)
        except Exception:
            LOGGER.exception("bybit_consumer_failed retry=%.1fs", backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 60.0)


async def heartbeat_loop(pool: asyncpg.Pool) -> None:
    while True:
        await asyncio.sleep(20)
        try:
            now = time.monotonic()
            ages = {
                name: (now - last if last > 0 else float("inf"))
                for name, last in LAST_EVENT_MONOTONIC.items()
            }
            status = "ok" if all(age <= 90.0 for age in ages.values()) else "degraded"
            age_text = ",".join(
                f"{name}={age:.0f}s" if math.isfinite(age) else f"{name}=never"
                for name, age in ages.items()
            )
            async with pool.acquire() as conn:
                await heartbeat(
                    conn,
                    "ws",
                    status=status,
                    detail=(
                        f"minute={len(STORE.minute)} realtime={len(STORE.realtime)} "
                        f"dropped_buckets={STORE.dropped_buckets} "
                        f"dropped_trades={STORE.dropped_trades} "
                        f"last_event:{age_text}"
                    ),
                )
                for exchange, age in ages.items():
                    venue_status = "ok" if age <= 90.0 else "degraded"
                    venue_age = f"{age:.0f}s" if math.isfinite(age) else "never"
                    await heartbeat(
                        conn,
                        f"ws-{exchange}",
                        status=venue_status,
                        detail=f"last_event={venue_age}",
                    )
        except Exception:
            LOGGER.exception("ws_heartbeat_failed")


async def run() -> None:
    global STORE
    settings = get_settings()
    STORE = BucketStore(
        max_bucket_minutes=settings.TRADESTORE_MAX_BUCKET_MINUTES,
        max_buckets_per_key=settings.TRADESTORE_MAX_BUCKETS_PER_KEY,
    )
    configure_logging(settings.LOG_LEVEL)
    pool = await create_pool(settings, application_name="coinalyze-ws")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    tasks = [
        asyncio.create_task(binance_consumer(), name="binance"),
        asyncio.create_task(bybit_consumer(), name="bybit"),
        asyncio.create_task(flush_minute(pool), name="flush-minute"),
        asyncio.create_task(flush_realtime(pool), name="flush-realtime"),
        asyncio.create_task(heartbeat_loop(pool), name="heartbeat"),
    ]
    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
