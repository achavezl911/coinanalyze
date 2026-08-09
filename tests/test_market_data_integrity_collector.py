from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import pytest

import app.scalp_collector as scalp
from app.scalp_collector import (
    BookResyncRequired,
    BookStore,
    LocalBook,
    bybit_liquidated_position_side,
    handle_binance,
    handle_bybit,
    persist_liquidation_health_snapshot,
    reset_liquidation_feed_health,
)

SYMBOL = "BTCUSDT_PERP.A"
EVENT_MS = 1_786_056_654_685


def test_bybit_liquidated_position_side_uses_position_semantics() -> None:
    assert bybit_liquidated_position_side("Buy") == "long"
    assert bybit_liquidated_position_side("Sell") == "short"
    assert bybit_liquidated_position_side("invalid") is None
    assert bybit_liquidated_position_side(None) is None


@pytest.mark.asyncio
async def test_handle_bybit_persists_liquidated_position_side(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
    monkeypatch.setattr(scalp, "now_ms", lambda: EVENT_MS)

    await handle_bybit(
        {
            "topic": "allLiquidation.BTCUSDT",
            "ts": EVENT_MS,
            "data": [
                {"id": "buy", "T": EVENT_MS, "S": "Buy", "p": "100", "v": "2"},
                {"id": "sell", "T": EVENT_MS, "S": "Sell", "p": "101", "v": "3"},
            ],
        }
    )

    rows = [queue.get_nowait(), queue.get_nowait()]
    assert [(row[2], row[3], row[7]) for row in rows] == [
        ("bybit", "long", "buy"),
        ("bybit", "short", "sell"),
    ]


@pytest.mark.asyncio
async def test_binance_force_order_semantics_remain_order_side_based(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
    monkeypatch.setattr(scalp, "now_ms", lambda: EVENT_MS)

    for order_side in ("SELL", "BUY"):
        await handle_binance(
            {
                "stream": "btcusdt@forceOrder",
                "data": {
                    "e": "forceOrder",
                    "E": EVENT_MS,
                    "o": {"s": "BTCUSDT", "S": order_side, "p": "100", "q": "1"},
                },
            }
        )

    rows = [queue.get_nowait(), queue.get_nowait()]
    assert [(row[2], row[3]) for row in rows] == [
        ("binance", "long"),
        ("binance", "short"),
    ]


def test_local_book_tracks_update_id_separately_from_cross_sequence() -> None:
    book = LocalBook(SYMBOL, "bybit")
    book.reset([["100", "1"]], [["101", "1"]], 1_000, update_id=10, cross_seq=500)

    assert book.update_id == 10
    assert book.cross_seq == 500
    assert book.apply_delta(
        [["100", "2"]],
        [],
        1_001,
        update_id=11,
        cross_seq=900,
    ) is True
    assert book.update_id == 11
    assert book.cross_seq == 900


@pytest.mark.parametrize("update_id", [None, 10, 9, 12])
def test_local_book_rejects_missing_duplicate_prior_and_skipped_updates(
    update_id: int | None,
) -> None:
    book = LocalBook(SYMBOL, "bybit")
    book.reset([["100", "1"]], [["101", "1"]], 1_000, update_id=10, cross_seq=500)

    assert book.apply_delta([["100", "2"]], [], 1_001, update_id=update_id) is False
    assert book.bids[100.0] == 1.0


@pytest.mark.asyncio
async def test_bybit_snapshot_delta_and_u_one_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    books = BookStore()
    monkeypatch.setattr(scalp, "BOOK_STORE", books)

    await handle_bybit(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1_000,
            "data": {"u": 10, "seq": 100, "b": [["100", "1"]], "a": [["101", "1"]]},
        }
    )
    await handle_bybit(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1_001,
            "data": {"u": 11, "seq": 101, "b": [["100", "2"]], "a": []},
        }
    )
    book = books.books[(SYMBOL, "bybit")]
    assert book.bids[100.0] == 2.0
    assert book.update_id == 11

    await handle_bybit(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1_002,
            "data": {"u": 1, "seq": 1, "b": [["99", "3"]], "a": [["102", "4"]]},
        }
    )
    restarted = books.books[(SYMBOL, "bybit")]
    assert restarted.update_id == 1
    assert restarted.bids == {99.0: 3.0}
    assert restarted.asks == {102.0: 4.0}


