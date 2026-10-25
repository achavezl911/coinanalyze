"""BOT-2 · remate 4: una prueba por regresion de R3 que encontro la validacion independiente, con sus escenarios (parcial +
anadido, reapertura a +-0.2 % con y sin el cierre ya en closed-pnl, promedio + cierre, reinicio tras promediar, base caida
3 min al abrir, cobertura con entradas cercanas), y por cada sospecha que resulto real. Cada una cae con app/bot de
main@f9c2621 POR EL DEFECTO (x1-tmp/bot2/r4-viejo.sh). Sin red: Bybit, la API local, Anthropic y Telegram de mentira. Las
de base, con TEST_DATABASE_URL (si no, se saltan). Cada lectura de Bybit va con su reloj: las operaciones de closed-pnl se
asignan a la vida de la posicion por su hora."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx
import pytest
from test_bot import _EnFila, _espera, base  # noqa: F401
from test_bot_r3 import ENTORNO, _mundo, _op, _pos, _SinRegistro

from app.bot import calidad
from app.bot import servicio as sv

M = 60_000


def _t0() -> int:
    return int(time.time() * 1000) // M * M - 3600_000


async def _tic(bot, monkeypatch, ms: int):
    monkeypatch.setattr(sv.time, "time", lambda: ms / 1000)
    await bot.tic_bybit()
    await _espera(bot)


async def _veredictos(db) -> list:
    return [r[0] for r in await db.fetch("SELECT posicion FROM bot_evaluacion WHERE tipo = 'veredicto' ORDER BY ts")]


async def _cierres(db) -> dict:
    return {r[0]: r[1] for r in await db.fetch("SELECT posicion, pnl_usd FROM bot_evaluacion WHERE tipo = 'cierre'")}


async def test_r10_un_parcial_y_un_anadido_son_la_misma_posicion(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [_pos(110500, t0 + 2 * M, size="0.006")], []], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)  # abierta: 0.004 a 110000
    ops.append(_op("parcial", 110000, 110450, 0.9, t0 + M + 30_000) | {"closedSize": "0.002"})  # cierra la mitad (+0.90)
    await _tic(bot, monkeypatch, t0 + 2 * M + 20_000)  # ... y anade 0.004 a 110750: 0.006 a 110500 (+0.45 %)
    ops.append(_op("final", 110500, 110300, -1.4, t0 + 2 * M + 40_000) | {"closedSize": "0.006"})
    await _tic(bot, monkeypatch, t0 + 3 * M + 20_000)  # cerrada entera
    await _tic(bot, monkeypatch, t0 + 13 * M + 20_000)  # R6: se puntua tras ESPERA desde su primera lectura
    monkeypatch.undo()
    textos = cuenta.get("textos", [])
    ids = await _veredictos(db)
    assert len(ids) == 1 and cuenta.get("messages") == 1, (ids, cuenta.get("messages"))  # antes: otro id y otra evaluacion pagada
    assert not any("+0.90" in t for t in textos)  # antes: «CERRADA BTCUSDT: +0.90 USD · ... ACIERTO» con la posicion abierta
    assert await _cierres(db) == {ids[0]: pytest.approx(-0.5)}  # el parcial y el final, de la misma vida


@pytest.mark.parametrize("tarde", [False, True], ids=["cierre-ya-en-closed-pnl", "cierre-una-lectura-despues"])
async def test_r1_cerrada_y_reabierta_en_el_mismo_minuto_son_dos_posiciones(base, monkeypatch, tarde):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    nueva = _pos(110150, t0 + M + 50_000)  # +0.14 %: dentro del 0.2 % con el que R3 decidia «la misma»; sin stop
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [nueva]] + ([[nueva]] if tarde else []) + [[]], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)
    cierre = _op("cierre", 110000, 110300, 1.0, t0 + M + 40_000)  # la cierra entera (+1.0) y abre otra en el mismo minuto
    if not tarde:
        ops.append(cierre)
    await _tic(bot, monkeypatch, t0 + 2 * M + 20_000)
    k = 2
    if tarde:  # closed-pnl la trae una lectura despues
        ops.append(cierre)
        k += 1
        await _tic(bot, monkeypatch, t0 + k * M + 20_000)
    ops.append(_op("cierre-2", 110150, 109550, -2.5, t0 + k * M + 30_000))
    await _tic(bot, monkeypatch, t0 + (k + 1) * M + 20_000)
    await _tic(bot, monkeypatch, t0 + (k + 12) * M + 20_000)  # R6: se puntua tras ESPERA desde su primera lectura
    monkeypatch.undo()
    ids = await _veredictos(db)
    assert len(set(ids)) == 2, ids  # antes: un solo id
    sin_stop = [r[0] for r in await db.fetch("SELECT detalle->>'texto' FROM bot_evento WHERE tipo = 'sin_stop' ORDER BY ts")]
    assert len(sin_stop) == 2  # antes: la nueva no avisaba (R6: el aviso ya no espera a saber la identidad; la nota va en su evaluacion)
    assert await _cierres(db) == {ids[0]: 1.0, ids[1]: -2.5}  # antes: -1.5, las dos sumadas
    reg = json.loads(await db.fetchval("SELECT detalle FROM bot_evaluacion WHERE tipo = 'veredicto' AND posicion = $1", ids[1]))
    assert reg["posicion"]["reapertura"].startswith("cerrada la anterior y reabierta entre dos lecturas (closed-pnl, orden cierre)")
    assert any(t.startswith("CERRADA BTCUSDT LARGO: +1.00") for t in cuenta["textos"])


async def test_r2_promediar_y_despues_cerrar_puntua(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)], [_pos(110300, t0 + M + 30_000, size="0.008")], []], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)
    await _tic(bot, monkeypatch, t0 + 2 * M + 20_000)  # promedia: 0.008 a 110300 (+0.27 %)
    ops.append(_op("cierre", 110300, 110800, 3.6, t0 + 2 * M + 40_000) | {"closedSize": "0.008"})
    await _tic(bot, monkeypatch, t0 + 3 * M + 20_000)
    await _tic(bot, monkeypatch, t0 + 13 * M + 20_000)  # R6: se puntua tras ESPERA desde su primera lectura
    monkeypatch.undo()
    ids = await _veredictos(db)
    assert await _cierres(db) == {ids[0]: 3.6}  # antes: su entrada no era la evaluada, no puntuaba, y a las 2 h «sin puntuar»


async def test_r7_un_reinicio_tras_promediar_no_paga_otra_evaluacion(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0)]], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)
    await bot.latido()
    # el bot cae; mientras, Alejandro promedia (0.008 a 110300); el bot vuelve con la posicion abierta
    otro = sv.Bot(ENTORNO, db, _mundo([[_pos(110300, t0 + 5 * M, size="0.008")]], ops, cuenta))
    await otro.carga()
    for minuto in (10, 10 + 121):  # y 2 h despues sigue abierta
        await _tic(otro, monkeypatch, t0 + minuto * M + 20_000)
    monkeypatch.undo()
    assert cuenta.get("messages") == 1 and len(await _veredictos(db)) == 1  # antes: id nuevo y otra evaluacion pagada
    assert await _cierres(db) == {} and not any("CERRADA" in t for t in cuenta.get("textos", []))  # antes: «sin puntuar» falso


class _Caida(_EnFila):
    """La base que no contesta mientras caida() (como 140 si PostgreSQL se reinicia)."""

    def __init__(self, c, caida):
        super().__init__(c)
        self.caida = caida

    def __getattr__(self, k):
        f = super().__getattr__(k)

        async def g(*a, **kw):
            if self.caida():
                raise OSError("connection refused (postgresql 5432)")
            return await f(*a, **kw)
        return g


async def test_r11_si_la_base_cae_3_min_al_abrir_se_evalua_cuando_vuelve(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, cuenta, reloj = _t0(), {}, [0]
    monkeypatch.setattr(sv.time, "time", lambda: reloj[0] / 1000)
    bot = sv.Bot(ENTORNO, _Caida(base, lambda: reloj[0] < t0 + 180_000), _mundo([[_pos(110000, t0 - 10_000)]], [], cuenta))
    for k in range(12):
        reloj[0] = t0 + k * M
        try:  # como el bucle real (cada): lo que revienta se anota y al minuto siguiente otra vuelta
            await bot.tic_bybit()
        except Exception:
            pass
        await _espera(bot)
    monkeypatch.undo()
    assert len(await _veredictos(base)) == 1 and cuenta.get("messages") == 1  # antes: tres intentos con la base caida y nunca mas


async def test_r4b_en_cobertura_una_fila_sin_lado_no_cuenta_para_ninguno(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, ops, cuenta = _t0(), [], {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, t0), _pos(110100, t0, side="Sell")], []], ops, cuenta))
    await _tic(bot, monkeypatch, t0 + M + 20_000)  # un largo a 110000 y un corto a 110100 (0.09 %), a la vez
    ops += [_op("largo", 110000, 110450, 1.5, t0 + M + 30_000), _op("corto", 110100, 109600, 1.8, t0 + M + 35_000),
            _op("sin-lado", 110050, 110080, -0.3, t0 + M + 40_000)]  # se movio menos que la comision: la aritmetica no dice el lado
    await _tic(bot, monkeypatch, t0 + 2 * M + 20_000)
    await _tic(bot, monkeypatch, t0 + 12 * M + 20_000)  # R6: se puntua tras ESPERA desde su primera lectura
    monkeypatch.undo()
    # antes (R3): 1.2 y 1.5, la -0.3 en las dos. R6: la fila sin lado llega DESPUES de que cada una cerrara entera a su entrada
    # (sus filas cubren su tamano): no es de ninguna de las dos, que se puntuan con lo suyo
    assert await _cierres(db) == {f"BTCUSDT:Buy:{t0}": 1.5, f"BTCUSDT:Sell:{t0}": 1.8}


async def test_r5_el_parte_se_marca_enviado_solo_despues_de_enviarlo(monkeypatch):
    cuenta: dict = {}
    bot = sv.Bot(ENTORNO, None, _mundo([[]], [], cuenta))
    monkeypatch.setattr(sv, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: datetime(2026, 10, 26, 13, 0, 20, tzinfo=UTC)),
                                                        "fromtimestamp": datetime.fromtimestamp, "fromisoformat": datetime.fromisoformat}))
    tropiezos = [OSError("la base tropieza (postgresql)")]

    async def salud():
        if tropiezos:
            raise tropiezos.pop()
        return {}

    async def nada(*a, **kw):
        return None
    bot.salud, bot.texto_salud, bot.evento = salud, lambda s, titulo: f"{titulo} · vivo", nada
    for _ in range(2):  # 13:00 y 13:01, como el bucle real
        try:
            await bot.tic_parte()
        except Exception:
            pass
    assert len([t for t in cuenta.get("textos", []) if t.startswith("PARTE")]) == 1  # antes: 0, el dia se quedaba sin parte


async def test_r6_y_14_cada_error_lo_resuelve_su_operacion(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    t0, cuenta = _t0(), {}
    bot = sv.Bot(ENTORNO, _EnFila(base), _mundo([[_pos(110000, t0)]], [], cuenta))
    lee = bot.bybit.get

    async def closed_pnl_roto(ruta, **kw):
        return {"retCode": 10001, "retMsg": "params error"} if ruta == "/v5/position/closed-pnl" else await lee(ruta, **kw)
    bot.bybit.get = closed_pnl_roto
    for k in (1, 2):  # closed-pnl falla las dos veces; position/list va bien
        await _tic(bot, monkeypatch, t0 + k * M + 20_000)
    monkeypatch.undo()
    cp = [v for v in bot.estado["errores"].values() if "closed-pnl" in v["texto"]]
    assert cp and not any(v["resuelto"] for v in cp), cp  # antes: «resuelto» porque position/list funciono

    otro = sv.Bot(ENTORNO, _SinRegistro(base), _mundo([[]], [], cuenta))
    await otro.opus("pregunta", "TAREA: PREGUNTA")  # pagada, y la base no la apunta
    await otro.latido()
    ll = [v for v in otro.estado["errores"].values() if "no registro la llamada" in v["texto"]]
    assert ll and not ll[0]["resuelto"]  # antes: el latido la daba por resuelta

    vueltas: list = []

    async def una_vuelta():
        vueltas.append(1)
        if len(vueltas) == 1:
            raise KeyError("retCode")
        if len(vueltas) == 3:
            raise asyncio.CancelledError
    tercero = sv.Bot({}, None, None)
    with pytest.raises(asyncio.CancelledError):
        await tercero.cada("bybit", 0.001, una_vuelta)
    ke = [v for v in tercero.estado["errores"].values() if "KeyError" in v["texto"]]
    assert ke and ke[0]["resuelto"]  # antes: una causa generica no se resolvia nunca

    viejo = {"KEYERROR evalua X": {"ultima": "2026-10-26T06:00:00Z", "texto": "evalua X: KeyError 'x'", "resuelto": None, "op": "evalua X"}}
    assert "caducado" in sv.errores_vigentes(viejo, datetime(2026, 10, 26, 12, 30, tzinfo=UTC))  # antes: como si fuera de ahora
    assert sv.errores_vigentes(viejo, datetime(2026, 10, 26, 13, 30, tzinfo=UTC)) == "ninguno"


def test_r8_el_parte_de_hoy_no_cuenta_hasta_su_hora():
    hoy = 29_870_000 // 1440 * 1440
    hasta = hoy + 600  # un /informe a las 10:00Z
    partes = [calidad._dia(hoy - k * 1440) for k in range(1, 8)]  # los siete dias anteriores, con su parte
    assert calidad.resumen([], {}, [], [], [], partes, hasta - 7 * 1440, hasta)["partes"] == "7 de 7 dias"  # antes: «7 de 8»


def test_sospecha_escala_recibe_lo_que_explica_una_rafaga_o_un_stop():
    flujo = ("liq_burst", "scalp_liquidations", "cvd_matrix", "delta_matrix", "oi_context", "funding_context")
    ctx = {k: {"x": 1} for k in flujo + ("context_metadata",)}
    escala = sv.mensaje("ESCALA", dec={}, ctx=ctx, posicion={}, alerta="RAFAGA")
    assert [k for k in flujo if f'"{k}"' not in escala] == []  # antes: ni el flujo ni las liquidaciones
    for tarea in ("ESCALA", "EVALUA", "PREGUNTA"):  # liq_burst y context_metadata no iban a ninguna
        m = sv.mensaje(tarea, dec={}, ctx=ctx, posicion={})
        assert '"liq_burst"' in m and '"context_metadata"' in m, tarea


async def test_sospecha_ninguna_clave_en_lo_que_se_guarda(monkeypatch):
    token = "123456:AAsecreto-del-bot"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    bot = sv.Bot({"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": "42"}, None, None)

    async def duerme(s):
        return None
    monkeypatch.setattr(sv.asyncio, "sleep", duerme)

    async def red_caida():
        raise httpx.ConnectError(f"no conecta con https://api.telegram.org/bot{token}/getUpdates")
    bot.tg.recibe = red_caida
    await bot.tic_telegram()
    assert token not in bot.estado["telegram"] and token not in sv.js(bot.estado)  # antes: str(e) tal cual al estado
    assert token not in sv.js({"detalle": f"lo que sea {token}"})


async def test_sospecha_las_respuestas_salen_en_el_orden_de_los_mensajes():
    bot = sv.Bot({"TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "42"}, None, None)
    enviadas: list = []

    async def recibe():  # (R5: dos preguntas a Opus; lo que no va a Opus ya no espera: test_bot_r5 reg3)
        return ["como esta btc", "y eth?"]

    async def atiende(t):
        if t == "como esta btc":
            await asyncio.sleep(0.05)  # Opus tarda
        return f"Opus: {t}"

    async def manda(t):
        enviadas.append(t)
        return True
    bot.tg.recibe, bot.atiende, bot.manda = recibe, atiende, manda
    await bot.tic_telegram()
    await _espera(bot)
    assert enviadas == ["Opus: como esta btc", "Opus: y eth?"]  # antes: al reves
