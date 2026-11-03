"""LA GESTION de la anatomia (BOT-3e, remate 1): stops, objetivos, entrada limite y cuenta sobre M1, M2, M8, sus
espejos y las candidatas del estudio. El criterio, en `anatomia_comun.py` (REMATE 1). numpy. Corre en 143.

USO:  python anatomia_gestion.py SALIDA OUT.json --candidatas candidatas.json
            descubrimiento: todas las celdas con p y q, la cuenta y congeladas.json (junto a OUT.json)
      python anatomia_gestion.py SALIDA OUT.json --confirma AAAA-MM-DD [--congeladas RUTA]
            solo mide la combinacion congelada en dias >= FECHA, sin reelegir nada.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anatomia_comun as C  # noqa: E402
import anatomia_estudio as E  # noqa: E402

NAN = np.nan
H = C.HORIZONTE


# ---------------------------------------------------------------- salidas (primer toque, gana el stop)
def salidas(o, h, lo, c, ini, e, lado, sl, tp, solo_stop0=False, bloque=2048):
    """Camino desde el minuto ini (H minutos; con solo_stop0, ini + H y en ini solo cuenta el stop). e precio de
    entrada, sl distancia de stop (escalar o por operacion). Devuelve (exito, bruto, salida, valida, mae a la salida)."""
    ini, e = np.asarray(ini, np.int64), np.asarray(e, float)
    sl = np.broadcast_to(np.asarray(sl, float), e.shape)
    k = len(ini)
    ex, br, sa, va, mae = (np.zeros(k, bool), np.full(k, NAN), np.full(k, -1, np.int64), np.zeros(k, bool),
                           np.full(k, NAN))
    nc = H + (1 if solo_stop0 else 0)
    paso = np.arange(nc)
    for a in range(0, k, bloque):
        s_ = slice(a, a + bloque)
        g, ee, ss = ini[s_], e[s_], sl[s_]
        ok0 = (g + nc - 1 < len(o)) & (g >= 0)
        f = np.where(ok0[:, None], g[:, None] + paso, 0)
        Hh, Ll = h[f], lo[f]
        ok = ok0 & np.isfinite(ee) & np.isfinite(ss) & (ss > 0) & np.isfinite(Hh).all(1) & np.isfinite(Ll).all(1)
        ok &= np.isfinite(c[np.where(ok0, g + nc - 1, 0)])
        with np.errstate(invalid="ignore", divide="ignore"):
            if lado > 0:
                st, ob = Ll <= (ee * (1 - ss))[:, None], Hh >= (ee * (1 + tp))[:, None]
                adv = 1 - Ll / ee[:, None]
            else:
                st, ob = Hh >= (ee * (1 + ss))[:, None], Ll <= (ee * (1 - tp))[:, None]
                adv = Hh / ee[:, None] - 1
            vence = lado * (c[np.where(ok0, g + nc - 1, 0)] / ee - 1)
        if solo_stop0:
            ob[:, 0] = False
        fs = np.where(st.any(1), st.argmax(1), nc)
        fo = np.where(ob.any(1), ob.argmax(1), nc)
        gana, pierde = fo < fs, (fs <= fo) & (fs < nc)
        col = np.where(gana, fo, np.where(pierde, fs, nc - 1))
        ex[s_] = gana & ok
        br[s_] = np.where(gana, tp, np.where(pierde, -ss, vence))
        sa[s_] = g + col
        va[s_] = ok
        mae[s_] = np.take_along_axis(np.maximum.accumulate(np.nan_to_num(adv, nan=0.0), 1), col[:, None], 1)[:, 0]
    br[~va] = NAN
    return ex, br, sa, va, mae


def mae_mfe(o, h, lo, G, lado):
    """MAE hasta tocar +MAE_OBJ (o 240) y MFE en 240, desde la apertura de t+1. NaN si falta un minuto."""
    f = G[:, None] + 1 + np.arange(H)
    f = np.minimum(f, len(o) - 1)
    e = o[np.minimum(G + 1, len(o) - 1)][:, None]
    with np.errstate(invalid="ignore", divide="ignore"):
        fav = (h[f] / e - 1) if lado > 0 else (1 - lo[f] / e)
        adv = (1 - lo[f] / e) if lado > 0 else (h[f] / e - 1)
    ok = np.isfinite(fav).all(1) & np.isfinite(adv).all(1) & (len(o) > G + H)
    toca = (fav >= C.MAE_OBJ).any(1)
    hasta = np.where(toca, (fav >= C.MAE_OBJ).argmax(1), H - 1)
    mae = np.take_along_axis(np.maximum.accumulate(np.nan_to_num(adv), 1), hasta[:, None], 1)[:, 0]
    return np.where(ok, mae, NAN), np.where(ok, np.nanmax(np.where(np.isfinite(fav), fav, -np.inf), 1), NAN), toca & ok


def _pct(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return {f"p{q}": (float(np.percentile(x, q)) * 100 if len(x) else None) for q in (50, 75, 90)} | {"n": len(x)}


# ---------------------------------------------------------------- stops del mercado y niveles (minutos <= t)
def contexto(B, ts):
    D = E.prepara(B, ts)
    X = {}
    for s in C.SIMBOLOS:
        b = B[s]
        o, h, lo, c = b["o"], b["h"], b["l"], E.ff(b["c"], 10)
        H60, L60, cp = E.rmax(h, 60), E.rmin(lo, 60), E.shift(c, 60)
        tr = np.fmax(H60, cp) - np.fmin(L60, cp)
        atr = sum(E.shift(tr, 60 * k) for k in range(C.ATR1H_VELAS)) / C.ATR1H_VELAS / c
        niv = {"largo": {"24h": E.rmin(lo, 1440), "sem": E.rmin(lo, 10080)},
               "corto": {"24h": E.rmax(h, 1440), "sem": E.rmax(h, 10080)}}
        for d in (3, 9):
            mx, mn = E.vela_anterior(h, lo, ts, ts + 60, d)
            niv["largo"][f"{d}d"], niv["corto"][f"{d}d"] = mn, mx
        X[s] = {"o": o, "h": h, "l": lo, "c": c, "atr": atr, "niv": niv,
                "mecha": {"largo": E.rmin(lo, C.STOP_MECHA_MIN) * (1 - C.STOP_MECHA_MARGEN),
                          "corto": E.rmax(h, C.STOP_MECHA_MIN) * (1 + C.STOP_MECHA_MARGEN)}}
    return D, X


def dist_stop(x, G, lado, regla):
    """Distancia de stop por decision para una regla: un numero (fijo), «mecha», «atr05» o «atr1»."""
    if isinstance(regla, (int, float)):
        return np.full(len(G), float(regla))
    if regla == "mecha":
        e, st = x["o"][np.minimum(G + 1, len(x["o"]) - 1)], x["mecha"][lado][G]
        with np.errstate(invalid="ignore", divide="ignore"):
            d = (1 - st / e) if lado == "largo" else (st / e - 1)
        return np.where(d > 0, d, NAN)
    return C.STOP_ATR[regla] * x["atr"][G]


def armadas(x, G, lado, nivel):
    """(armada, limite) por decision."""
    L, cc = x["niv"][lado][nivel][G], x["c"][G]
    with np.errstate(invalid="ignore", divide="ignore"):
        dd = cc / L - 1 if lado == "largo" else 1 - cc / L
    arm = np.isfinite(dd) & (dd >= 0) & (dd <= C.LIM_ARMA)
    sg = C.LADOS[lado]
    return arm, L * (1 - sg * C.LIM_MAS_ALLA)


def llenado(x, G, lado, lim):
    """Primer minuto de t+1..t+CADUCA que CRUZA el limite (-1 si caduca), y si el tramo tiene precio."""
    f = np.minimum(G[:, None] + 1 + np.arange(C.LIM_CADUCA), len(x["l"]) - 1)
    with np.errstate(invalid="ignore"):
        cr = (x["l"][f] <= (lim * (1 - C.LIM_CRUCE))[:, None]) if lado == "largo" else \
            (x["h"][f] >= (lim * (1 + C.LIM_CRUCE))[:, None])
    hay = cr.any(1)
    pos = cr.argmax(1)
    fin = np.where(hay, pos, C.LIM_CADUCA - 1)
    sano = np.isfinite(x["l"][f]) & np.isfinite(x["h"][f])
    ok = np.take_along_axis(np.cumsum(~sano, 1), fin[:, None], 1)[:, 0] == 0
    ok &= len(x["l"]) > G + C.LIM_CADUCA
    return np.where(hay, G + 1 + pos, -1), ok


# ---------------------------------------------------------------- p por desplazamiento circular (como el estudio)
def p_circular(m, y, v, S, t0=None):
    Fm = np.conj(np.fft.rfft(m.astype(float)))
    su = np.rint(np.fft.irfft(Fm * np.fft.rfft(y.astype(float)), len(m)))
    cu = np.rint(np.fft.irfft(Fm * np.fft.rfft(v.astype(float)), len(m)))
    if t0 is None:
        if cu[0] == 0:
            return None, None, 0, None
        t0 = su[0] / cu[0]
    with np.errstate(invalid="ignore", divide="ignore"):
        st = su[S] / cu[S]
    st = st[np.isfinite(st)]
    if not len(st):
        return None, t0, int(cu[0]), None
    p, via = C.p_desplazado(t0, st, len(S))
    return p, t0, int(cu[0]), via


def desplazamientos(n, semilla, k=C.DESPLAZAMIENTOS):
    smin = C.DESPL_MIN_MIN // C.REJILLA
    S = np.arange(smin, n - smin)
    return np.random.default_rng(semilla).choice(S, size=min(k, len(S)), replace=False) if len(S) else S


# ---------------------------------------------------------------- una celda
def entrada_mascara(D, s, defn):
    d = D[s]
    if defn["tipo"] == "mecanismo":
        x = d["M"].get((defn["nombre"], defn["capa"]))
        return None if x is None else E.condicion(x, "si")
    x = d["V"].get(defn["nombre"])
    return None if x is None else E.condicion(x, defn["cola"], defn.get("umbral"), bool(defn.get("estricto")))


def mide_celda(D, X, defn, desde, hasta, con_p=False, cache=None):
    """defn: simbolo, lado, capa, stop (numero o regla), objetivo y entrada (mecanismo / variable / limite). Devuelve
    la celda (con p si con_p) y las operaciones sin solape (ts, exito, R, stop, mae)."""
    s, lado, tp = defn["simbolo"], defn["lado"], defn["objetivo"]
    d, x, sg = D[s], X[s], C.LADOS[lado]
    G, tsg = d["G"], d["ts"]
    idx = (tsg >= max(desde, C.CAPA_A_DESDE if defn["capa"] == "A" else C.CAPA_B_DESDE)) & d["capa"][defn["capa"]]
    sl = dist_stop(x, G, lado, defn["stop"])
    cache = {} if cache is None else cache
    lim = defn["tipo"] == "limite"
    c_in = C.MAKER if lim else C.TAKER
    if lim:
        arm, L = armadas(x, G, lado, defn["nivel"])
        arm &= idx
        f, okf = llenado(x, G, lado, L)
        ex, br, sa, va, mae = (np.zeros(len(G), bool), np.full(len(G), NAN), G + C.LIM_CADUCA,
                               np.zeros(len(G), bool), np.full(len(G), NAN))
        j = np.flatnonzero(arm & okf & (f >= 0))
        r = salidas(x["o"], x["h"], x["l"], x["c"], f[j], L[j], sg, sl[j], tp, solo_stop0=True)
        for a, v in zip((ex, br, sa, va, mae), r, strict=True):
            a[j] = v
        cad = arm & okf & (f < 0)
        fin =(tsg + (np.where(va, sa, G + C.LIM_CADUCA) - G + 1) * 60) <= hasta
        m = (arm & okf & fin) & (va | cad)
    else:
        clave = (s, lado, str(defn["stop"]), tp)
        if clave not in cache:
            cache[clave] = salidas(x["o"], x["h"], x["l"], x["c"], G + 1, x["o"][np.minimum(G + 1, len(x["o"]) - 1)],
                                   sg, sl, tp)
        ex, br, sa, va, mae = cache[clave]
        fin = tsg + (H + 1) * 60 <= hasta
        va = va & idx & fin
        mk = entrada_mascara(D, s, defn)
        if mk is None:
            return None, None
        m = mk & va
    ne = br - c_in - C.TAKER
    idx = np.flatnonzero(m)
    tom = idx[C.sin_solape([(int(G[i]), int(sa[i])) for i in idx])]
    ops = tom[va[tom]]
    n, exitos = len(ops), int(ex[ops].sum())
    sm = float(np.mean(sl[ops])) if n else (float(defn["stop"]) if isinstance(defn["stop"], (int, float)) else None)
    emp = C.empate_g(sm, tp, c_in, C.TAKER) if sm else None
    celda = {**defn, "n": n, "exitos": exitos, "tasa": exitos / n if n else None,
             "neto": float(np.mean(ne[ops])) if n else None, "stop_medio": sm, "empate": emp,
             "azar": sm / (tp + sm) if sm else None}
    if lim:
        celda.update(armadas=int(len(tom)), llenadas=int(va[tom].sum()), no_llenadas=int((~va[tom]).sum()))
    if con_p:
        sem = C.SEMILLA + 11 * C.SIMBOLOS.index(s)
        if lim:
            JJ = np.flatnonzero(idx & (tsg + (2 * H + 2) * 60 <= hasta))
            dd = np.nanmedian(np.abs(1 - L[arm] / x["c"][G[arm]])) if arm.any() else NAN
            v_ = np.zeros(len(G), bool)
            y_ = np.zeros(len(G), bool)
            if np.isfinite(dd) and len(JJ):
                L0 = x["c"][G[JJ]] * (1 - sg * dd)
                f0, ok0 = llenado(x, G[JJ], lado, L0)
                jj = np.flatnonzero(ok0 & (f0 >= 0))
                e0, _, _, va0, _ = salidas(x["o"], x["h"], x["l"], x["c"], f0[jj], L0[jj], sg, sl[JJ][jj], tp, True)
                v_[JJ[jj]], y_[JJ[jj]] = va0, e0
            mm = arm & okf & va
            t0 = ex[mm].sum() / mm.sum() if mm.sum() else None
            p, t0, nt, via = (p_circular(mm[JJ], y_[JJ], v_[JJ], desplazamientos(len(JJ), sem), t0)
                              if t0 is not None and len(JJ) else (None, t0, 0, None))
        else:
            J = np.flatnonzero(idx & fin)
            p, t0, nt, via = p_circular(m[J], (ex & va)[J], va[J], desplazamientos(len(J), sem))
        celda.update(p=p, p_via=via, tasa_todas=t0, n_todas=nt)
    tr = {"ts": tsg[ops], "exito": ex[ops], "R": ne[ops] / (sl[ops] + c_in + C.TAKER), "stop": sl[ops],
          "com": c_in + C.TAKER, "mae": mae[ops]}
    return celda, tr


# ---------------------------------------------------------------- la cuenta
def caminos(ts, R, rng, k=C.CUENTA_CAMINOS, n=C.CUENTA_OPS):
    """Remuestreo por semanas: (k, n) de R."""
    sem = np.asarray(ts, np.int64) // 604800
    orden = np.argsort(sem, kind="stable")
    R, sem = np.asarray(R, float)[orden], sem[orden]
    us, ini, cnt = np.unique(sem, return_index=True, return_counts=True)
    w = rng.integers(0, len(us), size=(k, n))
    cc = np.cumsum(cnt[w], 1)
    pos = np.arange(n)
    d = (cc[:, :, None] <= pos[None, None, :]).sum(1)
    previo = np.where(d > 0, np.take_along_axis(cc, np.maximum(d - 1, 0), 1), 0)
    return R[ini[np.take_along_axis(w, d, 1)] + pos[None, :] - previo]


def racha(perdida):
    perdida = np.atleast_2d(perdida)
    run = best = np.zeros(perdida.shape[0], int)
    for j in range(perdida.shape[1]):
        run = np.where(perdida[:, j], run + 1, 0)
        best = np.maximum(best, run)
    return best


def cuenta(tr, semilla=C.SEMILLA):
    R = np.asarray(tr["R"], float)
    P = caminos(tr["ts"], R, np.random.default_rng(semilla))
    out = {"n": len(R), "neto_R": float(R.mean()), "suma_R_p50": float(np.median(P.sum(1))),
           "peor_racha": int(racha(R < 0)[0]), "peor_racha_p90": float(np.percentile(racha(P < 0), 90)),
           "riesgo": {}}
    for f in C.CUENTA_RIESGOS:
        eq = np.cumprod(np.clip(1 + f * P, 0, None), 1)
        pico = np.maximum.accumulate(np.maximum(eq, 1.0), 1)
        dd = (1 - eq / pico).max(1)
        out["riesgo"][f"{f:.2f}"] = {"caida_p50": float(np.median(dd)), "caida_p90": float(np.percentile(dd, 90)),
                                     "final_p50": float(np.median(eq[:, -1])),
                                     "p_ruina": float(np.mean(eq.min(1) <= C.CUENTA_RUINA))}
    return out


def apalancamiento(tr, margen=C.APAL_MARGEN, riesgo=C.APAL_RIESGO):
    """Por operacion: nocional, apalancamiento y liquidacion; la tasa sale de las etiquetas, no del nocional."""
    sl, com, mae = np.asarray(tr["stop"], float), tr["com"], np.asarray(tr["mae"], float)
    apal = riesgo / (sl + com) / margen
    liq = 1 / apal - C.APAL_MANT
    no_cabe = liq < sl + C.APAL_COLCHON
    n = len(sl)
    return {"apal_p50": float(np.median(apal)) if n else None, "liq_p50": float(np.median(liq)) if n else None,
            "no_cabe": int(no_cabe.sum()), "NO_CABE": bool(n and no_cabe.mean() > 0.5),
            "tocan_liquidacion": int((mae >= liq).sum()), "tasa": float(np.mean(tr["exito"])) if n else None}


# ---------------------------------------------------------------- la corrida
def definiciones(cands):
    ents = [{"tipo": "mecanismo", "nombre": nom, "cola": "si", "capa": cp, "lado": C.MECANISMOS[nom][0],
             "simbolo": s} for s in C.SIMBOLOS for nom, cp in C.GESTION_ENTRADAS]
    for k in cands or ():
        ents.append({q: k.get(q) for q in ("tipo", "nombre", "cola", "umbral", "estricto", "capa", "lado",
                                           "simbolo")})
    out = [{**en, "stop": st, "objetivo": tp} for en in ents
           for st in list(C.G_STOPS) + ["mecha"] + list(C.STOP_ATR) for tp in C.G_OBJETIVOS]
    out += [{"tipo": "limite", "nombre": f"limite_{nv}", "nivel": nv, "capa": "A", "lado": lado, "simbolo": s,
             "stop": st, "objetivo": tp} for s in C.SIMBOLOS for lado in C.LADOS for nv in C.LIM_NIVELES
            for st in C.G_STOPS for tp in C.G_OBJETIVOS]
    return out


def descubre(D, X, cands, hasta=C.CORTE_DESCUBRIMIENTO):
    celdas, trs, cache = [], [], {}
    for defn in definiciones(cands):
        ce, tr = mide_celda(D, X, defn, 0, hasta, con_p=True, cache=cache)
        if ce is not None:
            celdas.append(ce)
            trs.append(tr)
    q = C.benjamini_hochberg([c.get("p") for c in celdas])
    for c, qi, tr in zip(celdas, q, trs, strict=True):
        c["q"] = qi
        c["estado"] = "SIN N" if c["n"] < C.N_MIN_CONFIRMA else \
            ("PASA" if qi is not None and qi <= C.FDR_Q and C.gana(c["tasa"], c["neto"], c["empate"]) else "NO")
        if c["n"] >= C.N_MIN_CONFIRMA:
            c["cuenta"], c["apalancamiento"] = cuenta(tr), apalancamiento(tr)
    ok = [c for c in celdas if c["n"] >= C.N_MIN_CONFIRMA and c["empate"] is not None]
    mejor = max(ok, key=lambda c: (c["tasa"] - c["empate"], -(c["q"] if c["q"] is not None else 1)), default=None)
    MAE = {}
    for s in C.SIMBOLOS:
        d, G = D[s], D[s]["G"]
        for nom, cp in C.GESTION_ENTRADAS:
            if (nom, cp) not in d["M"]:
                continue
            m = E.condicion(d["M"][(nom, cp)], "si") & d["capa"][cp] & (d["ts"] + (H + 1) * 60 <= hasta)
            idx = np.flatnonzero(m)
            idx = idx[C.sin_solape([(int(G[i]), int(G[i]) + H) for i in idx])]
            mae, mfe, toca = mae_mfe(X[s]["o"], X[s]["h"], X[s]["l"], G[idx], C.LADOS[C.MECANISMOS[nom][0]])
            MAE[f"{s}:{nom}:{cp}"] = {"mae_tocan": _pct(mae[toca]), "mae_todas": _pct(mae), "mfe_todas": _pct(mfe)}
    return celdas, mejor, MAE


CONGELA = ("tipo", "nombre", "cola", "umbral", "estricto", "capa", "lado", "simbolo", "stop", "objetivo", "nivel")


def congela(mejor):
    d = {k: mejor[k] for k in CONGELA if k in mejor}
    d.update(comision_entrada=C.MAKER if d["tipo"] == "limite" else C.TAKER, comision_salida=C.TAKER,
             empate=mejor["empate"], azar=mejor["azar"],
             descubrimiento={k: mejor.get(k) for k in ("n", "exitos", "tasa", "p", "q")})
    return d


def confirma(D, X, cong, fecha_ts, hasta=np.inf):
    ce, _ = mide_celda(D, X, {k: cong[k] for k in CONGELA if k in cong}, fecha_ts, hasta)
    n, ex = (ce["n"], ce["exitos"]) if ce else (0, 0)
    return {**cong, "confirmacion": {"n": n, "exitos": ex, "tasa": ex / n if n else None,
                                     "wilson90_inf": C.wilson_inferior(ex, n),
                                     "veredicto": C.veredicto_con(ex, n, cong["empate"], cong["azar"])}}


def corre(salida, out, cand_ruta=None, fecha=None, cong_ruta=None):
    B, ts = E.carga(salida)
    D, X = contexto(B, ts)
    out = Path(out)
    cong_ruta = Path(cong_ruta) if cong_ruta else out.parent / "congeladas.json"
    res = {"criterio": "scripts/anatomia_comun.py (REMATE 1)", "salida": str(salida)}
    if fecha:
        fts = C._ts(fecha)
        cong = json.loads(cong_ruta.read_text())["congeladas"]
        res.update(modo="confirma", desde=fecha, congeladas=[confirma(D, X, k, fts) for k in cong])
    else:
        cands = json.loads(Path(cand_ruta).read_text())["candidatas"] if cand_ruta else []
        celdas, mejor, MAE = descubre(D, X, cands)
        res.update(modo="descubrimiento", celdas=celdas, mae_mfe=MAE, la_mejor_no_es_un_resultado=True)
        cong_ruta.write_text(json.dumps(E.limpia({"congeladas": [congela(mejor)] if mejor else []}), indent=1))
    out.write_text(json.dumps(E.limpia(res), indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("salida", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--candidatas", type=Path)
    ap.add_argument("--confirma", metavar="AAAA-MM-DD")
    ap.add_argument("--congeladas", type=Path)
    a = ap.parse_args(argv)
    corre(a.salida, a.out, a.candidatas, a.confirma, a.congeladas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
