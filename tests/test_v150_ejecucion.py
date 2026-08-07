"""v1.5.0 — la ejecucion NO se clasifica con un umbral universal de 5 bps."""

from __future__ import annotations

import inspect
import io
import tokenize

import pytest

from app import ai_context, api, scalp_logic
from app.scalp_logic import (
    EXECUTION_PROFILES,
    execution_assessment,
    hypothesis_evidence,
    scalp_bias_label,
)


def plan(**overrides: float | None) -> dict:
    """Operacion intradia completa: entrada 100, objetivo 100.5 (50 bps), stop 99.75."""
    base = {
        "profile": "intradia",
        "spread_bps": 1.0,
        "slippage_bps": 0.5,
        "fee_bps_per_side": 2.0,
        "size_usd": 10_000.0,
        "entry": 100.0,
        "target": 100.5,
        "stop": 99.75,
    }
    base.update(overrides)
    return base


# ---------------- ya no hay umbral universal ----------------


def test_el_spread_no_veta_por_si_solo() -> None:
    """Con la misma evidencia, un spread ancho ya no convierte la lectura en No Trade."""
    assert scalp_bias_label(80.0, 20.0) == ("Long Momentum", "alta")
    assert "spread" not in str(inspect.signature(scalp_bias_label))


def _codigo_sin_prosa(modulo) -> str:
    """Fuente del modulo SIN comentarios ni literales de texto.

    Los comentarios que explican por que se retiro el umbral contienen necesariamente la
    expresion retirada; lo que no puede quedar es codigo que la ejecute.
    """
    tokens = tokenize.generate_tokens(io.StringIO(inspect.getsource(modulo)).readline)
    return " ".join(
        tok.string
        for tok in tokens
        if tok.type not in (tokenize.COMMENT, tokenize.STRING)
    )


def test_no_queda_ningun_umbral_universal_de_5_bps_en_el_backend() -> None:
    """Ni el veredicto ni el veto pueden salir de comparar el spread contra un 5 literal."""
    for modulo in (scalp_logic, api, ai_context):
        codigo = _codigo_sin_prosa(modulo)
        for patron in ("spread_bps > 5", "spread > 5", "spread <= 5", "spread_bps ) > 5"):
            assert patron not in codigo, f"{modulo.__name__} ejecuta `{patron}`"
        # El literal de la etiqueta vieja no puede existir ni siquiera como cadena.
        fuente = inspect.getsource(modulo)
        assert "caro para intradía" not in fuente
        assert "caro para intradia" not in fuente
    # El unico 5 que queda es el umbral de AVISO de intradia, y vive en una constante con
    # nombre, es distinto por perfil y no produce ningun veredicto.
    assert EXECUTION_PROFILES["intradia"]["spread_warn_bps"] == 5.0
    assert execution_assessment(profile="intradia", spread_bps=99.0)["verdict"] == "SIN EVALUAR"
    # El unico 5 que queda es el umbral de AVISO de intradia, y vive en una constante con
    # nombre, es distinto por perfil y no produce ningun veredicto.
    assert EXECUTION_PROFILES["intradia"]["spread_warn_bps"] == 5.0
    assert execution_assessment(profile="intradia", spread_bps=99.0)["verdict"] == "SIN EVALUAR"


def test_el_umbral_de_aviso_depende_del_perfil_y_esta_documentado() -> None:
    assert set(EXECUTION_PROFILES) == {"intradia", "swing"}
    intradia = EXECUTION_PROFILES["intradia"]["spread_warn_bps"]
    swing = EXECUTION_PROFILES["swing"]["spread_warn_bps"]
    assert swing > intradia, "el swing tolera mucho mas spread que el intradia"
    for spec in EXECUTION_PROFILES.values():
        assert spec["note"], "cada perfil declara por que su umbral es el que es"


def test_un_spread_ancho_en_swing_no_se_llama_caro_para_intradia() -> None:
    out = execution_assessment(**plan(profile="swing", spread_bps=10.0, target=104.0, stop=98.0))
    assert out["profile"] == "swing"
    assert out["spread_warning"] is None, "10 bps no son un aviso en swing"
    assert out["verdict"] == "aceptable"
    assert "intradía" not in str(out)


def test_el_mismo_spread_si_avisa_en_intradia() -> None:
    out = execution_assessment(**plan(spread_bps=10.0))
    assert out["spread_warning"] is not None
    assert "AVISO" in out["spread_warning"]
    # ...pero el aviso no es el veredicto.
    assert out["status"] == "EVALUADO"


# ---------------- el veredicto sale del coste sobre el objetivo ----------------


