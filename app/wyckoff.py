"""Deteccion automatica y explicable de rangos con lectura Wyckoff + flujo.

La parte estructural reutiliza las cinco pruebas del validador manual. Este modulo solo
automatiza lo que antes tenia que dibujar el operador: busca varias ventanas recientes,
propone bordes robustos y conserva el candidato mejor validado. La etiqueta Wyckoff no es una
probabilidad; resume si precio, volumen y flujo son mas compatibles con acumulacion,
distribucion o equilibrio.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from statistics import median
from typing import Any

from app.interpretation import number
from app.zones import RANGE_PASSES_FOR_FORMING, range_validate_read

RANGE_WINDOWS = (365, 270, 240, 180, 150, 120, 90, 75, 60, 45, 40)
RANGE_END_OFFSETS = (0, 5, 10, 15, 20, 30)
BIAS_THRESHOLD = 25.0


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _bar_date(bar: dict[str, Any]) -> date | None:
    value = bar.get("ts") or bar.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (TypeError, ValueError):
        return None


def _clean_bars(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for raw in bars:
        values = {key: number(raw.get(key)) for key in ("open", "high", "low", "close")}
        if not all(math.isfinite(value) and value > 0 for value in values.values()):
            continue
        if values["low"] > values["high"]:
            continue
        clean.append({**raw, **values})
    return clean


def _range_bounds(window: list[dict[str, Any]]) -> tuple[float, float] | None:
    """Bordes robustos: p5 de minimos y p95 de maximos.

    Un unico wick extremo no debe multiplicar la altura del rectangulo. Los cierres y las
    mechas restantes todavia tienen que superar las cinco pruebas del validador existente.
    """
    lows = [number(bar["low"]) for bar in window]
    highs = [number(bar["high"]) for bar in window]
    low, high = _quantile(lows, 0.05), _quantile(highs, 0.95)
    if not (math.isfinite(low) and math.isfinite(high) and low > 0 and high > low):
        return None
    mid = (low + high) / 2
    if (high - low) / mid > 0.75:
        return None
    return low, high


def _candidate_rank(result: dict[str, Any], window: int, offset: int) -> float:
    tests = {test["key"]: test for test in result.get("tests") or []}
    rotations = number((tests.get("rotacion") or {}).get("value"))
    touches = number((tests.get("toques") or {}).get("value"))
    passed = int(result.get("passed") or 0)
    # Primero manda la validacion. A igualdad, se premia actividad real, mayor muestra y
    # cercania temporal; no se elige una ventana corta solo porque cabe mejor al ruido.
    return (
        passed * 100
        + min(rotations if math.isfinite(rotations) else 0, 8) * 3
        + min(touches if math.isfinite(touches) else 0, 4) * 4
        + min(window, 120) / 20
        - offset * 1.5
    )


def detect_latest_range(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Busca automaticamente el rango reciente y devuelve el candidato mejor validado."""
    clean = _clean_bars(bars)
    if len(clean) < 80:
        return {
            "available": False,
            "reason": f"Solo hay {len(clean)} velas diarias limpias; se necesitan al menos 80.",
        }

    candidates: list[dict[str, Any]] = []
    for offset in RANGE_END_OFFSETS:
        end = len(clean) - offset
        if end <= 0:
            continue
        for window_size in RANGE_WINDOWS:
            start = end - window_size
            if start < 0:
                continue
            window = clean[start:end]
            bounds = _range_bounds(window)
            if bounds is None:
                continue
            low, high = bounds
            prior = clean[max(0, start - 90) : start]
            validation = range_validate_read(window, prior, low, high)
            if not validation.get("available"):
                continue
            candidates.append(
                {
                    "start_index": start,
                    "end_index": end,
                    "window_bars": window_size,
                    "end_offset_bars": offset,
                    "low": low,
                    "high": high,
                    "validation": validation,
                    "rank": _candidate_rank(validation, window_size, offset),
                }
            )

    if not candidates:
        return {"available": False, "reason": "Ninguna ventana produjo bordes validables."}
    best = max(candidates, key=lambda candidate: candidate["rank"])
    validation = best["validation"]
    if int(validation.get("passed") or 0) < RANGE_PASSES_FOR_FORMING:
        return {
            "available": False,
            "reason": "No hay un rango automatico reciente: ningun candidato supera 3 pruebas.",
            "best_candidate": {
                "passed": validation.get("passed"),
                "evaluated": validation.get("evaluated"),
                "window_bars": best["window_bars"],
            },
        }

    start_bar = clean[best["start_index"]]
    end_bar = clean[best["end_index"] - 1]
    low, high = best["low"], best["high"]
    return {
        "available": True,
        "start_index": best["start_index"],
        "end_index": best["end_index"],
        "from": str(_bar_date(start_bar) or ""),
        "to": str(_bar_date(end_bar) or ""),
        "low": round(low, 8),
        "high": round(high, 8),
        "mid": round((low + high) / 2, 8),
        "height_pct": round((high - low) / ((low + high) / 2) * 100, 2),
        "bars": best["window_bars"],
        "end_offset_bars": best["end_offset_bars"],
        "validation": validation,
        "bounds_method": (
            "percentil 5 de minimos y percentil 95 de maximos; despues se exigen las mismas "
            "cinco pruebas del validador manual"
        ),
        "clean_bars": clean,
    }


