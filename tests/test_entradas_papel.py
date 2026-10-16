"""LA CUENTA DE PAPEL (campana 139, C3), sin base: el bloque papel de v1 y v2 del reglamento del arbol, aplicado a
resultados del resolutor sobre planes de respuesta conocida (los de tests/test_entradas_resolutor.py)."""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest
from test_entradas_resolutor import T, espejo_fila, espejo_velas, fila, tarde, velas

from app.entradas import papel as PAPEL
from app.entradas import reglamento as R
from app.entradas import resolutor as RES

DOC = R.cargar_valido()
V1, V2 = R.version(DOC, "v1"), R.version(DOC, "v2")
STOP_2030 = {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)}
OBJ_2030 = {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}


def disparado(rid: int, cambios: dict, *, horas: float = 0.0, symbol: str = "SOLUSDT_PERP.A", perfil="intradia",
              funding=None, corto: bool = False):
    """Una fila DISPARADO (registrada `horas` despues del escenario base) y su resultado."""
    f = fila(perfil)
    vs = velas(f, cambios)
    if corto:  # el corto del mismo mercado reflejado en torno a 100, con precios positivos como en produccion
        f, vs = espejo_fila(f), espejo_velas(vs)
        p = f["foto"]["plan"]
        p["stop"]["precio"] += 200
        p["objetivos"] = [x + 200 for x in p["objetivos"]]
        p["invalidacion"]["nivel"] += 200
        p["entrada"]["referencia"]["precio"] += 200
        vs = [{k: (v[k] + 200 if k != "ts" else v[k]) for k in v} for v in vs]
    d = timedelta(hours=horas)
    f.update(registro_id=rid, symbol=symbol, vela_cierre=T + d, registered_at=f["registered_at"] + d,
             caduca_en=f["caduca_en"] + d)
    p = f["foto"]["plan"]
    p["caducidad"]["caduca_en"] = RES.iso(RES._t(p["caducidad"]["caduca_en"]) + d)
    vs = [{**v, "ts": v["ts"] + d} for v in vs]
    return f, RES.resolver(f, vs, tarde(f) + d, funding)


def test_v2_toma_por_orden_de_registro_y_redondea_hacia_abajo_al_paso():
    a, ra = disparado(1, STOP_2030)
    b, rb = disparado(2, OBJ_2030, horas=6)
    c = PAPEL.cuenta(V2, [a, b], {1: ra, 2: rb})
    assert c["dimensiona"] is True and c["no_dimensiona"] is None and c["saltados"] == []
    assert [op["registro_id"] for op in c["operaciones"]] == [1, 2] and c["n"] == 2
    # 200 USD / (100.01 * (1 + 5.5 bps)) = 1.9987 SOL: hacia abajo al paso de 0.1 -> 1.9
    assert c["operaciones"][0]["lote"] == 1.9
    pnl1 = 1.9 * (ra["precio"] - 100.01) - 1.9 * 100.01 * 5.5e-4 - 1.9 * ra["precio"] * 5.5e-4
    assert c["operaciones"][0]["pnl_usd"] == round(pnl1, 2)
    # la segunda opera con el saldo que dejo la primera
    lote2 = int((200 + pnl1) / (100.01 * (1 + 5.5e-4)) / 0.1) * 0.1
    assert c["operaciones"][1]["lote"] == pytest.approx(lote2)
    assert [op["r_neto"] for op in c["operaciones"]] == [ra["pnl"]["r_neto"], rb["pnl"]["r_neto"]]
    assert c["saldo_usd"] == round(200 + pnl1 + c["operaciones"][1]["pnl_usd"], 2)
    assert c["firmeza"] == RES.FINAL


