from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.db import mark_feed_connected, mark_feed_degraded, mark_feed_error

ROOT = Path(__file__).resolve().parents[1]


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> None:
        self.calls.append((query, args))


def test_schema_defines_market_feed_health_idempotently() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS market_feed_health" in schema
    assert "PRIMARY KEY (feed, exchange)" in schema
    assert "status IN ('ok','degraded','error')" in schema
    assert "CREATE INDEX IF NOT EXISTS market_feed_health_updated_idx" in schema


@pytest.mark.asyncio
async def test_mark_feed_connected_preserves_an_existing_healthy_since() -> None:
    conn = RecordingConnection()

    await mark_feed_connected(conn, "liquidations", "bybit", "subscribed")  # type: ignore[arg-type]

    query, args = conn.calls[0]
    assert args == ("liquidations", "bybit", "subscribed")
    assert "WHEN market_feed_health.status = 'ok'" in query
    assert "THEN market_feed_health.healthy_since" in query
    assert "ELSE now()" in query


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("marker", "expected_status"),
    [(mark_feed_degraded, "degraded"), (mark_feed_error, "error")],
)
async def test_unhealthy_markers_only_record_loss_when_requested(marker, expected_status) -> None:
    conn = RecordingConnection()

    await marker(conn, "liquidations", "binance", "queue overflow", data_loss=True)

    query, args = conn.calls[0]
    assert args == ("liquidations", "binance", expected_status, "queue overflow", True)
    assert "WHEN $5 THEN now()" in query
    assert "ELSE market_feed_health.last_loss_at" in query
