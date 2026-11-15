"""A9 (DATOS A, F7-H1): el job que repone desde los aggTrades REST de Binance los minutos PARCIALES del footprint.
Contra una base desechable y un REST doble: nunca sale a la red."""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import orderflow_repone_binance as R  # noqa: E402

SCHEMA_SQL = (Path(__file__).resolve().parents[1] / "sql" / "schema.sql").read_text(encoding="utf-8")
# Un minuto de hace una hora: las particiones que crea el esquema van de ayer a pasado manana.
M = int(datetime.now(UTC).replace(second=0, microsecond=0).timestamp()) - 3600
TS = datetime.fromtimestamp(M, UTC)
HORA = TS.replace(minute=0)


@pytest.fixture
async def conn():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    schema = f"repone_{uuid.uuid4().hex}"
    c = await asyncpg.connect(dsn)
    await c.execute(f'CREATE SCHEMA "{schema}"')
    await c.execute(f'SET search_path TO "{schema}", public')
    await c.execute("SET TIME ZONE 'UTC'")
    await c.execute(SCHEMA_SQL)
    try:
        yield c
    finally:
        await c.execute("SET search_path TO public")
        await c.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await c.close()


def _agg(a, seg, precio, q, vende):
    """Una fila de /aggTrades como la sirve Binance: precio y cantidad en texto, m = el comprador era maker."""
    return {"a": a, "p": precio, "q": q, "f": a, "l": a, "T": M * 1000 + int(seg * 1000), "m": vende}


class _Rest:
    """aggTrades doble: el minuto M de BTCUSDT en fapi, paginado de dos en dos (R.LIMITE = 2)."""

    def __init__(self):
        self.filas = [_agg(10, 1, "80000.5", "0.5", False), _agg(11, 20.5, "80001.2", "0.25", True),
                      _agg(12, 59.999, "80000.9", "1", False), _agg(13, 60, "80003", "9", False)]
        self.pedidos = []

    def __call__(self, url, params):
        self.pedidos.append((url, dict(params)))
        assert url == R.URL["binance_usdm"] and params["symbol"] == "BTCUSDT"
        if "fromId" in params:
            filas = [f for f in self.filas if f["a"] >= params["fromId"]]
        else:
            filas = [f for f in self.filas if params["startTime"] <= f["T"] <= params["endTime"]]
        return filas[:params["limit"]]


async def _planta(conn):
    await conn.executemany(
        """INSERT INTO orderflow_cobertura(ts,venue,symbol,segundos,operaciones,definitivo) VALUES ($1,$2,$3,$4,$5,$6)""",
        [(TS, "binance_usdm", "BTC", 24, 1, True),                         # parcial: se repone
         (TS + timedelta(minutes=1), "binance_usdm", "BTC", 60, 5, True),  # entero: no se toca
         (TS + timedelta(minutes=2), "binance_usdm", "BTC", 30, 1, False),  # aun abierto: no se toca
         (TS, "okx_swap", "BTC", 10, 1, True)])                            # otro venue: no se toca
    await conn.executemany(
        """INSERT INTO orderflow_celda(ts,venue,symbol,nivel,compra_base,venta_base,compra_usd,venta_usd,compras,ventas)
           VALUES ($1,$2,'BTC',$3,$4,0,$5,0,1,0)""",
        [(TS, "binance_usdm", D(79990), D(1), D(79990)),          # lo poco oido: se sustituye
         (TS + timedelta(minutes=1), "binance_usdm", D(80100), D(5), D(400500))])
    await conn.execute("INSERT INTO orderflow_hora_hecha(ts, venue, symbol, lo, hi) VALUES ($1,'binance_usdm','BTC',0,1)",
                       HORA)


async def _celdas(conn, ts):
    return [tuple(r) for r in await conn.fetch(
        """SELECT nivel, compra_base, venta_base, compra_usd, venta_usd, compras, ventas FROM orderflow_celda
            WHERE venue='binance_usdm' AND symbol='BTC' AND ts=$1 ORDER BY nivel""", ts)]


