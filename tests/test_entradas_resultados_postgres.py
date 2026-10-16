"""LOS RESULTADOS GUARDADOS Y SERVIDOS (campana 139, C2 y C3) contra una base con sql/schema.sql.

Cada plan se registra en entrada_registro con el RELOJ PLANTADO de la base (la tecnica de test_entradas_vista.py):
el registro y sus disparadores leen la hora del esquema del test, asi que un DISPARADO se registra a los 136.8 s
del cierre de su vela aunque esa vela sea de hace dias, y despues se mira a cualquier hora.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import timedelta
from pathlib import Path

import asyncpg
import pytest
from test_entradas_resolutor import T, fila

from app.entradas import reglamento as R
from app.entradas import resolutor as RES
from app.entradas import resultados as RS
from app.entradas import ruta as RUTA

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SOL = "SOLUSDT_PERP.A"
H = "a" * 64


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _reloj(conn, instante) -> None:
    desfase = await conn.fetchval("SELECT ($1::timestamptz - pg_catalog.clock_timestamp())::text", instante)
    await conn.execute("SELECT set_config('reloj.desfase', $1, false)", desfase)


@pytest.fixture
async def base():
    schema = f"entradas_res_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(
        f'CREATE FUNCTION "{schema}".clock_timestamp() RETURNS timestamptz LANGUAGE sql VOLATILE AS '
        "$$ SELECT pg_catalog.clock_timestamp() + coalesce(current_setting('reloj.desfase', true), '0')::interval $$")
    await conn.execute(f'SET search_path TO "{schema}", pg_catalog, public')
    await conn.execute("SET TIME ZONE 'UTC'")
    try:
        await conn.execute(SCHEMA_SQL)
        await conn.execute("INSERT INTO market_assets(base_asset) VALUES('SOL') ON CONFLICT DO NOTHING")
        await conn.execute("INSERT INTO symbols(symbol, base_asset) VALUES($1, 'SOL') ON CONFLICT DO NOTHING", SOL)
        yield conn
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def registra(conn, f: dict, *, version="v2", estado="DISPARADO", clave="zona:99.5:100.2",
                   inicio=None) -> dict:
    """Inserta la fila con el reloj de la base a su registered_at, como lo haria el generador."""
    await _reloj(conn, f["registered_at"])
    fila_db = await conn.fetchrow(
        """INSERT INTO entrada_registro (version, familia, perfil, lado, symbol, clave, episodio, estado, motivo,
             vela_cierre, inicio_episodio, caduca_en, tope_retraso_s, huella_familia, huella_comun,
             huella_calendario, huella_lectura, huella_papel, codigo_version, huella_codigo, huella_foto, foto)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NULL, $9, $10, $11, 240, $12, $12, $12, $12, $12, 'entradas-motor-2',
                   $12, $12, $13::json)
           RETURNING *, foto::text AS foto""",
        version, f["familia"], f["perfil"], f["lado"], SOL, clave, hashlib.sha256(
            f"{version}{f['vela_cierre']}{estado}".encode()).hexdigest(), estado, f["vela_cierre"],
        inicio or f["vela_cierre"] - timedelta(minutes=15), f["caduca_en"] if estado == "DISPARADO" else None,
        H, json.dumps(f["foto"]))
    return dict(fila_db)


async def siembra(conn, f: dict, cambios: dict | None = None) -> None:
    """Las velas de 1 min de la vida del plan, planas a 100 salvo `cambios` (como en test_entradas_resolutor)."""
    from test_entradas_resolutor import velas
    await conn.executemany(
        "INSERT INTO ohlcv (ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx) "
        "VALUES ($1, $2, '1min', $3, $4, $5, $6, 10, 5, 1, 0) ON CONFLICT (symbol, interval, ts) DO UPDATE SET "
        "open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close",
        [(v["ts"], SOL, v["open"], v["high"], v["low"], v["close"]) for v in velas(f, cambios)])


async def resuelve(conn, filas: list[dict], ahora) -> dict[int, dict]:
    """de_filas con el reloj de la base en `ahora`: el disparador que guarda lee ESE reloj, no el del test."""
    await _reloj(conn, ahora)
    return await RS.de_filas(conn, filas, ahora)


STOP_2030 = {"2026-10-12T20:30": (100.0, 100.0, 98.9, 99.5)}
LISTO = T + timedelta(minutes=31) + RES.ASENTAMIENTO      # el stop de las 20:30 se asienta a las 21:13


async def test_lo_final_se_guarda_una_vez_con_sus_huellas(base):
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    r = (await resuelve(base, [f], LISTO))[f["registro_id"]]
    assert (r["salida"], r["firmeza"], r["instante"]) == (RES.STOP, RES.FINAL, "2026-10-12T20:30:00Z")
    filas = await base.fetch("SELECT *, resultado::text AS rt, convenciones::text AS ct FROM entrada_resultado")
    assert len(filas) == 1 and filas[0]["salida"] == "stop" and filas[0]["hipotetico"] is False
    assert filas[0]["huella_resultado"] == hashlib.sha256(filas[0]["rt"].encode()).hexdigest()
    assert filas[0]["huella_convenciones"] == hashlib.sha256(filas[0]["ct"].encode()).hexdigest()
    assert filas[0]["huella_convenciones"] == RES.HUELLA_CONVENCIONES
    assert json.loads(filas[0]["rt"]) == r
    # la segunda vez se lee lo guardado: aunque las velas cambien, el resultado dado no se reescribe
    await siembra(base, fila(), {})
    assert (await resuelve(base, [f], LISTO + timedelta(days=1)))[f["registro_id"]] == r
    assert await base.fetchval("SELECT count(*) FROM entrada_resultado") == 1


async def test_una_vela_reescrita_dentro_del_asentamiento_no_deja_nada_final(base):
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    dentro = LISTO - timedelta(minutes=20)
    r = (await resuelve(base, [f], dentro))[f["registro_id"]]
    assert (r["salida"], r["firmeza"], r["asentado_en"]) == (RES.STOP, RES.PROVISIONAL, RES.iso(LISTO))
    assert await base.fetchval("SELECT count(*) FROM entrada_resultado") == 0
    # ohlcv reescribe la vela del stop dentro de su ventana de 40 min: el provisional se mueve con ella
    await base.execute("UPDATE ohlcv SET low = 100.0, close = 100.0 WHERE symbol = $1 AND ts = $2",
                       SOL, T + timedelta(minutes=30))
    r2 = (await resuelve(base, [f], dentro))[f["registro_id"]]
    assert (r2["estado"], r2["salida"]) == (RES.ABIERTO, None)
    assert await base.fetchval("SELECT count(*) FROM entrada_resultado") == 0
    # y la base no deja guardar un resultado antes de su asentamiento, lo pida quien lo pida
    await _reloj(base, dentro)
    with pytest.raises(asyncpg.PostgresError) as no:
        await RS.guardar(base, {**r, "firmeza": RES.FINAL})
    assert no.value.sqlstate == "EN003"


async def test_la_base_rechaza_un_resultado_que_no_es_de_un_plan_del_registro(base):
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    r = (await resuelve(base, [f], LISTO))[f["registro_id"]]
    # con OTRA version del resolutor, para que la clave (registro_id, resolutor) no choque con lo ya guardado
    for malo in ({**r, "registro_id": 999, "resolutor": "otra"}, {**r, "hipotetico": True, "resolutor": "otra"}):
        with pytest.raises(asyncpg.PostgresError) as no:
            await RS.guardar(base, malo)
        assert no.value.sqlstate == "EN004", malo["registro_id"]


async def test_solo_anadir(base):
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    await resuelve(base, [f], LISTO + timedelta(hours=1))
    for orden in ("UPDATE entrada_resultado SET salida = 'objetivo'", "DELETE FROM entrada_resultado",
                  "TRUNCATE entrada_resultado"):
        with pytest.raises(asyncpg.PostgresError) as no:
            await base.execute(orden)
        assert no.value.sqlstate == "55000", orden


async def test_asentar_pendientes_y_el_barrido_emparejado(base):
    d = await registra(base, fila())
    sombra = fila()
    sombra["registered_at"] = T + timedelta(seconds=20)        # v1 decide a los ~20 s y entra al minuto
    sombra["foto"]["plan"]["stop"]["precio"] = 98.0             # su stop con cascada, mas lejos
    s = await registra(base, sombra, version="v1", estado="SOMBRA")
    await siembra(base, fila(), {**STOP_2030, "2026-10-12T21:00": (99.5, 102.5, 99.5, 102.0)})
    await _reloj(base, T + timedelta(hours=6))
    hecho = await RS.asentar_pendientes(base)
    assert hecho == {"mirados": 1, "finales": 1}
    filas = {x["registro_id"]: x for x in await base.fetch("SELECT registro_id, salida, hipotetico FROM entrada_resultado")}
    assert (filas[d["registro_id"]]["salida"], filas[d["registro_id"]]["hipotetico"]) == ("stop", False)
    assert (filas[s["registro_id"]]["salida"], filas[s["registro_id"]]["hipotetico"]) == ("objetivo", True)
    plan = (await RUTA.construir(base, lado="ambos", desde=None, hasta=None, version=None, symbol=None,
                                 limite=200, foto=False))["resultados"]["barrido_emparejado"]["planes"]
    assert plan == [{"registro_id": d["registro_id"], "symbol": SOL, "vela_cierre": "2026-10-12T20:00:00Z",
                     "salida": "stop", "motivo": None, "pareja": {
                         "registro_id": s["registro_id"], "salida_hipotetica": "objetivo",
                         "instante": "2026-10-12T21:00:00Z", "firmeza": "final", "t1_antes_que_el_stop": True}}]
    # una vuelta mas no guarda nada dos veces
    assert await RS.asentar_pendientes(base) == {"mirados": 0, "finales": 0}


async def test_la_ruta_sirve_el_resultado_saca_de_vivos_lo_acabado_y_cuenta_resueltos(base):
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    await _reloj(base, LISTO + timedelta(minutes=5))           # el stop ya es final y el reloj del plan no ha caducado
    resp = await RUTA.construir(base, lado="ambos", desde=T - timedelta(hours=1), hasta=T + timedelta(hours=1),
                                version=None, symbol=None, limite=200, foto=False)
    assert resp["por_lado"]["largo"]["vivos"]["disparados"] == []
    [d] = resp["por_lado"]["largo"]["ventana"]["disparados"]
    assert d["registro_id"] == f["registro_id"] and d["resultado"]["salida"] == RES.STOP
    assert d["resultado"]["firmeza"] == RES.FINAL
    [celda] = [c for c in resp["cuentas"] if c["version"] == "v2"]
    assert (celda["resueltos"], celda["sin_entrada"], celda["no_evaluables"]) == (1, 0, 0)
    assert resp["papel"]["v2"]["n"] == 1 and resp["papel"]["v1"]["n"] == 0
    assert resp["resultados"]["huella_convenciones"] == R.huella(RS.CONVENCIONES_DOC)
    assert [x["etapa"] for x in resp["faltan"]] == ["E4"]
    assert RUTA.fracciones_servidas(resp) == []


async def test_antes_de_la_vela_que_lo_acaba_esta_vivo_y_dice_hasta_donde_se_sabe(base):
    await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    await base.execute("DELETE FROM ohlcv WHERE ts >= $1", T + timedelta(minutes=30))
    await _reloj(base, T + timedelta(minutes=30, seconds=20))
    resp = await RUTA.construir(base, lado="ambos", desde=None, hasta=None, version=None, symbol=None,
                                limite=200, foto=False)
    [vivo] = resp["por_lado"]["largo"]["vivos"]["disparados"]
    assert vivo["resultado"]["estado"] == RES.ABIERTO and vivo["resultado"]["sabido_hasta"] == "2026-10-12T20:30:00Z"
    # llega la vela del stop: en la peticion siguiente ya no esta vivo, aunque nada se haya guardado
    await siembra(base, fila(), STOP_2030)
    resp = await RUTA.construir(base, lado="ambos", desde=None, hasta=None, version=None, symbol=None,
                                limite=200, foto=False)
    assert resp["por_lado"]["largo"]["vivos"]["disparados"] == []
    [d] = resp["por_lado"]["largo"]["ventana"]["disparados"]
    assert (d["resultado"]["salida"], d["resultado"]["firmeza"]) == (RES.STOP, RES.PROVISIONAL)
    assert await base.fetchval("SELECT count(*) FROM entrada_resultado") == 0


async def test_un_disparado_sin_su_vela_de_entrada_queda_pendiente_y_con_ella_se_resuelve(base):
    """Sin la vela de su entrada, el papel SERVIDO lo da pendiente (no saltado) y la cuenta es PROVISIONAL. Con la
    vela es una operacion, y con su stop asentado la cuenta es final."""
    f = await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    await base.execute("DELETE FROM ohlcv WHERE symbol = $1 AND ts = $2", SOL, RES.entrada_t(fila()))
    await _reloj(base, LISTO + timedelta(minutes=5))

    async def papel():
        return (await RUTA.construir(base, lado="ambos", desde=None, hasta=None, version=None, symbol=None,
                                     limite=200, foto=False))["papel"]["v2"]
    p = await papel()
    assert (p["saltados"], p["n"], p["operaciones"], p["saldo_usd"], p["firmeza"]) == ([], 0, [], 200.0,
                                                                                         RES.PROVISIONAL)
    assert [x["registro_id"] for x in p["pendientes"]] == [f["registro_id"]]
    assert p["pendientes"][0]["motivo"].endswith("la vela de 1 min de las 20:03Z no esta en la base")
    assert await base.fetchval("SELECT count(*) FROM entrada_resultado") == 0
    await siembra(base, fila(), STOP_2030)
    p = await papel()
    assert p["pendientes"] == [] and [op["registro_id"] for op in p["operaciones"]] == [f["registro_id"]]
    assert (p["n"], p["firmeza"], p["operaciones"][0]["salida"]) == (1, RES.FINAL, RES.STOP)


async def test_la_red_de_fracciones_sigue_condenando_con_resultados(base):
    """La E3 trae resultados, papel y convenciones a /api/entradas: la red de fracciones sigue mirando TODO lo que
    se sirve, y una frecuencia de resultados plantada en cualquiera de esos sitios la condena."""
    await registra(base, fila())
    await siembra(base, fila(), STOP_2030)
    await _reloj(base, LISTO + timedelta(minutes=5))
    resp = await RUTA.construir(base, lado="ambos", desde=T - timedelta(hours=1), hasta=T + timedelta(hours=1),
                                version=None, symbol=None, limite=200, foto=False)
    assert RUTA.fracciones_servidas(resp) == []
    plantados = [
        lambda r: r["papel"]["v2"].update(meta="1 de 1 llego a T1"),
        lambda r: r["resultados"]["barrido_emparejado"].update(planes=[{"t1_antes_que_el_stop": "100 %"}]),
        lambda r: r["cuentas"][0].update(tasa_objetivo=0.5),
        lambda r: r["por_lado"]["largo"]["ventana"]["disparados"][0]["resultado"].update(salida="3/7 objetivos"),
    ]
    for planta in plantados:
        r = json.loads(json.dumps(resp, default=str))
        planta(r)
        assert RUTA.fracciones_servidas(r), planta
