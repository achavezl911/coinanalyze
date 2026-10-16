"""LA CUENTA DE PAPEL de cada version en curso (campana 139, C3).

Es el bloque papel de su version TAL COMO ESTA REGISTRADO, aplicado a los resultados de sus DISPARADOS (nunca a
una SOMBRA): capital_usd sin apalancamiento, una cuenta por version en curso, toma todo DISPARADO de su version
por orden de registro SI CABE y apunta los saltados con su motivo, la cantidad redondeada HACIA ABAJO al paso de
cantidad de Bybit de su simbolo, funding solo adverso (el que el resolutor apunta por cobro cruzado), y la meta
es informativa: nunca motivo para cambiar, retirar o elegir una version. Sin paso (v1: null, sin fuente) la
cuenta NO dimensiona y lo dice: el paso no se inventa. No mueve fondos ni ejecuta nada.

QUE ES «SI CABE». Sin apalancamiento, el nocional de las posiciones abiertas no pasa del saldo. Cada operacion
usa lo que quede libre, con tope en comun.tamano_plan_usd (los USD con los que el registro midio el
deslizamiento en el libro), y con la comision de entrada dentro:
    cantidad = floor(min(libre, tamano_plan_usd) / (precio_entrada * (1 + comision_entrada)) / paso) * paso
Si no llega a un paso (en Bybit el paso es tambien la cantidad minima: unidad del parametro en v2), se salta.
Saltado es SOLO el que no cabe o no dimensiona: sin paso de cantidad para su simbolo, o con un resultado sin la
comision de entrada (la foto sin el coste de sus patas), que no deja dimensionar el lote.

LO QUE NO ES UNA OPERACION (remate 3 de la 139: cada frase, cierta del estado que la produce).
  sin_posicion   SIN ENTRADA y LIMITE NO LLENADA: no abren posicion.
  sin_resultado  NO EVALUABLE, haya entrado o no, y lo que salio SIN P&L (la foto sin el coste de sus patas): no se
                 sabe su P&L. La cuenta no lo apunta ni le reserva capital, asi que lo que viene despues se
                 dimensiona como si no hubiera entrado, y su motivo lo dice.

QUE ES UN PENDIENTE. Un DISPARADO sin entrada real todavia no tiene resultado: su vela de entrada, o una anterior, aun
falta (pasa unos dos minutos tras cada registro, y en cualquier hueco de velas). No esta saltado: va en
`pendientes` con su motivo, y la cuenta es PROVISIONAL mientras este. LOS POSTERIORES: la cuenta toma por orden de
registro, asi que todo DISPARADO posterior de la version que necesite capital queda pendiente DETRAS del primero
que lo este. Lo libre para el depende de lo que ocupe aquel y de como acabe. Los que no dimensionan, los que no
abren posicion y los que no tienen resultado no necesitan capital y se apuntan ya.

LAS OPERACIONES. «abierta»: la posicion esta abierta (su resultado sigue ABIERTO). «a la espera»: entro, su plan ya
acabo y falta una vela para saber como salio (ESPERANDO); sigue ocupando su nocional hasta que se sepa. «cerrada»:
salio, con su P&L.

LA FIRMEZA. FINAL si no queda nada por saber. Si no, PROVISIONAL, y provisional_por dice por que, cada razon cierta del
estado que la pone: pendientes (sin entrada real, o detras de uno), abiertas, a la espera, un T1 cuyo plan sigue (el
seguimiento de T2 y T3 no da hora), o lo que ya acabo y aun se asienta. provisional_hasta es la hora a la que la
cuenta sera FINAL, y solo se da cuando eso es lo unico que falta.

Lo que un DISPARADO trae de su resultado: precio e instante de entrada y de salida (con la banda pesimista ya
dentro), la comision de cada pata y los cobros de funding. P&L = lado * cantidad * (salida - entrada) - las dos
comisiones - el funding adverso, sobre el nocional de entrada. Es PURA: reproducible desde la base con los
resultados guardados y el bloque papel registrado en entrada_reglamento.
"""

from __future__ import annotations

import math
from typing import Any

from app.entradas import reglamento as R
from app.entradas import resolutor as RES

SIN_POSICION = (RES.SIN_ENTRADA, RES.LIMITE_NO_LLENADA)  # no abren posicion
NO_RESERVA = "la cuenta no lo apunta ni le reserva capital"
ABIERTA, A_LA_ESPERA, CERRADA = "abierta", "a la espera", "cerrada"


def _usd(x: float | None) -> float | None:
    return None if x is None else round(x, 2)


def _pendiente(r: dict[str, Any]) -> str:
    """Por que un DISPARADO sin entrada real todavia no tiene resultado."""
    if not r.get("sabido_hasta"):
        return "todavia no tiene resultado"
    falta = (f"aun sin entrada real: la vela de 1 min de las {r['sabido_hasta'][11:16]}Z aun no se puede usar (no esta "
             "en la base, la tapa un hueco de data_gap sin resolver, o empieza despues de `ahora`)")
    if r.get("estado") == RES.ESPERANDO:
        return f"{falta}; si sigue faltando a las {r['asentado_en']}, sera NO EVALUABLE"
    return falta


