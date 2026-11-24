"""AUDITOR R1 (app/bot/auditor.py): cada compuerta pasa, en el borde y falla; la resolucion del estado; falla
cerrado; determinismo. Puro: sin base ni red (encargo del dueno, seccion 8, pruebas 1 a 4 y 6)."""
import copy
import itertools
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.bot import auditor as A
from app.bot import calc

AHORA = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def hace(s: float) -> str:
    return (AHORA - timedelta(seconds=s)).isoformat()


def en(minutos: float) -> str:
    return (AHORA + timedelta(minutes=minutos)).isoformat()


def caso() -> dict:
    """Una posicion sana: LARGO con stop a 2 %, perdida 2.1 USD, liquidacion lejos, libro fresco, calendario limpio."""
    return {
        "posicion": {"symbol": "BTCUSDT", "lado": 1, "cantidad": 0.001, "entrada": 100_000.0, "stop": 98_000.0,
                     "objetivo": 104_000.0, "liquidacion": 90_000.0, "visto": (AHORA.timestamp() - 5) * 1000},
        "dec": {"generated_at": hace(2), "age": {"snapshot_lag_seconds": {"value": 40.0}}},
        "sobre": {"generated_at": hace(2),
                  "orderbook": {"bybit": {"ts": hace(2), "spread_bps": 0.5, "ask_notional_l1": 500_000.0,
                                          "bid_notional_l1": 500_000.0}},
                  "external_macro_context": {"event_risk": {"upcoming": [
                      {"title": "CPI", "event_at": en(60 * 30), "importance": 3}]}}},
        "veredicto_opus": "A FAVOR", "veredicto_decide": "A FAVOR", "ahora": AHORA,
    }


def audita(c: dict, **kw) -> A.Dictamen:
    return A.audita(c["posicion"], c["dec"], c["sobre"], c["veredicto_opus"], c["veredicto_decide"], c["ahora"], **kw)


def puerta(c: dict, nombre: str) -> A.Compuerta:
    return next(x for x in audita(c).compuertas if x.nombre == nombre)


def test_el_caso_sano_aprueba_las_nueve():
    d = audita(caso())
    assert [x.nombre for x in d.compuertas] == list(A.COMPUERTAS)
    assert d.estado == "APROBADO" and d.razon == "las 9 compuertas pasan", [x.como_dict() for x in d.compuertas]
    assert A.linea(d) == "AUDITOR: APROBADO · las 9 compuertas pasan" and d.riesgo() == []


# ---- 1. cada compuerta: pasa, borde, falla ----

def test_a1_veredicto_de_opus():
    c = caso()
    assert puerta(c, "A1").severidad == A.OK
    c["veredicto_opus"] = "NO EVALUABLE"  # borde: legible aunque no tome lado
    assert puerta(c, "A1").severidad == A.OK
    for malo in (None, "QUIZA", ""):
        c["veredicto_opus"] = malo
        assert puerta(c, "A1").severidad == A.NO_EVALUABLE


def test_a2_frescura_con_bordes_iguales_que_pasan():
    c = caso()
    assert puerta(c, "A2").severidad == A.OK
    c["posicion"]["visto"] = (AHORA.timestamp() - 30) * 1000
    c["sobre"]["orderbook"]["bybit"]["ts"] = hace(10)
    c["dec"]["age"]["snapshot_lag_seconds"]["value"] = 120.0
    c["dec"]["generated_at"] = c["sobre"]["generated_at"] = hace(30)
    assert puerta(c, "A2").severidad == A.OK, puerta(c, "A2").razon
    for donde, cambio in (("posicion", lambda c: c["posicion"].update(visto=(AHORA.timestamp() - 30.5) * 1000)),
                          ("libro bybit", lambda c: c["sobre"]["orderbook"]["bybit"].update(ts=hace(10.5))),
                          ("DECIDE instantanea", lambda c: c["dec"]["age"]["snapshot_lag_seconds"].update(value=121)),
                          ("sobre", lambda c: c["sobre"].update(generated_at=hace(31))),
                          ("DECIDE servido", lambda c: c["dec"].update(generated_at=hace(31)))):
        m = caso()
        cambio(m)
        g = puerta(m, "A2")
        assert g.severidad == A.NO_EVALUABLE and g.razon.startswith(donde), (donde, g.razon)
    m = caso()
    m["sobre"]["generated_at"] = en(1)  # del futuro: reloj incoherente, no fresco
    assert "futuro" in puerta(m, "A2").razon and puerta(m, "A2").severidad == A.NO_EVALUABLE
    m = caso()
    m["sobre"]["orderbook"]["bybit"] = None  # el sobre quita el libro de mas de 30 s
    assert puerta(m, "A2").razon == "falta el dato: sobre.orderbook.bybit.ts"


