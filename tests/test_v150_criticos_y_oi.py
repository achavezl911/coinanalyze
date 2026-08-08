"""Un setup no se CONFIRMA con requisitos críticos sin evaluar, y ΔOI no es dirección."""

from __future__ import annotations

import inspect

import pytest

from app import setups
from app.setups import (
    CONFIRMATION,
    CRITICAL,
    MIN_CONFIRMATIONS,
    MIN_COVERAGE_PCT,
    SECONDARY,
    SETUP_SPECS,
    classify_oi,
    evaluate_setup,
    oi_price_reading,
)

SETUPS = ("ruptura", "rechazo", "reversion", "continuacion")


def ctx_rico(**overrides: object) -> dict[str, object]:
    """Contexto con TODO observado, incluido lo que el sistema real no mide todavía."""
    base: dict[str, object] = {
        "price": 101.0, "barrier_level": 100.0, "breakout_boundary": 100.0, "touched_level": True,
        "volume_multiple": 1.4, "spot_delta": 500.0, "fut_delta": 900.0,
        "oi_chg_pct": 0.3, "book_bid_share": 0.62, "absorption": "Absorción de ventas",
        "reaction_pct": 0.4, "vwap_dist_pct": 0.2, "prior_trend": "alcista",
        "structure_event": "BOS", "structure_direction": "alcista", "liq_skew": 250_000.0,
        "multi_tf_aligned": True, "bars_closed_beyond": 3, "retest_done": True,
        "returned_inside": False, "pullback_pct": -0.8, "level_defended": True,
    }
    base.update(overrides)
    return base


# ---------------- 2. CONFIRMADO exige los criticos evaluados ----------------


def test_cada_setup_declara_niveles_en_todos_sus_requisitos() -> None:
    for setup in SETUPS:
        out = evaluate_setup(setup, "long", ctx_rico())
        for r in out["requisitos"]:
            assert r["nivel"] in (CRITICAL, CONFIRMATION, SECONDARY), r
        assert out["critical_total"] >= 1, f"{setup} no declara ningun critico"


def test_con_el_contexto_completo_si_se_puede_confirmar() -> None:
    """Control: si no confirmara nunca, la regla seria inútil en vez de estricta."""
    out = evaluate_setup("ruptura", "long", ctx_rico())
    assert out["state"] == "CONFIRMADO"
    assert out["missing_critical"] == []


@pytest.mark.parametrize(
    ("setup", "no_medidos"),
    [
        # Los tres que el prompt cita textualmente como reproducibles.
        ("ruptura", {"bars_closed_beyond": None, "retest_done": None, "returned_inside": None}),
        ("rechazo", {"returned_inside": None, "bars_closed_beyond": None}),
        ("continuacion", {"pullback_pct": None, "level_defended": None}),
    ],
)
def test_sin_criticos_evaluables_NUNCA_es_confirmado(setup: str, no_medidos: dict) -> None:
    out = evaluate_setup(setup, "long", ctx_rico(**no_medidos))
    assert out["state"] != "CONFIRMADO", f"{setup} confirma sin {sorted(no_medidos)}"
    assert out["state"] in ("CANDIDATO", "NO EVALUABLE", "PENDIENTE")
    assert out["missing_critical"], "no se declara que critico falta"


def test_el_estado_real_del_sistema_no_confirma_ninguna_ruptura() -> None:
    """`build_setup_context` deja en None lo que no se mide: eso no puede confirmar."""
    ctx = ctx_rico(bars_closed_beyond=None, retest_done=None, returned_inside=None,
                   pullback_pct=None, level_defended=None)
    for setup in SETUPS:
        out = evaluate_setup(setup, "long", ctx)
        if out["missing_critical"]:
            assert out["state"] != "CONFIRMADO", setup


def test_se_publican_los_recuentos_de_criticos_y_confirmaciones() -> None:
    out = evaluate_setup("ruptura", "long", ctx_rico(bars_closed_beyond=None))
    for campo in (
        "coverage_pct", "critical_total", "critical_evaluable",
        "confirmation_total", "confirmation_evaluable",
        "missing_critical", "missing_confirmation",
    ):
        assert campo in out, campo
    assert "aceptacion fuera del nivel" in out["missing_critical"]
    assert out["critical_evaluable"] == out["critical_total"] - 1
    assert 0 <= out["coverage_pct"] <= 100


def test_un_critico_incumplido_tampoco_confirma() -> None:
    """Distinto de no poder evaluarlo: aquí se midió y NO se cumple."""
    out = evaluate_setup("ruptura", "long", ctx_rico(bars_closed_beyond=0))
    assert out["state"] != "CONFIRMADO"
    assert out["missing_critical"] == []


def test_una_invalidacion_manda_sobre_todo() -> None:
    out = evaluate_setup("ruptura", "long", ctx_rico(returned_inside=True))
    assert out["state"] == "FALLIDO"


def test_sin_confirmaciones_suficientes_se_queda_en_candidato() -> None:
    out = evaluate_setup(
        "ruptura", "long",
        ctx_rico(volume_multiple=0.2, spot_delta=-500.0, fut_delta=-900.0, oi_chg_pct=None),
    )
    assert out["state"] != "CONFIRMADO"
    assert out["confirmation_met"] < out["min_confirmations"]


