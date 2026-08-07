"""Frecuencia HISTÓRICA de ruptura: una tasa base contada, no la salida de un modelo.

El panel se llamaba "probabilidad de ruptura". No lo es: no hay modelo calibrado ni
validación fuera de muestra, así que la palabra sobrevendía la evidencia y se retiró.

Con ~1 800 velas de 4 h por símbolo no hay muestra para entrenar nada, y una probabilidad de
modelo sería falsa precisión — el daño más grave que este panel podría hacerle a un operador
novato. Lo que sí se puede hacer es contar: cuántas veces, en la historia disponible, un intento
con estas características terminó en ruptura sostenida, y publicar esa frecuencia con su tamaño
de muestra y su intervalo de confianza.

Medido el 2026-08-04 sobre BTC+ETH+SOL (1 796 velas de 4 h cada uno):
  - rupturas alcistas: 117 intentos, 38.5% sostenidas
  - rupturas bajistas: 152 intentos, 38.8% sostenidas
  - por símbolo la tasa va de 36% a 42%, por eso agrupar los tres está justificado

Las tasas condicionales son MARGINALES (una variable cada vez). NO se combinan entre sí: las
variables están correlacionadas y multiplicarlas fabricaría una precisión que la muestra no
sostiene. El cruce completo (3x2x2) dejaría celdas de ~10 casos, y por eso no se hace.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from app.interpretation import number

# Ventana que define el extremo local que se intenta romper.
ATTEMPT_LOOKBACK = 30
# "Se acerca al nivel" = a menos de esta fracción de ATR.
ATTEMPT_NEAR_ATR = 0.5
# Y no se cuenta un intento nuevo hasta alejarse esto, para no contar un mismo empuje N veces.
ATTEMPT_EXIT_ATR = 1.5
# Horizonte de resolución: 12 velas de 4 h = 2 días.
OUTCOME_HORIZON = 12
# Cierres consecutivos al otro lado que cuentan como ruptura.
CONFIRM_CLOSES = 2
# Por debajo de esto un estrato no se publica: se devuelve unavailable con el motivo.
MIN_STRATUM = 10
# Volumen relativo exigido a una ruptura en vivo.
BREAKOUT_VOLUME_MULTIPLE = 1.5


def wilson_ci(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalo de Wilson: con n pequeño la aproximación normal se sale de [0,1] y da
    intervalos imposibles, que es justo el rango en el que se mueve esta muestra."""
    if total <= 0:
        return None
    phat = successes / total
    denominator = 1 + z**2 / total
    centre = (phat + z**2 / (2 * total)) / denominator
    margin = z * math.sqrt(phat * (1 - phat) / total + z**2 / (4 * total**2)) / denominator
    return (round(max(0.0, centre - margin) * 100, 1), round(min(1.0, centre + margin) * 100, 1))


def _atr(bars: list[dict[str, Any]], index: int, span: int = 14) -> float | None:
    window = bars[max(0, index - span) : index]
    if len(window) < 3:
        return None
    ranges: list[float] = []
    previous: float | None = None
    for bar in window:
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


def _delta_usd(bars: list[dict[str, Any]]) -> float:
    total = 0.0
    for bar in bars:
        close, volume, buy = (
            number(bar["close"]),
            number(bar["volume"]),
            number(bar["buy_volume"]),
        )
        if all(math.isfinite(v) for v in (close, volume, buy)):
            total += (2 * buy - volume) * close
    return total


def find_attempts(bars: list[dict[str, Any]], upward: bool) -> list[dict[str, Any]]:
    """Episodios de acercamiento al extremo local. Un mismo empuje es UN intento."""
    attempts: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for index in range(ATTEMPT_LOOKBACK, len(bars)):
        atr = _atr(bars, index)
        if not atr or atr <= 0:
            continue
        window = bars[index - ATTEMPT_LOOKBACK : index]
        level = (
            max(number(b["high"]) for b in window)
            if upward
            else min(number(b["low"]) for b in window)
        )
        bar = bars[index]
        near = (
            number(bar["high"]) >= level - ATTEMPT_NEAR_ATR * atr
            if upward
            else number(bar["low"]) <= level + ATTEMPT_NEAR_ATR * atr
        )
        far = (
            number(bar["high"]) < level - ATTEMPT_EXIT_ATR * atr
            if upward
            else number(bar["low"]) > level + ATTEMPT_EXIT_ATR * atr
        )
        if near and active is None:
            active = {"index": index, "level": level, "atr": atr}
        elif far and active is not None:
            attempts.append({**active, "active": False})
            active = None
    if active is not None:
        attempts.append({**active, "active": True})
    return attempts


