"""Campana 137 (E2) · GET /api/mesa/entradas: lo que la vista ENTRADAS de la mesa pinta.

- la ruta es GET, solo admite `symbol`, y sin las tablas del registro lo dice en vez de fallar;
- de punta a punta, con el generador REAL y las dos versiones: el DISPARADO vivo sale con su plan
  ENTERO (el coste de cada pata en bps y como fraccion del objetivo), la SOMBRA con lo que fallo,
  la activa antes que el ancla, y lo que el ancla no puede hacer dicho UNA vez;
- las CINCO respuestas de DECIDE, cada una con su frase, y un plan en contra se dice;
- el orden es por hora; la distancia va en % del precio;
- y la RED: ninguna fraccion, ningun porcentaje, ninguna tasa (fracciones_servidas, la misma de
  /api/entradas), salvo el rotulo de muestra que el reglamento manda.
"""

from __future__ import annotations

import copy
import inspect
import json
import os
import uuid
from datetime import timedelta
from pathlib import Path

import asyncpg
import entradas_banco as B
import entradas_vista_banco as EB
import pytest

from app import api
from app.entradas import codigo as C
from app.entradas import foto as F
from app.entradas import motor as M
from app.entradas import registro as G
from app.entradas import reglamento as R
from app.entradas import ruta as RUTA
from app.entradas import servicio as S
from app.entradas import vista as V

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
SIMBOLOS = (("BTCUSDT_PERP.A", "BTC"), ("ETHUSDT_PERP.A", "ETH"), ("SOLUSDT_PERP.A", "SOL"))


def _decide(scalp: str | None, *, edad: float = 12.0):
    """Lo que build_mesa_decide(frame="swing") sirve, reducido a lo que la vista lee de el."""
    async def palabra(_conn, _symbol, *, frame):
        assert frame == "swing", "la vista pide DECIDE en swing: de ahi salen las dos palabras"
        if scalp is None:
            raise RuntimeError("DECIDE no contesta")
        return {
            "max_age_s": 120.0,
            "age": {"snapshot_lag_seconds": {"value": edad, "status": "ok"}},
            "decide": {"bias": {"value": "NO EVALUABLE", "source_key": "mesa.decide.frame",
                                "motivo": "la lectura del operador es del SCALP, no de SWING"}},
            # mesa.decide.v3 (campana 138): la palabra del scalp es la que el sistema SOSTIENE, con su edad
            "lectura_scalp": {"bias": {"value": scalp, "source_key": "mesa.decide.memoria",
                                       "motivo": "data_confidence 12 < 70" if scalp == "NO EVALUABLE" else None},
                              "memoria": {"edad": {"desde": "2026-10-14T21:12:05+00:00",
                                                   "frase": "desde las 21:12:05Z (17 min)"}}},
        }
    return palabra


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


@pytest.fixture
async def sembrada():
    """BTC con un DISPARADO vivo y ETH con una SOMBRA, en v1 y en v2, por el generador real."""
    schema = f"entradas_vista_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    try:
        await conn.execute(SCHEMA_SQL)
        for symbol, base in SIMBOLOS:
            await conn.execute("INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING", base)
            await conn.execute("INSERT INTO symbols(symbol, base_asset) VALUES($1, $2) ON CONFLICT DO NOTHING",
                               symbol, base)
        T = await conn.fetchval(
            "SELECT date_bin('15 minutes', clock_timestamp(), TIMESTAMPTZ '1970-01-01 00:00:00+00')")
        doc = B.doc_de_prueba(T, "v1", "v2", tope_s=900)
        await B.sembrar(conn, T, B.insumos(T), "BTCUSDT_PERP.A", "BTC")
        await B.sembrar(conn, T, B.insumos(T, spot_vela=-1e6), "ETHUSDT_PERP.A", "ETH")
        await S.evaluar_vela(conn, T=T, doc=doc, huella_codigo=C.huella_codigo(), esperar=False)
        # evaluar_vela decide; el latido lo escribe el servicio al acabar la pasada
        await G.latir(conn, vela_cierre=T, estado="ok", duracion_s=1.0, detalle={}, error=None)
        yield conn, schema, T
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()


async def _vista(conn, activo: str = "BTC", scalp: str | None = "NO OPERAR") -> dict:
    return await V.construir(conn, symbol=f"{activo}USDT_PERP.A", activo=activo,
                             palabra_de_decide=_decide(scalp))


