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


@pytest.mark.asyncio
async def test_el_vaciado_de_apagado_se_lleva_los_minutos_cerrados(monkeypatch):
    """Los que esperan la gracia se perdian en cada reinicio: son dato real."""
    from app.ws_collector import LATE_TRADE_GRACE_SECONDS

    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    store = BucketStore()
    # un minuto cerrado hace 70 s: NO es elegible para el flush normal (gracia 125 s)
    cerrado_ms = int((ahora - 130) * 1000)
    await store.add("BTC", "binance", cerrado_ms, 100.0, 1.0, True)
    assert await store.minute_snapshot() == []
    assert LATE_TRADE_GRACE_SECONDS > 60
    # con gracia 0 si sale, que es lo que hace el vaciado del apagado
    assert len(await store.minute_snapshot(grace=0.0)) == 1


@pytest.mark.asyncio
async def test_el_vaciado_de_apagado_NO_publica_el_minuto_en_curso(monkeypatch):
    """Un minuto a medias escrito como completo seria inventarse un volumen."""
    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    store = BucketStore()
    await store.add("BTC", "binance", int((ahora - 5) * 1000), 100.0, 1.0, True)
    assert await store.minute_snapshot(grace=0.0) == []


@pytest.mark.asyncio
async def test_drain_devuelve_cuantos_minutos_salvo(monkeypatch):
    from app import ws_collector

    ahora = 1_000_000.0
    monkeypatch.setattr(time, "time", lambda: ahora)
    monkeypatch.setattr(ws_collector, "STORE", BucketStore())
    await ws_collector.STORE.add("BTC", "binance", int((ahora - 130) * 1000), 100.0, 1.0, True)
    escritos = []

    async def _falso(_pool, _ownership, snapshots):
        escritos.append(snapshots)

    monkeypatch.setattr(ws_collector, "_write_minute", _falso)
    assert await ws_collector.drain_closed_minutes(None, None) == 1
    assert len(escritos) == 1
    # y sin nada que salvar no toca la base
    monkeypatch.setattr(ws_collector, "STORE", BucketStore())
    assert await ws_collector.drain_closed_minutes(None, None) == 0
    assert len(escritos) == 1


def test_el_minuto_del_arranque_se_marca_corto():
    """K52: la fila existe y hoy pasa por completa; el que arranca a mitad no cubre 60 s."""
    from app.ws_collector import segundos_cubiertos

    arranque = 1_000_030.0  # el proceso empieza 30 s dentro del minuto que abre en 1000000
    assert segundos_cubiertos(1_000_000, arranque) == 30
    assert segundos_cubiertos(1_000_045, arranque) == 60  # minuto posterior: completo
    assert segundos_cubiertos(999_940, arranque) == 0     # minuto anterior entero: nada


def test_el_minuto_completo_NO_se_marca():
    """El control positivo: un guardia que marca todo esta tan roto como el que no marca."""
    from app.ws_collector import segundos_cubiertos

    arranque = 1_000_000.0
    assert segundos_cubiertos(1_000_000, arranque) == 60
    assert segundos_cubiertos(1_000_600, arranque) == 60


def test_los_dos_colectores_marcan_igual():
    """Lo pagan los dos y la marca tiene que significar lo mismo en las dos tablas."""
    from app.scalp_collector import segundos_cubiertos as futuros
    from app.ws_collector import segundos_cubiertos as spot

    for ts in (999_900, 1_000_000, 1_000_030, 1_000_120):
        assert spot(ts, 1_000_030.0) == futuros(ts, 1_000_030.0)
