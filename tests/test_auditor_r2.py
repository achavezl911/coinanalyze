"""AUDITOR R2 (encargo del dueno, seccion 6 y prueba 7): al cierre se califican Opus, DECIDE y el auditor en filas NUEVAS
(nunca UPDATE), con R = pnl / perdida al stop de A6; el informe dice, por fuente, n, acierto con Wilson al 95 % y R medio,
SIN CALIBRAR antes de 30, la comparacion pareada con la prueba de signos y la regla sellada de las 60 vidas pareadas."""

from __future__ import annotations

import json
import re
import time
import uuid

import asyncpg
import pytest
from test_bot import base  # noqa: F401

from app.bot import calidad
from app.bot import servicio as sv


def _auditor(estado: str = "APROBADO", perdida: float | None = 20.0) -> dict:
    a6 = ({"nombre": "A6", "severidad": "NO_APLICABLE", "razon": "sin stop", "valor": None, "umbral": None} if perdida is None
          else {"nombre": "A6", "severidad": "OK", "razon": "perdida al stop", "valor": perdida, "umbral": 50.0})
    return {"version": "auditor-r1", "estado": estado, "razon": "-", "compuertas": [a6]}


def _vida(opus: str, decide: str, pnl: float, estado: str = "APROBADO", perdida: float | None = 20.0) -> dict:
    m = calidad.mide(calidad.apertura(opus, "opus", decide, _auditor(estado, perdida)), pnl)
    return calidad.vida({"medicion": json.dumps(m), "coste_usd": 0.1})


# ------------------------------------------------------------------------------------- la estadistica, con casos conocidos
def test_wilson_y_la_prueba_de_signos_con_casos_conocidos():
    lo, hi = calidad.wilson(8, 10)
    assert (round(lo, 4), round(hi, 4)) == (0.4902, 0.9433)  # el de los libros: 8/10 -> [0.490, 0.943]
    lo, hi = calidad.wilson(0, 10)
    assert lo == 0.0 and round(hi, 4) == 0.2775  # z^2 / (n + z^2)
    assert calidad.wilson(0, 0) is None
    assert calidad.signos(9, 1) == pytest.approx(22 / 1024)  # 2 * (1 + 10) / 2^10
    assert calidad.signos(10, 0) == pytest.approx(2 / 1024) and calidad.signos(1, 9) == calidad.signos(9, 1)
    assert calidad.signos(5, 5) == 1.0 and calidad.signos(0, 0) == 1.0


def test_r_es_el_pnl_entre_la_perdida_al_stop_de_a6_y_sin_stop_no_se_calcula():
    m = calidad.mide(calidad.apertura("A FAVOR", "opus", "EN CONTRA", _auditor()), -5.0)
    assert (m["acierto_opus"], m["acierto_decide"], m["r"], m["auditor"]) == (False, True, -0.25, "APROBADO")
    assert calidad.linea_cierre(m) == ("MEDICION: OPUS A FAVOR -> FALLO · DECIDE EN CONTRA -> ACIERTO"
                                       " · AUDITOR al abrir APROBADO · R -0.25")
    sin = calidad.mide(calidad.apertura("A FAVOR", "opus", "A FAVOR", _auditor("RECHAZADO", None)), 3.0)
    assert sin["r"] is None and sin["sin_r"] == "sin stop al abrir: R no se calcula" and sin["sin_r"] in calidad.linea_cierre(sin)
    # Opus caido: el registrado salio de DECIDE; Opus no fue evaluable y no se le apunta el acierto de DECIDE
    caido = calidad.mide(calidad.apertura("EN CONTRA", "DECIDE (err)", "EN CONTRA", _auditor()), -1.0)
    assert caido["opus"] == "NO EVALUABLE" and caido["acierto_opus"] is None and caido["acierto_decide"] is True
    viejo = calidad.mide(calidad.apertura("A FAVOR", None, None, None), 1.0)  # vida de antes de R1: sin auditor
    assert viejo["acierto_opus"] is True and viejo["r"] is None and viejo["sin_r"].startswith("sin auditor al abrir")


