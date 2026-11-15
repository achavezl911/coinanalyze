"""A6 (DATOS A, hallazgos F4-I1/I3/I5): `upsert_liquidations` EJECUTADA contra una base desechable.

Hasta aqui ninguna prueba la corria (tests/test_ingest.py la sustituye con un monkeypatch) y tres
mutantes sobrevivian: largo/corto cruzados al guardar, el lado que falta leido como 0 y la fila con
un lado a cero tirada. Lo que se guarda en `liquidations` es lo que pinta la pantalla de 5 min.

El lado que falta: las columnas son NOT NULL (sql/schema.sql, tabla liquidations), asi que NULL no
cabe. El contrato es que NUNCA se escriba como 0: la fila se rechaza y el latido
ingest:liquidations_history sale degradado (`rejected_rows`), y sin latido ok el cubo vacio no se
certifica como cero (app/orderflow_lectura.py, ventana del latido).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import asyncpg
import pytest

from app.ingest import _liquidation_history_observation, upsert_liquidations

CANON = "BTCUSDT_PERP.A"
T0 = int(datetime(2026, 8, 28, 7, 45, tzinfo=UTC).timestamp())
MAPA = {CANON: CANON}


async def _conexion():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    return conn, tx


async def _filas(conn) -> dict[int, tuple[float, float]]:
    filas = await conn.fetch(
        "SELECT ts, long_liq, short_liq FROM liquidations WHERE symbol=$1 AND interval='5min' "
        "AND ts >= to_timestamp($2) ORDER BY ts", CANON, T0)
    return {int(f["ts"].timestamp()): (f["long_liq"], f["short_liq"]) for f in filas}


async def test_largo_y_corto_caen_cada_uno_en_su_columna():
    conn, tx = await _conexion()
    try:
        payload = {CANON: [{"t": T0, "l": 1500.5, "s": 7.25}, {"t": T0 + 300, "l": 0.0, "s": 300.0}]}
        assert await upsert_liquidations(conn, payload, MAPA, T0, T0 + 600) == 2
        assert await _filas(conn) == {T0: (1500.5, 7.25), T0 + 300: (0.0, 300.0)}
    finally:
        await tx.rollback()
        await conn.close()


async def test_un_lado_a_cero_se_guarda_y_no_se_tira():
    conn, tx = await _conexion()
    try:
        payload = {CANON: [{"t": T0, "l": 0.0, "s": 42.0}, {"t": T0 + 300, "l": 9.0, "s": 0}]}
        assert await upsert_liquidations(conn, payload, MAPA, T0, T0 + 600) == 2
        assert await _filas(conn) == {T0: (0.0, 42.0), T0 + 300: (9.0, 0.0)}
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.parametrize("falta", ["l", "s"])
async def test_el_lado_que_falta_nunca_se_escribe_como_cero(falta):
    conn, tx = await _conexion()
    try:
        coja = {"t": T0, "l": 11.0, "s": 22.0}
        del coja[falta]
        payload = {CANON: [coja, {"t": T0 + 300, "l": 1.0, "s": 2.0}]}
        aceptadas = await upsert_liquidations(conn, payload, MAPA, T0, T0 + 600)
        assert aceptadas == 1
        filas = await _filas(conn)
        assert T0 not in filas, f"la fila sin '{falta}' se guardo como {filas.get(T0)}"
        assert filas[T0 + 300] == (1.0, 2.0)
        # y la observacion lo declara: sin latido ok, el cubo vacio no es «cero liquidaciones»
        estado, detalle = _liquidation_history_observation(
            payload, (CANON,), accepted_rows=aceptadas,
            source_start=datetime.fromtimestamp(T0, tz=UTC),
            source_cutoff=datetime.fromtimestamp(T0 + 600, tz=UTC))
        assert estado == "degraded" and "rejected_rows" in detalle
    finally:
        await tx.rollback()
        await conn.close()


async def test_un_lado_nulo_o_negativo_tampoco_es_cero():
    conn, tx = await _conexion()
    try:
        payload = {CANON: [{"t": T0, "l": None, "s": 5.0}, {"t": T0 + 300, "l": 3.0, "s": -1.0}]}
        assert await upsert_liquidations(conn, payload, MAPA, T0, T0 + 600) == 0
        assert await _filas(conn) == {}
    finally:
        await tx.rollback()
        await conn.close()
