"""La ventana `desde`/`hasta`: un solo parser para las cuatro rutas que la aceptan.

Lo que se prueba no es que exista el parametro, sino las dos cosas que lo hacen util: que un
fin FIJO se pueda auditar, y que un fin ABIERTO diga que instante uso.
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api import declara_ventana, ventana_pedida

# El caso de prueba: viernes 09:30Z -> domingo 17:00Z.
VIERNES = "2026-09-04T09:30:00+00:00"
DOMINGO = "2026-09-07T17:00:00+00:00"


def test_ventana_con_fin_fijo_es_auditable():
    """El fin va fijo A PROPOSITO: una ventana que acaba en now() no se puede volver a pedir."""
    a, b = ventana_pedida(VIERNES, DOMINGO)
    sobre = {}
    declara_ventana(sobre, a, b)
    sobre = sobre["ventana_servida"]
    assert sobre["fin_abierto"] is False
    assert sobre["auditable"] is True
    assert sobre["desde"] == VIERNES and sobre["hasta"] == DOMINGO
    assert "manda la ventana pedida" in sobre["nota"]


def test_fin_abierto_ECHA_EL_INSTANTE_QUE_USO():
    """El panel tiene que saber hacer las dos cosas. La abierta no es auditable, y lo DICE,
    pero devuelve el instante para poder repetirla cerrada."""
    a, b = ventana_pedida(VIERNES, None)
    antes = datetime.now(UTC)
    sobre = {}
    declara_ventana(sobre, a, b)
    sobre = sobre["ventana_servida"]
    assert b is None and sobre["fin_abierto"] is True and sobre["auditable"] is False
    assert datetime.fromisoformat(sobre["hasta"]) >= antes
    assert "hay que repetir" in sobre["nota"]


def test_sin_ventana_no_se_declara_ninguna():
    """Sin `desde` manda el retroceso `days`, y anunciar una ventana servida seria mentir."""
    a, b = ventana_pedida(None, None)
    assert (a, b) == (None, None)
    sobre = {"rows": []}
    declara_ventana(sobre, a, b)
    assert sobre == {"rows": []}


@pytest.mark.parametrize(
    ("desde", "hasta", "trozo"),
    [
        (None, DOMINGO, "no acota nada"),
        ("2026-09-04 09:30", DOMINGO, "zona horaria"),
        (DOMINGO, VIERNES, "posterior a desde"),
        ("viernes", DOMINGO, "ISO-8601"),
    ],
)
def test_las_ventanas_imposibles_se_rechazan_diciendo_cual_es_el_problema(desde, hasta, trozo):
    """Un 422 que no dice que pasa obliga a adivinar, y adivinar es lo que se esta quitando."""
    with pytest.raises(HTTPException) as exc:
        ventana_pedida(desde, hasta)
    assert exc.value.status_code == 422
    assert trozo in str(exc.value.detail)


def test_la_ruta_de_rango_exige_desde_y_las_otras_tres_no():
    """`obligatoria` es la unica diferencia entre las cuatro: /api/rango/estructura no tiene
    retroceso al que caer, las otras si."""
    with pytest.raises(HTTPException) as exc:
        ventana_pedida(None, None, obligatoria=True)
    # Comillas angulares y NO acentos graves: el `detail` de un 422 es un valor publicado, y el
    # panel lo pinta con textContent, asi que la marca de markdown se veria tal cual.
    assert "hace falta «desde»" in str(exc.value.detail)
