"""LA RESOLUCION: una propuesta sellada contra las velas de 5 min de 140 (binance perpetuo, /api/ohlcv). Sola y sin juicio.

  PRIMERA VELA QUE CUENTA: la que EMPIEZA en la primera marca de 5 min estrictamente posterior al sello. Nada anterior
    al sello entra nunca (por eso una entrada sellada no puede saber su precio).
  MERCADO: se llena a la APERTURA de esa vela; esa misma vela ya cuenta para stop y objetivo. Su `entrada` es solo la
    referencia del sello (stop y objetivo son niveles fijos calculados sobre ella); d sale del precio LLENADO.
  LIMITE: se llena AL NIVEL cuando una vela lo toca (largo: minimo <= nivel; corto: maximo >= nivel), aunque abra mas
    alla (conservador: no se apunta la mejora). En la vela del llenado cuenta el stop, NO el objetivo (no se sabe si el
    objetivo fue antes o despues del llenado). Sin llenar al llegar `caduca` -> «caducada», R 0.
  DESPUES: la primera vela que toca el stop o el objetivo; si toca los dos, gana el stop. Si una vela ABRE mas alla del
    stop, se sale a su apertura. Al cumplirse `plazo_s` desde el llenado, salida al cierre de esa vela («plazo»).
  COSTE (en fraccion del nominal de entrada): entrada limite 2 pb (maker), entrada a mercado 5.5 pb y TODA salida 5.5 pb
    (taker); el stop se sirve 10 pb peor que su nivel (o que la apertura); funding 1 pb por cada sello de 8 h (0, 8, 16Z)
    entre la vela del llenado y el fin de la vela de salida, SIEMPRE en contra (el real no se lee: cota declarada).
  R neto = neto / d, con d = |entrada - stop| / entrada (1 R bruto = el stop, como en fable-be). USD neto = neto x
    nominal, nominal = riesgo / (d + 10 pb + com. entrada + 5.5 pb): un stop limpio pierde ~ el riesgo con todo.
  HUECO: si falta una vela del camino y hay velas posteriores, la propuesta queda PENDIENTE y se dice desde que vela.
    Nunca se resuelve con datos que faltan; si las velas no han llegado aun, PENDIENTE sin hueco.
"""
from __future__ import annotations

PASO, SELLO_FUNDING = 300, 28800
COM_MAKER, COM_TAKER, SLIP_STOP, FUNDING = 0.0002, 0.00055, 0.0010, 0.0001


def primera_vela(sello: int) -> int:
    return (sello // PASO + 1) * PASO


def resuelve(p: dict, velas: dict, ahora: int) -> dict:
    """velas: {inicio: (apertura, maximo, minimo, cierre)} de 5 min. Devuelve {'estado': 'resuelta', 'resultado': {...}}
    o {'estado': 'pendiente', 'hueco': inicio de la vela que falta o None, 'hasta': ultima vela mirada o None}."""
    s = 1 if p["lado"] == "largo" else -1
    e, st, ob = float(p["entrada"]), float(p["stop"]), float(p["objetivo"])
    mercado = p["orden"] == "mercado"
    ultima = max((t for t in velas if t + PASO <= ahora), default=None)
    t = primera_vela(int(p["sello"]))
    t_ll = None
    while True:
        if ultima is None or t > ultima:
            return {"estado": "pendiente", "hueco": None, "hasta": ultima}
        v = velas.get(t)
        if v is None:
            return {"estado": "pendiente", "hueco": t, "hasta": ultima}
        o, hi, lo, c = v
        if t_ll is None:
            if not mercado and t >= int(p["caduca"]):
                return {"estado": "resuelta", "resultado": _sin_llenar(p, t)}
            if mercado:
                e, t_ll, misma = o, t, False
            elif (lo <= e) if s > 0 else (hi >= e):
                t_ll, misma = t, True
            else:
                t += PASO
                continue
        else:
            misma = False
        d = abs(e - st) / e
        toca_stop = (lo <= st) if s > 0 else (hi >= st)
        toca_obj = (hi >= ob) if s > 0 else (lo <= ob)
        if not misma and t > t_ll and s * (o - st) <= 0:
            px, como = o * (1 - s * SLIP_STOP), "stop"
        elif toca_stop:
            px, como = st * (1 - s * SLIP_STOP), "stop"
        elif toca_obj and not misma:
            px, como = ob, "objetivo"
        elif t + PASO >= t_ll + int(p["plazo_s"]):
            px, como = c, "plazo"
        else:
            t += PASO
            continue
        return {"estado": "resuelta", "resultado": _cuenta(p, s, e, d, t_ll, t + PASO, px, como, mercado)}


def _sin_llenar(p: dict, t: int) -> dict:
    return {"id": p["id"], "llenada": False, "px_llenado": None, "t_llenado": None, "salida": "caducada",
            "px_salida": None, "t_salida": int(p["caduca"]), "r_neto": 0.0, "usd_neto": 0.0, "coste": {}}


def _cuenta(p: dict, s: int, e: float, d: float, t_ll: int, t_sal: int, px: float, como: str, mercado: bool) -> dict:
    com_e = COM_TAKER if mercado else COM_MAKER
    sellos = t_sal // SELLO_FUNDING - t_ll // SELLO_FUNDING
    fund = FUNDING * sellos
    neto = s * (px / e - 1) - com_e - COM_TAKER - fund
    nominal = float(p["riesgo_usd"]) / (d + SLIP_STOP + com_e + COM_TAKER)
    desl = s * (float(p["stop"]) - px) / e if como == "stop" else 0.0
    return {"id": p["id"], "llenada": True, "px_llenado": e, "t_llenado": t_ll, "salida": como, "px_salida": px,
            "t_salida": t_sal, "r_neto": round(neto / d, 6), "usd_neto": round(neto * nominal, 6),
            "coste": {"com_entrada_pb": com_e * 1e4, "com_salida_pb": COM_TAKER * 1e4,
                      "deslizamiento_stop_pb": round(desl * 1e4, 4), "funding_pb": round(fund * 1e4, 4),
                      "sellos_funding": sellos, "nominal_usd": round(nominal, 4), "d": round(d, 6)}}
