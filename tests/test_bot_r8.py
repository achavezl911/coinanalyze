"""BOT-2 · remate 8: lo que encontro la quinta validacion fuera del simulador. El interruptor y /estado con Bybit fallando
de forma persistente, sin ningun tic desde el arranque y con una excepcion no prevista en el tic (R2); la lectura cruda
que no aborta el tic (R5); los avisos de stop y de liquidacion por su CONDICION (R6); y las sospechas: los cierres
pendientes antes de cualquier await, el arranque protegido, un try por posicion en los avisos; la CORRECCION de una cifra
tardia con la base de verdad. Cada una cae con el app/bot de claude/bot-r7@50d4c00 por el defecto. Sin red; las de
base, con TEST_DATABASE_URL."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest import mock

import simulador_bot as S
from test_bot import AHORA, base  # noqa: F401
from test_bot_r7 import VIVO, _iso

from app.bot import centinela as cen
from app.bot import servicio as sv
from app.bot import vidas, vigia

TODO_BIEN = dict(unidad=VIVO, monitor=None, base_error=None, latido=AHORA - timedelta(seconds=40), parte_hoy=True,
                 informe_semana=True, falla_informe=None)
ENTORNO = {"BYBIT_API_KEY": "k", "BYBIT_API_SECRET": "s", "BOT_INFORMES": "/tmp"}


class _Bybit:
    """Bybit de mentira: la clave de solo lectura atada a la IP; position/list da `lista` o, con `falla`, un error."""

    def __init__(self, lista=(), falla=False):
        self.lista, self.falla = list(lista), falla

    async def get(self, ruta, **kw):
        if ruta == "/v5/user/query-api":
            return {"retCode": 0, "result": {"readOnly": 1, "ips": [S.IP]}}
        if ruta == "/v5/position/list":
            return {"retCode": 10016, "retMsg": "Server Error"} if self.falla else {"retCode": 0, "result": {"list": self.lista}}
        if ruta == "/v5/position/closed-pnl":
            return {"retCode": 0, "result": {"list": [], "nextPageCursor": ""}}
        if ruta == "/v5/market/risk-limit":
            return {"retCode": 0, "result": {"list": []}}
        raise AssertionError(ruta)


def _pos(symbol="BTCUSDT", side="Buy", entrada=110000.0, u=1793000000000, stop="", marca=None, liq=""):
    return {"symbol": symbol, "side": side, "size": "0.004", "avgPrice": repr(entrada), "markPrice": repr(marca or entrada),
            "leverage": "50", "liqPrice": liq, "stopLoss": stop, "takeProfit": "", "positionIM": "", "unrealisedPnl": "",
            "createdTime": "1792400000000", "updatedTime": str(u)}


def _bot(lista=(), falla=False):
    textos: list = []
    bot = sv.Bot(ENTORNO, S.BaseFalsa([1_793_000_000_000]), None)
    bot.bybit = _Bybit(lista, falla)

    async def manda(t):
        textos.append(t)
        return True
    bot.manda = manda
    bot.evalua = lambda p, m: _nada()  # (sin Opus ni la API: aqui no se mira el veredicto)
    return bot, textos


# ------------------------------------------------------------------------------------------------- R2: el interruptor
def test_sin_ningun_tic_desde_el_arranque_avisa_a_los_5_min_y_no_se_resuelve():
    nunca = {"activo": True, "arranque": _iso(AHORA - timedelta(minutes=9))}
    p = vigia.problemas(AHORA, **TODO_BIEN, bybit=nunca)
    assert list(p) == ["bybit"] and "NINGUNA lectura de Bybit desde que arranco hace 9 min" in p["bybit"]
    assert vigia.problemas(AHORA, **TODO_BIEN, bybit=nunca | {"arranque": _iso(AHORA - timedelta(minutes=2))}) == {}
    # recien arrancado (aun sin tic), Bybit apagado o sin latir: un «bybit» ya avisado NO se da por resuelto
    for b, latido in ((nunca | {"arranque": _iso(AHORA - timedelta(minutes=2))}, TODO_BIEN["latido"]),
                      ({"activo": False, "tic": _iso(AHORA)}, TODO_BIEN["latido"]),
                      ({"activo": True, "tic": _iso(AHORA)}, AHORA - timedelta(minutes=9))):
        inciertos = vigia.sin_juzgar(AHORA, latido, b)
        assert vigia.transicion({"bybit": "x"}, {}, False, frozenset(), inciertos) == ({}, [], []), b
    bien = {"activo": True, "tic": _iso(AHORA - timedelta(minutes=1))}  # solo un tic COMPLETO y reciente lo resuelve
    assert vigia.transicion({"bybit": "x"}, {}, False, frozenset(), vigia.sin_juzgar(AHORA, TODO_BIEN["latido"], bien))[1] == ["bybit"]


async def test_el_tic_sobrevive_a_releer_la_clave():
    """R2: lee_clave sustituia estado["bybit"] entero y BORRABA el tic: el interruptor daba por sano un tic ausente."""
    bot, _ = _bot([_pos()])
    await bot.tic_bybit()
    tic = bot.estado["bybit"]["tic"]
    bot.bybit.falla = True  # Bybit cae de forma persistente
    for _ in range(3):
        bot.clave_proxima = 0.0  # (la relectura de cada hora)
        await bot.tic_bybit()
    assert bot.estado["bybit"].get("tic") == tic and bot.estado["bybit"]["activo"]
    ahora = datetime.now(UTC) + timedelta(minutes=64)  # el «resuelto» falso del validador era en el minuto 64
    b = bot.estado["bybit"] | {"arranque": bot.estado["arranque"]}
    assert "bybit" in vigia.problemas(ahora, **(TODO_BIEN | {"latido": ahora}), bybit=b)
    assert "bybit" in vigia.sin_juzgar(ahora, ahora, b)


async def test_arranque_sin_ningun_tic_y_excepcion_no_prevista_avisan():
    """R2, los otros dos caminos: sin un solo tic completo desde el arranque, y una excepcion que escapa del tic."""
    bot, _ = _bot(falla=True)
    await bot.tic_bybit()
    assert "tic" not in bot.estado["bybit"]
    ahora = datetime.now(UTC) + timedelta(minutes=6)
    b = bot.estado["bybit"] | {"arranque": bot.estado["arranque"]}
    assert "NINGUNA lectura" in vigia.problemas(ahora, **(TODO_BIEN | {"latido": ahora}), bybit=b)["bybit"]
    otro, _ = _bot([_pos()])
    await otro.tic_bybit()
    tic = otro.estado["bybit"]["tic"]
    with mock.patch.object(sv.bb, "posiciones", side_effect=ValueError("respuesta rara")):
        try:
            await otro.tic_bybit()
        except ValueError:
            pass  # (el bucle `cada` lo anota y sigue)
        otro.clave_proxima = 0.0
        try:
            await otro.tic_bybit()
        except ValueError:
            pass
    assert otro.estado["bybit"]["tic"] == tic  # ni completo ni borrado: el interruptor avisa y no lo resuelve


def test_estado_dice_que_no_hubo_ninguna_lectura_completa():
    bot = sv.Bot({}, None, None)
    ahora = datetime.now(UTC)
    s = {"bybit": {"activo": True, "leida": _iso(ahora)}, "validacion": None, "fuentes": {}, "datos": "sin datos",
         "alertas_24h": {}, "errores": {}, "arranque": _iso(ahora - timedelta(minutes=10)), "latido": _iso(ahora),
         "ultima_alerta": None, "gasto_hoy": 0.0, "tope": 3.0, "gasto_ayer": 0.0, "telegram": "ok", "informe": "-"}
    assert "SIN NINGUNA LECTURA COMPLETA DE BYBIT DESDE EL ARRANQUE (HACE 10 MIN)" in bot.texto_salud(s, "ESTADO")
    s["arranque"] = _iso(ahora - timedelta(minutes=1))
    assert "recien arrancado" in bot.texto_salud(s, "ESTADO")


# ------------------------------------------------------------------------------------- R5 y R6: lectura cruda y avisos
def test_una_excepcion_de_la_lectura_cruda_no_aborta_el_tic():
    """R5: crudo_lectura fuera de try; una excepcion que no fuera de la base se llevaba la evaluacion y el cierre."""
    sec = S.Secuencia(nombre="crudo revienta", desfase=0, minutos=8, vidas=[
        S._v(1, "BTCUSDT:Buy", [(0.9, "abre", 0.004, 110000), (4.0, "cierra", 0, 110300)], 0)], esperado={1: "cifra"})

    original = S.BaseFalsa.execute

    async def execute(self, sql, *a):  # una excepcion que NO es de la base, al escribir la lectura cruda (y la de closed-pnl)
        if "bot_crudo" in sql:
            raise RuntimeError("bot_crudo roto")
        return await original(self, sql, *a)
    with mock.patch.object(S.BaseFalsa, "execute", execute):
        s = S.simula(sec, sv)
    assert S.comprueba(s) == [] and [t for _ms, t, _p, _u in s.reg.pagos] == ["evalua"]


async def test_stop_y_liquidacion_se_avisan_una_vez_por_condicion_aunque_cambie_el_updatedtime():
    """R6: por updatedTime se repetian -y el ESCALADO pagado- con cada funding o movimiento del stop."""
    bot, textos = _bot()
    p = {"clave": "BTCUSDT:Buy", "symbol": "BTCUSDT", "lado": 1, "cantidad": 0.004, "entrada": 110000.0, "marca": 109300.0,
         "stop": 109000.0, "liquidacion": None, "actualizada": 1}
    assert [t for _c, t, _x in await bot.seguridad([p])] == ["stop"]
    assert await bot.seguridad([p | {"actualizada": 2}]) == []  # un funding: el mismo stop, nada nuevo
    assert [t for _c, t, _x in await bot.seguridad([p | {"actualizada": 3, "stop": 109050.0}])] == ["stop"]  # stop movido
    q = p | {"stop": 108000.0, "marca": 109000.0, "liquidacion": 108600.0, "actualizada": 4}  # a 0.37 % de la liquidacion
    assert [t for _c, t, _x in await bot.seguridad([q])] == ["liquidacion"]
    assert await bot.seguridad([q | {"actualizada": 5, "liquidacion": 108620.0}]) == []  # la misma banda
    assert [t for _c, t, _x in await bot.seguridad([q | {"actualizada": 6, "marca": 108800.0}])] == ["liquidacion"]  # mas cerca
    assert len([t for t in textos if "stop" in t or "liquidacion" in t]) == 4


async def test_una_posicion_que_hace_lanzar_a_los_avisos_no_calla_a_las_demas():
    bot, textos = _bot()
    original = cen.alertas_posicion

    def alertas(p):
        if p["symbol"] == "BTCUSDT":
            raise ZeroDivisionError("una posicion rara")
        return original(p)
    lista = [sv.bb.posiciones({"result": {"list": [_pos(), _pos("ETHUSDT", "Sell", 3900.0)]}})][0]
    with mock.patch.object(cen, "alertas_posicion", alertas):
        await bot.seguridad(lista)
    assert any("ETHUSDT CORTO sin stop" in t for t in textos) and "seguridad" in json.dumps(bot.estado["errores"])


# ---------------------------------------------------------------------------------------------------- las sospechas
async def test_los_cierres_pendientes_se_apuntan_antes_de_cualquier_await():
    """Un latido en la ventana entre decide y los cierres (aqui, dentro del primer await: valida) guardaba el libro ya
    sin la vida puntuada y sin su CERRADA pendiente: un reinicio la perdia para siempre."""
    i = "BTCUSDT:Buy:1792999000000"
    bot, _ = _bot([_pos("ETHUSDT", "Sell", 3900.0)])
    bot.evaluadas[i] = {"veredicto": "A FAVOR", "posicion": {"clave": "BTCUSDT:Buy"}}
    res = {"pnl": 1.5, "ordenes": ["o-1"], "nota": None, "tramos": 1}
    original = vidas.Libro.calcula

    def calcula(self, ahora):
        cambios, out = original(self, ahora)
        out["resultados"].append((i, res))
        return cambios, out

    async def valida(self, p):  # el latido de tic_minuto, colado en el await
        await self.latido()
    original_d = vidas.Libro.decide

    def decide(self, ahora):  # (el bot de R7 llamaba a decide: asi cae por el defecto y no por el nombre)
        out = original_d(self, ahora)
        out["resultados"].append((i, res))
        return out
    with mock.patch.object(vidas.Libro, "calcula", calcula), mock.patch.object(vidas.Libro, "decide", decide), \
            mock.patch.object(sv.Bot, "valida", valida), mock.patch.object(sv.Bot, "cierre", lambda self, i, r: _nada()):
        await bot.tic_bybit()
    assert json.loads(bot.db.estado[1])["cierres_pendientes"] == {i: res}


async def test_el_arranque_sin_estado_avisa_de_seguridad_y_no_paga_hasta_cargarlo():
    bot, textos = _bot([_pos()])
    with mock.patch.object(sv.Bot, "carga", side_effect=OSError("la base no contesta")), \
            mock.patch.object(sv.Bot, "cada", lambda self, n, p, f: _nada()):
        await bot.corre()  # antes: la excepcion de carga tumbaba el arranque (y systemd lo reintentaba sin avisar de nada)
    assert bot.cargado is False and "ESTADO carga" in bot.estado["errores"]
    pagos: list = []
    with mock.patch.object(sv.Bot, "carga", side_effect=OSError("la base no contesta")), \
            mock.patch.object(sv.Bot, "evalua_una", lambda self, p, m: _apunta(pagos, p)):
        await bot.tic_bybit()
    assert any("BTCUSDT LARGO sin stop" in t for t in textos) and pagos == []  # la seguridad si; pagar, no
    with mock.patch.object(sv.Bot, "evalua_una", lambda self, p, m: _apunta(pagos, p)):
        await bot.tic_bybit()  # la base vuelve: carga y sigue
        while bot.tareas:  # (la evaluacion sale en su tarea)
            await asyncio.gather(*list(bot.tareas))
    assert bot.cargado is True and len(pagos) == 1


async def test_un_estado_que_revienta_al_leerlo_no_impide_arrancar():
    bot, _ = _bot()
    with mock.patch.object(vidas.Libro, "desde", side_effect=TypeError("'NoneType' object is not subscriptable")):
        await bot.carga()
    assert isinstance(bot.libro, vidas.Libro) and not bot.libro.claves and "ESTADO carga" in bot.estado["errores"]


async def _nada():
    return None


async def _apunta(pagos, p):
    pagos.append(p["id"])


# ------------------------------------------------------------------------------------ la cifra tardia, con la base
def test_una_fila_que_llega_despues_de_la_cerrada_la_corrige():
    """Punto 7: un parcial de ANTES de la primera lectura llega a closed-pnl 60 min tarde (S2 roto); la CERRADA sale con la
    cifra de lo que se vio (incompleta: el validador la vio salir como buena) y, al llegar la fila, la CORRECCION la retira
    -a tiempo habria sido A6P: un parcial suyo o una vida igual que no vio-. La ultima palabra nunca es una cifra falsa."""
    sec = S.Secuencia(nombre="parcial tardio", desfase=0, minutos=8, vidas=[
        S._v(1, "BTCUSDT:Buy", [(0.9, "abre", 0.006, 110000), (1.1, "parcial", 0.002, 110500), (4.0, "cierra", 0, 110300)], 0,
             retrasos={0: 60 * S.M})])
    s = S.simula(sec, sv)
    assert S.comprueba(s) == []
    cierres = [e for e in s.base.evaluacion if e["tipo"] == "cierre"]
    assert len(cierres) == 2 and cierres[1]["detalle"]["correccion"]["orden"] == "o1-1" and cierres[1]["pnl"] is None
    assert cierres[0]["pnl"] is not None and abs(cierres[0]["pnl"] - sec.vidas[0].pnl) > 0.1  # la incompleta
    assert [t.split("\n")[0] for _ts, t in s.reg.textos if t.startswith("CORRECCION")] == \
        [f"CORRECCION BTCUSDT LARGO: {cierres[0]['pnl']:+.2f} -> sin puntuar · el veredicto era {cierres[0]['veredicto']} -> sin puntuar"]


async def test_la_correccion_se_apunta_una_vez_y_la_semana_cuenta_la_ultima_cifra(base):  # noqa: F811
    i = "BTCUSDT:Buy:1792400000000"
    await base.execute("INSERT INTO bot_evaluacion (tipo, posicion, veredicto, detalle) VALUES ('veredicto', $1, 'A FAVOR', '{}')", i)
    await base.execute("INSERT INTO bot_evaluacion (tipo, posicion, veredicto, pnl_usd, acierto, detalle) VALUES"
                       " ('cierre', $1, 'A FAVOR', 1.0, true, '{\"ordenes\": [\"o-2\"], \"nota\": null}')", i)
    textos: list = []

    async def manda(t):
        textos.append(t)
        return True
    bot = sv.Bot({}, base, None)
    bot.manda = manda
    c = {"id": i, "pnl": None, "pnl_antes": 1.0, "orden": "o-1", "ordenes": ["o-2", "o-1"],
         "nota": "ambigua: T: llego tarde a closed-pnl la orden o-1 (S2 roto): la cifra +1.0000 no se sabe"}
    bot.correcciones_pendientes["k"] = c
    await bot.correccion("k", c)
    await bot.correccion("k", c)  # (un reinicio que la creyera pendiente: no se repite)
    filas = await base.fetch("SELECT pnl_usd, acierto, detalle FROM bot_evaluacion WHERE tipo = 'cierre' ORDER BY ts")
    assert [(f[0], f[1]) for f in filas] == [(1.0, True), (None, None)] and json.loads(filas[1][2])["correccion"]["orden"] == "o-1"
    assert len(textos) == 1 and textos[0].startswith("CORRECCION BTCUSDT LARGO: +1.00 -> sin puntuar") and "ambigua: T" in textos[0]
    ev = (await bot.cifras_semana())["evaluaciones"]  # una vida, con su ULTIMA cifra: ya no cuenta como acierto
    assert ev["cerradas"] == 1 and ev["puntuadas"] == 0 and bot.correcciones_pendientes == {}
    for o in ("o-1", "o-2"):
        await base.execute("INSERT INTO bot_operacion (orden, symbol, cantidad, entrada, salida, pnl_usd, cerrada, detalle)"
                           " VALUES ($1, 'BTCUSDT', 0.002, 110000, 110300, 0.5, now() - interval '1 hour', '{}')", o)
    otro = sv.Bot({}, base, None)  # al arrancar, las ordenes de la CERRADA y de la correccion son usadas: fuera de las vidas
    await otro.carga()
    assert {"o-1", "o-2"} <= set(otro.libro.ordenes) and not any(otro.libro.filas.values())
