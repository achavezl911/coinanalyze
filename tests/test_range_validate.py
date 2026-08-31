"""Fase 2 — validación de rango con cinco tests de umbral medido.

Los umbrales salen de 936 ventanas históricas (60/120/180 sesiones × 3 símbolos), no de
elegirlos a ojo. Se probaron y descartaron dos que no discriminaban nada: toques con
tolerancia del 10 % de la altura (los pasaba el 100 % de las ventanas) y ≥4 episodios por
borde (no lo cumple ninguna, 0 %).
"""

from __future__ import annotations

import math
import pathlib

from app.zones import (
    RANGE_MAX_DRIFT,
    RANGE_MIN_BARS,
    RANGE_MIN_EDGE_EPISODES,
    RANGE_MIN_ROTATIONS,
    range_validate_read,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

LOW, HIGH = 100.0, 120.0
MID = (LOW + HIGH) / 2


def _bar(close, span=1.0):
    return {"open": close, "high": close + span / 2, "low": close - span / 2, "close": close}


def _oscillating(cycles: int, per_cycle: int = 20, amplitude: float = 9.5, drift: float = 0.0):
    """Onda que toca ambos bordes y rota, con deriva opcional."""
    bars = []
    total = cycles * per_cycle
    for i in range(total):
        phase = 2 * math.pi * i / per_cycle
        bars.append(_bar(MID + amplitude * math.sin(phase) + drift * i))
    return bars


def _prior(n: int = 90, span: float = 1.0):
    return [_bar(MID, span) for _ in range(n)]


# ----------------------------------------------------------------- cobertura mínima
def test_short_window_is_unavailable_not_a_verdict() -> None:
    result = range_validate_read(_oscillating(1, 10), _prior(), LOW, HIGH)
    assert result["available"] is False
    assert str(RANGE_MIN_BARS) in result["reason"]


def test_inverted_bounds_rejected() -> None:
    result = range_validate_read(_oscillating(5), _prior(), HIGH, LOW)
    assert result["available"] is False


# ----------------------------------------------------------------- rango limpio
def test_clean_oscillation_is_a_range() -> None:
    result = range_validate_read(_oscillating(6), _prior(), LOW, HIGH)
    assert result["available"] is True
    assert result["verdict"] == "rango"
    assert result["passed"] >= result["required"]


def test_every_test_reports_value_threshold_and_reason() -> None:
    """Un novato tiene que poder aprender el criterio, no solo leer la conclusión."""
    result = range_validate_read(_oscillating(6), _prior(), LOW, HIGH)
    for test in result["tests"]:
        assert {"key", "label", "value", "threshold", "operator", "passed", "reading", "why"} <= set(test)
        assert test["why"], "cada test debe explicar por qué existe"


# ----------------------------------------------------------------- tendencia
def test_strong_trend_is_not_a_range() -> None:
    """Deriva sostenida: falla horizontalidad y no rota."""
    bars = [_bar(LOW + (HIGH - LOW) * i / 120) for i in range(120)]
    result = range_validate_read(bars, _prior(), LOW, HIGH)
    assert result["verdict"] == "no_es_rango"
    drift = next(t for t in result["tests"] if t["key"] == "horizontalidad")
    assert drift["passed"] is False
    assert drift["value"] > RANGE_MAX_DRIFT


def test_plateau_without_rotation_is_not_a_range() -> None:
    """Una meseta quieta contiene el precio pero no rota: es pausa, no rango."""
    bars = [_bar(MID + (0.4 if i % 2 else -0.4)) for i in range(120)]
    result = range_validate_read(bars, _prior(), LOW, HIGH)
    rotation = next(t for t in result["tests"] if t["key"] == "rotacion")
    touches = next(t for t in result["tests"] if t["key"] == "toques")
    assert rotation["passed"] is False
    assert touches["passed"] is False
    assert result["verdict"] != "rango"


def test_only_one_edge_tested_is_support_not_range() -> None:
    """Rebotes repetidos contra el suelo sin llegar nunca al techo."""
    bars = []
    for i in range(120):
        phase = 2 * math.pi * i / 20
        bars.append(_bar(LOW + 2.0 + 1.8 * abs(math.sin(phase))))
    result = range_validate_read(bars, _prior(), LOW, HIGH)
    touches = next(t for t in result["tests"] if t["key"] == "toques")
    assert touches["passed"] is False
    assert touches["value"] < RANGE_MIN_EDGE_EPISODES
    assert result["verdict"] != "rango"


# ----------------------------------------------------------------- discriminación
def test_rotation_uses_a_deadband() -> None:
    """Sin banda muerta, el ruido en torno al centro contaría como rotaciones y una serie
    plana parecería un rango muy activo."""
    noisy = [_bar(MID + (0.05 if i % 2 else -0.05)) for i in range(120)]
    result = range_validate_read(noisy, _prior(), LOW, HIGH)
    rotation = next(t for t in result["tests"] if t["key"] == "rotacion")
    assert rotation["value"] == 0
    assert RANGE_MIN_ROTATIONS > 0


def test_edge_touches_count_visits_not_bars() -> None:
    """15 barras pegadas al borde pueden ser UNA sola visita. Contar barras hacía que el
    test lo pasara siempre (medido: el 100 % de las ventanas históricas)."""
    parked = [_bar(LOW + 0.2) for _ in range(60)] + [_bar(HIGH - 0.2) for _ in range(60)]
    result = range_validate_read(parked, _prior(), LOW, HIGH)
    touches = next(t for t in result["tests"] if t["key"] == "toques")
    assert touches["value"] == 1, "una estancia larga en cada borde es una visita, no sesenta"


def test_volatility_expansion_fails_its_test() -> None:
    calm_prior = _prior(span=0.5)
    wild = _oscillating(6)
    for bar in wild:
        bar["high"] += 6
        bar["low"] -= 6
    result = range_validate_read(wild, calm_prior, LOW, HIGH)
    vol = next(t for t in result["tests"] if t["key"] == "volatilidad")
    assert vol["passed"] is False
    assert vol["value"] > 1.2


def test_missing_prior_history_marks_volatility_unavailable() -> None:
    """Sin historia previa el test no se puntúa como fallado: se declara no medible."""
    result = range_validate_read(_oscillating(6), [], LOW, HIGH)
    vol = next(t for t in result["tests"] if t["key"] == "volatilidad")
    assert vol["status"] == "unavailable"
    assert result["evaluated"] == 4, "el veredicto se decide solo sobre los tests medibles"


# ----------------------------------------------------------------- trazabilidad
def test_verdict_states_its_thresholds_are_measured() -> None:
    result = range_validate_read(_oscillating(6), _prior(), LOW, HIGH)
    assert "936" in result["method"]["thresholds_basis"]
    assert result["method"]["pass_rates_observed"]["rotacion"] == "~10%"


def test_verdict_carries_invalidation_and_does_not_predict() -> None:
    result = range_validate_read(_oscillating(6), _prior(), LOW, HIGH)
    assert "Deja de ser rango" in result["invalidation"]
    assert "no predice" in result["warning"]


# ----------------------------------------------------------------- acotar por fechas
def test_endpoint_accepts_dates_or_a_rolling_window_but_not_half_a_pair() -> None:
    """Una sola fecha deja el tramo a medio definir; el endpoint lo rechaza en vez de
    completarla por su cuenta."""
    source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    body = source[source.index("async def range_validate_endpoint") : source.index("@app.get(\"/api/context-metadata\")")]
    assert "start_date and end_date must come together" in body
    assert "start_date must be before end_date" in body


def test_range_validate_prefers_dates_over_the_rolling_window() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    body = source[source.index("async def range_validate") : source.index("async def level_breakout")]
    assert "if start_date is not None and end_date is not None:" in body
    # La referencia de volatilidad debe anclarse al INICIO del tramo, no a hoy ($2 es
    # start_date). Y la fecha se saca en UTC a proposito: ts::date pelado usaria la zona de
    # la SESION -America/Mexico_City en 140-, que con barras diarias estampadas a 00:00Z
    # resta un dia al 100 % de ellas y corre la ventana entera. Ver K76.
    assert "(ts AT TIME ZONE 'UTC')::date < $2" in body
