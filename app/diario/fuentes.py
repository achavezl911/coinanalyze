"""LAS TRES FUENTES del diario. Todas sellan por el mismo libro y pasan por el mismo `valida` (con el precio del sello).

(a) REGLAS CONGELADAS de claude/fable-be (scripts/fable_be_tendencia.py de esa rama, confirmacion del 2026-11-14):
    `D:imp1:v0:A`  diario, imp1 (retorno de 1 barra >= 1.5 x raiz(1) x rango medio de 14 barras anterior), sin filtro,
                   stop 3 %, objetivo 2 R (6 %), plazo 10 dias.
    `H:imp6:v1:D`  4 h, imp6 (retorno de 6 barras >= 1.5 x raiz(6) x el rango de 14 de antes del impulso), filtro v1
                   (rango de 14 >= la mediana de sus 90 anteriores), stop 3 %, objetivo 6 %, plazo 6 dias.
    `indicadores` y `estado` son COPIA literal de esa rama (prueba de paridad en tests/test_diario.py). AVISO = la barra
    CERRADA en que la senal se enciende (apagada o contraria en la anterior); sin solape por regla y activo (no se sella
    mientras la anterior siga abierta). Entrada a MERCADO: la apertura de la primera vela de 5 min tras el sello (el
    temporizador corre a los 20 s de cada cuarto de hora: ~5 min despues del cierre). Solo se evalua la ultima barra si
    cerro hace menos de una hora: un aviso viejo no se sella tarde. Velas de 4 h de 140; la diaria se arma con las 6 de 4 h.
(b) REJILLA DE CONTROL: tras cada cierre diario (00:00Z), por activo y lado, limites a 2, 4 y 6 % del cierre (largo
    debajo, corto encima), stop 3 % y objetivo 6 % del nivel, caducidad del llenado 5 dias, plazo 10 dias.
(c) BUZON DE FABLE: <diario>/buzon/*.json. Formato (version `diario-entradas/1`):
      {"formato": "diario-entradas/1", "corrida": "<texto libre: quien y cuando>",
       "propuestas": [{"id": "<unico>", "activo": "BTC|ETH|SOL", "lado": "largo|corto", "orden": "limite|mercado",
                       "entrada": <precio; en mercado, la referencia>, "stop": <precio>, "objetivo": <precio>,
                       "caduca": <s Unix o ISO 8601 UTC: hasta cuando vale el llenado>,
                       "plazo_h": <horas abierta como mucho; 240 si falta>, "riesgo_usd": <0 < r <= 5; 5 si falta>,
                       "porque": "<texto corto>"}]}
    Cada propuesta se sella (id `fable:<id>`) o se RECHAZA con motivo; el fichero pasa a buzon/leidos/. Un fichero que
    no es JSON o no trae `propuestas` deja un rechazo del fichero entero.
`valida` RECHAZA: activo, lado u orden fuera de lista; sin stop, objetivo o caducidad; caducidad ya pasada; geometria
al reves (largo: stop < entrada < objetivo); un LIMITE ya lleno al sellar (largo por encima del precio, corto por
debajo); un MERCADO con el stop ya cruzado; riesgo fuera de (0, PERDIDA_MAX]; id repetido.
"""
from __future__ import annotations

import json
import math
import os
import statistics
from datetime import UTC, datetime

from app.bot.calc import PERDIDA_MAX

DIA, H4 = 86400, 14400
OBJ_R = 2.0
REGLAS = {
    "D:imp1:v0:A": {"marco": "D", "dur": DIA, "regla": "imp1", "filtro": 0, "stop": 0.03, "plazo_d": 10},
    "H:imp6:v1:D": {"marco": "H", "dur": H4, "regla": "imp6", "filtro": 1, "stop": 0.03, "plazo_d": 6},
}
STOP_MIN = 0.005  # el stop mas cerca que se sella: con 0.1 % un salto de apertura daba +0.48 R (R3b H6)
REJILLA_PCT, REJILLA_STOP, REJILLA_OBJ, REJILLA_CADUCA_D, REJILLA_PLAZO_D = (0.02, 0.04, 0.06), 0.03, 0.06, 5, 10
FRESCO_S = 3600
FORMATO = "diario-entradas/1"


