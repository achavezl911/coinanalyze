"""Observables MEDIDOS sobre velas cerradas: bars_closed_beyond, returned_inside, retest_done,
pullback_pct y level_defended. Reglas duras de la especificacion:

- el centro de la zona NO es la frontera de ruptura (se usa high/low);
- una vela ABIERTA no cuenta como cierre (el bundle solo trae velas cerradas);
- un hueco en la secuencia necesaria -> NO_EVALUABLE, nunca False;
- la ausencia de dato -> None / PENDING, nunca False.
"""

from __future__ import annotations

from app.setups import build_setup_context, setup_observables

TF = 900  # 15 m en segundos


def _bars(start: int, closes: list[float], *, step: int = TF, hl: float = 0.2) -> list[dict]:
    """Velas cerradas ascendentes; high/low se derivan del cierre salvo override por tupla."""
    out = []
    ts = start
    for c in closes:
        if isinstance(c, tuple):
            close, high, low = c
        else:
            close, high, low = c, c + hl, c - hl
        out.append({"ts": ts, "open": None, "high": high, "low": low, "close": close})
        ts += step
    return out


def _bundle(bars: list[dict], *, atr: float | None = 1.0, pivots=None) -> dict:
    return {
        "timeframe": "15m",
        "bar_seconds": TF,
        "source": "test",
        "as_of": "2026-08-08T00:00:00+00:00",
        "bars": bars,
        "pivots": pivots or {"highs": [], "lows": []},
        "atr": atr,
    }


ZONE = {"low": 99.0, "high": 100.0, "center": 99.5}


# ---------------- 1.1 la frontera es high/low, no el centro ----------------


def test_ruptura_long_usa_zone_high_como_frontera() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.4, 100.5])))
    assert obs["breakout_boundary"] == 100.0
    assert obs["zone_center"] == 99.5
    assert obs["bars_closed_beyond"]["value"] == 2


def test_ruptura_short_usa_zone_low_como_frontera() -> None:
    obs = setup_observables(direction="short", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [98.5, 98.4])))
    assert obs["breakout_boundary"] == 99.0
    assert obs["bars_closed_beyond"]["value"] == 2


def test_precio_sobre_center_pero_dentro_de_resistencia_no_es_ruptura() -> None:
    # 99.7 > center(99.5) pero < high(100.0): NO cuenta como cierre fuera.
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [99.7, 99.8])))
    assert obs["bars_closed_beyond"]["value"] == 0


# ---------------- 1.2 bars_closed_beyond ----------------


def test_cero_cierres_fuera() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [99.2, 99.4, 99.1])))
    b = obs["bars_closed_beyond"]
    assert b["value"] == 0 and b["status"] == "MEASURED"


def test_un_cierre_fuera() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [99.5, 100.6])))
    assert obs["bars_closed_beyond"]["value"] == 1


def test_dos_cierres_fuera() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.3, 100.6])))
    assert obs["bars_closed_beyond"]["value"] == 2


def test_solo_cuenta_la_racha_final_no_los_toques_previos() -> None:
    # Un cierre fuera aislado y luego dentro: la racha final es 0.
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.5, 99.4, 99.3])))
    assert obs["bars_closed_beyond"]["value"] == 0


def test_hueco_en_la_secuencia_es_no_evaluable() -> None:
    # Dos cierres fuera pero separados por un hueco de datos (falta la vela intermedia).
    bars = [
        {"ts": 0, "open": None, "high": 100.6, "low": 100.2, "close": 100.4},
        {"ts": 2 * TF, "open": None, "high": 100.8, "low": 100.4, "close": 100.6},
    ]
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE, bundle=_bundle(bars))
    b = obs["bars_closed_beyond"]
    assert b["value"] is None and b["status"] == "NO_EVALUABLE"


def test_bundle_ausente_deja_bars_en_none() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE, bundle=None)
    assert obs["bars_closed_beyond"]["value"] is None
    assert obs["bars_closed_beyond"]["status"] == "UNAVAILABLE"


# ---------------- 1.3 returned_inside ----------------


def test_regreso_posterior_dentro_es_true() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.5, 99.4])))
    r = obs["returned_inside"]
    assert r["value"] is True and r["status"] == "MEASURED"


def test_sigue_fuera_es_false_no_none() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.5, 100.7])))
    assert obs["returned_inside"]["value"] is False


def test_sin_periodo_posterior_es_none() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [100.5])))
    r = obs["returned_inside"]
    assert r["value"] is None and r["status"] == "PENDING"


def test_sin_cierre_fuera_returned_inside_no_evaluable() -> None:
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE,
                            bundle=_bundle(_bars(0, [99.2, 99.3])))
    assert obs["returned_inside"]["value"] is None


