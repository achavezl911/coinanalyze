"""C1 de la campana 135 · el REGLAMENTO de las entradas se defiende solo.

Lo que se promete y cada plantado que tiene que fallar (el gemelo correcto pasa):

- un umbral que cambia sin version nueva: la huella declarada deja de ser la calculada;
- un umbral de F1 cambiado mueve la huella de F1 y NO la de F2 (ni la del bloque comun);
- dos reglas bajo una etiqueta de version (la regla de K62);
- una version sin HIPOTESIS;
- el ANCLA retirada;
- un umbral sin ORIGEN;
- un evento de calendario con hora anterior a la revision que lo trae o sin fuente, o una
  revision con una huella que no es la suya (los plantados van sobre la revision REAL mas
  nueva: cal-3 desde la campana 141);
- y, contra main, que ninguna version ni revision registrada cambie -ni un byte de su objeto,
  salvo retirarse- ni desaparezca del fichero (cal-1 y cal-2, cada una con su plantado).

Campana 136: v2 es v1 con los tres cambios del lazo y ninguno mas; cada version cabe con su
espera dentro de su tope; y las APUESTAS (las celdas que cuentan como hipotesis probadas) se
contrastan con las versiones del fichero: una apuesta que no cuadra no entra.

Campana 141: solo vale la revision vigente, asi que cal-3 (padre cal-2) trae TAL CUAL los
eventos de cal-2 desde su vigente_desde, mas los de diciembre; la vigente pasa de cal-2 a cal-3
el 2026-10-18T00:00:00Z.

El CI clona a profundidad 1, asi que la historia se compara contra origin/main, que el paso
«Fetch main for the reglamento history test» de .github/workflows/ci.yml trae antes de pytest.
Fuera de CI, sin esa referencia, ese test se SALTA y lo dice; dentro de CI, sin ella, FALLA:
no ver la historia no es un aprobado.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from app.entradas import reglamento as R

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def doc() -> dict:
    return R.cargar()


PRUEBA = "v-prueba"


def _nueva_version(doc: dict, *, etiqueta: str = PRUEBA, con_hipotesis: bool = True) -> dict:
    """Una hija correcta de v1 que cambia SOLO F2 (retest_max_velas 8 -> 10) y apuesta en F2
    intradia. Lleva su propia etiqueta: el fichero ya tiene una v2 de verdad (campana 136)."""
    v1 = R.version(doc, "v1")
    nueva = copy.deepcopy(v1)
    nueva.update(
        {
            "version": etiqueta,
            "padre": "v1",
            "fecha": "2026-10-20",
            "autor": "plantado del test",
            "motivo": "prueba: mas velas para el retest",
            "ancla": False,
            "retirada": None,
        }
    )
    nueva["bloques"]["F2"]["parametros"]["retest_max_velas"]["valor"] = 10
    nueva["huellas"] = {n: R.huella_bloque(nueva["bloques"][n]) for n in R.BLOQUES}
    if con_hipotesis:
        nueva["hipotesis"] = {
            "celdas": "F2 intradia largo y corto",
            "sentido": "mas DISPARADOS sin bajar el exceso sobre el equilibrio",
            "lectura": "n efectiva 30 de F2 intradia",
        }
    else:
        nueva.pop("hipotesis")
    doc["versiones"].append(nueva)
    doc["apuestas"]["versiones"].setdefault(
        etiqueta, {"celdas": [["F2", "intradia", "largo"], ["F2", "intradia", "corto"]]}
    )
    return nueva


def test_el_reglamento_del_arbol_es_valido(doc):
    assert R.validar(doc) == []


def test_el_test_recalcula_las_huellas_declaradas(doc):
    for v in doc["versiones"]:
        for nombre in R.BLOQUES:
            assert v["huellas"][nombre] == R.huella_bloque(v["bloques"][nombre]), (v["version"], nombre)
    for r in doc["calendario"]["revisiones"]:
        assert r["huella"] == R.huella_revision(r), r["revision"]


def test_un_umbral_de_F1_cambiado_mueve_su_huella_y_no_la_de_F2(doc):
    antes = {n: R.huella_bloque(doc["versiones"][0]["bloques"][n]) for n in R.BLOQUES}
    plantado = copy.deepcopy(doc)
    plantado["versiones"][0]["bloques"]["F1"]["parametros"]["entrada"]["valor"] = "limite"
    despues = {n: R.huella_bloque(plantado["versiones"][0]["bloques"][n]) for n in R.BLOQUES}
    assert antes["F1"] != despues["F1"]
    assert {n: antes[n] for n in R.BLOQUES if n != "F1"} == {
        n: despues[n] for n in R.BLOQUES if n != "F1"
    }
    errores = R.validar(plantado)
    assert len(errores) == 1 and "huella declarada de F1" in errores[0], errores
    assert "sin version nueva" in errores[0]


def test_un_cambio_de_texto_que_no_decide_no_mueve_la_huella(doc):
    antes = R.huella_bloque(doc["versiones"][0]["bloques"]["comun"])
    plantado = copy.deepcopy(doc)
    p = plantado["versiones"][0]["bloques"]["comun"]["parametros"]["tope_retraso_s"]
    p["origen"] = p["origen"] + " · cita corregida"
    assert R.huella_bloque(plantado["versiones"][0]["bloques"]["comun"]) == antes
    assert R.validar(plantado) == []


def test_dos_reglas_bajo_una_etiqueta_de_version(doc):
    _nueva_version(doc, etiqueta="v1")
    errores = R.validar(doc)
    assert any("aparece dos veces" in e and "no abarca dos reglas" in e for e in errores), errores


def test_una_version_sin_hipotesis_no_entra_y_su_gemela_si(doc):
    gemela = copy.deepcopy(doc)
    _nueva_version(gemela)
    assert R.validar(gemela) == []
    _nueva_version(doc, con_hipotesis=False)
    errores = R.validar(doc)
    assert any("sin HIPOTESIS" in e for e in errores), errores


def test_el_ancla_retirada_no_entra(doc):
    doc["versiones"][0]["retirada"] = {
        "fecha": "2026-11-01",
        "motivo": "plantado",
        "antes_de_su_lectura": True,
    }
    errores = R.validar(doc)
    assert any("el ANCLA no se retira" in e for e in errores), errores


def test_una_version_retirada_sigue_en_el_fichero_y_deja_de_correr(doc):
    en_curso = [v["version"] for v in R.versiones_en_curso(doc)]
    nueva = _nueva_version(doc)
    nueva["retirada"] = {"fecha": "2026-11-01", "motivo": "plantado", "antes_de_su_lectura": True}
    assert R.validar(doc) == []
    assert [v["version"] for v in R.versiones_en_curso(doc)] == en_curso
    assert R.version(doc, PRUEBA) is not None


def test_la_activa_es_la_ultima_por_orden_del_fichero(doc):
    en_curso = [v["version"] for v in R.versiones_en_curso(doc)]
    assert en_curso[0] == "v1" and R.version_activa(doc)["version"] == en_curso[-1]
    _nueva_version(doc)
    assert R.version_activa(doc)["version"] == PRUEBA
    assert [v["version"] for v in R.versiones_en_curso(doc)] == en_curso + [PRUEBA]


def test_un_umbral_sin_origen_no_entra(doc):
    doc["versiones"][0]["bloques"]["F2"]["parametros"]["retest_max_velas"]["origen"] = ""
    errores = R.validar(doc)
    assert any("sin ORIGEN" in e and "retest_max_velas" in e for e in errores), errores


def test_una_version_identica_a_su_padre_no_entra(doc):
    nueva = _nueva_version(doc)
    nueva["bloques"]["F2"]["parametros"]["retest_max_velas"]["valor"] = 8
    nueva["huellas"] = {n: R.huella_bloque(nueva["bloques"][n]) for n in R.BLOQUES}
    errores = R.validar(doc)
    assert any("no cambia ningun bloque" in e for e in errores), errores


def _ultima_revision(doc: dict) -> dict:
    """La revision de eventos mas nueva del fichero (cal-3 desde la campana 141): el sujeto de
    los plantados del calendario es la revision REAL, no una inventada por el test."""
    r = doc["calendario"]["revisiones"][-1]
    assert r["eventos"], f"{r['revision']} no trae eventos: el plantado no tendria sujeto"
    return r


def test_un_evento_anterior_a_su_revision_no_entra_y_su_gemelo_si(doc):
    assert R.validar(copy.deepcopy(doc)) == []  # el gemelo: la revision tal como esta
    r = _ultima_revision(doc)
    # un segundo antes de vigente_desde, y con la huella RECALCULADA: lo unico malo es la hora
    r["eventos"][0]["hora_utc"] = (
        R.instante(r["vigente_desde"]) - timedelta(seconds=1)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    r["huella"] = R.huella_revision(r)
    errores = R.validar(doc)
    assert len(errores) == 1 and "anterior a la revision que lo trae" in errores[0], errores
    assert r["revision"] in errores[0] and r["eventos"][0]["clave"] in errores[0]


def test_una_revision_con_una_huella_que_no_es_la_suya_no_entra(doc):
    r = _ultima_revision(doc)
    for otra in doc["calendario"]["revisiones"][:-1]:  # la de cada anterior, la de su padre incluida
        plantado = copy.deepcopy(doc)
        plantado["calendario"]["revisiones"][-1]["huella"] = otra["huella"]
        errores = R.validar(plantado)
        assert len(errores) == 1 and "la huella declarada" in errores[0], (otra["revision"], errores)
        assert r["revision"] in errores[0]


def test_un_evento_cambiado_sin_recalcular_la_huella_no_entra(doc):
    r = _ultima_revision(doc)
    r["eventos"][-1]["importancia"] = 1 if r["eventos"][-1]["importancia"] != 1 else 3
    errores = R.validar(doc)
    assert len(errores) == 1 and "la huella declarada" in errores[0], errores


@pytest.mark.parametrize("etiqueta, cubre_hasta", [
    ("cal-1", "2026-10-05T00:00:00Z"),
    ("cal-2", "2026-12-31T23:59:59Z"),  # estirar cal-2 en vez de traer cal-3 (campana 141)
])
def test_una_revision_ya_registrada_tocada_no_entra(doc, etiqueta, cubre_hasta):
    """cal-1 y cal-2 (y toda revision que ya este en main) no se tocan. Sin recalcular su huella
    la para el validador; recalculada, el validador NO puede verlo y la para la historia contra
    main; y un byte que no decide (su motivo) tampoco pasa: la revision se queda ENTERA."""
    main = copy.deepcopy(doc)
    assert _cambios_de_historia(main, doc) == []  # el gemelo
    i = [r["revision"] for r in doc["calendario"]["revisiones"]].index(etiqueta)
    tocada = doc["calendario"]["revisiones"][i]
    tocada["cubre_hasta"] = cubre_hasta
    errores = R.validar(doc)
    assert len(errores) == 1 and f"({etiqueta})" in errores[0] and "la huella declarada" in errores[0], errores
    tocada["huella"] = R.huella_revision(tocada)
    assert R.validar(doc) == []  # lavado: el fichero solo no lo ve
    assert f"la revision {etiqueta} de main cambio: cubre_hasta, huella" in _cambios_de_historia(main, doc)
    otro = copy.deepcopy(main)
    otro["calendario"]["revisiones"][i]["motivo"] += " (retocado)"
    assert R.validar(otro) == []
    assert _cambios_de_historia(main, otro) == [f"la revision {etiqueta} de main cambio: motivo"]
    otro = copy.deepcopy(main)
    del otro["calendario"]["revisiones"][i]
    assert f"la revision {etiqueta} de main desaparecio" in _cambios_de_historia(main, otro)


def test_un_evento_sin_fuente_no_entra(doc):
    r = _ultima_revision(doc)
    evento = r["eventos"][0]
    del evento["fuente"]  # la fuente no entra en la huella: lo unico malo es que falta
    errores = R.validar(doc)
    assert len(errores) == 1 and f"evento {evento['clave']} sin fuente" in errores[0], errores


def test_cal3_trae_tal_cual_los_de_cal2_que_quedan_y_los_de_diciembre(doc):
    """Campana 141. Cuando cal-3 entra en vigor los eventos de cal-2 dejan de contar: cal-3 TRAE
    los de cal-2 desde su vigente_desde, tal cual (su fuente incluida), mas 12 nuevos, todos
    despues de lo que cubria cal-2 y dentro de lo que cubre ella."""
    revisiones = {r["revision"]: r for r in doc["calendario"]["revisiones"]}
    assert "cal-3" in revisiones, "el reglamento no trae cal-3"
    cal2, cal3 = revisiones["cal-2"], revisiones["cal-3"]
    assert (cal3["padre"], cal3["vigente_desde"], cal3["cubre_hasta"]) == (
        "cal-2", "2026-10-18T00:00:00Z", "2026-12-31T23:59:59Z")
    desde = R.instante(cal3["vigente_desde"])
    quedan = [e for e in cal2["eventos"] if R.instante(e["hora_utc"]) >= desde]
    de_cal2 = {e["clave"] for e in cal2["eventos"]}
    assert [e for e in cal3["eventos"] if e["clave"] in de_cal2] == quedan and len(quedan) == 18
    nuevos = [e for e in cal3["eventos"] if e["clave"] not in de_cal2]
    assert len(nuevos) == 12 and all(
        R.instante(cal2["cubre_hasta"]) < R.instante(e["hora_utc"]) <= R.instante(cal3["cubre_hasta"])
        for e in nuevos
    )


def test_la_vigente_es_cal2_hasta_el_18_de_octubre_y_cal3_desde_entonces(doc):
    def vigente(texto: str) -> str:
        return R.revision_vigente(doc, R.instante(texto))["revision"]

    assert vigente("2026-10-17T23:59:59Z") == "cal-2"
    assert vigente("2026-10-18T00:00:00Z") == "cal-3"
    assert vigente("2026-12-31T23:59:59Z") == "cal-3"


def test_la_diferencia_con_el_padre_nombra_lo_que_cambia(doc):
    _nueva_version(doc)
    dif = R.diferencia_con_padre(doc, PRUEBA)
    assert dif["padre"] == "v1"
    assert [n for n, b in dif["bloques"].items() if b["cambia"]] == ["F2"]
    assert list(dif["bloques"]["F2"]["parametros"]) == ["retest_max_velas"]
    assert R.diferencia_con_padre(doc, "v1")["padre"] is None


def test_el_canonico_es_el_de_signal_replay(doc):
    signal_replay = pytest.importorskip("app.signal_replay")
    contenido = R.contenido_bloque(doc["versiones"][0]["bloques"]["comun"])
    assert R.huella(contenido) == signal_replay.canonical_json_hash(contenido)


def test_rellenar_no_reescribe_una_huella_declarada(doc, tmp_path):
    ruta = tmp_path / "reglamento.json"
    plantado = copy.deepcopy(doc)
    plantado["versiones"][0]["bloques"]["F1"]["parametros"]["entrada"]["valor"] = "limite"
    ruta.write_text(json.dumps(plantado), encoding="utf-8")
    assert R.main(["--ruta", str(ruta), "--rellena"]) == 1
    releido = R.cargar(ruta)
    assert releido["versiones"][0]["huellas"]["F1"] == doc["versiones"][0]["huellas"]["F1"]


def test_los_registros_esperados_cubren_cada_bloque_y_cada_revision(doc):
    filas = R.registros_esperados(doc)
    assert len(filas) == len(doc["versiones"]) * len(R.BLOQUES) + len(
        doc["calendario"]["revisiones"]
    )
    assert len({(f["etiqueta"], f["bloque"]) for f in filas}) == len(filas)
    for f in filas:
        assert f["huella"] == R.huella(f["contenido"])


# --------------------------------------------------------------------------- v2 (campana 136)

# Los TRES cambios decididos por el operador (lazo 1 y su adenda) y los parametros de cada uno.
TRES_CAMBIOS = {
    "a · el stop sin cascada": {("comun", "colchon_stop")},
    "b · el registro espera al spot": {("comun", "tope_retraso_s"), ("comun", "espera_datos_s"),
                                       ("comun", "espera_flujos")},
    "c · el paso de cantidad de Bybit": {("papel", "paso_cantidad_bybit")},
}


def test_v2_es_v1_con_los_tres_cambios_y_ninguno_mas(doc):
    v1, v2 = R.version(doc, "v1"), R.version(doc, "v2")
    assert v2["padre"] == "v1" and v2["ancla"] is False and v2["retirada"] is None
    dif = R.diferencia_con_padre(doc, "v2")
    cambiados = {(b, p) for b, cuerpo in dif["bloques"].items() for p in cuerpo["parametros"]}
    assert cambiados == set().union(*TRES_CAMBIOS.values()), cambiados
    for bloque in ("F1", "F2", "calendario", "lectura"):
        assert v2["huellas"][bloque] == v1["huellas"][bloque], bloque
    comun, padre = R.valores(v2["bloques"]["comun"]), R.valores(v1["bloques"]["comun"])
    assert padre["colchon_stop"]["fuera_de_racimo"] is True
    assert comun["colchon_stop"] == {**padre["colchon_stop"], "fuera_de_racimo": False}
    assert (padre["tope_retraso_s"], comun["tope_retraso_s"]) == (120, 240)
    assert "espera_flujos" not in padre and comun["espera_flujos"] == ["spot", "futuros"]
    paso = R.valores(v2["bloques"]["papel"])["paso_cantidad_bybit"]
    assert paso == {"BTCUSDT_PERP.A": 0.001, "ETHUSDT_PERP.A": 0.01, "SOLUSDT_PERP.A": 0.1}
    assert set(paso) == set(comun["simbolos"])
    assert "las 16" in v2["motivo"] and "son 8" in v2["motivo"]  # la errata de v1, declarada


def test_la_espera_de_cada_version_cabe_en_su_tope_y_en_la_cadencia(doc):
    """«Dentro del tope»: ningun intento empieza despues del tope de retraso de su version, y lo
    que tarda la pasada mas larga no llega a la siguiente (C4 e)."""
    cadencia = min(p["vela_min"] * 60 for v in R.versiones_en_curso(doc)
                   for p in R.valores(v["bloques"]["comun"])["perfiles"].values())
    for v in R.versiones_en_curso(doc):
        c = R.valores(v["bloques"]["comun"])
        e = c["espera_datos_s"]
        assert 0 < e["primer_intento"] <= e["ultimo_intento"] < c["tope_retraso_s"], v["version"]
        assert e["reintento"] > 0
        assert c["tope_retraso_s"] < c["tope_tick_s"] <= cadencia, v["version"]


def test_la_hipotesis_de_v2_declara_el_m_que_dicen_sus_apuestas(doc):
    v2 = R.version(doc, "v2")
    assert set(v2["hipotesis"]) == {"celdas", "sentido", "lectura"}
    apostado = R.apuestas(doc)
    f1 = sum(1 for a in apostado.values() for c in a["apostadas"] if c[0] == "F1")
    f2 = sum(1 for a in apostado.values() for c in a["apostadas"] if c[0] == "F2")
    assert (f1, f2) == (6, 4)
    # el texto libre dice lo mismo que la declaracion que lee la maquina
    m = re.search(r"Bonferroni con m = (\d+)", v2["hipotesis"]["lectura"])
    assert m and int(m.group(1)) == f1
    assert v2["hipotesis"]["lectura"].endswith("se publica cuantos son.")  # el parrafo de la adenda
    assert apostado["v1"] == {"apostadas": R.celdas(R.version(doc, "v1")), "sin_apuesta": []}
    assert apostado["v2"]["apostadas"] == [["F1", "intradia", "largo"], ["F1", "intradia", "corto"]]
    assert len(apostado["v2"]["sin_apuesta"]) == 6


def test_el_reglamento_del_arbol_declara_sus_apuestas_y_el_de_la_135_valida_sin_ellas(doc):
    assert set(doc["apuestas"]["versiones"]) == {v["version"] for v in doc["versiones"]}
    # el fichero del release de la 135 (solo v1, sin la seccion): valido, y nadie cuenta nada
    viejo = copy.deepcopy(doc)
    viejo["versiones"] = viejo["versiones"][:1]
    del viejo["apuestas"]
    assert R.validar(viejo) == [] and R.apuestas(viejo) is None


@pytest.mark.parametrize(
    "nombre, plantar, rastro",
    [
        ("version fantasma", lambda a: a.update({"v9": {"celdas": []}}), "v9 no es una version"),
        ("version sin declarar", lambda a: a.pop("v2"), "v2 no declara en que celdas apuesta"),
        ("familia que no existe", lambda a: a["v2"]["celdas"].append(["F3", "intradia", "largo"]),
         "no es una celda suya"),
        ("perfil que no es suyo", lambda a: a["v2"]["celdas"].append(["F1", "diario", "largo"]),
         "no es una celda suya"),
        ("lado que no existe", lambda a: a["v2"]["celdas"].append(["F1", "swing", "neutral"]),
         "no es una celda suya"),
        ("celda repetida", lambda a: a["v2"]["celdas"].append(["F1", "intradia", "largo"]),
         "repite la celda"),
    ],
)
def test_una_apuesta_que_no_cuadra_con_las_versiones_no_entra(doc, nombre, plantar, rastro):
    assert R.validar(copy.deepcopy(doc)) == []  # el gemelo
    plantar(doc["apuestas"]["versiones"])
    errores = R.validar(doc)
    assert len(errores) == 1 and rastro in errores[0], (nombre, errores)


# --------------------------------------------------------------------------- historia


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=60, check=False
    )


def _cambios_de_historia(anterior: dict, doc: dict) -> list[str]:
    """Lo que el fichero `doc` cambia de lo que `anterior` (main) ya tenia. Vacia = nada.

    Una version o una revision que ya esta en main se queda ENTERA (regla 1 del fichero): se
    compara el objeto, no solo su huella, porque la HIPOTESIS, el motivo y el origen no entran
    en ninguna huella y reescribirlos despues de ver un resultado seria lo mismo que cambiar la
    regla. Lo unico que puede pasarle a una version es retirarse (retirada: null -> objeto)."""
    cambios: list[str] = []
    for v in anterior["versiones"]:
        actual = R.version(doc, v["version"])
        if actual is None:
            cambios.append(f"la version {v['version']} de main desaparecio del fichero")
            continue
        for nombre in R.BLOQUES:
            if R.huella_bloque(actual["bloques"][nombre]) != R.huella_bloque(v["bloques"][nombre]):
                cambios.append(
                    f"{v['version']}.{nombre} cambio respecto a main: eso es una version nueva"
                )
        if v.get("retirada") is not None and actual.get("retirada") != v["retirada"]:
            cambios.append(f"{v['version']} des-retirada")
        distintos = sorted(
            k for k in set(v) | set(actual) if k != "retirada" and v.get(k) != actual.get(k)
        )
        if distintos:
            cambios.append(f"la version {v['version']} de main cambio: {', '.join(distintos)}")
    por_etiqueta = {r["revision"]: r for r in doc["calendario"]["revisiones"]}
    for r in anterior["calendario"]["revisiones"]:
        actual = por_etiqueta.get(r["revision"])
        if actual is None:
            cambios.append(f"la revision {r['revision']} de main desaparecio")
            continue
        distintos = sorted(k for k in set(r) | set(actual) if r.get(k) != actual.get(k))
        if distintos:
            cambios.append(f"la revision {r['revision']} de main cambio: {', '.join(distintos)}")
    # las apuestas de una version registrada: quitar una celda despues seria bajar el m de su familia
    ahora = (doc.get("apuestas") or {}).get("versiones", {})
    for version, entrada in (anterior.get("apuestas") or {}).get("versiones", {}).items():
        if ahora.get(version) != entrada:
            cambios.append(f"las apuestas de {version} de main cambiaron")
    return cambios


def test_la_historia_ve_un_byte_de_una_version_ya_registrada(doc):
    """v1 no se toca en un byte: ni un umbral (con su huella lavada), ni su hipotesis, ni un
    origen. La retirada si puede llegar, y una vez puesta no se quita."""
    main = copy.deepcopy(doc)
    plantado = copy.deepcopy(doc)
    plantado["versiones"][0]["hipotesis"]["celdas"] = "las 8"
    assert R.validar(plantado) == []  # ninguna huella cubre la hipotesis: el fichero solo no lo ve
    assert _cambios_de_historia(main, plantado) == ["la version v1 de main cambio: hipotesis"]
    plantado = copy.deepcopy(doc)
    comun = plantado["versiones"][0]["bloques"]["comun"]
    comun["parametros"]["colchon_stop"]["valor"]["fuera_de_racimo"] = False
    assert any("huella declarada de comun" in e for e in R.validar(plantado))
    plantado["versiones"][0]["huellas"]["comun"] = R.huella_bloque(comun)
    assert R.validar(plantado) == []  # lavado
    cambios = _cambios_de_historia(main, plantado)
    assert "v1.comun cambio respecto a main: eso es una version nueva" in cambios, cambios
    plantado = copy.deepcopy(doc)
    plantado["versiones"][0]["bloques"]["papel"]["parametros"]["meta_usd"]["origen"] += " · retocado"
    assert _cambios_de_historia(main, plantado) == ["la version v1 de main cambio: bloques"]
    # y sus apuestas: dejar a v1 con 4 celdas bajaria el m de F2 sin que ninguna huella se mueva
    plantado = copy.deepcopy(doc)
    plantado["apuestas"]["versiones"]["v1"]["celdas"] = plantado["apuestas"]["versiones"]["v1"]["celdas"][:4]
    assert R.validar(plantado) == []
    assert _cambios_de_historia(main, plantado) == ["las apuestas de v1 de main cambiaron"]


def test_ninguna_version_registrada_en_main_cambia_ni_desaparece(doc):
    ref = os.environ.get("ENTRADAS_REF_HISTORIA", "origin/main")
    if _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
        mensaje = f"sin {ref}: el test de historia no puede ver el reglamento anterior"
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail(mensaje + " (en CI lo trae el paso 'Fetch main for the reglamento history test')")
        pytest.skip(mensaje)
    previo = _git("show", f"{ref}:config/entradas/reglamento.json")
    if previo.returncode != 0:
        assert "does not exist" in previo.stderr or "exists on disk" in previo.stderr, previo.stderr
        return  # main todavia no tiene reglamento: no hay nada registrado que guardar
    assert _cambios_de_historia(json.loads(previo.stdout), doc) == []