# ---------- COPIA de claude/fable-be:scripts/fable_be_tendencia.py (indicadores, estado) ----------
def indicadores(bs: list, n_sma: int):
    c = [b[4] for b in bs]
    rb = [(b[2] - b[3]) / b[4] for b in bs]
    n = len(bs)
    rng, med, reg = [None] * n, [None] * n, [0] * n
    for i in range(13, n):
        rng[i] = sum(rb[i - 13:i + 1]) / 14
    for i in range(103, n):
        med[i] = statistics.median(rng[i - 90:i])
    for i in range(n_sma - 1, n):
        reg[i] = 1 if c[i] > sum(c[i - n_sma + 1:i + 1]) / n_sma else -1
    return rng, med, reg


def estado(regla: str, bs: list, rng: list, i: int) -> int:
    """+1 largo, -1 corto, 0 nada: la senal de la regla al CIERRE de la barra i, solo con barras <= i."""
    k = int(regla[3:])
    c = bs[i][4]
    if regla.startswith("rup"):
        if c > max(b[2] for b in bs[i - k:i]):
            return 1
        return -1 if c < min(b[3] for b in bs[i - k:i]) else 0
    if regla.startswith("est"):
        bl = [bs[i - k * (j + 1) + 1:i - k * j + 1] for j in range(3)]
        hh = [max(b[2] for b in x) for x in bl]
        ll = [min(b[3] for b in x) for x in bl]
        if hh[0] < hh[1] < hh[2] and ll[0] < ll[1] < ll[2]:
            return -1
        return 1 if hh[0] > hh[1] > hh[2] and ll[0] > ll[1] > ll[2] else 0
    r = c / bs[i - k][4] - 1
    return (r > 0) - (r < 0) if abs(r) >= 1.5 * math.sqrt(k) * rng[i - k] else 0
# ---------- fin de la copia ----------


def minimo_barras(celda: str) -> int:
    """Barras necesarias para que `aviso` sea el mismo que en fable-be en la ultima (indices >= 1 en rng y med)."""
    r = REGLAS[celda]
    k = int(r["regla"][3:])
    return max(14 + k + 1, 104 + 1 if r["filtro"] else 0)


def aviso(celda: str, bs: list, i: int, ind: tuple | None = None) -> int:
    """+1/-1 si la barra i es un AVISO de la celda (como el bucle de `mide` de fable-be, sin el solape), 0 si no."""
    r = REGLAS[celda]
    rng, med, _ = ind if ind is not None else indicadores(bs, 1)
    s = estado(r["regla"], bs, rng, i)
    if not s or s == estado(r["regla"], bs, rng, i - 1):
        return 0
    if r["filtro"] and (med[i] is None or rng[i] < med[i]):
        return 0
    return s


def tramo(velas: dict, dur: int) -> list[tuple]:
    """El tramo CONTIGUO final de barras (t, o, h, l, c, dur), sello de INICIO."""
    ts = sorted(velas)
    out = []
    for t in reversed(ts):
        if out and out[-1][0] - dur != t:
            break
        out.append((t, *velas[t], dur))
    return out[::-1]


def diarias(velas4h: dict) -> dict:
    """Velas diarias (00:00Z) con sus 6 velas de 4 h presentes; las demas no existen."""
    out = {}
    for d in sorted({t - t % DIA for t in velas4h}):
        seis = [velas4h.get(d + H4 * k) for k in range(6)]
        if all(seis):
            out[d] = (seis[0][0], max(x[1] for x in seis), min(x[2] for x in seis), seis[5][3])
    return out


def precio(velas5: dict, ahora: int) -> float | None:
    """El cierre de la ultima vela de 5 min cerrada, si cerro hace 15 min como mucho."""
    t = max((t for t in velas5 if t + 300 <= ahora), default=None)
    return velas5[t][3] if t is not None and ahora - (t + 300) <= 900 else None


def propuesta(fuente: str, id_: str, act: str, s: int, orden: str, entrada: float, stop: float, objetivo: float,
              caduca: int, plazo_s: int, sello: int, porque: str, riesgo: float = PERDIDA_MAX) -> dict:
    return {"fuente": fuente, "id": id_, "activo": act, "lado": "largo" if s > 0 else "corto", "orden": orden,
            "entrada": round(entrada, 8), "stop": round(stop, 8), "objetivo": round(objetivo, 8), "caduca": int(caduca),
            "plazo_s": int(plazo_s), "riesgo_usd": float(riesgo), "sello": int(sello), "porque": porque[:300]}


