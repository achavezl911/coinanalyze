"""EDAD R1 (M-05, F9 H3/H6, P10): toda «ultima fila» de la foto lleva tope de edad.

Los casos son los del diseno fable-dz2 («P5 -> R5») contra la pieza real:
- M-05 / H3: `price_1h`, `oi_bybit` y `oi_old` tomaban la ultima fila de CUALQUIER edad. Una
  fila plantada pasada su tope ya no cuenta (None); una fila fresca (CONTROL) da lo de main.
- H3: con la hora de futuros bloqueada por un hueco, `price_dir_1h` es None.
- H6: la foto del ciclo de OHLCV a +8 s de la frontera de 5 min salia sin regimen, porque su
  corte iba por delante del certificado de liquidaciones. Ahora se corta en el certificado si
  va UNA cubeta detras (tres cifras, con su `metrics_cutoff_at`); si va mas, sigue nulo.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from app.data_gaps import record_data_gap
from app.ingest import publish_snapshot
from app.metrics import LIQUIDATION_HISTORY_HEARTBEAT, compute_snapshot

PERP = "BTCUSDT_PERP.A"
T = datetime(2026, 3, 5, 12, 5, tzinfo=UTC)  # frontera de 5 min
CINCO = timedelta(minutes=5)

VELAS = """INSERT INTO ohlcv(ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx)
    SELECT g, $1::text, '1min', $4, $4, $4, $4, 10, 6, 5, 3
    FROM generate_series($2::timestamptz, $3::timestamptz, interval '1 minute') g
    ON CONFLICT (symbol, interval, ts) DO UPDATE
      SET open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close"""
CINCO_MIN = """INSERT INTO {tabla}(ts, symbol, interval, {c}_open, {c}_high, {c}_low, {c}_close)
    SELECT g, $1::text, '5min', $4, $4, $4, $4
    FROM generate_series($2::timestamptz, $3::timestamptz, interval '5 minutes') g"""
SPOT = """INSERT INTO spot_trades_agg(ts, symbol, exchange, interval, buy_vol_usd, sell_vol_usd,
        inst_buy_usd, inst_sell_usd, mid_buy_usd, mid_sell_usd, retail_buy_usd, retail_sell_usd,
        trade_count, covered_seconds, venue_count)
    SELECT g, 'BTC', 'combined', '1min', 100, 40, 0, 0, 0, 0, 0, 0, 5, 60, 2
    FROM generate_series($1::timestamptz, $2::timestamptz, interval '1 minute') g"""


async def _conexion():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    return conn, tx


async def _velas(conn, desde, hasta, close):
    await conn.execute(VELAS, PERP, desde, hasta, close)


async def _cinco(conn, tabla, desde, hasta, valor):
    c = {"open_interest": "oi", "oi_bybit": "oi", "funding_rate": "fr"}[tabla]
    await conn.execute(CINCO_MIN.format(tabla=tabla, c=c), PERP, desde, hasta, valor)


async def _foto(conn):
    return await compute_snapshot(
        conn, PERP, "BTC", T + timedelta(seconds=5), price_cutoff=T, metrics_cutoff=T
    )


async def _con(caso):
    conn, tx = await _conexion()
    try:
        return await caso(conn)
    finally:
        await tx.rollback()
        await conn.close()


# --- M-05 / H3: price_1h ------------------------------------------------------------------


async def test_price_1h_vela_de_hace_tres_horas_no_es_la_de_hace_una():
    async def caso(conn):
        await _velas(conn, T - timedelta(hours=3), T - timedelta(hours=3), 100.0)
        await _velas(conn, T - timedelta(minutes=1), T - timedelta(minutes=1), 110.0)
        return await _foto(conn)

    foto = await _con(caso)
    assert foto["price"] == 110.0, foto
    # main comparaba contra la vela de hace 3 h: +10 % -> price_dir_1h = 1
    assert foto["price_dir_1h"] is None, foto


async def test_price_1h_control_vela_de_hace_una_hora_da_lo_de_main():
    async def caso(conn):
        await _velas(conn, T - timedelta(minutes=60), T - timedelta(minutes=60), 100.0)
        await _velas(conn, T - timedelta(minutes=1), T - timedelta(minutes=1), 110.0)
        return await _foto(conn)

    assert (await _con(caso))["price_dir_1h"] == 1


async def test_price_dir_1h_none_con_la_hora_bloqueada():
    async def caso(conn):
        await _velas(conn, T - timedelta(minutes=60), T - timedelta(minutes=1), 100.0)
        await _velas(conn, T - timedelta(minutes=1), T - timedelta(minutes=1), 110.0)
        await record_data_gap(
            conn, feed="ohlcv_1min", feed_class="cadence", exchange="binance",
            market="perpetual", symbol=PERP, granularity="1min",
            start=T - timedelta(minutes=30), end=T - timedelta(minutes=29),
            expected_cadence=timedelta(minutes=1), evidence_type="missing_interval",
            detection_reason="configured cadence bucket absent",
            detection_source="test cadence detector",
        )
        return await _foto(conn)

    foto = await _con(caso)
    assert foto["btr_1h"] is None, foto
    # main conservaba price_1h y publicaba una direccion contra una hora con hueco
    assert foto["price_dir_1h"] is None, foto


# --- M-05 / H3: oi_bybit y oi_old ------------------------------------------------------------


async def test_oi_bybit_de_hace_media_hora_no_es_el_actual():
    async def caso(conn):
        await _cinco(conn, "oi_bybit", T - timedelta(minutes=30), T - timedelta(minutes=30), 500.0)
        return await _foto(conn)

    foto = await _con(caso)
    assert foto["oi_bybit"] is None, foto
    assert foto.get("oi_bybit_at") is None, foto


async def test_oi_bybit_control_cubeta_anterior_cuenta_con_su_hora():
    async def caso(conn):
        await _cinco(conn, "oi_bybit", T - 2 * CINCO, T - 2 * CINCO, 500.0)
        return await _foto(conn)

    foto = await _con(caso)
    assert foto["oi_bybit"] == 500.0, foto
    assert foto.get("oi_bybit_at", T - 2 * CINCO) == T - 2 * CINCO, foto


async def test_oi_old_de_hace_24_h_y_media_no_es_el_de_hace_24_h():
    async def caso(conn):
        await _cinco(conn, "open_interest", T - CINCO, T - CINCO, 1100.0)
        viejo = T - timedelta(hours=24, minutes=30)
        await _cinco(conn, "open_interest", viejo, viejo, 1000.0)
        return await _foto(conn)

    foto = await _con(caso)
    assert foto["oi"] == 1100.0, foto
    # main: (1100 - 1000) / 1000 = +10 % contra una fila de 24 h 30 min
    assert foto["oi_chg_24h_pct"] is None, foto


async def test_oi_old_control_de_hace_24_h_da_lo_de_main():
    async def caso(conn):
        await _cinco(conn, "open_interest", T - CINCO, T - CINCO, 1100.0)
        await _cinco(conn, "open_interest", T - timedelta(hours=24, minutes=5),
                     T - timedelta(hours=24, minutes=5), 1000.0)
        return await _foto(conn)

    assert (await _con(caso))["oi_chg_24h_pct"] == pytest.approx(10.0)


# --- H6: el corte de la foto es el de su certificado -----------------------------------------


async def _mercado_hasta_la_cubeta_anterior(conn, certificado_en, latido_en):
    """24 h de todo, con la cubeta [T-5, T) de 5 min SIN ingerir todavia (como a :05:08)."""
    desde = T - timedelta(hours=25)
    await _velas(conn, desde, T - timedelta(minutes=1), 100.0)
    await conn.execute(SPOT, desde, T - timedelta(minutes=1))
    for tabla, valor in (("open_interest", 1000.0), ("oi_bybit", 900.0), ("funding_rate", 0.01)):
        await _cinco(conn, tabla, desde, T - 2 * CINCO, valor)
    detalle = json.dumps({
        "source_start_ts": int((certificado_en - timedelta(hours=74)).timestamp()),
        "source_cutoff_ts": int(certificado_en.timestamp()),
        "requested_symbols": 1, "observed_symbols": 1,
        "requested_symbol_names": [PERP], "observed_symbol_names": [PERP],
        "missing_symbols": [], "returned_rows": 0, "accepted_rows": 0,
        "reason": "complete_observation",
    })
    await conn.execute(
        "INSERT INTO pipeline_heartbeat(service, updated_at, status, detail)"
        " VALUES ($1, $2, 'ok', $3) ON CONFLICT (service) DO UPDATE"
        " SET updated_at = EXCLUDED.updated_at, status = 'ok', detail = EXCLUDED.detail",
        LIQUIDATION_HISTORY_HEARTBEAT, latido_en, detalle,
    )


async def _publica_a_mas_8s(conn):
    """El ciclo de OHLCV de :05:08: suelo de precio y de metricas en T."""
    await publish_snapshot(
        conn, None, (PERP,), now_utc=T + timedelta(seconds=8), price_cutoff=T, metrics_cutoff=T
    )
    return await conn.fetchrow(
        "SELECT regime_score, metrics_cutoff_at, long_liq_24h FROM metrics_snapshot"
        " WHERE symbol = $1 ORDER BY ts DESC LIMIT 1", PERP,
    )


async def test_h6_foto_a_mas_8s_de_la_frontera_trae_regimen_con_su_corte():
    async def caso(conn):
        # el ciclo de metricas de :00 certifico [.., T-5); el de :05 aun no ha corrido
        await _mercado_hasta_la_cubeta_anterior(conn, T - CINCO, T - CINCO + timedelta(seconds=14))
        return await _publica_a_mas_8s(conn)

    fila = await _con(caso)
    # main: certificado T-5 < suelo T -> liquidaciones sin medir -> regime_score NULL
    assert fila["regime_score"] is not None, dict(fila)
    assert fila["long_liq_24h"] == 0.0, dict(fila)
    assert fila["metrics_cutoff_at"] == T - 2 * CINCO, dict(fila)


async def test_h6_control_ciclo_parado_15_min_sigue_rechazado():
    async def caso(conn):
        # certificado tres cubetas detras; el latido, fresco, para aislar la regla del corte
        await _mercado_hasta_la_cubeta_anterior(conn, T - 3 * CINCO, T - timedelta(seconds=60))
        return await _publica_a_mas_8s(conn)

    fila = await _con(caso)
    assert fila["regime_score"] is None, dict(fila)
    assert fila["long_liq_24h"] is None, dict(fila)


class _Latido:
    def __init__(self, corte):
        detalle = json.dumps({"source_cutoff_ts": int(corte.timestamp())})
        self.rows = [{"detail": detalle}]

    async def fetch(self, _query, *_args):
        return self.rows


@pytest.mark.parametrize(
    ("certificado", "esperado"),
    [(T, T), (T - CINCO, T - CINCO), (T - 2 * CINCO, T), (T + CINCO, T)],
)
async def test_h6_corte_certificado_solo_una_cubeta_detras(certificado, esperado):
    from app.metrics import certified_metrics_cutoff

    assert await certified_metrics_cutoff(_Latido(certificado), T) == esperado
