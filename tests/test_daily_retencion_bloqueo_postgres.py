"""MANT R1 · un bloqueo momentaneo en la retencion no tumba el ciclo del diario.

El despliegue 45129996802 (7b16e8a) revirtio solo: tras el reinicio, coinalyze-daily corrio
apply_retention -> apply_temporal_retention (DDL con bloqueo exclusivo sobre la madre
particionada), salto LockNotAvailableError por el lock_timeout de 3 s, el ciclo entero quedo en
'error', healthz paso a 'degraded' y la prueba de humo revirtio (rc 86). Basta una consulta con
la tabla abierta.

Aqui una segunda conexion mantiene ACCESS SHARE sobre spot_trades_realtime (lo que deja
cualquier SELECT dentro de una transaccion) mientras el ciclo corre con un lock_timeout corto:
el ciclo tiene que acabar en 'ok', con la particion vieja en su sitio y el aviso en el detalle;
soltado el bloqueo, el ciclo siguiente la retira. Con el codigo de main, el primer ciclo cae.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app import daily_agg

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


class _Pool:
    """Lo unico que cycle() pide al pool: acquire() como contexto."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    @asynccontextmanager
    async def acquire(self):
        yield self._conn


class _Cliente:
    """Coinalyze sin red: ninguna vela nueva. Lo que se mide es la retencion, no la descarga."""

    async def history(self, *args, **kwargs) -> dict:
        return {}


@pytest.fixture
async def base():
    schema = f"mant_r1_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    await conn.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
    try:
        yield conn, schema
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def _particion_vieja(conn: asyncpg.Connection) -> datetime:
    """Una fila de hace 5 dias en su particion: muy por encima de los 48 h que admite la config."""
    vieja = datetime.now(UTC) - timedelta(days=5)
    await conn.fetchval("SELECT ensure_temporal_partitions($1,0,0)", vieja)
    await conn.execute(
        """
        INSERT INTO spot_trades_realtime(
          ts,symbol,exchange,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,
          trade_count,last_px,last_event_ms
        ) VALUES($1,'BTC','binance',1,1,0,0,1,100,0)
        """,
        vieja,
    )
    return vieja


async def _particiones(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM pg_inherits WHERE inhparent = 'spot_trades_realtime'::regclass"
    )


async def _latido(conn: asyncpg.Connection) -> asyncpg.Record:
    return await conn.fetchrow(
        "SELECT status, detail FROM pipeline_heartbeat WHERE service='daily'"
    )


async def test_un_bloqueo_en_la_retencion_aplaza_y_no_deja_el_ciclo_en_error(base) -> None:
    conn, schema = base
    vieja = await _particion_vieja(conn)
    antes = await _particiones(conn)
    await conn.execute("SET lock_timeout = '300ms'")

    bloqueo = await asyncpg.connect(_dsn())
    try:
        await bloqueo.execute(f'SET search_path TO "{schema}", public')
        tx = bloqueo.transaction()
        await tx.start()
        await bloqueo.execute("LOCK TABLE spot_trades_realtime IN ACCESS SHARE MODE")

        # Con main esto lanza LockNotAvailableError y el bucle de run() marca 'error'.
        await daily_agg.cycle(_Pool(conn), _Cliente(), None)

        latido = await _latido(conn)
        assert latido["status"] == "ok"
        assert "retencion=aplazada_bloqueo" in latido["detail"]
        assert await _particiones(conn) == antes
        assert await conn.fetchval(
            "SELECT count(*) FROM spot_trades_realtime WHERE ts=$1", vieja
        ) == 1
        # El SAVEPOINT devolvio la transaccion del ciclo a su sitio: lo de antes de la
        # retencion se escribio (el latido va despues, en la misma conexion).
        await tx.rollback()
    finally:
        await bloqueo.close()

    # Soltado el bloqueo, el ciclo siguiente la retira.
    await daily_agg.cycle(_Pool(conn), _Cliente(), None)
    latido = await _latido(conn)
    assert latido["status"] == "ok"
    assert "retencion=aplicada" in latido["detail"]
    assert await _particiones(conn) < antes
    assert await conn.fetchval("SELECT count(*) FROM spot_trades_realtime WHERE ts=$1", vieja) == 0


async def test_otro_error_de_la_retencion_sigue_siendo_error(base, monkeypatch) -> None:
    """Solo el bloqueo se aplaza: cualquier otro fallo de la retencion sigue tumbando el ciclo."""
    conn, _schema = base

    async def rota(*args, **kwargs) -> None:
        raise asyncpg.exceptions.UndefinedTableError("relation does not exist")

    monkeypatch.setattr(daily_agg, "apply_retention", rota)
    with pytest.raises(asyncpg.exceptions.UndefinedTableError):
        await daily_agg.cycle(_Pool(conn), _Cliente(), None)


async def test_el_primer_ciclo_tras_arrancar_no_corre_la_retencion(base) -> None:
    """El primer ciclo va a los 45 s del arranque, en mitad del despliegue: la retencion espera
    al ciclo alineado de la hora siguiente."""
    conn, _schema = base
    vieja = await _particion_vieja(conn)
    antes = await _particiones(conn)
    await daily_agg.cycle(_Pool(conn), _Cliente(), None, aplicar_retencion=False)
    latido = await _latido(conn)
    assert latido["status"] == "ok"
    assert "retencion=primer_ciclo" in latido["detail"]
    assert await _particiones(conn) == antes
    assert await conn.fetchval("SELECT count(*) FROM spot_trades_realtime WHERE ts=$1", vieja) == 1


def test_run_pasa_el_primer_ciclo_sin_retencion() -> None:
    source = (ROOT / "app/daily_agg.py").read_text(encoding="utf-8")
    run = source[source.index("async def run()") :]
    assert "aplicar_retencion=not primer_ciclo" in run