def classify_outcome(bars: list[dict[str, Any]], attempt: dict[str, Any], upward: bool) -> str | None:
    """Resultado a 12 velas. Devuelve None si el intento aún no ha tenido tiempo de resolverse,
    para que un intento en curso NUNCA entre en la tasa base."""
    index, level = attempt["index"], attempt["level"]
    future = bars[index + 1 : index + 1 + OUTCOME_HORIZON]
    if len(future) < OUTCOME_HORIZON:
        return None
    beyond = [
        (number(b["close"]) > level) if upward else (number(b["close"]) < level) for b in future
    ]
    run = 0
    confirmed = False
    for flag in beyond:
        run = run + 1 if flag else 0
        if run >= CONFIRM_CLOSES:
            confirmed = True
            break
    if confirmed and beyond[-1]:
        return "sostenida"
    if confirmed:
        return "falsa"
    return "rechazo"


def attempt_features(
    bars: list[dict[str, Any]], attempt: dict[str, Any], all_attempts: list[dict[str, Any]]
) -> dict[str, Any]:
    """Rasgos conocidos ANTES de saber el resultado. Ninguno mira velas posteriores."""
    index, atr = attempt["index"], attempt["atr"]
    prior = sum(
        1
        for other in all_attempts
        if other["index"] < index
        and index - other["index"] <= 90
        and abs(other["level"] - attempt["level"]) <= atr
    )
    atr_short, atr_long = _atr(bars, index, 10), _atr(bars, index, 40)
    compressed = (
        atr_short / atr_long <= 0.9 if (atr_short and atr_long and atr_long > 0) else None
    )
    return {
        "prior_attempts": prior,
        "prior_bucket": 0 if prior == 0 else (1 if prior <= 2 else 2),
        "atr_compressed": compressed,
        "delta_positive": _delta_usd(bars[max(0, index - 30) : index]) > 0,
    }


def build_corpus(bars_by_symbol: dict[str, list[dict[str, Any]]], upward: bool) -> list[dict[str, Any]]:
    corpus: list[dict[str, Any]] = []
    for symbol, bars in bars_by_symbol.items():
        attempts = find_attempts(bars, upward)
        for attempt in attempts:
            outcome = classify_outcome(bars, attempt, upward)
            if outcome is None:
                continue
            corpus.append(
                {"symbol": symbol, "outcome": outcome, **attempt_features(bars, attempt, attempts)}
            )
    return corpus


def _rate(rows: list[dict[str, Any]], label: str, note: str = "") -> dict[str, Any]:
    total = len(rows)
    sustained = sum(r["outcome"] == "sostenida" for r in rows)
    if total < MIN_STRATUM:
        return {
            "label": label,
            "available": False,
            "n": total,
            "reason": f"Solo {total} casos análogos; se necesitan {MIN_STRATUM} para publicar una tasa.",
        }
    ci = wilson_ci(sustained, total)
    return {
        "label": label,
        "available": True,
        "rate_pct": round(sustained / total * 100, 1),
        "sustained": sustained,
        "n": total,
        "ci95_pct": ci,
        "false_break_pct": round(
            sum(r["outcome"] == "falsa" for r in rows) / total * 100, 1
        ),
        "rejection_pct": round(
            sum(r["outcome"] == "rechazo" for r in rows) / total * 100, 1
        ),
        "note": note,
    }