@pytest.mark.asyncio
async def test_bybit_gap_removes_book_until_a_new_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    books = BookStore()
    monkeypatch.setattr(scalp, "BOOK_STORE", books)
    snapshot = {
        "topic": "orderbook.50.BTCUSDT",
        "type": "snapshot",
        "ts": 1_000,
        "data": {"u": 10, "seq": 100, "b": [["100", "1"]], "a": [["101", "1"]]},
    }
    await handle_bybit(snapshot)

    with pytest.raises(BookResyncRequired):
        await handle_bybit(
            {
                "topic": "orderbook.50.BTCUSDT",
                "type": "delta",
                "ts": 1_001,
                "data": {"u": 12, "seq": 102, "b": [["100", "2"]], "a": []},
            }
        )
    assert (SYMBOL, "bybit") not in books.books

    with pytest.raises(BookResyncRequired):
        await handle_bybit(
            {
                "topic": "orderbook.50.BTCUSDT",
                "type": "delta",
                "ts": 1_002,
                "data": {"u": 13, "seq": 103, "b": [["100", "3"]], "a": []},
            }
        )
    assert await books.snapshot() == []

    await handle_bybit(snapshot)
    assert len(await books.snapshot()) == 1


class _FakeBybitSocket:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = iter(messages)

    async def send(self, _payload: str) -> None:
        return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        try:
            return json.dumps(next(self.messages))
        except StopIteration:
            raise asyncio.CancelledError from None


class _FakeConnect:
    def __init__(self, socket: _FakeBybitSocket) -> None:
        self.socket = socket

    async def __aenter__(self) -> _FakeBybitSocket:
        return self.socket

    async def __aexit__(self, *_args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_bybit_health_waits_for_positive_subscription_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persisted: list[tuple[str, str]] = []

    async def record_state(_pool, exchange: str, status: str, *_args, **_kwargs) -> bool:
        persisted.append((exchange, status))
        return True

    socket = _FakeBybitSocket([{"op": "subscribe", "success": True, "ret_msg": ""}])
    monkeypatch.setattr(scalp.websockets, "connect", lambda *_a, **_k: _FakeConnect(socket))
    monkeypatch.setattr(scalp, "persist_liquidation_feed_state", record_state)

    with pytest.raises(asyncio.CancelledError):
        await scalp.bybit_loop(object())  # type: ignore[arg-type]

    assert persisted == [("bybit", "ok"), ("bybit", "degraded")]


@pytest.mark.asyncio
async def test_monitor_persists_queue_loss_then_restores_connected_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, bool]] = []
    loss_at = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(scalp, "LIQ_FEED_CONNECTED", {"binance": True, "bybit": False})
    monkeypatch.setattr(scalp, "LIQ_LOSS_PENDING", {"binance": loss_at})

    async def degraded(_conn, _feed, exchange, *_args, data_loss=False):
        calls.append((exchange, "degraded", data_loss))

    async def connected(_conn, _feed, exchange, *_args):
        calls.append((exchange, "ok", False))

    monkeypatch.setattr(scalp, "mark_feed_shard_degraded", degraded)
    monkeypatch.setattr(scalp, "mark_feed_shard_connected", connected)

    await persist_liquidation_health_snapshot(object())  # type: ignore[arg-type]

    assert calls == [
        ("binance", "degraded", True),
        ("binance", "ok", False),
        ("bybit", "degraded", False),
    ]
    assert scalp.LIQ_LOSS_PENDING == {}


@pytest.mark.asyncio
async def test_collector_startup_breaks_persisted_liquidation_continuity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    connected = {"binance": True, "bybit": True}
    monkeypatch.setattr(scalp, "LIQ_FEED_CONNECTED", connected)

    async def degraded(_conn, feed, exchange, *_args, data_loss=False):
        assert data_loss is False
        calls.append((feed, exchange))

    monkeypatch.setattr(scalp, "mark_feed_shard_degraded", degraded)

    await reset_liquidation_feed_health(object())  # type: ignore[arg-type]

    assert connected == {"binance": False, "bybit": False}
    assert calls == [("liquidations", "binance"), ("liquidations", "bybit")]
