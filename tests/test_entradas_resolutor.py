"""EL RESOLUTOR (campana 139, C1): cada salida con un plan y unas velas de respuesta conocida, en los dos lados y en
los dos perfiles. El corto es el reflejo del largo: lo comprueba test_el_corto_es_el_reflejo, no se supone.

Sin base: resolver() es pura. El plan de prueba es el de un DISPARADO de v2 con numeros redondos: referencia 100,
stop 99 (100 bps), T1 102 / T2 103 / T3 104, nivel de invalidacion 99.5, base 0.5 bps y spread 1 bps (tolerancia
1.5 bps), comision taker 5.5 y maker 2, banda 1 bps. Registrado 136.8 s tras el cierre de su vela: entra 3 min
despues.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime, timedelta

import pytest

from app import signal_outcomes
from app.entradas import resolutor as RES

T = datetime(2026, 10, 12, 20, 0, tzinfo=UTC)
MIN = timedelta(minutes=1)
PERFILES = {"intradia": (15, 240), "swing": (240, 4320)}


def fila(perfil: str = "intradia", tipo: str = "mercado", precio_limite: float | None = None) -> dict:
    vela_min, caducidad = PERFILES[perfil]
    caduca = T + timedelta(minutes=caducidad)
    entrada_pata = ({"tipo": "mercado", "componentes_bps": {"taker": 5.5, "spread": 1.0, "deslizamiento": 0.0},
                     "total_bps": 6.5, "venue": "bybit"} if tipo == "mercado" else
                    {"tipo": "limite", "componentes_bps": {"maker": 2.0}, "total_bps": 2.0, "venue": "bybit"})
    plan = {
        "entrada": {"tipo": tipo, "precio": precio_limite, "banda_pesimista_bps": 1.0,
                    "referencia": {"precio": 100.0, "ts": "2026-10-12T19:59:59Z"}},
        "stop": {"precio": 99.0},
        "objetivos": [102.0, 103.0, 104.0],
        "invalidacion": {"nivel": 99.5, "hasta": RES.iso(caduca)},
        "caducidad": {"minutos": caducidad, "caduca_en": RES.iso(caduca)},
        "costes": {"entrada": entrada_pata,
                   "objetivo": {"tipo": "limite", "componentes_bps": {"maker": 2.0}, "total_bps": 2.0},
                   "stop": {"tipo": "stop", "componentes_bps": {"taker": 5.5, "spread": 1.0, "deslizamiento": 0.0},
                            "total_bps": 6.5}},
        "distancias_bps": {"stop": 100.0, "t1": 200.0},
        "r": {"neto": (200 - 6.5 - 2.0) / (100 + 6.5 + 6.5)},
    }
    foto = {"plan": plan, "mids": {"base_bps": 0.5}, "libro_bybit": {"spread_bps": 1.0},
            "parametros": {"comun": {"perfiles": {"intradia": {"vela_min": 15}, "swing": {"vela_min": 240}}}}}
    return {"registro_id": 7, "version": "v2", "estado": "DISPARADO", "familia": "F1", "perfil": perfil,
            "lado": "largo", "vela_cierre": T, "registered_at": T + timedelta(seconds=136.8),
            "caduca_en": caduca, "foto": foto}


def velas(f: dict, cambios: dict[str, tuple] | None = None, quita: tuple[str, ...] = ()) -> list[dict]:
    """Planas a 100 desde el cierre de la vela hasta la de caducidad; `cambios` pone (o, h, l, c) a un minuto."""
    caduca = RES.ventana(f)[1]
    m, salida = T, []
    cambios = {datetime.fromisoformat(k).replace(tzinfo=UTC): v for k, v in (cambios or {}).items()}
    quita_ = {datetime.fromisoformat(k).replace(tzinfo=UTC) for k in quita}
    while m <= caduca:
        if m not in quita_:
            o, h, l_, c = cambios.get(m, (100.0, 100.0, 100.0, 100.0))
            salida.append({"ts": m, "open": o, "high": h, "low": l_, "close": c})
        m += MIN
    return salida


def tarde(f: dict) -> datetime:
    """Un instante en que cualquier resultado del plan ya esta asentado (y pasada la gracia)."""
    return RES.ventana(f)[1] + timedelta(days=8)


def resuelve(perfil: str, cambios=None, quita=(), ahora=None, **kw):
    f = fila(perfil, **kw)
    return RES.resolver(f, velas(f, cambios, quita), ahora or tarde(f))


def _aprox(a, b, tol=1e-9):
    return abs(a - b) <= tol


# --------------------------------------------------------------------------- las ocho salidas, en los dos perfiles


@pytest.mark.parametrize("perfil", PERFILES)
def test_objetivo_cruzado_sale_en_t1(perfil):
    r = resuelve(perfil, {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)})
    assert (r["salida"], r["instante"], r["firmeza"]) == (RES.OBJETIVO, "2026-10-12T20:30:00Z", RES.FINAL)
    assert r["precio"] == 102.0
    assert r["entrada"] == {"instante": "2026-10-12T20:03:00Z", "precio": pytest.approx(100.01), "tipo": "mercado",
                            "apertura": 100.0, "banda_bps": 1.0, "comision_bps": 5.5}
    # con la entrada real en la referencia, T1 da (casi) el r.neto de la foto: la unidad R es la del plan
    assert r["pnl"]["r_neto"] == pytest.approx(fila(perfil)["foto"]["plan"]["r"]["neto"], abs=2e-3)
    assert r["pnl"]["comision_bps"] == {"entrada": 5.5, "salida": 2.0}


@pytest.mark.parametrize("perfil", PERFILES)
def test_t1_tocado_sin_cruzar_la_tolerancia_no_cuenta(perfil):
    # 102.01 pasa de T1 (102) pero no de T1 + 1.5 bps (102.0153): no esta cruzado
    r = resuelve(perfil, {"2026-10-12T20:30": (100.0, 102.01, 100.0, 101.0)})
    assert r["salida"] == RES.CADUCADO


@pytest.mark.parametrize("perfil", PERFILES)
def test_stop_tocado_sale_en_el_stop_con_su_banda(perfil):
    r = resuelve(perfil, {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)})
    assert (r["salida"], r["instante"]) == (RES.STOP, "2026-10-12T20:30:00Z")
    assert r["precio"] == pytest.approx(99.0 * (1 - 1e-4))
    assert r["pnl"]["r_neto"] == pytest.approx(-1.0, abs=2e-3)
    # el stop cuenta DENTRO de la tolerancia: 99.01 no llega a 99 y si a 99 + 1.5 bps
    assert resuelve(perfil, {"2026-10-12T20:30": (100.0, 100.0, 99.01, 99.5)})["salida"] == RES.STOP


@pytest.mark.parametrize("perfil", PERFILES)
def test_stop_saltado_con_hueco_sale_a_la_apertura_y_el_stop_es_el_favorable(perfil):
    r = resuelve(perfil, {"2026-10-12T20:30": (98.8, 98.9, 98.7, 98.8)})
    assert r["salida"] == RES.STOP
    assert r["precio"] == pytest.approx(98.8 * (1 - 1e-4))
    assert r["a_favor"]["salida"] == RES.STOP and r["a_favor"]["precio"] == pytest.approx(99.0 * (1 - 1e-4))
    assert r["pnl"]["bps_netos"] < r["a_favor"]["pnl"]["bps_netos"]


@pytest.mark.parametrize("perfil", PERFILES)
def test_stop_y_objetivo_en_la_misma_vela_cuenta_stop(perfil):
    r = resuelve(perfil, {"2026-10-12T20:30": (100.0, 102.5, 98.9, 100.0)})
    assert r["salida"] == RES.MISMA_VELA
    assert r["pnl"]["r_neto"] == pytest.approx(-1.0, abs=2e-3)
    assert r["a_favor"]["salida"] == RES.OBJETIVO and r["a_favor"]["precio"] == 102.0
    # si la APERTURA ya esta mas alla de T1, T1 fue primero: no hay duda que resolver en contra
    assert resuelve(perfil, {"2026-10-12T20:30": (102.5, 102.6, 98.9, 100.0)})["salida"] == RES.OBJETIVO


@pytest.mark.parametrize("perfil", PERFILES)
def test_invalidado_por_el_cierre_de_su_vela_del_perfil(perfil):
    vela_min = PERFILES[perfil][0]
    ultimo = T + timedelta(minutes=vela_min) - MIN          # el minuto que cierra la primera vela del perfil
    salida = T + timedelta(minutes=vela_min)
    r = resuelve(perfil, {ultimo.strftime("%Y-%m-%dT%H:%M"): (99.6, 99.7, 99.2, 99.3),
                          salida.strftime("%Y-%m-%dT%H:%M"): (99.3, 99.4, 99.2, 99.3)})
    assert (r["salida"], r["instante"]) == (RES.INVALIDADO, RES.iso(salida))
    assert r["precio"] == pytest.approx(99.3 * (1 - 1e-4))
    # el mismo cierre UN minuto antes no es de la vela del perfil: no invalida
    antes = (ultimo - MIN).strftime("%Y-%m-%dT%H:%M")
    assert resuelve(perfil, {antes: (99.6, 99.7, 99.2, 99.3)})["salida"] == RES.CADUCADO
    # y un cierre JUSTO en el nivel no esta al otro lado
    assert resuelve(perfil, {ultimo.strftime("%Y-%m-%dT%H:%M"): (99.6, 99.7, 99.2, 99.5)})["salida"] == RES.CADUCADO


@pytest.mark.parametrize("perfil", PERFILES)
def test_caducado_sale_a_la_apertura_de_la_caducidad(perfil):
    f = fila(perfil)
    caduca = RES.ventana(f)[1]
    r = RES.resolver(f, velas(f, {caduca.strftime("%Y-%m-%dT%H:%M"): (100.4, 100.5, 100.3, 100.4)}), tarde(f))
    assert (r["salida"], r["instante"]) == (RES.CADUCADO, RES.iso(caduca))
    assert r["precio"] == pytest.approx(100.4 * (1 - 1e-4))
    assert r["t2"] == {"precio": 103.0, "cruzado": False, "instante": None}


@pytest.mark.parametrize("perfil", PERFILES)
def test_sin_entrada_si_el_stop_o_t1_se_cumplen_antes_de_la_entrada_real(perfil):
    r = resuelve(perfil, {"2026-10-12T20:01": (100.0, 100.0, 98.9, 99.5)})
    assert (r["salida"], r["instante"], r["entrada"]) == (RES.SIN_ENTRADA, "2026-10-12T20:01:00Z", None)
    assert r["pnl"]["r_neto"] == 0.0 and "el stop" in r["motivo"]
    assert resuelve(perfil, {"2026-10-12T20:02": (100.0, 102.5, 100.0, 101.0)})["salida"] == RES.SIN_ENTRADA
    # la apertura de la entrada ya esta mas alla del stop: tampoco abre
    assert resuelve(perfil, {"2026-10-12T20:03": (98.9, 99.0, 98.8, 98.9)})["salida"] == RES.SIN_ENTRADA
    # lo mismo DESPUES de la entrada ya es un stop
    assert resuelve(perfil, {"2026-10-12T20:03": (100.0, 100.0, 98.9, 99.5)})["salida"] == RES.STOP


@pytest.mark.parametrize("perfil", PERFILES)
def test_no_evaluable_solo_a_la_gracia_y_vivo_antes_de_caducar(perfil):
    f = fila(perfil)
    caduca = RES.ventana(f)[1]
    vs = velas(f, quita=("2026-10-12T20:40",))
    vivo = RES.resolver(f, [v for v in vs if v["ts"] < T + timedelta(minutes=50)], T + timedelta(minutes=50))
    assert (vivo["estado"], vivo["firmeza"], vivo["sabido_hasta"]) == (RES.ABIERTO, RES.PROVISIONAL,
                                                                       "2026-10-12T20:40:00Z")
    espera = RES.resolver(f, vs, caduca + timedelta(days=1))
    assert (espera["estado"], espera["salida"], espera["firmeza"]) == (RES.ESPERANDO, None, RES.PROVISIONAL)
    gracia = caduca + MIN + RES.ASENTAMIENTO + RES.GRACIA
    assert espera["asentado_en"] == RES.iso(gracia)
    final = RES.resolver(f, vs, gracia)
    assert (final["salida"], final["firmeza"]) == (RES.NO_EVALUABLE, RES.FINAL)
    # un hueco DESPUES del evento no importa
    r = resuelve(perfil, {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)}, quita=("2026-10-12T20:40",))
    assert (r["salida"], r["firmeza"]) == (RES.STOP, RES.FINAL)
    # y un hueco declarado en data_gap tapa la vela aunque este
    tapado = RES.resolver(f, velas(f), gracia, huecos=[(T + timedelta(minutes=40), T + timedelta(minutes=41))])
    assert tapado["salida"] == RES.NO_EVALUABLE


@pytest.mark.parametrize("perfil", PERFILES)
def test_limite_no_llenada_y_limite_llenada(perfil):
    sin_llenar = resuelve(perfil, tipo="limite", precio_limite=99.6)
    assert sin_llenar["salida"] == RES.LIMITE_NO_LLENADA and sin_llenar["pnl"]["r_neto"] == 0.0
    assert sin_llenar["a_favor"]["hipotetico_a_mercado"]["salida"] == RES.CADUCADO
    # T1 antes de llenarse: no llenada, y su hipotetico a mercado es el objetivo
    t1_antes = resuelve(perfil, {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}, tipo="limite", precio_limite=99.6)
    assert (t1_antes["salida"], t1_antes["instante"]) == (RES.LIMITE_NO_LLENADA, "2026-10-12T20:30:00Z")
    assert t1_antes["a_favor"]["hipotetico_a_mercado"]["salida"] == RES.OBJETIVO
    # tocar la limite sin cruzarla no la llena; cruzarla si, a su precio y con comision maker
    llena = resuelve(perfil, {"2026-10-12T20:10": (99.8, 99.8, 99.6, 99.7), "2026-10-12T20:11": (99.7, 99.7, 99.55, 99.7),
                              "2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}, tipo="limite", precio_limite=99.6)
    assert (llena["salida"], llena["entrada"]["instante"], llena["entrada"]["precio"]) == (
        RES.OBJETIVO, "2026-10-12T20:11:00Z", 99.6)
    assert llena["pnl"]["comision_bps"] == {"entrada": 2.0, "salida": 2.0}


# --------------------------------------------------------------------------- lo que acompana a la salida


def test_t2_y_t3_se_informan_tras_t1_y_no_mueven_nada():
    r = resuelve("intradia", {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0),
                              "2026-10-12T21:00": (101.0, 103.5, 101.0, 103.0)})
    assert r["salida"] == RES.OBJETIVO and r["precio"] == 102.0
    assert r["t2"] == {"precio": 103.0, "cruzado": True, "instante": "2026-10-12T21:00:00Z"}
    assert r["t3"] == {"precio": 104.0, "cruzado": False, "instante": None}
    sin_t2 = resuelve("intradia", {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)})
    assert sin_t2["pnl"] == r["pnl"]
    # tras T1 el plan acaba en su stop: un T2 posterior ya no cuenta
    tras_stop = resuelve("intradia", {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0),
                                      "2026-10-12T20:40": (100.0, 100.0, 98.9, 99.0),
                                      "2026-10-12T21:00": (101.0, 103.5, 101.0, 103.0)})
    assert tras_stop["t2"]["cruzado"] is False


def test_provisional_hasta_que_se_asienta_su_ultima_vela():
    f = fila("intradia")
    vs = velas(f, {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)})
    listo = T + timedelta(minutes=31) + RES.ASENTAMIENTO
    antes = RES.resolver(f, vs, listo - timedelta(seconds=1))
    assert (antes["salida"], antes["firmeza"], antes["asentado_en"]) == (RES.STOP, RES.PROVISIONAL, RES.iso(listo))
    assert RES.resolver(f, vs, listo)["firmeza"] == RES.FINAL


def test_excursion_y_funding_solo_adverso():
    f = fila("swing")
    vs = velas(f, {"2026-10-12T23:00": (100.0, 101.0, 99.5, 100.0), "2026-10-13T09:00": (100.0, 100.0, 98.9, 99.0)})
    cobros = {datetime(2026, 10, 13, 0, tzinfo=UTC): {"fr_high": 0.01, "fr_low": 0.004},
              datetime(2026, 10, 13, 8, tzinfo=UTC): {"fr_high": -0.002, "fr_low": -0.01}}
    r = RES.resolver(f, vs, tarde(f), cobros)
    assert r["salida"] == RES.STOP
    assert [(c["cobro"], c["fr_adverso"]) for c in r["funding"]] == [
        ("2026-10-13T00:00:00Z", 0.01), ("2026-10-13T08:00:00Z", 0.0)]
    corto = RES.resolver(espejo_fila(f), espejo_velas(vs), tarde(f), cobros)
    assert [c["fr_adverso"] for c in corto["funding"]] == [0.0, 0.01]
    assert r["excursion"]["favor_bps"] == pytest.approx((101.0 - 100.01) / 100.01 * 1e4)
    assert r["excursion"]["contra_bps"] == pytest.approx((100.01 - 99.0 * (1 - 1e-4)) / 100.01 * 1e4)


def test_una_sombra_da_un_hipotetico_y_sin_plan_no_evaluable():
    f = fila("intradia")
    f["estado"] = "SOMBRA"
    r = RES.resolver(f, velas(f, {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)}), tarde(f))
    assert r["hipotetico"] is True and r["salida"] == RES.STOP
    sin = copy.deepcopy(f)
    sin["foto"]["plan"]["objetivos"] = []
    assert RES.resolver(sin, velas(sin), tarde(sin))["salida"] == RES.NO_EVALUABLE


def test_lo_que_declaran_las_convenciones_del_remate_2():
    """Convenciones «plan», «sin_coste», «t2_t3» y «huecos» (remate 2 de la 139): lo que dicen es lo que hace el
    codigo. Si una cambia, este test y la convencion cambian juntos."""
    stop_2030 = {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)}
    t1_2030 = {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0)}
    # plan: sin stop, NO EVALUABLE en el acto (antes incluso de la entrada), FINAL y sin instante ni hora
    sin_plan = fila("intradia")
    sin_plan["foto"]["plan"]["stop"]["precio"] = None
    r = RES.resolver(sin_plan, velas(sin_plan), T + MIN)
    assert (r["estado"], r["salida"], r["firmeza"], r["instante"], r["asentado_en"]) == (
        RES.ACABADO, RES.NO_EVALUABLE, RES.FINAL, None, None)
    # sin_coste: con un componente null, sin P&L en un STOP (y lo dice el motivo) y en un SIN ENTRADA; el precio, si
    sin = fila("intradia")
    sin["foto"]["plan"]["costes"]["stop"]["componentes_bps"]["deslizamiento"] = None
    r = RES.resolver(sin, velas(sin, stop_2030), tarde(sin))
    assert (r["salida"], r["pnl"], r["precio"] is not None) == (RES.STOP, None, True)
    assert r["motivo"].startswith("la foto no trae el coste de sus patas")
    r = RES.resolver(sin, velas(sin, {"2026-10-12T20:01": (100.0, 100.0, 98.9, 99.5)}), tarde(sin))
    assert (r["salida"], r["pnl"]) == (RES.SIN_ENTRADA, None)
    # ... salvo si al seguimiento de T2 y T3 le falta una vela: entonces el motivo dice eso
    hora = T + timedelta(minutes=60)
    r = RES.resolver(sin, [v for v in velas(sin, t1_2030) if v["ts"] < hora], hora)
    assert (r["salida"], r["pnl"]) == (RES.OBJETIVO, None) and r["motivo"].startswith("T2 y T3 se siguen")
    # t2_t3: tras T1, mientras el seguimiento no acaba, PROVISIONAL y sin hora de asentamiento, con su P&L
    f = fila("intradia")
    r = RES.resolver(f, [v for v in velas(f, t1_2030) if v["ts"] < hora], hora)
    assert (r["salida"], r["firmeza"], r["asentado_en"], r["pnl"] is not None) == (
        RES.OBJETIVO, RES.PROVISIONAL, None, True)
    # huecos: falta la vela de una salida ya decidida (la invalidacion de las 20:30): ESPERA, no ABIERTO, aunque el
    # plan no ha caducado
    vs = velas(f, {"2026-10-12T20:29": (100.0, 100.0, 99.4, 99.4)}, quita=("2026-10-12T20:30",))
    r = RES.resolver(f, vs, T + timedelta(minutes=50))
    assert (r["estado"], r["firmeza"], r["sabido_hasta"]) == (RES.ESPERANDO, RES.PROVISIONAL, "2026-10-12T20:30:00Z")


# --------------------------------------------------------------------------- el espejo


def espejo_fila(f: dict) -> dict:
    g = copy.deepcopy(f)
    g["lado"] = "corto"
    p = g["foto"]["plan"]
    p["stop"]["precio"] = -p["stop"]["precio"]
    p["objetivos"] = [-x for x in p["objetivos"]]
    p["invalidacion"]["nivel"] = -p["invalidacion"]["nivel"]
    p["entrada"]["referencia"]["precio"] = -p["entrada"]["referencia"]["precio"]
    if p["entrada"]["precio"] is not None:
        p["entrada"]["precio"] = -p["entrada"]["precio"]
    return g


def espejo_velas(vs: list[dict]) -> list[dict]:
    return [{"ts": v["ts"], "open": -v["open"], "high": -v["low"], "low": -v["high"], "close": -v["close"]} for v in vs]


CASOS = {
    "objetivo": {"2026-10-12T20:30": (100.0, 102.5, 100.0, 101.0), "2026-10-12T21:00": (101.0, 103.5, 101.0, 103.0)},
    "stop": {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)},
    "stop_hueco": {"2026-10-12T20:30": (98.8, 98.9, 98.7, 98.8)},
    "misma_vela": {"2026-10-12T20:30": (100.0, 102.5, 98.9, 100.0)},
    "invalidado": {"2026-10-12T20:14": (99.6, 99.7, 99.2, 99.3), "2026-10-12T23:59": (99.6, 99.7, 99.2, 99.3)},
    "caducado": {},
    "sin_entrada": {"2026-10-12T20:01": (100.0, 102.5, 100.0, 101.0)},
}


@pytest.mark.parametrize("perfil", PERFILES)
@pytest.mark.parametrize("caso", [*CASOS, "no_evaluable", "limite"])
def test_el_corto_es_el_reflejo_del_largo(perfil, caso):
    """El corto con el mercado reflejado (precio -> -precio) da la MISMA salida, el mismo instante y los mismos
    bps y R, con cada precio con el signo cambiado. Y reflejado alrededor de 100 (precios positivos, como en
    produccion) da la misma salida y el mismo instante, con el R a menos de 0.01."""
    kw = {"tipo": "limite", "precio_limite": 99.6} if caso == "limite" else {}
    f = fila(perfil, **kw)
    vs = velas(f, CASOS.get(caso), quita=("2026-10-12T20:40",) if caso == "no_evaluable" else ())
    largo = RES.resolver(f, vs, tarde(f))
    corto = RES.resolver(espejo_fila(f), espejo_velas(vs), tarde(f))
    assert corto["salida"] == largo["salida"] and corto["salida"] is not None
    for k in ("instante", "pnl", "excursion", "firmeza", "asentado_en", "estado", "motivo"):
        assert corto[k] == largo[k], k
    for k in ("precio",):
        assert (corto[k] is None and largo[k] is None) or _aprox(corto[k], -largo[k])
    for t in ("t2", "t3"):
        assert corto[t]["cruzado"] == largo[t]["cruzado"] if largo[t] else corto[t] is None
    # reflejado alrededor de 100: precios positivos
    g = espejo_fila(f)
    p = g["foto"]["plan"]
    p["stop"]["precio"] += 200
    p["objetivos"] = [x + 200 for x in p["objetivos"]]
    p["invalidacion"]["nivel"] += 200
    if p["entrada"]["precio"] is not None:
        p["entrada"]["precio"] += 200
    ws = [{k: (v[k] + 200 if k != "ts" else v[k]) for k in v} for v in espejo_velas(vs)]
    real = RES.resolver(g, ws, tarde(f))
    assert (real["salida"], real["instante"]) == (largo["salida"], largo["instante"])
    if largo["pnl"] and largo["pnl"]["r_neto"] is not None:
        assert real["pnl"]["r_neto"] == pytest.approx(largo["pnl"]["r_neto"], abs=0.01)


# --------------------------------------------------------------------------- las convenciones


def test_asentamiento_y_gracia_son_los_de_signal_outcomes():
    assert RES.ASENTAMIENTO == signal_outcomes.OUTCOME_SETTLEMENT_LAG
    assert RES.GRACIA == signal_outcomes.MISSING_DATA_FINAL_GRACE


@pytest.mark.parametrize("perfil", PERFILES)
def test_el_corte_en_ahora_se_declara_y_se_aplica(perfil):
    """Una vela que empieza despues de `ahora` no se usa aunque este en la base: es la convencion «corte», que se
    sirve con las demas y entra en su huella. La del minuto de `ahora` si cuenta."""
    assert "`ahora`" in RES.CONVENCIONES["corte"] and "no se usa" in RES.CONVENCIONES["corte"]
    f = fila(perfil)
    vs = velas(f, {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)})   # todas en la base, la del stop tambien
    antes = RES.resolver(f, vs, T + timedelta(minutes=29, seconds=59))
    assert (antes["estado"], antes["salida"], antes["sabido_hasta"]) == (RES.ABIERTO, None, "2026-10-12T20:30:00Z")
    en_su_minuto = RES.resolver(f, vs, T + timedelta(minutes=30, seconds=1))
    assert (en_su_minuto["salida"], en_su_minuto["firmeza"]) == (RES.STOP, RES.PROVISIONAL)


def test_cambiar_una_convencion_es_una_version_nueva():
    """La huella de las convenciones de entradas-resolutor-1 no se mueve: cambiar una exige subir la version
    (un resultado guardado lleva la suya y no se reescribe). Se movio sin subirla en los dos remates de la 139, antes
    de desplegar y sin cambiar lo que el codigo hace: la de d9f4520 (717a69038e1b...) no tenia el «corte», que ya se
    aplicaba desde 8b33125; la de 8fb7c20 (d3f41674d65d...) no decia todo lo que resolver() aplica. Ninguna de las
    dos llego a guardar un resultado en produccion."""
    registradas = {"entradas-resolutor-1": HUELLA_V1}
    assert RES.RESOLUTOR_VERSION in registradas
    assert registradas[RES.RESOLUTOR_VERSION] == RES.HUELLA_CONVENCIONES


HUELLA_V1 = "eb6248f2b29207c053d17e7fd6c97db4edf8d6c38b17616dfe74095ee2cea66f"
