"""v1.5.0 — direccion y setup son cosas distintas, y cada setup tiene logica propia."""

from __future__ import annotations

import pytest

from app.scalp_logic import hypothesis_evidence
from app.setups import (
    DIRECTIONS,
    SETUP_LABELS,
    SETUP_SPECS,
    build_setup_context,
    evaluate_setup,
    split_hypothesis,
)

SETUPS_REALES = ("ruptura", "rechazo", "reversion", "continuacion")


def ctx_rico(**overrides: object) -> dict[str, object]:
    """Observables suficientes para que los cuatro setups tengan algo que decir."""
    base: dict[str, object] = {
        "price": 101.0,
        "barrier_level": 100.0,
        "touched_level": True,
        "volume_multiple": 1.4,
        "spot_delta": 500.0,
        "fut_delta": 900.0,
        "oi_chg_pct": 0.3,
        "book_bid_share": 0.62,
        "absorption": "Absorción de ventas",
        "reaction_pct": 0.4,
        "vwap_dist_pct": 0.2,
        "prior_trend": "alcista",
        "structure_event": "BOS",
        "structure_direction": "alcista",
        "liq_skew": 250_000.0,
        "multi_tf_aligned": True,
        "bars_closed_beyond": 3,
        "retest_done": True,
        "returned_inside": False,
        "pullback_pct": -0.8,
        "level_defended": True,
    }
    base.update(overrides)
    return base


# ---------------- cada setup es DISTINTO ----------------


def test_los_cuatro_setups_piden_requisitos_distintos() -> None:
    requisitos = {
        setup: tuple(r["requisito"] for r in evaluate_setup(setup, "long", ctx_rico())["requisitos"])
        for setup in SETUPS_REALES
    }
    for a in SETUPS_REALES:
        for b in SETUPS_REALES:
            if a < b:
                assert requisitos[a] != requisitos[b], f"{a} y {b} piden lo mismo"


def test_cada_setup_invalida_por_motivos_propios() -> None:
    """Lo que mata a una ruptura no es lo que mata a una continuacion."""
    invalidantes = {
        setup: {
            r["requisito"]
            for r in evaluate_setup(setup, "long", ctx_rico())["requisitos"]
            if r["invalida"]
        }
        for setup in SETUPS_REALES
    }
    assert invalidantes["ruptura"] == {"no vuelve dentro del rango"}
    assert invalidantes["rechazo"] == {
        "sin aceptacion mas alla del nivel",
        "sin cierres aceptados fuera",
    }
    assert invalidantes["reversion"] == {"contexto previo contrario"}
    assert invalidantes["continuacion"] == {"contexto alineado con la direccion"}
    # ...y ningun par comparte exactamente el mismo conjunto.
    assert len({frozenset(v) for v in invalidantes.values()}) == len(SETUPS_REALES)


def test_el_mismo_contexto_da_veredictos_distintos_por_setup() -> None:
    """Tendencia alcista previa: continuacion viable, reversion imposible."""
    ctx = ctx_rico(prior_trend="alcista")
    continuacion = evaluate_setup("continuacion", "long", ctx)
    reversion = evaluate_setup("reversion", "long", ctx)
    assert continuacion["state"] != "FALLIDO"
    assert reversion["state"] == "FALLIDO"
    assert any("contexto previo" in i for i in reversion["invalidaciones"])


def test_ruptura_y_rechazo_leen_el_mismo_nivel_al_reves() -> None:
    """El precio aceptado por encima del nivel confirma la ruptura y mata el rechazo."""
    ctx = ctx_rico(price=101.0, barrier_level=100.0, bars_closed_beyond=3, returned_inside=False)
    assert evaluate_setup("ruptura", "long", ctx)["state"] in ("CONFIRMADO", "CANDIDATO")
    # En un rechazo LARGO el nivel es un soporte: que el precio este por ENCIMA no invalida.
    # Se invalida un rechazo BAJISTA, cuya tesis es que la resistencia aguante.
    assert evaluate_setup("rechazo", "short", ctx)["state"] == "FALLIDO"


