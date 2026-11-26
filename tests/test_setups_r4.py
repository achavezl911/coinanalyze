"""SETUPS R4 · V-13 + V-14 (Fable V3 N1 + N2): los dos requisitos de la continuacion vuelven a poder fallar.

V-13: «retroceso previo» se medía desde la mecha del pivote; con pivotes k=2 ese extremo ya distaba
>= 0.40 ATR y cumplia en 3650 de 3652 evaluaciones a 15 m. Ahora se mide en CIERRES.
V-14: «defensa del nivel» daba DEFENDIDO con el ultimo cierre al otro lado del nivel (hacian falta dos
cierres) y «reacciono» era `cierre > extremo`. Ahora el ultimo cierre pasado invalida y la reaccion pide
un cierre de vuelta MAS ALLA de la tolerancia.
"""

from __future__ import annotations

from app.setups import LEVEL_TOL_ATR_MULT, _level_defended, build_setup_context, evaluate_setup

TF = 900
_VIEW = {"layers": {"contexto": {"bias": "alcista"}, "confirmacion": {"bias": "alcista"}}}
_HHHL = {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": 1.0,
                              "distance_to_invalidation_pct": 5.0}}}
KW = {"tf": "15m", "source": "test", "as_of": "x"}


def _bars(velas: list, t0: int = 0) -> list[dict]:
    """(close, high, low) o un close suelto (high/low a +-0.2), una vela cada TF desde t0."""
    out = []
    for i, c in enumerate(velas):
        close, high, low = c if isinstance(c, tuple) else (c, c + 0.2, c - 0.2)
        out.append({"ts": t0 + i * TF, "open": None, "high": high, "low": low, "close": close})
    return out


def _continuacion(bars: list[dict], pivots: dict, atr: float = 1.0) -> tuple[dict, dict]:
    bundle = {"timeframe": "15m", "bar_seconds": TF, "source": "test", "as_of": "2026-11-26T00:00:00+00:00",
              "bars": bars, "atr": atr, "pivots": pivots}
    ctx = build_setup_context({"fut_delta_3m": 900.0, "vwap_dist_pct": 0.2}, _VIEW, {},
                              {"available": True, "current_price": bars[-1]["close"]}, _HHHL,
                              direction="long", setup="continuacion", observ_bundle=bundle)
    return ctx, evaluate_setup("continuacion", "long", ctx)


def _req(ev: dict, nombre: str) -> dict:
    return next(r for r in ev["requisitos"] if r["requisito"] == nombre)


# El caso real de 140 (Fable V3 N2): BTC largo, vela 15 m ts 1795117500. Velas (ts, high, low, close) de
# /api/ohlcv 5min agregadas a 15 m; pivotes y ATR los de `setup_confirmation_bundle` en ese cierre.
_N2_VELAS = [
    (1795111200, 62880.9, 62632.3, 62700.1), (1795112100, 63282.6, 62662.5, 63252.1),
    (1795113000, 63281.7, 63010.7, 63017.2), (1795113900, 63063.0, 62850.5, 62867.1),
    (1795114800, 62873.6, 62663.7, 62693.2), (1795115700, 62891.9, 62642.2, 62800.0),
    (1795116600, 62823.3, 62519.3, 62566.6), (1795117500, 62623.5, 62269.8, 62341.0),
]
_N2_PIV = {"highs": [(1795112100, 63282.6)], "lows": [(1795111200, 62632.3)]}
_N2_ATR = 399.77142857142826


def test_v14_el_caso_real_de_140_con_el_cierre_bajo_el_nivel_no_esta_defendido() -> None:
    bars = [{"ts": t, "open": None, "high": h, "low": lo, "close": c} for t, h, lo, c in _N2_VELAS]
    d = _level_defended(bars, 1, _N2_PIV, _N2_ATR, {}, **KW)
    assert d["defended_level_price"] == 62632.3
    assert bars[-1]["close"] < 62632.3 - _N2_ATR * LEVEL_TOL_ATR_MULT  # 62341.0 < 62432.4
    assert d["value"] is False, d  # main: True («nivel tocado y con reaccion a favor»)
    _, ev = _continuacion(bars, _N2_PIV, _N2_ATR)
    assert _req(ev, "defensa del nivel")["estado"] == "no_cumple"
    assert ev["state"] != "CONFIRMADO"


def test_v14_tocar_y_cerrar_un_pelo_sobre_el_minimo_no_es_reaccion() -> None:
    # Nivel 100, tolerancia 0.5: toca 100.0 y cierra en 100.1, dentro de la banda. main: defendido.
    piv = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0)]}
    bars = _bars([(100.0, 100.2, 100.0), 104, 108, (110.0, 110.0, 109.5), 106, 102, (100.1, 101.0, 100.0)])
    assert _level_defended(bars, 1, piv, 1.0, {}, **KW)["value"] is not True


def test_v13_un_retroceso_nulo_en_cierres_no_cumple() -> None:
    # Tras el maximo 110 las mechas bajan a 109.3 (0.7 ATR) pero ningun cierre cede: 110.5, 111, 111.6.
    piv = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0)]}
    bars = _bars([(100.0, 100.2, 100.0), 104, 108, (110.0, 110.0, 109.5),
                  (110.5, 110.8, 109.3), (111.0, 111.2, 109.8), (111.6, 111.8, 110.6)])
    ctx, ev = _continuacion(bars, piv)
    assert _req(ev, "retroceso previo")["estado"] == "pendiente"  # main: cumple (0.7 ATR de mecha)
    assert ev["state"] != "CONFIRMADO"
    pb = ctx["observables"]["pullback_pct"]
    assert pb["pullback_atr"] == 0
    assert pb["pullback_wick_atr"] >= LEVEL_TOL_ATR_MULT


def test_control_una_continuacion_de_libro_cumple_las_dos() -> None:
    # Impulso 100 -> 110, retroceso en cierres 110 -> 100.3 (9.7 ATR; 10.3 de mecha) hasta el origen,
    # que aguanta (ningun cierre bajo 99.5), y el ultimo cierre vuelve a 102.5, pasada la tolerancia.
    # Pasa con main y con la rama: el arreglo no rechaza la continuacion buena.
    piv = {"highs": [(3 * TF, 110.0)], "lows": [(0, 100.0)]}
    bars = _bars([(100.0, 100.2, 100.0), 104, 108, (110.0, 110.0, 109.5), 106, 102,
                  (100.3, 100.8, 99.7), (101.2, 101.4, 100.2), (102.5, 102.7, 101.1)])
    ctx, ev = _continuacion(bars, piv)
    assert ctx["observables"]["pullback_pct"]["pullback_atr"] >= LEVEL_TOL_ATR_MULT
    assert _req(ev, "retroceso previo")["estado"] == "cumple"
    assert _req(ev, "defensa del nivel")["estado"] == "cumple"
    assert ev["state"] == "CONFIRMADO", ev["missing_critical"] or ev["pendientes"]
