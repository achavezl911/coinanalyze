from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from statistics import median, pstdev
from typing import Any


def number(value: Any, default: float = math.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


@dataclass(frozen=True)
class Condition:
    text: str
    weight: int
    predicate: Callable[[dict[str, Any]], bool]


SETUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "A",
        "name": "Distribución encubierta",
        "bias": "SHORT de mediano plazo",
        "horizon": "mediano plazo",
        "conditions": (
            Condition("CVD spot 24h vendedor", 25, lambda c: number(c.get("cvd_spot_24h")) < 0),
            Condition(
                "Precio lateral o subiendo", 20, lambda c: number(c.get("price_dir_1h")) >= 0
            ),
            Condition(
                "Racha de CVD spot vendedor ≥3", 20, lambda c: number(c.get("daily_streak")) <= -3
            ),
            Condition("CVD spot acumulado bajista", 20, lambda c: number(c.get("daily_slope")) < 0),
            Condition(
                "OI sube con funding positivo",
                15,
                lambda c: number(c.get("oi_chg_24h_pct")) > 0 and number(c.get("fr_avg")) > 0,
            ),
        ),
        "reading": "El spot vende mientras el precio o el apalancamiento sostienen la cotización.",
        "invalidation": "El CVD spot gira comprador o se rompe la racha vendedora.",
    },
    {
        "id": "B",
        "name": "Acumulación silenciosa",
        "bias": "LONG de mediano plazo",
        "horizon": "mediano plazo",
        "conditions": (
            Condition("CVD spot 24h comprador", 25, lambda c: number(c.get("cvd_spot_24h")) > 0),
            Condition("Precio lateral o débil", 20, lambda c: number(c.get("price_dir_1h")) <= 0),
            Condition(
                "Racha de CVD spot comprador ≥3", 20, lambda c: number(c.get("daily_streak")) >= 3
            ),
            Condition("CVD spot acumulado alcista", 20, lambda c: number(c.get("daily_slope")) > 0),
            Condition(
                "Funding neutro/negativo y OI no acelerado",
                15,
                lambda c: (
                    number(c.get("fr_avg")) <= 0.01 and number(c.get("oi_chg_24h_pct")) <= 1.0
                ),
            ),
        ),
        "reading": "Demanda spot absorbe oferta sin que el precio refleje aún toda la presión.",
        "invalidation": "El CVD spot gira vendedor o hay ruptura bajista con spot vendedor.",
    },
    {
        "id": "C",
        "name": "Squeeze de shorts",
        "bias": "LONG de corto plazo",
        "horizon": "corto plazo",
        "conditions": (
            Condition("Funding negativo", 25, lambda c: number(c.get("fr_avg")) < 0),
            Condition(
                "Predomina liquidación de shorts",
                20,
                lambda c: 0 < number(c.get("liq_ratio_24h"), 1) < 1,
            ),
            Condition(
                "Mercado cargado de OI", 15, lambda c: number(c.get("oi_vol_24h_ratio")) >= 0.5
            ),
            Condition("Precio rebotando", 15, lambda c: number(c.get("price_dir_1h")) > 0),
            Condition(
                "Participación compradora acelera",
                25,
                lambda c: (
                    number(c.get("btr_15m")) > number(c.get("btr_1h")) > number(c.get("btr_24h"))
                ),
            ),
        ),
        "reading": "Exceso de cortos vulnerable a liquidación en cascada.",
        "invalidation": "Funding se normaliza o el precio pierde soporte con OI creciente.",
    },
    {
        "id": "D",
        "name": "Euforia / techo táctico",
        "bias": "Reducir LONG / SHORT táctico",
        "horizon": "corto plazo",
        "conditions": (
            Condition("Funding elevado", 25, lambda c: number(c.get("fr_avg")) >= 0.03),
            Condition(
                "OI y precio suben",
                25,
                lambda c: number(c.get("oi_chg_24h_pct")) > 1 and number(c.get("price_dir_1h")) > 0,
            ),
            Condition("CVD spot no confirma", 25, lambda c: number(c.get("cvd_spot_24h")) <= 0),
            Condition(
                "Longs comienzan a liquidarse", 25, lambda c: number(c.get("liq_ratio_24h"), 1) > 1
            ),
        ),
        "reading": "Alza apalancada sin respaldo spot, vulnerable a corrección violenta.",
        "invalidation": "El spot se suma y el funding se normaliza.",
    },
    {
        "id": "E",
        "name": "Capitulación / suelo táctico",
        "bias": "LONG contrarian",
        "horizon": "corto plazo",
        "conditions": (
            Condition(
                "Long liquidations dominantes", 25, lambda c: number(c.get("liq_ratio_24h"), 1) >= 2
            ),
            Condition("OI cae con fuerza", 20, lambda c: number(c.get("oi_chg_24h_pct")) <= -2),
            Condition("Spot CVD gira comprador", 25, lambda c: number(c.get("cvd_spot_24h")) > 0),
            Condition("Precio aún débil", 15, lambda c: number(c.get("price_dir_1h")) <= 0),
            Condition("Funding neutro o negativo", 15, lambda c: number(c.get("fr_avg")) <= 0),
        ),
        "reading": "Desapalancamiento forzado con indicios de compra spot institucional.",
        "invalidation": "Continúan liquidaciones sin acumulación spot.",
    },
)


