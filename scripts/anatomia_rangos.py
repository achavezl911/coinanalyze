"""LOS RANGOS de la anatomia (BOT-3e, remate 1): rangos de 1 h, como acaban y que estado los anticipa. El criterio,
en `anatomia_comun.py` (REMATE 1, RANGOS). numpy. Corre en 143.

USO:  python anatomia_rangos.py HIST OUT.json [--control]
      HIST = el directorio de `zonas_historia.py` y `mapa_datos.py` (/srv/coinanalyze/historia-bot).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anatomia_comun as C  # noqa: E402

NAN = np.nan
ESTADOS = ("dp_bajo", "dp_alto", "ds_bajo", "ds_alto", "d_oi", "posicion", "compresion", "toques_alto",
           "toques_bajo", "tend_30d", "top", "ruido")
LADOS = ("ARRIBA", "ABAJO")


# ---------------------------------------------------------------- carga: barras de 1 h
def horas(hist: Path, s: str) -> dict:
    S = f"{s}USDT"
    m = json.loads((hist / "historia.json").read_text())["simbolos"][S]
    t0, n = int(m["t0"]), int(m["n"])
    off = (-t0) % 60
    nh = (n - off) // 60
    def ld(nom):
        f = hist / f"{S}.{nom}.f64"
        if not f.exists():
            return np.full((nh, 60), NAN)
        x = np.fromfile(f, dtype="<f8")[off:off + nh * 60]
        return np.concatenate([x, np.full(nh * 60 - len(x), NAN)]).reshape(nh, 60)
    def suma(x):
        return np.where(np.isfinite(x).any(1), np.nansum(x, 1), NAN)
    qv, qb, sqv, sqb = ld("qv"), ld("qb"), ld("spot.qv"), ld("spot.qb")
    Hd = {"ts": (t0 + off + 60 * np.arange(nh, dtype=np.int64)) * 60, "o": ld("o")[:, 0],
          "h": np.nanmax(ld("h"), 1), "l": np.nanmin(ld("l"), 1), "c": ld("c")[:, -1], "qv": suma(qv),
          "dp": suma(2 * qb - qv), "sqv": suma(sqv), "ds": suma(2 * sqb - sqv)}
    mt = hist / f"{S}.metrics.f64"
    if mt.exists():
        M = np.fromfile(mt, dtype="<f8").reshape(-1, 6)
        j = (off + 60 * np.arange(nh) + 55) // 5
        ok = j < len(M)
        Hd["oi"] = np.where(ok, M[np.minimum(j, len(M) - 1), 0], NAN)
        Hd["top"] = np.where(ok, M[np.minimum(j, len(M) - 1), 3], NAN)
    else:
        Hd["oi"] = Hd["top"] = np.full(nh, NAN)
    return Hd


# ---------------------------------------------------------------- piezas (barra k: solo barras <= k)
def atr_diario(ts, h, l, c):
    """Por barra: media del rango verdadero de los RANGO_ATR_DIAS dias UTC completos anteriores."""
    dk = ts // 86400
    k0 = dk[0]
    nd = int(dk[-1] - k0 + 1)
    Hd, Ld, Cd = np.full(nd, -np.inf), np.full(nd, np.inf), np.full(nd, NAN)
    np.maximum.at(Hd, dk - k0, np.where(np.isfinite(h), h, -np.inf))
    np.minimum.at(Ld, dk - k0, np.where(np.isfinite(l), l, np.inf))
    Cd[dk - k0] = c                                    # el ultimo de cada dia queda (orden de ts)
    cp = np.concatenate([[NAN], Cd[:-1]])
    tr = np.fmax(Hd, cp) - np.fmin(Ld, cp)
    tr[~np.isfinite(tr)] = NAN
    cs = np.concatenate([[0.0], np.cumsum(np.nan_to_num(tr))])
    cn = np.concatenate([[0], np.cumsum(np.isfinite(tr))])
    d = np.arange(nd)
    a = np.maximum(d - C.RANGO_ATR_DIAS, 0)
    m = np.where((cn[d] - cn[a]) == C.RANGO_ATR_DIAS, (cs[d] - cs[a]) / C.RANGO_ATR_DIAS, NAN)
    m[d < C.RANGO_ATR_DIAS] = NAN
    return m[dk - k0]


def grupos(idx):
    return 0 if not len(idx) else 1 + int(np.sum(np.diff(idx) >= C.RANGO_SEP))


def cumple(h, l, c, atr, k, W):
    """(alto, bajo, toques_alto, toques_bajo) si en k hay rango de ventana W; si no, None."""
    if k - W + 1 < 0 or not np.isfinite(atr[k]):
        return None
    hw, lw = h[k - W + 1:k + 1], l[k - W + 1:k + 1]
    if not (np.isfinite(hw).all() and np.isfinite(lw).all()):
        return None
    alto, bajo = hw.max(), lw.min()
    alt = alto - bajo
    if not (0 < alt <= C.RANGO_ATR * atr[k]) or not (bajo <= c[k] <= alto):
        return None
    ta = np.flatnonzero(hw >= alto - C.RANGO_BANDA * alt)
    tb = np.flatnonzero(lw <= bajo + C.RANGO_BANDA * alt)
    if ta[-1] - ta[0] < C.RANGO_SEP or tb[-1] - tb[0] < C.RANGO_SEP:
        return None
    return alto, bajo, grupos(ta), grupos(tb)


def final(h, l, c, k, alto, bajo):
    """Clase, lado_final, barra en que acaba y si llega a 1 altura mas alla; None si la historia no alcanza."""
    alt = alto - bajo
    fin = k + 24 * C.RANGO_DIAS
    if fin >= len(c):
        return None
    clase, j = None, k + 1
    while j <= fin:
        arriba, abajo = c[j] >= alto + C.RANGO_FUERA * alt, c[j] <= bajo - C.RANGO_FUERA * alt
        if arriba or abajo:
            if j + C.RANGO_VUELTA >= len(c):
                return None
            v = c[j + 1:j + 1 + C.RANGO_VUELTA]
            dentro = np.flatnonzero((v >= bajo) & (v <= alto))
            lado = "ARRIBA" if arriba else "ABAJO"
            if not len(dentro):
                clase = clase or lado
                acaba = j + C.RANGO_VUELTA
                break
            clase = clase or "FALSA"
            j = j + 1 + int(dentro[0])
            continue
        j += 1
    else:
        lado, acaba = "SIN SALIDA", fin
        clase = clase or "SIN SALIDA"
    return {"clase": clase, "lado_final": lado, "acaba": int(acaba),
            "mas_alla_arriba": bool(np.nanmax(h[k + 1:fin + 1]) > alto + alt),
            "mas_alla_abajo": bool(np.nanmin(l[k + 1:fin + 1]) < bajo - alt)}


def estado(Hd, k, W, alto, bajo, ta, tb):
    sl = slice(k - W + 1, k + 1)
    c, alt = Hd["c"], alto - bajo
    cw = c[sl]
    bajo3, alto3 = cw <= bajo + alt / 3, cw >= alto - alt / 3
    def frac(x, den, m):
        d = np.nansum(Hd[den][sl])
        return float(np.nansum(Hd[x][sl][m]) / d) if d > 0 else NAN
    hw, lw = Hd["h"][sl], Hd["l"][sl]
    mitad = W // 2
    a1, a2 = hw[:mitad].max() - lw[:mitad].min(), hw[mitad:].max() - lw[mitad:].min()
    oi = Hd["oi"]
    return {"dp_bajo": frac("dp", "qv", bajo3), "dp_alto": frac("dp", "qv", alto3),
            "ds_bajo": frac("ds", "sqv", bajo3), "ds_alto": frac("ds", "sqv", alto3),
            "d_oi": float(oi[k] / oi[k - W + 1] - 1) if oi[k - W + 1] > 0 else NAN,
            "posicion": float((c[k] - bajo) / alt), "compresion": float(a2 / a1) if a1 > 0 else NAN,
            "toques_alto": float(ta), "toques_bajo": float(tb),
            "tend_30d": float(c[k] / c[k - 720] - 1) if k >= 720 else NAN, "top": float(Hd["top"][k])}


# ---------------------------------------------------------------- deteccion (secuencial, causal)
def rangos(Hd, control=False, semilla=C.SEMILLA):
    """Lista de rangos con estado y final. Con control, cada rango con planta > 2/3 recibe la deriva plantada en
    las barras siguientes (se copian las series: Hd no se toca)."""
    Hd = {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in Hd.items()}
    h, l, c, o, ts = Hd["h"], Hd["l"], Hd["c"], Hd["o"], Hd["ts"]
    atr = atr_diario(ts, h, l, c)
    rng = np.random.default_rng(semilla)
    ev, k = [], max(C.RANGO_W) - 1
    while k < len(c):
        hit = next(((W, r) for W in C.RANGO_W if (r := cumple(h, l, c, atr, k, W)) is not None), None)
        if hit is None:
            k += 1
            continue
        W, (alto, bajo, ta, tb) = hit
        e = {"k": k, "ts": int(ts[k]), "W": W, "alto": float(alto), "bajo": float(bajo),
             **estado(Hd, k, W, alto, bajo, ta, tb), "ruido": float(rng.random())}
        if control:
            e["planta"] = float(rng.random())
            if e["planta"] > 2 / 3:
                j = np.arange(1, len(c) - k)
                f = 1 + C.RANGO_PLANTA * (alto - bajo) / c[k] * np.minimum(j, 24) / 24
                for x in (o, h, l, c):
                    x[k + 1:] *= f
                atr = atr_diario(ts, h, l, c)
        fi = final(h, l, c, k, alto, bajo)
        if fi is None:
            break
        e.update(fi, ts_acaba=int(ts[fi["acaba"]]))
        ev.append(e)
        k = fi["acaba"] + 1
    return ev


# ---------------------------------------------------------------- celdas
def binom_cola(k, n, p=0.5):
    return float(sum(math.comb(n, i) for i in range(k, n + 1)) * p ** n) if n else None


def celdas(ev_por_sim, estados=ESTADOS):
    corte = C._ts(C.RANGO_CORTE)
    out = []
    for s, ev in ev_por_sim.items():
        aj = [e for e in ev if e["ts_acaba"] + 3600 <= corte]
        pr = [e for e in ev if e["ts"] >= corte]
        for est in estados:
            xa = np.array([e.get(est, NAN) for e in aj], float)
            xa = xa[np.isfinite(xa)]
            if len(xa) < 3:
                continue
            q1, q2 = np.quantile(xa, [1 / 3, 2 / 3])
            def ter(e):
                x = e.get(est, NAN)
                return None if not np.isfinite(x) else (0 if x <= q1 else (1 if x <= q2 else 2))
            for t in range(3):
                fila = {"simbolo": s, "estado": est, "tercil": t, "cortes": [float(q1), float(q2)]}
                for per, lista in (("ajuste", aj), ("prueba", pr)):
                    g = [e for e in lista if ter(e) == t]
                    n = len(g)
                    d = {"n": n, **{f"pct_{cl}": (sum(e["clase"] == cl for e in g) / n if n else None)
                                    for cl in ("ARRIBA", "ABAJO", "FALSA", "SIN SALIDA")},
                         "pct_1_altura_arriba": sum(e["mas_alla_arriba"] for e in g) / n if n else None,
                         "pct_1_altura_abajo": sum(e["mas_alla_abajo"] for e in g) / n if n else None}
                    for lado in LADOS:
                        x = sum(e["lado_final"] == lado for e in g)
                        d[lado] = {"exitos": x, "wilson90_inf": C.wilson_inferior(x, n),
                                   "p": binom_cola(x, n) if n >= C.N_MIN_CONFIRMA else None}
                    fila[per] = d
                out.append(fila)
    ps = [f["ajuste"][lado]["p"] for f in out for lado in LADOS]
    qs = iter(C.benjamini_hochberg(ps))
    for f in out:
        for lado in LADOS:
            a, p = f["ajuste"], f["prueba"]
            q = next(qs)
            a[lado]["q"] = q
            if a["n"] < C.N_MIN_CONFIRMA:
                v = "SIN CALIBRAR"
            else:
                wa = a[lado]["wilson90_inf"] > 0.5
                wp = p["n"] >= C.N_MIN_CONFIRMA and p[lado]["wilson90_inf"] > 0.5
                v = "PASA" if (wa and wp and q is not None and q <= C.FDR_Q) else (
                    "CONTEXTO" if (wa or wp) else "RUIDO")
            f[f"veredicto_{lado}"] = v
    return out


def ve(cs):
    planta = any(f["estado"] == "planta" and f["tercil"] == 2 and f["veredicto_ARRIBA"] == "PASA" for f in cs)
    ruido = sum(f["estado"] == "ruido" and f[f"veredicto_{lado}"] == "PASA" for f in cs for lado in LADOS)
    return {"ve": bool(planta and ruido == 0), "planta_pasa": planta, "ruido_que_pasa": int(ruido)}


def corre(hist, out, control=False):
    hist = Path(hist)
    ev = {s: rangos(horas(hist, s), control=control, semilla=C.SEMILLA + i) for i, s in enumerate(C.SIMBOLOS)}
    cs = celdas(ev, ESTADOS + (("planta",) if control else ()))
    res = {"criterio": "scripts/anatomia_comun.py (REMATE 1, RANGOS)", "hist": str(hist), "control": control,
           "rangos": {s: len(v) for s, v in ev.items()}, "celdas": cs}
    if control:
        res.update(ve(cs))
    Path(out).write_text(json.dumps(res, indent=1, default=float))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("hist", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--control", action="store_true")
    a = ap.parse_args(argv)
    corre(a.hist, a.out, a.control)
    return 0


if __name__ == "__main__":
    sys.exit(main())
