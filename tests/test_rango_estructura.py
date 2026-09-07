"""El veredicto de rango: nombra la estructura, o dice NINGUNA, y el cero de la ballena no vota.

Las cifras de los casos son las MEDIDAS contra 140 el 2026-09-07 sobre la ventana de Alejandro
-viernes 2026-09-04T09:30Z a domingo 2026-09-07T17:00Z- y su control de igual duracion.
"""

import pytest

from app.rango import _pruebas, _veredicto

# MEDIDO en 140. Ventana y control, BTCUSDT_PERP.A.
VENTANA = {
    "velas_1min": 4770, "precio_inicio": 81000.1, "precio_fin": 78989.3, "precio_pct": -2.482,
    "cvd_spot_usd": -113_608_752.0, "minutos_spot": 9540, "ballena_spot_usd": 0.0,
    "oi_inicio": 9_050_247_714.0, "oi_fin": 8_520_487_323.0, "oi_pct": -5.854, "muestras_oi": 954,
    "funding_medio_pct": 0.2760, "muestras_funding": 954,
    # 482, NO 954: `liquidations` solo escribe cuando hay evento. 954 es el denominador de
    # open_interest y funding_rate, que van a 5 min completos. Prestar un denominador de otra
    # tabla es exactamente la clase de cero que esta campaña existe para quitar.
    "liq_largos_usd": 60_862_490.0, "liq_cortos_usd": 20_465_735.0, "muestras_liq": 482,
}
# EL CONTROL ES `desde - duracion` .. `desde` -79.5 h antes del viernes, o sea 2026-09-01T02:00Z-,
# que es lo que calcula estructura_de_rango. Antes estaba fijado mal y por eso su CVD daba
# +123.9 M; re-medido da +142.5 M, que es la cifra que dio Alejandro (+143.4 M) y no la mia.
CONTROL = {
    "velas_1min": 4770, "precio_pct": 3.348, "cvd_spot_usd": 142_531_137.0, "minutos_spot": 9506,
    "oi_pct": 6.862, "muestras_oi": 954, "funding_medio_pct": 0.7223, "muestras_funding": 954,
    "liq_largos_usd": 47_656_815.0, "liq_cortos_usd": 112_694_641.0, "muestras_liq": 636,
    "ballena_spot_usd": 0.0,
}


def test_la_ventana_de_alejandro_es_desapalancamiento_y_no_distribucion():
    """EL CASO DE PRUEBA. El precio cae, el spot vende -y en el control compraba- y **el interes
    abierto cae con ellos**. En una distribucion alguien compra lo que otro vende y el OI aguanta;
    aqui las posiciones se CIERRAN. La casa no tenia nombre para esto y forzarlo a distribucion
    seria el mismo error que el README:255-262 ya cuenta."""
    v = _veredicto(_pruebas(VENTANA, CONTROL))
    assert v["estructura"] == "desapalancamiento", v
    assert "interes abierto cae" in v["porque"]
    assert v["pruebas_que_votan"] == 5 and v["pruebas_totales"] == 6


def test_el_cero_de_la_ballena_NO_VOTA_y_dice_por_que():
    """EL BRAZO QUE IMPORTA: el tramo esta a cero porque su umbral no se alcanza nunca en spot,
    no porque no haya manos grandes. Un cero que votara diria «no hubo institucionales»."""
    pruebas = _pruebas(VENTANA, CONTROL)
    ballena = next(p for p in pruebas if p["prueba"] == "ballena_spot")
    assert ballena["vota"] is None
    assert "5 000 000 USD por OPERACION SUELTA" in ballena["no_vota_porque"]
    assert "no se pueden ver" in ballena["no_vota_porque"]


def test_puede_decir_NINGUNA_con_todas_las_letras():
    """Un veredicto que siempre elige alguna no es un veredicto."""
    mezcla = dict(VENTANA, precio_pct=1.2, cvd_spot_usd=-5_000_000.0, oi_pct=0.4,
                  liq_largos_usd=10.0, liq_cortos_usd=11.0)
    v = _veredicto(_pruebas(mezcla, CONTROL))
    assert v["estructura"] == "ninguna"
    assert "no apuntan a la misma estructura" in v["porque"]


def test_una_prueba_sin_datos_NO_VOTA_y_se_declara():
    """Nada de rellenar un hueco con un cero: si no se pudo medir, se dice, y el denominador de
    votos baja."""
    sin_oi = dict(VENTANA, oi_pct=None, oi_inicio=None, oi_fin=None, muestras_oi=0)
    pruebas = _pruebas(sin_oi, CONTROL)
    oi = next(p for p in pruebas if p["prueba"] == "interes_abierto")
    assert oi["vota"] is None and "no tiene filas" in oi["no_vota_porque"]
    assert _veredicto(pruebas)["pruebas_que_votan"] == 4


def test_el_control_cambia_la_lectura_del_spot():
    """CONTROL QUE SE MUEVE: un spot vendedor no dice lo mismo si el tramo anterior compraba."""
    con_giro = _pruebas(VENTANA, CONTROL)
    sin_giro = _pruebas(VENTANA, dict(CONTROL, cvd_spot_usd=-90_000_000.0))
    a = next(p for p in con_giro if p["prueba"] == "cvd_spot")["dice"]
    b = next(p for p in sin_giro if p["prueba"] == "cvd_spot")["dice"]
    assert "en el tramo anterior compraba" in a
    assert a != b


def test_el_funding_no_vota_direccion():
    """Un funding positivo con el precio cayendo significa que los largos pagan Y pierden.
    Llamarlo «alcista» seria leerlo al reves, asi que vota `posicionamiento` y no direccion."""
    f = next(p for p in _pruebas(VENTANA, CONTROL) if p["prueba"] == "funding")
    assert f["vota"] == "posicionamiento"


def test_no_es_prediccion_y_lo_dice():
    v = _veredicto(_pruebas(VENTANA, CONTROL))
    assert "no anticipa" in v["no_es_prediccion"]
