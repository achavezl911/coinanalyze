"""scripts/filtra.py (BOT-3d) con un PRIVADO INVENTADO: cierres parciales, un volteo, Funding, una operacion fuera de la
historia y que la salida no lleve ninguna cantidad, precio ni fecha de las filas. Biblioteca estandar."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
from datetime import UTC, datetime

RAIZ = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("filtra", RAIZ / "scripts" / "filtra.py")
fi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fi)

T0 = int(datetime(2026, 2, 1, tzinfo=UTC).timestamp() * 1000)  # inicio de la historia inventada
H = 3_600_000


def ej(sim, lado, qty, precio, t, tipo="Trade", fee="0.0123"):
    return {"symbol": sim, "side": lado, "execQty": qty, "execPrice": precio, "execType": tipo, "execTime": str(t),
            "execValue": str(round(float(qty) * float(precio), 4)), "execFee": fee, "execId": f"x{t}{sim}{qty}"}


def ci(sim, lado, t, pnl, cev):
    return {"symbol": sim, "side": lado, "createdTime": str(t), "updatedTime": str(t + 500), "closedPnl": pnl,
            "cumEntryValue": cev, "avgEntryPrice": "43217.5531", "avgExitPrice": "43301.7713", "qty": "0.1371"}


def privado() -> dict:
    t = T0 + 10 * H
    e = [  # BTC largo con dos cierres parciales y una ejecucion de Funding en medio
        ej("BTCUSDT", "Buy", "0.1371", "43217.5531", t),
        ej("BTCUSDT", "Sell", "0.0503", "43301.7713", t + H),
        ej("BTCUSDT", "Sell", "0.0517", "43011.9917", t + 2 * H, tipo="Funding"),
        ej("BTCUSDT", "Sell", "0.0868", "43355.1239", t + 3 * H),
        # ETH: corto 1.3017, volteo comprando 2.0071 (queda largo 0.7054), cierra vendiendo 0.7054
        ej("ETHUSDT", "Sell", "1.3017", "2311.4417", t + 4 * H),
        ej("ETHUSDT", "Buy", "2.0071", "2299.8813", t + 5 * H),
        ej("ETHUSDT", "Sell", "0.7054", "2321.6629", t + 6 * H),
        # SOL fuera de la historia del mapa (2025)
        ej("SOLUSDT", "Buy", "3.1415", "187.4421", T0 - 60 * 24 * H),
        ej("SOLUSDT", "Sell", "3.1415", "189.0013", T0 - 60 * 24 * H + 2 * H),
    ]
    c = [ci("BTCUSDT", "Sell", t + H, "4.2361", "2173.8401"), ci("BTCUSDT", "Sell", t + 3 * H, "11.7319", "3751.2297"),
         ci("ETHUSDT", "Buy", t + 5 * H, "15.0311", "3008.8113"), ci("ETHUSDT", "Sell", t + 6 * H, "15.3337", "1622.3413"),
         ci("SOLUSDT", "Sell", T0 - 60 * 24 * H + 2 * H, "4.8977", "588.8411")]
    for i in range(12):  # doce BTC largos mas: un grupo con n >= 10
        ti = t + (20 + 6 * i) * H
        e += [ej("BTCUSDT", "Buy", "0.0211", "44017.1173", ti), ej("BTCUSDT", "Sell", "0.0211", "44101.3391", ti + H)]
        c.append(ci("BTCUSDT", "Sell", ti + H, ("1.7771" if i % 3 else "-0.9133"), "928.7611"))
    return {"cierres": c, "ejecuciones": e}


def estados() -> dict:
    mins = [T0 // 60000 + 240 * i for i in range(6 * 40)]
    return {"k": 2, "simbolos": {
        "BTCUSDT": {"minuto": mins, "S": [3] * len(mins), "rsi4h": [25.0] * len(mins)},
        "ETHUSDT": {"minuto": mins, "S": [-2] * len(mins), "rsi4h": [75.0] * len(mins)},
        "SOLUSDT": {"minuto": mins, "S": [0] * len(mins), "rsi4h": [None] * len(mins)}}}


def test_reconstruye_parciales_volteo_y_funding():
    ops, causas = fi.reconstruye(privado()["ejecuciones"])
    assert causas == {"ejecucion execType=Funding (no cuenta)": 1}
    btc = [o for o in ops if o["sim"] == "BTCUSDT"]
    assert len(btc) == 13 and btc[0]["lado"] == 1 and btc[0]["fin"] - btc[0]["ini"] == 3 * H  # Funding no la cierra
    eth = sorted((o for o in ops if o["sim"] == "ETHUSDT"), key=lambda o: o["ini"])
    assert [o["lado"] for o in eth] == [-1, 1]
    assert eth[0]["fin"] == eth[1]["ini"]  # el volteo cierra y abre en la misma ejecucion
    v = fi._d(round(2.0071 * 2299.8813, 4))
    parte = fi._d("1.3017") / fi._d("2.0071")
    assert eth[1]["val"] == fi._d(round(0.7054 * 2321.6629, 4)) + v * (1 - parte)
    assert eth[0]["fee"] + eth[1]["fee"] == fi._d("0.0123") * 3


def test_asigna_cierres_y_rendimiento():
    p = privado()
    ops, _ = fi.reconstruye(p["ejecuciones"])
    assert fi.asigna(ops, p["cierres"]) == {}
    b0 = min((o for o in ops if o["sim"] == "BTCUSDT"), key=lambda o: o["ini"])
    assert b0["n_cierres"] == 2 and b0["pnl"] == fi._d("4.2361") + fi._d("11.7319")
    assert b0["entrada"] == fi._d("2173.8401") + fi._d("3751.2297")
    eth = sorted((o for o in ops if o["sim"] == "ETHUSDT"), key=lambda o: o["ini"])
    assert [o["n_cierres"] for o in eth] == [1, 1] and eth[0]["pnl"] == fi._d("15.0311")


def test_cierre_sin_operacion_tiene_causa():
    ops, _ = fi.reconstruye(privado()["ejecuciones"])
    malos = [ci("XRPUSDT", "Sell", T0, "1.1111", "100.0001"), ci("BTCUSDT", "Buy", T0 + 11 * H, "1.1111", "100.0001")]
    assert fi.asigna(ops, malos) == {"simbolo sin operaciones cerradas": 1,
                                     "fuera de toda operacion de su lado (hora)": 1}


def test_estados_y_fuera_de_historia():
    doc = estados()
    k, est = fi.estados(doc)
    o = {"sim": "SOLUSDT", "lado": 1, "ini": T0 - 86_400_000}
    assert fi.estado(o, k, est) == "sin estado: entrada antes de la historia del mapa"
    o = {"sim": "BTCUSDT", "lado": -1, "ini": T0 + 5 * H}
    assert fi.estado(o, k, est) == "EN CONTRA" and o["S"] == 3
    o = {"sim": "ETHUSDT", "lado": -1, "ini": T0 + 5 * H}
    assert fi.estado(o, k, est) == "A FAVOR"
    o = {"sim": "BTCUSDT", "lado": 1, "ini": (doc["simbolos"]["BTCUSDT"]["minuto"][-1] + 240) * 60000}
    assert fi.estado(o, k, est) == "sin estado: entrada despues del fin de la historia del mapa"
    assert fi.estado({"sim": "ADAUSDT", "lado": 1, "ini": T0}, k, est) == "sin estado: activo fuera del mapa"


def _corre(p: dict, doc: dict) -> str:
    with tempfile.TemporaryDirectory() as d:
        pp, pe = pathlib.Path(d, "p.json"), pathlib.Path(d, "e.json")
        pp.write_text(json.dumps(p))
        pe.write_text(json.dumps(doc))
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / "filtra.py"), str(pp), str(pe)],
                           capture_output=True, text=True, check=True)
    return r.stdout


def test_salida_agregada_y_sin_datos_privados():
    p = privado()
    out = _corre(p, estados())
    assert "16 operaciones reconstruidas" in out
    assert "execType=Funding (no cuenta): 1" in out
    assert "sin asignar 0" in out
    assert "sin estado: entrada antes de la historia del mapa: 1" in out
    tot = next(ln for ln in out.splitlines() if "TOTAL" in ln)
    assert "n=16 " in tot and "acierto=" in tot and "ic90=" in tot and "comisiones=" in tot
    assert next(ln for ln in out.splitlines() if "EN CONTRA" in ln).rstrip().endswith("n=1")  # el largo de ETH tras el volteo
    assert any(ln.strip().startswith("largo con rsi4h < 30") and "n=13 " in ln for ln in out.splitlines())
    corto = next(ln for ln in out.splitlines() if ln.strip().startswith("corto con rsi4h > 70"))
    assert corto.rstrip().endswith("n=1")  # n < 10: solo su n
    privados = set()
    for f in p["ejecuciones"] + p["cierres"]:
        for kk, v in f.items():
            if kk not in ("symbol", "side", "execType", "execId"):
                privados.add(str(v))
    for t in [int(f["execTime"]) for f in p["ejecuciones"]]:
        d = datetime.fromtimestamp(t / 1000, UTC)
        privados |= {d.strftime("%Y-%m-%d"), d.strftime("%d/%m"), d.strftime("%H:%M"), str(t // 1000), str(t // 60000)}
    fugas = sorted(x for x in privados if x in out)
    assert not fugas, fugas
    assert "USD " not in out and "$" not in out


def test_lee_el_filtra_estados_commiteado():
    doc = json.loads((RAIZ / "scripts" / "filtra_estados.json").read_text())
    assert set(doc["simbolos"]) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"} and doc["k"] >= 1
    for v in doc["simbolos"].values():
        m = v["minuto"]
        assert len(m) == len(v["S"]) == len(v["rsi4h"]) and all(b - a == 240 for a, b in zip(m, m[1:], strict=False))
        assert m[0] == int(datetime(2026, 1, 1, tzinfo=UTC).timestamp()) // 60
    out = "\n".join(fi.informe(privado(), doc))
    assert "operaciones sin estado del mapa: 1" in out  # solo la de SOL de 2025


def test_spearman_con_empates_a_mano():
    assert fi.rangos([1, 2, 2, 3]) == [1.0, 2.5, 2.5, 4.0]
    # rx = [1, 2.5, 2.5, 4], ry = [1, 3, 2, 4]: sxy = 4.5, sxx = 4.5, syy = 5 -> rho = 3 / sqrt(22.5) = 3 / sqrt(10)
    assert abs(fi.spearman([1, 2, 2, 3], [1, 3, 2, 4]) - 3 / 10 ** 0.5) < 1e-12
    # empates en los dos: rx = [1.5, 1.5, 3.5, 3.5], ry = [1, 2.5, 2.5, 4]: sxy = 3, sxx = 4, syy = 4.5
    assert abs(fi.spearman([1, 1, 2, 2], [1, 2, 2, 3]) - 3 / 18 ** 0.5) < 1e-12
    assert fi.spearman_linea([1] * 9, list(range(9))).rstrip().endswith("n=9")  # n < 10: solo su n
    assert "rho=+1.000" in fi.spearman_linea(list(range(10)), list(range(10)))


def test_secciones_por_nivel_de_v():
    out = _corre(privado(), estados())
    lns = [ln.strip() for ln in out.splitlines()]
    sec = lns[lns.index("por nivel de v = lado*S (operaciones con estado del mapa):") + 1:]
    assert [ln.split("  ")[0] for ln in sec] == [
        "v <= -2", "v = -1", "v = 0", "v = +1", "v >= +2", "largo con v <= -2", "largo con v >= +2",
        "corto con v <= -2", "corto con v >= +2", "spearman(v, rendimiento)"]
    # 13 BTC largos con S=3 (v=+3), el ETH corto con S=-2 (v=+2), el ETH largo (v=-2); SOL sin estado
    assert sec[0].endswith("n=1") and sec[1].endswith("n=0") and sec[2].endswith("n=0") and sec[3].endswith("n=0")
    assert "n=14 " in sec[4] and "acierto=" in sec[4]
    assert sec[5].endswith("n=1") and "n=13 " in sec[6] and sec[7].endswith("n=0") and sec[8].endswith("n=1")
    assert "n=15 rho=" in sec[9]


def test_sin_imports_del_repo():
    src = (RAIZ / "scripts" / "filtra.py").read_text()
    mods = {ln.split()[1].split(".")[0] for ln in src.splitlines() if ln.startswith(("import ", "from "))}
    assert mods <= {"__future__", "bisect", "json", "random", "statistics", "sys", "decimal"}, mods