def _planes(respuesta: dict, tipo: str) -> list[dict]:
    if tipo in ("disparados", "vigilando"):
        return [p for c in respuesta["vivo"]["celdas"] for v in c["por_version"] for p in v[tipo]]
    return [p for v in respuesta["reciente"]["por_version"] for p in v["sombras"]]


def test_la_ruta_de_la_mesa_es_get_y_solo_admite_el_activo():
    rutas = [r for r in api.app.routes if getattr(r, "path", None) == "/api/mesa/entradas"]
    assert len(rutas) == 1 and rutas[0].methods == {"GET"}
    assert [n for n in inspect.signature(api.mesa_entradas).parameters if n != "request"] == ["symbol"]


async def test_sin_tablas_lo_dice_y_la_palabra_de_decide_sigue_llegando():
    conn = await asyncpg.connect(_dsn())
    schema = f"entradas_vista_{uuid.uuid4().hex}"
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}"')
    try:
        respuesta = await _vista(conn)
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        await conn.close()
    assert respuesta["disponible"] is False and "falta desplegar" in respuesta["motivo"]
    assert respuesta["decide"]["perfiles"]["intradia"]["palabra"] == "NO OPERAR"
    assert "vivo" not in respuesta, "sin registro no hay nada que ensenar como vivo"


async def test_de_punta_a_punta_el_disparado_vivo_sale_con_su_plan_entero(sembrada):
    conn, _, T = sembrada
    respuesta = await _vista(conn)
    assert respuesta["disponible"] is True and respuesta["activo"] == "BTC"

    # la ACTIVA se lee primero y el ANCLA va al final, en cada celda y en lo reciente
    assert [(v["version"], v["papel"]) for v in respuesta["reciente"]["por_version"]] == [
        ("v2", "ACTIVA"), ("v1", "ANCLA")]
    for celda in respuesta["vivo"]["celdas"]:
        assert [v["papel"] for v in celda["por_version"]] == ["ACTIVA", "ANCLA"]
    assert [(c["perfil"], c["lado"]) for c in respuesta["vivo"]["celdas"]] == [
        ("intradia", "largo"), ("intradia", "corto"), ("swing", "largo"), ("swing", "corto")]

    disparados = _planes(respuesta, "disparados")
    assert {d["version"] for d in disparados} == {"v1", "v2"}, "un DISPARADO vivo por version"
    for d in disparados:
        assert (d["perfil"], d["lado"], d["caducado"]) == ("intradia", "largo", False)
        assert d["entrada"]["regla"] and d["entrada"]["referencia"]["precio"] and d["entrada"]["referencia"]["instante"]
        assert d["stop"]["precio"] and d["stop"]["distancia_bps"] > 0
        assert [o["nombre"] for o in d["objetivos"]][0] == "T1" and all(o["precio"] for o in d["objetivos"])
        assert d["invalidacion"]["nivel"] and d["invalidacion"]["hasta"] and d["invalidacion"]["reloj"]
        assert d["caduca_en"] and d["r_neto"] and 0 < d["p_equilibrio"] < 1
        # el coste de cada pata: en bps, y como fraccion del objetivo = sus bps entre la distancia a T1
        assert [c["pata"] for c in d["costes"]] == ["entrada", "objetivo", "stop"]
        for c in d["costes"]:
            assert c["bps"] > 0 and c["venue"]
            assert c["x_objetivo"] == pytest.approx(c["bps"] / d["t1_distancia_bps"], abs=0.006)
            assert c["x_objetivo"] > 0, "un coste que no es cero no sale como cero"
        # los requisitos: la LISTA con su estado, sin conteo ni nota
        assert [r["nombre"] for r in d["requisitos"]] == list(F.FILTROS)
        assert {r["estado"] for r in d["requisitos"]} == {"cumple"}
        assert set(d) & {"nota", "puntuacion", "cumplidos", "score"} == set()
    # el mismo DISPARADO sale tambien en lo reciente, y ahi dice que sigue vivo
    assert all(d["vivo"] for v in respuesta["reciente"]["por_version"] for d in v["disparados"])

    # un VIGILANDO: su zona y lo que le separa del precio, en % del precio
    vigilando = _planes(respuesta, "vigilando")
    assert vigilando, "las F2 armadas"
    for v in vigilando:
        assert v["zona"]["low"] < v["zona"]["high"]
        assert v["distancia"]["pct"] >= 0 and v["distancia"]["donde"] in (
            "por encima de la zona", "por debajo de la zona", "dentro de la zona")
    assert respuesta["precio"]["valor"] and respuesta["precio"]["instante"] <= respuesta["as_of"]

    # el marco: lo que la ruta sirve, con el rotulo de muestra del reglamento y la n servida
    marco = respuesta["marco"]
    assert (marco["version_activa"], marco["ancla"]) == ("v2", "v1")
    assert marco["hipotesis_activa"] == R.version(R.cargar(), "v2")["hipotesis"]
    assert marco["calendario"]["revision"] and marco["calendario"]["dias_que_le_quedan"] > 0
    assert all(c["resueltos"] == 0 and c["muestra"]["rotulo"] == "SIN CALIBRAR · MUESTRA INSUFICIENTE (0/30)"
               for c in marco["cuentas"])
    assert marco["resueltos_motivo"] and all("resueltos_motivo" not in c for c in marco["cuentas"])
    assert [f["etapa"] for f in marco["faltan"]] == ["E3", "E3", "E4"], "la pantalla (E2) ya no falta"
    assert respuesta["generador"]["ultimo_latido"]["estado"] == "ok" and respuesta["generador"]["tope_s"] == 1800

    # LA RED: ni una fraccion, ni un porcentaje, ni una tasa. Y la red CONDENA si se le planta una.
    assert RUTA.fracciones_servidas(respuesta) == [], RUTA.fracciones_servidas(respuesta)
    assert "%" not in json.dumps(respuesta, ensure_ascii=False)
    for plantar in (
        lambda r: r["marco"]["cuentas"][0].__setitem__("tasa_acierto", 0.43),
        lambda r: r["marco"]["cuentas"][0].__setitem__("lectura", "3/7"),
        lambda r: _planes(r, "disparados")[0].__setitem__("lectura", "43 %"),
        lambda r: r["vivo"].__setitem__("aciertos", 3),
    ):
        plantada = copy.deepcopy(respuesta)
        plantar(plantada)
        assert RUTA.fracciones_servidas(plantada), "la red no condena una fraccion servida en la vista"


