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
