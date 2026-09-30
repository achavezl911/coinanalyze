"""La palabra de DECIDE dice la DECISION del sistema, no el signo de una resta.

El defecto que estos tests cobran, medido en PRODUCCION (release a15a89d) el 2026-09-30 a las
05:24:30Z sobre BTC: `decide.bias.value` = 'SHORT', `decide.state.value` = 'No Trade',
`edge` 5.0 y `no_trade_reasons` ['score_edge_low']. La palabra salia de
`operator_read.bias` -el SIGNO de long_score - short_score, sin umbral- y el estado sale de
`scalp_bias_label`, que exige edge >= 12 y que el score ganador llegue a 58.
"""
import pytest

from app.ai_context import (
    MESA_PALABRA_LONG,
    MESA_PALABRA_NO_EVALUABLE,
    MESA_PALABRA_SHORT,
    MESA_PALABRA_SIN_LADO,
    build_operator_read,
    palabra_de_la_decision,
)
from app.scalp_logic import scalp_bias_label
from app.signal_ledger import (
    _LONG_STATES,
    _NEUTRAL_STATES,
    _SHORT_STATES,
    classify_signal_observation,
)

CON_LADO = {MESA_PALABRA_LONG, MESA_PALABRA_SHORT}


def lado(palabra: str) -> str | None:
    return {MESA_PALABRA_LONG: "long", MESA_PALABRA_SHORT: "short"}.get(palabra)


@pytest.mark.parametrize("state", sorted(_LONG_STATES))
def test_los_estados_largos_dan_long(state):
    assert palabra_de_la_decision(state)[0] == MESA_PALABRA_LONG


@pytest.mark.parametrize("state", sorted(_SHORT_STATES))
def test_los_estados_cortos_dan_short(state):
    assert palabra_de_la_decision(state)[0] == MESA_PALABRA_SHORT


@pytest.mark.parametrize("state", sorted(_NEUTRAL_STATES))
def test_el_estado_neutral_no_es_un_lado(state):
    palabra, motivo = palabra_de_la_decision(state)
    assert palabra == MESA_PALABRA_SIN_LADO
    assert palabra not in CON_LADO
    # SIN MOTIVO A PROPOSITO: la linea de debajo de la palabra publica `no_trade_reasons`, que
    # dice POR QUE no se opera. Un motivo aqui la taparia para repetir lo que la palabra ya dice.
    assert motivo is None


def test_un_estado_que_no_existe_no_se_vuelve_un_lado():
    # «Long Breakout» LLEVA la palabra Long dentro y no es ninguno de los estados del registro.
    # Un mapa por subcadena lo convertiria en LONG en silencio; este no.
    palabra, motivo = palabra_de_la_decision("Long Breakout")
    assert palabra == MESA_PALABRA_NO_EVALUABLE
    assert motivo and "Long Breakout" in motivo


@pytest.mark.parametrize("state", ["Sin datos suficientes", "", None, "  "])
def test_lo_que_el_sistema_no_pudo_evaluar_se_dice(state):
    palabra, motivo = palabra_de_la_decision(state)
    assert palabra == MESA_PALABRA_NO_EVALUABLE
    assert motivo


def test_la_palabra_coincide_con_la_direccion_DEL_REGISTRO_estado_a_estado():
    """La promesa del encargo, contrastada contra `classify_signal_observation`.

    Se le dan al clasificador las condiciones en las que SI clasifica -libro ok y cobertura
    alta- para aislar la variable que importa: el estado.
    """
    for state in sorted(_LONG_STATES | _SHORT_STATES | _NEUTRAL_STATES):
        _, direccion, _ = classify_signal_observation(
            {"state": state, "book_status": "ok", "evidence_coverage_pct": 90.0}
        )
        palabra = palabra_de_la_decision(state)[0]
        esperado = {"long": "long", "short": "short", "neutral": None}[direccion]
        assert lado(palabra) == esperado, f"{state}: {palabra} contra {direccion}"


def test_ninguna_palabra_con_lado_sale_de_un_estado_sin_lado():
    for state in ["No Trade", "Sin datos suficientes", "Long Breakout", "", None]:
        assert palabra_de_la_decision(state)[0] not in CON_LADO


def test_la_franja_en_la_que_vivia_el_defecto():
    """El caso de produccion, reconstruido desde las DOS funciones que discrepaban.

    Con long 52 / short 48 el signo dice Long y `scalp_bias_label` dice «No Trade», porque el
    edge (4) no llega a 12. Esa franja es el defecto entero.
    """
    summary = {
        "long_score": 52.0,
        "short_score": 48.0,
        "book_status": "ok",
        "evidence_coverage_pct": 90.0,
    }
    state, _confianza = scalp_bias_label(summary["long_score"], summary["short_score"])
    assert state == "No Trade"
    read = build_operator_read({**summary, "state": state}, {"quality_score": 100})
    # El balance de evidencia SIGUE diciendo Long, y no se toca: es lo que se sirve rotulado.
    assert read["bias"] == "Long"
    assert read["state"] == "No Trade"
    # Y la palabra ya NO sale de ahi.
    assert palabra_de_la_decision(read["state"])[0] == MESA_PALABRA_SIN_LADO


def test_los_umbrales_que_el_signo_ignoraba_siguen_siendo_los_del_estado():
    # 58 es el suelo de un lado con edge suficiente; por debajo, «No Trade» aunque el signo mande.
    assert scalp_bias_label(57.9, 40.0)[0] == "No Trade"
    assert scalp_bias_label(58.0, 40.0)[0] == "Long Pullback"
    assert scalp_bias_label(70.0, 40.0)[0] == "Long Momentum"
    for a, b in [(57.9, 40.0), (52.0, 48.0), (11.0, 10.0)]:
        assert palabra_de_la_decision(scalp_bias_label(a, b)[0])[0] not in CON_LADO


def test_las_cuatro_palabras_son_las_cuatro_y_ninguna_mas():
    vistas = {
        palabra_de_la_decision(s)[0]
        for s in sorted(_LONG_STATES | _SHORT_STATES | _NEUTRAL_STATES)
        + ["Sin datos suficientes", "Long Breakout", "", None]
    }
    assert vistas == {
        MESA_PALABRA_LONG,
        MESA_PALABRA_SHORT,
        MESA_PALABRA_SIN_LADO,
        MESA_PALABRA_NO_EVALUABLE,
    }


def test_la_palabra_de_no_operar_no_se_lee_como_un_lado():
    # NO OPERAR contesta a «que hacer»; NEUTRAL -lo que decia la v1- es una lectura de mercado.
    assert MESA_PALABRA_SIN_LADO == "NO OPERAR"
    for palabra in (MESA_PALABRA_SIN_LADO, MESA_PALABRA_NO_EVALUABLE):
        assert lado(palabra) is None
