"""BOT-5: la candidata en sombra (app/bot/sombra.py). La base, con TEST_DATABASE_URL (si no, se salta)."""
import hashlib
import json
import os
import pathlib
import re
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest

from app import anatomia as A
from app.bot import servicio as sv
from app.bot import sombra as sb

RAIZ = pathlib.Path(__file__).resolve().parent.parent
T0 = A._ts("2026-10-21")
MIN = 60


def test_la_candidata_congelada_se_carga_y_un_byte_cambiado_no(tmp_path):
    cs = sb.carga()
    assert len(cs) == 1
    c = cs[0]
    assert (c.simbolo, c.lado, c.w, c.esquema, c.umbral, c.estricto) == ("SOL", -1, 60, "E1", -479834.70166359004, False)
    assert c.columna == A.COL["ds100k"] and c.venues == A.VENUES_SPOT and c.minimo == A.GRANDE_100K
    b = sb.CANDIDATAS.read_bytes()
    assert hashlib.sha256(b).hexdigest() == sb.CANDIDATAS_SHA
    otra = tmp_path / "c.json"
    otra.write_bytes(b.replace(b"-479834.70166359004", b"-479834.7"))
    with pytest.raises(ValueError, match="sha256"):
        sb.carga(otra)
    d = json.loads(b)
    d["congeladas"][0]["comision_salida"] = 0.0
    otra.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="comision"):
        sb.carga(otra, sha=hashlib.sha256(otra.read_bytes()).hexdigest())


def test_wilson_y_el_texto_de_la_cuenta():
    lo, hi = sb.wilson(37, 78)
    assert abs(lo - 0.3666) < 1e-3 and abs(hi - 0.5847) < 1e-3
    c = sb.carga()[0]
    t = sb.texto_cuenta(c, {"desde": datetime(2026, 11, 7, tzinfo=UTC), "disparos": 3, "resueltas": 2, "exitos": 1,
                            "sin_dato": 1})
    assert "SIN CALIBRAR" in t and "equilibrio 44.4%" in t and "azar 37.5%" in t and "IC95" in t
    assert "SIN CALIBRAR" not in sb.texto_cuenta(c, {"desde": None, "disparos": 30, "resueltas": 30, "exitos": 15,
                                                     "sin_dato": 0})
    for x in (t, sb.NO_MEDIDA, sb.orden_calc(c, {"entrada": 100.0})):
        assert not re.search(r"\b(compra|vende|entra)\b", x, re.I), x
    # 1 USD al stop con la comision: margen x apalancamiento x (0.6 % + 2 x 5.5 bps) = 1
    o = sb.orden_calc(c, {"entrada": 100.0})
    assert o == "/calc sol 100 100.6 99 14.08$ 10x corto"


# ------------------------------------------------------------------------- el escenario
def escenario():
    """Precio de SOL plano a 100 en binance_usdm, una venta de contado de 500k en el minuto 70 (decision 74), el
    precio toca el objetivo (-1 %) en el 100 y se queda en 99; falta el minuto 330 de precio. Un perpetuo de -900k en
    el 20 y un 99999 de contado no cuentan."""
    filas = []
    for m in range(0, 420):
        if m == 330:
            continue
        p = 100.0 if m < 100 else 99.0
        lo = 98.9 if m == 100 else p
        for k, (pr, s) in enumerate(((p, 1), (lo, 2), (p, 3))):
            filas.append((T0 + m * MIN + s, "binance_usdm", "SOL", pr, 1000.0, k % 2 == 0, f"u{m}-{k}"))
    filas.append((T0 + 70 * MIN + 30, "binance_spot", "SOL", 100.0, 500000.0, False, "s70"))
    filas.append((T0 + 20 * MIN + 30, "bybit_linear", "SOL", 100.0, 900000.0, False, "p20"))
    filas.append((T0 + 72 * MIN + 30, "okx_spot", "SOL", 100.0, 99999.0, False, "s72"))
    return filas


