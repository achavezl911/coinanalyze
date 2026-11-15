"""LAS VELAS: de 140 por harness/bin/api (/api/ohlcv, binance perpetuo agregado de 1 min; solo lectura) a una cache
local en el directorio del diario. La API da solo las ULTIMAS 2000 velas (5 min = ~6.9 dias): lo que 143 no recoja a
tiempo es un hueco para siempre, y asi se dice. Se guardan solo velas CERRADAS; las de 5 min, solo COMPLETAS (5 de 5
minutos) y sin hueco declarado; las de 4 h, con cobertura >= 99 % (una vela de 4 h con un minuto de menos sigue siendo
la misma vela para una regla diaria o de 4 h; a la resolucion no se le perdona ninguno).
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime

ACTIVOS = ("BTC", "ETH", "SOL")
SIMBOLO = {"BTC": "BTCUSDT_PERP.A", "ETH": "ETHUSDT_PERP.A", "SOL": "SOLUSDT_PERP.A"}
H = os.environ.get("DIARIO_HARNESS", "/srv/coinanalyze/harness/bin")
COBERTURA_MIN = {"5min": 100.0, "4hour": 99.0}
GUARDA_5M_S = 40 * 86400  # 5 dias de llenado + 10 de plazo caben de sobra


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def filas_a_velas(filas: list[dict], intervalo: str) -> dict[int, tuple]:
    out = {}
    for r in filas:
        if not r.get("is_closed") or r.get("close") is None or r.get("open") is None:
            continue
        if float(r.get("coverage_pct") or 0) < COBERTURA_MIN[intervalo]:
            continue
        out[_ts(r["bucket"])] = (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
    return out


def pide(act: str, intervalo: str, limite: int = 2000) -> dict[int, tuple]:
    """Las velas de 140 por el canal de solo lectura. Un fallo del canal sale como excepcion, nunca como dato."""
    r = subprocess.run(["sh", f"{H}/api", f"/api/ohlcv?symbol={SIMBOLO[act]}&interval={intervalo}&limit={limite}"],
                       capture_output=True, text=True, timeout=120, env={**os.environ, "TODO": "1"})
    if r.returncode != 0:
        raise RuntimeError(f"api {act} {intervalo} rc={r.returncode}: {(r.stderr or r.stdout).strip()[-200:]}")
    d = json.loads(r.stdout)
    if d.get("symbol") != SIMBOLO[act] or d.get("interval") != intervalo or not isinstance(d.get("rows"), list):
        raise RuntimeError(f"api {act} {intervalo}: respuesta inesperada {r.stdout[:160]}")
    return filas_a_velas(d["rows"], intervalo)


class Cache:
    """{dir}/velas/{ACTIVO}-{intervalo}.json; se escribe por fichero temporal + rename."""

    def __init__(self, carpeta: str):
        self.carpeta = os.path.join(carpeta, "velas")

    def _ruta(self, act: str, intervalo: str) -> str:
        return os.path.join(self.carpeta, f"{act}-{intervalo}.json")

    def lee(self, act: str, intervalo: str) -> dict[int, tuple]:
        try:
            with open(self._ruta(act, intervalo)) as f:
                return {int(k): tuple(v) for k, v in json.load(f).items()}
        except FileNotFoundError:
            return {}

    def mezcla(self, act: str, intervalo: str, nuevas: dict[int, tuple], ahora: int) -> dict[int, tuple]:
        v = self.lee(act, intervalo)
        v.update(nuevas)
        if intervalo == "5min":
            v = {t: x for t, x in v.items() if t >= ahora - GUARDA_5M_S}
        os.makedirs(self.carpeta, exist_ok=True)
        tmp = self._ruta(act, intervalo) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({str(t): list(x) for t, x in sorted(v.items())}, f, separators=(",", ":"))
        os.replace(tmp, self._ruta(act, intervalo))
        return v
