"""BOT-2 · remate 9: sin cargar no se pisa nada. Desde R8, si carga() fallaba al arrancar el bot seguia vivo con el libro
VACIO, y el latido lo escribia encima de bot_estado: la carga posterior leia lo pisado (vidas sin su historia, CERRADAS
pendientes que no salian nunca). Y con parte_hoy e informes_enviados sin cargar, el parte y el informe salian otra vez.
Cada prueba cae con el app/bot de claude/bot-r8@977ca59 por el defecto (x1-tmp/bot2/r9-viejo-t.sh). El arranque, por los
dos caminos: la base caida que vuelve y un KeyError en carga() con la base contestando. Sin red; la de SQL, con
TEST_DATABASE_URL."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest import mock

from test_bot import base  # noqa: F401
from test_bot_r8 import _bot, _nada, _pos

from app.bot import servicio as sv
from app.bot import vidas


def _guardado(bot) -> dict:
    return {k: v for k, v in json.loads(bot.db.estado[1]).items() if k in ("libro", "cierres_pendientes", "correcciones_pendientes")}


async def _con_estado():
    """Un bot que ya vivio: una posicion en su libro, evaluada, con su CERRADA pendiente; y su latido guardado."""
    bot, _ = _bot([_pos()])
    with mock.patch.object(sv.Bot, "valida", lambda self, p: _nada()), \
            mock.patch.object(sv.Bot, "evalua_una", lambda self, p, m: _nada()):
        await bot.tic_bybit()
    (i, p), = bot.pos.items()
    bot.db.evaluacion.append({"ts": bot.db.reloj[0], "tipo": "veredicto", "posicion": i, "veredicto": "a favor",
                              "detalle": {"motivo": "posicion nueva", "posicion": p}})
    bot.cierres_pendientes[i] = {"pnl": 12.5, "ordenes": ["o-1"], "nota": "cerrada"}
    await bot.latido()
    antes = _guardado(bot)
    assert antes["libro"]["claves"] and len(antes["cierres_pendientes"]) == 1
    return bot.db, antes


def _carga_lee():
    """Lo que carga() lee de bot_estado (lo que recibe Libro.desde), sin cambiar lo que hace con ello."""
    leido: list = []
    original = vidas.Libro.desde.__func__

    def desde(cls, guardado, *a, **k):
        leido.append({x: guardado.get(x) for x in sv.GUARDADO if x in guardado} if isinstance(guardado, dict) else guardado)
        return original(cls, guardado, *a, **k)
    return leido, mock.patch.object(vidas.Libro, "desde", classmethod(desde))


def _otro(db, lista=()):
    """El mismo bot tras un reinicio: su base, la misma."""
    bot, textos = _bot(lista)
    bot.db = db
    return bot, textos


async def _arranca(bot, error):
    with mock.patch.object(sv.Bot, "carga", side_effect=error), mock.patch.object(sv.Bot, "cada", lambda self, n, p, f: _nada()), \
            mock.patch.object(sv.Bot, "salud", lambda self: _nada()), mock.patch.object(sv.Bot, "texto_salud", lambda self, s, t: t):
        await bot.corre()
    assert bot.cargado is False


def _minuto():  # tic_minuto sin centinela, parte ni informe (esos, aparte)
    return mock.patch.multiple(sv.Bot, tic_centinela=lambda self: _nada(), tic_parte=lambda self: _nada(),
                               tic_informe=lambda self: _nada())


async def test_keyerror_en_carga_con_la_base_contestando_el_latido_no_pisa_y_la_carga_recupera_identico():
    db, antes = await _con_estado()
    bot, _ = _otro(db)
    await _arranca(bot, KeyError("una clave que carga no esperaba"))
    db.reloj[0] += 60_000
    with mock.patch.object(sv.Bot, "carga", side_effect=KeyError("otra vez")), _minuto():
        await bot.tic_minuto()  # antes: libro {} y cierres_pendientes {} encima de lo guardado
    assert db.estado[0] == db.reloj[0]  # el latido sale, con su hora
    escrito = json.loads(db.estado[1])
    assert "ESTADO carga" in escrito["errores"] and escrito["cargado"] is False  # y sus errores
    assert _guardado(bot) == antes
    db.reloj[0] += 60_000
    leido, espia = _carga_lee()
    with _minuto(), espia:
        await bot.tic_minuto()  # carga() vuelve a ir: recupera lo que habia
    assert bot.cargado is True and leido == [antes] and set(bot.libro.claves) == set(antes["libro"]["claves"])
    assert bot.cierres_pendientes == antes["cierres_pendientes"]


async def test_la_base_caida_que_vuelve_carga_antes_del_latido():
    db, antes = await _con_estado()
    bot, _ = _otro(db)
    db.caida = (0, 10**15)
    await _arranca(bot, OSError("connection refused (postgresql 5432)"))  # (como la de verdad: la base no contesta)
    with _minuto():
        await bot.tic_minuto()  # el latido tampoco entra
    db.caida = None
    db.reloj[0] += 60_000
    leido, espia = _carga_lee()
    with _minuto(), espia:
        await bot.tic_minuto()  # la base vuelve; antes: este latido, sin carga, pisaba lo guardado
        await bot.tic_bybit()  # (y la carga que sigue lee lo de antes)
    assert bot.cargado is True and leido[0] == antes and not bot.cierres_pendientes
    (i, res), = antes["cierres_pendientes"].items()  # la CERRADA pendiente sale, una vez
    assert [e["pnl"] for e in db.evaluacion if e["tipo"] == "cierre" and e["posicion"] == i] == [res["pnl"]]


async def test_con_bybit_apagado_la_carga_se_reintenta_en_el_minuto():
    db, antes = await _con_estado()
    bot, _ = _otro(db)
    await _arranca(bot, KeyError("x"))
    bot.bybit = None  # tic_bybit sale antes de reintentar: sin el minuto, el parte esperaria para siempre
    leido, espia = _carga_lee()
    with _minuto(), espia:
        await bot.tic_minuto()
    assert bot.cargado is True and leido == [antes]


async def test_sin_cargar_ni_parte_ni_informe_salen_otra_vez(tmp_path):
    db, _ = await _con_estado()
    bot, textos = _otro(db)
    bot.informes = str(tmp_path)
    (tmp_path / f"{sv.semana_iso(datetime.now(UTC))}.txt").write_text("el informe de la semana", encoding="utf-8")
    await _arranca(bot, KeyError("x"))
    with mock.patch.object(sv, "PARTE_HORA_UTC", 0), mock.patch.object(sv.Bot, "salud", lambda self: _nada()), \
            mock.patch.object(sv.Bot, "texto_salud", lambda self, s, t: t):
        await bot.tic_parte()
        await bot.tic_informe()
    assert not [t for t in textos if t.startswith(("PARTE", "INFORME SEMANAL"))], textos


async def test_sin_cargar_evalua_lo_dice_y_estado_no_inventa_el_informe():
    bot, _ = _bot([_pos()])
    await _arranca(bot, KeyError("x"))
    bot.estado["bybit"]["activo"] = True
    r = await bot.atiende("/evalua BTC")
    assert "no esta cargado" in r, r  # antes: «no hay posicion abierta que evaluar», con una abierta
    assert "no se sabe" in bot.estado_informe()  # antes: «todavia no», sin haber leido los enviados


async def test_la_consulta_del_latido_en_postgres_guarda_lo_suyo_sin_cargar(base):  # noqa: F811
    bot = sv.Bot({"BOT_INFORMES": "/tmp"}, base, None)
    bot.cierres_pendientes = {"BTCUSDT:Buy:1": {"pnl": 1.0, "ordenes": ["o"], "nota": "n"}}
    await bot.latido()
    antes = json.loads(await base.fetchval("SELECT estado::text FROM bot_estado WHERE clave = 'bot'"))
    otro = sv.Bot({"BOT_INFORMES": "/tmp"}, base, None)
    otro.cargado = False
    otro.anota("ESTADO", "no pude cargar", "carga")
    await otro.latido()
    d = json.loads(await base.fetchval("SELECT estado::text FROM bot_estado WHERE clave = 'bot'"))
    assert {k: d.get(k) for k in sv.GUARDADO} == {k: antes[k] for k in sv.GUARDADO}
    assert "ESTADO carga" in d["errores"] and d["cargado"] is False and d["arranque"] == otro.estado["arranque"]
    await base.execute("UPDATE bot_estado SET estado = '[1, 2]'::jsonb WHERE clave = 'bot'")  # lo que no se entiende, entero
    await otro.latido()
    assert await base.fetchval("SELECT estado::text FROM bot_estado WHERE clave = 'bot'") == "[1, 2]"
