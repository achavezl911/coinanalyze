"""El ESTUDIO de las zonas (campana BOT-3a): el barrido entero de una pasada, con el criterio de `zonas_comun`.

Necesita numpy, que ni el .venv del repo ni la CI tienen: corre con el venv APARTE de la historia
(/srv/coinanalyze/historia-bot/venv). Nada de app/ lo importa; la reproduccion de una fila (tests/test_zonas_medida.py)
va con biblioteca estandar.

USO:  venv/bin/python scripts/zonas_estudio.py HIST app/bot/zonas_medida.json tests/datos/zonas_muestra.json.xz
    HIST: el directorio de `zonas_historia.py` (columnas, historia.json, funding).
"""

from __future__ import annotations

import json
import lzma
import math
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zonas_comun as zc  # noqa: E402

import app.rafagas as rf  # noqa: E402

SIMBOLOS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
ACTIVOS = ("BTC", "ETH", "SOL", "TODOS")
LINEAS = (("PDH", "dia_ext"), ("PDL", "dia_ext"), ("PWH", "semana_ext"), ("PWL", "semana_ext"),
          ("POC", "perfil_poc"), ("VAH", "perfil_va"), ("VAL", "perfil_va"), ("VWAP", "vwap"),
          ("V+1", "vwap_1s"), ("V-1", "vwap_1s"), ("V+2", "vwap_2s"), ("V-2", "vwap_2s"),
          ("R3H", "rango_3d"), ("R3L", "rango_3d"), ("G1H", "giro_1h"), ("G1L", "giro_1h"),
          ("G4H", "giro_4h"), ("G4L", "giro_4h"), ("RU", "redondo"), ("RD", "redondo"))
ESQ = tuple(zc.ESQUEMAS)
NC = len(zc.CONTEXTOS)
T0 = time.time()
HUMO = os.environ.get("ZONAS_HUMO") == "1"
REPS = 1 if HUMO else zc.AZAR_REPS


def log(x: str) -> None:
    print(f"{time.time() - T0:7.0f}s {x}", flush=True)


def minuto(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp()) // 60