def test_a3_lectura_de_decide():
    c = caso()
    assert puerta(c, "A3").severidad == A.OK
    c["veredicto_decide"] = "NO EVALUABLE"
    g = puerta(c, "A3")
    assert g.severidad == A.AVISO and "sin una lectura evaluable de DECIDE" in g.razon
    c["veredicto_decide"] = None
    assert puerta(c, "A3").severidad == A.NO_EVALUABLE


def test_a4_acuerdo_entre_opus_y_decide():
    c = caso()
    assert puerta(c, "A4").severidad == A.OK
    c["veredicto_decide"] = "NO EVALUABLE"
    assert puerta(c, "A4").severidad == A.NO_APLICABLE
    c["veredicto_decide"] = "EN CONTRA"
    g = puerta(c, "A4")
    assert g.severidad == A.AVISO and g.razon == "Opus dice A FAVOR y DECIDE dice EN CONTRA"
    assert audita(c).estado == "CON RESERVAS"


def test_a5_sin_stop_falla_y_sin_la_clave_no_evalua():
    c = caso()
    assert puerta(c, "A5").severidad == A.OK
    for sin in (None, 0, 0.0):
        c["posicion"]["stop"] = sin
        d = audita(c)
        assert puerta(c, "A5").severidad == A.FALLA and d.estado == "RECHAZADO"
        assert [x.nombre for x in d.riesgo()] == ["A5"]
        assert puerta(c, "A6").severidad == A.NO_APLICABLE and puerta(c, "A7").severidad == A.NO_APLICABLE
    del c["posicion"]["stop"]  # la lectura de reserva del servicio no trae la clave: no se sabe, no "sin stop"
    assert puerta(c, "A5").severidad == A.NO_EVALUABLE and "no trae la clave" in puerta(c, "A5").razon


def test_a6_perdida_al_stop_con_el_borde_de_calc():
    c = caso()
    assert puerta(c, "A6").severidad == A.OK and puerta(c, "A6").valor == pytest.approx(2.1089)
    p = c["posicion"]
    por_unidad = (p["entrada"] - p["stop"]) + (p["entrada"] + p["stop"]) * calc.TAKER
    p["cantidad"] = calc.PERDIDA_MAX / por_unidad  # justo el tope: pasa
    assert puerta(c, "A6").severidad == A.OK, puerta(c, "A6").razon
    p["cantidad"] *= 1.001
    g = puerta(c, "A6")
    assert g.severidad == A.FALLA and g.umbral == calc.PERDIDA_MAX and [x.nombre for x in audita(c).riesgo()] == ["A6"]
    p["cantidad"] = -abs(p["cantidad"])  # el signo de la cantidad no esconde la perdida
    assert puerta(c, "A6").severidad == A.FALLA
    p.update(cantidad=1.0, stop=101_000.0)  # stop ya en ganancia: no hay perdida al stop
    assert puerta(c, "A6").severidad == A.OK and puerta(c, "A6").valor < 0


def test_a6_corto_usa_la_misma_formula_que_calcula():
    r = calc.calcula(100.0, 101.0, corto=True, tramos=[{"riskLimitValue": "1e9", "maintenanceMargin": "0.005",
                                                        "mmDeduction": ""}])
    p = {"lado": -1, "cantidad": r["cantidad"], "entrada": 100.0, "stop": 101.0}
    assert calc.perdida_al_stop(p["cantidad"], 100.0, 101.0, -1) == r["perdida_stop_usd"]
    c = caso()
    c["posicion"].update(p)
    assert puerta(c, "A6").valor == pytest.approx(r["perdida_stop_usd"])