def test_paso_puro_dispara_sin_solape_y_sin_dato():
    c = sb.carga()[0]
    mm: dict = {}
    sb.pliega([(datetime.fromtimestamp(t, UTC), v, p, u, b) for t, v, s, p, u, b, _ in escenario()], mm)
    flujo = lambda m: mm[m][c.columna] if m in mm else 0.0  # noqa: E731
    barra = lambda m: None if m not in mm else tuple(mm[m][A.COL[k]] for k in "ohlc")  # noqa: E731
    filas, hasta = [], T0 + 59 * MIN
    for ultimo in range(T0 + 60 * MIN, T0 + 420 * MIN, 7 * MIN):  # a saltos: el resultado no depende del ritmo
        nuevas, hasta = sb.paso(c, filas, hasta, ultimo, flujo, barra)
        filas += nuevas
    r = [(f["minuto"] // 60 - T0 // 60, f["estado"], f["exito"], f["salida"] and f["salida"] // 60 - T0 // 60) for f in filas]
    assert r == [(74, "exito", 1, 100), (104, "sin_dato", None, 330)]
    assert filas[0]["entrada"] == 100.0 and abs(filas[0]["neto"] - (0.01 - 2 * A.COMISION)) < 1e-15


# ------------------------------------------------------------------------- la base
@pytest.fixture
async def base():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    esquema = f"sombra_{uuid.uuid4().hex}"
    c = await asyncpg.connect(dsn)
    await c.execute(f'CREATE SCHEMA "{esquema}"')
    await c.execute(f'SET search_path TO "{esquema}", public')
    await c.execute("CREATE TABLE orderflow_cinta (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL,"
                    " precio numeric NOT NULL, base numeric NOT NULL DEFAULT 1, usd numeric NOT NULL,"
                    " compra boolean NOT NULL, id text NOT NULL)")
    sql = (RAIZ / "sql" / "schema.sql").read_text()
    await c.execute(sql[sql.index("-- CAMPANA BOT-2"):])
    try:
        yield c
    finally:
        await c.execute("SET search_path TO public")
        await c.execute(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE')
        await c.close()


async def _carga(base):
    await base.executemany(
        "INSERT INTO orderflow_cinta (ts, venue, symbol, precio, usd, compra, id) VALUES (to_timestamp($1), $2, $3, $4, $5,"
        " $6, $7)", [(float(t), v, s, p, u, b, i) for t, v, s, p, u, b, i in escenario()])


async def _filas(base):
    return [tuple(x) for x in await base.fetch(
        "SELECT (extract(epoch FROM minuto)::bigint - $1) / 60, estado, exito, neto, (extract(epoch FROM salida)::bigint - $1)"
        " / 60, entrada, motivo FROM bot_sombra ORDER BY minuto", T0)]


async def test_la_sombra_en_la_base_un_reinicio_no_duplica_ni_pierde(base):
    await _carga(base)
    s = sb.Sombra(base, {})
    vistas = []
    for m in range(60, 430):
        if m == 200:
            s = sb.Sombra(base, {})  # reinicio: el cursor y las vivas salen de la tabla
        vistas += [(f["minuto"] - T0) // 60 for f in await s.tic(T0 + m * MIN + sb.CIERRE_S + MIN)]
        if m == 120:
            assert [x[1] for x in await _filas(base)] == ["tocada", "abierta"]
    assert vistas == [74, 104]
    r = await _filas(base)
    neto = 0.01 - 2 * A.COMISION
    assert r == [(74, "exito", 1, neto, 100, 100.0, "objetivo"), (104, "sin_dato", None, None, 330, 99.0, "sin precio 10-21 05:30Z")]
    hasta = await base.fetchval("SELECT (extract(epoch FROM hasta)::bigint - $1) / 60 FROM bot_sombra_candidata", T0)
    assert hasta == 428
    # otra vuelta entera desde el principio no anade nada: la clave manda
    for m in (300, 429):
        assert await sb.Sombra(base, {}).tic(T0 + m * MIN + sb.CIERRE_S + MIN) == []
    assert await _filas(base) == r
    k = await sb.cuenta(base, sb.carga()[0])
    assert (k["disparos"], k["resueltas"], k["exitos"], k["sin_dato"]) == (2, 1, 1, 1)
    # lo final no se toca, el cursor no retrocede
    for q in ("UPDATE bot_sombra SET exito = 0 WHERE estado = 'exito'", "DELETE FROM bot_sombra",
              "UPDATE bot_sombra_candidata SET hasta = hasta - interval '1 hour'", "DELETE FROM bot_sombra_candidata"):
        with pytest.raises(asyncpg.exceptions.ObjectNotInPrerequisiteStateError):
            await base.execute(q)


async def test_el_primer_arranque_no_mira_atras(base):
    await _carga(base)
    assert await sb.Sombra(base, {}).tic(T0 + 200 * MIN + sb.CIERRE_S + MIN) == []
    assert await _filas(base) == []
    d, h = await base.fetchrow("SELECT (extract(epoch FROM desde)::bigint - $1) / 60, (extract(epoch FROM hasta)::bigint"
                               " - $1) / 60 FROM bot_sombra_candidata", T0)
    assert (d, h) == (200, 199)


@pytest.mark.parametrize("avisa", ["", "1"])
async def test_entrada_el_parte_y_el_interruptor(base, monkeypatch, avisa):
    await _carga(base)
    mandados = []

    async def manda(texto):
        mandados.append(texto)
        return True

    async def calcula(texto):
        return f"CALC {texto}"

    bot = sv.Bot({"BOT_SOMBRA_AVISA": avisa}, base, None)
    monkeypatch.setattr(bot, "manda", manda)
    monkeypatch.setattr(bot, "calcula", calcula)
    reloj = iter(range(60, 80))
    monkeypatch.setattr(sb, "ultimo_cerrado", lambda ahora: T0 + next(reloj) * MIN)
    for _ in range(60, 80):
        await bot.tic_sombra()
    if avisa:
        assert len(mandados) == 1 and sb.NO_MEDIDA in mandados[0]
        assert "CALC /calc sol 100 100.6 99 14.08$ 10x corto" in mandados[0]
    else:
        assert mandados == []
    e = await bot.atiende("/entrada")
    assert e.startswith(sv.ENTRADAS) and "En sombra" in e and "1 disparos" in e and "SIN CALIBRAR" in e
    assert (await bot.texto_sombra(corto=True)).startswith("SOMBRA SOL corto si ds100k_60 <= -479834.70")