class Activo:
    def __init__(self, hist: Path, s: str, meta: dict):
        m = meta["simbolos"][s]
        self.s, self.t0, self.n = s, m["t0"], m["n"]
        for col in ("o", "h", "l", "c", "qv", "qb"):
            setattr(self, "lo" if col == "l" else col, np.fromfile(hist / f"{s}.{col}.f64", dtype="<f8"))
        if HUMO:  # banco de humo: 2023-10 .. 2024-01, una repeticion de azar; no es una medida
            a0, a1 = minuto("2023-10-01") - self.t0, minuto("2024-02-01") - self.t0
            for col in ("o", "h", "lo", "c", "qv", "qb"):
                setattr(self, col, getattr(self, col)[a0:a1].copy())
            self.t0, self.n = self.t0 + a0, a1 - a0
        mm = self.t0 + np.arange(self.n, dtype=np.int64)
        self.di = (mm // 1440 - mm[0] // 1440).astype(np.int32)
        self.ds = np.r_[0, np.flatnonzero(np.diff(self.di)) + 1]  # inicio de cada dia
        self.hora = ((mm % 1440) // 60).astype(np.int8)
        self.mm = mm


def ffill(x: np.ndarray) -> np.ndarray:
    i = np.where(np.isnan(x), 0, np.arange(len(x)))
    np.maximum.accumulate(i, out=i)
    return x[i]


def antes(x: np.ndarray) -> np.ndarray:
    return np.r_[np.nan, x[:-1]]


def giros(h: np.ndarray, lo: np.ndarray, grupo: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ultimo maximo/minimo de giro (2 velas a cada lado) del marco `grupo`, efectivo desde la vela j+3."""
    st = np.r_[0, np.flatnonzero(np.diff(grupo)) + 1]
    H, L = np.maximum.reduceat(h, st), np.minimum.reduceat(lo, st)
    nh = len(H)
    gh, gl = np.full(nh, np.nan), np.full(nh, np.nan)
    j = np.arange(2, nh - 3)
    sh = (H[j] > H[j - 1]) & (H[j] > H[j - 2]) & (H[j] >= H[j + 1]) & (H[j] >= H[j + 2])
    sl = (L[j] < L[j - 1]) & (L[j] < L[j - 2]) & (L[j] <= L[j + 1]) & (L[j] <= L[j + 2])
    gh[j[sh] + 3], gl[j[sl] + 3] = H[j[sh]], L[j[sl]]
    gi = np.cumsum(np.r_[0, np.diff(grupo) != 0])
    return ffill(gh)[gi], ffill(gl)[gi]


def lineas(a: Activo):
    """(nombre, clase, L por barra), una a una para no tener las veinte en memoria."""
    di, ds = a.di, a.ds
    DH, DL = np.maximum.reduceat(a.h, ds), np.minimum.reduceat(a.lo, ds)
    DC = a.c[np.r_[ds[1:], a.n] - 1]
    yield "PDH", antes(DH)[di]
    yield "PDL", antes(DL)[di]
    dd = a.mm // 1440
    wk = (dd + 3) // 7
    wi = (wk - wk[0]).astype(np.int32)
    ws = np.r_[0, np.flatnonzero(np.diff(wi)) + 1]
    yield "PWH", antes(np.maximum.reduceat(a.h, ws))[wi]
    yield "PWL", antes(np.minimum.reduceat(a.lo, ws))[wi]
    # perfil del dia anterior
    nd = len(ds)
    poc, vah, val = (np.full(nd, np.nan) for _ in range(3))
    fin = np.r_[ds[1:], a.n]
    tp = (a.h + a.lo + a.c) / 3
    for d in range(1, nd):
        x, q = tp[ds[d - 1]:fin[d - 1]], a.qv[ds[d - 1]:fin[d - 1]]
        if q.sum() <= 0:
            continue
        g = DC[d - 1] * 0.001
        b = np.floor(x / g).astype(np.int64)
        b0 = b.min()
        vol = np.bincount(b - b0, weights=q)
        p = int(vol.argmax())
        lo_, hi_, acc, tot = p, p, vol[p], vol.sum()
        while acc < 0.7 * tot:
            vb = vol[lo_ - 1] if lo_ > 0 else -1.0
            va = vol[hi_ + 1] if hi_ + 1 < len(vol) else -1.0
            if va >= vb:
                hi_ += 1
                acc += va
            else:
                lo_ -= 1
                acc += vb
        poc[d], vah[d], val[d] = (b0 + p + 0.5) * g, (b0 + hi_ + 1) * g, (b0 + lo_) * g
    yield "POC", poc[di]
    yield "VAH", vah[di]
    yield "VAL", val[di]
    # VWAP del dia con lo cerrado antes de k, centrado en el cierre del dia anterior
    ref = antes(DC)[di]
    ok = tp > 0
    q = np.where(ok, a.qv / np.where(ok, tp, 1), 0.0)
    xc = tp - ref
    C1, C2, C3 = (np.r_[0, np.cumsum(np.nan_to_num(v))] for v in (q, q * xc, q * xc * xc))
    k = np.arange(a.n)
    s0 = ds[di]
    Q = C1[k] - C1[s0]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = (C2[k] - C2[s0]) / Q
        sd = np.sqrt(np.maximum((C3[k] - C3[s0]) / Q - mu * mu, 0))
    vw = np.where((k - s0 >= 60) & (Q > 0), ref + mu, np.nan)
    yield "VWAP", vw
    yield "V+1", vw + sd
    yield "V-1", vw - sd
    yield "V+2", vw + 2 * sd
    yield "V-2", vw - 2 * sd
    del C1, C2, C3, Q, mu, sd, vw, q, xc
    R3H = np.full(nd, np.nan)
    R3L = np.full(nd, np.nan)
    R3H[3:] = np.maximum(np.maximum(DH[:-3], DH[1:-2]), DH[2:-1])
    R3L[3:] = np.minimum(np.minimum(DL[:-3], DL[1:-2]), DL[2:-1])
    yield "R3H", R3H[di]
    yield "R3L", R3L[di]
    g1h, g1l = giros(a.h, a.lo, (a.mm // 60).astype(np.int64))
    yield "G1H", g1h
    yield "G1L", g1l
    del g1h, g1l
    g4h, g4l = giros(a.h, a.lo, (a.mm // 240).astype(np.int64))
    yield "G4H", g4h
    yield "G4L", g4l
    del g4h, g4l
    pc = antes(a.c)
    with np.errstate(invalid="ignore", divide="ignore"):
        paso = 10.0 ** (np.floor(np.log10(pc)) - 1)
        ru = np.ceil(pc / paso) * paso
        ru = np.where(ru == pc, ru + paso, ru)
        yield "RU", ru
        yield "RD", np.floor(pc / paso) * paso


def toques(a: Activo, L: np.ndarray, pc, rmax, rmin) -> tuple[np.ndarray, np.ndarray]:
    with np.errstate(invalid="ignore"):
        up = (pc > L) & (a.lo <= L) & (rmax >= L * (1 + zc.ACERCA))
        dn = (pc < L) & (a.h >= L) & (rmin <= L * (1 - zc.ACERCA))
    ks, last = [], -10 ** 9
    for k in np.flatnonzero(up | dn).tolist():
        if k - last > zc.REARME:
            ks.append(k)
            last = k
    ks = np.array(ks, dtype=np.int64)
    return ks, np.where(up[ks], 1, -1).astype(np.int8)


def operaciones(a: Activo, L: np.ndarray, ks: np.ndarray, desde: np.ndarray):
    """Por toque: la de modo toque y, si se confirma, la de reaccion o ruptura. (modo, lado, P, s, toque)."""
    Lk = L[ks]
    P0 = np.where(desde > 0, np.minimum(a.o[ks], Lk), np.maximum(a.o[ks], Lk))
    idx = np.minimum(ks[:, None] + np.arange(zc.ESPERA + 1), a.n - 1)
    C = a.c[idx]
    upc, dnc = C >= (Lk * (1 + zc.REACCION))[:, None], C <= (Lk * (1 - zc.REACCION))[:, None]
    fu = np.where(upc.any(1), upc.argmax(1), 99)
    fd = np.where(dnc.any(1), dnc.argmax(1), 99)
    r = ks + np.minimum(fu, fd)
    ok = (np.minimum(fu, fd) < 99) & (r + 2 < a.n)
    sube = fu < fd
    lado2 = np.where(sube, 1, -1).astype(np.int8)
    modo2 = np.where(sube == (desde > 0), 1, 2).astype(np.int8)  # rebote del lado del que viene: reaccion
    r = np.where(ok, r, 0)
    return ((np.zeros(len(ks), np.int8), desde, P0, ks, np.ones(len(ks), bool), ks),
            (modo2[ok], lado2[ok], a.c[r[ok] + 1], r[ok] + 2, np.zeros(ok.sum(), bool), ks[ok]))


def resuelve(a: Activo, s: np.ndarray, P: np.ndarray, d: np.ndarray, toq: np.ndarray):
    """(codigo [n,4]: 0 TP 1 SL 2 VENCE, neto [n,4], barra de decision [n,4]) con las reglas de zc.resultado."""
    N = len(s)
    cod = np.zeros((N, 4), np.int8)
    net = np.zeros((N, 4))
    dec = np.zeros((N, 4), np.int64)
    ar = np.arange(zc.HORIZONTE)
    BIG = 10 ** 9
    for b0 in range(0, N, 1024):
        sl_ = slice(b0, b0 + 1024)
        ss, PP, dd, tt = s[sl_], P[sl_], d[sl_] > 0, toq[sl_]
        idx = ss[:, None] + ar
        val = idx < a.n
        idx = np.minimum(idx, a.n - 1)
        H, Lo = a.h[idx], a.lo[idx]
        ult = np.minimum(ss + zc.HORIZONTE, a.n) - 1

        def primero(m):
            m &= val
            return np.where(m.any(1), m.argmax(1), BIG)

        fs, ft = {}, {}
        for sl in {v[1] for v in zc.ESQUEMAS.values()}:
            fs[sl] = primero(np.where(dd[:, None], Lo <= (PP * (1 - sl))[:, None], H >= (PP * (1 + sl))[:, None]))
        for tp in {v[0] for v in zc.ESQUEMAS.values()}:
            m = np.where(dd[:, None], H >= (PP * (1 + tp))[:, None], Lo <= (PP * (1 - tp))[:, None])
            m[tt, 0] = False
            ft[tp] = primero(m)
        sgn = np.where(dd, 1.0, -1.0)
        vence = sgn * (a.c[ult] / PP - 1) - zc.FEE
        for j, (tp, sl) in enumerate(zc.ESQUEMAS.values()):
            a_, b_ = ft[tp], fs[sl]
            esTP, esSL = a_ < b_, (b_ <= a_) & (b_ < BIG)
            cod[sl_, j] = np.where(esTP, 0, np.where(esSL, 1, 2))
            net[sl_, j] = np.where(esTP, tp - zc.FEE, np.where(esSL, -sl - zc.FEE, vence))
            dec[sl_, j] = np.where(esTP, ss + a_, np.where(esSL, ss + b_, ult))
    return cod, net, dec


class Contexto:
    """Los codigos de contexto (indice en zc.CONTEXTOS o -1) de cada dimension, por barra de toque y lado."""

    def __init__(self, a: Activo, btc: Activo | None, fun: tuple[np.ndarray, np.ndarray]):
        self.a, self.btc = a, btc
        ds = a.ds
        DC = a.c[np.r_[ds[1:], a.n] - 1]
        sma = np.convolve(DC, np.ones(20) / 20, mode="full")[:len(DC)]
        sma[:19] = np.nan
        self.sma1d = antes(sma)[a.di]
        g4 = (a.mm // 240).astype(np.int64)
        st4 = np.r_[0, np.flatnonzero(np.diff(g4)) + 1]
        C4 = a.c[np.r_[st4[1:], a.n] - 1]
        s4 = np.convolve(C4, np.ones(20) / 20, mode="full")[:len(C4)]
        s4[:19] = np.nan
        self.sma4h = antes(s4)[np.cumsum(np.r_[0, np.diff(g4) != 0])]
        lr = np.r_[0.0, np.diff(np.log(a.c))]
        rv = np.array([lr[ds[i]:(ds[i + 1] if i + 1 < len(ds) else a.n)].std() for i in range(len(ds))])
        alta = np.full(len(ds), -1, np.int8)
        for d in range(31, len(ds)):
            alta[d] = 1 if rv[d - 1] > np.median(rv[d - 30:d]) else 0
        self.alta = alta[a.di]
        self.fm, self.fr = fun

    def codigos(self, ks: np.ndarray, lado: np.ndarray) -> np.ndarray:
        a, C = self.a, zc.CONTEXTOS.index
        out = np.full((len(ks), len(zc.DIMENSIONES)), -1, np.int8)
        pc = a.c[ks - 1]
        for j, (ref, nom) in enumerate(((self.sma1d[ks], "t1d"), (self.sma4h[ks], "t4h"))):
            sg = np.where(pc > ref, 1, -1)
            out[:, j] = np.where(np.isnan(ref), -1, np.where(sg == lado, C(f"{nom}:favor"), C(f"{nom}:contra")))
        h = a.hora[ks]
        out[:, 2] = np.select([h < 7, h < 13, h < 21], [C("ses:asia"), C("ses:europa"), C("ses:eeuu")],
                              C("ses:cierre"))
        al = self.alta[ks]
        out[:, 3] = np.where(al < 0, -1, np.where(al == 1, C("vol:alta"), C("vol:baja")))
        if self.btc is not None:
            kb = ks + (a.t0 - self.btc.t0)
            okb = (kb >= 61) & (kb < self.btc.n)
            kb = np.where(okb, kb, 61)
            rb = self.btc.c[kb - 1] / self.btc.c[kb - 61] - 1
            out[:, 4] = np.where(~okb | (rb == 0), -1,
                                 np.where(np.sign(rb) == lado, C("lider:favor"), C("lider:contra")))
        j = np.searchsorted(self.fm, a.t0 + ks, side="right") - 1
        fr = np.where(j >= 0, self.fr[np.maximum(j, 0)], 0.0)
        out[:, 5] = np.where(fr == 0, -1, np.where(np.sign(fr) == -lado, C("fun:favor"), C("fun:contra")))
        return out


def funding(hist: Path, s: str) -> tuple[np.ndarray, np.ndarray]:
    filas = [ln.split("\t") for ln in (hist / f"{s}.funding.tsv").read_text().split("\n") if ln]
    filas.sort(key=lambda f: int(f[0]))
    return np.array([int(f[0]) for f in filas], np.int64), np.array([float(f[1]) for f in filas])


def agrega(tablas: list[dict], aj_hasta: dict, pr_desde: dict) -> np.ndarray:
    """Suma por celda: [esq, azar, tramo, modo, clase, activo(4), lado, ctx] -> (n, tp, sl, neto)."""
    shp = (4, 2, 2, 3, len(zc.CLASES), 4, 2, NC)
    tam = int(np.prod(shp))

    def col(c):
        return np.concatenate([t[c] for t in tablas])

    k = col("k")
    ai = np.concatenate([np.full(len(t["k"]), t["activo"], np.int64) for t in tablas])
    aj = np.array([aj_hasta[i] for i in range(3)])[ai]
    pr = np.array([pr_desde[i] for i in range(3)])[ai]
    tramo = np.where(k < aj, 0, np.where((k >= pr) & col("entero"), 1, -1))
    sel = tramo >= 0
    az, mo, cl, la = (col(c)[sel].astype(np.int64) for c in ("azar", "modo", "clase", "lado"))
    tr, ai, ctx, cod, net = tramo[sel], ai[sel], col("ctx")[sel], col("cod")[sel], col("net")[sel]
    miembros = [np.zeros(len(tr), np.int64)] + [ctx[:, j].astype(np.int64) for j in range(ctx.shape[1])]
    acc = np.zeros((4, tam))
    for e in range(4):
        w = (np.ones(len(tr)), cod[:, e] == 0, cod[:, e] == 1, net[:, e])
        for act in (ai, np.full(len(tr), 3)):
            for cx in miembros:
                ok = cx >= 0
                ix = np.ravel_multi_index((np.full(ok.sum(), e), az[ok], tr[ok], mo[ok], cl[ok], act[ok], la[ok],
                                           cx[ok]), shp)
                for q in range(4):
                    acc[q] += np.bincount(ix, weights=w[q][ok].astype(float), minlength=tam)
    return acc.reshape((4,) + shp)


def main(argv: list[str]) -> int:
    hist, salida, muestra = Path(argv[0]), Path(argv[1]), Path(argv[2])
    meta = json.loads((hist / "historia.json").read_text())
    fmeta = json.loads((hist / "funding.json").read_text())
    acts = [Activo(hist, s, meta) for s in SIMBOLOS]
    aj_hasta = {i: minuto(zc.AJUSTE_HASTA) - a.t0 for i, a in enumerate(acts)}
    pr_desde = {i: minuto(zc.PRUEBA_DESDE) - a.t0 for i, a in enumerate(acts)}
    tablas: list[dict] = []
    for ai, a in enumerate(acts):
        log(f"{a.s}: {a.n} barras")
        cx = Contexto(a, acts[0] if ai else None, funding(hist, a.s))
        pc = antes(a.c)
        rmax, rmin = np.full(a.n, np.nan), np.full(a.n, np.nan)
        rmax[zc.VENTANA:] = sliding_window_view(a.h, zc.VENTANA).max(axis=1)[:-1]
        rmin[zc.VENTANA:] = sliding_window_view(a.lo, zc.VENTANA).min(axis=1)[:-1]
        nd = int(a.di[-1]) + 1
        for li, ((nom, clase), (nom2, L)) in enumerate(zip(LINEAS, lineas(a), strict=True)):
            assert nom == nom2
            for rep in range(REPS + 1):
                if rep:
                    rng = np.random.default_rng([zc.SEMILLA, ai, li, rep])
                    u = rng.uniform(*zc.AZAR_U, nd) * rng.choice([-1.0, 1.0], nd)
                    Lr = L * (1 + u[a.di])
                else:
                    Lr = L
                ks, desde = toques(a, Lr, pc, rmax, rmin)
                for modo, lado, P, s, toq, kt in operaciones(a, Lr, ks, desde):
                    if not len(s):
                        continue
                    cod, net, dec = resuelve(a, s, P, lado, toq)
                    t = {"activo": ai, "k": kt, "azar": np.full(len(s), int(rep > 0), np.int8), "modo": modo,
                         "clase": np.full(len(s), zc.CLASES.index(clase), np.int8),
                         "lado": np.where(lado > 0, 0, 1).astype(np.int8), "ctx": cx.codigos(kt, lado),
                         "cod": cod, "net": net, "entero": s + zc.HORIZONTE <= a.n}
                    if rep == 0:
                        t.update(linea=nom, L=Lr[kt], dec=dec)
                    tablas.append(t)
            log(f"{a.s} {nom}: {len(ks)} toques en la ultima repeticion")
            del L
    acc = agrega(tablas, aj_hasta, pr_desde)
    log("agregado")
    out = informe(acc, meta, fmeta)
    out["rafagas"] = rafagas(acts, aj_hasta[0] + acts[0].t0, pr_desde[0] + acts[0].t0)
    guarda_muestra(acts, tablas, out, pr_desde, muestra)
    salida.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=True) + "\n")
    log(f"FIN {salida} {salida.stat().st_size} B")
    return 0


def informe(acc: np.ndarray, meta: dict, fmeta: dict) -> dict:
    eq = [zc.EQUILIBRIO[e] for e in ESQ]
    n, k, sl, net = acc
    with np.errstate(invalid="ignore", divide="ignore"):
        tasa = k / n
    # [esq, azar, tramo, ...]
    cand = (n[:, 0, 0] >= zc.N_MIN) & (tasa[:, 0, 0] > np.maximum(np.nan_to_num(tasa[:, 1, 0]),
                                                                   np.array(eq)[:, None, None, None, None, None]))
    m = int(cand.sum())
    z = zc.z_bonferroni(m)
    filas, cuenta = [], {"celdas": int(np.prod(n.shape[3:]) * 4), "candidatas": m, "z_bonferroni": round(z, 4),
                         "con_n_prueba_100": 0, "pasan": 0, "pasarian_sin_corregir": 0}
    for ix in zip(*np.nonzero(n[:, 0, 1] >= zc.N_MIN), strict=True):
        e, mo, cl, ac, la, cx = (int(v) for v in ix)
        nn, kk = int(n[e, 0, 1, mo, cl, ac, la, cx]), int(k[e, 0, 1, mo, cl, ac, la, cx])
        az = float(np.nan_to_num(tasa[e, 1, 1, mo, cl, ac, la, cx]))
        lo95 = zc.wilson(kk, nn)[0]
        lob = zc.wilson(kk, nn, z)[0]
        c_ = bool(cand[e, mo, cl, ac, la, cx])
        pasa = c_ and lob > max(eq[e], az)
        cuenta["con_n_prueba_100"] += 1
        cuenta["pasan"] += pasa
        cuenta["pasarian_sin_corregir"] += lo95 > max(eq[e], az)
        naj = int(n[e, 0, 0, mo, cl, ac, la, cx])
        filas.append([ESQ[e], zc.MODOS[mo], zc.CLASES[cl], ACTIVOS[ac], ("largo", "corto")[la], zc.CONTEXTOS[cx],
                      naj, round(float(k[e, 0, 0, mo, cl, ac, la, cx]) / naj, 4) if naj else None,
                      round(float(np.nan_to_num(tasa[e, 1, 0, mo, cl, ac, la, cx])), 4), int(c_),
                      nn, kk, int(sl[e, 0, 1, mo, cl, ac, la, cx]), round(kk / nn, 4), round(lo95, 4), round(lob, 4),
                      round(100 * float(net[e, 0, 1, mo, cl, ac, la, cx]) / nn, 4), round(az, 4),
                      int(n[e, 1, 1, mo, cl, ac, la, cx]), "PASA" if pasa else "no"])
    return {"campana": "BOT-3a", "huella_historia": meta["huella"],
            "historia": {s: {k_: v for k_, v in d.items() if k_ != "zips"} for s, d in meta["simbolos"].items()},
            "funding_meses": {s: len(d["zips"]) for s, d in fmeta["simbolos"].items()},
            "criterio": "scripts/zonas_comun.py", "esquemas": {e: list(zc.ESQUEMAS[e]) for e in ESQ},
            "equilibrio": {e: round(zc.EQUILIBRIO[e], 4) for e in ESQ}, "comision_ida_y_vuelta": zc.FEE,
            "ajuste_hasta": zc.AJUSTE_HASTA, "prueba_desde": zc.PRUEBA_DESDE, "n_min": zc.N_MIN,
            "azar_reps": zc.AZAR_REPS, "cuenta": cuenta, "extra": extra(n, k, net),
            "campos": ["esquema", "modo", "clase", "activo", "lado", "contexto", "n_ajuste", "tasa_ajuste",
                       "azar_ajuste", "candidata", "n", "aciertos", "stops", "tasa", "wilson95_lo",
                       "wilson_bonf_lo", "neto_pct", "azar", "n_azar", "veredicto"],
            "filas": filas}


def extra(n, k, net) -> dict:
    """INFORMACION EXTRA: ¿elegir el mejor valor de la dimension en el AJUSTE mejora la PRUEBA?"""
    with np.errstate(invalid="ignore", divide="ignore"):
        t, nt = k / n, net / n
    out = {}
    for dim in zc.DIMENSIONES:
        vals = [i for i, c in enumerate(zc.CONTEXTOS) if c.startswith(dim + ":")]
        dt, dn = [], []
        for e, mo, cl, ac, la in np.ndindex(4, 3, len(zc.CLASES), 4, 2):
            b = (e, 0, 0, mo, cl, ac, la)
            bp = (e, 0, 1, mo, cl, ac, la)
            if n[b + (0,)] < zc.N_MIN or n[bp + (0,)] < zc.N_MIN:
                continue
            ok = [v for v in vals if n[b + (v,)] >= zc.N_MIN]
            if not ok:
                continue
            v = max(ok, key=lambda v: t[b + (v,)])
            if t[b + (v,)] <= t[b + (0,)] or n[bp + (v,)] < zc.N_MIN:
                continue
            dt.append(t[bp + (v,)] - t[bp + (0,)])
            dn.append(nt[bp + (v,)] - nt[bp + (0,)])
        pos, neg = sum(x > 0 for x in dt), sum(x < 0 for x in dt)
        nn = pos + neg
        p = sum(math.comb(nn, i) for i in range(pos, nn + 1)) / 2 ** nn if nn else 1.0
        out[dim] = {"celdas": len(dt), "sube": pos, "baja": neg,
                    "delta_tasa_media": round(float(np.mean(dt)), 4) if dt else None,
                    "delta_neto_pct_medio": round(100 * float(np.mean(dn)), 4) if dn else None,
                    "p_signo": round(p, 6), "entra": bool(dt) and float(np.mean(dt)) > 0 and p < 0.01}
    return out


def rafagas(acts: list[Activo], aj_hasta_min: int, pr_desde_min: int) -> dict:
    """BOT-1 con sus umbrales congelados, sin liquidaciones, sobre el periodo comun de los tres activos."""
    u = rf.UMBRALES
    t0 = max(a.t0 for a in acts)
    t1 = min(a.t0 + a.n for a in acts)
    sers, zs = [], []
    for a in acts:
        sl = slice(t0 - a.t0, t1 - a.t0)
        c, qv, qb = a.c[sl], a.qv[sl], a.qb[sl]
        buy, sell = qb, qv - qb
        sers.append(rf.Serie(t0, c, a.h[sl], a.lo[sl], buy, sell))
        lr = np.r_[0.0, np.diff(np.log(c))]
        p1, p2 = np.r_[0, np.cumsum(lr)], np.r_[0, np.cumsum(lr * lr)]
        pv, pd = np.r_[0, np.cumsum(buy + sell)], np.r_[0, np.cumsum(buy - sell)]
        N = len(c)
        i = np.arange(u.W + u.BASE, N)
        a_, b_ = i - u.W - u.BASE + 1, i - u.W + 1
        s1, s2 = p1[b_] - p1[a_], p2[b_] - p2[a_]
        var = (s2 - s1 * s1 / u.BASE) / (u.BASE - 1)
        vb, vw = (pv[b_] - pv[a_]) / u.BASE, pv[i + 1] - pv[b_]
        okr = (var > 0) & (vb > 0) & (vw > 0)
        z, v, imb = (np.full(N, np.nan) for _ in range(3))
        with np.errstate(invalid="ignore", divide="ignore"):
            z[i] = np.where(okr, np.log(c[i] / c[i - u.W]) / np.sqrt(var * u.W), np.nan)
            v[i] = np.where(okr, vw / (u.W * vb), np.nan)
            imb[i] = np.where(okr, (pd[i + 1] - pd[b_]) / vw, np.nan)
        zs.append((z, v, imb))
    # cordura: los rasgos vectorizados contra app/rafagas en un tramo de 30 dias
    comp, iguales = [], []
    for j in range(3):
        se = sers[j]
        q = rf.Serie(se.t0, *(x[:43200].tolist() for x in (se.c, se.hi, se.lo, se.buy, se.sell)))
        zr = rf.rasgos(q, u.W, u.BASE)[0]
        comp.append(max(abs(zr[i] - zs[j][0][i]) for i in range(len(zr)) if zr[i] is not None))
        iguales.append(rf.detecta(q) == rf.detecta_rasgos(
            *(np.where(np.isnan(x[:43200]), None, x[:43200]).tolist() for x in zs[j]), u.Z, u.M, u.D, u.CALLA))
    log(f"rafagas: rasgos vectorizados contra app/rafagas, max |dz| {max(comp):.2e}, detecciones iguales {iguales}")
    evs = []
    rng = np.random.default_rng(zc.SEMILLA)
    N = t1 - t0
    for j, (z, v, imb) in enumerate(zs):
        with np.errstate(invalid="ignore"):
            sg = np.where(z > 0, 1, -1)
            cand = np.flatnonzero((sg * z >= u.Z) & (v >= u.M) & (sg * imb >= u.D))
        libre = 0
        otras = [zs[x][0] for x in range(3) if x != j]
        for i in cand.tolist():
            if i < libre:
                continue
            libre = i + u.CALLA
            s = int(sg[i])
            r = rf.clasifica(sers[j], i, s, u, otras, None)
            if r is None:
                continue
            cl, m = r
            e = i + m + 1
            if e + 1 + zc.HORIZONTE > N:
                continue
            tramo = 0 if t0 + i < aj_hasta_min else (1 if t0 + i >= pr_desde_min else -1)
            if tramo < 0:
                continue
            evs.append((j, cl, s if cl != rf.BARRIDO else -s, e, tramo))
    log(f"rafagas: {len(evs)} eventos")
    out: dict = {"periodo": [datetime.fromtimestamp(t0 * 60, UTC).isoformat(), datetime.fromtimestamp(t1 * 60,
                                                                                                    UTC).isoformat()],
                 "umbrales": asdict(rf.UMBRALES), "cordura_30d": {"max_dz": max(comp), "iguales": iguales},
                 "entrada": "c[i+m+1]: decide al cierre de i+m, entra a mercado un minuto despues", "filas": []}
    dias = {0: np.arange(0, (aj_hasta_min - t0) // 1440), 1: np.arange((pr_desde_min - t0 + 1439) // 1440,
                                                                     (N - zc.HORIZONTE - 2) // 1440)}
    res = {}
    for j in range(3):
        se = sers[j]
        aa = type("A", (), {"h": np.asarray(se.hi), "lo": np.asarray(se.lo), "c": np.asarray(se.c), "n": N})
        mine = [x for x in evs if x[0] == j]
        if not mine:
            continue
        e_ = np.array([x[3] for x in mine])
        d_ = np.array([x[2] for x in mine])
        res[j] = resuelve(aa, e_ + 1, aa.c[e_], d_, np.zeros(len(mine), bool))[:2]
        # azar: mismo minuto del dia, activo y lado, en un dia sorteado del mismo tramo
        tr = np.array([x[4] for x in mine])
        ea = np.concatenate([rng.choice(dias[t], zc.AZAR_DIAS) * 1440 + (e % 1440) for e, t in zip(e_, tr,
                                                                                                strict=True)])
        da = np.repeat(d_, zc.AZAR_DIAS)
        res[(j, "azar")] = resuelve(aa, ea + 1, aa.c[ea], da, np.zeros(len(ea), bool))[:2]
    m = 4 * 3 * 4  # esquemas x clases x activos (con TODOS): todas candidatas, el criterio esta congelado
    z = zc.z_bonferroni(m)
    for e, esq in enumerate(ESQ):
        eq = zc.EQUILIBRIO[esq]
        for cl in (rf.CASCADA, rf.BARRIDO, rf.SIN_CLASE):
            for ac in range(4):
                for t in (0, 1):
                    js = [ac] if ac < 3 else [0, 1, 2]
                    cods, nets, azc = [], [], []
                    for j in js:
                        if j not in res:
                            continue
                        mine = [x for x in evs if x[0] == j]
                        sel = np.array([x[1] == cl and x[4] == t for x in mine])
                        cods.append(res[j][0][sel, e])
                        nets.append(res[j][1][sel, e])
                        azc.append(res[(j, "azar")][0][np.repeat(sel, zc.AZAR_DIAS), e])
                    cod = np.concatenate(cods) if cods else np.array([])
                    nn, kk = len(cod), int((cod == 0).sum())
                    az = float((np.concatenate(azc) == 0).mean()) if nn else 0.0
                    lo95 = zc.wilson(kk, nn)[0]
                    lob = zc.wilson(kk, nn, z)[0]
                    ver = ("sin medir" if nn < zc.N_MIN else ("PASA" if lob > max(eq, az) else "no")) if t else "-"
                    out["filas"].append([esq, cl, ACTIVOS[ac], ("ajuste", "prueba")[t], nn, kk,
                                         round(kk / nn, 4) if nn else None, round(lo95, 4), round(lob, 4),
                                         round(100 * float(np.concatenate(nets).mean()), 4) if nn else None,
                                         round(az, 4), ver])
    out["campos"] = ["esquema", "clase", "activo", "tramo", "n", "aciertos", "tasa", "wilson95_lo", "wilson_bonf_lo",
                     "neto_pct", "azar", "veredicto"]
    out["m"], out["z_bonferroni"] = m, round(z, 4)
    return out


def guarda_muestra(acts, tablas, out, pr_desde, ruta: Path) -> None:
    """Los toques de UNA celda (modo, clase, activo, lado, contexto todos) de la prueba, con sus barras."""
    filas = out["filas"]
    elegida = None
    for clase in ("semana_ext", "rango_3d", "dia_ext", "giro_4h"):
        for f in sorted(filas, key=lambda f: f[10]):
            if f[0] == "B" and f[2] == clase and f[3] != "TODOS" and f[5] == "todos" and f[1] != "toque":
                elegida = f
                break
        if elegida:
            break
    if elegida is None:
        log("muestra: ninguna celda candidata para la muestra")
        return
    modo, clase, act, lado = elegida[1], elegida[2], elegida[3], elegida[4]
    ai = ACTIVOS.index(act)
    a = acts[ai]
    evs = []
    for t in tablas:
        if t["activo"] != ai or "linea" not in t or zc.CLASES[int(t["clase"][0])] != clase:
            continue
        lsel = (t["modo"] == zc.MODOS.index(modo)) & (t["lado"] == ("largo", "corto").index(lado)) & t["entero"] \
            & (t["k"] >= pr_desde[ai])
        for i in np.flatnonzero(lsel).tolist():
            k = int(t["k"][i])
            w0, w1 = k - zc.VENTANA - 1, int(t["dec"][i].max()) + 1
            evs.append({"linea": t["linea"], "k": k, "L": float(t["L"][i]), "w0": w0,
                        "o": a.o[w0:w1].tolist(), "h": a.h[w0:w1].tolist(), "l": a.lo[w0:w1].tolist(),
                        "c": a.c[w0:w1].tolist()})
    evs.sort(key=lambda x: x["k"])
    filas_cel = [f for f in filas if f[1:6] == [modo, clase, act, lado, "todos"]]
    dato = {"huella_historia": out["huella_historia"], "simbolo": a.s, "t0": a.t0, "modo": modo, "clase": clase,
            "activo": act, "lado": lado, "filas": filas_cel, "eventos": evs}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(lzma.compress(json.dumps(dato, separators=(",", ":")).encode(), preset=9))
    log(f"muestra {ruta}: {len(evs)} eventos, {ruta.stat().st_size} B, fila {modo} {clase} {act} {lado}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
