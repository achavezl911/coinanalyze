"""El cero de la ballena deja de publicarse como respuesta.

Lo que se prueba no es que salga un texto, sino que la declaracion SE CALCULA: el mismo codigo,
con un simbolo cuyo umbral si se alcanza, no declara nada. El control se mueve.
"""

from app.api import declarar_tramo_no_medible


def declara(sobre, ws):
    """La ayudante MUTA y devuelve None -asi K31 sigue leyendo la productora de verdad en
    el AST del handler-, de modo que la prueba mira el sobre, no el retorno."""
    copia = dict(sobre)
    declarar_tramo_no_medible(copia, ws)
    return copia

# MEDIDO en 140 el 2026-09-07: en 24 h, 0 de 1727 filas de BTC traen whale_intensity y
# 1727 de 1727 de SOL si. Mismo periodo, mismo codigo, distinto umbral.
BTC_A_CERO = {"rows": [{"bucket": i, "whale_delta": 0.0} for i in range(384)]}
SOL_CON_TRAMO = {"rows": [{"bucket": i, "whale_delta": 0.0} for i in range(383)]
                 + [{"bucket": 383, "whale_delta": -412_000.0}]}


def test_cero_en_todos_los_cubos_se_declara_NO_MEDIBLE():
    """384 cubos a cero no son 'no hubo manos grandes': son un umbral que no llega."""
    d = declara(BTC_A_CERO, "BTC")["tramo_no_medible"]
    assert d["medido"] is False
    assert d["cubos_con_tramo"] == 0 and d["cubos_servidos"] == 384
    assert d["umbral_usd"] == 5_000_000.0
    assert "UNA OPERACION SUELTA" in d["umbral_es_por"]
    assert "no se ven" in d["que_pasa"]


def test_el_hallazgo_es_que_el_umbral_bueno_NO_SE_PUEDE_medir():
    """No se inventa un umbral: se publica por que no se puede calcular y que haria falta."""
    d = declara(BTC_A_CERO, "BTC")["tramo_no_medible"]
    assert "NO SE PUEDE" in d["para_poder_medirlo"]
    assert "histograma" in d["para_poder_medirlo"]


def test_el_cero_NO_VOTA_y_la_respuesta_lo_dice():
    d = declara(BTC_A_CERO, "BTC")["tramo_no_medible"]
    assert "no participa en el regimen" in d["no_vota"]
    assert "se abstiene" in d["no_vota"]


def test_CONTROL_QUE_SE_MUEVE_un_solo_cubo_con_tramo_apaga_la_declaracion():
    """Es el brazo que impide que esto sea un cartel pegado a la ruta: con UN cubo medido de
    384, el instrumento si llega y no hay nada que declarar."""
    assert "tramo_no_medible" not in declara(SOL_CON_TRAMO, "SOL")


def test_sin_filas_no_se_declara_no_medible():
    """Cero filas es otra cosa -no se sirvio nada- y confundirlas seria el mismo error al reves."""
    assert "tramo_no_medible" not in declara({"rows": []}, "BTC")
