"""K69/K71 · la decision de archivar, y sobre todo sus TRES negativas.

Lo que las dos funciones ESCRIBEN esta fijado contra la re-derivacion de K04 en
test_data_gaps_postgres.py. Lo que aqui se prueba es lo otro: CUAL de los dos archivados
toca, y cuando hay que negarse, que es donde el archivado en falso entra si nadie mira.

Las negativas valen mas que el caso bueno. Un archivador que archiva siempre pasa
cualquier prueba del caso bueno, y es exactamente la herramienta que la noche del
2026-08-29 dejo 10 filas sin prueba.

LO QUE CAMBIA EN K71: la sonda pide una ventana ANCHA, no la del hueco. Una ventana de
cinco minutos vacia es AMBIGUA -- se lee igual si el horizonte se agoto que si la fuente
sirve el tramo y no publica ese bucket --, y son dos hechos distintos con dos pruebas
distintas. Y el mapa se indexa por (feed, exchange), porque data_gap guarda el simbolo
CANONICO para las dos bolsas y el proveedor quiere uno distinto para cada una.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.config import BYBIT_SYMBOL_MAP
from app.data_gaps import DataGap
from scripts.archive_beyond_horizon import (
    SONDA_POR_FEED,
    Sondeo,
    decidir,
    simbolo_de_proveedor,
)

INICIO = datetime(2026, 8, 28, 7, 45, tzinfo=UTC)
FIN = datetime(2026, 8, 28, 19, 5, tzinfo=UTC)


def _gap(**cambios) -> DataGap:
    base = {
        "id": 1,
        "feed": "ohlcv_1min",
        "feed_class": "cadence",
        "exchange": "binance",
        "market": "perpetual",
        "symbol": "BTCUSDT_PERP.A",
        "granularity": "1min",
        "start": INICIO,
        "end": FIN,
        "expected_cadence": timedelta(minutes=1),
        "status": "unresolved",
    }
    base.update(cambios)
    return DataGap(**base)


def _vacia() -> Sondeo:
    """La ancha vuelve del todo vacia: la fuente ya no sirve ni el tramo ni sus bordes."""
    return Sondeo(filas_dentro=0, ancha_filas=0, primera=None, ultima=None)


def _rodea() -> Sondeo:
    """La ancha trae buckets ANTES del inicio y DESPUES del final, y cero dentro."""
    return Sondeo(
        filas_dentro=0,
        ancha_filas=44,
        primera=INICIO - timedelta(hours=1),
        ultima=FIN + timedelta(hours=1),
    )


# --- LOS DOS CASOS BUENOS, que son DOS y no uno -----------------------------------------


def test_ancha_vacia_y_control_vivo_es_horizonte_agotado():
    veredicto = decidir(_gap(), sondeo=_vacia(), filas_control=120)

    assert veredicto.accion == "archivar_horizonte"
    assert "120" in veredicto.motivo


def test_ancha_que_rodea_el_hueco_es_ausencia_de_la_fuente_y_NO_horizonte():
    """LA DISTINCION QUE JUSTIFICA TODO EL CAMBIO. Los dos casos vuelven vacios DENTRO del
    hueco; solo la ventana ancha los separa. Medido en 140 el 2026-08-30: 4 de las 99
    filas caen aqui y archivarlas como horizonte habria pasado K04 siendo falso, porque
    el proveedor sirve ese tramo hoy mismo."""
    veredicto = decidir(_gap(), sondeo=_rodea(), filas_control=120)

    assert veredicto.accion == "archivar_ausencia"
    assert "RODEAN" in veredicto.motivo


# --- LAS TRES NEGATIVAS -----------------------------------------------------------------


def test_no_se_archiva_si_la_fuente_TODAVIA_sirve_la_ventana():
    """LA NEGATIVA QUE MAS IMPORTA. Archivar un hueco recuperable es mentir en la tabla y
    ademas tirar la unica oportunidad de traer el dato: el horizonte se cierra solo."""
    sondeo = Sondeo(
        filas_dentro=136, ancha_filas=200, primera=INICIO - timedelta(hours=1), ultima=FIN
    )
    veredicto = decidir(_gap(), sondeo=sondeo, filas_control=120)

    assert veredicto.accion == "rechazar"
    assert "136" in veredicto.motivo
    assert "recuperable" in veredicto.motivo


def test_no_se_archiva_si_el_control_esta_mudo():
    """Una fuente callada no prueba ausencia, solo silencio. Sin esto, una caida del
    proveedor barreria el backlog entero a 'unrecoverable' con aspecto de prueba."""
    veredicto = decidir(_gap(), sondeo=_vacia(), filas_control=0)

    assert veredicto.accion == "rechazar"
    assert "silencio" in veredicto.motivo


def test_no_se_archiva_si_la_ancha_responde_pero_NO_rodea_el_hueco():
    """El hueco pegado a la frontera del proveedor. Hay respuesta, asi que no es
    horizonte; no cubre el tramo, asi que no prueba ausencia. Es el caso que COLA.md tenia
    contado como 'las 11 del 08-17 en la ventana que CRUZA la frontera'. Sin esta negativa
    caeria por la rama de ausencia con un straddle que no existe."""
    sondeo = Sondeo(
        filas_dentro=0,
        ancha_filas=30,
        primera=INICIO + timedelta(minutes=5),  # empieza DENTRO del hueco
        ultima=FIN + timedelta(hours=1),
    )
    veredicto = decidir(_gap(), sondeo=sondeo, filas_control=120)

    assert veredicto.accion == "rechazar"
    assert "NO rodea" in veredicto.motivo


def test_tampoco_rodea_si_la_respuesta_termina_antes_del_final_del_hueco():
    """El otro lado del mismo borde: empieza antes pero se corta dentro."""
    sondeo = Sondeo(
        filas_dentro=0,
        ancha_filas=30,
        primera=INICIO - timedelta(hours=1),
        ultima=FIN - timedelta(minutes=5),
    )
    veredicto = decidir(_gap(), sondeo=sondeo, filas_control=120)

    assert veredicto.accion == "rechazar"
    assert "NO rodea" in veredicto.motivo


def test_las_negativas_se_evaluan_en_orden_util():
    """Con la ventana servida Y el control mudo gana el mensaje de la ventana: es el que
    dice que hay dato que rescatar, y perderlo por un mensaje sobre el control seria
    quedarse con la mitad menos accionable."""
    sondeo = Sondeo(filas_dentro=10, ancha_filas=10, primera=INICIO, ultima=FIN)
    veredicto = decidir(_gap(), sondeo=sondeo, filas_control=0)

    assert veredicto.accion == "rechazar"
    assert "recuperable" in veredicto.motivo


def test_una_pareja_no_declarada_se_rechaza_en_vez_de_adivinarle_endpoint():
    """Adivinar el endpoint mal daria CERO filas por la razon equivocada, y eso es una
    prueba falsa con formato de prueba buena. Misma regla que el method desconocido de
    K04: lo que no se sabe verificar se para, no se deja pasar."""
    veredicto = decidir(
        _gap(feed="orderbook_snapshot"), sondeo=_vacia(), filas_control=120
    )

    assert veredicto.accion == "rechazar"
    assert "no esta declarada" in veredicto.motivo


def test_el_exchange_forma_parte_de_la_llave_y_no_solo_el_feed():
    """open_interest_5min esta declarado para binance y bybit, pero un tercer exchange con
    el MISMO feed no hereda la entrada: si la llave fuera solo el feed, un hueco de okx se
    sondearia con el endpoint de otra bolsa y se archivaria con esa prueba."""
    veredicto = decidir(
        _gap(feed="open_interest_5min", exchange="okx"), sondeo=_vacia(), filas_control=120
    )

    assert veredicto.accion == "rechazar"
    assert "'okx'" in veredicto.motivo


def test_un_flujo_de_eventos_no_se_archiva_por_esta_via():
    """feed_class='event_stream' no tiene cadencia que sondear: su ausencia no se mide
    contando filas de una ventana."""
    veredicto = decidir(
        _gap(feed_class="event_stream", expected_cadence=None),
        sondeo=_vacia(),
        filas_control=120,
    )

    assert veredicto.accion == "rechazar"
    assert "cadencia" in veredicto.motivo


# --- LA IDENTIDAD DEL PROVEEDOR ---------------------------------------------------------


def test_bybit_se_sondea_con_el_simbolo_de_bybit_y_binance_con_el_canonico():
    """EL FALLO QUE ESTE CAMBIO CIERRA. data_gap guarda BTCUSDT_PERP.A para las dos
    bolsas; el proveedor quiere BTCUSDT.6 para bybit en el MISMO endpoint. Pedirle el
    canonico devuelve 200 con datos de BINANCE: una respuesta plausible sobre el feed
    equivocado, que es peor que un error. Medido en 140 el 2026-08-30, las dos bolsas
    difieren 54.3 % en BTC."""
    canonico = "BTCUSDT_PERP.A"

    assert simbolo_de_proveedor("open_interest_5min", "binance", canonico) == canonico
    assert simbolo_de_proveedor("open_interest_5min", "bybit", canonico) == (
        BYBIT_SYMBOL_MAP[canonico]
    )
    assert BYBIT_SYMBOL_MAP[canonico] != canonico


def test_un_simbolo_sin_traduccion_de_bybit_revienta_en_vez_de_caer_al_canonico():
    """El fallback silencioso es justo el fallo: devolver el canonico cuando falta la
    traduccion mediria binance y archivaria el hueco de bybit con esa prueba."""
    with pytest.raises(KeyError):
        simbolo_de_proveedor("open_interest_5min", "bybit", "NO_EXISTE_PERP.A")


def test_el_mapa_declara_las_parejas_medidas_y_ninguna_mas():
    """Guarda contra el crecimiento distraido del mapa: cada entrada exige haber medido el
    horizonte de ESE intervalo contra el proveedor, que es la leccion que costo el tramo
    mudo del 08-28. Todas las de aqui estan sondeadas en hechos.tsv del 2026-08-30."""
    assert set(SONDA_POR_FEED) == {
        ("ohlcv_1min", "binance"),
        ("ohlcv_5min", "binance"),
        ("long_short_ratio", "binance"),
        ("funding_rate", "binance"),
        ("predicted_funding_rate", "binance"),
        ("open_interest_5min", "binance"),
        ("open_interest_5min", "bybit"),
    }
    assert SONDA_POR_FEED[("ohlcv_1min", "binance")] == ("ohlcv-history", "1min")
    assert SONDA_POR_FEED[("ohlcv_5min", "binance")] == ("ohlcv-history", "5min")
    # Las dos bolsas comparten endpoint e intervalo: lo unico que las separa es el simbolo
    # que se pide, y por eso la traduccion no es un detalle sino LA guarda.
    assert (
        SONDA_POR_FEED[("open_interest_5min", "binance")]
        == SONDA_POR_FEED[("open_interest_5min", "bybit")]
    )
