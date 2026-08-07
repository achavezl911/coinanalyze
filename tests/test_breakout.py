"""Fase 3 — tasa base de ruptura.

Medido el 2026-08-04 sobre BTC+ETH+SOL (1 796 velas de 4 h cada uno): 117 intentos alcistas
resueltos con 38.5 % de rupturas sostenidas y 152 bajistas con 38.8 %. Por símbolo la tasa va
de 36 % a 42 %, lo que justifica agrupar los tres.
"""

from __future__ import annotations

import math

from app.breakout import (
    ATTEMPT_LOOKBACK,
    MIN_STRATUM,
    OUTCOME_HORIZON,
    breakout_read,
    build_corpus,
    classify_outcome,
    find_attempts,
    wilson_ci,
)


def _bar(close, span=2.0, buy_share=0.5, volume=1000.0):
    return {
        "high": close + span / 2,
        "low": close - span / 2,
        "close": close,
        "volume": volume,
        "buy_volume": volume * buy_share,
    }


def _flat(n, price=100.0, **kw):
    return [_bar(price, **kw) for _ in range(n)]


# ------------------------------------------------------------------ Wilson
def test_wilson_stays_inside_zero_one() -> None:
    """Con n pequeño la aproximación normal se sale de [0,1] y da intervalos imposibles."""
    low, high = wilson_ci(0, 10)
    assert low >= 0.0
    low, high = wilson_ci(10, 10)
    assert high <= 100.0


def test_wilson_narrows_as_the_sample_grows() -> None:
    small = wilson_ci(4, 10)
    large = wilson_ci(400, 1000)
    assert (small[1] - small[0]) > (large[1] - large[0])


def test_wilson_without_sample_is_none() -> None:
    assert wilson_ci(0, 0) is None


# ------------------------------------------------------------------ intentos
def test_one_push_counts_as_one_attempt() -> None:
    """Sin agrupar, un mismo empuje contra el nivel inflaría la muestra con decenas de
    'intentos' que en realidad son el mismo evento."""
    bars = _flat(ATTEMPT_LOOKBACK, 100.0) + [_bar(110.0) for _ in range(8)]
    attempts = find_attempts(bars, upward=True)
    assert len(attempts) == 1


def test_current_push_is_not_counted_as_a_prior_attempt() -> None:
    """El episodio abierto se estaba sumando a `prior_attempts`, aunque el estrato historico
    cuenta solamente intentos anteriores. Eso desplazaba la tasa condicional un bucket."""
    subject = _flat(ATTEMPT_LOOKBACK, 100.0) + [_bar(110.0) for _ in range(12)]
    attempts = find_attempts(subject, upward=True)
    assert attempts[-1]["active"] is True
    corpus = _corpus_bars()
    result = breakout_read({"A": corpus, "B": corpus, "C": corpus}, subject, 101.0, upward=True)
    assert result["available"] is True
    assert result["setup"]["prior_attempts"] == 0


def test_separated_pushes_count_separately() -> None:
    bars = (
        _flat(ATTEMPT_LOOKBACK, 100.0)
        + [_bar(110.0)]
        + _flat(12, 90.0)
        + [_bar(112.0)]
        + _flat(12, 90.0)
    )
    assert len(find_attempts(bars, upward=True)) >= 2


# ------------------------------------------------------------------ resultado
def test_unresolved_attempt_never_enters_the_base_rate() -> None:
    """Si no han pasado 12 velas, el intento no se ha resuelto. Contarlo sería mirar al
    futuro con información incompleta y sesgaría la tasa."""
    bars = _flat(ATTEMPT_LOOKBACK, 100.0) + [_bar(110.0)]
    attempt = {"index": ATTEMPT_LOOKBACK, "level": 105.0, "atr": 2.0}
    assert classify_outcome(bars, attempt, upward=True) is None


def test_sustained_break_requires_holding_at_the_horizon() -> None:
    base = _flat(ATTEMPT_LOOKBACK, 100.0)
    attempt = {"index": len(base) - 1, "level": 105.0, "atr": 2.0}
    sustained = base + _flat(OUTCOME_HORIZON, 115.0)
    assert classify_outcome(sustained, attempt, upward=True) == "sostenida"


def test_break_that_gives_back_is_a_false_break() -> None:
    base = _flat(ATTEMPT_LOOKBACK, 100.0)
    attempt = {"index": len(base) - 1, "level": 105.0, "atr": 2.0}
    fake = base + _flat(3, 115.0) + _flat(OUTCOME_HORIZON - 3, 95.0)
    assert classify_outcome(fake, attempt, upward=True) == "falsa"