def test_un_disparado_que_no_cabe_se_salta_con_su_motivo():
    a, ra = disparado(1, STOP_2030)
    b, rb = disparado(2, OBJ_2030, horas=0.25)     # entra a las 20:18, con la primera abierta hasta las 20:30
    c = PAPEL.cuenta(V2, [a, b], {1: ra, 2: rb})
    assert [op["registro_id"] for op in c["operaciones"]] == [1]
    assert len(c["saltados"]) == 1 and c["saltados"][0]["registro_id"] == 2
    assert c["saltados"][0]["motivo"].startswith("no cabe:") and "operacion 1" in c["saltados"][0]["motivo"]
    # en otra version, que no se cruza con esta, la segunda si cabe: una cuenta por version
    assert PAPEL.cuenta(V2, [b], {2: rb})["n"] == 1


def test_funding_solo_cuenta_el_cobro_adverso():
    cobros = {datetime(2026, 10, 13, 0, tzinfo=UTC): {"fr_high": 0.01, "fr_low": 0.004},
              datetime(2026, 10, 13, 8, tzinfo=UTC): {"fr_high": -0.002, "fr_low": -0.01}}
    stop_09 = {"2026-10-13T09:00": (100.0, 100.0, 98.9, 99.0)}
    a, ra = disparado(1, stop_09, perfil="swing", funding=cobros)
    c = PAPEL.cuenta(V2, [a], {1: ra})
    op = c["operaciones"][0]
    assert op["funding_usd"] == round(op["lote"] * op["precio_entrada"] * 0.01 / 100, 2)
    assert c["funding_usd"] == op["funding_usd"]
    # el corto del mismo mercado paga el segundo cobro y no el primero
    b, rb = disparado(1, stop_09, perfil="swing", funding=cobros, corto=True)
    op_c = PAPEL.cuenta(V2, [b], {1: rb})["operaciones"][0]
    assert op_c["funding_usd"] == round(op_c["lote"] * op_c["precio_entrada"] * 0.01 / 100, 2)
    # y sin ningun cobro adverso, no se cobra nada: el favorable nunca se abona
    favorable = {k: {"fr_high": -0.002, "fr_low": -0.01} for k in cobros}
    a2, ra2 = disparado(1, stop_09, perfil="swing", funding=favorable)
    assert PAPEL.cuenta(V2, [a2], {1: ra2})["operaciones"][0]["funding_usd"] == 0.0


def test_v1_no_dimensiona_y_lo_dice():
    a, ra = disparado(1, STOP_2030)
    c = PAPEL.cuenta(V1, [{**a, "version": "v1"}], {1: ra})
    assert c["dimensiona"] is False and "el paso no se inventa" in c["no_dimensiona"]
    assert c["n"] == 0 and c["saldo_usd"] == 200.0 and c["operaciones"] == []
    assert c["saltados"][0]["motivo"].startswith("no dimensiona")


def test_sin_entrada_no_abre_y_una_posicion_abierta_es_provisional():
    a, ra = disparado(1, {"2026-10-12T20:01": (100.0, 100.0, 98.9, 99.5)})
    c = PAPEL.cuenta(V2, [a], {1: ra})
    assert c["n"] == 0 and c["saltados"] == [] and c["sin_posicion"][0]["motivo"].startswith("sin entrada")
    f = fila("intradia")
    f.update(registro_id=3, symbol="SOLUSDT_PERP.A")
    vivo = RES.resolver(f, [v for v in velas(f) if v["ts"] < T + timedelta(minutes=30)], T + timedelta(minutes=30))
    c = PAPEL.cuenta(V2, [f], {3: vivo})
    assert c["abiertas"] == 1 and c["n"] == 0 and c["firmeza"] == RES.PROVISIONAL
    assert c["saldo_usd"] == 200.0


