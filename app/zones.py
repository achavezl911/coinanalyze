"""Carácter de una zona de precio: acumulación, distribución o rotación sin carácter.

Funciones puras, sin base de datos: reciben las barras y las sesiones ya consultadas.

Qué se puede medir y qué no
---------------------------
Para una zona de hace meses NO existe el libro de órdenes (6 h de retención) ni el flujo a
nivel de trade (14 d), asi que la absorción no puede observarse directamente. Lo que si existe
con 300 dias de profundidad es el delta agresivo de futuros por vela de 4 h — `ohlcv` a
intervalo `4hour` trae `buy_volume`, de modo que `(2*bv - v)*close` es delta REAL, no estimado —
y el CVD spot por sesion en `daily_session_agg`, con 392 sesiones.

Por eso la absorcion se infiere de su huella: **esfuerzo agresivo grande contra desplazamiento
de precio pequeño**. Es una inferencia y el veredicto lo declara con esas palabras.

Sobre los pesos
---------------
Son heuristicos y estan declarados como tales. No hay backtest que los respalde todavia; el
proposito de esta capa es hacer la lectura trazable y explicable, no producir una probabilidad.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.interpretation import number

# Minimo para emitir veredicto: 12 barras de 4 h = 2 dias dentro de la zona. Por debajo, el
# delta acumulado es demasiado ruidoso para separar absorcion de un simple paso por el nivel.
MIN_ZONE_BARS = 12
# Dos visitas al mismo nivel separadas por mas de esto son episodios distintos y se juzgan
# por separado: una zona no tiene un unico caracter a lo largo de meses.
VISIT_GAP_DAYS = 7

STRONG_SCORE = 55.0
WEAK_SCORE = 25.0

# --- Constantes CALIBRADAS sobre 1 796 velas de 4 h por simbolo (BTC/ETH/SOL), 2026-08-04 ---
#
# Desplazamiento. Comparar el recorrido de una zona de n velas contra el ATR de UNA vela es un
# error de escala: en un paseo aleatorio el recorrido crece con sqrt(n). Normalizando por
# ATR*sqrt(n) la mediana medida sale 0.475 / 0.475 / 0.493 / 0.518 para n = 12 / 24 / 55 / 155,
# es decir estable en el tamaño de ventana, que es justo lo que debe cumplir la normalizacion.
DISPLACEMENT_NORMAL = 0.50  # mediana empirica
DISPLACEMENT_STALLED = 0.15  # ~p10: el precio practicamente no fue a ninguna parte
#
# Esfuerzo. La fraccion direccional |Σdelta|/Σvolumen DEPENDE del tamaño de ventana
# (mediana 0.0175 con 12 velas -> 0.0083 con 155), asi que un umbral absoluto es inservible:
# en ventanas largas no se cruza nunca. Se modela como A * n^EXP, donde A es la mediana de una
# sola vela — que se mide POR SIMBOLO — y el exponente de agregacion es comun. Verificado:
# empirica/predicha = 0.77-1.17 en los tres simbolos y en n = 12/55/155.
EFFORT_AGGREGATION_EXPONENT = -0.292
#
# Eficiencia de absorcion = flujo direccional normalizado / recorrido normalizado, es decir
# cuanto flujo agresivo hizo falta por cada unidad de avance conseguida. Es UNA ratio en vez
# de dos puertas independientes, y su distribucion resulta casi identica en los tres simbolos
# (6 942 ventanas de 12/24/55/155 velas):
#   BTC  mediana 0.91  p75 1.63  p90 3.95
#   ETH  mediana 0.92  p75 1.65  p90 3.67
#   SOL  mediana 1.11  p75 2.03  p90 4.41
# Los umbrales son esos percentiles, no numeros elegidos a ojo.
# Suelo del denominador: sin el, una zona que cierra donde abrio dispara la ratio aunque el
# flujo sea insignificante. Fijado en ~p10 del recorrido normalizado relativo; con ese suelo
# la distribucion medida queda mediana 0.97 / p75 1.72 / p90 3.40, de donde salen los umbrales.
DISPLACEMENT_FLOOR = 0.15
ABSORPTION_ELEVATED = 1.7  # p75 medido
ABSORPTION_STRONG = 3.4  # p90 medido
# Por debajo de la mitad del flujo direccional tipico no hay absorcion que reclamar: si casi
# nadie empujo, que el precio no se moviera no dice nada de quien habia al otro lado.
EFFORT_MINIMUM = 0.5


# --------------------------------------------------------------------------- rango
# Umbrales medidos sobre 936 ventanas (60/120/180 velas diarias x 3 simbolos), no elegidos
# a ojo. Entre parentesis, que porcentaje de ventanas historicas pasa cada test: un test que
# pasara siempre no discriminaria nada, que es justo el defecto que hubo que corregir en la
# fase 1. Se probaron y descartaron: toques con tolerancia del 10% de la altura (pasaba el
# 100%) y >=4 episodios por borde (no lo cumple ninguna ventana, 0%).
RANGE_MIN_BARS = 40
RANGE_MAX_DRIFT = 0.40  # p25 de la deriva relativa (~23% pasa)
RANGE_MIN_CONTAINMENT = 0.90  # guarda del rectangulo, no discriminador
RANGE_MIN_ROTATIONS = 4  # p90 (~10% pasa)
RANGE_MIN_EDGE_EPISODES = 2  # p90 (~11% pasa)
RANGE_MAX_VOL_RATIO = 1.2  # p75 (~75% pasa)
RANGE_ROTATION_DEADBAND = 0.25  # fraccion de la semi-altura que hay que superar
# La tolerancia de toque se calibro con los bordes puestos en los EXTREMOS del tramo, que es
# como se dibuja un rectangulo en la practica. Con esos bordes el maximo se toca una sola vez
# por definicion, asi que una tolerancia estrecha vuelve el test inalcanzable: medido sobre
# 1 566 ventanas, >=2 episodios lo pasaba el 1% con tolerancia 0.05 y el 6% con 0.10. Con 0.15
# lo pasa el 14%, en linea con el resto de tests. (Calibrar con bordes en p5/p95 daba 11% con
# tolerancia 0.05 y llevaba a un umbral que en uso real no se cruzaba nunca.)
RANGE_EDGE_TOLERANCE = 0.15
RANGE_EDGE_EXIT = 0.30  # y no vuelve a contar hasta alejarse un 30%
RANGE_PASSES_FOR_RANGE = 4
RANGE_PASSES_FOR_FORMING = 3


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _atr_pct(bars: list[dict[str, Any]]) -> float | None:
    """ATR de la zona expresado en % del cierre, por mediana de rangos verdaderos."""
    ranges: list[float] = []
    previous: float | None = None
    for bar in bars:
        high, low, close = number(bar["high"]), number(bar["low"]), number(bar["close"])
        if not all(math.isfinite(v) and v > 0 for v in (high, low, close)):
            previous = None
            continue
        true_range = high - low
        if previous is not None:
            true_range = max(true_range, abs(high - previous), abs(low - previous))
        ranges.append(true_range / close * 100)
        previous = close
    return median(ranges) if ranges else None


def _percentile(value: float, sample: list[float]) -> float | None:
    clean = [item for item in sample if math.isfinite(item)]
    if len(clean) < 30:
        return None
    return sum(item <= value for item in clean) / len(clean) * 100.0


def _effort_result(
    bars: list[dict[str, Any]], atr_pct: float | None, effort_scale: float | None
) -> dict[str, Any]:
    """Esfuerzo agresivo frente al desplazamiento que consiguió.

    Delta negativo con el precio aguantando = alguien compró esa venta (acumulación).
    Delta positivo sin avance = alguien vendió esa compra (distribución).

    Ambas magnitudes se normalizan por el tamaño de la ventana antes de compararse; sin eso,
    una zona de 155 velas y otra de 12 no son comparables y los umbrales dejan de significar
    lo mismo en cada una.
    """
    delta_usd = 0.0
    volume_usd = 0.0
    for bar in bars:
        close = number(bar["close"])
        volume = number(bar["volume"])
        buy = number(bar["buy_volume"])
        if not all(math.isfinite(v) for v in (close, volume, buy)) or close <= 0:
            continue
        delta_usd += (2 * buy - volume) * close
        volume_usd += volume * close
    base = {"delta_usd": delta_usd, "volume_usd": volume_usd}
    if volume_usd <= 0 or atr_pct is None or atr_pct <= 0 or not effort_scale:
        return {"value": None, **base}

    first, last = number(bars[0]["close"]), number(bars[-1]["close"])
    if not (math.isfinite(first) and math.isfinite(last) and first > 0):
        return {"value": None, **base}

    count = len(bars)
    move_pct = (last / first - 1) * 100
    # Recorrido observado frente al que cabe esperar de n velas de este ATR.
    displacement_norm = abs(move_pct) / (atr_pct * math.sqrt(count))
    effort_ratio = abs(delta_usd) / volume_usd
    expected_effort = effort_scale * count**EFFORT_AGGREGATION_EXPONENT
    effort_norm = effort_ratio / expected_effort if expected_effort > 0 else 0.0

    # Cuanto flujo direccional costo cada unidad de avance. Alto = el mercado tuvo que
    # empujar mucho para moverse poco, que es la huella de la absorcion. Una sola ratio
    # captura lo que antes eran dos puertas separadas, y ademas es dimensionalmente lo que
    # se quiere medir: esfuerzo por resultado.
    displacement_relative = max(displacement_norm / DISPLACEMENT_NORMAL, DISPLACEMENT_FLOOR)
    efficiency = effort_norm / displacement_relative
    strength = (
        0.0
        if effort_norm < EFFORT_MINIMUM
        else _clamp(
            (efficiency - ABSORPTION_ELEVATED) / (ABSORPTION_STRONG - ABSORPTION_ELEVATED), 0, 1
        )
    )
    direction = -1.0 if delta_usd < 0 else (1.0 if delta_usd > 0 else 0.0)
    return {
        # Signo invertido a proposito: venta agresiva absorbida es ALCISTA.
        "value": -direction * strength,
        **base,
        "effort_ratio": effort_ratio,
        "effort_norm": effort_norm,
        "displacement_norm": displacement_norm,
        "displacement_pct_of_normal": displacement_norm / DISPLACEMENT_NORMAL * 100,
        "absorption_efficiency": efficiency,
        "price_move_pct": move_pct,
        "bars": count,
    }


def _rejection(bars: list[dict[str, Any]]) -> float | None:
    """Dónde cierra el precio dentro de cada barra. Cierres altos = compradores defendiendo."""
    positions: list[float] = []
    for bar in bars:
        high, low, close = number(bar["high"]), number(bar["low"]), number(bar["close"])
        span = high - low
        if not math.isfinite(span) or span <= 0:
            continue
        positions.append((close - low) / span)
    if len(positions) < 5:
        return None
    return (median(positions) - 0.5) * 2


def _oi_behaviour(oi_change_pct: float | None, price_move_pct: float | None) -> float | None:
    if oi_change_pct is None or price_move_pct is None:
        return None
    if price_move_pct <= 0 and oi_change_pct > 1:
        return 1.0  # entra posicion nueva mientras el precio aguanta
    if price_move_pct <= 0 and oi_change_pct < -2:
        return 0.5  # desapalancamiento: la oferta forzada se agota
    if price_move_pct > 0 and oi_change_pct > 2:
        return -0.5  # subida sostenida por apalancamiento, fragil
    return 0.0


def zone_character_read(visit: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Veredicto de una visita a la zona. Nunca usa datos posteriores a la visita."""
    bars = list(visit.get("bars") or [])
    if len(bars) < MIN_ZONE_BARS:
        return {
            "available": False,
            "reason": (
                f"Solo {len(bars)} barras de 4 h dentro de la zona; se necesitan "
                f"{MIN_ZONE_BARS} (2 días) para separar absorción de un simple paso por el nivel."
            ),
            "bars_4h": len(bars),
        }

    atr_pct = _atr_pct(bars)
    effort = _effort_result(bars, atr_pct, baseline.get("effort_scale"))
    price_move_pct = effort.get("price_move_pct")

    sessions = visit.get("sessions") or {}
    session_count = int(sessions.get("count") or 0)
    cvd_spot = sessions.get("cvd_spot_usd")
    oi_first, oi_last = sessions.get("oi_first"), sessions.get("oi_last")
    oi_change_pct = (
        (oi_last / oi_first - 1) * 100 if (oi_first and oi_last and oi_first > 0) else None
    )
    funding = sessions.get("funding_avg")

    median_abs_spot = baseline.get("median_abs_cvd_spot") or 0.0
    spot_value = None
    if cvd_spot is not None and session_count and median_abs_spot > 0:
        spot_value = _clamp(cvd_spot / (session_count * median_abs_spot))

    funding_pct = (
        _percentile(funding, baseline.get("funding_sample") or []) if funding is not None else None
    )
    funding_value = None
    if funding_pct is not None:
        funding_value = 1.0 if funding_pct <= 20 else (-1.0 if funding_pct >= 80 else 0.0)

    components = [
        {
            "key": "esfuerzo_resultado",
            "label": "Esfuerzo agresivo vs desplazamiento",
            "weight": 35.0,
            "value": effort["value"],
        },
        {"key": "cvd_spot", "label": "CVD spot de la zona", "weight": 25.0, "value": spot_value},
        {
            "key": "open_interest",
            "label": "Comportamiento del open interest",
            "weight": 15.0,
            "value": _oi_behaviour(oi_change_pct, price_move_pct),
        },
        {
            "key": "funding",
            "label": "Funding (posicionamiento)",
            "weight": 15.0,
            "value": funding_value,
        },
        {
            "key": "rechazos",
            "label": "Cierres dentro de la barra",
            "weight": 10.0,
            "value": _rejection(bars),
        },
    ]

    # Renormalizacion sobre lo medible: sumar 0 por un componente ausente no es neutral,
    # arrastra el score hacia el centro y disfraza la falta de datos de equilibrio.
    measurable = [c for c in components if c["value"] is not None]
    measured_weight = sum(c["weight"] for c in measurable)
    total_weight = sum(c["weight"] for c in components)
    score = (
        sum(c["value"] * c["weight"] for c in measurable) / measured_weight * 100
        if measured_weight
        else 0.0
    )
    coverage = measured_weight / total_weight * 100 if total_weight else 0.0

    if not measurable:
        character, strength = "sin_datos", "sin datos"
    elif score >= STRONG_SCORE:
        character, strength = "acumulacion", "clara"
    elif score >= WEAK_SCORE:
        character, strength = "acumulacion", "indicios"
    elif score <= -STRONG_SCORE:
        character, strength = "distribucion", "clara"
    elif score <= -WEAK_SCORE:
        character, strength = "distribucion", "indicios"
    else:
        character, strength = "sin_caracter", "rotación neutra"

    positives = [c for c in measurable if c["value"] > 0]
    negatives = [c for c in measurable if c["value"] < 0]
    agreement = (
        max(len(positives), len(negatives)) / len(measurable) * 100 if measurable else 0.0
    )
    if coverage < 50 or not measurable:
        confidence = "baja"
    elif agreement >= 75 and abs(score) >= STRONG_SCORE:
        confidence = "alta"
    elif agreement >= 60:
        confidence = "media"
    else:
        confidence = "baja"

    significance = None
    median_vol = baseline.get("median_bar_volume_usd") or 0.0
    if median_vol > 0 and effort["volume_usd"]:
        significance = round(effort["volume_usd"] / len(bars) / median_vol, 2)

    return {
        "available": True,
        "character": character,
        "strength": strength,
        "score": round(score, 1),
        "confidence": confidence,
        "evidence_coverage_pct": round(coverage, 1),
        "agreement_pct": round(agreement, 1),
        "bars_4h": len(bars),
        "sessions": session_count,
        "from": str(visit.get("from") or "")[:10],
        "to": str(visit.get("to") or "")[:10],
        "components": [
            {
                "key": c["key"],
                "label": c["label"],
                "weight": c["weight"],
                "value": round(c["value"], 3) if c["value"] is not None else None,
                "contribution": round(c["value"] * c["weight"], 1)
                if c["value"] is not None
                else None,
                "status": "unavailable" if c["value"] is None else "measured",
            }
            for c in components
        ],
        "measurements": {
            "delta_futuros_usd": round(effort["delta_usd"], 2),
            "volumen_usd": round(effort["volume_usd"], 2),
            "fraccion_direccional": round(effort["effort_ratio"], 4)
            if effort.get("effort_ratio") is not None
            else None,
            "esfuerzo_vs_normal": round(effort["effort_norm"], 2)
            if effort.get("effort_norm") is not None
            else None,
            "recorrido_vs_normal_pct": round(effort["displacement_pct_of_normal"], 1)
            if effort.get("displacement_pct_of_normal") is not None
            else None,
            "eficiencia_absorcion": round(effort["absorption_efficiency"], 2)
            if effort.get("absorption_efficiency") is not None
            else None,
            "precio_cambio_pct": round(price_move_pct, 2) if price_move_pct is not None else None,
            "atr_zona_pct": round(atr_pct, 3) if atr_pct is not None else None,
            "cvd_spot_usd": round(cvd_spot, 2) if cvd_spot is not None else None,
            "oi_cambio_pct": round(oi_change_pct, 2) if oi_change_pct is not None else None,
            "funding_medio": round(funding, 6) if funding is not None else None,
            "funding_percentil": funding_pct,
            "volumen_relativo": significance,
        },
        "narrative": _narrative(character, strength, effort, spot_value, oi_change_pct, funding_pct),
        "method": {
            "weights": {c["key"]: c["weight"] for c in components},
            "weights_basis": "heurísticos, sin calibrar contra resultado realizado",
            "renormalised_over": [c["key"] for c in measurable],
            "unavailable": [c["key"] for c in components if c["value"] is None],
            "clocks": "delta de futuros en UTC de 4 h; CVD spot en sesión NYSE. No se suman.",
        },
        "warning": (
            "La absorción se infiere de esfuerzo agresivo contra desplazamiento de precio, no "
            "se observa en el libro: sin profundidad histórica no hay forma de verla directa. "
            "El score es un balance de evidencia, no una probabilidad."
        ),
    }


