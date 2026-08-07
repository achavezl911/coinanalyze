from __future__ import annotations

import asyncio
import time

import pytest

import app.scalp_collector as scalp
from app.scalp_collector import (
    BookResyncRequired,
    BookStore,
    TradeBucket,
    TradeStore,
    all_expected_fresh,
    handle_binance,
    mark_exchange_disconnected,
)


@pytest.mark.asyncio
async def test_tradestore_prunes_old_buckets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scalp.SETTINGS, "TRADESTORE_MAX_BUCKET_MINUTES", 5)
    monkeypatch.setattr(scalp, "TRADESTORE_DROPPED_BUCKETS", 0)
    monkeypatch.setattr(scalp, "TRADESTORE_DROPPED_TRADES", 0)
    store = TradeStore()
    old_ts = int(time.time()) - 3600
    store.minute[("BTCUSDT_PERP.A", "binance", old_ts)] = TradeBucket(trade_count=7)
    await store.prune()
    assert store.minute == {}
    assert scalp.TRADESTORE_DROPPED_BUCKETS == 1
    assert scalp.TRADESTORE_DROPPED_TRADES == 7


@pytest.mark.asyncio
async def test_tradestore_prunes_overflow_per_symbol_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scalp.SETTINGS, "TRADESTORE_MAX_BUCKET_MINUTES", 120)
    monkeypatch.setattr(scalp.SETTINGS, "TRADESTORE_MAX_BUCKETS_PER_KEY", 2)
    monkeypatch.setattr(scalp, "TRADESTORE_DROPPED_BUCKETS", 0)
    store = TradeStore()
    now_ts = int(time.time())
    for offset in range(4):
        store.minute[("BTCUSDT_PERP.A", "binance", now_ts + offset)] = TradeBucket(trade_count=1)
    await store.prune()
    assert len(store.minute) == 2
    assert scalp.TRADESTORE_DROPPED_BUCKETS == 2


@pytest.mark.asyncio
async def test_bookstore_lags_are_per_symbol_and_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scalp, "now_ms", lambda: 20_000)
    books = BookStore()
    await books.set_snapshot("BTCUSDT_PERP.A", "binance", [["100", "1"]], [["101", "1"]], 5_000)
    assert (await books.symbol_exchange_lags())[("BTCUSDT_PERP.A", "binance")] == 15


def test_health_requires_every_symbol_and_venue_to_be_fresh() -> None:
    expected = {
        ("BTCUSDT_PERP.A", "binance"),
        ("BTCUSDT_PERP.A", "bybit"),
    }
    assert all_expected_fresh({("BTCUSDT_PERP.A", "binance"): 1}, expected, 30) is False
    assert all_expected_fresh({key: 1 for key in expected}, expected, 30) is True


@pytest.mark.asyncio
async def test_binance_late_orderbook_event_forces_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scalp.SETTINGS, "BINANCE_BOOK_MAX_EVENT_LAG_SECONDS", 2)
    monkeypatch.setattr(scalp, "BINANCE_BOOK_STALE_TOTAL", 0)
    monkeypatch.setattr(scalp, "now_ms", lambda: 10_000)
    monkeypatch.setattr(scalp, "BOOK_STORE", BookStore())
    message = {
        "stream": "btcusdt@depth10@100ms",
        "data": {"s": "BTCUSDT", "E": 1_000, "b": [["100", "1"]], "a": [["101", "1"]]},
    }
    with pytest.raises(BookResyncRequired):
        await handle_binance(message)
    assert scalp.BINANCE_BOOK_STALE_TOTAL == 1


def test_disconnect_immediately_invalidates_only_that_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    timestamps = {
        ("BTCUSDT_PERP.A", "binance"): 10.0,
        ("BTCUSDT_PERP.A", "bybit"): 20.0,
    }
    monkeypatch.setattr(scalp, "LAST_TRADE_EVENT", timestamps)

    mark_exchange_disconnected("bybit")

    assert timestamps[("BTCUSDT_PERP.A", "binance")] == 10.0
    assert timestamps[("BTCUSDT_PERP.A", "bybit")] == 0.0


@pytest.mark.asyncio
async def test_bybit_disconnect_drops_book_and_uses_backoff(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    books = BookStore()
    await books.set_snapshot("BTCUSDT_PERP.A", "bybit", [["100", "1"]], [["101", "1"]], 1_000)
    timestamps = {("BTCUSDT_PERP.A", "bybit"): 10.0}
    delays: list[float] = []

    def fail_connect(*_args, **_kwargs):
        raise OSError("network unavailable")

    async def stop_after_delay(delay: float) -> None:
        delays.append(delay)
        raise asyncio.CancelledError

    monkeypatch.setattr(scalp, "BOOK_STORE", books)
    monkeypatch.setattr(scalp, "LAST_TRADE_EVENT", timestamps)
    monkeypatch.setattr(scalp.websockets, "connect", fail_connect)
    monkeypatch.setattr(scalp.asyncio, "sleep", stop_after_delay)

    with pytest.raises(asyncio.CancelledError):
        await scalp.bybit_loop()

    assert await books.symbol_exchange_lags() == {}
    assert timestamps[("BTCUSDT_PERP.A", "bybit")] == 0.0
    assert delays == [scalp.WS_RECONNECT_INITIAL_SECONDS]
    assert "bybit_linear_disconnected" in caplog.text


@pytest.mark.asyncio
async def test_binance_trade_event_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    trade_store = TradeStore()
    event_ms = int(time.time() * 1000)
    monkeypatch.setattr(scalp, "TRADE_STORE", trade_store)
    message = {
        "stream": "btcusdt@trade",
        "data": {"e": "trade", "s": "BTCUSDT", "p": "100", "q": "2", "T": event_ms, "m": False},
    }

    await handle_binance(message)

    assert len(trade_store.minute) == 1
    (symbol, exchange, _), bucket = next(iter(trade_store.minute.items()))
    assert symbol == "BTCUSDT_PERP.A"
    assert exchange == "binance"
    assert bucket.buy_vol_usd == 200
    assert bucket.sell_vol_usd == 0
