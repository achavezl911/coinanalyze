"""C3 · la calculadora de una operacion lineal USDT de Bybit en margen AISLADO. Pura: los tramos, el paso y el funding
entran como argumentos (bybit.py los lee de las rutas publicas).

POR RIESGO (BOT-SEGURIDAD B5): el tamano sale de lo que se pierde hasta el stop, PERDIDA_MAX = 5 USD (el dueno lo subio de 3.6 el 2026-11-15) con la comision
taker de 5.5 bps por lado (entrada y salida), redondeando el paso de Bybit hacia abajo. Entrada y stop son obligatorios;
objetivo opcional; apalancamiento por omision 10x (solo decide el margen y la liquidacion, no el riesgo). Se fueron los
valores por omision de antes (10 USD x 50, stop a -0.6 %, objetivo a +2 %).

Liquidacion (aislada): MM = valor x MMR - mmDeduction del tramo cuyo riskLimitValue cubre el valor de la posicion;
largo: entrada - (IM - MM) / cantidad; corto: entrada + (IM - MM) / cantidad, con IM = valor / apalancamiento.
ponytail: formula de memoria, NO contrastada con la doc publica en BOT-2 (WebFetch sin permiso para su dominio); la
primera posicion real la mide: valida() pone al lado la liqPrice que da Bybit y la diferencia.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

TAKER = 0.00055
PERDIDA_MAX, APALANCAMIENTO = 5.0, 10.0
LIQ_VECES = 2.0  # la liquidacion a menos de esto veces la distancia al stop se avisa


def tramo(tramos: list[dict], valor: float) -> dict:
    """El primer tramo (por riskLimitValue creciente) que cubre el valor; si ninguno, el ultimo."""
    orden = sorted(tramos, key=lambda t: float(t["riskLimitValue"]))
    return next((t for t in orden if float(t["riskLimitValue"]) >= valor), orden[-1])


def liquidacion(entrada: float, cantidad: float, apalancamiento: float, lado: int, tramos: list[dict]) -> tuple[float, float]:
    """-> (precio de liquidacion, MMR del tramo)."""
    valor = cantidad * entrada
    t = tramo(tramos, valor)
    mm = valor * float(t["maintenanceMargin"]) - float(t.get("mmDeduction") or 0)
    return entrada - lado * (valor / apalancamiento - mm) / cantidad, float(t["maintenanceMargin"])


def perdida_al_stop(cantidad: float, entrada: float, stop: float, lado: int) -> float:
    """Lo que se pierde al stop con la comision taker de entrada y de stop (la regla de PERDIDA_MAX). Con signo: un
    stop ya en ganancia da menos. La usan calcula y el auditor (app/bot/auditor.py, A6)."""
    return cantidad * (entrada - stop) * lado + cantidad * entrada * TAKER + cantidad * stop * TAKER


def calcula(
    entrada: float,
    stop: float | None = None,
    objetivo: float | None = None,
    *,
    riesgo: float = PERDIDA_MAX,
    apalancamiento: float = APALANCAMIENTO,
    corto: bool | None = None,
    paso: str = "0.001",
    tramos: list[dict],
    funding: float | None = None,
    funding_h: float = 8.0,
) -> dict:
    """corto: True CORTO, False LARGO, None (sin decir) el que diga el stop. La direccion que se DICE manda y una
    incoherencia se dice (remate 3, bug 13). riesgo: lo que se pierde al stop con comision, como mucho PERDIDA_MAX."""
    if stop is None:
        raise ValueError("falta el stop: el tamano sale de lo que se pierde hasta el (/calc activo entrada stop)")
    if stop == entrada:
        raise ValueError("el stop es la entrada")
    if not 0 < riesgo <= PERDIDA_MAX:
        raise ValueError(f"el riesgo va de 0 a {PERDIDA_MAX:g} USD (pediste {riesgo:g})")
    if apalancamiento <= 0:
        raise ValueError("el apalancamiento tiene que ser positivo")
    lado = (-1 if stop > entrada else 1) if corto is None else (-1 if corto else 1)
    nombre = "CORTO" if lado < 0 else "LARGO"
    if (entrada - stop) * lado <= 0:
        raise ValueError(f"pediste {nombre} pero el stop {stop:g} esta {'por debajo' if stop < entrada else 'por encima'} de la"
                         f" entrada {entrada:g}: en un {nombre} va {'por encima' if lado < 0 else 'por debajo'}")
    if objetivo is not None and (objetivo - entrada) * lado <= 0:
        raise ValueError(f"el objetivo {objetivo:g} esta del lado del stop para un {nombre}")
    # lo que pierde UNA unidad al stop: la distancia y la comision de los dos lados (entrada y stop)
    por_unidad = abs(entrada - stop) + (entrada + stop) * TAKER
    # el tamano se redondea HACIA ABAJO al paso de Bybit, en decimal (en float 0.3/0.1 no da 3)
    p = Decimal(paso)
    pasos = (Decimal(str(riesgo)) / Decimal(str(por_unidad)) / p).to_integral_value(ROUND_DOWN)
    avisos = []
    if pasos < 1:
        pasos = Decimal(1)
        avisos.append(f"NO CABE: el paso minimo ({paso}) ya pierde {float(p) * por_unidad:.2f} USD al stop, mas que tu"
                      f" riesgo de {riesgo:.2f} USD; el tamano de abajo es ese paso, NO el riesgo pedido")
    cantidad = float(pasos * p)
    valor = cantidad * entrada
    im = valor / apalancamiento
    liq, mmr = liquidacion(entrada, cantidad, apalancamiento, lado, tramos)
    com_in = valor * TAKER
    perdida = perdida_al_stop(cantidad, entrada, stop, lado)
    dist_stop, dist_liq = abs(entrada - stop), (entrada - liq) * lado
    if (stop - liq) * lado <= 0:
        avisos.append(f"la liquidacion ({liq:.6g}) queda ANTES del stop: te liquidan antes; baja el apalancamiento")
    elif dist_liq < LIQ_VECES * dist_stop:
        avisos.append(f"la liquidacion ({liq:.6g}) queda a {dist_liq / dist_stop:.2f} veces la distancia al stop (menos de"
                      f" {LIQ_VECES:g}): poco colchon; baja el apalancamiento")
    r = {
        "lado": nombre,
        "entrada": entrada, "stop": stop, "objetivo": objetivo,
        "cantidad": cantidad, "valor_usd": valor, "margen_usd": im, "apalancamiento": apalancamiento,
        "riesgo_pedido_usd": riesgo, "perdida_stop_usd": perdida,
        "mmr": mmr, "liquidacion": liq, "liq_pct": (liq / entrada - 1) * 100, "liq_veces_stop": dist_liq / dist_stop,
        "comision_usd": None, "ganancia_obj_usd": None, "rr_bruto": None, "rr_neto": None, "comision_come_pct": None,
        "funding_usd": None if funding is None else -lado * valor * funding, "funding_h": funding_h,
        "avisos": avisos,
    }
    if objetivo is not None:
        com_obj = cantidad * objetivo * TAKER
        bruto = cantidad * abs(objetivo - entrada)
        ganancia = bruto - com_in - com_obj
        r.update(comision_usd=com_in + com_obj, ganancia_obj_usd=ganancia, rr_bruto=abs(objetivo - entrada) / dist_stop,
                 rr_neto=ganancia / perdida, comision_come_pct=(com_in + com_obj) / bruto * 100)
    return r


# B5: la tolerancia va en DISTANCIA a la liquidacion (|formula - Bybit| / |entrada - Bybit|), no en % del precio: a 50x
# la liquidacion esta a ~2 % y 0.5 % del precio era un cuarto de esa distancia. Y solo vale para el MISMO simbolo.
VALIDA_DIST_PCT = 2.0


def nota_validacion(v: dict | None, simbolo: str | None = None) -> str:
    """v: la ultima validacion contra una posicion real {symbol, dia, dif_pct, dif_dist_pct} (None: todavia ninguna);
    simbolo: el de la cuenta (None: no se compara)."""
    if not v:
        return "sin validar contra Bybit"
    if simbolo and v["symbol"] != simbolo:
        return f"sin validar contra Bybit en {simbolo} (la ultima validacion, en {v['symbol']} {v['dia']}, no vale aqui)"
    d = v.get("dif_dist_pct")
    if d is None:
        return f"sin validar en distancia (la de {v['symbol']} {v['dia']} se midio en % del precio)"
    base = f"validada contra Bybit: {d:.2f} % de la distancia a la liquidacion en {v['symbol']} {v['dia']}"
    return base if d <= VALIDA_DIST_PCT else (f"OJO: se separo de Bybit {d:.2f} % de la distancia a la liquidacion (>"
                                              f" {VALIDA_DIST_PCT:g} %) en {v['symbol']} {v['dia']}: no fiable")


def texto(r: dict, simbolo: str, validacion: dict | None = None) -> str:
    f = r["funding_usd"]
    obj = "objetivo: sin dar" if r["objetivo"] is None else f"objetivo {r['objetivo']:.6g}"
    lineas = [
        f"{simbolo} {r['lado']} · entrada {r['entrada']:.6g} · stop {r['stop']:.6g} · {obj}",
        f"tamano {r['cantidad']:g} · riesgo real {r['perdida_stop_usd']:.2f} USD al stop con comision (pedido"
        f" {r['riesgo_pedido_usd']:.2f})",
        f"nominal {r['valor_usd']:.2f} USD · margen {r['margen_usd']:.2f} USD a {r['apalancamiento']:g}x",
        f"liquidacion {r['liquidacion']:.6g} ({r['liq_pct']:+.2f} %, {r['liq_veces_stop']:.1f} veces la distancia al stop,"
        f" MMR {r['mmr'] * 100:g} %; {nota_validacion(validacion, simbolo)})",
    ]
    if r["objetivo"] is not None:
        lineas += [f"ganancia al objetivo {r['ganancia_obj_usd']:.2f} USD (con comision) · R:R {r['rr_bruto']:.2f} bruto /"
                   f" {r['rr_neto']:.2f} neto · la comision ({r['comision_usd']:.2f} USD) se come el"
                   f" {r['comision_come_pct']:.1f} % del objetivo"]
    lineas.append("funding: sin dato" if f is None else f"funding: {'cobras' if f >= 0 else 'pagas'} {abs(f):.3f} USD cada"
                  f" {r['funding_h']:g} h")
    lineas += [f"AVISO: {a}" for a in r["avisos"]]
    return "\n".join(lineas)
