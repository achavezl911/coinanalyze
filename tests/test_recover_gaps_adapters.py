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
from app.data_gaps import DataGap, RecoveryValidationError
from scripts.recover_gaps import (
    PLANES_METRICA,
    CoinalyzeLongShortAdapter,
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

    # long_short_ratio ya NO sirve de ejemplo: desde #112 tiene adaptador propio. Se
    # cambia por un feed que de verdad no lo tiene, en vez de borrar el caso.
    assert exact_adapter_for(_gap(feed="liquidations"), adaptadores, permitidos) is None
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

    # +2: el de ohlcv 1min y el de long_short, que tienen escritor propio
    assert len(adaptadores) == len(PLANES_METRICA) + 2
    identidades = [(p.feed, p.exchange) for p in PLANES_METRICA]
    assert len(identidades) == len(set(identidades))


def test_long_short_ratio_TIENE_adaptador_pero_NO_plan_y_se_dice_por_que():
    """Sigue fuera de PLANES_METRICA, y ahora por escrito con su alternativa al lado.

    Su tabla no es (o,h,l,c) sino long_pct/short_pct/ratio, o sea otro escritor
    (upsert_long_short). Si alguien lo anade a PLANES_METRICA sin cambiar el escritor,
    upsert_ohlc_metric lo rechaza por su lista blanca -- pero este test lo dice antes. Lo
    que NO puede pasar ya es que quede sin via: el hueco de 136 buckets del 2026-08-28 no
    se pudo recuperar por falta de este adaptador.
    """
    assert all(p.feed != "long_short_ratio" for p in PLANES_METRICA)
    adaptadores = construir_adaptadores(ClienteFalso())
    assert ("long_short_ratio", "binance", "perpetual", "5min") in adaptadores


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


# --- long_short_ratio: el feed que NO cabia en el plan generico -------------------------


class ClienteFalsoLongShort:
    """Devuelve posicionamiento (l/s/r), que es lo que este endpoint publica."""

    def __init__(self, filas=None) -> None:
        self.llamadas: list[dict] = []
        self.filas = filas

    async def history(self, endpoint, symbols, **kwargs):
        self.llamadas.append({"endpoint": endpoint, "symbols": list(symbols), **kwargs})
        clave = list(symbols)[0]
        if self.filas is not None:
            return {clave: self.filas}
        return {
            clave: [
                {"t": int(INICIO.timestamp()), "l": 60.0, "s": 40.0, "r": 1.5},
                {
                    "t": int((INICIO + timedelta(minutes=5)).timestamp()),
                    "l": 45.0, "s": 55.0, "r": 0.818,
                },
            ]
        }


def _gap_ls(**cambios) -> DataGap:
    return _gap(feed="long_short_ratio", granularity="5min", **cambios)


@pytest.mark.asyncio
async def test_long_short_se_pide_al_endpoint_de_posicionamiento_y_con_el_canonico():
    """binance no traduce, pero se fija de que ENDPOINT sale: pedirlo a ohlcv-history
    devolveria precio donde tiene que haber reparto de la multitud."""
    cliente = ClienteFalsoLongShort()
    adaptador = CoinalyzeLongShortAdapter(cliente)

    observaciones = await adaptador.fetch(_gap_ls())

    assert cliente.llamadas[0]["endpoint"] == "long-short-ratio-history"
    assert cliente.llamadas[0]["symbols"] == [CANON]
    assert cliente.llamadas[0]["interval"] == "5min"
    assert [o.symbol for o in observaciones] == [CANON, CANON]
    assert [o.feed for o in observaciones] == ["long_short_ratio"] * 2


@pytest.mark.asyncio
async def test_long_short_NO_pide_convert_to_usd():
    """Un porcentaje no se convierte a dolares. El plan generico lleva convert_to_usd
    porque el interes abierto lo necesita; aqui no existe el parametro y es correcto."""
    cliente = ClienteFalsoLongShort()

    await CoinalyzeLongShortAdapter(cliente).fetch(_gap_ls())

    assert "convert_to_usd" not in cliente.llamadas[0]


@pytest.mark.asyncio
async def test_postgres_la_fila_incoherente_hace_FALLAR_la_recuperacion_entera():
    """EL SILENCIO DE upsert_long_short ES VENENO AQUI, y este es el test que lo fija.

    upsert_long_short descarta sin avisar la fila cuyo l+s se aleja de 100 (ingest.py).
    En el ciclo vivo eso es correcto -- mejor no tener el dato que inventar el reparto --.
    Aqui seria dejar el hueco marcado 'recovered' con MENOS buckets de los que
    validate_recovery acaba de exigir: un VERDE cuya evidencia es un conteo que encogio.
    La comparacion count != len(observations) lo convierte en fallo duro.
    """
    import os

    import asyncpg

    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    cliente = ClienteFalsoLongShort(filas=[
        {"t": int(INICIO.timestamp()), "l": 60.0, "s": 40.0, "r": 1.5},
        # l+s = 130, o sea que no es un reparto. upsert_long_short la tira en silencio.
        {"t": int((INICIO + timedelta(minutes=5)).timestamp()),
         "l": 60.0, "s": 70.0, "r": 0.857},
    ])
    adaptador = CoinalyzeLongShortAdapter(cliente)
    observaciones = await adaptador.fetch(_gap_ls())
    assert len(observaciones) == 2, "la fuente mando dos y el adaptador no filtra"

    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        with pytest.raises(RecoveryValidationError):
            await adaptador.persist(conn, observaciones)
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_la_recuperacion_de_long_short_aterriza_en_su_tabla():
    """Donde aterriza el dato, con el reparto intacto y no convertido a otra unidad."""
    import os

    import asyncpg

    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    tx = conn.transaction()
    await tx.start()
    try:
        adaptador = CoinalyzeLongShortAdapter(ClienteFalsoLongShort())
        observaciones = await adaptador.fetch(_gap_ls())
        await adaptador.persist(conn, observaciones)

        fila = await conn.fetchrow(
            "SELECT symbol, long_pct, short_pct, ratio FROM long_short_ratio "
            "WHERE ts=$1 AND interval='5min' AND symbol=$2", INICIO, CANON
        )
        assert fila is not None, "tiene que caer en long_short_ratio"
        assert fila["symbol"] == CANON
        assert (fila["long_pct"], fila["short_pct"]) == (60.0, 40.0)
    finally:
        await tx.rollback()
        await conn.close()