def _narrative(
    character: str,
    strength: str,
    effort: dict[str, Any],
    spot_value: float | None,
    oi_change_pct: float | None,
    funding_pct: float | None,
) -> list[str]:
    """Frases con las cifras dentro. Un novato debe leer la causa, no la etiqueta."""
    lines: list[str] = []
    delta = effort.get("delta_usd") or 0.0
    recorrido = effort.get("displacement_pct_of_normal")
    esfuerzo = effort.get("effort_norm")
    if recorrido is not None and esfuerzo is not None:
        side = "vendieron" if delta < 0 else "compraron"
        millions = abs(delta) / 1e6
        bars = effort.get("bars") or 0
        if effort.get("value"):
            absorbed_by = "compró" if delta < 0 else "vendió"
            lines.append(
                f"Los futuros {side} {millions:,.0f} M USD netos, un flujo direccional "
                f"{esfuerzo:.1f}× lo normal, y el precio solo recorrió el {recorrido:.0f}% de lo "
                f"habitual para {bars} velas: alguien {absorbed_by} esa oferta sin mover el "
                "mercado."
            )
        elif recorrido < 60:
            lines.append(
                f"El precio apenas recorrió el {recorrido:.0f}% de lo habitual para {bars} velas, "
                f"con un flujo direccional de {esfuerzo:.1f}× lo normal. El esfuerzo por unidad "
                "de avance no llega al percentil 75 histórico: se lee como equilibrio entre las "
                "dos partes, no como absorción por una de ellas."
            )
        else:
            lines.append(
                f"Los futuros {side} {millions:,.0f} M USD netos y el precio recorrió el "
                f"{recorrido:.0f}% de lo habitual para {bars} velas: un desplazamiento normal "
                "para ese flujo, así que no hay señal de absorción."
            )
    if spot_value is not None:
        verb = "acompañó comprando" if spot_value > 0 else "no acompañó: vendió"
        lines.append(f"El contado {verb} durante la zona.")
    if oi_change_pct is not None:
        if oi_change_pct > 1:
            lines.append(
                f"El open interest subió {oi_change_pct:.1f}%: entró posición nueva mientras el "
                "precio se mantenía en la zona."
            )
        elif oi_change_pct < -2:
            lines.append(
                f"El open interest cayó {abs(oi_change_pct):.1f}%: hubo desapalancamiento, la "
                "oferta forzada se estaba agotando."
            )
    if funding_pct is not None:
        if funding_pct <= 20:
            lines.append(
                f"El funding estuvo en el percentil {funding_pct:.0f} del último año: los cortos "
                "pagaban, lo que suele preceder a rebotes por presión de cierre."
            )
        elif funding_pct >= 80:
            lines.append(
                f"El funding estuvo en el percentil {funding_pct:.0f}: los largos pagaban, "
                "posicionamiento amontonado al alza."
            )
    if character == "sin_caracter":
        lines.append(
            "Las evidencias no apuntan mayoritariamente a ningún lado: la zona se comporta como "
            "rotación entre compradores y vendedores, no como acumulación ni distribución."
        )
    elif strength == "indicios":
        lines.append(
            f"La lectura es de {character} pero solo con indicios: la evidencia apunta en esa "
            "dirección sin la fuerza suficiente para considerarla una firma clara."
        )
    return lines