def test_un_disparado_sin_su_vela_de_entrada_esta_pendiente_y_la_cuenta_no_es_final():
    """Saltado es SOLO el que no cabe o no dimensiona. Uno sin su vela de entrada esta PENDIENTE, con su motivo, y la
    cuenta es PROVISIONAL. Detras de el esperan los posteriores que necesitan capital; los que no lo necesitan (no
    dimensiona, sin posicion) se apuntan ya."""
    a, ra = disparado(1, STOP_2030)
    b, rb = disparado(2, OBJ_2030, horas=6)
    c_, rc_ = disparado(3, {"2026-10-12T20:01": (100.0, 100.0, 98.9, 99.5)}, horas=7)     # sin entrada
    d, rd = disparado(4, OBJ_2030, horas=8, symbol="XRPUSDT_PERP.A")                      # sin paso: no dimensiona
    sin_vela = [v for v in velas(a, STOP_2030) if v["ts"] != RES.entrada_t(a)]
    ra_p = RES.resolver(a, sin_vela, T + timedelta(minutes=5))
    assert (ra_p["estado"], ra_p["entrada"]) == (RES.ABIERTO, None)
    filas = [a, b, c_, d]
    c = PAPEL.cuenta(V2, filas, {1: ra_p, 2: rb, 3: rc_, 4: rd})
    assert [s["registro_id"] for s in c["saltados"]] == [4] and c["saltados"][0]["motivo"].startswith("no dimensiona")
    assert (c["n"], c["operaciones"], c["saldo_usd"], c["firmeza"]) == (0, [], 200.0, RES.PROVISIONAL)
    assert [p["registro_id"] for p in c["pendientes"]] == [1, 2]
    assert c["pendientes"][0]["motivo"].endswith("la vela de 1 min de las 20:03Z no esta en la base")
    assert c["pendientes"][1]["motivo"].startswith("detras del registro 1, que esta pendiente")
    assert [s["registro_id"] for s in c["sin_posicion"]] == [3]
    # llega su vela: las dos operan, como sin los otros dos, y la cuenta es final
    c2 = PAPEL.cuenta(V2, filas, {1: ra, 2: rb, 3: rc_, 4: rd})
    assert c2["pendientes"] == [] and c2["firmeza"] == RES.FINAL
    assert c2["operaciones"] == PAPEL.cuenta(V2, [a, b], {1: ra, 2: rb})["operaciones"]
    # tres a la vez sin su vela de entrada (lo que midio el operador en d9f4520): tres pendientes, y no es final
    tres = [{**a, "registro_id": 10 + i, "symbol": s} for i, s in enumerate(("BTCUSDT_PERP.A", "ETHUSDT_PERP.A",
                                                                           "SOLUSDT_PERP.A"))]
    c3 = PAPEL.cuenta(V2, tres, {10 + i: ra_p for i in range(3)})
    assert (len(c3["pendientes"]), c3["saltados"], c3["n"], c3["saldo_usd"], c3["firmeza"]) == (
        3, [], 0, 200.0, RES.PROVISIONAL)
    # en un hueco que dura: pendiente hasta la gracia, y a la gracia no abre posicion
    espera = RES.resolver(a, sin_vela, RES.ventana(a)[1] + timedelta(days=1))
    c4 = PAPEL.cuenta(V2, [a], {1: espera})
    assert c4["pendientes"][0]["motivo"].endswith("sera NO EVALUABLE") and c4["firmeza"] == RES.PROVISIONAL
    c5 = PAPEL.cuenta(V2, [a], {1: RES.resolver(a, sin_vela, tarde(a))})
    assert c5["sin_posicion"][0]["motivo"].startswith("no evaluable") and c5["firmeza"] == RES.FINAL


def test_la_cuenta_no_cambia_con_el_orden_en_que_llegan_las_filas():
    a, ra = disparado(1, STOP_2030)
    b, rb = disparado(2, OBJ_2030, horas=6)
    uno = PAPEL.cuenta(V2, [a, b], {1: ra, 2: rb})
    assert PAPEL.cuenta(V2, [b, a], {1: ra, 2: rb}) == uno
    assert PAPEL.cuenta(copy.deepcopy(V2), [a, b], {1: ra, 2: rb}) == uno