# ---------------- 1.4 retest_done (SECONDARY) ----------------


def test_retest_con_contacto_y_reaccion() -> None:
    # rompe (100.6), vuelve a tocar la frontera 100.0 (low=100.02), y reacciona por encima.
    bars = _bars(0, [(100.6, 100.8, 100.4), (100.2, 100.4, 100.02), (100.9, 101.0, 100.5)])
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE, bundle=_bundle(bars))
    r = obs["retest_done"]
    assert r["value"] is True and r["retest_status"] == "done"
    assert r["retest_time"] == bars[1]["ts"]


def test_sin_retest_es_false_no_bloquea() -> None:
    # rompe y sigue subiendo sin volver a tocar el nivel.
    bars = _bars(0, [(100.6, 100.8, 100.5), (101.5, 101.7, 101.3)])
    obs = setup_observables(direction="long", setup="ruptura", zone=ZONE, bundle=_bundle(bars))
    assert obs["retest_done"]["value"] is False
    assert obs["retest_done"]["retest_status"] == "not_yet"


# ---------------- 1.5 pullback_pct ----------------


def test_pullback_real_desde_impulso_estructural() -> None:
    # impulso: swing low 100 (t=0) -> swing high 110 (t=5*TF); retroceso a 106 despues.
    pivots = {"highs": [(5 * TF, 110.0)], "lows": [(0, 100.0)]}
    bars = _bars(0, [100, 103, 106, 108, 110, (110, 110, 110), (106, 107, 106)])
    obs = setup_observables(direction="long", setup="continuacion", zone=ZONE,
                            bundle=_bundle(bars, pivots=pivots, atr=2.0))
    p = obs["pullback_pct"]
    assert p["status"] == "MEASURED"
    assert p["value"] < 0  # retroceso de un impulso alcista es negativo
    assert p["impulse_end"] == 5 * TF


def test_sin_impulso_identificable_pullback_none() -> None:
    obs = setup_observables(direction="long", setup="continuacion", zone=ZONE,
                            bundle=_bundle(_bars(0, [100, 101]), pivots={"highs": [], "lows": []}))
    p = obs["pullback_pct"]
    assert p["value"] is None and p["status"] == "UNAVAILABLE"


# ---------------- 1.6 level_defended ----------------


def test_nivel_defendido() -> None:
    # nivel = swing low 100 (t=0); el precio baja a tocarlo (low 100.05) y reacciona arriba.
    pivots = {"highs": [], "lows": [(0, 100.0)]}
    bars = _bars(0, [(100.05, 100.4, 100.02), (100.3, 100.5, 100.1), (101.0, 101.2, 100.6)])
    obs = setup_observables(direction="long", setup="continuacion", zone=ZONE,
                            bundle=_bundle(bars, pivots=pivots, atr=1.0))
    d = obs["level_defended"]
    assert d["value"] is True
    assert d["defended_level_type"] == "swing_low"
    assert d["defended_level_price"] == 100.0


def test_nivel_perdido() -> None:
    # nivel = swing low 100; dos cierres claramente por debajo -> perdido (False).
    pivots = {"highs": [], "lows": [(0, 100.0)]}
    bars = _bars(0, [(98.5, 99.0, 98.3), (98.0, 98.5, 97.8)])
    obs = setup_observables(direction="long", setup="continuacion", zone=ZONE,
                            bundle=_bundle(bars, pivots=pivots, atr=0.5))
    assert obs["level_defended"]["value"] is False


# ---------------- puente con build_setup_context ----------------


def test_build_setup_context_sin_bundle_mantiene_none() -> None:
    ctx = build_setup_context(
        {}, {"layers": {}}, {},
        {"available": True, "current_price": 100.0, "nearest_resistance": {"center": 102.0}},
        {"horizons": {}}, direction="long", setup="ruptura",
    )
    for k in ("bars_closed_beyond", "retest_done", "returned_inside", "pullback_pct",
              "level_defended"):
        assert ctx[k] is None
    assert ctx["observables"] is None


def test_build_setup_context_con_bundle_mide_los_observables() -> None:
    barreras = {
        "available": True,
        "current_price": 100.5,
        "nearest_resistance": {"center": 99.5, "low": 99.0, "high": 100.0},
    }
    bundle = _bundle(_bars(0, [100.4, 100.6]))
    ctx = build_setup_context(
        {}, {"layers": {}}, {}, barreras, {"horizons": {}},
        direction="long", setup="ruptura", observ_bundle=bundle,
    )
    assert ctx["breakout_boundary"] == 100.0
    assert ctx["zone_center"] == 99.5
    assert ctx["bars_closed_beyond"] == 2
    assert ctx["observables"]["bars_closed_beyond"]["timeframe"] == "15m"
