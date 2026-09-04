"""K52c · el minuto que desaparece del bucket, contra Postgres de verdad.

Un arranque de coinalyze-ws.service a las 05:20:58 deja al minuto 05:20 con UN segundo
util. Binance opera en ese segundo y bybit no, asi que ws_collector.py:288
-HAVING COUNT(DISTINCT exchange)=2- no emite la fila 'combined' de ese minuto. La ruta
lee exchange='combined', de modo que el minuto no sale ni corto ni sin marca: DESAPARECE,
y el bucket de 15 minutos se sirve con 14 y con covered_seconds_min=60, short_minutes=0 y
unknown_minutes=0, es decir IDENTICO a uno completo. Eso es fallar abierto.

Estas pruebas fijan las tres propiedades de las que depende que deje de ocurrir, y una
cuarta que protege al INSTRUMENTO: cero filas tiene que tener firma propia y no poder
leerse como un bucket sano. Esa cuarta esta aqui porque el SQL con el que se diagnostico
K52b filtraba symbol='BTCUSDT_PERP.A' sobre una tabla cuyos simbolos son BTC/ETH/SOL
-app/api.py:1020 traduce con WS_SYMBOL_MAP- y devolvia cero filas pase lo que pase, que se
lee exactamente igual que el fallo que se estaba buscando.

No reimplementan el SELECT: llaman a api.whale_delta con un pool de pega, asi que si el
SELECT de la ruta no cambia, estas pruebas no pueden ponerse verdes.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

import app.api as api

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

SIMBOLO = "BTCUSDT_PERP.A"          # lo que se le pide a la ruta
ACTIVO = "BTC"                      # lo que la ruta busca en la tabla (WS_SYMBOL_MAP)
BUCKET_A = datetime(2026, 9, 3, 5, 15, tzinfo=UTC)
BUCKET_B = datetime(2026, 9, 3, 5, 30, tzinfo=UTC)
MINUTO_DEL_ARRANQUE = 5             # 05:20, el minuto en que arranco el colector


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"k52c_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    await connection.execute(
        "INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING", ACTIVO
    )
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


class _Adquisicion:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    async def __aenter__(self):
        return self._conexion

    async def __aexit__(self, *_exc) -> bool:
        return False


class _PoolDePega:
    """Lo justo para que `async with app.state.pool.acquire() as conn` sea la conexion."""

    def __init__(self, conexion) -> None:
        self._conexion = conexion

    def acquire(self) -> _Adquisicion:
        return _Adquisicion(self._conexion)


async def _minuto(conn, ts: datetime, exchange: str, venue_count: int, covered: int) -> None:
    await conn.execute(
        "INSERT INTO spot_trades_agg("
        "  ts,symbol,exchange,venue_count,interval,buy_vol_usd,sell_vol_usd,"
        "  inst_buy_usd,inst_sell_usd,mid_buy_usd,mid_sell_usd,"
        "  retail_buy_usd,retail_sell_usd,trade_count,covered_seconds"
        ") VALUES($1,$2,$3,$4,'1min',100,40,100,40,0,0,0,0,10,$5)",
        ts, ACTIVO, exchange, venue_count, covered,
    )


async def _bucket(conn, inicio: datetime, *, hueco_en: int | None) -> None:
    """15 minutos en los tres exchanges. En `hueco_en`, SOLO binance y con 1 segundo.

    Es la forma exacta del 2026-09-03T05:20Z: el colector arranca en el segundo 58, binance
    opera en el segundo que queda y bybit no, asi que el HAVING de ws_collector.py:288 no
    emite el 'combined' de ese minuto.
    """
    for i in range(15):
        ts = inicio + timedelta(minutes=i)
        if i == hueco_en:
            await _minuto(conn, ts, "binance", 1, 1)
            continue
        await _minuto(conn, ts, "binance", 1, 60)
        await _minuto(conn, ts, "bybit", 1, 60)
        await _minuto(conn, ts, "combined", 2, 60)


async def _censo(conn, inicio: datetime) -> dict[str, int]:
    """LA PRUEBA DE QUE LA ADULTERACION OCURRIO, no solo el veredicto del test."""
    filas = await conn.fetch(
        "SELECT exchange, count(*)::int AS n FROM spot_trades_agg "
        " WHERE symbol=$1 AND interval='1min' AND ts >= $2 AND ts < $2 + interval '15 minutes'"
        " GROUP BY exchange ORDER BY exchange",
        ACTIVO, inicio,
    )
    censo = {f["exchange"]: f["n"] for f in filas}
    print(f"censo del fixture en {inicio:%H:%MZ}: {censo}")
    return censo


async def _servir(conn, monkeypatch) -> dict:
    assert SIMBOLO in api.SETTINGS.SYMBOLS, "el fixture pide un simbolo que la config no sirve"
    monkeypatch.setattr(api.app.state, "pool", _PoolDePega(conn), raising=False)
    return await api.whale_delta(symbol=SIMBOLO, interval="15min", limit=384)


def _viejos(fila: dict) -> tuple:
    return fila["covered_seconds_min"], fila["short_minutes"], fila["unknown_minutes"]


async def test_el_minuto_que_no_llega_a_combined_se_cuenta_en_minutes_present(conn, monkeypatch):
    """BRAZOS R y V. Sin el campo esto revienta con KeyError, que no se puede aflojar."""
    await _bucket(conn, BUCKET_A, hueco_en=MINUTO_DEL_ARRANQUE)
    await _bucket(conn, BUCKET_B, hueco_en=None)

    # 1 · la adulteracion, ANTES de mirar la ruta: al bucket A le falta el combined del 05:20.
    assert await _censo(conn, BUCKET_A) == {"binance": 15, "bybit": 14, "combined": 14}
    assert await _censo(conn, BUCKET_B) == {"binance": 15, "bybit": 15, "combined": 15}

    sobre = await _servir(conn, monkeypatch)
    filas = sobre["rows"]
    # 2 · cero filas NO es un pase. Si el filtro se equivoca de simbolo, se cae aqui.
    assert filas != [], "la ruta no devolvio filas: el fixture o el filtro estan mal"
    assert len(filas) == 2
    a, b = filas
    assert (a["bucket"], b["bucket"]) == (BUCKET_A, BUCKET_B)

    # 3 · EL FALLO ABIERTO, documentado: los tres campos viejos NO distinguen 14 de 15.
    assert _viejos(a) == _viejos(b) == (60, 0, 0)

    # 4 · y el unico campo que si los distingue.
    print(f"A={a['minutes_present']} B={b['minutes_present']}")
    assert a["minutes_present"] == 14
    assert b["minutes_present"] == 15


async def test_control_positivo_un_bucket_entero_dice_quince(conn, monkeypatch):
    """BRAZO C. El mismo bucket, el mismo codigo, el hueco RELLENO: tiene que decir 15.

    Sin esta prueba, `minutes_present` cableado a 14 -o a cualquier constante- compraria el
    verde de la anterior. Con las dos, ningun valor constante satisface a las dos.
    """
    await _bucket(conn, BUCKET_A, hueco_en=None)
    assert await _censo(conn, BUCKET_A) == {"binance": 15, "bybit": 15, "combined": 15}

    sobre = await _servir(conn, monkeypatch)
    assert sobre["rows"] != []
    fila = sobre["rows"][0]
    assert fila["minutes_present"] == 15
    assert _viejos(fila) == (60, 0, 0)


async def test_cero_filas_tiene_firma_propia_y_no_se_lee_como_completo(conn, monkeypatch):
    """BRAZO Z. Control del INSTRUMENTO, no del sujeto.

    La tabla existe y esta vacia para este simbolo. La respuesta tiene que NOMBRARLO
    -status 'no_data' y rows vacio- en vez de parecerse a una serie sana. Es la leccion del
    SQL con el simbolo equivocado, puesta en codigo.
    """
    sobre = await _servir(conn, monkeypatch)
    assert sobre["rows"] == []
    assert sobre["data_gaps"]["status"] == "no_data"
    assert sobre["coverage"]["served_window"] is None
