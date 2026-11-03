"""EL ESTUDIO de la anatomia (BOT-3e): mide el criterio de `scripts/anatomia_comun.py` sobre la base de
`anatomia_extrae.py`. numpy + scikit-learn (venv aparte, fuera del repo). Corre en 143.

USO:  python anatomia_estudio.py SALIDA OUT.json                 descubrimiento; escribe OUT.json y candidatas.json
      python anatomia_estudio.py SALIDA OUT.json --control       primero el control positivo; si no ve, para
            con --control las candidatas van a candidatas-control.json: no pisan las del modo normal.
      python anatomia_estudio.py SALIDA OUT.json --confirma AAAA-MM-DD [--candidatas RUTA]
            solo mide candidatas.json (por defecto, junto a OUT.json) en dias >= FECHA, sin reelegir nada.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anatomia_comun as C  # noqa: E402

W7 = C.Z_DIAS * 1440
WG7 = W7 // C.REJILLA
NAN = np.nan


# ---------------------------------------------------------------- carga
def carga(salida: Path):
    B, ts = {}, None
    for s in C.SIMBOLOS:
        with gzip.open(Path(salida) / f"base-{s}.tsv.gz", "rt", encoding="utf-8") as f:
            cab = f.readline().rstrip("\n").split("\t")
            filas = [[float(v) if v else NAN for v in ln.rstrip("\n").split("\t")] for ln in f if ln.strip()]
        a = np.array(filas, dtype=float).reshape(-1, len(cab))
        B[s] = {c: a[:, i] for i, c in enumerate(cab)}
        if ts is None:
            ts = B[s]["ts"].astype(np.int64)
        elif not np.array_equal(ts, B[s]["ts"].astype(np.int64)):
            raise SystemExit(f"base-{s}: minutos distintos de base-{C.SIMBOLOS[0]}")
    if len(ts) > 1 and np.any(np.diff(ts) != 60):
        raise SystemExit("la base no es una rejilla continua de 1 minuto")
    return B, ts


# ---------------------------------------------------------------- utilidades causales (salida en i: solo <= i)
def shift(x, k):
    y = np.full(len(x), NAN)
    if k < len(x):
        y[k:] = x[:len(x) - k]
    return y


def ffill(x, limite=None):
    n = len(x)
    i = np.where(np.isfinite(x), np.arange(n), -1)
    np.maximum.accumulate(i, out=i)
    y = np.where(i >= 0, x[np.maximum(i, 0)], NAN)
    if limite is not None:
        y[np.arange(n) - i > limite] = NAN
    return y, i


def ff(x, limite=None):
    return ffill(x, limite)[0]


def _acum(x):
    return np.concatenate([[0.0], np.cumsum(x)])


def rsum(x, w, cob=0.8):
    """Suma de los ultimos w minutos (incluido i); NAN si hay menos de cob*w validos."""
    v = np.isfinite(x)
    cs, cn = _acum(np.where(v, x, 0.0)), _acum(v)
    i = np.arange(len(x)) + 1
    j = np.maximum(i - w, 0)
    return np.where(cn[i] - cn[j] >= cob * w - 1e-9, cs[i] - cs[j], NAN)


def z7(x):
    """z contra los 7 dias anteriores, SIN el presente: ventana [i-W7, i-1]."""
    v = np.isfinite(x)
    x0 = np.where(v, x, 0.0)
    cs, cs2, cn = _acum(x0), _acum(x0 * x0), _acum(v)
    b = np.arange(len(x))
    a = np.maximum(b - W7, 0)
    n = cn[b] - cn[a]
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = (cs[b] - cs[a]) / n
        sd = np.sqrt(np.maximum((cs2[b] - cs2[a]) / n - mu * mu, 0.0))
        z = (x - mu) / sd
    return np.where((n >= C.Z_MIN_MIN) & (sd > 0) & v, z, NAN)


def rmax(x, w):
    """Maximo de los ultimos w (incluido i), ignorando NAN (van Herk / Gil-Werman)."""
    n = len(x)
    y = np.concatenate([np.full(w - 1, -np.inf), np.where(np.isfinite(x), x, -np.inf)])
    y = np.concatenate([y, np.full((-len(y)) % w, -np.inf)]).reshape(-1, w)
    g = np.maximum.accumulate(y, axis=1).ravel()
    h = np.maximum.accumulate(y[:, ::-1], axis=1)[:, ::-1].ravel()
    out = np.maximum(h[:n], g[w - 1:w - 1 + n])
    return np.where(np.isfinite(out), out, NAN)


def rmin(x, w):
    return -rmax(-x, w)


def ret(c, w):
    with np.errstate(invalid="ignore", divide="ignore"):
        return c / shift(c, w) - 1


def rcorr(a, b, w):
    v = np.isfinite(a) & np.isfinite(b)
    a0, b0 = np.where(v, a, 0.0), np.where(v, b, 0.0)
    i = np.arange(len(a)) + 1
    j = np.maximum(i - w, 0)
    S = {k: _acum(x) for k, x in (("a", a0), ("b", b0), ("ab", a0 * b0), ("aa", a0 * a0), ("bb", b0 * b0),
                                  ("n", v.astype(float)))}
    s = {k: S[k][i] - S[k][j] for k in S}
    with np.errstate(invalid="ignore", divide="ignore"):
        num = s["n"] * s["ab"] - s["a"] * s["b"]
        den = np.sqrt((s["n"] * s["aa"] - s["a"] ** 2) * (s["n"] * s["bb"] - s["b"] ** 2))
        r = num / den
    return np.where((s["n"] >= 0.8 * w) & (den > 0), r, NAN)


def rsi_fase(c, k, n=14):
    """RSI de Wilder sobre velas de k minutos que cierran en i (fase movil): usa c[i], c[i-k], c[i-2k]..."""
    N = len(c)
    x = np.concatenate([c, np.full((-N) % k, NAN)]).reshape(-1, k)
    ag, al, cnt = np.full(k, NAN), np.full(k, NAN), np.zeros(k)
    out = np.full(x.shape, NAN)
    for r in range(1, x.shape[0]):
        d = x[r] - x[r - 1]
        ok = np.isfinite(d)
        g, lo = np.where(ok & (d > 0), d, 0.0), np.where(ok & (d < 0), -d, 0.0)
        semilla = ok & np.isnan(ag)
        ag = np.where(semilla, g, np.where(ok, (ag * (n - 1) + g) / n, ag))
        al = np.where(semilla, lo, np.where(ok, (al * (n - 1) + lo) / n, al))
        cnt += ok
        with np.errstate(invalid="ignore", divide="ignore"):
            rsi = np.where(al > 0, 100 - 100 / (1 + ag / al), np.where(ag > 0, 100.0, 50.0))
        out[r] = np.where(ok & (cnt >= n), rsi, NAN)
    return out.ravel()[:N]


def pct7(xg):
    """Rango percentil de xg[k] contra los puntos de rejilla de los 7 d anteriores (sin k)."""
    n = len(xg)
    p = np.concatenate([np.full(WG7, NAN), xg])
    out = np.full(n, NAN)
    for a in range(0, n, 4096):
        b = min(n, a + 4096)
        win = swv(p, WG7)[a:b]
        x = xg[a:b, None]
        v = np.isfinite(win)
        nv = v.sum(1)
        menor = ((win < x) & v).sum(1) + 0.5 * ((win == x) & v).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[a:b] = np.where((nv >= C.PCT_MIN) & np.isfinite(xg[a:b]), menor / nv, NAN)
    return out


def cond(mascara, *insumos):
    ok = np.ones(len(mascara), bool)
    for x in insumos:
        ok &= np.isfinite(x)
    return np.where(ok, np.where(ok, mascara, False).astype(float), NAN)


# ---------------------------------------------------------------- etiquetas
def etiquetas(o, h, lo, c, G, lado, esquema, bloque=4096):
    """Para cada decision t en G: (exito, neto, minuto de salida, valida). Igual que anatomia_comun.etiqueta."""
    tp, sl = C.ESQUEMAS[esquema]
    N, H = len(o), C.HORIZONTE
    ex, ne, sa, va = (np.zeros(len(G)), np.full(len(G), NAN), np.full(len(G), -1, np.int64),
                      np.zeros(len(G), bool))
    paso = np.arange(1, H + 1)
    for a in range(0, len(G), bloque):
        g = G[a:a + bloque]
        g = g[g + H < N]
        if not len(g):
            continue
        k = slice(a, a + len(g))
        filas = g[:, None] + paso
        e = o[g + 1]
        Hh, Ll, Cc = h[filas], lo[filas], c[filas]
        ok = np.isfinite(e) & np.isfinite(Hh).all(1) & np.isfinite(Ll).all(1) & np.isfinite(Cc).all(1)
        with np.errstate(invalid="ignore"):
            if lado > 0:
                st, ob = Ll <= (e * (1 - sl))[:, None], Hh >= (e * (1 + tp))[:, None]
            else:
                st, ob = Hh >= (e * (1 + sl))[:, None], Ll <= (e * (1 - tp))[:, None]
        fs = np.where(st.any(1), st.argmax(1), H)
        fo = np.where(ob.any(1), ob.argmax(1), H)
        gana = fo < fs
        pierde = (fs <= fo) & (fs < H)
        with np.errstate(invalid="ignore", divide="ignore"):
            vence = lado * (c[g + H] / e - 1) - 2 * C.COMISION
        ex[k] = gana
        ne[k] = np.where(gana, tp - 2 * C.COMISION, np.where(pierde, -sl - 2 * C.COMISION, vence))
        sa[k] = np.where(gana, g + 1 + fo, np.where(pierde, g + 1 + fs, g + H))
        va[k] = ok
    ne[~va] = NAN
    return ex * va, ne, sa, va


# ---------------------------------------------------------------- variables y mecanismos
def rejilla(ts):
    return np.flatnonzero(((ts // 60) + 1) % C.REJILLA == 0)


def horario(ts1):
    md = (ts1 // 60) % 1440
    dia = ts1 // 86400
    sem = (dia + 3) % 7                       # lunes = 0 (el 1-ene-1970 fue jueves)
    hora = md // 60
    du, inv = np.unique(dia, return_inverse=True)
    ap = np.array([C.apertura_eeuu_utc(datetime.fromtimestamp(int(d) * 86400, UTC)) for d in du])[inv]
    return {
        "sesion": np.select([md < 480, md < 780, md < 1260], [0.0, 1.0, 2.0], 3.0),
        "min_a_funding": ((480 - md % 480) % 480).astype(float),
        "min_desde_apertura_eeuu": np.where((sem < 5) & (md >= ap), md - ap, NAN).astype(float),
        "viernes_08z": ((sem == 4) & (hora == 8)).astype(float),
        "lunes_00z": ((sem == 0) & (hora == 0)).astype(float),
        "hora_semana": (sem * 24 + hora).astype(float),
    }


def vela_anterior(h, lo, ts, ts1, D):
    """Maximo y minimo de la vela de D dias ANTERIOR a la que contiene t+1 (velas en dias Unix multiplos de D)."""
    dk = (ts // 86400) // D
    k0 = dk.min()
    mx = np.full(dk.max() - k0 + 1, -np.inf)
    mn = np.full(dk.max() - k0 + 1, np.inf)
    np.maximum.at(mx, dk - k0, np.where(np.isfinite(h), h, -np.inf))
    np.minimum.at(mn, dk - k0, np.where(np.isfinite(lo), lo, np.inf))
    prev = (ts1 // 86400) // D - 1 - k0
    ok = (prev >= 0) & (prev < len(mx))
    p = np.clip(prev, 0, len(mx) - 1)
    a, b = np.where(ok, mx[p], NAN), np.where(ok, mn[p], NAN)
    return np.where(np.isfinite(a), a, NAN), np.where(np.isfinite(b), b, NAN)


def prepara(B, ts, oraculo=False):
    """Por simbolo: rejilla G, variables V (en G), mecanismos M[(nombre, capa)], etiquetas y capas."""
    G = rejilla(ts)
    tsg = ts[G]
    ts1 = tsg + 60
    t_fin = (ts + 60).astype(float)
    hor = horario(ts1)
    cb = ff(B["BTC"]["c"], 10)
    btc_r = {w: ret(cb, w) for w in (5, 15, 60)}
    btc_r5_z = z7(btc_r[5])
    D = {}
    for si, s in enumerate(C.SIMBOLOS):
        b = B[s]
        V = {}
        c = ff(b["c"], 10)
        h, lo = b["h"], b["l"]
        for w in (5, 15, 60):
            V[f"r_{w}"] = ret(c, w)
        r1 = ret(c, 1)
        for lado in "ls":
            x = b[f"liq_{lado}"]
            for w in (1, 5, 15, 60):
                V[f"liq_{lado}_{w}"] = rsum(x, w)
                V[f"liq_{lado}_{w}_z"] = z7(V[f"liq_{lado}_{w}"])
            V[f"liq_{lado}_n60s"] = b[f"liq_{lado}_n"]
            V[f"liq_{lado}_seg_grande"] = np.where(np.isfinite(x), t_fin - ff(b[f"liq_{lado}_gr_ult"]), NAN)
            for w in (5, 15, 60):
                V[f"liq5_{lado}_{w}"] = rsum(b[f"liq5_{lado}"], w, cob=0.8 / C.REJILLA)
                V[f"liq5_{lado}_{w}_z"] = z7(V[f"liq5_{lado}_{w}"])
        for k in "ps":
            for w in (1, 5, 15, 60):
                V[f"d{k}_{w}"] = rsum(b["d" + k], w)
                V[f"d{k}_{w}_z"] = z7(V[f"d{k}_{w}"])
                V[f"d{k}100k_{w}"] = rsum(b[f"d{k}100k"], w)
                V[f"d{k}1m_{w}"] = rsum(b[f"d{k}1m"], w)
            V[f"m{k}_5"] = np.where(np.isfinite(b["n" + k]), np.nan_to_num(rmax(b["m" + k], 5)), NAN)
            V[f"n{k}_5"] = rsum(b["n" + k], 5)
            V[f"n{k}_5_z"] = z7(V[f"n{k}_5"])
        for col in ("deseq01", "deseq05", "deseq05_todos"):
            V[col] = b[col]
        V["d_deseq05_5"] = b["deseq05"] - shift(b["deseq05"], 5)
        V["alcance_c"], V["alcance_v"], V["mayor_mediana"] = b["alc_c"], b["alc_v"], b["mayor_med"]
        oi, oiag = ff(b["oi"], 30), ff(b["oi_ag"], 30)
        V["d_oi_1h"], V["d_oi_4h"] = ret(oi, 60), ret(oi, 240)
        V["d_oiag_1h"], V["d_oiag_4h"] = ret(oiag, 60), ret(oiag, 240)
        V["cuadrante_oi"] = np.where(np.isfinite(V["d_oi_1h"]) & np.isfinite(V["r_60"]),
                                     2.0 * (V["d_oi_1h"] <= 0) + 1.0 * (V["r_60"] <= 0), NAN)
        V["funding"], V["funding_previsto"], V["ratio_lc"] = ff(b["fr"], 30), ff(b["pfr"], 30), ff(b["ls"], 30)
        V["spot_agg_15"] = rsum(b["sa_delta"], 15)
        V["spot_agg_15_z"] = z7(V["spot_agg_15"])
        for w in (5, 15, 60):
            V[f"dsp_{w}"] = V[f"ds_{w}"] - V[f"dp_{w}"]
        with np.errstate(invalid="ignore", divide="ignore"):
            V["prima_cb"] = b["c_cb"] / b["c"] - 1
        rs1 = ret(ff(b["c_cb"], 2), 1)
        V["lider_15"] = rcorr(shift(rs1, 1), r1, 15) - rcorr(shift(r1, 1), rs1, 15)
        cruz = s != "BTC"
        for nom, x in (("btc_r5", btc_r[5]), ("btc_r15", btc_r[15]),
                       ("fuerza_15", V["r_15"] - btc_r[15]), ("fuerza_60", V["r_60"] - btc_r[60])):
            V[nom] = x if cruz else np.full(len(ts), NAN)
        for nom, k in (("15m", 15), ("1h", 60), ("4h", 240), ("1d", 1440)):
            V[f"rsi_{nom}"] = rsi_fase(c, k)
        cp = shift(c, 1)
        with np.errstate(invalid="ignore", divide="ignore"):
            tr = (np.fmax(h, cp) - np.fmin(lo, cp)) / c
        atr = rsum(tr, 60) / 60
        for nom, w in (("24h", 1440), ("sem", W7)):
            V[f"dist_max_{nom}"] = c / rmax(h, w) - 1
            V[f"dist_min_{nom}"] = c / rmin(lo, w) - 1
        for d in (3, 9):
            mx, mn = vela_anterior(h, lo, ts, ts + 60, d)
            V[f"dist_max_{d}d"], V[f"dist_min_{d}d"] = c / mx - 1, c / mn - 1
        vol = np.where(np.isfinite(b["vol_ref"]), b["vol_ref"], 0.0)
        pv = np.where(np.isfinite(h + lo + c), (h + lo + c) / 3 * vol, 0.0)
        dia = ts // 86400
        i0 = np.searchsorted(dia, dia)
        cpv, cv = _acum(pv), _acum(vol)
        with np.errstate(invalid="ignore", divide="ignore"):
            vwap = (cpv[1:] - cpv[i0]) / (cv[1:] - cv[i0])
        V["dist_vwap_dia"] = c / vwap - 1
        # mecanismos al minuto
        M = {}
        bajo15, alto15 = rmin(lo, C.M1_VENTANA), rmax(h, C.M1_VENTANA)
        bajo_prev = shift(rmin(lo, C.M1_MIN_NUEVO), C.M1_VENTANA)
        alto_prev = shift(rmax(h, C.M1_MIN_NUEVO), C.M1_VENTANA)
        for capa, zl, zs in (("B", "liq_l_15_z", "liq_s_15_z"), ("A", "liq5_l_15_z", "liq5_s_15_z")):
            M[("M1", capa)] = cond((bajo15 < bajo_prev) & (V[zl] >= C.M1_Z) & (c >= bajo15 * (1 + C.M1_REBOTE)),
                                   bajo15, bajo_prev, V[zl], c)
            M[("M1e", capa)] = cond((alto15 > alto_prev) & (V[zs] >= C.M1_Z) & (c <= alto15 * (1 - C.M1_REBOTE)),
                                    alto15, alto_prev, V[zs], c)
        M[("M2", "B")] = cond((V["dp_5_z"] <= -C.M2_Z) & (V["r_5"] >= -C.M2_RET), V["dp_5_z"], V["r_5"])
        M[("M2e", "B")] = cond((V["dp_5_z"] >= C.M2_Z) & (V["r_5"] <= C.M2_RET), V["dp_5_z"], V["r_5"])
        M[("M3", "B")] = rmax(b["muro_c"], C.REJILLA)
        M[("M3e", "B")] = rmax(b["muro_v"], C.REJILLA)
        M[("M4", "B")] = cond((V["ds_15_z"] >= C.M4_Z) & (V["dp_15_z"] <= 0), V["ds_15_z"], V["dp_15_z"])
        M[("M4e", "B")] = cond((V["ds_15_z"] <= -C.M4_Z) & (V["dp_15_z"] >= 0), V["ds_15_z"], V["dp_15_z"])
        if cruz:
            M[("M7", "A")] = cond((btc_r5_z >= C.M7_Z) & (V["r_5"] < C.M7_FRAC * btc_r[5]), btc_r5_z, V["r_5"])
            M[("M7e", "A")] = cond((btc_r5_z <= -C.M7_Z) & (V["r_5"] > C.M7_FRAC * btc_r[5]), btc_r5_z, V["r_5"])
        for lado, nom in (("l", "M8"), ("s", "M8e")):
            L, idx = ffill(b[f"liq_{lado}_ult"])
            casc = np.where(idx >= 0, b[f"liq_{lado}_casc"][np.maximum(idx, 0)], NAN)
            calma = t_fin - L
            M[(nom, "B")] = np.where(np.isfinite(b[f"liq_{lado}"]),
                                     ((casc == 1) & (calma >= C.CASCADA_CALMA_S)
                                      & (calma < C.CASCADA_CALMA_S + 60 * C.REJILLA)).astype(float), NAN)
        vol5z = z7(rsum(b["vol_ref"], 5))
        rup_a, rup_b = c > shift(rmax(h, C.M1_MIN_NUEVO), 1), c < shift(rmin(lo, C.M1_MIN_NUEVO), 1)
        # a la rejilla
        VG = {k: v[G] for k, v in V.items()}
        MG = {k: v[G] for k, v in M.items()}
        VG.update(hor)
        VG["atr_1h_pct"] = pct7(atr[G])
        pr5 = pct7(np.abs(VG["r_5"]))
        bajo = np.where(np.isfinite(pr5), pr5 <= 1 / 3, False)
        VG["absorcion"] = np.where(np.isfinite(pr5) & np.isfinite(VG["dp_5_z"]),
                                   np.where(bajo, np.abs(VG["dp_5_z"]), 0.0), NAN)
        VG["absorcion_firmada"] = np.where(np.isfinite(pr5) & np.isfinite(VG["dp_5_z"]),
                                           np.where(bajo, VG["dp_5_z"], 0.0), NAN)
        poi, pfu = pct7(VG["d_oi_4h"]), pct7(VG["funding"])
        MG[("M5", "A")] = cond((poi >= C.M5_OI) & (pfu <= C.M5_FUND) & (VG["r_15"] > 0), poi, pfu, VG["r_15"])
        MG[("M5e", "A")] = cond((poi >= C.M5_OI) & (pfu >= 1 - C.M5_FUND) & (VG["r_15"] < 0), poi, pfu, VG["r_15"])
        ap = VG["atr_1h_pct"]
        MG[("M6", "B")] = cond((ap <= C.M6_ATR) & rup_a[G] & (vol5z[G] >= C.M6_VOL_Z), ap, vol5z[G], c[G])
        MG[("M6e", "B")] = cond((ap <= C.M6_ATR) & rup_b[G] & (vol5z[G] >= C.M6_VOL_Z), ap, vol5z[G], c[G])
        rng = np.random.default_rng(C.SEMILLA + si)
        for i in range(C.RUIDOS):
            VG[f"ruido_{i:02d}"] = rng.standard_normal(len(G))
        lab = {(lado, e): etiquetas(b["o"], b["h"], b["l"], b["c"], G, sg, e)
               for lado, sg in C.LADOS.items() for e in C.ESQUEMAS}
        cinta = _acum((b["fuente"] == C.FUENTE_CINTA).astype(float))
        Gc = np.minimum(G, len(ts) - C.HORIZONTE - 1)
        camino_cinta = (cinta[Gc + C.HORIZONTE + 1] - cinta[Gc + 1] == C.HORIZONTE) & (len(ts) > G + C.HORIZONTE)
        va = lab[("largo", "E1")][3]
        capas = {"A": va & (tsg >= C.CAPA_A_DESDE), "B": va & camino_cinta & (tsg >= C.CAPA_B_DESDE)}
        if oraculo:
            VG["oraculo"] = lab[("largo", "E1")][0] + \
                np.random.default_rng(C.SEMILLA + 99 + si).normal(0, C.ORACULO_RUIDO, len(G))
            VG["oraculo"][~va] = NAN
        D[s] = {"G": G, "ts": tsg, "V": VG, "M": MG, "lab": lab, "capa": capas}
    return D


# ---------------------------------------------------------------- medida
def umbral(x, cola):
    """(umbral, estricto) de la cola sobre los valores validos x, o None si la celda es degenerada."""
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return None
    if cola == "alto":
        u = float(np.quantile(x, 1 - C.DECIL))
        est = bool(np.mean(x >= u) > C.COLA_MAX)
        f = np.mean(x > u) if est else np.mean(x >= u)
    else:
        u = float(np.quantile(x, C.DECIL))
        est = bool(np.mean(x <= u) > C.COLA_MAX)
        f = np.mean(x < u) if est else np.mean(x <= u)
    return None if f < C.COLA_MIN else (u, est)


def condicion(x, cola, u=None, estricto=False):
    with np.errstate(invalid="ignore"):
        if cola == "alto":
            m = x > u if estricto else x >= u
        elif cola == "bajo":
            m = x < u if estricto else x <= u
        elif cola == "si":
            m = x == 1
        else:                                              # valor de una categorica
            m = x == u
    return m & np.isfinite(x)


def operaciones(m, ex, ne, sa, va, G):
    idx = np.flatnonzero(m & va)
    tom = C.sin_solape([(int(G[i]), int(sa[i])) for i in idx])
    sel = idx[tom]
    return len(sel), int(ex[sel].sum()), (float(ne[sel].mean()) if len(sel) else None)


def _f(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else x


def mide(D, desde, hasta, extra=(), desplazamientos=C.DESPLAZAMIENTOS, esquema="E1"):
    """Todas las celdas (variable x cola y mecanismos) por capa, simbolo y lado, decisiones con desde <= ts < hasta
    y salida antes de `hasta`. Devuelve la lista de celdas con p y q."""
    celdas = []
    smin = C.DESPL_MIN_MIN // C.REJILLA
    for capa, capa_desde in (("A", C.CAPA_A_DESDE), ("B", C.CAPA_B_DESDE)):
        nombres = [n for n, (cp, _t, _d) in C.VARIABLES.items() if cp == capa] + \
            ([n for n in extra] if capa == "A" else [])
        for si, s in enumerate(C.SIMBOLOS):
            d = D[s]
            fin_ok = d["ts"] + (C.HORIZONTE + 1) * 60 <= hasta
            idx = np.flatnonzero((d["ts"] >= max(desde, capa_desde)) & fin_ok)
            if len(idx) < 2 * smin + 2:
                continue
            Gi = d["G"][idx]
            rng = np.random.default_rng(C.SEMILLA + 7 * si + (0 if capa == "A" else 3))
            S = np.arange(smin, len(idx) - smin)
            S = rng.choice(S, size=min(desplazamientos, len(S)), replace=False)
            for lado in C.LADOS:
                ex, ne, sa, va = (a[idx] for a in d["lab"][(lado, esquema)])
                va = va & d["capa"][capa][idx]
                if va.sum() == 0:
                    continue
                def una(m, extra_celda, x, *, capa=capa, s=s, lado=lado, S=S, Gi=Gi, ex=ex, ne=ne, sa=sa, va=va):
                    # el azar y los desplazamientos, solo sobre las decisiones donde la variable EXISTE: si no,
                    # un tramo sin variable (los 2 primeros dias de un z, un hueco) con otro regimen se lleva el p
                    vx = va & np.isfinite(x)
                    if vx.sum() == 0:
                        return
                    y = ex * vx
                    Fy, Fv = np.fft.rfft(y), np.fft.rfft(vx.astype(float))
                    base = {"capa": capa, "simbolo": s, "lado": lado, "esquema": esquema,
                            "azar_tasa": float(y[vx].mean()), "azar_neto": float(np.nanmean(ne[vx])),
                            "azar_n": int(vx.sum())}
                    m = m & vx
                    Fm = np.conj(np.fft.rfft(m.astype(float)))
                    su = np.rint(np.fft.irfft(Fm * Fy, len(m)))
                    cu = np.rint(np.fft.irfft(Fm * Fv, len(m)))
                    if cu[0] == 0:
                        return
                    with np.errstate(invalid="ignore", divide="ignore"):
                        st = su[S] / cu[S]
                    t0 = su[0] / cu[0]
                    st = st[np.isfinite(st)]
                    p, via = C.p_desplazado(t0, st, len(S))
                    n, exitos, neto = operaciones(m, ex, ne, sa, va, Gi)
                    celdas.append({**extra_celda, **base, "n_todas": int(cu[0]), "tasa_todas": float(t0),
                                   "n": n, "exitos": exitos, "tasa": (exitos / n if n else None), "neto": neto,
                                   "p": p, "p_via": via})

                for nom in nombres:
                    x = d["V"][nom][idx]
                    if not np.isfinite(x).any():
                        continue
                    tipo = C.VARIABLES[nom][1] if nom in C.VARIABLES else "cont"
                    xd = x[va]
                    if tipo == "cont":
                        for cola in ("alto", "bajo"):
                            u = umbral(xd, cola)
                            if u is not None:
                                una(condicion(x, cola, *u), {"tipo": "variable", "nombre": nom, "cola": cola,
                                                             "umbral": u[0], "estricto": u[1]}, x)
                    elif tipo == "bin":
                        una(condicion(x, "si"), {"tipo": "variable", "nombre": nom, "cola": "si"}, x)
                    else:
                        for v in np.unique(x[np.isfinite(x)]):
                            una(condicion(x, "valor", float(v)), {"tipo": "variable", "nombre": nom,
                                                                  "cola": "valor", "umbral": float(v)}, x)
                for (nom, cp), x in d["M"].items():
                    if cp == capa and C.MECANISMOS[nom][0] == lado:
                        una(condicion(x[idx], "si"), {"tipo": "mecanismo", "nombre": nom, "cola": "si"}, x[idx])
    q = C.benjamini_hochberg([c["p"] for c in celdas])
    for c, qi in zip(celdas, q, strict=True):
        c["q"] = qi
        c["estado"] = "SIN N" if c["n"] < C.N_MIN_MECANISMO else (
            "PASA" if qi <= C.FDR_Q and C.gana(c["tasa"], c["neto"], C.empate(c["esquema"]), c["azar_tasa"]) else "NO")
    return celdas


def candidatas(celdas):
    ok = [c for c in celdas if c["estado"] != "SIN N" and not c["nombre"].startswith(("ruido_", "oraculo"))]
    pasan = sorted((c for c in ok if c["estado"] == "PASA"),
                   key=lambda c: (c["q"], -((c["tasa"] or 0) - c["azar_tasa"])))
    if pasan:
        sel, solo = pasan[:C.MAX_CANDIDATAS], False
    else:
        sel, solo = sorted(ok, key=lambda c: (c["p"], -((c["tasa"] or 0) - c["azar_tasa"])))[:C.SOLO_MIRAR], True
    claves = ("tipo", "nombre", "cola", "umbral", "estricto", "capa", "simbolo", "lado", "esquema")
    return [{**{k: c.get(k) for k in claves}, "solo_mirar": solo,
             "descubrimiento": {k: c[k] for k in ("n", "tasa", "neto", "azar_tasa", "p", "q")}} for c in sel]


# ---------------------------------------------------------------- todo junto
def todo_junto(D, hasta, barajados=C.HGB_BARAJADOS, params=None):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    params = params or C.HGB
    smin = C.DESPL_MIN_MIN // C.REJILLA
    out = {}
    for capa, desde in (("A", C.CAPA_A_DESDE), ("B", C.CAPA_B_DESDE)):
        cols = [n for n, (cp, _t, _d) in C.VARIABLES.items()
                if (cp == "A" or capa == "B") and not n.startswith("ruido_")]
        for lado in C.LADOS:
            X, y, t, sim = [], [], [], []
            for si, s in enumerate(C.SIMBOLOS):
                d = D[s]
                idx = np.flatnonzero(d["capa"][capa] & (d["ts"] >= desde)
                                   & (d["ts"] + (C.HORIZONTE + 1) * 60 <= hasta))
                if not len(idx):
                    continue
                X.append(np.column_stack([d["V"][c][idx] for c in cols] + [np.full(len(idx), si)]))
                y.append(d["lab"][(lado, "E1")][0][idx])
                t.append(d["ts"][idx])
                sim.append(np.full(len(idx), si))
            if not X or sum(len(a) for a in y) < 50:
                out[f"{capa}_{lado}"] = {"estado": "SIN N"}
                continue
            X, y, t, sim = np.vstack(X), np.concatenate(y), np.concatenate(t), np.concatenate(sim)
            bordes = np.quantile(t, np.linspace(0, 1, C.HGB_TRAMOS + 1))
            purga = C.HGB_PURGA_MIN * 60

            def fuera(yv, *, X=X, t=t, bordes=bordes, purga=purga):
                pr = np.full(len(yv), NAN)
                for f in range(C.HGB_TRAMOS):
                    a, b = bordes[f], bordes[f + 1]
                    te = (t >= a) & ((t < b) if f < C.HGB_TRAMOS - 1 else (t <= b))
                    tr = (t + purga < a) | (t > b + purga)
                    if tr.sum() < 20 or len(np.unique(yv[tr])) < 2 or not te.any():
                        continue
                    Xt = X[tr]
                    ok = np.array([len(np.unique(col[np.isfinite(col)])) > 1 for col in Xt.T])  # sin constantes
                    m = HistGradientBoostingClassifier(random_state=C.SEMILLA, **params).fit(Xt[:, ok], yv[tr])
                    pr[te] = m.predict_proba(X[te][:, ok])[:, 1]
                ok = np.isfinite(pr)
                if len(np.unique(yv[ok])) < 2:
                    return None, None
                top = ok & (pr >= np.nanquantile(pr, 1 - C.HGB_MEJOR))
                return float(roc_auc_score(yv[ok], pr[ok])), float(yv[top].mean())

            auc, tasa = fuera(y)
            rng = np.random.default_rng(C.SEMILLA + 5)
            nulos = []
            for _ in range(barajados):
                yb = y.copy()
                for si in np.unique(sim):
                    k = np.flatnonzero(sim == si)
                    if len(k) > 2 * smin + 1:
                        yb[k] = np.roll(y[k], int(rng.integers(smin, len(k) - smin)))
                nulos.append(fuera(yb))
            an = [a for a, _ in nulos if a is not None]
            out[f"{capa}_{lado}"] = {"n": int(len(y)), "auc": auc, "tasa_5_mejor": tasa,
                                     "tasa_base": float(y.mean()), "auc_desplazadas": an,
                                     "tasa_5_mejor_desplazadas": [b for _, b in nulos if b is not None],
                                     "p_auc": ((1 + sum(a >= auc for a in an)) / (1 + len(an))
                                               if auc is not None else None)}
    return out


# ---------------------------------------------------------------- control positivo
def planta(B, ts, D0):
    """Copia de B con un empuje tras cada M1 largo (capa A o B) del descubrimiento."""
    Bp = {}
    N = len(ts)
    for s in C.SIMBOLOS:
        d = D0[s]
        m = np.zeros(len(d["G"]), bool)
        for capa in "AB":
            x = d["M"].get(("M1", capa))
            if x is not None:
                m |= (x == 1)
        logf = np.zeros(N)
        for t in d["G"][m & (d["ts"] < C.CORTE_DESCUBRIMIENTO)]:
            k = np.arange(1, N - t)
            logf[t + 1:] += np.log1p(C.EMPUJE * np.minimum(1.0, k / C.EMPUJE_MIN))
        Bp[s] = dict(B[s])
        for col in ("o", "h", "l", "c", "c_cb"):
            Bp[s][col] = B[s][col] * np.exp(logf)
    return Bp


def control(B, ts, desplazamientos=C.DESPLAZAMIENTOS):
    D0 = prepara(B, ts)
    Bp = planta(B, ts, D0)
    D = prepara(Bp, ts, oraculo=True)
    celdas = mide(D, 0, C.CORTE_DESCUBRIMIENTO, extra=("oraculo",), desplazamientos=desplazamientos)
    pasan = [c for c in celdas if c["estado"] == "PASA"]
    m1 = [c for c in pasan if c["nombre"] == "M1" and c["lado"] == "largo"]
    orc = [c for c in pasan if c["nombre"] == "oraculo" and c["cola"] == "alto" and c["lado"] == "largo"]
    ruido = [c for c in pasan if c["nombre"].startswith("ruido_")]
    ve = bool(m1) and bool(orc) and len(ruido) <= C.FDR_Q * len(pasan)
    def resumen(cs):
        return [{k: c.get(k) for k in ("nombre", "cola", "capa", "simbolo", "lado", "n", "tasa",
                                       "azar_tasa", "p", "q")} for c in cs]
    return {"ve": ve, "m1_encontrado": resumen(m1), "oraculo_encontrado": resumen(orc),
            "ruido_que_pasa": resumen(ruido), "celdas_que_pasan": len(pasan),
            "pasan": sorted({c["nombre"] for c in pasan})}, celdas


# ---------------------------------------------------------------- confirmacion
def confirma(D, cands, fecha_ts, hasta=None):
    res = []
    for k in cands:
        d = D[k["simbolo"]]
        ex, ne, sa, va = d["lab"][(k["lado"], k["esquema"])]
        fin = d["ts"] + (C.HORIZONTE + 1) * 60 <= (hasta if hasta is not None else np.inf)
        idx = (d["ts"] >= fecha_ts) & d["capa"][k["capa"]] & fin
        x = d["M"][(k["nombre"], k["capa"])] if k["tipo"] == "mecanismo" else d["V"][k["nombre"]]
        m = condicion(x, k["cola"], k.get("umbral"), bool(k.get("estricto"))) & idx
        n, exitos, neto = operaciones(m, ex, ne, sa, va, d["G"])
        res.append({**k, "confirmacion": {"n": n, "exitos": exitos, "tasa": exitos / n if n else None,
                                          "neto": neto, "wilson90_inf": C.wilson_inferior(exitos, n),
                                          "empate": C.empate(k["esquema"]), "azar": C.azar(k["esquema"]),
                                          "veredicto": C.veredicto_confirma(exitos, n, k["esquema"])}})
    return res


def limpia(o):
    if isinstance(o, dict):
        return {str(k): limpia(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [limpia(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return _f(float(o))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def corre(salida, out, control_pos=False, fecha=None, cand_ruta=None, desplazamientos=C.DESPLAZAMIENTOS,
          barajados=C.HGB_BARAJADOS, hgb=True, hgb_params=None):
    B, ts = carga(salida)
    out = Path(out)
    cand_ruta = Path(cand_ruta) if cand_ruta else out.parent / (
        "candidatas-control.json" if control_pos and not fecha else "candidatas.json")
    res = {"criterio": "scripts/anatomia_comun.py", "salida": str(salida)}
    if fecha:
        cands = json.loads(cand_ruta.read_text())["candidatas"]
        fts = int(datetime.fromisoformat(fecha).replace(tzinfo=UTC).timestamp())
        res.update(modo="confirma", desde=fecha, candidatas=confirma(prepara(B, ts), cands, fts))
        out.write_text(json.dumps(limpia(res), indent=1))
        return res
    res["modo"] = "descubrimiento"
    if control_pos:
        ctrl, _ = control(B, ts, desplazamientos)
        res["control"], res["ve_el_estudio"] = ctrl, ctrl["ve"]
        if not ctrl["ve"]:
            out.write_text(json.dumps(limpia(res), indent=1))
            return res
    else:
        res["ve_el_estudio"] = None                        # no medido: corre con --control
    D = prepara(B, ts)
    celdas = mide(D, 0, C.CORTE_DESCUBRIMIENTO, desplazamientos=desplazamientos)
    cands = candidatas(celdas)
    res["celdas"] = celdas
    res["ruido_que_pasa"] = sum(1 for c in celdas if c["nombre"].startswith("ruido_") and c["estado"] == "PASA")
    res["candidatas"] = cands
    if hgb:
        res["todo_junto"] = todo_junto(D, C.CORTE_DESCUBRIMIENTO, barajados, hgb_params)
    out.write_text(json.dumps(limpia(res), indent=1))
    cand_ruta.write_text(json.dumps(limpia({"candidatas": cands}), indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--confirma", metavar="AAAA-MM-DD")
    ap.add_argument("--candidatas", type=Path)
    a = ap.parse_args(argv)
    r = corre(a.salida, a.out, a.control, a.confirma, a.candidatas)
    print(f"{a.out}: modo {r['modo']}, ve_el_estudio={r.get('ve_el_estudio')}, "
          f"candidatas {len(r.get('candidatas', []))}")


if __name__ == "__main__":
    main()
