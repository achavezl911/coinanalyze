from __future__ import annotations

import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

import app.scalp_collector as scalp_collector
import app.scalp_logic as scalp_logic
import app.ws_collector as ws_collector
from app.daily_agg import (
    DAILY_VERDICT_LOGIC_VERSION,
    DAILY_VERDICT_SNAPSHOT_VERSION,
)
from app.metrics import REGIME_LOGIC_VERSION
from app.signal_execution import EXECUTION_SNAPSHOT_VERSION
from app.signal_ledger import SIGNAL_EVIDENCE_VERSION, SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION

SYMBOL = "BTCUSDT_PERP.A"


def test_future_trade_is_rejected_at_reception_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reception_ms = 1_800_000_000_000
    monkeypatch.setattr(scalp_collector, "now_ms", lambda: reception_ms)
    monkeypatch.setattr(time, "time", lambda: reception_ms / 1000)

    assert scalp_collector.valid_trade("100", "1", reception_ms) is not None
    assert scalp_collector.valid_trade("100", "1", reception_ms + 1) is None
    assert ws_collector.valid_trade("100", "1", reception_ms) is not None
    assert ws_collector.valid_trade("100", "1", reception_ms + 1) is None


@pytest.mark.asyncio
async def test_future_binance_book_is_dropped_and_requests_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reception_ms = 1_800_000_000_000
    books = scalp_collector.BookStore()
    await books.set_snapshot(
        SYMBOL,
        "binance",
        [["100", "1"]],
        [["101", "1"]],
        reception_ms,
    )
    monkeypatch.setattr(scalp_collector, "BOOK_STORE", books)
    monkeypatch.setattr(scalp_collector, "now_ms", lambda: reception_ms)

    with pytest.raises(scalp_collector.BookResyncRequired):
        await scalp_collector.handle_binance(
            {
                "stream": "btcusdt@depth10@100ms",
                "data": {
                    "e": "depthUpdate",
                    "s": "BTCUSDT",
                    "E": reception_ms + 1,
                    "b": [["100", "2"]],
                    "a": [["101", "2"]],
                },
            }
        )

    assert (SYMBOL, "binance") not in books.books


@pytest.mark.asyncio
async def test_future_bybit_book_is_dropped_and_requests_resync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reception_ms = 1_800_000_000_000
    books = scalp_collector.BookStore()
    await books.set_snapshot(
        SYMBOL,
        "bybit",
        [["100", "1"]],
        [["101", "1"]],
        reception_ms,
        update_id=10,
    )
    monkeypatch.setattr(scalp_collector, "BOOK_STORE", books)
    monkeypatch.setattr(scalp_collector, "now_ms", lambda: reception_ms)

    with pytest.raises(scalp_collector.BookResyncRequired):
        await scalp_collector.handle_bybit(
            {
                "topic": "orderbook.50.BTCUSDT",
                "type": "snapshot",
                "ts": reception_ms + 1,
                "data": {
                    "u": 11,
                    "seq": 101,
                    "b": [["100", "2"]],
                    "a": [["101", "2"]],
                },
            }
        )

    assert (SYMBOL, "bybit") not in books.books


@pytest.mark.asyncio
async def test_combined_book_materializer_bounds_latest_venues_by_db_clock() -> None:
    class Connection:
        query = ""

        async def execute(self, query: str, *_args: object) -> str:
            self.query = query
            return "INSERT 0 0"

    conn = Connection()
    await scalp_collector._write_combined_books(
        conn,  # type: ignore[arg-type]
        [SimpleNamespace(symbol=SYMBOL)],  # type: ignore[list-item]
    )

    latest = conn.query.split("), totals AS", 1)[0]
    assert "SELECT clock_timestamp() AS as_of" in latest
    assert "ts >= cutoff.as_of-interval '10 seconds'" in latest
    assert "ts <= cutoff.as_of" in latest