def _signed_balance(values: list[float]) -> float | None:
    magnitude = sum(abs(value) for value in values)
    return sum(values) / magnitude if magnitude > 0 else None


def _atr_abs(bars: list[dict[str, Any]]) -> float | None:
    ranges: list[float] = []
    previous: float | None = None
    for bar in bars:
        high, low, close = number(bar["high"]), number(bar["low"]), number(bar["close"])
        true_range = high - low
        if previous is not None:
            true_range = max(true_range, abs(high - previous), abs(low - previous))
        if math.isfinite(true_range) and true_range > 0:
            ranges.append(true_range)
        previous = close
    return median(ranges) if ranges else None


def _events(bars: list[dict[str, Any]], low: float, high: float) -> list[dict[str, Any]]:
    atr = _atr_abs(bars)
    if not atr:
        return []
    volumes = [
        number(bar.get("volume")) * number(bar.get("close"))
        for bar in bars
        if math.isfinite(number(bar.get("volume"))) and number(bar.get("volume")) > 0
    ]
    typical_volume = median(volumes) if volumes else None
    found: list[dict[str, Any]] = []
    for index, bar in enumerate(bars):
        high_px, low_px, close_px = (
            number(bar["high"]),
            number(bar["low"]),
            number(bar["close"]),
        )
        span = high_px - low_px
        if span <= 0:
            continue
        close_position = (close_px - low_px) / span
        dollar_volume = number(bar.get("volume")) * close_px
        volume_multiple = (
            dollar_volume / typical_volume
            if typical_volume and math.isfinite(dollar_volume) and dollar_volume > 0
            else None
        )
        common = {
            "date": str(_bar_date(bar) or ""),
            "close": round(close_px, 8),
            "volume_multiple": round(volume_multiple, 2) if volume_multiple is not None else None,
            "bars_ago": len(bars) - 1 - index,
        }
        if low - low_px >= atr * 0.20 and close_px >= low and close_position >= 0.55:
            found.append(
                {
                    **common,
                    "type": "spring",
                    "direction": "bullish",
                    "detail": "Perforo el soporte y cerro de vuelta dentro del rango.",
                }
            )
        if high_px - high >= atr * 0.20 and close_px <= high and close_position <= 0.45:
            found.append(
                {
                    **common,
                    "type": "upthrust",
                    "direction": "bearish",
                    "detail": "Perforo la resistencia y cerro de vuelta dentro del rango.",
                }
            )
    return found[-8:]


