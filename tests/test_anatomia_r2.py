"""Remate 2 de la anatomia (BOT-3e): que PASA sea ganar, la via del p y las candidatas del control. Sinteticos."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "tests"))

np = pytest.importorskip("numpy")
C = pytest.importorskip("anatomia_comun")
G = pytest.importorskip("anatomia_gestion")
E = pytest.importorskip("anatomia_estudio")


# ---------------------------------------------------------------- PASA exige el signo
def test_gestion_q_bajo_y_neto_negativo_no_pasa(monkeypatch):
    # la celda del operador (liq_l_1_z alto, BTC corto, 0.02/0.02): n 48, 2 exitos, empate 0.527, neto -0.00035
    base = {"simbolo": "BTC", "lado": "corto", "stop": 0.02, "objetivo": 0.02, "p": 1e-37, "empate": 0.527,
            "azar": 0.5}
    celdas = [
        {**base, "nombre": "pierde", "n": 48, "exitos": 2, "tasa": 2 / 48, "neto": -0.00035},
        {**base, "nombre": "bajo_empate", "n": 48, "exitos": 24, "tasa": 0.5, "neto": 0.001},
        {**base, "nombre": "neto_cero", "n": 48, "exitos": 30, "tasa": 0.625, "neto": 0.0},
        {**base, "nombre": "gana", "n": 48, "exitos": 30, "tasa": 0.625, "neto": 0.002},
        {**base, "nombre": "poca_n", "n": 29, "exitos": 25, "tasa": 25 / 29, "neto": 0.01},
    ]
    monkeypatch.setattr(G, "definiciones", lambda cands: [{"nombre": c["nombre"]} for c in celdas])
    monkeypatch.setattr(G, "mide_celda", lambda D, X, defn, *a, **k: (
        dict(next(c for c in celdas if c["nombre"] == defn["nombre"])), {}))
    monkeypatch.setattr(G, "cuenta", lambda tr: None)
    monkeypatch.setattr(G, "apalancamiento", lambda tr: None)
    D = {s: {"G": None, "M": {}} for s in C.SIMBOLOS}
    out, mejor, _ = G.descubre(D, None, [])
    est = {c["nombre"]: c["estado"] for c in out}
    assert all(c["q"] <= C.FDR_Q for c in out)                   # q bajo en todas: el signo es lo que decide
    assert est["pierde"] == "NO", est
    assert est["bajo_empate"] == "NO" and est["neto_cero"] == "NO", est
    assert est["gana"] == "PASA" and est["poca_n"] == "SIN N", est


def test_gana():
    assert C.gana(0.6, 0.001, 0.527) and not C.gana(0.5, 0.001, 0.527) and not C.gana(0.6, 0.0, 0.527)
    assert not C.gana(0.6, 0.001, 0.527, azar_=0.61) and not C.gana(None, 0.001, 0.5)
    assert not C.gana(0.6, float("nan"), 0.5)


# ---------------------------------------------------------------- la via del p
def test_desplazamientos_degenerados_no_dan_cola_normal():
    n = 2000
    m, y, v = np.zeros(n), np.zeros(n), np.ones(n)
    m[[0, 1000]] = 1
    y[[0, 1000]] = 1                                        # tasa observada 1; desplazada: 0, 0.5 o 1
    S = np.arange(100, n - 100)
    r = G.p_circular(m, y, v, S)
    assert r[0] >= 1 / (1 + len(S)), r                       # 1f166e9: cola normal, p ~ 1e-200
    assert r[1] == 1 and r[3] == "conteo", r


def test_cola_normal_con_desplazamientos_ricos():
    st = np.random.default_rng(0).normal(0.3, 0.02, 2000)
    p, via = C.p_desplazado(0.5, st, len(st))               # 10 desviaciones por encima, k = 0
    assert via == "normal" and p < 1 / (1 + len(st))
    p, via = C.p_desplazado(0.5, np.r_[np.zeros(1990), np.full(10, 0.1)], 2000)
    assert via == "conteo" and p == 1 / 2001


# ---------------------------------------------------------------- control y normal en la misma carpeta
@pytest.fixture(scope="module")
def grande():
    from test_anatomia import sintetico
    return sintetico()


def test_control_y_normal_no_se_pisan(grande, tmp_path):
    from test_anatomia import escribe
    B, ts = grande
    escribe(B, ts, tmp_path / "base")
    rc = E.corre(tmp_path / "base", tmp_path / "control.json", control_pos=True, desplazamientos=300, hgb=False)
    assert rc["ve_el_estudio"], rc.get("control")             # el control positivo sigue viendo con la regla nueva
    assert (tmp_path / "candidatas-control.json").exists()     # 1f166e9: lo escribe en candidatas.json
    assert not (tmp_path / "candidatas.json").exists()
    antes = (tmp_path / "candidatas-control.json").read_bytes()
    rn = E.corre(tmp_path / "base", tmp_path / "normal.json", desplazamientos=100, hgb=False)
    assert (tmp_path / "candidatas-control.json").read_bytes() == antes
    assert json.loads((tmp_path / "candidatas.json").read_text())["candidatas"] == json.loads(
        json.dumps(E.limpia(rn["candidatas"])))
    for r in (rc, rn):                                         # en el estudio, PASA tambien es ganar
        for c in r["celdas"]:
            assert c["p_via"] in ("normal", "conteo")
            if c["estado"] == "PASA":
                assert c["tasa"] >= C.empate(c["esquema"]) and c["neto"] > 0 and c["tasa"] >= c["azar_tasa"], c
