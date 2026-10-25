"""BOT-2 · remate 3: una prueba por bug de la revision (y los dos de produccion). Cada una cae con el codigo de main@4f6819d
POR EL DEFECTO (comprobado con git stash: x1-tmp/bot2/r3-viejo.sh). Sin red: Bybit, la API local, Anthropic y Telegram
de mentira. Las de base, con TEST_DATABASE_URL (si no, se saltan)."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx
import pytest
from test_bot import (  # noqa: F401
    TRAMOS,
    _clave,
    _EnFila,
    _espera,
    _filas,
    _NoCierra,
    _telegram,
    base,
)

from app.bot import bybit as bb
from app.bot import calc, calidad, llm, vigia
from app.bot import centinela as cen
from app.bot import servicio as sv

ENTORNO = {"BYBIT_API_KEY": "k", "BYBIT_API_SECRET": "s", "ANTHROPIC_API_KEY": "a", "API_INTERNAL_TOKEN": "tok",
           "TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "42"}


def _mundo(posiciones: list, ops: list, cuenta: dict, veredicto: str = "A FAVOR", clave=None):
    """Bybit, la API local, Anthropic y Telegram de mentira. position/list da posiciones[k] en su k-esima llamada (la
    ultima se repite); closed-pnl da `ops`; cuenta[...] lleva cuantas veces se pidio cada cosa."""
    def responde(r: httpx.Request) -> httpx.Response:
        p = r.url.path
        cuenta[p.rsplit("/", 1)[-1]] = cuenta.get(p.rsplit("/", 1)[-1], 0) + 1
        if p == "/v5/user/query-api":
            return clave(r) if clave else httpx.Response(200, json=_clave())
        if p == "/v5/position/list":
            k = min(cuenta["list"] - 1, len(posiciones) - 1)
            return httpx.Response(200, json={"retCode": 0, "result": {"list": posiciones[k]}})
        if p == "/v5/position/closed-pnl":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": ops}})
        if p == "/v5/market/risk-limit":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": TRAMOS["BTCUSDT"]}})
        if p.startswith("/api/"):  # el sobre y DECIDE de la API local
            return httpx.Response(200, json={"decide": {"bias": {"value": "LONG"}, "evaluable": {"value": True}}, "cvd_matrix": {}})
        if p.endswith("/count_tokens"):
            return httpx.Response(200, json={"input_tokens": 1000})
        if p == "/v1/messages":
            return httpx.Response(200, json={"content": [{"type": "text", "text": f"VEREDICTO: {veredicto}"}],
                                             "usage": {"input_tokens": 1000, "output_tokens": 100}})
        if p.endswith("/sendMessage"):
            cuenta.setdefault("textos", []).append(json.loads(r.content)["text"])
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"no previsto: {r.url}")
    return httpx.AsyncClient(transport=httpx.MockTransport(responde))


def _pos(entrada: float, actualizada: int, **kw) -> dict:
    return {"symbol": "BTCUSDT", "side": "Buy", "size": "0.004", "avgPrice": str(entrada), "markPrice": str(entrada),
            "leverage": "50", "liqPrice": "", "stopLoss": "", "takeProfit": "", "createdTime": "1792400000000",
            "updatedTime": str(actualizada)} | kw


def _op(orden: str, entrada: float, salida: float, pnl: float, cerrada: int) -> dict:
    return {"symbol": "BTCUSDT", "orderId": orden, "side": "Sell", "closedSize": "0.004", "avgEntryPrice": str(entrada),
            "avgExitPrice": str(salida), "closedPnl": str(pnl), "leverage": "50", "updatedTime": str(cerrada)}


async def test_bug1_dos_posiciones_del_mismo_simbolo_son_dos_y_cada_una_puntua_con_lo_suyo(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    ahora = int(time.time() * 1000)
    h = 3600_000
    p1, p2 = _pos(110000, ahora - 3 * h), _pos(111000, ahora - h)  # el mismo createdTime: «first time ... on this symbol»
    ops = [_op("vieja", 109000, 109500, 1.9, ahora - 4 * h),  # de antes de la primera: no es de ninguna
           _op("o-1", 110000, 110450, 1.5, ahora - 2 * h),
           _op("o-2", 111000, 110500, -2.3, ahora - h // 2),
           _op("corto", 108000, 107500, 1.9, ahora - h // 3)]  # un corto (la aritmetica lo dice): de otro lado
    cuenta: dict = {}
    db = _EnFila(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[p1], [], [p2], []], ops, cuenta))
    # cada lectura un minuto despues de lo que ve (R4: las operaciones se asignan a la vida por su hora; antes las cuatro
    # lecturas eran «ahora» y la primera posicion se cerraba 2 h despues de su ultima operacion)
    for t in (ahora - 3 * h, ahora - 2 * h, ahora - h, ahora - h // 2):
        monkeypatch.setattr(sv.time, "time", lambda t=t: (t + 60_000) / 1000)
        await bot.tic_bybit()
        await _espera(bot)
    monkeypatch.undo()
    ids = [r[0] for r in await db.fetch("SELECT posicion FROM bot_evaluacion WHERE tipo = 'veredicto' ORDER BY ts")]
    assert len(set(ids)) == 2, ids  # antes: el mismo id para las dos
    assert await db.fetchval("SELECT count(*) FROM bot_evento WHERE tipo = 'sin_stop'") == 2  # antes: la 2a sin aviso
    cierres = {r["posicion"]: r["pnl_usd"] for r in await db.fetch("SELECT posicion, pnl_usd FROM bot_evaluacion WHERE tipo = 'cierre'")}
    assert cierres == {ids[0]: 1.5, ids[1]: -2.3}, cierres  # antes: la 1a sumaba todo lo del simbolo


async def test_bug2_un_fallo_pasajero_al_leer_la_clave_se_reintenta_pronto_y_se_dice(monkeypatch):
    t = [1_800_000_000.0]
    monkeypatch.setattr(sv.time, "time", lambda: t[0])
    respuestas = [httpx.Response(502, text="Bad Gateway"), httpx.Response(200, json=_clave())]
    cuenta: dict = {}
    bot = sv.Bot(ENTORNO, None, _mundo([[]], [], cuenta, clave=lambda r: respuestas.pop(0)))
    bot.tg = None

    async def sin_registro(*a, **kw):
        return None
    bot.evento = sin_registro
    await bot.lee_clave()
    b = bot.estado["bybit"]
    assert b["activo"] is False and b["error"] and "reintento en 30 s" in b["error"]
    t[0] += 31  # antes: hasta dentro de una hora no se volvia a mirar
    if time.time() >= bot.clave_proxima:
        await bot.lee_clave()
    assert bot.estado["bybit"]["activo"] is True

    async def red_caida(*a, **kw):
        raise httpx.ConnectError("sin red")
    bot2 = sv.Bot(ENTORNO, None, None)
    bot2.bybit.get = red_caida
    await bot2.lee_clave()  # antes: la excepcion subia y el estado quedaba «activo False, error None»
    assert bot2.estado["bybit"]["error"].startswith("no pude leer la clave")


class _SinRegistro(_EnFila):
    """La base que no apunta las llamadas ni las evaluaciones (como 140 con un INSERT que falla)."""

    def __getattr__(self, k):
        f = super().__getattr__(k)

        async def g(sql, *a, **kw):
            if isinstance(sql, str) and ("INSERT INTO bot_llamada" in sql or "INSERT INTO bot_evaluacion" in sql):
                raise asyncpg.UntranslatableCharacterError("el registro no entra")
            return await f(sql, *a, **kw)
        return g


async def test_bug3_lo_pagado_cuenta_aunque_no_se_registre_y_no_se_vuelve_a_pagar(base):  # noqa: F811 - el fixture `base` de test_bot
    cuenta: dict = {}
    db = _SinRegistro(base)
    bot = sv.Bot(ENTORNO, db, _mundo([[_pos(110000, int(time.time() * 1000) - 60_000)]], [], cuenta))
    caidas = []
    for _ in range(3):  # como el bucle real (cada): lo que revienta se anota y al minuto siguiente otra vuelta
        try:
            await bot.tic_bybit()
        except Exception as e:
            caidas.append(repr(e)[:120])
        await _espera(bot)
    assert cuenta.get("messages") == 1, f"pagadas {cuenta.get('messages')} · {caidas}"  # antes: una pagada cada minuto
    assert await bot.gastado_hoy() == pytest.approx(1000 * 4e-6 + 100 * 20e-6)  # antes: 0, el tope no la veia


class _SinEventos(_EnFila):
    def __getattr__(self, k):
        f = super().__getattr__(k)

        async def g(sql, *a, **kw):
            if isinstance(sql, str) and "INSERT INTO bot_evento" in sql:
                raise asyncpg.UntranslatableCharacterError("el registro no entra")
            return await f(sql, *a, **kw)
        return g


async def test_bug4_si_la_base_no_registra_el_aviso_no_se_repite(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    dia = 29_870_000 // 1440 * 1440
    filas = _filas(dia - cen.CALIENTA, 600, rafaga=dia + 300)
    await base.executemany(
        "INSERT INTO ohlcv VALUES (to_timestamp($1::bigint * 60), $2, '1min', $3, $4, $5, $6::float8 + $7::float8, $6)",
        [(m, cen.SIMBOLO[a], *x) for a, f in filas.items() for m, x in f.items()])
    cuenta: dict = {}
    bot = sv.Bot(ENTORNO, _SinEventos(base), _mundo([[]], [], cuenta))
    for minuto in (dia + 302, dia + 303):  # como el bucle real (cada): lo que revienta se anota y otra vuelta
        monkeypatch.setattr(sv.time, "time", lambda m=minuto: m * 60 + 20)
        try:
            await bot.tic_centinela()
        except Exception:
            pass
    textos = cuenta.get("textos", [])
    assert len(textos) == 6 and len(set(textos)) == 6  # 3 rafagas y 3 clases, una vez; antes: repetidas cada minuto
    monkeypatch.setattr(sv, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: datetime(2026, 10, 26, 14, tzinfo=UTC)),
                                                        "fromtimestamp": datetime.fromtimestamp, "fromisoformat": datetime.fromisoformat}))

    async def salud():
        return {}
    bot.salud, bot.texto_salud = salud, lambda s, titulo: f"{titulo} · vivo"
    for _ in range(2):
        try:
            await bot.tic_parte()
        except Exception:
            pass
    assert len([t for t in cuenta["textos"] if t.startswith("PARTE")]) == 1  # antes: un parte por minuto


async def test_bug5_se_puntua_el_primer_veredicto(base):  # noqa: F811 - el fixture `base` de test_bot
    db = _EnFila(base)
    p = {"id": "BTCUSDT:Buy:1", "clave": "BTCUSDT:Buy", "symbol": "BTCUSDT", "lado": 1, "entrada": 110000.0, "liquidacion": None}
    cuenta: dict = {}
    bot = sv.Bot(ENTORNO, db, _mundo([[]], [], cuenta, veredicto="A FAVOR"))
    await bot.evalua(p, "posicion nueva")
    bot.http = _mundo([[]], [], cuenta, veredicto="EN CONTRA")
    await bot.evalua(p, "a peticion")  # el /evalua a mano: se registra, no pisa
    veredicto = lambda v: v["veredicto"] if isinstance(v, dict) else v  # noqa: E731 - main guardaba el texto a secas
    assert veredicto(bot.evaluadas[p["id"]]) == "A FAVOR"  # antes: EN CONTRA, el ultimo
    otro = sv.Bot(ENTORNO, db, None)
    await otro.carga()  # tras reiniciar, el primero (antes: sin ORDER BY)
    assert veredicto(otro.evaluadas[p["id"]]) == "A FAVOR"


async def test_bug6_una_escalada_no_para_el_minuto():
    bot = sv.Bot({}, None, None)

    async def nada(*a, **kw):
        return None

    async def escala_lenta(p, alerta):
        await asyncio.sleep(5)
    bot.evento, bot.manda, bot.escala = nada, nada, escala_lenta
    bot.pos = {"BTCUSDT:Buy:1": {"symbol": "BTCUSDT"}}
    r = {"activo": "BTCUSDT", "minuto": int(time.time() // 60), "lado": 1, "z": 5.0, "v": 3.0, "imb": 0.5, "precio": 1.0,
         "clase": None, "clase_min": None}
    t0 = time.monotonic()
    await asyncio.wait_for(bot.rafaga(r, int(time.time() // 60), {"BTCUSDT": {}}), 1.0)  # antes: esperaba los 5 s
    assert time.monotonic() - t0 < 1 and len(bot.tareas) == 1
    await asyncio.sleep(0)  # que la tarea arranque, y se cancela esperandola
    tareas = list(bot.tareas)
    for t in tareas:
        t.cancel()
    await asyncio.gather(*tareas, return_exceptions=True)
    assert llm.TIMEOUT["low"] < llm.TIMEOUT["high"] < 900  # antes: 900 s para todas


async def test_bug7_sin_base_no_hay_falso_resuelto_y_lo_que_no_llego_no_se_resuelve_solo(base, tmp_path):  # noqa: F811 - el fixture `base` de test_bot
    async def conecta():
        return _NoCierra(base)

    async def sin_base():
        raise OSError("la base no contesta")
    e = {"TELEGRAM_BOT_TOKEN": "1:p", "TELEGRAM_CHAT_ID": "-1", "BOT_INFORMES": str(tmp_path)}
    vivo, f, avisos = {"ActiveState": "active"}, tmp_path / "estado.json", []
    lunes = datetime(2026, 10, 26, 14, tzinfo=UTC)
    await base.execute("INSERT INTO bot_estado VALUES ('bot', $1, '{}')", lunes - timedelta(minutes=20))
    await vigia.pasada(e, _telegram(avisos), vivo, conecta, f, lunes)  # latido, parte e informe: avisados
    await vigia.pasada(e, _telegram(avisos), vivo, sin_base, f, lunes + timedelta(minutes=5))
    assert not any("resuelto" in a for a in avisos)  # antes: «resuelto» para todo lo que dependia de la base
    await base.execute("UPDATE bot_estado SET ts = $1 WHERE clave = 'bot'", lunes + timedelta(days=1))
    await vigia.pasada(e, _telegram(avisos), vivo, conecta, f, lunes + timedelta(days=1, minutes=1))  # martes 14:01
    ultimo = avisos[-1]
    assert "parte del" not in ultimo and "NO llego nunca" in ultimo and "el parte de hoy" in ultimo  # antes: «resuelto»


async def test_bug8_el_cursor_de_pagina_va_tal_cual():
    vistas = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: vistas.append(r) or httpx.Response(200, json={"retCode": 0})))
    await bb.Bybit("k", "s", http).get("/v5/position/closed-pnl", category="linear", limit=100, cursor="6880%3A1%2C6880%3A1")
    q = vistas[0].url.query.decode()
    assert "cursor=6880%3A1%2C6880%3A1" in q and "%25" not in q  # antes: %253A


async def test_bug9_y_12_telegram_espera_si_falla_y_cada_mensaje_aparte(monkeypatch):
    esperas = []

    async def duerme(s):
        esperas.append(s)
    monkeypatch.setattr(sv.asyncio, "sleep", duerme)
    bot = sv.Bot({"TELEGRAM_BOT_TOKEN": "1:t", "TELEGRAM_CHAT_ID": "42"}, None, None)

    async def red_caida():
        raise httpx.ConnectError("sin red")
    bot.tg.recibe = red_caida
    await bot.tic_telegram()  # antes: la excepcion subia, el bucle reintentaba cada segundo y el estado seguia «ok»
    assert esperas == [5.0] and "reintento en 5 s" in bot.estado["telegram"]
    monkeypatch.undo()
    respuestas = []

    async def recibe():
        return ["/malo", "/entrada"]

    async def atiende(t):
        if t == "/malo":
            raise IndexError("roto")
        return sv.ENTRADAS

    async def manda(t):
        respuestas.append(t)
        return True
    bot.tg.recibe, bot.atiende, bot.manda = recibe, atiende, manda
    await bot.tic_telegram()
    await _espera(bot)
    assert any(r.startswith("no pude contestar") for r in respuestas) and sv.ENTRADAS in respuestas  # antes: se perdia el 2o


async def test_bug10_un_estado_corrupto_no_tumba_el_interruptor(base, tmp_path):  # noqa: F811 - el fixture `base` de test_bot
    async def conecta():
        return _NoCierra(base)
    f = tmp_path / "estado.json"
    f.write_text('{"notificados": {"lat')  # un apagon a mitad de escribir
    p = await vigia.pasada({"BOT_INFORMES": str(tmp_path)}, _telegram([]), {"ActiveState": "active"}, conecta, f,
                           datetime(2026, 10, 26, 10, tzinfo=UTC))
    assert "latido" in p["problemas"] and json.loads(f.read_text())["ts"]  # antes: json.loads reventaba cada pasada


def test_bug11_el_ultimo_dia_parcial_entra():
    desde = 29_870_000 // 1440 * 1440 + 600  # 10:00Z
    r = calidad.resumen([], {}, [], [], [], [], desde, desde + 7 * 1440)
    assert len(r["falsas_por_dia"]) == 8  # antes: 7, sin el ultimo dia parcial
    assert r["partes"] == "0 de 7 dias"  # R4 (R8): el parte del ultimo dia (13:00Z) aun no tocaba a las 10:00Z


def test_bug13_la_direccion_dicha_manda():
    with pytest.raises(ValueError, match="pediste CORTO pero el stop 109000 esta por debajo"):  # antes: LARGO sin aviso
        calc.calcula(110000, 109000, corto=True, paso="0.001", tramos=TRAMOS["BTCUSDT"])
    r = calc.calcula(100, 101, paso="0.1", tramos=TRAMOS["SOLUSDT"])  # un corto solo por su stop: antes, error falso
    assert r["lado"] == "CORTO" and r["objetivo"] == pytest.approx(98)
    with pytest.raises(ValueError, match="objetivo 103 esta del lado del stop para un CORTO"):
        calc.calcula(100, 101, 103, paso="0.1", tramos=TRAMOS["SOLUSDT"])
    assert sv.args_calc("/calc sol 150 largo")["corto"] is False


async def test_nota_una_respuesta_de_error_no_se_cobra():
    def responde(r):
        if r.url.path.endswith("/count_tokens"):
            return httpx.Response(200, json={"input_tokens": 50_000})
        return httpx.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}})
    r = await llm.llama(httpx.AsyncClient(transport=httpx.MockTransport(responde)), "k", "e", "t", gastado=0, tope=3, effort="high")
    assert r["llamada"] and r["coste"] == 0 and not r["estimado"] and "no se cobra" in r["error"]  # antes: el peor caso


async def test_14_un_error_resuelto_se_dice_resuelto():
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True})))
    bot = sv.Bot({}, None, http)
    bot.anota("API_140", "/api/healthz no contesta: ConnectError", "/api/healthz")  # R4: con su operacion
    await bot.api("/api/healthz")
    assert bot.estado["errores"]["API_140 /api/healthz"].get("resuelto")  # antes: seguia saliendo como si fuera de ahora
    hace_dos_h = datetime.now(UTC) + timedelta(hours=2)
    assert "resuelto" in sv.errores_vigentes(bot.estado["errores"], datetime.now(UTC))
    assert sv.errores_vigentes(bot.estado["errores"], hace_dos_h) == "ninguno"


def test_15_cada_ruta_recibe_solo_su_parte_del_sobre():
    ctx = {"wyckoff": {"x": 1}, "field_disambiguation": {}, "orderbook": {"bid": 1}, "divergences": {"5m": 2}, "snapshot": {"p": 3}}
    escala = sv.mensaje("ESCALA", dec={}, ctx=ctx, posicion={}, alerta="a")
    evalua = sv.mensaje("EVALUA", dec={}, ctx=ctx, posicion={})
    assert "wyckoff" not in escala and "wyckoff" not in evalua and "field_disambiguation" not in evalua  # antes: todo
    # (R4: escala ya recibe cvd_matrix; lo que sigue sin recibir es, por ejemplo, divergences)
    assert '"orderbook"' in escala and '"divergences"' not in escala and '"divergences"' in evalua


async def test_s4_un_apagon_que_cruza_la_medianoche_no_pierde_las_rafagas_de_ayer(base, monkeypatch):  # noqa: F811 - el fixture `base` de test_bot
    hoy = 29_870_000 // 1440 * 1440
    filas = _filas(hoy - 1440 - cen.CALIENTA, 1440 + cen.CALIENTA + 30, rafaga=hoy - 20)  # rafaga a las 23:40 de ayer
    await base.executemany(
        "INSERT INTO ohlcv VALUES (to_timestamp($1::bigint * 60), $2, '1min', $3, $4, $5, $6::float8 + $7::float8, $6)",
        [(m, cen.SIMBOLO[a], *x) for a, f in filas.items() for m, x in f.items()])
    bot = sv.Bot({}, base, None)
    bot.desde_minuto = hoy - 30  # el ultimo latido antes del apagon: 23:30 de ayer
    monkeypatch.setattr(sv.time, "time", lambda: (hoy + 20) * 60 + 20)  # vuelve a las 00:20
    await bot.tic_centinela()
    assert await base.fetchval("SELECT count(*) FROM bot_evento WHERE tipo = 'rafaga'") == 3  # antes: 0