def valida(p: dict, px: float | None, ahora: int, vistos: set) -> str | None:
    """None si se puede sellar; si no, el motivo del rechazo."""
    if not p.get("id") or p["id"] in vistos:
        return "id vacio o repetido"
    if p.get("activo") not in ("BTC", "ETH", "SOL"):
        return f"activo {p.get('activo')!r} fuera de BTC/ETH/SOL"
    if p.get("lado") not in ("largo", "corto") or p.get("orden") not in ("limite", "mercado"):
        return f"lado {p.get('lado')!r} u orden {p.get('orden')!r} fuera de lista"
    for c in ("stop", "objetivo", "caduca", "entrada"):
        v = p.get(c)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0:
            return f"falta {c} (o no es un numero positivo)"
    rg = p.get("riesgo_usd")
    if not isinstance(rg, (int, float)) or isinstance(rg, bool) or not 0 < rg <= PERDIDA_MAX:
        return f"riesgo {p.get('riesgo_usd')} fuera de (0, {PERDIDA_MAX:g}] USD"
    if not isinstance(p.get("plazo_s"), int) or p["plazo_s"] <= 0:
        return "plazo no valido"
    if p["caduca"] <= ahora:
        return "caducidad ya pasada al sellar"
    s = 1 if p["lado"] == "largo" else -1
    if not (s * p["stop"] < s * p["entrada"] < s * p["objetivo"]):
        return "geometria al reves (largo: stop < entrada < objetivo; corto al reves)"
    if abs(p["entrada"] - p["stop"]) / p["entrada"] < STOP_MIN:
        return f"stop a {abs(p['entrada'] - p['stop']) / p['entrada']:.2%} de la entrada, minimo {STOP_MIN:.1%}"
    if px is None:
        return "sin precio de 140 al sellar (vela de 5 min de hace mas de 15 min)"
    if p["orden"] == "limite" and s * p["entrada"] >= s * px:
        return f"ya llena al sellar: limite {p['lado']} a {p['entrada']:g} con el precio en {px:g}"
    if p["orden"] == "mercado" and s * p["stop"] >= s * px:
        return f"stop ya cruzado al sellar (precio {px:g})"
    return None


def reglas(velas4h: dict[str, dict], ahora: int, bloqueadas: set) -> tuple[list[dict], list[str]]:
    """Propuestas de las reglas congeladas sobre la ULTIMA barra cerrada de cada activo y marco (solo si es fresca)."""
    props, notas = [], []
    for celda, r in REGLAS.items():
        for act, v4 in velas4h.items():
            v4 = {t: x for t, x in v4.items() if t + H4 <= ahora}
            bs = tramo(diarias(v4) if r["marco"] == "D" else v4, r["dur"])
            if not bs:
                notas.append(f"{celda} {act}: sin barras")
                continue
            T = bs[-1][0] + r["dur"]
            if ahora - T > FRESCO_S:
                continue
            if len(bs) < minimo_barras(celda):
                notas.append(f"{celda} {act}: {len(bs)} barras contiguas, hacen falta {minimo_barras(celda)}")
                continue
            if (celda, act) in bloqueadas:
                continue
            s = aviso(celda, bs, len(bs) - 1)
            if not s:
                continue
            ref, d = bs[-1][4], r["stop"]
            k = int(r["regla"][3:])
            ret = bs[-1][4] / bs[-1 - k][4] - 1
            props.append(propuesta(f"regla:{celda}", f"regla:{celda}:{act}:{T}", act, s, "mercado", ref,
                                   ref * (1 - s * d), ref * (1 + s * OBJ_R * d), ahora + 3600, r["plazo_d"] * DIA, ahora,
                                   f"{celda}: {r['regla']} {ret:+.2%} al cierre de la barra de "
                                   f"{datetime.fromtimestamp(bs[-1][0], UTC).strftime('%Y-%m-%d %H:%MZ')}"))
    return props, notas


def rejilla(velas4h: dict[str, dict], ahora: int, errores: list | None = None) -> list[dict]:
    """La rejilla del ULTIMO dia cerrado, si cerro hace menos de 24 h. Un activo sin ese dia (faltan velas de 4 h)
    va a `errores`: el dia sin control se ve en el estado y en el marcador, no calla (R3b H3)."""
    out, errores = [], [] if errores is None else errores
    ayer = datetime.fromtimestamp(ahora - ahora % DIA - DIA, UTC).strftime("%Y-%m-%d")
    for act, v4 in velas4h.items():
        dd = diarias({t: x for t, x in v4.items() if t + H4 <= ahora})
        if not dd:
            errores.append(f"rejilla {act}: sin ningun dia con sus seis velas de 4 h; el {ayer} queda sin rejilla")
            continue
        d = max(dd)
        if ahora - (d + DIA) > DIA or d + DIA > ahora:
            ult = datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d")
            errores.append(f"rejilla {act}: el ultimo dia con sus seis velas de 4 h es el {ult}; el {ayer} queda sin rejilla")
            continue
        c = dd[d][3]
        dia = datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d")
        for s in (1, -1):
            for pct in REJILLA_PCT:
                e = c * (1 - s * pct)
                out.append(propuesta("rejilla", f"rejilla:{act}:{'L' if s > 0 else 'C'}:{pct:.2f}:{dia}", act, s,
                                     "limite", e, e * (1 - s * REJILLA_STOP), e * (1 + s * REJILLA_OBJ),
                                     ahora + REJILLA_CADUCA_D * DIA, REJILLA_PLAZO_D * DIA, ahora,
                                     f"rejilla de control: {pct:.0%} del cierre diario {c:g} del {dia}"))
    return out


