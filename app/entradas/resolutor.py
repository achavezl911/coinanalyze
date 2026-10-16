"""EL RESOLUTOR (campana 139, E3): como acabo cada plan del registro, por PRIMER TOQUE en las velas de 1 min.

resolver() es PURA: una fila del registro con su foto, las velas de 1 min de su simbolo, los cobros de funding
y un instante (el reloj de la base). No lee el reloj ni la base: el plan es el de su foto tal como se registro,
contra la serie que el plan nombra (ohlcv 1 min de su simbolo .A, Binance). Es biblioteca estandar a proposito,
como reglamento.py: lo importa K107, que corre sin el entorno de la app.

EL LOTE SALE ENTERO en el primero de sus eventos: T1 (el exito del bloque lectura), el stop, la invalidacion
por su regla o la caducidad. T2 y T3 se informan y no mueven nada: el reglamento define el exito en T1 y no
define salidas parciales. Las ocho salidas: OBJETIVO, STOP, STOP Y OBJETIVO EN LA MISMA VELA (cuenta stop),
INVALIDADO, CADUCADO, SIN ENTRADA, NO EVALUABLE y LIMITE NO LLENADA.

EL LARGO Y EL CORTO. Como el motor, razona en el «espacio del lado» (x = +precio en largo, -precio en corto):
el corto es el reflejo exacto del largo por construccion, y un test lo comprueba en vez de suponerlo.

LAS CONVENCIONES (abajo) se SIRVEN con cada resultado, con RESOLUTOR_VERSION y su huella. Cambiar una es una
version nueva del resolutor: un resultado guardado no se reescribe (entrada_resultado es solo-anadir y su
clave es (registro_id, resolutor)). Lo que se aparta de la propuesta E3 de la COLA lo dice CAMBIOS_E3.

LO QUE NO HACE: ninguna frecuencia. Da el resultado de UN plan; cuantos resueltos lleva una celda lo cuenta
quien sirve, y la frecuencia es la E4.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.entradas import reglamento as R

RESOLUTOR_VERSION = "entradas-resolutor-1"
# Los de app/signal_outcomes.py (OUTCOME_SETTLEMENT_LAG y MISSING_DATA_FINAL_GRACE), copiados para seguir
# siendo biblioteca estandar; tests/test_entradas_resolutor.py ata que sean los mismos.
ASENTAMIENTO = timedelta(minutes=42)
GRACIA = timedelta(days=7)
MINUTO = timedelta(minutes=1)
BPS = 10_000
COBROS_FUNDING_H = (0, 8, 16)

OBJETIVO, STOP, MISMA_VELA = "objetivo", "stop", "stop_y_objetivo_misma_vela"
INVALIDADO, CADUCADO, SIN_ENTRADA = "invalidado", "caducado", "sin_entrada"
NO_EVALUABLE, LIMITE_NO_LLENADA = "no_evaluable", "limite_no_llenada"
SALIDAS = (OBJETIVO, STOP, MISMA_VELA, INVALIDADO, CADUCADO, SIN_ENTRADA, NO_EVALUABLE, LIMITE_NO_LLENADA)
ABIERTO, ACABADO, ESPERANDO = "abierto", "acabado", "esperando_velas"
FINAL, PROVISIONAL = "final", "provisional"

CONVENCIONES = {
    "unidad": "cada DISPARADO, cada version por separado; sobre una SOMBRA el mismo calculo es un HIPOTETICO "
    "rotulado como tal, que nunca entra en una cuenta de DISPARADOS",
    "serie": "ohlcv de 1 min del simbolo del plan (.A, Binance), tal como esta en la base al resolver",
    "entrada_mercado": "apertura de la vela de 1 min floor(registered_at)+1min, movida en contra por la banda "
    "pesimista de la foto (plan.entrada.banda_pesimista_bps: spread y deslizamiento de Bybit en T)",
    "entrada_limite": "al precio de la foto (plan.entrada.precio; si es null, su referencia), y solo si una vela "
    "de 1 min desde floor(registered_at)+1min la CRUZA (largo: minimo por debajo; corto: maximo por encima), "
    "sin banda. Si antes cruza T1, se invalida o caduca: LIMITE NO LLENADA, 0 USD, con su hipotetico a mercado "
    "aparte",
    "tolerancia_venue": "el plan se ejecuta en Bybit y se mide sobre Binance: tolerancia = |mids.base_bps| de la "
    "foto mas el spread de Bybit de la foto (libro_bybit.spread_bps, un tick); sin libro (solo una SOMBRA), "
    "solo la base",
    "objetivo": "T1 cuenta si el precio lo CRUZA mas alla de la tolerancia (largo: maximo > T1 + tolerancia); "
    "sale al precio de T1, orden limite (maker), sin banda; si la vela abre ya mas alla, sale igual a T1 y la "
    "apertura es el caso favorable",
    "stop": "cuenta si el precio lo TOCA dentro de la tolerancia (largo: minimo <= stop + tolerancia); sale al "
    "precio del stop a mercado (taker) movido en contra por la banda de la pata stop; si la vela abre ya mas "
    "alla (nivel saltado con hueco), sale a esa apertura con la banda, y el precio del stop es el caso "
    "favorable",
    "misma_vela": "si en una vela de 1 min se cumplen el stop y T1 y su apertura no decide cual fue primero, "
    "cuenta el STOP y T1 es el caso favorable. La apertura si decide: es el primer precio de la vela",
    "invalidacion": "cierre de una vela del perfil (date_bin desde 1970-01-01 UTC, el reloj de "
    "plan.invalidacion) estrictamente al otro lado de plan.invalidacion.nivel (largo: cierre < nivel; corto: "
    "cierre > nivel), posterior a la entrada y no posterior a la caducidad; sale a mercado en la apertura del "
    "minuto en que cierra esa vela, con la banda de la pata stop. En el mismo instante que la caducidad, cuenta "
    "INVALIDADO",
    "caducidad": "sin evento antes de plan.caducidad.caduca_en, sale a mercado en la apertura de la vela de "
    "1 min que empieza en ese instante, con la banda de la pata stop",
    "sin_entrada": "si T1 o el stop se cumplen entre el cierre de su vela y la entrada real, o la apertura de "
    "la entrada ya esta mas alla de uno de los dos, no abre posicion: 0 USD y R 0, cuenta en el denominador y "
    "no es exito",
    "costes": "la banda (spread y deslizamiento) va en el precio y a cada pata se le cobra la comision de su "
    "foto: entrada taker (maker si es limite), objetivo maker, stop taker; las salidas por invalidacion o "
    "caducidad pagan la pata stop",
    "r": "R neto = bps netos / riesgo neto del PLAN registrado (plan.distancias_bps.stop mas el coste total de "
    "las patas de entrada y de stop de la foto): la unidad la fija el registro, no la entrada real. Con la "
    "entrada real en la referencia de la foto, T1 da el r.neto de la foto y el stop da -1",
    "t2_t3": "se informa si el precio los cruzo (la regla de T1) y cuando, desde la entrada hasta el fin del "
    "plan -su stop, su invalidacion o su caducidad-, aunque el lote ya saliera entero en T1; no mueven nada",
    "excursion": "maxima a favor y en contra, en bps de la entrada real, sobre las velas con la posicion "
    "abierta (de la de entrada a la anterior a la de salida) y el precio de salida",
    "huecos": "un minuto ausente antes del evento que decide, o cubierto por un hueco de data_gap sin "
    "resolver, PUDO esconder un nivel: el plan espera; si a la gracia de signal_outcomes (7 dias despues de "
    "su asentamiento) sigue faltando, es NO EVALUABLE",
    "asentamiento": "un resultado es FINAL cuando la ultima vela que usa tiene mas de 42 min "
    "(OUTCOME_SETTLEMENT_LAG de signal_outcomes: ohlcv se reescribe 40 min hacia atras, mas 2); antes es "
    "PROVISIONAL y dice hasta cuando",
    "funding": "cobros de Binance a las 00, 08 y 16 UTC dentro de [entrada, salida] (los dos bordes, en "
    "contra), cada uno con el cubo de 5 min de funding_rate que acaba en el: su extremo adverso (largo fr_high, "
    "corto fr_low) si va en contra del lado, 0 si va a favor; lo usa la cuenta de papel",
}
HUELLA_CONVENCIONES = R.huella({"version": RESOLUTOR_VERSION, "convenciones": CONVENCIONES})

# Lo que esta version cambia de la propuesta E3 escrita en harness/COLA.md el 2026-10-02, y por que.
CAMBIOS_E3 = [
    "el margen de la tolerancia de venue, que la propuesta dejaba sin fijar, es el spread de Bybit de la foto "
    "(un tick): sale de la foto y no de una constante nueva",
    "el no evaluable no distingue que nivel pudo esconder un minuto ausente: no hay en la base otra serie que "
    "acote el rango de ese minuto, asi que todo minuto ausente antes del evento que decide puede esconderlo",
    "invalidado y caducado no pagan una pata propia: la foto no la trae, y pagan la del stop (taker)",
]


def _t(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        momento = valor
    else:
        momento = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    return momento.astimezone(UTC) if momento.tzinfo else momento.replace(tzinfo=UTC)


def iso(momento: datetime) -> str:
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _minuto(momento: datetime) -> datetime:
    return momento.replace(second=0, microsecond=0)


def foto_de(fila: dict[str, Any]) -> dict[str, Any]:
    foto = fila["foto"]
    return json.loads(foto) if isinstance(foto, str) else foto


def entrada_t(fila: dict[str, Any]) -> datetime:
    """El minuto de la entrada real: floor(registered_at)+1min."""
    return _minuto(_t(fila["registered_at"])) + MINUTO


def ventana(fila: dict[str, Any]) -> tuple[datetime, datetime]:
    """[desde, hasta] de las velas de 1 min que el plan puede usar: del cierre de su vela a su caducidad."""
    plan = foto_de(fila)["plan"]
    return _t(fila["vela_cierre"]), _t(plan["caducidad"]["caduca_en"])


def cobros_funding(desde: datetime, hasta: datetime) -> list[datetime]:
    """Los cobros de Binance (00, 08, 16 UTC) dentro de [desde, hasta]."""
    dia = desde.replace(hour=0, minute=0, second=0, microsecond=0)
    cobros = []
    while dia <= hasta:
        cobros += [dia.replace(hour=h) for h in COBROS_FUNDING_H if desde <= dia.replace(hour=h) <= hasta]
        dia += timedelta(days=1)
    return cobros


def _pata(plan: dict[str, Any], nombre: str) -> tuple[float | None, float | None, float | None]:
    """(comision, banda, total) en bps de una pata de la foto. None si la foto no trae el dato."""
    pata = (plan.get("costes") or {}).get(nombre) or {}
    comps = pata.get("componentes_bps") or {}
    if not comps or any(v is None for v in comps.values()):
        return None, None, pata.get("total_bps")
    comision = sum(v for k, v in comps.items() if k in ("taker", "maker"))
    banda = sum(v for k, v in comps.items() if k not in ("taker", "maker"))
    return comision, banda, pata.get("total_bps")


def resolver(fila: dict[str, Any], velas: list[dict[str, Any]], ahora: datetime,
             funding: dict[datetime, dict[str, float]] | None = None,
             huecos: list[tuple[Any, Any]] = ()) -> dict[str, Any]:
    """El resultado de UN plan. `velas`: las de 1 min de su simbolo ({ts, open, high, low, close}); `funding`:
    {cobro: {fr_high, fr_low}} del cubo de 5 min que acaba en cada cobro; `huecos`: los [desde, hasta) de
    data_gap sin resolver; `ahora`: el reloj de la base, que decide final o provisional."""
    foto = foto_de(fila)
    plan = foto["plan"]
    lado, perfil = fila["lado"], fila["perfil"]
    if lado not in R.LADOS:
        raise ValueError(f"lado desconocido {lado!r}")
    s = 1.0 if lado == "largo" else -1.0
    ahora = _t(ahora)
    T, caduca = ventana(fila)
    t_entrada = entrada_t(fila)
    vela_min = timedelta(minutes=foto["parametros"]["comun"]["perfiles"][perfil]["vela_min"])
    entrada = plan.get("entrada") or {}
    limite = entrada.get("tipo") == "limite"
    stop = (plan.get("stop") or {}).get("precio")
    objetivos = (plan.get("objetivos") or [])[:3]
    nivel = (plan.get("invalidacion") or {}).get("nivel")
    out: dict[str, Any] = {
        "registro_id": fila.get("registro_id"), "version": fila.get("version"),
        "resolutor": RESOLUTOR_VERSION, "huella_convenciones": HUELLA_CONVENCIONES,
        "hipotetico": fila.get("estado") != "DISPARADO",
        "estado": ACABADO, "salida": None, "firmeza": FINAL, "asentado_en": None, "instante": None,
        "precio": None, "entrada": None, "pnl": None, "favorable": None, "t2": None, "t3": None,
        "excursion": None, "funding": [], "sabido_hasta": None, "motivo": None,
    }
    if stop is None or not objetivos or nivel is None:
        out.update(salida=NO_EVALUABLE, motivo="la foto no trae stop, T1 o nivel de invalidacion: no hay plan "
                   "que resolver (solo una SOMBRA puede faltar de ellos)")
        return out

    mids, libro = foto.get("mids") or {}, foto.get("libro_bybit") or {}
    tol = abs(mids.get("base_bps") or 0.0) + (libro.get("spread_bps") or 0.0)
    com_e, banda_pata_e, total_e = _pata(plan, "entrada")
    com_obj, _, _ = _pata(plan, "objetivo")
    com_stop, banda_stop, total_stop = _pata(plan, "stop")
    banda_e = 0.0 if limite else entrada.get("banda_pesimista_bps", banda_pata_e)
    d_stop = (plan.get("distancias_bps") or {}).get("stop")
    riesgo = d_stop + total_e + total_stop if None not in (d_stop, total_e, total_stop) else None
    con_coste = None not in (com_e, com_obj, com_stop, banda_stop, banda_e)

    S, N = s * stop, s * nivel
    Ts = [s * t for t in objetivos]
    por_ts = {_t(v["ts"]): v for v in velas}
    tapados = [(_t(a), _t(b)) for a, b in huecos]

    def vela(m: datetime) -> dict[str, float] | None:
        v = por_ts.get(m)
        if v is None or any(a < m + MINUTO and b > m for a, b in tapados):
            return None
        xs = (s * float(v["high"]), s * float(v["low"]))
        return {"o": s * float(v["open"]), "h": max(xs), "l": min(xs), "c": s * float(v["close"])}

    def cruza(x: float, x_nivel: float) -> bool:
        return x > x_nivel + abs(x_nivel) * tol / BPS

    def toca(x: float) -> bool:
        return x <= S + abs(S) * tol / BPS

    def cierra_en_contra(m: datetime, v: dict[str, float]) -> bool:
        """La vela de 1 min `m` es la ultima de una vela del perfil que cierra al otro lado del nivel."""
        fin = m + MINUTO
        return (fin - T) % vela_min == timedelta(0) and fin <= caduca and v["c"] < N

    def contra(x: float, banda: float | None) -> float:
        return x - abs(x) * (banda or 0.0) / BPS

    def pnl(x_e: float, x_s: float, com_salida: float | None) -> dict[str, Any] | None:
        if not con_coste:
            return None
        brutos = (x_s - x_e) / abs(x_e) * BPS
        netos = brutos - com_e - com_salida
        return {"bps_brutos": brutos, "bps_netos": netos, "r_neto": netos / riesgo if riesgo else None,
                "comision_bps": {"entrada": com_e, "salida": com_salida}}

    def asienta(ultima: datetime) -> None:
        listo = ultima + MINUTO + ASENTAMIENTO
        out["asentado_en"] = iso(listo)
        out["firmeza"] = FINAL if ahora >= listo else PROVISIONAL

    def espera(m: datetime, que: str, vivo: bool = True) -> dict[str, Any]:
        """Falta la vela `m`. Antes de caducar (y si el plan no ha acabado ya) esta ABIERTO: se sabe que no ha
        tocado nada hasta `m`. Si no, espera a la gracia; a la gracia es NO EVALUABLE."""
        out["sabido_hasta"] = iso(m)
        if vivo and ahora < caduca:
            out.update(estado=ABIERTO, firmeza=PROVISIONAL,
                       motivo=f"sin tocar stop, T1 ni invalidacion hasta la vela de 1 min de las {iso(m)[11:16]}Z, "
                       "que todavia no esta en la base")
            return out
        tope = caduca + MINUTO + ASENTAMIENTO + GRACIA
        motivo = f"falta la vela de 1 min de las {iso(m)} ({que}) y pudo esconder un nivel"
        if ahora >= tope:
            out.update(salida=NO_EVALUABLE, firmeza=FINAL, asentado_en=iso(tope), instante=None, precio=None,
                       pnl=None, favorable=None, excursion=None, motivo=motivo)
        else:
            out.update(estado=ESPERANDO, firmeza=PROVISIONAL, asentado_en=iso(tope),
                       motivo=f"{motivo}; si sigue faltando a las {iso(tope)} sera NO EVALUABLE")
        return out

    def acaba(nombre: str, m: datetime, motivo: str) -> dict[str, Any]:
        out.update(salida=nombre, instante=iso(m), pnl=_cero(con_coste), motivo=motivo)
        asienta(m)
        return out

    # 1 · entre el cierre de la vela y la entrada real: lo que se cumple aqui deja el plan SIN ENTRADA
    m = T
    while m < t_entrada:
        v = vela(m)
        if v is None:
            return espera(m, "antes de la entrada")
        cumple = [n for n, ok in (("T1", cruza(v["h"], Ts[0])), ("el stop", toca(v["l"]))) if ok]
        if cumple:
            return acaba(SIN_ENTRADA, m, f"{' y '.join(cumple)} en la vela de las {iso(m)[11:16]}Z, antes de la "
                         f"entrada real de las {iso(t_entrada)[11:16]}Z: no abre posicion")
        m += MINUTO

    # 2 · la entrada real
    v = vela(t_entrada)
    if v is None:
        return espera(t_entrada, "la de la entrada")
    if not limite:
        if toca(v["o"]) or cruza(v["o"], Ts[0]):
            return acaba(SIN_ENTRADA, t_entrada, "la apertura de la entrada real ya esta mas alla "
                         + ("del stop" if toca(v["o"]) else "de T1") + ": no abre posicion")
        x_e, m_ini = v["o"] + abs(v["o"]) * (banda_e or 0.0) / BPS, t_entrada
    else:
        precio = entrada.get("precio")
        L = s * (precio if precio is not None else (entrada.get("referencia") or {}).get("precio"))
        m = t_entrada
        while True:
            w = vela(m) if m < caduca else None
            if m >= caduca or (w is not None and (cruza(w["h"], Ts[0]) or cierra_en_contra(m, w))
                               and not w["l"] < L):
                motivo = ("no cruzo la limite antes de caducar" if m >= caduca else
                          "T1 cruzado o invalidado antes de llenarse la limite")
                hipotetico = resolver({**fila, "foto": {**foto, "plan": {**plan, "entrada": {
                    **entrada, "tipo": "mercado"}}}}, velas, ahora, funding, huecos)
                acaba(LIMITE_NO_LLENADA, min(m, caduca - MINUTO), motivo + ": 0 USD")
                out["instante"] = iso(min(m, caduca))
                out["favorable"] = {"hipotetico_a_mercado": {k: hipotetico.get(k) for k in (
                    "salida", "instante", "precio", "pnl", "firmeza")},
                    "que_es": "el mismo plan entrando a mercado: hipotetico, fuera de toda cuenta"}
                return out
            if w is None:
                return espera(m, "esperando a que se llene la limite")
            if w["l"] < L:
                x_e, m_ini = L, m
                break
            m += MINUTO
    out["entrada"] = {"instante": iso(m_ini), "precio": s * x_e, "tipo": entrada.get("tipo"),
                      "apertura": None if limite else s * v["o"], "banda_bps": banda_e}

    # 3 · la vida, minuto a minuto: el primer evento
    alto = bajo = x_e
    tocados: dict[int, str] = {}
    evento: tuple | None = None
    m = m_ini
    while m < caduca:
        v = vela(m)
        if v is None:
            return espera(m, "con la posicion abierta")
        llena_aqui = limite and m == m_ini   # la limite se lleno DENTRO de esta vela: su apertura no cuenta
        if not llena_aqui and toca(v["o"]):
            evento = (STOP, contra(v["o"], banda_stop), com_stop, (STOP, contra(S, banda_stop), com_stop))
        elif not llena_aqui and cruza(v["o"], Ts[0]):
            evento = (OBJETIVO, Ts[0], com_obj, (OBJETIVO, v["o"], com_obj))
        elif toca(v["l"]) and cruza(v["h"], Ts[0]):
            evento = (MISMA_VELA, contra(S, banda_stop), com_stop, (OBJETIVO, Ts[0], com_obj))
        elif toca(v["l"]):
            evento = (STOP, contra(S, banda_stop), com_stop, None)
        elif cruza(v["h"], Ts[0]) and not llena_aqui:
            evento = (OBJETIVO, Ts[0], com_obj, None)
        if evento is None or evento[0] == OBJETIVO:
            for i, x_t in enumerate(Ts[1:], 2):
                if i not in tocados and cruza(v["h"], x_t):
                    tocados[i] = iso(m)
        if evento is not None:
            m_s = m
            break
        alto, bajo = max(alto, v["h"]), min(bajo, v["l"])
        if cierra_en_contra(m, v):
            w = vela(m + MINUTO)
            if w is None:
                return espera(m + MINUTO, "la de la salida por invalidacion", vivo=False)
            evento, m_s = (INVALIDADO, contra(w["o"], banda_stop), com_stop, None), m + MINUTO
            break
        m += MINUTO
    if evento is None:
        w = vela(caduca)
        if w is None:
            return espera(caduca, "la de la salida por caducidad", vivo=False)
        evento, m_s = (CADUCADO, contra(w["o"], banda_stop), com_stop, None), caduca

    nombre, x_s, com_s, alternativa = evento
    alto, bajo = max(alto, x_s), min(bajo, x_s)
    out.update(salida=nombre, instante=iso(m_s), precio=s * x_s, pnl=pnl(x_e, x_s, com_s),
               excursion={"favor_bps": (alto - x_e) / abs(x_e) * BPS, "contra_bps": (x_e - bajo) / abs(x_e) * BPS})
    if alternativa is not None:
        out["favorable"] = {"salida": alternativa[0], "precio": s * alternativa[1],
                            "pnl": pnl(x_e, alternativa[1], alternativa[2]),
                            "que_es": "el caso favorable de lo que dentro de un minuto no se puede saber: fuera "
                            "de toda cuenta"}
    ultima = m_s

    # 4 · tras salir en T1 el plan sigue, sin lote, hasta su stop, su invalidacion o su caducidad: T2 y T3
    if nombre == OBJETIVO and len(tocados) < len(Ts) - 1:
        m = m_s + MINUTO
        while m < caduca:
            v = vela(m)
            if v is None:
                tope = caduca + MINUTO + ASENTAMIENTO + GRACIA
                out["sabido_hasta"] = iso(m)
                if ahora < tope:
                    out.update(firmeza=PROVISIONAL, asentado_en=None,
                               motivo=f"T2 y T3 se siguen hasta el fin del plan: falta la vela de las {iso(m)}")
                    _cobros(out, s, funding)
                    _t23(out, objetivos, tocados, sabido=False)
                    return out
                out["motivo"] = f"T2 y T3 no se saben desde la vela de las {iso(m)}, que falto hasta la gracia"
                _t23(out, objetivos, tocados, sabido=False)
                out.update(firmeza=FINAL, asentado_en=iso(tope))
                _cobros(out, s, funding)
                return out
            for i, x_t in enumerate(Ts[1:], 2):
                if i not in tocados and cruza(v["h"], x_t):
                    tocados[i] = iso(m)
            ultima = m
            if toca(v["l"]) or cierra_en_contra(m, v) or len(tocados) == len(Ts) - 1:
                break
            m += MINUTO
    _t23(out, objetivos, tocados, sabido=True)
    asienta(ultima)
    _cobros(out, s, funding)
    if not con_coste:
        out["motivo"] = "la foto no trae el coste de sus patas (solo una SOMBRA puede): salida sin P&L"
    return out


def _t23(out: dict[str, Any], objetivos: list[float], tocados: dict[int, str], sabido: bool) -> None:
    for i in (2, 3):
        if len(objetivos) >= i:
            out[f"t{i}"] = {"precio": objetivos[i - 1], "cruzado": True if i in tocados else (False if sabido else None),
                            "instante": tocados.get(i)}


def _cobros(out: dict[str, Any], s: float, funding: dict[datetime, dict[str, float]] | None) -> None:
    """Los cobros de funding con la posicion abierta: [entrada, salida], los dos bordes en contra. Sin
    `funding` (el hipotetico de una SOMBRA) no se mira ninguno."""
    if funding is None:
        return
    for cobro in cobros_funding(_t(out["entrada"]["instante"]), _t(out["instante"])):
        dato = funding.get(cobro)
        if dato is None:
            out["funding"].append({"cobro": iso(cobro), "medido": False, "fr_extremo": None, "fr_adverso": None})
            continue
        extremo = float(dato["fr_high"] if s > 0 else dato["fr_low"])
        out["funding"].append({"cobro": iso(cobro), "medido": True, "fr_extremo": extremo,
                               "fr_adverso": max(0.0, s * extremo)})


def _cero(con_coste: bool) -> dict[str, Any] | None:
    return {"bps_brutos": 0.0, "bps_netos": 0.0, "r_neto": 0.0, "comision_bps": None} if con_coste else None

