"""SETUPS R2 · Z-03 + Z-04 (fable-dz4 P2 y P3), por el camino real build_setup_context -> evaluate_setup.

Z-03: el OI de 15 m (`oi_chg_15m_pct`) se cruzaba con el precio de 3 m; el tablero cruza los dos de
15 m. Con OI y precio de 15 m subiendo y el de 3 m bajando, el setup decia lo contrario que el
tablero. El rechazo NO cambia: su reaccion sigue siendo la de 3 m.

Z-04: «retroceso previo» cumplia con cualquier valor distinto de 0 y «defensa del nivel» la cumplia
la propia vela del pivote (`ts >= level_ts`). Ahora el retroceso cuenta si mide >= LEVEL_TOL_ATR_MULT
ATR y la defensa se mide en el MISMO tramo que el retroceso -las velas posteriores al extremo del
impulso- contra su origen.
"""

from __future__ import annotations

from barreras_reales import barreras as barreras_reales

from app.setups import (
    LEVEL_TOL_ATR_MULT,
    build_setup_context,
    classify_oi,
    evaluate_setup,
    oi_price_reading,
)

TF = 900
_VIEW = {"layers": {"contexto": {"bias": "alcista"}, "confirmacion": {"bias": "alcista"}}}
_HHHL = {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": 1.0,
                              "distance_to_invalidation_pct": 5.0}}}


def _req(ev: dict, nombre: str) -> dict:
    return next(r for r in ev["requisitos"] if r["requisito"] == nombre)


def _bars(velas: list) -> list[dict]:
    """(close, high, low) o un close suelto (high/low a +-0.2), una vela cada TF desde ts=0."""
    out = []
    for i, c in enumerate(velas):
        close, high, low = c if isinstance(c, tuple) else (c, c + 0.2, c - 0.2)
        out.append({"ts": i * TF, "open": None, "high": high, "low": low, "close": close})
    return out


def _bundle(bars: list[dict], pivots: dict, atr: float = 1.0) -> dict:
    return {"timeframe": "15m", "bar_seconds": TF, "source": "test",
            "as_of": "2026-11-23T00:00:00+00:00", "bars": bars, "atr": atr, "pivots": pivots}


# ---------------- Z-03 · el OI de 15 m contra el precio de 15 m ----------------

_SCALP_Z03 = {"price_move_3m_pct": -0.05, "price_move_15m_pct": 0.60, "oi_chg_15m_pct": 1.5,
              "fut_delta_3m": 5e5, "spot_delta_3m": 2e5}


def _oi_ruptura(direccion: str, scalp: dict) -> dict:
    ctx = build_setup_context(scalp, _VIEW, {}, barreras_reales(110.0, volumen=1.4), {"horizons": {}},
                              direction=direccion, setup="ruptura")
    return _req(evaluate_setup("ruptura", direccion, ctx), "open interest")


def test_z03_el_oi_de_ruptura_dice_lo_mismo_que_el_tablero() -> None:
    tablero = oi_price_reading(0.60, classify_oi(1.5, timeframe="15m"), fut_delta=5e5, spot_delta=2e5)
    assert tablero["supports"] == 1  # el tablero: OI y precio de 15 m suben -> a favor del largo
    largo, corto = _oi_ruptura("long", _SCALP_Z03), _oi_ruptura("short", _SCALP_Z03)
    # main: no_cumple / cumple (cruzaba con el precio de 3 m, que baja)
    assert (largo["estado"], corto["estado"]) == ("cumple", "no_cumple")
    assert "precio 15 m" in largo["detalle"]


def test_z03_sin_precio_de_15_m_el_oi_no_se_evalua_con_el_de_3_m() -> None:
    scalp = {k: v for k, v in _SCALP_Z03.items() if k != "price_move_15m_pct"}
    assert _oi_ruptura("long", scalp)["estado"] == "no_evaluable"


