"""EL MARCADOR del diario: por fuente, y cada fuente contra la rejilla de control en su mismo periodo.

  N = operaciones LLENADAS y CERRADAS (las caducadas sin llenar cuentan para la tasa de llenado, no para el R).
  Por fuente: propuestas, resueltas, llenadas, tasa de llenado, R medio y USD medio por operacion (con todo el coste),
  por activo y lado, peor racha (perdedoras seguidas por hora de salida) y caida maxima (de la suma de R, y en USD).
  CONTRA LA REJILLA: R medio de la fuente menos R medio de la rejilla, ambas con las operaciones selladas en los DIAS
  (UTC) del periodo de la fuente (de su primer sello a su ultimo); intervalo del 95 % remuestreando DIAS con
  reemplazo (pareado: el mismo dia entra con sus operaciones de las dos), B = 2000, semilla fija.
  «SIN N» con menos de 30 resueltas llenadas: las cifras se dan, pero no dicen nada todavia.
  INDECIDIBLES: las cerradas «indecidible» por un hueco de velas sin precio (resuelve.indecidible) no entran en
  resueltas, llenado ni R: se cuentan aparte. «con velas publicas»: resueltas con alguna vela del volcado publico.
El texto es corto, para el bot (/entradas): el diario NO da entradas ni avisa de nada.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import UTC, datetime

DIA, N_MIN, B, SEMILLA = 86400, 30, 2000, 20261115
ORDEN = ("regla:D:imp1:v0:A", "regla:H:imp6:v1:D", "fable", "rejilla")


def operaciones(filas: list[dict]) -> tuple[dict, dict]:
    """(propuestas por id, resultados por id) a partir de las filas del libro."""
    props = {f["id"]: f for f in filas if f["tipo"] == "propuesta"}
    res = {f["id"]: f for f in filas if f["tipo"] == "resultado"}
    return props, res


def _racha_caida(ops: list[dict]) -> tuple[int, float, float]:
    peor = racha = 0
    sr = su = pico_r = pico_u = 0.0
    caida_r = caida_u = 0.0
    for o in sorted(ops, key=lambda o: (o["t_salida"], o["id"])):
        racha = racha + 1 if o["r_neto"] < 0 else 0
        peor = max(peor, racha)
        sr, su = sr + o["r_neto"], su + o["usd_neto"]
        pico_r, pico_u = max(pico_r, sr), max(pico_u, su)
        caida_r, caida_u = max(caida_r, pico_r - sr), max(caida_u, pico_u - su)
    return peor, round(caida_r, 4), round(caida_u, 4)


def _dia(o: dict) -> int:
    return o["sello"] // DIA


def contra_rejilla(ops: list[dict], rej: list[dict]) -> dict | None:
    """Diferencia de R medio contra la rejilla en los dias del periodo de la fuente, con su intervalo por dias."""
    if not ops:
        return None
    d0, d1 = min(map(_dia, ops)), max(map(_dia, ops))
    rej = [o for o in rej if d0 <= _dia(o) <= d1]
    if not rej:
        return {"dias": d1 - d0 + 1, "n_rejilla": 0, "dif": None, "ic": None}
    por_f, por_r = defaultdict(list), defaultdict(list)
    for o in ops:
        por_f[_dia(o)].append(o["r_neto"])
    for o in rej:
        por_r[_dia(o)].append(o["r_neto"])
    dias = sorted(set(por_f) | set(por_r))
    media = lambda xs: sum(xs) / len(xs)  # noqa: E731
    dif = media([r for d in dias for r in por_f[d]]) - media([r for d in dias for r in por_r[d]])
    az, difs = random.Random(SEMILLA), []
    for _ in range(B):
        m = [az.choice(dias) for _ in dias]
        f = [r for d in m for r in por_f[d]]
        g = [r for d in m for r in por_r[d]]
        if f and g:
            difs.append(media(f) - media(g))
    difs.sort()
    ic = (round(difs[int(0.025 * len(difs))], 4), round(difs[int(0.975 * len(difs)) - 1], 4)) if difs else None
    return {"dias": d1 - d0 + 1, "n_rejilla": len(rej), "dif": round(dif, 4), "ic": ic}


def calcula(filas: list[dict]) -> dict:
    props, res = operaciones(filas)
    fuentes = defaultdict(lambda: {"propuestas": 0, "resueltas": 0, "indecidibles": 0, "con_publicas": 0, "ops": []})
    for i, p in props.items():
        x = fuentes[p["fuente"]]
        x["propuestas"] += 1
        r = res.get(i)
        if r is None:
            continue
        if r["salida"] == "indecidible":
            x["indecidibles"] += 1
            continue
        x["resueltas"] += 1
        x["con_publicas"] += bool(r.get("velas_publicas"))
        if r["llenada"]:
            x["ops"].append({**r, "sello": p["sello"], "activo": p["activo"], "lado": p["lado"]})
    rechazos = defaultdict(int)
    for f in filas:
        if f["tipo"] == "rechazo":
            rechazos[f["fuente"]] += 1
    out = {}
    rej = fuentes["rejilla"]["ops"] if "rejilla" in fuentes else []
    for f in sorted(fuentes, key=lambda k: (ORDEN.index(k) if k in ORDEN else 99, k)):
        x, ops = fuentes[f], fuentes[f]["ops"]
        n = len(ops)
        peor, caida_r, caida_u = _racha_caida(ops)
        al = defaultdict(list)
        for o in ops:
            al[(o["activo"], o["lado"])].append(o["r_neto"])
        out[f] = {"propuestas": x["propuestas"], "resueltas": x["resueltas"], "llenadas": n,
                  "pendientes": x["propuestas"] - x["resueltas"] - x["indecidibles"], "rechazos": rechazos.get(f, 0),
                  "indecidibles": x["indecidibles"], "con_publicas": x["con_publicas"],
                  "tasa_llenado": round(n / x["resueltas"], 4) if x["resueltas"] else None,
                  "r_medio": round(sum(o["r_neto"] for o in ops) / n, 4) if n else None,
                  "usd_medio": round(sum(o["usd_neto"] for o in ops) / n, 4) if n else None,
                  "usd_total": round(sum(o["usd_neto"] for o in ops), 4),
                  "por_activo_lado": {f"{a} {lado}": (len(v), round(sum(v) / len(v), 4)) for (a, lado), v in sorted(al.items())},
                  "peor_racha": peor, "caida_r": caida_r, "caida_usd": caida_u, "sin_n": n < N_MIN,
                  "contra_rejilla": contra_rejilla(ops, rej) if f != "rejilla" else None}
    if rechazos.get("fable") and "fable" not in out:
        out["fable"] = {"propuestas": 0, "resueltas": 0, "llenadas": 0, "pendientes": 0, "rechazos": rechazos["fable"],
                        "sin_n": True}
    return out


def _f(x, fmt: str = "+.2f") -> str:
    return "-" if x is None else format(x, fmt)


def texto(filas: list[dict], cabeza: dict, ahora: int, huecos: list[str] | None = None) -> str:
    m = calcula(filas)
    h = datetime.fromtimestamp(ahora, UTC).strftime("%Y-%m-%d %H:%MZ")
    out = [f"DIARIO DE ENTRADAS en sombra ({h}; 5 USD de riesgo; el bot NO da entradas) · libro n={cabeza['n']} "
           f"sha256 {cabeza['sha256'][:16]}"]
    if not m:
        out.append("sin propuestas todavia")
    for f, x in m.items():
        cab = f"{f}: {x['propuestas']} propuestas, {x['resueltas']} resueltas, {x['llenadas']} llenadas"
        if x.get("rechazos"):
            cab += f", {x['rechazos']} rechazadas"
        if x.get("indecidibles"):
            cab += f", {x['indecidibles']} indecidibles por hueco (aparte)"
        if x.get("con_publicas"):
            cab += f", {x['con_publicas']} con velas publicas"
        if x.get("tasa_llenado") is not None:
            cab += f" (llenado {x['tasa_llenado']:.0%})"
        if x["sin_n"]:
            cab += f" · SIN N ({x['llenadas']}/{N_MIN})"
        out.append(cab)
        if not x.get("llenadas"):
            continue
        lin = (f"  R medio {_f(x['r_medio'])} · {_f(x['usd_medio'])} USD/op · total {_f(x['usd_total'])} USD · peor racha "
               f"{x['peor_racha']} · caida {x['caida_r']:.2f} R / {x['caida_usd']:.2f} USD")
        c = x.get("contra_rejilla")
        if c and c["dif"] is not None:
            ic = f" [{c['ic'][0]:+.2f}, {c['ic'][1]:+.2f}]" if c["ic"] else ""
            lin += f" · contra la rejilla {c['dif']:+.2f} R{ic} ({c['dias']} d, {c['n_rejilla']} de rejilla)"
        elif c:
            lin += f" · contra la rejilla: sin rejilla llenada en sus {c['dias']} d"
        out.append(lin)
        out.append("  " + " · ".join(f"{k} {n}x{r:+.2f}" for k, (n, r) in x["por_activo_lado"].items()))
    if huecos:
        out.append(f"PENDIENTES por hueco de velas: {len(huecos)} ({'; '.join(huecos[:3])})")
    return "\n".join(out)
