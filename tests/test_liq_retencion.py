"""Campana 150 · liquidations_realtime con SU retencion (LIQ_REALTIME_RETENTION_DAYS, 30 d por omision), separada de
la de los trades de scalp (SCALP_TRADE_RETENTION_HOURS), que no cambia. Base desechable con sql/schema.sql aplicado."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

import app.scalp_collector as scalp
from app.config import Settings

EDADES = {"2h": timedelta(hours=2), "13h": timedelta(hours=13), "29d": timedelta(days=29), "31d": timedelta(days=31)}


def test_la_retencion_de_liquidaciones_es_de_30_dias_por_omision() -> None:
    assert Settings.model_fields["LIQ_REALTIME_RETENTION_DAYS"].default == 30


@pytest.mark.asyncio
async def test_una_pasada_poda_liquidaciones_a_30_dias_y_trades_a_12_horas(monkeypatch: pytest.MonkeyPatch) -> None:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    monkeypatch.setattr(scalp.SETTINGS, "SCALP_TRADE_RETENTION_HOURS", 12)  # la de 140
    monkeypatch.setattr(scalp.SETTINGS, "LIQ_REALTIME_RETENTION_DAYS", 30)
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
        await conn.execute(
            "INSERT INTO symbols(symbol, base_asset) VALUES('BTCUSDT_PERP.A', 'BTC') ON CONFLICT DO NOTHING")
        await conn.execute("SELECT ensure_temporal_partitions(now(), 33, 1)")
        await conn.execute("TRUNCATE liquidations_realtime, futures_trades_realtime")
        ahora = datetime.now(UTC)
        for nombre, edad in EDADES.items():
            ts = ahora - edad
            await conn.execute(
                "INSERT INTO liquidations_realtime(ts, symbol, exchange, side, notional_usd, price, qty, event_id) "
                "VALUES($1, 'BTCUSDT_PERP.A', 'binance', 'long', 1000, 100000, 0.01, $2)", ts, nombre)
            await conn.execute(
                "INSERT INTO futures_trades_realtime(ts, symbol, exchange, buy_vol_usd, sell_vol_usd, large_buy_usd, "
                "large_sell_usd, trade_count, last_px) VALUES($1, 'BTCUSDT_PERP.A', 'binance', 1, 1, 0, 0, 1, 100000)",
                ts)
        async with conn.transaction():
            await scalp.cleanup_expired_rows(conn)
        liq = {r["event_id"] for r in await conn.fetch("SELECT event_id FROM liquidations_realtime")}
        trades = await conn.fetch("SELECT ts FROM futures_trades_realtime")
    finally:
        await conn.close()
    assert liq == {"2h", "13h", "29d"}
    assert [r["ts"] for r in trades] == [ahora - EDADES["2h"]]
