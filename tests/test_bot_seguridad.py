"""BOT-SEGURIDAD B1-B4: con dobles en memoria, sin red y sin base. Cada prueba falla con el app/bot de main@1a8d5e3."""
import asyncio
import json
import math
import time

import pytest

from app.bot import bybit as bb
from app.bot import centinela as cen
from app.bot import servicio as sv
from app.bot import sombra as sb

POS = {"clave": "SOLUSDT:Buy", "symbol": "SOLUSDT", "lado": 1, "entrada": 100.0, "marca": 99.5, "stop": 99.4,
       "liquidacion": 90.0, "actualizada": 1}


def bot(monkeypatch, entrega):
    """Un Bot sin Telegram ni base: manda() contesta lo que diga entrega[0] y evento() apunta (tipo, enviada)."""
    b = sv.Bot({}, None, None)
    b.mandados, b.eventos = [], []

    async def manda(texto):
        b.mandados.append(texto)
        return entrega[0]

    async def evento(tipo, activo, minuto, enviada, **k):
        b.eventos.append((tipo, activo, enviada, k.get("detalle") or {}))

    monkeypatch.setattr(b, "manda", manda)
    monkeypatch.setattr(b, "evento", evento)
    return b


# ------------------------------------------------------------------------- B1
def test_b1_un_aviso_que_telegram_no_entrega_se_reintenta_y_no_se_repite(monkeypatch):
    entrega = [False]
    b = bot(monkeypatch, entrega)
    assert asyncio.run(b.seguridad([POS])) == []  # Telegram cae: no se da por avisado
    asyncio.run(b.seguridad([POS]))  # sigue caido: se reintenta, pero el fallo va al registro UNA vez
    entrega[0] = True
    assert [t for _, t, _ in asyncio.run(b.seguridad([POS]))] == ["stop"]  # vuelve: sale
    asyncio.run(b.seguridad([POS]))  # y ya no se repite
    assert len(b.mandados) == 3 and all("stop" in m for m in b.mandados)
    assert [(t, e) for t, _, e, _ in b.eventos] == [("stop", False), ("stop", True)]


def test_b1_la_carga_solo_da_por_avisados_los_entregados():
    import inspect
    fuente = inspect.getsource(sv.Bot.carga)
    assert "AND enviada" in fuente[fuente.index("self.avisados"):]


# ------------------------------------------------------------------------- B2
def velas(retraso: dict, ahora: int, rafaga_btc: int | None = None) -> dict:
    """{activo: {minuto: (hi, lo, c, buy, sell)}} con ruido determinista; una subida de 3 % en 5 min con volumen en BTC."""
    out = {}
    for k, a in enumerate(cen.ACTIVOS):
        f, c = {}, 100.0
        for m in range(ahora - 600, ahora - retraso.get(a, 0)):
            r = 0.0005 * math.sin(m * 1.7 + k)
            buy = sell = 5.0
            if a == "BTCUSDT" and rafaga_btc is not None and rafaga_btc - 4 <= m <= rafaga_btc:
                r, buy, sell = 0.006, 60.0, 4.0
            c *= 1 + r
            f[m] = (c * 1.0002, c * 0.9998, c, buy, sell)
        out[a] = f
    return out


class DB:
    def __init__(self, filas):
        self.filas = filas

    async def fetch(self, sql, simbolos, m0, m1):
        return [(a, m, *x) for a, f in self.filas.items() for m, x in f.items() if m0 <= m < m1]


