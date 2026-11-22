"""A1 (DATOS A, hallazgo F3-F5): la ventana larga de flujo solo es `complete` si lo de DENTRO esta.

`_flow_windows` daba `complete` mirando solo los extremos: que el agg de 1 min empezase antes
del inicio de la ventana y que el realtime llegase hasta ahora. Con 80 minutos ausentes en
medio de 8 h, la suma salia como la suma de la ventana y data_confidence la llamaba
«cobertura continua». Aqui se planta ese hueco (y un minuto corto, covered_seconds < 60)
contra la base desechable, para el spot y para el futuro, con un control sin hueco.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import asyncpg
import pytest

from app.scalp_logic import futures_flow_windows, spot_flow_windows

T = datetime(2026, 3, 2, 12, 0, tzinfo=UTC)
PATAS = {
    "spot": ("BTC", "spot_trades_realtime", "spot_trades_agg", spot_flow_windows),
    "futures": ("BTCUSDT_PERP.A", "futures_trades_realtime", "futures_trades_agg", futures_flow_windows),
}
VENUES = (("binance", 1), ("bybit", 1), ("combined", 2))


async def _conexion():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    return conn, tx


async def _planta(conn, pata: str, *, hueco: tuple[int, int] | None = None,
                 corto: tuple[int, int] | None = None):
    """Agg de 1 min de T-9h a T-6min (sin los minutos de `hueco`, y con los de `corto` a 30 s;
    los dos en minutos antes de T) y realtime de 5 s de T-10min a T-5s, en las tres venues."""
    symbol, rt, agg, _ = PATAS[pata]
    await conn.execute(
        f"CREATE TABLE {rt}_da_a1 PARTITION OF {rt} "
        "FOR VALUES FROM ('2026-03-02 00:00:00+00') TO ('2026-03-03 00:00:00+00')")
    extra_cols = (
        ",inst_buy_usd,inst_sell_usd,mid_buy_usd,mid_sell_usd,retail_buy_usd,retail_sell_usd"
        if pata == "spot" else ",large_buy_usd,large_sell_usd")
    extra_vals = ",0,0,0,0,0,0" if pata == "spot" else ",0,0"
    for exchange, vc in VENUES:
        await conn.execute(
            f"INSERT INTO {agg}(ts,symbol,exchange,interval,buy_vol_usd,sell_vol_usd{extra_cols},"
            "trade_count,covered_seconds,venue_count) "
            f"SELECT m,$1,$2,'1min',10,4{extra_vals},3,"
            "CASE WHEN $5::int IS NOT NULL AND m <= $3 - $5::int * interval '1 minute' "
            "AND m > $3 - $8::int * interval '1 minute' THEN 30 ELSE 60 END,$4 "
            "FROM generate_series($3::timestamptz - interval '9 hours', $3::timestamptz - interval '6 minutes', "
            "interval '1 minute') m "
            "WHERE $6::int IS NULL OR NOT (m <= $3 - $6::int * interval '1 minute' "
            "AND m > $3 - $7::int * interval '1 minute')",
            symbol, exchange, T, vc, corto[0] if corto else None,
            hueco[0] if hueco else None, hueco[1] if hueco else None, corto[1] if corto else None)
        extra_rt_cols = ",inst_buy_usd,inst_sell_usd" if pata == "spot" else ",large_buy_usd,large_sell_usd"
        await conn.execute(
            f"INSERT INTO {rt}(ts,symbol,exchange,buy_vol_usd,sell_vol_usd{extra_rt_cols},"
            "trade_count,last_px,venue_count) "
            "SELECT s,$1,$2,1,0,0,0,1,80000,$4 "
            "FROM generate_series($3::timestamptz - interval '10 minutes', "
            "$3::timestamptz - interval '5 seconds', interval '5 seconds') s",
            symbol, exchange, T, vc)


async def _ocho_horas(conn, pata: str) -> dict:
    symbol, _, _, fn = PATAS[pata]
    flujo = await fn(conn, symbol, [("8h", 28800)], T)
    return flujo["8h"]


@pytest.mark.parametrize("pata", list(PATAS))
async def test_control_sin_hueco_la_ventana_de_8h_es_completa(pata):
    conn, tx = await _conexion()
    try:
        await _planta(conn, pata)
        ventana = await _ocho_horas(conn, pata)
        for exchange, _ in VENUES:
            item = ventana[exchange]
            assert item["source"] == "agg_1min+realtime", item
            assert item["complete"] is True, item
            assert item["coverage_status"] == "complete", item
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.parametrize("pata", list(PATAS))
async def test_ochenta_minutos_ausentes_en_medio_no_es_completa(pata):
    conn, tx = await _conexion()
    try:
        # sin los minutos de T-300min (incluido) a T-220min: 80 minutos, en medio de las 8 h
        await _planta(conn, pata, hueco=(220, 300))
        ventana = await _ocho_horas(conn, pata)
        for exchange, _ in VENUES:
            item = ventana[exchange]
            assert item["complete"] is False, f"{pata}/{exchange}: 80 min ausentes y complete: {item}"
            assert item["coverage_status"] == "partial", item
            assert item["coverage_reason"] == "agg_minutes_missing", item
            assert item["agg_minutes_expected"] - item["agg_minutes"] == 80, item
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.parametrize("pata", list(PATAS))
async def test_un_minuto_corto_dentro_se_cuenta_y_no_tumba_la_ventana(pata):
    """R2b A2: la regla minuto a minuto (agg_full = agg_minutes) daba parcial un dia sano por
    un minuto de reconexion. Se cuentan sus segundos: 30 de 28 500 no bajan de COBERTURA_MINIMA."""
    conn, tx = await _conexion()
    try:
        await _planta(conn, pata, corto=(240, 241))
        item = (await _ocho_horas(conn, pata))["combined"]
        assert item["agg_minutes_full"] == item["agg_minutes"] - 1, item
        assert item["complete"] is True, item
        assert item["coverage_reason"] is None, item
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.parametrize("pata", list(PATAS))
async def test_veinte_minutos_cortos_dentro_no_es_completa(pata):
    # 20 minutos a 30 s: 600 s de 28 500 (0.9789), por debajo de COBERTURA_MINIMA
    conn, tx = await _conexion()
    try:
        await _planta(conn, pata, corto=(240, 260))
        item = (await _ocho_horas(conn, pata))["combined"]
        assert item["complete"] is False, item
        assert item["coverage_status"] == "partial", item
        assert item["coverage_reason"] == "agg_minutes_short", item
        assert item["agg_covered_seconds"] == 475 * 60 - 20 * 30, item
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.parametrize("hueco", [None, (220, 300)])
async def test_data_confidence_dice_lo_que_dice_la_ventana_y_no_cobertura_continua(monkeypatch, hueco):
    """data_confidence miraba en el futuro solo el MIN/MAX de su realtime y llamaba a todo
    «cobertura continua». Ahora sus dos patas salen de la misma ventana que la matriz; aqui
    se fija el reloj de la ventana en T para poder plantar en el pasado."""
    from app import ai_context

    conn, tx = await _conexion()
    try:
        await _planta(conn, "spot", hueco=hueco)
        await _planta(conn, "futures", hueco=hueco)
        for nombre in ("spot_flow_windows", "futures_flow_windows"):
            original = getattr(ai_context, nombre)

            async def en_t(c, s, w, as_of=None, _f=original):
                return await _f(c, s, w, T)

            monkeypatch.setattr(ai_context, nombre, en_t)
        fila = await ai_context.data_confidence_row(conn, "BTCUSDT_PERP.A")
        esperado = hueco is None
        for pata in ("spot", "futures"):
            assert fila[f"flow_8h_{pata}_complete"] is esperado, fila
            assert fila[f"flow_8h_{pata}_coverage_reason"] == (None if esperado else "agg_minutes_missing")
        assert fila["flow_8h_complete"] is esperado
        assert "cobertura continua" not in fila["quality_score_basis"]
    finally:
        await tx.rollback()
        await conn.close()
