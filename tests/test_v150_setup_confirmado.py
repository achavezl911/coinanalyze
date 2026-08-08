"""El camino REAL de produccion: datos OHLCV/barreras -> build_setup_context -> evaluate_setup.

No se construye el ctx a mano: se alimenta build_setup_context con barreras, estructura y un
paquete de velas cerradas, y se comprueba que con datos SUFICIENTES los setups pueden llegar a
CONFIRMADO, y que siguen fail-closed cuando faltan los observables criticos (sin bundle).
"""

from __future__ import annotations

from app.setups import build_setup_context, evaluate_setup

TF = 900


def _bars(closes: list) -> list[dict]:
    out, ts = [], 0
    for c in closes:
        close, high, low = c if isinstance(c, tuple) else (c, c + 0.2, c - 0.2)
        out.append({"ts": ts, "open": None, "high": high, "low": low, "close": close})
        ts += TF
    return out


def _bundle(bars, *, atr=1.0, pivots=None):
    return {
        "timeframe": "15m", "bar_seconds": TF, "source": "test",
        "as_of": "2026-08-08T00:00:00+00:00", "bars": bars, "atr": atr,
        "pivots": pivots or {"highs": [], "lows": []},
    }


_VIEW = {"layers": {"contexto": {"bias": "alcista"}, "confirmacion": {"bias": "alcista"}}}


def _scalp(**over):
    base = {
        "spot_delta_3m": 500.0, "fut_delta_3m": 900.0, "oi_chg_15m_pct": 0.3,
        "imbalance_l5": 0.62, "price_move_3m_pct": 0.4, "absorption": "Sin señal",
        "vwap_dist_pct": 0.2, "liquidations_measured": False,
    }
    base.update(over)
    return base


# ---------------- Ruptura CONFIRMADO por el flujo real ----------------


def test_ruptura_llega_a_confirmado_con_datos_suficientes() -> None:
    barreras = {
        "available": True, "current_price": 100.5,
        "nearest_resistance": {"center": 99.5, "low": 99.0, "high": 100.0},
        "live_pressure": {"volume_multiple_15m": 1.4},
    }
    bundle = _bundle(_bars([100.4, 100.6]))  # dos cierres > high(100) -> aceptacion
    ctx = build_setup_context(
        _scalp(), _VIEW, {}, barreras, {"horizons": {}},
        direction="long", setup="ruptura", observ_bundle=bundle,
    )
    assert ctx["bars_closed_beyond"] == 2
    assert ctx["returned_inside"] is False
    out = evaluate_setup("ruptura", "long", ctx)
    assert out["state"] == "CONFIRMADO", out["missing_critical"] or out["pendientes"]


def test_ruptura_es_fail_closed_sin_bundle() -> None:
    barreras = {
        "available": True, "current_price": 100.5,
        "nearest_resistance": {"center": 99.5, "low": 99.0, "high": 100.0},
        "live_pressure": {"volume_multiple_15m": 1.4},
    }
    ctx = build_setup_context(
        _scalp(), _VIEW, {}, barreras, {"horizons": {}}, direction="long", setup="ruptura",
    )
    out = evaluate_setup("ruptura", "long", ctx)
    assert out["state"] != "CONFIRMADO"
    assert "aceptacion fuera del nivel" in out["missing_critical"]


# ---------------- Rechazo CONFIRMADO por el flujo real ----------------


def test_rechazo_llega_a_confirmado_con_datos_suficientes() -> None:
    # Rechazo largo: se apoya en el SOPORTE (low 99 / high 100). Toca la zona y vuelve arriba.
    barreras = {
        "available": True, "current_price": 100.5, "active_zone": {"center": 99.5},
        "nearest_support": {"center": 99.5, "low": 99.0, "high": 100.0},
    }
    bundle = _bundle(_bars([99.5, 100.5]))  # entra en zona y cierra de vuelta sobre high
    ctx = build_setup_context(
        _scalp(), _VIEW, {}, barreras, {"horizons": {}},
        direction="long", setup="rechazo", observ_bundle=bundle,
    )
    assert ctx["returned_inside"] is True
    assert ctx["bars_closed_beyond"] == 0  # ningun cierre aceptado bajo el soporte
    out = evaluate_setup("rechazo", "long", ctx)
    assert out["state"] == "CONFIRMADO", out["missing_critical"] or out["pendientes"]


def test_rechazo_es_fail_closed_sin_bundle() -> None:
    barreras = {
        "available": True, "current_price": 100.5, "active_zone": {"center": 99.5},
        "nearest_support": {"center": 99.5, "low": 99.0, "high": 100.0},
    }
    ctx = build_setup_context(
        _scalp(), _VIEW, {}, barreras, {"horizons": {}}, direction="long", setup="rechazo",
    )
    out = evaluate_setup("rechazo", "long", ctx)
    assert out["state"] != "CONFIRMADO"
    assert "retorno al rango" in out["missing_critical"]


# ---------------- Continuacion CONFIRMADO por el flujo real ----------------


def test_continuacion_llega_a_confirmado_con_datos_suficientes() -> None:
    # impulso 100 -> 110, retroceso que TOCA el swing low 100 y reacciona hacia arriba.
    pivots = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0)]}
    bars = _bars([
        (100.0, 100.2, 100.0), 104, 108, (110.0, 110.0, 109.5),
        106, 102, (100.1, 100.6, 100.02), 101, (103.0, 103.2, 101.0),
    ])
    bundle = _bundle(bars, atr=1.0, pivots=pivots)
    barreras = {"available": True, "current_price": 103.0}
    structure = {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": 1.0,
                                      "distance_to_invalidation_pct": 5.0}}}
    ctx = build_setup_context(
        _scalp(multi_tf=True), _VIEW, {}, barreras, structure,
        direction="long", setup="continuacion", observ_bundle=bundle,
    )
    assert ctx["prior_trend"] == "alcista"
    assert ctx["pullback_pct"] is not None and ctx["pullback_pct"] < 0
    assert ctx["level_defended"] is True
    out = evaluate_setup("continuacion", "long", ctx)
    assert out["state"] == "CONFIRMADO", out["missing_critical"] or out["pendientes"]


def test_continuacion_es_fail_closed_sin_bundle() -> None:
    barreras = {"available": True, "current_price": 103.0}
    structure = {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": 1.0,
                                      "distance_to_invalidation_pct": 5.0}}}
    ctx = build_setup_context(
        _scalp(), _VIEW, {}, barreras, structure, direction="long", setup="continuacion",
    )
    out = evaluate_setup("continuacion", "long", ctx)
    assert out["state"] != "CONFIRMADO"
    assert {"retroceso previo", "defensa del nivel"} & set(out["missing_critical"])