async def test_la_sombra_dice_que_fallo_y_el_ancla_se_dice_una_vez(sembrada):
    conn, _, _ = sembrada
    respuesta = await _vista(conn, "ETH")
    por_version = {v["version"]: v for v in respuesta["reciente"]["por_version"]}
    intradia = {v: [s for s in b["sombras"] if s["perfil"] == "intradia"] for v, b in por_version.items()}
    assert intradia["v2"] and "spot_vela" in intradia["v2"][0]["fallan"], "en v2 el spot en contra FALLA"
    # el ancla, tal como corre este banco (sin esperar), evalua el spot: no hay nada «que no pueda»
    assert por_version["v1"]["papel"] == "ANCLA" and por_version["v2"]["no_puede"] is None
    assert por_version["v1"]["no_puede"]["frase"].startswith("ANCLA · v1 corre siempre")

    # con el spot NO EVALUABLE en todas sus sombras (como en produccion), se dice UNA vez y sale de las filas
    registro = await RUTA.construir(conn, lado="ambos", desde=None, hasta=None, version=None,
                                    symbol="ETHUSDT_PERP.A", limite=V.LIMITE, foto=True)
    for lado in registro["por_lado"].values():
        for s in lado["ventana"]["sombras"]:
            if s["version"] == "v1":
                for n in ("spot_vela", "spot_hora"):
                    s["foto"]["filtros"][n] = {"estado": "no_evaluable", "valor": None, "umbral": None,
                                               "motivo": "hueco de spot: 58 de 60 minutos con las 2 venues"}
    compuesta = V.componer(registro, symbol="ETHUSDT_PERP.A", activo="ETH", precio=respuesta["precio"],
                           decide=None, decide_error="DECIDE no contesta", doc=R.cargar_valido())
    ancla = next(v for v in compuesta["reciente"]["por_version"] if v["papel"] == "ANCLA")
    assert ancla["no_puede"]["requisitos"] == ["spot_vela", "spot_hora"]
    assert "spot_vela y spot_hora no se pudieron evaluar en NINGUNA" in ancla["no_puede"]["frase"]
    assert "decide a los 20 s" in ancla["no_puede"]["frase"], "el por que sale del reglamento del ancla"
    assert all(not {x["nombre"] for x in s["no_evaluables"]} & {"spot_vela", "spot_hora"} for s in ancla["sombras"])
    # y el motivo servido que cuenta MINUTOS no es una tasa de planes: la red lo deja pasar
    assert RUTA.fracciones_servidas(compuesta) == []