# ------------------------------------------------------------------------------- SIN CALIBRAR y las lecturas 30 / 60 / 120
def test_antes_de_30_dice_sin_calibrar_y_solo_lee_en_30_60_y_120_sobre_las_primeras():
    m = calidad.medicion([_vida("A FAVOR", "EN CONTRA", 1.0) for _ in range(29)])
    for f in calidad.FUENTES:
        assert m["fuentes"][f] == {"n": 29, "estado": "SIN CALIBRAR · MUESTRA INSUFICIENTE (29/30)"}
    t = "\n".join(calidad.texto_medicion(m))
    assert "OPUS: SIN CALIBRAR · MUESTRA INSUFICIENTE (29/30)" in t and "IC95" not in t
    assert "REGLA SELLADA: 29/60 vidas pareadas, sin lectura" in t
    # 30 aciertos de Opus y despues 15 fallos: la lectura es en n=30 sobre las 30 PRIMERAS (no ve los fallos)
    vidas = [_vida("A FAVOR", "EN CONTRA", 1.0) for _ in range(30)] + [_vida("A FAVOR", "EN CONTRA", -1.0) for _ in range(15)]
    o = calidad.medicion(vidas)["fuentes"]["OPUS"]
    assert (o["n"], o["lectura_en"], o["aciertos"], o["tasa"]) == (45, 30, 30, 1.0)
    for n, corte in ((59, 30), (60, 60), (119, 60), (120, 120), (200, 120)):
        assert calidad.medicion([_vida("A FAVOR", "A FAVOR", 1.0)] * n)["fuentes"]["DECIDE"]["lectura_en"] == corte


def test_una_fuente_que_no_le_gana_a_siempre_a_favor_no_aporta():
    # 21 de 30 ganadoras; Opus dice siempre A FAVOR: acierta lo mismo que la linea base y no le gana
    vidas = [_vida("A FAVOR", "EN CONTRA", 1.0 if k < 21 else -1.0) for k in range(30)]
    m = calidad.medicion(vidas)
    o, b = m["fuentes"]["OPUS"], m["fuentes"]["SIEMPRE A FAVOR"]
    assert (o["tasa"], b["tasa"], o["base_mismas_vidas"], o["le_gana_a_la_base"]) == (0.7, 0.7, 0.7, False)
    assert "OPUS lectura en n=30" in "\n".join(calidad.texto_medicion(m)) and "NO LE GANA A LA BASE, no aporta" in \
        "\n".join(calidad.texto_medicion(m))
    # DECIDE acierta las 30 (dice EN CONTRA justo en las perdedoras): su Wilson [0.886, 1] deja abajo el 0.7
    vidas = [_vida("A FAVOR", "A FAVOR" if k < 21 else "EN CONTRA", 1.0 if k < 21 else -1.0) for k in range(30)]
    assert calidad.medicion(vidas)["fuentes"]["DECIDE"]["le_gana_a_la_base"] is True


# ----------------------------------------------------------------------------- la pareada y la regla sellada de las 60
def test_la_regla_sellada_lee_solo_con_60_pareadas_y_sin_discordantes_opus_no_supera():
    p = calidad.medicion([_vida("A FAVOR", "A FAVOR", 1.0)] * 59)["pareada"]
    assert p["regla"] == "REGLA SELLADA: 59/60 vidas pareadas, sin lectura" and "supera" not in p and p["lectura_en"] == 30
    p = calidad.medicion([_vida("A FAVOR", "A FAVOR", 1.0)] * 60)["pareada"]  # siempre dicen lo mismo: diferencia 0 exacta
    assert (p["difieren"], p["diferencia"], p["intervalo"], p["p_signos"], p["supera"]) == (0, 0.0, [0.0, 0.0], 1.0, False)
    assert "Opus NO supera a DECIDE" in p["regla"] and "la decision es suya" in p["regla"]


def test_la_pareada_cuenta_quien_acierta_cuando_difieren_con_la_prueba_de_signos():
    def pareadas(b: int, c: int) -> list[dict]:  # b: acierta solo Opus; c: solo DECIDE; el resto, los dos
        return ([_vida("A FAVOR", "EN CONTRA", 1.0)] * b + [_vida("EN CONTRA", "A FAVOR", 1.0)] * c
                + [_vida("A FAVOR", "A FAVOR", 1.0)] * (60 - b - c))
    p = calidad.medicion(pareadas(9, 1))["pareada"]
    assert (p["difieren"], p["acierta_opus"], p["acierta_decide"], p["p_signos"]) == (10, 9, 1, 0.0215)
    assert p["diferencia"] == round(8 / 60, 4) and p["intervalo"][0] > 0 and p["supera"] is True
    p = calidad.medicion(pareadas(6, 4))["pareada"]  # 6 contra 4: el intervalo incluye 0
    assert p["intervalo"][0] < 0 < p["intervalo"][1] and p["supera"] is False and p["p_signos"] == round(calidad.signos(6, 4), 4)
    p = calidad.medicion(pareadas(1, 9))["pareada"]  # DECIDE mejor: diferencia negativa
    assert p["diferencia"] < 0 and p["intervalo"][1] < 0 and p["supera"] is False
    # una vida en que Opus no fue evaluable no entra en la pareada (ni en la de Opus), si en la de DECIDE
    caida = calidad.vida({"medicion": calidad.mide(calidad.apertura("A FAVOR", "DECIDE (err)", "A FAVOR", _auditor()), 1.0)})
    m = calidad.medicion(pareadas(9, 1)[:59] + [caida])
    assert (m["pareada"]["n"], m["fuentes"]["OPUS"]["n"], m["fuentes"]["DECIDE"]["n"]) == (59, 59, 60)


