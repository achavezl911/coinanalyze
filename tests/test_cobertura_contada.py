"""COBERTURA R1 (M-01, M-02, R2b A1/A2): la cobertura del flujo se CUENTA en segundos cubiertos.

Los casos son los del diseno fable-dz2 (fable_dz2_casos.py, caso_m01) contra la pieza real:
- M-01: la foto sumaba los minutos de spot que hubiera como si fueran 24 h y pedia huecos al
  feed «spot_trades» de data_gap, que no escribe nadie. Cobertura 0.1667 y 0.3056 -> bloqueado.
- M-02: el realtime con sus dos extremos y 698 minutos vacios en medio daba la ventana por
  completa (MIN/MAX de la tabla). Cobertura contada 0.5146 -> parcial.
- Dia normal (control): 54 minutos de reconexion de 55 s repartidos (0.99688) NO se bloquea en
  la foto, y en la ventana de flujo ya no sale parcial por la regla minuto a minuto (A2).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.metrics import COBERTURA_MINIMA, compute_snapshot
from app.scalp_logic import spot_flow_windows

T = datetime(2026, 3, 5, 12, 0, tzinfo=UTC)
D = T - timedelta(hours=24)
MIN = timedelta(minutes=1)
SIEMBRA = """INSERT INTO spot_trades_agg(ts, symbol, exchange, interval, buy_vol_usd, sell_vol_usd,
        inst_buy_usd, inst_sell_usd, mid_buy_usd, mid_sell_usd, retail_buy_usd, retail_sell_usd,
        trade_count, covered_seconds, venue_count)
    SELECT g, $1::text, $5::text, '1min', 100, 40, 0, 0, 0, 0, 0, 0, 5, $4::smallint,
           CASE WHEN $5 = 'combined' THEN 2 ELSE 1 END
    FROM generate_series($2::timestamptz, $3::timestamptz - interval '1 minute', interval '1 minute') g"""


async def _conexion():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    return conn, tx


async def _siembra(conn, symbol, desde, hasta, segundos, exchanges=("combined",)):
    for exchange in exchanges:
        await conn.execute(SIEMBRA, symbol, desde, hasta, segundos, exchange)


async def _dia_normal(conn, symbol, exchanges=("combined",)):
    """1440 minutos; uno de cada 27 (54) con 55 s: 270 s de 86 400 sin escuchar."""
    await _siembra(conn, symbol, D, T, 60, exchanges)
    await conn.execute(
        "UPDATE spot_trades_agg SET covered_seconds = 55 WHERE symbol = $1 AND ts >= $2"
        " AND (extract(epoch FROM ts - $2)::int / 60) % 27 = 0", symbol, D)


async def _cobertura(conn, symbol) -> float:
    return await conn.fetchval(
        "SELECT SUM(LEAST(COALESCE(covered_seconds, 0), 60))::float8 / 86400 FROM spot_trades_agg"
        " WHERE symbol = $1 AND exchange = 'combined' AND ts >= $2 AND ts < $3", symbol, D, T)


async def _foto(conn, symbol="BTC"):
    return await compute_snapshot(conn, "BTCUSDT_PERP.A", symbol, now_utc=T + timedelta(seconds=5))


async def test_m01_cuatro_horas_de_veinticuatro_no_se_publican_como_el_dia():
    conn, tx = await _conexion()
    try:
        await _siembra(conn, "BTC", T - timedelta(hours=4), T, 60)
        assert round(await _cobertura(conn, "BTC"), 4) == 0.1667
        foto = await _foto(conn)
        # main publicaba 240 x 60 = 14 400 como el CVD spot de 24 h
        assert foto["cvd_spot_24h"] is None, foto
        assert foto["spot_vol_24h"] is None, foto
    finally:
        await tx.rollback()
        await conn.close()


async def test_m01_veinte_horas_a_diez_segundos_por_minuto_tampoco():
    conn, tx = await _conexion()
    try:
        await _siembra(conn, "BTC", T - timedelta(hours=4), T, 60)
        await _siembra(conn, "BTC", D, T - timedelta(hours=4), 10)
        assert round(await _cobertura(conn, "BTC"), 4) == 0.3056
        foto = await _foto(conn)
        # main publicaba 1440 x 60 = 86 400: todos los minutos estan, casi ninguno escuchado
        assert foto["cvd_spot_24h"] is None, foto
    finally:
        await tx.rollback()
        await conn.close()


async def test_m01_un_covered_seconds_nulo_cuenta_cero():
    """Legado (app/api.py:1253): NULL no certifica nada. LEAST(NULL, 60) valdria 60."""
    conn, tx = await _conexion()
    try:
        await _siembra(conn, "BTC", D, T, 60)
        await conn.execute("UPDATE spot_trades_agg SET covered_seconds = NULL WHERE symbol = 'BTC'"
                           " AND ts < $1", D + timedelta(hours=1))
        foto = await _foto(conn)
        assert foto["cvd_spot_24h"] is None, foto
    finally:
        await tx.rollback()
        await conn.close()


async def test_dia_normal_con_minutos_cortos_repartidos_se_publica():
    conn, tx = await _conexion()
    try:
        await _dia_normal(conn, "BTC")
        cobertura = await _cobertura(conn, "BTC")
        assert COBERTURA_MINIMA <= cobertura < 0.9970, cobertura
        foto = await _foto(conn)
        assert foto["cvd_spot_24h"] == 1440 * 60.0, foto
        assert foto["spot_vol_24h"] == 1440 * 140.0, foto
    finally:
        await tx.rollback()
        await conn.close()


async def _ventana_24h(conn, *, hueco: bool):
    """Un dia en las tres venues con el realtime tocando los DOS extremos de la ventana (T-24h y
    T-10s): el normal de 0.997, o con `hueco` el de dz2 sin 698 minutos a partir de T-18h."""
    venues = ("binance", "bybit", "combined")
    await conn.execute(
        "CREATE TABLE spot_trades_realtime_cobertura_r1 PARTITION OF spot_trades_realtime "
        "FOR VALUES FROM ('2026-03-04 00:00:00+00') TO ('2026-03-06 00:00:00+00')")
    if hueco:
        # el control de dz2 (CTRL de caso_m01): 24 minutos de 55 s y 2 de 59 s, y el hueco de M-02
        await _siembra(conn, "ETH", D, T, 60, venues)
        await conn.execute("UPDATE spot_trades_agg SET covered_seconds = 55 WHERE symbol = 'ETH'"
                           " AND extract(minute FROM ts) = 0")
        await conn.execute("UPDATE spot_trades_agg SET covered_seconds = 59 WHERE symbol = 'ETH'"
                           " AND ts = ANY($1::timestamptz[])",
                           [T - timedelta(hours=3) + 7 * MIN, T - timedelta(hours=9) + 7 * MIN])
        await conn.execute("DELETE FROM spot_trades_agg WHERE symbol = 'ETH' AND ts >= $1 AND ts < $2",
                           T - timedelta(hours=18), T - timedelta(hours=18) + 698 * MIN)
    else:
        await _dia_normal(conn, "ETH", venues)
    for exchange in venues:
        await conn.execute(
            "INSERT INTO spot_trades_realtime(ts,symbol,exchange,buy_vol_usd,sell_vol_usd,"
            "inst_buy_usd,inst_sell_usd,trade_count,last_px,venue_count) "
            "SELECT s,'ETH',$1,1,0,0,0,1,3000,$2 FROM unnest($3::timestamptz[]) s",
            exchange, 2 if exchange == "combined" else 1, [D, T - timedelta(seconds=10)])
    return (await spot_flow_windows(conn, "ETH", [("24h", 86400)], T))["24h"]["combined"]


async def test_m02_los_extremos_del_realtime_no_tapan_un_hueco_de_dentro():
    conn, tx = await _conexion()
    try:
        item = await _ventana_24h(conn, hueco=True)
        # main: realtime_complete por MIN/MAX -> complete, servida por dos filas de realtime
        assert item["source"] != "realtime", item
        assert item["complete"] is False, item
        assert item["coverage_status"] == "partial", item
        assert item["coverage_reason"] == "agg_minutes_missing", item
        assert round(item["agg_covered_seconds"] / 86400, 4) == 0.5146, item
    finally:
        await tx.rollback()
        await conn.close()


async def test_dia_normal_la_ventana_de_flujo_es_completa():
    """R2b A2: la regla minuto a minuto (agg_full = agg_minutes) lo daba parcial."""
    conn, tx = await _conexion()
    try:
        item = await _ventana_24h(conn, hueco=False)
        assert item["source"] == "agg_1min+realtime", item
        assert item["agg_minutes"] == item["agg_minutes_expected"] == 1440, item
        assert item["agg_minutes_full"] == 1440 - 54, item
        assert item["complete"] is True, item
        assert item["coverage_reason"] is None, item
    finally:
        await tx.rollback()
        await conn.close()
