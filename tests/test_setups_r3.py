"""Setups R3 (V-05, Fable V1 N1): la ruptura juzga la zona del cruce MAS RECIENTE del cierre.

`episodio` buscaba en (detras, activa, delante) y se quedaba con la PRIMERA zona con cruce:
en 140 (11-25 03:04Z, BTC swing long) juzgaba `nearest_support` con un cruce del 11-21 cuando
el ultimo cruce era el de la resistencia. El doble es el de `fable_v1_casos.py` N1. Desempate:
si la misma vela cruza dos fronteras, gana el orden (detras, activa, delante), como en main.
"""

from __future__ import annotations

from app import setups as S

SOPORTE = {"low": 90.0, "high": 100.0, "center": 95.0}
RESISTENCIA = {"low": 110.0, "high": 120.0, "center": 115.0}
B = {"active_zone": None, "nearest_support": SOPORTE, "nearest_resistance": RESISTENCIA}
FIN = 1_795_000_000


def velas(cierres: list[float]) -> list[dict]:
    n = len(cierres)
    return [{"ts": FIN - (n - 1 - i) * 900, "open": c, "high": c + 1, "low": c - 1, "close": c}
            for i, c in enumerate(cierres)]


def test_n1_ruptura_long_juzga_el_cruce_mas_reciente():
    """Cruza el techo del soporte en la vela 2 y el de la resistencia en la 4 (el ULTIMO)."""
    zona, i0 = S.episodio("ruptura", 1, B, velas([95, 96, 105, 106, 125, 108, 107]))
    assert (zona, i0) == (RESISTENCIA, 4)


def test_n1_espejo_ruptura_short():
    """Short: cruza el suelo de la resistencia (vela 2) y despues el del soporte (vela 4)."""
    zona, i0 = S.episodio("ruptura", -1, B, velas([115, 114, 105, 104, 85, 92, 93]))
    assert (zona, i0) == (SOPORTE, 4)


def test_n1_la_activa_cruzada_despues_gana_a_la_de_detras():
    activa = {"low": 102.0, "high": 104.0, "center": 103.0}
    b = {**B, "active_zone": activa}
    zona, i0 = S.episodio("ruptura", 1, b, velas([95, 96, 101, 101, 105, 105]))
    assert (zona, i0) == (activa, 4)


def test_n1_veredicto_por_el_contexto_real():
    """Por `build_setup_context`: tras el ultimo cruce (resistencia) el cierre volvio dentro."""
    bars = velas([95] * 30 + [96, 105, 106, 125, 108, 107])
    b = {**B, "current_price": 107.0}
    ctx = S.build_setup_context({}, {"layers": {}}, None, b, {}, direction="long", setup="ruptura",
                                observ_bundle={"timeframe": "15m", "bar_seconds": 900,
                                               "source": "doble", "bars": bars})
    assert (ctx["zone_low"], ctx["zone_high"]) == (110.0, 120.0)
    assert ctx["returned_inside"] is True
    assert S.evaluate_setup("ruptura", "long", ctx)["state"] == "FALLIDO"


def test_control_una_sola_zona_con_cruce_igual_que_main():
    zona, i0 = S.episodio("ruptura", 1, B, velas([95, 96, 105, 106, 107, 108]))
    assert (zona, i0) == (SOPORTE, 2)
    zona, i0 = S.episodio("ruptura", 1, B, velas([105, 106, 125, 108]))
    assert (zona, i0) == (RESISTENCIA, 2)


def test_control_sin_cruce_cae_en_activa_o_delante():
    zona, i0 = S.episodio("ruptura", 1, B, velas([95, 96, 97]))
    assert (zona, i0) == (RESISTENCIA, None)


def test_desempate_misma_vela_gana_el_orden_detras_activa_delante():
    zona, i0 = S.episodio("ruptura", 1, B, velas([95, 96, 125, 126]))
    assert (zona, i0) == (SOPORTE, 2)