def test_el_auditor_se_mide_rechazadas_contra_aprobadas_y_el_coste_por_vida_evaluada():
    aprobadas = [_vida("A FAVOR", "A FAVOR", 10.0, "APROBADO")] * 30
    m = calidad.medicion(aprobadas + [_vida("A FAVOR", "A FAVOR", 10.0, "RECHAZADO")] * 30)
    assert m["auditor"]["distingue"] is False and "sus compuertas no distinguen" in m["auditor"]["veredicto"]
    m = calidad.medicion(aprobadas + [_vida("A FAVOR", "A FAVOR", -16.0, "RECHAZADO")] * 30)
    assert m["auditor"]["APROBADO"]["r_medio"] == (0.5, 30) and m["auditor"]["RECHAZADO"]["r_medio"] == (-0.8, 30)
    assert m["auditor"]["distingue"] is True
    # las RECHAZADAS por A5 (sin stop) no tienen R: el auditor no lee, pero su tasa de ganadoras si
    m = calidad.medicion(aprobadas + [_vida("A FAVOR", "A FAVOR", -1.0, "RECHAZADO", None)] * 30)
    assert "distingue" not in m["auditor"] and m["auditor"]["RECHAZADO"]["ganadoras"] == 0 and m["auditor"]["RECHAZADO"]["con_r"] == 0
    assert m["coste_opus"] == {"usd": 6.0, "vidas_evaluadas": 60, "por_vida_evaluada": 0.1}


# ------------------------------------------------------------------------- prueba 7 del dueno: el cierre, sin UPDATE
class _Espia:
    """La base de verdad, apuntando cada SQL que le llega."""

    def __init__(self, db):
        self.db, self.sql = db, []

    def __getattr__(self, k):
        f = getattr(self.db, k)

        async def apunta(sql, *a):
            self.sql.append(sql)
            return await f(sql, *a)
        return apunta


async def _filas(base) -> list[tuple]:  # noqa: F811
    return [tuple(r) for r in await base.fetch(
        "SELECT id, ts, tipo, posicion, veredicto, veredicto_decide, pnl_usd, acierto, detalle::text FROM bot_evaluacion ORDER BY ts, id")]


