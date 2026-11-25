"""COBERTURA R2 (V-12): un dia de despliegues no apaga el regimen; un corte real, si.

Medido por el operador en 140 el 2026-11-25: desde el despliegue de COBERTURA R1 toda foto salia
con regime_score NULL. El contado BTC de 24 h cubria 0.98494 (los ~12 reinicios del colector de
ese dia) y COBERTURA_MINIMA = 0.99 bloqueaba spot_24h, que es fuente del regimen (fail-closed).
- 0.985 (dia de despliegues): spot_24h NO bloqueado y el regimen con numero. Cae con 0.99.
- 0.97 (corte de ~43 min): spot_24h bloqueado y el regimen None. La regla sigue mordiendo.
Los huecos son minutos sueltos repartidos, como los reinicios; el resto del mercado, completo.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.metrics import LIQUIDATION_HISTORY_HEARTBEAT, compute_snapshot

PERP = "BTCUSDT_PERP.A"
T = datetime(2026, 3, 5, 12, 5, tzinfo=UTC)  # frontera de 5 min
CINCO = timedelta(minutes=5)
DESDE = T - timedelta(hours=25)
VELAS = """INSERT INTO ohlcv(ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx)
    SELECT g, $1::text, '1min', 100, 100, 100, 100, 10, 6, 5, 3
    FROM generate_series($2::timestamptz, $3::timestamptz, interval '1 minute') g"""
CINCO_MIN = """INSERT INTO {tabla}(ts, symbol, interval, {c}_open, {c}_high, {c}_low, {c}_close)
    SELECT g, $1::text, '5min', $4, $4, $4, $4
    FROM generate_series($2::timestamptz, $3::timestamptz, interval '5 minutes') g"""
SPOT = """INSERT INTO spot_trades_agg(ts, symbol, exchange, interval, buy_vol_usd, sell_vol_usd,
        inst_buy_usd, inst_sell_usd, mid_buy_usd, mid_sell_usd, retail_buy_usd, retail_sell_usd,
        trade_count, covered_seconds, venue_count)
    SELECT g, 'BTC', 'combined', '1min', 100, 40, 0, 0, 0, 0, 0, 0, 5, 60, 2
    FROM generate_series($1::timestamptz, $2::timestamptz, interval '1 minute') g"""


async def _mercado(conn):
    """25 h de velas, contado, OI, OI bybit y funding, y liquidaciones certificadas hasta T."""
    await conn.execute(VELAS, PERP, DESDE, T - timedelta(minutes=1))
    await conn.execute(SPOT, DESDE, T - timedelta(minutes=1))
    for tabla, c, valor in (("open_interest", "oi", 1000.0), ("oi_bybit", "oi", 900.0),
                            ("funding_rate", "fr", 0.01)):
        await conn.execute(CINCO_MIN.format(tabla=tabla, c=c), PERP, DESDE, T - CINCO, valor)
    detalle = json.dumps({
        "source_start_ts": int((T - timedelta(hours=74)).timestamp()),
        "source_cutoff_ts": int(T.timestamp()),
        "requested_symbols": 1, "observed_symbols": 1,
        "requested_symbol_names": [PERP], "observed_symbol_names": [PERP],
        "missing_symbols": [], "returned_rows": 0, "accepted_rows": 0,
        "reason": "complete_observation",
    })
    await conn.execute(
        "INSERT INTO pipeline_heartbeat(service, updated_at, status, detail)"
        " VALUES ($1, $2, 'ok', $3) ON CONFLICT (service) DO UPDATE"
        " SET updated_at = EXCLUDED.updated_at, status = 'ok', detail = EXCLUDED.detail",
        LIQUIDATION_HISTORY_HEARTBEAT, T + timedelta(seconds=4), detalle,
    )


async def _contado_a(conn, minutos_fuera: int, segundos_del_ultimo: int) -> float:
    """Quita `minutos_fuera` minutos sueltos (uno cada 30 min) de las 24 h y deja uno a medias."""
    assert minutos_fuera <= 47  # el ultimo hueco cae antes de T - 2 min, el minuto a medias
    inicio = T - timedelta(hours=24)
    fuera = [inicio + timedelta(minutes=30 * i + 7) for i in range(minutos_fuera)]
    await conn.execute(
        "DELETE FROM spot_trades_agg WHERE symbol = 'BTC' AND ts = ANY($1::timestamptz[])", fuera)
    await conn.execute(
        "UPDATE spot_trades_agg SET covered_seconds = $2 WHERE symbol = 'BTC' AND ts = $1",
        T - timedelta(minutes=2), segundos_del_ultimo)
    return await conn.fetchval(
        "SELECT SUM(LEAST(COALESCE(covered_seconds, 0), 60))::float8 / 86400 FROM spot_trades_agg"
        " WHERE symbol = 'BTC' AND exchange = 'combined' AND ts >= $1 AND ts < $2", inicio, T)


async def _foto_con_contado(minutos_fuera: int, segundos_del_ultimo: int):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        await _mercado(conn)
        cobertura = await _contado_a(conn, minutos_fuera, segundos_del_ultimo)
        foto = await compute_snapshot(
            conn, PERP, "BTC", T + timedelta(seconds=5), price_cutoff=T, metrics_cutoff=T
        )
        return cobertura, foto
    finally:
        await tx.rollback()
        await conn.close()


async def test_dia_de_despliegues_0985_no_apaga_el_regimen():
    # 21 minutos fuera y uno con 24 s: 1418 * 60 + 24 = 85 104 s de 86 400
    cobertura, foto = await _foto_con_contado(21, 24)
    assert cobertura == pytest.approx(0.985), cobertura
    # main (0.99): spot_24h bloqueado -> cvd_spot_24h None y regime_score None
    assert foto["cvd_spot_24h"] is not None, foto
    assert foto["regime_score"] is not None, foto


async def test_corte_de_43_min_0970_sigue_apagando_el_regimen():
    # 43 minutos fuera y uno con 48 s: 1396 * 60 + 48 = 83 808 s de 86 400
    cobertura, foto = await _foto_con_contado(43, 48)
    assert cobertura == pytest.approx(0.97), cobertura
    assert foto["cvd_spot_24h"] is None, foto
    assert foto["regime_score"] is None, foto
    assert foto["regime_label"] == "Sin datos suficientes", foto
