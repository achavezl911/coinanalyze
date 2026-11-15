"""DIARIO DE ENTRADAS (fase 2): libro encadenado, resolucion, fuentes y marcador. Datos sinteticos, sin red ni base."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bot import calc
from app.diario import libro as lb
from app.diario import resuelve as rs


def _prop(i: str = "x:1", **kw) -> dict:
    p = {"fuente": "rejilla", "id": i, "activo": "BTC", "lado": "largo", "orden": "limite", "entrada": 98.0, "stop": 95.06,
         "objetivo": 103.88, "caduca": 1000 + 5 * 86400, "plazo_s": 10 * 86400, "riesgo_usd": 5.0, "sello": 1000,
         "porque": "prueba"}
    p.update(kw)
    return p


def test_r0_perdida_max_sigue_a_5():
    assert calc.PERDIDA_MAX == 5.0


def test_libro_intacto_y_cabeza(tmp_path):
    r = str(tmp_path / "d" / "e.jsonl")
    L = lb.Libro(r)
    for k in range(4):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000 + k)
    assert lb.verifica(r) == []
    cab = L.cabeza()
    assert cab["n"] == 3 and lb.verifica(r, cab) == []
    assert [o["n"] for o in L.lee()] == [0, 1, 2, 3]
    assert L.lee()[0]["prev"] == lb.GENESIS


def test_libro_rechaza_una_linea_tocada(tmp_path):
    r = str(tmp_path / "e.jsonl")
    L = lb.Libro(r)
    for k in range(4):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000 + k)
    cab = L.cabeza()
    lineas = Path(r).read_bytes().splitlines()
    o = json.loads(lineas[1])
    o["entrada"] = 97.0  # se toca el nivel de una propuesta ya sellada, en forma canonica
    lineas[1] = lb.canon(o)
    Path(r).write_bytes(b"\n".join(lineas) + b"\n")
    p = lb.verifica(r)
    assert any(x.startswith("linea 2: prev") for x in p), p
    with pytest.raises(ValueError, match="libro tocado"):
        L.lee()
    # la cola: tocar la ULTIMA linea solo la delata la cabeza publicada
    lineas = Path(r).read_bytes().splitlines()
    lineas[1] = lb.canon({**o, "entrada": 98.0})
    o3 = json.loads(lineas[3])
    lineas[3] = lb.canon({**o3, "stop": 1.0})
    Path(r).write_bytes(b"\n".join(lineas) + b"\n")
    assert lb.verifica(r) == []
    assert any("cabeza" in x for x in lb.verifica(r, cab))


def test_libro_quitar_una_linea_y_resultados(tmp_path):
    r = str(tmp_path / "e.jsonl")
    L = lb.Libro(r)
    for k in range(3):
        L.anade("propuesta", _prop(f"x:{k}"), ahora=1000)
    lineas = Path(r).read_bytes().splitlines()
    Path(r).write_bytes(lineas[0] + b"\n" + lineas[2] + b"\n")
    assert any("n=2" in x for x in lb.verifica(r))
    r2 = str(tmp_path / "f.jsonl")
    L2 = lb.Libro(r2)
    res = {"id": "x:9", "llenada": False, "px_llenado": None, "t_llenado": None, "salida": "caducada", "px_salida": None,
           "t_salida": None, "r_neto": 0.0, "usd_neto": 0.0, "coste": {}}
    L2.anade("resultado", res, ahora=1)
    assert any("sin propuesta" in x for x in lb.verifica(r2))
    with pytest.raises(ValueError, match="faltan"):
        L2.anade("propuesta", {"id": "y"})


# ---------- la resolucion ----------
T0 = 28800 * 100  # un sello de funding exacto: las velas de abajo no cruzan otro salvo que se diga


def _v(*filas, t0=T0 + 300):
    """velas de 5 min seguidas desde t0: cada fila (o, h, l, c)."""
    return {t0 + 300 * k: f for k, f in enumerate(filas)}


def _p(**kw) -> dict:
    base = {"id": "r:1", "lado": "largo", "orden": "limite", "entrada": 100.0, "stop": 97.0, "objetivo": 106.0,
            "caduca": T0 + 3600, "plazo_s": 7200, "riesgo_usd": 5.0, "sello": T0 + 10}
    base.update(kw)
    return base


def test_resuelve_llenado_y_objetivo_coste_a_mano():
    v = _v((101, 101.5, 100.5, 101), (100.8, 101, 99.5, 100.2), (100.2, 104, 100, 103), (103, 106.5, 102, 106))
    r = rs.resuelve(_p(), v, T0 + 10**6)
    assert r["estado"] == "resuelta"
    x = r["resultado"]
    assert x["llenada"] and x["t_llenado"] == T0 + 600 and x["px_llenado"] == 100.0
    assert x["salida"] == "objetivo" and x["px_salida"] == 106.0 and x["t_salida"] == T0 + 1500
    # a mano: 6 % - 2 pb maker - 5.5 pb taker, sin funding -> 0.05925; R = 0.05925 / 0.03; nominal = 5 / 0.03175
    assert x["r_neto"] == pytest.approx(1.975)
    assert x["usd_neto"] == pytest.approx(0.05925 * 5 / 0.03175)
    assert x["coste"]["sellos_funding"] == 0


def test_resuelve_misma_vela_gana_el_stop_y_funding():
    # llena y, en otra vela posterior, toca stop Y objetivo: stop a 97 servido 10 pb peor
    v = _v((100.5, 100.6, 99.9, 100.2), (100, 107, 96, 100))
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert x["salida"] == "stop" and x["px_salida"] == pytest.approx(97 * 0.999)
    assert x["r_neto"] == pytest.approx((97 * 0.999 / 100 - 1 - 0.0002 - 0.00055) / 0.03)
    # cruzando un sello de funding: 1 pb mas en contra
    v2 = {T0 + 28800 - 600: (100.5, 100.6, 99.9, 100.2), T0 + 28800 - 300: (100, 100.5, 99.8, 100),
          T0 + 28800: (100, 107, 96, 100)}
    p2 = _p(sello=T0 + 28800 - 700, caduca=T0 + 10**5, plazo_s=10**5)
    x2 = rs.resuelve(p2, v2, T0 + 10**6)["resultado"]
    assert x2["coste"]["sellos_funding"] == 1
    assert x2["r_neto"] == pytest.approx((97 * 0.999 / 100 - 1 - 0.0002 - 0.00055 - 0.0001) / 0.03)


def test_resuelve_en_la_vela_del_llenado_cuenta_el_stop_no_el_objetivo():
    x = rs.resuelve(_p(), _v((100.5, 106.5, 99.0, 100)), T0 + 10**6)
    assert x["estado"] == "pendiente"  # llenada; el objetivo de esa vela no cuenta y no hay mas velas
    x = rs.resuelve(_p(), _v((100.5, 106.5, 96.0, 100)), T0 + 10**6)["resultado"]
    assert x["salida"] == "stop"


def test_resuelve_mercado_corto_abre_mas_alla_del_stop():
    p = _p(lado="corto", orden="mercado", entrada=100.3, stop=103.0, objetivo=94.0)
    v = _v((100, 100.5, 99.5, 100.2), (104, 104.5, 103.5, 104))
    x = rs.resuelve(p, v, T0 + 10**6)["resultado"]
    assert x["px_llenado"] == 100 and x["px_salida"] == pytest.approx(104 * 1.001)
    assert x["r_neto"] == pytest.approx(-0.04214 / 0.03)
    assert x["coste"]["deslizamiento_stop_pb"] == pytest.approx(110.4)


def test_resuelve_caducada_sin_llenar_y_plazo():
    v = {T0 + 300 * k: (101, 101.5, 100.5, 101) for k in range(1, 14)}
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert not x["llenada"] and x["salida"] == "caducada" and x["r_neto"] == 0.0 and x["t_salida"] == T0 + 3600
    v = {T0 + 300 * k: (100, 100.5, 99.5, 100.1) for k in range(1, 40)}
    x = rs.resuelve(_p(), v, T0 + 10**6)["resultado"]
    assert x["salida"] == "plazo" and x["t_salida"] == T0 + 300 + 7200 and x["px_salida"] == 100.1


def test_resuelve_hueco_deja_pendiente_y_lo_dice():
    v = _v((101, 101.5, 100.5, 101), (100.8, 101, 99.5, 100.2), (100.2, 104, 100, 103), (103, 106.5, 102, 106))
    del v[T0 + 900]
    r = rs.resuelve(_p(), v, T0 + 10**6)
    assert r == {"estado": "pendiente", "hueco": T0 + 900, "hasta": T0 + 1200}
    # una vela que aun no ha cerrado no cuenta
    r = rs.resuelve(_p(), _v((101, 101.5, 100.5, 101)), T0 + 400)
    assert r["estado"] == "pendiente" and r["hueco"] is None
