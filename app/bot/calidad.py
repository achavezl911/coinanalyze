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

import json
import math
from collections import Counter
from datetime import UTC, datetime
from typing import Any

ESQUEMAS = {"a": (0.02, 0.006, 1), "c": (0.012, 0.006, -1)}
DIA = 1440
PARTE_HORA_UTC = 13  # 07:00 en America/Mexico_City (UTC-6, la zona de 140 y 143): el parte, antes de que abra Europa


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
            llamadas: list[dict], partes: list[str], desde: int, hasta: int, vidas: list[dict] | None = None,
            a_mano: dict | None = None) -> dict:
    """alertas: [{activo, minuto, lado, clase}] (la rafaga con su clase); velas: {activo: {minuto: (alto, bajo, cierre)}};
    evaluaciones: los 'cierre' [{veredicto, acierto, pnl_usd}]; operaciones: [{pnl_usd}]; llamadas: [{dia, coste_usd,
    tope_usd}]; partes: los dias (AAAA-MM-DD) con parte; desde/hasta: minutos de la semana. vidas / a_mano: la MEDICION
    de AUDITOR R2 (las filas de `vida()`, acumuladas: ver `medicion`); sin vidas, el informe no la trae."""
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
    # solo los dias cuyo parte TOCABA dentro de la ventana (a las PARTE_HORA_UTC): el de hoy no cuenta hasta su hora, ni
    # el del primer dia si la ventana empieza despues (remate 4, R8: un /informe a las 10:00Z decia «7 de 8»)
    tocaban = [d for d in todos if desde <= _minuto(d) + PARTE_HORA_UTC * 60 < hasta]
    out["partes"] = f"{sum(1 for d in tocaban if d in partes)} de {len(tocaban)} dias"
    if vidas is not None:
        out["medicion"] = medicion(vidas, a_mano)
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
    ] + (texto_medicion(r["medicion"]) if "medicion" in r else []))


def _dia(minuto: int) -> str:
    return datetime.fromtimestamp(minuto * 60, UTC).strftime("%Y-%m-%d")


def _minuto(dia: str) -> int:
    return int(datetime.strptime(dia, "%Y-%m-%d").replace(tzinfo=UTC).timestamp()) // 60


# ---------------------------------------------------------------------------------------------------------------------
# AUDITOR R2 (seccion 6 del encargo del dueno, 20261122): A QUIEN CREERLE. Al cierre se califican Opus, DECIDE y el R
# (pnl_usd / la perdida al stop que calculo A6 al abrir) en la fila 'cierre' NUEVA (detalle.medicion; la tabla es solo
# anadir). Las vidas de antes de R2 se recalifican AQUI, en la consulta, con lo que su fila 'veredicto' guardo al abrir.
# Lecturas solo en n = 30, 60 y 120 (antes: SIN CALIBRAR, como el reglamento); la regla sellada, a las 60 pareadas.

MEDICION = "auditor-r2"
CON_LADO = ("A FAVOR", "EN CONTRA")
MINIMO = 30
LECTURAS = (30, 60, 120)
PAREADAS = 60  # la regla sellada (entregas/*-auditor-prediccion.md)
Z95 = 1.959963984540054
FUENTES = ("OPUS", "DECIDE", "SIEMPRE A FAVOR")
ESTADOS_AUDITOR = ("APROBADO", "CON RESERVAS", "RECHAZADO", "NO EVALUABLE", "SIN AUDITOR")
# las vidas de `vida()`, ACUMULADAS hasta $1 (minuto), en orden de su primer cierre: la ULTIMA cifra de cada una (una
# CORRECCION es otra fila 'cierre'), su primer veredicto automatico (lo que se sabia al abrir) y el coste de su llamada
SQL_VIDAS = (
    "SELECT c.posicion, c.pnl_usd, c.detalle->'medicion' medicion, coalesce(v.veredicto, c.veredicto) veredicto,"
    " v.detalle->>'fuente' fuente, coalesce(v.veredicto_decide, c.veredicto_decide) veredicto_decide,"
    " v.detalle->'auditor' auditor, coalesce(c.detalle->'medicion'->>'llamada', v.detalle->>'llamada') llamada, l.coste_usd"
    " FROM (SELECT DISTINCT ON (posicion) posicion, veredicto, veredicto_decide, pnl_usd, detalle FROM bot_evaluacion"
    " WHERE tipo = 'cierre' AND ts < to_timestamp($1::bigint * 60) ORDER BY posicion, ts DESC) c"
    " JOIN (SELECT posicion, min(ts) t0 FROM bot_evaluacion WHERE tipo = 'cierre' GROUP BY posicion) f USING (posicion)"
    " LEFT JOIN LATERAL (SELECT veredicto, veredicto_decide, detalle FROM bot_evaluacion e WHERE e.tipo = 'veredicto'"
    " AND e.posicion = c.posicion AND e.detalle->>'motivo' LIKE 'posicion nueva%' ORDER BY e.ts LIMIT 1) v ON true"
    " LEFT JOIN bot_llamada l ON l.id::text = coalesce(c.detalle->'medicion'->>'llamada', v.detalle->>'llamada')"
    " ORDER BY f.t0, c.posicion")
