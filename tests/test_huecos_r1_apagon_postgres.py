"""huecos-r1 (H-01 + N2) con la FORMA REAL: las filas de data_gap de 140 que tocan el apagon del 2026-11-16.

El fixture son las filas de ohlcv_1min/ohlcv_5min que el operador exporto de 140 el 2026-11-22 (ids reales). En 140 el
recuperador ya habia partido los padres por el reloj de la fuente: los hijos de 11-17 00:17 en adelante estan
'recovered', los de 11-16 15:31 a 11-17 00:17 siguen 'unresolved' (la fuente ya no los sirve), y los 75 padres seguian
abiertos TAPANDO lo repuesto: la sonda h01 daba 13 de 13 velas de 1 h sin precio. Tres de esos padres (832197-832199,
15:31 a 23:34/23:36) se detectaron DESPUES de partir y su borde cae dentro de un hijo: es N2.

RECUPERA-R1 paso sus pruebas sinteticas y fallo en produccion; esta va sobre las filas de alli.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

import app.api as api
import scripts.recupera_huecos as recupera
from app.data_gaps import BLOQUEA_SQL, PARTITION_DETECTION_SOURCE
from app.ingest import upsert_ohlcv

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
FIXTURE = json.loads((ROOT / "tests/fixtures/data_gap_apagon_20261116.json").read_text(encoding="utf-8"))
SYM = "BTCUSDT_PERP.A"
SIMBOLOS = frozenset({"BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A"})
MIN = timedelta(minutes=1)
H = timedelta(hours=1)
AHORA = datetime(2026, 11, 22, 12, 39, tzinfo=UTC)  # la hora a la que la sonda de 140 dio ROJO
# Lo que ve la sonda h01 (fable_dz2_sonda.py): /api/ohlcv 1hour limit=120 a esa hora, dentro de su ventana del apagon.
SONDA = (datetime(2026, 11, 17, 13, tzinfo=UTC), datetime(2026, 11, 18, 2, tzinfo=UTC))
SIN_DATO = (datetime(2026, 11, 16, 15, 31, tzinfo=UTC), datetime(2026, 11, 17, 0, 17, tzinfo=UTC))


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def base():
    schema = f"huecos_r1_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    await conn.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
    await conn.execute("INSERT INTO symbols(symbol,base_asset) VALUES($1,'BTC') ON CONFLICT DO NOTHING", SYM)
    try:
        await _carga(conn)
        yield conn
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def _carga(conn) -> None:
    """Las filas reales, en el orden de sus ids; lo que el fixture no trae se rellena con lo que exige el esquema."""
    hecho = datetime(2026, 11, 18, 12, tzinfo=UTC)
    filas = []
    for valores in FIXTURE["filas"]:
        r = dict(zip(FIXTURE["columnas"], valores, strict=True))
        abierto = r["status"] == "unresolved"
        filas.append((
            r["feed"], r["exchange"], r["market"], r["symbol"], r["granularity"],
            datetime.fromisoformat(r["start_ts"]), datetime.fromisoformat(r["end_ts"]),
            MIN if r["granularity"] == "1min" else 5 * MIN, f"fila real de 140, id {r['id']}", r["detection_source"],
            r["status"], None if abierto else hecho, None if abierto else "cadence reconciliation (140)",
            "{}" if abierto else '{"method": "cadence_reconciliation"}',
        ))
    await conn.executemany(
        """
        INSERT INTO data_gap(feed, feed_class, exchange, market, symbol, granularity, start_ts, end_ts,
          expected_cadence, evidence_type, detection_reason, detection_source, status, resolved_at, recovered_at,
          resolution_reason, recovery_metadata)
        VALUES($1, 'cadence', $2, $3, $4, $5, $6, $7, $8, 'missing_interval', $9, $10, $11, $12, $12, $13, $14::jsonb)
        """,
        filas,
    )
    assert await conn.fetchval("SELECT count(*) FROM data_gap") == len(FIXTURE["filas"]) == 284


async def _planta_velas(conn) -> None:
    """Lo que 140 tiene de BTC: lo que cubren sus filas 1min 'recovered' (de 11-17 00:17) y la serie viva despues."""
    ini, fin = datetime(2026, 11, 17, 0, 17, tzinfo=UTC), datetime(2026, 11, 18, 6, tzinfo=UTC)
    velas = []
    t = ini
    while t < fin:
        velas.append({"t": int(t.timestamp()), "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 10, "bv": 5, "tx": 3, "btx": 1})
        t += MIN
    await upsert_ohlcv(conn, {SYM: velas}, {SYM: SYM}, int(ini.timestamp()), int(fin.timestamp()), "1min")


class _Pool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        conn = self.conn

        class Ctx:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *_):
                return False

        return Ctx()


class FuenteQueNoSeLlama:
    async def history(self, *_a, **_k):
        raise AssertionError("cerrar un padre teselado no pregunta a la fuente")


async def _padres_abiertos(conn) -> int:
    return await conn.fetchval(
        "SELECT count(*) FROM data_gap WHERE status='unresolved' AND detection_source <> $1", PARTITION_DETECTION_SOURCE
    )


async def _minutos_tapados(conn) -> int:
    """Buckets de una fila 'recovered' (el dato ESTA) que una fila que bloquea sigue tapando, por identidad."""
    return await conn.fetchval(
        f"""
        WITH rec AS (
          SELECT DISTINCT feed, exchange, market, symbol, granularity, b
            FROM data_gap r, generate_series(r.start_ts, r.end_ts - r.expected_cadence, r.expected_cadence) b
           WHERE r.status = 'recovered')
        SELECT count(*) FROM rec
         WHERE EXISTS (SELECT 1 FROM data_gap g
                        WHERE g.feed=rec.feed AND g.exchange=rec.exchange AND g.market=rec.market
                          AND g.symbol=rec.symbol AND g.granularity=rec.granularity
                          AND {BLOQUEA_SQL} AND g.start_ts <= rec.b AND g.end_ts > rec.b)
        """  # noqa: S608 -- constante
    )


async def _sonda(conn, monkeypatch) -> tuple[int, int, list[dict]]:
    """(sin precio, velas) de 1 h en la ventana de la sonda h01, y lo declarado, por la ruta real /api/ohlcv."""
    monkeypatch.setattr(api, "validate_symbol", lambda s: s)
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)
    r = await api.ohlcv(SYM, interval="1hour", limit=120)
    dentro = [f for f in r["rows"] if SONDA[0] <= f["bucket"] < SONDA[1]]
    return sum(f["close"] is None for f in dentro), len(dentro), r["data_gaps"]["declared"]


def _cubre(declarados: list[dict], ini: datetime, fin: datetime) -> bool:
    """La union de lo declarado cubre [ini, fin) sin hueco (se declara hijo a hijo, no de una pieza)."""
    for d in sorted(declarados, key=lambda d: d["start"]):
        if datetime.fromisoformat(d["start"]) <= ini:
            ini = max(ini, datetime.fromisoformat(d["end"]))
    return ini >= fin


async def _k04_particion(conn, padre: int) -> bool:
    """El predicado de harness/checks/K04-huecos.sh para partitioned_by_source_coverage, sobre la fila del padre."""
    return await conn.fetchval(
        """
        SELECT g.recovery_metadata->>'partition_detection_source' IS NOT NULL
          AND (SELECT count(*) >= 1
                      AND sum(least(h.end_ts, g.end_ts) - greatest(h.start_ts, g.start_ts)) = g.end_ts - g.start_ts
                 FROM data_gap h
                WHERE h.feed=g.feed AND h.exchange=g.exchange AND h.market=g.market
                  AND h.symbol=g.symbol AND h.granularity=g.granularity
                  AND h.detection_source=g.recovery_metadata->>'partition_detection_source'
                  AND h.id <> g.id AND h.start_ts < g.end_ts AND h.end_ts > g.start_ts)
          AND NOT EXISTS (
                SELECT 1 FROM data_gap a JOIN data_gap b
                    ON b.id > a.id
                   AND b.feed=a.feed AND b.exchange=a.exchange AND b.market=a.market
                   AND b.symbol=a.symbol AND b.granularity=a.granularity
                   AND b.detection_source=a.detection_source
                   AND b.id <> g.id AND b.start_ts < g.end_ts AND b.end_ts > g.start_ts
                   AND a.start_ts < b.end_ts AND b.start_ts < a.end_ts
                 WHERE a.feed=g.feed AND a.exchange=g.exchange AND a.market=g.market
                   AND a.symbol=g.symbol AND a.granularity=g.granularity
                   AND a.detection_source=g.recovery_metadata->>'partition_detection_source'
                   AND a.id <> g.id AND a.start_ts < g.end_ts AND a.end_ts > g.start_ts)
        FROM data_gap g WHERE g.id=$1
        """,
        padre,
    )


async def test_la_primera_pasada_del_timer_cierra_los_padres_y_destapa_lo_repuesto(base, monkeypatch) -> None:
    conn = base
    await _planta_velas(conn)
    antes_abiertos, antes_tapados = await _padres_abiertos(conn), await _minutos_tapados(conn)
    sin, velas, _ = await _sonda(conn, monkeypatch)
    assert (antes_abiertos, sin, velas) == (75, 13, 13), "en main: 75 padres abiertos y la sonda h01 ROJO 13 de 13"
    assert antes_tapados == 3 * 1504, antes_tapados  # de 11-17 00:17 a 11-18 01:21 (fin del padre 824981), por simbolo

    huella = await conn.fetchval("SELECT md5(string_agg(id || status, ',' ORDER BY id)) FROM data_gap")
    seco = await recupera.parte(conn, FuenteQueNoSeLlama(), ahora=AHORA, permitidos=SIMBOLOS, seco=True)
    assert huella == await conn.fetchval("SELECT md5(string_agg(id || status, ',' ORDER BY id)) FROM data_gap")

    # La primera pasada del timer (sin --parte), con la fuente sin llamar: lo que 140 hara tras desplegar.
    resumen = await recupera.recupera(conn, FuenteQueNoSeLlama(), ahora=AHORA, permitidos=SIMBOLOS)
    despues = (await _padres_abiertos(conn), await _minutos_tapados(conn), *(await _sonda(conn, monkeypatch))[:2])
    assert despues == (0, 0, 0, 13), "(padres abiertos, buckets recovered tapados, velas sin precio, velas) tras la pasada"
    assert (resumen.get("padres_cerrados"), resumen.get("padres_abiertos"), resumen["pedidas"]) == (75, 0, 0), resumen
    _, _, declarados = await _sonda(conn, monkeypatch)
    # La ruta declara solo dentro de lo que sirve (desde la vela de 11-17 00:00): ahi el hijo abierto 23:17-00:17 sigue.
    assert _cubre(declarados, datetime(2026, 11, 17, tzinfo=UTC), SIN_DATO[1]), [(d["start"], d["end"]) for d in declarados]
    assert await conn.fetchval(
        "SELECT count(*) FROM data_gap WHERE status='unresolved' AND detection_source=$1", PARTITION_DETECTION_SOURCE
    ) == 24, "los 8 hijos abiertos de cada simbolo siguen abiertos: no se archiva nada"
    # Lo que el modo en seco decia que destaparia es lo que la pasada destapo (BTC, el unico con velas).
    # 00:17 al fin de la union de padres de BTC (11-18 01:21): 1504 minutos.
    assert seco.get("destaparia") == (datetime(2026, 11, 18, 1, 21, tzinfo=UTC) - SIN_DATO[1]) // MIN, seco

    cerrados = await conn.fetch(
        "SELECT id, status, recovery_metadata->>'method' AS m FROM data_gap WHERE detection_source <> $1"
        " AND status='unrecoverable'", PARTITION_DETECTION_SOURCE,
    )
    assert len(cerrados) == 75 and {(c["status"], c["m"]) for c in cerrados} == {("unrecoverable", "partitioned_by_source_coverage")}
    for c in cerrados:
        assert await _k04_particion(conn, c["id"]), f"K04 re-deriva la particion de {c['id']}"

    segunda = await recupera.recupera(conn, FuenteQueNoSeLlama(), ahora=AHORA, permitidos=SIMBOLOS)
    assert (segunda["padres_cerrados"], segunda["padres_abiertos"]) == (0, 0)


async def test_n2_un_padre_partido_antes_con_otro_borde_no_queda_saltado(base) -> None:
    """--parte sobre la union de BTC: su rejilla trae el borde 23:34 del padre 832197, la particion previa no lo tiene.
    Antes saltaba la union entera PARA SIEMPRE; ahora sigue saltando el partir, pero cierra lo que ya esta teselado."""
    conn = base
    await _planta_velas(conn)
    resumen = await recupera.parte(conn, FuenteQueNoSeLlama(), ahora=AHORA, permitidos=frozenset({SYM}), seco=False)
    (info,) = [u for u in resumen["uniones"] if u["feed"] == "ohlcv_1min"]
    assert info["salta"] == "particion_previa_distinta", info
    assert (info.get("padres_cerrados"), info.get("padres_abiertos")) == (25, 0), info
    n2 = await conn.fetchval(
        "SELECT count(*) FROM data_gap WHERE symbol=$1 AND detection_source <> $2 AND status='unrecoverable'"
        " AND end_ts = '2026-11-16 23:34+00'", SYM, PARTITION_DETECTION_SOURCE,
    )
    assert n2 == 1, "el padre cuyo borde cae dentro de un hijo tambien se cierra"
    assert resumen["pedidas"] == 0


async def test_cerrar_se_niega_si_dos_hijos_se_solapan(base) -> None:
    """Un solape puede compensar un hueco en la suma: el cierre recorre la teselacion, y K04 suma Y mira el solape.
    Sobre el padre real 832197 (15:31-23:34, el de N2): sus hijos 17:58-18:17 y 20:17-21:17 se tocan 10 min."""
    conn = base

    async def solape(on: bool) -> None:  # 17:58-18:17 pasa a acabar 18:27: pisa al 18:17-19:17
        await conn.execute(
            "UPDATE data_gap SET end_ts=$3 WHERE symbol=$1 AND detection_source=$2 AND start_ts='2026-11-16 17:58+00'",
            SYM, PARTITION_DETECTION_SOURCE, datetime(2026, 11, 16, 18, 27 if on else 17, tzinfo=UTC),
        )

    async def hueco(on: bool) -> None:  # 20:17-21:17 pasa a empezar 20:27: deja 10 min sin cuenta
        await conn.execute(
            "UPDATE data_gap SET start_ts=$3 WHERE symbol=$1 AND detection_source=$2 AND end_ts='2026-11-16 21:17+00'",
            SYM, PARTITION_DETECTION_SOURCE, datetime(2026, 11, 16, 20, 27 if on else 17, tzinfo=UTC),
        )

    padre = await conn.fetchval(
        "SELECT id FROM data_gap WHERE symbol=$1 AND end_ts='2026-11-16 23:34+00' AND detection_source <> $2",
        SYM, PARTITION_DETECTION_SOURCE,
    )
    from app.data_gaps import close_partitioned_gap

    await solape(True)
    await hueco(True)  # misma suma que la ventana del padre
    with pytest.raises(ValueError, match="overlap"):
        await close_partitioned_gap(conn, gap_id=padre, proof_source="prueba")
    await solape(False)
    with pytest.raises(ValueError, match="do not tile"):
        await close_partitioned_gap(conn, gap_id=padre, proof_source="prueba")
    await hueco(False)
    assert await close_partitioned_gap(conn, gap_id=padre, proof_source="prueba") == "unrecoverable"
    assert await _k04_particion(conn, padre)
    # Lo que K04 vigila: que la afirmacion siga en pie si despues alguien mueve un hijo.
    await solape(True)
    await hueco(True)
    assert not await _k04_particion(conn, padre), "un solape que compensa un hueco en la suma"
    await solape(False)
    assert not await _k04_particion(conn, padre), "un hueco"
