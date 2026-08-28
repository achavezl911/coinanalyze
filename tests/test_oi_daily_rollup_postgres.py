"""K67 · el resumen diario de OI, contra Postgres de verdad.

apply_retention borra open_interest y oi_bybit con un DELETE liso por antiguedad, sin la
exencion que ohlcv si tiene para interval='daily'. Con HARD_DATA_RETENTION_DAYS=90 en 140 y
la recoleccion arrancada el 2026-07-23, el primer dia se pierde el 2026-10-21 y a partir de
ahi la serie empieza un dia mas tarde cada dia SIN QUE NINGUNA CONSULTA FALLE. Estas pruebas
fijan las cuatro propiedades de las que depende que eso deje de ocurrir.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.daily_agg import (
    OI_DAILY_EXPECTED_SAMPLES,
    apply_retention,
    rollup_open_interest_daily,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SYMBOL = "BTCUSDT_PERP.A"


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"oi_daily_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    await connection.execute(
        "INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING"
    )
    await connection.execute(
        "INSERT INTO symbols(symbol,base_asset) VALUES($1,'BTC') ON CONFLICT DO NOTHING",
        SYMBOL,
    )
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


async def _muestra(conn, tabla: str, ts: datetime, valor: float) -> None:
    await conn.execute(
        f"INSERT INTO {tabla}(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close) "  # noqa: S608
        "VALUES($1,$2,'5min',$3,$3,$3,$3)",
        ts, SYMBOL, valor,
    )


async def _dia(conn, tabla: str, dia: datetime, valores: list[float]) -> None:
    for i, valor in enumerate(valores):
        await _muestra(conn, tabla, dia + timedelta(minutes=5 * i), valor)


@pytest.mark.asyncio
async def test_open_y_close_son_el_primer_y_ultimo_bucket_no_el_minimo_ni_el_maximo(conn):
    """El error que un recalculo perezoso no veria.

    Con la serie 30, 10, 50, 20 el minimo es 10 y el maximo 50, pero el open es 30 y el
    close es 20. Un min(oi_open) daria un numero que NUNCA EXISTIO a esa hora.
    """

    ayer = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await _dia(conn, "open_interest", ayer, [30.0, 10.0, 50.0, 20.0])

    await rollup_open_interest_daily(conn)

    fila = await conn.fetchrow(
        "SELECT * FROM open_interest_daily WHERE symbol=$1 AND source='coinalyze'", SYMBOL
    )
    assert fila is not None
    assert fila["oi_open"] == 30.0, "open es el PRIMER bucket, no el minimo"
    assert fila["oi_close"] == 20.0, "close es el ULTIMO bucket, no el maximo"
    assert fila["oi_high"] == 50.0
    assert fila["oi_low"] == 10.0
    assert fila["samples"] == 4
    assert fila["expected_samples"] == OI_DAILY_EXPECTED_SAMPLES
    assert fila["day"] == ayer.date()


@pytest.mark.asyncio
async def test_el_dia_en_curso_no_se_escribe_porque_su_close_aun_va_a_cambiar(conn):
    hoy = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    ayer = hoy - timedelta(days=1)
    await _dia(conn, "open_interest", ayer, [1.0, 2.0])
    await _dia(conn, "open_interest", hoy, [3.0, 4.0])

    await rollup_open_interest_daily(conn)

    dias = [r["day"] for r in await conn.fetch("SELECT day FROM open_interest_daily")]
    assert dias == [ayer.date()], "una fila que se reescribe sola no es un resumen"


@pytest.mark.asyncio
async def test_las_dos_fuentes_se_resumen_por_separado_y_el_rollup_es_idempotente(conn):
    ayer = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await _dia(conn, "open_interest", ayer, [10.0, 11.0])
    await _dia(conn, "oi_bybit", ayer, [90.0, 91.0])

    await rollup_open_interest_daily(conn)
    primera = await conn.fetch(
        "SELECT source,oi_open,oi_close,samples FROM open_interest_daily ORDER BY source"
    )
    await rollup_open_interest_daily(conn)
    segunda = await conn.fetch(
        "SELECT source,oi_open,oi_close,samples FROM open_interest_daily ORDER BY source"
    )

    assert [dict(r) for r in primera] == [
        {"source": "bybit", "oi_open": 90.0, "oi_close": 91.0, "samples": 2},
        {"source": "coinalyze", "oi_open": 10.0, "oi_close": 11.0, "samples": 2},
    ]
    # La segunda pasada no duplica ni cambia nada: el relleno hacia atras es la MISMA
    # sentencia que la pasada diaria, asi que correrla de mas no puede hacer dano.
    assert [dict(r) for r in segunda] == [dict(r) for r in primera]


@pytest.mark.asyncio
async def test_el_resumen_SOBREVIVE_al_purgado_que_se_lleva_sus_5min(conn):
    """La prueba que da sentido a todo lo demas.

    Se siembra un dia mas viejo que la retencion, se resume y se purga en el MISMO orden
    que cycle(). Los 5min desaparecen; el resumen tiene que seguir ahi. Si esto falla, la
    tabla no sirve para nada: el 2026-10-21 empezaria la perdida silenciosa igual.
    """

    viejo = (datetime.now(UTC) - timedelta(days=120)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await _dia(conn, "open_interest", viejo, [7.0, 8.0, 9.0])

    await rollup_open_interest_daily(conn)
    await apply_retention(conn, 90, 400, 30, 6, 30)

    quedan_5min = await conn.fetchval(
        "SELECT count(*) FROM open_interest WHERE (ts AT TIME ZONE 'UTC')::date=$1",
        viejo.date(),
    )
    resumen = await conn.fetchrow(
        "SELECT oi_open,oi_close,samples FROM open_interest_daily WHERE day=$1", viejo.date()
    )

    assert quedan_5min == 0, "el purgado tenia que llevarse los 5min de un dia de hace 120"
    assert resumen is not None, "el resumen NO puede irse con ellos: es toda su razon de ser"
    assert (resumen["oi_open"], resumen["oi_close"], resumen["samples"]) == (7.0, 9.0, 3)
