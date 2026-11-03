"""Remate 1 de la anatomia (BOT-3e): gestion (rejilla, limite, mecha, cuenta, apalancamiento) y rangos. Sinteticos."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "tests"))

np = pytest.importorskip("numpy")
C = pytest.importorskip("anatomia_comun")
G = pytest.importorskip("anatomia_gestion")
R = pytest.importorskip("anatomia_rangos")

H = C.HORIZONTE


# ---------------------------------------------------------------- gestion
def camino(n=H + 10, base=100.0):
    o = np.full(n, base)
    return o, o + 0.1, o - 0.1, o.copy()


def test_rejilla_a_mano():
    o, h, lo, c = camino()
    h[5] = 102.05                                  # objetivo 2 % en el minuto 5
    lo[8] = 98.9                                    # el stop despues: no cuenta
    ex, br, sa, va, _ = G.salidas(o, h, lo, c, [0], [100.0], 1, 0.01, 0.02)
    assert va[0] and ex[0] and br[0] == pytest.approx(0.02) and sa[0] == 5
    o, h, lo, c = camino()
    h[3], lo[3] = 102.5, 98.9                       # los dos en el mismo minuto: gana el stop
    ex, br, *_ = G.salidas(o, h, lo, c, [0], [100.0], 1, 0.01, 0.02)
    assert not ex[0] and br[0] == pytest.approx(-0.01)
    o, h, lo, c = camino()
    c[H - 1] = 100.5                               # nada toca: vence al cierre del minuto H
    ex, br, sa, *_ = G.salidas(o, h, lo, c, [0], [100.0], 1, 0.01, 0.02)
    assert not ex[0] and br[0] == pytest.approx(0.005) and sa[0] == H - 1
    o, h, lo, c = camino()
    lo[7] = 97.9                                    # corto: el objetivo esta abajo
    ex, br, *_ = G.salidas(o, h, lo, c, [0], [100.0], -1, 0.01, 0.02)
    assert ex[0] and br[0] == pytest.approx(0.02)


def test_empate_taker_y_maker():
    assert C.empate_g(0.01, 0.02) == pytest.approx((0.01 + 0.0011) / 0.03)
    assert C.empate_g(0.01, 0.02, C.MAKER) == pytest.approx((0.01 + 0.00075) / 0.03)
    assert C.empate_g(0.004, 0.01, C.MAKER) < C.empate_g(0.004, 0.01)


def test_limite_que_solo_toca_no_llena():
    n = C.LIM_CADUCA + 20
    lo, h = np.full(n, 101.0), np.full(n, 102.0)
    x = {"l": lo, "h": h}
    lim = np.array([100.0])
    lo[10] = 100.0                                  # toca el limite, no lo cruza
    lo[11] = 100.0 * (1 - C.LIM_CRUCE / 2)          # lo cruza por menos del minimo
    f, ok = G.llenado(x, np.array([0]), "largo", lim)
    assert f[0] == -1 and ok[0]
    lo[30] = 100.0 * (1 - C.LIM_CRUCE) - 1e-9       # lo cruza por el minimo
    f, ok = G.llenado(x, np.array([0]), "largo", lim)
    assert f[0] == 30
    h[:] = 99.0
    lo[:] = 98.0
    h[12] = 100.0                                  # corto, espejo
    f, _ = G.llenado(x, np.array([0]), "corto", lim)
    assert f[0] == -1


@pytest.fixture(scope="module")
def mercado():
    from test_anatomia import sintetico
    return sintetico(dias=12)


def test_stop_bajo_la_mecha_sin_mirar_adelante(mercado):
    B, ts = mercado
    _, X = G.contexto(B, ts)
    g = np.array([len(ts) // 2])
    d = G.dist_stop(X["BTC"], g, "largo", "mecha")
    lo = X["BTC"]["l"]
    esperado = 1 - np.min(lo[g[0] - C.STOP_MECHA_MIN + 1:g[0] + 1]) * (1 - C.STOP_MECHA_MARGEN) / X["BTC"]["o"][g[0] + 1]
    assert d[0] == pytest.approx(esperado)
    B2 = copy.deepcopy(B)
    B2["BTC"]["l"][g[0] + 1:] *= 0.5               # el futuro se hunde
    _, X2 = G.contexto(B2, ts)
    assert G.dist_stop(X2["BTC"], g, "largo", "mecha")[0] == pytest.approx(d[0])


def operaciones(stop):
    return {"stop": np.full(40, stop), "com": C.COMISION * 2, "mae": np.linspace(0, 0.03, 40),
            "exito": np.arange(40) % 3 == 0}


def test_no_cabe():
    a = G.apalancamiento(operaciones(0.02))
    assert not a["NO_CABE"] and a["no_cabe"] == 0
    apal = C.APAL_RIESGO / (0.02 + 2 * C.COMISION) / C.APAL_MARGEN
    assert a["liq_p50"] == pytest.approx(1 / apal - C.APAL_MANT)
    b = G.apalancamiento(operaciones(0.02), margen=1.0)  # 10x de apalancamiento mas: la liquidacion antes que el stop
    assert b["NO_CABE"] and b["no_cabe"] == 40
    assert b["tocan_liquidacion"] == int((np.linspace(0, 0.03, 40) >= b["liq_p50"]).sum()) > 0


def test_el_apalancamiento_no_cambia_la_tasa():
    tr = operaciones(0.006)
    tasas = {G.apalancamiento(tr, margen=m, riesgo=r)["tasa"] for m, r in ((10, 3.55), (1, 3.55), (100, 1), (10, 50))}
    assert len(tasas) == 1


# ---------------------------------------------------------------- rangos
def serie_h(desde="2018-01-01", hasta="2030-01-01", semilla=3):
    """Horas de un OU en logaritmo con mechas: rangos a menudo, salidas casi nunca."""
    rng = np.random.default_rng(semilla)
    t0 = C._ts(desde)
    n = (C._ts(hasta) - t0) // 3600
    x = np.zeros(n)
    e = rng.normal(0, 0.003, n)
    for i in range(1, n):
        x[i] = 0.8 * x[i - 1] + e[i]
    c = 100 * np.exp(x)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.004, n)))
    lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.004, n)))
    qv = np.full(n, 1e6)
    return {"ts": t0 + 3600 * np.arange(n, dtype=np.int64), "o": o, "h": h, "l": lo, "c": c, "qv": qv,
            "dp": rng.normal(0, 1e5, n), "sqv": qv, "ds": rng.normal(0, 1e5, n), "oi": 1e9 * (1 + 0.01 * x),
            "top": 1 + x}


def corta(Hd, k):
    return {a: (v[:k] if isinstance(v, np.ndarray) else v) for a, v in Hd.items()}


def test_rango_sin_mirar_adelante():
    Hd = serie_h(hasta="2018-03-01")
    ev = R.rangos(Hd)
    assert ev
    k, W = ev[0]["k"], ev[0]["W"]
    h, lo, c, ts = (corta(Hd, k + 1)[a] for a in ("h", "l", "c", "ts"))
    atr = R.atr_diario(ts, h, lo, c)
    assert R.cumple(h, lo, c, atr, k, W) == R.cumple(Hd["h"], Hd["l"], Hd["c"], R.atr_diario(
        Hd["ts"], Hd["h"], Hd["l"], Hd["c"]), k, W)
    Hd2 = corta(Hd, k + 24 * C.RANGO_DIAS + C.RANGO_VUELTA + 2)
    Hd2 = {a: (v.copy() if isinstance(v, np.ndarray) else v) for a, v in Hd2.items()}
    for a in ("o", "h", "l", "c"):
        Hd2[a][k + 1:] *= 1.3                      # el futuro cambia: la deteccion en k no
    e2 = R.rangos(Hd2)[0]
    assert (e2["k"], e2["W"], e2["alto"], e2["bajo"], e2["posicion"]) == (k, W, ev[0]["alto"], ev[0]["bajo"],
                                                                         ev[0]["posicion"])


def test_falsa_contra_arriba():
    n, k = 400, 100
    def final(c):
        return R.final(c + 0.5, c - 0.5, c, k, 110.0, 100.0)
    c = np.full(n, 105.0)
    c[k + 5:] = 113.0                              # fuera 0.3 alturas y no vuelve
    f = final(c)
    assert (f["clase"], f["lado_final"]) == ("ARRIBA", "ARRIBA") and not f["mas_alla_arriba"]
    c = np.full(n, 105.0)
    c[k + 5:k + 8] = 113.0                         # sale y vuelve antes de 24 h
    c[k + 50:] = 97.0                              # y acaba de verdad abajo
    f = final(c)
    assert (f["clase"], f["lado_final"]) == ("FALSA", "ABAJO")
    c = np.full(n, 105.0)
    c[k + 5:] = 112.0                              # fuera, pero por menos de 0.25 alturas
    assert final(c)["clase"] == "SIN SALIDA"
    c = np.full(n, 105.0)
    c[k + 5:] = 121.0
    assert final(c)["mas_alla_arriba"]


def test_n_menor_que_30_es_sin_calibrar():
    corte = C._ts(C.RANGO_CORTE)
    ev = [{"ts": corte + s * 86400 * 10, "ts_acaba": corte + s * 86400 * 10 + 3600, "clase": "ARRIBA",
           "lado_final": "ARRIBA", "mas_alla_arriba": False, "mas_alla_abajo": False, "ruido": float(i)}
          for i, s in enumerate(list(range(-30, 0)) + list(range(1, 31)))]
    cs = R.celdas({"BTC": ev}, ("ruido",))
    assert cs and all(f["ajuste"]["n"] < 30 for f in cs)
    assert {f["veredicto_ARRIBA"] for f in cs} == {"SIN CALIBRAR"}


def test_controles_de_rangos():
    ev = R.rangos(serie_h(), control=True)
    cs = R.celdas({"BTC": ev}, ("planta", "ruido"))
    v = R.ve(cs)
    assert v["planta_pasa"], [(f["tercil"], f["veredicto_ARRIBA"]) for f in cs if f["estado"] == "planta"]
    assert v["ruido_que_pasa"] == 0 and v["ve"]
    sin = R.celdas({"BTC": R.rangos(serie_h())}, ("ruido",))
    assert not any(f[f"veredicto_{x}"] == "PASA" for f in sin for x in R.LADOS)


# ---------------------------------------------------------------- mide_celda con p (remate 4: el renombre I -> idx)
def celda_sintetica(n=200, semilla=5):
    """n decisiones en la rejilla, todas en la capa A, y un camino aleatorio que da salidas validas."""
    g = np.arange(n) * C.REJILLA
    N = int(g[-1]) + 2 * H + C.LIM_CADUCA + 20
    c = 100 * np.exp(np.cumsum(np.random.default_rng(semilla).normal(0, 0.001, N)))
    o = np.r_[c[0], c[:-1]]
    entra = np.zeros(n, bool)
    entra[::7] = True                                  # pocas entradas: flatnonzero(m) no tiene la forma de G
    niv = np.full(N, np.nan)                           # y pocas armadas: con todas, el indice mide len(G) y no cae
    niv[g[entra]] = c[g[entra]] / (1 + C.LIM_ARMA / 2)
    x = {"o": o, "h": np.maximum(o, c) * 1.0005, "l": np.minimum(o, c) * 0.9995, "c": c, "niv": {"largo": {"n1": niv}}}
    d = {"G": g, "ts": C.CAPA_A_DESDE + g * 60, "capa": {"A": np.ones(n, bool)}, "M": {("m1", "A"): entra * 1.0}}
    return {"BTC": d}, {"BTC": x}, entra


@pytest.mark.parametrize("tipo", ["mecanismo", "limite"])
def test_mide_celda_con_p_no_reusa_el_indice(tipo):
    D, X, entra = celda_sintetica()
    defn = {"simbolo": "BTC", "lado": "largo", "capa": "A", "stop": 0.002, "objetivo": 0.002, "tipo": tipo,
            "nombre": "m1", "nivel": "n1"}
    hasta = int(D["BTC"]["ts"][-1]) + 10 ** 6
    celda, _ = G.mide_celda(D, X, defn, C.CAPA_A_DESDE, hasta, con_p=True)
    assert "p" in celda and celda["n_todas"] > 0
    if tipo == "mecanismo":
        x, g = X["BTC"], D["BTC"]["G"]
        va = G.salidas(x["o"], x["h"], x["l"], x["c"], g + 1, x["o"][g + 1], 1, 0.002, 0.002)[3]
        assert celda["n_todas"] == int((entra & va).sum())     # la p cuenta TODAS las entradas validas de la capa
        assert celda["p"] is not None