def test_coste_sobre_objetivo_aceptable() -> None:
    out = execution_assessment(**plan())
    # spread 1 + fees 2x2 + slippage 0.5x2 = 6 bps sobre un objetivo de 50 bps = 12 %.
    assert out["total_cost_bps"] == 6.0
    assert out["target_bps"] == 50.0
    assert out["cost_to_target"] == pytest.approx(0.12)
    assert out["verdict"] == "ajustado"


def test_el_mismo_coste_es_prohibitivo_con_un_objetivo_pequeno() -> None:
    caro = execution_assessment(**plan(target=100.1))  # objetivo 10 bps
    barato = execution_assessment(**plan(target=102.0))  # objetivo 200 bps
    assert caro["total_cost_bps"] == barato["total_cost_bps"], "el coste es el mismo"
    assert caro["cost_to_target_band"] == "prohibitivo"
    assert barato["cost_to_target_band"] == "aceptable"
    assert caro["verdict"] == "prohibitivo"
    assert barato["verdict"] != "prohibitivo"


def test_unas_comisiones_mas_altas_empeoran_el_veredicto() -> None:
    maker = execution_assessment(**plan(fee_bps_per_side=0.2, order_type="maker"))
    taker = execution_assessment(**plan(fee_bps_per_side=5.5, order_type="taker"))
    assert maker["total_cost_bps"] < taker["total_cost_bps"]
    assert maker["verdict"] == "aceptable"
    assert taker["verdict"] == "prohibitivo"


def test_el_coste_sobre_riesgo_tambien_manda() -> None:
    """Objetivo comodo pero stop pegadisimo: la peor de las dos lecturas es la que vale."""
    out = execution_assessment(**plan(target=110.0, stop=99.9))
    assert out["cost_to_target_band"] == "aceptable"
    assert out["cost_to_risk_band"] == "prohibitivo"
    assert out["verdict"] == "prohibitivo"


def test_el_funding_estimado_entra_en_el_coste() -> None:
    sin_funding = execution_assessment(**plan())
    con_funding = execution_assessment(**plan(funding_bps=8.0))
    assert con_funding["total_cost_bps"] - sin_funding["total_cost_bps"] == 8.0


# ---------------- fail-closed ----------------


@pytest.mark.parametrize(
    ("falta", "etiqueta"),
    [("target", "objetivo"), ("stop", "stop"), ("fee_bps_per_side", "comision"),
     ("size_usd", "tamaño"), ("entry", "entrada")],
)
def test_sin_los_insumos_de_la_operacion_es_sin_evaluar(falta: str, etiqueta: str) -> None:
    out = execution_assessment(**plan(**{falta: None}))
    assert out["status"] == "SIN EVALUAR"
    assert out["verdict"] == "SIN EVALUAR"
    assert etiqueta in out["missing_inputs"]


def test_spread_estrecho_sin_plan_sigue_siendo_sin_evaluar() -> None:
    """Un spread de 0.2 bps no autoriza nada por si mismo."""
    out = execution_assessment(profile="intradia", spread_bps=0.2)
    assert out["verdict"] == "SIN EVALUAR"
    assert set(out["missing_inputs"]) == {"entrada", "objetivo", "stop", "comision", "tamaño"}


def test_se_declara_que_componentes_del_coste_faltan() -> None:
    out = execution_assessment(**plan(slippage_bps=None))
    assert "slippage_bps" in out["cost_components_missing"]
    assert out["total_cost_bps"] == 5.0  # spread 1 + fees 4, sin slippage


def test_la_hipotesis_publica_sin_evaluar_mientras_no_haya_plan() -> None:
    perfil = {"profile": "swing", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0, "spread_bps": 12.0}
    out = hypothesis_evidence("long", perfil, scalp)
    assert out["execution"]["status"] == "SIN EVALUAR"
    assert out["execution"]["profile"] == "swing"
    # 12 bps no disparan aviso en swing y en ningun caso se habla de intradia.
    assert out["execution"]["spread_warning"] is None


def test_la_hipotesis_evalua_la_ejecucion_cuando_el_operador_da_el_plan() -> None:
    perfil = {"profile": "intradia", "coverage_pct": 100.0, "layers": {}, "contradictions": []}
    scalp = {"absorption": "Sin señal", "basis_status": "VALID", "book_status": "ok",
             "missing_components": [], "evidence_coverage_pct": 100.0, "spread_bps": 1.0}
    out = hypothesis_evidence(
        "long", perfil, scalp,
        plan={"entry": 100.0, "target": 102.0, "stop": 99.0,
              "size_usd": 5_000.0, "fee_bps_per_side": 2.0, "slippage_bps": 0.5},
    )
    assert out["execution"]["status"] == "EVALUADO"
    assert out["execution"]["verdict"] == "aceptable"
