import asyncio

import pytest

import app.scalp_collector as scalp
from app.scalp_collector import LocalBook, safe_liq_put
from app.scalp_logic import compute_scalp_summary


def test_scalp_score_uses_spot_futures_divergence():
    base = {
        "fut_delta_1m": 0.0,
        "fut_volume_1m": 1000.0,
        "fut_delta_3m": 800.0,
        "fut_volume_3m": 1000.0,
        "spot_delta_3m": -800.0,
        "spot_volume_3m": 1000.0,
        "imbalance_l5": 0.5,
        "price": 100.0,
        "first_px_3m": 100.0,
        "last_px_3m": 100.2,
        "book_status": "ok",
    }
    summary = compute_scalp_summary(base)
    assert summary["spot_fut_divergence_norm"] < 0
    assert summary["short_score"] > summary["long_score"]


class _CleanupConnection:
    def __init__(self):
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, query, *args):
        self.calls.append((query, args))


@pytest.mark.asyncio
async def test_designated_shard_cleans_expired_rows_for_removed_symbols():
    conn = _CleanupConnection()

    await scalp.cleanup_expired_rows(conn)  # type: ignore[arg-type]

    assert scalp.owns_global_cleanup(0) is True
    assert scalp.owns_global_cleanup(1) is False
    assert len(conn.calls) == 5
    assert all("symbol" not in query for query, _args in conn.calls)


@pytest.mark.parametrize("book_status", ["missing", "stale"])
def test_scalp_summary_degrades_when_book_is_not_fresh(book_status: str):
    summary = compute_scalp_summary(
        {
            "book_status": book_status,
            "fut_delta_1m": 1_000.0,
            "fut_volume_1m": 1_000.0,
            "fut_delta_3m": 1_000.0,
            "fut_volume_3m": 1_000.0,
            "spot_delta_3m": 1_000.0,
            "spot_volume_3m": 1_000.0,
            "imbalance_l5": 1.0,
        }
    )
    assert summary["book_status"] == book_status
    assert summary["state"] == "No Trade"
    assert summary["confidence"] == "baja"
    assert f"book {book_status}" in summary["reason"]


def test_local_book_rejects_non_monotonic_sequence():
    book = LocalBook("BTCUSDT_PERP.A", "bybit")
    book.reset([["100", "1"]], [["101", "1"]], 1000, update_id=10)
    assert book.apply_delta([["100", "2"]], [], 1001, update_id=11) is True
    assert book.apply_delta([["100", "3"]], [], 1002, update_id=11) is False


@pytest.mark.asyncio
async def test_liquidation_queue_overflow_is_counted(monkeypatch):
    small_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    monkeypatch.setattr(scalp, "LIQ_QUEUE", small_queue)
    monkeypatch.setattr(scalp, "LIQ_DROPPED", 0)
    monkeypatch.setattr(scalp, "LIQ_LOSS_PENDING", {})
    item = (None, "BTCUSDT_PERP.A", "binance", "long", 1.0, 1.0, 1.0, "e")
    await safe_liq_put(item)  # type: ignore[arg-type]
    await safe_liq_put(item)  # type: ignore[arg-type]
    assert scalp.LIQ_DROPPED == 1
    assert "binance" in scalp.LIQ_LOSS_PENDING
    assert small_queue.qsize() == 1


def test_scalp_summary_exposes_basis_bps() -> None:
    """El basis ya no llega calculado desde SQL: lo decide basis_quality con la edad."""
    now_ms = 1_786_056_654_685.0
    summary = compute_scalp_summary(
        {
            "fut_price": 101.0,
            "spot_price": 100.0,
            "fut_event_ms": now_ms - 8_000,
            "spot_event_ms": now_ms - 8_200,
            "now_ms": now_ms,
        }
    )
    assert summary["basis_bps"] == 100.0
    assert summary["basis_status"] == "VALID"
    assert summary["fut_price"] == 101.0
    assert summary["spot_price"] == 100.0


def test_scalp_summary_no_publica_basis_sin_marca_de_tiempo() -> None:
    """Sin reloj no hay forma de saber si las patas siguen vivas: no se inventa un numero."""
    summary = compute_scalp_summary({"fut_price": 101.0, "spot_price": 100.0})
    assert summary["basis_bps"] is None
    assert summary["basis_status"] == "UNAVAILABLE"


def test_scalp_summary_marks_missing_book() -> None:
    summary = compute_scalp_summary({})
    assert summary["book_status"] == "missing"
