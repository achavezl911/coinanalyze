"""EL BARRIDO del mapa de valor (campana BOT-3c): mide el criterio de `scripts/mapa_comun.py`. numpy + scikit-learn.

USO (con el venv aparte, fuera del repo):
    python mapa_estudio.py HIST OUT.json                   la medida real
    MAPA_CONTROL=1 python mapa_estudio.py HIST CTRL.json REAL.json
        el control positivo: planta el empuje tras RSI4h < 30 y el oraculo de F8 en una copia en memoria, mide
        con la misma tuberia y escribe en REAL.json la seccion «control» con lo que encontro.
HIST: el directorio de `zonas_historia.py` y `mapa_datos.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mapa_comun import (  # noqa: E402
    AJUSTE_HASTA,
    CALIENTE,
    DIA,
    EMPUJE,
    EMPUJE_MIN,
    ESQUEMAS,
    FEE,
    LISTON,
    N_MIN,
    NOMBRE_ESQ,
    PASO,
    PRUEBA_DESDE,
    SEMILLA,
    B,
    rsi_wilder,
)
from zonas_historia import SIMBOLOS  # noqa: E402

warnings.filterwarnings("ignore", category=RuntimeWarning)
CONTROL = os.environ.get("MAPA_CONTROL") == "1"
INI = time.time()
LADOS = {"largo": 1, "corto": -1}
DIA0 = 18262  # 2020-01-01 en dias epoch


def log(x: str) -> None:
    print(f"{time.time() - INI:7.0f}s {x}", flush=True)


def minuto(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=UTC).timestamp()) // 60


AJ_FIN, PR_INI = minuto(AJUSTE_HASTA), minuto(PRUEBA_DESDE)


def prev(x: np.ndarray, n: int, fn) -> np.ndarray:
    """fn de x[j-n..j-1] (sin la j)."""
    out = np.full(len(x), np.nan)
    if len(x) > n:
        out[n:] = fn(swv(x, n)[: len(x) - n], axis=1)
    return out


def incl(x: np.ndarray, n: int, fn) -> np.ndarray:
    """fn de x[j-n+1..j] (con la j)."""
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        out[n - 1:] = fn(swv(x, n), axis=1)
    return out


def atras(x: np.ndarray, k: int) -> np.ndarray:
    return np.r_[np.full(k, np.nan), x[:-k]]


def rsi(x: np.ndarray) -> np.ndarray:
    return np.array(rsi_wilder([float(v) for v in x]))


def velas(o, h, lo, c, qv, qb, P):
    r = lambda a: a.reshape(-1, P)  # noqa: E731
    return o[::P].copy(), r(h).max(1), r(lo).min(1), c[P - 1::P].copy(), r(qv).sum(1), r(qb).sum(1)


class Activo:
    """Todo a nivel de vela de 4 h: decision j al cierre de la vela j, entrada en el minuto 240 (j + 1)."""

    def __init__(self, hist: Path, s: str, ai: int, meta: dict):
        m = meta["simbolos"][s]
        off = (-m["t0"]) % DIA
        n = (m["n"] - off) // DIA * DIA
        self.s, self.ai, self.t0, self.n = s, ai, m["t0"] + off, n
        ld = lambda nom: np.fromfile(hist / f"{s}.{nom}.f64", dtype="<f8")[off:off + n]  # noqa: E731
        o, h, lo, c, qv, qb = (ld(x) for x in ("o", "h", "l", "c", "qv", "qb"))
        J = n // PASO
        self.J = J
        self.E = PASO * (np.arange(J) + 1)  # minuto relativo de entrada
        self.Eabs = self.t0 + self.E
        self.fmin, self.frate = funding(hist, s)
        if CONTROL:
            o, h, lo, c, self.fpl = planta(o, h, lo, c)
        self.cond: dict[str, tuple[str, np.ndarray]] = {}
        self.anclas: dict[str, tuple[str, np.ndarray]] = {}
        self.col: dict[str, np.ndarray] = {}
        self.features(hist, s, off, n, o, h, lo, c, qv, qb)
        self.salidas(o, h, lo, c)
        if CONTROL:
            ult = np.minimum(self.E + DIA - 1, n - 1)
            sg = np.where(n >= self.E + DIA, np.sign(c[ult] / o[np.minimum(self.E, n - 1)] - 1), np.nan)
            self.col["oraculo"] = sg + np.random.default_rng(SEMILLA + 7 + ai).normal(size=J)

    def features(self, hist, s, off, n, o, h, lo, c, qv, qb):
        J, col = self.J, self.col
        O4, H4, L4, C4, V4, B4 = velas(o, h, lo, c, qv, qb, PASO)
        Od, Hd, Ld, Cd, _, _ = velas(o, h, lo, c, qv, qb, DIA)
        nd = len(Cd)
        diaria = (np.arange(J) + 1) % 6 == 0
        dd = (np.arange(J) + 1) // 6 - 1  # ultimo dia cerrado en la decision j
        dd_ok = dd >= 0

        def a4h(xd):  # valor diario del ultimo dia cerrado
            out = np.full(J, np.nan)
            out[dd_ok] = xd[dd[dd_ok]]
            return out

        def soloD(bd):  # condicion diaria: solo en la decision de las 00:00
            out = np.zeros(J, bool)
            out[diaria] = bd[dd[diaria]]
            return out

        r4 = C4 / atras(C4, 1) - 1
        R24 = C4 / atras(C4, 6) - 1
        col["r4"], col["R24"], col["R72"] = r4, R24, C4 / atras(C4, 18) - 1
        # F2
        rs4, rsd = rsi(C4), rsi(Cd)
        col["rsi4"], col["rsi1d"] = rs4, a4h(rsd)
        cn = self.cond
        for nom, cc, rr, D in (("4h", C4, rs4, False), ("1d", Cd, rsd, True)):
            f = soloD if D else (lambda b: b)
            cn[f"rsi{nom}_bajo"] = ("F2", f(rr < 30))
            cn[f"rsi{nom}_alto"] = ("F2", f(rr > 70))
            cn[f"div{nom}_alc"] = ("F2", f((cc < prev(cc, 20, np.min)) & (rr > prev(rr, 20, np.min))))
            cn[f"div{nom}_baj"] = ("F2", f((cc > prev(cc, 20, np.max)) & (rr < prev(rr, 20, np.max))))
        # F3
        D24 = incl(2 * B4 - V4, 6, np.sum)
        V24 = incl(V4, 6, np.sum)
        dv = D24 / V24
        col["dv24"] = dv
        relvol = V4 / prev(V4, 180, np.mean)
        rstd = r4 / prev(r4, 180, np.std)
        col["relvol"], col["rstd"] = relvol, rstd
        aj = self.Eabs < AJ_FIN
        p75 = np.nanpercentile(np.abs(dv[aj]), 75)
        cn["acomp_alc"] = ("F3", (R24 > 0) & (dv > p75))
        cn["acomp_baj"] = ("F3", (R24 < 0) & (dv < -p75))
        cn["contra_alc"] = ("F3", (R24 < 0) & (dv > p75))
        cn["contra_baj"] = ("F3", (R24 > 0) & (dv < -p75))
        cn["vol_alto_alc"] = ("F3", (relvol > 2.5) & (C4 > O4))
        cn["vol_alto_baj"] = ("F3", (relvol > 2.5) & (C4 < O4))
        cn["climax_alc"] = ("F3", (relvol > 4) & (rstd > 3))
        cn["climax_baj"] = ("F3", (relvol > 4) & (rstd < -3))
        # F4
        z4 = (C4 - incl(C4, 20, np.mean)) / incl(C4, 20, np.std)
        zd = (Cd - incl(Cd, 20, np.mean)) / incl(Cd, 20, np.std)
        racha = np.zeros(nd)
        for i in range(1, nd):
            u = np.sign(Cd[i] - Cd[i - 1])
            racha[i] = (racha[i - 1] + u) if u != 0 and np.sign(racha[i - 1]) in (0, u) else u
        rango = (Hd - Ld) / Cd
        rrel = rango / prev(rango, 20, np.mean)
        col["z4"], col["z1d"], col["racha"], col["rango_rel"] = z4, a4h(zd), a4h(racha), a4h(rrel)
        cn["ext4h_sobre"], cn["ext4h_bajo"] = ("F4", z4 > 2), ("F4", z4 < -2)
        cn["ext1d_sobre"], cn["ext1d_bajo"] = ("F4", soloD(zd > 2)), ("F4", soloD(zd < -2))
        cn["racha_alc"], cn["racha_baj"] = ("F4", soloD(racha >= 5)), ("F4", soloD(racha <= -5))
        cn["rango_exp_alc"] = ("F4", soloD((rrel > 2) & (Cd > Od)))
        cn["rango_exp_baj"] = ("F4", soloD((rrel > 2) & (Cd < Od)))
        cn["rango_comp"] = ("F4", soloD(rrel < 0.5))
        # F1 (y los anclajes alternativos para la robustez)
        dabs = self.t0 // DIA + np.arange(nd) - DIA0
        for D in (3, 9):
            for A in range(D):
                k = (dabs - A) // D
                cierra = np.zeros(nd, bool)
                cierra[:-1] = k[1:] != k[:-1]
                cierra[-1] = (dabs[-1] - A + 1) % D == 0
                ini = np.r_[0, np.flatnonzero(k[1:] != k[:-1]) + 1]
                ho, hh, hl = Od[ini], np.maximum.reduceat(Hd, ini), np.minimum.reduceat(Ld, ini)
                fin = np.r_[ini[1:] - 1, nd - 1]
                hc = Cd[fin]
                completa = np.r_[False, np.ones(len(ini) - 1, bool)] if dabs[0] % D != A % D else np.ones(len(ini), bool)
                kk = np.searchsorted(ini, np.arange(nd), side="right") - 1  # vela de cada dia
                tam = hh - hl
                cs = {
                    "ruptura_alc": hc > atras(hh, 1), "ruptura_baj": hc < atras(hl, 1),
                    "mecha_inf": (np.minimum(ho, hc) - hl) >= 0.5 * tam,
                    "mecha_sup": (hh - np.maximum(ho, hc)) >= 0.5 * tam,
                    "barre_min": (hl < atras(hl, 1)) & (hc > atras(hl, 1)),
                    "barre_max": (hh > atras(hh, 1)) & (hc < atras(hh, 1)),
                }
                for nom, bv in cs.items():
                    bv = bv & completa & np.r_[False, completa[:-1]]
                    bd = cierra & bv[kk]
                    dst = self.cond if A == 0 else self.anclas
                    dst[f"f1_{D}d_{nom}" + ("" if A == 0 else f"_A{A}")] = ("F1", soloD(bd))
                if A == 0:  # posicion del cierre en la ultima vela de D dias cerrada
                    pos = np.full(nd, np.nan)
                    for i in range(nd):
                        q = kk[i] - (0 if cierra[i] else 1)
                        if q >= 0 and tam[q] > 0:
                            pos[i] = (Cd[i] - hl[q]) / tam[q]
                    col[f"pos{D}"] = a4h(pos)
        # F5
        mt = np.fromfile(hist / f"{s}.metrics.f64", dtype="<f8").reshape(-1, 6)[off // 5:(off + n) // 5]
        mi = 48 * (np.arange(J) + 1) - 1
        OI, top_cta, top_pos, cuentas, taker = mt[mi, 0], mt[mi, 2], mt[mi, 3], mt[mi, 4], None
        doi = OI / np.where(mi >= 288, mt[np.maximum(mi - 288, 0), 0], np.nan) - 1
        tk = mt[:, 5]
        okk = ~np.isnan(tk)
        cs_t, cs_n = np.r_[0, np.cumsum(np.where(okk, tk, 0))], np.r_[0, np.cumsum(okk)]
        lo_i = np.maximum(mi - 287, 0)
        taker = (cs_t[mi + 1] - cs_t[lo_i]) / np.maximum(cs_n[mi + 1] - cs_n[lo_i], 1)
        taker[(cs_n[mi + 1] - cs_n[lo_i]) < 144] = np.nan
        col.update(doi24=doi, top_cta=top_cta, top_pos=top_pos, cuentas=cuentas, taker24=taker)
        pc = lambda x, q: np.nanpercentile(x[aj], q) if np.isfinite(x[aj]).sum() > 100 else np.nan  # noqa: E731
        p90, p10 = pc(doi, 90), pc(doi, 10)
        cn["oi_sube_precio_sube"] = ("F5", (doi > p90) & (R24 > 0))
        cn["oi_sube_precio_baja"] = ("F5", (doi > p90) & (R24 < 0))
        cn["oi_baja_precio_sube"] = ("F5", (doi < p10) & (R24 > 0))
        cn["oi_baja_precio_baja"] = ("F5", (doi < p10) & (R24 < 0))
        for nom, x in (("top", top_pos), ("cuentas", cuentas), ("taker", taker)):
            cn[f"{nom}_alto"], cn[f"{nom}_bajo"] = ("F5", x > pc(x, 90)), ("F5", x < pc(x, 10))
        # F6
        fi = np.searchsorted(self.fmin, self.Eabs, side="left") - 1
        fun = np.where(fi >= 0, self.frate[np.maximum(fi, 0)], np.nan)
        pr = np.fromfile(hist / f"{s}.prima.f64", dtype="<f8")[off:off + n].reshape(-1, PASO)
        pm4 = np.nanmean(pr, axis=1)
        prima = incl(pm4, 2, np.nanmean)
        col["fun"], col["prima8"] = fun, prima
        cn["fun_alto"], cn["fun_bajo"] = ("F6", fun > pc(fun, 95)), ("F6", fun < pc(fun, 5))
        cn["prima_alta"], cn["prima_baja"] = ("F6", prima > pc(prima, 90)), ("F6", prima < pc(prima, 10))
        self.prima_desde = None if not np.isfinite(pm4).any() else int(np.flatnonzero(np.isfinite(pm4))[0])
        # F7
        sc = np.fromfile(hist / f"{s}.spot.c.f64", dtype="<f8")[off:off + n]
        if CONTROL:
            sc = sc * self.fpl  # el empuje mueve el activo, no solo el perpetuo
        sv = np.fromfile(hist / f"{s}.spot.qv.f64", dtype="<f8")[off:off + n].reshape(-1, PASO)
        sb = np.fromfile(hist / f"{s}.spot.qb.f64", dtype="<f8")[off:off + n].reshape(-1, PASO)
        SC4 = sc[PASO - 1::PASO]
        SV4, SB4 = sv.sum(1), sb.sum(1)  # NaN si falta algun minuto spot en la vela
        lead = (SC4 / atras(SC4, 6) - 1) - R24
        sV24 = incl(SV4, 6, np.sum)
        dflujo = incl(2 * SB4 - SV4, 6, np.sum) / sV24 - dv
        share = sV24 / V24
        col.update(lead=lead, dflujo=dflujo, spot_share=share)
        cn["lidera_spot_alc"], cn["lidera_spot_baj"] = ("F7", lead > pc(lead, 90)), ("F7", lead < pc(lead, 10))
        cn["flujo_spot_alc"], cn["flujo_spot_baj"] = ("F7", dflujo > pc(dflujo, 90)), ("F7", dflujo < pc(dflujo, 10))
        cn["spot_pesa"], cn["spot_ligero"] = ("F7", share > pc(share, 90)), ("F7", share < pc(share, 10))
        # F0
        ru = np.random.default_rng(SEMILLA + self.ai).normal(size=J)
        col["ruido"] = ru
        cn["ruido_alto"], cn["ruido_bajo"] = ("F0", ru > pc(ru, 90)), ("F0", ru < pc(ru, 10))
        col["hora"] = (np.arange(J) % 6).astype(float)
        self.diaria = diaria
        cal = np.arange(J) < CALIENTE * 6
        for d in (self.cond, self.anclas):
            for k, (f, b) in d.items():
                d[k] = (f, b & ~cal)
        self.rsi4_bajo = (rs4 < 30) & ~cal

    def salidas(self, o, h, lo, c):
        """net[esq, lado][j] y sal[esq, lado][j] (minuto relativo de salida); NaN / -1 si el tope no cabe."""
        n = self.n
        H60, L60 = h.reshape(-1, 60).max(1), lo.reshape(-1, 60).min(1)
        F = self.fmin - self.t0
        CR = np.r_[0.0, np.cumsum(self.frate)]
        self.net, self.sal, self.tipo = {}, {}, {}
        for e, (tp, sl, tope) in ESQUEMAS.items():
            ok = np.flatnonzero(self.E + tope <= n)
            W = tope // 60
            for lado, d in LADOS.items():
                net = np.full(self.J, np.nan)
                sal = np.full(self.J, -1, np.int64)
                tipo = np.zeros(self.J, np.int8)
                for ch in np.array_split(ok, max(1, len(ok) // 1500)):
                    Ei = self.E[ch]
                    P = o[Ei]
                    hrs = Ei[:, None] // 60 + np.arange(W)[None, :]
                    if d > 0:
                        lt, ls = P * (1 + tp), P * (1 - sl)
                        mt, ms = H60[hrs] >= lt[:, None], L60[hrs] <= ls[:, None]
                    else:
                        lt, ls = P * (1 - tp), P * (1 + sl)
                        mt, ms = L60[hrs] <= lt[:, None], H60[hrs] >= ls[:, None]
                    big = 1 << 40

                    def primero(m, niv, arr, cmp, Ei=Ei, big=big):
                        has = m.any(1)
                        fh = m.argmax(1)
                        mins = (Ei // 60 + fh)[:, None] * 60 + np.arange(60)[None, :]
                        hit = cmp(arr[mins], niv[:, None])
                        return np.where(has, mins[np.arange(len(Ei)), hit.argmax(1)], big)

                    ge, le = np.greater_equal, np.less_equal
                    kt = primero(mt, lt, h if d > 0 else lo, ge if d > 0 else le)
                    ks = primero(ms, ls, lo if d > 0 else h, le if d > 0 else ge)
                    ult = Ei + tope - 1
                    es_sl = (ks <= kt) & (ks < big)
                    es_tp = (kt < ks) & (kt < big)
                    k = np.where(es_sl, ks, np.where(es_tp, kt, ult))
                    nt = np.where(es_sl, -sl - FEE, np.where(es_tp, tp - FEE, d * (c[ult] / P - 1) - FEE))
                    fs = CR[np.searchsorted(F, k, "right")] - CR[np.searchsorted(F, Ei, "right")]
                    net[ch] = nt - d * fs
                    sal[ch] = k
                    tipo[ch] = np.where(es_sl, 2, np.where(es_tp, 1, 3))
                self.net[e, lado], self.sal[e, lado], self.tipo[e, lado] = net, sal, tipo


def funding(hist: Path, s: str) -> tuple[np.ndarray, np.ndarray]:
    filas = [ln.split("\t") for ln in (hist / f"{s}.funding.tsv").read_text().split("\n") if ln]
    filas.sort(key=lambda f: int(f[0]))
    return np.array([int(f[0]) for f in filas], np.int64), np.array([float(f[1]) for f in filas])


def planta(o, h, lo, c):
    """Control positivo: empuje de EMPUJE en EMPUJE_MIN minutos tras cada decision de 4 h con RSI < 30."""
    C4 = c[PASO - 1::PASO]
    rs = rsi(C4)
    ev = PASO * (np.flatnonzero(rs < 30) + 1)
    n = len(c)
    lf = np.zeros(n + 1)
    paso = np.zeros(n + 1)
    g = float(os.environ.get("MAPA_EMPUJE", EMPUJE))
    M = int(os.environ.get("MAPA_EMPUJE_MIN", EMPUJE_MIN))
    rampa = np.log1p(g * np.arange(M) / M)
    for E in ev:
        m = min(M, n - E)
        lf[E:E + m] += rampa[:m]
        if n > E + M:
            paso[E + M] += np.log1p(g)
    f = np.exp(lf[:n] + np.cumsum(paso)[:n])
    log(f"  planta {len(ev)} empujes, factor final {f[-1]:.3g}")
    return o * f, h * f, lo * f, c * f, f


def operaciones(a: Activo, idx: np.ndarray, e: str, lado: str) -> np.ndarray:
    """Las decisiones j de idx que abren operacion: una abierta a la vez."""
    net, sal = a.net[e, lado], a.sal[e, lado]
    out, ult = [], -1
    for j in idx:
        if np.isnan(net[j]) or a.E[j] <= ult:
            continue
        out.append(j)
        ult = sal[j]
    return np.array(out, np.int64)


class Juez:
    def __init__(self, acts: list[Activo]):
        w0 = (DIA0 + 3) // 7
        self.wk = {a.s: (a.Eabs // DIA + 3) // 7 - w0 for a in acts}
        self.NW = max(int(w.max()) for w in self.wk.values()) + 1
        self.W = np.random.default_rng(SEMILLA).poisson(1.0, (B, self.NW)).astype(np.float64)
        self.cache: dict = {}

    def per(self, a: Activo, e: str, lado: str, tramo: str) -> np.ndarray:
        if tramo == "ajuste":
            return (a.Eabs < AJ_FIN) & (a.t0 + a.sal[e, lado] < AJ_FIN) & ~np.isnan(a.net[e, lado])
        return (a.Eabs >= PR_INI) & ~np.isnan(a.net[e, lado])

    def boot(self, a: Activo, j: np.ndarray, net: np.ndarray):
        wk = self.wk[a.s][j]
        S = np.bincount(wk, net[j], minlength=self.NW)
        N = np.bincount(wk, minlength=self.NW).astype(float)
        return (self.W @ S) / (self.W @ N)

    def azar(self, a: Activo, e: str, lado: str, tramo: str, diaria: bool):
        key = (a.s, e, lado, tramo, diaria)
        if key not in self.cache:
            m = self.per(a, e, lado, tramo) & (a.diaria if diaria else True)
            j = np.flatnonzero(m)
            net = a.net[e, lado]
            self.cache[key] = (float(net[j].mean()) if len(j) else np.nan, self.boot(a, j, net),
                               float((net[j] > 0).mean()) if len(j) else np.nan)
        return self.cache[key]

    def tramo(self, a: Activo, ops: np.ndarray, e: str, lado: str, tramo: str, diaria: bool) -> dict:
        m = self.per(a, e, lado, tramo)
        j = ops[m[ops]]
        net = a.net[e, lado]
        am, ab, aw = self.azar(a, e, lado, tramo, diaria)
        out = {"n": int(len(j)), "azar": rd(am), "acierto_azar": rd(aw)}
        if len(j) == 0:
            return out
        cb = self.boot(a, j, net)
        out.update(neto=rd(net[j].mean()), se=rd(np.nanstd(cb)), acierto=rd((net[j] > 0).mean()),
                   dif=rd(net[j].mean() - am), se_dif=rd(np.nanstd(cb - ab)))
        if tramo == "prueba":
            yr = (a.Eabs[j] // DIA - DIA0)
            anos = {}
            for y in (2024, 2025, 2026):
                lo_, hi_ = (datetime(y, 1, 1, tzinfo=UTC).timestamp() // 86400 - DIA0,
                            datetime(y + 1, 1, 1, tzinfo=UTC).timestamp() // 86400 - DIA0)
                mm = (yr >= lo_) & (yr < hi_)
                if mm.any():
                    anos[str(y)] = [int(mm.sum()), rd(net[j][mm].mean())]
            out["anos"] = anos
        return out


def rd(x) -> float | None:
    x = float(x)
    return None if not np.isfinite(x) else round(x, 6)


def celdas(acts, juez, conds_por_activo, tag="") -> list[dict]:
    out = []
    for a in acts:
        for nom, (fam, b) in conds_por_activo(a).items():
            idx = np.flatnonzero(b)
            diaria = bool(len(idx)) and bool(a.diaria[idx].all())
            for e in ESQUEMAS:
                for lado in LADOS:
                    ops = operaciones(a, idx, e, lado)
                    out.append({"familia": fam, "cond": nom, "esquema": e, "activo": a.s, "lado": lado,
                                "rejilla": "1d" if diaria else "4h",
                                "ajuste": juez.tramo(a, ops, e, lado, "ajuste", diaria),
                                "prueba": juez.tramo(a, ops, e, lado, "prueba", diaria)})
        log(f"  celdas{tag} {a.s}: {len(out)}")
    return out


COLS = ("r4", "R24", "R72", "rsi4", "rsi1d", "z4", "z1d", "racha", "rango_rel", "dv24", "relvol", "rstd", "pos3",
        "pos9", "doi24", "top_cta", "top_pos", "cuentas", "taker24", "fun", "prima8", "lead", "dflujo",
        "spot_share", "ruido", "hora")


def f8(acts: list[Activo]) -> dict:
    """{(barajado, esq, lado): prob fuera de muestra (NaN fuera) y umbral} por activo: devuelve conds por activo."""
    from sklearn.ensemble import HistGradientBoostingClassifier

    cols = COLS + (("oraculo",) if CONTROL else ())
    X = np.vstack([np.column_stack([a.col[k] for k in cols] + [np.full(a.J, a.ai, float)]) for a in acts])
    Eabs = np.concatenate([a.Eabs for a in acts])
    quien = np.concatenate([np.full(a.J, i) for i, a in enumerate(acts)])
    jj = np.concatenate([np.arange(a.J) for a in acts])
    mes = (Eabs * 60).astype("datetime64[s]").astype("datetime64[M]").astype(np.int64)
    cal = jj >= CALIENTE * 6
    rng = np.random.default_rng(SEMILLA + 99)
    res: dict = {}
    for barajado in (False, True):
        for e, (_, _, tope) in ESQUEMAS.items():
            for lado in LADOS:
                net = np.concatenate([a.net[e, lado] for a in acts])
                y = (net > 0).astype(int)
                ok = ~np.isnan(net) & cal
                p = np.full(len(net), np.nan)
                for Y in range(2022, 2027):
                    y0, y1 = minuto(f"{Y}-01-01"), minuto(f"{Y + 1}-01-01")
                    tr = ok & (Eabs + tope < y0)
                    te = cal & (Eabs >= y0) & (Eabs < y1)
                    yt = y[tr].copy()
                    if barajado:
                        mt = mes[tr]
                        for u in np.unique(mt):
                            ii = np.flatnonzero(mt == u)
                            yt[ii] = yt[rng.permutation(ii)]
                    clf = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200, max_leaf_nodes=15,
                                                         min_samples_leaf=200, l2_regularization=1.0,
                                                         random_state=SEMILLA)
                    clf.fit(X[tr], yt)
                    p[te] = clf.predict_proba(X[te])[:, 1]
                # umbral: p95 de las predicciones fuera de muestra de los 365 dias anteriores (>= 90 dias)
                orden = np.argsort(Eabs, kind="stable")
                te_, pe_ = Eabs[orden], p[orden]
                fin = np.isfinite(pe_)
                tf, pf = te_[fin], pe_[fin]
                senal = np.zeros(len(p), bool)
                ini_oos = minuto("2022-01-01")
                for t in np.unique(Eabs[np.isfinite(p)]):
                    if t < ini_oos + 90 * DIA:
                        continue
                    a0, a1 = np.searchsorted(tf, t - 365 * DIA), np.searchsorted(tf, t)
                    thr = np.percentile(pf[a0:a1], 95)
                    m = (Eabs == t) & (p >= thr)
                    senal |= m
                res[barajado, e, lado] = senal
                log(f"  F8 barajado={barajado} {e} {lado}: {int(senal.sum())} senales")
    out = {}
    for i, a in enumerate(acts):
        d = {}
        for (bj, e, lado), s in res.items():
            d[(bj, e, lado)] = s[quien == i][np.argsort(jj[quien == i])]
        out[a.s] = d
    return out


def celdas_f8(acts, juez, sen) -> list[dict]:
    out = []
    for a in acts:
        for bj in (False, True):
            for e in ESQUEMAS:
                for lado in LADOS:
                    idx = np.flatnonzero(sen[a.s][bj, e, lado])
                    ops = operaciones(a, idx, e, lado)
                    out.append({"familia": "F8_barajado" if bj else "F8", "cond": "top5", "esquema": e,
                                "activo": a.s, "lado": lado, "rejilla": "4h",
                                "ajuste": juez.tramo(a, ops, e, lado, "ajuste", False),
                                "prueba": juez.tramo(a, ops, e, lado, "prueba", False)})
    return out


def juzga(cs: list[dict], m: int | None = None) -> int:
    from statistics import NormalDist

    for c in cs:
        aj = c["ajuste"]
        c["candidata"] = bool(aj["n"] >= N_MIN and aj.get("neto") is not None and aj["azar"] is not None
                              and aj["neto"] > aj["azar"])
    if m is None:
        m = sum(c["candidata"] for c in cs if c["familia"] != "F8_barajado")
    z = NormalDist().inv_cdf(1 - 0.05 / max(m, 1))
    bar = {(c["esquema"], c["activo"], c["lado"]): c["prueba"].get("neto") for c in cs
           if c["familia"] == "F8_barajado"}
    for c in cs:
        pr = c["prueba"]
        if not c["candidata"]:
            c["veredicto"] = "no candidata" if c["ajuste"]["n"] >= N_MIN else "sin medir (ajuste)"
            continue
        if pr["n"] < N_MIN or pr.get("se") is None:
            c["veredicto"] = "sin medir"
            continue
        lb, lbd = pr["neto"] - z * pr["se"], pr["dif"] - z * (pr["se_dif"] or 0)
        c["cota_neto"], c["cota_dif"] = rd(lb), rd(lbd)
        v = "PASA" if lb > 0 and lbd > 0 else ("CONTEXTO" if lbd > 0 else "RUIDO")
        if c["familia"] == "F8" and v != "RUIDO":
            b = bar.get((c["esquema"], c["activo"], c["lado"]))
            if b is not None and pr["neto"] <= b:
                v = "RUIDO"
        c["veredicto"] = v
    return m


def familias(cs: list[dict]) -> dict:
    out = {}
    for f in sorted({c["familia"] for c in cs}):
        fc = [c for c in cs if c["familia"] == f]
        v = [c["veredicto"] for c in fc]
        medibles = [c for c in fc if c["ajuste"]["n"] >= N_MIN and c["prueba"]["n"] >= N_MIN]
        ver = ("PAGA" if "PASA" in v else "CONTEXTO" if "CONTEXTO" in v else
               "SIN MEDIR" if not medibles else "RUIDO")
        mejor = max((c for c in fc if c.get("cota_neto") is not None), key=lambda c: c["cota_neto"], default=None)
        out[f] = {"veredicto": ver, "celdas": len(fc), "candidatas": sum(c["candidata"] for c in fc),
                  "medibles": len(medibles), "pasa": v.count("PASA"), "contexto": v.count("CONTEXTO"),
                  "sin_medir": sum(x.startswith("sin medir") for x in v),
                  "pasa_celdas": [f"{c['cond']} {c['esquema']} {c['activo']} {c['lado']}" for c in fc
                                  if c["veredicto"] == "PASA"],
                  "mejor": None if mejor is None else {k: mejor[k] for k in
                                                        ("cond", "esquema", "activo", "lado", "cota_neto",
                                                         "cota_dif", "prueba")}}
    return out


def main(argv: list[str]) -> int:
    hist, outp = Path(argv[1]), Path(argv[2])
    meta = json.loads((hist / "historia.json").read_text())
    acts = []
    for i, s in enumerate(SIMBOLOS):
        log(f"{s} cargando")
        acts.append(Activo(hist, s, i, meta))
        log(f"{s} listo: {acts[-1].J} decisiones, {len(acts[-1].cond)} condiciones")
    juez = Juez(acts)
    cs = celdas(acts, juez, lambda a: a.cond)
    cs += celdas_f8(acts, juez, f8(acts))
    m = juzga(cs)
    fam = familias(cs)
    log(f"m = {m}; " + " ".join(f"{f}:{d['veredicto']}" for f, d in fam.items()))
    if CONTROL:
        return control(acts, cs, fam, outp, Path(argv[3]))
    anc = celdas(acts, juez, lambda a: a.anclas, " anclas")
    juzga(anc, m)
    robust = {}
    for c in anc:
        A = c["cond"].rsplit("_A", 1)[1]
        D = c["cond"].split("_")[1]
        r = robust.setdefault(f"{D} A{A}", {"pasa": 0, "contexto": 0, "medibles": 0})
        r["pasa"] += c["veredicto"] == "PASA"
        r["contexto"] += c["veredicto"] == "CONTEXTO"
        r["medibles"] += c["ajuste"]["n"] >= N_MIN and c["prueba"]["n"] >= N_MIN
    dmeta = json.loads((hist / "datos.json").read_text())
    huella = hashlib.sha256((meta["huella"] + json.dumps(dmeta, sort_keys=True) +
                             Path(__file__).read_text() + (Path(__file__).parent / "mapa_comun.py").read_text())
                            .encode()).hexdigest()[:16]
    muestra = []
    for a in acts:
        for e, lado in (("a", "largo"), ("e", "corto")):
            j = np.flatnonzero(~np.isnan(a.net[e, lado]) & (a.Eabs >= PR_INI))[::997][:2]
            muestra += [{"activo": a.s, "Eabs": int(a.Eabs[k]), "esquema": e, "lado": lado,
                         "tipo": ["", "TP", "SL", "VENCE"][int(a.tipo[e, lado][k])], "neto": rd(a.net[e, lado][k]),
                         "salida_abs": int(a.t0 + a.sal[e, lado][k])} for k in j]
    out = {"campana": "BOT-3c", "criterio": "scripts/mapa_comun.py", "huella": huella,
           "huella_historia": meta["huella"], "m": m, "B": B, "esquemas": NOMBRE_ESQ,
           "liston_acierto": {k: round(v, 4) for k, v in LISTON.items()},
           "datos": {s: {"perp_desde": str(datetime.fromtimestamp(a.t0 * 60, UTC).date()),
                         "metrics_desde": dmeta["simbolos"][s]["metrics"]["primer_dia"],
                         "prima_desde": dmeta["simbolos"][s]["prima"]["primer_mes"],
                         "spot_desde": dmeta["simbolos"][s]["spot"]["primer_mes"]} for s, a in
                     zip(SIMBOLOS, acts, strict=True)},
           "familias": fam, "anclajes_f1": robust,
           "liquidaciones": "SIN MEDIR: no hay historia fina publica (liquidationSnapshot 404); solo 90 dias de "
                            "5 min en Coinalyze y el agregado individual desde 2026-10-20",
           "muestra": muestra, "celdas": cs}
    outp.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    log(f"FIN {outp} {outp.stat().st_size} B")
    return 0


def control(acts, cs, fam, outp: Path, realp: Path) -> int:
    real = json.loads(realp.read_text())
    rv = {(c["familia"], c["cond"], c["esquema"], c["activo"], c["lado"]): c["veredicto"] for c in real["celdas"]}
    nuevas = [c for c in cs if c["veredicto"] == "PASA" and
              rv.get((c["familia"], c["cond"], c["esquema"], c["activo"], c["lado"])) != "PASA"]
    act = {a.s: a for a in acts}
    malas = []
    for c in nuevas:
        if c["familia"] in ("F8", "F8_barajado"):
            continue
        a = act[c["activo"]]
        b = a.cond[c["cond"]][1]
        solape = (b & a.rsi4_bajo).sum() / max(b.sum(), 1)
        if c["lado"] != "largo" or solape < 0.5:
            malas.append(f"{c['familia']} {c['cond']} {c['esquema']} {c['activo']} {c['lado']} solape={solape:.2f}")
    rsi_ok = any(c["cond"] == "rsi4h_bajo" and c["lado"] == "largo" and c["veredicto"] == "PASA" for c in cs)
    res = {"F2_rsi4h_bajo_largo_pasa": rsi_ok, "F8": fam.get("F8", {}).get("veredicto"),
           "F8_barajado": fam.get("F8_barajado", {}).get("veredicto"), "F0": fam.get("F0", {}).get("veredicto"),
           "nuevas_pasa": len(nuevas), "nuevas_sin_explicar": malas[:20],
           "familias": {f: d["veredicto"] for f, d in fam.items()},
           "celdas_rsi4h_bajo_largo": [{k: c[k] for k in ("esquema", "activo", "veredicto")} | {
               "neto": c["prueba"].get("neto"), "azar": c["prueba"].get("azar")} for c in cs
               if c["cond"] == "rsi4h_bajo" and c["lado"] == "largo"]}
    res["ve_el_estudio"] = bool(rsi_ok and res["F8"] == "PAGA" and res["F0"] == "RUIDO" and not malas)
    outp.write_text(json.dumps({"control": res, "celdas": cs}, separators=(",", ":")) + "\n")
    real["control"] = res
    realp.write_text(json.dumps(real, separators=(",", ":")) + "\n")
    log(f"CONTROL ve_el_estudio={res['ve_el_estudio']} {json.dumps(res)[:600]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