@pytest.mark.parametrize(
    ("scalp", "largo", "corto", "debe_decir"),
    [
        ("LONG", "mismo_lado", "en_contra", "sostiene LONG en los ultimos 5 min"),
        ("SHORT", "en_contra", "mismo_lado", "sostiene SHORT en los ultimos 5 min"),
        ("NO OPERAR", "condicional", "condicional", "no sostiene un lado en los ultimos 5 min"),
        ("NO EVALUABLE", "no_dice", "no_dice", "ni los respalda ni los desaconseja"),
        (None, "sin_respuesta", "sin_respuesta", "Sin respuesta de DECIDE"),
    ],
)
async def test_las_cinco_respuestas_de_decide_cada_una_con_su_frase(sembrada, scalp, largo, corto, debe_decir):
    conn, _, _ = sembrada
    decide = (await _vista(conn, scalp=scalp))["decide"]
    intradia = decide["perfiles"]["intradia"]
    assert intradia["marco"] == "SCALP" and intradia["palabra"] == scalp
    assert intradia["rotulo"] == (scalp or "SIN RESPUESTA")
    assert debe_decir in intradia["frase"]
    assert (intradia["para"]["largo"]["relacion"], intradia["para"]["corto"]["relacion"]) == (largo, corto)
    en_contra = [x["etiqueta"] for x in intradia["para"].values() if x["relacion"] == "en_contra"]
    assert all("EN CONTRA" in e for e in en_contra), "un plan en contra del lado que DECIDE toma se dice"
    if scalp == "NO OPERAR":
        assert {x["etiqueta"] for x in intradia["para"].values()} == {"plan condicional: el sistema no sostiene un lado"}
    # campana 138: la palabra INTRADIA es la que el sistema sostiene, y su frase no dice «en este instante»
    if scalp is not None:
        assert "en este instante" not in intradia["frase"]
        assert intradia["edad_de_la_palabra"] == "desde las 21:12:05Z (17 min)"
        assert intradia["desde"] == "2026-10-14T21:12:05+00:00"
    # SWING es hoy NO EVALUABLE por el marco: ni desaconseja el plan ni lo respalda
    swing = decide["perfiles"]["swing"]
    if scalp is None:
        assert swing["sin_respuesta"] and swing["motivo"] and "No se sabe" in swing["frase"]
    else:
        assert (swing["marco"], swing["palabra"]) == ("SWING", "NO EVALUABLE")
        assert "la lectura del operador es del SCALP, no de SWING" in swing["frase"]
        assert {x["relacion"] for x in swing["para"].values()} == {"no_dice"}
        assert "EN CONTRA" not in swing["frase"] and "mismo lado" not in json.dumps(swing["para"])
        assert decide["edad_s"] == 12.0 and decide["max_age_s"] == 120.0
        assert "no sale de una ventana de evaluaciones" in swing["edad_de_la_palabra"]


async def test_la_palabra_de_scalp_que_la_vista_lee_es_la_que_decide_sirve_en_scalp(sembrada):
    """La vista saca las DOS palabras de UNA llamada a DECIDE en swing. Esto ata esa suposicion al
    codigo de verdad: lo que build_mesa_decide publica en lectura_scalp.bias (marco swing) es el
    veredicto que publica en decide.bias cuando el marco es scalp."""
    conn, _, _ = sembrada
    en_scalp = (await api.build_mesa_decide(conn, "BTCUSDT_PERP.A", frame="scalp"))["decide"]["bias"]
    en_swing = await api.build_mesa_decide(conn, "BTCUSDT_PERP.A", frame="swing")
    del_scalp = en_swing["lectura_scalp"]["bias"]
    assert (del_scalp["value"], del_scalp["source_key"], del_scalp["motivo"]) == (
        en_scalp["value"], en_scalp["source_key"], en_scalp["motivo"])
    assert en_swing["decide"]["bias"]["source_key"] == "mesa.decide.frame"
    # y con el DECIDE real la vista compone sin romperse, diga lo que diga esta base sin mercado
    respuesta = await V.construir(conn, symbol="BTCUSDT_PERP.A", activo="BTC",
                                  palabra_de_decide=api.build_mesa_decide)
    assert respuesta["decide"]["perfiles"]["intradia"]["rotulo"] == en_scalp["value"]
    assert RUTA.fracciones_servidas(respuesta) == []


