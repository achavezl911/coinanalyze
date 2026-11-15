"""EL SIMULADOR CIEGO (fase 2b): un modelo propone entradas SOBRE EL PASADO sin ver el futuro, y se miden como el diario.

S1 FOTO CIEGA de un instante t (el CIERRE de una vela de 4 h): SOLO velas CERRADAS antes de t (inicio + duracion <= t):
  las ultimas 90 diarias, 120 de 4 h y 288 de 5 min del activo, del banco (<BANCO>/<ACT>-daily-ohlc.txt y
  -4hour-ohlc.txt: t|o|h|l|c|v; <ACT>-5m.txt: t|h|l|c|v, SIN apertura). ANONIMIZADA con un sorteo por foto
  (random.Random(f"{semilla}:{activo}:{t}"), reproducible): el activo es «A», «B» o «C»; los precios se dividen por
  factor = ultimo cierre de 4 h / objetivo, objetivo log-uniforme en [5, 20] (por debajo de cualquier precio crudo
  del banco: el minimo de SOL es 60.03), con 6 cifras significativas; el volumen va relativo a la media de su serie;
  el tiempo, como «cierre hace N horas/minutos» desde t, mas la hora del dia UTC de t (sin dia ni fecha). La clave
  (activo, t, letra, factor) se guarda APARTE y el proponente no la ve.
"""
from __future__ import annotations

import functools
import math
import os
import random

BANCO = os.environ.get("DIARIO_BANCO", "/root/banco-perfil")
ACTIVOS = ("BTC", "ETH", "SOL")
DIA, H4, M5 = 86400, 14400, 300
N_D, N_H, N_M = 90, 120, 288
OBJ_MIN, OBJ_MAX = 5.0, 20.0
SEMILLA = 20261115


@functools.lru_cache(maxsize=16)
def carga(banco: str, act: str) -> dict:
    """{'D'|'H': {inicio: (o, h, l, c, v)}, 'M': {inicio: (h, l, c, v)}} del banco."""
    out = {}
    for k, nom in (("D", "daily-ohlc"), ("H", "4hour-ohlc"), ("M", "5m")):
        with open(os.path.join(banco, f"{act}-{nom}.txt")) as f:
            out[k] = {int(x.split("|")[0]): tuple(map(float, x.split("|")[1:])) for x in f if x.strip()}
    return out


def cerradas(serie: dict, dur: int, t: int, n: int) -> list[tuple]:
    """Las n ultimas velas (inicio, ...) CERRADAS en t: inicio + dur <= t."""
    return [(s, *serie[s]) for s in sorted(s for s in serie if s + dur <= t)][-n:]


def _p(x: float) -> str:
    return f"{x:.6g}"


def foto(banco: str, act: str, t: int, semilla: int = SEMILLA) -> tuple[str, dict]:
    """(texto de la foto, clave). La foto no lleva nada de t en adelante, ni fechas, ni precios sin escalar."""
    if t % H4:
        raise ValueError(f"t={t} no es el cierre de una vela de 4 h")
    b = carga(banco, act)
    az = random.Random(f"{semilla}:{act}:{t}")
    letra = az.choice("ABC")
    objetivo = math.exp(az.uniform(math.log(OBJ_MIN), math.log(OBJ_MAX)))
    D, H, M = cerradas(b["D"], DIA, t, N_D), cerradas(b["H"], H4, t, N_H), cerradas(b["M"], M5, t, N_M)
    if not (D and H and M):
        raise ValueError(f"{act} t={t}: el banco no tiene velas cerradas de las tres series")
    f = H[-1][4] / objetivo
    out = [f"FOTO · activo «{letra}» (perpetuo) · AHORA = cierre de una vela de 4 h; hora del dia UTC ahora: "
           f"{(t % DIA) // 3600:02d}:00",
           "Precios divididos por un factor oculto (las proporciones son exactas). Volumen relativo a la media de su "
           "serie (1.00 = media). Velas de la mas vieja a la mas reciente; solo velas ya cerradas.",
           f"DIARIAS (cierran a las 00:00 UTC; {len(D)}) · hace = horas desde su cierre · hace|o|h|l|c|v"]

    def filas(vs: list, dur: int, unidad: int, campos: int) -> None:
        mv = sum(v[-1] for v in vs) / len(vs) or 1.0
        for v in vs:
            precios = "|".join(_p(x / f) for x in v[1:1 + campos])
            out.append(f"{(t - v[0] - dur) // unidad}|{precios}|{v[-1] / mv:.2f}")

    filas(D, DIA, 3600, 4)
    out.append(f"4 HORAS ({len(H)}) · hace = horas desde su cierre · hace|o|h|l|c|v")
    filas(H, H4, 3600, 4)
    out.append(f"5 MINUTOS ({len(M)}; sin apertura) · hace = minutos desde su cierre · hace|h|l|c|v")
    filas(M, M5, 60, 3)
    return "\n".join(out) + "\n", {"activo": act, "t": t, "letra": letra, "factor": f, "semilla": semilla}
