"""LOS DATOS NUEVOS del mapa de valor (campana BOT-3c), desde data.binance.vision, reproducible. Biblioteca estandar.

Junto a la historia de `zonas_historia.py` (perpetuo de 1 min desde t0, mismo DIR), por simbolo:
    <SIM>.spot.{c,qv,qb}.f64   spot 1 min (spot/monthly/klines/<SIM>/1m) en la MISMA rejilla que el perpetuo
                               (minuto t0 + i); NaN donde spot no publica
    <SIM>.prima.f64            cierre de 1 min del premiumIndexKlines (futures/um/monthly), misma rejilla, NaN fuera
    <SIM>.metrics.f64          rejilla de 5 min desde t0 (fila j = minuto t0 + 5 j), 6 columnas float64 por fila:
                               sum_open_interest, sum_open_interest_value, count_toptrader_long_short_ratio,
                               sum_toptrader_long_short_ratio, count_long_short_ratio, sum_taker_long_short_vol_ratio
                               (futures/um/daily/metrics); NaN donde no hay fila
y DIR/datos.json: el primer mes/dia publicado de cada fuente (se busca: 404 hasta encontrarlo), filas, y el sha256
de la concatenacion de los sha256 de los zips de cada fuente. Lo crudo no toca el disco.

USO (python3 a secas):  mapa_datos.py DIR
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import zipfile
from array import array
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from zonas_historia import SIMBOLOS, baja, filas, meses  # noqa: E402

BASE = "https://data.binance.vision/data"
SPOT = BASE + "/spot/monthly/klines/{s}/1m/{s}-1m-{m}.zip"
PRIMA = BASE + "/futures/um/monthly/premiumIndexKlines/{s}/1m/{s}-1m-{m}.zip"
METRICS = BASE + "/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
MCOLS = ("sum_open_interest", "sum_open_interest_value", "count_toptrader_long_short_ratio",
         "sum_toptrader_long_short_ratio", "count_long_short_ratio", "sum_taker_long_short_vol_ratio")
HASTA_MES, HASTA_DIA = "2026-09", date(2026, 10, 1)


def mensual(url: str, s: str, nom: str, cols: dict, t0: int, n: int, log) -> dict:
    out = {k: array("d", [float("nan")]) * n for k in cols}
    shas, primero, filas_ = [], None, 0
    for m in meses("2019-09", HASTA_MES):
        z = baja(url.format(s=s, m=m))
        if z is None:
            if primero is None:
                continue
            log(f"{s} {nom} {m} 404 tras el primero")
            continue
        primero = primero or m
        shas.append(hashlib.sha256(z).hexdigest())
        for f in filas(z):
            i = f[0] - t0
            if 0 <= i < n:
                filas_ += 1
                for k, j in cols.items():
                    out[k][i] = f[j]
    for k, a in out.items():
        with open(DIR / f"{s}.{k}.f64", "wb") as fh:
            a.tofile(fh)
    log(f"{s} {nom} desde {primero}: {filas_} minutos")
    return {"primer_mes": primero, "minutos": filas_, "zips": len(shas),
            "sha256_zips": hashlib.sha256("".join(shas).encode()).hexdigest()}


def _num(x: str) -> float:
    try:
        return float(x.strip('"'))
    except ValueError:
        return float("nan")  # celdas vacias ('""') en algunos dias


def metrics(s: str, t0: int, n: int, log) -> dict:
    n5 = n // 5
    out = array("d", [float("nan")]) * (n5 * 6)
    dias = []
    d = date(2020, 1, 1)
    while d < HASTA_DIA:
        dias.append(d.isoformat())
        d += timedelta(days=1)
    with ThreadPoolExecutor(12) as ex:
        zs = list(ex.map(lambda x: baja(METRICS.format(s=s, d=x)), dias))
    shas, primero, filas_ = [], None, 0
    for x, z in zip(dias, zs, strict=True):
        if z is None:
            continue
        primero = primero or x
        shas.append(hashlib.sha256(z).hexdigest())
        with zipfile.ZipFile(io.BytesIO(z)) as zf, zf.open(zf.namelist()[0]) as f:
            idx = None
            for linea in io.TextIOWrapper(f, encoding="ascii"):
                p = linea.strip().split(",")
                if idx is None and "create_time" in p:
                    idx = [p.index(c) for c in MCOLS]
                    continue
                if not p[0][:1].isdigit() or idx is None:
                    continue
                mm = int(datetime.fromisoformat(p[0]).replace(tzinfo=UTC).timestamp()) // 60
                j = (mm - t0) // 5
                if 0 <= j < n5 and (mm - t0) % 5 == 0:
                    filas_ += 1
                    for c, k in enumerate(idx):
                        out[j * 6 + c] = _num(p[k])
    with open(DIR / f"{s}.metrics.f64", "wb") as fh:
        out.tofile(fh)
    log(f"{s} metrics desde {primero}: {len([z for z in zs if z])} dias, {filas_} filas")
    return {"primer_dia": primero, "dias": len(shas), "filas": filas_,
            "sha256_zips": hashlib.sha256("".join(shas).encode()).hexdigest()}


def main(argv: list[str]) -> int:
    global DIR
    DIR = Path(argv[1])
    ini = time.time()

    def log(x: str) -> None:
        print(f"{time.time() - ini:7.0f}s {x}", flush=True)

    hist = json.loads((DIR / "historia.json").read_text())
    meta: dict = {"fuentes": {"spot": SPOT, "prima": PRIMA, "metrics": METRICS}, "simbolos": {}}
    for s in SIMBOLOS:
        t0, n = hist["simbolos"][s]["t0"], hist["simbolos"][s]["n"]
        meta["simbolos"][s] = {
            "metrics": metrics(s, t0, n, log),
            "prima": mensual(PRIMA, s, "prima", {"prima": 4}, t0, n, log),
            "spot": mensual(SPOT, s, "spot", {"spot.c": 4, "spot.qv": 5, "spot.qb": 6}, t0, n, log),
        }
        (DIR / "datos.json").write_text(json.dumps(meta, indent=1) + "\n")
    log("FIN")
    return 0


DIR = Path(".")
if __name__ == "__main__":
    sys.exit(main(sys.argv))