def test_b2_un_activo_parado_no_deja_ciegos_a_los_otros(monkeypatch):
    ahora = int(time.time() // 60)
    b = bot(monkeypatch, [True])
    b.db = DB(velas({"SOLUSDT": 300}, ahora, rafaga_btc=ahora - 3))
    vistas = []

    async def rafaga(r, ahora, filas):
        vistas.append((r["activo"], r["minuto"]))

    monkeypatch.setattr(b, "rafaga", rafaga)
    asyncio.run(b.tic_centinela())
    assert [a for a, m in vistas if m >= ahora - 10] == ["BTCUSDT"]  # con el «hasta» comun (el de SOL, 5 h atras) no se veia
    d = b.estado["datos"]
    assert d["activos"]["SOLUSDT"]["retraso_min"] == 300 and d["activos"]["BTCUSDT"]["retraso_min"] == 0
    # el aviso UNICO del retraso de SOL, con su clave; otro tic no lo repite
    asyncio.run(b.tic_centinela())
    vig = [x for x in b.eventos if x[0] == "vigia"]
    assert len(vig) == 1 and vig[0][1] == "SOLUSDT" and vig[0][3]["clave"].startswith("retraso:SOLUSDT:")
    assert sum("SOL: velas de 1 min con 300 min de retraso" in m for m in b.mandados) == 1
    s = b.texto_salud(dict(SALUD, datos=b.estado["datos"]), "ESTADO")
    assert "ATRASADAS: SOL" in s and "(300 min)" in s


def test_b2_la_rafaga_del_dia_sale_igual_antes_del_minuto_comun():
    ahora = (int(time.time() // 60) // 1440) * 1440 + 900
    filas = velas({}, ahora, rafaga_btc=ahora - 100)
    dia = ahora // 1440 * 1440
    todas = cen.rafagas_del_dia(filas, dia, ahora)
    por_activo = cen.rafagas_del_dia(filas, dia, dict.fromkeys(cen.ACTIVOS, ahora))
    assert todas == por_activo and any(r["activo"] == "BTCUSDT" and r["clase"] for r in todas)


SALUD = {"bybit": {"activo": False, "error": "sin BYBIT_API_KEY/BYBIT_API_SECRET", "dias_clave": None, "expira": None},
         "validacion": None, "fuentes": {}, "alertas_24h": {}, "errores": {}, "arranque": "2026-11-15T00:00:00Z",
         "latido": "2026-11-15T00:00:00Z", "ultima_alerta": None, "gasto_hoy": 0.0, "tope": 1.0, "gasto_ayer": 0.0,
         "telegram": "ok", "informe": None}


# ------------------------------------------------------------------------- B3
def test_b3_hora_sql_mira_el_simbolo_y_las_venues():
    assert "symbol = $1" in sb.HORA_SQL and "venue = ANY($2" in sb.HORA_SQL


def test_b3_la_retirada_corta_las_decisiones_nuevas():
    c = sb.carga()[0]
    assert c.retirada == ("2026-11-14", "elegida como maximo de una rejilla en la misma muestra; bajo el empate con la"
                          " entrada real; 3 de 11 en sombra")
    assert sb.corte(c) == 1794614400  # 2026-11-14 00:00Z
    flujo = lambda m: -1e7  # noqa: E731  todo dispara
    barra = lambda m: (100.0, 100.0, 100.0, 100.0)  # noqa: E731
    antes, _ = sb.paso(c, [], sb.corte(c) - 7200, sb.corte(c) - 60, flujo, barra)
    despues, _ = sb.paso(c, [], sb.corte(c) - 60, sb.corte(c) + 86400, flujo, barra)
    assert antes and not [f for f in despues if f["minuto"] >= sb.corte(c)]
    assert sb.texto_cuenta(c, {"desde": None, "disparos": 3, "resueltas": 3, "exitos": 1, "sin_dato": 0},
                           corto=True).startswith("SOMBRA RETIRADA el 2026-11-14")


def test_b3_un_minuto_sin_filas_del_simbolo_es_sin_dato(monkeypatch):
    """La cinta del doble solo trae BTC en los venues de contado: para SOL no hay minuto con dato."""
    vistos = []

    class DBc:
        async def fetch(self, sql, *args):
            vistos.append((sql, args))
            if sql == sb.HORA_SQL:
                return [] if args[0] == "SOL" else [(1,)]
            return []

    s = sb.Sombra.__new__(sb.Sombra)
    s.db, s.horas = DBc(), {}
    c = sb.carga()[0]
    h = sb.A._ts("2026-10-21") + 3600
    con = asyncio.run(s.con_dato(c, h, h + 7200))
    assert con == set() and vistos and vistos[0][1][:2] == ("SOL", list(c.venues))


# ------------------------------------------------------------------------- B4
def test_b4_un_json_que_no_es_objeto_es_una_lectura_fallida():
    for d in (None, [], 3, "x"):
        assert bb.transitorio(d) and bb.error(d) and not bb.juzga_clave(d)["activo"]
    with pytest.raises(ValueError):
        bb.posiciones({"retCode": 0, "result": []})


class BB:
    def __init__(self, respuestas):
        self.r = respuestas

    async def get(self, ruta, **k):
        return self.r[ruta]


def test_b4_position_list_null_no_tumba_el_tic_y_la_seguridad_sigue(monkeypatch):
    entrega = [False]
    b = bot(monkeypatch, entrega)
    b.bybit = BB({"/v5/user/query-api": {"retCode": 0, "result": {"readOnly": 1, "ips": ["*"]}},
                  "/v5/position/list": {"retCode": 0, "result": {"list": []}}})
    b.clave_proxima = 0.0

    async def nada(*a, **k):
        return True
    for n in ("avisa_caducidad", "crudo_lectura", "recarga", "operaciones"):
        monkeypatch.setattr(b, n, nada)
    b.bybit_ultima = [POS]  # lo ultimo leido: una posicion con el stop cerca, cuyo aviso Telegram no entrego
    b.bybit.r["/v5/position/list"] = None
    asyncio.run(b.tic_bybit())  # no lanza
    entrega[0] = True
    asyncio.run(b.tic_bybit())
    assert [(t, e) for t, _, e, _ in b.eventos if t == "stop"] == [("stop", False), ("stop", True)]
    assert any("position/list" in k for k in b.estado["errores"])


def test_b4_el_solo_lectura_caduca_a_las_2_h(monkeypatch):
    b = bot(monkeypatch, [True])
    b.bybit = BB({"/v5/user/query-api": {"retCode": 0, "result": {"readOnly": 1, "ips": ["*"]}},
                  "/v5/position/list": {"retCode": 0, "result": {"list": []}}})
    asyncio.run(b.lee_clave())
    assert b.estado["bybit"]["activo"]
    b.bybit.r["/v5/user/query-api"] = {"retCode": 10006, "retMsg": "too many visits"}  # pasajero: no juzga la clave
    b.clave_buena -= 7201
    for _ in range(3):
        asyncio.run(b.lee_clave())
        asyncio.run(b.caduca_veredicto())
    hm = time.strftime("%H:%MZ", time.gmtime(b.clave_buena))
    sin = [m for m in b.mandados if "clave sin verificar" in m]
    assert len(sin) == 1 and f"desde {hm}" in sin[0]
    s = b.texto_salud(dict(SALUD, bybit=b.estado["bybit"], datos=None), "ESTADO")
    assert f"Bybit: clave sin verificar desde {hm}" in s
    json.dumps(b.estado)  # el estado sigue siendo publicable


# ------------------------------------------------------------------------- B5
from app.bot import calc  # noqa: E402

TRAMOS = {  # grabado de GET /v5/market/risk-limit (2026-10-24 16:13Z), dos tramos (el mismo que tests/test_bot.py)
    "BTCUSDT": [{"riskLimitValue": "300000", "maintenanceMargin": "0.0033", "mmDeduction": ""},
                {"riskLimitValue": "2000000", "maintenanceMargin": "0.005", "mmDeduction": "510"}],
    "SOLUSDT": [{"riskLimitValue": "50000", "maintenanceMargin": "0.005", "mmDeduction": ""},
                {"riskLimitValue": "100000", "maintenanceMargin": "0.0056", "mmDeduction": "30"}],
}


def test_b5_el_tamano_sale_del_riesgo_con_comision_y_el_paso_hacia_abajo():
    r = calc.calcula(150, 149, tramos=TRAMOS["SOLUSDT"], paso="0.1")
    assert r["cantidad"] == pytest.approx(3.0)  # main: 10 USD x 50 / 150 = 3.3, sin mirar el stop
    por_unidad = 1 + (150 + 149) * 0.00055  # 3.6 / 1.16445 = 3.09 -> 3.0 al paso 0.1
    assert r["perdida_stop_usd"] == pytest.approx(3.0 * por_unidad) and r["perdida_stop_usd"] <= calc.PERDIDA_MAX == 3.6
    assert r["apalancamiento"] == 10 and r["valor_usd"] == pytest.approx(450) and r["margen_usd"] == pytest.approx(45)
    assert r["objetivo"] is None and r["rr_bruto"] is None and not r["avisos"]
    t = calc.texto(r, "SOLUSDT")
    assert "riesgo real 3.49 USD" in t and "nominal 450.00 USD" in t and "margen 45.00 USD a 10x" in t
    assert calc.calcula(150, 149, 153, riesgo=2, tramos=TRAMOS["SOLUSDT"], paso="0.1")["cantidad"] == pytest.approx(1.7)
    for mal in ({}, {"riesgo": 4}):  # sin stop no hay tamano; el riesgo no pasa de 3.6
        with pytest.raises(ValueError):
            calc.calcula(150, *([] if not mal else [149]), tramos=TRAMOS["SOLUSDT"], paso="0.1", **mal)
    assert sv.args_calc("/calc sol 150 149 2$ corto")["riesgo"] == 2.0


def test_b5_avisa_la_liquidacion_cerca_y_el_paso_que_no_cabe():
    r = calc.calcula(100, 99, apalancamiento=50, tramos=TRAMOS["SOLUSDT"], paso="0.1")
    assert r["liquidacion"] == pytest.approx(98.5) and any("1.50 veces la distancia al stop" in a for a in r["avisos"])
    r = calc.calcula(100, 99, apalancamiento=100, tramos=TRAMOS["SOLUSDT"], paso="0.1")
    assert any("ANTES del stop" in a for a in r["avisos"])
    r = calc.calcula(110000, 100000, tramos=TRAMOS["BTCUSDT"], paso="0.001")
    assert r["cantidad"] == pytest.approx(0.001) and any(a.startswith("NO CABE") for a in r["avisos"])


def test_b5_la_validacion_va_en_distancia_y_solo_para_su_simbolo():
    r = calc.calcula(150, 149, tramos=TRAMOS["SOLUSDT"], paso="0.1")
    btc = {"symbol": "BTCUSDT", "dia": "2026-11-01", "dif_pct": 0.01, "dif_dist_pct": 0.5}
    assert "sin validar contra Bybit en SOLUSDT" in calc.texto(r, "SOLUSDT", btc)  # main: «validada» con la de BTC
    lejos = {"symbol": "SOLUSDT", "dia": "2026-11-01", "dif_pct": 0.3, "dif_dist_pct": 15.0}  # 0.3 % del precio pasaba
    assert "OJO: se separo de Bybit 15.00 % de la distancia" in calc.texto(r, "SOLUSDT", lejos)
    assert "validada contra Bybit: 0.50 % de la distancia" in calc.texto(r, "BTCUSDT", btc)


def test_b5_el_bot_pide_entrada_y_stop(monkeypatch):
    b = bot(monkeypatch, [True])
    rutas = {"/v5/market/risk-limit": {"retCode": 0, "result": {"list": TRAMOS["BTCUSDT"]}},
             "/v5/market/instruments-info": {"retCode": 0, "result": {"list": [{"lotSizeFilter": {"qtyStep": "0.001"},
                                                                                  "fundingInterval": 480}]}},
             "/v5/market/tickers": {"retCode": 0, "result": {"list": [{"markPrice": "110000", "fundingRate": ""}]}}}

    async def get(self, ruta, **k):
        return rutas[ruta]
    monkeypatch.setattr(bb.Bybit, "get", get)
    assert asyncio.run(b.atiende("/calc btc 110000")).startswith("no evaluable: el tamano sale del riesgo")
    t = asyncio.run(b.atiende("/calc btc 110000 109340"))
    assert "tamano 0.004 · riesgo real 3.12 USD" in t and "a 10x" in t


# ------------------------------------------------------------------------- B6
def test_b6_prueba_manda_una_muestra_del_stop_cerca_sin_tocar_los_avisos(monkeypatch):
    b = bot(monkeypatch, [True])
    assert not sv.a_opus("/prueba") and "/prueba" in sv.AYUDA
    assert asyncio.run(b.atiende("/prueba")) == ""
    (m,) = b.mandados
    assert m.startswith("PRUEBA · ") and "MUESTRA" in m
    assert b.avisados == set() and b.fallidos == set() and b.eventos == []
    asyncio.run(b.seguridad([POS]))  # el aviso real de esa misma posicion sale igual, con el mismo formato
    assert len(b.mandados) == 2 and m[len("PRUEBA · "):].split(" · (MUESTRA")[0] == b.mandados[1]


# ------------------------------------------------------------------------- E1 / E2
DIA = 86400
HOY = 1794700800  # 2026-11-15 00:00Z


def diarias_btc(n: int = 60, hasta: int = HOY) -> list:
    """n diarias de BTC que acaban en la que CIERRA en «hasta», cierre subiendo de 1 en 1 (100, 101...), alto = bajo = cierre;
    mas la diaria en curso (abre en «hasta») con cierre 1 y unas 4 h."""
    t0 = hasta - n * DIA
    f = [("BTCUSDT", "daily", t0 + k * DIA, 100.0 + k, 100.0 + k, 100.0 + k) for k in range(n)]
    f.append(("BTCUSDT", "daily", hasta, 1.0, 1.0, 1.0))  # abierta: no cuenta
    f += [("BTCUSDT", "4hour", hasta - 8 * 3600 + k * 14400, 150.0 + k, 150.0 + k, 150.0 + k) for k in range(3)]
    return f


def test_e1_solo_velas_cerradas_y_con_la_ingesta_posterior_a_su_cierre():
    from app.bot import sesgo as ses
    f = diarias_btc()
    d = ses.cerradas(f, "daily", HOY + 1200, HOY + 1800)  # latido 00:20Z: la que cerro a las 00:00Z cuenta
    assert len(d) == 60 and d[-1][0] == HOY - DIA and d[-1][3] == 159.0
    d = ses.cerradas(f, "daily", HOY + 300, HOY + 1800)  # latido 00:05Z: pudo escribirla a medias, no cuenta
    assert d[-1][0] == HOY - 2 * DIA
    h4 = ses.cerradas(f, "4hour", HOY + 1200, HOY + 1800)  # la de 00:00Z esta abierta
    assert [x[0] for x in h4] == [HOY - 8 * 3600, HOY - 4 * 3600]
    assert ses.cerradas(f, "daily", None, HOY + 1800) == []


def test_e2_el_sesgo_su_racha_su_rango_y_su_invalidacion():
    from app.bot import sesgo as ses
    s = ses.sesgo(ses.cerradas(diarias_btc(), "daily", HOY + 1200, HOY + 1800), HOY + 1800)
    media = sum(range(110, 160)) / 50  # 134.5
    assert s["dato"] and s["cierre"] == 159.0 and abs(s["media"] - media) < 1e-9
    assert abs(s["pct"] - (159 / media - 1) * 100) < 1e-9 and s["lado"] == 1 and s["dias"] == 11  # 60 - 49 con media
    assert s["rompe"] == "maximo" and s["max20"] == 158.0
    t = ses.texto(diarias_btc(), HOY + 1200, HOY + 1800)
    assert "contexto, NO es una entrada" in t and "ninguna regla medida ha confirmado ventaja" in t and "claude/fable-be" in t
    assert "BTC: diario del 11-14" in t and "+18.22 % por encima de su media de 50 d (134.5)" in t
    assert "11 d seguidos por encima" in t and "rompio el maximo de 20 d (158)" in t
    assert "invalidacion: un cierre diario por debajo de la media" in t and "4 h: ultima cerrada 11-15 00:00Z, 151" in t
    assert "ETH: sin dato desde nunca" in t
    viejo = ses.texto(diarias_btc(hasta=HOY - 3 * DIA), HOY + 1200, HOY + 1800)  # la ultima cerrada, la de 11-12 (cierra 11-13 00:00Z): 48 h
    assert "BTC: sin dato desde 11-13 00:00Z" in viejo


def test_e2_entrada_y_el_parte_dicen_el_sesgo(monkeypatch):
    b = bot(monkeypatch, [True])

    class DBs:
        async def fetchval(self, sql, *a):
            return HOY + 1200

        async def fetch(self, sql, simbolos, *a):
            assert simbolos == ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"]
            return diarias_btc()
    b.db = DBs()

    async def sombra(corto=False):
        return "SOMBRA"
    monkeypatch.setattr(b, "texto_sombra", sombra)
    monkeypatch.setattr(sv.time, "time", lambda: HOY + 1800.0)
    e = asyncio.run(b.atiende("/entrada"))
    assert e.startswith(sv.ENTRADAS) and "SESGO (contexto, NO es una entrada" in e and "BTC: diario del 11-14" in e
    b.cargado, b.parte_hoy = True, None
    monkeypatch.setattr(sv, "PARTE_HORA_UTC", 0)
    monkeypatch.setattr(b, "salud", lambda: _salud())
    asyncio.run(b.tic_parte())
    assert any(m.startswith("PARTE ") and "SESGO (contexto, NO es una entrada" in m for m in b.mandados)


async def _salud():
    return dict(SALUD, datos=None)


# ------------------------------------------------------------------------- B7
def _evalua_if(expr: str, github: dict) -> bool:
    """Evalua la expresion de GitHub del job (solo ||, &&, ==, != y github.* con cadenas) en python."""
    import re

    class Punto(dict):
        __getattr__ = dict.get

    def o(d):
        return Punto({k: o(v) if isinstance(v, dict) else v for k, v in d.items()})
    py = expr.replace("||", " or ").replace("&&", " and ")
    assert re.fullmatch(r"[\w.' =!]+", py), py
    return bool(eval(py, {"__builtins__": {}}, {"github": o(github)}))


def test_b7_un_pr_desde_un_fork_no_corre_en_el_runner_de_143():
    import pathlib

    import yaml
    ci = yaml.safe_load(pathlib.Path(__file__).resolve().parents[1].joinpath(".github/workflows/ci.yml").read_text())
    assert ci["permissions"] == {"contents": "read"}
    (job,) = ci["jobs"].values()
    expr = job.get("if")
    assert expr, "main: el job corre para cualquier pull_request, tambien desde un fork"
    repo = "dueno/coinanalyze"
    assert _evalua_if(expr, {"event_name": "push", "repository": repo, "event": {}})
    assert _evalua_if(expr, {"event_name": "pull_request", "repository": repo,
                             "event": {"pull_request": {"head": {"repo": {"full_name": repo}}}}})
    assert not _evalua_if(expr, {"event_name": "pull_request", "repository": repo,
                                 "event": {"pull_request": {"head": {"repo": {"full_name": "otro/coinanalyze"}}}}})