def test_el_readme_no_niega_las_entradas_que_el_sistema_genera():
    """Remate R1. El README decia, del sistema entero y en presente, «no genera entradas mecánicas»: desde
    la campana 135 las genera. Se lee sin saltos de linea, que es por donde se cayo de la busqueda."""
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    assert "no genera entradas" not in readme.lower()
    assert "`config/entradas/reglamento.json`" in readme and "`#<marco>/<activo>/entradas`" in readme


def test_una_fraccion_del_objetivo_que_no_es_cero_no_sale_como_cero(monkeypatch):
    """Remate R2. «x0,00 del objetivo» se lee «no cuesta nada». La precision la pone la ruta (A77): dos
    decimales, y por debajo de 0,01 los que hagan falta para que se vea su primera cifra. El cliente pinta
    lo que llega, sin redondear (tests/js/mesa_entradas.test.js; en un navegador, K106)."""
    assert [V._fraccion(v) for v in (0.0375, 0.0446, 0.5, 1.234, 12)] == [0.04, 0.04, 0.5, 1.23, 12.0]
    assert [V._fraccion(v) for v in (0.007, 0.002146, 0.0096, 0.00032, 4e-7)] == [0.007, 0.002, 0.01, 0.0003, 4e-7]
    assert all(V._fraccion(10.0 ** -n) > 0 > V._fraccion(-(10.0 ** -n)) for n in range(1, 30))
    assert V._fraccion(0) == 0.0 and V._fraccion(None) is None
    # por la ruta: el plan que midio el operador (T1 a 932,1 bps), y el gemelo: una pata que de verdad no cuesta
    plan = copy.deepcopy(EB.PLAN)
    plan["distancias_bps"]["t1"] = 932.1
    plan["costes"]["stop"]["total_bps"] = 0.0
    plan["cocientes"]["coste_objetivo"] = 0.0086
    monkeypatch.setattr(EB, "PLAN", plan)
    d = _planes(EB.respuesta(None), "disparados")[0]
    assert [(c["pata"], c["bps"], c["x_objetivo"]) for c in d["costes"]] == [
        ("entrada", 6.0, 0.006), ("objetivo", 2.0, 0.002), ("stop", 0.0, 0.0)]
    assert d["coste_ida_y_vuelta_x_objetivo"] == 0.009


async def test_la_tabla_de_recuentos_dice_que_cuenta_y_el_registro_lo_cumple(sembrada):
    """Remate R3. La columna se llamaba VIGILANDO, como el estado de un plan vivo, y «VIGILANDO 264» se leia
    «264 planes vigilados ahora». La ruta sirve la frase que dice que cuenta cada columna, y lo que la frase
    afirma se comprueba aqui sobre lo que el registro DE VERDAD escribe: una fila al abrirse, otra al cerrarse."""
    conn, _, T = sembrada
    marco = (await _vista(conn))["marco"]
    frase = marco["cuentas_que_cuentan"]
    assert frase == V.CUENTAS_QUE_CUENTAN and "NO planes vivos" in frase
    assert all(e.replace("_", " ") in frase for e in M.ESTADOS), "la frase nombra la fila de cada columna"
    # la cabecera de cada columna: una por estado del motor, y ninguna se llama como el estado de un plan
    assert tuple(marco["cuentas_rotulos"]) == M.ESTADOS
    assert not set(marco["cuentas_rotulos"].values()) & {*V.ROTULOS_VIVO.values(), *M.ESTADOS}

    async def episodios():
        return [dict(f) for f in await conn.fetch(
            "SELECT version, symbol, familia, perfil, lado, clave, episodio, "
            "count(*) FILTER (WHERE estado = 'VIGILANDO') AS abre, "
            "count(*) FILTER (WHERE estado <> 'VIGILANDO') AS cierra "
            "FROM entrada_registro GROUP BY 1, 2, 3, 4, 5, 6, 7 ORDER BY 1, 2, 3, 4, 5, 6, 7")]

    antes = await episodios()
    assert antes and all(e["abre"] == 1 and e["cierra"] <= 1 for e in antes), "una fila al abrirse y como mucho otra al cerrarse"
    assert any(e["cierra"] for e in antes), "el escenario trae episodios cerrados"
    # cada columna cuenta los episodios que tienen esa fila; uno que sigue abierto solo cuenta en la primera
    assert marco["cuentas"]
    for c in marco["cuentas"]:
        suyos = [e for e in antes if all(e[k] == c[k] for k in ("familia", "perfil", "lado", "version"))]
        assert c["VIGILANDO"] == len(suyos)
        assert c["DISPARADO"] + c["SOMBRA"] + c["CERRADO_SIN_DISPARO"] == sum(e["cierra"] for e in suyos)
    # y re-evaluar la misma vela (la recuperacion de una pasada que murio a medias) no le anade filas a ninguno
    await S.evaluar_vela(conn, T=T, doc=B.doc_de_prueba(T, "v1", "v2", tope_s=900), huella_codigo=C.huella_codigo(),
                         esperar=False)
    assert await episodios() == antes


