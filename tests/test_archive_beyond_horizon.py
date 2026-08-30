"""K69 · la decision de archivar por horizonte agotado, y sobre todo sus dos negativas.

Lo que archive_beyond_source_horizon ESCRIBE ya esta fijado contra la re-derivacion de
K04 en test_data_gaps_postgres.py. Lo que aqui se prueba es lo otro: CUANDO se llama y
cuando hay que negarse, que es donde el archivado en falso entra si nadie mira.

Las dos negativas valen mas que el caso bueno. Un archivador que archiva siempre pasa
cualquier prueba del caso bueno, y es exactamente la herramienta que la noche del
2026-08-29 dejo 10 filas sin prueba.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.data_gaps import DataGap
from scripts.archive_beyond_horizon import SONDA_POR_FEED, decidir


def _gap(**cambios) -> DataGap:
    base = {
        "id": 1,
        "feed": "ohlcv_1min",
        "feed_class": "cadence",
        "exchange": "binance",
        "market": "perpetual",
        "symbol": "BTCUSDT_PERP.A",
        "granularity": "1min",
        "start": datetime(2026, 8, 28, 7, 46, tzinfo=UTC),
        "end": datetime(2026, 8, 28, 21, 2, tzinfo=UTC),
        "expected_cadence": timedelta(minutes=1),
        "status": "unresolved",
    }
    base.update(cambios)
    return DataGap(**base)


def test_se_archiva_cuando_la_ventana_esta_vacia_y_el_control_responde():
    """El caso bueno: la fuente contesta hoy y no contesta aquello. Eso, y solo eso,
    distingue un horizonte agotado de una caida."""
    veredicto = decidir(_gap(), filas_ventana=0, filas_control=120)

    assert veredicto.accion == "archivar"
    assert "control 120" in veredicto.motivo


def test_no_se_archiva_si_la_fuente_TODAVIA_sirve_la_ventana():
    """LA NEGATIVA QUE MAS IMPORTA. Archivar un hueco recuperable es mentir en la tabla
    y ademas tirar la unica oportunidad de traer el dato: el horizonte se cierra solo."""
    veredicto = decidir(_gap(), filas_ventana=796, filas_control=120)

    assert veredicto.accion == "rechazar"
    assert "796" in veredicto.motivo
    assert "recover_gaps.py" in veredicto.motivo


def test_no_se_archiva_si_el_control_esta_mudo():
    """Una fuente callada no prueba ausencia, solo silencio. Sin esto, una caida del
    proveedor barreria el backlog entero a 'unrecoverable' con aspecto de prueba."""
    veredicto = decidir(_gap(), filas_ventana=0, filas_control=0)

    assert veredicto.accion == "rechazar"
    assert "silencio" in veredicto.motivo


def test_las_dos_negativas_se_evaluan_en_orden_util():
    """Con la ventana servida Y el control mudo gana el mensaje de la ventana: es el que
    dice que hay dato que rescatar, y perderlo por un mensaje sobre el control seria
    quedarse con la mitad menos accionable."""
    veredicto = decidir(_gap(), filas_ventana=10, filas_control=0)

    assert veredicto.accion == "rechazar"
    assert "recover_gaps.py" in veredicto.motivo


def test_un_feed_no_declarado_se_rechaza_en_vez_de_adivinarle_endpoint():
    """Adivinar el endpoint mal daria CERO filas por la razon equivocada, y eso es una
    prueba falsa con formato de prueba buena. Misma regla que el method desconocido de
    K04: lo que no se sabe verificar se para, no se deja pasar."""
    veredicto = decidir(_gap(feed="long_short_ratio"), filas_ventana=0, filas_control=120)

    assert veredicto.accion == "rechazar"
    assert "no declarado" in veredicto.motivo


def test_un_flujo_de_eventos_no_se_archiva_por_esta_via():
    """feed_class='event_stream' no tiene cadencia que sondear: su ausencia no se mide
    contando filas de una ventana."""
    veredicto = decidir(
        _gap(feed_class="event_stream", expected_cadence=None), filas_ventana=0, filas_control=120
    )

    assert veredicto.accion == "rechazar"
    assert "cadencia" in veredicto.motivo


def test_el_mapa_de_feeds_solo_declara_lo_que_se_ha_medido():
    """Guarda contra el crecimiento distraido del mapa: cada entrada nueva exige haber
    medido el horizonte de ESE intervalo, que es la leccion que costo el tramo mudo."""
    assert set(SONDA_POR_FEED) == {"ohlcv_1min"}
    assert SONDA_POR_FEED["ohlcv_1min"] == ("ohlcv-history", "1min")