def test_never_closing_beyond_is_a_rejection() -> None:
    base = _flat(ATTEMPT_LOOKBACK, 100.0)
    attempt = {"index": len(base) - 1, "level": 105.0, "atr": 2.0}
    rejected = base + _flat(OUTCOME_HORIZON, 98.0)
    assert classify_outcome(rejected, attempt, upward=True) == "rechazo"


# ------------------------------------------------------------------ muestra
def test_thin_corpus_refuses_to_publish_a_rate() -> None:
    tiny = {"X": _flat(ATTEMPT_LOOKBACK + OUTCOME_HORIZON + 5, 100.0)}
    result = breakout_read(tiny, tiny["X"], 105.0, upward=True)
    assert result["available"] is False
    assert "insuficiente" in result["reason"]


def test_thin_stratum_is_unavailable_not_a_number() -> None:
    """Un estrato con 3 casos no puede publicar un porcentaje: el ruido lo domina."""
    from app.breakout import _rate

    thin = _rate([{"outcome": "sostenida"}] * 3, "estrato fino")
    assert thin["available"] is False
    assert thin["n"] == 3
    assert str(MIN_STRATUM) in thin["reason"]


# ------------------------------------------------------------------ look-ahead
def test_features_never_look_past_the_attempt() -> None:
    """Los rasgos que definen el estrato tienen que conocerse ANTES del resultado; si no,
    la tasa base estaría condicionada a información que en vivo no existe."""
    import inspect

    from app import breakout

    source = inspect.getsource(breakout.attempt_features)
    assert "index +" not in source and "index+1" not in source
    assert "bars[max(0, index - 30) : index]" in source


def test_corpus_outcomes_are_only_the_three_defined_labels() -> None:
    bars = (_flat(ATTEMPT_LOOKBACK, 100.0) + [_bar(110.0)] + _flat(OUTCOME_HORIZON + 2, 115.0)) * 3
    corpus = build_corpus({"A": bars}, upward=True)
    assert {row["outcome"] for row in corpus} <= {"sostenida", "falsa", "rechazo"}


# ------------------------------------------------------------------ presentación
def _corpus_bars():
    """Serie larga y variada para que el corpus supere el mínimo."""
    bars = []
    for cycle in range(14):
        bars += _flat(ATTEMPT_LOOKBACK, 100.0 + cycle)
        bars += [_bar(112.0 + cycle)]
        bars += _flat(OUTCOME_HORIZON + 2, (116.0 if cycle % 2 else 95.0) + cycle)
    return bars


def test_rate_is_always_reported_with_sample_and_interval() -> None:
    """Nunca un porcentaje a secas: sin n e IC, una tasa base parece una probabilidad."""
    bars = _corpus_bars()
    result = breakout_read({"A": bars, "B": bars, "C": bars}, bars, 110.0, upward=True)
    if not result["available"]:
        return
    base = result["base_rate"]
    if base["available"]:
        assert base["n"] >= MIN_STRATUM
        assert base["ci95_pct"] is not None
        assert base["ci95_pct"][0] <= base["rate_pct"] <= base["ci95_pct"][1]


def test_output_refuses_to_combine_conditional_rates() -> None:
    bars = _corpus_bars()
    result = breakout_read({"A": bars, "B": bars, "C": bars}, bars, 110.0, upward=True)
    if not result["available"]:
        return
    assert "no se multiplican" in result["warning"].lower()
    assert "NO es la salida de un modelo" in result["warning"]


def test_confirmation_requires_all_four_checks() -> None:
    bars = _corpus_bars()
    result = breakout_read({"A": bars, "B": bars, "C": bars}, bars, 110.0, upward=True)
    if not result["available"]:
        return
    confirmation = result["confirmation"]
    assert confirmation["required"] == len(confirmation["checks"]) == 4
    assert (confirmation["state"] == "confirmada") == (confirmation["met"] == 4)
    for check in confirmation["checks"]:
        assert check["detail"], "cada condición debe decir qué se midió"


def test_every_rate_is_a_finite_percentage() -> None:
    bars = _corpus_bars()
    result = breakout_read({"A": bars, "B": bars, "C": bars}, bars, 110.0, upward=True)
    if not result["available"]:
        return
    for entry in [result["base_rate"], *result["conditional_rates"]]:
        if entry.get("available"):
            assert math.isfinite(entry["rate_pct"])
            assert 0.0 <= entry["rate_pct"] <= 100.0
