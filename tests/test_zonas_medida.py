"""BOT-3a: el criterio de las zonas (scripts/zonas_comun.py) y la tabla medida (app/bot/zonas_medida.json).

Biblioteca estandar: la fila de la muestra fija se reproduce sin numpy, con las reglas de zonas_comun, y tiene que
dar los mismos n, aciertos, stops y neto que el barrido vectorizado escribio en el json.
"""

from __future__ import annotations

import json
import lzma
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import zonas_comun as zc  # noqa: E402

MEDIDA = RAIZ / "app" / "bot" / "zonas_medida.json"
MUESTRA = RAIZ / "tests" / "datos" / "zonas_muestra.json.xz"


def _camino(*barras):
    """Barras (h, l, c) a listas o, h, l, c; la apertura es el cierre anterior."""
    h = [b[0] for b in barras]
    lo = [b[1] for b in barras]
    c = [b[2] for b in barras]
    return [c[0]] + c[:-1], h, lo, c


def test_empate_en_la_barra_gana_el_stop():
    _, h, lo, c = _camino((100, 100, 100), (101.5, 99.0, 100))
    assert zc.resultado(h, lo, c, 1, 100.0, 1, 0.01, 0.006, False)[:1] == ("SL",)
    assert zc.resultado(h, lo, c, 1, 100.0, -1, 0.01, 0.006, False)[:1] == ("SL",)


def test_en_la_barra_del_toque_solo_cuenta_el_stop():
    _, h, lo, c = _camino((100, 100, 100), (101.5, 99.9, 100.8), (100.9, 100.5, 100.8))
    assert zc.resultado(h, lo, c, 1, 100.0, 1, 0.01, 0.006, True)[0] == "VENCE"
    assert zc.resultado(h, lo, c, 1, 100.0, 1, 0.01, 0.006, False) == ("TP", 0.01 - zc.FEE, 1)


def test_sin_tocar_vence_al_cierre_con_su_neto():
    _, h, lo, c = _camino((100, 100, 100), (100.5, 99.8, 100.2))
    r = zc.resultado(h, lo, c, 1, 100.0, -1, 0.02, 0.006, False)
    assert r[0] == "VENCE" and r[2] == 1 and r[1] == pytest.approx(-0.002 - zc.FEE)


def test_equilibrios_del_encargo():
    assert round(zc.EQUILIBRIO["A"], 3) == 0.273 and round(zc.EQUILIBRIO["B"], 3) == 0.444


def test_toque_reaccion_y_ruptura():
    # 61 barras que bajan de 101 a 100.2, toque de 100 desde arriba, cierre en 100.3 (reaccion: largo)
    h = [101.0] * 61 + [100.4, 100.4, 100.4]
    lo = [100.2] * 61 + [99.95, 100.2, 100.2]
    c = [100.6] * 61 + [100.3, 100.3, 100.3]
    o = [100.6] * 64
    assert zc.es_toque(h, lo, c, 61, 100.0) == 1
    assert zc.operacion(o, h, lo, c, 61, 100.0, 1, "reaccion") == (1, 100.3, 63)
    assert zc.operacion(o, h, lo, c, 61, 100.0, 1, "ruptura") is None
    assert zc.operacion(o, h, lo, c, 61, 100.0, 1, "toque") == (1, 100.0, 61)


def _medida() -> dict:
    if not MEDIDA.exists():
        pytest.skip("sin app/bot/zonas_medida.json")
    return json.loads(MEDIDA.read_text())


def test_pasa_cumple_el_criterio_entero():
    d = _medida()
    C = d["campos"]
    filas = [dict(zip(C, f, strict=True)) for f in d["filas"]]
    z = zc.z_bonferroni(d["cuenta"]["candidatas"])
    assert d["cuenta"]["z_bonferroni"] == pytest.approx(z, abs=1e-3)
    pasan = 0
    for f in filas:
        assert f["n"] >= zc.N_MIN
        lo95 = zc.wilson(f["aciertos"], f["n"])[0]
        lob = zc.wilson(f["aciertos"], f["n"], z)[0]
        assert f["wilson95_lo"] == pytest.approx(lo95, abs=1e-4)
        assert f["wilson_bonf_lo"] == pytest.approx(lob, abs=1e-4)
        ok = bool(f["candidata"]) and lob > max(zc.EQUILIBRIO[f["esquema"]], f["azar"])
        assert (f["veredicto"] == "PASA") == ok, f
        pasan += ok
    assert pasan == d["cuenta"]["pasan"]


def test_la_muestra_reproduce_su_fila():
    d = _medida()
    if not MUESTRA.exists():
        pytest.skip("sin muestra")
    assert MUESTRA.stat().st_size < 2 * 1024 * 1024
    m = json.loads(lzma.decompress(MUESTRA.read_bytes()))
    assert m["huella_historia"] == d["huella_historia"]
    C = d["campos"]
    filas = {f[0]: dict(zip(C, f, strict=True)) for f in m["filas"]}
    assert set(filas) == set(zc.ESQUEMAS)
    lado = 1 if m["lado"] == "largo" else -1
    cuenta = {e: [0, 0, 0, 0.0] for e in zc.ESQUEMAS}
    for ev in m["eventos"]:
        o, h, lo, c = ev["o"], ev["h"], ev["l"], ev["c"]
        k, L = ev["k"] - ev["w0"], ev["L"]
        desde = zc.es_toque(h, lo, c, k, L)
        assert desde != 0, ev["k"]
        op = zc.operacion(o, h, lo, c, k, L, desde, m["modo"])
        assert op is not None and op[0] == lado, ev["k"]
        _, P, s = op
        for e, (tp, sl) in zc.ESQUEMAS.items():
            r, neto, _ = zc.resultado(h, lo, c, s, P, lado, tp, sl, m["modo"] == "toque")
            q = cuenta[e]
            q[0] += 1
            q[1] += r == "TP"
            q[2] += r == "SL"
            q[3] += neto
    for e, (n, k, sl, neto) in cuenta.items():
        f = filas[e]
        assert (n, k, sl) == (f["n"], f["aciertos"], f["stops"]), e
        assert 100 * neto / n == pytest.approx(f["neto_pct"], abs=1e-4), e
