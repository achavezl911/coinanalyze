"""Zona R1 (Z-01 CRITICO, F11a S8): el setup juzga la zona de SU episodio, no la siguiente.

Todo pasa por el productor REAL (`price_barrier_read`) y el contexto REAL (`build_setup_context`):
nada de barreras a mano, que es como Z-01 se escondio (dz4 N1). Las escenas son las del doble
de fable-dz4 (`scripts/fable_dz4_setups.py`), ya con el codigo en app/setups.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app import setups as S
from app.interpretation import price_barrier_read
from app.scalp_logic import _atr, _swings

AHORA = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
FIN = int(AHORA.timestamp()) - 900
N = 32  # EPISODIO_MAX_VELAS, escrito aqui para que el control corra tambien contra main


def _diarias() -> list[dict]:
    puntos = [100, 110, 104, 120, 110, 120, 100, 110, 100, 120, 110, 116]
    cierres = [float(puntos[0])]
    for a, b in zip(puntos, puntos[1:], strict=False):
        pasos = max(2, round(abs(b - a) / 2.5))
        cierres += [a + (b - a) * (i + 1) / pasos for i in range(pasos)]
    return [{"session_date": f"d{i:03d}", "price_high": c + 0.5, "price_low": c - 0.5,
             "price_close": c, "volume_usd": 1e9, "cvd_spot_usd": None} for i, c in enumerate(cierres)]


DIARIAS = _diarias()


def barreras(precio: float) -> dict:
    return price_barrier_read(DIARIAS, [], precio, live={"volume_multiple_15m": 2.0})


def paquete(cierres: list[float], mecha: float = 0.0004) -> dict:
    n = len(cierres)
    bars = [{"ts": FIN - (n - 1 - i) * 900, "open": None, "high": c * (1 + mecha),
             "low": c * (1 - mecha), "close": c} for i, c in enumerate(cierres)]
    sh, sl = _swings([x["high"] for x in bars], [x["low"] for x in bars], [x["ts"] for x in bars], k=2)
    return {"timeframe": "15m", "bar_seconds": 900, "source": "doble", "as_of": AHORA.isoformat(),
            "bars": bars, "pivots": {"highs": sh, "lows": sl}, "atr": _atr(bars), "sample_count": n}


def flujo(signo: int) -> dict:
    return {"spot_delta_3m": 1.0 * signo, "fut_delta_3m": 1.0 * signo, "oi_chg_15m_pct": 1.5,
            "price_move_3m_pct": 0.01 * signo, "price_move_15m_pct": 0.01 * signo,
            "imbalance_l5": 0.5 + 0.1 * signo}


def lee(setup: str, direccion: str, scalp: dict, b: dict, pq: dict) -> tuple[dict, dict]:
    ctx = S.build_setup_context(scalp, {"layers": {}}, None, b, {}, direction=direccion,
                                setup=setup, observ_bundle=pq)
    return ctx, S.evaluate_setup(setup, direccion, ctx)


def req(ev: dict, nombre: str) -> str:
    return next(r["estado"] for r in ev["requisitos"] if r["requisito"] == nombre)


RESISTENCIA = barreras(106.0)["nearest_resistance"]


def test_ruptura_real_confirma_sobre_la_zona_cruzada():
    p = RESISTENCIA["high"] * 1.01
    pq = paquete([RESISTENCIA["low"] * 0.99] * 394 + [p] * 6)
    ctx, ev = lee("ruptura", "long", flujo(1), barreras(p), pq)
    assert ev["state"] == "CONFIRMADO", ev["requisitos"]
    # La ultima zona cuya frontera cruzo el cierre, no la siguiente por encima del precio.
    assert (round(ctx["zone_low"], 2), round(ctx["zone_high"], 2), round(p, 2)) == (110.35, 110.65, 110.75)
    assert ev["episodio"] == {
        "zona": {"low": ctx["zone_low"], "high": ctx["zone_high"], "center": ctx["zone_center"]},
        "vela_apertura_ts": pq["bars"][394]["ts"], "max_velas": 32, "calibrado": False,
    }


def test_ruptura_sin_intento_no_es_fallida():
    """F11a S8: un cierre viejo mas alla de la frontera y el precio dentro NO es una ruptura fallida."""
    pq = paquete([RESISTENCIA["high"] * 1.01] * 40 + [106.0] * 360)
    ctx, ev = lee("ruptura", "long", {}, barreras(106.0), pq)
    assert ev["state"] != "FALLIDO"
    assert ctx["returned_inside"] is None and ev["episodio"] is None


def test_ruptura_fallida_de_verdad_sigue_fallida():
    pq = paquete([106.0] * 370 + [RESISTENCIA["high"] * 1.01] * 10 + [106.0] * 20)
    ctx, ev = lee("ruptura", "long", {}, barreras(106.0), pq)
    assert ev["state"] == "FALLIDO" and ctx["returned_inside"] is True
    assert ev["episodio"]["vela_apertura_ts"] == pq["bars"][370]["ts"]


def test_rechazo_con_soporte_lejano_no_confirma():
    """Z-01: el precio en una zona y el rechazo juzgado contra el soporte de debajo."""
    mejor = None
    for paso in range(641):
        p = 94.0 + paso * 0.05
        b = barreras(p)
        if b.get("active_zone") and b.get("nearest_support"):
            lejos = p / b["nearest_support"]["high"] - 1
            if mejor is None or lejos > mejor[0]:
                mejor = (lejos, p, b)
    lejos, p, b = mejor
    assert round(lejos * 100, 1) == 9.0
    sop = b["nearest_support"]
    ctx, ev = lee("rechazo", "long", {"price_move_3m_pct": 0.01, "fut_delta_3m": 1.0}, b,
                  paquete([sop["center"]] * 60 + [p] * 340))
    assert ev["state"] == "CANDIDATO"
    assert ctx["zone_low"] <= p <= ctx["zone_high"]  # la zona del precio, la del episodio
    assert ctx["touched_level"] is True and ctx["returned_inside"] is False


@pytest.mark.parametrize(("velas", "estado"), [(10, "CONFIRMADO"), (340, "CANDIDATO")])
def test_rechazo_con_toque_reciente_o_viejo(velas, estado):
    sop = barreras(106.0)["nearest_support"]
    q = sop["high"] * 1.004
    bq = barreras(q)
    assert not bq.get("active_zone") and bq["nearest_support"]["center"] == sop["center"]
    pq = paquete([q * 1.02] * (390 - velas) + [sop["center"]] * 10 + [q] * velas)
    ctx, ev = lee("rechazo", "long", {"price_move_3m_pct": 0.01, "fut_delta_3m": 1.0}, bq, pq)
    assert ev["state"] == estado
    assert req(ev, "contacto con el nivel") == ("cumple" if velas < N else "pendiente")


def test_barrido_ningun_veredicto_sin_episodio():
    """129 precios x 2 setups x 2 direcciones x 2 formas. La invariante es la sonda de 140."""
    n = N
    confirmados = {"ruptura": 0, "rechazo": 0}
    huerfanos = []
    for paso in range(129):
        p = 94.0 + paso * 0.25
        b = barreras(p)
        for direccion, signo in (("long", 1), ("short", -1)):
            formas = (paquete([p * (1 - 0.03 * signo)] * 380 + [p] * 20),  # llega desde lejos
                      paquete([p * (1 + 0.03 * signo)] * 40 + [p] * 360))  # S8: un cierre viejo
            for pq in formas:
                recientes = pq["bars"][-n - 1:]
                for setup in ("ruptura", "rechazo"):
                    ctx, ev = lee(setup, direccion, flujo(signo), b, pq)
                    if setup == "rechazo" and ev["state"] == "CONFIRMADO":
                        confirmados[setup] += 1
                        if not any(x["low"] <= ctx["zone_high"] and x["high"] >= ctx["zone_low"]
                                   for x in recientes):
                            huerfanos.append((p, direccion, setup, "CONFIRMADO sin contacto"))
                    if setup == "ruptura" and ev["state"] in ("CONFIRMADO", "FALLIDO"):
                        lado = [(x["close"] - ctx["breakout_boundary"]) * signo for x in recientes]
                        cruce = any(a <= 0 < c for a, c in zip(lado, lado[1:], strict=False))
                        confirmados[setup] += ev["state"] == "CONFIRMADO"
                        if not cruce:
                            huerfanos.append((p, direccion, setup, f"{ev['state']} sin cruce"))
    assert huerfanos == []
    assert confirmados["ruptura"] > 0 and confirmados["rechazo"] > 0, confirmados
