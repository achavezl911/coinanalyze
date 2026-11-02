"""EL SESGO (campana BOT-3d): ¿sumadas con una regla fija, las condiciones del mapa pagan comision? numpy, venv aparte.

USO (con el venv aparte, fuera del repo):
    python mapa_sesgo.py HIST OUT.json                       la medida real, con el control negativo
    MAPA_CONTROL=1 MAPA_EMPUJE=0.003 MAPA_EMPUJE_MIN=1 python mapa_sesgo.py HIST CTRL.json REAL.json
        el control positivo: la misma regla sobre la copia plantada de mapa_estudio; escribe en REAL.json la
        seccion «control_positivo» (rsi4h_bajo tiene que entrar con signo + y el esquema a largo mejorar).

LA REGLA la fijo el operador; aqui no se cambia ni se prueban variantes:
  1 condiciones: las de F2..F7 y las de F1 de 3 dias (anclaje 0). Ni F0, ni F8, ni F1 de 9 dias.
  2 AJUSTE, tres activos juntos, esquema c, operaciones y remuestreo del Juez de mapa_estudio (las celdas tal cual:
    una diaria opera en su decision de las 00:00 contra el azar diario), los mismos pesos por semana para los dos
    lados: dir = (dif_largo - dif_corto) / 2, se_dir su desviacion remuestreada. ENTRA si n >= 100 en cada lado y
    |dir| / se_dir >= 2, con el signo de dir.
  3 S en cada decision de 4 h: suma de los signos de las condiciones ciertas; una diaria cuenta en su decision de
    las 00:00 y en las 5 siguientes.
  4 k: el menor entero >= 1 con |S| >= k en <= 10 % de las decisiones del AJUSTE (Eabs < 2023-12-30, fuera de los
    30 dias calientes), los tres activos juntos.
  5 largo si S >= k, corto si S <= -k, una abierta a la vez por activo, esquema y lado (operaciones de mapa_estudio).
  6 PRUEBA, por esquema y lado, tres activos juntos, contra el azar de 4 h: m = 10, z = Phi^-1(1 - 0.05/10),
    n >= 100; PASA / CONTEXTO / RUIDO como en mapa_comun. Cada activo y cada ano, sin que cuenten.
Nada de la PRUEBA entra en las condiciones, los signos ni k: se calculan antes de abrirla.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapa_estudio as me  # noqa: E402
from mapa_comun import CALIENTE, ESQUEMAS, N_MIN, NOMBRE_ESQ  # noqa: E402
from zonas_historia import SIMBOLOS  # noqa: E402

FAMS = ("F2", "F3", "F4", "F5", "F6", "F7")
ESQ_AJ, Z_ENTRA, FRAC_K, M_JUICIO, N_AZAR, SEM_AZAR = "c", 2.0, 0.10, 10, 500, 20261103
Z = NormalDist().inv_cdf(1 - 0.05 / M_JUICIO)
rd = me.rd


def elegibles(a: me.Activo) -> dict[str, np.ndarray]:
    return {nom: b for nom, (f, b) in a.cond.items() if f in FAMS or nom.startswith("f1_3d_")}


def junta(juez: me.Juez, acts, js: dict, e: str, lado: str):
    """Los tres activos juntos con los mismos pesos por semana: (media, vector remuestreado, n)."""
    S, N, tot, n = np.zeros(juez.NW), np.zeros(juez.NW), 0.0, 0
    for a in acts:
        j, net = js[a.s], a.net[e, lado]
        wk = juez.wk[a.s][j]
        S += np.bincount(wk, net[j], minlength=juez.NW)
        N += np.bincount(wk, minlength=juez.NW)
        tot, n = tot + float(net[j].sum()), n + len(j)
    return (tot / n if n else np.nan), (juez.W @ S) / (juez.W @ N), n


def azar(juez, acts, e, lado, tramo, diaria, cache={}):  # noqa: B006
    key = (e, lado, tramo, diaria, me.CONTROL)
    if key not in cache:
        js = {a.s: np.flatnonzero(juez.per(a, e, lado, tramo) & (a.diaria if diaria else True)) for a in acts}
        cache[key] = junta(juez, acts, js, e, lado)
    return cache[key]


def en_tramo(juez, a, ops, e, lado, tramo):
    return ops[juez.per(a, e, lado, tramo)[ops]]


def paso2(acts, juez) -> dict:
    out = {}
    for nom, (fam, _) in acts[0].cond.items():  # el orden de mapa_estudio: fija la posicion de cada signo al azar
        if nom not in elegibles(acts[0]):
            continue
        tr = np.concatenate([np.flatnonzero(elegibles(a)[nom]) for a in acts])
        diaria = bool(len(tr)) and all(bool(a.diaria[np.flatnonzero(elegibles(a)[nom])].all()) for a in acts)
        r = {"familia": fam, "rejilla": "1d" if diaria else "4h"}
        db = {}
        for lado in me.LADOS:
            js = {a.s: en_tramo(juez, a, me.operaciones(a, np.flatnonzero(elegibles(a)[nom]), ESQ_AJ, lado),
                                ESQ_AJ, lado, "ajuste") for a in acts}
            mu, cb, n = junta(juez, acts, js, ESQ_AJ, lado)
            am, ab, _ = azar(juez, acts, ESQ_AJ, lado, "ajuste", diaria)
            r[f"n_{lado}"], r[f"dif_{lado}"] = n, rd(mu - am)
            db[lado] = cb - ab
        d = (r["dif_largo"] - r["dif_corto"]) / 2 if r["n_largo"] and r["n_corto"] else np.nan
        se = float(np.nanstd((db["largo"] - db["corto"]) / 2)) if np.isfinite(d) else np.nan
        r["dir"], r["se_dir"] = rd(d), rd(se)
        r["entra"] = bool(r["n_largo"] >= N_MIN and r["n_corto"] >= N_MIN and se > 0 and abs(d) / se >= Z_ENTRA)
        r["signo"] = int(np.sign(d)) if r["entra"] else 0
        out[nom] = r
    return out


def matrices(acts, nombres: list[str], diarias: list[bool]) -> dict[str, np.ndarray]:
    """Por activo, (J x condiciones) en int8: la condicion cierta en la decision, la diaria extendida 5 mas."""
    out = {}
    for a in acts:
        X = np.zeros((a.J, len(nombres)), np.int8)
        for i, (nom, dia) in enumerate(zip(nombres, diarias, strict=True)):
            b = elegibles(a)[nom].copy()
            if dia:
                b0 = b.copy()
                for t in range(1, 6):
                    b[t:] |= b0[:-t]
            X[:, i] = b
        out[a.s] = X
    return out


def puntua(acts, X: dict, signos: np.ndarray) -> dict[str, np.ndarray]:
    return {a.s: (X[a.s].astype(np.int32) @ signos.astype(np.int32)) if len(signos) else np.zeros(a.J, np.int32)
            for a in acts}


def umbral(acts, S: dict) -> tuple[int, float]:
    v = np.concatenate([np.abs(S[a.s][(a.Eabs < me.AJ_FIN) & (np.arange(a.J) >= CALIENTE * 6)]) for a in acts])
    k = 1
    while (v >= k).mean() > FRAC_K:
        k += 1
    return k, float((v >= k).mean())


def opera(acts, S, k, e, lado) -> dict[str, np.ndarray]:
    return {a.s: me.operaciones(a, np.flatnonzero(S[a.s] >= k if lado == "largo" else S[a.s] <= -k), e, lado)
            for a in acts}


def tabla(acts, juez, S, k) -> list[dict]:
    filas = []
    for e in ESQUEMAS:
        for lado in me.LADOS:
            ops = opera(acts, S, k, e, lado)
            f = {"esquema": e, "nombre": NOMBRE_ESQ[e], "lado": lado}
            for tramo in ("ajuste", "prueba"):
                js = {a.s: en_tramo(juez, a, ops[a.s], e, lado, tramo) for a in acts}
                mu, cb, n = junta(juez, acts, js, e, lado)
                am, ab, _ = azar(juez, acts, e, lado, tramo, False)
                aw = np.concatenate([a.net[e, lado][js[a.s]] for a in acts])
                f[tramo] = {"n": n, "neto": rd(mu), "se": rd(np.nanstd(cb)), "azar": rd(am), "dif": rd(mu - am),
                            "se_dif": rd(np.nanstd(cb - ab)), "acierto": rd((aw > 0).mean()) if n else None}
                if tramo == "prueba":
                    yr = np.concatenate([a.Eabs[js[a.s]] for a in acts]) // me.DIA
                    f["prueba"]["anos"] = {
                        str(y): [int(m.sum()), rd(aw[m].mean())] for y in (2024, 2025, 2026)
                        if (m := (yr >= me.minuto(f"{y}-01-01") // me.DIA)
                            & (yr < me.minuto(f"{y + 1}-01-01") // me.DIA)).any()}
                    f["prueba"]["activos"] = {a.s: juez.tramo(a, ops[a.s], e, lado, "prueba", False) for a in acts}
            p = f["prueba"]
            if p["n"] < N_MIN or p["se"] is None:
                f["veredicto"] = "sin medir"
            else:
                lb, lbd = p["neto"] - Z * p["se"], p["dif"] - Z * (p["se_dif"] or 0)
                f["cota_neto"], f["cota_dif"] = rd(lb), rd(lbd)
                f["veredicto"] = "PASA" if lb > 0 and lbd > 0 else ("CONTEXTO" if lbd > 0 else "RUIDO")
            filas.append(f)
    return filas


def netos_prueba(acts, juez, S, k) -> np.ndarray:
    out = np.full((len(ESQUEMAS), 2), np.nan)
    for i, e in enumerate(ESQUEMAS):
        for jl, lado in enumerate(me.LADOS):
            ops = opera(acts, S, k, e, lado)
            v = np.concatenate([a.net[e, lado][en_tramo(juez, a, ops[a.s], e, lado, "prueba")] for a in acts])
            if len(v):
                out[i, jl] = v.mean()
    return out


def mide(hist: Path):
    meta = json.loads((hist / "historia.json").read_text())
    acts = []
    for i, s in enumerate(SIMBOLOS):
        acts.append(me.Activo(hist, s, i, meta))
        me.log(f"{s} listo: {acts[-1].J} decisiones")
    juez = me.Juez(acts)
    p2 = paso2(acts, juez)
    ent = [n for n, r in p2.items() if r["entra"]]
    me.log(f"entran {len(ent)} de {len(p2)}: " + " ".join(f"{n}{'+' if p2[n]['signo'] > 0 else '-'}" for n in ent))
    X = matrices(acts, ent, [p2[n]["rejilla"] == "1d" for n in ent])
    sg = np.array([p2[n]["signo"] for n in ent])
    S = puntua(acts, X, sg)
    k, frac = umbral(acts, S)
    me.log(f"k = {k} (fraccion del ajuste con |S| >= k: {frac:.4f})")
    return meta, acts, juez, p2, ent, X, sg, S, k, frac


def resumen(filas) -> list[str]:
    out = []
    for f in filas:
        p = f["prueba"]
        out.append(f"{f['esquema']} {f['lado']:5} aj n={f['ajuste']['n']} neto={f['ajuste']['neto']} | pr n={p['n']} "
                   f"neto={p['neto']} se={p['se']} dif={p['dif']} se_dif={p['se_dif']} {f['veredicto']}")
    return out


def main(argv: list[str]) -> int:
    hist, outp = Path(argv[1]), Path(argv[2])
    meta, acts, juez, p2, ent, X, sg, S, k, frac = mide(hist)
    filas = tabla(acts, juez, S, k)
    for ln in resumen(filas):
        me.log(ln)
    if me.CONTROL:
        realp = Path(argv[3])
        real = json.loads(realp.read_text())
        fa = next(f for f in filas if f["esquema"] == "a" and f["lado"] == "largo")
        ra = next(f for f in real["tabla"] if f["esquema"] == "a" and f["lado"] == "largo")
        r = p2.get("rsi4h_bajo", {})
        mejora = None if fa["prueba"]["neto"] is None or ra["prueba"]["neto"] is None else \
            rd(fa["prueba"]["neto"] - ra["prueba"]["neto"])
        cp = {"empuje": os.environ.get("MAPA_EMPUJE"), "empuje_min": os.environ.get("MAPA_EMPUJE_MIN"),
              "rsi4h_bajo": {x: r.get(x) for x in ("entra", "signo", "dir", "se_dir", "n_largo", "n_corto")},
              "entran": {n: p2[n]["signo"] for n in ent}, "k": k,
              "a_largo_prueba_control": fa["prueba"], "a_largo_prueba_real": {x: ra["prueba"][x] for x in
                                                                               ("n", "neto", "dif", "acierto")},
              "mejora_neto": mejora, "veredicto_a_largo": fa["veredicto"]}
        cp["lo_ve"] = bool(r.get("entra") and r.get("signo") == 1 and mejora is not None and mejora > 0)
        real["control_positivo"] = cp
        realp.write_text(json.dumps(real, separators=(",", ":")) + "\n")
        me.log(f"CONTROL lo_ve={cp['lo_ve']} rsi4h_bajo={cp['rsi4h_bajo']} mejora_neto={mejora}")
        return 0
    real_net = netos_prueba(acts, juez, S, k)
    rng = np.random.default_rng(SEM_AZAR)
    azn, aks = np.full((N_AZAR, len(ESQUEMAS), 2), np.nan), []
    for r in range(N_AZAR if len(ent) else 0):
        sr = rng.choice(np.array([-1, 1]), size=len(ent))
        Sr = puntua(acts, X, sr)
        kr, _ = umbral(acts, Sr)
        aks.append(kr)
        azn[r] = netos_prueba(acts, juez, Sr, kr)
        if r % 50 == 0:
            me.log(f"  azar {r}")
    neg = {}
    for i, e in enumerate(ESQUEMAS):
        for jl, lado in enumerate(me.LADOS):
            v = azn[:, i, jl][np.isfinite(azn[:, i, jl])]
            neg[f"{e} {lado}"] = {"real": rd(real_net[i, jl]), "validos": int(len(v)),
                                  "percentil": rd(100 * (v < real_net[i, jl]).mean()) if len(v) else None,
                                  "p50": rd(np.median(v)) if len(v) else None,
                                  "p95": rd(np.percentile(v, 95)) if len(v) else None}
    dmeta = json.loads((hist / "datos.json").read_text())
    here = Path(__file__).parent
    huella = hashlib.sha256((meta["huella"] + json.dumps(dmeta, sort_keys=True) + Path(__file__).read_text()
                             + (here / "mapa_estudio.py").read_text() + (here / "mapa_comun.py").read_text())
                            .encode()).hexdigest()[:16]
    out = {"campana": "BOT-3d", "regla": "scripts/mapa_sesgo.py (docstring)", "huella": huella,
           "huella_historia": meta["huella"], "m": M_JUICIO, "z": round(Z, 4), "esquema_ajuste": ESQ_AJ,
           "condiciones": p2, "entran": {n: {"signo": p2[n]["signo"], "dir": p2[n]["dir"], "se_dir": p2[n]["se_dir"],
                                             "rejilla": p2[n]["rejilla"]} for n in ent},
           "k": k, "fraccion_ajuste_k": round(frac, 4), "tabla": filas,
           "control_negativo": {"vectores": N_AZAR if ent else 0, "semilla": SEM_AZAR,
                                "k_azar": {str(x): aks.count(x) for x in sorted(set(aks))}, "celdas": neg}}
    outp.write_text(json.dumps(out, separators=(",", ":")) + "\n")
    for c, v in neg.items():
        me.log(f"negativo {c}: {v}")
    me.log(f"FIN {outp} {outp.stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
