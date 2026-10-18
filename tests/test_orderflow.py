"""OF-1 · el colector y la lectura del order-flow (campana 140).

Los mensajes son REALES: uno por caso, de 15 min de flujo publico grabados el 2026-10-17 04:02-04:17Z, recortados a
una o dos operaciones. Lo que se fija, y como se rompe cada cosa:
  1 el agresor de cada venue: Coinbase publica el lado del MAKER; leido como taker, un venue entero sale al reves;
  2 las unidades: OKX swap en contratos (x ctVal) y Deribit inverso en USD (base = amount / precio);
  3 el nivel en Decimal exacto: en float, 2400.1 / 0.1 da 24000.999999999996 y cae en el nivel de abajo;
  4 lo que no es una operacion de esta conexion: la foto de Bitget al suscribirse y el last_match de Coinbase;
  5 la cobertura: una reconexion a mitad de minuto descuenta, y un minuto solo es completo si se cubrio entero;
  6 un minuto escrito dos veces sustituye, no suma;
  7 un minuto incompleto se declara en data_gap con la prueba que K04 re-deriva, y los contiguos alargan la fila;
  8 la value area con su algoritmo declarado; 9 healthz informa de orderflow sin degradar el status.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest
from fastapi import HTTPException

import app.api as api
from app import orderflow as of
from app import orderflow_lectura as lec

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
D = Decimal

MUESTRAS = {
    "binance_spot": [
        '{"stream":"solusdt@aggTrade","data":{"e":"aggTrade","E":1792209735039,"s":"SOLUSDT","a":678778278,'
        '"p":"104.92000000","q":"0.07000000","f":2080532009,"l":2080532009,"T":1792209735039,"m":true,"M":true}}',
        '{"stream":"btcusdt@aggTrade","data":{"e":"aggTrade","E":1792209732499,"s":"BTCUSDT","a":4091664942,'
        '"p":"81552.55000000","q":"0.00200000","f":6770334199,"l":6770334199,"T":1792209732498,"m":false,"M":true}}',
    ],
    "binance_usdm": [
        '{"stream":"btcusdt@aggTrade","data":{"e":"aggTrade","E":1792209732414,"a":3488312020,"s":"BTCUSDT",'
        '"p":"81508.80","q":"0.004","nq":"0.004","f":8181101442,"l":8181101443,"T":1792209732263,"m":true,"st":1}}',
    ],
    "bybit_spot": [
        '{"topic":"publicTrade.ETHUSDT","ts":1792209745632,"type":"snapshot","data":[{"i":"2280000001783520502",'
        '"T":1792209745631,"p":"2427.56","v":"0.02142","S":"Buy","seq":184408825354,"s":"ETHUSDT","BT":false,'
        '"RPI":false}]}',
    ],
    "bybit_linear": [
        '{"topic":"publicTrade.SOLUSDT","type":"snapshot","ts":1792209733500,"data":[{"T":1792209733500,'
        '"s":"SOLUSDT","S":"Sell","v":"1.9","p":"104.860","L":"MinusTick","i":"9504122a-5f21-5723-9327-aa69a1155699",'
        '"BT":false,"RPI":false,"seq":285253492047}]}',
    ],
    "okx_spot": [
        '{"arg":{"channel":"trades","instId":"BTC-USDT"},"data":[{"instId":"BTC-USDT","tradeId":"1071574710",'
        '"px":"81546.1","sz":"0.00012263","side":"buy","ts":"1792209734191","count":"1","source":"0",'
        '"seqId":82519384497}]}',
    ],
    "okx_swap": [
        '{"arg":{"channel":"trades","instId":"BTC-USDT-SWAP"},"data":[{"instId":"BTC-USDT-SWAP",'
        '"tradeId":"3001945377","px":"81509.7","sz":"0.01","side":"sell","ts":"1792209733139","count":"1",'
        '"source":"0","seqId":346714995256}]}',
    ],
    "coinbase_spot": [
        '{"type":"match","trade_id":1107242362,"maker_order_id":"f8bd6a65-76cb-4f58-a4ed-6f743ed6b69f",'
        '"taker_order_id":"145b3c28-c0bc-4611-ae8c-bacfe706d983","side":"sell","size":"0.00059678",'
        '"price":"81419.05","product_id":"BTC-USD","sequence":137877577038,"time":"2026-10-17T04:02:13.965271Z"}',
        '{"type":"last_match","trade_id":357987236,"maker_order_id":"9cd5e17e-6323-43d6-ad53-9e21fd41c15a",'
        '"taker_order_id":"c4bb1302-5f01-4e24-92ca-89355c15645b","side":"sell","size":"0.51006871",'
        '"price":"104.77","product_id":"SOL-USD","sequence":33165637422,"time":"2026-10-17T04:02:10.202896Z"}',
    ],
    "bitget_usdt": [
        '{"action":"snapshot","arg":{"instType":"USDT-FUTURES","channel":"trade","instId":"BTCUSDT"},"data":['
        '{"ts":"1792209729719","price":"81506.8","size":"0.0001","side":"sell","tradeId":"1495201466202996738"},'
        '{"ts":"1792209729719","price":"81506.8","size":"0.0079","side":"sell","tradeId":"1495201466202996736"}],'
        '"ts":1792209732583}',
        '{"action":"update","arg":{"instType":"USDT-FUTURES","channel":"trade","instId":"BTCUSDT"},"data":['
        '{"ts":"1792209739991","price":"81506.7","size":"0.0265","side":"sell","tradeId":"1495201509286887436"},'
        '{"ts":"1792209739991","price":"81506.7","size":"0.0048","side":"sell","tradeId":"1495201509286887434"}],'
        '"ts":1792209739992}',
    ],
    "deribit_perp": [
        '{"jsonrpc":"2.0","method":"subscription","params":{"channel":"trades.ETH-PERPETUAL.100ms","data":['
        '{"timestamp":1792209747919,"price":2424.55,"direction":"sell","index_price":2424.14,'
        '"instrument_name":"ETH-PERPETUAL","trade_seq":222884001,"amount":1.0,"mark_price":2424.65,'
        '"tick_direction":2,"trade_id":"ETH-313974869","contracts":1.0}]}}',
        '{"jsonrpc":"2.0","method":"subscription","params":{"channel":"trades.BTC-PERPETUAL.100ms","data":['
        '{"timestamp":1792209749366,"price":81444.5,"direction":"buy","index_price":81432.33,'
        '"instrument_name":"BTC-PERPETUAL","trade_seq":306866904,"amount":10.0,"mark_price":81447.98,'
        '"tick_direction":2,"trade_id":"453275287","contracts":1.0}]}}',
        '{"jsonrpc":"2.0","method":"subscription","params":{"channel":"trades.SOL_USDC-PERPETUAL.100ms","data":['
        '{"timestamp":1792209733122,"price":104.813,"direction":"sell","index_price":104.7901,'
        '"instrument_name":"SOL_USDC-PERPETUAL","trade_seq":15213092,"amount":0.002,"mark_price":104.8017,'
        '"tick_direction":0,"trade_id":"USDC-79085511","contracts":2.0}]}}',
    ],
}

# (venue, mensaje, activo, ts_ms, precio, base, usd, compra, id)
ESPERADO = [
    ("binance_spot", 0, "SOL", 1792209735039, "104.92", "0.07", "7.3444", False, "678778278"),
    ("binance_spot", 1, "BTC", 1792209732498, "81552.55", "0.002", "163.1051", True, "4091664942"),
    # T (la hora de la operacion), no E (la del evento): en USD-M difieren 151 ms aqui.
    ("binance_usdm", 0, "BTC", 1792209732263, "81508.8", "0.004", "326.0352", False, "3488312020"),
    ("bybit_spot", 0, "ETH", 1792209745631, "2427.56", "0.02142", "51.9983352", True, "2280000001783520502"),
    ("bybit_linear", 0, "SOL", 1792209733500, "104.86", "1.9", "199.234", False,
     "9504122a-5f21-5723-9327-aa69a1155699"),
    ("okx_spot", 0, "BTC", 1792209734191, "81546.1", "0.00012263", "9.999998243", True, "1071574710"),
    # 0.01 CONTRATOS x ctVal 0.01 = 0.0001 BTC. Leido como base, el volumen sale x100.
    ("okx_swap", 0, "BTC", 1792209733139, "81509.7", "0.0001", "8.15097", False, "3001945377"),
    # side=sell es el MAKER: el agresor COMPRO.
    ("coinbase_spot", 0, "BTC", 1792209733965, "81419.05", "0.00059678", "48.589260659", True, "1107242362"),
    ("deribit_perp", 2, "SOL", 1792209733122, "104.813", "0.002", "0.209626", False, "USDC-79085511"),
]


@pytest.mark.parametrize("venue,i,activo,ts,precio,base,usd,compra,ident", ESPERADO)
def test_cada_venue_su_agresor_sus_unidades_y_su_hora(venue, i, activo, ts, precio, base, usd, compra, ident):
    [op] = of.interpreta(venue, MUESTRAS[venue][i])
    assert (op.activo, op.ts_ms, op.compra, op.id) == (activo, ts, compra, ident)
    assert (op.precio, op.base, op.usd) == (D(precio), D(base), D(usd))


def test_deribit_inverso_en_usd_y_precio_exacto_aunque_venga_como_numero():
    [eth] = of.interpreta("deribit_perp", MUESTRAS["deribit_perp"][0])
    [btc] = of.interpreta("deribit_perp", MUESTRAS["deribit_perp"][1])
    assert eth.precio == D("2424.55") and eth.usd == D("1.0") and not eth.compra
    assert eth.base == (D("1.0") / D("2424.55")).quantize(D("1e-12"))
    assert btc.usd == D("10.0") and btc.compra and btc.base == (D("10") / D("81444.5")).quantize(D("1e-12"))
    # json con float habria dejado 104.813 como binario; aqui es el texto exacto.
    [sol] = of.interpreta("deribit_perp", MUESTRAS["deribit_perp"][2])
    assert str(sol.precio) == "104.813"


def test_lo_que_no_es_una_operacion_de_esta_conexion_no_entra():
    assert of.interpreta("bitget_usdt", MUESTRAS["bitget_usdt"][0]) == []  # foto de antes de suscribirse
    assert of.interpreta("coinbase_spot", MUESTRAS["coinbase_spot"][1]) == []  # last_match
    assert of.interpreta("okx_swap", "pong") == []
    assert of.interpreta("bybit_spot", '{"success":true,"ret_msg":"subscribe","op":"subscribe"}') == []
    ops = of.interpreta("bitget_usdt", MUESTRAS["bitget_usdt"][1])
    assert [(o.id, o.compra, o.base) for o in ops] == [
        ("1495201509286887436", False, D("0.0265")), ("1495201509286887434", False, D("0.0048"))]


def test_el_nivel_se_calcula_en_decimal_y_en_float_cae_al_de_abajo():
    assert of.nivel_de(D("2400.1"), D("0.1")) == D("2400.1")
    assert math.floor(2400.1 / 0.1) == 24000  # la trampa que esto evita: el nivel de abajo
    assert of.nivel_de(D("109.32"), D("0.01")) == D("109.32")
    assert math.floor(109.32 / 0.01) == 10931
    assert of.nivel_de(D("104.5"), D("0.01")) == D("104.50")
    assert of.nivel_de(D("81563.28"), D("1")) == D("81563")
    assert of.nivel_de(D("2428.13000000"), D("0.1")) == D("2428.1")
    assert of.nivel_de(D("2428.10000000"), D("0.1")) == D("2428.1")


def test_la_cobertura_descuenta_la_reconexion_y_el_minuto_entero_es_el_unico_completo():
    c = of.Cobertura()
    c.abre(1010.0)
    assert c.segundos(1020, ahora=1100.0) == 60
    c.cierra(1050.0)
    c.abre(1052.5)
    assert c.segundos(1020, ahora=1200.0) == 57  # 30 + 27.5 -> 57: falto el hueco de 2.5 s
    assert c.reconexiones(1020) == 1
    assert c.segundos(1080, ahora=1200.0) == 60
    assert c.segundos(1140, ahora=1170.0) == 30  # minuto en curso: lo cubierto hasta ahora
    c.cierra(1199.9)
    assert c.segundos(1140, ahora=1300.0) == 59  # 59.9 s no es el minuto entero
    assert of.Cobertura().segundos(1020, ahora=2000.0) == 0


def _alm(inicio: float = 900.0) -> of.Almacen:
    return of.Almacen({"BTC": D(1), "ETH": D("0.1"), "SOL": D("0.01")},
                      {"BTC": D(1_000_000), "ETH": D(400_000), "SOL": D(150_000)}, inicio)


def _op(ts: int, precio: str, base: str, compra: bool, ident: str, activo: str = "BTC") -> of.Op:
    return of.Op(activo, ts, D(precio), D(base), D(precio) * D(base), compra, ident)


def test_el_almacen_agrega_deduplica_cuenta_tardias_y_lo_que_llega_tarde_de_mas():
    alm = _alm()
    alm.anade("binance_spot", [_op(1_020_500, "100.4", "2", True, "a"), _op(1_021_000, "100.9", "1", False, "b"),
                               _op(1_021_000, "100.9", "1", False, "b")], ahora=1030.0)
    mi = alm.minutos[("binance_spot", "BTC", 1020)]
    assert alm.duplicadas == 1 and mi.ops == 2
    assert mi.celdas[D(100)] == [D(2), D(1), D("200.8"), D("100.9"), 1, 1]
    mi.escrito = True
    alm.anade("binance_spot", [_op(1_022_000, "101.0", "3", True, "c")], ahora=1100.0)
    assert mi.tardias == 1 and mi.sucio and mi.celdas[D(101)][0] == D(3)
    # Pasado el plazo de reescritura (cierre + 70 s) solo se cuenta: ni celda ni cinta.
    antes = len(alm.cinta)
    alm.anade("binance_spot", [_op(1_023_000, "101.0", "3", True, "d")], ahora=1020 + 60 + 70.0)
    assert alm.fuera[("binance_spot", "BTC", 1020)] == 1 and len(alm.cinta) == antes
    # De antes de que arrancara este proceso: se descarta.
    alm.anade("binance_spot", [_op(840_000, "100", "1", True, "e")], ahora=1030.0)
    assert alm.descartadas == 1
    # Grande: al menos el umbral de su activo.
    alm.anade("okx_swap", [_op(1_024_000, "100000", "10", True, "g")], ahora=1030.0)
    assert [g[-2] for g in alm.grandes] == ["g"] and alm.grandes[0][-1] == D(1_000_000)


def test_value_area_con_el_algoritmo_declarado():
    assert lec.value_area({D(100): D(10), D(101): D(30), D(102): D(50), D(103): D(20), D(104): D(5),
                           D(105): D(40)}) == (D(100), D(103), D(110))
    # a igualdad de volumen, el POC es el de precio mas bajo; arriba y abajo empatados, se anade el de arriba
    assert lec.poc_de({D(1): D(5), D(2): D(5)}) == D(1)
    assert lec.value_area({D(1): D(10), D(2): D(20), D(3): D(10)}) == (D(2), D(3), D(30))
    assert lec.value_area({}) is None


def test_el_paso_automatico_sube_la_escalera_hasta_que_la_vela_mediana_cabe():
    # al paso 1 la mediana toca 41 niveles, al 2 toca 21: no caben en 20; al 5, 9
    assert lec.paso_automatico([(D(100), D(140)), (D(100), D(110)), (D(100), D(200))], D(1)) == (D(5), 9)
    # con un numero par de velas la mediana es el elemento n // 2: la de arriba
    assert lec.paso_automatico([(D(0), D(0)), (D(0), D(30))], D(1)) == (D(2), 16)
    # nunca por debajo del paso base, y sin velas con celdas, el paso base
    assert lec.paso_automatico([(D("2430.0"), D("2431.5"))], D("0.1")) == (D("0.1"), 16)
    assert lec.paso_automatico([], D("0.01")) == (D("0.01"), None)


def test_el_paso_tiene_que_ser_multiplo_del_base():
    assert lec.paso_de(None, D(1)) == D(1) and lec.paso_de("5", D(1)) == D(5)
    assert lec.paso_de("0.3", D("0.1")) == D("0.3")
    for malo in ("0.5", "-1", "0", "abc", "NaN"):
        with pytest.raises(lec.Peticion):
            lec.paso_de(malo, D(1))


# --------------------------------------------------------------------------------------------- con base


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"orderflow_{uuid.uuid4().hex}"
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


class _Adquisicion:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    async def __aenter__(self):
        return self._conexion

    async def __aexit__(self, *_exc) -> bool:
        return False


class _Pool:
    def __init__(self, conexion) -> None:
        self._conexion = conexion

    def acquire(self) -> _Adquisicion:
        return _Adquisicion(self._conexion)


# Un minuto UTC de hoy: las particiones que crea el esquema son de ayer a pasado manana.
M = int(datetime.now(UTC).replace(second=0, microsecond=0).timestamp()) - 3600


def _cubre_todo(alm: of.Almacen, desde: float) -> None:
    for c in alm.coberturas.values():
        c.abre(desde)


async def test_un_minuto_escrito_dos_veces_sustituye_y_no_suma(conn):
    pool = _Pool(conn)
    alm = _alm(inicio=M - 300)
    _cubre_todo(alm, M - 300)
    alm.proximo_primera = alm.proximo_final = M
    ops = [_op(M * 1000 + 1_000, "81563.28", "0.5", True, "1"), _op(M * 1000 + 2_000, "81563.90", "0.25", False, "2")]
    alm.anade("binance_spot", ops, ahora=M + 50.0)
    await of.vuelca(pool, None, alm, M + 60 + of.ESCRIBE_S + 1, inicio=M - 300)
    celdas = await conn.fetch("SELECT * FROM orderflow_celda")
    assert [(c["nivel"], c["compra_base"], c["venta_base"], c["compras"], c["ventas"]) for c in celdas] == [
        (D(81563), D("0.5"), D("0.25"), 1, 1)]
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cobertura WHERE ts=$1", of._ts(M)) == 27
    assert await conn.fetchval("SELECT bool_or(definitivo) FROM orderflow_cobertura") is False
    # una tardia, y la reescritura del minuto: tiene que SUSTITUIR
    alm.anade("binance_spot", [_op(M * 1000 + 3_000, "81564.00", "1", True, "3")], ahora=M + 90.0)
    await of.vuelca(pool, None, alm, M + 60 + of.REESCRIBE_S + 1, inicio=M - 300)
    filas = await conn.fetch("SELECT nivel, compra_base, compras, ventas FROM orderflow_celda ORDER BY nivel")
    assert [(f["nivel"], f["compra_base"], f["compras"], f["ventas"]) for f in filas] == [
        (D(81563), D("0.5"), 1, 1), (D(81564), D(1), 1, 0)]
    cob = await conn.fetchrow(
        "SELECT * FROM orderflow_cobertura WHERE venue='binance_spot' AND symbol='BTC' AND ts=$1", of._ts(M))
    assert (cob["operaciones"], cob["tardias"], cob["segundos"], cob["definitivo"]) == (3, 1, 60, True)
    # las celdas de un minuto completo son exactamente la agregacion de su cinta
    assert await conn.fetchval("SELECT count(*) FROM orderflow_cinta") == 3
    assert await conn.fetchval(
        "SELECT sum(base) FILTER (WHERE compra) FROM orderflow_cinta") == await conn.fetchval(
        "SELECT sum(compra_base) FROM orderflow_celda")
    # un lote mas, sin nada nuevo, no toca nada
    await of.vuelca(pool, None, alm, M + 60 + of.REESCRIBE_S + 5, inicio=M - 300)
    assert await conn.fetchval("SELECT sum(compras + ventas) FROM orderflow_celda") == 3
    assert await conn.fetchval("SELECT count(*) FROM data_gap") == 0


async def test_un_minuto_incompleto_se_declara_con_su_prueba_y_los_contiguos_alargan_la_fila(conn):
    pool = _Pool(conn)
    alm = _alm(inicio=M - 300)
    for venue, c in alm.coberturas.items():
        if venue != "okx_swap":
            c.abre(M - 300)
    alm.proximo_primera = alm.proximo_final = M
    await of.vuelca(pool, None, alm, M + 120 + of.REESCRIBE_S + 1, inicio=M - 300)
    huecos = await conn.fetch("SELECT * FROM data_gap ORDER BY symbol")
    assert [(h["exchange"], h["symbol"], h["start_ts"], h["end_ts"]) for h in huecos] == [
        ("okx_swap", a, of._ts(M), of._ts(M + 120)) for a in ("BTC", "ETH", "SOL")]
    h = huecos[0]
    assert (h["status"], h["evidence_type"], h["feed_class"], h["feed"]) == (
        "unrecoverable", "disconnect", "event_stream", "orderflow")
    assert h["recovery_metadata"] and "orderflow_sin_cobertura" in h["recovery_metadata"]
    assert h["resolution_reason"] and h["resolved_at"] is not None
    # la prueba que K04 re-deriva: ningun minuto de la ventana esta completo
    assert await conn.fetchval(
        """SELECT count(*) FROM orderflow_cobertura c WHERE c.venue='okx_swap' AND c.symbol='BTC'
           AND c.ts >= $1 AND c.ts < $2 AND c.segundos = 60""", h["start_ts"], h["end_ts"]) == 0


async def test_al_arrancar_se_cierra_lo_que_quedo_a_medias_y_se_declara_lo_que_nadie_escucho(conn):
    pool = _Pool(conn)
    await conn.execute(
        """INSERT INTO orderflow_cobertura(ts,venue,symbol,segundos,operaciones,definitivo)
           VALUES ($1,'binance_spot','BTC',60,10,true), ($2,'binance_spot','BTC',40,7,false)""",
        of._ts(M), of._ts(M + 60))
    assert await of.declara_parada_anterior(pool, None, M + 600 + 5) == 2
    huecos = await conn.fetch("SELECT start_ts, end_ts, evidence_type FROM data_gap")
    assert [(h["start_ts"], h["end_ts"], h["evidence_type"]) for h in huecos] == [
        (of._ts(M + 60), of._ts(M + 600), "collector_outage")]
    assert await conn.fetchval("SELECT bool_and(definitivo) FROM orderflow_cobertura") is True


async def _celdas(conn, filas):
    await conn.executemany(
        """INSERT INTO orderflow_celda(ts,venue,symbol,nivel,compra_base,venta_base,compra_usd,venta_usd,compras,
                                       ventas) VALUES ($1,$2,'BTC',$3,$4,$5,$6,$7,$8,$9)""", filas)


async def test_footprint_y_perfil_salen_de_las_celdas_en_texto_exacto(conn):
    a, b = of._ts(M), of._ts(M + 60)
    await _celdas(conn, [
        (a, "binance_spot", D(81563), D("0.5"), D("0.25"), D("40781.5"), D("20390.75"), 1, 1),
        (a, "okx_spot", D(81567), D("1"), D("0"), D("81567"), D(0), 2, 0),
        (b, "binance_spot", D(81570), D("0"), D("2"), D(0), D("163140"), 0, 3),
    ])
    fp = await lec.footprint(conn, symbol="btc", desde=lec.iso(a), hasta=lec.iso(of._ts(M + 120)), marco="1m",
                             paso="5", venues=None, unidad="base")
    assert fp["paso"] == "5" and fp["paso_base"] == "1" and len(fp["velas"]) == 2
    v0 = fp["velas"][0]
    assert [(n["nivel"], n["compra"], n["venta"], n["delta"]) for n in v0["niveles"]] == [
        ("81560", "0.5", "0.25", "0.25"), ("81565", "1", "0", "1")]
    assert (v0["compra"], v0["venta"], v0["poc"], v0["operaciones"]) == ("1.5", "0.25", "81565", 4)
    assert v0["cobertura"]["minutos_esperados"] == 9 and not v0["cobertura"]["completa"]
    pf = await lec.perfil(conn, symbol="BTC", desde=lec.iso(a), hasta=lec.iso(of._ts(M + 120)), paso=None,
                          venues="binance_spot", unidad="usd")
    assert [n["nivel"] for n in pf["niveles"]] == ["81563", "81570"] and pf["poc"] == "81570"
    assert pf["value_area"]["val"] == "81570" and pf["total"] == "224312.25"
    for malo in ({"marco": "2m"}, {"paso": "0.5"}, {"venues": "bitmex_perp"}, {"desde": lec.iso(a + timedelta(
            seconds=30))}):
        kw = {"symbol": "BTC", "desde": lec.iso(a), "hasta": lec.iso(of._ts(M + 120)), "marco": "1m",
              "paso": None, "venues": None, "unidad": None, **malo}
        with pytest.raises(lec.Peticion):
            await lec.footprint(conn, **kw)


async def test_footprint_con_paso_automatico_y_la_value_area_de_cada_vela(conn):
    a = of._ts(M)
    # una vela que toca 61 niveles al paso 1: el paso automatico es 5 (13 niveles); la siguiente vela, vacia
    await _celdas(conn, [
        (a, "binance_spot", D(81500), D("1"), D("0"), D("81500"), D(0), 1, 0),
        (a, "binance_spot", D(81530), D("2"), D("1"), D("163060"), D("81530"), 2, 1),
        (a, "binance_spot", D(81560), D("0"), D("1"), D(0), D("81560"), 0, 1),
    ])
    fp = await lec.footprint(conn, symbol="BTC", desde=lec.iso(a), hasta=lec.iso(of._ts(M + 120)), marco="1m",
                             paso="auto", venues="binance_spot", unidad="base")
    assert fp["paso"] == "5" and fp["paso_auto"]["niveles_vela_mediana"] == 13
    assert fp["paso_auto"]["velas_con_celdas"] == 1 and fp["value_area"]["porcentaje"] == 70
    v0, v1 = fp["velas"]
    assert [n["nivel"] for n in v0["niveles"]] == ["81500", "81530", "81560"] and v0["poc"] == "81530"
    # 70 % de 5 es 3.5: desde el POC (3) arriba y abajo empatan a 1, se anade el de arriba
    assert v0["value_area"] == {"val": "81530", "vah": "81560", "volumen": "4"}
    assert v1["niveles"] == [] and v1["value_area"] is None
    # con un paso fijado no hay paso_auto, y una ventana sin celdas se queda en el paso base
    assert "paso_auto" not in await lec.footprint(conn, symbol="BTC", desde=lec.iso(a), hasta=lec.iso(of._ts(M + 60)),
                                                  marco="1m", paso="5", venues=None, unidad=None)
    vacio = await lec.footprint(conn, symbol="ETH", desde=lec.iso(a), hasta=lec.iso(of._ts(M + 60)), marco="1m",
                                paso="auto", venues=None, unidad=None)
    assert vacio["paso"] == "0.1" and vacio["paso_auto"]["niveles_vela_mediana"] is None


class _Peticion:
    def __init__(self, **query) -> None:
        self.query_params = query


async def test_las_rutas_dicen_422_y_no_recortan_en_silencio(conn, monkeypatch):
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    desde, hasta = lec.iso(of._ts(M)), lec.iso(of._ts(M + 60))
    ok = await api.orderflow_footprint(_Peticion(symbol="BTC", desde=desde, hasta=hasta), symbol="BTC",
                                       desde=desde, hasta=hasta)
    assert ok["que"].startswith("footprint") and ok["as_of"].endswith("Z")
    json.dumps(ok)  # sin default=: ni un Decimal ni un datetime sin pasar a texto
    with pytest.raises(HTTPException) as exc:
        await api.orderflow_footprint(_Peticion(symbol="BTC", hora="15"), symbol="BTC", desde=desde, hasta=hasta)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await api.orderflow_footprint(_Peticion(symbol="BTC"), symbol="BTC", desde=desde,
                                      hasta=lec.iso(of._ts(M) + timedelta(days=40)))
    assert exc.value.status_code == 422 and "31 dias" in exc.value.detail
    ref = await api.orderflow_referencia(_Peticion())
    assert ref["pasos"] == {"BTC": "1", "ETH": "0.1", "SOL": "0.01"} and len(ref["mercados"]) == 9
    json.dumps(ref)


class _HealthConnection:
    def __init__(self, heartbeats) -> None:
        self.heartbeats = heartbeats

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def fetchval(self, _query, *_args):
        return 1

    async def fetch(self, query, *_args):
        if "pipeline_heartbeat" in query:
            return self.heartbeats
        return [{"symbol": s, "latest_snapshot": datetime.now(UTC), "lag_seconds": 0.0} for s in api.SETTINGS.SYMBOLS]


class _HealthPool:
    def __init__(self, connection) -> None:
        self.connection = connection

    def acquire(self):
        return self.connection


@pytest.mark.parametrize("servicio,degrada", [("orderflow", False), ("otro", True)])
async def test_healthz_informa_de_orderflow_sin_degradar(monkeypatch, servicio, degrada):
    now = datetime.now(UTC)
    filas = [{"service": s, "status": "ok", "updated_at": now, "lag_seconds": 0.0}
             for s in ("api", "daily", "ws", "scalp", "ingest", "ingest:ohlcv_1m", "ingest:metrics_5m")]
    filas.append({"service": servicio, "status": "degraded", "updated_at": now, "lag_seconds": 5000.0,
                  "detail": "venues=8/9 abajo=okx_swap"})
    monkeypatch.setattr(api.app.state, "pool", _HealthPool(_HealthConnection(filas)), raising=False)

    async def nada(*_a, **_k):
        return None

    monkeypatch.setattr(api, "heartbeat", nada)
    health = await api.health()
    assert (health["status"] == "degraded") is degrada
    assert servicio in health["governed_services"]  # sigue gobernado: K05 lo ve
    informados = [i["service"] for i in health["informative_services"]]
    assert informados == ([] if degrada else ["orderflow"])
    if not degrada:
        assert health["informative_services"][0]["failing"] is True


class _WsMudo:
    """Una conexion que entrega UNA operacion y despues nada: abierta, pero muda."""

    def __init__(self, primero: str) -> None:
        self.cola = [primero]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def send(self, _texto) -> None:
        return None

    async def recv(self):
        if self.cola:
            return self.cola.pop()
        await asyncio.sleep(0.01)
        raise TimeoutError


async def test_una_conexion_abierta_que_no_entrega_no_cubre(monkeypatch):
    # Es el caso de Binance USD-M por /stream (medido por el operador el 10-17): conecta y no entrega. Sin la regla
    # del silencio, la cobertura diria 60 s sobre un minuto vacio.
    monkeypatch.setattr(of, "SILENCIO_S", 0.2)
    monkeypatch.setattr(of.random, "uniform", lambda *_a: 0.0)
    monkeypatch.setattr(of, "connect", lambda *_a, **_k: _WsMudo(MUESTRAS["binance_usdm"][0]))
    alm = _alm(inicio=0.0)
    salud = {"ultimo": {}, "caidas": defaultdict(int), "mal_formados": defaultdict(int)}
    tarea = asyncio.create_task(of.escucha("binance_usdm", alm, salud))
    for _ in range(300):
        await asyncio.sleep(0.01)
        if salud["caidas"]["binance_usdm"]:
            break
    tarea.cancel()
    await asyncio.gather(tarea, return_exceptions=True)
    assert salud["caidas"]["binance_usdm"] >= 1
    desde, hasta = alm.coberturas["binance_usdm"].tramos[0]
    # el tramo acaba en la ULTIMA operacion recibida, no cuando se dio por muerta la conexion
    assert hasta is not None and hasta - desde < 0.1


# --------------------------------------------------------------------------------------------- OF-3 (campana 143)
# La medianoche de HOY: el esquema crea particiones de ayer a pasado manana, asi que una sesion que la cruza tiene sus
# dos lados en la base. El reloj se planta con _cerrado (el ultimo minuto que se da por escuchado).
T0 = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _reloj(monkeypatch, cerrado: datetime) -> None:
    monkeypatch.setattr(lec, "_cerrado", lambda _ahora: cerrado)


async def _cobertura(conn, filas):
    await conn.executemany(
        """INSERT INTO orderflow_cobertura(ts,venue,symbol,segundos,operaciones,definitivo)
           VALUES ($1,$2,'BTC',$3,$4,true)""", filas)


async def test_una_sesion_que_cruza_la_medianoche_es_una_y_el_compuesto_suma_sus_sesiones(conn, monkeypatch):
    _reloj(monkeypatch, T0 + timedelta(days=2))
    m = timedelta(minutes=1)
    await _celdas(conn, [
        (T0 - 30 * m, "binance_spot", D(100), D(1), D(0), D("100.5"), D(0), 1, 0),
        (T0 + 30 * m, "binance_spot", D(101), D(0), D(2), D(0), D("202.2"), 0, 1),
        (T0 + 30 * m, "okx_spot", D(100), D(1), D(1), D("100.2"), D("100.4"), 1, 1),
    ])
    await _cobertura(conn, [(T0 - 30 * m, "binance_spot", 60, 1), (T0 + 30 * m, "binance_spot", 60, 1),
                            (T0 + 30 * m, "okx_spot", 45, 2)])
    r = await lec.sesiones(conn, symbol="BTC", desde=lec.iso(T0 - 60 * m), hasta=lec.iso(T0 + 60 * m),
                           sesion="23:00-01:00", paso=None, venues="okx_spot,binance_spot", unidad="base")
    assert r["sesion"]["cruza_medianoche"] and r["sesion"]["minutos"] == 120 and len(r["sesiones"]) == 1
    s = r["sesiones"][0]
    assert (s["inicio"], s["fin"], s["en_curso"]) == (lec.iso(T0 - 60 * m), lec.iso(T0 + 60 * m), False)
    assert [(n["nivel"], n["compra"], n["venta"]) for n in s["niveles"]] == [("100", "2", "1"), ("101", "0", "2")]
    # POC 100 (3); el 70 % de 5 es 3.5: se anade 101 (el unico vecino)
    assert s["poc"] == "100" and s["value_area"] == {"val": "100", "vah": "101", "volumen": "5"}
    assert (s["cobertura"]["minutos_esperados"], s["cobertura"]["minutos_con_fila"],
            s["cobertura"]["minutos_completos"], s["cobertura"]["completa"]) == (240, 3, 2, False)
    assert r["compuesto"]["sesiones"] == 1 and r["compuesto"]["niveles"] == s["niveles"]
    # en curso: el reloj a las 00:10 corta la cobertura ahi; las celdas posteriores entran (la sesion crece)
    _reloj(monkeypatch, T0 + 10 * m)
    viva = (await lec.sesiones(conn, symbol="BTC", desde=lec.iso(T0 - 60 * m), hasta=lec.iso(T0 + 60 * m),
                               sesion="23:00-01:00", paso=None, venues="okx_spot,binance_spot",
                               unidad="base"))["sesiones"][0]
    assert viva["en_curso"] and viva["corte"] == lec.iso(T0 + 10 * m)
    assert viva["cobertura"]["minutos_esperados"] == 140 and viva["total"] == s["total"]
    # dos sesiones de 00:00-00:31 (hoy y manana): el compuesto es su suma, con su cobertura sumada
    _reloj(monkeypatch, T0 + timedelta(days=2))
    await _celdas(conn, [(T0 + timedelta(days=1, minutes=10), "binance_spot", D(100), D(3), D(0), D("300"), D(0), 2,
                          0)])
    dos = await lec.sesiones(conn, symbol="BTC", desde=lec.iso(T0), hasta=lec.iso(T0 + timedelta(days=1, minutes=31)),
                             sesion="00:00-00:31", paso="1", venues="binance_spot", unidad="usd")
    assert [x["inicio"] for x in dos["sesiones"]] == [lec.iso(T0), lec.iso(T0 + timedelta(days=1))]
    assert dos["sesiones"][0]["niveles"][0]["nivel"] == "101" and dos["compuesto"]["sesiones"] == 2
    assert [(n["nivel"], n["total"]) for n in dos["compuesto"]["niveles"]] == [("100", "300"), ("101", "202.2")]
    assert dos["compuesto"]["cobertura"]["minutos_esperados"] == 62 and dos["compuesto"]["poc"] == "100"
    json.dumps(dos)


async def test_el_tpo_rellena_el_rango_de_cada_periodo_con_su_letra(conn, monkeypatch):
    _reloj(monkeypatch, T0 + timedelta(days=2))
    m = timedelta(minutes=1)
    await _celdas(conn, [
        (T0 + 1 * m, "binance_spot", D(100), D(1), D(0), D(100), D(0), 1, 0),
        (T0 + 1 * m, "binance_spot", D(140), D(1), D(0), D(140), D(0), 1, 0),
        (T0 + 31 * m, "binance_spot", D(120), D(1), D(0), D(120), D(0), 1, 0),
        (T0 + 31 * m, "binance_spot", D(125), D(0), D(1), D(0), D(125), 0, 1),
        (T0 + 61 * m, "binance_spot", D(150), D(1), D(0), D(150), D(0), 1, 0),
    ])
    r = await lec.tpo(conn, symbol="BTC", desde=lec.iso(T0), hasta=lec.iso(T0 + 120 * m), sesion=None, paso="10",
                      venues="binance_spot")
    s = r["sesiones"][0]
    assert [p["letra"] for p in s["periodos"]] == ["A", "B", "C", "D"] and s["periodos"][3]["lo"] is None
    assert [(n["nivel"], n["letras"]) for n in s["niveles"]] == [
        ("100", "A"), ("110", "A"), ("120", "AB"), ("130", "A"), ("140", "A"), ("150", "C")]
    # POC 120 (2 TPO); 70 % de 7 = 4.9: se anaden 130, 140 y 150 (empates: el de arriba)
    assert s["poc"] == "120" and s["value_area"] == {"val": "120", "vah": "150", "tpo": "5"} and s["tpo"] == 7
    assert s["balance_inicial"] == {"lo": "100", "hi": "140"}
    assert [(t["desde"], t["hasta"], t["extremo"]) for t in s["single_prints"]] == [
        ("100", "110", "bajo"), ("130", "150", "alto")]
    # paso automatico: los periodos con celdas tocan 41, 6 y 1 niveles al paso base; el mediano, 6
    auto = await lec.tpo(conn, symbol="BTC", desde=lec.iso(T0), hasta=lec.iso(T0 + 120 * m), sesion="dia",
                         paso="auto", venues="binance_spot")
    assert auto["paso"] == "1" and auto["paso_auto"]["niveles_periodo_mediano"] == 6
    assert r["letras"][25:28] == "Zab" and len(r["letras"]) == 48
    json.dumps(auto)


async def test_el_vwap_es_exacto_y_sus_bandas_salen_del_precio_medio_de_cada_nivel(conn, monkeypatch):
    _reloj(monkeypatch, T0 + timedelta(days=2))
    m = timedelta(minutes=1)
    await _celdas(conn, [
        (T0, "binance_spot", D(100), D(1), D(1), D("100.4"), D("100.6"), 1, 1),
        (T0 + m, "binance_spot", D(102), D(2), D(0), D("204.8"), D(0), 2, 0),
    ])
    r = await lec.vwap(conn, symbol="BTC", desde=lec.iso(T0), hasta=lec.iso(T0 + 3 * m), marco="1m", sesion=None,
                       venues="binance_spot")
    p = r["sesiones"][0]["puntos"]
    assert [(x["ts"], x["vwap"], x["sigma"]) for x in p] == [
        (lec.iso(T0), "100.5", "0"), (lec.iso(T0 + m), "101.45", "0.95"), (lec.iso(T0 + 2 * m), "101.45", "0.95")]
    # sigma^2 = (2 x (100.5 - 101.45)^2 + 2 x (102.4 - 101.45)^2) / 4 = 0.9025
    assert p[1]["bandas"] == {"1": ["100.5", "102.4"], "2": ["99.55", "103.35"], "3": ["98.6", "104.3"]}
    assert r["redondeo"] == "0.01" and r["bandas"] == [1, 2, 3]
    # una ventana que empieza despues que la sesion acumula desde el inicio de la sesion
    tarde = await lec.vwap(conn, symbol="BTC", desde=lec.iso(T0 + m), hasta=lec.iso(T0 + 3 * m), marco="1m",
                           sesion="dia", venues="binance_spot")
    assert [x["vwap"] for x in tarde["sesiones"][0]["puntos"]] == ["101.45", "101.45"]
    json.dumps(r)


async def test_las_rutas_de_of3_dicen_422_y_no_recortan_en_silencio(conn, monkeypatch):
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    desde, hasta = lec.iso(T0), lec.iso(T0 + timedelta(minutes=5))
    for ruta, extra in ((api.orderflow_sesiones, {}), (api.orderflow_tpo, {}), (api.orderflow_vwap, {"marco": "1m"})):
        ok = await ruta(_Peticion(symbol="BTC"), symbol="BTC", desde=desde, hasta=hasta, **extra)
        assert ok["as_of"].endswith("Z") and ok["sesion"]["nombre"] == "dia"
        json.dumps(ok)
        for malo in ({"sesion": "25:00-01:00"}, {"sesion": "noche"}, {"hasta": lec.iso(T0 + timedelta(days=40))}):
            with pytest.raises(HTTPException) as exc:
                await ruta(_Peticion(symbol="BTC"), **{"symbol": "BTC", "desde": desde, "hasta": hasta, **extra, **malo})
            assert exc.value.status_code == 422
        with pytest.raises(HTTPException) as exc:
            await ruta(_Peticion(symbol="BTC", hora="1"), symbol="BTC", desde=desde, hasta=hasta, **extra)
        assert exc.value.status_code == 422
    # el tope de las sesiones es de 7 dias (P1): una sesion que empezo antes que la ventana cuenta desde su inicio
    with pytest.raises(HTTPException) as exc:
        await api.orderflow_sesiones(_Peticion(symbol="BTC"), symbol="BTC", desde=lec.iso(T0 - timedelta(days=6)),
                                     hasta=lec.iso(T0 + timedelta(days=1)), sesion="23:00-22:00")
    assert exc.value.status_code == 422 and "7 dias" in exc.value.detail and "5 s" in exc.value.detail
    ok = await api.orderflow_sesiones(_Peticion(symbol="BTC"), symbol="BTC", desde=lec.iso(T0 - timedelta(days=6)),
                                      hasta=lec.iso(T0 + timedelta(days=1)), sesion="dia")
    assert len(ok["sesiones"]) == 7


# ===================================================================================================================
# OF-5a (campana 146) · LOS INDICADORES y LA ORDEN AGREGADA
# ===================================================================================================================
# Una hora entera de hace dos (las particiones de la cinta y de las sueltas van de ayer a pasado manana) y un reloj
# plantado a sus 37 min: lo que acabo hace menos de 15 min es PENDIENTE, lo de antes que falta es HUECO.
B0 = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)


def _m(minutos: float) -> datetime:
    return B0 + timedelta(minutes=minutos)


async def test_los_indicadores_dicen_hueco_pendiente_y_el_cero_certificado(conn, monkeypatch):
    monkeypatch.setattr(lec, "_ahora", lambda: _m(37))
    s = "BTCUSDT_PERP.A"
    await conn.executemany(
        "INSERT INTO open_interest(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close) VALUES ($1,$2,'5min',$3,$3,$3,$3)",
        [(_m(k), s, 1000.0 + k) for k in (0, 5, 15, 20, 25, 30)])  # faltan el de :10 (hueco) y el de :35 (pendiente)
    await conn.execute("INSERT INTO long_short_ratio(ts,symbol,interval,long_pct,short_pct,ratio) VALUES "
                       "($1,$2,'5min',55.5,44.5,1.2472)", _m(0), s)
    await conn.executemany("INSERT INTO liquidations(ts,symbol,interval,long_liq,short_liq) VALUES ($1,$2,'5min',$3,$4)",
                           [(_m(5), s, 100.5, 0.0), (_m(20), s, 0.0, 7.25)])
    barrido = {"source_start_ts": int(_m(5).timestamp()), "source_cutoff_ts": int(_m(25).timestamp())}
    await conn.execute("INSERT INTO pipeline_heartbeat(service,updated_at,status,detail) VALUES "
                       "('ingest:liquidations_history', now(), 'ok', $1)", json.dumps(barrido))
    await conn.executemany(
        """INSERT INTO liquidations_realtime(ts,symbol,exchange,side,notional_usd,price,qty,event_id)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
        [(_m(2), s, "binance", "long", 5000.5, 81000.1, 0.0617, "e1"), (_m(12), s, "bybit", "short", 120.0, 81010.0,
                                                                         0.0015, "e2")])
    d = await lec.indicadores(conn, symbol="BTC", desde=lec.iso(_m(0)), hasta=lec.iso(_m(45)), marco="5m")
    json.dumps(d)
    oi = {c["ts"]: c for c in d["series"]["oi_binance"]["cubos"]}
    assert d["cubo_minutos"] == 5 and len(oi) == 9 and d["simbolo_coinalyze"] == s
    assert oi[lec.iso(_m(5))] == {"ts": lec.iso(_m(5)), "estado": "completo", "puntos": 1, "ceros": 0, "faltan": 0,
                                  "pendientes": 0, "valores": {"oi": "1005"}}
    assert oi[lec.iso(_m(10))]["estado"] == "hueco" and oi[lec.iso(_m(10))]["valores"] is None  # nunca un cero
    assert [oi[lec.iso(_m(k))]["estado"] for k in (35, 40)] == ["pendiente", "pendiente"]
    assert [c["estado"] for c in d["series"]["oi_bybit"]["cubos"]] == ["hueco"] * 4 + ["pendiente"] * 5
    liq = {c["ts"]: c for c in d["series"]["liquidaciones"]["cubos"]}
    # fuera del barrido (:00) no se sabe; dentro, sin fila es CERO certificado; despues de su corte, pendiente
    assert [liq[lec.iso(_m(k))]["estado"] for k in (0, 5, 10, 15, 20, 25)] == \
        ["hueco", "completo", "completo", "completo", "completo", "pendiente"]
    assert liq[lec.iso(_m(10))]["ceros"] == 1 and liq[lec.iso(_m(10))]["valores"] == {"largos": "0", "cortos": "0"}
    assert liq[lec.iso(_m(5))]["valores"] == {"largos": "100.5", "cortos": "0"}
    assert d["series"]["largos_cortos"]["cubos"][0]["valores"] == {"largos": "55.5", "cortos": "44.5", "ratio": "1.2472"}
    assert [(e["exchange"], e["lado"], e["usd"]) for e in d["sueltas"]["eventos"]] == \
        [("binance", "long", "5000.5"), ("bybit", "short", "120")]
    # con velas de 15 min, un cubo por vela: el cierre de su ultimo punto, o la suma; y su estado
    q = await lec.indicadores(conn, symbol="BTC", desde=lec.iso(_m(0)), hasta=lec.iso(_m(45)), marco="15m")
    oi15 = [(c["estado"], c["valores"]) for c in q["series"]["oi_binance"]["cubos"]]
    assert oi15 == [("incompleto", {"oi": "1005"}), ("completo", {"oi": "1025"}), ("en_curso", {"oi": "1030"})]
    liq15 = [(c["estado"], c["valores"]) for c in q["series"]["liquidaciones"]["cubos"]]
    assert liq15 == [("incompleto", {"largos": "100.5", "cortos": "0"}), ("en_curso", {"largos": "0", "cortos": "7.25"}),
                     ("pendiente", None)]
    # con velas de 1 min, el cubo de 5 min que contiene `desde` (un escalon de 5 velas)
    u = await lec.indicadores(conn, symbol="BTC", desde=lec.iso(_m(3)), hasta=lec.iso(_m(13)), marco="1m")
    assert [c["ts"] for c in u["series"]["oi_binance"]["cubos"]] == [lec.iso(_m(k)) for k in (0, 5, 10)]
    for malo in ({"marco": "2m"}, {"hasta": lec.iso(_m(0) + timedelta(days=40))}):
        with pytest.raises(lec.Peticion):
            await lec.indicadores(conn, **{"symbol": "BTC", "desde": lec.iso(_m(0)), "hasta": lec.iso(_m(45)),
                                           "marco": "5m", **malo})


