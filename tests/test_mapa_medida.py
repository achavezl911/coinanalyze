"""BOT-3c: el criterio del mapa de valor, con biblioteca estandar.

Las reglas de resolucion (empate = stop, funding cobrado/pagado) y el RSI se fijan sobre caminos sinteticos; si la
historia de /srv/coinanalyze/historia-bot esta (fuera de git), cada operacion de la «muestra» de
scripts/mapa_valor.json se recalcula aqui con `mapa_comun.resultado` y tiene que dar el mismo neto que numpy.
"""

from __future__ import annotations

import json
import math
import sys
from array import array
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
from mapa_comun import ESQUEMAS, FEE, LISTON, resultado, rsi_wilder  # noqa: E402

HIST = Path("/srv/coinanalyze/historia-bot")
VALOR = RAIZ / "scripts" / "mapa_valor.json"


def test_empate_en_un_minuto_gana_el_stop():
    o, h, lo, c = [100.0] * 3, [100.0, 101.5, 100.0], [100.0, 99.0, 100.0], [100.0] * 3
    assert resultado(o, h, lo, c, 0, 1, 0.01, 0.006, 3)[:2] == ("SL", -0.006 - FEE)
    assert resultado(o, h, lo, c, 0, -1, 0.01, 0.006, 3)[:2] == ("SL", -0.006 - FEE)


def test_objetivo_y_vence():
    o, h, lo, c = [100.0] * 4, [100.0, 100.5, 101.2, 100.0], [99.9] * 4, [100.0, 100.0, 101.0, 100.3]
    assert resultado(o, h, lo, c, 0, 1, 0.01, 0.006, 4) == ("TP", 0.01 - FEE, 2)
    tipo, net, k = resultado(o, h, lo, c, 0, 1, 0.05, 0.006, 4)
    assert (tipo, k) == ("VENCE", 3) and math.isclose(net, 0.003 - FEE)


def test_funding_se_paga_largo_y_se_cobra_corto_solo_dentro():
    o = h = lo = c = [100.0] * 10
    fun = [(0, 0.5), (3, 0.001), (9, 0.002), (12, 0.5)]  # la de T y la de despues de salir no cuentan
    _, nl, k = resultado(o, h, lo, c, 0, 1, 0.5, 0.5, 10, fun)
    _, nc, _ = resultado(o, h, lo, c, 0, -1, 0.5, 0.5, 10, fun)
    assert k == 9 and math.isclose(nl, -FEE - 0.003) and math.isclose(nc, -FEE + 0.003)


def test_liston_y_esquemas():
    assert round(LISTON["a"], 4) == 0.0688 and round(LISTON["d"], 4) == 0.0122
    assert [ESQUEMAS[k][2] // 1440 for k in "abcde"] == [1, 1, 5, 14, 30]


def test_rsi_de_wilder():
    assert all(math.isnan(v) for v in rsi_wilder([1.0, 2.0, 3.0]))
    r = rsi_wilder([float(i) for i in range(30)])
    assert r[14] == 100.0 and r[-1] == 100.0
    r = rsi_wilder([10.0, 11.0] * 20)
    assert 40 < r[-1] < 60


@pytest.mark.skipif(not (HIST / "historia.json").exists() or not VALOR.exists(), reason="sin historia local")
def test_la_muestra_se_reproduce_con_biblioteca_estandar():
    meta = json.loads((HIST / "historia.json").read_text())
    muestra = json.loads(VALOR.read_text())["muestra"]
    assert len(muestra) >= 6
    for op in muestra:
        s = op["activo"]
        t0 = meta["simbolos"][s]["t0"]
        tp, sl, tope = ESQUEMAS[op["esquema"]]
        T = op["Eabs"] - t0
        cols = {}
        for col in ("o", "h", "l", "c"):
            a = array("d")
            with open(HIST / f"{s}.{col}.f64", "rb") as f:
                f.seek(T * 8)
                a.fromfile(f, tope)
            cols[col] = a
        fun = []
        for ln in (HIST / f"{s}.funding.tsv").read_text().split("\n"):
            if ln:
                m, r = ln.split("\t")
                if op["Eabs"] <= int(m) <= op["Eabs"] + tope:
                    fun.append((int(m) - op["Eabs"], float(r)))
        lado = 1 if op["lado"] == "largo" else -1
        tipo, net, k = resultado(cols["o"], cols["h"], cols["l"], cols["c"], 0, lado, tp, sl, tope, fun)
        assert (tipo, k + op["Eabs"]) == (op["tipo"], op["salida_abs"]), op
        assert math.isclose(net, op["neto"], abs_tol=2e-6), op
