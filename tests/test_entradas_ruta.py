"""C4 de la campana 135 · GET /api/entradas.

- toda la ruta es GET y todos sus parametros tienen valor por defecto;
- sin tablas del registro, lo dice (falta desplegar) en vez de fallar;
- con el registro vacio sirve las cuentas a cero, resueltos 0 y el motivo de lo que falta;
- con un DISPARADO y una SOMBRA sembrados de punta a punta, los sirve por lado, la sombra con su
  vector de filtros, y la referencia «ya medido» con sus citas;
- y la RED: la ruta sirviendo una fraccion de aciertos se condena; la ruta real pasa.
"""

from __future__ import annotations

import copy
import inspect
import os
import uuid
from datetime import timedelta
from pathlib import Path

import asyncpg
import entradas_banco as B
import pytest

from app import api
from app.entradas import codigo as C
from app.entradas import reglamento as R
from app.entradas import ruta as RUTA
from app.entradas import servicio as S

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def conn():
    schema = f"entradas_ruta_{uuid.uuid4().hex}"
    connection = await asyncpg.connect(_dsn())
    await connection.execute(f'CREATE SCHEMA "{schema}"')
    await connection.execute(f'SET search_path TO "{schema}", public')
    await connection.execute("SET TIME ZONE 'UTC'")
    try:
        yield connection, schema
    finally:
        await connection.execute("SET search_path TO public")
        await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await connection.close()


async def _con_esquema(connection) -> None:
    await connection.execute(SCHEMA_SQL)
    for symbol, base in (("BTCUSDT_PERP.A", "BTC"), ("ETHUSDT_PERP.A", "ETH"), ("SOLUSDT_PERP.A", "SOL")):
        await connection.execute("INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING", base)
        await connection.execute("INSERT INTO symbols(symbol, base_asset) VALUES($1, $2) ON CONFLICT DO NOTHING",
                                 symbol, base)


def _por_defecto(**cambios):
    kw = {"lado": "ambos", "desde": None, "hasta": None, "version": None, "symbol": None,
          "limite": 200, "foto": False}
    kw.update(cambios)
    return kw


def test_la_ruta_es_get_y_todos_sus_parametros_tienen_valor_por_defecto():
    rutas = [r for r in api.app.routes if getattr(r, "path", None) == "/api/entradas"]
    assert len(rutas) == 1 and rutas[0].methods == {"GET"}
    firma = inspect.signature(api.entradas)
    for nombre, parametro in firma.parameters.items():
        if nombre == "request":
            continue
        assert parametro.default is not inspect.Parameter.empty, nombre


async def test_sin_tablas_lo_dice_y_no_falla(conn):
    connection, schema = conn
    # esquema vacio y SIN public en el camino: la base de CI tiene schema.sql en public
    await connection.execute(f'SET search_path TO "{schema}"')
    respuesta = await RUTA.construir(connection, **_por_defecto())
    assert respuesta["disponible"] is False and "falta desplegar" in respuesta["motivo"]
    assert respuesta["referencia_ya_medido"]["items"]
    assert RUTA.fracciones_servidas(respuesta) == []


async def test_registro_vacio_cuentas_a_cero_y_motivos_servidos(conn):
    connection, _ = conn
    await _con_esquema(connection)
    respuesta = await RUTA.construir(connection, **_por_defecto())
    assert respuesta["disponible"] is True
    assert set(respuesta["por_lado"]) == {"largo", "corto"}
    assert respuesta["cuentas"] == []
    assert respuesta["generador"]["motivo"] == "el generador aun no ha corrido en esta base"
    assert respuesta["reglamento"]["version_activa"] == "v1"
    assert {f["estado"] for f in respuesta["reglamento"]["registro_en_base"]} == {"sin registrar"}
    assert any(f["etapa"] == "E3" for f in respuesta["faltan"])
    assert RUTA.fracciones_servidas(respuesta) == []
    solo_corto = await RUTA.construir(connection, **_por_defecto(lado="corto"))
    assert set(solo_corto["por_lado"]) == {"corto"}


async def test_de_punta_a_punta_sirve_disparados_y_sombras_por_lado_sin_fracciones(conn):
    connection, _ = conn
    await _con_esquema(connection)
    T = await connection.fetchval(
        "SELECT date_bin('15 minutes', clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')"
    )
    doc = R.cargar()
    v1 = doc["versiones"][0]
    v1["bloques"]["comun"]["parametros"]["tope_retraso_s"]["valor"] = 900
    v1["huellas"] = {n: R.huella_bloque(v1["bloques"][n]) for n in R.BLOQUES}
    rev = B.revision(cubre_hasta=T + timedelta(days=10))
    rev["vigente_desde"] = B.M.iso(T - timedelta(days=1))
    rev["huella"] = R.huella_revision(rev)
    doc["calendario"]["revisiones"] = [rev]
    await B.sembrar(connection, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
    await B.sembrar(connection, T, B.insumos(T, spot_vela=-1e6), "ETHUSDT_PERP.A", "ETH")
    await S.evaluar_vela(connection, T=T, doc=doc, huella_codigo=C.huella_codigo(), esperar=False)

    respuesta = await RUTA.construir(connection, **_por_defecto(desde=T - timedelta(hours=1)))
    largo = respuesta["por_lado"]["largo"]
    assert [d["symbol"] for d in largo["vivos"]["disparados"]] == ["BTCUSDT_PERP.A"]
    sombras = largo["ventana"]["sombras"]
    assert [s["symbol"] for s in sombras] == ["ETHUSDT_PERP.A"]
    filtros = sombras[0]["resumen"]["filtros"]
    assert filtros["spot_vela"]["estado"] == "falla"
    assert "solo perpetuo" in sombras[0]["resumen"]["decision"]["etiquetas"]
    assert respuesta["por_lado"]["corto"]["vivos"]["vigilando"], "las F2 corto armadas"
    celdas = {(c["familia"], c["lado"]): c for c in respuesta["cuentas"]}
    assert celdas[("F1", "largo")]["DISPARADO"] == 1 and celdas[("F1", "largo")]["SOMBRA"] == 1
    assert all(c["resueltos"] == 0 for c in respuesta["cuentas"])
    assert RUTA.fracciones_servidas(respuesta) == [], RUTA.fracciones_servidas(respuesta)
    entera = await RUTA.construir(connection, **_por_defecto(desde=T - timedelta(hours=1), foto=True))
    assert entera["por_lado"]["largo"]["vivos"]["disparados"][0]["foto"]["plan"]["p_equilibrio"]
    assert RUTA.fracciones_servidas(entera) == []

    # LA RED: la misma respuesta sirviendo una fraccion de aciertos se condena
    for plantar in (
        lambda r: r["cuentas"][0].__setitem__("tasa_acierto", 0.43),
        lambda r: r["cuentas"][0].__setitem__("aciertos", "3/7"),
        lambda r: r["por_lado"]["largo"]["vivos"]["disparados"][0].__setitem__("lectura", "43 %"),
        lambda r: r.__setitem__("win_rate", 0.5),
    ):
        plantada = copy.deepcopy(respuesta)
        plantar(plantada)
        assert RUTA.fracciones_servidas(plantada), "la red no condena una fraccion servida"


def test_la_referencia_ya_medido_lleva_su_cita_y_no_la_condena_la_red():
    ref = RUTA.REFERENCIA_YA_MEDIDO
    assert "YA MEDIDO" in ref["rotulo"]
    for item in ref["items"]:
        assert item["cita"].startswith(("harness/COLA.md:", "harness/hechos.tsv:")), item
    assert RUTA.fracciones_servidas({"referencia_ya_medido": ref}) == []
