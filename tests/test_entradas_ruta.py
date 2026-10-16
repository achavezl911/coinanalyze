"""C4 de la campana 135 · GET /api/entradas.

- toda la ruta es GET y todos sus parametros tienen valor por defecto;
- sin tablas del registro, lo dice (falta desplegar) en vez de fallar;
- con el registro vacio sirve las cuentas a cero y el motivo de lo que falta (desde la 139, solo la E4);
- con un DISPARADO y una SOMBRA sembrados de punta a punta, los sirve por lado, la sombra con su
  vector de filtros, y la referencia «ya medido» con sus citas;
- y la RED: la ruta sirviendo una fraccion de aciertos se condena; la ruta real pasa.
"""

from __future__ import annotations

import copy
import inspect
import os
import uuid
from datetime import UTC, datetime, timedelta
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
    assert respuesta["reglamento"]["version_activa"] == "v2"
    assert respuesta["reglamento"]["versiones_en_curso"] == ["v1", "v2"]
    assert respuesta["reglamento"]["ancla"] == "v1"
    assert respuesta["reglamento"]["hipotesis_activa"] == R.version(R.cargar(), "v2")["hipotesis"]
    assert {f["estado"] for f in respuesta["reglamento"]["registro_en_base"]} == {"sin registrar"}
    assert [f["etapa"] for f in respuesta["faltan"]] == ["E4"], "el resultado y el papel (E3) ya no faltan"
    assert RUTA.fracciones_servidas(respuesta) == []
    solo_corto = await RUTA.construir(connection, **_por_defecto(lado="corto"))
    assert set(solo_corto["por_lado"]) == {"corto"}


