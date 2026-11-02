"""FILTRA (campana BOT-3d): ¿las operaciones reales de Alejandro iban mejor con el mapa a favor? SOLO biblioteca estandar.

USO (lo corre el OPERADOR en 140, no en 143):
    python scripts/filtra.py PRIVADO scripts/filtra_estados.json
PRIVADO: el JSON de app/bot/historial.py (claves `cierres`, filas de /v5/position/closed-pnl, y `ejecuciones`, filas de
/v5/execution/list, campos de Bybit v5). filtra_estados.json: lo escribe scripts/filtra_estados.py (datos publicos).

Reconstruye cada operacion de plano a plano por simbolo y en orden de execTime con las ejecuciones execType == Trade
(cierres parciales y volteo incluidos; Funding y el resto no cuentan), le asigna sus filas de cierres por simbolo, hora
y lado, y su rendimiento es suma de closedPnl / suma de cumEntryValue (% del nocional). Estado del mapa: el de la ultima
decision de 4 h con minuto <= la entrada: A FAVOR si lado*S >= k, EN CONTRA si lado*S <= -k, NEUTRO si no.

IMPRIME SOLO AGREGADOS: nunca una fila, una fecha suelta, un precio, una cantidad ni una cifra en USD. Un grupo con
n < 10 sale solo con su n.
"""

from __future__ import annotations

import bisect
import json
import random
import statistics
import sys
from decimal import Decimal, InvalidOperation

N_GRUPO, B, SEMILLA, TOLERA_MS = 10, 2000, 20261103, 60_000


def _d(x) -> Decimal:
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _ms(f: dict, *claves: str) -> int | None:
    for k in claves:
        try:
            return int(f[k])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def reconstruye(ejecuciones: list[dict]) -> tuple[list[dict], dict]:
    """Operaciones de plano a plano. Devuelve (operaciones, causas de lo que no cuenta)."""
    causas: dict[str, int] = {}
    por_sim: dict[str, list] = {}
    for i, f in enumerate(ejecuciones):
        tipo = str(f.get("execType", ""))
        t, q = _ms(f, "execTime"), _d(f.get("execQty"))
        if tipo != "Trade":
            c = f"ejecucion execType={tipo or '?'} (no cuenta)"
        elif t is None or q <= 0 or f.get("side") not in ("Buy", "Sell") or not f.get("symbol"):
            c = "ejecucion Trade ilegible (sin hora, cantidad o lado)"
        else:
            c = None
        if c:
            causas[c] = causas.get(c, 0) + 1
            continue
        por_sim.setdefault(f["symbol"], []).append((t, i, f))
    ops = []
    for sim, filas in por_sim.items():
        filas.sort(key=lambda x: (x[0], x[1]))
        pos, op = Decimal(0), None
        for t, _, f in filas:
            q = _d(f["execQty"]) * (1 if f["side"] == "Buy" else -1)
            fee, val = _d(f.get("execFee")), _d(f.get("execValue"))
            nuevo = pos + q
            if pos != 0 and nuevo != 0 and (nuevo > 0) != (pos > 0):  # volteo: cierra lo que habia y abre el resto
                parte = abs(pos) / abs(q)
                op["fee"] += fee * parte
                op["val"] += val * parte
                op["fin"] = t
                ops.append(op)
                op = {"sim": sim, "lado": 1 if nuevo > 0 else -1, "ini": t, "fin": None,
                      "fee": fee * (1 - parte), "val": val * (1 - parte)}
            else:
                if pos == 0:
                    op = {"sim": sim, "lado": 1 if q > 0 else -1, "ini": t, "fin": None, "fee": Decimal(0),
                          "val": Decimal(0)}
                op["fee"] += fee
                op["val"] += val
                if nuevo == 0:
                    op["fin"] = t
                    ops.append(op)
                    op = None
            pos = nuevo
        if op is not None:
            op["fin"] = None
            ops.append(op)
    for o in ops:
        o["pnl"], o["entrada"], o["n_cierres"] = Decimal(0), Decimal(0), 0
    return ops, causas