# --------------------------------------------------------------------------- rango
def _ols_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator <= 0:
        return 0.0
    return sum((i - mean_x) * (v - mean_y) for i, v in enumerate(values)) / denominator


def _rotations(closes: list[float], low: float, high: float) -> int:
    """Cambios de mitad con banda muerta: sin ella el ruido alrededor del centro contaria
    como rotaciones y cualquier serie plana pareceria un rango muy activo."""
    mid = (low + high) / 2
    band = (high - low) / 2 * RANGE_ROTATION_DEADBAND
    side: str | None = None
    count = 0
    for close in closes:
        current = "u" if close > mid + band else ("d" if close < mid - band else None)
        if current and current != side:
            if side is not None:
                count += 1
            side = current
    return count


def _edge_episodes(bars: list[dict[str, Any]], edge: float, height: float, upper: bool) -> int:
    """Visitas DISTINTAS a un borde. Contar barras sueltas no sirve: 15 barras pegadas al
    borde pueden ser una sola visita larga, y lo que valida un rango es que el borde se
    pruebe, se abandone y se vuelva a probar."""
    tolerance = height * RANGE_EDGE_TOLERANCE
    exit_distance = height * RANGE_EDGE_EXIT
    count = 0
    inside = False
    for bar in bars:
        high, low = number(bar["high"]), number(bar["low"])
        near = (high >= edge - tolerance) if upper else (low <= edge + tolerance)
        far = (high < edge - exit_distance) if upper else (low > edge + exit_distance)
        if near and not inside:
            count += 1
            inside = True
        elif far:
            inside = False
    return count


