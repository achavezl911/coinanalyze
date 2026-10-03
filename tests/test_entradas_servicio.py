"""C2 f de la campana 135 · el generador NO ESTORBA a la recoleccion.

En produccion el generador vive en coinalyze-ingest, cuyo bucle de eventos recoge ohlcv 1min y
las metricas con app.ingest.run_aligned_feed; los trades y el libro los recogen OTROS procesos
(coinalyze-scalp y coinalyze-ws), asi que lo unico que puede estorbar es compartir el bucle de
ingest. Aqui se reproduce eso: un recolector con el planificador REAL de ingest (cadencia 1 s,
una fila por tick) y, a la vez, una pasada plantada que:

  - TARDA mas que su tope (y que un tick): duerme 4 s con tope de 1 s;
  - QUEMA CPU 3 s en su hilo (compite por el GIL);
  - LANZA una excepcion.

En los tres la cadencia del recolector antes, durante y despues es la misma (filas por ventana),
el fallo queda en entrada_latido, y una segunda pasada mientras la primera vive se SALTA.
"""

from __future__ import annotations

import asyncio
import os
import time
from types import SimpleNamespace

import asyncpg
import pytest

from app.entradas import servicio as S
from app.ingest import run_aligned_feed


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _latidos(desde_id: int) -> list[dict]:
    conn = await asyncpg.connect(_dsn())
    try:
        filas = await conn.fetch(
            "SELECT latido_id, estado, detalle::text AS detalle FROM entrada_latido "
            "WHERE latido_id > $1 ORDER BY latido_id", desde_id)
        return [dict(f) for f in filas]
    finally:
        await conn.close()


async def _ultimo_latido() -> int:
    conn = await asyncpg.connect(_dsn())
    try:
        tabla = await conn.fetchval("SELECT to_regclass('entrada_latido')")
        if tabla is None:
            pytest.skip("la base de prueba no tiene schema.sql en public (CI lo aplica)")
        return await conn.fetchval("SELECT coalesce(max(latido_id), 0) FROM entrada_latido")
    finally:
        await conn.close()


async def _con_recolector(plantar, fases: tuple[float, float, float]) -> tuple[list[int], list[float]]:
    """Recolector con el planificador real de ingest; devuelve filas por fase y los instantes."""
    stop = asyncio.Event()
    marcas: list[float] = []

    async def recoge() -> None:
        marcas.append(time.monotonic())

    tarea = asyncio.create_task(
        run_aligned_feed(stop, recoge, cadence_seconds=1, offset_seconds=0, name="recolector")
    )
    t0 = time.monotonic()
    await asyncio.sleep(fases[0])
    t1 = time.monotonic()
    await plantar()
    await asyncio.sleep(max(0.0, fases[1] - (time.monotonic() - t1)))
    t2 = time.monotonic()
    await asyncio.sleep(fases[2])
    t3 = time.monotonic()
    stop.set()
    await tarea
    cuenta = [sum(1 for m in marcas if a <= m < b) for a, b in ((t0, t1), (t1, t2), (t2, t3))]
    return cuenta, [round(t1 - t0, 2), round(t2 - t1, 2), round(t3 - t2, 2)]


async def test_el_control_condena_un_generador_mal_alojado_que_bloquea_el_bucle():
    """A57: la variable que decide es DONDE corre el trabajo. El mismo sueño de 4 s ejecutado en
    el bucle de ingest (como un callback mas) tiene que tumbar la cadencia, o el control no mide."""

    async def plantar() -> None:
        time.sleep(4)  # en el bucle, sin hilo: lo que el diseño evita

    cuenta, duraciones = await _con_recolector(plantar, (3.0, 4.0, 3.0))
    por_segundo = [c / d for c, d in zip(cuenta, duraciones, strict=True)]
    print(f"mal alojado: filas por fase {cuenta} en {duraciones} s -> {por_segundo}")
    assert min(por_segundo) < 0.6 * max(por_segundo), (cuenta, duraciones)


@pytest.mark.parametrize("plantado", ["lento", "cpu", "lanza"])
async def test_un_generador_plantado_no_toca_la_cadencia_y_su_fallo_queda_servido(plantado):
    ajustes = SimpleNamespace(pg_dsn=_dsn())
    desde = await _ultimo_latido()

    def lento() -> None:
        time.sleep(4)

    def cpu() -> None:
        fin = time.monotonic() + 3
        x = 0
        while time.monotonic() < fin:
            x += 1

    def lanza() -> None:
        raise RuntimeError("generador plantado que lanza")

    objetivo = {"lento": lento, "cpu": cpu, "lanza": lanza}[plantado]

    async def plantar() -> None:
        await S.pasada(ajustes, objetivo=objetivo, tope_s=1)
        if plantado == "lento":
            await S.pasada(ajustes, objetivo=lento, tope_s=1)  # la primera sigue viva: se salta

    cuenta, duraciones = await _con_recolector(plantar, (3.0, 4.0, 3.0))
    por_segundo = [c / d for c, d in zip(cuenta, duraciones, strict=True)]
    print(f"{plantado}: filas por fase {cuenta} en {duraciones} s -> {por_segundo}")
    assert min(por_segundo) >= 0.6 * max(por_segundo), (plantado, cuenta, duraciones)
    while S._EN_CURSO.locked():  # deja que el hilo plantado acabe antes del siguiente caso
        await asyncio.sleep(0.2)
    estados = [f["estado"] for f in await _latidos(desde)]
    esperado = {"lento": ["tope", "saltado"], "cpu": ["tope"], "lanza": ["error"]}[plantado]
    assert sorted(estados) == sorted(esperado), estados
