"""K68b · el resumen de 5min, contra Postgres de verdad.

EL DEFECTO MEDIDO. El ciclo del ingest llama a rollup_ohlcv_5m con los MISMOS limites
que usa para pedirle datos al proveedor -40 minutos-, o sea que su alcance va atado a la
RESPUESTA y no al ALMACENAMIENTO. Un 1min que llegue mas tarde por recuperacion no
produce nunca su vela de 5. La noche del 2026-08-29 se recuperaron 4464 buckets de 1min
del apagon y el 5min se quedo con 1440 huecos, 894 de ellos con sus CINCO minutos ya
guardados esperando a que alguien los resumiera.

Y EL AGUJERO NO ESPERA: el 1min se borra a los HARD_DATA_RETENTION_DAYS (90 en 140) y el
5min aguanta HTF_DATA_RETENTION_DAYS (400). Pasados los 90 dias ya no hay con que
construir la vela, asi que el hueco queda fijado en la serie de 5min durante 400 dias.

LA PREGUNTA QUE ESTAS PRUEBAS CONTESTAN, y que no se contesta citando el codigo. De los
1440 buckets ausentes, 894 tienen los cinco minutos, 528 no tienen ninguno y 18 son
PARCIALES, con entre 1 y 4. Si el barrido pasara sobre esos 18 sin exigir los cinco,
fabricaria velas de 5min hechas con 1 a 4 minutos y las serviria como completas: menos
volumen, menos rango y un delta mas pequeno, indistinguibles de una vela cerrada. Es K37
literal -- una ausencia convertida en dato CORTO que la metrica cuenta como presente.
La guarda existe (HAVING COUNT(*) = 5 en app/ingest.py) pero AQUI SE INDUCE EL CASO en
vez de citarla, porque una guarda que nadie ha visto actuar es una promesa.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.daily_agg import apply_retention, ventana_barrido_5m
from app.ingest import rollup_ohlcv_5m

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SYMBOL = "BTCUSDT_PERP.A"
SYMBOLS = (SYMBOL,)

# Un borde de bucket de 5 minutos, lejos del presente para que nada vivo lo toque.
BUCKET = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"ohlcv_5m_{uuid.uuid4().hex}"
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


async def _sembrar_minutos(conn, base: datetime, minutos: list[int], *, volumen: float = 10.0):
    """Escribe 1min sueltos. `minutos` son offsets dentro del bucket de cinco."""
    for m in minutos:
        ts = base + timedelta(minutes=m)
        await conn.execute(
            """
            INSERT INTO ohlcv(ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx)
            VALUES($1,$2,'1min',100,101,99,100.5,$3,$4,7,3)
            """,
            ts,
            SYMBOL,
            volumen,
            volumen / 2,
        )


async def _velas_5min(conn, base: datetime):
    return await conn.fetch(
        "SELECT ts,volume,tx FROM ohlcv WHERE symbol=$1 AND interval='5min' AND ts=$2",
        SYMBOL,
        base,
    )


def _ventana(base: datetime) -> tuple[int, int]:
    return int(base.timestamp()), int((base + timedelta(minutes=5)).timestamp())


@pytest.mark.parametrize("cuantos", [1, 2, 3, 4])
async def test_un_bucket_incompleto_no_se_construye(conn, cuantos):
    """EL CASO INDUCIDO. Con 1 a 4 minutos no puede nacer una vela de 5.

    Se recorren los cuatro grados de incompletitud a proposito: un fallo que solo
    apareciera con 4 de 5 -el mas parecido a una vela buena, y por tanto el mas dificil
    de ver despues- pasaria desapercibido si solo se probara con 1.
    """
    await _sembrar_minutos(conn, BUCKET, list(range(cuantos)))
    ini, fin = _ventana(BUCKET)

    construidas = await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin)

    assert construidas == 0
    assert await _velas_5min(conn, BUCKET) == []


async def test_con_los_cinco_minutos_si_se_construye(conn):
    """CONTROL POSITIVO. Sin esto, un rollup que no construyera NADA pasaria la prueba
    de arriba con nota, y seria un instrumento muerto que parece una guarda."""
    await _sembrar_minutos(conn, BUCKET, [0, 1, 2, 3, 4])
    ini, fin = _ventana(BUCKET)

    construidas = await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin)

    filas = await _velas_5min(conn, BUCKET)
    assert construidas == 1
    assert len(filas) == 1
    # La vela suma los cinco minutos: 5 x 10 de volumen y 5 x 7 de tx. Si alguna vez se
    # construyera con cuatro, este numero lo dice en vez de callarselo.
    assert float(filas[0]["volume"]) == pytest.approx(50.0)
    assert filas[0]["tx"] == 35


async def test_el_minuto_que_falta_completa_la_vela_despues(conn):
    """El bucket incompleto no se pierde: se queda esperando. Cuando la recuperacion
    trae el minuto que faltaba, la MISMA funcion lo resuelve sin nada especial."""
    await _sembrar_minutos(conn, BUCKET, [0, 1, 2, 3])
    ini, fin = _ventana(BUCKET)
    assert await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin) == 0

    await _sembrar_minutos(conn, BUCKET, [4])

    assert await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin) == 1
    assert len(await _velas_5min(conn, BUCKET)) == 1


async def test_el_barrido_alcanza_lo_que_la_ventana_viva_no(conn):
    """LA REGRESION DEL DEFECTO. Con la ventana de la peticion -40 minutos- un bucket
    viejo no se resume jamas; con la del barrido si. Es el fallo entero, en una prueba."""
    ahora = datetime.now(UTC).replace(second=0, microsecond=0)
    viejo = (ahora - timedelta(days=30)).replace(minute=0)
    await _sembrar_minutos(conn, viejo, [0, 1, 2, 3, 4])

    ventana_viva = await rollup_ohlcv_5m(
        conn,
        SYMBOLS,
        int((ahora - timedelta(minutes=40)).timestamp()),
        int(ahora.timestamp()),
    )
    assert ventana_viva == 0
    assert await _velas_5min(conn, viejo) == []

    barrido = await rollup_ohlcv_5m(
        conn,
        SYMBOLS,
        int((ahora - timedelta(days=91)).timestamp()),
        int(ahora.timestamp()),
        only_missing=True,
    )
    assert barrido == 1
    assert len(await _velas_5min(conn, viejo)) == 1


async def test_only_missing_no_reescribe_lo_que_ya_existe(conn):
    """only_missing cambia UNA cosa y solo una: si lo existente se pisa. Se comprueba
    en los dos sentidos, porque un flag que no hace nada pasa igual de bien la mitad
    de las pruebas."""
    await _sembrar_minutos(conn, BUCKET, [0, 1, 2, 3, 4])
    ini, fin = _ventana(BUCKET)
    await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin)
    await conn.execute(
        "UPDATE ohlcv SET volume=999 WHERE symbol=$1 AND interval='5min' AND ts=$2",
        SYMBOL,
        BUCKET,
    )

    await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin, only_missing=True)
    filas = await _velas_5min(conn, BUCKET)
    assert float(filas[0]["volume"]) == pytest.approx(999.0)

    await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin, only_missing=False)
    filas = await _velas_5min(conn, BUCKET)
    assert float(filas[0]["volume"]) == pytest.approx(50.0)


async def test_only_missing_sigue_exigiendo_los_cinco_minutos(conn):
    """La guarda es la MISMA por los dos caminos. Si algun dia se parte la consulta en
    dos, esta prueba es la que lo caza: el barrido es justo el camino que recorre datos
    viejos y parciales, o sea donde mas dano haria una vela corta."""
    await _sembrar_minutos(conn, BUCKET, [0, 1, 2, 3])
    ini, fin = _ventana(BUCKET)

    construidas = await rollup_ohlcv_5m(conn, SYMBOLS, ini, fin, only_missing=True)

    assert construidas == 0
    assert await _velas_5min(conn, BUCKET) == []


async def test_el_resumen_va_antes_de_la_purga_o_la_vela_no_nace_jamas(conn):
    """EL ORDEN DENTRO DEL CICLO, fijado igual que en K67.

    Los cinco minutos tienen 90.5 dias: apply_retention con hard=90 los borra, pero el
    5min aguanta htf=400. Resumiendo ANTES la vela nace y sobrevive a la purga de sus
    propios ingredientes. Al reves no habria nada que resumir, y el hueco quedaria en la
    serie de 5min 400 dias -- sin que ninguna consulta fallara.
    """
    viejo = (datetime.now(UTC) - timedelta(days=90, hours=12)).replace(
        minute=0, second=0, microsecond=0
    )
    await _sembrar_minutos(conn, viejo, [0, 1, 2, 3, 4])
    ventana = (
        int((datetime.now(UTC) - timedelta(days=91)).timestamp()),
        int(datetime.now(UTC).timestamp()),
    )

    await rollup_ohlcv_5m(conn, SYMBOLS, *ventana, only_missing=True)
    await apply_retention(conn, 90, 400, 30, 48, 30)

    assert len(await _velas_5min(conn, viejo)) == 1
    restantes_1min = await conn.fetchval(
        "SELECT count(*) FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts>=$2",
        SYMBOL,
        viejo,
    )
    assert restantes_1min == 0


def test_la_ventana_del_barrido_contiene_lo_que_la_purga_va_a_borrar():
    """El dia de mas no es holgura: es lo que hace que el orden signifique algo.

    apply_retention borra el 1min anterior a now()-hard_days. Si el barrido empezara
    justo ahi, lo que esta a punto de borrarse ya estaria fuera de su alcance y ponerlo
    antes de la purga no protegeria de nada. Se exige que el inicio sea ESTRICTAMENTE
    anterior al corte, que es la unica propiedad de la que depende la colocacion.
    """
    ahora = datetime(2026, 8, 30, 3, 45, tzinfo=UTC)
    hard_days = 90
    inicio, fin = ventana_barrido_5m(ahora, hard_days)

    corte_purga = int((ahora - timedelta(days=hard_days)).timestamp())
    assert inicio < corte_purga
    assert fin == int(ahora.timestamp())
    assert corte_purga - inicio == 86400


async def test_el_orden_inverso_pierde_la_vela(conn):
    """CONTROL NEGATIVO del orden. Sin esto, la prueba de arriba pasaria aunque el orden
    diera igual, y no probaria nada sobre la colocacion de la llamada."""
    viejo = (datetime.now(UTC) - timedelta(days=90, hours=12)).replace(
        minute=0, second=0, microsecond=0
    )
    await _sembrar_minutos(conn, viejo, [0, 1, 2, 3, 4])
    ventana = (
        int((datetime.now(UTC) - timedelta(days=91)).timestamp()),
        int(datetime.now(UTC).timestamp()),
    )

    await apply_retention(conn, 90, 400, 30, 48, 30)
    await rollup_ohlcv_5m(conn, SYMBOLS, *ventana, only_missing=True)

    assert await _velas_5min(conn, viejo) == []
