"""El plan tiene que ser posible EN EL LADO QUE DECLARA, y la ruta lo tiene que DECIR.

EL HECHO QUE MOTIVA ESTE FICHERO, medido contra produccion el 2026-09-06 a las 08:11Z:
un largo con entrada 79814.3, stop 80612.4 (ARRIBA) y objetivo 78218.0 (ABAJO) devolvia
`risk_bps=99.99`, `target_bps=200.0` y `cost_to_risk_band="aceptable"`, exactamente los
mismos numeros que el mismo plan bien puesto, y sin un solo aviso.

DECISION DE PRODUCTO DEL OPERADOR, 2026-09-06: **avisa, no rechaces**. Un 400 rompe a
quien ya llama la ruta. Por eso la mitad mas importante de este fichero no es la que
comprueba que el aviso sale, sino la que comprueba **que no ha cambiado nada mas**.
"""

from __future__ import annotations

import pytest

from app.scalp_logic import coherencia_del_plan, execution_assessment

ENTRADA = 100_000.0


def evalua(**kw):
    base = dict(
        profile="intradia",
        spread_bps=1.5,
        fee_bps_per_side=5.0,
        size_usd=10_000.0,
        entry=ENTRADA,
    )
    base.update(kw)
    return execution_assessment(**base)


# --------------------------------------------------------------------------
# NEGATIVO · los planes posibles no pueden enrojecer
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "side, stop, target",
    [
        ("long", 99_000.0, 102_000.0),
        ("short", 102_000.0, 99_000.0),
    ],
)
def test_plan_posible_es_coherente(side, stop, target):
    r = evalua(side=side, stop=stop, target=target)
    assert r["plan_coherence"] == "COHERENTE"
    assert r["plan_incoherencias"] == []
    assert r["plan_warning"] is None


# --------------------------------------------------------------------------
# POSITIVO · EL CASO QUE MOTIVO EL CAMBIO
# --------------------------------------------------------------------------

def test_largo_con_el_plan_del_reves_se_declara_incoherente():
    """Es el plan exacto que produccion aceptaba en silencio, a escala redonda."""
    r = evalua(side="long", stop=102_000.0, target=99_000.0)
    assert r["plan_coherence"] == "INCOHERENTE"
    assert set(r["plan_incoherencias"]) == {
        "stop_no_esta_por_debajo_de_la_entrada",
        "objetivo_no_esta_por_encima_de_la_entrada",
    }
    assert "largo" in r["plan_warning"]


def test_corto_con_el_plan_del_reves_se_declara_incoherente():
    r = evalua(side="short", stop=99_000.0, target=102_000.0)
    assert r["plan_coherence"] == "INCOHERENTE"
    assert set(r["plan_incoherencias"]) == {
        "stop_no_esta_por_encima_de_la_entrada",
        "objetivo_no_esta_por_debajo_de_la_entrada",
    }


def test_solo_una_pata_mal_solo_nombra_esa_pata():
    """Si el objetivo esta bien y el stop no, no se acusa al objetivo."""
    r = evalua(side="long", stop=102_000.0, target=102_000.0)
    assert r["plan_coherence"] == "INCOHERENTE"
    assert r["plan_incoherencias"] == ["stop_no_esta_por_debajo_de_la_entrada"]


def test_stop_pegado_a_la_entrada_no_pasa_por_bueno():
    """La desigualdad es ESTRICTA: un stop en la entrada no es riesgo cero, es un plan
    sin riesgo declarable."""
    r = evalua(side="long", stop=ENTRADA, target=102_000.0)
    assert r["plan_coherence"] == "INCOHERENTE"


# --------------------------------------------------------------------------
# ANTI-FANTASMA · lo que no se puede comprobar NO es "coherente"
# --------------------------------------------------------------------------

def test_sin_lado_no_hay_nada_que_validar_y_se_dice():
    r = evalua(side=None, stop=102_000.0, target=99_000.0)
    assert r["plan_coherence"] == "SIN LADO"
    assert r["plan_incoherencias"] == []


def test_lado_desconocido_tampoco_se_da_por_bueno():
    assert coherencia_del_plan("neutral", ENTRADA, 99_000.0, 102_000.0)[0] == "SIN LADO"


def test_sin_entrada_no_se_puede_comparar_nada():
    r = evalua(side="long", entry=None, stop=99_000.0, target=102_000.0)
    assert r["plan_coherence"] == "SIN DATOS"


