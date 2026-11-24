"""DATOS B · B3 (F6-R2): el apagon que se recupera solo, contra Postgres de verdad y una fuente doblada.

EL DEFECTO (fable-f6, R2). Un hueco de ohlcv 1min se puede pedir a la fuente unas 24 h; pasado eso, ya no. El repaso
(scripts/resweep_cadence_gaps.py) troceaba en una rejilla FIJA de 6 h anclada al hueco mas viejo y solo pedia una
ventana si un hueco cabia ENTERO dentro: un hueco de mas de 6 h, o uno que cruzaba la rejilla, no se pedia NUNCA. Los
casos son los de la entrega de fable-f6 (minutos desde el inicio de la serie, (inicio, duracion)):
  A (60,360) cabe justo · B (60,361) un minuto mas · C (60,41) corto · D (60,10)+(400,41) el segundo cruza · E (60,480)
Y nadie lo corria solo: el recuperador (scripts/recupera_huecos.py, timer cada 30 min) es lo que faltaba.

LO QUE SE EXIGE: B, D y E acaban recovered y A y C siguen; una fuente MUDA no archiva nada; dos corridas seguidas, la
segunda no pide nada; los trozos salen del hueco y no de una rejilla; lo que esta fuera del horizonte no se pide.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

import scripts.resweep_cadence_gaps as resweep
from app.data_gaps import SOURCE_ABSENCE_REASON, reconcile_cadence_coverage, record_data_gap
from app.ingest import upsert_ohlcv

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SYM = "BTCUSDT_PERP.A"
MIN = timedelta(minutes=1)
IDENT = {"feed": "ohlcv_1min", "exchange": "binance", "market": "perpetual", "symbol": SYM, "granularity": "1min"}
PLAN = resweep.PLANS[("ohlcv_1min", "1min")]
CASOS = {
    "A": (600, [(60, 360)]),
    "B": (600, [(60, 361)]),
    "C": (600, [(60, 41)]),
    "D": (600, [(60, 10), (400, 41)]),
    "E": (720, [(60, 480)]),
}


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def base():
    """(conexion, esquema): un esquema desechable por test con sql/schema.sql aplicado."""
    schema = f"recupera_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    await conn.execute("INSERT INTO market_assets(base_asset) VALUES('BTC') ON CONFLICT DO NOTHING")
    await conn.execute("INSERT INTO symbols(symbol,base_asset) VALUES($1,'BTC') ON CONFLICT DO NOTHING", SYM)
    try:
        yield conn, schema
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


def _vela(t: datetime) -> dict:
    return {"t": int(t.timestamp()), "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 10, "bv": 5, "tx": 3, "btx": 1}


class FuenteDoble:
    """La fuente: sirve TODAS las velas de 1 min de lo que se le pide ([start, end)), o nada si esta muda. Apunta cada
    peticion para que el test vea QUE se pidio."""

    pedidas: list[tuple[datetime, datetime]] = []
    muda = False
    salta: set[datetime] = set()  # buckets que la fuente no publica (su salto, no una caida)

    def __init__(self, *_a, **_k) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def history(self, _endpoint, symbols, *, interval, start_ts, end_ts):
        paso = {"1min": MIN, "5min": 5 * MIN}[interval]
        ini, fin = datetime.fromtimestamp(start_ts, UTC), datetime.fromtimestamp(end_ts, UTC)
        FuenteDoble.pedidas.append((ini, fin))
        if FuenteDoble.muda:
            return {s: [] for s in symbols}
        velas, t = [], ini
        while t < fin:
            if t not in FuenteDoble.salta:
                velas.append(_vela(t))
            t += paso
        return {s: list(velas) for s in symbols}


@pytest.fixture(autouse=True)
def fuente():
    FuenteDoble.pedidas, FuenteDoble.muda, FuenteDoble.salta = [], False, set()
    yield FuenteDoble


async def _plantar(conn, t0: datetime, total: int, agujeros: list[tuple[int, int]]) -> set[datetime]:
    """La serie de `total` minutos sin los agujeros, y los huecos declarados por el detector REAL."""
    ausentes = {t0 + (a + i) * MIN for a, dura in agujeros for i in range(dura)}
    presentes = [t0 + i * MIN for i in range(total) if t0 + i * MIN not in ausentes]
    fin = t0 + total * MIN
    await upsert_ohlcv(conn, {SYM: [_vela(t) for t in presentes]}, {SYM: SYM}, int(t0.timestamp()), int(fin.timestamp()), "1min")
    await reconcile_cadence_coverage(
        conn, observations=presentes, **IDENT, start=t0, end=fin, cadence=MIN, detection_source="plantado_test"
    )
    return ausentes


async def _estados(conn) -> list[str]:
    return [r["status"] for r in await conn.fetch("SELECT status FROM data_gap WHERE symbol=$1 ORDER BY start_ts, id", SYM)]


async def _faltan(conn, ausentes: set[datetime]) -> int:
    hay = await conn.fetchval(
        "SELECT count(*) FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts = ANY($2::timestamptz[])", SYM, sorted(ausentes)
    )
    return len(ausentes) - hay


def _t0(total: int) -> datetime:
    """La serie acaba una hora antes de ahora: dentro del horizonte de 24 h de la fuente."""
    ahora = datetime.now(UTC).replace(second=0, microsecond=0)
    return ahora - timedelta(hours=1) - total * MIN


# ------------------------------------------------------------------------------------------------ el repaso (resweep)


@pytest.fixture
def repaso(base, monkeypatch):
    conn, schema = base

    async def pool(_settings=None, application_name: str = "test"):
        return await asyncpg.create_pool(
            _dsn(), min_size=1, max_size=2, server_settings={"search_path": f'"{schema}", public', "timezone": "UTC"}
        )

    monkeypatch.setattr(resweep, "get_settings", lambda: SimpleNamespace(
        SYMBOLS=[SYM], COINALYZE_RATE_LIMIT_UNITS=40, COINALYZE_BASE_URL="http://doble.invalid", API_KEY="doble"))
    monkeypatch.setattr(resweep, "create_pool", pool)
    monkeypatch.setattr(resweep, "PostgresSlidingWindowRateLimiter", lambda _pool, _units: None)
    monkeypatch.setattr(resweep, "CoinalyzeClient", FuenteDoble)
    return conn


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", sorted(CASOS))
async def test_el_repaso_pide_y_recupera_los_cinco_casos_de_f6(repaso, caso) -> None:
    total, agujeros = CASOS[caso]
    ausentes = await _plantar(repaso, _t0(total), total, agujeros)

    await resweep.run("ohlcv_1min", 200, False, False)

    assert FuenteDoble.pedidas, f"caso {caso}: el repaso no le pidio NADA a la fuente"
    assert await _faltan(repaso, ausentes) == 0, f"caso {caso}: siguen faltando velas"
    assert set(await _estados(repaso)) == {"recovered"}, f"caso {caso}: {await _estados(repaso)}"


# ------------------------------------------------------------------------------------------------ el recuperador


def _recuperador():
    import scripts.recupera_huecos as recupera

    return recupera


async def _corre(conn, ahora: datetime | None = None, limite: int = 50) -> dict:
    recupera = _recuperador()
    return await recupera.recupera(conn, FuenteDoble(), ahora=ahora or datetime.now(UTC), permitidos={SYM}, limite=limite)


@pytest.mark.asyncio
@pytest.mark.parametrize("caso", sorted(CASOS))
async def test_el_recuperador_deja_recovered_los_cinco_casos(base, caso) -> None:
    conn, _ = base
    total, agujeros = CASOS[caso]
    ausentes = await _plantar(conn, _t0(total), total, agujeros)

    resumen = await _corre(conn)

    assert await _faltan(conn, ausentes) == 0, f"caso {caso}: siguen faltando velas"
    assert set(await _estados(conn)) == {"recovered"}, f"caso {caso}: {await _estados(conn)}"
    assert resumen["recuperados"] == len(agujeros)
    # Los trozos salen del HUECO: cada uno empieza donde empieza lo que falta o donde acabo el anterior, y ninguno
    # pasa del trozo del plan ni pide un minuto que ya estaba.
    for ini, fin in FuenteDoble.pedidas:
        assert fin - ini <= PLAN.chunk
        assert ini in ausentes and fin - MIN in ausentes, (ini, fin)
    assert sum(((fin - ini) // MIN for ini, fin in FuenteDoble.pedidas), 0) == len(ausentes)


@pytest.mark.asyncio
async def test_dos_corridas_seguidas_la_segunda_no_pide_nada(base) -> None:
    conn, _ = base
    total, agujeros = CASOS["E"]
    await _plantar(conn, _t0(total), total, agujeros)
    await _corre(conn)
    FuenteDoble.pedidas = []

    resumen = await _corre(conn)

    assert FuenteDoble.pedidas == []
    assert resumen["pedidas"] == 0 and resumen["pendientes"] == 0 and resumen["urgente"] is None


@pytest.mark.asyncio
async def test_una_fuente_muda_no_archiva_nada(base) -> None:
    conn, _ = base
    total, agujeros = CASOS["D"]
    await _plantar(conn, _t0(total), total, agujeros)
    filas_antes = await conn.fetchval("SELECT count(*) FROM data_gap")
    FuenteDoble.muda = True

    resumen = await _corre(conn)

    assert FuenteDoble.pedidas, "con la fuente muda se le tiene que haber preguntado igual"
    assert await _estados(conn) == ["unresolved", "unresolved"]
    assert await conn.fetchval("SELECT count(*) FROM data_gap WHERE status='unrecoverable'") == 0
    # Ni una fila nueva: el reconcile del hueco entero no apunta lo que otro detector ya tiene apuntado.
    assert await conn.fetchval("SELECT count(*) FROM data_gap") == filas_antes
    assert resumen["pendientes"] == 2 and resumen["urgente"] is not None


@pytest.mark.asyncio
async def test_lo_que_ya_salio_del_horizonte_no_se_pide_ni_se_archiva(base) -> None:
    conn, _ = base
    t0 = datetime.now(UTC).replace(second=0, microsecond=0) - timedelta(hours=30)
    await _plantar(conn, t0, 120, [(30, 20)])  # hace ~29 h: fuera de las 24 h de ohlcv 1min

    resumen = await _corre(conn)

    assert FuenteDoble.pedidas == [] and resumen["pendientes"] == 0
    assert await _estados(conn) == ["unresolved"]


@pytest.mark.asyncio
async def test_un_hueco_que_cruza_el_horizonte_pide_solo_la_parte_que_la_fuente_sirve(base) -> None:
    conn, _ = base
    ahora = datetime.now(UTC).replace(second=0, microsecond=0)
    t0 = ahora - timedelta(hours=26)
    await _plantar(conn, t0, 25 * 60, [(60, 120)])  # [t0+1h, t0+3h) = [ahora-25h, ahora-23h)

    resumen = await _corre(conn, ahora=ahora)

    borde = ahora - _recuperador().HORIZONTE[("ohlcv_1min", "1min")]
    assert FuenteDoble.pedidas and min(ini for ini, _ in FuenteDoble.pedidas) >= borde
    assert await _estados(conn) == ["unresolved"]  # la parte vieja no esta: ni recovered ni archivado
    # Lo que queda ya no se puede pedir: no es un pendiente RECUPERABLE y no debe tener reloj.
    assert resumen["pendientes"] == 0 and resumen["urgente"] is None


@pytest.mark.asyncio
async def test_el_tope_de_peticiones_se_respeta_y_lo_urgente_va_primero(base) -> None:
    conn, _ = base
    total, agujeros = CASOS["D"]
    t0 = _t0(total)
    await _plantar(conn, t0, total, agujeros)

    resumen = await _corre(conn, limite=1)

    assert FuenteDoble.pedidas == [(t0 + 60 * MIN, t0 + 70 * MIN)]
    assert resumen["cortado_por_tope"] is True
    assert await _estados(conn) == ["recovered", "unresolved"]


@pytest.mark.asyncio
async def test_un_salto_de_la_fuente_no_se_archiva_ni_da_reloj(base) -> None:
    conn, _ = base
    total, agujeros = CASOS["C"]
    t0 = _t0(total)
    await _plantar(conn, t0, total, agujeros)
    FuenteDoble.salta = {t0 + 70 * MIN}

    resumen = await _corre(conn)

    assert await _estados(conn) == ["unresolved"]  # falta un bucket: ni recovered ni archivado
    assert await conn.fetchval("SELECT count(*) FROM data_gap WHERE status='unrecoverable'") == 0
    assert resumen["pendientes"] == 0 and resumen["urgente"] is None and resumen["saltados_por_la_fuente"] == 1


# --- recupera-r2 (R2b B3): el cupo por vencimiento y el salto aislado, archivado SOLO con prueba en la misma respuesta


async def _hueco(conn, feed: str, gran: str, cadencia: timedelta, ini: datetime, fin: datetime) -> int:
    return await record_data_gap(
        conn, feed=feed, feed_class="cadence", exchange="binance", market="perpetual", symbol=SYM, granularity=gran,
        start=ini, end=fin, evidence_type="missing_interval", detection_reason="test", detection_source="plantado_test",
        expected_cadence=cadencia,
    )


@pytest.mark.asyncio
async def test_el_cupo_va_a_lo_que_vence_antes_no_a_lo_que_empieza_antes(base) -> None:
    """Con main el cupo se ordenaba por `lo`: el hueco de ohlcv_5min de hace 100 h (192 h de reloj, le quedan 92)
    se llevaba la unica peticion y el de ohlcv_1min de hace 23 h (le queda 1 h) se perdia."""
    conn, _ = base
    ahora = datetime.now(UTC).replace(second=0, microsecond=0)
    viejo = ahora - timedelta(hours=100)
    servible = ahora - timedelta(hours=23)
    await _hueco(conn, "ohlcv_5min", "5min", 5 * MIN, viejo, viejo + 30 * MIN)
    await _hueco(conn, "ohlcv_1min", "1min", MIN, servible, servible + 10 * MIN)

    resumen = await _corre(conn, ahora=ahora, limite=1)

    assert FuenteDoble.pedidas == [(servible, servible + 10 * MIN)]
    assert resumen["cortado_por_tope"] is True


@pytest.mark.asyncio
async def test_el_salto_aislado_se_archiva_con_sus_dos_vecinos_y_no_se_vuelve_a_pedir(base) -> None:
    """Con main el bucket que la fuente no publica se pedia SOLO, volvia vacio, seguia 'unresolved' y se re-pedia en
    cada corrida. Ahora se pide con un bucket de margen: la respuesta trae los dos vecinos y no el salto, y eso es la
    prueba que archive_source_response_absence exige."""
    conn, _ = base
    total = 120
    t0 = _t0(total)
    await _plantar(conn, t0, total, [(60, 1)])
    FuenteDoble.salta = {t0 + 60 * MIN}

    resumen = await _corre(conn)

    fila = await conn.fetchrow("SELECT status, resolution_reason, recovery_metadata::text AS m FROM data_gap WHERE symbol=$1", SYM)
    assert fila["status"] == "unrecoverable" and fila["resolution_reason"] == SOURCE_ABSENCE_REASON
    meta = json.loads(fila["m"])
    assert meta["method"] == "source_response_absence" and meta["proof_source"] == "recupera_huecos salto"
    assert meta["window_returned_rows"] == 0 and meta["response_returned_rows"] == 2
    assert FuenteDoble.pedidas == [(t0 + 60 * MIN, t0 + 61 * MIN), (t0 + 59 * MIN, t0 + 62 * MIN)]
    assert resumen["archivados_salto"] == 1 and resumen["pendientes"] == 0 and resumen["urgente"] is None
    FuenteDoble.pedidas = []

    segunda = await _corre(conn)

    assert FuenteDoble.pedidas == [] and segunda["pedidas"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("como", ["muda", "sin_vecino_en_la_respuesta"])
async def test_el_salto_sin_prueba_en_la_misma_respuesta_no_se_archiva(base, como) -> None:
    """El control: la fuente muda no prueba nada, y un vecino que esta en NUESTRA base pero no en la respuesta tampoco."""
    conn, _ = base
    total = 120
    t0 = _t0(total)
    await _plantar(conn, t0, total, [(60, 1)])
    if como == "muda":
        FuenteDoble.muda = True
    else:
        FuenteDoble.salta = {t0 + 59 * MIN, t0 + 60 * MIN}

    resumen = await _corre(conn)

    assert await _estados(conn) == ["unresolved"]
    assert resumen.get("archivados_salto", 0) == 0  # .get: el control pasa tambien con main, que no archivaba


def test_el_latido_se_escribe_entero_y_legible(tmp_path) -> None:
    recupera = _recuperador()
    f = tmp_path / "latido.json"
    recupera.escribe_latido(f, {"ts": "2026-11-15T10:00:00+00:00", "pendientes": 0, "urgente": None})
    assert json.loads(f.read_text())["pendientes"] == 0
    assert not list(tmp_path.glob("*.tmp"))
