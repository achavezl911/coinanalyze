"""Regresiones de la auditoria v1.3.8.

Cada test fija una conclusion que se verifico contra la base viva del LXC 140 antes de
tocar el codigo; el comentario de cada uno dice que se midio.
"""

from __future__ import annotations

import pathlib

from app.interpretation import price_barrier_read
from app.scalp_logic import _classify_passive, compute_swing_score, flow_confirmation

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


# ---------------------------------------------------------------- flujo por dos patas
def test_flow_vote_follows_both_legs_not_the_differential() -> None:
    """Medido en vivo (BTC, 2026-08-04): spot +10 047 y futuros +8 152 135, ambas patas
    COMPRANDO, y el diferencial daba -8 142 089, es decir un voto bajista."""
    result = flow_confirmation(10_047.0, 8_152_135.0)
    assert result["vote"] == 1
    assert result["state"] == "spot_y_futuros_compran"
    assert result["agreement"] is True


def test_both_legs_selling_votes_short() -> None:
    result = flow_confirmation(-3_187_426.0, -62_852_329.0)
    assert result["vote"] == -1
    assert result["agreement"] is True


def test_legs_that_disagree_produce_conflict_not_direction() -> None:
    """El desacuerdo entre spot y futuros es informacion, no una direccion."""
    result = flow_confirmation(5_000_000.0, -8_000_000.0)
    assert result["vote"] == 0
    assert result["agreement"] is False
    assert result["state"] == "spot_compra_futuros_vende"


def test_missing_leg_is_unavailable_never_zero() -> None:
    for spot, fut in ((None, 1.0), (1.0, None), (None, None)):
        result = flow_confirmation(spot, fut)
        assert result["vote"] is None
        assert result["state"] == "sin_datos"


def test_no_module_votes_direction_from_the_spot_minus_futures_differential() -> None:
    """El diferencial refleja el signo del CVD de futuros invertido en 93-94% de las
    sesiones (medido sobre 90 sesiones x 3 simbolos). No puede volver a ser un voto."""
    source = (APP / "scalp_logic.py").read_text(encoding="utf-8")
    trend = source[source.index("async def trend_matrix") : source.index("def compute_swing_score")]
    assert "flow_confirmation(spot_d, fut_d)" in trend
    for banned in ("if cvd_flow and cvd_flow > 0", "spot_minus_futures"):
        assert banned not in trend


# ------------------------------------------------------- absorcion sin doble conteo
def test_absorption_confirms_with_spot_leg_not_with_the_differential() -> None:
    """diff<0 es casi automatico cuando los futuros compran, asi que exigirlo junto a
    fut_delta>0 contaba dos veces la misma observacion."""
    # Futuros compran agresivo, el precio no sube, y el SPOT vende -> distribucion.
    absorbed, reading, _, _ = _classify_passive(
        fut_delta=8_000_000.0,
        fut_vol=20_000_000.0,
        price_move_pct=-0.004,
        spot_delta=-500_000.0,
        location="alto_valor",
        atr_pct=0.4,
    )
    assert absorbed == "compras"
    assert reading == "redistribucion_silenciosa"

    # Mismo flujo agresivo pero el spot ACOMPANA la compra: ya no es distribucion.
    _, reading_confirmed, _, _ = _classify_passive(
        fut_delta=8_000_000.0,
        fut_vol=20_000_000.0,
        price_move_pct=-0.004,
        spot_delta=+500_000.0,
        location="alto_valor",
        atr_pct=0.4,
    )
    assert reading_confirmed == "neutral"


def test_absorption_without_spot_data_stays_neutral() -> None:
    absorbed, reading, _, _ = _classify_passive(
        fut_delta=8_000_000.0,
        fut_vol=20_000_000.0,
        price_move_pct=-0.004,
        spot_delta=None,
        location="alto_valor",
        atr_pct=0.4,
    )
    assert absorbed == "compras"
    assert reading == "neutral"


# --------------------------------------------------- swing: ausencia != unanimidad
def _blocks(**over):
    base = {
        "structure_detail": {"horizons": {}},
        "macro_context": {"metrics": []},
        "cross_asset": {},
        "passive_flow": {},
        "trend_matrix": {"timeframes": {}},
    }
    base.update(over)
    return base


def test_single_active_component_is_not_reported_as_unanimous() -> None:
    """Medido en vivo (BTC): score 45 con 4 de 7 componentes mudos se publicaba como
    'long_share_pct: 100.0' y el panel pintaba el medidor lleno."""
    result = compute_swing_score(
        _blocks(trend_matrix={"timeframes": {"1d": {"cvd_spot": 5.0}, "3d": {"cvd_spot": 5.0}}})
    )
    assert result["long_share_pct"] == 20.0  # 20 de 100 puntos de peso
    assert result["short_share_pct"] == 0.0
    assert result["neutral_share_pct"] == 80.0
    assert result["evidence_coverage_pct"] == 20.0


