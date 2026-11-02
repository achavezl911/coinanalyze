"""BOT-2 R10 «la clave sin IP»: Alejandro esta detras de CGNAT (2026-10-27 la salida de 140 cambio y Bybit dio 10010 cinco
dias). La clave es de SOLO LECTURA y SIN IP: la IP deja de condicionar y la guarda es readOnly. La clave sin IP caduca: el
estado, el parte y Telegram (una vez por umbral, tambien tras reiniciar) lo dicen. Sin red; la carga, con la base de test_bot.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from test_bot import base  # noqa: F401
from test_bot_r8 import _bot

from app.bot import bybit as bb
from app.bot import servicio as sv

AHORA = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


def _clave(**r):
    return {"retCode": 0, "retMsg": "", "result": {"readOnly": 1, **r}}


def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.mark.parametrize("r", [{"ips": ["*"]}, {"ips": []}, {}, {"ips": ["187.190.153.112"]}])
def test_las_tres_formas_de_sin_ip_y_con_ip_activan_la_de_solo_lectura(r):
    j = bb.juzga_clave(_clave(**r))
    assert j["activo"] is True and j["solo_lectura"] is True and j["error"] is None


@pytest.mark.parametrize("r", [{"ips": ["*"]}, {"ips": []}, {}, {"ips": ["187.190.153.112"]}])
def test_la_que_puede_operar_se_apaga_con_ip_o_sin_ella(r):
    j = bb.juzga_clave(_clave(readOnly=0, **r))
    assert j["activo"] is False and j["error"] == "la clave PUEDE OPERAR"


def test_la_guarda_explicita_readonly_0_y_cualquier_ip():
    j = bb.juzga_clave({"retCode": 0, "result": {"readOnly": 0, "ips": ["*"]}})
    assert j["activo"] is False and j["solo_lectura"] is False and "PUEDE OPERAR" in j["error"]


@pytest.mark.parametrize("r", [
    {"deadlineDay": -2, "expiredAt": "1970-01-01T00:00:00Z"},  # el ejemplo de la doc
    {}, {"deadlineDay": 80}, {"expiredAt": ""}, {"expiredAt": None}, {"expiredAt": "manana"},
    {"expiredAt": _iso(AHORA - timedelta(hours=2))},  # ya pasada: una caducada de verdad la rechaza Bybit (33004)
    {"deadlineDay": -2, "expiredAt": _iso(AHORA + timedelta(days=30))},  # negativo contra una fecha futura: no cuadra
])
def test_un_dato_sin_sentido_es_sin_dato_y_no_caducada(r):
    assert bb.caducidad(r, AHORA) is None
    j = bb.juzga_clave(_clave(ips=["*"], **r), AHORA)
    assert j["activo"] is True and j["dias_clave"] is None and j["expira"] is None and j["error"] is None


def test_con_dato_los_dias_y_la_fecha():
    j = bb.juzga_clave(_clave(ips=["*"], deadlineDay=90, expiredAt="2027-02-02T00:00:00Z"), AHORA)
    assert j["dias_clave"] == 91 and j["expira"] == "2027-02-02T00:00:00Z" and j["activo"] is True


def _con_caducidad(bot, dias):
    bot.estado["bybit"] |= {"activo": True, "solo_lectura": True, "expira": _iso(datetime.now(UTC) + timedelta(days=dias))}
    return bot.estado["bybit"]["expira"]


async def test_avisa_una_vez_por_umbral_y_el_mas_urgente_si_cruza_varios():
    bot, textos = _bot()
    expira = _con_caducidad(bot, 20)
    await bot.avisa_caducidad()
    assert textos == [] and bot.estado["bybit"]["dias_clave"] == 19
    bot.estado["bybit"]["expira"] = expira = _iso(datetime.now(UTC) + timedelta(days=13.5))
    await bot.avisa_caducidad()
    await bot.avisa_caducidad()
    assert len(textos) == 1 and "13 dias" in textos[0] and "SIN IP" in textos[0] and "SOLO LECTURA" in textos[0]
    assert bot.clave_avisada == {expira: [14]}
    bot.estado["bybit"]["expira"] = expira = _iso(datetime.now(UTC) + timedelta(days=2.5))  # salta 7 y 3: un aviso, el de 3
    bot.clave_avisada = {expira: [14]}
    await bot.avisa_caducidad()
    await bot.avisa_caducidad()
    assert len(textos) == 2 and "2 dias" in textos[1] and bot.clave_avisada == {expira: [14, 7, 3]}
    bot.estado["bybit"]["expira"] = _iso(datetime.now(UTC) + timedelta(hours=5))
    bot.clave_avisada = {bot.estado["bybit"]["expira"]: [14, 7, 3]}
    await bot.avisa_caducidad()
    assert len(textos) == 3 and "MENOS DE UN DIA" in textos[2]


async def test_sin_dato_sin_cargar_o_sin_entregar_no_marca_ni_avisa():
    bot, textos = _bot()
    await bot.avisa_caducidad()  # sin dato
    bot.cargado = False
    _con_caducidad(bot, 5)
    await bot.avisa_caducidad()  # sin cargar no se sabe que ya se aviso
    assert textos == [] and bot.clave_avisada == {}
    bot.cargado = True

    async def no_entrega(t):
        return False
    bot.manda = no_entrega
    await bot.avisa_caducidad()
    assert bot.clave_avisada == {}  # se reintenta en el proximo tic


async def test_una_clave_renovada_empieza_de_cero():
    bot, textos = _bot()
    bot.clave_avisada = {"2027-02-02T00:00:00Z": [14, 7, 3, 1]}
    expira = _con_caducidad(bot, 10)
    await bot.avisa_caducidad()
    assert len(textos) == 1 and bot.clave_avisada == {expira: [14]}


async def test_tras_reiniciar_no_repite_un_umbral_ya_avisado(base):  # noqa: F811
    textos: list = []

    async def manda(t):
        textos.append(t)
        return True
    bot = sv.Bot({"BOT_INFORMES": "/tmp"}, base, None)
    bot.manda = manda
    expira = _con_caducidad(bot, 6)
    await bot.avisa_caducidad()
    assert len(textos) == 1 and bot.clave_avisada == {expira: [14, 7]}
    await bot.latido()
    otro = sv.Bot({"BOT_INFORMES": "/tmp"}, base, None)
    otro.manda = manda
    await otro.carga()
    assert otro.clave_avisada == {expira: [14, 7]}
    otro.estado["bybit"] |= {"activo": True, "expira": expira}
    await otro.avisa_caducidad()
    assert len(textos) == 1


def test_el_parte_y_estado_dicen_la_caducidad_sin_afirmar_ip():
    bot, _ = _bot()
    ahora = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    s = {"arranque": ahora, "latido": ahora, "validacion": None, "fuentes": {}, "datos": "sin dato", "alertas_24h": {},
         "errores": {}, "ultima_alerta": "ninguna", "gasto_hoy": 0.0, "gasto_ayer": 0.0, "tope": 3.0, "telegram": "ok",
         "informe": "no", "bybit": {"activo": True, "leida": ahora, "tic": ahora, "dias_clave": 40, "expira": "2026-12-12T00:00:00Z"}}
    linea = next(x for x in bot.texto_salud(s, "PARTE").splitlines() if x.startswith("Bybit:"))
    assert "caduca en 40 dias (2026-12-12T00:00:00Z)" in linea and "IP" not in linea
    s["bybit"] |= {"dias_clave": None, "expira": None}
    assert "caducidad de la clave: sin dato" in bot.texto_salud(s, "PARTE")
