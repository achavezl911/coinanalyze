"""A2 (DATOS A, hallazgo F3-F1): una reconexion a mitad de minuto no se escribe como minuto entero.

`segundos_cubiertos` conocia el arranque y la parada del proceso, pero no los cortes de en
medio: el websocket de un venue que caia en el segundo 20 y volvia en el 56 dejaba una fila
con covered_seconds=60. Aqui se conduce el consumidor DE VERDAD (spot en ws_collector, futuros
en scalp_collector) con un websocket doble y un reloj plantado: oye en el 5 y en el 20, se
cae en el 50 (se detecta tarde: el corte cuenta desde el ultimo mensaje oido) y vuelve en el
56. Lo que se mira es lo que el escritor del minuto manda a la base: 24 s, no 60.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import app.scalp_collector as sc
import app.ws_collector as ws

SIMBOLO = "BTCUSDT_PERP.A"


def _ts() -> int:
    """Un minuto entero bastante despues del arranque del proceso (el K52 no cuenta aqui)."""
    return (int(max(ws.PROCESO_INICIADO, sc.PROCESO_INICIADO)) // 60 + 10) * 60


class _Ws:
    """Websocket doble: cada paso es (instante, mensaje | excepcion)."""

    def __init__(self, reloj: list[float], pasos: list) -> None:
        self.reloj = reloj
        self.pasos = list(pasos)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def send(self, _msg):
        return None

    async def recv(self):
        t, cosa = self.pasos.pop(0)
        self.reloj[0] = t
        if isinstance(cosa, BaseException):
            raise cosa
        return cosa

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.recv()


def _conecta(reloj: list[float], conexiones: list):
    """connect() doble: cada conexion es (instante en que abre, pasos)."""

    def connect(*_a, **_k):
        t, pasos = conexiones.pop(0)
        reloj[0] = t
        return _Ws(reloj, pasos)

    return connect


class _Conexion:
    def __init__(self) -> None:
        self.lotes: list[tuple[str, list]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    def transaction(self):
        return self

    async def executemany(self, sql, records):
        self.lotes.append((sql, list(records)))

    async def execute(self, *_a, **_k):
        return None


class _Pool:
    def __init__(self) -> None:
        self.conn = _Conexion()

    def acquire(self):
        return self.conn


@pytest.fixture
def reloj(monkeypatch):
    reloj = [float(_ts() - 30)]
    monkeypatch.setattr(time, "time", lambda: reloj[0])
    # el estado de escucha es del proceso: cada prueba empieza sin cortes
    for modulo in (ws, sc):
        for escucha in getattr(modulo, "ESCUCHA", {}).values():
            escucha.__init__()
    return reloj


def _guion(ts: int, mensaje) -> list:
    """Conecta antes del minuto, oye en el 5 y el 20, cae en el 50; vuelve en el 56."""
    return [
        (ts - 30, [(ts + 5, mensaje), (ts + 20, mensaje), (ts + 50, OSError("caida"))]),
        (ts + 56, [(ts + 58, mensaje), (ts + 70, asyncio.CancelledError())]),
    ]


def _sin_esperas(monkeypatch):
    """El backoff no espera: el reloj lo mueve la siguiente conexion."""
    dormir = asyncio.sleep

    async def sleep(_s, *_a, **_k):
        await dormir(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)


async def test_spot_cae_del_20_al_56_y_el_minuto_dice_24_segundos(reloj, monkeypatch):
    ts = _ts()
    monkeypatch.setattr(ws, "connect", _conecta(reloj, _guion(ts, '{"data": {"s": "NADA"}}')))
    _sin_esperas(monkeypatch)
    with pytest.raises(asyncio.CancelledError):
        await ws.binance_consumer((SIMBOLO,))

    pool = _Pool()
    claves = [(ws.WS_SYMBOL_MAP[SIMBOLO], v, m) for m in (ts - 60, ts, ts + 60) for v in ("binance", "bybit")]
    await ws._write_minute(pool, None, [(k, ws.Bucket(trade_count=1)) for k in claves])
    filas = pool.conn.lotes[0][1]
    cubiertos = {(r[2], int(r[0].timestamp()) - ts): r[14] for r in filas}

    assert cubiertos[("binance", 0)] == 24, cubiertos  # 0-20 y 56-60
    assert cubiertos[("binance", -60)] == 60, cubiertos
    assert cubiertos[("binance", 60)] == 60, cubiertos  # ya habia vuelto en el 56
    assert cubiertos[("bybit", 0)] == 60, cubiertos  # el otro venue no se cayo


async def test_futuros_cae_del_20_al_56_y_el_minuto_dice_24_segundos(reloj, monkeypatch):
    ts = _ts()
    monkeypatch.setattr(sc.websockets, "connect", _conecta(reloj, _guion(ts, '{"data": {"s": "NADA"}}')))
    _sin_esperas(monkeypatch)

    async def nada(*_a, **_k):
        return None

    monkeypatch.setattr(sc.BOOK_STORE, "drop_exchange", nada)
    with pytest.raises(asyncio.CancelledError):
        await sc.binance_loop()

    conn = _Conexion()
    claves = [(SIMBOLO, v, m) for m in (ts - 60, ts, ts + 60) for v in ("binance", "bybit")]
    await sc._write_trade_rows(
        conn, "futures_trades_agg", [(k, sc.TradeBucket(trade_count=1)) for k in claves], realtime=False
    )
    filas = conn.lotes[0][1]
    cubiertos = {(r[2], int(r[0].timestamp()) - ts): r[10] for r in filas}

    assert cubiertos[("binance", 0)] == 24, cubiertos
    assert cubiertos[("binance", -60)] == 60, cubiertos
    assert cubiertos[("binance", 60)] == 60, cubiertos
    assert cubiertos[("bybit", 0)] == 60, cubiertos


async def test_un_venue_que_sigue_caido_al_escribir_cuenta_hasta_el_corte(reloj, monkeypatch):
    """Si el minuto se escribe con el venue aun sin volver, lo oido es hasta el ultimo mensaje."""
    ts = _ts()
    guion = [(ts - 30, [(ts + 5, '{}'), (ts + 15, '{}'), (ts + 40, OSError("caida"))])]
    monkeypatch.setattr(ws, "connect", _conecta(reloj, guion))

    async def sleep(_s, *_a, **_k):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", sleep)
    with pytest.raises(asyncio.CancelledError):
        await ws.binance_consumer((SIMBOLO,))

    pool = _Pool()
    await ws._write_minute(pool, None, [((ws.WS_SYMBOL_MAP[SIMBOLO], "binance", ts), ws.Bucket(trade_count=1))])
    assert pool.conn.lotes[0][1][0][14] == 15


def test_sin_cortes_el_resultado_es_el_de_antes():
    """Control: sin cortes, ningun minuto cambia (la extension no toca el camino de siempre)."""
    for modulo in (ws, sc):
        for ts in (1000, 1020, 1060, 2000):
            assert modulo.segundos_cubiertos(ts, inicio=1030) == modulo.segundos_cubiertos(ts, 1030, None, ())
            assert modulo.segundos_cubiertos(ts, 1030, 1045) == modulo.segundos_cubiertos(ts, 1030, 1045, ())
