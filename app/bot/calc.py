"""C3 · la calculadora de una operacion lineal USDT de Bybit en margen AISLADO. Pura: los tramos, el paso y el funding
entran como argumentos (bybit.py los lee de las rutas publicas).

Por omision, la forma de Alejandro: 10 USD de margen a 50x, stop a -0.6 % y objetivo a +2 %, con su perdida maxima
de 3 USD. Comision taker 5.5 bps por lado (entrada y salida).

Liquidacion (aislada): MM = valor x MMR - mmDeduction del tramo cuyo riskLimitValue cubre el valor de la posicion;
largo: entrada - (IM - MM) / cantidad; corto: entrada + (IM - MM) / cantidad, con IM = valor / apalancamiento.
ponytail: formula de memoria, NO contrastada con la doc publica en BOT-2 (WebFetch sin permiso para su dominio); la
primera posicion real la mide: evaluar() pone al lado la liqPrice que da Bybit y la diferencia en bps.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal

TAKER = 0.00055
MARGEN, APALANCAMIENTO, STOP_PCT, OBJETIVO_PCT, PERDIDA_MAX = 10.0, 50.0, 0.6, 2.0, 3.0


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


def calcula(
    entrada: float,
    stop: float | None = None,
    objetivo: float | None = None,
    *,
    margen: float = MARGEN,
    apalancamiento: float = APALANCAMIENTO,
    corto: bool = False,
    paso: str = "0.001",
    tramos: list[dict],
    funding: float | None = None,
    funding_h: float = 8.0,
) -> dict:
    lado = -1 if corto else 1
    if stop is None:
        stop = entrada * (1 - lado * STOP_PCT / 100)
    if objetivo is None:
        objetivo = entrada * (1 + lado * OBJETIVO_PCT / 100)
    if stop == entrada:
        raise ValueError("el stop es la entrada")
    lado = 1 if stop < entrada else -1
    if (objetivo - entrada) * lado <= 0:
        raise ValueError("el objetivo esta del lado del stop")
    # el tamano se redondea HACIA ABAJO al paso de Bybit, en decimal (en float 0.3/0.1 no da 3)
    p = Decimal(paso)
    cantidad = float((Decimal(str(margen * apalancamiento)) / Decimal(str(entrada)) / p).to_integral_value(ROUND_DOWN) * p)
    if cantidad <= 0:
        raise ValueError(f"el tamano no llega a un paso de {paso}")
    valor = cantidad * entrada
    im = valor / apalancamiento
    liq, mmr = liquidacion(entrada, cantidad, apalancamiento, lado, tramos)
    com_in, com_stop, com_obj = valor * TAKER, cantidad * stop * TAKER, cantidad * objetivo * TAKER
    perdida = cantidad * abs(entrada - stop) + com_in + com_stop
    bruto = cantidad * abs(objetivo - entrada)
    ganancia = bruto - com_in - com_obj
    avisos = []
    if perdida > PERDIDA_MAX:
        avisos.append(f"la perdida al stop ({perdida:.2f} USD con comision) pasa de tu maximo ({PERDIDA_MAX:.0f} USD)")
    if (stop - liq) * lado <= 0:
        avisos.append(f"el stop esta mas alla de la liquidacion ({liq:.6g}): te liquidan antes")
    return {
        "lado": "LARGO" if lado > 0 else "CORTO",
        "entrada": entrada, "stop": stop, "objetivo": objetivo,
        "cantidad": cantidad, "valor_usd": valor, "margen_usd": im, "apalancamiento": apalancamiento,
        "mmr": mmr, "liquidacion": liq, "liq_pct": (liq / entrada - 1) * 100,
        "comision_usd": com_in + com_obj, "perdida_stop_usd": perdida, "ganancia_obj_usd": ganancia,
        "rr_bruto": abs(objetivo - entrada) / abs(entrada - stop), "rr_neto": ganancia / perdida,
        "comision_come_pct": (com_in + com_obj) / bruto * 100,
        "funding_usd": None if funding is None else -lado * valor * funding, "funding_h": funding_h,
        "avisos": avisos,
    }


def texto(r: dict, simbolo: str) -> str:
    f = r["funding_usd"]
    lineas = [
        f"{simbolo} {r['lado']} · entrada {r['entrada']:.6g} · stop {r['stop']:.6g} · objetivo {r['objetivo']:.6g}",
        f"tamano {r['cantidad']:g} ({r['valor_usd']:.2f} USD) · margen {r['margen_usd']:.2f} USD a {r['apalancamiento']:g}x",
        f"liquidacion {r['liquidacion']:.6g} ({r['liq_pct']:+.2f} %, MMR {r['mmr'] * 100:g} %)",
        f"perdida al stop {r['perdida_stop_usd']:.2f} USD · ganancia al objetivo {r['ganancia_obj_usd']:.2f} USD (con comision)",
        f"R:R {r['rr_bruto']:.2f} bruto / {r['rr_neto']:.2f} neto · la comision ({r['comision_usd']:.2f} USD) se come el"
        f" {r['comision_come_pct']:.1f} % del objetivo",
        "funding: sin dato" if f is None else f"funding: {'cobras' if f >= 0 else 'pagas'} {abs(f):.3f} USD cada {r['funding_h']:g} h",
    ]
    lineas += [f"AVISO: {a}" for a in r["avisos"]]
    return "\n".join(lineas)