def test_los_pendientes_son_distintos_entre_setups() -> None:
    # Estructura observada pero apuntando al lado contrario: el requisito de reversion queda
    # PENDIENTE (se midio y aun no se cumple), no no_evaluable.
    ctx = ctx_rico(
        bars_closed_beyond=0, retest_done=False,
        structure_event="BOS", structure_direction="bajista",
    )
    pendientes = {s: set(evaluate_setup(s, "long", ctx)["pendientes"]) for s in SETUPS_REALES}
    assert "aceptacion fuera del nivel" in pendientes["ruptura"]
    assert "aceptacion fuera del nivel" not in pendientes["reversion"]
    assert "perdida o recuperacion de estructura" in pendientes["reversion"]
    assert "perdida o recuperacion de estructura" not in pendientes["ruptura"]


# ---------------- fail-closed ----------------


@pytest.mark.parametrize("setup", SETUPS_REALES)
def test_sin_dependencias_obligatorias_es_no_evaluable(setup: str) -> None:
    out = evaluate_setup(setup, "long", {})
    assert out["state"] == "NO EVALUABLE"
    assert out["faltantes"], "no se declara que falta"


@pytest.mark.parametrize("setup", SETUPS_REALES)
def test_sin_direccion_no_se_puede_evaluar_un_setup(setup: str) -> None:
    out = evaluate_setup(setup, "neutral", ctx_rico())
    assert out["state"] == "NO EVALUABLE"
    assert "direccion" in out["faltantes"]


def test_un_observable_ausente_no_se_da_por_bueno() -> None:
    out = evaluate_setup("ruptura", "long", ctx_rico(volume_multiple=None, retest_done=None))
    estados = {r["requisito"]: r["estado"] for r in out["requisitos"]}
    assert estados["volumen de empuje"] == "no_evaluable"
    assert estados["retest del nivel"] == "no_evaluable"
    assert "volumen de empuje" in out["no_evaluables"]


def test_setup_ninguno_no_afirma_nada() -> None:
    out = evaluate_setup("ninguno", "long", ctx_rico())
    assert out["state"] == "NO EVALUABLE"
    assert out["requisitos"] == []


def test_setup_desconocido_es_error() -> None:
    with pytest.raises(ValueError, match="setup desconocido"):
        evaluate_setup("moon", "long", ctx_rico())


# ---------------- compatibilidad con los valores antiguos ----------------


@pytest.mark.parametrize(
    ("legacy", "esperado"),
    [
        ("long", ("long", "ninguno")),
        ("short", ("short", "ninguno")),
        ("neutral", ("neutral", "ninguno")),
        ("esperando_ruptura", ("neutral", "ruptura")),
        ("esperando_rechazo", ("neutral", "rechazo")),
        ("esperando_reversion", ("neutral", "reversion")),
        ("esperando_continuacion", ("neutral", "continuacion")),
    ],
)
def test_los_valores_guardados_se_traducen_al_par(legacy: str, esperado: tuple) -> None:
    assert split_hypothesis(legacy) == esperado


def test_direccion_y_setup_son_seleccionables_por_separado() -> None:
    perfil = {"profile": "intradia", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0}
    out = hypothesis_evidence(
        None, perfil, scalp, direction="short", setup="rechazo", setup_context=ctx_rico()
    )
    assert out["direction"] == "short"
    assert out["setup"] == "rechazo"
    assert out["setup_label"] == "Rechazo"
    assert out["label"] == "Short · Rechazo"
    assert out["setup_evaluation"]["setup"] == "rechazo"