def test_sin_stop_ni_objetivo_no_se_puede_comparar_nada():
    r = evalua(side="long", stop=None, target=None)
    assert r["plan_coherence"] == "SIN DATOS"


def test_con_solo_el_objetivo_si_se_puede_juzgar_esa_mitad():
    """SIN DATOS es para cuando no hay NINGUN extremo, no para cuando falta uno: si
    faltara el matiz, media validacion se perderia en silencio."""
    assert coherencia_del_plan("long", ENTRADA, None, 99_000.0)[0] == "INCOHERENTE"
    assert coherencia_del_plan("long", ENTRADA, None, 102_000.0)[0] == "COHERENTE"


# --------------------------------------------------------------------------
# LA MITAD QUE MAS IMPORTA · AVISA, NO ROMPE
# --------------------------------------------------------------------------

CAMPOS_QUE_YA_SE_CONSUMIAN = (
    "profile", "profile_label", "horizon", "status", "verdict", "total_cost_bps",
    "cost_components_bps", "cost_components_missing", "target_bps", "risk_bps",
    "cost_to_target", "cost_to_risk", "cost_to_target_band", "cost_to_risk_band",
    "missing_inputs", "inputs", "spread_warning", "spread_warn_bps", "bands_note",
)


def test_el_plan_incoherente_no_cambia_ni_un_campo_de_los_de_antes():
    """SIN ESTA PRUEBA EL CAMBIO NO SE PUEDE DEFENDER.

    LA PRIMERA VERSION DE ESTA PRUEBA ESTABA MAL Y FALLO, y el fallo fue util. Comparaba
    el largo bueno (stop 99k, objetivo 102k) contra el largo imposible (stop 102k,
    objetivo 99k) y exigia que `verdict` no cambiara. Pero esos dos planes **no tienen las
    mismas distancias en los mismos papeles**: al darles la vuelta, riesgo y objetivo se
    intercambian, cost_to_risk y cost_to_target tambien, y la peor banda pasa de
    "aceptable" a "ajustado". El campo cambiaba por la aritmetica de siempre, no por lo
    que yo acababa de anadir.

    LA COMPARACION CORRECTA fija los numeros y mueve SOLO el lado declarado: los mismos
    stop 102k y objetivo 99k son un CORTO perfectamente posible y un LARGO imposible.
    Distancias identicas, papeles identicos, y la unica diferencia legitima es `side`.
    Si algun campo de los de antes cambiara aqui, el cambio habria roto a alguien.
    """
    corto_ok = evalua(side="short", stop=102_000.0, target=99_000.0)
    largo_mal = evalua(side="long", stop=102_000.0, target=99_000.0)
    assert corto_ok["plan_coherence"] == "COHERENTE"
    assert largo_mal["plan_coherence"] == "INCOHERENTE"
    for campo in CAMPOS_QUE_YA_SE_CONSUMIAN:
        if campo == "inputs":
            continue  # lleva `side`, que es justo lo que se esta moviendo
        assert corto_ok[campo] == largo_mal[campo], f"el campo {campo} cambio, y no debia"
    assert {k: v for k, v in corto_ok["inputs"].items() if k != "side"} == {
        k: v for k, v in largo_mal["inputs"].items() if k != "side"
    }


def test_los_bps_siguen_siendo_distancias_absolutas():
    """El valor exacto, clavado: la decision es AVISAR, no recalcular. Si alguien decide
    algun dia que `risk_bps` lleve signo, esta prueba lo obliga a decirlo en voz alta en
    vez de cambiarlo de paso."""
    r = evalua(side="long", stop=102_000.0, target=99_000.0)
    assert r["risk_bps"] == 200.0
    assert r["target_bps"] == 100.0
    assert r["status"] == "EVALUADO"


def test_los_tres_campos_nuevos_salen_siempre():
    """Un campo que a veces no esta obliga a quien lo lee a adivinar. Los tres salen en
    los cuatro estados."""
    for kw in (
        dict(side="long", stop=99_000.0, target=102_000.0),
        dict(side="long", stop=102_000.0, target=99_000.0),
        dict(side=None, stop=99_000.0, target=102_000.0),
        dict(side="long", stop=None, target=None),
    ):
        r = evalua(**kw)
        assert "plan_coherence" in r
        assert "plan_incoherencias" in r
        assert "plan_warning" in r
        assert r["plan_coherence"] in {"COHERENTE", "INCOHERENTE", "SIN LADO", "SIN DATOS"}
