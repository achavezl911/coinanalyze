from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import websockets
from websockets.exceptions import ConnectionClosed

from app.config import FUTURES_PAIR_MAP, LARGE_TRADE_THRESHOLD_MAP, PAIR_SYMBOL_MAP, get_settings
from app.data_gaps import record_event_stream_loss
from app.db import (
    ServiceOwnership,
    ServiceOwnershipLost,
    acquire_service_lock,
    create_pool,
    fenced_transaction,
    heartbeat_shard,
    mark_feed_shard_connected,
    mark_feed_shard_degraded,
    mark_feed_shard_error,
    monitor_service_lock,
)
from app.logging_setup import configure_logging
from app.partitioning import apply_temporal_retention
from app.scalp_logic import compute_scalp_summary, scalp_context
from app.sharding import assigned_symbols

LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()
configure_logging(SETTINGS.LOG_LEVEL)
ACTIVE_SYMBOLS = assigned_symbols(
    tuple(SETTINGS.SYMBOLS),
    SETTINGS.COLLECTOR_SHARD_INDEX,
    SETTINGS.COLLECTOR_SHARD_COUNT,
)
ACTIVE_SYMBOL_SET = frozenset(ACTIVE_SYMBOLS)
LIQUIDATION_HEALTH_SHARDS = tuple(
    shard_index
    for shard_index in range(SETTINGS.COLLECTOR_SHARD_COUNT)
    if assigned_symbols(
        tuple(SETTINGS.SYMBOLS),
        shard_index,
        SETTINGS.COLLECTOR_SHARD_COUNT,
    )
)

BINANCE_STREAM_BASE = "wss://fstream.binance.com/stream?streams="
BINANCE_MARKET_STREAM_BASE = "wss://fstream.binance.com/market/stream?streams="
BYBIT_LINEAR_WS = "wss://stream.bybit.com/v5/public/linear"
MAX_NOTIONAL_USD = 10_000_000_000.0
LARGE_TRADE_THRESHOLD = LARGE_TRADE_THRESHOLD_MAP
REALTIME_MAX_EVENT_AGE_SECONDS = 15.0
LATE_TRADE_GRACE_SECONDS = 125.0
TRADESTORE_DROPPED_BUCKETS = 0
TRADESTORE_DROPPED_TRADES = 0
BINANCE_BOOK_STALE_TOTAL = 0
BINANCE_BOOK_RECONNECT_TOTAL = 0
WS_RECONNECT_INITIAL_SECONDS = 5.0
WS_RECONNECT_MAX_SECONDS = 60.0

LIQUIDATION_INSERT_SQL = """
INSERT INTO liquidations_realtime(ts,symbol,exchange,side,notional_usd,price,qty,event_id)
VALUES($1,$2,$3,$4,$5,$6,$7,$8)
ON CONFLICT(exchange,event_id,ts) DO NOTHING
"""


