"""151-A · LA CAPA HONDA DEL LIBRO: el parseo de books-full (OKX) y merge-depth (Bitget), la regla del cubo, la frontera
con lo vivo y el rancio.

Las respuestas tienen la forma EXACTA de los venues (grabadas desde 143 el 2026-11-03, x1-tmp/c151/crudos), recortadas
a pocos niveles para que cada caso se lea entero.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

import asyncpg
import pytest

from app import libro_honda as lh
from app import libro_lectura as lec

ROOT = Path(__file__).resolve().parents[1]
OKX = (b'{"code":"0","msg":"","data":[{"asks":[["77530.1","120","0","3"],["77530.5","5","0","1"],'
       b'["77541.0","300","0","2"],["77555.3","1","0","1"]],"bids":[["77530","7","0","1"],["77521.2","40","0","2"],'
       b'["77510.0","2","0","1"],["77498.9","1000","0","9"]],"ts":"1793734711002"}]}')
BITGET = (b'{"code":"00000","msg":"success","requestTime":1793734711778,"data":{"asks":[[77530.0,9.2548],'
          b'[77540.0,22.9972]],"bids":[[77520.0,10.6957],[77510.0,42.1327],[77500.0,1.5],[77490.0,0.25]],'
          b'"ts":1793734711778,"scale":"10","precision":"scale2","isMaxPrecision":"NO"}}')
OKX_BTC = next(f for f in lh.FUENTES if (f.venue, f.activo) == ("okx_swap", "BTC"))
BITGET_BTC = next(f for f in lh.FUENTES if (f.venue, f.activo) == ("bitget_usdt", "BTC"))


def test_books_full_en_contratos_por_ctval_y_exacto():
    f = lh.parsea(OKX_BTC, OKX)
    assert f.ts_ms == 1793734711002
    assert f.lados["b"][1] == (D("77521.2"), D("0.40"))  # 40 contratos x ctVal 0.01
    assert f.lados["a"][0] == (D("77530.1"), D("1.20"))


def test_merge_depth_en_decimal_sin_pasar_por_float():
    f = lh.parsea(BITGET_BTC, BITGET)
    assert f.lados["b"][0] == (D("77520.0"), D("10.6957")) and isinstance(f.lados["b"][0][1], D)
    with pytest.raises(ValueError):
        lh.parsea(BITGET_BTC, b'{"code":"40001","msg":"x","data":null}')


def test_el_cubo_se_mide_con_los_precios_y_solo_vale_si_parte_el_paso():
    assert lh.cubo([D("77520.0"), D("77510.0"), D("77490.0")]) == D("10")
    assert lh.cubo([D("77530.1"), D("77530.5"), D("77541.0")]) == D("0.1")
    assert lh.parte([D("77520.0"), D("77510.0")], D("10"), "suelo")
    assert not lh.parte([D("77500"), D("77400")], D("10"), "suelo")  # scale3: cubo 100 no parte 10
    assert not lh.parte([D("77525"), D("77515")], D("10"), "suelo")  # cubo 10 desplazado: los bordes no coinciden
    assert not lh.parte([D("77530.0"), D("77540.0")], D("10"), "techo")  # la venta de Bitget: (P - c, P]
    assert lh.parte([D("1.0"), D("1.1")], D("0.5"), "suelo")  # cubo 0.1 parte 0.5 ...
    assert not lh.parte([D("2287"), D("2288")], D("0.5"), "suelo")  # ... cubo 1 no (bitget ETH scale2)
    assert lh.parte([D("93.19"), D("93.18")], D("0.02"), "suelo")  # SOL scale1


def test_la_escalera_honda_empieza_donde_acaba_lo_vivo_y_no_corta_un_nivel():
    f = lh.parsea(OKX_BTC, OKX)
    # el vivo conoce la compra hasta 77525 (entero el nivel 77530) y la venta hasta 77540 (entero el 77530)
    b = lh.escalera_honda(f.lados["b"], "b", D("10"), D("77525"), D("77530"))
    a = lh.escalera_honda(f.lados["a"], "a", D("10"), D("77540"), D("77530"))
    # compra: 77520 (77521.2 x 0.40), 77510 (77510.0), y 77500 NO: la foto solo llega a 77498.9 ... que si lo cubre
    assert b == (D("77520"), [D("0.40"), D("0.02"), D("0")], D("77498.9"))
    # venta: 77540 (77541.0); 77550 no: 77550 + 10 > 77555.3, la foto no lo cubre entero
    assert a == (D("77540"), [D("3.00")], D("77555.3"))


def test_la_escalera_honda_para_en_el_dos_por_ciento():
    pares = [(D(100) - D(i) / 10, D(1)) for i in range(0, 400)]  # hasta 60.1, a paso 0.1
    desde, qs, _ = lh.escalera_honda(pares, "b", D("1"), D("99.5"), D("100"))
    assert desde == D("99") and desde - (len(qs) - 1) == D("98")  # suelo(100 x 0.98) = 98


def test_bitget_guarda_la_compra_y_nunca_la_venta():
    f = lh.parsea(BITGET_BTC, BITGET)
    t = lh.fila(BITGET_BTC, f, 1793734710, (D("77515"), D("77535")), D("77525"), "x")
    assert t[10] == D("77510") and t[11] == [D("42.1327"), D("1.5"), D("0.25")]  # 77510: el vivo lo ve a medias
    assert t[12] is None and t[13] is None and t[15] is None  # la venta: (P - c, P] no parte el nivel


def test_junta_quita_lo_que_el_vivo_de_ahora_ya_conoce_y_lo_rancio():
    t0 = datetime(2026, 11, 3, tzinfo=UTC)
    lado = (D("77500"), [D(1), D(2), D(3)])
    assert lh.junta(lado, "b", D("10"), D("77510"), t0, t0 + timedelta(seconds=5)) == lado
    assert lh.junta(lado, "b", D("10"), D("77495"), t0, t0) == (D("77490"), [D(2), D(3)])  # el vivo llega a 77495: 77490 a medias
    assert lh.junta(lado, "a", D("10"), D("77515"), t0, t0) == (D("77510"), [D(2), D(3)])
    assert lh.junta(lado, "b", D("10"), D("77510"), t0, t0 + timedelta(seconds=lh.RANCIA_S + 1)) is None


def test_una_foto_rancia_se_sirve_sin_niveles():
    t0 = datetime(2026, 11, 3, tzinfo=UTC)
    f = {"ts": t0, "venue": "okx_swap", "ts_libro": t0, "fuente": "x", "paso": D(10), "cubo": D("0.1"),
         "precio": D(1), "vivo_compra": D(1), "vivo_venta": D(2), "compra_nivel": D(0), "compras": [D(1)],
         "venta_nivel": None, "ventas": None, "alcance_compra": D(1), "alcance_venta": None}
    assert lec.honda_fila(f, t0 + timedelta(seconds=lh.RANCIA_S))["compras"] == {"desde": "0", "cantidades": ["1"]}
    viejo = lec.honda_fila(f, t0 + timedelta(seconds=lh.RANCIA_S + 0.001))
    assert viejo["rancia"] and viejo["compras"] is None and viejo["alcance"]["compra"] == "1"


@pytest.fixture
async def conn():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    schema = f"honda_{uuid.uuid4().hex}"
    c = await asyncpg.connect(dsn)
    await c.execute(f'CREATE SCHEMA "{schema}"')
    await c.execute(f'SET search_path TO "{schema}", public')
    await c.execute((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
    try:
        yield c
    finally:
        await c.execute("SET search_path TO public")
        await c.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await c.close()


async def test_lo_guardado_se_sirve_con_su_hora_y_su_alcance_y_lo_rancio_sin_niveles(conn):
    ahora = await conn.fetchval("SELECT date_trunc('second', now())")
    f = lh.parsea(OKX_BTC, OKX)
    f.ts_ms = int(ahora.timestamp() * 1000) - 2000
    t = lh.fila(OKX_BTC, f, int(ahora.timestamp()) - 1, (D("77525"), D("77540")), D("77530"), "books-full")
    await conn.execute(lh.HONDA_SQL, *t)
    r = await lec.honda(conn, symbol="BTC", venues=None, desde=None, hasta=None, ahora=ahora)
    (o,) = r["fotos"]
    assert o["venue"] == "okx_swap" and not o["rancia"] and o["alcance"] == {"compra": "77498.9", "venta": "77555.3"}
    assert o["compras"]["desde"] == "77520" and [D(q) for q in o["compras"]["cantidades"]] == [D("0.4"), D("0.02"), 0]
    r = await lec.honda(conn, symbol="BTC", venues=None, desde=None, hasta=None, ahora=ahora + timedelta(seconds=80))
    assert r["fotos"][0]["rancia"] and r["fotos"][0]["compras"] is None
    ref = await lec.referencia(conn)
    assert ref["honda"]["rancia_s"] == 75 and "binance_usdm" in ref["honda"]["fuera"]