async def test_la_orden_agregada_es_venue_milisegundo_y_lado_y_el_vivo_pide_solo_lo_nuevo(conn, monkeypatch):
    t1 = _m(1) + timedelta(milliseconds=123)
    filas = [(t1, "binance_usdm", "100", "0.1", "10", True, "a1"), (t1, "binance_usdm", "101", "0.1", "20", True, "a2"),
             (t1, "binance_usdm", "102", "0.1", "30", True, "a3"), (t1, "binance_usdm", "100", "0.05", "5", False, "a4"),
             (t1 + timedelta(milliseconds=1), "binance_usdm", "103", "0.07", "7", True, "a5"),
             (t1, "bybit_linear", "99", "10", "1000", True, "b1"),
             (_m(10) - timedelta(seconds=5), "binance_usdm", "104", "1", "104", False, "a6")]
    await conn.executemany("""INSERT INTO orderflow_cinta(ts,venue,symbol,precio,base,usd,compra,id)
                              VALUES ($1,$2,'BTC',$3::numeric,$4::numeric,$5::numeric,$6,$7)""", filas)
    monkeypatch.setattr(lec, "_ahora", lambda: _m(10))
    d = await lec.ordenes(conn, symbol="BTC", venues="binance_usdm,bybit_linear", min_usd=None, desde=None, hasta=None,
                          limit=10)
    json.dumps(d)
    assert d["hasta"] == lec.iso(_m(10) - timedelta(seconds=8)) and d["margen_s"] == 8
    assert [(o["ts"], o["venue"], o["agresor"], o["operaciones"], o["usd"], o["precio_min"], o["precio_max"])
            for o in d["ordenes"]] == [
        (lec.iso(t1 + timedelta(milliseconds=1)), "binance_usdm", "compra", 1, "7", "103", "103"),
        (lec.iso(t1), "binance_usdm", "venta", 1, "5", "100", "100"),
        (lec.iso(t1), "binance_usdm", "compra", 3, "60", "100", "102"),
        (lec.iso(t1), "bybit_linear", "compra", 1, "1000", "99", "99")]
    grandes = await lec.ordenes(conn, symbol="BTC", venues="binance_usdm,bybit_linear", min_usd="50", desde=None,
                                hasta=None, limit=10)
    assert [o["usd"] for o in grandes["ordenes"]] == ["60", "1000"]
    # el vivo: desde el hasta servido, solo lo nuevo (la operacion de hace 5 s ya cae dentro del margen)
    monkeypatch.setattr(lec, "_ahora", lambda: _m(10) + timedelta(seconds=10))
    nuevo = await lec.ordenes(conn, symbol="BTC", venues="binance_usdm,bybit_linear", min_usd=None, desde=d["hasta"],
                              hasta=None, limit=10)
    assert [(o["usd"], o["agresor"]) for o in nuevo["ordenes"]] == [("104", "venta")]
    for malo in ({"desde": lec.iso(_m(0)).replace(".000Z", ".000500+00:00")}, {"desde": lec.iso(_m(-90))},
                 {"min_usd": "-1"}):
        with pytest.raises(lec.Peticion):
            await lec.ordenes(conn, **{"symbol": "BTC", "venues": None, "min_usd": None, "desde": None, "hasta": None,
                                       "limit": 10, **malo})


async def test_las_rutas_de_of5a_dicen_422_y_no_recortan_en_silencio(conn, monkeypatch):
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    desde, hasta = lec.iso(_m(0)), lec.iso(_m(45))
    ok = await api.orderflow_indicadores(_Peticion(symbol="BTC"), symbol="BTC", desde=desde, hasta=hasta, marco="5m")
    assert ok["as_of"].endswith("Z") and len(ok["series"]) == 6
    json.dumps(ok)
    ok = await api.orderflow_ordenes(_Peticion(symbol="BTC"), symbol="BTC", limit=5)
    assert ok["ordenes"] == [] and ok["as_of"].endswith("Z")
    for ruta, kw in ((api.orderflow_indicadores, {"desde": desde, "hasta": hasta}), (api.orderflow_ordenes, {})):
        with pytest.raises(HTTPException) as exc:
            await ruta(_Peticion(symbol="BTC", hora="1"), symbol="BTC", **kw)
        assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc:
        await api.orderflow_ordenes(_Peticion(symbol="BTC"), symbol="BTC", desde=lec.iso(_m(-120)), limit=5)
    assert exc.value.status_code == 422 and "60 min" in exc.value.detail