def test_a7_liquidacion_a_dos_veces_el_stop():
    c = caso()
    p = c["posicion"]
    p.update(entrada=100.0, stop=95.0, cantidad=0.1, liquidacion=90.0)  # borde: exactamente 2 veces
    assert puerta(c, "A7").severidad == A.OK and puerta(c, "A7").valor == 2.0
    p["liquidacion"] = 91.0
    assert puerta(c, "A7").severidad == A.FALLA and [x.nombre for x in audita(c).riesgo()] == ["A7"]
    p["liquidacion"] = 96.0  # antes del stop
    assert "ANTES del stop" in puerta(c, "A7").razon and puerta(c, "A7").severidad == A.FALLA
    p.update(lado=-1, stop=105.0, liquidacion=110.0)  # corto, borde
    assert puerta(c, "A7").severidad == A.OK
    p["liquidacion"] = 109.0
    assert puerta(c, "A7").severidad == A.FALLA
    p["liquidacion"] = None
    assert puerta(c, "A7").severidad == A.AVISO
    del p["liquidacion"]
    assert puerta(c, "A7").severidad == A.NO_EVALUABLE


def test_a8_bandas_de_coste_del_reglamento():
    c = caso()
    assert puerta(c, "A8").severidad == A.OK
    # borde: entrada a mercado (5.5 + 0.5) y stop (5.5 + 0.5) = 12 bps sobre 80 bps de stop = 0.15 justo
    c["posicion"].update(entrada=10_000.0, stop=9_920.0, objetivo=None, cantidad=0.01)
    g = puerta(c, "A8")
    assert g.severidad == A.OK and g.valor["coste_riesgo"] == pytest.approx(0.15), g.razon
    c["posicion"]["stop"] = 9_925.0
    assert puerta(c, "A8").severidad == A.AVISO and "del riesgo al stop" in puerta(c, "A8").razon
    c = caso()
    c["posicion"]["objetivo"] = 100_100.0  # 10 bps de recorrido: el coste se lo come
    assert puerta(c, "A8").severidad == A.AVISO and "objetivo" in puerta(c, "A8").razon
    c = caso()
    c["sobre"]["orderbook"]["bybit"]["ask_notional_l1"] = 50.0  # el L1 no cubre 100 USD de entrada larga
    assert puerta(c, "A8").severidad == A.NO_EVALUABLE and "deslizamiento" in puerta(c, "A8").razon
    c = caso()
    c["posicion"].update(stop=None, objetivo=None)
    assert puerta(c, "A8").severidad == A.NO_APLICABLE


def test_a9_calendario_y_su_cobertura():
    c = caso()
    assert puerta(c, "A9").severidad == A.OK
    ev = c["sobre"]["external_macro_context"]["event_risk"]["upcoming"]
    ev[:] = [{"title": "PMI", "event_at": en(239), "importance": 2},  # borde: importancia por debajo
             {"title": "CPI", "event_at": en(241), "importance": 3}]  # borde: justo fuera de la ventana
    assert puerta(c, "A9").severidad == A.OK
    ev[1]["event_at"] = en(240)
    g = puerta(c, "A9")
    assert g.severidad == A.AVISO and "CPI" in g.razon and audita(c).estado == "CON RESERVAS"
    ev[:] = [{"title": "PMI", "event_at": en(30), "importance": 1}]
    assert puerta(c, "A9").severidad == A.NO_EVALUABLE and "sin cubrir" in puerta(c, "A9").razon
    ev[:] = []
    assert puerta(c, "A9").severidad == A.NO_EVALUABLE
    del c["sobre"]["external_macro_context"]
    assert puerta(c, "A9").razon.startswith("falta el dato")


# ---- 2. resolucion del estado ----

def test_resolucion_del_estado_exhaustiva():
    sev = (A.OK, A.NO_APLICABLE, A.AVISO, A.FALLA, A.NO_EVALUABLE)
    vistos = set()
    for combo in itertools.product(sev, repeat=4):
        cs = [A.Compuerta(f"A{i + 1}", s, f"r{i}") for i, s in enumerate(combo)]
        estado, razon = A.resuelve(cs)
        peor = max(A.RANGO[s] for s in combo)
        assert estado == A.ESTADOS[peor]
        if peor:
            assert razon == f"A{[A.RANGO[s] for s in combo].index(peor) + 1}: r{[A.RANGO[s] for s in combo].index(peor)}"
        vistos.add(estado)
    assert vistos == {"APROBADO", "CON RESERVAS", "RECHAZADO", "NO EVALUABLE"}
    assert A.resuelve([]) == ("NO EVALUABLE", "sin compuertas: no hay dictamen")
    assert A.resuelve([A.Compuerta("A1", A.OK, "x"), A.Compuerta("A2", "RARO", "y")])[0] == "NO EVALUABLE"


