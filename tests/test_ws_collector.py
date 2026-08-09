import time

import pytest

from app.ws_collector import (
    WHALE_TRADE_THRESHOLD,
    Bucket,
    BucketStore,
    binance_url,
    spot_pairs,
    valid_trade,
)


def test_valid_trade_rejects_bad_values(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    now_ms = 1_000_000_000
    assert valid_trade("100", "2", now_ms) == (100.0, 2.0, now_ms)
    assert valid_trade("nan", "2", now_ms) is None
    assert valid_trade("100", "0", now_ms) is None
    assert valid_trade("100", "2", now_ms - 121_000) is None
    assert valid_trade("100", "2", now_ms + 31_000) is None
    assert valid_trade("10000000", "100000000", now_ms) is None


@pytest.mark.asyncio
async def test_ack_does_not_drop_bucket_changed_during_flush(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    store = BucketStore()
    event_ms = 999_800_000
    await store.add("BTC", "binance", event_ms, 100.0, 1.0, True)
    snapshots = await store.minute_snapshot()
    assert len(snapshots) == 1
    await store.add("BTC", "binance", event_ms + 1, 100.0, 1.0, True)
    await store.ack_minute(snapshots)
    assert len(store.minute) == 1


@pytest.mark.asyncio
async def test_bucketstore_caps_realtime_buckets_during_database_outage(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)
    store = BucketStore(max_bucket_minutes=120, max_buckets_per_key=2)
    for offset_ms in (0, 5_000, 10_000):
        await store.add("BTC", "binance", 1_000_000_000 - offset_ms, 100.0, 1.0, True)

    assert len(store.realtime) == 2
    assert store.dropped_buckets == 1
    assert store.dropped_trades == 1


def test_whale_trade_threshold_is_asset_specific():
    bucket = Bucket()
    bucket.add(1_000_000, True, WHALE_TRADE_THRESHOLD["BTC"])
    assert bucket.inst_buy_usd == 0
    assert bucket.mid_buy_usd == 1_000_000
    bucket.add(5_000_000, True, WHALE_TRADE_THRESHOLD["BTC"])
    assert bucket.inst_buy_usd == 5_000_000


def test_heartbeat_publishes_each_spot_venue() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ws_collector.py").read_text()
    assert 'f"ws-{exchange}:{shard_index}/{shard_count}"' in source


def test_websocket_topics_are_generated_only_for_assigned_symbols():
    symbols = ("ETHUSDT_PERP.A",)

    assert spot_pairs(symbols) == ("ETHUSDT",)
    assert binance_url(symbols).endswith("ethusdt@aggTrade")
    assert "btcusdt" not in binance_url(symbols)
    assert "solusdt" not in binance_url(symbols)
