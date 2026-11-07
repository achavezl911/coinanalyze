"""K119 · genera el banco y lo que el ESTUDIO dice de el. Se corre UNA vez, con numpy (venv aparte, fuera del repo):
    python harness/checks/K119-genera.py
Escribe, junto a este fichero:
  K119-sintetico.tsv.xz  las filas SINTETICAS de SOL (horas 00-03Z y 06-18Z del 2026-10-21), formato COPY de
                         orderflow_cinta (ts venue symbol precio base usd compra id). Las horas 04-05Z son la MUESTRA
                         real (/srv/coinanalyze/muestra-anatomia/cinta, solo SOL), citada por su sha256.
  K119-esperado.json     las operaciones que toma el estudio (anatomia_extrae.extrae + anatomia_estudio.carga/prepara
                         + condicion/etiquetas/sin_solape, como `confirma`) y las decisiones que cumplen sin etiqueta.
Los sucesos plantados (entregas/20261107-1618-bot-sombra-prediccion.md):
  F1 venta de contado de EXACTAMENTE 479834.70166359004 a las 01:10 (borde del umbral, <=) -> vence por la muestra
  F2 -300k 09:40 y -200k 10:39: solo la ventana de 60 los junta -> exito
  F5 -500k 12:40 -> sube y toca el stop; F6 la misma ventana, primera decision >= su salida -> exito
  F4 -500k 16:40 -> falta el minuto de binance_usdm de 18:20 en su camino: sin etiqueta (el bot: sin_dato)
  senuelos: -600k de perpetuo 06:10, 6 x 99999 de contado 07:20, -479834.70 de contado 08:30.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import lzma
import math
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
import anatomia_comun as C  # noqa: E402
import anatomia_estudio as E  # noqa: E402
import anatomia_extrae as X  # noqa: E402

from app import anatomia as A  # noqa: E402

DIA = "2026-10-21"
T0 = A._ts(DIA)
MUESTRA = Path("/srv/coinanalyze/muestra-anatomia/cinta") / DIA
HORAS_REALES = (4, 5)
CANDIDATAS = REPO / "config" / "anatomia" / "congeladas-20261103.json"


def hm(m):
    return T0 + m * 60


def tstxt(t, us=0):
    d = datetime.fromtimestamp(t, UTC)
    return d.strftime("%Y-%m-%d %H:%M:%S") + (f".{us:06d}".rstrip("0") if us else "") + "+00"


def real():
    filas = []
    for h in HORAS_REALES:
        with gzip.open(MUESTRA / f"orderflow_cinta-20261021T{h:02d}Z.tsv.gz", "rt", encoding="utf-8") as f:
            filas += [x for x in (ln.rstrip("\n").split("\t") for ln in f) if len(x) > 2 and x[2] == "SOL"]
    return filas


def sha_muestra():
    h = hashlib.sha256()
    for hh in HORAS_REALES:
        h.update((MUESTRA / f"orderflow_cinta-20261021T{hh:02d}Z.tsv.gz").read_bytes())
    return h.hexdigest()


def camino(p_ini, p_fin_real):
    """Cierre sintetico por minuto (00-03 y 06-18); None en las horas reales."""
    c = {}
    ola = lambda m, base: base * (1 + 0.0008 * math.sin(m / 7.0))  # noqa: E731
    for m in range(0, 240):
        c[m] = ola(m, p_ini)
    nivel = p_fin_real
    for m in range(360, 1140):
        if m < 640:                                   # hasta 10:40
            c[m] = ola(m, nivel)
        elif m < 670:                                 # F2: baja 1.2 % en 30 min
            c[m] = c[639] * (1 - 0.012 * (m - 639) / 30)
        elif m < 765:                                 # meseta hasta 12:45
            c[m] = c[669] * (1 + 0.0003 * math.sin(m / 7.0))
        elif m < 778:                                 # F5: sube 0.8 % en 13 min -> stop
            c[m] = c[764] * (1 + 0.008 * (m - 764) / 13)
        elif m < 800:                                 # meseta arriba hasta 13:20 (F6 entra en ella)
            c[m] = c[777] * (1 + 0.0003 * math.sin(m / 7.0))
        elif m < 830:                                 # F6: baja 1.2 % en 30 min -> objetivo
            c[m] = c[799] * (1 - 0.012 * (m - 799) / 30)
        else:
            c[m] = c[829] * (1 + 0.0008 * math.sin(m / 7.0))
    return c


def sinteticas(p_ini, p_fin_real):
    c = camino(p_ini, p_fin_real)
    filas, n = [], 0

    def fila(t, us, venue, precio, usd, compra):
        nonlocal n
        n += 1
        filas.append([tstxt(t, us), venue, "SOL", f"{precio:.4f}" if isinstance(precio, float) else precio,
                      f"{float(usd) / float(precio):.4f}", usd if isinstance(usd, str) else f"{usd:.4f}",
                      "t" if compra else "f", f"k119-{n:06d}"])

    for m in sorted(c):
        t = hm(m)
        o = c[m - 1] if m - 1 in c else c[m] * (1 - 0.0001)
        cl = c[m]
        hi, lo = max(o, cl) * 1.0002, min(o, cl) * 0.9998
        fila(t, 500000, "okx_spot", cl, 500.0, m % 2 == 0)            # hora presente aunque falte la referencia
        if m == 18 * 60 + 20:
            continue                                                    # F4: falta el minuto de precio
        for us, p in ((1000, o), (15000, hi), (30000, lo), (59000, cl)):
            fila(t, us, "binance_usdm", p, 2000.0, us % 2 == 0)
    sucesos = (
        (1 * 60 + 10, "binance_spot", "479834.70166359004"),           # F1, el borde exacto
        (6 * 60 + 10, "bybit_linear", "600000"),                         # senuelo: perpetuo
        *((7 * 60 + 20, "okx_spot", "99999") for _ in range(6)),         # senuelo: impresos de 99999
        (8 * 60 + 30, "binance_spot", "479834.70"),                      # senuelo: el umbral redondeado
        (9 * 60 + 40, "binance_spot", "300000"),                         # F2 (1)
        (10 * 60 + 39, "okx_spot", "200000"),                            # F2 (2)
        (12 * 60 + 40, "coinbase_spot", "500000"),                       # F5 / F6
        (16 * 60 + 40, "bybit_spot", "500000"),                          # F4
    )
    for k, (m, venue, usd) in enumerate(sucesos):
        fila(hm(m) + 30, 1000 * (k + 1), venue, f"{c[m]:.4f}", usd, False)
    return filas


def clave(x):
    s = x[0]
    t = A._ts(s[:19])
    frac = s[19:].split("+")[0]
    us = int((frac[1:] + "000000")[:6]) if frac else 0
    return (t * 1_000_000 + us, x[7].encode())


def main():
    reales = real()
    usdm = [x for x in reales if x[1] == "binance_usdm"]
    p_ini, p_fin = float(usdm[0][3]), float(usdm[-1][3])
    sint = sinteticas(p_ini, p_fin)
    todas = sorted(reales + sint, key=clave)
    with tempfile.TemporaryDirectory(prefix="k119g-") as tmp:
        arch, sal = Path(tmp) / "archivo", Path(tmp) / "salida"
        dd = arch / "cinta" / DIA
        dd.mkdir(parents=True)
        por_hora = {}
        for x in todas:
            por_hora.setdefault(int(x[0][11:13]), []).append(x)
        for h, xs in por_hora.items():
            with gzip.open(dd / f"orderflow_cinta-20261021T{h:02d}Z.tsv.gz", "wt", encoding="utf-8") as f:
                f.writelines("\t".join(x) + "\n" for x in xs)
        X.extrae(arch, sal, DIA, log=lambda *a: None)
        B, ts = E.carga(sal)
        D = E.prepara(B, ts)
    cand = json.loads(CANDIDATAS.read_text())["congeladas"]
    assert len(cand) == 1
    k = {**cand[0], "esquema": A.esquema_de(cand[0]["objetivo"], cand[0]["stop"])}
    d = D[k["simbolo"]]
    ex, ne, sa, va = d["lab"][(k["lado"], k["esquema"])]
    idx = d["capa"][k["capa"]] & (d["ts"] >= T0)
    x = d["V"][k["nombre"]]
    cumple = E.condicion(x, k["cola"], k["umbral"], bool(k["estricto"])) & (d["ts"] >= C.CAPA_B_DESDE)
    m = cumple & idx
    sel_i = np.flatnonzero(m & va)
    tom = C.sin_solape([(int(d["G"][i]), int(sa[i])) for i in sel_i])
    sel = sel_i[tom]
    n, exitos, neto = E.operaciones(m, ex, ne, sa, va, d["G"])
    ref = E.confirma(D, [k], T0)[0]["confirmacion"]
    assert (n, exitos, neto) == (ref["n"], ref["exitos"], ref["neto"]), (n, exitos, neto, ref)
    o = B[k["simbolo"]]["o"]
    ops = [{"minuto": int(d["ts"][i]), "hm": tstxt(int(d["ts"][i]))[11:16], "entrada": float(o[d["G"][i] + 1]),
            "exito": int(ex[i]), "neto": float(ne[i]), "salida": int(ts[sa[i]])} for i in sel]
    sin_etiqueta = [int(t) for t in d["ts"][cumple & ~idx]]
    xs = lzma.compress("".join("\t".join(x) + "\n" for x in sorted(sint, key=clave)).encode())
    (AQUI / "K119-sintetico.tsv.xz").write_bytes(xs)
    out = {"dia": DIA, "muestra": str(MUESTRA), "muestra_horas": list(HORAS_REALES), "muestra_sha256": sha_muestra(),
           "sintetico_sha256": hashlib.sha256(xs).hexdigest(), "filas_reales_sol": len(reales),
           "filas_sinteticas": len(sint), "candidata_sha256": hashlib.sha256(CANDIDATAS.read_bytes()).hexdigest(),
           "operaciones": ops, "sin_etiqueta": sin_etiqueta,
           "cumplen": [tstxt(int(t))[11:16] for t in d["ts"][cumple]],
           "confirma": {"n": n, "exitos": exitos, "neto": neto}}
    (AQUI / "K119-esperado.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("operaciones", "confirma", "filas_reales_sol", "filas_sinteticas")},
                     indent=1))
    print("sin_etiqueta", [tstxt(t)[11:16] for t in sin_etiqueta])
    print("cumplen", out["cumplen"])


if __name__ == "__main__":
    main()
