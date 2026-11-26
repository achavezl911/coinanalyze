"""MARGEN R1 (V-17): el bot sabe si la posicion va en margen CRUZADO o AISLADO antes de juzgar su liquidacion.

El caso (11-26, primer /evalua real): SOL corto 3 a 71.31, 50x, liqPrice 114.411 de Bybit. La formula de
app/bot/calc.py supone margen AISLADO (a 50x la pondria hacia 72.4); en CRUZADO todo el saldo respalda la posicion y
Bybit la pone lejos. El bot dijo «se separo de Bybit 97.52 % ... no fiable» y Opus «compruebala en Bybit»: la cifra de
Bybit era la buena. Todo con dobles de Bybit, sin red; sin base (el INSERT falla y el mensaje sale igual).
"""

from __future__ import annotations

import time

import asyncpg

from app.bot import bybit as bb
from app.bot import servicio as sv

OPUS = {"texto": "VEREDICTO: A FAVOR\n- la lectura acompana [decide.bias.value]", "error": None, "id": None}
# position/list del caso (cuenta unificada: tradeMode siempre 0, el modo NO va en la posicion)
LISTA = {"retCode": 0, "result": {"list": [{
    "symbol": "SOLUSDT", "side": "Sell", "size": "3", "avgPrice": "71.31", "markPrice": "71.2", "leverage": "50",
    "liqPrice": "114.411", "stopLoss": "72.5", "takeProfit": "", "positionIM": "4.41", "unrealisedPnl": "0.3",
    "tradeMode": 0, "updatedTime": "1795000000000"}]}}
CRUZADA = {"retCode": 0, "result": {"marginMode": "REGULAR_MARGIN", "unifiedMarginStatus": 5}}
AISLADA = {"retCode": 0, "result": {"marginMode": "ISOLATED_MARGIN", "unifiedMarginStatus": 5}}
SIN_PERMISO = {"retCode": 10005, "retMsg": "Permission denied"}
# la validacion que dejo el caso en bot_evento: 97.52 % de la distancia
CASO = {"symbol": "SOLUSDT", "dia": "2026-11-26", "dif_pct": 58.4, "dif_dist_pct": 97.52}
TRAMOS = [{"riskLimitValue": "200000", "maintenanceMargin": "0.01", "mmDeduction": "0"}]


class Base:
    async def execute(self, *a):
        raise asyncpg.InterfaceError("sin base en la prueba")

    async def fetchval(self, *a):
        raise asyncpg.InterfaceError("sin base en la prueba")


class Bybit:
    """El doble de Bybit: cada ruta, su respuesta; apunta las rutas pedidas."""

    def __init__(self, cuenta: dict):
        self.r = {"/v5/account/info": cuenta, "/v5/position/list": LISTA,
                  "/v5/market/risk-limit": {"retCode": 0, "result": {"list": TRAMOS}}}
        self.pedidas: list = []

    async def get(self, ruta, **kw):
        assert ruta in bb.PRIVADAS + bb.PUBLICAS, ruta  # solo lectura: nada fuera de la lista
        self.pedidas.append(ruta)
        return self.r[ruta]


def montado(cuenta: dict, validacion: dict | None = CASO):
    bot, mandados, a_opus = sv.Bot({}, Base(), None), [], []
    bot.bybit = Bybit(cuenta)
    if validacion:
        bot.validaciones["SOLUSDT"] = validacion

    async def sobre(activo):
        return {"generated_at": None}, {"decide": {"bias": {"value": "SHORT"}, "evaluable": {"value": True}}}

    async def opus(ruta, texto):
        a_opus.append(texto)
        return OPUS

    async def manda(texto):
        mandados.append(texto)
        return True
    bot.sobre, bot.opus, bot.manda = sobre, opus, manda
    return bot, mandados, a_opus


def posicion() -> dict:
    (p,) = bb.posiciones(LISTA)
    return p | {"id": "SOLUSDT:Sell:1", "visto": time.time() * 1000}


async def test_cruzado_el_caso_del_dueno_no_dice_no_fiable_y_da_la_de_bybit():
    bot, mandados, a_opus = montado(CRUZADA)
    await bot.evalua(posicion(), "/evalua")
    (m,) = mandados
    assert "no fiable" not in m and "compruebala" not in m, m  # lo que dijo el 11-26
    assert "margen cruzado" in m and "114.411" in m and "todo el saldo" in m, m
    assert '"margen": "cruzado"' in a_opus[0]  # Opus recibe el modo en la POSICION
    assert "cruzado" in sv.ESTABLE and "compruebala" not in sv.ESTABLE  # y sabe que hacer con el


async def test_aislado_compara_con_la_formula_como_hoy():
    bot, mandados, a_opus = montado(AISLADA)
    await bot.evalua(posicion(), "/evalua")
    assert "no fiable" in mandados[0] and "formula:" in mandados[0], mandados  # > 2 %: avisa
    bot, mandados, _ = montado(AISLADA, CASO | {"dif_dist_pct": 0.8})
    await bot.evalua(posicion(), "/evalua")
    assert "validada contra Bybit: 0.80 %" in mandados[0], mandados


async def test_modo_desconocido_se_dice_y_no_se_juzga():
    bot, mandados, a_opus = montado(SIN_PERMISO)
    await bot.evalua(posicion(), "/evalua")
    (m,) = mandados
    assert "no fiable" not in m and "modo de margen desconocido" in m and "114.411" in m, m
    assert '"margen": null' in a_opus[0]


async def test_valida_solo_compara_una_posicion_aislada():
    bot, _, _ = montado(CRUZADA, None)
    await bot.valida(posicion())
    assert "/v5/market/risk-limit" not in bot.bybit.pedidas and not bot.validaciones  # cruzada: nada que validar
    bot, _, _ = montado(SIN_PERMISO, None)
    await bot.valida(posicion())
    assert not bot.validaciones  # desconocido: tampoco
    bot, _, _ = montado(AISLADA, None)
    await bot.valida(posicion())
    assert bot.validaciones["SOLUSDT"]["dif_dist_pct"] is not None  # aislada: como hoy


def test_el_modo_sale_de_la_cuenta_y_un_trademode_1_manda():
    (p,) = bb.posiciones(LISTA)
    assert bb.modo_margen(CRUZADA, p) == ("cruzado", None)
    assert bb.modo_margen({"retCode": 0, "result": {"marginMode": "PORTFOLIO_MARGIN"}}, p) == ("cruzado", None)
    assert bb.modo_margen(AISLADA, p) == ("aislado", None)
    assert bb.modo_margen(CRUZADA, p | {"trade_mode": 1}) == ("aislado", None)  # aislada por simbolo: solo puede ser eso
    modo, motivo = bb.modo_margen(SIN_PERMISO, p)
    assert modo is None and "permiso" in motivo
    assert bb.modo_margen({"retCode": 0, "result": {"marginMode": "OTRO"}}, p)[0] is None
    modo, motivo = bb.modo_margen({"retCode": 0, "result": {"unifiedMarginStatus": 1}}, p)
    assert modo is None and "clasica" in motivo  # cuenta clasica: el tradeMode 0 no se lee como cruzado sin mas
    assert "/v5/account/info" in bb.PRIVADAS
