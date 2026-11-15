"""DIARIO DE ENTRADAS (fase 2): libro encadenado, resolucion, fuentes y marcador. Datos sinteticos, sin red ni base."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.bot import calc
from app.diario import libro as lb


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