async def test_de_punta_a_punta_sirve_disparados_y_sombras_por_lado_sin_fracciones(conn):
    connection, _ = conn
    await _con_esquema(connection)
    T = await connection.fetchval(
        "SELECT date_bin('15 minutes', clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')"
    )
    doc = B.doc_de_prueba(T, tope_s=900)
    await B.sembrar(connection, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
    await B.sembrar(connection, T, B.insumos(T, spot_vela=-1e6), "ETHUSDT_PERP.A", "ETH")
    await S.evaluar_vela(connection, T=T, doc=doc, huella_codigo=C.huella_codigo(), esperar=False)

    respuesta = await RUTA.construir(connection, **_por_defecto(desde=T - timedelta(hours=1)))
    largo = respuesta["por_lado"]["largo"]
    assert [d["symbol"] for d in largo["vivos"]["disparados"]] == ["BTCUSDT_PERP.A"]
    # SOLO el perfil intradia: si la vela T cierra tambien una vela de 4 h (una de cada dieciseis)
    # el generador evalua el swing, que aqui no tiene sembrada su ventana y registra sus SOMBRAS
    # de datos. Este test dependia de la hora a la que corria (campana 136: fallo a las 00:07Z).
    sombras = [s for s in largo["ventana"]["sombras"] if s["perfil"] == "intradia"]
    assert [s["symbol"] for s in sombras] == ["ETHUSDT_PERP.A"]
    filtros = sombras[0]["resumen"]["filtros"]
    assert filtros["spot_vela"]["estado"] == "falla"
    assert "solo perpetuo" in sombras[0]["resumen"]["decision"]["etiquetas"]
    assert respuesta["por_lado"]["corto"]["vivos"]["vigilando"], "las F2 corto armadas"
    celdas = {(c["familia"], c["lado"]): c for c in respuesta["cuentas"] if c["perfil"] == "intradia"}
    assert celdas[("F1", "largo")]["DISPARADO"] == 1 and celdas[("F1", "largo")]["SOMBRA"] == 1
    # recien registrado y sin velas despues de su vela: sin resultado FINAL, y el DISPARADO sigue vivo
    assert all(c["resueltos"] == 0 for c in respuesta["cuentas"])
    [vivo] = respuesta["por_lado"]["largo"]["vivos"]["disparados"]
    assert vivo["resultado"]["estado"] == "abierto" and vivo["resultado"]["firmeza"] == "provisional"
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


# --------------------------------------------------------------------------- dos versiones (136)


def _declaradas(doc: dict) -> dict[str, int]:
    """Las hipotesis apostadas por familia, contadas del JSON del fichero y de nada mas: el
    contraste de lo que la ruta sirve (no pasa por app/entradas/reglamento.apuestas)."""
    cuenta = dict.fromkeys(R.FAMILIAS, 0)
    for entrada in doc["apuestas"]["versiones"].values():
        for familia, _perfil, _lado in entrada["celdas"]:
            cuenta[familia] += 1
    return cuenta


def _mal_contadas(reglamento: dict, doc: dict) -> list[str]:
    """LA RED de C5 c: lo que la ruta dice que lleva probado cada familia contra lo declarado."""
    declaradas = _declaradas(doc)
    return [
        f"{f}: la ruta sirve {reglamento['por_familia'][f]['hipotesis_probadas']} y el reglamento "
        f"declara {declaradas[f]}"
        for f in R.FAMILIAS
        if reglamento["por_familia"][f]["hipotesis_probadas"] != declaradas[f]
    ]


def test_las_hipotesis_que_van_son_las_apostadas_y_contar_como_antes_se_condena(monkeypatch):
    doc = R.cargar_valido()
    momento = datetime(2026, 10, 12, tzinfo=UTC)
    reglamento = RUTA._reglamento(doc, momento)
    f1, f2 = reglamento["por_familia"]["F1"], reglamento["por_familia"]["F2"]
    assert (f1["hipotesis_probadas"], f2["hipotesis_probadas"]) == (6, 4)
    assert f1["apuestas"] == {"v1": [["intradia", "largo"], ["intradia", "corto"], ["swing", "largo"],
                                     ["swing", "corto"]],
                              "v2": [["intradia", "largo"], ["intradia", "corto"]]}
    # v2 mueve F1 swing y las cuatro de F2 SIN apuesta, y la ruta lo dice
    assert f1["sin_apuesta"] == {"v1": [], "v2": [["swing", "largo"], ["swing", "corto"]]}
    assert f2["apuestas"]["v2"] == [] and len(f2["sin_apuesta"]["v2"]) == 4
    assert _mal_contadas(reglamento, doc) == []
    # el plantado: contar como hasta la 135, una hipotesis por huella distinta del bloque de familia
    monkeypatch.setattr(RUTA, "_hipotesis", lambda doc, familia: {
        "hipotesis_probadas": len({v["huellas"][familia] for v in doc["versiones"]})})
    viejo = RUTA._reglamento(doc, momento)
    assert viejo["por_familia"]["F1"]["hipotesis_probadas"] == 1  # lo que decia la ruta antes de v2
    assert _mal_contadas(viejo, doc) == [
        "F1: la ruta sirve 1 y el reglamento declara 6", "F2: la ruta sirve 1 y el reglamento declara 4"]


def test_sin_apuestas_declaradas_la_ruta_no_cuenta_nada():
    doc = R.cargar_valido()
    del doc["apuestas"]
    f1 = RUTA._reglamento(doc, datetime(2026, 10, 12, tzinfo=UTC))["por_familia"]["F1"]
    assert f1["hipotesis_probadas"] is None and "no declara" in f1["motivo"]


def test_v2_es_la_activa_y_su_diferencia_con_el_padre_son_los_tres_cambios():
    reglamento = RUTA._reglamento(R.cargar_valido(), datetime(2026, 10, 12, tzinfo=UTC))
    assert reglamento["version_activa"] == "v2" and reglamento["versiones_en_curso"] == ["v1", "v2"]
    dif = reglamento["diferencia_con_el_padre"]
    assert dif["padre"] == "v1"
    cambian = {b: sorted(c["parametros"]) for b, c in dif["bloques"].items() if c["cambia"]}
    assert cambian == {
        "comun": ["colchon_stop", "espera_datos_s", "espera_flujos", "tope_retraso_s"],
        "papel": ["paso_cantidad_bybit"],
    }
    stop = dif["bloques"]["comun"]["parametros"]["colchon_stop"]
    assert stop["antes"]["valor"]["fuera_de_racimo"] is True
    assert stop["despues"]["valor"]["fuera_de_racimo"] is False
    assert dif["bloques"]["comun"]["parametros"]["espera_flujos"]["antes"] is None
    assert RUTA.fracciones_servidas({"reglamento": reglamento}) == []


def test_el_calendario_vigente_y_los_dias_que_le_quedan():
    doc = R.cargar_valido()
    antes = RUTA._reglamento(doc, datetime(2026, 10, 9, 23, 0, tzinfo=UTC))["calendario_vigente"]
    assert antes["revision"] == "cal-1" and antes["dias_que_le_quedan"] < 0  # no cubre nada
    cal = RUTA._reglamento(doc, datetime(2026, 10, 10, 0, 0, tzinfo=UTC))["calendario_vigente"]
    assert cal["revision"] == "cal-2" and cal["eventos"] == 20
    assert cal["vigente_desde"] == "2026-10-10T00:00:00Z" and cal["cubre_hasta"] == "2026-11-30T23:59:59Z"
    assert cal["dias_que_le_quedan"] == pytest.approx(52.0, abs=0.01)
    assert cal["renovacion_minima_dias"] == 14
    vencido = RUTA._reglamento(doc, datetime(2026, 12, 2, tzinfo=UTC))["calendario_vigente"]
    assert vencido["revision"] == "cal-2" and vencido["dias_que_le_quedan"] < 0


def test_la_red_no_deja_colar_una_fraccion_dentro_de_la_hipotesis_servida():
    reglamento = RUTA._reglamento(R.cargar_valido(), datetime(2026, 10, 12, tzinfo=UTC))
    assert RUTA.fracciones_servidas({"reglamento": reglamento}) == []
    assert "tasa" in reglamento["hipotesis_activa"]["sentido"]  # el texto del lazo, tal cual
    plantada = copy.deepcopy(reglamento)
    plantada["hipotesis_activa"]["aciertos_hasta_hoy"] = "3/7"
    assert RUTA.fracciones_servidas({"reglamento": plantada}), "una clave ajena dentro de la hipotesis"
    plantada = copy.deepcopy(reglamento)
    plantada["por_familia"]["F1"]["lectura"] = "43 %"
    assert RUTA.fracciones_servidas({"reglamento": plantada})


def test_la_referencia_ya_medido_lleva_su_cita_y_no_la_condena_la_red():
    ref = RUTA.REFERENCIA_YA_MEDIDO
    assert "YA MEDIDO" in ref["rotulo"]
    for item in ref["items"]:
        assert item["cita"].startswith(("harness/COLA.md:", "harness/hechos.tsv:")), item
    assert RUTA.fracciones_servidas({"referencia_ya_medido": ref}) == []