def asigna(ops: list[dict], cierres: list[dict]) -> dict:
    """Cada fila de cierres a su operacion: mismo simbolo, lado contrario al de cierre, hora dentro [ini, fin + tolera]."""
    causas: dict[str, int] = {}
    por_sim: dict[str, list] = {}
    for o in ops:
        if o["fin"] is not None:
            por_sim.setdefault(o["sim"], []).append(o)
    for f in cierres:
        sim = f.get("symbol")
        lado = {"Sell": 1, "Buy": -1}.get(f.get("side"))  # el lado del cierre es el contrario al de la posicion
        cands = por_sim.get(sim) or []
        if not cands:
            c = "simbolo sin operaciones cerradas"
        elif lado is None:
            c = "sin lado legible"
        else:
            c = "fuera de toda operacion de su lado (hora)"
            for clave in ("createdTime", "updatedTime"):
                t = _ms(f, clave)
                if t is None:
                    continue
                dentro = [o for o in cands if o["lado"] == lado and o["ini"] <= t <= o["fin"] + TOLERA_MS]
                if dentro:
                    o = min(dentro, key=lambda o: abs(o["fin"] - t))
                    o["pnl"] += _d(f.get("closedPnl"))
                    o["entrada"] += _d(f.get("cumEntryValue"))
                    o["n_cierres"] += 1
                    c = None
                    break
        if c:
            causas[c] = causas.get(c, 0) + 1
    return causas


def estados(doc: dict) -> tuple[int, dict]:
    return int(doc["k"]), {s: (v["minuto"], v["S"], v["rsi4h"]) for s, v in doc["simbolos"].items()}


def estado(o: dict, k: int, est: dict, paso: int = 240) -> str:
    """A FAVOR / EN CONTRA / NEUTRO, o 'sin estado: <causa>'. Guarda el rsi4h en la operacion."""
    if o["sim"] not in est:
        return "sin estado: activo fuera del mapa"
    mins, S, rsi = est[o["sim"]]
    m = o["ini"] // 60000
    i = bisect.bisect_right(mins, m) - 1
    if i < 0:
        return "sin estado: entrada antes de la historia del mapa"
    if m >= mins[-1] + paso:
        return "sin estado: entrada despues del fin de la historia del mapa"
    o["S"], o["rsi4h"] = S[i], rsi[i]
    v = o["lado"] * S[i]
    return "A FAVOR" if v >= k else ("EN CONTRA" if v <= -k else "NEUTRO")


