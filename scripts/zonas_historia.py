"""La HISTORIA de las zonas (campana BOT-3a): velas de 1 min de los perpetuos USD-M de Binance, reproducible.

DE DONDE. Las klines MENSUALES publicas de data.binance.vision (futures/um/monthly/klines/<SIM>/1m), que traen el
volumen del agresor comprador: no hace falta aggTrades para ninguna clase medida. Cada zip se baja a memoria, se
comprueba contra su .CHECKSUM (sha256 publicado por Binance), se agrega y se suelta: lo crudo no toca el disco.

QUE QUEDA, por simbolo, en DIR: seis columnas float64 little-endian contiguas por minuto desde t0 (epoch // 60)::
    <SIM>.o.f64  .h  .l  .c     precios de la vela
    <SIM>.qv.f64                USD negociados (quote_volume)
    <SIM>.qb.f64                USD del agresor comprador (taker_buy_quote_volume)
y DIR/historia.json con t0, n, primer y ultimo mes, el sha256 de cada zip, los minutos rellenados y la HUELLA
(sha256 de los bytes de todas las columnas y de t0/n). Un minuto que falta se rellena con el ultimo cierre y
volumen 0, como en BOT-1. Leer con numpy.memmap o con array('d').

USO (python3 a secas):  zonas_historia.py DIR 2019-09 2026-10
    busca el primer mes publicado de cada simbolo desde el primero dado (404 hasta encontrarlo) y llega al ultimo
    que exista hasta el segundo dado.
                        zonas_historia.py DIR 2019-09 2026-10 funding
    la tasa de financiacion liquidada (fundingRate mensual): un contexto con historia larga.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from array import array
from pathlib import Path

SIMBOLOS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
URL = "https://data.binance.vision/data/futures/um/monthly/klines/{s}/1m/{s}-1m-{m}.zip"
COLS = ("o", "h", "l", "c", "qv", "qb")


def meses(desde: str, hasta: str) -> list[str]:
    y, mo = map(int, desde.split("-"))
    out = []
    while f"{y:04d}-{mo:02d}" <= hasta:
        out.append(f"{y:04d}-{mo:02d}")
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return out


def baja(url: str, intentos: int = 8) -> bytes | None:
    """Los bytes, o None si Binance dice 404. Reintenta las conexiones perdidas."""
    for k in range(intentos):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # noqa: BLE001 - conexiones que se caen hacia Binance
            err = e
        time.sleep(min(60, 2 ** k))
    raise RuntimeError(f"{url}: {err}")


def filas(z: bytes):
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        nombre = zf.namelist()[0]
        with zf.open(nombre) as f:
            for linea in io.TextIOWrapper(f, encoding="ascii"):
                p = linea.split(",")
                if not p[0][:1].isdigit():
                    continue  # cabecera (los meses recientes la traen)
                t = int(p[0])
                if t > 10 ** 14:
                    t //= 1000  # microsegundos
                yield (t // 60000, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7]), float(p[10]))


def simbolo(dir_: Path, s: str, desde: str, hasta: str, log) -> dict:
    cols = {k: array("d") for k in COLS}
    t0 = None
    rellenos = repetidos = 0
    zips: dict[str, str] = {}
    for m in meses(desde, hasta):
        z = baja(URL.format(s=s, m=m))
        if z is None:
            if t0 is None:
                log(f"{s} {m} 404 (aun no publicado)")
                continue
            log(f"{s} {m} 404: la historia acaba en el mes anterior")
            break
        ck = baja(URL.format(s=s, m=m) + ".CHECKSUM")
        sha = hashlib.sha256(z).hexdigest()
        if ck is None or ck.split()[0].decode() != sha:
            raise RuntimeError(f"{s} {m}: el sha256 no casa con el .CHECKSUM")
        zips[m] = sha
        for t, o, h, lo, c, qv, qb in filas(z):
            if t0 is None:
                t0 = t
            k = t - t0
            n = len(cols["c"])
            if k < n:
                repetidos += 1
                continue
            while n < k:  # hueco: ultimo cierre, volumen 0
                pc = cols["c"][-1]
                for col, v in zip(COLS, (pc, pc, pc, pc, 0.0, 0.0), strict=True):
                    cols[col].append(v)
                rellenos += 1
                n += 1
            for col, v in zip(COLS, (o, h, lo, c, qv, qb), strict=True):
                cols[col].append(v)
        log(f"{s} {m} {len(z)} B, {len(cols['c'])} min, rellenos {rellenos}")
    h = hashlib.sha256()
    for col in COLS:
        b = cols[col].tobytes()
        (dir_ / f"{s}.{col}.f64").write_bytes(b)
        h.update(b)
    ms = sorted(zips)
    return {"t0": t0, "n": len(cols["c"]), "primer_mes": ms[0], "ultimo_mes": ms[-1], "minutos_rellenados": rellenos,
            "minutos_repetidos": repetidos, "sha256_columnas": h.hexdigest(), "zips": zips}


FUNDING = "https://data.binance.vision/data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m}.zip"


def funding(dir_: Path, desde: str, hasta: str, log) -> None:
    """DIR/<SIM>.funding.tsv: minuto de liquidacion (epoch // 60) y tasa, y DIR/funding.json con el sha de cada zip."""
    meta: dict = {"fuente": FUNDING, "simbolos": {}}
    for s in SIMBOLOS:
        out, zips = [], {}
        for m in meses(desde, hasta):
            z = baja(FUNDING.format(s=s, m=m))
            if z is None:
                continue
            zips[m] = hashlib.sha256(z).hexdigest()
            with zipfile.ZipFile(io.BytesIO(z)) as zf, zf.open(zf.namelist()[0]) as f:
                for linea in io.TextIOWrapper(f, encoding="ascii"):
                    p = linea.strip().split(",")
                    if p[0][:1].isdigit():
                        out.append(f"{int(p[0]) // 60000}\t{p[-1]}")
        (dir_ / f"{s}.funding.tsv").write_text("\n".join(out) + "\n")
        meta["simbolos"][s] = {"filas": len(out), "zips": zips}
        log(f"{s} funding {len(out)} filas, {len(zips)} meses")
    (dir_ / "funding.json").write_text(json.dumps(meta, indent=1) + "\n")


def main(argv: list[str]) -> int:
    dir_, desde, hasta = Path(argv[0]), argv[1], argv[2]
    dir_.mkdir(parents=True, exist_ok=True)

    def log(x: str) -> None:
        print(time.strftime("%H:%M:%S"), x, flush=True)

    if argv[3:] == ["funding"]:
        funding(dir_, desde, hasta, log)
        return 0

    meta = {"fuente": URL, "columnas": COLS, "simbolos": {}}
    for s in SIMBOLOS:
        meta["simbolos"][s] = simbolo(dir_, s, desde, hasta, log)
    h = hashlib.sha256()
    for s in SIMBOLOS:
        d = meta["simbolos"][s]
        h.update(f"{s} {d['t0']} {d['n']} {d['sha256_columnas']}\n".encode())
    meta["huella"] = h.hexdigest()[:16]
    (dir_ / "historia.json").write_text(json.dumps(meta, indent=1) + "\n")
    log(f"HUELLA {meta['huella']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