async def test_prueba_7_el_cierre_califica_en_filas_nuevas_sin_update_y_el_informe_dice_sin_calibrar(base):  # noqa: F811
    i = "BTCUSDT:Buy:1792400000000"
    p = {"clave": "BTCUSDT:Buy", "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.004, "entrada": 110000.0, "actualizada": 1792400000000, "id": i}
    llamada = await base.fetchval(
        "INSERT INTO bot_llamada (motivo, modelo, effort, tokens_entrada, tokens_salida, coste_usd, tope_usd)"
        " VALUES ('evalua', 'm', 'high', 1, 1, 0.12, 3.0) RETURNING id::text")
    await base.execute("INSERT INTO bot_evaluacion (tipo, posicion, veredicto, veredicto_decide, detalle)"
                       " VALUES ('veredicto', $1, 'A FAVOR', 'EN CONTRA', $2::jsonb)",
                       i, json.dumps({"motivo": "posicion nueva", "posicion": p, "fuente": "opus", "llamada": llamada, "auditor": _auditor()}))
    # una vida de ANTES de R2 (su cierre sin medicion) y un /evalua a mano, que no se califica
    viejo = "ETHUSDT:Sell:1792300000000"
    await base.execute("INSERT INTO bot_evaluacion (ts, tipo, posicion, veredicto, detalle) VALUES"
                       " (now() - interval '2 days', 'veredicto', $1, 'EN CONTRA', '{\"motivo\": \"posicion nueva\"}'::jsonb)", viejo)
    await base.execute("INSERT INTO bot_evaluacion (ts, tipo, posicion, veredicto, pnl_usd, acierto, detalle) VALUES"
                       " (now() - interval '1 day', 'cierre', $1, 'EN CONTRA', 2.0, false, '{\"ordenes\": [\"v-1\"]}'::jsonb)", viejo)
    await base.execute("INSERT INTO bot_evaluacion (tipo, posicion, veredicto, detalle)"
                       " VALUES ('veredicto', $1, 'NO EVALUABLE', '{\"motivo\": \"/evalua\"}'::jsonb)", i)
    textos = []

    async def manda(t):
        textos.append(t)
        return True

    espia = _Espia(base)
    bot = sv.Bot({}, espia, None)
    await bot.carga()
    bot.manda = manda
    antes = await _filas(base)
    await bot.cierre(i, {"pnl": -5.0, "ordenes": ["o-1"], "nota": None})
    despues = await _filas(base)
    assert despues[:len(antes)] == antes and len(despues) == len(antes) + 1  # las de antes, intactas; UNA nueva
    nueva = await base.fetchrow("SELECT veredicto, veredicto_decide, acierto, detalle FROM bot_evaluacion WHERE tipo = 'cierre'"
                                " AND posicion = $1", i)
    m = json.loads(nueva["detalle"])["medicion"]
    assert (nueva["veredicto"], nueva["veredicto_decide"], nueva["acierto"]) == ("A FAVOR", "EN CONTRA", False)
    assert (m["version"], m["acierto_opus"], m["acierto_decide"], m["auditor"], m["r"], m["llamada"]) == \
        ("auditor-r2", False, True, "APROBADO", -0.25, llamada)
    assert textos == ["CERRADA BTCUSDT LARGO: -5.00 USD · el veredicto era A FAVOR -> FALLO\nMEDICION: OPUS A FAVOR -> FALLO"
                      " · DECIDE EN CONTRA -> ACIERTO · AUDITOR al abrir APROBADO · R -0.25"]

    # la cifra tardia: otra fila MAS, con la medicion rehecha; las de antes, intactas
    antes = despues
    await bot.correccion("o-2", {"id": i, "pnl": 4.0, "ordenes": ["o-1", "o-2"], "nota": "llego tarde", "orden": "o-2", "pnl_antes": -5.0})
    despues = await _filas(base)
    assert despues[:len(antes)] == antes and len(despues) == len(antes) + 1
    m = json.loads(despues[-1][8])["medicion"]
    assert (m["acierto_opus"], m["acierto_decide"], m["r"], m["auditor"]) == (True, False, 0.2, "APROBADO")
    assert textos[-1].startswith("CORRECCION BTCUSDT LARGO: -5.00 -> +4.00 USD") and \
        "MEDICION: OPUS A FAVOR -> ACIERTO · DECIDE EN CONTRA -> FALLO · AUDITOR al abrir APROBADO · R +0.20" in textos[-1]
    assert not [s for s in espia.sql if re.search(r"\bUPDATE\b|\bDELETE\b", s, re.I)]
    with pytest.raises(asyncpg.PostgresError):  # y la tabla no lo admitiria: es solo anadir
        await base.execute("UPDATE bot_evaluacion SET acierto = true WHERE posicion = $1", i)

    # el informe: dos vidas (una recalificada en la consulta), SIN CALIBRAR, el coste y el /evalua aparte
    r = await bot.cifras_semana(int(time.time() // 60) + 1)
    med = r["medicion"]
    assert (med["vidas"], med["recalificadas"]) == (2, 1)
    assert med["fuentes"]["OPUS"] == {"n": 2, "estado": "SIN CALIBRAR · MUESTRA INSUFICIENTE (2/30)"}
    assert med["fuentes"]["DECIDE"]["n"] == 1 and med["pareada"]["n"] == 1
    assert med["coste_opus"] == {"usd": 0.12, "vidas_evaluadas": 2, "por_vida_evaluada": 0.06}
    assert med["a_mano"] == {"NO EVALUABLE": 1}
    t = calidad.texto(r)
    assert "OPUS: SIN CALIBRAR · MUESTRA INSUFICIENTE (2/30)" in t and "REGLA SELLADA: 1/60 vidas pareadas, sin lectura" in t
    assert "evaluaciones no automaticas de la semana (/evalua; no se califican): 1 (NO EVALUABLE 1)" in t
    assert str(uuid.UUID(llamada)) == llamada
