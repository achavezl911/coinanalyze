"""LLENADO R1 (I12 D2 + D3, P21): la limite cuya PRIMERA vela que cuenta ya abre mas alla de su precio era ejecutable
al llegar: se llena a esa apertura con comision de tomador y lo dice (`regla`). Los casos de fable-dz4 «P7»: caen con
main@9dc6fd5 (llenada al limite con 2.0 pb) y pasan con llenado-r1; los de CONTROL dan lo mismo con las dos."""
from __future__ import annotations

import pytest
from test_entradas_resolutor import resuelve as resuelve_entrada

from app.diario import resuelve as rs
from app.entradas import resolutor as RES

T0 = 28800 * 100  # un sello de funding exacto: ninguna vela de abajo cruza otro


def _p(**kw) -> dict:
    base = {"id": "r:1", "lado": "largo", "orden": "limite", "entrada": 100.0, "stop": 98.0, "objetivo": 104.0,
            "caduca": T0 + 3600, "plazo_s": 7200, "riesgo_usd": 5.0, "sello": T0 + 10}
    base.update(kw)
    return base


def _diario(velas: list[tuple], **kw) -> dict:
    return rs.resuelve(_p(**kw), {T0 + 300 * (k + 1): v for k, v in enumerate(velas)}, T0 + 10**6)["resultado"]


# ---------------------------------------------------------------- diario (velas de 5 min)

def test_diario_abre_por_debajo_del_limite_se_llena_a_la_apertura_como_tomador():
    """En main: «llenada a 100.0, comision 2.0 pb, R +1.9625»."""
    x = _diario([(99.6, 99.7, 99.5, 99.6), (99.6, 104.5, 99.5, 104.0)])
    assert (x["px_llenado"], x["t_llenado"], x["salida"]) == (99.6, T0 + 300, "objetivo")
    assert x["coste"]["com_entrada_pb"] == pytest.approx(5.5) and x["regla"] == rs.REGLA_CRUZADA
    assert x["r_neto"] == pytest.approx(2.6815, abs=1e-4)


def test_diario_abre_bajo_el_stop_compra_y_sale_a_la_apertura():
    """En main: compra a 100.0 y sale a 97.4025, R -1.3362."""
    x = _diario([(97.5, 97.6, 97.0, 97.2)])
    assert x["px_llenado"] == 97.5 and x["px_salida"] == pytest.approx(97.4025) and x["salida"] == "stop"
    assert x["r_neto"] == pytest.approx(-0.1050, abs=1e-4)


def test_diario_el_corto_es_el_reflejo():
    x = _diario([(100.4, 100.5, 100.3, 100.4), (100.4, 100.5, 95.0, 95.5)], lado="corto", stop=102.0, objetivo=96.0)
    assert x["px_llenado"] == 100.4 and x["regla"] == rs.REGLA_CRUZADA and x["salida"] == "objetivo"
    assert x["r_neto"] == pytest.approx((1 - 96 / 100.4 - 0.0011) / (1.6 / 100.4))


@pytest.mark.parametrize("caso, velas, kw, esperado", [
    ("cruce dentro de la vela", [(100.3, 100.4, 99.8, 100.0), (100.0, 104.5, 99.9, 104.0)], {}, (100.0, "objetivo", 2.0)),
    ("segunda vela", [(100.3, 100.4, 100.1, 100.2), (99.6, 99.7, 99.5, 99.6), (99.6, 104.5, 99.5, 104.0)], {},
     (100.0, "objetivo", 2.0)),
    ("caducada", [(99.6, 99.7, 99.5, 99.6)], {"caduca": T0 + 300}, (None, "caducada", None)),
])
def test_diario_control_igual_que_main(caso, velas, kw, esperado):
    x = _diario(velas, **kw)
    assert (x["px_llenado"], x["salida"], x["coste"].get("com_entrada_pb")) == esperado, caso
    assert "regla" not in x


# ---------------------------------------------------------------- entradas (velas de 1 min)

def test_entradas_limite_cruzada_entra_a_la_apertura_con_banda_y_tomador():
    """En main: «100.2 con 2.0 pb, R 1.6188». La vela de la entrada real (20:03) abre en 100.0, bajo 100.2."""
    r = resuelve_entrada("intradia", {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}, tipo="limite",
                         precio_limite=100.2)
    assert (r["salida"], r["entrada"]["instante"]) == (RES.OBJETIVO, "2026-10-12T20:03:00Z")
    assert r["entrada"]["precio"] == pytest.approx(100.01)
    assert r["entrada"]["regla"] == RES.REGLA_CRUZADA and RES.RESOLUTOR_VERSION == "entradas-resolutor-2"
    assert r["entrada"]["apertura"] == 100.0 and r["pnl"]["comision_bps"] == {"entrada": 5.5, "salida": 2.0}
    assert r["pnl"]["r_neto"] == pytest.approx(1.6945, abs=1e-4)


def test_entradas_limite_cruzada_mas_alla_del_stop_no_abre_como_la_de_mercado():
    """En main: llenada a 100.2 y stop en esa misma vela."""
    cambios = {"2026-10-12T20:03": (98.9, 99.0, 98.8, 98.9)}
    r = resuelve_entrada("intradia", cambios, tipo="limite", precio_limite=100.2)
    assert r["salida"] == RES.SIN_ENTRADA == resuelve_entrada("intradia", cambios)["salida"]


@pytest.mark.parametrize("perfil", ["intradia", "swing"])
def test_entradas_control_cruce_dentro_y_segunda_vela_igual_que_main(perfil):
    t1 = {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}
    dentro = resuelve_entrada(perfil, {"2026-10-12T20:03": (100.0, 100.0, 99.8, 99.9), **t1}, tipo="limite",
                              precio_limite=99.9)
    segunda = resuelve_entrada(perfil, {"2026-10-12T20:04": (99.8, 99.8, 99.8, 99.8), **t1}, tipo="limite",
                               precio_limite=99.9)
    for r, minuto in ((dentro, "03"), (segunda, "04")):
        assert (r["salida"], r["entrada"]["instante"], r["entrada"]["precio"]) == (
            RES.OBJETIVO, f"2026-10-12T20:{minuto}:00Z", 99.9)
        assert r["pnl"]["comision_bps"]["entrada"] == 2.0 and "regla" not in r["entrada"]
