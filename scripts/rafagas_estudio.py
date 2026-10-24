"""El estudio de las RAFAGAS (campana BOT-1): la muestra y las tablas, reproducibles.

LA MUESTRA (``muestra``): barras de 1 min de los perpetuos USD-M de Binance (BTCUSDT, ETHUSDT, SOLUSDT) hechas EN
FLUJO desde las operaciones agregadas publicas (data.binance.vision, aggTrades): se baja UN zip (el mayor, ETH de un
mes, ~0.5 GB), se lee sin descomprimir a disco, se agrega y se borra antes del siguiente. Por minuto se guarda::

    m       minuto (epoch // 60)
    c       ultimo precio del minuto
    p35     ultimo precio con hora <= segundo 35 del minuto (la ENTRADA a +35 s de una alerta en el cierre anterior)
    ha la   maximo y minimo en [0, 35 s]          hb lb   maximo y minimo en (35 s, 60 s)
    buy     USD comprados por el agresor (is_buyer_maker = false)       sell    USD vendidos por el agresor
    n       operaciones agregadas

Los precios van como los escribe Binance (texto) y los USD redondeados al entero: misma entrada, mismos bytes.
Un minuto sin operaciones no se escribe (``carga`` lo rellena con el ultimo precio y volumen 0). Hueco o mitad sin
operaciones: ha/la o hb/lb vacios.

Las liquidaciones (Coinalyze, bloques de 5 min, solo en 140 y con 90 dias de retencion) van en ``liq.tsv`` (epoch
del inicio del bloque, simbolo, USD de largos, USD de cortos), sacadas con::

    TODO=1 sh harness/bin/prodsql "SELECT extract(epoch FROM ts)::bigint, split_part(symbol,'_',1), long_liq,
        short_liq FROM liquidations WHERE interval='5min' AND ts >= '<desde>' AND ts < '<hasta>' ORDER BY 1, 2"

USO:  python scripts/rafagas_estudio.py muestra DIR 2026-03 2026-09 [2026-10-01 2026-10-23]
          meses enteros (zip mensual) y, opcionalmente, dias sueltos (zip diario) de un mes aun sin publicar
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import lzma
import math
import random
import statistics
import subprocess
import sys
import zipfile
from array import array
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app.rafagas as rf  # noqa: E402

SIMBOLOS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
URL = "https://data.binance.vision/data/futures/um/{per}/aggTrades/{s}/{s}-aggTrades-{f}.zip"


def agrega(zpath: Path) -> dict[int, list]:
    """Un zip de aggTrades -> {minuto: [c, p35, ha, la, hb, lb, buy, sell, n]} (precios en texto)."""
    out: dict[int, list] = {}
    with zipfile.ZipFile(zpath) as z:
        f = io.TextIOWrapper(z.open(z.namelist()[0]), encoding="ascii", newline="")
        for row in csv.reader(f):
            if not row[0].isdigit():  # cabecera
                continue
            ps, p, q, t = row[1], float(row[1]), float(row[2]), int(row[5])
            m, ms = divmod(t, 60000)
            b = out.get(m)
            if b is None:
                b = out[m] = [ps, None, None, None, None, None, 0.0, 0.0, 0]
            b[0] = ps
            if ms <= 35000:
                b[1] = ps
                if b[2] is None or p > float(b[2]):
                    b[2] = ps
                if b[3] is None or p < float(b[3]):
                    b[3] = ps
            else:
                if b[4] is None or p > float(b[4]):
                    b[4] = ps
                if b[5] is None or p < float(b[5]):
                    b[5] = ps
            if row[6] == "true":
                b[7] += p * q
            else:
                b[6] += p * q
            b[8] += 1
    return out


def _ficheros(desde_mes: str, hasta_mes: str, dias: tuple[str, str] | None):
    y, mo = map(int, desde_mes.split("-"))
    while f"{y:04d}-{mo:02d}" <= hasta_mes:
        yield "monthly", f"{y:04d}-{mo:02d}"
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    if dias:
        d, fin = date.fromisoformat(dias[0]), date.fromisoformat(dias[1])
        while d <= fin:
            yield "daily", d.isoformat()
            d += timedelta(days=1)


def muestra(dir_: Path, desde_mes: str, hasta_mes: str, dias: tuple[str, str] | None) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    tmp = dir_ / "baja.zip"
    for s in SIMBOLOS:
        filas: dict[int, list] = {}
        for per, f in _ficheros(desde_mes, hasta_mes, dias):
            url = URL.format(per=per, s=s, f=f)
            subprocess.run(["curl", "-sf", "--max-time", "1800", "-o", str(tmp), url], check=True)
            tam = tmp.stat().st_size
            filas.update(agrega(tmp))
            tmp.unlink()
            print(f"{s} {f} {tam} B -> {len(filas)} minutos", flush=True)
        with lzma.open(dir_ / f"{s}.tsv.xz", "wt", encoding="ascii", newline="\n") as w:
            for m in sorted(filas):
                c, p35, ha, la, hb, lb, buy, sell, n = filas[m]
                w.write(f"{m}\t{c}\t{p35 or ''}\t{ha or ''}\t{la or ''}\t{hb or ''}\t{lb or ''}"
                        f"\t{round(buy)}\t{round(sell)}\t{n}\n")
        del filas


# ------------------------------------------------------------------------------------------------ la carga

DIA = 1440
FEE = 0.0011  # taker 5.5 bps por lado, ida y vuelta (los 0.55 USD sobre 500 de base_azar.py)
# esquema: (objetivo, stop, sentido respecto a la rafaga)
ESQUEMAS = {"a": (0.02, 0.006, 1), "b": (0.012, 0.006, 1), "c": (0.012, 0.006, -1)}
EQUILIBRIO = {k: (sl + FEE) / (tp + sl) for k, (tp, sl, _) in ESQUEMAS.items()}
HORIZONTES = (1, 5, 15, 60)
AJUSTE = ("2026-03-01", "2026-08-31", "2026-09-01")  # detecciones [desde, hasta), el camino se corta en el tercero
AJUSTE_LIQ = "2026-07-27"
PRUEBA = ("2026-09-01", "2026-10-22")  # el camino llega al final de los datos
QUITADO = "2026-10-20"  # el dia de los dos controles: fuera de la prueba
CONTROLES = (("CASCADA", 1, "2026-10-20T13:55", "2026-10-20T14:20"),
             ("BARRIDO", -1, "2026-10-20T15:10", "2026-10-20T15:16"))
REJILLA = {"W": (2, 3, 5), "Z": (4.0, 5.0, 6.0, 7.0), "M": (2.0, 3.0, 5.0), "D": (0.10, 0.25), "G": (0.3, 0.5)}
MIN_POR_CLASE = 15
BARAJAS, SEMILLA = 200, 20261024


def minuto(iso: str) -> int:
    return int(datetime.fromisoformat(iso + ("" if "T" in iso else "T00:00") + "+00:00").timestamp()) // 60


def iso(m: int) -> str:
    return datetime.fromtimestamp(m * 60, UTC).strftime("%Y-%m-%dT%H:%MZ")


@dataclass
class Muestra:
    t0: int
    series: dict[str, rf.Serie]
    p35: dict[str, list[float]]
    ha: dict[str, list[float]]
    la: dict[str, list[float]]
    hb: dict[str, list[float]]
    lb: dict[str, list[float]]
    liq: dict[str, dict[int, tuple[float, float]]]
    huella: str

    def i(self, m: int) -> int:
        return m - self.t0


def _lineas(ruta: Path):
    """(etiqueta, campos) de una muestra: un directorio de `muestra` o un fichero de `recorta`."""
    if ruta.is_dir():
        for s in SIMBOLOS:
            with lzma.open(ruta / f"{s}.tsv.xz", "rt", encoding="ascii") as f:
                for ln in f:
                    yield s, ln.rstrip("\n").split("\t")
        with open(ruta / "liq.tsv", encoding="ascii") as f:
            for ln in f:
                yield "L", ln.rstrip("\n").split("\t")
    else:
        with lzma.open(ruta, "rt", encoding="ascii") as f:
            for ln in f:
                et, _, resto = ln.rstrip("\n").partition("\t")
                yield et, resto.split("\t")


def huella(ruta: Path) -> str:
    h = hashlib.sha256()
    for f in ([ruta / f"{s}.tsv.xz" for s in SIMBOLOS] + [ruta / "liq.tsv"]) if ruta.is_dir() else [ruta]:
        h.update(f.read_bytes())
    return h.hexdigest()


def carga(ruta: Path) -> Muestra:
    """Las barras de cada activo, contiguas (un minuto sin operaciones: el ultimo precio y volumen 0) y recortadas
    al tramo comun. Las lineas de un activo vienen ordenadas por minuto: se rellena al leer, sin diccionario."""
    liq: dict[str, dict[int, tuple[float, float]]] = {s: {} for s in SIMBOLOS}
    col: dict[str, tuple[int, list[array]]] = {}
    for et, x in _lineas(ruta):
        if et == "L":
            liq[x[1]][int(x[0])] = (float(x[2]), float(x[3]))
            continue
        m = int(x[0])
        if et not in col:
            col[et] = (m, [array("d") for _ in range(10)])
        m0, (c, hi, lo, buy, sell, p35, ha, la, hb, lb) = col[et]
        prev = c[-1] if c else float(x[1])
        while m0 + len(c) < m:  # minutos sin operaciones
            for a in (c, hi, lo, p35, ha, la, hb, lb):
                a.append(prev)
            buy.append(0.0), sell.append(0.0)
        cc = float(x[1])
        pp = float(x[2]) if x[2] else prev
        a1, a2 = (float(x[3]), float(x[4])) if x[3] else (pp, pp)
        b1, b2 = (float(x[5]), float(x[6])) if x[5] else (cc, cc)
        for a, y in ((c, cc), (hi, max(a1, b1)), (lo, min(a2, b2)), (p35, pp), (ha, a1), (la, a2), (hb, b1),
                     (lb, b2), (buy, float(x[7])), (sell, float(x[8]))):
            a.append(y)
    t0 = max(m0 for m0, _ in col.values())
    t1 = min(m0 + len(a[0]) for m0, a in col.values())
    mu = Muestra(t0, {}, {}, {}, {}, {}, {}, liq, huella(ruta))
    for s in SIMBOLOS:
        m0, arr = col.pop(s)
        c, hi, lo, buy, sell, p35, ha, la, hb, lb = (a[t0 - m0:t1 - m0] for a in arr)
        mu.series[s] = rf.Serie(t0, c, hi, lo, buy, sell)
        mu.p35[s], mu.ha[s], mu.la[s], mu.hb[s], mu.lb[s] = p35, ha, la, hb, lb
    return mu


def recorta(dir_: Path, salida: Path, desde: str, hasta: str) -> None:
    """La muestra de K116: barras con minuto en [desde, hasta) y bloques de liquidaciones con inicio ahi."""
    a, b = minuto(desde), minuto(hasta)
    with lzma.open(salida, "wt", encoding="ascii", newline="\n") as w:
        for et, x in _lineas(dir_):
            m = int(x[0]) // 60 if et == "L" else int(x[0])
            if a <= m < b:
                w.write(et + "\t" + "\t".join(x) + "\n")


# ------------------------------------------------------------------------------------------------ la medida

def resultado(mu: Muestra, s: str, e: int, d: int, tp: float, sl: float, fin: int) -> tuple[str, float]:
    """Entrada al precio del segundo 35 de la barra e, sentido d. ('TP'|'SL'|'VENCE', neto). Medio minuto que
    toca los dos: stop. Sin tocar ninguno en 24 h (o al cortarse el camino en fin): el precio de salida."""
    P = mu.p35[s][e]
    ha, la, hb, lb = mu.ha[s], mu.la[s], mu.hb[s], mu.lb[s]
    ult = min(e + DIA, fin - 1)
    if d > 0:
        obj, stp = P * (1 + tp), P * (1 - sl)
        for k in range(e, ult + 1):
            if k > e:
                if la[k] <= stp:
                    return "SL", -sl - FEE
                if ha[k] >= obj:
                    return "TP", tp - FEE
            if k < e + DIA:
                if lb[k] <= stp:
                    return "SL", -sl - FEE
                if hb[k] >= obj:
                    return "TP", tp - FEE
    else:
        obj, stp = P * (1 - tp), P * (1 + sl)
        for k in range(e, ult + 1):
            if k > e:
                if ha[k] >= stp:
                    return "SL", -sl - FEE
                if la[k] <= obj:
                    return "TP", tp - FEE
            if k < e + DIA:
                if hb[k] >= stp:
                    return "SL", -sl - FEE
                if lb[k] <= obj:
                    return "TP", tp - FEE
    salida = mu.p35[s][e + DIA] if e + DIA <= ult else mu.series[s].c[ult]
    return "VENCE", d * (salida / P - 1) - FEE


def recorrido(mu: Muestra, s: str, e: int, sentido: int, h: int, fin: int) -> tuple[float, float] | None:
    """(MFE, MAE) en % de [entrada, entrada + h min], en el sentido de la rafaga."""
    if e + h >= fin:
        return None
    se = mu.series[s]
    mx = max(mu.hb[s][e], mu.ha[s][e + h], *se.hi[e + 1:e + h])
    mn = min(mu.lb[s][e], mu.la[s][e + h], *se.lo[e + 1:e + h])
    P = mu.p35[s][e]
    a, b = (mx / P - 1, 1 - mn / P) if sentido > 0 else (1 - mn / P, mx / P - 1)
    return max(a, 0.0) * 100, max(b, 0.0) * 100


@dataclass(frozen=True)
class Evento:
    s: str
    i: int  # barra de deteccion
    sg: int  # sentido de la rafaga
    clase: str
    m: int  # minutos hasta decidir la clase
    e: int  # barra de entrada (cierre de decision + 35 s)


def eventos(mu: Muestra, u: rf.Umbrales, rz: dict, dets: dict, con_liq: bool) -> list[Evento]:
    """Las rafagas ya detectadas ({activo: [(i, s)]}) con su clase; rz: {activo: rasgos con u.W}."""
    out = []
    for s in SIMBOLOS:
        otras = [rz[o][0] for o in SIMBOLOS if o != s]
        for i, sg in dets[s]:
            cl = rf.clasifica(mu.series[s], i, sg, u, otras, mu.liq[s] if con_liq else None)
            if cl is not None:
                out.append(Evento(s, i, sg, cl[0], cl[1], i + cl[1] + 1))
    return out


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    z = 1.959964
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (c - r, c + r)


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


# ------------------------------------------------------------------------------------------------ el ajuste

def ajuste(mu: Muestra) -> dict:
    a, b, fin = (mu.i(minuto(x)) for x in AJUSTE)
    cache: dict = {}

    def neto(ev: Evento, esq: str) -> float:
        tp, sl, sen = ESQUEMAS[esq]
        k = (ev.s, ev.e, ev.sg * sen, esq)
        if k not in cache:
            cache[k] = resultado(mu, ev.s, ev.e, ev.sg * sen, tp, sl, fin)[1]
        return cache[k]

    filas = []
    for W in REJILLA["W"]:
        rz = {s: rf.rasgos(mu.series[s], W) for s in SIMBOLOS}
        for Z in REJILLA["Z"]:
            for M in REJILLA["M"]:
                for D in REJILLA["D"]:
                    dets = {s: rf.detecta_rasgos(*rz[s], Z, M, D, 60, a, b) for s in SIMBOLOS}
                    for G in REJILLA["G"]:
                        u = rf.Umbrales(W=W, Z=Z, M=M, D=D, G=G)
                        evs = eventos(mu, u, rz, dets, False)
                        pol = [neto(ev, "a") for ev in evs if ev.clase == rf.CASCADA]
                        nc = len(pol)
                        pol += [neto(ev, "c") for ev in evs if ev.clase == rf.BARRIDO]
                        filas.append({"W": W, "Z": Z, "M": M, "D": D, "G": G, "rafagas": len(evs),
                                      "cascadas": nc, "barridos": len(pol) - nc,
                                      "neto_medio_pct": round(100 * sum(pol) / len(pol), 4) if pol else None})
    validas = [f for f in filas if f["cascadas"] >= MIN_POR_CLASE and f["barridos"] >= MIN_POR_CLASE]
    elegido = max(validas, key=lambda f: (f["neto_medio_pct"], f["cascadas"] + f["barridos"]))
    return {"huella": mu.huella, "periodo": AJUSTE, "puntos": len(filas), "validos": len(validas),
            "elegido": elegido, "rejilla": filas}


# ------------------------------------------------------------------------------------------------ la prueba

def prueba(mu: Muestra, u: rf.Umbrales = rf.UMBRALES) -> dict:
    a, b = mu.i(minuto(PRUEBA[0])), mu.i(minuto(PRUEBA[1]))
    fin = len(mu.series[SIMBOLOS[0]].c)
    q0 = mu.i(minuto(QUITADO))
    fuera = range(q0, q0 + DIA)
    dias = [d for d in range(a, b, DIA) if d not in fuera]
    rz = {s: rf.rasgos(mu.series[s], u.W, u.BASE) for s in SIMBOLOS}
    dets = {s: rf.detecta_rasgos(*rz[s], u.Z, u.M, u.D, u.CALLA, a, b) for s in SIMBOLOS}
    out: dict = {"huella": mu.huella, "umbrales": asdict(u), "prueba": PRUEBA, "quitado": QUITADO,
                 "dias": len(dias), "equilibrio": {k: round(v, 4) for k, v in EQUILIBRIO.items()}}
    for variante, con_liq in (("sin_liq", False), ("con_liq", True)):
        todos = eventos(mu, u, rz, dets, con_liq)
        evs = [ev for ev in todos if ev.i not in fuera]
        ctrl = [ev for ev in todos if ev.i in fuera]
        out[variante] = {"eventos": [[ev.s, iso(mu.t0 + ev.i), ev.sg, ev.clase, ev.m, iso(mu.t0 + ev.e)]
                                     for ev in evs],
                         "tablas": _tablas(mu, evs, fin, dias),
                         "control": _control(mu, ctrl)}
    return out


def _tablas(mu: Muestra, evs: list[Evento], fin: int, dias: list[int]) -> dict:
    cache: dict = {}

    def res(s: str, e: int, d: int, esq: str) -> tuple[str, float]:
        k = (s, e, d, esq)
        if k not in cache:
            tp, sl, _ = ESQUEMAS[esq]
            cache[k] = resultado(mu, s, e, d, tp, sl, fin)
        return cache[k]

    # el azar: cada evento conserva activo, sentido y minuto del dia de su entrada; se sortea el dia
    rnd = random.Random(SEMILLA)
    azar = {ev: [dias[rnd.randrange(len(dias))] + (ev.e - dias[0]) % DIA for _ in range(BARAJAS)] for ev in evs}
    tablas: dict = {}
    for clase in (rf.CASCADA, rf.BARRIDO, rf.SIN_CLASE):
        tablas[clase] = {}
        for activo in SIMBOLOS + ("TODOS",):
            sel = [ev for ev in evs if ev.clase == clase and activo in ("TODOS", ev.s)]
            fila: dict = {"n": len(sel)}
            for h in HORIZONTES:
                rr = [r for r in (recorrido(mu, ev.s, ev.e, ev.sg, h, fin) for ev in sel) if r]
                fila[f"mfe_mae_{h}m"] = ([round(statistics.median([r[0] for r in rr]), 4),
                                          round(statistics.median([r[1] for r in rr]), 4),
                                          round(statistics.fmean([r[0] for r in rr]), 4),
                                          round(statistics.fmean([r[1] for r in rr]), 4)] if rr else None)
            for esq, (_, _, sen) in ESQUEMAS.items():
                if esq == "c" and clase != rf.BARRIDO:
                    continue
                rs = [res(ev.s, ev.e, ev.sg * sen, esq) for ev in sel]
                k = sum(1 for r in rs if r[0] == "TP")
                tasas = []
                for j in range(BARAJAS):
                    tz = [res(ev.s, azar[ev][j], ev.sg * sen, esq)[0] == "TP" for ev in sel]
                    tasas.append(sum(tz) / len(tz) if tz else 0.0)
                lo, hi = wilson(k, len(sel))
                tasa = k / len(sel) if sel else None
                fila[esq] = {"aciertos": k, "stops": sum(1 for r in rs if r[0] == "SL"),
                             "vencen": sum(1 for r in rs if r[0] == "VENCE"),
                             "tasa": round(tasa, 4) if sel else None,
                             "wilson95": [round(lo, 4), round(hi, 4)],
                             "neto_medio_pct": round(100 * statistics.fmean([r[1] for r in rs]), 4) if rs else None,
                             "azar": ([round(statistics.fmean(tasas), 4), round(_pct(tasas, 0.025), 4),
                                       round(_pct(tasas, 0.975), 4)] if sel else None),
                             "ventaja": _veredicto(len(sel), lo, tasa, _pct(tasas, 0.975) if sel else None,
                                                   EQUILIBRIO[esq])}
            tablas[clase][activo] = fila
    return tablas


def _veredicto(n: int, lo: float, tasa: float | None, azar975: float | None, eq: float) -> str:
    if n < 20:
        return "n insuficiente"
    return "VENTAJA MEDIDA" if lo > eq and tasa > azar975 else "sin ventaja medida"


def _control(mu: Muestra, ctrl: list[Evento]) -> list[dict]:
    out = []
    for clase, sg, desde, hasta in CONTROLES:
        a, b = mu.i(minuto(desde)), mu.i(minuto(hasta))
        dentro = [ev for ev in ctrl if a <= ev.i <= b]
        ok = (any(ev.clase == clase and ev.sg == sg for ev in dentro)
              and not any(ev.clase in (rf.CASCADA, rf.BARRIDO) and ev.clase != clase for ev in dentro))
        out.append({"control": clase, "franja": [desde, hasta], "visto": ok,
                    "eventos": [[ev.s, iso(mu.t0 + ev.i), ev.sg, ev.clase, ev.m] for ev in dentro]})
    return out


def _json(x: dict) -> str:
    return json.dumps(x, ensure_ascii=True, sort_keys=True, indent=1) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) >= 4 and argv[0] == "muestra":
        muestra(Path(argv[1]), argv[2], argv[3], (argv[4], argv[5]) if len(argv) >= 6 else None)
        return 0
    if len(argv) == 5 and argv[0] == "recorta":
        recorta(Path(argv[1]), Path(argv[2]), argv[3], argv[4])
        return 0
    if len(argv) == 3 and argv[0] in ("ajuste", "prueba"):
        r = (ajuste if argv[0] == "ajuste" else prueba)(carga(Path(argv[1])))
        Path(argv[2]).write_text(_json(r), encoding="ascii")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
