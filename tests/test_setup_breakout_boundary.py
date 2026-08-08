"""La ruptura se decide contra la FRONTERA de la zona (breakout_boundary), nunca contra el
centro: superar el centro sin salir de la zona NO es una ruptura. Ademas hypothesis_evidence
publica la zona y los observables ya calculados sin tocar su logica.

- ruptura LONG  -> frontera = resistance.high
- ruptura SHORT -> frontera = support.low
- superar zone_center pero seguir dentro de la zona deja "cierre mas alla" en PENDIENTE.
"""

from __future__ import annotations

from app.scalp_logic import hypothesis_evidence
from app.setups import build_setup_context, evaluate_setup

TF = 900  # 15 m en segundos


def _estado_cierre(setup_out: dict) -> str:
    """Estado del requisito critico 'cierre mas alla de la barrera'."""
    for r in setup_out["requisitos"]:
        if r["requisito"] == "cierre mas alla de la barrera":
            return r["estado"]
    raise AssertionError("el requisito 'cierre mas alla de la barrera' no existe")


# ---------------- 1. la frontera es high/low, no el centro ----------------


def test_ruptura_long_dentro_de_la_zona_queda_pendiente() -> None:
    # zona 100..110 (centro 105); precio 107 supera el centro pero sigue DENTRO de la zona.
    ctx = {
        "price": 107.0,
        "barrier_level": 105.0,
        "breakout_boundary": 110.0,
        "zone_low": 100.0,
        "zone_high": 110.0,
        "zone_center": 105.0,
    }
    out = evaluate_setup("ruptura", "long", ctx)
    assert _estado_cierre(out) == "pendiente"


def test_ruptura_long_por_encima_de_la_frontera_cumple() -> None:
    ctx = {
        "price": 111.0,
        "barrier_level": 105.0,
        "breakout_boundary": 110.0,
        "zone_low": 100.0,
        "zone_high": 110.0,
        "zone_center": 105.0,
    }
    out = evaluate_setup("ruptura", "long", ctx)
    assert _estado_cierre(out) == "cumple"


def test_ruptura_short_dentro_de_la_zona_queda_pendiente() -> None:
    # zona 90..100 (centro 95); precio 93 supera el centro hacia abajo pero sigue DENTRO.
    ctx = {
        "price": 93.0,
        "barrier_level": 95.0,
        "breakout_boundary": 90.0,
        "zone_low": 90.0,
        "zone_high": 100.0,
        "zone_center": 95.0,
    }
    out = evaluate_setup("ruptura", "short", ctx)
    assert _estado_cierre(out) == "pendiente"


def test_ruptura_short_por_debajo_de_la_frontera_cumple() -> None:
    ctx = {
        "price": 89.0,
        "barrier_level": 95.0,
        "breakout_boundary": 90.0,
        "zone_low": 90.0,
        "zone_high": 100.0,
        "zone_center": 95.0,
    }
    out = evaluate_setup("ruptura", "short", ctx)
    assert _estado_cierre(out) == "cumple"


# ---------------- 2. build_setup_context fija la frontera segun direccion ----------------


def test_build_setup_context_ruptura_long_frontera_es_resistance_high() -> None:
    barreras = {
        "available": True,
        "current_price": 107.0,
        "nearest_resistance": {"low": 100.0, "high": 110.0, "center": 105.0},
    }
    ctx = build_setup_context(
        {}, {"layers": {}}, {}, barreras, {"horizons": {}},
        direction="long", setup="ruptura",
    )
    assert ctx["breakout_boundary"] == 110.0
    assert ctx["breakout_boundary"] == ctx["zone_high"]


def test_build_setup_context_ruptura_short_frontera_es_support_low() -> None:
    barreras = {
        "available": True,
        "current_price": 93.0,
        "nearest_support": {"low": 90.0, "high": 100.0, "center": 95.0},
    }
    ctx = build_setup_context(
        {}, {"layers": {}}, {}, barreras, {"horizons": {}},
        direction="short", setup="ruptura",
    )
    assert ctx["breakout_boundary"] == 90.0
    assert ctx["breakout_boundary"] == ctx["zone_low"]


# ---------------- 3. hypothesis_evidence publica zona y observables ----------------


def _bundle(closes: list[float]) -> dict:
    bars = []
    ts = 0
    for c in closes:
        bars.append({"ts": ts, "open": None, "high": c + 0.2, "low": c - 0.2, "close": c})
        ts += TF
    return {
        "timeframe": "15m", "bar_seconds": TF, "source": "test",
        "as_of": "2026-08-08T00:00:00+00:00", "bars": bars,
        "pivots": {"highs": [], "lows": []}, "atr": 1.0,
    }


def test_hypothesis_evidence_publica_setup_zone_y_observables() -> None:
    barreras = {
        "available": True,
        "current_price": 100.6,
        "nearest_resistance": {"low": 99.0, "high": 100.0, "center": 99.5},
    }
    setup_ctx = build_setup_context(
        {}, {"layers": {}}, {}, barreras, {"horizons": {}},
        direction="long", setup="ruptura", observ_bundle=_bundle([100.4, 100.6]),
    )
    perfil = {"profile": "intradia", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0}
    out = hypothesis_evidence(
        None, perfil, scalp, direction="long", setup="ruptura", setup_context=setup_ctx
    )

    # La zona se publica con sus cuatro fronteras.
    assert "setup_zone" in out
    zona = out["setup_zone"]
    for clave in ("zone_low", "zone_high", "zone_center", "breakout_boundary"):
        assert clave in zona, clave
    assert zona["zone_high"] == 100.0
    assert zona["zone_center"] == 99.5
    assert zona["breakout_boundary"] == 100.0

    # Los observables medidos se publican tal cual los calculo build_setup_context.
    assert "setup_observables" in out
    observables = out["setup_observables"]
    assert observables is not None
    for clave in ("bars_closed_beyond", "returned_inside", "retest_done",
                  "pullback_pct", "level_defended"):
        assert clave in observables, clave


def test_hypothesis_evidence_sin_setup_context_no_rompe() -> None:
    perfil = {"profile": "intradia", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0}
    out = hypothesis_evidence(None, perfil, scalp, direction="long", setup="ruptura")
    assert out["setup_observables"] is None
    assert out["setup_zone"] == {
        "zone_low": None, "zone_high": None, "zone_center": None, "breakout_boundary": None,
    }
