"""La CALIDAD del bot, en cifras deterministas: lo que hizo el precio despues de cada alerta y el acierto de las
evaluaciones contra como acabo cada posicion. Pura: las filas entran como argumentos (el bot las lee de su base; la tarea
semanal de 143, por bin/prodsql). La redaccion del informe semanal (Claude Max en 143) solo puede citar estas cifras.

LA REGLA DE BOT-1 (scripts/rafagas_estudio.py:131 y :241): desde el cierre del minuto de la rafaga (el precio al que
llega la alerta), (a) objetivo +2 % / stop -0.6 % A FAVOR de la rafaga -> «de verdad CASCADA» si toca el objetivo;
(c) objetivo +1.2 % / stop -0.6 % EN CONTRA -> «de verdad BARRIDO» si toca el objetivo; en 24 h; un minuto que toca los
dos cuenta como stop. ponytail: BOT-1 entra en el segundo 35 con medios minutos de aggTrades; aqui, velas de 1 min del
ohlcv de 140 y el cierre: mas grueso, y se dice. Ni (a) ni (c) en 24 h = FALSA ALARMA; sin 24 h de velas detras =
SIN CERRAR (no cuenta).
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

ESQUEMAS = {"a": (0.02, 0.006, 1), "c": (0.012, 0.006, -1)}
DIA = 1440


def desenlace(velas: dict[int, tuple], minuto: int, lado: int, tp: float, sl: float, sentido: int) -> str:
    """velas: {minuto: (alto, bajo, cierre)}. -> 'TP' | 'SL' | 'VENCE' (24 h sin tocar) | 'SIN CERRAR' (faltan velas)."""
    if minuto not in velas:
        return "SIN CERRAR"
    p, d = velas[minuto][2], lado * sentido
    obj, stp = p * (1 + d * tp), p * (1 - d * sl)
    for k in range(minuto + 1, minuto + DIA + 1):
        if k not in velas:
            return "SIN CERRAR"
        hi, lo, _ = velas[k]
        if (lo <= stp) if d > 0 else (hi >= stp):
            return "SL"
        if (hi >= obj) if d > 0 else (lo <= obj):
            return "TP"
    return "VENCE"


def resumen(alertas: list[dict], velas: dict[str, dict], evaluaciones: list[dict], operaciones: list[dict],
            llamadas: list[dict], partes: list[str], desde: int, hasta: int) -> dict:
    """alertas: [{activo, minuto, lado, clase}] (la rafaga con su clase); velas: {activo: {minuto: (alto, bajo, cierre)}};
    evaluaciones: los 'cierre' [{veredicto, acierto, pnl_usd}]; operaciones: [{pnl_usd}]; llamadas: [{dia, coste_usd,
    tope_usd}]; partes: los dias (AAAA-MM-DD) con parte; desde/hasta: minutos de la semana."""
    out: dict = {"desde": _dia(desde), "hasta": _dia(hasta - 1), "alertas": len(alertas),
                 "por_clase": dict(Counter(a["clase"] or "SIN CLASIFICAR" for a in alertas))}
    vistas = {"CASCADA": [0, 0], "BARRIDO": [0, 0]}  # [de verdad, juzgadas] de las que el bot llamo asi
    verdad, falsas, sin_cerrar = Counter(), Counter(), 0
    for a in alertas:
        v = velas.get(a["activo"]) or {}
        r = {k: desenlace(v, a["minuto"], a["lado"], *ESQUEMAS[k]) for k in ESQUEMAS}
        if "SIN CERRAR" in r.values():
            sin_cerrar += 1
            continue
        verdad["CASCADA"] += r["a"] == "TP"
        verdad["BARRIDO"] += r["c"] == "TP"
        if r["a"] != "TP" and r["c"] != "TP":
            falsas[_dia(a["minuto"])] += 1
        if a["clase"] in vistas:
            vistas[a["clase"]][1] += 1
            vistas[a["clase"]][0] += r["a" if a["clase"] == "CASCADA" else "c"] == "TP"
    # todos los dias que TOCA la ventana, el ultimo parcial incluido (antes: range(desde, hasta, DIA) se lo saltaba si la
    # ventana no empezaba a las 00:00Z: remate 3, bug 11)
    todos = sorted({_dia(m) for m in range(desde // DIA * DIA, hasta, DIA)} | ({_dia(hasta - 1)} if hasta > desde else set()))
    out["de_verdad"] = dict(verdad)
    out["falsas_alarmas"] = sum(falsas.values())
    out["falsas_por_dia"] = {d: falsas.get(d, 0) for d in todos}  # los dias sin ninguna, con 0: que no parezcan sin dato
    out["sin_cerrar"] = sin_cerrar
    out["clase_acertada"] = {k: f"{a} de {n}" for k, (a, n) in vistas.items()}
    puntuadas = [e for e in evaluaciones if e.get("acierto") is not None]
    out["evaluaciones"] = {"cerradas": len(evaluaciones), "puntuadas": len(puntuadas),
                           "aciertos": sum(1 for e in puntuadas if e["acierto"]),
                           "por_veredicto": {v: f"{sum(1 for e in puntuadas if e['veredicto'] == v and e['acierto'])} de "
                                                f"{sum(1 for e in puntuadas if e['veredicto'] == v)}" for v in ("A FAVOR", "EN CONTRA")}}
    pnl = [float(o["pnl_usd"]) for o in operaciones if o.get("pnl_usd") is not None]
    out["operaciones"] = {"cerradas": len(operaciones), "ganadoras": sum(1 for x in pnl if x > 0), "pnl_usd": round(sum(pnl), 2)}
    dias: dict = {}
    for ll in llamadas:
        g = dias.setdefault(str(ll["dia"]), [0.0, float(ll["tope_usd"])])
        g[0] += float(ll["coste_usd"])
        g[1] = min(g[1], float(ll["tope_usd"]))
    out["gasto"] = {d: f"{g:.2f} de {t:.2f}" for d, (g, t) in sorted(dias.items())}
    out["partes"] = f"{sum(1 for d in todos if d in partes)} de {len(todos)} dias"
    return out


def texto(r: dict) -> str:
    e, o = r["evaluaciones"], r["operaciones"]
    return "\n".join([
        f"SEMANA {r['desde']} .. {r['hasta']}",
        f"alertas {r['alertas']}: {', '.join(f'{k} {n}' for k, n in sorted(r['por_clase'].items())) or 'ninguna'}",
        f"lo que hizo el precio (regla de BOT-1, velas de 1 min): de verdad cascada {r['de_verdad'].get('CASCADA', 0)},"
        f" de verdad barrido {r['de_verdad'].get('BARRIDO', 0)}, falsas alarmas {r['falsas_alarmas']}"
        f" {r['falsas_por_dia'] or ''}, sin cerrar {r['sin_cerrar']}",
        f"la clase del bot acerto: CASCADA {r['clase_acertada']['CASCADA']}, BARRIDO {r['clase_acertada']['BARRIDO']}",
        f"evaluaciones cerradas {e['cerradas']}, puntuadas {e['puntuadas']}, aciertos {e['aciertos']}"
        f" (A FAVOR {e['por_veredicto']['A FAVOR']}, EN CONTRA {e['por_veredicto']['EN CONTRA']})",
        f"operaciones cerradas en Bybit {o['cerradas']}, ganadoras {o['ganadoras']}, pnl {o['pnl_usd']:+.2f} USD",
        f"gasto de la API por dia: {', '.join(f'{d} {g}' for d, g in r['gasto'].items()) or 'sin llamadas'}",
        f"partes diarios: {r['partes']} · avisos del interruptor: {r.get('avisos_del_interruptor', 'sin dato')}",
    ])


def _dia(minuto: int) -> str:
    return datetime.fromtimestamp(minuto * 60, UTC).strftime("%Y-%m-%d")
