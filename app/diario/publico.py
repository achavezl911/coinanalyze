"""EL VOLCADO PUBLICO: las velas de 5 min que 140 no tiene, desde data.binance.vision (solo lectura, sin claves).

Por que: el apagon del 11-16 15:30Z -> 11-18 01:25Z dejo en /api/ohlcv 280 cubos sin precio y 128 sin fila (BTC), y
el diario congelo sus 18 propuestas «pendiente por hueco» sin plazo (R3b H1). Las velas de la ruta son las de 1 min
del perpetuo USD-M de binance agregadas a 5 min; el volcado diario de ese MISMO instrumento es
  https://data.binance.vision/data/futures/um/daily/klines/<SIM>/1m/<SIM>-1m-<AAAA-MM-DD>.zip  (+ .CHECKSUM, sha256)
y se agrega igual que la ruta: apertura del primer minuto, maximo y minimo, cierre del ultimo; solo cubos con sus
5 de 5 minutos (como COBERTURA_MIN['5min'] = 100 en velas.py).

  CUANDO   solo un cubo CERRADO, sin precio, que bloquea una propuesta, y cuyo dia UTC ya paso (el volcado sale despues).
           Un dia se pide como mucho una vez por REINTENTO_S; un CHECKSUM que no casa no entra NUNCA (se anota).
  DONDE    <diario>/velas/<ACT>-5min-publico.json, aparte de la cache de 140: la fuente queda en el NOMBRE del fichero y
           en sus campos (`fuente`, `dias` con el sha256 de cada zip). Nunca pisa una vela de 140: al resolver, manda 140.
  SI NO    a los INDECIDIBLE_S del fin del cubo que falta, la propuesta se cierra «indecidible» (resuelve.indecidible) y
           el marcador la cuenta aparte: ni R, ni llenado.
Para comparar las dos fuentes en dias con las dos: python -m app.diario publico compara BTC 2026-11-15
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import urllib.request
import zipfile
from datetime import UTC, datetime

DIA, PASO = 86400, 300
FUENTE = "data.binance.vision futures/um daily klines 1m"
URL = "https://data.binance.vision/data/futures/um/daily/klines/{s}/1m/{s}-1m-{d}.zip"
SIMBOLO = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
REINTENTO_S = 3600


def _baja(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 - URL fija de arriba
        return r.read()


def dia_iso(d: int) -> str:
    return datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d")


def velas_del_zip(datos: bytes, checksum: str, nombre: str) -> dict[int, tuple]:
    """Las velas de 5 min de un zip diario de 1 min. ValueError si el sha256 no es el del .CHECKSUM."""
    esperado = checksum.split()[0].strip().lower() if checksum.split() else ""
    if hashlib.sha256(datos).hexdigest() != esperado:
        raise ValueError(f"{nombre}: el sha256 del zip no es el del CHECKSUM")
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        texto = z.read(z.namelist()[0]).decode()
    minutos = {}
    for fila in csv.reader(texto.splitlines()):
        if not fila or not fila[0].strip().isdigit():
            continue  # la cabecera (los volcados viejos no la traen)
        t = int(fila[0])
        t = t // 1_000_000 if t > 10**14 else t // 1000  # ms (o us en los volcados nuevos de spot)
        minutos[t] = (float(fila[1]), float(fila[2]), float(fila[3]), float(fila[4]))
    return agrega_5m(minutos)


def agrega_5m(minutos: dict[int, tuple]) -> dict[int, tuple]:
    """Como /api/ohlcv: date_bin de 5 min, apertura del primero, cierre del ultimo; solo cubos con 5 de 5 minutos."""
    cubos: dict[int, list] = {}
    for t in sorted(minutos):
        cubos.setdefault(t - t % PASO, []).append(minutos[t])
    return {t: (xs[0][0], max(x[1] for x in xs), min(x[2] for x in xs), xs[-1][3])
            for t, xs in cubos.items() if len(xs) == PASO // 60}


def baja_dia(act: str, d: int, baja=_baja) -> tuple[dict[int, tuple], str]:
    """(velas de 5 min del dia d, sha256 del zip). Cualquier fallo (red, checksum) sale como excepcion."""
    s = SIMBOLO[act]
    url = URL.format(s=s, d=dia_iso(d))
    checksum = baja(url + ".CHECKSUM").decode()
    datos = baja(url)
    return velas_del_zip(datos, checksum, url.rsplit("/", 1)[1]), hashlib.sha256(datos).hexdigest()


class Publico:
    """<carpeta>/velas/<ACT>-5min-publico.json = {fuente, dias: {AAAA-MM-DD: sha256}, intentos: {AAAA-MM-DD: t},
    malos: {AAAA-MM-DD: motivo}, velas: {inicio: [o, h, l, c]}}."""

    def __init__(self, carpeta: str):
        self.carpeta = os.path.join(carpeta, "velas")

    def _ruta(self, act: str) -> str:
        return os.path.join(self.carpeta, f"{act}-5min-publico.json")

    def carga(self, act: str) -> dict:
        try:
            with open(self._ruta(act)) as f:
                return json.load(f)
        except FileNotFoundError:
            return {"fuente": FUENTE, "dias": {}, "intentos": {}, "malos": {}, "velas": {}}

    def lee(self, act: str) -> dict[int, tuple]:
        return {int(k): tuple(v) for k, v in self.carga(act)["velas"].items()}

    def _guarda(self, act: str, x: dict) -> None:
        os.makedirs(self.carpeta, exist_ok=True)
        tmp = self._ruta(act) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(x, f, separators=(",", ":"), sort_keys=True)
        os.replace(tmp, self._ruta(act))

    def rellena(self, act: str, huecos: list[int], ahora: int, errores: list, fallos: list | None = None,
                baja=_baja) -> list[str]:
        """Pide el dia de cada cubo hueco cuyo dia UTC ya paso. Devuelve los dias que entraron. Un CHECKSUM que no
        casa va a `errores` (es un error); un volcado que aun no esta o la red caida, a `fallos` (se reintenta)."""
        x, nuevos = self.carga(act), []
        for d in sorted({t - t % DIA for t in huecos if t + PASO <= ahora}):
            iso = dia_iso(d)
            if d + DIA > ahora or iso in x["dias"] or ahora - x["intentos"].get(iso, -REINTENTO_S) < REINTENTO_S:
                continue
            x["intentos"][iso] = ahora
            try:
                velas, sha = baja_dia(act, d, baja)
            except Exception as e:  # sin volcado todavia, red caida o checksum malo: se anota y se reintenta
                motivo = f"{type(e).__name__} {str(e)[:120]}"
                if isinstance(e, ValueError):
                    x["malos"][iso] = motivo
                (errores if isinstance(e, ValueError) or fallos is None else fallos).append(f"publico {act} {iso}: {motivo}")
                continue
            x["velas"].update({str(t): list(v) for t, v in velas.items()})
            x["dias"][iso] = sha
            nuevos.append(iso)
        self._guarda(act, x)
        return nuevos


def compara(act: str, d: int, ruta: dict[int, tuple], baja=_baja) -> dict:
    """Cuanto se parecen las velas publicas y las de la ruta en el dia d (las dos con precio)."""
    pub, _ = baja_dia(act, d, baja)
    comunes = sorted(set(pub) & {t for t in ruta if d <= t < d + DIA})
    def igual(a: float, b: float) -> bool:
        return abs(a - b) <= 1e-9 * max(1.0, abs(a))

    iguales = [t for t in comunes if all(map(igual, pub[t], ruta[t]))]
    dif_bps = [max(abs(a / b - 1) * 1e4 for a, b in zip(pub[t], ruta[t], strict=True)) for t in comunes]
    por_campo = {k: sum(not igual(pub[t][i], ruta[t][i]) for t in comunes) for i, k in enumerate("ohlc")}
    return {"activo": act, "dia": dia_iso(d), "publicas": len(pub), "comunes": len(comunes), "identicas": len(iguales),
            "distintas_por_campo": por_campo, "peor_dif_bps": round(max(dif_bps), 4) if dif_bps else None,
            "distintas": [(datetime.fromtimestamp(t, UTC).strftime("%H:%MZ"), pub[t], ruta[t])
                          for t in comunes if t not in iguales][:3]}
