"""C1, C2 y C3 de la campana 135 contra Postgres de verdad (base desechable de CI).

Lo que se induce aqui en vez de citarse:
- append-only: UPDATE, DELETE y TRUNCATE los rechaza el DISPARADOR (SQLSTATE 55000, su texto),
  no una sesion de solo lectura (25006);
- registered_at lo pone la base aunque el cliente mande otro;
- un DISPARADO por encima del tope lo rechaza la base (EN001) y queda como SOMBRA «tardio»;
- dos vivos en una clave: el segundo lo rechaza la base (EN002);
- registrar por huella ANTES de emitir: la misma etiqueta con otra regla no emite nada;
- los insumos se cortan en T (C2 b: nada posterior, ninguna barra sin cerrar en el corte) y un
  minuto ausente deja la vela NO EVALUABLE (C2 c);
- de punta a punta: la vela T sembrada en la base da un DISPARADO con su foto, y un resolutor de
  juguete lo resuelve leyendo SOLO el registro y ohlcv 1 min.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import entradas_banco as B
import pytest

from app.entradas import codigo as C
from app.entradas import foto as F
from app.entradas import insumos as I
from app.entradas import motor as M
from app.entradas import registro as G
from app.entradas import reglamento as R
from app.entradas import servicio as S

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SIMBOLOS = (("BTCUSDT_PERP.A", "BTC"), ("ETHUSDT_PERP.A", "ETH"), ("SOLUSDT_PERP.A", "SOL"))


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"entradas_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    await connection.execute(SCHEMA_SQL)
    for symbol, base in SIMBOLOS:
        await connection.execute(
            "INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING", base
        )
        await connection.execute(
            "INSERT INTO symbols(symbol, base_asset) VALUES($1, $2) ON CONFLICT DO NOTHING",
            symbol, base,
        )
    try:
        yield connection
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


async def _ahora_T(conn) -> datetime:
    return await conn.fetchval(
        "SELECT date_bin('15 minutes', clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')"
    )


def _transicion(T: datetime, *, estado: str = "VIGILANDO", episodio: str | None = None,
                clave: str = "zona:94.74:95.26", tope: float = 120, caduca: datetime | None = None,
                symbol: str = "BTCUSDT_PERP.A") -> dict:
    t = copy.deepcopy(B.elige(B.paso(B.insumos())["transiciones"], familia="F1", lado="largo",
                              estado="DISPARADO")[0])
    t.update({"estado": estado, "vela_cierre": T, "inicio_episodio": T - timedelta(minutes=15),
              "episodio": episodio or uuid.uuid4().hex + uuid.uuid4().hex, "clave": clave,
              "tope_retraso_s": tope, "symbol": symbol,
              "caduca_en": caduca if estado == "DISPARADO" else None,
              "motivo": None if estado in ("DISPARADO", "VIGILANDO") else "plantado"})
    return t


# --------------------------------------------------------------------------- append-only


@pytest.mark.parametrize("tabla", ["entrada_registro", "entrada_reglamento", "entrada_latido"])
async def test_update_delete_y_truncate_los_rechaza_el_disparador_con_su_texto(conn, tabla):
    T = await _ahora_T(conn)
    await G.insertar(conn, _transicion(T), "c" * 64)
    await conn.execute(
        "INSERT INTO entrada_reglamento(etiqueta, bloque, huella, contenido) VALUES ('v0', 'F1', $1, '{}')",
        "a" * 64,
    )
    await G.latir(conn, vela_cierre=T, estado="ok", duracion_s=1.0, detalle={}, error=None)
    columna = {"entrada_registro": "motivo", "entrada_reglamento": "bloque", "entrada_latido": "error"}
    for sentencia in (f"UPDATE {tabla} SET {columna[tabla]} = 'x'", f"DELETE FROM {tabla}",
                      f"TRUNCATE {tabla}"):
        with pytest.raises(asyncpg.PostgresError) as exc:
            await conn.execute(sentencia)
        assert exc.value.sqlstate == "55000", (sentencia, exc.value.sqlstate)
        assert f"{tabla} is append-only" in str(exc.value), str(exc.value)
        assert "read-only" not in str(exc.value)
    assert await conn.fetchval(f"SELECT count(*) FROM {tabla}") >= 1


async def test_el_control_distingue_el_disparador_de_una_sesion_de_solo_lectura(conn):
    """El canal de produccion es de solo lectura: alli el UPDATE lo rechaza la SESION (25006) y
    no prueba nada del disparador. Aqui se ven los dos codigos, y K105 juzga por catalogo."""
    T = await _ahora_T(conn)
    await G.insertar(conn, _transicion(T), "c" * 64)
    async with conn.transaction(readonly=True):
        with pytest.raises(asyncpg.PostgresError) as exc:
            await conn.execute("UPDATE entrada_registro SET motivo = 'x'")
    assert exc.value.sqlstate == "25006"
    with pytest.raises(asyncpg.PostgresError) as exc:
        await conn.execute("UPDATE entrada_registro SET motivo = 'x'")
    assert exc.value.sqlstate == "55000"


async def test_registered_at_lo_pone_la_base_aunque_el_cliente_mande_otro(conn):
    T = await _ahora_T(conn)
    t = _transicion(T)
    args = G._argumentos(t, "c" * 64)
    columnas = G._INSERTA_REGISTRO.split("(", 1)[1].split(")", 1)[0]
    sql = (f"INSERT INTO entrada_registro ({columnas}, registered_at) VALUES "
           f"({', '.join(f'${i}' for i in range(1, 24))}::json, '2000-01-01T00:00:00Z') "
           "RETURNING registered_at")
    sql = sql.replace("$23::json::json", "$23::json")
    registrada = await conn.fetchval(sql, *args)
    assert registrada > datetime(2026, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------- tardio y dos vivos


async def test_un_disparado_tardio_lo_rechaza_la_base_y_queda_como_sombra_tardia(conn):
    ahora = await conn.fetchval("SELECT clock_timestamp()")
    vela = ahora - timedelta(seconds=200)
    t = _transicion(vela, estado="DISPARADO", caduca=vela + timedelta(minutes=240))
    with pytest.raises(asyncpg.PostgresError) as exc:
        await conn.fetchrow(G._INSERTA_REGISTRO, *G._argumentos(t, "c" * 64))
    assert exc.value.sqlstate == G.TARDIO
    r = await G.insertar(conn, t, "c" * 64)
    assert r["estado"] == "SOMBRA" and r["motivo"] == "tardio" and r["retraso_s"] > 120
    fila = await conn.fetchrow("SELECT estado, caduca_en, huella_foto FROM entrada_registro")
    assert fila["estado"] == "SOMBRA" and fila["caduca_en"] is None
    assert fila["huella_foto"] == t["huella_foto"]  # la misma foto: solo cambia el estado
    # el gemelo a tiempo entra como DISPARADO
    T = await _ahora_T(conn)
    a_tiempo = _transicion(T, estado="DISPARADO", caduca=T + timedelta(minutes=240), tope=900,
                           clave="zona:1:2")
    assert (await G.insertar(conn, a_tiempo, "c" * 64))["estado"] == "DISPARADO"


async def test_dos_vivos_en_una_clave_los_rechaza_la_base(conn):
    T = await _ahora_T(conn)
    primero = _transicion(T - timedelta(minutes=30))
    await G.insertar(conn, primero, "c" * 64)
    segundo = _transicion(T)
    r = await G.insertar(conn, segundo, "c" * 64)
    assert r["registrado"] is False and "episodio vivo" in r["rechazo"]
    # cerrado el primero, el segundo entra
    cierre = _transicion(T - timedelta(minutes=15), estado="CERRADO_SIN_DISPARO",
                         episodio=primero["episodio"])
    await G.insertar(conn, cierre, "c" * 64)
    assert (await G.insertar(conn, segundo, "c" * 64))["registrado"] is True
    # un DISPARADO vivo ocupa su clave hasta caducar
    d1 = _transicion(T, estado="DISPARADO", caduca=T + timedelta(minutes=240), tope=900,
                     clave="zona:7:8")
    assert (await G.insertar(conn, d1, "c" * 64))["registrado"] is True
    d2 = _transicion(T, estado="DISPARADO", caduca=T + timedelta(minutes=240), tope=900,
                     clave="zona:7:8")
    assert (await G.insertar(conn, d2, "c" * 64))["registrado"] is False


# --------------------------------------------------------------------------- registro por huella


async def test_se_registra_por_huella_y_una_etiqueta_no_abarca_dos_reglas(conn):
    doc = R.cargar()
    registradas = C.registradas()
    contenido = C.contenido()
    primero = await G.registrar_reglamento(conn, doc, registradas, M.CODIGO_VERSION, contenido)
    assert primero["ok"], primero
    n = await conn.fetchval("SELECT count(*) FROM entrada_reglamento")
    assert n == primero["filas"]
    for fila in await conn.fetch("SELECT huella, contenido::text AS c FROM entrada_reglamento "
                                 "WHERE bloque <> 'codigo'"):
        assert F.huella_texto(fila["c"]) == fila["huella"]  # la huella se recomprueba del texto
    plantado = copy.deepcopy(doc)
    v1 = plantado["versiones"][0]
    v1["bloques"]["F1"]["parametros"]["entrada"]["valor"] = "limite"
    v1["huellas"]["F1"] = R.huella_bloque(v1["bloques"]["F1"])  # ¡lavado!: el fichero cuadra solo
    assert R.validar(plantado) == []
    segundo = await G.registrar_reglamento(conn, plantado, registradas, M.CODIGO_VERSION, contenido)
    assert segundo["ok"] is False
    assert segundo["conflictos"] == [{"etiqueta": "v1", "bloque": "F1",
                                      "fichero": v1["huellas"]["F1"],
                                      "base": doc["versiones"][0]["huellas"]["F1"]}]
    assert await conn.fetchval("SELECT count(*) FROM entrada_reglamento") == n


async def test_un_codigo_cambiado_sin_subir_su_version_no_emite(conn):
    otro = {"piezas": {"app/entradas/motor.py": "0" * 64}}
    r = await G.registrar_reglamento(conn, R.cargar(), C.registradas(), M.CODIGO_VERSION, otro)
    assert r["ok"] is False and "subir la version" in r["motivo"]
    assert await conn.fetchval("SELECT count(*) FROM entrada_reglamento") == 0


# --------------------------------------------------------------------------- insumos cortados en T


_sembrar = B.sembrar


async def test_c2b_los_insumos_se_cortan_en_T_y_nada_posterior_entra(conn):
    T = await _ahora_T(conn)
    ins = B.insumos(T)
    await _sembrar(conn, T, ins, "BTCUSDT_PERP.A", "BTC")
    # Lo que NO puede entrar: velas y flujos posteriores a T, y una barra de 4 h sin cerrar en
    # el corte (abre a las T-15m, cierra 3 h 45 despues) con un minimo que crearia un pivote.
    await conn.execute(
        "INSERT INTO ohlcv(ts, symbol, interval, open, high, low, close, volume, buy_volume, tx, btx) "
        "VALUES ($1, 'BTCUSDT_PERP.A', '1min', 90, 90, 80, 90, 1, 0.5, 1, 1), "
        "($2, 'BTCUSDT_PERP.A', '4hour', 96, 96, 80, 96, 1, 0.5, 1, 1)",
        T, T - timedelta(minutes=15),
    )
    comun = B.comun()
    cal = R.valores(B.versiones()[0]["bloques"]["calendario"])
    cargados = await I.cargar(conn, symbol="BTCUSDT_PERP.A", base_asset="BTC", T=T,
                              perfil="intradia", comun=comun, calendario=cal, modo=M.PROSPECTIVO)
    assert M.de_iso(cargados["velas"][-1]["fin"]) == T
    assert min(v["low"] for v in cargados["velas"] if v["low"] is not None) > 80
    assert all(M.de_iso(b["cierre"]) <= T - timedelta(minutes=15) for b in cargados["h4"])
    assert all(M.de_iso(b["cierre"]) <= T - timedelta(minutes=15) for b in cargados["diarias"])
    assert cargados["flujos"]["spot"]["vela"]["completo"] is True
    assert cargados["flujos"]["spot"]["vela"]["delta_usd"] == pytest.approx(1e6)
    assert M.de_iso(cargados["libro_bybit"]["ts"]) <= T
    assert I.vela_de_T_completa(cargados)


async def test_un_minuto_de_spot_con_una_sola_venue_deja_la_pata_incompleta(conn):
    """«Spot con las dos venues» se CUENTA por minuto: antes de 0df80b2 (2026-08-11) una fila
    'combined' pudo escribirse con una sola venue, asi que no basta con ella."""
    T = await _ahora_T(conn)
    await _sembrar(conn, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
    kw = {"symbol": "BTCUSDT_PERP.A", "base_asset": "BTC", "T": T, "perfil": "intradia",
          "comun": B.comun(), "calendario": R.valores(B.versiones()[0]["bloques"]["calendario"]),
          "modo": M.PROSPECTIVO}
    antes = (await I.cargar(conn, **kw))["flujos"]["spot"]["vela"]
    assert antes["completo"] and antes["minutos"] == 15
    await conn.execute("DELETE FROM spot_trades_agg WHERE symbol = 'BTC' AND exchange = 'bybit' "
                       "AND ts = $1", T - timedelta(minutes=3))
    despues = (await I.cargar(conn, **kw))["flujos"]["spot"]["vela"]
    assert not despues["completo"] and despues["minutos"] == 14
    assert despues["minutos_con_una_venue"] == 1


async def test_c2c_un_minuto_ausente_en_la_base_deja_la_vela_no_evaluable(conn):
    T = await _ahora_T(conn)
    await _sembrar(conn, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
    comun = B.comun()
    cal = R.valores(B.versiones()[0]["bloques"]["calendario"])
    kw = {"symbol": "BTCUSDT_PERP.A", "base_asset": "BTC", "T": T, "perfil": "intradia",
          "comun": comun, "calendario": cal, "modo": M.PROSPECTIVO}
    assert I.vela_de_T_completa(await I.cargar(conn, **kw))
    # DELETE en una tabla que no es del registro (ohlcv): la base de prueba lo permite
    await conn.execute("DELETE FROM ohlcv WHERE symbol = 'BTCUSDT_PERP.A' AND interval = '1min' "
                       "AND ts = $1", T - timedelta(minutes=7))
    cargados = await I.cargar(conn, **kw)
    assert not I.vela_de_T_completa(cargados)
    res = M.paso(T=T, symbol="BTCUSDT_PERP.A", perfil="intradia", modo=M.PROSPECTIVO,
                 versiones=B.versiones(), insumos=cargados, previos=[],
                 revision=B.revision(cubre_hasta=T + timedelta(days=30)), codigo=B.CODIGO)
    assert res["transiciones"] == [] and "14 de 15" in res["evaluacion"]["motivo"]


# --------------------------------------------------------------------------- de punta a punta


def _doc_de_prueba(T: datetime) -> dict:
    """v1 con un tope de retraso que cabe en la duracion del test y un calendario que cubre:
    solo cambia lo necesario para que la vela T actual pueda disparar desde una base de prueba."""
    doc = R.cargar()
    v1 = doc["versiones"][0]
    v1["bloques"]["comun"]["parametros"]["tope_retraso_s"]["valor"] = 900
    v1["huellas"] = {n: R.huella_bloque(v1["bloques"][n]) for n in R.BLOQUES}
    rev = B.revision(cubre_hasta=T + timedelta(days=30))
    rev["vigente_desde"] = M.iso(T - timedelta(days=1))
    rev["huella"] = R.huella_revision(rev)
    doc["calendario"]["revisiones"] = [rev]
    return doc


async def resolutor_de_juguete(conn, registro_id: int) -> str:
    """Lee SOLO entrada_registro y ohlcv 1min (nada de la foto que no este en la fila)."""
    fila = dict(await conn.fetchrow(
        "SELECT estado, motivo, registered_at, retraso_s, tope_retraso_s, huella_foto, symbol, "
        "foto::text AS foto FROM entrada_registro WHERE registro_id = $1", registro_id))
    errores = F.validar_fila(fila)
    if errores:
        raise ValueError(errores)
    foto = json.loads(fila["foto"])
    plan = foto["plan"]
    if plan.get("p_equilibrio") is None or not (foto["mids"].get("binance") and foto["mids"].get("bybit")):
        raise ValueError("foto sin p* o sin los mids de las dos venues")
    largo = foto["lado"] == "largo"
    stop, t1 = plan["stop"]["precio"], plan["objetivos"][0]
    desde = fila["registered_at"].replace(second=0, microsecond=0) + timedelta(minutes=1)
    minutos = await conn.fetch(
        "SELECT ts, high, low FROM ohlcv WHERE symbol = $1 AND interval = '1min' AND ts >= $2 "
        "AND ts < $3 ORDER BY ts", fila["symbol"], desde, M.de_iso(plan["caducidad"]["caduca_en"]))
    for m in minutos:
        if (m["low"] <= stop) if largo else (m["high"] >= stop):
            return "stop"
        if (m["high"] >= t1) if largo else (m["low"] <= t1):
            return "exito"
    return "abierto"


async def test_de_punta_a_punta_la_vela_T_dispara_y_el_juguete_resuelve_desde_el_registro(conn):
    T = await _ahora_T(conn)
    doc = _doc_de_prueba(T)
    for symbol, base in SIMBOLOS[:2]:
        await _sembrar(conn, T, B.insumos(T), symbol, base)
    salida = await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo="c" * 64, esperar=False)
    registradas = [r for v in salida for r in v["registradas"]]
    disparados = [r for r in registradas if r["estado"] == "DISPARADO"]
    assert {r["symbol"] for r in disparados} == {"BTCUSDT_PERP.A", "ETHUSDT_PERP.A"}, salida
    for r in disparados:
        fila = dict(await conn.fetchrow(
            "SELECT estado, motivo, registered_at, retraso_s, tope_retraso_s, huella_foto, "
            "foto::text AS foto FROM entrada_registro WHERE registro_id = $1", r["registro_id"]))
        assert F.validar_fila(fila) == []
        assert F.huella_texto(fila["foto"]) == fila["huella_foto"]
    # el juguete: BTC sube a T1, ETH cae al stop, ambos DESPUES del registro
    btc = next(r for r in disparados if r["symbol"] == "BTCUSDT_PERP.A")
    eth = next(r for r in disparados if r["symbol"] == "ETHUSDT_PERP.A")
    registrada = await conn.fetchval("SELECT registered_at FROM entrada_registro WHERE registro_id = $1",
                                     btc["registro_id"])
    primero = registrada.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for symbol, recorrido in (("BTCUSDT_PERP.A", [(95.7, 96.0), (96.0, 105.0)]),
                              ("ETHUSDT_PERP.A", [(95.7, 96.0), (93.0, 96.0)])):
        for i, (lo, hi) in enumerate(recorrido):
            await conn.execute(
                "INSERT INTO ohlcv(ts, symbol, interval, open, high, low, close, volume, buy_volume, "
                "tx, btx) VALUES ($1, $2, '1min', $3, $4, $3, $4, 1, 0.5, 1, 1) "
                "ON CONFLICT (symbol, interval, ts) DO UPDATE SET high = EXCLUDED.high, low = EXCLUDED.low",
                primero + timedelta(minutes=i), symbol, lo, hi,
            )
    assert await resolutor_de_juguete(conn, btc["registro_id"]) == "exito"
    assert await resolutor_de_juguete(conn, eth["registro_id"]) == "stop"
