"""ESQUEMA R1 (V-03) · re-aplicar sql/schema.sql sobre una base al dia no espera a las escrituras vivas.

El despliegue de 98dca1d aborto (rc=6) con un interbloqueo en el DROP/CREATE TRIGGER de
liquidations_realtime: el envoltorio de 140 re-aplica el esquema entero con los colectores escribiendo, y
cada CREATE INDEX IF NOT EXISTS, ADD COLUMN IF NOT EXISTS, DROP/ADD CONSTRAINT o CREATE TRIGGER toma su
bloqueo (Share, ShareRowExclusive o AccessExclusive) ANTES de mirar si hay algo que hacer. Ahora esas
ordenes pasan por esquema_ddl(), que mira el catalogo (sin bloqueo) y solo ejecuta lo que falta.
Aqui: una sesion deja un INSERT sin confirmar en liquidations_realtime (RowExclusive retenido) y, en otra
prueba, ademas una retencion a medias (DROP de una particion caducada sin confirmar). Re-aplicar con
lock_timeout de 5 s termina. Las mismas ordenes ejecutadas a pelo, como las ejecutaba main, se quedan
esperando. Banco contra el schema.sql de main y control de base nueva: entregas/*-esquema-r1.md.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
ORDEN = re.compile(r"SELECT esquema_ddl\(\$ddl\$(.*?)\$ddl\$", re.S)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _sesion(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    return conn


@pytest.fixture
async def base():
    schema = f"esquema_r1_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    conn_s = await _sesion(schema)
    await conn_s.execute(SCHEMA_SQL)
    await conn_s.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
    await conn_s.execute("INSERT INTO symbols(symbol, base_asset) VALUES('BTCUSDT', 'BTC') ON CONFLICT DO NOTHING")
    ahora = datetime.now(UTC)
    await conn_s.fetchval("SELECT ensure_temporal_partitions($1, 0, 0)", ahora)
    await conn_s.fetchval("SELECT ensure_temporal_partitions($1, 0, 0)", ahora - timedelta(days=5))
    await conn_s.close()
    try:
        yield schema
    finally:
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def _retiene(schema: str, *, retencion: bool) -> asyncpg.Connection:
    """Una transaccion abierta con un INSERT en liquidations_realtime y, si se pide, el DROP de la particion
    caducada (lo que deja drop_expired_temporal_partitions a medio camino)."""
    viva = await _sesion(schema)
    await viva.execute("BEGIN")
    await viva.execute(
        "INSERT INTO liquidations_realtime(ts, symbol, exchange, side, notional_usd, price, qty, event_id)"
        " VALUES(now(), 'BTCUSDT', 'binance', 'long', 1000, 100000, 0.01, $1)",
        uuid.uuid4().hex,
    )
    if retencion:
        tiradas = await viva.fetchval(
            "SELECT drop_expired_temporal_partitions('liquidations_realtime', now() - interval '2 days')"
        )
        assert tiradas == 1
    return viva


def _ordenes_de_liquidaciones() -> list[str]:
    ordenes = [o for o in ORDEN.findall(SCHEMA_SQL) if re.search(r"\bliquidations_realtime\b", o)]
    assert any("liquidations_realtime_event_unique_trigger" in o for o in ordenes)
    return ordenes


@pytest.mark.parametrize("retencion", [False, True], ids=["insert", "insert+retencion"])
async def test_reaplicar_no_espera_a_las_escrituras_vivas(base, retencion: bool) -> None:
    viva = await _retiene(base, retencion=retencion)
    otra = await _sesion(base)
    try:
        await otra.execute("SET lock_timeout = '5s'")
        t0 = time.monotonic()
        await otra.execute(SCHEMA_SQL)
        assert time.monotonic() - t0 < 5
        # la transaccion viva no se ha enterado: sigue abierta y confirma
        await viva.execute("COMMIT")
        assert await otra.fetchval("SELECT count(*) FROM liquidations_realtime") == 1
    finally:
        await viva.close()
        await otra.close()


async def test_las_mismas_ordenes_a_pelo_esperan(base) -> None:
    """El control: lo que salva es la guarda. Cada orden de liquidations_realtime sin esquema_ddl() (como
    en main) pide un bloqueo que choca con el RowExclusive del INSERT vivo, salvo COMMENT, que toma
    ShareUpdateExclusive y no choca."""
    viva = await _retiene(base, retencion=False)
    otra = await _sesion(base)
    esperan, pasan = [], []
    try:
        for orden in _ordenes_de_liquidaciones():
            tx = otra.transaction()
            await tx.start()
            try:
                await otra.execute("SET LOCAL lock_timeout = '1s'")
                await otra.execute(orden)
                pasan.append(orden)
            except asyncpg.exceptions.LockNotAvailableError:
                esperan.append(orden)
            finally:
                await tx.rollback()
    finally:
        await viva.execute("ROLLBACK")
        await viva.close()
        await otra.close()
    assert esperan and all(o.startswith("COMMENT ON ") for o in pasan), pasan
    assert any("liquidations_realtime_event_unique_trigger" in o for o in esperan)
