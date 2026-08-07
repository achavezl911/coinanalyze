"""P1: selector intradia/swing con jerarquia explicita de temporalidades.

`trend_matrix` resolvia el conflicto entre marcos con un `medium_term_alignment` que decia
"mixto" y ahi se acababa. El perfil localiza la contradiccion en una capa concreta y declara
si invalida la tesis o solo obliga a esperar.
"""
from __future__ import annotations

import pytest

from app.scalp_logic import TRADING_PROFILES, profile_view


def trend(**biases: str) -> dict:
    return {"timeframes": {tf: {"bias": b, "flow_state": "x"} for tf, b in biases.items()}}


def matrix(**legs: tuple[float | None, float | None]) -> list[dict]:
    return [
        {
            "window": tf,
            "spot_delta": s,
            "fut_delta": f,
            "coverage_status": "complete" if s is not None and f is not None else "unavailable",
        }
        for tf, (s, f) in legs.items()
    ]


ALCISTA = (1_000.0, 5_000.0)
BAJISTA = (-1_000.0, -5_000.0)


def test_todo_alineado_da_sesgo_y_confianza_alta() -> None:
    out = profile_view(
        trend(**{"4h": "alcista", "1h": "alcista"}),
        matrix(**{"18m": ALCISTA, "15m": ALCISTA, "5m": ALCISTA, "1m": ALCISTA, "30s": ALCISTA}),
        "intradia",
    )
    assert out["bias"] == "alcista"
    assert out["confidence"] == "alta"
    assert out["contradictions"] == []
    assert out["coverage_pct"] == 100.0


def test_el_gatillo_no_tumba_una_tesis_swing() -> None:
    """Requisito explicito del prompt maestro: 30s/1m no invalidan varios dias."""
    out = profile_view(
        trend(**{"3d": "alcista", "1d": "alcista", "8h": "alcista", "4h": "alcista", "1h": "alcista"}),
        matrix(**{"18m": BAJISTA, "15m": BAJISTA}),
        "swing",
    )
    efectos = {c["efecto"] for c in out["contradictions"]}
    assert "invalida" not in efectos
    assert "esperar" in efectos
    assert out["bias"] == "alcista"


def test_el_mismo_conflicto_si_invalida_en_intradia() -> None:
    """La MISMA evidencia cambia de lectura segun el perfil: eso es el selector."""
    t = trend(**{"4h": "alcista", "1h": "alcista"})
    m = matrix(**{"18m": ALCISTA, "15m": ALCISTA, "5m": ALCISTA, "1m": BAJISTA, "30s": BAJISTA})
    intradia = profile_view(t, m, "intradia")
    assert any(c["efecto"] == "invalida" for c in intradia["contradictions"])
    assert intradia["confidence"] == "baja"


def test_contexto_contra_confirmacion_invalida_en_intradia() -> None:
    out = profile_view(
        trend(**{"4h": "alcista", "1h": "alcista"}),
        matrix(**{"18m": BAJISTA, "15m": BAJISTA, "5m": BAJISTA, "1m": ALCISTA, "30s": ALCISTA}),
        "intradia",
    )
    invalidan = [c for c in out["contradictions"] if c["efecto"] == "invalida"]
    assert invalidan
    assert "contexto vs confirmacion" in invalidan[0]["entre"]


def test_las_capas_de_cada_perfil_son_disjuntas() -> None:
    """El §6.2 original repetia 8h/4h en contexto y confirmacion, y 1h en dos capas.

    Con capas solapadas la misma observacion votaba dos veces e inflaba la confluencia. Se
    reparten sin repetir; el conjunto de temporalidades del perfil no cambia.
    """
    for perfil, spec in TRADING_PROFILES.items():
        vistos: list[str] = []
        for conf in spec["layers"].values():
            vistos.extend(conf["timeframes"])
        assert len(vistos) == len(set(vistos)), f"{perfil} repite: {vistos}"


def test_la_cobertura_escala_con_los_marcos_medidos() -> None:
    """Una sola temporalidad no puede aportar el peso completo de su capa."""
    out = profile_view(
        trend(**{"4h": "alcista", "18m": "alcista", "1m": "alcista"}), [], "intradia"
    )
    # 30*(1/2) + 45*(1/3) + 25*(1/2) = 42.5
    assert out["coverage_pct"] == 42.5
    assert out["confidence"] == "baja"