@pytest.mark.asyncio
async def test_scalp_context_uses_one_injected_cutoff_for_every_window() -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

    class Connection:
        query = ""
        args: tuple[object, ...] = ()
        baseline_args: tuple[object, ...] = ()

        async def fetchrow(self, query: str, *args: object) -> dict[str, Any]:
            self.query = query
            self.args = args
            return {}

        async def fetch(self, _query: str, *args: object) -> list[dict[str, Any]]:
            self.baseline_args = args
            return []

    conn = Connection()
    await scalp_logic.scalp_context(conn, SYMBOL, cutoff)  # type: ignore[arg-type]

    assert "now()" not in conn.query.lower()
    assert conn.args[-1] == cutoff
    assert conn.baseline_args[-1] == cutoff
    for source in (
        "ohlcv",
        "futures_trades_realtime",
        "spot_trades_realtime",
        "orderbook_snapshot",
        "liquidations_realtime",
        "open_interest",
    ):
        assert source in conn.query
    assert conn.query.count("ts <= $8") >= 7
    assert "BETWEEN 0 AND 10 THEN 'ok'" in conn.query


@pytest.mark.asyncio
async def test_swing_propagates_one_as_of_to_all_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    seen: dict[str, datetime | None] = {}

    def block(name: str):
        async def fake(_conn: object, _symbol: str, as_of=None, **_kwargs):
            seen[name] = as_of
            return {"name": name, "as_of": as_of.isoformat()}

        return fake

    monkeypatch.setattr(scalp_logic, "structure_detail", block("structure_detail"))
    monkeypatch.setattr(scalp_logic, "macro_context", block("macro_context"))
    monkeypatch.setattr(scalp_logic, "cross_asset", block("cross_asset"))
    monkeypatch.setattr(scalp_logic, "passive_flow", block("passive_flow"))
    monkeypatch.setattr(scalp_logic, "trend_matrix", block("trend_matrix"))
    monkeypatch.setattr(
        scalp_logic,
        "compute_swing_score",
        lambda blocks: {"bias": "NEUTRAL", "blocks_seen": sorted(blocks)},
    )

    result = await scalp_logic.swing_score(object(), SYMBOL, cutoff)  # type: ignore[arg-type]

    assert set(seen) == {
        "structure_detail",
        "macro_context",
        "cross_asset",
        "passive_flow",
        "trend_matrix",
    }
    assert set(seen.values()) == {cutoff}
    assert result["as_of"] == cutoff.isoformat()
    assert result["as_of_semantics"] == "shared_event_time_cutoff"


@pytest.mark.asyncio
async def test_swing_intraday_helpers_use_cutoff_for_both_bounds() -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

    class Connection:
        calls: list[tuple[str, tuple[object, ...]]] = []

        async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
            self.calls.append((query, args))
            return []

    conn = Connection()
    await scalp_logic._binned(conn, SYMBOL, 3600, 300, cutoff)  # type: ignore[arg-type]
    await scalp_logic._resample_highs_lows(
        conn, SYMBOL, 3600, 20, as_of=cutoff  # type: ignore[arg-type]
    )

    binned_query, binned_args = conn.calls[0]
    resample_query, resample_args = conn.calls[1]
    assert "ts >= $4::timestamptz-" in binned_query
    assert "ts <= $4" in binned_query
    assert binned_args[-1] == cutoff
    assert "AND ts <= $5" in resample_query
    assert resample_args[-1] == cutoff


@pytest.mark.asyncio
async def test_macro_daily_query_excludes_sessions_after_cutoff() -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)  # 08:00 New York

    class Connection:
        query = ""
        args: tuple[object, ...] = ()

        async def fetch(self, query: str, *args: object) -> list[dict[str, Any]]:
            self.query = query
            self.args = args
            return []

    conn = Connection()
    result = await scalp_logic.macro_context(
        conn, SYMBOL, as_of=cutoff  # type: ignore[arg-type]
    )

    assert "session_date <= $3" in conn.query
    assert conn.args[-1].isoformat() == "2026-08-10"
    assert result["as_of"] == cutoff.isoformat()


def test_pr24_versions_change_only_evidence_and_daily_logic() -> None:
    assert SIGNAL_EVIDENCE_VERSION == 5
    assert DAILY_VERDICT_LOGIC_VERSION == "daily-verdict-v4"
    assert SCALP_SIGNAL_LOGIC_VERSION == "scalp-summary-v1"
    assert SIGNAL_SAMPLING_VERSION == 1
    assert REPLAY_CONTEXT_VERSION == 1
    assert REGIME_LOGIC_VERSION == 2
    assert OUTCOME_VERSION == 1
    assert EXECUTION_SNAPSHOT_VERSION == 1
    assert DAILY_VERDICT_SNAPSHOT_VERSION == 1