def test_los_umbrales_de_confirmacion_estan_declarados() -> None:
    assert MIN_CONFIRMATIONS >= 1
    assert 0 < MIN_COVERAGE_PCT <= 100
    for constante in (MIN_CONFIRMATIONS, MIN_COVERAGE_PCT):
        assert constante is not None
    # Y se publican con cada evaluacion, no viven escondidos en el codigo.
    out = evaluate_setup("ruptura", "long", ctx_rico())
    assert out["min_confirmations"] == min(MIN_CONFIRMATIONS, out["confirmation_total"])
    assert out["min_coverage_pct"] == MIN_COVERAGE_PCT


def test_la_clasificacion_de_cada_requisito_esta_documentada() -> None:
    """Cada evaluador explica en su docstring cuales son sus criticos."""
    for setup, spec in SETUP_SPECS.items():
        doc = inspect.getdoc(spec["evaluar"]) or ""
        assert "CRITIC" in doc.upper(), f"{setup} no documenta su jerarquia"


# ---------------- 3. el OI es un ESTADO, no una direccion ----------------


def test_oi_solo_no_vota_ninguna_direccion() -> None:
    for chg in (0.3, 2.0, -0.3, -2.0):
        estado = classify_oi(chg)
        assert estado["directional"] is False
        assert "LONG" not in estado["state"] and "SHORT" not in estado["state"]


def test_oi_arriba_no_es_long_ni_oi_abajo_es_short() -> None:
    """Sin precio, el OI no sostiene ninguna direccion."""
    for chg in (1.5, -1.5):
        lectura = oi_price_reading(None, classify_oi(chg))
        assert lectura["supports"] is None
        assert lectura["quadrant"] is None


def test_los_seis_estados_del_prompt_existen() -> None:
    assert classify_oi(None)["state"] == "NO_EVALUABLE"
    assert classify_oi(0.0)["state"] == "FLAT"
    assert classify_oi(0.3)["state"] == "EXPANSION"
    assert classify_oi(-0.3)["state"] == "CONTRACTION"
    assert classify_oi(5.0)["state"] == "EXTREME_EXPANSION"
    assert classify_oi(-5.0)["state"] == "EXTREME_CONTRACTION"


def test_el_extremo_prefiere_la_distribucion_medida() -> None:
    medido = classify_oi(0.2, band="extremo")
    assert medido["state"] == "EXTREME_EXPANSION"
    assert "banda medida" in medido["basis"]
    por_z = classify_oi(0.2, robust_z=4.1)
    assert por_z["state"] == "EXTREME_EXPANSION"
    assert "z robusto" in por_z["basis"]
    # Sin baseline se dice que el umbral es una convencion, no una medicion.
    sin_base = classify_oi(5.0)
    assert "sin baseline" in sin_base["basis"]


@pytest.mark.parametrize(
    ("precio", "oi_chg", "cuadrante", "sostiene"),
    [
        (0.5, 1.0, "expansion_alcista", 1),    # precio ↑ + OI ↑
        (-0.5, 1.0, "expansion_bajista", -1),  # precio ↓ + OI ↑
        (0.5, -1.0, "cierre_en_subida", None),  # precio ↑ + OI ↓ -> short covering
        (-0.5, -1.0, "cierre_en_bajada", None),  # precio ↓ + OI ↓ -> desapalancamiento
    ],
)
def test_los_cuatro_cuadrantes_precio_oi(
    precio: float, oi_chg: float, cuadrante: str, sostiene: int | None
) -> None:
    lectura = oi_price_reading(precio, classify_oi(oi_chg))
    assert lectura["quadrant"] == cuadrante
    assert lectura["supports"] == sostiene


def test_el_cierre_de_posiciones_no_demuestra_flujo_nuevo() -> None:
    subida = oi_price_reading(0.5, classify_oi(-1.0))
    assert "NO demuestra compras nuevas" in subida["reading"]
    assert subida["new_positioning"] is False
    bajada = oi_price_reading(-0.5, classify_oi(-1.0))
    assert "NO demuestra ventas nuevas" in bajada["reading"]


def test_la_lectura_no_se_presenta_como_certeza_causal() -> None:
    lectura = oi_price_reading(0.5, classify_oi(1.0))
    assert "compatible" in lectura["reading"]
    assert lectura["caveat"], "toda lectura conjunta declara su límite"
    assert "no demostrado" in lectura["caveat"].lower()


def test_los_setups_ya_no_tratan_el_oi_como_un_delta() -> None:
    fuente = inspect.getsource(setups)
    assert '_flow_check("open interest"' not in fuente
    assert '_flow_check("respuesta de futuros (OI)"' not in fuente
    assert '_oi_check("open interest"' in fuente
    assert '_oi_check("respuesta de futuros (OI)"' in fuente


def test_en_un_setup_el_oi_que_solo_sube_no_cumple_por_si_mismo() -> None:
    """OI expandiendo pero precio cayendo: no confirma un long, y tampoco lo invalida."""
    out = evaluate_setup("ruptura", "long", ctx_rico(oi_chg_pct=2.0, reaction_pct=-0.6))
    oi = next(r for r in out["requisitos"] if r["requisito"] == "open interest")
    assert oi["estado"] == "no_cumple"
    # Y con el precio subiendo mientras el OI cae, queda PENDIENTE: es un cierre, no una tesis.
    out2 = evaluate_setup("ruptura", "long", ctx_rico(oi_chg_pct=-2.0, reaction_pct=0.6))
    oi2 = next(r for r in out2["requisitos"] if r["requisito"] == "open interest")
    assert oi2["estado"] == "pendiente"