def _semana(ms: int) -> int:
    return (ms // 86_400_000 + 3) // 7


def intervalo(ops: list[dict]) -> tuple[float, float] | None:
    sem: dict[int, list[float]] = {}
    for o in ops:
        sem.setdefault(_semana(o["ini"]), []).append(o["r"])
    claves = list(sem)
    rng = random.Random(SEMILLA)
    medias = []
    for _ in range(B):
        v = [x for _ in claves for x in sem[claves[rng.randrange(len(claves))]]]
        medias.append(sum(v) / len(v))
    medias.sort()
    return medias[int(0.05 * B)], medias[int(0.95 * B) - 1]


def linea(nombre: str, ops: list[dict]) -> str:
    n = len(ops)
    if n < N_GRUPO:
        return f"  {nombre:<34} n={n}"
    r = [o["r"] for o in ops]
    lo, hi = intervalo(ops)
    val = sum((o["val"] for o in ops), Decimal(0))
    com = float(sum((o["fee"] for o in ops), Decimal(0)) / val * 100) if val else float("nan")
    dur = statistics.median((o["fin"] - o["ini"]) / 3_600_000 for o in ops)
    return (f"  {nombre:<34} n={n} acierto={100 * sum(x > 0 for x in r) / n:.1f}% media={statistics.fmean(r):+.3f}% "
            f"mediana={statistics.median(r):+.3f}% ic90=[{lo:+.3f}%, {hi:+.3f}%] duracion_mediana={dur:.1f}h "
            f"comisiones={com:.3f}%")


def informe(priv: dict, doc: dict) -> list[str]:
    k, est = estados(doc)
    ops, causas_e = reconstruye(priv.get("ejecuciones") or [])
    causas_c = asigna(ops, priv.get("cierres") or [])
    out = [f"FILTRA · mapa k={k} · {len(ops)} operaciones reconstruidas de las ejecuciones"]
    for c, n in sorted(causas_e.items()):
        out.append(f"  {c}: {n}")
    out.append(f"cierres: {len(priv.get('cierres') or [])} filas, sin asignar {sum(causas_c.values())}")
    for c, n in sorted(causas_c.items()):
        out.append(f"  sin asignar · {c}: {n}")
    validas, fuera = [], {}
    for o in ops:
        if o["fin"] is None:
            c = "abierta al final del fichero"
        elif not o["n_cierres"] or o["entrada"] <= 0:
            c = "sin filas de cierres asignadas"
        else:
            o["r"] = float(o["pnl"] / o["entrada"] * 100)
            o["estado"] = estado(o, k, est)
            validas.append(o)
            continue
        fuera[c] = fuera.get(c, 0) + 1
    out.append(f"operaciones medibles: {len(validas)}; no medibles {sum(fuera.values())}")
    for c, n in sorted(fuera.items()):
        out.append(f"  no medible · {c}: {n}")
    sin = {}
    for o in validas:
        if o["estado"].startswith("sin estado"):
            sin[o["estado"]] = sin.get(o["estado"], 0) + 1
    out.append(f"operaciones sin estado del mapa: {sum(sin.values())}")
    for c, n in sorted(sin.items()):
        out.append(f"  {c}: {n}")
    out.append("rendimiento = suma closedPnl / suma cumEntryValue, % del nocional; ic90 por remuestreo de semanas")
    out.append(linea("TOTAL (medibles)", validas))
    for g in ("A FAVOR", "EN CONTRA", "NEUTRO"):
        out.append(linea(g, [o for o in validas if o["estado"] == g]))
    for lado, nom in ((1, "largo"), (-1, "corto")):
        out.append(linea(f"lado {nom}", [o for o in validas if o["lado"] == lado]))
        for g in ("A FAVOR", "EN CONTRA", "NEUTRO"):
            out.append(linea(f"lado {nom} · {g}", [o for o in validas if o["lado"] == lado and o["estado"] == g]))
    for s in sorted({o["sim"] for o in validas if o["sim"] in est}):
        out.append(linea(f"activo {s}", [o for o in validas if o["sim"] == s]))
    fm = [o for o in validas if o["sim"] not in est]
    if fm:
        out.append(linea("activos fuera del mapa (juntos)", fm))
    con = [o for o in validas if o.get("rsi4h") is not None]
    out.append("preguntas extra (operaciones con estado y rsi4h):")
    for lado, nom, cond, txt in ((1, "largo", lambda x: x < 30, "rsi4h < 30"), (-1, "corto", lambda x: x > 70, "rsi4h > 70")):
        mio = [o for o in con if o["lado"] == lado]
        out.append(linea(f"{nom} con {txt}", [o for o in mio if cond(o["rsi4h"])]))
        out.append(linea(f"{nom} resto", [o for o in mio if not cond(o["rsi4h"])]))
    mapa = [o for o in validas if "S" in o]
    for o in mapa:
        o["v"] = o["lado"] * o["S"]
    out.append("por nivel de v = lado*S (operaciones con estado del mapa):")
    for nom, cond in NIVELES:
        out.append(linea(nom, [o for o in mapa if cond(o["v"])]))
    for lado, nom in ((1, "largo"), (-1, "corto")):
        for txt, cond in (NIVELES[0], NIVELES[-1]):
            out.append(linea(f"{nom} con {txt}", [o for o in mapa if o["lado"] == lado and cond(o["v"])]))
    out.append(spearman_linea([o["v"] for o in mapa], [o["r"] for o in mapa]))
    return out


NIVELES = (("v <= -2", lambda v: v <= -2), ("v = -1", lambda v: v == -1), ("v = 0", lambda v: v == 0),
           ("v = +1", lambda v: v == 1), ("v >= +2", lambda v: v >= 2))


def rangos(x: list[float]) -> list[float]:
    """Rangos 1..n; los empates reciben la media de los rangos que ocupan."""
    orden = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and x[orden[j + 1]] == x[orden[i]]:
            j += 1
        for t in range(i, j + 1):
            r[orden[t]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> float:
    """Pearson sobre rangos medios; nan si un lado no varia."""
    rx, ry = rangos(x), rangos(y)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx, syy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    return sxy / (sxx * syy) ** 0.5 if sxx and syy else float("nan")


def spearman_linea(v: list[float], r: list[float]) -> str:
    nombre = "spearman(v, rendimiento)"
    if len(v) < N_GRUPO:
        return f"  {nombre:<34} n={len(v)}"
    return f"  {nombre:<34} n={len(v)} rho={spearman(v, r):+.3f}"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("uso: python scripts/filtra.py PRIVADO scripts/filtra_estados.json")
        return 2
    with open(argv[1]) as f:
        priv = json.load(f)
    with open(argv[2]) as f:
        doc = json.load(f)
    print("\n".join(informe(priv, doc)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
