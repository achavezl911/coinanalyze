"""BOT-2 · remate 5: una prueba por regresion de R4 que encontro la segunda validacion independiente, con sus escenarios
(caida + otra vida cerrada mientras; lista vacia una vez con updatedTime cambiado; /estado detras de una pregunta a Opus;
parcial con la hora de Bybit 500 ms despues de la lectura; bot_estado mal formado), y por cada sospecha que resulto real.
Cada una cae con app/bot de main@3164640 POR EL DEFECTO (x1-tmp/bot2/r5-viejo.sh). Sin red; las de base, con
TEST_DATABASE_URL."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import asyncpg
from test_bot import _EnFila, _espera, base  # noqa: F401
from test_bot_r3 import ENTORNO, _mundo, _op, _pos
from test_bot_r4 import M, _cierres, _t0, _tic, _veredictos

from app.bot import servicio as sv


async def _sin_stop(db) -> int:
    return await db.fetchval("SELECT count(*) FROM bot_evento WHERE tipo = 'sin_stop'")


async def test_reg1_tras_una_caida_la_evaluada_puntua_solo_hasta_su_cierre(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)]], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)
    await bot.latido()
    # el bot cae; mientras, la evaluada cierra (+1.0) y otra del mismo simbolo y lado abre y cierra a otra entrada (-2.5)
    ops += [_op("suya", 110000, 110300, 1.0, t0 + 2 * M), _op("otra", 111000, 110400, -2.5, t0 + 5 * M)]
    otro = sv.Bot(ENTORNO, db, _mundo([[]], ops, cuenta))
    await otro.carga()
    for k in (10, 11):
        await _tic(otro, monkeypatch, t0 + k * M + 20_000)
    monkeypatch.undo()
    ids = await _veredictos(db)
    assert await _cierres(db) == {ids[0]: 1.0}  # antes: -1.5 (las dos sumadas) y FALLO de un A FAVOR que acerto


async def test_reg2_una_lista_vacia_una_vez_no_cierra_la_posicion(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    con_stop = _pos(110000, t0 + 2 * M + 10_000, stopLoss="109400")  # Alejandro le puso el stop: otro updatedTime
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [], [con_stop]], ops, cuenta))
    for k in (1, 2, 3, 3 + 125):  # la lista vacia UNA vez (retCode 0); y 2 h despues sigue abierta
        await _tic(bot, monkeypatch, t0 + k * M + 20_000)
    monkeypatch.undo()
    assert cuenta.get("messages") == 1 and len(await _veredictos(db)) == 1  # antes: id nuevo y otra evaluacion pagada
    assert await _sin_stop(db) == 1  # (el de la primera lectura; antes: avisos repetidos con el id nuevo)
    assert await _cierres(db) == {} and not any("CERRADA" in t for t in cuenta.get("textos", []))  # antes: «sin puntuar» falso


async def test_reg3_lo_que_no_va_a_opus_contesta_al_momento():
    bot = sv.Bot({"TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "42"}, None, None)
    enviadas: list = []

    async def recibe():
        return ["como esta btc", "/entrada", "y eth?"]

    async def atiende(t):
        if t == "/entrada":
            return sv.ENTRADAS
        if t == "como esta btc":
            await asyncio.sleep(0.05)  # Opus tarda
        return f"Opus: {t}"

    async def manda(t):
        enviadas.append(t)
        return True
    bot.tg.recibe, bot.atiende, bot.manda = recibe, atiende, manda
    await bot.tic_telegram()
    await _espera(bot)
    # /entrada no espera a Opus (antes: detras de la pregunta, hasta su timeout); las dos preguntas, en su orden
    assert enviadas == [sv.ENTRADAS, "Opus: como esta btc", "Opus: y eth?"]


async def test_reg4_la_hora_de_bybit_un_poco_adelantada_no_parte_la_posicion(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [_pos(110000, t0, size="0.002")]], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)  # 0.004
    await _tic(bot, monkeypatch, t0 + 2 * M + 20_000)  # ya se ve 0.002: el parcial ocurrio; closed-pnl aun no lo trae
    ops.append(_op("parcial", 110000, 110450, 0.9, t0 + 2 * M + 20_500) | {"closedSize": "0.002"})  # hora de Bybit: 500 ms DESPUES
    await _tic(bot, monkeypatch, t0 + 3 * M + 20_000)  # sigue abierta, 0.002
    monkeypatch.undo()
    assert len(await _veredictos(db)) == 1 and cuenta.get("messages") == 1  # antes: la partia en dos y pagaba otra evaluacion
    assert await _cierres(db) == {}


async def test_reg5_un_estado_mal_formado_no_tumba_al_bot(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, cuenta = _t0(), {}
    db = _EnFila(base)
    await db.execute("INSERT INTO bot_estado VALUES ('bot', now(), $1::jsonb)", sv.js({"vidas": {"BTCUSDT:Buy": {"id": f"BTCUSDT:Buy:{t0}"}}}))
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)]], [], cuenta))
    await bot.carga()
    caidas = []
    for k in (1, 2):  # como el bucle real (cada)
        try:
            await _tic(bot, monkeypatch, t0 + k * M + 20_000)
        except Exception as e:
            caidas.append(repr(e)[:80])
    monkeypatch.undo()
    assert caidas == [] and len(await _veredictos(db)) == 1, caidas  # antes: KeyError 'obs' en cada tic, para siempre
    assert any("descarto la vida BTCUSDT:Buy" in x["texto"] for x in bot.estado["errores"].values())  # y se dice


async def test_reg5_unas_vidas_que_no_son_un_diccionario_no_impiden_arrancar(base):  # noqa: F811 - el fixture `base` de test_bot
    await base.execute("INSERT INTO bot_estado VALUES ('bot', now(), $1::jsonb)", sv.js({"vidas": ["no es un diccionario"]}))
    bot = sv.Bot(ENTORNO, base, None)
    await bot.carga()  # antes: AttributeError y el bot no arrancaba
    assert any("vidas" in x["texto"] for x in bot.estado["errores"].values())


async def test_sospecha_el_plan_b_no_pega_una_posicion_nueva_a_una_vieja(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [_pos(110300, t0, size="0.008")], []], ops, cuenta))
    for k in (1, 2, 3, 4):  # abierta, promediada (0.008 a 110300) y cerrada; closed-pnl todavia no trae su cierre
        await _tic(bot, monkeypatch, t0 + k * M + 20_000)
    await bot.latido()  # cae esperando la fila de su cierre
    ops.append(_op("suya", 110300, 110800, 4.0, t0 + 2 * M + 40_000) | {"closedSize": "0.008"})
    nueva = _pos(111500, t0 + 6 * M)  # mientras, Alejandro abre OTRA en BTC largo, sin stop
    otro = sv.Bot(ENTORNO, db, _mundo([[nueva]], ops, cuenta))
    await otro.carga()
    await _tic(otro, monkeypatch, t0 + 10 * M + 20_000)
    await _tic(otro, monkeypatch, t0 + 14 * M + 20_000)  # R6: se puntua tras ESPERA desde su primera lectura
    monkeypatch.undo()
    ids = await _veredictos(db)
    # antes: el plan B la daba por ABIERTA (no estaba en las vidas) y la nueva quedaba pegada, sin evaluar ni avisar
    assert len(set(ids)) == 2 and await _sin_stop(db) == 2, ids
    assert await _cierres(db) == {ids[0]: 4.0}


class _FallaEth(_EnFila):
    """La base que no apunta la fila eth-1 de closed-pnl (operaciones() cae a mitad, despues de apuntar la de BTC)."""

    def __getattr__(self, k):
        f = super().__getattr__(k)

        async def g(sql, *a, **kw):
            if isinstance(sql, str) and "INSERT INTO bot_operacion" in sql and a and a[0] == "eth-1":
                raise asyncpg.UntranslatableCharacterError("la fila no entra")
            return await f(sql, *a, **kw)
        return g


async def test_sospecha_operaciones_que_cae_a_mitad_no_deja_sin_chequeo_de_reapertura(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    nueva = _pos(110150, t0 + M + 50_000)
    bot = sv.Bot(ENTORNO, _FallaEth(base), _mundo([[_pos(110000, t0)], [nueva]], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)
    ops += [_op("cierre", 110000, 110300, 1.0, t0 + M + 40_000),  # cerrada entera y reabierta en el mismo minuto...
            _op("eth-1", 3900, 3950, 0.2, t0 + M + 45_000) | {"symbol": "ETHUSDT"}]  # ... y una fila de ETH que no entra
    for k in (2, 3):
        await _tic(bot, monkeypatch, t0 + k * M + 20_000)
    monkeypatch.undo()
    assert len(set(await _veredictos(base))) == 2  # antes: la fila de BTC quedaba «vista» y la reapertura no se miraba nunca


async def test_sospecha_los_errores_por_id_no_se_acumulan(base):  # noqa: F811 - el fixture `base` de test_bot
    bot = sv.Bot({}, base, None)
    hace_2h = (datetime.now(UTC) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for k in range(50):
        bot.anota("KEYERROR", f"evalua BTCUSDT:Buy:{k}: KeyError", f"evalua BTCUSDT:Buy:{k}")
        bot.estado["errores"][f"KEYERROR evalua BTCUSDT:Buy:{k}"]["resuelto"] = hace_2h  # resueltos: ya no se ensenan
    await bot.latido()
    estado = json.loads(await base.fetchval("SELECT estado FROM bot_estado WHERE clave = 'bot'"))
    assert estado["errores"] == {}  # antes: 50 claves que el estado arrastraba para siempre


def test_sospecha_configuracion_no_caduca_mientras_sigue():
    errores = {"CONFIGURACION configuracion": {"ultima": "2026-10-26T06:00:00Z", "texto": "BOT_EFFORT_ESCALA='max' no vale en tiempo real: uso low",
                                               "resuelto": None, "op": "configuracion"}}
    v = sv.errores_vigentes(errores, datetime(2026, 10, 26, 13, 30, tzinfo=UTC))
    assert "BOT_EFFORT_ESCALA" in v and "caducado" not in v  # antes: caducada a las 6 h con el error en pie