def breakout_read(
    bars_by_symbol: dict[str, list[dict[str, Any]]],
    subject_bars: list[dict[str, Any]],
    level: float,
    upward: bool,
    live: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Tasa base para el nivel pedido más el estado del intento en curso."""
    if not math.isfinite(level) or level <= 0:
        return {"available": False, "reason": "Nivel no válido."}
    if len(subject_bars) < ATTEMPT_LOOKBACK + OUTCOME_HORIZON:
        return {"available": False, "reason": "Historia insuficiente para el activo consultado."}

    corpus = build_corpus(bars_by_symbol, upward)
    if len(corpus) < MIN_STRATUM:
        return {
            "available": False,
            "reason": f"Solo {len(corpus)} intentos históricos resueltos; muestra insuficiente.",
        }

    # Estado actual, con los MISMOS rasgos que definen los estratos.
    index = len(subject_bars)
    atr = _atr(subject_bars, index) or 0.0
    attempts_now = find_attempts(subject_bars, upward)
    recent = [
        a
        for a in attempts_now
        if not a.get("active")
        and index - a["index"] <= 90
        and atr > 0
        and abs(a["level"] - level) <= atr
    ]
    atr_short, atr_long = _atr(subject_bars, index, 10), _atr(subject_bars, index, 40)
    compressed = (
        atr_short / atr_long <= 0.9 if (atr_short and atr_long and atr_long > 0) else None
    )
    delta_positive = _delta_usd(subject_bars[-30:]) > 0
    setup = {
        "prior_attempts": len(recent),
        "atr_compressed": compressed,
        "delta_positive": delta_positive,
        "atr_4h": round(atr, 8) if atr else None,
    }

    conditionals = []
    if compressed is not None:
        subset = [r for r in corpus if r["atr_compressed"] is compressed]
        conditionals.append(
            _rate(
                subset,
                "ATR comprimido" if compressed else "ATR sin comprimir",
                "La compresión de volatilidad es el rasgo con señal más consistente en ambas "
                "direcciones; aun así los intervalos son anchos.",
            )
        )
    subset = [r for r in corpus if r["delta_positive"] is delta_positive]
    conditionals.append(
        _rate(
            subset,
            "Delta de 30 velas positivo" if delta_positive else "Delta de 30 velas negativo",
            "Señal sugerente, no establecida: su intervalo se solapa con el de la tasa general.",
        )
    )
    bucket = 0 if len(recent) == 0 else (1 if len(recent) <= 2 else 2)
    subset = [r for r in corpus if r["prior_bucket"] == bucket]
    conditionals.append(
        _rate(
            subset,
            {0: "Sin intentos previos", 1: "Con 1-2 intentos previos", 2: "Con 3 o más previos"}[
                bucket
            ],
        )
    )

    overall = _rate(corpus, "Todos los intentos análogos")
    live = live or {}
    checks = _confirmation_checks(subject_bars, level, upward, live)
    met = sum(bool(c["met"]) for c in checks)

    return {
        "available": True,
        "level": level,
        "direction": "alcista" if upward else "bajista",
        "setup": setup,
        "base_rate": overall,
        "conditional_rates": conditionals,
        "confirmation": {
            "checks": checks,
            "met": met,
            "required": len(checks),
            "state": "confirmada" if met == len(checks) else "sin confirmar",
        },
        "method": {
            "attempt": (
                f"acercamiento a menos de {ATTEMPT_NEAR_ATR} ATR del extremo de "
                f"{ATTEMPT_LOOKBACK} velas; un mismo empuje cuenta como UN intento"
            ),
            "sustained": (
                f"{CONFIRM_CLOSES} cierres consecutivos al otro lado dentro de "
                f"{OUTCOME_HORIZON} velas Y seguir al otro lado al final del horizonte"
            ),
            "pooling": "BTC+ETH+SOL agrupados; por símbolo la tasa va de 36% a 42%",
            "corpus_size": len(corpus),
            "min_stratum": MIN_STRATUM,
        },
        "warning": (
            "NO es la salida de un modelo ni una probabilidad calibrada: es la frecuencia con "
            "que intentos parecidos acabaron en ruptura sostenida en la historia disponible. "
            "Las tasas condicionales son marginales y NO se multiplican entre sí: las variables "
            "están correlacionadas y combinarlas fabricaría precisión que la muestra no sostiene. "
            "Los intentos sin resolver no entran en el cálculo."
        ),
    }


def _confirmation_checks(
    bars: list[dict[str, Any]], level: float, upward: bool, live: dict[str, Any]
) -> list[dict[str, Any]]:
    """Las cuatro condiciones que exige una ruptura. Se cumplen las cuatro o no hay ruptura."""
    last = bars[-1] if bars else {}
    close = number(last.get("close"))
    beyond = (close > level) if upward else (close < level)
    volumes = [
        number(b["volume"]) * number(b["close"])
        for b in bars[-90:]
        if math.isfinite(number(b["volume"]))
    ]
    median_volume = median(volumes) if volumes else None
    last_volume = number(last.get("volume", math.nan)) * close if math.isfinite(close) else math.nan
    multiple = (
        last_volume / median_volume if (median_volume and math.isfinite(last_volume)) else None
    )
    delta = _delta_usd(bars[-1:])
    aligned = (delta > 0) if upward else (delta < 0)
    # El retest solo puede evaluarse una vez roto: antes no es "fallado", es "todavía no".
    recent_closes = [number(b["close"]) for b in bars[-CONFIRM_CLOSES:]]
    closes_beyond = sum(
        (c > level) if upward else (c < level) for c in recent_closes if math.isfinite(c)
    )
    return [
        {
            "key": "cierre_fuera",
            "label": f"Cierre de 4 h {'sobre' if upward else 'bajo'} el nivel",
            "met": bool(beyond),
            "detail": f"Último cierre {close:,.2f} vs nivel {level:,.2f}."
            if math.isfinite(close)
            else "Sin cierre disponible.",
        },
        {
            "key": "volumen",
            "label": f"Volumen ≥ {BREAKOUT_VOLUME_MULTIPLE}× la mediana",
            "met": bool(multiple is not None and multiple >= BREAKOUT_VOLUME_MULTIPLE),
            "detail": f"{multiple:.2f}× la mediana de 90 velas."
            if multiple is not None
            else "Sin volumen de referencia.",
        },
        {
            "key": "delta",
            "label": "Delta de la vela a favor",
            "met": bool(aligned),
            "detail": f"Delta {delta / 1e6:,.1f} M USD en la última vela.",
        },
        {
            "key": "sostenimiento",
            "label": f"{CONFIRM_CLOSES} cierres consecutivos fuera",
            "met": closes_beyond >= CONFIRM_CLOSES,
            "detail": f"{closes_beyond} de los últimos {CONFIRM_CLOSES} cierres fuera del nivel.",
        },
    ]
