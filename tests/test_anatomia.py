"""BOT-3e, la anatomia: criterio (anatomia_comun), extractor (anatomia_extrae) y estudio (anatomia_estudio).
Fixtures sinteticos; sin red ni base. Los del estudio piden numpy y scikit-learn (se saltan si no estan)."""
import gzip
import json
import random
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import anatomia_comun as C  # noqa: E402
import anatomia_extrae as X  # noqa: E402


# ---------------------------------------------------------------- etiqueta: primer toque, empate en el minuto
def _camino(n=260, p=100.0):
    return [p] * n, [p] * n, [p] * n, [p] * n


def test_etiqueta_primer_toque_y_empate_gana_el_stop():
    o, h, lo, c = _camino()
    h[5] = 101.0                                           # objetivo E1 largo (+1 %) en el minuto 5
    lo[9] = 99.0                                            # stop despues: no cuenta
    ex, neto, sal = C.etiqueta(o, h, lo, c, 0, 1, "E1")
    assert ex and sal == 5 and neto == pytest.approx(0.01 - 2 * C.COMISION)
    o, h, lo, c = _camino()
    h[5], lo[5] = 101.0, 99.4                               # los dos en el mismo minuto: gana el stop
    ex, neto, sal = C.etiqueta(o, h, lo, c, 0, 1, "E1")
    assert not ex and sal == 5 and neto == pytest.approx(-0.006 - 2 * C.COMISION)
    o, h, lo, c = _camino()
    lo[3] = 99.0                                            # corto: el objetivo esta abajo
    assert C.etiqueta(o, h, lo, c, 0, -1, "E1")[0]
    o, h, lo, c = _camino()
    c[240] = 100.5                                         # sin toque: cierra en el 240
    ex, neto, sal = C.etiqueta(o, h, lo, c, 0, 1, "E1")
    assert not ex and sal == 240 and neto == pytest.approx(0.005 - 2 * C.COMISION)
    assert C.empate("E1") == pytest.approx(0.444, abs=1e-3) and C.empate("E2") == pytest.approx(0.273, abs=1e-3)


def test_sin_solape_y_wilson():
    assert C.sin_solape([(0, 10), (5, 12), (10, 20), (19, 30), (20, 25)]) == [0, 2, 4]
    assert C.veredicto_confirma(5, 20, "E1") == "SIN N"
    assert C.veredicto_confirma(30, 30, "E1") == "CONFIRMA"


# ---------------------------------------------------------------- extractor: libro con nulos, hora que falta
def test_libro_con_nulos():
    assert X.arr("{1.5,NULL,2}") == [1.5, None, 2.0]
    assert X.arr("\\N") is None
    fila = ["ts", "binance_usdm", "BTC", "ts", "99.9", "100.1", "0.1", "99.9", "{1,50,NULL,1,1}", "100.1",
            "{1,1,NULL,1,1}", "99", "101"]
    ant = X.foto(fila)
    assert ant and ant["c"][2] is None
    b, a = X.profundidad(ant, 0.0035)                     # los nulos no suman ni rompen
    assert b == pytest.approx(99.9 + 99.8 * 50) and a == pytest.approx(100.1 + 100.2)
    act = X.foto(fila[:8] + ["{1,1,NULL,1,1}"] + fila[9:])
    assert X.muro(ant, act, 99.95, 100.05) == (1, 0)       # el muro de 50 a 99.8 se va sin que llegue el precio
    assert X.muro(ant, act, 99.75, 100.05) == (0, 0)       # el precio llego: se lo comieron, no lo quitaron
    act2 = X.foto(fila[:8] + ["{1,NULL,NULL,1,1}"] + fila[9:])
    assert X.muro(ant, act2, 99.95, 100.05) == (0, 0)      # nulo en la foto nueva: no se sabe, no se cuenta
    act3 = X.foto(fila[:6] + ["0.2"] + fila[7:])
    assert X.muro(ant, act3, 99.95, 100.05) == (None, None)  # cambio de paso: no se sabe


def test_hora_que_falta_se_cuenta(tmp_path):
    arch, sal = tmp_path / "archivo", tmp_path / "salida"
    d = arch / "cinta" / "2026-10-21"
    d.mkdir(parents=True)
    for h in range(24):
        if h == 5:
            continue
        with gzip.open(d / f"orderflow_cinta-20261021T{h:02d}Z.tsv.gz", "wt") as f:
            f.write(f"2026-10-21 {h:02d}:00:01+00\tbinance_usdm\tBTC\t100\t1\t100\tt\t1\n")
    hu = X.extrae(arch, sal, desde="2026-10-21", log=lambda *a: None)
    assert hu["horas_faltantes"]["cinta"] == ["2026-10-21T05"]
    assert json.loads((sal / "huecos.json").read_text())["horas_faltantes_n"]["cinta"] == 1
    with gzip.open(sal / "base-BTC.tsv.gz", "rt") as f:
        cab = f.readline().rstrip("\n").split("\t")
        filas = [ln.rstrip("\n").split("\t") for ln in f]
    assert len(filas) == 1440
    i = cab.index("o")
    assert filas[5 * 60 + 1][i] == "" and filas[4 * 60][i] == "100"   # la hora que falta no se rellena


