"""Z-05 · el «porque» del veredicto de rango dice SOLO los votos que hubo.

`_veredicto` elige «desapalancamiento» con dos votos bajistas de tres -precio, spot,
liquidaciones- y el OI cayendo, pero publicaba un «porque» FIJO: «el precio cae, el spot vende y el
interes abierto cae con ellos». Si los dos bajistas eran el precio y las liquidaciones, o el spot no
voto, la pantalla afirmaba un hecho que no se midio (22 de 120 ventanas cerradas de 6 h en 140 el
2026-11-22, `scripts/sonda_rango_porque.py`). Lo mismo con las frases fijas de distribucion y
acumulacion.

El veredicto NO cambia (ni el nombre ni la regla): exigir el voto de spot moveria la distribucion
con un criterio sin calibrar. Cambia la frase, que se compone con los votos que hubo. Los casos
R1a-R1e son los de Fable (fable-f18, `fable_f18_casos.py`); con el codigo viejo caen todos.
"""

from __future__ import annotations

import itertools

import pytest

from app.rango import _pruebas, _veredicto
from scripts.sonda_rango_porque import afirmaciones_sin_voto


def _ventana(**cambios):
    v = {
        "precio_pct": -1.0, "velas_1min": 360, "cvd_spot_usd": -5e6, "minutos_spot": 720,
        "oi_pct": -0.5, "muestras_oi": 72, "liq_largos_usd": 3e6, "liq_cortos_usd": 1e6,
        "muestras_liq": 72, "funding_medio_pct_8h": 0.005, "muestras_funding": 72,
        "ballena_spot_usd": 0.0,
    }
    v.update(cambios)
    return v


# nombre -> (ventana, estructura que la regla de siempre elige, frase que el «porque» debe decir)
CASOS = {
    "R1a spot sin filas, precio y liquidaciones bajistas, OI cae":
        (_ventana(cvd_spot_usd=None, minutos_spot=0), "desapalancamiento", "el spot no voto"),
    "R1b spot compra +50 M, precio y liquidaciones bajistas, OI cae":
        (_ventana(cvd_spot_usd=5e7), "desapalancamiento", "el spot no acompana"),
    "R1c precio sube +2 %, spot vende, se rompen largos, OI cae":
        (_ventana(precio_pct=2.0), "desapalancamiento", "el precio no acompana"),
    "R1d precio sube +1 %, spot vende, se rompen largos, OI aguanta":
        (_ventana(precio_pct=1.0, oi_pct=0.3), "compatible_con_distribucion", "el precio no acompana"),
    "R1e precio baja -0.05 %, spot compra, se rompen cortos, OI aguanta":
        (_ventana(precio_pct=-0.05, cvd_spot_usd=1e6, liq_largos_usd=1e6, liq_cortos_usd=2e6, oi_pct=0.1),
         "compatible_con_acumulacion", "el precio no acompana"),
}


@pytest.mark.parametrize("nombre", list(CASOS))
def test_el_porque_no_afirma_un_voto_que_no_hubo(nombre):
    ventana, estructura, frase = CASOS[nombre]
    pruebas = _pruebas(ventana, {})
    v = _veredicto(pruebas)
    # Primero lo que el codigo viejo ya hacia bien: el NOMBRE no se mueve.
    assert v["estructura"] == estructura, v
    assert afirmaciones_sin_voto(v, pruebas) == [], v["porque"]
    assert frase in v["porque"], v["porque"]


def test_cuando_todos_acompanan_la_frase_lo_dice_entera():
    """El caso de siempre -precio cae, spot vende, OI cae- sigue diciendo los tres hechos."""
    pruebas = _pruebas(_ventana(), {})
    v = _veredicto(pruebas)
    assert v["estructura"] == "desapalancamiento"
    for hecho in ("el precio cae", "el spot vende", "se rompen los largos", "el interes abierto cae"):
        assert hecho in v["porque"], v["porque"]
    assert "no acompana" not in v["porque"] and "no voto" not in v["porque"]


PRECIO = {"alcista": 1.0, "bajista": -1.0, None: None}
SPOT = {"alcista": 5e6, "bajista": -5e6, None: None}
OI = {"traspaso": 0.5, "cierre": -0.5, None: None}
LIQ = {"alcista": (1e6, 3e6), "bajista": (3e6, 1e6), None: (None, None)}


def test_ninguna_combinacion_de_votos_afirma_lo_que_no_se_voto():
    """Las 81 combinaciones de las cuatro patas que citan votos: ningun «porque» afirma un lado que
    su prueba no voto, y cada estructura con nombre dice algo de cada una de las cuatro."""
    for p, s, o, liq in itertools.product(PRECIO, SPOT, OI, LIQ):
        ventana = _ventana(
            precio_pct=PRECIO[p], cvd_spot_usd=SPOT[s], minutos_spot=720 if s else 0,
            oi_pct=OI[o], liq_largos_usd=LIQ[liq][0], liq_cortos_usd=LIQ[liq][1],
        )
        pruebas = _pruebas(ventana, {})
        assert [x["vota"] for x in pruebas[:4]] == [p, s, o, liq]
        v = _veredicto(pruebas)
        assert afirmaciones_sin_voto(v, pruebas) == [], (p, s, o, liq, v["porque"])
        if v["estructura"] != "ninguna":
            for pata in (("el precio",), ("el spot",), ("el interes abierto",),
                         ("liquidaciones", "se rompen los")):
                assert any(x in v["porque"] for x in pata), (p, s, o, liq, v["porque"])
