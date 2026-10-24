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


async def test_opus_xhigh_y_su_coste():
    http, vistas = _anthropic()
    r = await llm.llama(http, "k", "sys", "hola", gastado=0.0, tope=3.0)
    assert r["texto"] == "VEREDICTO: A FAVOR" and r["coste"] == pytest.approx(50_000 * 4e-6 + 3000 * 20e-6) and not r["estimado"]
    cuerpo = json.loads(vistas[1].content)
    assert cuerpo["model"] == "claude-opus-5-5" and cuerpo["output_config"] == {"effort": "xhigh"} and cuerpo["max_tokens"] == 16000
    assert vistas[1].headers["anthropic-version"] == "2023-06-01"


async def test_el_tope_no_se_pasa_y_una_caida_apunta_el_peor_caso():
    http, vistas = _anthropic()
    r = await llm.llama(http, "k", "sys", "hola", gastado=3.0 - llm.reserva(50_000) + 0.01, tope=3.0)
    assert r["texto"] is None and "tope diario" in r["error"] and not r["llamada"] and len(vistas) == 1  # solo count_tokens
    http, _ = _anthropic(falla=True)
    r = await llm.llama(http, "k", "sys", "hola", gastado=0.0, tope=3.0)
    assert r["llamada"] and r["estimado"] and r["coste"] == pytest.approx(llm.reserva(50_000))


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