def test_z03_la_reversion_cruza_el_oi_con_el_precio_de_15_m() -> None:
    """La reversion es el otro llamador de `_oi_check`: el mismo OI, el mismo precio."""
    ctx = build_setup_context(_SCALP_Z03, _VIEW, {}, barreras_reales(110.0, volumen=1.4),
                              {"horizons": {}}, direction="long", setup="reversion")
    oi = _req(evaluate_setup("reversion", "long", ctx), "respuesta de futuros (OI)")
    assert oi["estado"] == "cumple" and "precio 15 m" in oi["detalle"]  # main: no_cumple


def test_z03_el_rechazo_no_cambia() -> None:
    """El rechazo no lee el OI y su reaccion sigue siendo la de 3 m: el precio de 15 m no le mueve nada."""
    b = barreras_reales(110.0, volumen=1.4)
    sin15 = {k: v for k, v in _SCALP_Z03.items() if k != "price_move_15m_pct"}
    evs = [evaluate_setup("rechazo", "short", build_setup_context(
        s, _VIEW, {}, b, {"horizons": {}}, direction="short", setup="rechazo")) for s in (_SCALP_Z03, sin15)]
    assert evs[0]["requisitos"] == evs[1]["requisitos"]


# ---------------- Z-04 · retroceso con tamano y defensa en su tramo ----------------

_PIV = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0)]}
_IMPULSO = [(100.0, 100.2, 100.0), 104, 108, (110.0, 110.0, 109.5)]


def _continuacion(bars: list[dict], pivots: dict) -> tuple[dict, dict]:
    ctx = build_setup_context({"fut_delta_3m": 900.0, "vwap_dist_pct": 0.2}, _VIEW, {},
                              {"available": True, "current_price": bars[-1]["close"]}, _HHHL,
                              direction="long", setup="continuacion",
                              observ_bundle=_bundle(bars, pivots))
    return ctx, evaluate_setup("continuacion", "long", ctx)


def test_z04_un_retroceso_de_6_centesimas_no_confirma() -> None:
    # Tras el maximo 110 el precio solo cede a 109.934 (-0.06 %, 0.066 ATR) y sigue subiendo.
    bars = _bars(_IMPULSO + [(110.1, 110.2, 109.934), (110.4, 110.5, 110.0), (110.8, 111.0, 110.3)])
    ctx, ev = _continuacion(bars, _PIV)
    assert round(ctx["pullback_pct"], 2) == -0.06
    assert ctx["observables"]["pullback_pct"]["pullback_atr"] < LEVEL_TOL_ATR_MULT
    # main: CONFIRMADO (abs(-0.06) > 0 y la vela del pivote 100 «defendia» su propio nivel)
    assert ev["state"] == "CANDIDATO", ev
    assert _req(ev, "retroceso previo")["estado"] == "pendiente"
    assert _req(ev, "defensa del nivel")["estado"] != "cumple"


def test_z04_la_vela_del_pivote_no_defiende_su_propio_nivel() -> None:
    # El caso de 140 (2026-11-23 03:32Z): el nivel defendido ERA el extremo del retroceso. Retroceso
    # de 2 ATR hasta un minimo nuevo (108) que no vuelve al origen del impulso (100).
    piv = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0), (5 * TF, 108.0)]}
    bars = _bars(_IMPULSO + [109, (108.2, 108.6, 108.0), 109, (110.0, 110.2, 109.2)])
    ctx, ev = _continuacion(bars, piv)
    assert ev["state"] != "CONFIRMADO", ev  # main: CONFIRMADO, nivel 108 tocado por su vela
    d = ctx["observables"]["level_defended"]
    assert d["defended_level_price"] == 100.0 and d["defended_level_ts"] == 0
    assert d["defense_from_ts"] == ctx["observables"]["pullback_pct"]["pullback_start"] == 3 * TF


def test_z04_un_retroceso_real_y_defendido_sigue_confirmado() -> None:
    bars = _bars(_IMPULSO + [106, 102, (100.1, 100.6, 100.02), 101, (103.0, 103.2, 101.0)])
    ctx, ev = _continuacion(bars, _PIV)
    assert ctx["observables"]["pullback_pct"]["pullback_atr"] >= LEVEL_TOL_ATR_MULT
    assert ctx["level_defended"] is True
    assert ev["state"] == "CONFIRMADO", ev["missing_critical"] or ev["pendientes"]

