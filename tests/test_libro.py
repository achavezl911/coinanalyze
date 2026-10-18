"""OF-4a · EL DATO DEL LIBRO (campana 144): el libro local y la numeracion de cada venue, el alcance, la foto, la
cobertura y sus huecos, el relevo en vivo y la lectura.

Los mensajes tienen la forma EXACTA de los venues (grabados el 2026-10-17 en P1, x1-tmp/c144/p1), recortados a pocos
niveles para que cada caso se lea entero.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
from fastapi import HTTPException

import app.api as api
from app import libro as lb
from app import libro_lectura as lec
from app.orderflow import nivel_de

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
D = Decimal
SIN_CONEXION: dict = {"seq": None}


def _libros(venue: str) -> dict[str, lb.Libro]:
    return {a: lb.Libro(venue, a) for a in lb.ACTIVOS}


def _bin(U: int, u: int, pu: int, b=(), a=(), E: int = 1_792_000_000_000, s: str = "BTCUSDT") -> str:
    return json.dumps({"stream": f"{s.lower()}@depth@100ms", "data": {
        "e": "depthUpdate", "E": E, "T": E, "s": s, "U": U, "u": u, "pu": pu,
        "b": [list(x) for x in b], "a": [list(x) for x in a]}})


def _foto_rest(L: int, bids, asks) -> dict:
    return {"lastUpdateId": L, "bids": [list(x) for x in bids], "asks": [list(x) for x in asks]}


# --------------------------------------------------------------------------------------------- la escalera
def _ingenua(lib: lb.Libro, paso: Decimal, banda: int):
    """La cuenta a mano: cada precio a su nivel por division, y los niveles enteros dentro del alcance."""
    compra, venta = max(lib.compras.q), min(lib.ventas.q)
    alc_c, alc_v = lib.alcances()
    nc, nv = nivel_de(compra, paso), nivel_de(venta, paso)
    cs, vs = [], []
    n = nc
    while len(cs) < banda and n >= alc_c:
        cs.append(sum((q for p, q in lib.compras.q.items() if nivel_de(p, paso) == n), D(0)))
        n -= paso
    n = nv
    while len(vs) < banda and n + paso <= alc_v:
        vs.append(sum((q for p, q in lib.ventas.q.items() if nivel_de(p, paso) == n), D(0)))
        n += paso
    return nc, cs, nv, vs


@pytest.mark.parametrize("semilla", range(6))
def test_la_escalera_cuadra_con_la_cuenta_ingenua(semilla):
    rnd = random.Random(semilla)
    lib = lb.Libro("bybit_linear", "BTC")
    medio = D(81000) + D(rnd.randint(0, 999)) / 10
    compras = {medio - D(rnd.randint(1, 3000)) / 10: D(rnd.randint(1, 900)) / 1000 for _ in range(400)}
    ventas = {medio + D(rnd.randint(1, 3000)) / 10: D(rnd.randint(1, 900)) / 1000 for _ in range(400)}
    lib.carga(compras, ventas, 1, 0, 0)
    for paso, banda in ((D(10), 80), (D(1), 100), (D(50), 3)):
        assert lb.escalera(lib, paso, banda) == _ingenua(lib, paso, banda), (semilla, paso)
    lib.alcance = (medio - D(37), medio + D(41))  # un alcance FIJO (Binance) que corta niveles por la mitad
    assert lb.escalera(lib, D(10), 80) == _ingenua(lib, D(10), 80)


def test_un_nivel_que_el_alcance_corta_no_se_guarda():
    lib = lb.Libro("okx_swap", "BTC")
    lib.carga({D("81005"): D(1), D("80995.5"): D(2)}, {D("81006"): D(3), D("81019.9"): D(4)}, 1, 0, 0)
    nc, cs, nv, vs = lb.escalera(lib, D(10), 80)
    # compra: alcance 80995.5 -> el nivel 80990 (80990-80999.9) no se conoce entero: fuera; venta: alcance 81019.9 ->
    # el nivel 81010 acabaria en 81020 > 81019.9: fuera (conservador), y la cantidad de 81019.9 no aparece
    assert (nc, cs, nv, vs) == (D(81000), [D(1)], D(81000), [D(3)])


# --------------------------------------------------------------------------------------------- Binance
def test_binance_usdm_casa_la_foto_con_su_regla_e_ignora_lo_que_cae_fuera_del_alcance():
    v, libros = lb.VENUES["binance_usdm"], _libros("binance_usdm")
    lib = libros["BTC"]
    lb.procesa(v, libros, _bin(1, 5, 0, b=[("81000.0", "1")]), 10.0, SIN_CONEXION)
    lb.procesa(v, libros, _bin(6, 9, 5, b=[("81001.0", "2")], a=[("81003.0", "5")]), 10.1, SIN_CONEXION)
    assert not lib.valido and len(lib.buffer) == 2
    lib.foto_rest = _foto_rest(7, [("81000.0", "1"), ("80990.0", "4")], [("81002.0", "3"), ("81010.0", "6")])
    lb.binance_sincroniza(v, lib, 10.2)
    # se descarta u < 7 (el primer evento), el segundo cruza 7 (6 <= 7 <= 9) y se aplica sobre la foto
    assert lib.valido and lib.seq == 9 and lib.alcance == (D("80990.0"), D("81010.0"))
    assert lib.compras.q == {D("81001.0"): D(2), D("81000.0"): D(1), D("80990.0"): D(4)}
    lb.procesa(v, libros, _bin(10, 11, 9, b=[("80000.0", "9")], a=[("81003.0", "0")]), 10.3, SIN_CONEXION)
    assert lib.valido and D("80000.0") not in lib.compras.q and D("81003.0") not in lib.ventas.q  # fuera: ignorado
    lb.procesa(v, libros, _bin(14, 15, 12, b=[("81001.5", "1")]), 10.4, SIN_CONEXION)  # pu 12 != 11
    assert not lib.valido and lib.saltos[0] == 1 and len(lib.buffer) == 1 and "sequence_discontinuity" in lib.causas[0]


def test_binance_spot_numera_con_U_igual_al_u_anterior_mas_uno():
    v, libros = lb.VENUES["binance_spot"], _libros("binance_spot")
    lib = libros["ETH"]
    ev = lambda U, u, **k: _bin(U, u, 0, s="ETHUSDT", **k)  # noqa: E731
    lb.procesa(v, libros, ev(8, 10, b=[("2390.00", "1")], a=[("2391.00", "1")]), 1.0, SIN_CONEXION)
    lib.foto_rest = _foto_rest(9, [("2390.00", "1")], [("2391.00", "1")])
    lb.binance_sincroniza(v, lib, 1.1)  # 8 <= 9 + 1 <= 10
    assert lib.valido and lib.seq == 10
    lb.procesa(v, libros, ev(11, 12, b=[("2390.50", "1")]), 1.2, SIN_CONEXION)
    assert lib.valido and lib.seq == 12
    lb.procesa(v, libros, ev(14, 15), 1.3, SIN_CONEXION)
    assert not lib.valido


def test_una_foto_rest_anterior_a_lo_guardado_no_casa_y_se_pide_otra():
    v, libros = lb.VENUES["binance_usdm"], _libros("binance_usdm")
    lib = libros["BTC"]
    lb.procesa(v, libros, _bin(10, 12, 9, b=[("81000.0", "1")]), 1.0, SIN_CONEXION)
    lib.foto_rest = _foto_rest(5, [("81000.0", "1")], [("81001.0", "1")])
    lb.binance_sincroniza(v, lib, 1.1)
    assert not lib.valido and lib.foto_rest is None  # entre 5 y 10 hubo diferencias que no estan: otra foto


# --------------------------------------------------------------------------------------------- los demas venues
def _bybit(tipo: str, u: int, b=(), a=(), topic="orderbook.1000.BTCUSDT") -> str:
    return json.dumps({"topic": topic, "type": tipo, "ts": 1_792_000_000_000, "data": {
        "s": topic.rsplit(".", 1)[-1], "b": [list(x) for x in b], "a": [list(x) for x in a], "u": u, "seq": 7},
        "cts": 1_792_000_000_000})


def test_bybit_foto_deltas_seguidos_y_un_salto_que_pide_suscribirse_otra_vez():
    v, libros = lb.VENUES["bybit_linear"], _libros("bybit_linear")
    lib = libros["BTC"]
    lb.procesa(v, libros, _bybit("snapshot", 100, b=[("81000.0", "1")], a=[("81000.1", "1")]), 1.0, SIN_CONEXION)
    lb.procesa(v, libros, _bybit("delta", 101, b=[("81000.0", "0"), ("80999.9", "2")]), 1.1, SIN_CONEXION)
    assert lib.valido and lib.compras.q == {D("80999.9"): D(2)}
    lb.procesa(v, libros, _bybit("delta", 5, topic="orderbook.200.BTCUSDT"), 1.2, SIN_CONEXION)  # otra profundidad
    assert lib.valido and lib.seq == 101
    lb.procesa(v, libros, _bybit("delta", 103), 1.3, SIN_CONEXION)
    assert not lib.valido and lib.resuscribir and lib.saltos[0] == 1
    lb.procesa(v, libros, _bybit("snapshot", 1, b=[("81000.0", "1")], a=[("81000.1", "1")]), 2.0, SIN_CONEXION)
    assert lib.valido and [t[0] for t in lib.cob.tramos] == [1.0, 2.0]  # el hueco 1.3-2.0 no se cubre


def test_okx_numera_con_prevseqid_y_el_swap_va_en_contratos_por_ctval():
    v, libros = lb.VENUES["okx_swap"], _libros("okx_swap")
    lib = libros["BTC"]
    msg = lambda accion, prev, seq, b=(), a=(): json.dumps({  # noqa: E731
        "arg": {"channel": "books", "instId": "BTC-USDT-SWAP"}, "action": accion, "data": [{
            "asks": [list(x) + ["0", "1"] for x in a], "bids": [list(x) + ["0", "1"] for x in b],
            "ts": "1792000000000", "checksum": 0, "prevSeqId": prev, "seqId": seq}]})
    lb.procesa(v, libros, msg("snapshot", -1, 10, b=[("81000", "250")], a=[("81000.1", "3")]), 1.0, SIN_CONEXION)
    assert lib.valido and lib.compras.q == {D("81000"): D("2.50")}  # 250 contratos x 0.01 BTC
    lb.procesa(v, libros, msg("update", 10, 11, a=[("81000.1", "0")]), 1.1, SIN_CONEXION)
    assert not lib.ventas.q and not lib.valido  # un lado vacio: no es un libro
    lb.procesa(v, libros, msg("snapshot", -1, 20, b=[("81000", "1")], a=[("81000.1", "1")]), 1.2, SIN_CONEXION)
    lb.procesa(v, libros, msg("update", 22, 23), 1.3, SIN_CONEXION)
    assert not lib.valido and lib.saltos[0] == 1


def test_bitget_numera_con_pseq():
    v, libros = lb.VENUES["bitget_usdt"], _libros("bitget_usdt")
    lib = libros["SOL"]
    msg = lambda accion, pseq, seq: json.dumps({  # noqa: E731
        "action": accion, "arg": {"instType": "USDT-FUTURES", "channel": "books", "instId": "SOLUSDT"},
        "data": [{"asks": [["103.01", "5"]], "bids": [["103.00", "4"]], "ts": "1792000000000", "seq": seq,
                  "pseq": pseq}], "ts": 1792000000000})
    lb.procesa(v, libros, msg("snapshot", 0, 50), 1.0, SIN_CONEXION)
    lb.procesa(v, libros, msg("update", 50, 51), 1.1, SIN_CONEXION)
    assert lib.valido and lib.seq == 51
    lb.procesa(v, libros, msg("update", 53, 54), 1.2, SIN_CONEXION)
    assert not lib.valido


def test_deribit_inverso_en_usd_borrado_y_change_id():
    v, libros = lb.VENUES["deribit_perp"], _libros("deribit_perp")
    lib = libros["BTC"]
    msg = lambda tipo, prev, cid, b, a: json.dumps({"jsonrpc": "2.0", "method": "subscription", "params": {  # noqa: E731
        "channel": "book.BTC-PERPETUAL.100ms", "data": {"type": tipo, "timestamp": 1792000000000, "prev_change_id":
                                                         prev, "change_id": cid, "instrument_name": "BTC-PERPETUAL",
                                                         "bids": b, "asks": a}}})
    lb.procesa(v, libros, msg("snapshot", None, 7, [["new", 81000.5, 1000]], [["new", 81001.0, 10]]), 1.0,
               SIN_CONEXION)
    assert lib.compras.q == {D("81000.5"): (D(1000) / D("81000.5")).quantize(lb.BASE_INVERSO)}  # USD / precio
    lb.procesa(v, libros, msg("change", 7, 8, [["delete", 81000.5, 0], ["new", 80999.0, 500]], []), 1.1,
               SIN_CONEXION)
    assert lib.valido and list(lib.compras.q) == [D("80999.0")]
    lb.procesa(v, libros, msg("change", 9, 10, [], []), 1.2, SIN_CONEXION)
    assert not lib.valido and lib.resuscribir


def test_coinbase_numera_la_conexion_y_un_salto_invalida_sus_tres_libros():
    v, libros, conexion = lb.VENUES["coinbase_spot"], _libros("coinbase_spot"), {"seq": None}
    msg = lambda n, tipo, ups: json.dumps({"channel": "l2_data", "timestamp": "2026-10-17T22:51:07.730498123Z",  # noqa: E731
                                           "sequence_num": n, "events": [{"type": tipo, "product_id": "ETH-USD",
                                                                          "updates": ups}]})
    ups = [{"side": "bid", "event_time": "x", "price_level": "2393.10", "new_quantity": "1.5"},
           {"side": "offer", "event_time": "x", "price_level": "2393.20", "new_quantity": "2"}]
    lb.procesa(v, libros, msg(0, "snapshot", ups), 1.0, conexion)
    lb.procesa(v, libros, json.dumps({"channel": "heartbeats", "sequence_num": 1, "events": []}), 1.1, conexion)
    lb.procesa(v, libros, msg(2, "update", [{"side": "bid", "event_time": "x", "price_level": "2393.10",
                                             "new_quantity": "0.5"}]), 1.2, conexion)
    assert libros["ETH"].valido and libros["ETH"].compras.q == {D("2393.10"): D("0.5")}
    assert libros["ETH"].ts_ms == 1792277467730
    with pytest.raises(lb.SaltoDeConexion):
        lb.procesa(v, libros, msg(4, "update", []), 1.3, conexion)


def test_un_libro_cruzado_deja_de_ser_valido_y_no_se_fotografia():
    v, libros = lb.VENUES["bybit_spot"], _libros("bybit_spot")
    lib = libros["BTC"]
    lb.procesa(v, libros, _bybit("snapshot", 1, b=[("81000.0", "1")], a=[("81000.1", "1")]), 1.0, SIN_CONEXION)
    lb.procesa(v, libros, _bybit("delta", 2, b=[("81000.2", "1")]), 1.1, SIN_CONEXION)
    assert not lib.valido and "cruzado" in lib.motivo and "source_failure" in lib.causas[0]
    alm = lb.Almacen(0.0)
    lb.fotografia(list(libros.values()), alm, 5)
    assert not alm.fotos


# --------------------------------------------------------------------------------------------- el relevo
def test_el_aviso_cabe_en_un_notify_y_dice_cuantos_niveles_conoce():
    lib = lb.Libro("bybit_linear", "BTC")
    lib.carga({D(81000) - D(i) / 10: D(i) for i in range(1, 2000)},
              {D("81000.1") + D(i) / 10: D(i) for i in range(0, 60)}, 1, 5, 6)
    lib.valida(1.0)
    d = json.loads(carga := lb.carga_relevo(lib, D(1), 2.0))
    assert len(carga.encode()) <= lb.CARGA_MAX
    assert (d["kc"], d["kv"]) == (100, 6)  # la venta llega a 81006.0: de 81000 a 81005, 6 niveles enteros de 1 USD
    lib.invalida(3.0, "prueba", "disconnect")
    assert json.loads(lb.carga_relevo(lib, D(1), 3.0))["x"] == "prueba"


def test_el_cliente_recibe_el_aviso_a_su_paso_sin_el_nivel_grueso_del_borde():
    lib = lb.Libro("okx_spot", "BTC")
    lib.carga({D("81000.5"): D(1), D("80999.5"): D(2), D("80995.5"): D(3)}, {D("81001"): D(4), D("81009"): D(5)},
              1, 5, 6)
    lib.valida(1.0)
    d = json.loads(lb.carga_relevo(lib, D(1), 2.0))
    d["l"] = 7
    m = lec.mensaje(d, D(1), D(5), 50)
    # compra al paso base: el alcance es 80995.5, asi que se conocen 81000 (1), 80999 (2), 80998, 80997 y 80996 (0); el
    # 80995 no entero. A 5 USD: 81000 (1); el 80995-80999 necesitaria el 80995: fuera. La venta llega hasta 81009:
    # 81000-81004 (4) entero; 81005-81009 necesitaria hasta el 81009 al paso base, que el alcance no da entero
    assert d["kc"] == 5 and m["compras"] == [["81000", "1"]] and m["ventas"] == [["81000", "4"]]
    assert lec.mensaje({"v": "okx_spot", "s": "BTC", "x": "cruzado", "e": 1, "l": 2}, D(1), D(1), 5)["tipo"] == \
        "sin_libro"


def test_reagrega_suma_y_corta_los_bordes_como_la_cuenta_a_mano():
    finos = [D(i) for i in range(1, 24)]  # 23 niveles de 10 USD desde 81000 hacia abajo: 80780 el ultimo
    desde, qs = lec.reagrega(D(81000), finos, D(10), D(50), True)
    # 81000 (1) entero; 80950 (2..6); ... ; 80800 (17..21); 80750 necesitaria 80750 y solo llega a 80780: fuera
    assert desde == D(81000) and qs == [D(1), sum(finos[1:6]), sum(finos[6:11]), sum(finos[11:16]),
                                        sum(finos[16:21])]
    desde, qs = lec.reagrega(D(81000), finos[:7], D(10), D(50), False)  # venta: 81000-81060
    assert desde == D(81000) and qs == [sum(finos[:5])]  # 81050-81099 no esta entero
    assert lec.reagrega(D(81000), finos, D(10), D(10), True) == (D(81000), finos)


# --------------------------------------------------------------------------------------------- el websocket
class _Ws:
    def __init__(self, query: dict) -> None:
        self.query_params, self.enviado, self.aceptado = query, [], False
        self.headers, self.client = {}, SimpleNamespace(host="127.0.0.1")

    async def send_denial_response(self, r):
        self.enviado.append(("rechazo", r.status_code, json.loads(r.body)))

    async def accept(self):
        self.aceptado = True

    async def send_json(self, d):
        self.enviado.append(("json", d))
        if d["tipo"] == "latido":
            raise lec.WebSocketDisconnect()

    async def send_text(self, t):
        self.enviado.append(("text", json.loads(t)))
        raise lec.WebSocketDisconnect()


class _PoolPasos:
    def acquire(self):
        conn = SimpleNamespace(fetch=lambda *_a: _filas())

        class _Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_):
                return False

        return _Ctx()


async def _filas():
    return [{"symbol": "BTC", "paso": "1"}, {"symbol": "ETH", "paso": "0.1"}, {"symbol": "SOL", "paso": "0.01"}]


async def test_el_websocket_rechaza_con_su_porque_y_reparte_lo_ultimo(monkeypatch):
    monkeypatch.setattr(lec.RELEVO, "arranca", lambda _dsn: None)
    ws = _Ws({"symbol": "BTC"})
    await lec.vivo(ws, _PoolPasos(), "dsn", "Forbidden")
    assert ws.enviado == [("rechazo", 403, {"detail": "Forbidden"})] and not ws.aceptado
    for q, frase in (({"symbol": "DOGE"}, "symbol tiene que ser"), ({"symbol": "BTC", "paso": "1.5"}, "multiplo"),
                     ({"symbol": "BTC", "niveles": "500"}, "entre 1 y 100"), ({"symbol": "BTC", "hora": "1"},
                                                                             "no reconocidos: hora")):
        ws = _Ws(q)
        await lec.vivo(ws, _PoolPasos(), "dsn", None)
        assert ws.enviado[0][:2] == ("rechazo", 422) and frase in ws.enviado[0][2]["detail"], q
    lec.RELEVO.ultimo[("binance_usdm", "BTC")] = {"v": "binance_usdm", "s": "BTC", "t": 1, "r": 2, "e": 3, "l": 4,
                                                  "b": "81000.5", "a": "81000.6", "kc": 1, "kv": 1,
                                                  "c": [["81000", "2"]], "w": [["81000", "3"]]}
    try:
        ws = _Ws({"symbol": "BTC", "venues": "binance_usdm"})
        await lec.vivo(ws, _PoolPasos(), "dsn", None)
    finally:
        lec.RELEVO.ultimo.clear()
    assert ws.aceptado and ws.enviado[0][1]["tipo"] == "inicio"
    assert ws.enviado[1][1]["compras"] == [["81000", "2"]] and ws.enviado[1][1]["recibido_ms"] == 2
    assert not lec.RELEVO.clientes  # el que se fue no se queda en la lista


def test_el_websocket_mira_el_token_y_el_origen_porque_el_middleware_http_no_corre(monkeypatch):
    monkeypatch.setattr(api, "SETTINGS", SimpleNamespace(API_INTERNAL_TOKEN="t", API_INTERNAL_ALLOWED_CIDRS=()))
    ws = lambda token: SimpleNamespace(headers={"X-Internal-Token": token}, client=SimpleNamespace(host="1.2.3.4"))  # noqa: E731
    assert api.websocket_prohibido(ws("t")) is None
    assert api.websocket_prohibido(ws("otro")) == "Forbidden"
    monkeypatch.setattr(api, "SETTINGS", SimpleNamespace(API_INTERNAL_TOKEN="", API_INTERNAL_ALLOWED_CIDRS=()))
    assert "not configured" in api.websocket_prohibido(ws("t"))


# --------------------------------------------------------------------------------------------- la base
def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"libro_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


class _Una:
    def __init__(self, c) -> None:
        self.c = c

    async def __aenter__(self):
        return self.c

    async def __aexit__(self, *_):
        return False


class _Pool:
    def __init__(self, c) -> None:
        self.c = c

    def acquire(self):
        return _Una(self.c)


# Un minuto UTC de hoy (el esquema crea particiones de ayer a pasado manana).
M = int(datetime.now(UTC).replace(second=0, microsecond=0).timestamp()) - 3600
SALUD = {"caidas": {}, "mal_formados": {}, "reconexiones": {}, "avisos": 0, "avisos_fallidos": 0}


async def test_un_minuto_completo_son_doce_fotos_y_uno_incompleto_se_declara_con_su_prueba(conn):
    libros = [lb.Libro("bybit_linear", "BTC"), lb.Libro("okx_swap", "ETH")]
    for lib in libros:
        lib.carga({D("81000.0"): D(1), D("80950.0"): D(2)}, {D("81000.1"): D(3), D("81100.0"): D(4)}, 1, M * 1000, 0)
        lib.valida(M - 30.0)
    alm = lb.Almacen(M - 120.0)
    alm.proximo = M
    for g in range(M, M + 60, lb.FOTO_S):
        lb.fotografia(libros, alm, g)
        if g == M + 30:  # despues de la foto de M+30: el libro cubrio 30.5 s y tiene 7 fotos (las que caben)
            libros[1].invalida(M + 30.5, "salto: prueba", "sequence_discontinuity")
    await lb.vuelca(_Pool(conn), None, alm, libros, M + 63.0, M - 120.0, {**SALUD, "reconexiones": {}})
    cob = {r["venue"]: r for r in await conn.fetch("SELECT * FROM libro_cobertura")}
    assert (cob["bybit_linear"]["segundos"], cob["bybit_linear"]["fotos"]) == (60, 60 // lb.FOTO_S)
    assert (cob["okx_swap"]["segundos"], cob["okx_swap"]["fotos"], cob["okx_swap"]["saltos"]) == (30, 7, 1)
    huecos = await conn.fetch("SELECT * FROM data_gap WHERE feed = 'libro'")
    assert len(huecos) == 1 and huecos[0]["exchange"] == "okx_swap" and \
        huecos[0]["evidence_type"] == "sequence_discontinuity" and huecos[0]["status"] == "unrecoverable" and \
        json.loads(huecos[0]["recovery_metadata"])["method"] == "libro_sin_cobertura"
    f = await conn.fetchrow("SELECT * FROM libro_foto WHERE venue = 'bybit_linear' ORDER BY ts LIMIT 1")
    assert (f["compra"], f["venta"], f["compra_nivel"], list(f["compras"]), f["venta_nivel"], list(f["ventas"])) == \
        (D("81000.0"), D("81000.1"), D(81000), [D(1), D(0), D(0), D(0), D(0), D(2)], D(81000), [D(3)] + [D(0)] * 9)
    # lo servido es lo guardado, y a un paso mayor suma sin el nivel grueso del borde
    servido = await lec.fotos(conn, symbol="BTC", desde=lec.iso(lb._ts(M)), hasta=lec.iso(lb._ts(M + 60)),
                              venues="bybit_linear", paso="50", cada=30)
    assert [x["ts"] for x in servido["fotos"]] == [lec.iso(lb._ts(M)), lec.iso(lb._ts(M + 30))]
    assert servido["fotos"][0]["compras"] == {"desde": "81000", "cantidades": ["1", "2"]}
    # la venta guardada llega al nivel 81090 (alcance 81100): 81000-81049 (3) y 81050-81099 (0), los dos enteros
    assert servido["fotos"][0]["ventas"] == {"desde": "81000", "cantidades": ["3", "0"]}


async def test_al_arrancar_se_declara_lo_que_nadie_escucho(conn):
    lib = lb.Libro("deribit_perp", "SOL")
    lib.carga({D("103"): D(1)}, {D("103.01"): D(1)}, 1, 0, 0)
    lib.valida(M - 10.0)
    alm = lb.Almacen(M)
    await lb.vuelca(_Pool(conn), None, alm, [lib], M + 63.0, M, {**SALUD, "reconexiones": {}})
    assert await lb.declara_parada_anterior(_Pool(conn), None, M + 600.0) == 1
    g = await conn.fetchrow("SELECT * FROM data_gap WHERE feed = 'libro' AND start_ts = $1", lb._ts(M + 60))
    assert g["end_ts"] == lb._ts(M + 600) and g["evidence_type"] == "collector_outage"


async def test_las_rutas_del_libro_dicen_422_y_no_recortan_en_silencio(conn, monkeypatch):
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    pet = lambda **q: SimpleNamespace(query_params=q)  # noqa: E731
    d, h = lec.iso(lb._ts(M)), lec.iso(lb._ts(M + 60))
    ok = await api.libro_fotos(pet(symbol="BTC", desde=d, hasta=h), symbol="BTC", desde=d, hasta=h)
    assert ok["fotos"] == [] and ok["as_of"].endswith("Z")
    for q, frase in (({"paso": "15"}, "multiplo entero positivo de 10"), ({"cada": 7}, "multiplo de 5"),
                     ({"venues": "kraken"}, "venues desconocidos"), ({"hasta": lec.iso(lb._ts(M + 8 * 86400))},
                                                                     "7 dias")):
        with pytest.raises(HTTPException) as exc:
            await api.libro_fotos(pet(symbol="BTC", **q), **{"symbol": "BTC", "desde": d, "hasta": h, **q})
        assert exc.value.status_code == 422 and frase in exc.value.detail, q
    with pytest.raises(HTTPException) as exc:
        await api.libro_fotos(pet(symbol="BTC", hora="1"), symbol="BTC", desde=d, hasta=h)
    assert exc.value.status_code == 422
    ref = await api.libro_referencia(pet())
    assert len(ref["venues"]) == 9 and ref["foto"]["pasos"] == {"BTC": "10", "ETH": "0.5", "SOL": "0.02"}
    json.dumps(ref)
    json.dumps(await api.libro_cobertura(pet(symbol="SOL", desde=d, hasta=h), symbol="SOL", desde=d, hasta=h))


def test_el_paso_de_la_foto_es_multiplo_del_paso_base_de_of1():
    assert all(lb.PASOS[a] % b == 0 for a, b in {"BTC": D(1), "ETH": D("0.1"), "SOL": D("0.01")}.items())


async def test_un_relevo_que_no_escucha_no_sirve_nada_como_vivo(monkeypatch):
    r = lec.Relevo()
    r._aviso(None, 0, "libro", json.dumps({"v": "okx_swap", "s": "ETH", "x": "cruzado", "e": 1}))
    assert r.ultimo[("okx_swap", "ETH")]["x"] == "cruzado"

    async def falla(**_k):
        raise OSError("sin base")

    monkeypatch.setattr(lec.asyncpg, "connect", falla)
    tarea = asyncio.create_task(r._escucha("dsn"))
    for _ in range(200):
        await asyncio.sleep(0.01)
        if r.estado.startswith("caido"):
            break
    tarea.cancel()
    await asyncio.gather(tarea, return_exceptions=True)
    assert r.estado.startswith("caido") and not r.ultimo
