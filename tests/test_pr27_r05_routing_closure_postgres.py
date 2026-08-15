"""PR27-R05 PostgreSQL suite: effective-map divergence writes no raw row.

The R04 PostgreSQL suite proves the flush paths fail closed when the *catalog*
resolves routing B.  Red on ee3792ca, this suite proves the same for the
divergence R04 cannot see: the catalog and its registered contract stay intact
while one of the four effective maps is repointed.  Pending data is already in
the stores; not a single row may reach the raw tables.
"""

from __future__ import annotations

import asyncio

import pytest

import app.scalp_collector as scalp
import app.ws_collector as ws
from app import config
from app.signal_runtime_contract import (
    RawMarketProducerContractError,
    attest_raw_market_producer,
)
from tests.test_pr27_r04_raw_producer_closure_postgres import (
    A_FUT_PX,
    A_SPOT_PX,
    B_FUT_PX,
    B_SPOT_PX,
    _bounded_sleep,
    _connect,
    _count,
    _drop,
    _Pool,
    _seed_futures,
    _seed_spot,
)


@pytest.mark.asyncio
async def test_scalp_flush_delivers_nothing_under_a_divergent_futures_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r05_scalp")
    try:
        routing = attest_raw_market_producer("scalp_collector")

        # Under coherent maps the same seeded store writes.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(A_FUT_PX))
        _bounded_sleep(scalp, monkeypatch)
        with pytest.raises(asyncio.CancelledError):
            await scalp.flush_trades(_Pool(conn), routing=routing)
        written_under_a = await _count(conn, "futures_trades_realtime")
        assert written_under_a > 0

        # The catalog still matches the registry; only the effective map moved.
        monkeypatch.setattr(scalp, "TRADE_STORE", _seed_futures(B_FUT_PX, age_seconds=15))
        monkeypatch.setitem(config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A", "ETHUSDT")
        _bounded_sleep(scalp, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_trades(_Pool(conn), routing=routing)

        assert await _count(conn, "futures_trades_realtime") == written_under_a
        assert await conn.fetchval(
            "SELECT count(*) FROM futures_trades_realtime WHERE last_px=$1", B_FUT_PX
        ) == 0
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_ws_flush_delivers_nothing_under_a_divergent_spot_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, schema = await _connect("test_pr27_r05_ws")
    try:
        routing = attest_raw_market_producer("ws_collector")

        monkeypatch.setattr(ws, "STORE", _seed_spot(A_SPOT_PX))
        _bounded_sleep(ws, monkeypatch)
        with pytest.raises(asyncio.CancelledError):
            await ws.flush_realtime(_Pool(conn), routing=routing)
        written_under_a = await _count(conn, "spot_trades_realtime")
        assert written_under_a > 0

        monkeypatch.setattr(ws, "STORE", _seed_spot(B_SPOT_PX, age_seconds=15))
        monkeypatch.setitem(config.SPOT_PAIR_MAP, "BTC", "ETHUSDT")
        _bounded_sleep(ws, monkeypatch)
        with pytest.raises(RawMarketProducerContractError):
            await ws.flush_realtime(_Pool(conn), routing=routing)

        assert await _count(conn, "spot_trades_realtime") == written_under_a
        assert await conn.fetchval(
            "SELECT count(*) FROM spot_trades_realtime WHERE last_px=$1", B_SPOT_PX
        ) == 0
    finally:
        await _drop(conn, schema)


@pytest.mark.asyncio
async def test_delivery_refuses_internal_keys_outside_the_attested_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A store key outside the validated keyspace must abort the delivery."""

    conn, schema = await _connect("test_pr27_r05_foreign_key")
    try:
        routing = attest_raw_market_producer("scalp_collector")
        store = _seed_futures(A_FUT_PX)
        for (_symbol, exchange, ts), bucket in list(store.realtime.items()):
            store.realtime[("DOGEUSDT_PERP.A", exchange, ts)] = bucket
        monkeypatch.setattr(scalp, "TRADE_STORE", store)
        _bounded_sleep(scalp, monkeypatch)

        with pytest.raises(RawMarketProducerContractError):
            await scalp.flush_trades(_Pool(conn), routing=routing)
        assert await _count(conn, "futures_trades_realtime") == 0
    finally:
        await _drop(conn, schema)
