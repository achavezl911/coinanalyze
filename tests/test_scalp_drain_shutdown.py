"""Apagar el colector no puede costar tres minutos de operativa.

Un bucket de minuto no es elegible para escribirse hasta M+185 s (60 s de minuto mas
LATE_TRADE_GRACE_SECONDS) y hasta entonces vive SOLO en RAM. systemd manda SIGTERM y el
proceso moria en el acto: medido en 140 el 2026-08-25, 19 despliegues y 33 minutos
ausentes de futures_trades_agg en 14 rachas, iguales en los tres simbolos y los tres
exchanges.

El drenaje se lleva los minutos CERRADOS, que estan completos y solo esperaban su
colchon. El minuto en curso se queda fuera: esta a medias y escribirlo lo convertiria de
ausencia -visible y declarable- en cifra silenciosamente incompleta.
"""

import time

import pytest

import app.scalp_collector as sc
from app.scalp_collector import LATE_TRADE_GRACE_SECONDS, TradeBucket, TradeStore


def _marca(minutos_atras: int) -> int:
    """La marca de N minutos antes del minuto en curso, sobre la rejilla de 60 s.

    Se cuenta en minutos enteros y no en segundos a proposito: un bucket es elegible
    cuando ts+60 <= now-gracia, asi que expresar el limite en segundos sueltos deja
    casos que caen a un lado o a otro segun el segundo en que corra el test.
    """
    return int(time.time()) // 60 * 60 - 60 * minutos_atras


def _bucket(valor: float = 1000.0) -> TradeBucket:
    b = TradeBucket()
    b.add(valor, True, 50000.0, int(time.time() * 1000), 10**9)
    return b


@pytest.fixture
def store(monkeypatch) -> TradeStore:
    nuevo = TradeStore()
    monkeypatch.setattr(sc, "TRADE_STORE", nuevo)
    return nuevo


class _Conexion:
    def __init__(self) -> None:
        self.escrituras: list[str] = []

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def executemany(self, sql, _records):
        self.escrituras.append(sql)

    async def execute(self, *_args, **_kwargs):
        return None

    async def fetchval(self, *_args, **_kwargs):
        # La generacion que espera el fence de app.db.assert_service_ownership.
        return 7


class _Pool:
    def __init__(self) -> None:
        self.conn = _Conexion()
        self.tomas = 0

    def acquire(self):
        self.tomas += 1
        return self.conn


async def test_el_colchon_retiene_un_minuto_cerrado_y_grace_cero_lo_suelta(store) -> None:
    """El caso exacto de la perdida: minuto ya cerrado pero aun dentro de los 125 s."""
    clave = ("BTCUSDT_PERP.A", "binance", _marca(1))
    store.minute[clave] = _bucket()

    assert await store.minute_snapshot() == []
    assert [k for k, _ in await store.minute_snapshot(grace=0.0)] == [clave]


async def test_el_minuto_en_curso_no_se_drena(store) -> None:
    """Escribirlo a medias seria peor que no escribirlo: la ausencia al menos se ve."""
    en_curso = ("BTCUSDT_PERP.A", "binance", _marca(0))
    cerrado = ("BTCUSDT_PERP.A", "binance", _marca(1))
    store.minute[en_curso] = _bucket()
    store.minute[cerrado] = _bucket()

    assert [k for k, _ in await store.minute_snapshot(grace=0.0)] == [cerrado]


async def test_drenar_escribe_las_dos_tablas_y_vacia_lo_escrito(store) -> None:
    cerrado = ("BTCUSDT_PERP.A", "binance", _marca(1))
    en_curso = ("BTCUSDT_PERP.A", "binance", _marca(0))
    store.minute[cerrado] = _bucket()
    store.minute[en_curso] = _bucket()
    pool = _Pool()

    assert await sc.drenar_minutos(pool) == 1
    assert pool.tomas == 1
    escrituras = " ".join(pool.conn.escrituras)
    assert "futures_trades_agg" in escrituras
    assert "'combined'" in escrituras
    # Lo drenado se saca de RAM y lo que sigue abierto se queda para el siguiente ciclo.
    assert list(store.minute) == [en_curso]


async def test_drenar_sin_minutos_cerrados_no_toca_la_base(store) -> None:
    store.minute[("BTCUSDT_PERP.A", "binance", _marca(0))] = _bucket()
    pool = _Pool()

    assert await sc.drenar_minutos(pool) == 0
    assert pool.tomas == 0


