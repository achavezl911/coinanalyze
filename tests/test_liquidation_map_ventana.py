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


class _Conexion:
    """Despacha por el texto de la consulta, como hacen las cuatro que emite la funcion."""

    def __init__(self, buckets: list[dict]) -> None:
        self.buckets = buckets

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