def evaluate_setups(snapshot: dict[str, Any], daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    streak = 0
    for row in reversed(daily_rows):
        spot = number(row.get("cvd_spot_usd"))
        sign = 1 if spot > 0 else -1 if spot < 0 else 0
        if sign == 0:
            break
        if streak == 0:
            streak = sign
        elif (streak > 0 and sign > 0) or (streak < 0 and sign < 0):
            streak += sign
        else:
            break

    cumulative = [number(row.get("cumulative_spot")) for row in daily_rows]
    cumulative = [value for value in cumulative if math.isfinite(value)]
    slope = 0.0
    if len(cumulative) >= 2:
        sample = cumulative[-min(5, len(cumulative)) :]
        slope = (sample[-1] - sample[0]) / max(len(sample) - 1, 1)

    context = dict(snapshot)
    context["daily_streak"] = streak
    context["daily_slope"] = slope

    evaluations: list[dict[str, Any]] = []
    for setup in SETUPS:
        matched: list[str] = []
        missing: list[str] = []
        score = 0
        for condition in setup["conditions"]:
            if condition.predicate(context):
                matched.append(condition.text)
                score += condition.weight
            else:
                missing.append(condition.text)
        state = "activo" if score >= 70 else "vigilancia" if score >= 50 else "inactivo"
        evaluations.append(
            {
                "id": setup["id"],
                "name": setup["name"],
                "bias": setup["bias"],
                "horizon": setup["horizon"],
                "confidence": score,
                "state": state,
                "matched": matched,
                "missing": missing,
                "reading": setup["reading"],
                "invalidation": setup["invalidation"],
            }
        )
    evaluations.sort(key=lambda item: item["confidence"], reverse=True)
    return {
        "daily_streak": streak,
        "daily_slope": slope,
        "daily_flow_source": "cvd_spot_usd (Binance+Bybit)",
        "primary": evaluations[0] if evaluations else None,
        "setups": evaluations,
        "warning": "Sesgo probabilístico. No constituye señal mecánica ni recomendación financiera.",
    }


def daily_flow_read(daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Resume la última sesión cerrada sin convertir CVD en inventario no observable.

    El cuartil mide si la agresión spot fue excepcional frente a la historia disponible.
    La respuesta del precio dice si esa agresión logró desplazar la cotización. Una posible
    reversión sólo se eleva cuando una defensa previa recibe confirmación compradora después.
    """
    rows = sorted(daily_rows, key=lambda row: str(row.get("session_date") or ""))
    if not rows:
        return {"available": False, "reason": "No hay sesiones cerradas para interpretar."}

    latest = rows[-1]
    spot = number(latest.get("cvd_spot_usd"))
    futures = number(latest.get("cvd_fut_usd"))
    price = number(latest.get("price_chg_pct"))
    percentile = number(latest.get("cvd_spot_percentile"))
    if not all(math.isfinite(value) for value in (spot, futures, price, percentile)):
        return {
            "available": False,
            "as_of": str(latest.get("session_date") or ""),
            "reason": "La última sesión no tiene CVD spot, futuros, precio y percentil completos.",
        }

    strong_buy = spot > 0 and percentile >= 75
    strong_sell = spot < 0 and percentile <= 25
    both_buy = spot > 0 and futures > 0
    both_sell = spot < 0 and futures < 0
    prior_defense = next(
        (
            row
            for row in reversed(rows[-4:-1])
            if row.get("price_response") == "venta_sin_caida"
            and number(row.get("cvd_spot_percentile"), 50.0) <= 25
        ),
        None,
    )

    tone = "neutral"
    state = "sin_ventaja"
    headline = "Flujo sin ventaja clara"
    interpretation = "La agresión spot no es extrema o spot y futuros no producen una respuesta concluyente."
    action = "ESPERAR · no forzar una lectura direccional"
    confirmation = "Esperar agresión spot extrema y una respuesta del precio coherente."
    invalidation = "No aplica mientras no exista una hipótesis direccional."
    evidence = 1

    if strong_buy and both_buy and price > 0 and prior_defense is not None:
        defense_date = str(prior_defense.get("session_date") or "la sesión previa")
        tone, state, evidence = "positive", "confirmando", 4
        headline = "Posible reversión: compra spot fuerte"
        interpretation = (
            f"Después de la defensa del {defense_date}, spot y futuros compraron y el precio "
            "avanzó. La secuencia es compatible con oferta absorbida y demanda tomando control."
        )
        action = "VIGILAR LONG · confirmación en curso"
        confirmation = "La siguiente sesión debe conservar el avance y evitar volver al cuartil vendedor spot."
        invalidation = "Nueva venta spot fuerte con caída del precio; la defensa habría fallado."
    elif strong_buy and both_buy and price > 0:
        tone, state, evidence = "positive", "demanda", 3
        headline = "Se está comprando fuerte en spot"
        interpretation = "Spot y futuros compran con agresión y el precio responde al alza; hay demanda efectiva, todavía basada en una sesión."
        action = "SESGO LONG · esperar continuidad o retroceso defendido"
        confirmation = "Otra sesión con CVD spot comprador o un retroceso que no pierda el avance."
        invalidation = "Compra agresiva sin nueva subida o giro al cuartil vendedor spot."
    elif strong_buy and price <= 0:
        tone, state, evidence = "negative", "oferta", 3 if both_buy else 2
        headline = "Compran fuerte, pero el precio no sube"
        interpretation = "La demanda agresiva spot no consigue desplazar el precio; es compatible con oferta pasiva absorbiendo compras."
        action = "NO PERSEGUIR LONG · posible techo o rango"
        confirmation = "Para invalidar la oferta, el precio debe cerrar al alza con spot aún comprador."
        invalidation = "Si spot gira vendedor y el precio cae, la lectura pasa a continuación bajista."
    elif strong_buy and futures < 0:
        tone, state, evidence = "positive", "defensa_inicial", 2
        headline = "Spot compra fuerte contra futuros vendedores"
        interpretation = "La demanda spot compensa presión vendedora apalancada. Es una primera defensa, no una reversión confirmada."
        action = "VIGILAR LONG · aún no entrar por esta señal sola"
        confirmation = "Futuros deben dejar de vender y el precio mantener un cierre positivo."
        invalidation = "Venta spot y futuros conjunta con caída del precio."
    elif strong_sell and both_sell and price >= 0:
        tone, state, evidence = "positive", "defensa", 3
        headline = "Por más que venden, el precio no cae"
        interpretation = "La venta agresiva spot y de futuros no desplaza el precio; es una huella de posible absorción compradora, no prueba directa de acumulación."
        action = "POSIBLE REVERSIÓN · esperar compra que confirme"
        confirmation = "CVD spot en cuartil comprador y cierre positivo en una de las próximas sesiones."
        invalidation = "Nueva venta fuerte con caída; la supuesta defensa no sostuvo el precio."
    elif strong_sell and price < 0:
        tone, state, evidence = "negative", "oferta", 3 if both_sell else 2
        headline = "Venta spot fuerte con caída"
        interpretation = "La oferta agresiva sí produce desplazamiento bajista; todavía no aparece una huella de suelo."
        action = "NO ANTICIPAR SUELO · sesgo defensivo"
        confirmation = "Un suelo exige venta fuerte sin caída y después demanda spot con seguimiento."
        invalidation = "El escenario bajista pierde fuerza si la venta deja de mover el precio."
    elif both_sell and price >= 0:
        tone, state, evidence = "positive", "defensa", 2
        headline = "Venden, pero el precio no cae"
        interpretation = "Hay posible defensa, aunque la venta spot no alcanza el cuartil extremo."
        action = "VIGILAR · falta intensidad para hablar de reversión"
        confirmation = "Compra spot fuerte con avance del precio."
        invalidation = "Venta conjunta con caída en la siguiente sesión."
    elif both_buy and price > 0:
        tone, state, evidence = "positive", "demanda", 2
        headline = "Compras con seguimiento, aún no extremas"
        interpretation = "Spot y futuros compran y el precio avanza, pero el CVD spot no está en su cuartil fuerte."
        action = "VIGILAR LONG · exigir continuidad"
        confirmation = "CVD spot debe entrar al cuartil comprador o sostener varios cierres positivos."
        invalidation = "Compra sin subida o giro vendedor conjunto."
    elif both_sell and price < 0:
        tone, state, evidence = "negative", "oferta", 2
        headline = "Venden y el precio cae, sin intensidad extrema"
        interpretation = "La oferta tiene seguimiento bajista, aunque el CVD spot no está en su cuartil vendedor."
        action = "SESGO DEFENSIVO · no anticipar un suelo"
        confirmation = "La presión se vuelve extrema si el CVD spot entra al cuartil vendedor."
        invalidation = "La venta deja de mover el precio o aparece compra spot fuerte."
    elif both_buy and price <= 0:
        tone, state, evidence = "negative", "oferta", 2
        headline = "Compran, pero el precio no sube"
        interpretation = "La compra conjunta no logra avance; posible oferta, todavía sin intensidad spot extrema."
        action = "ESPERAR · no perseguir el precio"
        confirmation = "Un cierre positivo con CVD spot fuerte invalidaría la posible oferta."
        invalidation = "Venta conjunta con caída confirmaría que la demanda falló."

    confluence = "alta" if evidence >= 3 else "media" if evidence == 2 else "baja"
    return {
        "available": True,
        "as_of": str(latest.get("session_date") or ""),
        "headline": headline,
        "tone": tone,
        "state": state,
        "confluence": confluence,
        "action": action,
        "interpretation": interpretation,
        "confirmation": confirmation,
        "invalidation": invalidation,
        "metrics": {
            "cvd_spot_usd": spot,
            "cvd_spot_percentile": percentile,
            "cvd_fut_usd": futures,
            "price_chg_pct": price,
            "oi_chg_usd": number(latest.get("oi_chg_usd"), 0.0),
        },
        "method": "Cuartiles históricos de CVD spot + dirección de futuros + respuesta del precio + secuencia de hasta 4 sesiones.",
        "warning": "La confluencia mide acuerdo entre evidencias, no probabilidad de ganancia ni una orden de entrada.",
    }


CVD_LOOKBACK_SESSIONS = 90
CVD_SIGNAL_WINDOW = 3
CVD_HORIZON_SESSIONS = 2
CVD_SIGNAL_THRESHOLD = 30.0

BARRIER_LOOKBACK_SESSIONS = 730
BARRIER_PIVOT_WIDTH = 2
# 720 barras de 4h = 120 dias. Depende de que ohlcv 5min tenga esa profundidad; el rollup en
# vivo solo la construye hacia adelante, asi que sin backfill la cobertura real es mucho menor
# y hay que declararla en vez de dejar que el panel aparente 120 dias de pivotes.
BARRIER_INTRADAY_TARGET_BARS = 720
MARKET_MEMORY_DAYS = 730
MARKET_MEMORY_ANALOGS = 5


def _percentile(value: float, sample: list[float]) -> float:
    return sum(item <= value for item in sample) / len(sample) * 100.0


def _memory_features(rows: list[dict[str, Any]], index: int) -> dict[str, float] | None:
    if index < 60:
        return None
    window = rows[index - 59 : index + 1]
    closes = [number(row.get("close")) for row in window]
    highs = [number(row.get("high")) for row in window]
    lows = [number(row.get("low")) for row in window]
    volumes = [number(row.get("volume_usd")) for row in window]
    if not all(math.isfinite(value) and value > 0 for value in closes + highs + lows):
        return None
    returns = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(1, len(closes))]
    low_60, high_60 = min(lows), max(highs)
    span = high_60 - low_60
    valid_volumes = [value for value in volumes if math.isfinite(value) and value > 0]
    volume_ratio = 1.0
    if len(valid_volumes) >= 20:
        recent = [value for value in volumes[-5:] if math.isfinite(value) and value > 0]
        volume_ratio = median(recent) / median(valid_volumes) if recent else 1.0
    return {
        "return_5d_pct": (closes[-1] / closes[-6] - 1) * 100,
        "return_20d_pct": (closes[-1] / closes[-21] - 1) * 100,
        "drawdown_60d_pct": (closes[-1] / high_60 - 1) * 100,
        "range_position_60d_pct": (closes[-1] - low_60) / span * 100 if span > 0 else 50.0,
        "volatility_20d_pct": pstdev(returns[-20:]),
        "volume_ratio_5d": volume_ratio,
    }


def market_memory_read(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compara el régimen de precio actual con episodios pasados sin mirar su futuro.

    Es memoria descriptiva de dos años, no una predicción: el CVD spot táctico conserva
    su ventana de 90 sesiones porque responde a un horizonte distinto.
    """
    ordered = sorted(rows, key=lambda row: str(row.get("date") or row.get("bucket") or ""))
    ordered = ordered[-MARKET_MEMORY_DAYS:]
    if len(ordered) < 120:
        return {
            "available": False,
            "sessions": len(ordered),
            "reason": "Se necesitan al menos 120 días diarios completos para comparar regímenes.",
        }
    current_index = len(ordered) - 1
    current = _memory_features(ordered, current_index)
    if current is None:
        return {"available": False, "sessions": len(ordered), "reason": "Historia diaria incompleta."}

    feature_names = tuple(current)
    candidates: list[tuple[int, dict[str, float]]] = []
    for index in range(60, current_index - 20):
        features = _memory_features(ordered, index)
        if features is not None:
            candidates.append((index, features))
    if len(candidates) < 20:
        return {"available": False, "sessions": len(ordered), "reason": "No hay suficientes episodios comparables."}

    scales: dict[str, float] = {}
    for name in feature_names:
        values = [features[name] for _, features in candidates]
        center = median(values)
        mad = median([abs(value - center) for value in values])
        scales[name] = mad if mad > 1e-9 else max(abs(center) * 0.1, 1.0)
    ranked = sorted(
        (
            sum(abs(features[name] - current[name]) / scales[name] for name in feature_names),
            index,
            features,
        )
        for index, features in candidates
    )
    selected: list[tuple[float, int, dict[str, float]]] = []
    for item in ranked:
        if all(abs(item[1] - other[1]) >= 20 for other in selected):
            selected.append(item)
        if len(selected) == MARKET_MEMORY_ANALOGS:
            break

    analogs: list[dict[str, Any]] = []
    for distance, index, features in selected:
        close = number(ordered[index].get("close"))
        future = {
            f"return_{days}d_pct": (number(ordered[index + days].get("close")) / close - 1) * 100
            for days in (5, 10, 20)
        }
        future_closes = [number(row.get("close")) for row in ordered[index + 1 : index + 21]]
        analogs.append(
            {
                "date": str(ordered[index].get("date") or ordered[index].get("bucket"))[:10],
                "similarity_score": round(100 / (1 + distance), 1),
                "state": {name: round(value, 2) for name, value in features.items()},
                "forward": {
                    **{name: round(value, 2) for name, value in future.items()},
                    "best_20d_pct": round((max(future_closes) / close - 1) * 100, 2),
                    "worst_20d_pct": round((min(future_closes) / close - 1) * 100, 2),
                },
            }
        )

    forward_20 = [item["forward"]["return_20d_pct"] for item in analogs]
    median_20 = median(forward_20)
    positive = sum(value > 0 for value in forward_20)
    tilt = "LONG" if median_20 >= 3 and positive >= 3 else "SHORT" if median_20 <= -3 and positive <= 2 else "NEUTRAL"
    position = current["range_position_60d_pct"]
    ret20 = current["return_20d_pct"]
    if position <= 30 and current["return_5d_pct"] > 0:
        phase = "rebote desde zona baja"
    elif position <= 30 and ret20 < 0:
        phase = "presión bajista en zona baja"
    elif position >= 70 and ret20 > 0:
        phase = "expansión cerca de máximos del rango"
    elif abs(ret20) <= 4:
        phase = "compresión lateral"
    else:
        phase = "transición de régimen"

    highs = [number(row.get("high")) for row in ordered]
    lows = [number(row.get("low")) for row in ordered]
    close = number(ordered[-1].get("close"))
    return {
        "available": True,
        "coverage": {
            "days": len(ordered),
            "from": str(ordered[0].get("date") or ordered[0].get("bucket"))[:10],
            "to": str(ordered[-1].get("date") or ordered[-1].get("bucket"))[:10],
            "target_days": MARKET_MEMORY_DAYS,
        },
        "phase": phase,
        "historical_tilt": tilt,
        "current": {
            **{name: round(value, 2) for name, value in current.items()},
            "two_year_high": round(max(highs), 8),
            "two_year_low": round(min(lows), 8),
            "distance_from_high_pct": round((close / max(highs) - 1) * 100, 2),
            "distance_from_low_pct": round((close / min(lows) - 1) * 100, 2),
        },
        "analogs": analogs,
        "analog_summary": {
            "sample": len(analogs),
            "median_return_5d_pct": round(median(item["forward"]["return_5d_pct"] for item in analogs), 2),
            "median_return_10d_pct": round(median(item["forward"]["return_10d_pct"] for item in analogs), 2),
            "median_return_20d_pct": round(median_20, 2),
            "positive_20d_count": positive,
        },
        "method": "5 vecinos no solapados por retorno 5/20d, posición y drawdown 60d, volatilidad 20d y volumen relativo; distancia robusta por MAD",
        "source": "OHLCV diario de futuros Binance vía Coinalyze; no contiene CVD spot histórico.",
        "warning": "Los análogos describen lo que ocurrió después en pocos casos similares; no son probabilidad, señal autónoma ni garantía de repetición.",
    }


def _cvd_observation(rows: list[dict[str, Any]], index: int) -> dict[str, float] | None:
    history = rows[index - CVD_LOOKBACK_SESSIONS : index]
    if len(history) < CVD_LOOKBACK_SESSIONS or index < CVD_SIGNAL_WINDOW:
        return None
    spot_history = [number(row.get("cvd_spot_usd")) for row in history]
    fut_history = [number(row.get("cvd_fut_usd")) for row in history]
    close_history = [number(row.get("price_close")) for row in history]
    current = rows[index - CVD_SIGNAL_WINDOW + 1 : index + 1]
    current_spot = [number(row.get("cvd_spot_usd")) for row in current]
    current_fut = [number(row.get("cvd_fut_usd")) for row in current]
    current_close = number(rows[index].get("price_close"))
    prior_close = number(rows[index - CVD_SIGNAL_WINDOW].get("price_close"))
    values = spot_history + fut_history + close_history + current_spot + current_fut
    if not all(math.isfinite(value) for value in values + [current_close, prior_close]):
        return None
    if min(close_history + [current_close, prior_close]) <= 0:
        return None

    spot_windows = [
        sum(spot_history[i : i + CVD_SIGNAL_WINDOW])
        for i in range(len(spot_history) - CVD_SIGNAL_WINDOW + 1)
    ]
    fut_windows = [
        sum(fut_history[i : i + CVD_SIGNAL_WINDOW])
        for i in range(len(fut_history) - CVD_SIGNAL_WINDOW + 1)
    ]
    price_windows = [
        (close_history[i] / close_history[i - CVD_SIGNAL_WINDOW] - 1) * 100
        for i in range(CVD_SIGNAL_WINDOW, len(close_history))
    ]
    spot_sum = sum(current_spot)
    fut_sum = sum(current_fut)
    price_change = (current_close / prior_close - 1) * 100
    spot_percentile = _percentile(spot_sum, spot_windows)
    fut_percentile = _percentile(fut_sum, fut_windows)
    price_percentile = _percentile(price_change, price_windows)
    score = spot_percentile - price_percentile
    return {
        "score": score,
        "spot_sum": spot_sum,
        "fut_sum": fut_sum,
        "price_change_pct": price_change,
        "spot_percentile": spot_percentile,
        "fut_percentile": fut_percentile,
        "price_percentile": price_percentile,
        "spot_futures_gap": spot_percentile - fut_percentile,
    }


def _cvd_side(score: float) -> str:
    if score >= CVD_SIGNAL_THRESHOLD:
        return "LONG"
    if score <= -CVD_SIGNAL_THRESHOLD:
        return "SHORT"
    return "ESPERAR"


def cvd_swing_read(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Interpreta CVD spot frente a precio para una operación de dos sesiones.

    La escala de cada activo cambia con el tiempo, por eso se comparan percentiles y no
    USD crudos. El backtest es walk-forward: cada observación solo ve sus 90 sesiones
    anteriores. Las señales se solapan y no incluyen costes, por lo que la tasa de acierto
    es contexto histórico, no una probabilidad futura.
    """
    ordered = sorted(rows, key=lambda row: str(row.get("session_date") or ""))
    minimum = CVD_LOOKBACK_SESSIONS + CVD_SIGNAL_WINDOW
    if len(ordered) < minimum:
        return {
            "available": False,
            "reason": f"Se necesitan al menos {minimum} sesiones completas.",
            "sessions": len(ordered),
        }
    latest = _cvd_observation(ordered, len(ordered) - 1)
    if latest is None:
        return {"available": False, "reason": "La ventana contiene datos incompletos."}

    signed_returns: list[float] = []
    longs = shorts = 0
    for index in range(CVD_LOOKBACK_SESSIONS, len(ordered) - CVD_HORIZON_SESSIONS):
        observation = _cvd_observation(ordered, index)
        if observation is None:
            continue
        side = _cvd_side(observation["score"])
        if side == "ESPERAR":
            continue
        close_now = number(ordered[index].get("price_close"))
        close_future = number(ordered[index + CVD_HORIZON_SESSIONS].get("price_close"))
        if not (math.isfinite(close_now) and math.isfinite(close_future) and close_now > 0):
            continue
        raw_return = (close_future / close_now - 1) * 100
        signed_returns.append(raw_return if side == "LONG" else -raw_return)
        longs += side == "LONG"
        shorts += side == "SHORT"

    side = _cvd_side(latest["score"])
    strength = (
        "alta" if abs(latest["score"]) >= 50 else "media" if side != "ESPERAR" else "sin ventaja"
    )
    if side == "LONG":
        thesis = "El CVD spot supera a la respuesta del precio: hay demanda que el precio todavía no refleja por completo."
        invalidation = "Cancelar si el score baja de +15 o el CVD spot de 3 sesiones gira vendedor."
    elif side == "SHORT":
        thesis = "El precio supera al CVD spot: el avance no tiene confirmación equivalente de demanda spot."
        invalidation = (
            "Cancelar si el score sube de -15 o el CVD spot de 3 sesiones gira comprador."
        )
    else:
        thesis = "Precio y CVD spot no están lo bastante separados frente a su historia; no hay ventaja CVD clara."
        invalidation = (
            "Esperar a que la separación alcance ±30 puntos y la estructura de 4h/8h confirme."
        )

    previous_closes = [number(row.get("price_close")) for row in ordered[-4:-1]]
    levels = {
        "last_close": round(number(ordered[-1].get("price_close")), 8),
        "confirm_above": round(max(previous_closes), 8),
        "confirm_below": round(min(previous_closes), 8),
    }
    trades = len(signed_returns)
    return {
        "available": True,
        "as_of": str(ordered[-1].get("session_date")),
        "signal": side,
        "score": round(latest["score"], 1),
        "strength": strength,
        "horizon": "2 sesiones",
        "thesis": thesis,
        "invalidation": invalidation,
        "evidence": {
            "cvd_spot_3s_usd": round(latest["spot_sum"], 2),
            "cvd_futures_3s_usd": round(latest["fut_sum"], 2),
            "price_change_3s_pct": round(latest["price_change_pct"], 3),
            "cvd_spot_percentile_90s": round(latest["spot_percentile"], 1),
            "cvd_futures_percentile_90s": round(latest["fut_percentile"], 1),
            "price_percentile_90s": round(latest["price_percentile"], 1),
            "spot_vs_price_points": round(latest["score"], 1),
            "spot_vs_futures_points": round(latest["spot_futures_gap"], 1),
        },
        "reference_levels": levels,
        "backtest": {
            "method": "walk-forward 90 sesiones; retorno firmado a 2 sesiones",
            "trades": trades,
            "longs": longs,
            "shorts": shorts,
            "win_rate_pct": round(sum(value > 0 for value in signed_returns) / trades * 100, 1)
            if trades
            else None,
            "mean_return_pct": round(sum(signed_returns) / trades, 3) if trades else None,
            "median_return_pct": round(median(signed_returns), 3) if trades else None,
            "sample_status": "ok" if trades >= 30 else "insuficiente",
        },
        "method": {
            "lookback_sessions": CVD_LOOKBACK_SESSIONS,
            "signal_window_sessions": CVD_SIGNAL_WINDOW,
            "signal_threshold_points": CVD_SIGNAL_THRESHOLD,
            "spot_venues": "Binance+Bybit",
            "futures_venues": "Binance; solo contexto, no entra en la señal",
        },
        "warning": "Backtest con señales solapadas, sin comisiones ni slippage; no es probabilidad ni recomendación financiera.",
    }


def _barrier_candidates(
    rows: list[dict[str, Any]],
    *,
    source: str,
    time_key: str,
    high_key: str,
    low_key: str,
    close_key: str,
    volume_key: str,
    bar_days: float,
    cvd_key: str | None = None,
) -> tuple[list[dict[str, Any]], float | None]:
    clean: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda item: str(item.get(time_key) or "")):
        close = number(row.get(close_key))
        if not math.isfinite(close) or close <= 0:
            continue
        high = number(row.get(high_key))
        low = number(row.get(low_key))
        # El rollup conserva cierres desde antes que high/low/volumen. Los cierres antiguos
        # siguen aportando un nivel, pero sin puntos de volumen ni falsa precision de mecha.
        high = high if math.isfinite(high) and high > 0 else close
        low = low if math.isfinite(low) and low > 0 else close
        cvd = number(row.get(cvd_key)) if cvd_key else math.nan
        clean.append(
            {
                "time": str(row.get(time_key) or ""),
                "high": high,
                "low": low,
                "close": close,
                "volume": number(row.get(volume_key)),
                "cvd": cvd,
                "cvd_known": math.isfinite(cvd),
            }
        )
    if len(clean) < BARRIER_PIVOT_WIDTH * 2 + 3:
        return [], None

    true_ranges = []
    for index, row in enumerate(clean):
        previous = clean[index - 1]["close"] if index else row["close"]
        true_ranges.append(
            max(row["high"] - row["low"], abs(row["high"] - previous), abs(row["low"] - previous))
        )
    atr_sample = [value for value in true_ranges[-14:] if value > 0]
    atr = median(atr_sample) if atr_sample else None
    volumes = [row["volume"] for row in clean if math.isfinite(row["volume"]) and row["volume"] > 0]
    normal_volume = median(volumes) if volumes else None
    if not atr:
        return [], None

    candidates: list[dict[str, Any]] = []
    k = BARRIER_PIVOT_WIDTH
    for index in range(k, len(clean) - k):
        row = clean[index]
        neighbors = clean[index - k : index] + clean[index + 1 : index + k + 1]
        following = clean[index + 1 : min(len(clean), index + 4)]
        if not following:
            continue
        pivots = []
        # absorbed queda en None cuando la barra no trae CVD: sin ese dato la absorcion es
        # DESCONOCIDA, no "no hubo". Tratarla como False dejaba el componente muerto.
        if row["high"] > max(item["high"] for item in neighbors):
            reaction = max(0.0, (row["high"] - min(item["low"] for item in following)) / atr)
            pivots.append(
                ("rechazo_alto", row["high"], reaction, row["cvd"] > 0 if row["cvd_known"] else None)
            )
        if row["low"] < min(item["low"] for item in neighbors):
            reaction = max(0.0, (max(item["high"] for item in following) - row["low"]) / atr)
            pivots.append(
                ("rechazo_bajo", row["low"], reaction, row["cvd"] < 0 if row["cvd_known"] else None)
            )
        for origin, level, reaction, absorbed in pivots:
            raw_volume = (
                row["volume"] if math.isfinite(row["volume"]) and row["volume"] > 0 else None
            )
            candidates.append(
                {
                    "level": level,
                    "origin": origin,
                    "source": source,
                    "time": row["time"],
                    "age_days": (len(clean) - 1 - index) * bar_days,
                    "reaction_atr": reaction,
                    "volume_usd": raw_volume,
                    "volume_multiple": raw_volume / normal_volume
                    if raw_volume and normal_volume
                    else None,
                    "absorbed": absorbed,
                    "touch_weight": 1.5 if source == "1d" else 1.0,
                }
            )
    return candidates, atr


def _barrier_zones(
    candidates: list[dict[str, Any]], price: float, tolerance: float
) -> list[dict[str, Any]]:
    clusters: list[list[dict[str, Any]]] = []
    centers: list[float] = []
    for candidate in sorted(candidates, key=lambda item: item["level"]):
        matches = [
            (abs(candidate["level"] - center), index)
            for index, center in enumerate(centers)
            if abs(candidate["level"] - center) <= tolerance
        ]
        if not matches:
            clusters.append([candidate])
            centers.append(candidate["level"])
            continue
        _, selected = min(matches)
        clusters[selected].append(candidate)
        weights = [item["touch_weight"] for item in clusters[selected]]
        centers[selected] = sum(
            item["level"] * weight for item, weight in zip(clusters[selected], weights, strict=True)
        ) / sum(weights)

    zones = []
    for cluster, center in zip(clusters, centers, strict=True):
        touches = len(cluster)
        touch_equivalent = sum(item["touch_weight"] for item in cluster)
        reactions = [item["reaction_atr"] for item in cluster]
        volume_multiples = [
            item["volume_multiple"] for item in cluster if item["volume_multiple"] is not None
        ]
        reaction_atr = median(reactions)
        volume_multiple = median(volume_multiples) if volume_multiples else None
        known_absorption = [item["absorbed"] for item in cluster if item["absorbed"] is not None]
        absorption_rate = sum(known_absorption) / len(known_absorption) if known_absorption else None
        age_days = min(item["age_days"] for item in cluster)
        # El score se reparte sobre los componentes que SI se pudieron medir. Sumar 0 por un
        # componente ausente no es neutral: hunde el score y desplaza la etiqueta
        # fuerte/media/debil hacia abajo sin que nada lo indique.
        parts = [
            ("toques", min(touch_equivalent / 4, 1), 35.0),
            ("reaccion_atr", min(reaction_atr / 2, 1), 25.0),
            (
                "volumen_relativo",
                min(max(volume_multiple - 0.5, 0) / 1.5, 1) if volume_multiple is not None else None,
                20.0,
            ),
            ("absorcion_cvd", absorption_rate, 10.0),
            ("recencia", max(0.0, 1 - age_days / BARRIER_LOOKBACK_SESSIONS), 10.0),
        ]
        available = [(name, value, weight) for name, value, weight in parts if value is not None]
        weight_total = sum(weight for _, _, weight in available)
        score = (
            min(100.0, sum(value * weight for _, value, weight in available) / weight_total * 100)
            if weight_total
            else 0.0
        )
        missing = [name for name, value, _ in parts if value is None]
        difficulty = "fuerte" if score >= 70 else "media" if score >= 50 else "débil"
        references = {}
        for source in ("4h", "1d"):
            values = [
                item["volume_usd"]
                for item in cluster
                if item["source"] == source and item["volume_usd"]
            ]
            references[source] = round(median(values), 2) if values else None
        lows = [item["level"] for item in cluster]
        pad = tolerance * 0.2
        zones.append(
            {
                "center": round(center, 8),
                "low": round(min(lows) - pad, 8),
                "high": round(max(lows) + pad, 8),
                "score": round(score, 1),
                "difficulty": difficulty,
                "touches": touches,
                "weighted_touches": round(touch_equivalent, 1),
                "high_rejections": sum(item["origin"] == "rechazo_alto" for item in cluster),
                "low_rejections": sum(item["origin"] == "rechazo_bajo" for item in cluster),
                "reaction_atr": round(reaction_atr, 2),
                "absorption_rate": round(absorption_rate, 2)
                if absorption_rate is not None
                else None,
                "scored_components": [name for name, _, _ in available],
                "unavailable_components": missing,
                "score_weight_pct": round(weight_total, 1),
                "volume_multiple": round(volume_multiple, 2)
                if volume_multiple is not None
                else None,
                "volume_reference_usd": references,
                "last_touch": min(cluster, key=lambda item: item["age_days"])["time"],
                "age_days": round(age_days, 1),
                "sources": sorted({item["source"] for item in cluster}),
            }
        )
    return zones


def price_barrier_read(
    daily_rows: list[dict[str, Any]],
    intraday_rows: list[dict[str, Any]],
    current_price: Any,
    live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Estima dificultad de soportes/resistencias; no pretende ver liquidez oculta."""
    price = number(current_price)
    if not math.isfinite(price) or price <= 0:
        return {"available": False, "reason": "Precio actual no disponible."}
    daily = daily_rows[-BARRIER_LOOKBACK_SESSIONS:]
    daily_candidates, daily_atr = _barrier_candidates(
        daily,
        source="1d",
        time_key="session_date",
        high_key="price_high",
        low_key="price_low",
        close_key="price_close",
        volume_key="volume_usd",
        cvd_key="cvd_spot_usd",
        bar_days=1.0,
    )
    intraday_candidates, _ = _barrier_candidates(
        intraday_rows,
        source="4h",
        time_key="bucket",
        high_key="high",
        low_key="low",
        close_key="close",
        volume_key="volume_usd",
        cvd_key="cvd_spot_usd",
        bar_days=1 / 6,
    )
    intraday_coverage = round(
        min(100.0, len(intraday_rows) / BARRIER_INTRADAY_TARGET_BARS * 100), 1
    )
    intraday_status = (
        "complete"
        if intraday_coverage >= 90
        else "partial"
        if intraday_coverage >= 25
        else "insufficient"
    )
    candidates = daily_candidates + intraday_candidates
    if len(candidates) < 2:
        return {
            "available": False,
            "reason": "No hay suficientes pivotes para formar barreras.",
            "current_price": price,
        }
    tolerance = max(price * 0.0035, (daily_atr or 0) * 0.25)
    zones = _barrier_zones(candidates, price, tolerance)
    active = [zone for zone in zones if zone["low"] <= price <= zone["high"]]
    supports = sorted(
        (zone for zone in zones if zone["center"] < price and zone not in active),
        key=lambda zone: zone["center"],
        reverse=True,
    )
    resistances = sorted(
        (zone for zone in zones if zone["center"] > price and zone not in active),
        key=lambda zone: zone["center"],
    )
    support = supports[0] if supports else None
    resistance = resistances[0] if resistances else None
    active_zone = max(active, key=lambda zone: zone["score"]) if active else None

    for zone, side in ((support, "support"), (resistance, "resistance")):
        if zone is None:
            continue
        edge = zone["high"] if side == "support" else zone["low"]
        zone["distance_pct"] = round(abs(edge / price - 1) * 100, 3)

    live = live or {}
    volume_multiple = number(live.get("volume_multiple_15m"))
    delta_ratio = number(live.get("delta_ratio_15m"))
    price_move = number(live.get("price_move_15m_pct"))
    imbalance = number(live.get("imbalance_l5"))
    bull_pressure = 50.0
    if math.isfinite(delta_ratio):
        bull_pressure += max(-1.0, min(1.0, delta_ratio / 0.15)) * 25
    if math.isfinite(price_move):
        bull_pressure += max(-1.0, min(1.0, price_move / 0.30)) * 15
    if live.get("book_status") == "ok" and math.isfinite(imbalance):
        bull_pressure += max(-1.0, min(1.0, (imbalance - 0.5) / 0.15)) * 10
    absorption = "ninguna"
    if math.isfinite(delta_ratio) and math.isfinite(price_move):
        if delta_ratio >= 0.10 and price_move <= 0:
            absorption = "compras absorbidas"
            bull_pressure -= 25
        elif delta_ratio <= -0.10 and price_move >= 0:
            absorption = "ventas absorbidas"
            bull_pressure += 25
    bull_pressure = max(0.0, min(100.0, bull_pressure))
    effort = (
        min(max(volume_multiple, 0.0) / 1.5 * 100, 100) if math.isfinite(volume_multiple) else 50.0
    )
    attack_up = round(bull_pressure * 0.75 + effort * 0.25, 1)
    attack_down = round((100 - bull_pressure) * 0.75 + effort * 0.25, 1)
    near_support = bool(support and support["distance_pct"] <= 1.0)
    near_resistance = bool(resistance and resistance["distance_pct"] <= 1.0)

    if active_zone or (near_support and near_resistance):
        decision = "ESPERAR: zona en disputa"
    elif near_resistance:
        if attack_up >= 70:
            decision = "VIGILAR LONG de ruptura"
        elif resistance["score"] >= 50 and attack_down >= 55:
            decision = "VIGILAR SHORT por rechazo"
        else:
            decision = "ESPERAR frente a resistencia"
    elif near_support:
        if attack_down >= 70:
            decision = "VIGILAR SHORT de ruptura"
        elif support["score"] >= 50 and attack_up >= 55:
            decision = "VIGILAR LONG por rechazo"
        else:
            decision = "ESPERAR frente a soporte"
    else:
        decision = "ESPERAR: precio entre barreras"

    return {
        "available": True,
        "current_price": round(price, 8),
        "decision": decision,
        "active_zone": active_zone,
        "nearest_support": support,
        "nearest_resistance": resistance,
        "live_pressure": {
            "bull_score": round(bull_pressure, 1),
            "bear_score": round(100 - bull_pressure, 1),
            "breakout_up_score": attack_up,
            "breakdown_score": attack_down,
            "volume_15m_usd": live.get("volume_15m_usd"),
            "normal_volume_15m_usd": live.get("normal_volume_15m_usd"),
            "volume_multiple_15m": round(volume_multiple, 2)
            if math.isfinite(volume_multiple)
            else None,
            "delta_ratio_15m": round(delta_ratio, 3) if math.isfinite(delta_ratio) else None,
            "price_move_15m_pct": round(price_move, 3) if math.isfinite(price_move) else None,
            "absorption_15m": absorption,
            "book_imbalance_l5": round(imbalance, 3) if math.isfinite(imbalance) else None,
            "book_status": live.get("book_status", "missing"),
            "baseline_buckets": live.get("baseline_buckets"),
        },
        "long_case": {
            "rejection": f"Rechazo confirmado sobre {support['low']:.2f}" if support else None,
            "breakout": f"Cierre 15m sobre {resistance['high']:.2f} + retest"
            if resistance
            else None,
            "flow_requirement": "breakout_up_score >= 70 y volumen 15m >= 1.0x normal",
        },
        "short_case": {
            "rejection": f"Rechazo confirmado bajo {resistance['high']:.2f}"
            if resistance
            else None,
            "breakdown": f"Cierre 15m bajo {support['low']:.2f} + retest" if support else None,
            "flow_requirement": "breakdown_score >= 70 y volumen 15m >= 1.0x normal",
        },
        "method": {
            "lookback_daily_sessions": len(daily),
            "intraday_bars": len(intraday_rows),
            "intraday_target_bars": BARRIER_INTRADAY_TARGET_BARS,
            "intraday_coverage_pct": intraday_coverage,
            "intraday_coverage_status": intraday_status,
            "intraday_timeframe": "4h",
            "zone_tolerance_pct": round(tolerance / price * 100, 3),
            "score_components": "pesos toques 35 / reaccion ATR 25 / volumen relativo 20 / "
            "absorcion CVD 10 / recencia 10, RENORMALIZADOS sobre los componentes medibles de "
            "cada zona (ver scored_components y unavailable_components). Las velas diarias no "
            "llevan CVD: daily_session_agg va en sesion NYSE, desalineada del dia UTC de ohlcv.",
        },
        "warnings": (
            [
                f"Pivotes 4h calculados sobre {len(intraday_rows)} barras de "
                f"{BARRIER_INTRADAY_TARGET_BARS} objetivo ({intraday_coverage}%): las zonas "
                "intradia solo reflejan ese tramo reciente, no 120 dias."
            ]
            if intraday_status != "complete"
            else []
        ),
        "warning": "La dificultad es evidencia historica, no volumen oculto ni probabilidad. Una ruptura exige cierre 15m, volumen relativo, delta direccional y retest; no basta una mecha.",
    }