def test_una_capa_que_se_contradice_a_si_misma_no_vota() -> None:
    out = profile_view(
        trend(**{"4h": "alcista", "1h": "bajista"}),
        matrix(**{"18m": ALCISTA, "15m": ALCISTA, "5m": ALCISTA, "1m": ALCISTA, "30s": ALCISTA}),
        "intradia",
    )
    assert out["layers"]["contexto"]["bias"] == "conflicto"
    assert out["layers"]["contexto"]["score"] == 0.0
    assert any(c["efecto"] == "esperar" for c in out["contradictions"])


def test_el_dato_ausente_no_cuenta_como_neutral() -> None:
    """Regla del proyecto: se renormaliza sobre lo medible, nunca se suma 0."""
    out = profile_view(trend(**{"4h": "alcista", "1h": "alcista"}), [], "intradia")
    assert out["layers"]["confirmacion"]["bias"] == "sin_datos"
    assert out["layers"]["confirmacion"]["contribution"] is None
    assert out["bias"] == "alcista"  # el contexto medible manda
    assert out["coverage_pct"] < 100
    assert out["missing_data"]


def test_sin_ningun_dato_no_se_inventa_sesgo() -> None:
    out = profile_view({"timeframes": {}}, [], "swing")
    assert out["bias"] == "sin_datos"
    assert out["net_score"] is None
    assert out["confidence"] == "baja"


def test_los_pesos_y_contribuciones_son_auditables() -> None:
    """Sin caja negra: cada capa publica peso, score y aportacion."""
    out = profile_view(
        trend(**{"4h": "alcista", "1h": "alcista"}),
        matrix(**{"18m": ALCISTA, "15m": ALCISTA, "5m": ALCISTA, "1m": ALCISTA, "30s": ALCISTA}),
        "intradia",
    )
    for layer in out["layers"].values():
        assert layer["weight"] > 0
        assert layer["contribution"] is not None
        assert len(layer["timeframes"]) == layer["expected_timeframes"]
        for tf in layer["timeframes"]:
            assert tf["source"] in {"trend_matrix", "delta_matrix", "ninguna"}
    assert "convencion declarada" in out["weights_note"]


def test_los_perfiles_priorizan_temporalidades_distintas() -> None:
    intra = TRADING_PROFILES["intradia"]["layers"]
    swing = TRADING_PROFILES["swing"]["layers"]
    assert "30s" in intra["gatillo"]["timeframes"]
    assert "3d" in swing["contexto"]["timeframes"]
    assert all("3d" not in c["timeframes"] for c in intra.values())
    # 18m es obligatoria y aparece en los dos perfiles.
    assert any("18m" in c["timeframes"] for c in intra.values())
    assert any("18m" in c["timeframes"] for c in swing.values())


def test_en_swing_el_gatillo_ejecuta_pero_no_vota() -> None:
    """v1.5.0: 30s/1m tienen capa propia en swing, con PESO CERO.

    Antes vivian en `reference_only` y no aparecian en la jerarquia; ahora se ven donde
    corresponde (ejecucion) pero su peso es 0, asi que afinan el precio de entrada y no
    pueden mover el sesgo de una tesis de varios dias.
    """
    swing = TRADING_PROFILES["swing"]["layers"]
    assert set(swing["ejecucion"]["timeframes"]) == {"1m", "30s"}
    assert swing["ejecucion"]["weight"] == 0
    assert all(
        "30s" not in c["timeframes"] for nombre, c in swing.items() if nombre != "ejecucion"
    )
    out = profile_view(
        trend(**{"3d": "alcista", "1d": "alcista", "8h": "alcista", "4h": "alcista", "1h": "alcista"}),
        matrix(**{"18m": ALCISTA, "15m": ALCISTA, "5m": ALCISTA, "1m": BAJISTA, "30s": BAJISTA}),
        "swing",
    )
    assert out["bias"] == "alcista", "el gatillo no puede girar la tesis"
    assert out["layers"]["ejecucion"]["contribution"] == 0.0
    assert all(c["efecto"] != "invalida" for c in out["contradictions"])


def test_5m_no_es_a_la_vez_entrada_y_referencia_secundaria() -> None:
    """Describirla en las dos capas era una contradiccion de la propia jerarquia."""
    swing = TRADING_PROFILES["swing"]
    assert "5m" in swing["layers"]["entrada"]["timeframes"]
    assert "5m" not in swing["reference_only"]
    for perfil, spec in TRADING_PROFILES.items():
        en_capas = {tf for c in spec["layers"].values() for tf in c["timeframes"]}
        assert not (en_capas & set(spec["reference_only"])), perfil


def test_perfil_desconocido_es_error() -> None:
    with pytest.raises(ValueError, match="perfil desconocido"):
        profile_view({"timeframes": {}}, [], "scalping")
