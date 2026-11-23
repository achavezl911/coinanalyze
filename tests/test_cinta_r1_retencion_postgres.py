"""CINTA R1 (V-02) · la retencion tira las particiones caducadas aunque el recorte del borde caiga.

En 140 (11-22/11-23) orderflow_cinta guardaba 65 M filas para una retencion de 48 h: la unica sentencia de
apply_temporal_retention hacia el DROP y el DELETE del borde en la misma transaccion, el DELETE pasaba del
command_timeout del pool y el ROLLBACK se llevaba tambien el DROP. Aqui se fija el contrato nuevo: el DROP se
confirma en su transaccion ANTES de recortar, el recorte va por tramos acotados que respetan el corte, y el
presupuesto corta la vuelta sin deshacer nada. La forma real (millones de filas, timeout de 3 s, main contra la
rama) se midio en banco: entregas/*-cinta-r1.md.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

import asyncpg
import pytest

from app import partitioning
from app.partitioning import apply_temporal_retention

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def base():
    schema = f"cinta_r1_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    try:
        yield conn
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def _cinta(conn: asyncpg.Connection, marcas: list[datetime]) -> None:
    for marca in marcas:
        await conn.fetchval("SELECT ensure_temporal_partitions($1,0,0)", marca)
    await conn.executemany(
        "INSERT INTO orderflow_cinta(ts, venue, symbol, precio, base, usd, compra, id)"
        " VALUES($1, 'binance_usdm', 'BTC', 100000, 0.01, 1000, true, $2)",
        [(m, f"t{i}") for i, m in enumerate(marcas)],
    )


def _montaje() -> tuple[datetime, datetime, list[datetime]]:
    """Un dia entero caducado (D-4), la particion del borde (la del corte de 48 h) con filas a los dos lados
    del corte, y lo reciente."""
    ahora = datetime.now(UTC)
    vieja = ahora - timedelta(days=4)
    borde = datetime.combine((ahora - timedelta(hours=48)).date(), time(), UTC)
    filas = [vieja, borde, borde + timedelta(seconds=1), ahora - timedelta(hours=47), ahora - timedelta(hours=1)]
    return vieja, borde, filas


async def _existe(conn: asyncpg.Connection, dia: datetime) -> bool:
    return await conn.fetchval("SELECT to_regclass($1)", f"orderflow_cinta_p{dia:%Y%m%d}") is not None


async def test_un_tramo_que_cae_no_deshace_el_drop(base) -> None:
    conn = base
    vieja, borde, filas = _montaje()
    await _cinta(conn, filas)
    entradas = 0

    @asynccontextmanager
    async def transaccion():
        nonlocal entradas
        entradas += 1
        async with conn.transaction():
            if entradas == 2:  # el primer tramo del borde: como el command_timeout de 140
                raise TimeoutError
            yield

    with pytest.raises(TimeoutError):
        await apply_temporal_retention(conn, "orderflow_cinta", 48, transaccion=transaccion)

    # Con main, el ROLLBACK del DELETE se llevaba el DROP: la particion vieja seguia ahi.
    assert not await _existe(conn, vieja)
    # El tramo que cayo no borro nada: lo caducado del borde espera a la vuelta siguiente.
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta WHERE ts = $1", borde) == 1
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == len(filas) - 1


async def test_los_tramos_borran_lo_caducado_y_nada_mas(base, monkeypatch) -> None:
    conn = base
    monkeypatch.setattr(partitioning, "BLOQUES_POR_TRAMO", 1)  # muchos tramos con pocas filas
    vieja, borde, filas = _montaje()
    paso = ((datetime.now(UTC) - timedelta(hours=47)) - borde) / 3000
    filas += [borde + i * paso for i in range(3000)]
    await _cinta(conn, filas)
    bloques = await conn.fetchval(
        "SELECT pg_relation_size($1::regclass) / current_setting('block_size')::bigint", f"orderflow_cinta_p{borde:%Y%m%d}")
    assert bloques > 3

    r = await apply_temporal_retention(conn, "orderflow_cinta", 48)

    caducadas = sum(1 for f in filas if f < r.corte and f.date() >= borde.date())
    assert (r.tiradas, r.borradas, r.completa) == (1, caducadas, True)
    assert not await _existe(conn, vieja)
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta WHERE ts < $1", r.corte) == 0
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == sum(1 for f in filas if f >= r.corte)


async def test_el_presupuesto_corta_sin_deshacer_el_drop(base, monkeypatch) -> None:
    conn = base
    monkeypatch.setattr(partitioning, "PRESUPUESTO_S", 0.0)
    vieja, borde, filas = _montaje()
    await _cinta(conn, filas)

    r = await apply_temporal_retention(conn, "orderflow_cinta", 48)

    assert (r.tiradas, r.borradas, r.completa) == (1, 0, False)
    assert not await _existe(conn, vieja)
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == len(filas) - 1


async def test_el_tope_adelanta_el_corte(base) -> None:
    conn = base
    vieja, borde, filas = _montaje()
    await _cinta(conn, filas)

    r = await apply_temporal_retention(conn, "orderflow_cinta", 48, tope=vieja - timedelta(days=1))

    assert (r.tiradas, r.borradas) == (0, 0)
    assert await _existe(conn, vieja)
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == len(filas)


async def test_el_tramo_solo_toca_hijas_diarias_de_tablas_gestionadas(base) -> None:
    conn = base
    _vieja, borde, filas = _montaje()
    await _cinta(conn, filas)
    hija = f"orderflow_cinta_p{borde:%Y%m%d}"
    corte = datetime.now(UTC)
    with pytest.raises(asyncpg.RaiseError, match="not managed by temporal partitioning"):
        await conn.fetchval("SELECT podar_temporal_tramo('signal_observation', $1, $2, 0, 10)", hija, corte)
    with pytest.raises(asyncpg.RaiseError, match="is not a daily partition of"):
        await conn.fetchval("SELECT podar_temporal_tramo('orderflow_celda', $1, $2, 0, 10)", hija, corte)
    with pytest.raises(asyncpg.RaiseError, match="tramo invalido"):
        await conn.fetchval("SELECT podar_temporal_tramo('orderflow_cinta', $1, $2, -1, 10)", hija, corte)
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == len(filas)


async def test_la_guarda_de_celda_para_en_la_primera_hora_sin_sumar(base) -> None:
    """Requisito 3 de V-02: las horas de orderflow_celda (lo que lee suma_horas) que caducan sin las marcas de los
    nueve venues no se tiran. Con la config de hoy (celda 30 d, horas 23 d) la ventana esta vacia; aqui, 48 h / 3 d."""
    from app.orderflow import ACTIVOS, SIN_SUMAR_SQL, VENUES_CELDA

    conn = base
    args = (48, 3, list(ACTIVOS), len(VENUES_CELDA))
    primera = await conn.fetchval(
        "SELECT date_bin(interval '1 hour', now() - interval '3 days', timestamptz '2000-01-01') + interval '1 hour'")
    assert await conn.fetchval(SIN_SUMAR_SQL, *args) == primera
    await conn.execute(
        "INSERT INTO orderflow_hora_hecha(ts, venue, symbol)"
        " SELECT h, v, s FROM generate_series($1::timestamptz, now() - interval '48 hours', interval '1 hour') h,"
        " unnest($2::text[]) v, unnest($3::text[]) s",
        primera, list(VENUES_CELDA), list(ACTIVOS))
    assert await conn.fetchval(SIN_SUMAR_SQL, *args) is None
    hueco = primera + timedelta(hours=5)
    await conn.execute("DELETE FROM orderflow_hora_hecha WHERE ts = $1 AND symbol = 'SOL' AND venue = 'okx_swap'", hueco)
    assert await conn.fetchval(SIN_SUMAR_SQL, *args) == hueco
