"""HUELIQ R1 (H-03, P12): el colector declara su parada y su silencio en data_gap feed='liquidations'.

En 140 el apagon de 34.6 h salio «sin huecos»: el feed solo lo escribia `queue_full`. Fueron dos cosas,
y cada una tiene su prueba: la maquina apagada (PROP parada: el arranque ve un latido de hace mas del
TOPE) y el colector VIVO 21 h con todas sus conexiones en TimeoutError (PROP mudo: los intentos
fallidos no pueden refrescar el latido, y la reconexion declara el silencio). El CONTROL: un latido de
hace 20 s es una vuelta de monitor(), no una parada.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import pytest

import app.orderflow_lectura as lec
import app.scalp_collector as scalp
from app.db import mark_feed_shard_connected
from app.scalp_logic import _liquidation_feed_quality_status

SCHEMA_SQL = (Path(__file__).resolve().parents[1] / "sql/schema.sql").read_text(encoding="utf-8")
SIMBOLO = "BTCUSDT_PERP.A"
HUECOS = "SELECT exchange, symbol, start_ts, end_ts, evidence_type FROM data_gap WHERE feed='liquidations'"


@pytest.fixture
async def conn(monkeypatch: pytest.MonkeyPatch):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    schema = f"hueliq_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(dsn)
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    monkeypatch.setattr(scalp, "ACTIVE_SYMBOLS", (SIMBOLO,))
    monkeypatch.setattr(scalp, "LIQ_FEED_CONNECTED", {"binance": False, "bybit": False})
    monkeypatch.setattr(scalp, "LIQ_HEARTBEAT_BROKEN", {"binance": False, "bybit": False}, raising=False)
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


async def _planta_latido(conn: asyncpg.Connection, edad: timedelta) -> datetime:
    """El feed de binance estuvo sano; su ultimo latido fue hace `edad`."""
    await mark_feed_shard_connected(
        conn, "liquidations", "binance", scalp.SETTINGS.COLLECTOR_SHARD_INDEX,
        scalp.SETTINGS.COLLECTOR_SHARD_COUNT, scalp.LIQUIDATION_HEALTH_SHARDS, "subscription active",
    )
    return await _envejece(conn, edad)


async def _envejece(conn: asyncpg.Connection, edad: timedelta) -> datetime:
    return await conn.fetchval(
        "UPDATE market_feed_health_shard SET updated_at = now() - $1::interval "
        "WHERE feed='liquidations' AND exchange='binance' RETURNING updated_at", edad)


async def _latido(conn: asyncpg.Connection) -> datetime:
    return await conn.fetchval(
        "SELECT updated_at FROM market_feed_health_shard WHERE feed='liquidations' AND exchange='binance'")


async def _ind(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Los huecos que ve la ruta de indicadores (IND) en las ultimas 3 h."""
    ahora = datetime.now(UTC)
    b = ahora.replace(second=0, microsecond=0) + timedelta(minutes=5 - ahora.minute % 5)
    d = await lec.indicadores(conn, symbol="BTC", desde=lec.iso(b - timedelta(hours=3)), hasta=lec.iso(b),
                              marco="5m")
    return d["sueltas"]["huecos"]


async def _calidad(conn: asyncpg.Connection) -> str:
    salud = {r["exchange"]: dict(r) for r in await conn.fetch(
        "SELECT exchange,status,healthy_since,last_loss_at,updated_at,detail "
        "FROM market_feed_health WHERE feed='liquidations'")}
    return _liquidation_feed_quality_status(salud, ("binance",), datetime.now(UTC), 3 * 3600)[0]


async def test_prop_parada_el_arranque_declara_el_latido_viejo(conn) -> None:
    latido = await _planta_latido(conn, timedelta(hours=2))

    await scalp.reset_liquidation_feed_health(conn)

    filas = [dict(f) for f in await conn.fetch(HUECOS)]
    assert filas == [{"exchange": "binance", "symbol": SIMBOLO, "start_ts": latido,
                      "end_ts": await _latido(conn), "evidence_type": "collector_outage"}]
    assert [(h["exchange"], h["desde"], h["evidencia"]) for h in await _ind(conn)] == \
        [("binance", lec.iso(latido), "collector_outage")]
    # _liquidation_feed_quality_status no lee data_gap: lee market_feed_health, que el arranque
    # deja degradado. Con main tambien da DOWN; se fija que el arreglo no lo rompe.
    assert await _calidad(conn) == "DOWN"


async def test_control_un_latido_de_hace_20_s_no_es_una_parada(conn) -> None:
    await _planta_latido(conn, timedelta(seconds=20))

    await scalp.reset_liquidation_feed_health(conn)

    assert await conn.fetch(HUECOS) == []
    assert await _ind(conn) == []


class _Socket:
    def __init__(self, fin: BaseException | None) -> None:
        self.fin = fin

    def __aiter__(self) -> _Socket:
        return self

    async def __anext__(self) -> str:
        if self.fin is not None:
            raise self.fin
        raise StopAsyncIteration


class _Conexion:
    def __init__(self, entrar, socket: _Socket) -> None:
        self.entrar, self.socket = entrar, socket

    async def __aenter__(self) -> _Socket:
        await self.entrar()
        return self.socket

    async def __aexit__(self, *_exc: Any) -> bool:
        return False


class _Pool:
    def __init__(self, conexion: asyncpg.Connection) -> None:
        self.conexion = conexion

    def acquire(self) -> _Conexion:
        async def nada() -> None:
            return None
        return _Conexion(nada, self.conexion)  # type: ignore[arg-type]


