"""EL SIMULADOR CIEGO (fase 2b): un modelo propone entradas SOBRE EL PASADO sin ver el futuro, y se miden como el diario.

S1 FOTO CIEGA de un instante t (el CIERRE de una vela de 4 h): SOLO velas CERRADAS antes de t (inicio + duracion <= t):
  las ultimas 90 diarias, 120 de 4 h y 288 de 5 min del activo, del banco (<BANCO>/<ACT>-daily-ohlc.txt y
  -4hour-ohlc.txt: t|o|h|l|c|v; <ACT>-5m.txt: t|h|l|c|v, SIN apertura). ANONIMIZADA con un sorteo por foto
  (random.Random(f"{semilla}:{activo}:{t}"), reproducible): el activo es «A», «B» o «C»; los precios se dividen por
  factor = ultimo cierre de 4 h / objetivo, objetivo log-uniforme en [5, 20] (por debajo de cualquier precio crudo
  del banco: el minimo de SOL es 60.03), con 6 cifras significativas; el volumen va relativo a la media de su serie;
  el tiempo, como «cierre hace N horas/minutos» desde t, mas la hora del dia UTC de t (sin dia ni fecha). La clave
  (activo, t, letra, factor) se guarda APARTE y el proponente no la ve.
S3 SELLO Y RESOLUCION: cada propuesta se DESANONIMIZA con su clave (precios x factor, caduca = t + segundos, la letra
  vuelve a ser el activo) y se sella con fuente «fable-ciego» en un libro APARTE (<dir>/diario-ciego.jsonl, el mismo
  formato y verificador que entradas.jsonl), con el sello en t simulado y la MISMA validacion (fuentes.valida con el
  precio de la ultima vela de 5 min cerrada en t). En el mismo instante se sella la rejilla de control del activo
  (fuentes.rejilla; id con «@<instante>»). Se resuelve con resuelve.py sobre las velas de 5 min DEL BANCO posteriores a t,
  con «ahora» = fin del banco. El banco de 5 min no trae apertura: la apertura es el cierre de la vela anterior
  recortado a [bajo, alto] y, sin vela anterior, la vela no existe (hueco: la propuesta queda pendiente).
"""
from __future__ import annotations

import functools
import math
import os
import random

from app.diario import fuentes as fu
from app.diario import libro as lb
from app.diario import marcador as mc
from app.diario import proponente as pr

FUENTE = "fable-ciego"
CADUCA_MAX, PLAZO_H_MAX = 432000, 240  # 5 dias de caducidad, 10 de plazo

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


# ---------- S3: sello y resolucion ----------
def velas5(banco: str, act: str) -> dict:
    """{inicio: (o, h, l, c)} de 5 min para resuelve.py; o = cierre anterior recortado a [l, h]; sin anterior, no hay vela."""
    m = carga(banco, act)["M"]
    return {s: (min(max(m[s - M5][2], lo), h), h, lo, c) for s, (h, lo, c, _v) in m.items() if s - M5 in m}


def velas4(banco: str, act: str) -> dict:
    return {s: x[:4] for s, x in carga(banco, act)["H"].items()}


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def desanonimiza(cruda, clave: dict, iid: str) -> tuple[dict | None, str | None]:
    """(propuesta del libro en precios y tiempos REALES, None) o (la propuesta si se pudo formar, motivo de rechazo)."""
    if not isinstance(cruda, dict):
        return None, "la propuesta no es un objeto JSON"
    real = dict(cruda)
    motivo = None
    if cruda.get("activo") != clave["letra"]:
        motivo = f"activo {cruda.get('activo')!r}: la foto era «{clave['letra']}»"
    real["activo"] = clave["activo"]
    for c in ("entrada", "stop", "objetivo"):
        if _num(cruda.get(c)):
            real[c] = cruda[c] * clave["factor"]
    ca = cruda.get("caduca")
    if _num(ca) and 0 < ca <= CADUCA_MAX:
        real["caduca"] = clave["t"] + int(ca)
    else:
        real["caduca"] = None
        motivo = motivo or f"caduca {ca!r}: segundos desde AHORA en (0, {CADUCA_MAX}]"
    if "plazo_h" in cruda and not (_num(cruda["plazo_h"]) and 0 < cruda["plazo_h"] <= PLAZO_H_MAX):
        motivo = motivo or f"plazo_h {cruda['plazo_h']!r} fuera de (0, {PLAZO_H_MAX}]"
    p = fu.de_fable(real, clave["t"])
    p["fuente"] = FUENTE
    p["id"] = f"{FUENTE}:{iid}:{cruda.get('id')}" if cruda.get("id") else ""
    return p, motivo


def sella_instante(L: lb.Libro, banco: str, clave: dict, iid: str, reg: dict, vistos: set) -> dict:
    """Sella en t la respuesta del proponente (propuestas o rechazos) y la rejilla de control del activo."""
    from app.diario.__main__ import sella

    act, t = clave["activo"], clave["t"]
    v5 = velas5(banco, act)
    px = fu.precio(v5, t)
    n = {"selladas": 0, "rechazadas": 0}

    def rechaza(id_: str, motivo: str, cruda) -> None:
        L.anade("rechazo", {"fuente": FUENTE, "id": id_, "motivo": motivo, "cruda": cruda, "sello": t}, t)
        n["rechazadas"] += 1

    crudas, motivo = pr.lee(reg.get("texto")) if not reg.get("error") else ([], f"proponente: {reg['error'][:200]}")
    if motivo:
        rechaza(f"{FUENTE}:{iid}", motivo, (reg.get("texto") or "")[:2000] or None)
    for cruda in crudas:
        p, m = desanonimiza(cruda, clave, iid)
        m = m or fu.valida(p, px, t, vistos)
        if m:
            rechaza((p or {}).get("id") or f"{FUENTE}:{iid}", m, cruda)
        else:
            L.anade("propuesta", p, t)
            n["selladas"] += 1
        if p and p["id"]:
            vistos.add(p["id"])
    rej = fu.rejilla({act: velas4(banco, act)}, t)
    for p in rej:
        p["id"] += f"@{iid}"
    if rej:
        n["rejilla"] = sella(L, rej, {act: v5}, t, vistos)
    else:
        L.anade("rechazo", {"fuente": "rejilla", "id": f"rejilla:{act}@{iid}", "motivo": "sin dia cerrado completo en el banco",
                            "cruda": None, "sello": t}, t)
    return n


def resuelve_y_marca(L: lb.Libro, banco: str, carpeta: str) -> dict:
    """Resuelve lo sellado con las velas de 5 min del banco (ahora = su fin) y escribe <carpeta>/marcador.txt."""
    from app.diario.__main__ import resuelve_todo

    filas = L.lee()
    v5 = {a: velas5(banco, a) for a in sorted({p["activo"] for p in mc.operaciones(filas)[0].values()})}
    fin = max((max(v, default=0) for v in v5.values()), default=0) + M5
    n, huecos = resuelve_todo(L, filas, v5, fin)
    t = ("SIMULADOR CIEGO (fase 2b): propuestas de Fable SOBRE EL PASADO con fotos ciegas, sello en t simulado y "
         "resueltas con el banco; NO es el diario en vivo.\n" + mc.texto(L.lee(), L.cabeza(), fin, huecos))
    with open(os.path.join(carpeta, "marcador.txt"), "w") as f:
        f.write(t + "\n")
    return {"resueltas": n, "huecos": len(huecos), "fin_banco": fin, "marcador": t}