class BookResyncRequired(RuntimeError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def floor_ts_seconds(event_ms: int, bucket_seconds: int) -> int:
    return (event_ms // (bucket_seconds * 1000)) * bucket_seconds


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
    current = now_ms()
    if ts_ms < current - 120_000 or ts_ms > current + 30_000:
        return None
    return price, qty, ts_ms


@dataclass
class TradeBucket:
    buy_vol_usd: float = 0.0
    sell_vol_usd: float = 0.0
    large_buy_usd: float = 0.0
    large_sell_usd: float = 0.0
    trade_count: int = 0
    last_px: float = 0.0
    last_event_ms: int = 0
    revision: int = 0

    def add(self, usd_value: float, is_buy: bool, price: float, event_ms: int, large_threshold: float) -> None:
        if is_buy:
            self.buy_vol_usd += usd_value
            if usd_value >= large_threshold:
                self.large_buy_usd += usd_value
        else:
            self.sell_vol_usd += usd_value
            if usd_value >= large_threshold:
                self.large_sell_usd += usd_value
        if event_ms >= self.last_event_ms:
            self.last_event_ms = event_ms
            self.last_px = price
        self.trade_count += 1
        self.revision += 1


class TradeStore:
    def __init__(self) -> None:
        self.realtime: dict[tuple[str, str, int], TradeBucket] = {}
        self.minute: dict[tuple[str, str, int], TradeBucket] = {}
        self.lock = asyncio.Lock()

    async def add(self, symbol: str, exchange: str, event_ms: int, price: float, qty: float, is_buy: bool) -> None:
        usd_value = price * qty
        rt_ts = floor_ts_seconds(event_ms, 5)
        minute_ts = floor_ts_seconds(event_ms, 60)
        async with self.lock:
            self.minute.setdefault((symbol, exchange, minute_ts), TradeBucket()).add(
                usd_value, is_buy, price, event_ms, LARGE_TRADE_THRESHOLD[symbol]
            )
            if event_ms >= int((time.time() - REALTIME_MAX_EVENT_AGE_SECONDS) * 1000):
                self.realtime.setdefault((symbol, exchange, rt_ts), TradeBucket()).add(
                    usd_value, is_buy, price, event_ms, LARGE_TRADE_THRESHOLD[symbol]
                )
            self._prune_locked()

    def _prune_locked(self) -> None:
        global TRADESTORE_DROPPED_BUCKETS, TRADESTORE_DROPPED_TRADES
        now_sec = int(time.time())
        ttl_cutoff = now_sec - (SETTINGS.TRADESTORE_MAX_BUCKET_MINUTES * 60)
        for store_name, store in (("realtime", self.realtime), ("minute", self.minute)):
            stale_keys = [key for key in store if key[2] < ttl_cutoff]
            for key in stale_keys:
                bucket = store.pop(key)
                TRADESTORE_DROPPED_BUCKETS += 1
                TRADESTORE_DROPPED_TRADES += bucket.trade_count
            grouped: dict[tuple[str, str], list[tuple[int, tuple[str, str, int]]]] = {}
            for key in store:
                grouped.setdefault((key[0], key[1]), []).append((key[2], key))
            for _, entries in grouped.items():
                if len(entries) <= SETTINGS.TRADESTORE_MAX_BUCKETS_PER_KEY:
                    continue
                overflow = sorted(entries)[: len(entries) - SETTINGS.TRADESTORE_MAX_BUCKETS_PER_KEY]
                for _, key in overflow:
                    bucket = store.pop(key)
                    TRADESTORE_DROPPED_BUCKETS += 1
                    TRADESTORE_DROPPED_TRADES += bucket.trade_count
            if stale_keys:
                LOGGER.warning(
                    "tradestore_pruned_stale store=%s buckets=%d dropped_buckets_total=%d dropped_trades_total=%d",
                    store_name, len(stale_keys), TRADESTORE_DROPPED_BUCKETS, TRADESTORE_DROPPED_TRADES,
                )

    async def prune(self) -> None:
        async with self.lock:
            self._prune_locked()

    async def realtime_snapshot(self) -> list[tuple[tuple[str, str, int], TradeBucket]]:
        cutoff = time.time() - 3.0
        async with self.lock:
            self._prune_locked()
            return [(k, replace(v)) for k, v in self.realtime.items() if k[2] + 5 <= cutoff]

    async def minute_snapshot(self) -> list[tuple[tuple[str, str, int], TradeBucket]]:
        cutoff = time.time() - LATE_TRADE_GRACE_SECONDS
        async with self.lock:
            self._prune_locked()
            return [(k, replace(v)) for k, v in self.minute.items() if k[2] + 60 <= cutoff]

    async def ack_realtime(self, snapshots: list[tuple[tuple[str, str, int], TradeBucket]]) -> None:
        async with self.lock:
            for key, snap in snapshots:
                current = self.realtime.get(key)
                if current and current.revision == snap.revision:
                    self.realtime.pop(key, None)

    async def ack_minute(self, snapshots: list[tuple[tuple[str, str, int], TradeBucket]]) -> None:
        async with self.lock:
            for key, snap in snapshots:
                current = self.minute.get(key)
                if current and current.revision == snap.revision:
                    self.minute.pop(key, None)

    async def size(self) -> tuple[int, int]:
        async with self.lock:
            return len(self.realtime), len(self.minute)


@dataclass
class BookStats:
    ts_ms: int
    symbol: str
    exchange: str
    bid_px: float | None
    ask_px: float | None
    mid_px: float | None
    spread_bps: float | None
    bid_notional_l1: float
    ask_notional_l1: float
    bid_notional_l5: float
    ask_notional_l5: float
    bid_notional_l10: float
    ask_notional_l10: float
    imbalance_l1: float | None
    imbalance_l5: float | None
    imbalance_l10: float | None
    wall_up_pct: float | None
    wall_down_pct: float | None


class LocalBook:
    def __init__(self, symbol: str, exchange: str) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.bids: dict[float, float] = {}
        self.asks: dict[float, float] = {}
        self.ts_ms = 0
        self.update_id: int | None = None
        self.cross_seq: int | None = None

    def reset(
        self,
        bids: list[list[str]],
        asks: list[list[str]],
        ts_ms: int,
        update_id: int | None = None,
        cross_seq: int | None = None,
    ) -> None:
        self.bids = self._levels(bids)
        self.asks = self._levels(asks)
        self.ts_ms = ts_ms
        self.update_id = update_id
        self.cross_seq = cross_seq

    def apply_delta(
        self,
        bids: list[list[str]],
        asks: list[list[str]],
        ts_ms: int,
        update_id: int | None = None,
        cross_seq: int | None = None,
    ) -> bool:
        if update_id is None:
            return False
        if self.update_id is not None and update_id != self.update_id + 1:
            return False
        for book, levels in ((self.bids, bids), (self.asks, asks)):
            for price_raw, qty_raw in levels:
                try:
                    price = float(price_raw)
                    qty = float(qty_raw)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue
                if qty <= 0:
                    book.pop(price, None)
                else:
                    book[price] = qty
        self.ts_ms = ts_ms
        if update_id is not None:
            self.update_id = update_id
        self.cross_seq = cross_seq
        return True

    @staticmethod
    def _levels(levels: list[list[str]]) -> dict[float, float]:
        result: dict[float, float] = {}
        for price_raw, qty_raw in levels:
            try:
                price = float(price_raw)
                qty = float(qty_raw)
            except (TypeError, ValueError):
                continue
            if price > 0 and qty > 0:
                result[price] = qty
        return result

    def stats(self) -> BookStats | None:
        if not self.bids or not self.asks:
            return None
        bids = sorted(self.bids.items(), reverse=True)[:10]
        asks = sorted(self.asks.items())[:10]
        bid_px = bids[0][0]
        ask_px = asks[0][0]
        if bid_px <= 0 or ask_px <= 0 or ask_px < bid_px:
            return None
        mid = (bid_px + ask_px) / 2
        spread_bps = ((ask_px - bid_px) / mid) * 10_000 if mid > 0 else None

        def notional(levels: list[tuple[float, float]], n: int) -> float:
            return sum(price * qty for price, qty in levels[:n])

        b1, a1 = notional(bids, 1), notional(asks, 1)
        b5, a5 = notional(bids, 5), notional(asks, 5)
        b10, a10 = notional(bids, 10), notional(asks, 10)

        def imb(b: float, a: float) -> float | None:
            return b / (b + a) if b + a > 0 else None

        max_ask = max(asks, key=lambda x: x[0] * x[1])[0] if asks else None
        max_bid = max(bids, key=lambda x: x[0] * x[1])[0] if bids else None
        wall_up_pct = ((max_ask - mid) / mid) * 100 if max_ask and mid > 0 else None
        wall_down_pct = ((mid - max_bid) / mid) * 100 if max_bid and mid > 0 else None
        return BookStats(
            ts_ms=self.ts_ms,
            symbol=self.symbol,
            exchange=self.exchange,
            bid_px=bid_px,
            ask_px=ask_px,
            mid_px=mid,
            spread_bps=spread_bps,
            bid_notional_l1=b1,
            ask_notional_l1=a1,
            bid_notional_l5=b5,
            ask_notional_l5=a5,
            bid_notional_l10=b10,
            ask_notional_l10=a10,
            imbalance_l1=imb(b1, a1),
            imbalance_l5=imb(b5, a5),
            imbalance_l10=imb(b10, a10),
            wall_up_pct=wall_up_pct,
            wall_down_pct=wall_down_pct,
        )


class BookStore:
    def __init__(self) -> None:
        self.books: dict[tuple[str, str], LocalBook] = {}
        self.lock = asyncio.Lock()

    async def set_snapshot(
        self,
        symbol: str,
        exchange: str,
        bids: list[list[str]],
        asks: list[list[str]],
        ts_ms: int,
        update_id: int | None = None,
        cross_seq: int | None = None,
    ) -> None:
        async with self.lock:
            self.books.setdefault((symbol, exchange), LocalBook(symbol, exchange)).reset(
                bids,
                asks,
                ts_ms,
                update_id,
                cross_seq,
            )

    async def apply_delta(
        self,
        symbol: str,
        exchange: str,
        bids: list[list[str]],
        asks: list[list[str]],
        ts_ms: int,
        update_id: int | None = None,
        cross_seq: int | None = None,
    ) -> bool:
        async with self.lock:
            key = (symbol, exchange)
            book = self.books.get(key)
            if book is None:
                return False
            ok = book.apply_delta(bids, asks, ts_ms, update_id, cross_seq)
            if not ok:
                self.books.pop(key, None)
            return ok

    async def drop_exchange(self, exchange: str) -> None:
        async with self.lock:
            for key in list(self.books):
                if key[1] == exchange:
                    self.books.pop(key, None)

    async def symbol_exchange_lags(self) -> dict[tuple[str, str], int]:
        now = now_ms()
        async with self.lock:
            return {
                key: int((now - book.ts_ms) / 1000) if book.ts_ms else -1
                for key, book in self.books.items()
            }

    async def snapshot(self) -> list[BookStats]:
        async with self.lock:
            stats = [book.stats() for book in self.books.values()]
        return [item for item in stats if item is not None]

    async def ladders(self) -> list[tuple[str, str, int, list[list[float]], list[list[float]]]]:
        """Escalera completa por venue, para calcular slippage de cualquier tamanio.

        `stats()` trunca a 10 niveles, pero Bybit entrega 50 (`orderbook.50`) y se estaban
        tirando. Se guarda la escalera cruda, no un slippage precalculado, para que el tamanio
        de la posicion sea un parametro de consulta y no una constante del esquema.
        """
        async with self.lock:
            out = []
            for (symbol, exchange), book in self.books.items():
                if not book.bids or not book.asks:
                    continue
                bids = [[p, q] for p, q in sorted(book.bids.items(), reverse=True)]
                asks = [[p, q] for p, q in sorted(book.asks.items())]
                out.append((symbol, exchange, book.ts_ms, bids, asks))
        return out


TRADE_STORE = TradeStore()
BOOK_STORE = BookStore()
LIQ_QUEUE: asyncio.Queue[tuple[datetime, str, str, str, float, float, float, str]] = asyncio.Queue(maxsize=5000)
LAST_TRADE_EVENT = {
    (symbol, exchange): 0.0
    for symbol in ACTIVE_SYMBOLS
    for exchange in ("binance", "bybit")
}
LAST_FLUSH = {"trades": 0.0, "books": 0.0, "liquidations": 0.0, "signals": 0.0}
LIQ_DROPPED = 0
LIQ_FEED_CONNECTED = {"binance": False, "bybit": False}
LIQ_LOSS_PENDING: dict[str, datetime] = {}
LIQ_GAP_PENDING: set[tuple[str, str, datetime]] = set()


async def persist_liquidation_feed_state(
    pool: asyncpg.Pool | None,
    exchange: str,
    status: str,
    detail: str | None = None,
    *,
    data_loss: bool = False,
    ownership: ServiceOwnership | None = None,
) -> bool:
    """Persist low-frequency feed state; event handlers only mutate in-memory flags."""
    if pool is None:
        return False
    fence = {"ownership": ownership} if ownership is not None else {}
    try:
        async with pool.acquire() as conn:
            if status == "ok":
                await mark_feed_shard_connected(
                    conn,
                    "liquidations",
                    exchange,
                    SETTINGS.COLLECTOR_SHARD_INDEX,
                    SETTINGS.COLLECTOR_SHARD_COUNT,
                    LIQUIDATION_HEALTH_SHARDS,
                    detail,
                    **fence,
                )
            elif status == "error":
                await mark_feed_shard_error(
                    conn,
                    "liquidations",
                    exchange,
                    SETTINGS.COLLECTOR_SHARD_INDEX,
                    SETTINGS.COLLECTOR_SHARD_COUNT,
                    LIQUIDATION_HEALTH_SHARDS,
                    detail,
                    data_loss=data_loss,
                    **fence,
                )
            else:
                await mark_feed_shard_degraded(
                    conn,
                    "liquidations",
                    exchange,
                    SETTINGS.COLLECTOR_SHARD_INDEX,
                    SETTINGS.COLLECTOR_SHARD_COUNT,
                    LIQUIDATION_HEALTH_SHARDS,
                    detail,
                    data_loss=data_loss,
                    **fence,
                )
        return True
    except ServiceOwnershipLost:
        raise
    except Exception:
        LOGGER.exception(
            "liquidation_feed_health_persist_failed exchange=%s status=%s",
            exchange,
            status,
        )
        return False


async def persist_liquidation_health_snapshot(
    conn: asyncpg.Connection,
    ownership: ServiceOwnership | None = None,
) -> None:
    """Flush connection and loss flags from memory without doing DB I/O per event."""
    fence = {"ownership": ownership} if ownership is not None else {}
    for exchange, connected in LIQ_FEED_CONNECTED.items():
        loss_at = LIQ_LOSS_PENDING.get(exchange)
        if loss_at is not None:
            await mark_feed_shard_degraded(
                conn,
                "liquidations",
                exchange,
                SETTINGS.COLLECTOR_SHARD_INDEX,
                SETTINGS.COLLECTOR_SHARD_COUNT,
                LIQUIDATION_HEALTH_SHARDS,
                f"queue overflow detected at {loss_at.isoformat()}",
                data_loss=True,
                **fence,
            )
            pending_gaps = sorted(
                (item for item in LIQ_GAP_PENDING if item[1] == exchange),
                key=lambda item: (item[2], item[0]),
            )
            for symbol, gap_exchange, event_at in pending_gaps:
                await persist_liquidation_event_loss(
                    conn, symbol, gap_exchange, event_at, ownership=ownership,
                )
                LIQ_GAP_PENDING.discard((symbol, gap_exchange, event_at))
        if connected:
            await mark_feed_shard_connected(
                conn,
                "liquidations",
                exchange,
                SETTINGS.COLLECTOR_SHARD_INDEX,
                SETTINGS.COLLECTOR_SHARD_COUNT,
                LIQUIDATION_HEALTH_SHARDS,
                "subscription active",
                **fence,
            )
        else:
            await mark_feed_shard_degraded(
                conn,
                "liquidations",
                exchange,
                SETTINGS.COLLECTOR_SHARD_INDEX,
                SETTINGS.COLLECTOR_SHARD_COUNT,
                LIQUIDATION_HEALTH_SHARDS,
                "stream disconnected",
                **fence,
            )
        if loss_at is not None and LIQ_LOSS_PENDING.get(exchange) == loss_at:
            LIQ_LOSS_PENDING.pop(exchange, None)


async def persist_liquidation_event_loss(
    conn: asyncpg.Connection,
    symbol: str,
    exchange: str,
    event_at: datetime,
    *,
    ownership: ServiceOwnership | None = None,
) -> int:
    """Fence the collector generation in the transaction that records event loss."""
    async with fenced_transaction(conn, ownership):
        return await record_event_stream_loss(
            conn,
            feed="liquidations",
            exchange=exchange,
            market="perpetual",
            symbol=symbol,
            start=event_at,
            end=event_at + timedelta(microseconds=1),
            evidence_type="queue_full",
            detection_reason="liquidation event dropped because the persistence queue was full",
            detection_source="scalp_collector.safe_liq_put",
        )


async def reset_liquidation_feed_health(
    conn: asyncpg.Connection,
    ownership: ServiceOwnership | None = None,
) -> None:
    """Break persisted continuity before any stream can reconnect after process start."""
    fence = {"ownership": ownership} if ownership is not None else {}
    for exchange in LIQ_FEED_CONNECTED:
        LIQ_FEED_CONNECTED[exchange] = False
        await mark_feed_shard_degraded(
            conn,
            "liquidations",
            exchange,
            SETTINGS.COLLECTOR_SHARD_INDEX,
            SETTINGS.COLLECTOR_SHARD_COUNT,
            LIQUIDATION_HEALTH_SHARDS,
            "scalp collector starting; awaiting stream confirmation",
            **fence,
        )


def mark_exchange_disconnected(exchange: str) -> None:
    for symbol in ACTIVE_SYMBOLS:
        LAST_TRADE_EVENT[(symbol, exchange)] = 0.0


def all_expected_fresh(
    lags: dict[tuple[str, str], int],
    expected: set[tuple[str, str]],
    max_lag: int,
) -> bool:
    return bool(expected) and all(0 <= lags.get(key, -1) < max_lag for key in expected)


async def flush_trades(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    while True:
        await asyncio.sleep(SETTINGS.SCALP_FLUSH_SECONDS)
        snapshots = await TRADE_STORE.realtime_snapshot()
        minute_snapshots = await TRADE_STORE.minute_snapshot()
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, ownership):
                    if snapshots:
                        await _write_trade_rows(conn, "futures_trades_realtime", snapshots, realtime=True)
                        await _write_combined_realtime(conn, snapshots)
                    if minute_snapshots:
                        await _write_trade_rows(conn, "futures_trades_agg", minute_snapshots, realtime=False)
                        await _write_combined_minute(conn, minute_snapshots)
                    if snapshots or minute_snapshots:
                        LAST_FLUSH["trades"] = time.monotonic()
            if snapshots:
                await TRADE_STORE.ack_realtime(snapshots)
            if minute_snapshots:
                await TRADE_STORE.ack_minute(minute_snapshots)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("scalp_trade_flush_failed")
            await TRADE_STORE.prune()


async def _write_trade_rows(
    conn: asyncpg.Connection,
    table: str,
    snapshots: list[tuple[tuple[str, str, int], TradeBucket]],
    *,
    realtime: bool,
) -> None:
    if realtime:
        records = [
            (
                datetime.fromtimestamp(ts, UTC), symbol, exchange,
                b.buy_vol_usd, b.sell_vol_usd, b.large_buy_usd, b.large_sell_usd,
                b.trade_count, b.last_px, b.last_event_ms,
            )
            for (symbol, exchange, ts), b in snapshots
        ]
        await conn.executemany(
            f"""
            INSERT INTO {table}(ts,symbol,exchange,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count,last_px,last_event_ms)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT(symbol,exchange,ts) DO UPDATE SET
              buy_vol_usd=EXCLUDED.buy_vol_usd,
              sell_vol_usd=EXCLUDED.sell_vol_usd,
              large_buy_usd=EXCLUDED.large_buy_usd,
              large_sell_usd=EXCLUDED.large_sell_usd,
              trade_count=EXCLUDED.trade_count,
              last_px=EXCLUDED.last_px,
              last_event_ms=EXCLUDED.last_event_ms
            """,
            records,
        )
    else:
        records = [
            (
                datetime.fromtimestamp(ts, UTC), symbol, exchange, "1min",
                b.buy_vol_usd, b.sell_vol_usd, b.large_buy_usd, b.large_sell_usd, b.trade_count,
            )
            for (symbol, exchange, ts), b in snapshots
        ]
        await conn.executemany(
            f"""
            INSERT INTO {table}(ts,symbol,exchange,interval,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT(symbol,exchange,interval,ts) DO UPDATE SET
              buy_vol_usd=EXCLUDED.buy_vol_usd,
              sell_vol_usd=EXCLUDED.sell_vol_usd,
              large_buy_usd=EXCLUDED.large_buy_usd,
              large_sell_usd=EXCLUDED.large_sell_usd,
              trade_count=EXCLUDED.trade_count
            """,
            records,
        )


async def _write_combined_realtime(
    conn: asyncpg.Connection,
    snapshots: list[tuple[tuple[str, str, int], TradeBucket]],
) -> None:
    touched = sorted({(symbol, ts) for (symbol, _, ts), _ in snapshots})
    await conn.executemany(
        """
        INSERT INTO futures_trades_realtime(ts,symbol,exchange,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count,last_px,last_event_ms)
        SELECT ts,symbol,'combined',SUM(buy_vol_usd),SUM(sell_vol_usd),SUM(large_buy_usd),SUM(large_sell_usd),SUM(trade_count)::integer,
               (array_agg(last_px ORDER BY last_event_ms DESC, exchange))[1],
               MAX(last_event_ms)
        FROM futures_trades_realtime
        WHERE symbol=$1 AND ts=$2 AND exchange IN ('binance','bybit')
        GROUP BY ts,symbol
        ON CONFLICT(symbol,exchange,ts) DO UPDATE SET
          buy_vol_usd=EXCLUDED.buy_vol_usd,
          sell_vol_usd=EXCLUDED.sell_vol_usd,
          large_buy_usd=EXCLUDED.large_buy_usd,
          large_sell_usd=EXCLUDED.large_sell_usd,
          trade_count=EXCLUDED.trade_count,
          last_px=EXCLUDED.last_px,
          last_event_ms=EXCLUDED.last_event_ms
        """,
        [(symbol, datetime.fromtimestamp(ts, UTC)) for symbol, ts in touched],
    )


async def _write_combined_minute(
    conn: asyncpg.Connection,
    snapshots: list[tuple[tuple[str, str, int], TradeBucket]],
) -> None:
    touched = sorted({(symbol, ts) for (symbol, _, ts), _ in snapshots})
    await conn.executemany(
        """
        INSERT INTO futures_trades_agg(ts,symbol,exchange,interval,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,trade_count)
        SELECT ts,symbol,'combined','1min',SUM(buy_vol_usd),SUM(sell_vol_usd),SUM(large_buy_usd),SUM(large_sell_usd),SUM(trade_count)::integer
        FROM futures_trades_agg
        WHERE symbol=$1 AND ts=$2 AND exchange IN ('binance','bybit')
        GROUP BY ts,symbol
        ON CONFLICT(symbol,exchange,interval,ts) DO UPDATE SET
          buy_vol_usd=EXCLUDED.buy_vol_usd,
          sell_vol_usd=EXCLUDED.sell_vol_usd,
          large_buy_usd=EXCLUDED.large_buy_usd,
          large_sell_usd=EXCLUDED.large_sell_usd,
          trade_count=EXCLUDED.trade_count
        """,
        [(symbol, datetime.fromtimestamp(ts, UTC)) for symbol, ts in touched],
    )


async def flush_books(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    while True:
        await asyncio.sleep(SETTINGS.SCALP_ORDERBOOK_FLUSH_SECONDS)
        rows = await BOOK_STORE.snapshot()
        if not rows:
            continue
        records = [
            (
                datetime.fromtimestamp(item.ts_ms / 1000, UTC), item.symbol, item.exchange,
                item.bid_px, item.ask_px, item.mid_px, item.spread_bps,
                item.bid_notional_l1, item.ask_notional_l1, item.bid_notional_l5, item.ask_notional_l5,
                item.bid_notional_l10, item.ask_notional_l10, item.imbalance_l1, item.imbalance_l5,
                item.imbalance_l10, item.wall_up_pct, item.wall_down_pct,
            )
            for item in rows
        ]
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, ownership):
                    await conn.executemany(
                        """
                        INSERT INTO orderbook_snapshot(
                          ts,symbol,exchange,bid_px,ask_px,mid_px,spread_bps,
                          bid_notional_l1,ask_notional_l1,bid_notional_l5,ask_notional_l5,
                          bid_notional_l10,ask_notional_l10,imbalance_l1,imbalance_l5,imbalance_l10,
                          wall_up_pct,wall_down_pct
                        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
                        ON CONFLICT(symbol,exchange,ts) DO NOTHING
                        """,
                        records,
                    )
                    await _write_combined_books(conn, rows)
                    await _write_ladders(conn)
                    LAST_FLUSH["books"] = time.monotonic()
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("orderbook_flush_failed")


async def _write_ladders(conn: asyncpg.Connection) -> None:
    """Estado ACTUAL del libro por venue: una fila por (symbol,exchange), sobrescrita.

    Sin historial a proposito. `orderbook_snapshot` ya guarda la serie de agregados y pesa
    61 MB por 6 h; guardar 50 niveles cada 2 s multiplicaria eso para responder una pregunta
    que solo se hace sobre el ahora ("cuanto me cuesta ejecutar este tamanio"). La
    persistencia de paredes es P3 y necesitaria su propio diseno de muestreo.
    """
    ladders = await BOOK_STORE.ladders()
    if not ladders:
        return
    await conn.executemany(
        """
        INSERT INTO orderbook_depth(symbol,exchange,ts,bids,asks,levels)
        VALUES($1,$2,$3,$4,$5,$6)
        ON CONFLICT(symbol,exchange) DO UPDATE SET
          ts=EXCLUDED.ts,bids=EXCLUDED.bids,asks=EXCLUDED.asks,levels=EXCLUDED.levels
        """,
        [
            (
                symbol,
                exchange,
                datetime.fromtimestamp(ts_ms / 1000, UTC),
                json.dumps(bids),
                json.dumps(asks),
                min(len(bids), len(asks)),
            )
            for symbol, exchange, ts_ms, bids, asks in ladders
        ],
    )


async def _write_combined_books(conn: asyncpg.Connection, rows: list[BookStats]) -> None:
    touched = sorted({item.symbol for item in rows})
    for symbol in touched:
        await conn.execute(
            """
            WITH latest AS (
              SELECT DISTINCT ON (exchange) * FROM orderbook_snapshot
              WHERE symbol=$1 AND exchange IN ('binance','bybit') AND ts >= now()-interval '10 seconds'
              ORDER BY exchange,ts DESC
            ), totals AS (
              SELECT MIN(ts) AS ts,$1::text AS symbol,'combined' AS exchange,
                SUM(bid_notional_l1) AS bid_notional_l1,SUM(ask_notional_l1) AS ask_notional_l1,
                SUM(bid_notional_l5) AS bid_notional_l5,SUM(ask_notional_l5) AS ask_notional_l5,
                SUM(bid_notional_l10) AS bid_notional_l10,SUM(ask_notional_l10) AS ask_notional_l10,
                CASE WHEN SUM(bid_notional_l1+ask_notional_l1)>0 THEN SUM(bid_notional_l1)/SUM(bid_notional_l1+ask_notional_l1) END AS imbalance_l1,
                CASE WHEN SUM(bid_notional_l5+ask_notional_l5)>0 THEN SUM(bid_notional_l5)/SUM(bid_notional_l5+ask_notional_l5) END AS imbalance_l5,
                CASE WHEN SUM(bid_notional_l10+ask_notional_l10)>0 THEN SUM(bid_notional_l10)/SUM(bid_notional_l10+ask_notional_l10) END AS imbalance_l10,
                MIN(wall_up_pct) AS wall_up_pct,MIN(wall_down_pct) AS wall_down_pct
              FROM latest HAVING COUNT(*) > 0
            ), best_venue AS (
              SELECT bid_px,ask_px,mid_px,spread_bps
              FROM latest
              WHERE bid_px IS NOT NULL AND ask_px IS NOT NULL AND ask_px >= bid_px
              ORDER BY spread_bps NULLS LAST, ts DESC
              LIMIT 1
            ), agg AS (
              SELECT totals.ts,totals.symbol,totals.exchange,
                best_venue.bid_px,best_venue.ask_px,best_venue.mid_px,best_venue.spread_bps,
                totals.bid_notional_l1,totals.ask_notional_l1,totals.bid_notional_l5,totals.ask_notional_l5,
                totals.bid_notional_l10,totals.ask_notional_l10,totals.imbalance_l1,totals.imbalance_l5,totals.imbalance_l10,
                totals.wall_up_pct,totals.wall_down_pct
              FROM totals LEFT JOIN best_venue ON true
            )
            INSERT INTO orderbook_snapshot(
              ts,symbol,exchange,bid_px,ask_px,mid_px,spread_bps,bid_notional_l1,ask_notional_l1,
              bid_notional_l5,ask_notional_l5,bid_notional_l10,ask_notional_l10,imbalance_l1,
              imbalance_l5,imbalance_l10,wall_up_pct,wall_down_pct
            ) SELECT * FROM agg
            ON CONFLICT(symbol,exchange,ts) DO NOTHING
            """,
            symbol,
        )


async def flush_liquidations(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    buffer: list[tuple[datetime, str, str, str, float, float, float, str]] = []
    while True:
        try:
            item = await asyncio.wait_for(LIQ_QUEUE.get(), timeout=2.0)
            buffer.append(item)
            while len(buffer) < 100:
                with contextlib.suppress(asyncio.QueueEmpty):
                    buffer.append(LIQ_QUEUE.get_nowait())
                if LIQ_QUEUE.empty():
                    break
        except TimeoutError:
            pass
        if not buffer:
            continue
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, ownership):
                    await conn.executemany(
                        LIQUIDATION_INSERT_SQL,
                        buffer,
                    )
                    LAST_FLUSH["liquidations"] = time.monotonic()
            buffer.clear()
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("liquidation_flush_failed retained=%d", len(buffer))
            await asyncio.sleep(2)


async def binance_loop() -> None:
    global BINANCE_BOOK_RECONNECT_TOTAL
    pairs = [FUTURES_PAIR_MAP[s].lower() for s in ACTIVE_SYMBOLS]
    streams: list[str] = []
    for pair in pairs:
        # forceOrder queda suscrito aqui A PROPOSITO aunque binance_market_loop() ya
        # lo cubre en el endpoint /market: si el legacy vuelve a emitir no perdemos
        # liquidaciones, y si emiten los dos el INSERT deduplica por (exchange,event_id).
        streams.extend([f"{pair}@trade", f"{pair}@depth10@100ms", f"{pair}@forceOrder"])
    url = BINANCE_STREAM_BASE + "/".join(streams)
    backoff = WS_RECONNECT_INITIAL_SECONDS
    while True:
        started = time.monotonic()
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                LOGGER.info("binance_futures_connected streams=%d", len(streams))
                async for raw in ws:
                    if time.monotonic() - started > SETTINGS.BINANCE_BOOK_FORCE_RECONNECT_SECONDS:
                        BINANCE_BOOK_RECONNECT_TOTAL += 1
                        await BOOK_STORE.drop_exchange("binance")
                        raise BookResyncRequired("scheduled Binance book reconnect/resync")
                    backoff = WS_RECONNECT_INITIAL_SECONDS
                    await handle_binance(json.loads(raw))
        except asyncio.CancelledError:
            raise
        except BookResyncRequired as exc:
            LOGGER.warning("binance_futures_resync reason=%s retry=%.1fs", exc, backoff)
        except (ConnectionClosed, TimeoutError, OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("binance_futures_disconnected error=%s retry=%.1fs", type(exc).__name__, backoff)
        except Exception:
            LOGGER.exception("binance_futures_ws_error retry=%.1fs", backoff)
        await BOOK_STORE.drop_exchange("binance")
        mark_exchange_disconnected("binance")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, WS_RECONNECT_MAX_SECONDS)


async def handle_binance(message: dict[str, Any]) -> None:
    data = message.get("data", {})
    stream = str(message.get("stream", ""))
    event_type = data.get("e")
    pair = str(data.get("s") or stream.split("@")[0]).upper()
    symbol = PAIR_SYMBOL_MAP.get(pair)
    if not symbol or symbol not in ACTIVE_SYMBOL_SET:
        return
    if event_type in {"aggTrade", "trade"}:
        parsed = valid_trade(data.get("p"), data.get("q"), data.get("T") or data.get("E"))
        if parsed is None:
            return
        price, qty, event_ms = parsed
        # Binance m=True means buyer is maker, so taker aggressor is sell.
        is_buy = not bool(data.get("m"))
        await TRADE_STORE.add(symbol, "binance", event_ms, price, qty, is_buy)
        LAST_TRADE_EVENT[(symbol, "binance")] = time.monotonic()
    elif "depth" in stream:
        global BINANCE_BOOK_STALE_TOTAL
        bids = data.get("b") or []
        asks = data.get("a") or []
        ts_ms = int(data.get("E") or now_ms())
        lag_s = (now_ms() - ts_ms) / 1000
        if lag_s > SETTINGS.BINANCE_BOOK_MAX_EVENT_LAG_SECONDS:
            BINANCE_BOOK_STALE_TOTAL += 1
            LOGGER.warning("binance_orderbook_late_event symbol=%s lag_seconds=%.3f", symbol, lag_s)
            await BOOK_STORE.drop_exchange("binance")
            raise BookResyncRequired(f"stale Binance orderbook event for {symbol}")
        await BOOK_STORE.set_snapshot(symbol, "binance", bids, asks, ts_ms)
    elif event_type == "forceOrder":
        order = data.get("o") or {}
        parsed = valid_trade(order.get("p") or order.get("ap"), order.get("q"), order.get("T") or data.get("E"))
        if parsed is None:
            return
        price, qty, event_ms = parsed
        order_side = str(order.get("S", "")).upper()
        side = "long" if order_side == "SELL" else "short"
        event_id = f"{symbol}:{event_ms}:{order_side}:{price}:{qty}"
        await safe_liq_put((datetime.fromtimestamp(event_ms / 1000, UTC), symbol, "binance", side, price * qty, price, qty, event_id))


async def binance_market_loop(
    pool: asyncpg.Pool | None = None,
    ownership: ServiceOwnership | None = None,
) -> None:
    """Liquidaciones Binance. Las URLs legacy se decomisaron el 2026-04-23: forceOrder
    solo emite en el endpoint /market nuevo; trade/depth siguen en la conexion legacy."""
    pairs = [FUTURES_PAIR_MAP[s].lower() for s in ACTIVE_SYMBOLS]
    url = BINANCE_MARKET_STREAM_BASE + "/".join(f"{p}@forceOrder" for p in pairs)
    backoff = WS_RECONNECT_INITIAL_SECONDS
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                LIQ_FEED_CONNECTED["binance"] = True
                await persist_liquidation_feed_state(
                    pool,
                    "binance",
                    "ok",
                    "forceOrder connection open",
                    ownership=ownership,
                )
                LOGGER.info("binance_market_connected streams=%d", len(pairs))
                async for raw in ws:
                    backoff = WS_RECONNECT_INITIAL_SECONDS
                    await handle_binance(json.loads(raw))
        except asyncio.CancelledError:
            LIQ_FEED_CONNECTED["binance"] = False
            await persist_liquidation_feed_state(
                pool,
                "binance",
                "degraded",
                "forceOrder connection closed",
                ownership=ownership,
            )
            raise
        except ServiceOwnershipLost:
            raise
        except (ConnectionClosed, TimeoutError, OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("binance_market_disconnected error=%s retry=%.1fs", type(exc).__name__, backoff)
        except Exception:
            LOGGER.exception("binance_market_ws_error retry=%.1fs", backoff)
        LIQ_FEED_CONNECTED["binance"] = False
        await persist_liquidation_feed_state(
            pool,
            "binance",
            "degraded",
            "forceOrder connection closed",
            ownership=ownership,
        )
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, WS_RECONNECT_MAX_SECONDS)


async def bybit_loop(
    pool: asyncpg.Pool | None = None,
    ownership: ServiceOwnership | None = None,
) -> None:
    pairs = [FUTURES_PAIR_MAP[s] for s in ACTIVE_SYMBOLS]
    args = []
    for pair in pairs:
        args.extend([f"publicTrade.{pair}", f"orderbook.50.{pair}", f"allLiquidation.{pair}"])
    backoff = WS_RECONNECT_INITIAL_SECONDS
    while True:
        try:
            async with websockets.connect(BYBIT_LINEAR_WS, ping_interval=20, ping_timeout=20, max_size=2_000_000) as ws:
                await ws.send(json.dumps({"op": "subscribe", "args": args}))
                LOGGER.info("bybit_linear_connected topics=%d", len(args))
                async for raw in ws:
                    backoff = WS_RECONNECT_INITIAL_SECONDS
                    message = json.loads(raw)
                    if message.get("op") == "subscribe":
                        if message.get("success") is True:
                            LIQ_FEED_CONNECTED["bybit"] = True
                            await persist_liquidation_feed_state(
                                pool,
                                "bybit",
                                "ok",
                                "allLiquidation subscription confirmed",
                                ownership=ownership,
                            )
                        else:
                            LIQ_FEED_CONNECTED["bybit"] = False
                            await persist_liquidation_feed_state(
                                pool,
                                "bybit",
                                "error",
                                f"subscription rejected: {message.get('ret_msg')!s}"[:500],
                                ownership=ownership,
                            )
                        continue
                    await handle_bybit(message)
        except asyncio.CancelledError:
            LIQ_FEED_CONNECTED["bybit"] = False
            await persist_liquidation_feed_state(
                pool,
                "bybit",
                "degraded",
                "allLiquidation connection closed",
                ownership=ownership,
            )
            raise
        except ServiceOwnershipLost:
            raise
        except BookResyncRequired as exc:
            LOGGER.warning("bybit_linear_resync reason=%s retry=%.1fs", exc, backoff)
        except (ConnectionClosed, TimeoutError, OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("bybit_linear_disconnected error=%s retry=%.1fs", type(exc).__name__, backoff)
        except Exception:
            LOGGER.exception("bybit_linear_ws_error retry=%.1fs", backoff)
        LIQ_FEED_CONNECTED["bybit"] = False
        await persist_liquidation_feed_state(
            pool,
            "bybit",
            "degraded",
            "allLiquidation connection closed",
            ownership=ownership,
        )
        await BOOK_STORE.drop_exchange("bybit")
        mark_exchange_disconnected("bybit")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, WS_RECONNECT_MAX_SECONDS)


def parse_sequence(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None


def bybit_liquidated_position_side(raw_side: object) -> str | None:
    side = str(raw_side or "").strip().upper()
    if side == "BUY":
        return "long"
    if side == "SELL":
        return "short"
    return None


async def handle_bybit(message: dict[str, Any]) -> None:
    topic = str(message.get("topic", ""))
    if not topic:
        return
    parts = topic.split(".")
    pair = parts[-1].upper()
    symbol = PAIR_SYMBOL_MAP.get(pair)
    if not symbol or symbol not in ACTIVE_SYMBOL_SET:
        return
    data = message.get("data") or []
    if topic.startswith("publicTrade"):
        trades = data if isinstance(data, list) else [data]
        for trade in trades:
            parsed = valid_trade(trade.get("p"), trade.get("v"), trade.get("T") or message.get("ts"))
            if parsed is None:
                continue
            price, qty, event_ms = parsed
            is_buy = str(trade.get("S", "")).lower() == "buy"
            await TRADE_STORE.add(symbol, "bybit", event_ms, price, qty, is_buy)
            LAST_TRADE_EVENT[(symbol, "bybit")] = time.monotonic()
    elif topic.startswith("orderbook"):
        if not isinstance(data, dict):
            return
        ts_ms = int(message.get("ts") or data.get("ts") or now_ms())
        bids = data.get("b") or []
        asks = data.get("a") or []
        update_id = parse_sequence(data.get("u"))
        cross_seq = parse_sequence(data.get("seq"))
        if message.get("type") == "snapshot" or update_id == 1:
            if update_id is None:
                await BOOK_STORE.drop_exchange("bybit")
                raise BookResyncRequired(f"Bybit snapshot missing update ID for {symbol}")
            await BOOK_STORE.set_snapshot(
                symbol,
                "bybit",
                bids,
                asks,
                ts_ms,
                update_id=update_id,
                cross_seq=cross_seq,
            )
        else:
            if not await BOOK_STORE.apply_delta(
                symbol,
                "bybit",
                bids,
                asks,
                ts_ms,
                update_id=update_id,
                cross_seq=cross_seq,
            ):
                LOGGER.warning(
                    "bybit_orderbook_update_gap symbol=%s update_id=%s cross_seq=%s",
                    symbol,
                    update_id,
                    cross_seq,
                )
                raise BookResyncRequired(f"Bybit orderbook update ID gap for {symbol}")
    elif topic.startswith("allLiquidation"):
        liqs = data if isinstance(data, list) else [data]
        for liq in liqs:
            parsed = valid_trade(liq.get("p"), liq.get("v") or liq.get("qty"), liq.get("T") or message.get("ts"))
            if parsed is None:
                continue
            price, qty, event_ms = parsed
            side = bybit_liquidated_position_side(liq.get("S"))
            if side is None:
                LOGGER.warning(
                    "bybit_liquidation_invalid_side symbol=%s raw_side=%r",
                    symbol,
                    liq.get("S"),
                )
                continue
            raw_side = str(liq.get("S", "")).upper()
            event_id = str(liq.get("id") or f"{symbol}:{event_ms}:{raw_side}:{price}:{qty}")
            await safe_liq_put((datetime.fromtimestamp(event_ms / 1000, UTC), symbol, "bybit", side, price * qty, price, qty, event_id))


async def safe_liq_put(item: tuple[datetime, str, str, str, float, float, float, str]) -> None:
    global LIQ_DROPPED
    try:
        LIQ_QUEUE.put_nowait(item)
    except asyncio.QueueFull:
        LIQ_DROPPED += 1
        loss_at = datetime.now(UTC)
        LIQ_LOSS_PENDING[item[2]] = loss_at
        event_at = item[0] if isinstance(item[0], datetime) else loss_at
        if event_at.tzinfo is None or event_at.utcoffset() is None:
            event_at = event_at.replace(tzinfo=UTC)
        LIQ_GAP_PENDING.add((item[1], item[2], event_at.astimezone(UTC)))
        if LIQ_DROPPED == 1 or LIQ_DROPPED % 100 == 0:
            LOGGER.warning("liquidation_queue_overflow dropped_total=%d queue_size=%d", LIQ_DROPPED, LIQ_QUEUE.qsize())




async def persist_scalp_signals(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    while True:
        await asyncio.sleep(SETTINGS.SCALP_SIGNAL_INTERVAL_SECONDS)
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, ownership):
                    records: list[tuple[object, ...]] = []
                    for symbol in ACTIVE_SYMBOLS:
                        ctx = await scalp_context(conn, symbol)
                        summary = compute_scalp_summary(ctx)
                        records.append(
                            (
                                datetime.now(UTC),
                                symbol,
                                float(summary["long_score"]),
                                float(summary["short_score"]),
                                str(summary["state"]),
                                str(summary["confidence"]),
                                str(summary["reason"]),
                                summary.get("fut_delta_1m"),
                                summary.get("fut_delta_3m"),
                                summary.get("spot_delta_3m"),
                                summary.get("diff_3m"),
                                summary.get("spot_fut_divergence_norm"),
                                summary.get("book_status"),
                                summary.get("book_lag_seconds"),
                                summary.get("basis_bps"),
                                summary.get("absorption"),
                            )
                        )
                    await conn.executemany(
                        """
                        INSERT INTO scalp_signal_snapshot(
                          ts,symbol,long_score,short_score,state,confidence,reason,
                          fut_delta_1m,fut_delta_3m,spot_delta_3m,diff_3m,
                          spot_fut_divergence_norm,book_status,book_lag_seconds,basis_bps,absorption
                        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
                        ON CONFLICT(symbol,ts) DO NOTHING
                        """,
                        records,
                    )
                    LAST_FLUSH["signals"] = time.monotonic()
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("scalp_signal_snapshot_failed")


async def monitor(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    while True:
        await asyncio.sleep(30)
        now = time.monotonic()
        feed_lags = {key: (int(now - value) if value else -1) for key, value in LAST_TRADE_EVENT.items()}
        flush_lags = {k: (int(now - v) if v else -1) for k, v in LAST_FLUSH.items()}
        book_lags = await BOOK_STORE.symbol_exchange_lags()
        expected = set(LAST_TRADE_EVENT)
        rt_buckets, minute_buckets = await TRADE_STORE.size()
        detail = ";".join([
            ",".join(
                f"trade_{exchange}_{symbol.split('USDT')[0]}:{lag}s"
                for (symbol, exchange), lag in sorted(feed_lags.items())
            ),
            ",".join(f"flush_{k}:{v}s" for k, v in flush_lags.items()),
            ",".join(
                f"book_{exchange}_{symbol.split('USDT')[0]}:{lag}s"
                for (symbol, exchange), lag in sorted(book_lags.items())
            ),
            f"liq_queue:{LIQ_QUEUE.qsize()}",
            f"liq_dropped:{LIQ_DROPPED}",
            f"trade_buckets_rt:{rt_buckets}",
            f"trade_buckets_minute:{minute_buckets}",
            f"trade_dropped_buckets:{TRADESTORE_DROPPED_BUCKETS}",
            f"trade_dropped_trades:{TRADESTORE_DROPPED_TRADES}",
            f"binance_book_stale:{BINANCE_BOOK_STALE_TOTAL}",
            f"binance_reconnects:{BINANCE_BOOK_RECONNECT_TOTAL}",
        ])[:500]
        feed_ok = all_expected_fresh(feed_lags, expected, 90)
        flush_ok = (
            0 <= flush_lags.get("trades", -1) < 30
            and 0 <= flush_lags.get("books", -1) < 30
            and 0 <= flush_lags.get("signals", -1) < max(90, SETTINGS.SCALP_SIGNAL_INTERVAL_SECONDS * 4)
        )
        queue_ok = LIQ_QUEUE.qsize() < int(LIQ_QUEUE.maxsize * 0.8)
        book_ok = all_expected_fresh(book_lags, expected, SETTINGS.BINANCE_BOOK_STALE_SECONDS)
        store_ok = rt_buckets <= SETTINGS.TRADESTORE_MAX_BUCKETS_PER_KEY * len(ACTIVE_SYMBOLS) * 3
        status = (
            "ok"
            if not ACTIVE_SYMBOLS or (feed_ok and flush_ok and queue_ok and book_ok and store_ok)
            else "degraded"
        )
        try:
            async with pool.acquire() as conn:
                await heartbeat_shard(
                    conn,
                    "scalp",
                    SETTINGS.COLLECTOR_SHARD_INDEX,
                    SETTINGS.COLLECTOR_SHARD_COUNT,
                    status=status,
                    detail=(f"symbols={','.join(ACTIVE_SYMBOLS) or 'none'};{detail}")[:500],
                    ownership=ownership,
                )
                if ACTIVE_SYMBOLS:
                    await persist_liquidation_health_snapshot(conn, ownership)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("scalp_heartbeat_failed")


def owns_global_cleanup(shard_index: int) -> bool:
    return shard_index == 0


async def cleanup_expired_rows(conn: asyncpg.Connection) -> None:
    await apply_temporal_retention(
        conn,
        "futures_trades_realtime",
        SETTINGS.SCALP_TRADE_RETENTION_HOURS,
    )
    # futures_trades_agg debe cubrir una sesion NYSE completa (24h) para que
    # daily_agg pueda calcular el CVD de futuros de Binance+Bybit; ver
    # SCALP_MINUTE_RETENTION_HOURS.
    await conn.execute(
        "DELETE FROM futures_trades_agg "
        "WHERE ts < now()-($1::int * interval '1 hour')",
        SETTINGS.SCALP_MINUTE_RETENTION_HOURS,
    )
    await apply_temporal_retention(
        conn,
        "orderbook_snapshot",
        SETTINGS.SCALP_ORDERBOOK_RETENTION_HOURS,
    )
    await apply_temporal_retention(
        conn,
        "liquidations_realtime",
        SETTINGS.SCALP_TRADE_RETENTION_HOURS,
    )
    await apply_temporal_retention(
        conn,
        "scalp_signal_snapshot",
        SETTINGS.SCALP_SIGNAL_RETENTION_HOURS,
    )


async def cleanup(
    pool: asyncpg.Pool,
    ownership: ServiceOwnership | None = None,
) -> None:
    while True:
        await asyncio.sleep(3600)
        try:
            async with pool.acquire() as conn:
                async with fenced_transaction(conn, ownership):
                    await cleanup_expired_rows(conn)
        except ServiceOwnershipLost:
            raise
        except Exception:
            LOGGER.exception("scalp_cleanup_failed")


async def main() -> None:
    service_lock = await acquire_service_lock(
        SETTINGS,
        "scalp",
        SETTINGS.COLLECTOR_SHARD_INDEX,
        SETTINGS.COLLECTOR_SHARD_COUNT,
    )
    pool = await create_pool(
        SETTINGS,
        application_name=(
            f"coinalyze-scalp-{SETTINGS.COLLECTOR_SHARD_INDEX}-"
            f"{SETTINGS.COLLECTOR_SHARD_COUNT}"
        ),
        ownership=service_lock,
    )
    tasks = [
        asyncio.create_task(
            monitor_service_lock(
                service_lock,
                "scalp",
                SETTINGS.COLLECTOR_SHARD_INDEX,
                SETTINGS.COLLECTOR_SHARD_COUNT,
            ),
            name="service-lock",
        ),
        asyncio.create_task(monitor(pool, service_lock)),
    ]
    if owns_global_cleanup(SETTINGS.COLLECTOR_SHARD_INDEX):
        tasks.append(asyncio.create_task(cleanup(pool, service_lock)))
    if ACTIVE_SYMBOLS:
        async with pool.acquire() as conn:
            await reset_liquidation_feed_health(conn, service_lock)
        tasks.extend(
            (
                asyncio.create_task(binance_loop()),
                asyncio.create_task(binance_market_loop(pool, service_lock)),
                asyncio.create_task(bybit_loop(pool, service_lock)),
                asyncio.create_task(flush_trades(pool, service_lock)),
                asyncio.create_task(flush_books(pool, service_lock)),
                asyncio.create_task(flush_liquidations(pool, service_lock)),
                asyncio.create_task(persist_scalp_signals(pool, service_lock)),
            )
        )
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await pool.close()
        await service_lock.close()


if __name__ == "__main__":
    asyncio.run(main())
