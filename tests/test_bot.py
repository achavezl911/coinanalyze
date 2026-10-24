"""BOT-2 · el bot de Telegram (app/bot), sin red: las APIs reales no se llaman desde 143. Las respuestas de Bybit y
Telegram son las de su forma publica (las de risk-limit e instruments-info, GRABADAS de la ruta publica de Bybit el
2026-10-24 sin clave); Anthropic, la forma de platform.claude.com. La base, con TEST_DATABASE_URL (si no, se salta)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import pathlib
import re
import uuid

import asyncpg
import httpx
import pytest

from app.bot import bybit as bb
from app.bot import calc, llm
from app.bot import centinela as cen
from app.bot import servicio as sv

RAIZ = pathlib.Path(__file__).resolve().parents[1]
# grabado de GET https://api.bybit.com/v5/market/risk-limit?category=linear&symbol=X (2026-10-24 16:13Z), dos tramos
TRAMOS = {
    "BTCUSDT": [{"riskLimitValue": "300000", "maintenanceMargin": "0.0033", "mmDeduction": ""},
                {"riskLimitValue": "2000000", "maintenanceMargin": "0.005", "mmDeduction": "510"}],
    "SOLUSDT": [{"riskLimitValue": "50000", "maintenanceMargin": "0.005", "mmDeduction": ""},
                {"riskLimitValue": "100000", "maintenanceMargin": "0.0056", "mmDeduction": "30"}],
}


# --------------------------------------------------------------------------------------------- C3 la calculadora
def test_la_forma_de_alejandro_en_btc_pasa_de_su_maximo_por_la_comision():
    r = calc.calcula(110000, tramos=TRAMOS["BTCUSDT"], paso="0.001")
    assert r["lado"] == "LARGO" and r["stop"] == pytest.approx(109340) and r["objetivo"] == pytest.approx(112200)
    assert r["cantidad"] == pytest.approx(0.004) and r["valor_usd"] == pytest.approx(440)  # 0.004545 al paso 0.001
    assert r["liquidacion"] == pytest.approx(110000 - (2200 - 363))  # IM/q = 440/50/0.004, MM/q = 440*0.0033/0.004
    assert r["perdida_stop_usd"] == pytest.approx(2.64 + 0.242 + 0.004 * 109340 * 0.00055)
    assert r["comision_come_pct"] == pytest.approx((0.242 + 0.004 * 112200 * 0.00055) / 8.8 * 100)
    assert any("pasa de tu maximo" in a for a in r["avisos"])


def test_el_paso_se_redondea_en_decimal_y_sol_usa_su_tramo():
    assert calc.calcula(1000, margen=3, apalancamiento=100, paso="0.1", tramos=TRAMOS["SOLUSDT"])["cantidad"] == pytest.approx(0.3)
    r = calc.calcula(150, tramos=TRAMOS["SOLUSDT"], paso="0.1")
    assert r["cantidad"] == pytest.approx(3.3) and r["mmr"] == 0.005
    assert r["liquidacion"] == pytest.approx(150 * (1 - 0.02 + 0.005))


def test_corto_stop_tras_la_liquidacion_y_funding():
    r = calc.calcula(100, corto=True, apalancamiento=100, margen=10, paso="0.1", tramos=TRAMOS["SOLUSDT"], funding=0.0001)
    assert r["lado"] == "CORTO" and r["stop"] > 100 > r["objetivo"] and r["liquidacion"] > 100
    assert r["funding_usd"] == pytest.approx(r["valor_usd"] * 0.0001)  # el corto cobra con funding positivo
    r = calc.calcula(100, 98.5, 103, apalancamiento=100, paso="0.1", tramos=TRAMOS["SOLUSDT"])
    assert any("mas alla de la liquidacion" in a for a in r["avisos"])
    with pytest.raises(ValueError):
        calc.calcula(100, 99, 98, paso="0.1", tramos=TRAMOS["SOLUSDT"])
    assert "funding: sin dato" in calc.texto(calc.calcula(150, tramos=TRAMOS["SOLUSDT"], paso="0.1"), "SOLUSDT")


# --------------------------------------------------------------------------------------------- Bybit solo lectura
def _clave(**r):
    return {"retCode": 0, "retMsg": "", "result": {"readOnly": 1, "ips": ["138.186.31.141"], **r}}


def test_la_clave_solo_se_activa_de_solo_lectura_y_atada_a_la_ip():
    ip = "138.186.31.141"
    assert bb.juzga_clave(_clave(), ip)["activo"] is True
    assert bb.juzga_clave(_clave(readOnly=0), ip)["error"] == "la clave PUEDE OPERAR"
    assert bb.juzga_clave(_clave(ips=["*"]), ip)["activo"] is False
    sin = {"retCode": 0, "result": {"ips": [ip]}}  # sin readOnly: en contra, nunca a favor
    assert bb.juzga_clave(sin, ip)["activo"] is False and bb.juzga_clave(sin, ip)["solo_lectura"] is False
    ipmal = bb.juzga_clave({"retCode": 10010, "retMsg": "Unmatched IP"}, ip)
    assert ipmal["activo"] is False and "IP" in ipmal["error"] and ipmal["solo_lectura"] is None


def test_posiciones_abiertas_de_la_lista():
    d = {"retCode": 0, "result": {"list": [
        {"symbol": "BTCUSDT", "side": "Buy", "size": "0.004", "avgPrice": "110000", "markPrice": "109800",
         "leverage": "50", "liqPrice": "108163.4", "stopLoss": "109340", "takeProfit": "", "positionIM": "8.8",
         "unrealisedPnl": "-0.8", "createdTime": "1792400000000"},
        {"symbol": "ETHUSDT", "side": "", "size": "0", "avgPrice": "0", "createdTime": "1"}]}}
    (p,) = bb.posiciones(d)
    assert p["id"] == "BTCUSDT:Buy:1792400000000" and p["lado"] == 1 and p["stop"] == 109340 and p["objetivo"] is None


async def test_el_cliente_firma_las_privadas_no_las_publicas_y_no_sale_de_su_lista():
    vistas = []
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: vistas.append(r) or httpx.Response(200, json={"retCode": 0})))
    c = bb.Bybit("CLAVE", "SECRETO", http)
    await c.get("/v5/position/list", category="linear", settleCoin="USDT")
    await c.get("/v5/market/tickers", category="linear", symbol="BTCUSDT")
    priv, pub = vistas
    q = "category=linear&settleCoin=USDT"
    assert priv.url.query.decode() == q and priv.method == "GET"
    esperada = hmac.new(b"SECRETO", (priv.headers["X-BAPI-TIMESTAMP"] + "CLAVE5000" + q).encode(), hashlib.sha256).hexdigest()
    assert priv.headers["X-BAPI-SIGN"] == esperada
    assert "X-BAPI-API-KEY" not in pub.headers
    with pytest.raises(ValueError):
        await c.get("/v5/order/create")


def test_el_codigo_del_bot_no_tiene_rutas_de_ordenes_retiros_ni_transferencias():
    prohibidas = re.compile(r"/v5/(order|asset|position/(set|trading-stop|switch|add-margin|confirm)|account/(set|upgrade))"
                            r"|/v5/\S*(withdraw|transfer)", re.I)
    for f in sorted((RAIZ / "app" / "bot").glob("*.py")):
        t = f.read_text()
        assert not prohibidas.search(t), f"{f.name}: {prohibidas.search(t).group(0)}"
        for ruta in re.findall(r"/v5/[a-z/-]+", t):
            assert ruta in bb.PRIVADAS + bb.PUBLICAS, f"{f.name}: {ruta}"
    assert ".post(" not in (RAIZ / "app" / "bot" / "bybit.py").read_text()


# --------------------------------------------------------------------------------------------- C1 el centinela
def _filas(t0: int, n: int, rafaga: int | None = None) -> dict:
    """Tres activos, precio en zigzag +-5 bps y 10 de volumen por minuto; con rafaga, +0.5 %/min y 50 comprador."""
    out = {}
    for a in cen.ACTIVOS:
        f, p = {}, 100.0
        for k in range(n):
            m = t0 + k
            if rafaga is not None and rafaga - 1 <= m <= rafaga + 6:  # vol x2 en su segundo minuto: rafaga
                p *= 1.005
                f[m] = (p, p * 0.999, p, 45.0, 5.0)
            else:
                p *= 1.0005 if k % 2 else 1 / 1.0005
                f[m] = (p * 1.0002, p * 0.9998, p, 5.0, 5.0)
        out[a] = f
    return out


def test_una_rafaga_en_los_tres_es_alerta_y_cascada_y_el_prefijo_coincide():
    dia = 29_870_000 // 1440 * 1440
    filas = _filas(dia - cen.CALIENTA, 600, rafaga=dia + 300)
    rs = cen.rafagas_del_dia(filas, dia, dia + 600 - cen.CALIENTA)
    assert [(r["activo"], r["minuto"] - dia, r["lado"], r["clase"]) for r in rs] == [
        (a, 300, 1, "CASCADA") for a in cen.ACTIVOS]
    assert rs[0]["z"] >= 4 and rs[0]["v"] >= 2 and rs[0]["imb"] >= 0.25
    pre = cen.rafagas_del_dia(filas, dia, dia + 301)  # el bot con la vela de la rafaga: la ve, sin clase todavia
    assert [(r["minuto"] - dia, r["clase"]) for r in pre] == [(300, None)] * 3
    assert [r["clase"] for r in cen.rafagas_del_dia(filas, dia, dia + 302)] == ["CASCADA"] * 3  # al minuto siguiente
    assert cen.rafagas_del_dia(_filas(dia - cen.CALIENTA, 600), dia, dia + 420) == []
    hueco = {a: {m: x for m, x in f.items() if m != dia + 100} for a, f in filas.items()}
    assert len(cen.rafagas_del_dia(hueco, dia, dia + 420)) == 3  # un minuto sin fila no tumba el dia
    assert "ALERTA, no entrada" in cen.texto_rafaga(rs[0]) and "sin ventaja medida" in cen.texto_clase(rs[0])


def test_alertas_de_una_posicion():
    p = {"symbol": "BTCUSDT", "lado": 1, "entrada": 100.0, "marca": 99.55, "stop": 99.4, "liquidacion": 99.3}
    assert [t for t, _ in cen.alertas_posicion(p)] == ["stop", "liquidacion"]
    assert [t for t, _ in cen.alertas_posicion(p | {"marca": 99.9})] == []
    assert [t for t, _ in cen.alertas_posicion(p | {"stop": None, "marca": 99.9})] == ["sin_stop"]
    corto = {"symbol": "SOLUSDT", "lado": -1, "entrada": 100.0, "marca": 100.5, "stop": 100.6, "liquidacion": 101.6}
    assert [t for t, _ in cen.alertas_posicion(corto)] == ["stop"]


# --------------------------------------------------------------------------------------------- Opus y el tope
def _anthropic(entrada=50_000, usage=None, falla=False):
    vistas = []

    def responde(r):
        vistas.append(r)
        if r.url.path.endswith("/count_tokens"):
            return httpx.Response(200, json={"input_tokens": entrada})
        if falla:
            raise httpx.ReadTimeout("lento", request=r)
        return httpx.Response(200, json={"content": [{"type": "thinking", "thinking": "x"}, {"type": "text", "text": "VEREDICTO: A FAVOR"}],
                                         "stop_reason": "end_turn", "usage": usage or {"input_tokens": entrada, "output_tokens": 3000}})
    return httpx.AsyncClient(transport=httpx.MockTransport(responde)), vistas


async def test_opus_con_el_esfuerzo_de_la_ruta_la_cache_y_su_coste():
    http, vistas = _anthropic(usage={"input_tokens": 48_700, "cache_creation_input_tokens": 1300, "output_tokens": 3000})
    r = await llm.llama(http, "k", "estable", "hola", gastado=0.0, tope=3.0, effort="low")
    assert r["texto"] == "VEREDICTO: A FAVOR" and not r["estimado"] and r["entrada"] == 50_000 and r["cache"] == {"leida": 0, "escrita": 1300}
    assert r["coste"] == pytest.approx(48_700 * 4e-6 + 1300 * 5e-6 + 3000 * 20e-6)
    cuerpo = json.loads(vistas[1].content)
    assert cuerpo["model"] == "claude-opus-5-5" and cuerpo["output_config"] == {"effort": "low"} and cuerpo["max_tokens"] == 4000
    assert cuerpo["system"] == [{"type": "text", "text": "estable", "cache_control": {"type": "ephemeral"}}]
    assert vistas[1].headers["anthropic-version"] == "2023-06-01"
    assert (await llm.llama(http, "k", "e", "t", gastado=0, tope=3, effort="altisimo"))["error"].startswith("esfuerzo")


def test_el_esfuerzo_por_ruta_sale_del_entorno_y_max_no_entra_en_tiempo_real():
    assert sv.esfuerzos({}) == ({"escala": "low", "pregunta": "medium", "evalua": "high"}, [])
    e, avisos = sv.esfuerzos({"BOT_EFFORT_EVALUA": "xhigh", "BOT_EFFORT_ESCALA": "max", "BOT_EFFORT_PREGUNTA": "rapido"})
    assert e == {"escala": "low", "pregunta": "medium", "evalua": "xhigh"} and len(avisos) == 2
    assert len(sv.ESTABLE) > 3000  # > 512 tokens: el minimo cacheable de Opus 5.5 (cl100k da 1281)


async def test_el_tope_no_se_pasa_y_una_caida_apunta_el_peor_caso():
    http, vistas = _anthropic()
    r = await llm.llama(http, "k", "sys", "hola", gastado=3.0 - llm.reserva(50_000, "high") + 0.01, tope=3.0)
    assert r["texto"] is None and "tope diario" in r["error"] and not r["llamada"] and len(vistas) == 1  # solo count_tokens
    http, _ = _anthropic(falla=True)
    r = await llm.llama(http, "k", "sys", "hola", gastado=0.0, tope=3.0, effort="medium")
    assert r["llamada"] and r["estimado"] and r["coste"] == pytest.approx(llm.reserva(50_000, "medium"))
    assert llm.reserva(50_000, "low") < llm.reserva(50_000, "medium") < llm.reserva(50_000, "high")


# --------------------------------------------------------------------------------------------- el servicio
def test_limpia_borra_las_claves_de_mensajes_y_logs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:SECRETO-DE-TELEGRAM")
    assert sv.limpia("GET https://api.telegram.org/bot123456:SECRETO-DE-TELEGRAM/getUpdates") == \
        "GET https://api.telegram.org/bot***/getUpdates"
    try:
        raise RuntimeError("fallo en bot123456:SECRETO-DE-TELEGRAM")
    except RuntimeError:
        import sys
        rec = logging.LogRecord("x", logging.WARNING, "f", 1, "url %s", ("bot123456:SECRETO-DE-TELEGRAM",), sys.exc_info())
    assert "SECRETO" not in sv.Formato().format(rec)


async def test_telegram_solo_atiende_al_chat_de_alejandro():
    upd = {"ok": True, "result": [{"update_id": 7, "message": {"chat": {"id": 42}, "text": "/estado"}},
                                  {"update_id": 8, "message": {"chat": {"id": 666}, "text": "/calc btc 1"}}]}
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=upd)))
    tg = sv.Telegram("t", "42", http)
    assert await tg.recibe() == ["/estado"] and tg.ajenos == 1 and tg.offset == 9
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(409, json={"ok": False})))
    with pytest.raises(RuntimeError, match="409"):
        await sv.Telegram("t", "42", http).recibe()


def test_veredicto_de_decide_y_lectura_del_de_opus():
    dec = lambda sesgo, ev=True: {"decide": {"bias": {"value": sesgo}, "evaluable": {"value": ev}}}  # noqa: E731
    assert sv.veredicto_decide(dec("LONG"), 1) == "A FAVOR" and sv.veredicto_decide(dec("LONG"), -1) == "EN CONTRA"
    assert sv.veredicto_decide(dec("NO OPERAR"), 1) == "NO EVALUABLE" and sv.veredicto_decide(dec("LONG", False), 1) == "NO EVALUABLE"
    assert sv.lee_veredicto("algo\nVEREDICTO: EN CONTRA\n- x") == "EN CONTRA" and sv.lee_veredicto("sin formato") is None


def test_ordenes_de_texto():
    assert sv.args_calc("/calc sol 150 149.1 153 20$ 25x corto") == {
        "activo": "SOLUSDT", "numeros": [150.0, 149.1, 153.0], "margen": 20.0, "apalancamiento": 25.0, "corto": True}
    with pytest.raises(ValueError):
        sv.args_calc("/calc btc mil")
    assert sv.activo_de("como esta eth?") == "ETHUSDT" and sv.activo_de("quien compra") == "BTCUSDT"


async def test_entradas_apagadas_y_sin_bybit_no_evalua():
    bot = sv.Bot({}, db=None, http=None)
    assert (await bot.atiende("/entrada")).startswith("Entradas APAGADAS") and "n >= 30" in sv.ENTRADAS
    assert "Bybit apagado" in await bot.atiende("/evalua")
    assert bot.estado["telegram"].startswith("sin Telegram") and bot.tg is None


# --------------------------------------------------------------------------------------------- la base
@pytest.fixture
async def base():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    esquema = f"bot_{uuid.uuid4().hex}"
    c = await asyncpg.connect(dsn)
    await c.execute(f'CREATE SCHEMA "{esquema}"')
    await c.execute(f'SET search_path TO "{esquema}", public')
    await c.execute("CREATE TABLE ohlcv (ts timestamptz, symbol text, interval text, high float8, low float8,"
                    " close float8, volume float8, buy_volume float8)")
    sql = (RAIZ / "sql" / "schema.sql").read_text()
    await c.execute(sql[sql.index("-- CAMPANA BOT-2"):])
    try:
        yield c
    finally:
        await c.execute("SET search_path TO public")
        await c.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')
        await c.close()


async def test_el_centinela_registra_cada_rafaga_una_vez_y_el_registro_es_solo_anadir(base, monkeypatch):
    dia = 29_870_000 // 1440 * 1440
    filas = _filas(dia - cen.CALIENTA, 600, rafaga=dia + 300)
    await base.executemany(
        "INSERT INTO ohlcv VALUES (to_timestamp($1::bigint * 60), $2, '1min', $3, $4, $5, $6::float8 + $7::float8, $6)",
        [(m, cen.SIMBOLO[a], *x) for a, f in filas.items() for m, x in f.items()])
    bot = sv.Bot({}, base, None)
    for ahora in (dia + 302, dia + 305, dia + 305):  # la ve; la clasifica; nada nuevo
        monkeypatch.setattr(sv.time, "time", lambda a=ahora: a * 60 + 20)
        await bot.tic_centinela()
        await bot.latido()
    filas_ev = await base.fetch("SELECT tipo, symbol, clase, enviada FROM bot_evento ORDER BY tipo, symbol")
    assert [tuple(f) for f in filas_ev] == [("clase", a, "CASCADA", False) for a in cen.ACTIVOS] + \
        [("rafaga", a, None, False) for a in cen.ACTIVOS]
    estado = json.loads(await base.fetchval("SELECT estado FROM bot_estado"))
    assert estado["datos"]["retraso_min"] == 0 and estado["bybit"]["error"].startswith("sin BYBIT")
    otro = sv.Bot({}, base, None)  # un reinicio carga lo registrado y no duplica
    await otro.carga()
    await otro.tic_centinela()
    assert await base.fetchval("SELECT count(*) FROM bot_evento") == 6
    with pytest.raises(asyncpg.PostgresError, match="solo anadir"):
        await base.execute("DELETE FROM bot_evento")
    await base.execute("INSERT INTO bot_llamada (motivo, modelo, effort, tokens_entrada, tokens_salida, coste_usd, tope_usd)"
                       " VALUES ('pregunta', 'claude-opus-5-5', 'xhigh', 1, 1, 0.25, 3)")
    assert await bot.gastado_hoy() == pytest.approx(0.25)


def _mundo(posiciones: list[list[dict]], vistas: list):
    """Bybit, la API local y Anthropic de mentira; position/list devuelve posiciones[k] en su k-esima llamada."""
    n = {"pos": 0}

    def responde(r: httpx.Request) -> httpx.Response:
        vistas.append(f"{r.method} {r.url.host}{r.url.path}")
        p = r.url.path
        if p == "/v5/user/query-api":
            return httpx.Response(200, json=_clave())
        if p == "/v5/position/list":
            k = min(n["pos"], len(posiciones) - 1)
            n["pos"] += 1
            return httpx.Response(200, json={"retCode": 0, "result": {"list": posiciones[k]}})
        if p == "/v5/market/risk-limit":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": TRAMOS["BTCUSDT"]}})
        if p == "/v5/position/closed-pnl":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": [{
                "symbol": "BTCUSDT", "orderId": "o-1", "side": "Sell", "closedSize": "0.004", "avgEntryPrice": "110000",
                "avgExitPrice": "110450", "closedPnl": "1.5", "leverage": "50", "createdTime": "1792400999000",
                "updatedTime": "1792400999000"}]}})
        if p == "/v5/market/instruments-info":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": [{"lotSizeFilter": {"qtyStep": "0.001"}, "fundingInterval": 480}]}})
        if p == "/v5/market/tickers":
            return httpx.Response(200, json={"retCode": 0, "result": {"list": [{"markPrice": "110000", "fundingRate": "0.0001"}]}})
        if p == "/api/ai/context":
            assert r.headers["X-Internal-Token"] == "tok"
            return httpx.Response(200, json={"interpretation_prompt": "ROL", "cvd_matrix": {"5m": 1}})
        if p == "/api/mesa/decide":
            return httpx.Response(200, json={"decide": {"bias": {"value": "LONG"}, "evaluable": {"value": True}}})
        if p.endswith("/count_tokens"):
            assert "interpretation_prompt" not in r.content.decode()  # sus reglas no viajan
            return httpx.Response(200, json={"input_tokens": 1000})
        if p == "/v1/messages":
            return httpx.Response(200, json={"content": [{"type": "text", "text": "VEREDICTO: A FAVOR\n- CVD a favor [cvd_matrix.5m]"}],
                                             "usage": {"input_tokens": 1000, "output_tokens": 500}})
        raise AssertionError(f"ruta no prevista: {r.url}")
    return httpx.AsyncClient(transport=httpx.MockTransport(responde))


async def test_c2_registra_el_veredicto_antes_y_lo_puntua_al_cerrar(base):
    pos = {"symbol": "BTCUSDT", "side": "Buy", "size": "0.004", "avgPrice": "110000", "markPrice": "109900", "leverage": "50",
           "liqPrice": "108163", "stopLoss": "109340", "takeProfit": "112200", "positionIM": "8.8", "createdTime": "1792400000000"}
    vistas: list = []
    entorno = {"BYBIT_API_KEY": "k", "BYBIT_API_SECRET": "s", "ANTHROPIC_API_KEY": "a", "API_INTERNAL_TOKEN": "tok"}
    bot = sv.Bot(entorno, base, _mundo([[pos], []], vistas))
    await bot.tic_bybit()  # la clave, la posicion nueva, su evaluacion
    (v,) = await base.fetch("SELECT tipo, posicion, veredicto, veredicto_decide, detalle FROM bot_evaluacion")
    assert (v["tipo"], v["posicion"], v["veredicto"], v["veredicto_decide"]) == ("veredicto", "BTCUSDT:Buy:1792400000000", "A FAVOR", "A FAVOR")
    det = json.loads(v["detalle"])
    assert det["fuente"] == "opus" and det["decide"]["decide"]["bias"]["value"] == "LONG" and det["horas"]["posicion"]
    ll = await base.fetchrow("SELECT id, motivo, effort, coste_usd, detalle FROM bot_llamada")
    assert (ll["motivo"], ll["effort"]) == ("evalua", "high") and ll["coste_usd"] == pytest.approx(1000 * 4e-6 + 500 * 20e-6)
    entrada = json.loads(ll["detalle"])  # lo que vio y lo que contesto: se puede reproducir
    assert entrada["entrada"].startswith("TAREA: EVALUA") and '"cvd_matrix"' in entrada["entrada"] and entrada["respuesta"].startswith("VEREDICTO")
    assert det["llamada"] == str(ll["id"]) and entrada["estable"] == sv.ESTABLE_SHA
    val = json.loads(await base.fetchval("SELECT detalle FROM bot_evento WHERE tipo = 'validacion'"))
    assert val["bybit"] == 108163 and val["dif_pct"] == pytest.approx(0, abs=1e-6)  # la formula da 110000 - (2200 - 363)
    assert await base.fetchval("SELECT pnl_usd FROM bot_operacion WHERE orden = 'o-1'") == 1.5
    assert not any("/v5/order" in x or x.startswith("POST api.bybit") for x in vistas)
    otro = sv.Bot(entorno, base, _mundo([[pos]], []))  # un reinicio con la posicion abierta: no se re-evalua ni se paga
    await otro.carga()
    await otro.tic_bybit()
    assert list(otro.evaluadas) == ["BTCUSDT:Buy:1792400000000"]
    assert await base.fetchval("SELECT count(*) FROM bot_evaluacion") == 1 and await base.fetchval("SELECT count(*) FROM bot_llamada") == 1
    await bot.tic_bybit()  # cerrada: se puntua
    c = await base.fetchrow("SELECT veredicto, pnl_usd, acierto FROM bot_evaluacion WHERE tipo = 'cierre'")
    assert tuple(c) == ("A FAVOR", 1.5, True) and bot.evaluadas == {}
    assert "AVISO: la perdida al stop" in await otro.calcula("/calc btc")
    assert "validada contra Bybit: 0.00 % en BTCUSDT" in await otro.calcula("/calc btc 110000")  # carga() la recupero
    assert "sin validar contra Bybit" in calc.texto(calc.calcula(150, tramos=TRAMOS["SOLUSDT"], paso="0.1"), "SOLUSDT")
    lejos = {"symbol": "SOLUSDT", "dia": "2026-10-25", "dif_pct": 0.8}
    assert "OJO: se separo de Bybit 0.80 % (> 0.5 %)" in calc.texto(calc.calcula(150, tramos=TRAMOS["SOLUSDT"], paso="0.1"), "SOLUSDT", lejos)


# --------------------------------------------------------------------------------------------- el interruptor (banco)
from datetime import UTC, datetime, timedelta  # noqa: E402

from app.bot import vigia  # noqa: E402

AHORA = datetime(2026, 10, 26, 14, 0, tzinfo=UTC)  # lunes, pasado el parte (13:00Z) y la hora del informe (13:30Z)


def test_problemas_del_interruptor():
    vivo = {"ActiveState": "active", "SubState": "running", "Result": "success"}
    todo_bien = dict(unidad=vivo, monitor=None, base_error=None, latido=AHORA - timedelta(seconds=40), parte_hoy=True,
                     informe_semana=True, falla_informe=None)
    assert vigia.problemas(AHORA, **todo_bien) == {}
    p = vigia.problemas(AHORA, **(todo_bien | {"latido": AHORA - timedelta(minutes=9)}))
    assert list(p) == ["latido"] and "9 min" in p["latido"]
    caida = vigia.problemas(AHORA, **(todo_bien | {"unidad": {"ActiveState": "activating", "SubState": "auto-restart",
                                                               "Result": "exit-code"}, "monitor": "exit-code"}))
    assert "cayo con exit-code" in caida["unidad"]
    assert list(vigia.problemas(AHORA, **(todo_bien | {"base_error": "OSError"}))) == ["base"]
    sin = vigia.problemas(AHORA, **(todo_bien | {"parte_hoy": False, "informe_semana": False, "falla_informe": "uso semanal de Max 41 %"}))
    assert sin == {"parte:2026-10-26": "el parte de hoy (13:00Z) no salio",
                   "informe:2026-W44": "el informe semanal no llego: uso semanal de Max 41 %"}
    temprano = AHORA.replace(hour=13, minute=10)  # antes de las 13:30Z ni el parte ni el informe se echan en falta
    assert vigia.problemas(temprano, **(todo_bien | {"parte_hoy": False, "informe_semana": False})) == {}


class _NoCierra:
    def __init__(self, c):
        self.c = c

    def __getattr__(self, k):
        return getattr(self.c, k)

    async def close(self):
        pass


def _telegram(enviados: list, codigo: int = 200):
    def responde(r):
        enviados.append(json.loads(r.content)["text"])
        return httpx.Response(codigo, json={"ok": codigo == 200})
    return httpx.AsyncClient(transport=httpx.MockTransport(responde))


async def test_el_interruptor_avisa_una_vez_y_otra_al_volver(base, tmp_path):
    async def conecta():
        return _NoCierra(base)
    entorno = {"TELEGRAM_BOT_TOKEN": "123:puente", "TELEGRAM_CHAT_ID": "-100", "BOT_INFORMES": str(tmp_path)}
    vivo = {"ActiveState": "active", "SubState": "running", "Result": "success"}
    f = tmp_path / "estado.json"
    await base.execute("INSERT INTO bot_estado VALUES ('bot', $1, '{}')", AHORA - timedelta(minutes=12))  # latido parado de mentira
    await base.execute("INSERT INTO bot_evento (tipo, enviada, ts) VALUES ('parte', true, $1)", AHORA - timedelta(minutes=50))
    await base.execute("INSERT INTO bot_evento (tipo, enviada, detalle) VALUES ('informe', true, '{\"semana\": \"2026-W44\"}')")
    enviados: list = []
    p = await vigia.pasada(entorno, _telegram(enviados), vivo, conecta, f, AHORA)
    assert len(enviados) == 1 and "ALERTA" in enviados[0] and "no late desde hace 12 min" in enviados[0]
    assert p["envio"]["ok"] and list(p["notificados"]) == ["latido"]
    publicado = json.loads(await base.fetchval("SELECT estado FROM bot_estado WHERE clave = 'vigia'"))
    assert list(publicado["problemas"]) == ["latido"] and await base.fetchval("SELECT count(*) FROM bot_evento WHERE tipo = 'vigia'") == 1
    await vigia.pasada(entorno, _telegram(enviados), vivo, conecta, f, AHORA + timedelta(minutes=5))
    assert len(enviados) == 1  # sigue parado: no repite
    await base.execute("UPDATE bot_estado SET ts = $1 WHERE clave = 'bot'", AHORA + timedelta(minutes=9, seconds=30))
    p = await vigia.pasada(entorno, _telegram(enviados), vivo, conecta, f, AHORA + timedelta(minutes=10))
    assert len(enviados) == 2 and "resuelto" in enviados[1] and p["notificados"] == {}


async def test_el_interruptor_dice_la_caida_la_base_y_reintenta_si_telegram_falla(base, tmp_path):
    async def conecta():
        return _NoCierra(base)

    async def sin_base():
        raise OSError("connection refused")
    entorno = {"TELEGRAM_BOT_TOKEN": "123:puente", "TELEGRAM_OUTPUT_CHAT_ID": "-200", "BOT_INFORMES": str(tmp_path),
               "MONITOR_SERVICE_RESULT": "exit-code"}
    caido = {"ActiveState": "activating", "SubState": "auto-restart", "Result": "exit-code"}
    f = tmp_path / "estado.json"
    enviados: list = []
    p = await vigia.pasada(entorno, _telegram(enviados, 500), caido, sin_base, f, AHORA.replace(hour=12))
    assert not p["envio"]["ok"] and p["notificados"] == {} and set(p["problemas"]) == {"unidad", "base"}
    p = await vigia.pasada(entorno, _telegram(enviados), caido, sin_base, f, AHORA.replace(hour=12, minute=5))
    assert p["envio"]["ok"] and "cayo con exit-code" in enviados[-1] and "la base no contesta" in enviados[-1]
    assert set(p["notificados"]) == {"unidad", "base"}
    assert await base.fetchval("SELECT count(*) FROM bot_estado WHERE clave = 'vigia'") == 0  # sin base no publica: lo dice K117