def _sin_resultado(r: dict[str, Any]) -> str | None:
    """Por que no se sabe su P&L, o None si se sabe (o se sabra cuando salga)."""
    entrada = r.get("entrada")
    if r.get("salida") == RES.NO_EVALUABLE:
        que = (f"entro a las {entrada['instante'][11:16]}Z y no se sabe como salio" if entrada
               else "no se sabe si entro")
        return f"no evaluable: {que} ({r.get('motivo')}); no se sabe su P&L, y {NO_RESERVA}"
    if r.get("estado") == RES.ACABADO and entrada and r.get("pnl") is None:
        return (f"{r['salida'].replace('_', ' ')} a las {(r.get('instante') or '')[11:16]}Z, sin P&L: la foto no trae "
                f"el coste de sus patas; {NO_RESERVA}")
    return None


def cuenta(version: dict[str, Any], disparados: list[dict[str, Any]],
           resultados: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """La cuenta de una version: `version` es su objeto del reglamento; `disparados`, sus filas DISPARADO (con
    registro_id y symbol); `resultados`, el de cada una (guardado o recalculado ahora)."""
    papel = R.valores(version["bloques"]["papel"])
    comun = R.valores(version["bloques"]["comun"])
    capital = float(papel["capital_usd"])
    tamano = float(comun["tamano_plan_usd"])
    pasos = papel["paso_cantidad_bybit"] or {}
    if papel["apalancamiento"] != 1:
        raise R.ReglamentoInvalido("la cuenta de papel solo sabe aplicar apalancamiento 1")
    salida: dict[str, Any] = {
        "version": version["version"], "capital_usd": capital, "meta_usd": papel["meta_usd"],
        "meta": "informativa: nunca motivo para cambiar, retirar o elegir una version",
        "dimensiona": any(v is not None for v in pasos.values()), "no_dimensiona": None,
        "saldo_usd": capital, "funding_usd": 0.0, "n": 0, "abiertas": 0, "firmeza": RES.FINAL,
        "provisional_hasta": None, "provisional_por": [], "operaciones": [], "saltados": [], "pendientes": [],
        "sin_posicion": [], "sin_resultado": [],
    }
    sin_paso = [s for s, v in pasos.items() if v is None]
    if sin_paso:
        salida["no_dimensiona"] = (
            f"{version['version']} no dimensiona en {', '.join(sorted(sin_paso))}: su paso de cantidad de Bybit es "
            "null, sin fuente citada en su reglamento; el paso no se inventa, y sus DISPARADOS ahi se saltan")
    saldo = capital
    abiertas: list[dict[str, Any]] = []   # las que ocupan su nocional en el instante que se mira
    por_liquidar: list[dict[str, Any]] = []  # las cerradas, a liquidar en el orden de su salida
    tomados: list[dict[str, Any]] = []  # el resultado de cada DISPARADO que la cuenta toma (no saltado ni pendiente)

    def liquida(hasta: str | None) -> None:
        nonlocal saldo
        for op in sorted([p for p in por_liquidar if hasta is None or p["instante_salida"] <= hasta],
                         key=lambda p: (p["instante_salida"], p["registro_id"])):
            saldo += op["_pnl"]
            por_liquidar.remove(op)
            abiertas.remove(op)

    detras: int | None = None  # el primer pendiente: lo posterior que necesita capital espera a que se sepa
    propios = 0  # pendientes por si mismos (sin entrada real); el resto de `pendientes`, detras de uno
    for f in sorted(disparados, key=lambda x: x["registro_id"]):
        rid, symbol = f["registro_id"], f["symbol"]
        r = resultados.get(rid) or {}
        base = {"registro_id": rid, "symbol": symbol, "familia": f["familia"], "perfil": f["perfil"],
                "lado": f["lado"], "vela_cierre": RES.iso(RES._t(f["vela_cierre"]))}
        paso = pasos.get(symbol)
        if paso is None:
            salida["saltados"].append({**base, "motivo": "no dimensiona: sin paso de cantidad de Bybit para "
                                       f"{symbol} en el reglamento de {version['version']}"})
            continue
        if r.get("salida") in SIN_POSICION:
            salida["sin_posicion"].append({**base, "motivo": f"{r['salida'].replace('_', ' ')}: no abre posicion"})
            tomados.append(r)
            continue
        sin = _sin_resultado(r)
        if sin:
            salida["sin_resultado"].append({**base, "motivo": sin})
            tomados.append(r)
            continue
        entrada = r.get("entrada")
        if not entrada:
            salida["pendientes"].append({**base, "motivo": _pendiente(r)})
            propios += 1
            detras = detras or rid
            continue
        if entrada.get("comision_bps") is None:
            salida["saltados"].append({**base, "motivo": "no dimensiona: su resultado no trae la comision de entrada "
                                       "(la foto no trae el coste de sus patas)"})
            continue
        if detras is not None:
            salida["pendientes"].append({**base, "motivo": (
                f"detras del registro {detras}, que esta pendiente: la cuenta toma por orden de registro, y lo libre "
                "para este depende de lo que ocupe aquel y de como acabe")})
            continue
        liquida(entrada["instante"])
        libre = saldo - sum(p["nocional_usd"] for p in abiertas)
        precio = float(entrada["precio"])
        com_e = float(entrada["comision_bps"])
        cantidad = math.floor(round(min(libre, tamano) / (precio * (1 + com_e / RES.BPS)) / paso, 9)) * paso
        cantidad = round(cantidad, 9)
        if cantidad < paso:
            ocupado = [p["registro_id"] for p in abiertas]
            cuanto = "lo libre" if libre <= tamano else "el tope de tamano_plan_usd"
            salida["saltados"].append({**base, "motivo": (
                f"no cabe: {max(min(libre, tamano), 0.0):.2f} USD ({cuanto}) no compran {paso:g} "
                f"{symbol.split('USDT')[0]} a {precio:g} con la comision de entrada"
                + (f"; el resto esta en la operacion {', '.join(map(str, ocupado))}" if ocupado else ""))})
            continue
        nocional = cantidad * precio
        op = {**base, "estado": A_LA_ESPERA if r.get("estado") == RES.ESPERANDO else ABIERTA, "salida": None,
              "firmeza": RES.PROVISIONAL, "lote": cantidad, "paso": paso, "instante_entrada": entrada["instante"],
              "precio_entrada": precio, "nocional_usd": nocional, "instante_salida": None, "precio_salida": None,
              "asentado_en": None, "comision_usd": None, "funding_usd": None, "pnl_usd": None, "r_neto": None,
              "funding_sin_medir": []}
        abiertas.append(op)
        tomados.append(r)
        if r.get("estado") == RES.ACABADO and r.get("precio") is not None and r.get("pnl"):
            s = 1.0 if f["lado"] == "largo" else -1.0
            precio_s = float(r["precio"])
            com_s = float(r["pnl"]["comision_bps"]["salida"])
            comision = nocional * com_e / RES.BPS + cantidad * precio_s * com_s / RES.BPS
            funding = sum(nocional * c["fr_adverso"] / 100 for c in r.get("funding") or [] if c["medido"])
            pnl = s * cantidad * (precio_s - precio) - comision - funding
            op.update(estado=CERRADA, salida=r["salida"], firmeza=r["firmeza"], instante_salida=r["instante"],
                      precio_salida=precio_s, asentado_en=r.get("asentado_en"), comision_usd=comision,
                      funding_usd=funding, pnl_usd=pnl, r_neto=r["pnl"]["r_neto"], _pnl=pnl,
                      funding_sin_medir=[c["cobro"] for c in r.get("funding") or [] if not c["medido"]])
            por_liquidar.append(op)
            salida["funding_usd"] += funding
            salida["n"] += 1
        salida["operaciones"].append(op)
    liquida(None)
    ops = salida["operaciones"]
    salida["abiertas"] = sum(op["estado"] == ABIERTA for op in ops)
    # lo que ya acabo y aun no es FINAL: con su hora de asentamiento, o sin ella (un T1 cuyo plan sigue)
    acabado = [r for r in tomados if r.get("estado") == RES.ACABADO and r.get("firmeza") != RES.FINAL]
    con_hora = [r["asentado_en"] for r in acabado if r.get("asentado_en")]
    razones = [razon for razon, hay in (
        ("hay DISPARADOS aun sin entrada real", propios),
        ("hay DISPARADOS que esperan detras de uno pendiente", len(salida["pendientes"]) > propios),
        ("hay operaciones abiertas", salida["abiertas"]),
        ("hay operaciones a la espera de una vela que falta para saber como salieron",
         any(op["estado"] == A_LA_ESPERA for op in ops)),
        ("hay DISPARADOS que salieron en T1 y cuyo plan sigue (T2 y T3) hasta su stop, su invalidacion o su "
         "caducidad: ese seguimiento no da hora", len(con_hora) < len(acabado)),
    ) if hay]
    if con_hora:
        razones.append(f"lo que ya acabo se asienta a las {max(con_hora)}")
    salida["firmeza"] = RES.PROVISIONAL if razones else RES.FINAL
    salida["provisional_por"] = razones
    salida["provisional_hasta"] = max(con_hora) if con_hora and len(razones) == 1 else None
    salida["saldo_usd"] = _usd(saldo)
    salida["funding_usd"] = _usd(salida["funding_usd"])
    for op in ops:
        op.pop("_pnl", None)
        for k in ("nocional_usd", "comision_usd", "funding_usd", "pnl_usd"):
            op[k] = _usd(op[k])
    return salida
