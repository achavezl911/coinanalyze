"""N-01 (fable-f17 A) · una vela INCOMPLETA dentro del episodio lo deja no evaluable ENTERO.

`paso` ya se niega cuando la incompleta es la vela de T; hasta entradas-motor-2 una vela del INTERIOR
del episodio con un minuto ausente se saltaba (motor.py `if v is None: continue`) y el episodio podia
disparar sobre una estructura a la que le faltaba esa vela. Desde entradas-motor-3 el episodio se
cierra sin disparo con la razon escrita (`no_evaluable: vela ... incompleta`), y `decidir` rechaza una
foto con una vela incompleta. Los casos son los de entregas/fable/fable-f17/scripts/fable_f17_casos.py
(caso A), sobre el banco de tests/entradas_banco.py: F1 largo en la zona 94.74-95.26.
"""

from __future__ import annotations

import copy
from datetime import timedelta

import entradas_banco as B
import pytest

from app.entradas import motor as M

CUARTO = timedelta(minutes=15)
T1, T2, T3 = B.T0, B.T0 + CUARTO, B.T0 + 2 * CUARTO
ARMA = (96.0, 96.2, 95.6, 95.7)
CIERRA = (95.7, 95.8, 94.0, 94.2)  # cierra bajo la zona: con sus 15 minutos, «zona aceptada»
DENTRO = (95.7, 95.8, 95.0, 95.1)  # toca y cierra dentro: el episodio sigue VIGILANDO


def _armado() -> tuple[dict, list[dict]]:
    r1 = B.paso(B.insumos(T1, gatillo=ARMA))
    vig = B.elige(r1["transiciones"], familia="F1", lado="largo", estado="VIGILANDO")
    assert vig, "el escenario base ya no arma F1 largo"
    return vig[0], [{**t, "orden": i} for i, t in enumerate(r1["transiciones"])]


def _t3(segunda: tuple, gatillo: tuple, precio_corte: float, minutos_t2: int) -> list[dict]:
    vig, previos = _armado()
    ins = B.insumos(T3, gatillo=gatillo, previas=[ARMA, segunda], precio_corte=precio_corte)
    assert ins["velas"][-2]["fin"] == M.iso(T2)
    ins["velas"][-2]["minutos"] = minutos_t2
    r3 = B.paso(ins, previos=previos)
    assert r3["evaluacion"]["estado"] == "ok"
    return [t for t in B.elige(r3["transiciones"], familia="F1", lado="largo")
            if t["episodio"] == vig["episodio"]]


def test_caso_a_la_vela_que_cerraba_incompleta_no_dispara_el_episodio_y_lo_dice():
    """f17 A: con la vela de T2 a 14/15, entradas-motor-2 DISPARABA en T3 con un stop que no vio su minimo."""
    hueco = B.paso(B.insumos(T2, gatillo=CIERRA, previas=[ARMA], precio_corte=95.7, minutos_gatillo=14),
                   previos=_armado()[1])
    assert hueco["transiciones"] == [] and hueco["evaluacion"]["estado"] == "no_evaluable"

    filas = _t3(CIERRA, (94.2, 96.2, 94.1, 95.8), 94.2, minutos_t2=14)
    assert [f["estado"] for f in filas] == ["CERRADO_SIN_DISPARO"], filas
    fila = filas[0]
    assert fila["motivo"].startswith("no_evaluable: ")
    assert f"vela {M.iso(T2 - CUARTO)} incompleta: 14 de 15 minutos" in fila["motivo"]
    assert fila["foto"]["motivo"] == fila["motivo"]
    assert fila["codigo_version"] == M.CODIGO_VERSION == "entradas-motor-3"
    assert [v["minutos"] for v in fila["foto"]["episodio"]["velas"]] == [15, 14, 15]


@pytest.mark.parametrize("minutos_t2", [14, 0])
def test_una_vela_interior_incompleta_cierra_el_episodio_que_con_ella_entera_dispara(minutos_t2):
    """El mismo recorrido con T2 entera dispara (control); con T2 a 14/15 o sin filas, no evaluable."""
    gatillo = (95.1, 96.2, 95.0, 95.8)
    entero = _t3(DENTRO, gatillo, 95.1, minutos_t2=15)
    assert [f["estado"] for f in entero] in (["DISPARADO"], ["SOMBRA"]), entero
    assert entero[0]["motivo"] is None or "no_evaluable" not in entero[0]["motivo"]

    roto = _t3(DENTRO, gatillo, 95.1, minutos_t2=minutos_t2)
    assert [f["estado"] for f in roto] == ["CERRADO_SIN_DISPARO"], roto
    assert f"incompleta: {minutos_t2} de 15 minutos" in roto[0]["motivo"]


def test_episodio_completo_igual_que_antes_cierra_por_zona_aceptada():
    """Control: con la vela de T2 entera, el episodio se cierra en T2 por la estructura, como hasta ahora."""
    vig, previos = _armado()
    r2 = B.paso(B.insumos(T2, gatillo=CIERRA, previas=[ARMA], precio_corte=95.7), previos=previos)
    filas = [t for t in B.elige(r2["transiciones"], familia="F1", lado="largo")
             if t["episodio"] == vig["episodio"]]
    assert [f["estado"] for f in filas] == ["CERRADO_SIN_DISPARO"]
    assert filas[0]["motivo"] == "zona aceptada: cierre al otro lado"


def test_decidir_rechaza_una_foto_con_una_vela_incompleta():
    gatillo = (95.1, 96.2, 95.0, 95.8)
    foto = _t3(DENTRO, gatillo, 95.1, minutos_t2=15)[0]["foto"]
    M.decidir(foto)
    plantada = copy.deepcopy(foto)
    plantada["episodio"]["velas"][1]["minutos"] = 14
    with pytest.raises(M.FotoIncoherente, match="incompleta"):
        M.decidir(plantada)