def _session_date(row: dict[str, Any]) -> date | None:
    value = row.get("session_date") or row.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _bias_read(
    range_bars: list[dict[str, Any]], sessions: list[dict[str, Any]], events: list[dict[str, Any]]
) -> dict[str, Any]:
    start_date, end_date = _bar_date(range_bars[0]), _bar_date(range_bars[-1])
    matching_sessions = [
        row
        for row in sessions
        if start_date
        and end_date
        and (session_date := _session_date(row)) is not None
        and start_date <= session_date <= end_date
    ]

    spot_values = [
        value
        for row in matching_sessions
        if math.isfinite(value := number(row.get("cvd_spot_usd")))
    ]
    futures_values: list[float] = []
    up_down_volume: list[float] = []
    for bar in range_bars:
        close, open_px, volume, buy = (
            number(bar.get("close")),
            number(bar.get("open")),
            number(bar.get("volume")),
            number(bar.get("buy_volume")),
        )
        if all(math.isfinite(value) for value in (close, volume, buy)) and volume > 0:
            futures_values.append((2 * buy - volume) * close)
        if all(math.isfinite(value) for value in (close, open_px, volume)) and volume > 0:
            signed_volume = volume * close * (1 if close > open_px else (-1 if close < open_px else 0))
            up_down_volume.append(signed_volume)

    closes = [number(bar["close"]) for bar in range_bars]
    quarter = max(5, len(closes) // 4)
    height = max(number(bar["high"]) for bar in range_bars) - min(
        number(bar["low"]) for bar in range_bars
    )
    price_progress = (
        _clamp((sum(closes[-quarter:]) / quarter - sum(closes[:quarter]) / quarter) / height)
        if height > 0
        else None
    )
    recent_events = [event for event in events if int(event.get("bars_ago") or 0) <= 30]
    event_raw = sum(
        (1 if event["direction"] == "bullish" else -1)
        * min(number(event.get("volume_multiple")) if event.get("volume_multiple") else 1.0, 2.0)
        for event in recent_events
    )
    event_value = _clamp(event_raw / 2) if recent_events else 0.0

    components = [
        {
            "key": "cvd_spot",
            "label": "CVD spot dentro del rango",
            "weight": 30.0,
            "value": _signed_balance(spot_values),
            "detail": f"{len(spot_values)} sesiones NYSE medibles",
        },
        {
            "key": "delta_futuros",
            "label": "Balance de delta de futuros",
            "weight": 25.0,
            "value": _signed_balance(futures_values),
            "detail": f"{len(futures_values)} velas diarias con buy volume",
        },
        {
            "key": "volumen_precio",
            "label": "Volumen en dias alcistas vs bajistas",
            "weight": 15.0,
            "value": _signed_balance(up_down_volume),
            "detail": "Volumen diario asignado por direccion del cuerpo",
        },
        {
            "key": "progreso_precio",
            "label": "Progreso del precio dentro del rango",
            "weight": 15.0,
            "value": price_progress,
            "detail": "Media del ultimo cuarto frente al primero, normalizada por la altura",
        },
        {
            "key": "spring_upthrust",
            "label": "Springs vs upthrusts recientes",
            "weight": 15.0,
            "value": event_value,
            "detail": f"{len(recent_events)} eventos en las ultimas 30 sesiones",
        },
    ]
    measured = [component for component in components if component["value"] is not None]
    measured_weight = sum(component["weight"] for component in measured)
    score = (
        sum(component["value"] * component["weight"] for component in measured) / measured_weight * 100
        if measured_weight
        else 0.0
    )
    coverage = measured_weight / sum(component["weight"] for component in components) * 100
    bullish = sum(component["value"] > 0.10 for component in measured)
    bearish = sum(component["value"] < -0.10 for component in measured)
    bias = "bullish" if score >= BIAS_THRESHOLD else "bearish" if score <= -BIAS_THRESHOLD else "neutral"
    reading = {
        "bullish": "compatible_con_acumulacion",
        "bearish": "compatible_con_distribucion",
        "neutral": "equilibrio_sin_ventaja",
    }[bias]

    oi_values = [number(row.get("oi_close")) for row in matching_sessions]
    oi_values = [value for value in oi_values if math.isfinite(value) and value > 0]
    oi_change = (oi_values[-1] / oi_values[0] - 1) * 100 if len(oi_values) >= 2 else None
    funding_values = [number(row.get("fr_avg")) for row in matching_sessions]
    funding_values = [value for value in funding_values if math.isfinite(value)]
    return {
        "score": round(score, 1),
        "bias": bias,
        "reading": reading,
        "evidence_coverage_pct": round(coverage, 1),
        "agreement": {"bullish": bullish, "bearish": bearish, "measured": len(measured)},
        "components": [
            {
                **component,
                "value": round(component["value"], 3) if component["value"] is not None else None,
                "contribution": round(component["value"] * component["weight"], 1)
                if component["value"] is not None
                else None,
                "status": "measured" if component["value"] is not None else "unavailable",
            }
            for component in components
        ],
        "supporting_metrics": {
            "spot_cvd_usd": round(sum(spot_values), 2) if spot_values else None,
            "futures_delta_usd": round(sum(futures_values), 2) if futures_values else None,
            "oi_change_pct": round(oi_change, 2) if oi_change is not None else None,
            "funding_avg": round(sum(funding_values) / len(funding_values), 6)
            if funding_values
            else None,
        },
    }


def _phase(
    all_bars: list[dict[str, Any]], detected: dict[str, Any], bias: dict[str, Any], events: list[dict[str, Any]]
) -> dict[str, str]:
    low, high = detected["low"], detected["high"]
    last = all_bars[-3:]
    closes = [number(bar["close"]) for bar in last]
    if len(closes) >= 2 and all(close > high for close in closes[-2:]):
        return {
            "code": "E",
            "state": "markup_fuera_del_rango",
            "explanation": "Dos cierres diarios consecutivos estan sobre la resistencia automatica.",
        }
    if len(closes) >= 2 and all(close < low for close in closes[-2:]):
        return {
            "code": "E",
            "state": "markdown_fuera_del_rango",
            "explanation": "Dos cierres diarios consecutivos estan bajo el soporte automatico.",
        }
    recent = [event for event in events if int(event.get("bars_ago") or 0) <= 20]
    if recent:
        latest = recent[-1]
        return {
            "code": "C",
            "state": "prueba_spring" if latest["type"] == "spring" else "prueba_upthrust",
            "explanation": latest["detail"],
        }
    position = _clamp((closes[-1] - low) / (high - low), 0, 1) if closes else 0.5
    if bias["bias"] == "bullish" and position >= 0.60:
        return {
            "code": "D",
            "state": "demanda_toma_control",
            "explanation": "El balance es alcista y el precio trabaja en el 40% superior del rango.",
        }
    if bias["bias"] == "bearish" and position <= 0.40:
        return {
            "code": "D",
            "state": "oferta_toma_control",
            "explanation": "El balance es bajista y el precio trabaja en el 40% inferior del rango.",
        }
    return {
        "code": "B",
        "state": "construccion_de_causa",
        "explanation": "El precio sigue rotando dentro del rango sin ruptura confirmada.",
    }


def wyckoff_auto_read(
    bars: list[dict[str, Any]], sessions: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    detected = detect_latest_range(bars)
    if not detected.get("available"):
        return {
            **{key: value for key, value in detected.items() if key != "clean_bars"},
            "method": "busqueda automatica sobre ventanas de 40 a 365 sesiones",
        }

    clean = detected.pop("clean_bars")
    start, end = detected["start_index"], detected["end_index"]
    range_bars = clean[start:end]
    events = _events(range_bars, detected["low"], detected["high"])
    # Si el mejor rango termino antes de hoy, la recencia de sus eventos se mide contra hoy,
    # no contra la ultima barra del rectangulo.
    for event in events:
        event["bars_ago"] = int(event.get("bars_ago") or 0) + detected["end_offset_bars"]
    bias = _bias_read(range_bars, sessions or [], events)
    phase = _phase(clean, detected, bias, events)
    current = number(clean[-1]["close"])
    position = _clamp((current - detected["low"]) / (detected["high"] - detected["low"]), 0, 1)
    chart_start = max(0, start - 20)
    chart_bars = [
        {
            "time": str(_bar_date(bar) or ""),
            "open": round(number(bar["open"]), 8),
            "high": round(number(bar["high"]), 8),
            "low": round(number(bar["low"]), 8),
            "close": round(number(bar["close"]), 8),
        }
        for bar in clean[chart_start:]
    ]
    return {
        "available": True,
        "range": {key: value for key, value in detected.items() if key not in {"start_index", "end_index"}},
        "bias": bias,
        "phase": phase,
        "events": events,
        "current": {
            "price": round(current, 8),
            "position_pct": round(position * 100, 1),
            "location": "tercio_inferior" if position < 1 / 3 else "tercio_superior" if position > 2 / 3 else "centro",
        },
        "trade_map": {
            "long_confirmation": (
                f"Dos cierres diarios sobre {detected['high']:.2f}; despues, retest que sostenga "
                "la antigua resistencia."
            ),
            "short_confirmation": (
                f"Dos cierres diarios bajo {detected['low']:.2f}; despues, retest fallido del "
                "antiguo soporte."
            ),
            "inside_range": (
                f"Dentro de [{detected['low']:.2f}, {detected['high']:.2f}] no perseguir el "
                f"centro ({detected['mid']:.2f}); los bordes son las zonas de decision."
            ),
        },
        "chart_bars": chart_bars,
        "method": {
            "name": "Wyckoff + flujo, automatico y explicable",
            "range_search": "40 a 365 sesiones; finales 0/5/10/15/20/30 dias atras",
            "bias_weights": {
                "cvd_spot": 30,
                "delta_futuros": 25,
                "volumen_precio": 15,
                "progreso_precio": 15,
                "spring_upthrust": 15,
            },
            "warning": (
                "Las fases Wyckoff son una clasificacion heuristica, no una probabilidad ni una "
                "orden. La ruptura solo se confirma con cierres y retest."
            ),
        },
    }
