"""La palabra de DECIDE dice la DECISION del sistema, no el signo de una resta.

El defecto que estos tests cobran, medido en PRODUCCION (release a15a89d) el 2026-09-30 a las
05:24:30Z sobre BTC: `decide.bias.value` = 'SHORT', `decide.state.value` = 'No Trade',
`edge` 5.0 y `no_trade_reasons` ['score_edge_low']. La palabra salia de
`operator_read.bias` -el SIGNO de long_score - short_score, sin umbral- y el estado sale de
`scalp_bias_label`, que exige edge >= 12 y que el score ganador llegue a 58.

Y LA REGLA SON DOS MITADES, no una:
  1 · el umbral del handoff sobre `data_confidence` (por debajo -> NO EVALUABLE, con su motivo)
  2 · `classify_signal_observation` ENTERA, que cierra la puerta ANTES de mirar el estado si el
      libro no esta ok o la cobertura no llega a 50
"""
import pytest

from app.ai_context import (
    MESA_NO_EVALUABLE_UNDER,
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

# LA LECTURA BUENA: lo que hay que darle a la regla para que llegue a mirar el estado. Si un test
# usa estos valores y aun asi no llega, el fallo es de la regla y no del banco.
BUENA = {"book_status": "ok", "coverage": 90.0, "quality_score": 100.0}


def palabra(**cambios) -> str:
    return palabra_de_la_decision(**{**BUENA, **cambios})[0]


def motivo(**cambios) -> str | None:
    return palabra_de_la_decision(**{**BUENA, **cambios})[2]


def clave(**cambios) -> str:
    return palabra_de_la_decision(**{**BUENA, **cambios})[1]


# --- 2 · la direccion del registro, estado a estado --------------------------------------


@pytest.mark.parametrize("state", sorted(_LONG_STATES))
def test_los_estados_largos_dan_long(state):
    assert palabra(state=state) == MESA_PALABRA_LONG


@pytest.mark.parametrize("state", sorted(_SHORT_STATES))
def test_los_estados_cortos_dan_short(state):
    assert palabra(state=state) == MESA_PALABRA_SHORT


@pytest.mark.parametrize("state", sorted(_NEUTRAL_STATES))
def test_el_estado_neutral_no_es_un_lado(state):
    assert palabra(state=state) == MESA_PALABRA_SIN_LADO
    assert palabra(state=state) not in CON_LADO
    # SIN MOTIVO A PROPOSITO: la linea de debajo de la palabra publica `no_trade_reasons`, que
    # dice POR QUE no se opera. Un motivo aqui la taparia para repetir lo que la palabra ya dice.
    assert motivo(state=state) is None


def test_un_estado_que_no_existe_no_se_vuelve_un_lado():
    # «Long Breakout» LLEVA la palabra Long dentro y no es ninguno de los estados del registro.
    # Un mapa por subcadena lo convertiria en LONG en silencio; este no.
    assert palabra(state="Long Breakout") == MESA_PALABRA_NO_EVALUABLE
    assert "Long Breakout" in (motivo(state="Long Breakout") or "")


@pytest.mark.parametrize("state", ["Sin datos suficientes", "", None, "  "])
def test_lo_que_el_sistema_no_pudo_evaluar_se_dice(state):
    assert palabra(state=state) == MESA_PALABRA_NO_EVALUABLE
    assert motivo(state=state)


def test_la_palabra_coincide_con_la_direccion_DEL_REGISTRO_estado_a_estado():
    """La promesa del encargo, contrastada contra `classify_signal_observation`."""
    traduccion = {"long": MESA_PALABRA_LONG, "short": MESA_PALABRA_SHORT,
                  "neutral": MESA_PALABRA_SIN_LADO, "unavailable": MESA_PALABRA_NO_EVALUABLE}
    for state in sorted(_LONG_STATES | _SHORT_STATES | _NEUTRAL_STATES):
        _, direccion, _ = classify_signal_observation(
            {"state": state, "book_status": "ok", "evidence_coverage_pct": 90.0}
        )
        assert palabra(state=state) == traduccion[direccion], f"{state}: contra {direccion}"


# --- 1 · el umbral del handoff ------------------------------------------------------------


def test_por_debajo_del_umbral_la_palabra_es_no_evaluable_aunque_el_estado_tenga_lado():
    """R1 del remate: decir «no se» con su regla NO es callar un lado.

    La decision del sistema sigue a la vista en ESTADO, y la tarjeta se raya. La calidad se hunde
    justo en los transitorios -reinicios, feeds reconectando- que es cuando menos conviene una
    palabra de 30 px afirmando un lado.
    """
    assert palabra(state="Long Momentum", quality_score=10.0) == MESA_PALABRA_NO_EVALUABLE
    assert clave(state="Long Momentum", quality_score=10.0) == "data_confidence.quality_score"
    assert "10" in (motivo(state="Long Momentum", quality_score=10.0) or "")


@pytest.mark.parametrize("q", [0.0, 10.0, 69.0, 69.9])
def test_el_umbral_tapa_cualquier_lado(q):
    for state in sorted(_LONG_STATES | _SHORT_STATES | _NEUTRAL_STATES):
        assert palabra(state=state, quality_score=q) == MESA_PALABRA_NO_EVALUABLE


def test_la_frontera_del_umbral_es_MAYOR_O_IGUAL():
    # 70 exacto SI es evaluable. Un `>` en vez de un `>=` se comeria justo este caso.
    assert MESA_NO_EVALUABLE_UNDER == 70.0
    assert palabra(state="Long Momentum", quality_score=70.0) == MESA_PALABRA_LONG
    assert palabra(state="Long Momentum", quality_score=69.9) == MESA_PALABRA_NO_EVALUABLE


def test_sin_calidad_no_se_inventa_una():
    assert palabra(state="Long Momentum", quality_score=None) == MESA_PALABRA_NO_EVALUABLE
    assert "no llega" in (motivo(state="Long Momentum", quality_score=None) or "")


# --- 2b · las puertas que el registro cierra ANTES de mirar el estado ---------------------


@pytest.mark.parametrize("libro", ["stale", "missing", "", None, "degraded"])
def test_con_el_libro_no_ok_el_registro_no_evalua(libro):
    """El operador lo midio sobre la entrega de la 132: libro no ok con No Trade daba NO OPERAR.

    El registro da `unavailable` para esa observacion, no `neutral`: no es que el sistema haya
    decidido no operar, es que no se pudo evaluar.
    """
    assert palabra(state="No Trade", book_status=libro) == MESA_PALABRA_NO_EVALUABLE
    assert palabra(state="Long Momentum", book_status=libro) == MESA_PALABRA_NO_EVALUABLE
    assert clave(state="No Trade", book_status=libro) == "signal_ledger.classify_signal_observation"


@pytest.mark.parametrize("cob", [0.0, 40.0, 49.9, None])
def test_con_la_cobertura_corta_el_registro_no_evalua(cob):
    assert palabra(state="Long Momentum", coverage=cob) == MESA_PALABRA_NO_EVALUABLE


def test_la_frontera_de_la_cobertura_es_la_del_registro():
    assert palabra(state="Long Momentum", coverage=50.0) == MESA_PALABRA_LONG
    assert palabra(state="Long Momentum", coverage=49.9) == MESA_PALABRA_NO_EVALUABLE


def test_el_motivo_del_registro_nombra_las_tres_entradas_y_ningun_umbral():
    """R2: la regla se importa, no se copia. Ni este motivo ni este test repiten sus umbrales."""
    m = motivo(state="Long Momentum", book_status="stale", coverage=40.0)
    assert m
    assert "Long Momentum" in m and "stale" in m and "40" in m
    # el motivo NO reescribe las condiciones del registro: no dice «< 50» ni «book != ok»
    assert "<" not in m and "!=" not in m


# --- la regla ENTERA, en el orden que tiene ----------------------------------------------


def test_el_umbral_del_handoff_manda_sobre_la_clasificacion():
    # Con las dos puertas cerradas, el motivo que se publica es el del handoff: es la regla
    # explicita del diseno, y la que el operador quiere leer primero.
    assert clave(state="Long Momentum", quality_score=10.0, book_status="stale") == (
        "data_confidence.quality_score"
    )


def test_ninguna_palabra_con_lado_sale_de_una_observacion_que_el_registro_no_evalua():
    casos = [
        {"state": "No Trade"},
        {"state": "Sin datos suficientes"},
        {"state": "Long Breakout"},
        {"state": None},
        {"state": "Long Momentum", "book_status": "stale"},
        {"state": "Short Momentum", "coverage": 10.0},
        {"state": "Long Pullback", "quality_score": 1.0},
    ]
    for caso in casos:
        assert palabra(**caso) not in CON_LADO, caso


def test_las_cuatro_palabras_son_las_cuatro_y_ninguna_mas():
    vistas = {
        palabra(state=s)
        for s in sorted(_LONG_STATES | _SHORT_STATES | _NEUTRAL_STATES)
        + ["Sin datos suficientes", "Long Breakout", "", None]
    } | {palabra(state="Long Momentum", quality_score=0.0)}
    assert vistas == {
        MESA_PALABRA_LONG,
        MESA_PALABRA_SHORT,
        MESA_PALABRA_SIN_LADO,
        MESA_PALABRA_NO_EVALUABLE,
    }


def test_la_palabra_de_no_operar_no_se_lee_como_un_lado():
    # NO OPERAR contesta a «que hacer»; NEUTRAL -lo que decia la v1- es una lectura de mercado.
    # Y NO OPERAR no es NO EVALUABLE: una es una decision, la otra es la ausencia de una.
    assert MESA_PALABRA_SIN_LADO == "NO OPERAR"
    assert MESA_PALABRA_SIN_LADO != MESA_PALABRA_NO_EVALUABLE
    assert palabra(state="No Trade") == MESA_PALABRA_SIN_LADO
    assert palabra(state="No Trade", book_status="stale") == MESA_PALABRA_NO_EVALUABLE


# --- la franja en la que vivia el defecto -------------------------------------------------


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
    assert palabra(state=read["state"]) == MESA_PALABRA_SIN_LADO


def test_los_umbrales_que_el_signo_ignoraba_siguen_siendo_los_del_estado():
    # 58 es el suelo de un lado con edge suficiente; por debajo, «No Trade» aunque el signo mande.
    assert scalp_bias_label(57.9, 40.0)[0] == "No Trade"
    assert scalp_bias_label(58.0, 40.0)[0] == "Long Pullback"
    assert scalp_bias_label(70.0, 40.0)[0] == "Long Momentum"
    for a, b in [(57.9, 40.0), (52.0, 48.0), (11.0, 10.0)]:
        assert palabra(state=scalp_bias_label(a, b)[0]) not in CON_LADO