def _cuando(v) -> int | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v)
    if isinstance(v, str):
        try:
            return int(datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    return None


def buzon(carpeta: str, ahora: int) -> list[tuple[str, dict | None, str | None]]:
    """(fichero, contenido, error) de cada JSON del buzon, en orden de nombre. No mueve nada."""
    out = []
    if not os.path.isdir(carpeta):
        return out
    for nom in sorted(os.listdir(carpeta)):
        ruta = os.path.join(carpeta, nom)
        if not nom.endswith(".json") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta) as f:
                d = json.load(f)
            if not isinstance(d, dict) or d.get("formato") != FORMATO or not isinstance(d.get("propuestas"), list):
                raise ValueError(f"no es {FORMATO} con una lista `propuestas`")
            out.append((ruta, d, None))
        except (ValueError, OSError) as e:
            out.append((ruta, None, f"{type(e).__name__}: {str(e)[:160]}"))
    return out


def de_fable(cruda: dict, ahora: int) -> dict:
    """Una propuesta del buzon en la forma del libro (sin validar: eso lo hace `valida`)."""
    plazo_h = cruda.get("plazo_h", 240)
    return {"fuente": "fable", "id": f"fable:{cruda.get('id')}" if cruda.get("id") else "",
            "activo": cruda.get("activo"), "lado": cruda.get("lado"), "orden": cruda.get("orden"),
            "entrada": cruda.get("entrada"), "stop": cruda.get("stop"), "objetivo": cruda.get("objetivo"),
            "caduca": _cuando(cruda.get("caduca")),
            "plazo_s": int(plazo_h * 3600) if isinstance(plazo_h, (int, float)) and not isinstance(plazo_h, bool) else None,
            "riesgo_usd": cruda.get("riesgo_usd", PERDIDA_MAX), "sello": ahora, "porque": str(cruda.get("porque", ""))[:300]}


def sella_buzon(libro, carpeta: str, precios: dict, ahora: int, vistos: set) -> dict:
    """Sella o rechaza cada propuesta del buzon y mueve el fichero a leidos/. Sin precio fresco de los tres activos no
    toca nada: los ficheros esperan a la siguiente corrida (y si caducan entretanto, se rechazan por caducadas)."""
    n = {"selladas": 0, "rechazadas": 0, "ficheros": 0}
    fichs = buzon(carpeta, ahora)
    if not fichs or any(precios.get(a) is None for a in ("BTC", "ETH", "SOL")):
        return n
    leidos = os.path.join(carpeta, "leidos")
    os.makedirs(leidos, exist_ok=True)
    for ruta, d, err in fichs:
        nom = os.path.basename(ruta)
        if err:
            libro.anade("rechazo", {"fuente": "fable", "id": f"fichero:{nom}", "motivo": err, "cruda": None,
                                    "sello": ahora}, ahora)
            n["rechazadas"] += 1
        for cruda in d["propuestas"] if d else []:
            p = de_fable(cruda, ahora) if isinstance(cruda, dict) else None
            motivo = valida(p, precios.get(p["activo"]), ahora, vistos) if p else "la propuesta no es un objeto JSON"
            if motivo:
                libro.anade("rechazo", {"fuente": "fable", "id": (p or {}).get("id") or f"fichero:{nom}",
                                        "motivo": motivo, "cruda": cruda, "sello": ahora}, ahora)
                n["rechazadas"] += 1
            else:
                libro.anade("propuesta", p, ahora)
                vistos.add(p["id"])
                n["selladas"] += 1
        destino = os.path.join(leidos, nom)
        os.replace(ruta, destino if not os.path.exists(destino) else f"{destino}.{ahora}")
        n["ficheros"] += 1
    return n