# ---------------------------------------------------------------- estudio (numpy)
np = pytest.importorskip("numpy")
E = pytest.importorskip("anatomia_estudio")


def sintetico(dias=23, semilla=1, inmersiones=True):
    """Paseo aleatorio por simbolo desde 2026-10-18 con inmersiones (-1.5 % en 10 min, rebote 0.25 %) y una
    rafaga de liquidaciones largas, de media cada 8 h: el M1 tiene donde dispararse."""
    N = dias * 1440
    ts = C.CAPA_B_DESDE + 60 * np.arange(N, dtype=np.int64)
    rng = np.random.default_rng(semilla)
    B = {}
    for s in C.SIMBOLOS:
        r = rng.normal(0, 0.0004, N)
        liq_l = rng.exponential(1000, N)
        if inmersiones:                                    # Poisson y sin deriva neta: sin empuje, M1 no sabe nada
            r += 0.0125 / 480
            t0 = 0
            while True:
                t0 += int(rng.exponential(480))
                if t0 >= N - 20:
                    break
                r[t0:t0 + 10] -= 0.0015
                r[t0 + 10:t0 + 15] += 0.0005
                liq_l[t0:t0 + 10] *= 60
        c = 100 * np.exp(np.cumsum(r))
        o = np.concatenate([[c[0]], c[:-1]])
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0002, N)))
        lo = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0002, N)))
        b = {k: rng.standard_normal(N) for k in C.COLUMNAS_BASE}
        b.update(ts=ts.astype(float), fuente=np.ones(N), o=o, h=h, l=lo, c=c, c_cb=c * (1 + rng.normal(0, 1e-4, N)),
                 vol_ref=rng.exponential(1e6, N), liq_l=liq_l, liq_s=rng.exponential(1000, N))
        for lado in "ls":
            b[f"liq_{lado}_n"] = rng.poisson(2, N).astype(float)
            b[f"liq_{lado}_ult"] = ts + 30.0
            b[f"liq_{lado}_casc"] = (rng.random(N) < 0.02).astype(float)
            b[f"liq_{lado}_gr_ult"] = np.where(rng.random(N) < 0.05, ts + 20.0, np.nan)
            b[f"liq5_{lado}"] = np.where(np.arange(N) % 5 == 4, rng.exponential(5000, N), np.nan)
        for k in ("muro_c", "muro_v"):
            b[k] = (rng.random(N) < 0.01).astype(float)
        b["oi"] = 1e9 * np.exp(np.cumsum(rng.normal(0, 1e-3, N)))
        b["oi_ag"] = b["oi"] * 3
        B[s] = b
    return B, ts


def escribe(B, ts, ruta):
    ruta.mkdir(parents=True, exist_ok=True)
    for s in C.SIMBOLOS:
        with gzip.open(ruta / f"base-{s}.tsv.gz", "wt") as f:
            f.write("\t".join(C.COLUMNAS_BASE) + "\n")
            cols = [B[s][k] for k in C.COLUMNAS_BASE]
            for i in range(len(ts)):
                f.write("\t".join("" if not np.isfinite(x[i]) else repr(float(x[i])) for x in cols) + "\n")


def test_etiquetas_vectorizadas_como_el_criterio():
    rng = random.Random(3)
    N = 700
    c = [100.0]
    for _ in range(N - 1):
        c.append(c[-1] * (1 + rng.gauss(0, 0.002)))
    o = [c[0]] + c[:-1]
    h = [max(a, b) * (1 + abs(rng.gauss(0, 0.001))) for a, b in zip(o, c, strict=True)]
    lo = [min(a, b) * (1 - abs(rng.gauss(0, 0.001))) for a, b in zip(o, c, strict=True)]
    G = np.arange(0, N - 241, 7)
    A = [np.array(v) for v in (o, h, lo, c)]
    for lado, sg in C.LADOS.items():
        for e in C.ESQUEMAS:
            ex, ne, sa, va = E.etiquetas(*A, G, sg, e)
            for k, t in enumerate(G):
                r = C.etiqueta(o, h, lo, c, int(t), sg, e)
                assert va[k] and (bool(ex[k]), round(ne[k], 12), int(sa[k])) == \
                    (bool(r[0]), round(r[1], 12), r[2]), (lado, e, t)


