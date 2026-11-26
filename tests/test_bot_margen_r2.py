"""MARGEN R2 (resto de V-17): una validacion VIEJA de la liquidacion no se arrastra si el modo de margen no la respalda.

La validacion de SOL del 11-26 (97.52 %) se hizo con la formula AISLADA sobre una posicion CRUZADA y quedo en bot_evento
sin modo: al arrancar se carga y /calc o el /evalua de una posicion aislada seguian diciendo «no fiable» con ella. Una
validacion solo cuenta si se hizo en aislado Y la cuenta sigue en aislado. Todo con dobles: ni red ni filas del dueno.
"""

from __future__ import annotations

import json
from datetime import date

import httpx

from app.bot import servicio as sv
from tests.test_bot_margen import AISLADA, CASO, CRUZADA, TRAMOS, montado, posicion

CON_MODO = CASO | {"modo_margen": "aislado"}


async def test_evalua_aislada_no_usa_una_validacion_sin_modo_ni_de_otro_modo():
    for v in (CASO, CASO | {"modo_margen": "cruzado"}):
        bot, mandados, _ = montado(AISLADA, v)
        await bot.evalua(posicion(), "/evalua")
        (m,) = mandados
        assert "no fiable" not in m and "validada" not in m and "sin validar" in m, (v, m)


async def test_evalua_aislada_con_validacion_aislada_como_hoy():
    bot, mandados, _ = montado(AISLADA, CON_MODO)
    await bot.evalua(posicion(), "/evalua")
    assert "no fiable" in mandados[0], mandados
    bot, mandados, _ = montado(AISLADA, CON_MODO | {"dif_dist_pct": 0.8})
    await bot.evalua(posicion(), "/evalua")
    assert "validada contra Bybit: 0.80 %" in mandados[0], mandados


def _publica(r: httpx.Request) -> httpx.Response:
    lista = {"/v5/market/risk-limit": TRAMOS,
             "/v5/market/instruments-info": [{"lotSizeFilter": {"qtyStep": "0.1"}, "fundingInterval": 480}],
             "/v5/market/tickers": [{"fundingRate": "0.0001"}]}[r.url.path]
    return httpx.Response(200, json={"retCode": 0, "result": {"list": lista}})


async def _calc(cuenta: dict, v: dict) -> str:
    bot, _, _ = montado(cuenta, v)
    bot.http = httpx.AsyncClient(transport=httpx.MockTransport(_publica))
    bot.estado["validacion"] = v
    return await bot.calcula("/calc sol 150 149")


async def test_calc_solo_usa_la_validacion_si_su_modo_es_aislado_y_el_de_la_cuenta_tambien():
    for cuenta, v in ((AISLADA, CASO), (CRUZADA, CASO), (CRUZADA, CON_MODO), (AISLADA, CASO | {"modo_margen": "cruzado"})):
        t = await _calc(cuenta, v)
        assert "no fiable" not in t and "validada" not in t and "sin validar" in t, (cuenta, v, t)
    assert "no fiable" in await _calc(AISLADA, CON_MODO)  # aislada sobre aislada: como hoy


class _Base:
    """bot_evento con dos validaciones de SOL: la del 11-26 sin modo y, en ADA, una aislada. Lo demas, vacio."""

    def __init__(self):
        self.filas = [({"posicion": "SOLUSDT:Sell:1", "symbol": "SOLUSDT", "dif_pct": 58.4, "dif_dist_pct": 97.52}, date(2026, 11, 26)),
                      ({"posicion": "ADAUSDT:Buy:1", "symbol": "ADAUSDT", "dif_pct": 0.1, "dif_dist_pct": 0.8,
                        "modo_margen": "aislado"}, date(2026, 11, 20))]

    async def fetch(self, sql, *a):
        if "tipo = 'validacion'" not in sql:
            return []
        filas = [(d, dia) for d, dia in self.filas  # el filtro del WHERE por el modo, si lo lleva
                 if "modo_margen' = 'aislado'" not in sql or d.get("modo_margen") == "aislado"]
        if "DISTINCT ON" in sql:
            return [{"detalle": json.dumps(d), "d": dia} for d, dia in filas]
        return [(d["posicion"],) for d, _ in filas]

    async def fetchval(self, *a):
        return None

    async def fetchrow(self, *a):
        return None


async def test_al_arrancar_la_validacion_sin_modo_no_se_carga_y_no_se_toca():
    bot = sv.Bot({}, _Base(), None)
    filas = json.dumps(bot.db.filas, default=str)
    await bot.carga()
    assert "SOLUSDT" not in bot.validaciones, bot.validaciones  # la del 11-26 se ignora por regla
    assert bot.validaciones["ADAUSDT"]["modo_margen"] == "aislado" and bot.estado["validacion"]["symbol"] == "ADAUSDT"
    assert "SOLUSDT:Sell:1" not in bot.validadas  # su posicion, si fuera aislada, se vuelve a validar con modo
    assert json.dumps(bot.db.filas, default=str) == filas  # nada borrado ni reescrito