def test_un_plan_caducado_no_sale_como_vivo_y_el_orden_es_por_hora():
    r = EB.respuesta(None, caduca_en_s=-1.0, latido_hace_s=None)
    assert _planes(r, "disparados") == [], "caduco hace un segundo: no esta entre lo vivo"
    activa = r["reciente"]["por_version"][0]
    assert [(d["registro_id"], d["caducado"], d["vivo"]) for d in activa["disparados"]] == [(7, True, False)]
    assert [s["registro_id"] for s in activa["sombras"]] == [3, 2, 1], "por hora, y a igual hora el mas reciente"
    # un plan de v1 y otro de v2 sobre la MISMA zona: cada uno en el bloque de SU version
    celda = r["vivo"]["celdas"][0]
    assert [(v["version"], v["papel"], [p["registro_id"] for p in v["vigilando"]]) for v in celda["por_version"]] == [
        ("v2", "ACTIVA", [11]), ("v1", "ANCLA", [10])]
    assert celda["por_version"][0]["vigilando"][0]["zona"] == celda["por_version"][1]["vigilando"][0]["zona"]
    # una celda vacia dice por que, y un generador que no ha corrido tambien
    vacias = [v["sin_planes"] for c in r["vivo"]["celdas"][1:] for v in c["por_version"]]
    assert len(vacias) == 6 and all(vacias)
    assert r["generador"]["ultimo_latido"] is None and r["generador"]["motivo"]
    assert V._distancia({"low": 100.0, "high": 101.0}, {"valor": 102.0}) == {
        "pct": 0.98, "donde": "por encima de la zona", "motivo": None}
    assert V._distancia({"low": 100.0, "high": 101.0}, {"valor": 99.0})["donde"] == "por debajo de la zona"
    assert V._distancia({"low": 100.0, "high": 101.0}, {"valor": 100.5})["pct"] == 0.0
    assert V._distancia({"low": 100.0, "high": 101.0}, {"valor": None, "motivo": "sin vela"})["motivo"] == "sin vela"
    assert RUTA.fracciones_servidas(r) == []


def test_la_pasada_a_medias_se_dice_y_solo_mientras_dura():
    """Cada version registra a su hora y el latido se escribe al acabar la ultima (TRASPASO del
    10-10: «no leer una pasada antes de T + 4 min»). La pantalla se mira a cualquier hora: si hay
    planes de una vela que aun no ha latido, la ruta lo dice."""
    acabada = EB.respuesta("LONG")
    assert acabada["generador"]["pasada_en_curso"] is None, "el latido es de la ultima vela con planes"
    a_medias = EB.respuesta("LONG", latido_vela_h=10)
    frase = a_medias["generador"]["pasada_en_curso"]
    assert frase.startswith("La vela de las 11:00Z esta todavia registrandose")
    assert "v1 a partir de los 20 s y v2 a partir de los 135 s" in frase, "las horas salen del reglamento"
    assert EB.respuesta("LONG", latido_hace_s=None)["generador"]["pasada_en_curso"] is None, "sin latido lo dice el aviso"
    assert RUTA.fracciones_servidas(a_medias) == []


async def test_la_ruta_rechaza_un_parametro_que_no_conoce(sembrada):
    class Peticion:
        query_params = {"symbol": "BTCUSDT_PERP.A", "foto": "true"}

    with pytest.raises(api.HTTPException) as fallo:
        await api.mesa_entradas(Peticion(), symbol="BTCUSDT_PERP.A")
    assert fallo.value.status_code == 422 and "foto" in fallo.value.detail
    assert V.REFRESCO_S == 45 and V.SIN_DATO_S > 2 * V.REFRESCO_S, "la vista obedece la cadencia servida"
    # la cadencia se sirve: la pantalla no la decide
    conn, _, _ = sembrada
    frescura = (await _vista(conn))["frescura"]
    assert (frescura["refresco_s"], frescura["sin_dato_s"]) == (V.REFRESCO_S, V.SIN_DATO_S)
    assert (timedelta(seconds=V.VELA_GENERADOR_S * V.VELAS_SIN_LATIR)) == timedelta(minutes=30)
