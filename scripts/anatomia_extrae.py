"""LA EXTRACCION de la anatomia (BOT-3e): reduce el archivo a una rejilla de 1 minuto por simbolo. Biblioteca
estandar, Python 3.13, lectura pura: corre en el NODO.

USO:  python3 anatomia_extrae.py ARCHIVO SALIDA [--desde AAAA-MM-DD]

ARCHIVO/<dir>/<AAAA-MM-DD>/<tabla>-<AAAAMMDD>T<HH>Z.tsv.gz (COPY de Postgres, TSV sin cabecera, nulo = \\N).
Escribe SALIDA/dias/<AAAA-MM-DD>.json + SALIDA/dias/<SIM>/<AAAA-MM-DD>.tsv.gz por dia y, al final,
SALIDA/base-<SIM>.tsv.gz (columnas COLUMNAS_BASE de anatomia_comun, con cabecera) y SALIDA/huecos.json.
REANUDABLE: un dia con su .json marcado completo no se rehace; uno incompleto (le faltaba alguna hora), si.
Memoria: un dia de acumuladores por minuto y, de la cinta, una linea cada vez (nunca el fichero entero).

Una hora que falta se cuenta en huecos.json y se deja vacia: nunca se rellena. Dentro de una hora presente, un
minuto sin filas es CERO para flujos y liquidaciones (la tabla publica lo que ocurre), y VACIO para precios y libro.
Las 5 min de coinalyze (liquidaciones, oi, funding...) sin fila en una hora presente: cero en liquidaciones (coinalyze
no publica cubos vacios; el latido que lo certifica no esta en el archivo: SUPUESTO), vacio en el resto.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from collections import deque
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import anatomia_comun as C  # noqa: E402

PERP, SPOT = frozenset(C.VENUES_PERP), frozenset(C.VENUES_SPOT)
NCOL = len(C.COLUMNAS_BASE)
COL = {n: i for i, n in enumerate(C.COLUMNAS_BASE)}


def epoch(ts: str) -> float:
    if ts.endswith("+00"):
        ts = ts[:-3]
        return datetime.fromisoformat(ts).replace(tzinfo=UTC).timestamp()
    return datetime.fromisoformat(ts).timestamp()


def base_de(simbolo: str):
    for s in C.SIMBOLOS:
        if simbolo.startswith(s):
            return s
    return None


def fichero(archivo: Path, d: str, dia: str, hora: int) -> Path:
    tabla = C.TABLAS[d][0]
    return archivo / d / dia / f"{tabla}-{dia.replace('-', '')}T{hora:02d}Z.tsv.gz"


def lineas(p: Path):
    with gzip.open(p, "rt", encoding="utf-8", newline="\n") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln:
                yield ln.split("\t")


def num(s):
    return None if s == "\\N" or s == "" else float(s)


def arr(s):
    """Array de Postgres {a,b,NULL} -> lista con None en los nulos."""
    if s == "\\N":
        return None
    s = s.strip("{}")
    return [None if x in ("NULL", "") else float(x) for x in s.split(",")] if s else []


class Dia:
    def __init__(self, archivo: Path, dia: str):
        self.archivo, self.dia = archivo, dia
        self.t0 = int(datetime.fromisoformat(dia).replace(tzinfo=UTC).timestamp())
        self.m = {s: [[None] * NCOL for _ in range(1440)] for s in C.SIMBOLOS}
        self.huecos: dict[str, list[str]] = {}
        self.ignorados: dict[str, list[str]] = {}
        self.fuera = 0
        self.oc = {}                 # (sim, minuto) -> [ts_o, ts_c]

    def minuto(self, ts: str):
        if ts.endswith("+00") and ts[:10] == self.dia:
            return int(ts[11:13]) * 60 + int(ts[14:16])
        m = int(epoch(ts) - self.t0) // 60
        if 0 <= m < 1440:
            return m
        self.fuera += 1
        return None

    def horas(self, d: str):
        """(hora, ruta) de las horas presentes; las que faltan van a huecos si el dir ya debia existir."""
        for h in range(24):
            p = fichero(self.archivo, d, self.dia, h)
            if p.exists():
                yield h, p
            elif d in C.ESPERADO_DESDE and self.dia >= C.ESPERADO_DESDE[d]:
                self.huecos.setdefault(d, []).append(f"{self.dia}T{h:02d}")

    def ceros(self, h: int, cols):
        for s in C.SIMBOLOS:
            for m in range(h * 60, h * 60 + 60):
                f = self.m[s][m]
                for c in cols:
                    if f[COL[c]] is None:
                        f[COL[c]] = 0.0

    # ---------------------------------------------------------------- cinta
    def cinta(self):
        io, ih, il, ic, ivr = COL["o"], COL["h"], COL["l"], COL["c"], COL["vol_ref"]
        flujo = ("vol_perp", "dp", "dp100k", "dp1m", "np", "vol_spot", "ds", "ds100k", "ds1m", "ns")
        for h, p in self.horas("cinta"):
            self.ceros(h, flujo + ("vol_ref",))
            for x in lineas(p):
                s = x[2]
                if s not in self.m:
                    continue
                m = self.minuto(x[0])
                if m is None:
                    continue
                f, v, usd, precio = self.m[s][m], x[1], float(x[5]), float(x[3])
                sg = usd if x[6] == "t" else -usd
                if v in PERP:
                    k = "p"
                elif v in SPOT:
                    k = "s"
                else:
                    continue
                f[COL["vol_" + ("perp" if k == "p" else "spot")]] += usd
                f[COL["d" + k]] += sg
                if usd >= C.GRANDE_100K:
                    f[COL["d" + k + "100k"]] += sg
                    if usd >= C.GRANDE_1M:
                        f[COL["d" + k + "1m"]] += sg
                f[COL["n" + k]] += 1
                im = COL["m" + k]
                if f[im] is None or usd > f[im]:
                    f[im] = usd
                if v == C.VENUE_REF:
                    f[ivr] += usd
                    f[COL["fuente"]] = C.FUENTE_CINTA
                    oc = self.oc.get((s, m))
                    if oc is None:
                        self.oc[(s, m)] = [x[0], x[0]]
                        f[io] = f[ih] = f[il] = f[ic] = precio
                    else:
                        if x[0] < oc[0]:
                            oc[0], f[io] = x[0], precio
                        if x[0] >= oc[1]:
                            oc[1], f[ic] = x[0], precio
                        if precio > f[ih]:
                            f[ih] = precio
                        if precio < f[il]:
                            f[il] = precio
                elif v == C.VENUE_PRIMA:
                    oc = self.oc.get((s, m, v))
                    if oc is None or x[0] >= oc:
                        self.oc[(s, m, v)] = x[0]
                        f[COL["c_cb"]] = precio
        self.oc.clear()

    # ---------------------------------------------------------------- precio de respaldo (solo capa A)
    def respaldo(self):
        for d, fuente in (("futuros-realtime", C.FUENTE_FUTUROS), ("libro-l1", C.FUENTE_L1)):
            vistos = {}
            for _h, p in self.horas(d):
                for x in lineas(p):
                    if x[2] != "binance":
                        continue
                    s = base_de(x[1])
                    m = self.minuto(x[0]) if s else None
                    if m is None:
                        continue
                    f = self.m[s][m]
                    if f[COL["fuente"]] not in (None, fuente):
                        continue
                    px = num(x[8]) if d == "futuros-realtime" else num(x[5])
                    if px is None:
                        continue
                    f[COL["fuente"]] = fuente
                    if d == "futuros-realtime":
                        f[COL["vol_ref"]] = (f[COL["vol_ref"]] or 0.0) + float(x[3]) + float(x[4])
                    k = (s, m)
                    if k not in vistos:
                        vistos[k] = [x[0], x[0]]
                        f[COL["o"]] = f[COL["h"]] = f[COL["l"]] = f[COL["c"]] = px
                        continue
                    oc = vistos[k]
                    if x[0] < oc[0]:
                        oc[0], f[COL["o"]] = x[0], px
                    if x[0] >= oc[1]:
                        oc[1], f[COL["c"]] = x[0], px
                    f[COL["h"]] = max(f[COL["h"]], px)
                    f[COL["l"]] = min(f[COL["l"]], px)

    # ---------------------------------------------------------------- liquidaciones al segundo
    def liq_rt(self):
        ev = []
        previo = (date.fromisoformat(self.dia) - timedelta(days=1)).isoformat()
        p = fichero(self.archivo, "liquidaciones-realtime", previo, 23)
        fuentes = [p] if p.exists() else []
        for h, q in self.horas("liquidaciones-realtime"):
            fuentes.append(q)
            self.ceros(h, ("liq_l", "liq_s", "liq_l_n", "liq_s_n"))
        for q in fuentes:
            for x in lineas(q):
                s = base_de(x[1])
                if s and x[3] in ("long", "short"):
                    ev.append((epoch(x[0]), s, x[3][0], float(x[4])))
        ev.sort()
        racha = {}
        for t, s, lado, usd in ev:
            dq = racha.setdefault((s, lado), deque())
            dq.append(t)
            while dq and dq[0] < t - C.CASCADA_S:
                dq.popleft()
            m = int(t - self.t0) // 60
            if not 0 <= m < 1440:
                continue
            f = self.m[s][m]
            f[COL[f"liq_{lado}"]] += usd
            f[COL[f"liq_{lado}_n"]] += 1
            f[COL[f"liq_{lado}_ult"]] = t
            f[COL[f"liq_{lado}_casc"]] = 1 if len(dq) >= C.CASCADA_N else 0
            if usd >= C.LIQ_GRANDE_USD[s]:
                f[COL[f"liq_{lado}_gr_ult"]] = t

    # ---------------------------------------------------------------- libro
    def libro(self):
        previo = {}                      # sim -> foto de binance_usdm del minuto anterior
        for _h, p in self.horas("libro"):
            ultima = {}
            for x in lineas(p):
                s = x[2]
                if s not in self.m:
                    continue
                m = self.minuto(x[0])
                if m is None:
                    continue
                k = (s, m, x[1])
                if k not in ultima or x[0] >= ultima[k][0]:
                    ultima[k] = x
            por_min = {}
            for (s, m, v), x in ultima.items():
                por_min.setdefault((s, m), {})[v] = foto(x)
            for (s, m) in sorted(por_min):
                fotos, f = por_min[(s, m)], self.m[s][m]
                b05 = a05 = 0.0
                for ft in fotos.values():
                    if ft is None:
                        continue
                    b, a = profundidad(ft, C.LIBRO_BANDAS[1])
                    b05 += b
                    a05 += a
                f[COL["deseq05_todos"]] = (b05 - a05) / (b05 + a05) if b05 + a05 > 0 else None
                r = fotos.get(C.VENUE_REF)
                if r is None:
                    previo.pop(s, None)
                    continue
                for col, banda in zip(("deseq01", "deseq05"), C.LIBRO_BANDAS, strict=True):
                    b, a = profundidad(r, banda)
                    f[COL[col]] = (b - a) / (b + a) if b + a > 0 else None
                f[COL["alc_c"]] = 1 - r["alc_c"] / r["medio"]
                f[COL["alc_v"]] = r["alc_v"] / r["medio"] - 1
                f[COL["mayor_med"]] = mayor_mediana(r)
                ant = previo.get(s)
                if ant is not None and ant["m"] == m - 1:
                    f[COL["muro_c"]], f[COL["muro_v"]] = muro(ant, r, f[COL["l"]], f[COL["h"]])
                r["m"] = m
                previo[s] = r

    # ---------------------------------------------------------------- 5 min de coinalyze
    def cinco(self):
        reglas = (("liquidaciones-5min", (("liq5_l", 3), ("liq5_s", 4)), True),
                  ("oi-bybit", (("oi", 6),), False), ("oi", (("oi_ag", 6),), False),
                  ("funding", (("fr", 6),), False), ("funding-previsto", (("pfr", 6),), False),
                  ("largos-cortos", (("ls", 5),), False))
        for d, cols, cero in reglas:
            elegido = {}
            for h, p in self.horas(d):
                if cero:
                    self.ceros(h, [c for c, _ in cols])
                for x in lineas(p):
                    s = base_de(x[1])
                    if s is None:
                        continue
                    if elegido.get(s) != x[1]:
                        if s not in elegido or (x[1].endswith("_PERP.A") and not elegido[s].endswith("_PERP.A")):
                            if s in elegido:
                                self.ignorados.setdefault(d, []).append(elegido[s])
                            elegido[s] = x[1]
                        else:
                            if x[1] not in self.ignorados.setdefault(d, []):
                                self.ignorados[d].append(x[1])
                            continue
                    m = self.minuto(x[0])
                    if m is None:
                        continue
                    m += 4 if x[2] == "5min" else 0
                    if m < 1440:
                        for c, i in cols:
                            self.m[s][m][COL[c]] = num(x[i])
        for _h, p in self.horas("spot-agregado"):
            for x in lineas(p):
                if x[2] != "combined" or x[1] not in self.m:
                    continue
                m = self.minuto(x[0])
                if m is None:
                    continue
                m += 4 if x[3] == "5min" else 0
                if m < 1440:
                    b, v = float(x[4]), float(x[5])
                    self.m[x[1]][m][COL["sa_delta"]] = b - v
                    self.m[x[1]][m][COL["sa_vol"]] = b + v

    def corre(self):
        self.cinta()
        self.respaldo()
        self.liq_rt()
        self.libro()
        self.cinco()
        for s in C.SIMBOLOS:
            for m, f in enumerate(self.m[s]):
                f[0] = self.t0 + 60 * m
                if f[COL["fuente"]] is None:
                    f[COL["fuente"]] = 0
        return self


def foto(x):
    try:
        compra, venta, paso = float(x[4]), float(x[5]), float(x[6])
        return {"medio": (compra + venta) / 2, "compra": compra, "venta": venta, "paso": paso,
                "cn": float(x[7]), "c": arr(x[8]) or [], "vn": float(x[9]), "v": arr(x[10]) or [],
                "alc_c": float(x[11]), "alc_v": float(x[12])}
    except (ValueError, IndexError):
        return None


def niveles(ft, lado):
    """(precio del nivel, cantidad o None) por nivel del lado."""
    if lado == "c":
        return [(ft["cn"] - i * ft["paso"], q) for i, q in enumerate(ft["c"])]
    return [(ft["vn"] + i * ft["paso"], q) for i, q in enumerate(ft["v"])]


def profundidad(ft, banda):
    b = sum(p * q for p, q in niveles(ft, "c") if q is not None and p >= ft["medio"] * (1 - banda))
    a = sum(p * q for p, q in niveles(ft, "v") if q is not None and p <= ft["medio"] * (1 + banda))
    return b, a


def mediana(xs):
    xs = sorted(xs)
    n = len(xs)
    return None if n == 0 else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


def mayor_mediana(ft):
    xs = [p * q for lado in ("c", "v") for p, q in niveles(ft, lado) if q is not None and q > 0]
    md = mediana(xs)
    return max(xs) / md if md else None


def muro(ant, act, low, high):
    """M3 y su espejo: (muro de compra quitado, muro de venta quitado), 1/0, de la foto `ant` (minuto m-1) a `act`
    (minuto m). low/high: minimo y maximo de binance_usdm en m (None: se usa el mejor precio de `act`)."""
    out = []
    for lado, tope in (("c", low), ("v", high)):
        qs = [q for _p, q in niveles(ant, lado) if q is not None and q > 0]
        md = mediana(qs)
        if md is None or act["paso"] != ant["paso"]:
            out.append(None)                               # sin libro previo, o cambio de paso: no se sabe
            continue
        idx = {round(p / act["paso"]): q for p, q in niveles(act, lado)}
        quitado = 0
        for p, q in niveles(ant, lado):
            if q is None or q < C.MURO_VECES * md:
                continue
            if lado == "c" and p < ant["medio"] * (1 - C.MURO_DIST):
                continue
            if lado == "v" and p > ant["medio"] * (1 + C.MURO_DIST):
                continue
            k = round(p / ant["paso"])
            if k not in idx or idx[k] is None:
                continue                                   # fuera de la foto nueva o nulo: no se sabe
            llega = (tope if tope is not None else act["compra"]) <= p + ant["paso"] if lado == "c" else \
                (tope if tope is not None else act["venta"]) >= p
            if idx[k] < C.MURO_QUEDA * q and not llega:
                quitado = 1
        out.append(quitado)
    return out[0], out[1]


def fmt(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return repr(v) if isinstance(v, float) else str(v)


def escribe_gz(ruta: Path, filas, cabecera=None):
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="\n") as f:
        if cabecera:
            f.write("\t".join(cabecera) + "\n")
        for fila in filas:
            f.write(fila if isinstance(fila, str) else "\t".join(fmt(v) for v in fila) + "\n")
    os.replace(tmp, ruta)


def dias_del_archivo(archivo: Path, desde: str):
    vistos = set()
    for d in C.TABLAS:
        if (archivo / d).is_dir():
            vistos.update(x.name for x in (archivo / d).iterdir() if x.is_dir() and len(x.name) == 10)
    vistos = sorted(v for v in vistos if v >= desde)
    if not vistos:
        return []
    a, b = date.fromisoformat(vistos[0]), date.fromisoformat(vistos[-1])
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def extrae(archivo: Path, salida: Path, desde: str = C.ARCHIVO_DESDE, log=print):
    desde = max(desde, C.ARCHIVO_DESDE)
    (salida / "dias").mkdir(parents=True, exist_ok=True)
    for s in C.SIMBOLOS:
        (salida / "dias" / s).mkdir(exist_ok=True)
    dias = dias_del_archivo(archivo, desde)
    for dia in dias:
        meta = salida / "dias" / f"{dia}.json"
        if meta.exists() and json.loads(meta.read_text())["completo"]:
            continue
        d = Dia(archivo, dia).corre()
        for s in C.SIMBOLOS:
            escribe_gz(salida / "dias" / s / f"{dia}.tsv.gz", d.m[s])
        sin = {s: sum(1 for f in d.m[s] if f[COL["fuente"]] == 0) for s in C.SIMBOLOS}
        sin_cinta = {s: sum(1 for f in d.m[s] if f[COL["fuente"]] != C.FUENTE_CINTA) for s in C.SIMBOLOS} \
            if dia >= C.CINTA_DESDE else {s: 0 for s in C.SIMBOLOS}
        tmp = meta.with_suffix(".tmp")
        tmp.write_text(json.dumps({"dia": dia, "completo": not d.huecos, "horas_faltantes": d.huecos,
                                   "minutos_sin_precio": sin, "minutos_sin_precio_cinta": sin_cinta,
                                   "simbolos_ignorados": d.ignorados, "filas_fuera_de_dia": d.fuera}))
        os.replace(tmp, meta)
        log(f"{dia} hecho, horas faltantes: {sum(len(v) for v in d.huecos.values())}")
    huecos = {"dias": dias, "horas_faltantes": {}, "minutos_sin_precio": {s: 0 for s in C.SIMBOLOS},
              "minutos_sin_precio_cinta": {s: 0 for s in C.SIMBOLOS}, "simbolos_ignorados": {},
              "filas_fuera_de_dia": 0}
    for dia in dias:
        mt = json.loads((salida / "dias" / f"{dia}.json").read_text())
        for k, v in mt["horas_faltantes"].items():
            huecos["horas_faltantes"].setdefault(k, []).extend(v)
        for k in ("minutos_sin_precio", "minutos_sin_precio_cinta"):
            for s in C.SIMBOLOS:
                huecos[k][s] += mt[k][s]
        for k, v in mt["simbolos_ignorados"].items():
            ig = huecos["simbolos_ignorados"].setdefault(k, [])
            ig.extend(x for x in v if x not in ig)
        huecos["filas_fuera_de_dia"] += mt["filas_fuera_de_dia"]
    huecos["horas_faltantes_n"] = {k: len(v) for k, v in huecos["horas_faltantes"].items()}
    for s in C.SIMBOLOS:
        def filas(s=s):
            for dia in dias:
                with gzip.open(salida / "dias" / s / f"{dia}.tsv.gz", "rt", encoding="utf-8") as f:
                    yield from f
        escribe_gz(salida / f"base-{s}.tsv.gz", filas(), C.COLUMNAS_BASE)
    (salida / "huecos.json").write_text(json.dumps(huecos, indent=1))
    return huecos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("archivo", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--desde", default=C.ARCHIVO_DESDE)
    a = ap.parse_args(argv)
    h = extrae(a.archivo, a.salida, a.desde)
    print(f"{len(h['dias'])} dias; horas faltantes por dir: {h['horas_faltantes_n']}")


if __name__ == "__main__":
    main()