async def test_el_colchon_por_defecto_sigue_siendo_el_de_siempre(store) -> None:
    """El drenaje no puede cambiar el camino normal: fuera del apagado, un minuto sigue
    esperando sus 125 s para absorber operaciones tardias."""
    # Cerrado hace 2 min: entre 120 y 180 s, siempre por debajo de los 185 que exige
    # el colchon. Cerrado hace 5: entre 300 y 360, siempre por encima.
    retenido = ("BTCUSDT_PERP.A", "binance", _marca(2))
    elegible = ("ETHUSDT_PERP.A", "binance", _marca(5))
    store.minute[retenido] = _bucket()
    store.minute[elegible] = _bucket()

    assert LATE_TRADE_GRACE_SECONDS == 125.0
    assert [k for k, _ in await store.minute_snapshot()] == [elegible]
    assert {k for k, _ in await store.minute_snapshot(grace=0.0)} == {retenido, elegible}


class _PoolCerrable(_Pool):
    def __init__(self) -> None:
        super().__init__()
        self.cerrado = False

    async def close(self) -> None:
        self.cerrado = True


class _Cerrojo:
    """Lo minimo que mira el fence: servicio, shard y generacion."""

    service = "scalp"
    shard_index = 0
    shard_count = 1
    generation = 7

    def __init__(self) -> None:
        self.cerrado = False

    async def close(self) -> None:
        self.cerrado = True


async def test_sigterm_pasa_por_el_drenaje_en_vez_de_matar_el_proceso(store, monkeypatch) -> None:
    """La regresion exacta: sin manejador de SIGTERM el proceso moria en el acto y el
    finally de main() no llegaba a correr, asi que nadie vaciaba TRADE_STORE.

    Se comprueba que el manejador ESTA instalado antes de mandar la senal: si no lo
    estuviera, la senal mataria a pytest en vez de fallar el test."""
    import asyncio
    import os
    import signal

    pool = _PoolCerrable()
    cerrojo = _Cerrojo()

    async def _eterno(*_args, **_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(sc, "ACTIVE_SYMBOLS", ())
    monkeypatch.setattr(sc, "acquire_service_lock", lambda *_a, **_k: _completado(cerrojo))
    monkeypatch.setattr(sc, "create_pool", lambda *_a, **_k: _completado(pool))
    monkeypatch.setattr(sc, "monitor_service_lock", _eterno)
    monkeypatch.setattr(sc, "monitor", _eterno)
    monkeypatch.setattr(sc, "owns_global_cleanup", lambda _i: False)

    cerrado = ("BTCUSDT_PERP.A", "binance", _marca(1))
    store.minute[cerrado] = _bucket()

    tarea = asyncio.create_task(sc.main())
    await asyncio.sleep(0.05)
    bucle = asyncio.get_running_loop()
    assert signal.SIGTERM in bucle._signal_handlers, "main() no instalo el manejador"

    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(tarea, timeout=10)

    assert pool.conn.escrituras, "el apagado no escribio el minuto cerrado"
    assert store.minute == {}
    assert pool.cerrado and cerrojo.cerrado


async def _completado(valor):
    return valor


async def test_el_desmontaje_espera_a_todas_las_tareas_antes_de_cerrar_el_pool(
    store, monkeypatch
) -> None:
    """`trabajo` es un gather sin return_exceptions: termina en cuanto UNA hija cae.

    Si el apagado siguiera ahi, cerraria el pool mientras las demas aun se desmontan, y
    dos de los lazos escriben en la base dentro de su except CancelledError. Medido en
    140 el 2026-08-26: "liquidation_feed_health_persist_failed ... pool is closed" en
    los dos exchanges, en la primera parada ordenada que corrio.
    """
    import asyncio
    import os
    import signal

    pool = _PoolCerrable()
    cerrojo = _Cerrojo()
    visto: dict[str, bool] = {}

    async def _cede_rapido(*_args, **_kwargs):
        await asyncio.Event().wait()

    async def _cede_despacio(*_args, **_kwargs):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)
            visto["pool_cerrado"] = pool.cerrado
            raise

    monkeypatch.setattr(sc, "ACTIVE_SYMBOLS", ())
    monkeypatch.setattr(sc, "acquire_service_lock", lambda *_a, **_k: _completado(cerrojo))
    monkeypatch.setattr(sc, "create_pool", lambda *_a, **_k: _completado(pool))
    monkeypatch.setattr(sc, "monitor_service_lock", _cede_rapido)
    monkeypatch.setattr(sc, "monitor", _cede_despacio)
    monkeypatch.setattr(sc, "owns_global_cleanup", lambda _i: False)

    tarea = asyncio.create_task(sc.main())
    await asyncio.sleep(0.05)
    bucle = asyncio.get_running_loop()
    assert signal.SIGTERM in bucle._signal_handlers

    os.kill(os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(tarea, timeout=10)

    assert visto.get("pool_cerrado") is False, "el pool se cerro antes de que cedieran todas"
    assert pool.cerrado