def _atr_abs(bars: list[dict[str, Any]]) -> float | None:
    ranges: list[float] = []
    previous: float | None = None
    for bar in bars:
        high, low, close = number(bar["high"]), number(bar["low"]), number(bar["close"])
        if not all(math.isfinite(v) for v in (high, low, close)):
            previous = None
            continue
        true_range = high - low
        if previous is not None:
            true_range = max(true_range, abs(high - previous), abs(low - previous))
        ranges.append(true_range)
        previous = close
    return median(ranges) if ranges else None


def range_validate_read(
    bars: list[dict[str, Any]],
    prior_bars: list[dict[str, Any]],
    low: float,
    high: float,
) -> dict[str, Any]:
    """Cinco tests con umbral explicito y valor medido al lado.

    El veredicto no es una etiqueta opaca: cada test dice que se midio, contra que y por que,
    para que el operador aprenda el criterio en vez de memorizar la conclusion.
    """
    if len(bars) < RANGE_MIN_BARS:
        return {
            "available": False,
            "reason": (
                f"Solo {len(bars)} sesiones en el tramo; se necesitan {RANGE_MIN_BARS} para "
                "juzgar si hay rango. Menos que eso no da tiempo a que el precio rote."
            ),
            "bars": len(bars),
        }
    height = high - low
    if height <= 0:
        return {"available": False, "reason": "El borde inferior debe estar por debajo del superior."}

    closes = [c for c in (number(b["close"]) for b in bars) if math.isfinite(c)]
    if len(closes) < RANGE_MIN_BARS:
        return {"available": False, "reason": "Cierres incompletos en el tramo.", "bars": len(closes)}

    drift = abs(_ols_slope(closes) * len(closes)) / height
    containment = sum(low <= c <= high for c in closes) / len(closes)
    rotations = _rotations(closes, low, high)
    episodes_low = _edge_episodes(bars, low, height, upper=False)
    episodes_high = _edge_episodes(bars, high, height, upper=True)
    atr_window = _atr_abs(bars)
    atr_prior = _atr_abs(prior_bars) if prior_bars else None
    vol_ratio = atr_window / atr_prior if (atr_window and atr_prior and atr_prior > 0) else None

    tests: list[dict[str, Any]] = [
        {
            "key": "horizontalidad",
            "label": "El precio no deriva",
            "value": round(drift, 3),
            "threshold": RANGE_MAX_DRIFT,
            "operator": "<=",
            "passed": drift <= RANGE_MAX_DRIFT,
            "reading": f"La tendencia de fondo recorrió el {drift * 100:.0f}% de la altura del rango.",
            "why": "Un rango oscila alrededor de un nivel; si deriva, es tendencia con ruido.",
            "status": "measured",
        },
        {
            "key": "contencion",
            "label": "Los bordes contienen el precio",
            "value": round(containment * 100, 1),
            "threshold": RANGE_MIN_CONTAINMENT * 100,
            "operator": ">=",
            "passed": containment >= RANGE_MIN_CONTAINMENT,
            "reading": f"El {containment * 100:.0f}% de los cierres quedó dentro del rectángulo.",
            "why": "Comprueba que el rectángulo describe de verdad al precio. Es una guarda del "
            "trazado, no un discriminador: uno bien dibujado lo pasa casi siempre.",
            "status": "measured",
        },
        {
            "key": "rotacion",
            "label": "Rota entre los dos lados",
            "value": rotations,
            "threshold": RANGE_MIN_ROTATIONS,
            "operator": ">=",
            "passed": rotations >= RANGE_MIN_ROTATIONS,
            "reading": f"{rotations} cambios completos entre la mitad superior y la inferior.",
            "why": "Un rango es ida y vuelta. Una meseta que no rota es una pausa, no un rango.",
            "status": "measured",
        },
        {
            "key": "toques",
            "label": "Ambos bordes fueron probados",
            "value": min(episodes_low, episodes_high),
            "threshold": RANGE_MIN_EDGE_EPISODES,
            "operator": ">=",
            "passed": min(episodes_low, episodes_high) >= RANGE_MIN_EDGE_EPISODES,
            "reading": f"{episodes_low} visitas al soporte y {episodes_high} a la resistencia.",
            "why": "Si solo se probó un borde, es un soporte o una resistencia, no un rango.",
            "status": "measured",
        },
        {
            "key": "volatilidad",
            "label": "La volatilidad no se expande",
            "value": round(vol_ratio, 2) if vol_ratio is not None else None,
            "threshold": RANGE_MAX_VOL_RATIO,
            "operator": "<=",
            "passed": vol_ratio is not None and vol_ratio <= RANGE_MAX_VOL_RATIO,
            "reading": (
                f"El rango diario medio es {vol_ratio:.2f}× el de las 90 sesiones previas."
                if vol_ratio is not None
                else "Sin historia previa suficiente para comparar la volatilidad."
            ),
            "why": "Un rango comprime; una expansión sostenida suele romperlo.",
            "status": "measured" if vol_ratio is not None else "unavailable",
        },
    ]

    measurable = [t for t in tests if t["status"] == "measured"]
    passed = sum(bool(t["passed"]) for t in measurable)
    if passed >= RANGE_PASSES_FOR_RANGE:
        verdict, plain = "rango", "Es un rango"
    elif passed >= RANGE_PASSES_FOR_FORMING:
        verdict, plain = "rango_en_formacion", "Rango en formación"
    else:
        verdict, plain = "no_es_rango", "No es un rango"

    failed = [t["label"] for t in measurable if not t["passed"]]
    mid = (low + high) / 2
    narrative = [
        f"{plain}: pasa {passed} de {len(measurable)} pruebas "
        f"(se piden {RANGE_PASSES_FOR_RANGE} para confirmarlo)."
    ]
    if failed:
        narrative.append("No cumple: " + "; ".join(failed) + ".")
    if verdict != "no_es_rango":
        narrative.append(
            f"Mientras siga siendo rango, el precio tiende a volver hacia {mid:,.0f}; los "
            "extremos son las zonas de decisión, no el centro."
        )
    return {
        "available": True,
        "verdict": verdict,
        "verdict_plain": plain,
        "passed": passed,
        "evaluated": len(measurable),
        "required": RANGE_PASSES_FOR_RANGE,
        "range": {
            "low": low,
            "high": high,
            "mid": round(mid, 8),
            "height_pct": round(height / mid * 100, 2),
        },
        "bars": len(bars),
        "tests": tests,
        "narrative": narrative,
        "invalidation": (
            f"Deja de ser rango si el precio cierra fuera de [{low:,.0f}, {high:,.0f}] y la "
            "volatilidad se expande por encima de 1.2x, o si deja de rotar entre los bordes."
        ),
        "method": {
            "source": "velas diarias",
            "thresholds_basis": (
                "percentiles medidos sobre 936 ventanas historicas (60/120/180 sesiones x 3 "
                "simbolos), no umbrales elegidos a ojo"
            ),
            "pass_rates_observed": {
                "horizontalidad": "~23%",
                "contencion": "~100% (guarda del trazado)",
                "rotacion": "~10%",
                "toques": "~14% (bordes en los extremos del tramo)",
                "volatilidad": "~75%",
            },
        },
        "warning": (
            "Clasifica la estructura observada; no predice cuanto durara el rango ni hacia "
            "donde rompera. Un rango valido puede romperse en la siguiente sesion."
        ),
    }
