"""K64/K04 · el adaptador generico de metricas, y sobre todo su identidad de simbolo.

EL AVISO QUE ORIGINA ESTE FICHERO, medido por el operador: upsert_ohlc_metric es UNA
funcion pero NO es UN SOLO MAPA. El ciclo vivo le pasa `identity` para open_interest,
funding_rate y predicted_funding_rate, y `bybit_inverse` para oi_bybit (ingest.py:792-794
y :840). La identidad hay que traducirla en LOS DOS SENTIDOS -- canonico->proveedor para
PEDIR y proveedor->canonico para GUARDAR -- y equivocar el segundo es la trampa de #108
una capa mas abajo.

Aqui se prueba con un cliente falso que CAPTURA la peticion, porque lo que hay que fijar
es exactamente eso: con QUE simbolo se pide y con CUAL se guarda.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import BYBIT_SYMBOL_MAP
from app.data_gaps import DataGap
from scripts.recover_gaps import (
    PLANES_METRICA,
    CoinalyzeMetricAdapter,
    construir_adaptadores,
    exact_adapter_for,
)

CANON = "BTCUSDT_PERP.A"
INICIO = datetime(2026, 8, 28, 7, 45, tzinfo=UTC)


class ClienteFalso:
    """Captura la peticion y devuelve dos buckets bajo la clave que le pidieron."""

    def __init__(self) -> None:
        self.llamadas: list[dict] = []

    async def history(self, endpoint, symbols, **kwargs):
        self.llamadas.append({"endpoint": endpoint, "symbols": list(symbols), **kwargs})
        clave = list(symbols)[0]
        return {
            clave: [
                {"t": int(INICIO.timestamp()), "o": 1.0, "h": 1.0, "l": 1.0, "c": 1.0},
                {
                    "t": int((INICIO + timedelta(minutes=5)).timestamp()),
                    "o": 2.0, "h": 2.0, "l": 2.0, "c": 2.0,
                },
            ]
        }


def _gap(**cambios) -> DataGap:
    base = {
        "id": 1,
        "feed": "open_interest_5min",
        "feed_class": "cadence",
        "exchange": "binance",
        "market": "perpetual",
        "symbol": CANON,
        "granularity": "5min",
        "start": INICIO,
        "end": INICIO + timedelta(minutes=10),
        "expected_cadence": timedelta(minutes=5),
        "status": "unresolved",
    }
    base.update(cambios)
    return DataGap(**base)


def _plan(feed: str, exchange: str):
    for plan in PLANES_METRICA:
        if (plan.feed, plan.exchange) == (feed, exchange):
            return plan
    raise AssertionError(f"sin plan para {feed}@{exchange}")


# --- LA IDENTIDAD, EN LOS DOS SENTIDOS --------------------------------------------------


@pytest.mark.asyncio
async def test_bybit_se_PIDE_con_el_simbolo_del_proveedor():
    """El proveedor quiere BTCUSDT.6 en el MISMO endpoint que binance. Pedirle el canonico
    devolveria 200 con datos de BINANCE y los guardariamos como bybit."""
    cliente = ClienteFalso()
    adaptador = CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "bybit"))

    await adaptador.fetch(_gap(exchange="bybit"))

    assert cliente.llamadas[0]["symbols"] == [BYBIT_SYMBOL_MAP[CANON]]
    assert BYBIT_SYMBOL_MAP[CANON] != CANON


@pytest.mark.asyncio
async def test_bybit_se_GUARDA_con_el_simbolo_canonico():
    """La otra direccion. validate_recovery compara la identidad de cada observacion
    contra la del hueco, asi que dejar el simbolo del proveedor aqui hace reventar la
    recuperacion -- y si algun dia no reventara, lo guardaria mal."""
    cliente = ClienteFalso()
    adaptador = CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "bybit"))

    observaciones = await adaptador.fetch(_gap(exchange="bybit"))

    assert observaciones, "el adaptador tiene que ver las filas que devolvio el proveedor"
    assert {o.symbol for o in observaciones} == {CANON}
    assert all(o.exchange == "bybit" for o in observaciones)


@pytest.mark.asyncio
async def test_binance_pide_y_guarda_el_canonico_sin_traducir():
    cliente = ClienteFalso()
    adaptador = CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "binance"))

    observaciones = await adaptador.fetch(_gap())

    assert cliente.llamadas[0]["symbols"] == [CANON]
    assert {o.symbol for o in observaciones} == {CANON}


# --- LA UNIDAD ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_el_interes_abierto_se_pide_convertido_a_usd_y_el_funding_no():
    """convert_to_usd NO es un detalle. El ciclo vivo pide open-interest-history con
    convert_to_usd=True (ingest.py:796-805) y funding/predicted sin el. Recuperar el
    interes abierto sin la conversion guardaria OTRA UNIDAD en la misma columna y nada
    reventaria: una fila que parece buena y no lo es."""
    cliente = ClienteFalso()

    await CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "binance")).fetch(_gap())
    await CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "bybit")).fetch(
        _gap(exchange="bybit")
    )
    await CoinalyzeMetricAdapter(cliente, _plan("funding_rate", "binance")).fetch(
        _gap(feed="funding_rate")
    )
    await CoinalyzeMetricAdapter(cliente, _plan("predicted_funding_rate", "binance")).fetch(
        _gap(feed="predicted_funding_rate")
    )

    assert [ll["convert_to_usd"] for ll in cliente.llamadas] == [True, True, None, None]
    assert [ll["endpoint"] for ll in cliente.llamadas] == [
        "open-interest-history", "open-interest-history",
        "funding-rate-history", "predicted-funding-rate-history",
    ]


# --- EL REGISTRO Y SUS NEGATIVAS ---------------------------------------------------------


def test_las_dos_bolsas_del_mismo_feed_son_adaptadores_DISTINTOS():
    """Si el registro se indexara solo por feed, un hueco de bybit se recuperaria contra la
    tabla open_interest y al reves. Comparten endpoint: lo unico que los separa es el
    simbolo que piden y la tabla en la que escriben."""
    adaptadores = construir_adaptadores(ClienteFalso())
    permitidos = frozenset({CANON})

    binance = exact_adapter_for(_gap(), adaptadores, permitidos)
    bybit = exact_adapter_for(_gap(exchange="bybit"), adaptadores, permitidos)

    assert binance is not None and bybit is not None
    assert binance is not bybit
    assert binance.plan.table == "open_interest"
    assert bybit.plan.table == "oi_bybit"
    assert binance.plan.endpoint == bybit.plan.endpoint


def test_una_identidad_no_registrada_devuelve_None_en_vez_de_adivinar():
    """Caer a None marca el hueco irrecuperable; adivinarle adaptador lo guardaria en la
    tabla equivocada, que es peor que no recuperarlo."""
    adaptadores = construir_adaptadores(ClienteFalso())
    permitidos = frozenset({CANON})

    assert exact_adapter_for(_gap(feed="long_short_ratio"), adaptadores, permitidos) is None
    assert exact_adapter_for(_gap(exchange="okx"), adaptadores, permitidos) is None
    assert exact_adapter_for(_gap(granularity="1min"), adaptadores, permitidos) is None
    assert exact_adapter_for(_gap(market="spot"), adaptadores, permitidos) is None


def test_un_simbolo_fuera_de_los_configurados_no_se_recupera():
    adaptadores = construir_adaptadores(ClienteFalso())

    assert exact_adapter_for(_gap(), adaptadores, frozenset({"ETHUSDT_PERP.A"})) is None


def test_el_registro_no_admite_dos_adaptadores_para_la_misma_identidad():
    """Guarda contra el crecimiento distraido de PLANES_METRICA: dos planes con la misma
    identidad dejarian que el ultimo pisara al primero en silencio."""
    adaptadores = construir_adaptadores(ClienteFalso())

    assert len(adaptadores) == len(PLANES_METRICA) + 1  # +1 el de ohlcv 1min
    identidades = [(p.feed, p.exchange) for p in PLANES_METRICA]
    assert len(identidades) == len(set(identidades))


def test_long_short_ratio_NO_tiene_plan_y_se_dice_por_que():
    """No es un olvido: su tabla no es (o,h,l,c) sino long_pct/short_pct/ratio, o sea otro
    escritor. Si alguien lo anade a PLANES_METRICA sin cambiar el escritor,
    upsert_ohlc_metric lo rechaza por su lista blanca -- pero este test lo dice antes."""
    assert all(p.feed != "long_short_ratio" for p in PLANES_METRICA)


def test_las_tablas_y_prefijos_son_los_que_acepta_el_escritor():
    """La lista blanca de upsert_ohlc_metric (ingest.py:250) es un conjunto CERRADO de
    cuatro parejas. Declarar aqui una que no este seria escribir en la tabla equivocada o
    reventar en produccion en vez de en la prueba."""
    permitidas = {
        ("open_interest", "oi"), ("oi_bybit", "oi"),
        ("funding_rate", "fr"), ("predicted_funding_rate", "pfr"),
    }
    assert {(p.table, p.prefix) for p in PLANES_METRICA} == permitidas


@pytest.mark.asyncio
async def test_postgres_la_recuperacion_de_bybit_aterriza_en_oi_bybit_con_el_canonico():
    """DONDE ATERRIZA EL DATO, que es lo unico que las pruebas con cliente falso no dicen.

    Las dos bolsas comparten endpoint y se diferencian en la tabla y en el simbolo. Este
    test escribe de verdad y comprueba las dos cosas a la vez: que la fila cae en
    oi_bybit y NO en open_interest, y que su symbol es el CANONICO -- que es lo que el
    ciclo vivo guarda con bybit_inverse (ingest.py:840) y lo que leen las consultas.
    Dentro de una transaccion que termina en ROLLBACK.
    """
    import os

    import asyncpg

    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        cliente = ClienteFalso()
        adaptador = CoinalyzeMetricAdapter(cliente, _plan("open_interest_5min", "bybit"))
        gap = _gap(exchange="bybit")
        observaciones = await adaptador.fetch(gap)

        antes_binance = await conn.fetchval(
            "SELECT count(*) FROM open_interest WHERE ts=$1 AND symbol=$2", INICIO, CANON
        )
        await adaptador.persist(conn, observaciones)

        fila = await conn.fetchrow(
            "SELECT symbol, oi_close FROM oi_bybit WHERE ts=$1 AND interval='5min' "
            "AND symbol=$2", INICIO, CANON
        )
        assert fila is not None, "la recuperacion de bybit tiene que caer en oi_bybit"
        assert fila["symbol"] == CANON
        assert await conn.fetchval(
            "SELECT count(*) FROM open_interest WHERE ts=$1 AND symbol=$2", INICIO, CANON
        ) == antes_binance, "y NO puede tocar la tabla de binance"
    finally:
        await tx.rollback()
        await conn.close()
