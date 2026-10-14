"""El instrumento de C1 (campana 138) da lo que tiene que dar sobre una serie de respuesta conocida, y un
instrumento roto NO lo da: si un mutante pasa el control, el control no mide nada."""

import pytest

import scripts.mide_palabra_grande as M


def test_el_instrumento_sano_da_la_respuesta_conocida():
    assert M.control() == 0


@pytest.mark.parametrize(
    "mutante",
    [
        {"frescura": 1e12},  # no ve que el colector dejo de escribir
        {"r1": M.deslizante(300, 0.4)},  # un umbral que no exige sostener
        {"r1": M.deslizante(300, 0.6, minimo=1)},  # afirma con una ventana casi vacia
    ],
    ids=["sin-frescura", "umbral-40", "sin-minimo"],
)
def test_un_instrumento_roto_no_pasa_el_control(mutante):
    assert M.control(**mutante) > 0


def test_la_clasificacion_es_la_del_registro():
    assert [M.palabra(s, "ok") for s in ("Long Pullback", "Short Rejection", "No Trade", "Sin datos suficientes")] == [
        M.L, M.S, M.N, M.E]
    assert M.palabra("Long Pullback", "stale") == M.E and M.palabra("Long Pullback", "NULL") == M.E