async def test_prop_mudo_el_proceso_vivo_con_intentos_fallidos_y_la_reconexion_declara(
    conn, monkeypatch: pytest.MonkeyPatch,
) -> None:
    intentos = 6
    visto: dict[str, Any] = {"llamadas": 0, "latidos": []}

    async def nada() -> None:
        return None

    async def falla() -> None:
        visto["latidos"].append(await _latido(conn))
        raise TimeoutError

    def connect(*_a: Any, **_k: Any) -> _Conexion:
        visto["llamadas"] += 1
        n = visto["llamadas"]
        if n == 1:  # una conexion buena que se cierra: su cierre es el ultimo latido sano
            return _Conexion(nada, _Socket(None))
        if n <= 1 + intentos:  # el silencio: 21 h de TimeoutError en 140, aqui `intentos`
            return _Conexion(falla, _Socket(None))
        return _Conexion(nada, _Socket(asyncio.CancelledError()))  # reconecta, y se para la prueba

    monkeypatch.setattr(scalp.websockets, "connect", connect)
    monkeypatch.setattr(scalp, "WS_RECONNECT_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(scalp, "WS_RECONNECT_MAX_SECONDS", 0.0)
    await scalp.reset_liquidation_feed_health(conn)
    real = scalp.persist_liquidation_feed_state

    async def persiste(pool, exchange, status, *args, **kwargs):
        ok = await real(pool, exchange, status, *args, **kwargs)
        if visto["llamadas"] == 1 and status == "degraded":  # el cierre de la buena paso hace 2 h
            visto["silencio_desde"] = await _envejece(conn, timedelta(hours=2))
        return ok

    monkeypatch.setattr(scalp, "persist_liquidation_feed_state", persiste)

    with pytest.raises(asyncio.CancelledError):
        await scalp.binance_market_loop(_Pool(conn))  # type: ignore[arg-type]

    desde = visto["silencio_desde"]
    # ningun intento fallido refresco el latido: sigue en el cierre de la ultima conexion buena
    assert visto["latidos"] == [desde] * intentos
    filas = [dict(f) for f in await conn.fetch(HUECOS)]
    reconexion = await conn.fetchval(
        "SELECT healthy_since FROM market_feed_health_shard WHERE feed='liquidations' AND exchange='binance'")
    assert filas == [{"exchange": "binance", "symbol": SIMBOLO, "start_ts": desde, "end_ts": reconexion,
                      "evidence_type": "collector_outage"}]
    assert [(h["exchange"], h["desde"], h["evidencia"]) for h in await _ind(conn)] == \
        [("binance", lec.iso(desde), "collector_outage")]


# HUELIQ R1b (V-08, Fable V1 N4): el silencio se juzga ENTERO, del ultimo latido sano al primer `ok`.
# Con main el arranque juzgaba [latido, arranque) y reescribia el latido; el `ok` juzgaba [arranque, ok):
# 80 s parado + 85 s reconectando = 165 s sin liquidaciones y ningun hueco declarado.
async def _pasan(conn: asyncpg.Connection, s: int) -> None:
    """El reloj avanza `s` segundos: todo lo guardado retrocede `s` respecto a now()."""
    await conn.execute(
        "UPDATE market_feed_health_shard SET updated_at = updated_at - make_interval(secs => $1) "
        "WHERE feed='liquidations'", s)
    await conn.execute(
        "UPDATE data_gap SET start_ts = start_ts - make_interval(secs => $1), "
        "end_ts = end_ts - make_interval(secs => $1) WHERE feed='liquidations'", s)


async def _parada_y_reconexion(
    conn: asyncpg.Connection, parada: int, reconexion: int, *, mira_latido: bool = False,
) -> list[float]:
    """Parado `parada` s, arranca, reconecta durante `reconexion` s y llega el primer `ok`."""
    latido = await _planta_latido(conn, timedelta(seconds=parada))
    await scalp.reset_liquidation_feed_health(conn)
    if mira_latido:
        # el arranque no da por sano un latido cuyo silencio no declaro
        assert await _latido(conn) == latido
    await _pasan(conn, reconexion)
    await scalp._write_liquidation_health(conn, "binance", "ok", "subscription active")
    filas = await conn.fetch(HUECOS + " ORDER BY start_ts")
    assert {(f["exchange"], f["symbol"], f["evidence_type"]) for f in filas} <= \
        {("binance", SIMBOLO, "collector_outage")}
    return [(f["end_ts"] - f["start_ts"]).total_seconds() for f in filas]


async def test_prop_r1b_80_s_parado_y_85_de_reconexion_es_un_hueco_de_165_s(conn) -> None:
    duraciones = await _parada_y_reconexion(conn, 80, 85, mira_latido=True)

    assert len(duraciones) == 1 and abs(duraciones[0] - 165) < 2, duraciones


async def test_prop_r1b_200_s_parado_y_85_de_reconexion_extiende_la_fila_sin_duplicarla(conn) -> None:
    duraciones = await _parada_y_reconexion(conn, 200, 85)

    assert len(duraciones) == 1 and abs(duraciones[0] - 285) < 2, duraciones


async def test_r1b_200_s_parado_y_ok_inmediato_es_una_fila_como_hoy(conn) -> None:
    duraciones = await _parada_y_reconexion(conn, 200, 0)

    assert len(duraciones) == 1 and abs(duraciones[0] - 200) < 2, duraciones


async def test_control_r1b_40_s_parado_y_30_de_reconexion_no_es_un_hueco(conn) -> None:
    assert await _parada_y_reconexion(conn, 40, 30) == []
