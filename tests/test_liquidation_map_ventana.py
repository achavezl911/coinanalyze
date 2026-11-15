"""K42 — /api/liquidation-map declara la ventana que uso y la truncacion de niveles.

Sin ventana declarada la cifra no se puede verificar desde fuera: el filtro vivia dentro
de la consulta como ``ts >= now()-180min`` y asyncpg abre una transaccion por consulta,
asi que ni las dos consultas de la propia funcion compartian ``now()``. Un oraculo
externo, ademas, corre contra una ventana que se desliza por los dos bordes mientras
compara.

Y ``levels`` son los 12 mayores, no el mapa entero: quien los sume creyendo que tiene la
ventana completa se equivoca en silencio. Medido en 140 el 2026-08-26: 16 buckets, los 12
mostrados sumaban 1324507.75 de 1330540.05. Por eso la truncacion se declara.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.scalp_logic import liquidation_map

SIM = "BTCUSDT_PERP.A"
AHORA = datetime(2026, 8, 26, 2, 30, tzinfo=UTC)
PRECIO = 80000.0


def _sano(**cambios) -> dict:
    fila = {"status": "ok", "healthy_since": AHORA - timedelta(days=1), "last_loss_at": None,
            "updated_at": AHORA - timedelta(seconds=5), "detail": None}
    return {**fila, **cambios}


class _Conexion:
    """Despacha por el texto de la consulta, como hacen las que emite la funcion.

    Desde A4 (DATOS A) tambien lee la salud del feed (market_feed_health): por omision, los dos
    venues sanos toda la ventana, que es lo que las pruebas de K42 daban por supuesto."""

    def __init__(self, buckets: list[dict], salud: dict | None = None) -> None:
        self.buckets = buckets
        self.salud = {"binance": _sano(), "bybit": _sano()} if salud is None else salud

    async def fetchval(self, query: str, *_args: object):
        if "SELECT now()" in query:
            return AHORA
        if "FROM ohlcv" in query:
            return PRECIO
        raise AssertionError(f"fetchval inesperado: {query}")

    async def fetch(self, query: str, *args: object):
        if "liquidations_realtime" in query:
            self.ventana = (args[1], args[2])
            return self.buckets
        if "market_feed_health" in query:
            return [{"exchange": ex, **fila} for ex, fila in self.salud.items()]
        return []  # _resample_highs_lows: sin velas, atr None


def _bucket(precio: float, largo: float, corto: float) -> dict:
    return {"bucket": precio, "long_liq": largo, "short_liq": corto, "total": largo + corto}


@pytest.mark.asyncio
async def test_declara_la_ventana_que_uso() -> None:
    conn = _Conexion([_bucket(80000.0, 10.0, 5.0)])
    d = await liquidation_map(conn, SIM)

    assert d["window_end"] == AHORA.isoformat()
    assert d["window_start"] == (AHORA - timedelta(minutes=180)).isoformat()
    assert d["window_minutes"] == 180
    assert d["as_of"] == d["window_end"]
    # y la ventana declarada es EXACTAMENTE la que se le paso a la consulta
    assert conn.ventana == (AHORA - timedelta(minutes=180), AHORA)


@pytest.mark.asyncio
async def test_bucket_size_es_10bps_del_precio() -> None:
    conn = _Conexion([_bucket(80000.0, 1.0, 0.0)])
    d = await liquidation_map(conn, SIM)
    assert d["bucket_size"] == pytest.approx(PRECIO * 10 / 10000.0)


@pytest.mark.asyncio
async def test_la_truncacion_a_12_es_visible() -> None:
    """Con 16 buckets se sirven 12, y la respuesta dice cuantos hay y cuanto suman TODOS."""
    buckets = [_bucket(79000.0 + i * 80, float(100 - i), 0.0) for i in range(16)]
    conn = _Conexion(buckets)
    d = await liquidation_map(conn, SIM)

    assert d["buckets_total"] == 16
    assert d["levels_shown"] == 12
    assert len(d["levels"]) == 12
    mostrado = sum(n["total_notional"] for n in d["levels"])
    assert d["window_notional"] == pytest.approx(sum(b["total"] for b in buckets))
    # el punto entero: lo mostrado NO es la ventana, y la diferencia es declarable
    assert mostrado < d["window_notional"]
    assert d["window_notional"] - mostrado == pytest.approx(sum(b["total"] for b in buckets[12:]))


@pytest.mark.asyncio
async def test_sin_truncacion_los_totales_coinciden() -> None:
    buckets = [_bucket(79000.0 + i * 80, float(10 - i), 0.0) for i in range(5)]
    d = await liquidation_map(_Conexion(buckets), SIM)

    assert d["buckets_total"] == 5
    assert d["levels_shown"] == 5
    assert sum(n["total_notional"] for n in d["levels"]) == pytest.approx(d["window_notional"])


@pytest.mark.asyncio
async def test_ventana_vacia_declara_cero_y_no_miente() -> None:
    d = await liquidation_map(_Conexion([]), SIM)

    assert d["available"] is True
    assert d["buckets_total"] == 0
    assert d["levels_shown"] == 0
    assert d["window_notional"] == 0
    assert d["window_start"] and d["window_end"]


# ---------------------------------------------------------------------------- A4 (DATOS A, F3-F6)
# Una ventana sin filas era «0 liquidado» aunque el colector estuviera caido: el cero solo es cero
# si el feed se escucho toda la ventana.


@pytest.mark.asyncio
async def test_ventana_vacia_con_el_feed_caido_es_sin_dato_y_no_cero() -> None:
    caido = _sano(status="down", detail="bybit_liquidations_disconnected",
                  updated_at=AHORA - timedelta(minutes=20))
    d = await liquidation_map(_Conexion([], {"binance": _sano(), "bybit": caido}), SIM)

    # lo primero, lo que main dice MAL: 0 liquidado con bybit caido
    assert d["window_notional"] is None
    assert d["feed_alive"] is False
    assert d["feed_status"] == "DOWN"
    assert d["feed_reason"] == "bybit_liquidations_disconnected"
    assert set(d["cumulative_within_band"].values()) == {None}


@pytest.mark.asyncio
async def test_un_venue_reconectado_dentro_de_la_ventana_no_certifica_el_cero() -> None:
    reconecto = _sano(healthy_since=AHORA - timedelta(minutes=30))
    d = await liquidation_map(_Conexion([], {"binance": reconecto, "bybit": _sano()}), SIM)

    assert (d["feed_alive"], d["feed_status"], d["window_notional"]) == (False, "PARTIAL", None)
    assert "binance" in d["feed_reason"]


@pytest.mark.asyncio
async def test_sin_salud_del_feed_no_se_sabe() -> None:
    d = await liquidation_map(_Conexion([], {}), SIM)
    assert (d["feed_alive"], d["feed_status"], d["window_notional"]) == (False, "UNAVAILABLE", None)


@pytest.mark.asyncio
async def test_con_el_feed_caido_lo_oido_se_sirve_y_el_lado_vacio_no_es_cero() -> None:
    caido = _sano(status="down", updated_at=AHORA - timedelta(minutes=20))
    d = await liquidation_map(_Conexion([_bucket(80000.0, 10.0, 0.0)], {"binance": caido, "bybit": _sano()}), SIM)

    assert d["feed_alive"] is False
    assert d["window_notional"] == 10.0  # lo oido: un minimo
    assert d["cumulative_within_band"]["long_liq_within_0.5pct"] == 10.0
    assert d["cumulative_within_band"]["short_liq_within_0.5pct"] is None


@pytest.mark.asyncio
async def test_con_el_feed_vivo_el_cero_es_cero() -> None:
    d = await liquidation_map(_Conexion([]), SIM)
    assert (d["feed_alive"], d["feed_status"], d["feed_reason"]) == (True, "OK", None)
    assert set(d["cumulative_within_band"].values()) == {0}