def test_no_measurable_evidence_reports_sin_datos_not_neutral() -> None:
    result = compute_swing_score(_blocks())
    assert result["bias"] == "SIN_DATOS"
    assert result["evidence_coverage_pct"] == 0.0
    assert result["long_share_pct"] == 0.0


def test_low_coverage_degrades_conviction() -> None:
    result = compute_swing_score(
        _blocks(trend_matrix={"timeframes": {"1d": {"cvd_spot": 5.0}, "3d": {"cvd_spot": 5.0}}})
    )
    assert result["evidence_coverage_pct"] < 50
    assert result["conviction"] == "baja"


def test_contradictory_substructure_is_flagged_as_conflict() -> None:
    """HH_HL en 1d y LH_LL en 3d se promediaban a 0 y quedaban indistinguibles de 'sin dato'."""
    result = compute_swing_score(
        _blocks(structure_detail={"horizons": {"1d": {"state": "HH_HL"}, "3d": {"state": "LH_LL"}}})
    )
    structure = next(c for c in result["components"] if c["name"] == "Estructura 1d/3d")
    assert structure["status"] == "conflict"
    assert "Estructura 1d/3d" in result["conflicts"]


def test_component_without_data_is_unavailable_not_neutral() -> None:
    """Para BTC, cross_asset.relative_strength_vs_base_pct es null en todas las ventanas
    (el activo base ES BTC): el componente no existe, no es una lectura neutral."""
    result = compute_swing_score(_blocks(cross_asset={"relative_strength_vs_base_pct": {}}))
    rs = next(c for c in result["components"] if c["name"] == "Fuerza relativa vs BTC")
    assert rs["status"] == "unavailable"


# ------------------------------------------------- barreras: renormalizar, no sumar 0
_TRIANGLE = (0, 1, 2, 3, 4, 3, 2, 1)


def _bars(count: int, key_time: str, **extra):
    """Onda triangular con deriva: produce maximos y minimos locales estrictos, que es lo
    que _barrier_candidates necesita para reconocer pivotes con k=2."""
    rows = []
    for index in range(count):
        base = 100.0 + _TRIANGLE[index % 8] + (index // 8) * 0.3
        rows.append(
            {
                key_time: f"2026-01-01T00:00:{index:04d}",
                "price_high" if key_time == "session_date" else "high": base + 0.5,
                "price_low" if key_time == "session_date" else "low": base - 0.5,
                "price_close" if key_time == "session_date" else "close": base,
                "volume_usd": 1_000_000.0,
                **extra,
            }
        )
    return rows


def test_missing_cvd_renormalises_instead_of_scoring_zero() -> None:
    """Verificado en vivo: la resistencia BTC daba exactamente 77.7 = 35+25+7.73+0+10,
    es decir el componente de absorcion CVD (10 puntos) nunca sumaba nada."""
    daily = _bars(60, "session_date", cvd_spot_usd=None)
    result = price_barrier_read(daily, [], 103.0)
    assert result["available"] is True
    zones = [z for z in (result["nearest_support"], result["nearest_resistance"]) if z]
    assert zones, "el escenario debe producir al menos una zona"
    for zone in zones:
        assert "absorcion_cvd" in zone["unavailable_components"]
        assert zone["absorption_rate"] is None
        # el peso vivo excluye la absorcion, no la puntua como 0
        assert zone["score_weight_pct"] == 90.0


def test_present_cvd_is_scored_and_reported() -> None:
    daily = _bars(60, "session_date", cvd_spot_usd=5_000_000.0)
    result = price_barrier_read(daily, [], 103.0)
    zones = [z for z in (result["nearest_support"], result["nearest_resistance"]) if z]
    for zone in zones:
        assert "absorcion_cvd" in zone["scored_components"]
        assert zone["absorption_rate"] is not None
        assert zone["score_weight_pct"] == 100.0


def test_intraday_coverage_is_declared_and_warned() -> None:
    """El panel usaba 48 barras de 4h (7.8 dias de ohlcv 5min) presentandolas como el
    tramo de 720 barras / 120 dias que el codigo pide."""
    daily = _bars(60, "session_date", cvd_spot_usd=1.0)
    intraday = _bars(48, "bucket", cvd_spot_usd=1.0)
    result = price_barrier_read(daily, intraday, 103.0)
    method = result["method"]
    assert method["intraday_bars"] == 48
    assert method["intraday_target_bars"] == 720
    assert method["intraday_coverage_status"] == "insufficient"
    assert result["warnings"], "una cobertura insuficiente debe advertirse explicitamente"