# ---- 3. falla cerrado ----

def test_una_excepcion_en_una_compuerta_no_aprueba(monkeypatch):
    def revienta(_):
        raise ZeroDivisionError("division por cero")
    monkeypatch.setattr(A, "PUERTAS", tuple((n, revienta if n == "A4" else f) for n, f in A.PUERTAS))
    d = audita(caso())
    assert d.estado == "NO EVALUABLE" and d.razon == "A4: error: ZeroDivisionError: division por cero"


def test_un_dato_faltante_no_aprueba():
    c = caso()
    del c["posicion"]["entrada"]
    d = audita(c)
    assert d.estado == "NO EVALUABLE" and d.razon == "A6: falta el dato: posicion.entrada"
    d = A.audita(None, None, None, None, None, None)
    assert d.estado == "NO EVALUABLE" and len(d.compuertas) == 9
    assert {x.severidad for x in d.compuertas if x.nombre in ("A1", "A2", "A9")} == {A.NO_EVALUABLE}


def test_un_umbral_faltante_no_aprueba_ni_se_inventa():
    for falta, nombre in (("PERDIDA_MAX", "A6"), ("LIQ_VECES", "A7"), ("REALTIME_STALE_SECONDS", "A2"),
                          ("banda_coste_riesgo_max", "A8"), ("ventana_min_intradia", "A9")):
        u = {k: v for k, v in A.UMBRALES.items() if k != falta}
        d = audita(caso(), umbrales=u)
        assert d.estado == "NO EVALUABLE" and d.razon == f"{nombre}: umbral faltante: {falta}", d.razon
    d = audita(caso(), umbrales={})
    assert {x.nombre for x in d.compuertas if x.severidad == A.NO_EVALUABLE} == {"A2", "A6", "A7", "A8", "A9"}


def test_la_linea_no_falla_nunca():
    assert A.linea(None) == "AUDITOR: NO EVALUABLE (error: sin dictamen)"
    assert A.linea(audita(caso()), "TypeError: x") == "AUDITOR: NO EVALUABLE (error: TypeError: x)"
    assert A.linea(object()).startswith("AUDITOR: NO EVALUABLE (error:")


# ---- 4. determinismo y pureza ----

def test_la_misma_entrada_da_el_mismo_dictamen():
    c = caso()
    c["veredicto_decide"] = "EN CONTRA"
    antes = copy.deepcopy(c)
    uno, dos = audita(c).como_dict(), audita(copy.deepcopy(c)).como_dict()
    assert uno == dos and json.dumps(uno, sort_keys=True) == json.dumps(dos, sort_keys=True)
    assert c == antes  # no muta lo que recibe
    json.loads(json.dumps(uno, allow_nan=False))  # cabe en jsonb tal cual


def test_el_auditor_no_tiene_reloj_red_base_ni_azar():
    fuente = Path(A.__file__).read_text()
    for prohibido in ("now(", "time.time", "random", "httpx", "asyncpg", "import os", "urllib", "socket"):
        assert prohibido not in fuente, prohibido


# ---- 6. los umbrales son los de calc.py y de donde viven ----

def test_los_umbrales_salen_de_donde_viven():
    from app.ai_context import MESA_DECIDE_MAX_AGE_S
    from app.entradas import reglamento as R
    from app.scalp_logic import REALTIME_STALE_SECONDS
    v = R.version_activa(R.cargar_valido())
    comun, cal = R.valores(v["bloques"]["comun"]), R.valores(v["bloques"]["calendario"])
    u = A.UMBRALES
    assert (u["PERDIDA_MAX"], u["LIQ_VECES"]) == (calc.PERDIDA_MAX, calc.LIQ_VECES)
    assert u["REALTIME_STALE_SECONDS"] == REALTIME_STALE_SECONDS and u["MESA_DECIDE_MAX_AGE_S"] == MESA_DECIDE_MAX_AGE_S
    assert u["libro_edad_max_s"] == comun["libro_edad_max_s"] and u["coste_pata"] == comun["coste_pata"]
    assert u["comision_bps_lado"]["taker"] == pytest.approx(calc.TAKER * 1e4)  # la misma comision en los dos sitios
    assert (u["importancia_minima"], u["ventana_min_intradia"]) == (cal["importancia_minima"], cal["ventana_min"]["intradia"])
