"""RECUPERA R1: el hueco que CRUZA el reloj de la fuente, con la forma del apagon del 2026-11-16, en base desechable.

EL DEFECTO. El apagon (11-16 15:31Z a 11-18 02:05Z) dejo padres ohlcv_1min de ~34 h con las ultimas ~24 h ya en la base.
reconcile solo recupera una fila con TODOS sus buckets, el recuperador no pide nada que empiece fuera del reloj de la
fuente y blocking_requirement_keys bloqueaba todo 'unrecoverable': /api/ohlcv servia sin precio minutos que estaban.

LO QUE SE EXIGE (recupera_huecos.py --parte): antes, las velas del tramo con dato salen sin precio; despues, con precio,
la parte vieja sigue declarada como hueco, los padres quedan cerrados con la prueba que K04 re-deriva, y con la fuente
MUDA no se archiva ni se destapa nada. En seco no escribe ni pregunta.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

import app.api as api
import scripts.recupera_huecos as recupera
from app.data_gaps import PARTITION_DETECTION_SOURCE, reconcile_cadence_coverage, record_data_gap
from app.ingest import upsert_ohlcv

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SYM = "BTCUSDT_PERP.A"
MIN = timedelta(minutes=1)
H = timedelta(hours=1)
IDENT = {"feed": "ohlcv_1min", "exchange": "binance", "market": "perpetual", "symbol": SYM, "granularity": "1min"}
# Alineado a 5 min: si no, la vela de 5 min que cruza -25 h mezcla minutos de las dos partes y sale tapada (con razon).
_T = datetime.now(UTC).replace(second=0, microsecond=0)
AHORA = _T - timedelta(minutes=_T.minute % 5)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def base():
    schema = f"recupera_r1_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    await conn.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
    await conn.execute("INSERT INTO symbols(symbol,base_asset) VALUES($1,'BTC') ON CONFLICT DO NOTHING", SYM)
    try:
        yield conn
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


def _vela(t: datetime) -> dict:
    return {"t": int(t.timestamp()), "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 10, "bv": 5, "tx": 3, "btx": 1}


class FuenteReloj:
    """La fuente con RELOJ: sirve cada bucket de [start, end) solo si es mas nuevo que ahora - horizonte de su
    intervalo (1min 24 h, 5min 192 h), o nada si esta muda. Apunta cada peticion."""

    reloj = {"1min": (MIN, timedelta(hours=24)), "5min": (timedelta(minutes=5), timedelta(hours=192))}

    def __init__(self, muda: bool = False) -> None:
        self.muda = muda
        self.pedidas: list[tuple[str, datetime, datetime]] = []

    async def history(self, _endpoint, symbols, *, interval, start_ts, end_ts):
        paso, horizonte = self.reloj[interval]
        ini, fin = datetime.fromtimestamp(start_ts, UTC), datetime.fromtimestamp(end_ts, UTC)
        self.pedidas.append((interval, ini, fin))
        velas, t, borde = [], ini, datetime.now(UTC) - horizonte
        while t < fin and not self.muda:
            if t >= borde:
                velas.append(_vela(t))
            t += paso
        return {s: list(velas) for s in symbols}


async def _guarda(conn, ini: datetime, fin: datetime) -> list[datetime]:
    ts = [ini + i * MIN for i in range(int((fin - ini) / MIN))]
    await upsert_ohlcv(conn, {SYM: [_vela(t) for t in ts]}, {SYM: SYM}, int(ini.timestamp()), int(fin.timestamp()), "1min")
    return ts


async def _apagon(conn) -> dict:
    """La forma del apagon: serie hasta -35 h, hueco declarado [-35 h, -1 h) por el detector real, otro ANIDADO de otro
    detector [-34 h, -1 h), y despues el dueno rellena [-25 h, -1 h) a mano sin conciliar (la base lo tiene, el hueco
    sigue). Lo de [-35 h, -25 h) no lo tiene nadie: la fuente ya no lo sirve."""
    t0 = AHORA - 36 * H
    vistos = await _guarda(conn, t0, AHORA - 35 * H) + await _guarda(conn, AHORA - H, AHORA - 30 * MIN)
    await reconcile_cadence_coverage(
        conn, observations=vistos, **IDENT, start=t0, end=AHORA - 30 * MIN, cadence=MIN, detection_source="plantado_test"
    )
    anidado = await record_data_gap(
        conn, **{k: v for k, v in IDENT.items()}, feed_class="cadence", start=AHORA - 34 * H, end=AHORA - H,
        evidence_type="missing_interval", detection_reason="otro detector", detection_source="otro_detector",
        expected_cadence=MIN,
    )
    await _guarda(conn, AHORA - 25 * H, AHORA - H)
    padres = [r["id"] for r in await conn.fetch("SELECT id FROM data_gap ORDER BY start_ts")]
    assert len(padres) == 2 and anidado in padres
    return {"padres": padres}


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


@pytest.fixture
def ruta(base, monkeypatch):
    """/api/ohlcv llamada en el proceso contra la base desechable."""
    monkeypatch.setattr(api, "validate_symbol", lambda s: s)
    monkeypatch.setattr(api.app.state, "pool", _Pool(base), raising=False)

    async def velas() -> dict:
        respuesta = await api.ohlcv(SYM, interval="5min", limit=2000)
        return respuesta

    return velas


def _con_precio(respuesta: dict, ini: datetime, fin: datetime) -> tuple[int, int]:
    filas = [r for r in respuesta["rows"] if ini <= r["bucket"] < fin]
    return sum(1 for r in filas if r["close"] is not None), len(filas)


async def _corre(conn, fuente, **k) -> dict:
    return await recupera.parte(conn, fuente, ahora=AHORA, permitidos=frozenset({SYM}), limite=60, **k)


def _cubre(declarados: list[dict], ini: datetime, fin: datetime) -> bool:
    return any(datetime.fromisoformat(d["start"]) <= ini and datetime.fromisoformat(d["end"]) >= fin for d in declarados)


async def _k04_particion(conn, padre: int) -> bool:
    """El predicado de harness/checks/K04-huecos.sh para partitioned_by_source_coverage, sobre la fila del padre."""
    return await conn.fetchval(
        """
        SELECT g.recovery_metadata->>'partition_detection_source' IS NOT NULL
          AND (SELECT count(*) >= 2 AND count(*) FILTER (WHERE h.status='unresolved') = 0
                      AND sum(h.end_ts - h.start_ts) = g.end_ts - g.start_ts
                 FROM data_gap h
                WHERE h.feed=g.feed AND h.symbol=g.symbol AND h.granularity=g.granularity
                  AND h.detection_source=g.recovery_metadata->>'partition_detection_source'
                  AND h.start_ts >= g.start_ts AND h.end_ts <= g.end_ts)
          AND NOT EXISTS (
                SELECT 1 FROM data_gap a JOIN data_gap b
                    ON b.id > a.id AND b.symbol=a.symbol AND b.detection_source=a.detection_source
                   AND b.start_ts >= g.start_ts AND b.end_ts <= g.end_ts
                   AND a.start_ts < b.end_ts AND b.start_ts < a.end_ts
                 WHERE a.symbol=g.symbol
                   AND a.detection_source=g.recovery_metadata->>'partition_detection_source'
                   AND a.start_ts >= g.start_ts AND a.end_ts <= g.end_ts)
        FROM data_gap g WHERE g.id=$1
        """,
        padre,
    )


async def test_el_apagon_se_parte_y_lo_que_esta_en_la_base_sale_con_precio(base, ruta) -> None:
    conn = base
    plantado = await _apagon(conn)
    con_dato = (AHORA - 25 * H, AHORA - H)
    viejo = (AHORA - 35 * H, AHORA - 25 * H)

    antes = await ruta()
    hay, total = _con_precio(antes, *con_dato)
    assert total == 24 * 12 and hay == 0, "en main las 288 velas del tramo con dato salen sin precio"

    fuente = FuenteReloj()
    resumen = await _corre(conn, fuente, seco=False)
    info = resumen["uniones"][0]
    assert info["minutos_en_base"] == 24 * 60 and info["sin_dato_fuera_del_reloj"] == 10 * 60, info
    assert info["padres_cerrados"] == 2 and info["padres_abiertos"] == 0, info
    assert info["minutos_destapados"] == resumen["destapados"] == 24 * 60, info

    despues = await ruta()
    hay, total = _con_precio(despues, *con_dato)
    assert (hay, total) == (288, 288), "el tramo que esta en la base sale con precio"
    assert not [r for r in despues["rows"] if viejo[0] <= r["bucket"] < viejo[1]], "nada se inventa en la parte vieja"
    assert _cubre(despues["data_gaps"]["declared"], *viejo), "la parte vieja sigue declarada como hueco"
    assert not _cubre(despues["data_gaps"]["declared"], con_dato[0], con_dato[0] + 5 * MIN)

    for padre in plantado["padres"]:
        fila = await conn.fetchrow("SELECT status, recovery_metadata->>'method' AS m FROM data_gap WHERE id=$1", padre)
        assert (fila["status"], fila["m"]) == ("unrecoverable", "partitioned_by_source_coverage")
        assert await _k04_particion(conn, padre), "K04 re-deriva la particion desde la fila"
    viejos = await conn.fetch(
        "SELECT status, recovery_metadata FROM data_gap WHERE detection_source=$1 AND end_ts <= $2",
        PARTITION_DETECTION_SOURCE, viejo[1],
    )
    assert viejos and all(r["status"] == "unrecoverable" for r in viejos)
    assert all('"provider_horizon_exhausted"' in r["recovery_metadata"] for r in viejos)
    assert all(ini >= viejo[0] and fin <= viejo[1] for _i, ini, fin in fuente.pedidas[:-1]), "solo pidio la parte vieja"

    segunda = await _corre(conn, FuenteReloj(), seco=False)
    assert segunda["pedidas"] == 0 and not segunda["uniones"], "una segunda corrida no tiene nada que partir"


async def test_con_la_fuente_muda_no_se_archiva_ni_se_destapa_nada(base, ruta) -> None:
    conn = base
    plantado = await _apagon(conn)
    resumen = await _corre(conn, FuenteReloj(muda=True), seco=False)
    info = resumen["uniones"][0]
    assert info.get("fuente_muda") and info["archivados_fuera_del_reloj"] == 0, info
    assert info["padres_cerrados"] == 0 and info["minutos_destapados"] == 0, info
    for padre in plantado["padres"]:
        assert await conn.fetchval("SELECT status FROM data_gap WHERE id=$1", padre) == "unresolved"
    assert not await conn.fetchval("SELECT count(*) FROM data_gap WHERE status='unrecoverable'")
    hay, _ = _con_precio(await ruta(), AHORA - 25 * H, AHORA - H)
    assert hay == 0


async def test_en_seco_cuenta_y_no_escribe_ni_pregunta(base) -> None:
    conn = base
    plantado = await _apagon(conn)
    huella = await conn.fetchval("SELECT md5(string_agg(id || status || start_ts::text || end_ts::text, ',' ORDER BY id)) FROM data_gap")
    fuente = FuenteReloj()
    async with conn.transaction(readonly=True):
        resumen = await _corre(conn, fuente, seco=True, gaps=frozenset({plantado["padres"][1]}))
    info = resumen["uniones"][0]
    assert (info["minutos_en_base"], info["sin_dato_fuera_del_reloj"]) == (24 * 60, 10 * 60), info
    assert sorted(info["padres_mixtos"]) == sorted(plantado["padres"]), "un gap id trae tambien su anidado"
    assert info["destaparia"] == resumen["destaparia"] == 24 * 60, "lo que dice en seco es lo que destapa la corrida real"
    assert fuente.pedidas == [] and resumen["pedidas"] == 0
    assert huella == await conn.fetchval("SELECT md5(string_agg(id || status || start_ts::text || end_ts::text, ',' ORDER BY id)) FROM data_gap")


async def test_r2_un_hueco_de_34_h_de_5min_dentro_del_reloj_acaba_recuperado(base) -> None:
    """R2: el recuperador del timer tambien pide ohlcv 5min dentro de su horizonte (192 h, citado), por trozos."""
    conn = base
    ident5 = {**IDENT, "feed": "ohlcv_5min", "granularity": "5min"}
    cinco = timedelta(minutes=5)
    ini, fin = AHORA - 35 * H, AHORA - H
    gap = await record_data_gap(
        conn, **ident5, feed_class="cadence", start=ini, end=fin, evidence_type="missing_interval",
        detection_reason="apagon", detection_source="plantado_test", expected_cadence=cinco,
    )
    fuente = FuenteReloj()
    resumen = await recupera.recupera(conn, fuente, ahora=AHORA, permitidos=frozenset({SYM}), limite=60)
    assert await conn.fetchval("SELECT status FROM data_gap WHERE id=$1", gap) == "recovered", resumen
    velas = await conn.fetchval(
        "SELECT count(*) FROM ohlcv WHERE symbol=$1 AND interval='5min' AND ts >= $2 AND ts < $3", SYM, ini, fin
    )
    assert velas == 34 * 12
    assert fuente.pedidas and {p[0] for p in fuente.pedidas} == {"5min"}
    assert max(b - a for _, a, b in fuente.pedidas) <= recupera.PLANS[("ohlcv_5min", "5min")].chunk, "por trozos"
    assert recupera.HORIZONTE[("ohlcv_5min", "5min")] == recupera.HORIZONTE_OHLCV_5MIN == timedelta(hours=192)
