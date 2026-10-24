"""C1 · el centinela: el detector de BOT-1 (app/rafagas.py) sobre el ohlcv 1min de 140, BTC/ETH/SOL siempre.

Umbral de ALERTA z = 4 (el ataque del operador sobre la muestra de BOT-1: ve la cascada del 10-20 en los tres activos
y ETH 15:13Z; con z = 7 no ve nada); el resto, los umbrales congelados de BOT-1. Clasificacion en 1-3 min sin
liquidaciones (BOT1.prueba en hechos.tsv: con liquidaciones da lo mismo).

Reproducible: cada dia UTC se detecta sobre [dia - CALIENTA, dia + 1440 + DECIDE) y cuentan las rafagas con minuto
dentro del dia. Como detecta() solo mira hacia atras, el bot en vivo (que ve un prefijo del dia) y K117 (que rehace el
dia entero) dan lo mismo sobre las mismas velas. Un minuto sin fila: el cierre anterior y volumen 0.
"""

from __future__ import annotations

import dataclasses

import app.rafagas as rf

ACTIVOS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SIMBOLO = {a: f"{a}_PERP.A" for a in ACTIVOS}
UMBRALES = dataclasses.replace(rf.UMBRALES, Z=4.0)
CALIENTA = 180
SQL_VELAS = """
SELECT split_part(symbol, '_', 1), (extract(epoch FROM ts)::bigint / 60)::int, high, low, close, buy_volume,
       volume - buy_volume
  FROM ohlcv
 WHERE interval = '1min' AND symbol = ANY($1::text[])
   AND ts >= to_timestamp($2::bigint * 60) AND ts < to_timestamp($3::bigint * 60)
"""
STOP_CERCA = 0.7  # recorrido de la entrada al stop que dispara la alerta
LIQ_CERCA_PCT = 0.5
LEYENDA = "ALERTA, no entrada · sin ventaja medida tras una rafaga (BOT-1)"


def series(filas: dict, t0: int, t1: int) -> dict[str, rf.Serie] | None:
    """filas: {activo: {minuto: (hi, lo, c, buy, sell)}} -> una Serie por activo en [t0, t1), o None si falta uno."""
    out = {}
    for a in ACTIVOS:
        f = filas.get(a) or {}
        dentro = [m for m in f if t0 <= m < t1]
        if not dentro:
            return None
        previo = f[min(dentro)][2]
        hi, lo, c, buy, sell = cols = ([], [], [], [], [])
        for m in range(t0, t1):
            x = f.get(m) or (previo, previo, previo, 0.0, 0.0)
            previo = x[2]
            for col, y in zip(cols, x, strict=True):
                col.append(y)
        out[a] = rf.Serie(t0, c, hi, lo, buy, sell)
    return out


def rafagas_del_dia(filas: dict, dia: int, hasta: int, u: rf.Umbrales = UMBRALES) -> list[dict]:
    """Las rafagas con minuto en [dia, min(dia + 1440, hasta)), con su clase si ya hay DECIDE velas detras (si no,
    clase None). dia: minuto de las 00:00Z; hasta: el primer minuto que no tienen cerrado los tres activos."""
    t0, t1 = dia - CALIENTA, min(hasta, dia + 1440 + u.DECIDE)
    se = series(filas, t0, t1)
    if se is None:
        return []
    rasgos = {a: rf.rasgos(se[a], u.W, u.BASE) for a in ACTIVOS}
    out = []
    for a in ACTIVOS:
        z, v, imb = rasgos[a]
        for i, s in rf.detecta_rasgos(z, v, imb, u.Z, u.M, u.D, u.CALLA):
            if not dia <= t0 + i < dia + 1440:
                continue
            cl = rf.clasifica(se[a], i, s, u, [rasgos[o][0] for o in ACTIVOS if o != a])
            out.append({"activo": a, "minuto": t0 + i, "lado": s, "z": z[i], "v": v[i], "imb": imb[i],
                        "precio": se[a].c[i], "clase": cl[0] if cl else None, "clase_min": cl[1] if cl else None})
    return out


def alertas_posicion(p: dict) -> list[tuple[str, str]]:
    """(tipo, texto) para una posicion abierta: sin stop, stop cerca (>= 70 % del camino) o liquidacion cerca."""
    out, e, m, lado = [], p["entrada"], p["marca"], p["lado"]
    if not p.get("stop"):
        out.append(("sin_stop", f"{p['symbol']} sin stop puesto"))
    elif e and m and (e - p["stop"]) * lado > 0 and (e - m) / (e - p["stop"]) >= STOP_CERCA:
        out.append(("stop", f"{p['symbol']} a {(m / p['stop'] - 1) * 100 * lado:+.2f} % del stop ({p['stop']:g}), marca {m:g}"))
    liq = p.get("liquidacion")
    if liq and m and abs(m / liq - 1) * 100 < LIQ_CERCA_PCT:
        out.append(("liquidacion", f"{p['symbol']} a {abs(m / liq - 1) * 100:.2f} % de la liquidacion ({liq:g})"))
    return out


def texto_rafaga(r: dict) -> str:
    sentido = "ALCISTA" if r["lado"] > 0 else "BAJISTA"
    return (f"{r['activo'][:-4]} rafaga {sentido} {_hhmm(r['minuto'])} z={r['z']:+.2f} vol x{r['v']:.1f}"
            f" desequilibrio {r['imb']:+.2f} · {r['precio']:g}\n{LEYENDA}")


def texto_clase(r: dict) -> str:
    return f"{r['activo'][:-4]} {_hhmm(r['minuto'])} -> {r['clase']} (1-3 min)\n{LEYENDA}"


def _hhmm(minuto: int) -> str:
    return f"{minuto // 60 % 24:02d}:{minuto % 60:02d}Z"