# las evaluaciones no automaticas (/evalua, rafaga...) de [$1, $2) minutos: se reportan aparte, sin calificar
SQL_A_MANO = (
    "SELECT veredicto, count(*)::int FROM bot_evaluacion WHERE tipo = 'veredicto'"
    " AND coalesce(detalle->>'motivo', '') NOT LIKE 'posicion nueva%'"
    " AND ts >= to_timestamp($1::bigint * 60) AND ts < to_timestamp($2::bigint * 60) GROUP BY 1")


def wilson(aciertos: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Intervalo de Wilson de una proporcion (95 % por omision). Sin muestra, None."""
    if n <= 0:
        return None
    p, z2 = aciertos / n, z * z
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    ancho = z * ((p * (1 - p) + z2 / (4 * n)) / n) ** 0.5 / (1 + z2 / n)
    return max(0.0, centro - ancho), min(1.0, centro + ancho)


def signos(b: int, c: int) -> float:
    """Prueba de signos exacta, bilateral: p de ver un reparto tan desigual como b contra c si las dos fuentes valen lo
    mismo (binomial n = b + c, 1/2). Sin casos discordantes, 1."""
    n = b + c
    if n == 0:
        return 1.0
    cola = sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * cola)


def apertura(veredicto: str | None, fuente: str | None, veredicto_decide: str | None, auditor: Any,
             llamada: str | None = None) -> dict:
    """Lo que se sabia AL ABRIR, de la fila 'veredicto' (o de la memoria del bot): el veredicto de Opus (si el registrado
    salio de DECIDE porque Opus cayo, Opus no fue evaluable; sin `fuente` -filas viejas- el registrado es el de Opus, como
    lo puntuaba el informe), el de DECIDE, el estado del auditor y la perdida al stop de A6."""
    if isinstance(auditor, str):
        auditor = json.loads(auditor)
    opus = veredicto if fuente in (None, "opus") and veredicto in CON_LADO else "NO EVALUABLE"
    ap: dict = {"opus": opus, "decide": veredicto_decide if veredicto_decide in CON_LADO else "NO EVALUABLE",
                "auditor": None, "perdida_stop": None, "sin_r": None, "llamada": llamada}
    if not isinstance(auditor, dict) or not auditor.get("estado"):
        ap["sin_r"] = "sin auditor al abrir (vida anterior a auditor-r1): R no se calcula"
        return ap
    ap["auditor"] = auditor["estado"]
    a6 = next((c for c in auditor.get("compuertas") or [] if isinstance(c, dict) and c.get("nombre") == "A6"), None)
    valor = a6.get("valor") if a6 else None
    if a6 is None:
        ap["sin_r"] = f"el auditor no corrio A6 ({str(auditor.get('razon'))[:120]}): R no se calcula"
    elif a6.get("severidad") == "NO_APLICABLE":
        ap["sin_r"] = "sin stop al abrir: R no se calcula"
    elif not isinstance(valor, (int, float)) or isinstance(valor, bool) or not math.isfinite(valor):
        ap["sin_r"] = f"A6 sin cifra ({a6.get('severidad')}: {str(a6.get('razon'))[:120]}): R no se calcula"
    elif valor <= 0:
        ap["sin_r"] = f"stop en ganancia al abrir (perdida al stop {valor:.2f} USD): sin riesgo, R no se calcula"
    else:
        ap["perdida_stop"] = float(valor)
    return ap


def acierta(veredicto: str | None, pnl: float | None) -> bool | None:
    """La regla de siempre (cierre de R1): (pnl > 0) == A FAVOR; NO EVALUABLE o sin pnl no se califica."""
    return None if veredicto not in CON_LADO or pnl is None else (pnl > 0) == (veredicto == "A FAVOR")


def mide(ap: dict, pnl: float | None) -> dict:
    """La medicion de una vida cerrada: lo de la apertura mas el acierto de Opus y de DECIDE y el R."""
    r = None if pnl is None or ap.get("perdida_stop") is None else round(pnl / ap["perdida_stop"], 4)
    sin_r = None if r is not None else (ap.get("sin_r") or "sin pnl: R no se calcula")
    return {"version": MEDICION, "opus": ap.get("opus", "NO EVALUABLE"), "decide": ap.get("decide", "NO EVALUABLE"),
            "auditor": ap.get("auditor"), "perdida_stop": ap.get("perdida_stop"), "llamada": ap.get("llamada"),
            "acierto_opus": acierta(ap.get("opus"), pnl), "acierto_decide": acierta(ap.get("decide"), pnl),
            "pnl_usd": pnl, "r": r, "sin_r": sin_r}


def linea_cierre(m: dict) -> str:
    """La segunda linea de la CERRADA (y de la CORRECCION): las otras dos fuentes y el R."""
    def nota(v: str, a: bool | None) -> str:
        return f"{v} -> {'sin puntuar' if a is None else ('ACIERTO' if a else 'FALLO')}"
    r = f"R {m['r']:+.2f}" if m.get("r") is not None else str(m.get("sin_r"))
    return (f"MEDICION: OPUS {nota(m['opus'], m['acierto_opus'])} · DECIDE {nota(m['decide'], m['acierto_decide'])}"
            f" · AUDITOR al abrir {m.get('auditor') or 'sin auditor'} · {r}")


def vida(fila: dict) -> dict:
    """Una vida del informe: la `medicion` que escribio su cierre si la tiene (R2) y, si no, recalificada aqui con lo que
    guardo su fila 'veredicto' (sin tocar la base). fila: {pnl_usd, medicion, veredicto, fuente, veredicto_decide,
    auditor, llamada, coste_usd}."""
    m = fila.get("medicion")
    if isinstance(m, str):
        m = json.loads(m)
    if isinstance(m, dict) and m.get("version"):
        out = dict(m, recalificada=False)
    else:
        ap = apertura(fila.get("veredicto"), fila.get("fuente"), fila.get("veredicto_decide"), fila.get("auditor"),
                      fila.get("llamada"))
        out = dict(mide(ap, fila.get("pnl_usd")), recalificada=True)
    c = fila.get("coste_usd")
    out["coste_usd"] = float(c) if c is not None else None
    return out


def _media(xs: list[float]) -> tuple[float, int] | None:
    return (round(sum(xs) / len(xs), 4), len(xs)) if xs else None


def _corte(n: int) -> int | None:
    """La lectura que toca con n: la mayor de 30, 60 y 120 ya alcanzada, sobre las PRIMERAS en orden de cierre."""
    return max((k for k in LECTURAS if k <= n), default=None)


def _sin_calibrar(n: int) -> str:
    return f"SIN CALIBRAR · MUESTRA INSUFICIENTE ({n}/{MINIMO})"


def _fuente(vidas: list[dict], nombre: str) -> dict:
    if nombre == "SIEMPRE A FAVOR":
        muestra = [(v, v["pnl_usd"] > 0, "A FAVOR") for v in vidas if v.get("pnl_usd") is not None]
    else:
        k = nombre.lower()
        muestra = [(v, v[f"acierto_{k}"], v[k]) for v in vidas if v.get(f"acierto_{k}") is not None]
    out: dict = {"n": len(muestra)}
    corte = _corte(len(muestra))
    if corte is None:
        return out | {"estado": _sin_calibrar(len(muestra))}
    leida = muestra[:corte]
    a = sum(1 for _, ok, _ in leida if ok)
    w = wilson(a, corte)
    r = {d: _media([v["r"] for v, _, dijo in leida if dijo == d and v.get("r") is not None]) for d in CON_LADO}
    out |= {"estado": f"LECTURA EN n={corte}", "lectura_en": corte, "aciertos": a, "tasa": round(a / corte, 4),
            "wilson": [round(w[0], 4), round(w[1], 4)], "r_a_favor": r["A FAVOR"], "r_en_contra": r["EN CONTRA"]}
    if nombre != "SIEMPRE A FAVOR":  # «siempre A FAVOR» en ESTAS vidas: si el intervalo no la deja abajo, no aporta
        base = sum(1 for v, _, _ in leida if v["pnl_usd"] > 0) / corte
        out |= {"base_mismas_vidas": round(base, 4), "le_gana_a_la_base": w[0] > base}
    return out


def _cuenta(xs: list[dict]) -> dict:
    b = sum(1 for v in xs if v["acierto_opus"] and not v["acierto_decide"])
    c = sum(1 for v in xs if v["acierto_decide"] and not v["acierto_opus"])
    n, w = len(xs), wilson(b, b + c)
    # la diferencia de aciertos (Opus - DECIDE) = (b - c) / n; su intervalo, condicionado a los b + c discordantes: el de
    # Wilson de b / (b + c), llevado a la escala de n. Sin discordantes, 0 exacto (incluye 0).
    lo, hi = ((b + c) / n * (2 * w[0] - 1), (b + c) / n * (2 * w[1] - 1)) if w else (0.0, 0.0)
    return {"difieren": b + c, "acierta_opus": b, "acierta_decide": c, "p_signos": round(signos(b, c), 4),
            "diferencia": round((b - c) / n, 4) if n else 0.0, "intervalo": [round(lo, 4), round(hi, 4)]}


def _pareada(vidas: list[dict]) -> dict:
    muestra = [v for v in vidas if v.get("acierto_opus") is not None and v.get("acierto_decide") is not None]
    out: dict = {"n": len(muestra)}
    corte = _corte(len(muestra))
    out |= ({"estado": _sin_calibrar(len(muestra))} if corte is None
            else {"estado": f"LECTURA EN n={corte}", "lectura_en": corte} | _cuenta(muestra[:corte]))
    if len(muestra) < PAREADAS:
        out["regla"] = f"REGLA SELLADA: {len(muestra)}/{PAREADAS} vidas pareadas, sin lectura"
        return out
    out["supera"] = _cuenta(muestra[:PAREADAS])["intervalo"][0] > 0
    out["regla"] = ("REGLA SELLADA (60 pareadas): Opus SUPERA a DECIDE (el intervalo de la diferencia queda por encima de 0)"
                    if out["supera"] else "REGLA SELLADA (60 pareadas): Opus NO supera a DECIDE (el intervalo de la diferencia"
                    " incluye 0 o es negativo): el dueno evalua apagar la evaluacion de Opus; la decision es suya")
    return out


def _auditor(vidas: list[dict]) -> dict:
    """El auditor tambien se mide: por su estado al abrir, la tasa de ganadoras y el R medio. Las RECHAZADAS por A5 (sin
    stop) no tienen R: por eso tambien la tasa de ganadoras, que no necesita stop."""
    out: dict = {}
    for e in ESTADOS_AUDITOR:
        g = [v for v in vidas if (v.get("auditor") or "SIN AUDITOR") == e and v.get("pnl_usd") is not None]
        d: dict = {"n": len(g), "con_r": sum(1 for v in g if v.get("r") is not None)}
        corte = _corte(len(g))
        if corte is None:
            d["estado"] = _sin_calibrar(len(g))
        else:
            leida = g[:corte]
            a = sum(1 for v in leida if v["pnl_usd"] > 0)
            w = wilson(a, corte)
            d |= {"estado": f"LECTURA EN n={corte}", "lectura_en": corte, "ganadoras": a,
                  "wilson": [round(w[0], 4), round(w[1], 4)], "r_medio": _media([v["r"] for v in leida if v.get("r") is not None])}
        out[e] = d
    ap, re_ = out["APROBADO"], out["RECHAZADO"]
    if ap.get("r_medio") and re_.get("r_medio") and min(ap["r_medio"][1], re_["r_medio"][1]) >= MINIMO:
        out["distingue"] = re_["r_medio"][0] < ap["r_medio"][0]
        out["veredicto"] = ("las RECHAZADAS salen peor en R que las APROBADAS" if out["distingue"] else
                            "las RECHAZADAS NO salen peor en R que las APROBADAS: sus compuertas no distinguen y se revisan")
    else:
        out["veredicto"] = "auditor sin lectura: APROBADAS y RECHAZADAS necesitan cada una 30 vidas con R"
    return out


def medicion(vidas: list[dict], a_mano: dict | None = None) -> dict:
    """vidas: las de `vida()`, en orden de cierre (la primera cerrada, primero), ACUMULADAS desde el principio (una lectura
    en n fija no puede ser de una semana). a_mano: {veredicto: n} de las evaluaciones no automaticas (/evalua...) de la
    semana, que no se califican."""
    evaluadas = [v for v in vidas if v.get("acierto_opus") is not None]
    coste = sum(v["coste_usd"] for v in vidas if v.get("coste_usd") is not None)
    return {"vidas": len(vidas), "recalificadas": sum(1 for v in vidas if v.get("recalificada")),
            "fuentes": {f: _fuente(vidas, f) for f in FUENTES}, "pareada": _pareada(vidas),
            "coste_opus": {"usd": round(coste, 4), "vidas_evaluadas": len(evaluadas),
                           "por_vida_evaluada": round(coste / len(evaluadas), 4) if evaluadas else None},
            "auditor": _auditor(vidas), "a_mano": dict(a_mano or {})}


def _pct(x: float) -> str:
    return f"{100 * x:.1f} %"


def _r(m: tuple | list | None) -> str:
    return f"{m[0]:+.2f} R (n {m[1]})" if m else "sin R"


def texto_medicion(m: dict) -> list[str]:
    lineas = [f"MEDICION (acumulada; primer veredicto automatico de cada vida: {m['vidas']} cerradas, {m['recalificadas']}"
              " recalificadas en la consulta; lecturas solo en n = 30, 60 y 120):"]
    for f in FUENTES:
        d, nombre = m["fuentes"][f], f + (" (linea base)" if f == "SIEMPRE A FAVOR" else "")
        if "lectura_en" not in d:
            lineas.append(f"  {nombre}: {d['estado']}")
            continue
        s = (f"  {nombre} lectura en n={d['lectura_en']} (de {d['n']}): acierto {d['aciertos']}/{d['lectura_en']} ="
             f" {_pct(d['tasa'])} [IC95 {_pct(d['wilson'][0])} .. {_pct(d['wilson'][1])}],"
             f" R medio A FAVOR {_r(d['r_a_favor'])} · EN CONTRA {_r(d['r_en_contra'])}")
        if "base_mismas_vidas" in d:
            s += (f" · base en las mismas vidas {_pct(d['base_mismas_vidas'])}: "
                  + ("LE GANA" if d["le_gana_a_la_base"] else "NO LE GANA A LA BASE, no aporta"))
        lineas.append(s)
    p = m["pareada"]
    lineas.append(f"  OPUS vs DECIDE pareadas: {p['estado']}" if "lectura_en" not in p else
                  f"  OPUS vs DECIDE pareadas, lectura en n={p['lectura_en']} (de {p['n']}): difieren {p['difieren']},"
                  f" acierta Opus {p['acierta_opus']}, acierta DECIDE {p['acierta_decide']}, prueba de signos"
                  f" p={p['p_signos']:.3f}, diferencia {p['diferencia']:+.3f} [{p['intervalo'][0]:+.3f} .. {p['intervalo'][1]:+.3f}]")
    lineas.append(f"  {p['regla']}")
    c = m["coste_opus"]
    lineas.append(f"  coste de Opus: {c['usd']:.2f} USD, {c['vidas_evaluadas']} vidas evaluadas -> "
                  + (f"{c['por_vida_evaluada']:.2f} USD por vida evaluada" if c["por_vida_evaluada"] is not None else "sin vidas evaluadas"))
    a, partes = m["auditor"], []
    for e in ESTADOS_AUDITOR:
        d = a[e]
        if d["n"]:
            partes.append(f"{e} {d['estado']}" if "lectura_en" not in d else
                          f"{e} ganadoras {d['ganadoras']}/{d['lectura_en']}, {_r(d['r_medio'])}")
    lineas.append(f"  AUDITOR al abrir: {' · '.join(partes) or 'sin vidas'}")
    lineas.append(f"  {a['veredicto']}")
    am = m["a_mano"]
    lineas.append(f"  evaluaciones no automaticas de la semana (/evalua; no se califican): {sum(am.values())}"
                  + (f" ({', '.join(f'{k} {n}' for k, n in sorted(am.items()))})" if am else ""))
    return lineas