def test_la_misma_direccion_con_setups_distintos_da_resultados_distintos() -> None:
    perfil = {"profile": "intradia", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0}
    salidas = {
        setup: hypothesis_evidence(
            None, perfil, scalp, direction="long", setup=setup, setup_context=ctx_rico()
        )
        for setup in SETUPS_REALES
    }
    # Antes las cuatro "esperando_*" producian exactamente la misma respuesta: mismos
    # requisitos, mismos pendientes y mismas invalidaciones.
    firmas = {
        s: (
            o["setup_state"],
            tuple(o["pending_conditions"]),
            tuple(o["invalidations"]),
            tuple(
                (r["requisito"], r["estado"])
                for r in o["setup_evaluation"]["requisitos"]
            ),
        )
        for s, o in salidas.items()
    }
    assert len(set(firmas.values())) == len(SETUPS_REALES)


def test_los_estados_publicados_son_los_del_prompt() -> None:
    permitidos = {"PENDIENTE", "CANDIDATO", "CONFIRMADO", "FALLIDO", "NO EVALUABLE"}
    for setup in (*SETUPS_REALES, "ninguno"):
        for direccion in DIRECTIONS:
            for ctx in (ctx_rico(), {}):
                assert evaluate_setup(setup, direccion, ctx)["state"] in permitidos


def test_las_etiquetas_del_selector_estan_completas() -> None:
    assert set(SETUP_LABELS) == {"ninguno", *SETUPS_REALES}
    assert set(SETUP_SPECS) == set(SETUPS_REALES)
    assert set(DIRECTIONS) == {"long", "short", "neutral"}


# ---------------- el puente con los bloques publicados ----------------


def test_build_setup_context_no_inventa_lo_que_no_se_mide() -> None:
    ctx = build_setup_context(
        {"spot_delta_3m": 10.0, "fut_delta_3m": 20.0, "liquidations_measured": False},
        {"layers": {}},
        {},
        {"available": True, "current_price": 100.0, "nearest_resistance": {"center": 102.0}},
        {"horizons": {}},
        direction="long",
        setup="ruptura",
    )
    assert ctx["price"] == 100.0
    assert ctx["barrier_level"] == 102.0
    for no_medido in ("bars_closed_beyond", "retest_done", "returned_inside", "pullback_pct"):
        assert ctx[no_medido] is None, no_medido
    # Sin ventana de liquidaciones medida no hay skew, ni siquiera cero.
    assert ctx["liq_skew"] is None


def test_build_setup_context_elige_la_barrera_segun_direccion_y_setup() -> None:
    barreras = {
        "available": True,
        "current_price": 100.0,
        "nearest_resistance": {"center": 105.0},
        "nearest_support": {"center": 95.0},
    }
    args = ({}, {"layers": {}}, {}, barreras, {"horizons": {}})
    assert build_setup_context(*args, direction="long", setup="ruptura")["barrier_level"] == 105.0
    assert build_setup_context(*args, direction="short", setup="ruptura")["barrier_level"] == 95.0
    # Un rechazo largo se apoya en el soporte, no ataca la resistencia.
    assert build_setup_context(*args, direction="long", setup="rechazo")["barrier_level"] == 95.0
    assert build_setup_context(*args, direction="short", setup="rechazo")["barrier_level"] == 105.0


def test_el_evento_de_estructura_sale_de_las_distancias_publicadas() -> None:
    alcista = build_setup_context(
        {}, {"layers": {}}, {},
        {"available": True, "current_price": 100.0},
        {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": 1.2,
                             "distance_to_invalidation_pct": 4.0}}},
        direction="long", setup="reversion",
    )
    assert alcista["structure_event"] == "BOS"
    assert alcista["structure_direction"] == "alcista"
    assert alcista["prior_trend"] == "alcista"

    sin_evento = build_setup_context(
        {}, {"layers": {}}, {},
        {"available": True, "current_price": 100.0},
        {"horizons": {"4h": {"state": "HH_HL", "distance_to_bos_pct": -1.2,
                             "distance_to_invalidation_pct": 4.0}}},
        direction="long", setup="reversion",
    )
    assert sin_evento["structure_event"] is None