async def test_repone_solo_el_minuto_parcial_con_su_cobertura_y_lo_deja_escrito(conn, monkeypatch):
    monkeypatch.setattr(R, "LIMITE", 2)
    await _planta(conn)
    rest = _Rest()
    hasta = TS + timedelta(minutes=5)

    # sin --escribe: lista y no toca nada
    inf = await R.repone(conn, TS, hasta, trae=rest, log=lambda *_: None)
    assert [(f["venue"], f["operaciones"], f["escrito"]) for f in inf] == [("binance_usdm", 3, False)]
    assert await _celdas(conn, TS) == [(D(79990), D(1), D(0), D(79990), D(0), 1, 0)]

    inf = await R.repone(conn, TS, hasta, trae=rest, escribe=True, log=lambda *_: None)
    assert [f["escrito"] for f in inf] == [True]
    # 3 operaciones del minuto (la del segundo 60 es del siguiente), paso de BTC = 1, el agresor compra si m = false
    assert await _celdas(conn, TS) == [
        (D(80000), D("1.5"), D(0), D("40000.25") + D("80000.9"), D(0), 2, 0),
        (D(80001), D(0), D("0.25"), D(0), D("20000.3"), 0, 1)]
    assert rest.pedidos[1][1] == {"symbol": "BTCUSDT", "fromId": 12, "limit": 2}   # pagina por fromId
    cob = {(r["ts"], r["venue"]): (r["segundos"], r["operaciones"]) for r in await conn.fetch(
        "SELECT ts, venue, segundos, operaciones FROM orderflow_cobertura")}
    assert cob[(TS, "binance_usdm")] == (60, 3)
    assert cob[(TS + timedelta(minutes=1), "binance_usdm")] == (60, 5)
    assert cob[(TS + timedelta(minutes=2), "binance_usdm")] == (30, 1)
    assert cob[(TS, "okx_swap")] == (10, 1)
    assert await _celdas(conn, TS + timedelta(minutes=1)) == [(D(80100), D(5), D(0), D(400500), D(0), 1, 0)]
    assert await conn.fetchval("SELECT count(*) FROM orderflow_hora_hecha") == 0   # la suma horaria se rehace
    gap = await conn.fetchrow("SELECT status, start_ts, end_ts, detection_source, recovery_metadata FROM data_gap")
    assert (gap["status"], gap["start_ts"], gap["end_ts"]) == ("recovered", TS, TS + timedelta(minutes=1))
    assert gap["detection_source"] == R.FUENTE and '"agg_id": [10, 12]' in gap["recovery_metadata"]

    # idempotente: una segunda pasada no encuentra nada que reponer y no cambia nada
    antes = await _celdas(conn, TS)
    assert await R.repone(conn, TS, hasta, trae=rest, escribe=True, log=lambda *_: None) == []
    assert await _celdas(conn, TS) == antes
    assert await conn.fetchval("SELECT count(*) FROM data_gap") == 1


async def test_el_contraste_compara_un_minuto_entero_sin_escribir(conn, monkeypatch):
    await _planta(conn)
    filas_m1 = [dict(f, T=f["T"] + 60_000) for f in _Rest().filas[:1]]   # una compra de 0.5 a 80000.5 en M+1

    def trae(url, params):
        return [f for f in filas_m1 if params["startTime"] <= f["T"] <= params["endTime"]]

    out = await R.contraste(conn, TS, TS + timedelta(minutes=5), 5, trae=trae, log=lambda *_: None)
    assert [(f["iguales"], f["distintos"]) for f in out] == [(False, ["80000", "80100"])]
    assert await _celdas(conn, TS + timedelta(minutes=1)) == [(D(80100), D(5), D(0), D(400500), D(0), 1, 0)]