def test_sin_mirar_adelante_en_ninguna_variable():
    B, ts = sintetico(dias=6)
    D0 = E.prepara(B, ts)
    G = D0["ETH"]["G"]
    t = int(G[len(G) * 3 // 4])
    rng = np.random.default_rng(9)
    Bp = {s: {k: (v if k == "ts" else np.concatenate([v[:t + 1], v[t + 1:] * rng.uniform(0.5, 2, len(v) - t - 1)]))
              for k, v in b.items()} for s, b in B.items()}
    D1 = E.prepara(Bp, ts)
    esperadas = {n for n, (_c, _t, _d) in C.VARIABLES.items()}
    for s in C.SIMBOLOS:
        assert esperadas <= set(D0[s]["V"]), esperadas - set(D0[s]["V"])
        k = t >= G
        for n in esperadas:
            a, b = D0[s]["V"][n][k], D1[s]["V"][n][k]
            assert np.array_equal(a, b, equal_nan=True), (s, n)
        for m, x in D0[s]["M"].items():
            assert np.array_equal(x[k], D1[s]["M"][m][k], equal_nan=True), (s, m)
    assert {m for m, _c in D0["ETH"]["M"]} == set(C.MECANISMOS)
    assert any(np.isfinite(D0["SOL"]["V"][n][-10:]).any() for n in ("liq_l_15_z", "rsi_1h", "atr_1h_pct"))


@pytest.fixture(scope="module")
def grande():
    return sintetico()


def test_control_positivo_ve(grande):
    B, ts = grande
    ctrl, celdas = E.control(B, ts, desplazamientos=300)
    assert ctrl["m1_encontrado"], ctrl
    assert ctrl["oraculo_encontrado"], ctrl
    assert ctrl["ve"], ctrl
    assert {c["capa"] for c in ctrl["m1_encontrado"]} == {"B"}   # en el fixture solo la capa B tiene liq_l
    assert all(c["estado"] in ("PASA", "NO", "SIN N") for c in celdas)


def test_control_sin_empuje_no_ve(grande, monkeypatch):
    B, ts = grande
    monkeypatch.setattr(C, "EMPUJE", 0.0)                  # el mismo control sin nada plantado tras M1
    ctrl, _ = E.control(B, ts, desplazamientos=300)
    assert not ctrl["m1_encontrado"] and not ctrl["ve"], ctrl
    assert ctrl["oraculo_encontrado"]


def test_todo_junto_corre(grande):
    pytest.importorskip("sklearn")
    B, ts = grande
    D = E.prepara({s: B[s] for s in C.SIMBOLOS}, ts)
    r = E.todo_junto(D, C.CORTE_DESCUBRIMIENTO, barajados=2,
                     params=dict(max_iter=10, max_leaf_nodes=7, min_samples_leaf=50))
    assert set(r) == {"A_largo", "A_corto", "B_largo", "B_corto"}
    assert all(0 <= v["auc"] <= 1 and len(v["auc_desplazadas"]) == 2 for v in r.values())


def test_confirma_no_reelige(grande, tmp_path):
    B, ts = grande
    escribe(B, ts, tmp_path / "base")
    out = tmp_path / "out.json"
    E.corre(tmp_path / "base", out, desplazamientos=100, hgb=False)
    cands = json.loads((tmp_path / "candidatas.json").read_text())["candidatas"]
    assert cands and len(cands) <= C.MAX_CANDIDATAS
    r = E.corre(tmp_path / "base", tmp_path / "conf.json", fecha="2026-11-03")["candidatas"]
    def quita(k):
        return {a: b for a, b in k.items() if a != "confirmacion"}
    assert [quita(k) for k in r] == cands                 # las mismas, en el mismo orden, sin tocar el umbral
    assert all(k["confirmacion"]["veredicto"] in ("CONFIRMA", "CONTEXTO", "RUIDO", "SIN N") for k in r)
    # el umbral es el guardado: si se cambia en el fichero, la confirmacion lo obedece
    var = [k for k in cands if k["tipo"] == "variable" and k["cola"] == "alto"]
    if var:
        var[0]["umbral"] = 1e30
        (tmp_path / "candidatas.json").write_text(json.dumps({"candidatas": cands}))
        r2 = E.corre(tmp_path / "base", tmp_path / "conf2.json", fecha="2026-11-03")["candidatas"]
        assert [k for k in r2 if k["umbral"] == 1e30][0]["confirmacion"]["n"] == 0
