from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.db import (
    mark_feed_connected,
    mark_feed_degraded,
    mark_feed_error,
    mark_feed_shard_connected,
)

ROOT = Path(__file__).resolve().parents[1]


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, *args: Any) -> None:
        self.calls.append((query, args))

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None


def test_schema_defines_market_feed_health_idempotently() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS market_feed_health" in schema
    assert "PRIMARY KEY (feed, exchange)" in schema
    assert "status IN ('ok','degraded','error')" in schema
    assert "CREATE INDEX IF NOT EXISTS market_feed_health_updated_idx" in schema
    assert "CREATE TABLE IF NOT EXISTS market_feed_health_shard" in schema
    assert "PRIMARY KEY (feed, exchange, shard_index, shard_count)" in schema


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


@pytest.mark.asyncio
async def test_sharded_feed_health_serializes_and_aggregates_fail_closed() -> None:
    conn = RecordingConnection()

    await mark_feed_shard_connected(
        conn,  # type: ignore[arg-type]
        "liquidations",
        "bybit",
        1,
        2,
        (0, 1),
        "subscribed",
    )

    assert len(conn.calls) == 3
    lock_query, lock_args = conn.calls[0]
    shard_query, shard_args = conn.calls[1]
    aggregate_query, aggregate_args = conn.calls[2]
    assert "pg_advisory_xact_lock" in lock_query
    assert lock_args == ("coinanalyze:feed-health:liquidations:bybit:2",)
    assert "INSERT INTO market_feed_health_shard" in shard_query
    assert shard_args == ("liquidations", "bybit", 1, 2, "ok", "subscribed", False)
    assert "observed_shards <> cardinality" in aggregate_query
    assert "MIN(updated_at)" in aggregate_query
    assert "INSERT INTO market_feed_health(" in aggregate_query
    assert aggregate_args == ("liquidations", "bybit", 2, [0, 1])


@pytest.mark.asyncio
async def test_shard_without_symbols_cannot_publish_feed_health() -> None:
    conn = RecordingConnection()

    with pytest.raises(ValueError, match="without symbols"):
        await mark_feed_shard_connected(
            conn,  # type: ignore[arg-type]
            "liquidations",
            "binance",
            1,
            3,
            (0, 2),
        )

    assert conn.calls == []
