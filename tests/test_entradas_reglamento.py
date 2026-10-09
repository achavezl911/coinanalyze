"""C1 de la campana 135 · el REGLAMENTO de las entradas se defiende solo.

Lo que se promete y cada plantado que tiene que fallar (el gemelo correcto pasa):

- un umbral que cambia sin version nueva: la huella declarada deja de ser la calculada;
- un umbral de F1 cambiado mueve la huella de F1 y NO la de F2 (ni la del bloque comun);
- dos reglas bajo una etiqueta de version (la regla de K62);
- una version sin HIPOTESIS;
- el ANCLA retirada;
- un umbral sin ORIGEN;
- un evento de calendario con hora anterior a la revision que lo trae, o una revision con una
  huella que no es la suya (campana 136: los plantados van sobre la revision REAL, cal-2);
- y, contra main, que ninguna version ni revision registrada cambie -ni un byte de su objeto,
  salvo retirarse- ni desaparezca del fichero.

El CI clona a profundidad 1, asi que la historia se compara contra origin/main, que el paso
«Fetch main for the reglamento history test» de .github/workflows/ci.yml trae antes de pytest.
Fuera de CI, sin esa referencia, ese test se SALTA y lo dice; dentro de CI, sin ella, FALLA:
no ver la historia no es un aprobado.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from app.entradas import reglamento as R

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def doc() -> dict:
    return R.cargar()


def _nueva_version(doc: dict, *, etiqueta: str = "v2", con_hipotesis: bool = True) -> dict:
    """Una hija correcta de v1 que cambia SOLO F2 (retest_max_velas 8 -> 10)."""
    v1 = R.version(doc, "v1")
    v2 = copy.deepcopy(v1)
    v2.update(
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
    v2["bloques"]["F2"]["parametros"]["retest_max_velas"]["valor"] = 10
    v2["huellas"] = {n: R.huella_bloque(v2["bloques"][n]) for n in R.BLOQUES}
    if con_hipotesis:
        v2["hipotesis"] = {
            "celdas": "F2 intradia largo y corto",
            "sentido": "mas DISPARADOS sin bajar el exceso sobre el equilibrio",
            "lectura": "n efectiva 30 de F2 intradia",
        }
    else:
        v2.pop("hipotesis")
    doc["versiones"].append(v2)
    return v2


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
    v2 = _nueva_version(doc)
    v2["retirada"] = {"fecha": "2026-11-01", "motivo": "plantado", "antes_de_su_lectura": True}
    assert R.validar(doc) == []
    assert [v["version"] for v in R.versiones_en_curso(doc)] == ["v1"]
    assert R.version(doc, "v2") is not None


def test_la_activa_es_la_ultima_por_orden_del_fichero(doc):
    assert R.version_activa(doc)["version"] == "v1"
    _nueva_version(doc)
    assert R.version_activa(doc)["version"] == "v2"
    assert [v["version"] for v in R.versiones_en_curso(doc)] == ["v1", "v2"]


def test_un_umbral_sin_origen_no_entra(doc):
    doc["versiones"][0]["bloques"]["F2"]["parametros"]["retest_max_velas"]["origen"] = ""
    errores = R.validar(doc)
    assert any("sin ORIGEN" in e and "retest_max_velas" in e for e in errores), errores


def test_una_version_identica_a_su_padre_no_entra(doc):
    v2 = _nueva_version(doc)
    v2["bloques"]["F2"]["parametros"]["retest_max_velas"]["valor"] = 8
    v2["huellas"] = {n: R.huella_bloque(v2["bloques"][n]) for n in R.BLOQUES}
    errores = R.validar(doc)
    assert any("no cambia ningun bloque" in e for e in errores), errores


def _ultima_revision(doc: dict) -> dict:
    """La revision de eventos mas nueva del fichero (cal-2 desde la campana 136): el sujeto de
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
    r["huella"] = doc["calendario"]["revisiones"][0]["huella"]  # la de cal-1, que es de otra
    errores = R.validar(doc)
    assert len(errores) == 1 and "la huella declarada" in errores[0], errores
    assert r["revision"] in errores[0]


def test_un_evento_cambiado_sin_recalcular_la_huella_no_entra(doc):
    r = _ultima_revision(doc)
    r["eventos"][-1]["importancia"] = 1 if r["eventos"][-1]["importancia"] != 1 else 3
    errores = R.validar(doc)
    assert len(errores) == 1 and "la huella declarada" in errores[0], errores


def test_una_revision_ya_registrada_tocada_no_entra(doc):
    """cal-1 (y toda revision que ya este en main) no se toca. Sin recalcular su huella la para
    el validador; recalculada, el validador NO puede verlo y la para la historia contra main;
    y un byte que no decide (su motivo) tampoco pasa: la revision se queda ENTERA."""
    main = copy.deepcopy(doc)
    assert _cambios_de_historia(main, doc) == []  # el gemelo
    cal1 = doc["calendario"]["revisiones"][0]
    cal1["cubre_hasta"] = "2026-10-05T00:00:00Z"
    errores = R.validar(doc)
    assert len(errores) == 1 and "cal-1" in errores[0] and "la huella declarada" in errores[0], errores
    cal1["huella"] = R.huella_revision(cal1)
    assert R.validar(doc) == []  # lavado: el fichero solo no lo ve
    assert any("cal-1" in c for c in _cambios_de_historia(main, doc))
    otro = copy.deepcopy(main)
    otro["calendario"]["revisiones"][0]["motivo"] += " (retocado)"
    assert R.validar(otro) == []
    assert _cambios_de_historia(main, otro) == ["la revision cal-1 de main cambio: motivo"]
    otro = copy.deepcopy(main)
    del otro["calendario"]["revisiones"][0]
    assert "la revision cal-1 de main desaparecio" in _cambios_de_historia(main, otro)


def test_la_diferencia_con_el_padre_nombra_lo_que_cambia(doc):
    _nueva_version(doc)
    dif = R.diferencia_con_padre(doc, "v2")
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
