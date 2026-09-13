"""El descubridor del panel, y su control en las dos direcciones.

Estos tests son la red que impide que la FASE 2 deje ciego al resto: si el descubrimiento se
rompe, esto lo dice AQUI y no en forma de nueve suites que aprueban sin sujeto.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from panel_fuentes import FICHEROS, FUENTE, RAIZ

BIN = RAIZ / "harness" / "bin" / "panel-fuentes"


def _corre(repo: Path, *args: str):
    return subprocess.run([sys.executable, str(BIN), "--repo", str(repo), *args],
                          capture_output=True, text=True, timeout=120)


def test_hoy_descubre_el_panel_y_es_el_fichero_de_siempre() -> None:
    """Con UN fichero, la concatenacion tiene que ser byte a byte `static/app.js`.

    Es lo que permite exigir la regresion EXACTA en vez de «parecida».
    """
    # SE COMPARA CONTRA EL FICHERO DE VERDAD, leido aqui a proposito. Mi propio parcheador
    # automatico convirtio esta linea en `FUENTE == FUENTE` -una tautologia que pasa siempre-
    # y eso es exactamente aflojar un criterio hasta que deje de condenar. Restaurada.
    assert FICHEROS, "el descubridor no encontro ninguna fuente del panel"
    assert (RAIZ / "static" / "app.js").read_text(encoding="utf-8") == FUENTE


def _arbol_de_modulos(tmp: Path) -> Path:
    """Un arbol minimo CON LA FORMA NUEVA: entrada con type=module e imports relativos."""
    st = tmp / "static"
    (st / "sub").mkdir(parents=True)
    (st / "index.html").write_text(
        '<html><head><script defer src="/static/vendor/x.min.js"></script>'
        '<script type="module" src="/static/app.js"></script></head><body></body></html>',
        encoding="utf-8")
    (st / "sub" / "hondo.js").write_text("const HONDO = 1;\n", encoding="utf-8")
    (st / "medio.js").write_text("import './sub/hondo.js';\nconst MEDIO = 2;\n", encoding="utf-8")
    (st / "app.js").write_text("import './medio.js';\nconst ENTRADA = 3;\n", encoding="utf-8")
    return tmp


def test_descubre_n_modulos_siguiendo_los_imports(tmp_path: Path) -> None:
    repo = _arbol_de_modulos(tmp_path)
    r = _corre(repo)
    assert r.returncode == 0, r.stderr
    lineas = r.stdout.split()
    # dependencias ANTES que quien las importa: la concatenacion tiene que poder ejecutarse
    assert lineas == ["static/sub/hondo.js", "static/medio.js", "static/app.js"], lineas
    # y `vendor/` no es el panel: es tercero y se excluye por su prefijo, no por su nombre
    assert not any("vendor" in x for x in lineas)


def test_la_concatenacion_de_n_modulos_no_deja_imports_sueltos(tmp_path: Path) -> None:
    repo = _arbol_de_modulos(tmp_path)
    r = _corre(repo, "--cat")
    assert r.returncode == 0, r.stderr
    assert "import" not in r.stdout, "un import sin resolver convierte la concatenacion en un error de sintaxis"
    for marca in ("HONDO", "MEDIO", "ENTRADA"):
        assert marca in r.stdout


def test_un_import_CON_NOMBRES_no_se_concatena_a_la_brava(tmp_path: Path) -> None:
    """EL LIMITE, DECLARADO. Concatenar solo es fiel con imports de EFECTO.

    Con un import que ATA nombres, la concatenacion seria otra cosa; entonces esto se niega
    con rc=2 en vez de devolver algo que parece el panel y no lo es.
    """
    repo = _arbol_de_modulos(tmp_path)
    (repo / "static" / "app.js").write_text(
        "import { MEDIO } from './medio.js';\nconst ENTRADA = MEDIO;\n", encoding="utf-8")
    r = _corre(repo, "--cat")
    assert r.returncode == 2
    assert "import CON NOMBRES" in r.stderr


def test_sin_script_de_panel_no_se_inventa_una_lista(tmp_path: Path) -> None:
    """CONTROL EN LA OTRA DIRECCION: sin sujeto, NO MEDIDO y no una lista vacia."""
    st = tmp_path / "static"
    st.mkdir(parents=True)
    (st / "index.html").write_text(
        '<html><head><script defer src="/static/vendor/solo-tercero.js"></script>'
        '</head><body></body></html>', encoding="utf-8")
    r = _corre(tmp_path)
    assert r.returncode == 2
    assert "no hay panel que medir" in r.stderr


def test_un_modulo_declarado_que_no_existe_revienta(tmp_path: Path) -> None:
    repo = _arbol_de_modulos(tmp_path)
    (repo / "static" / "medio.js").write_text("import './no-esta.js';\n", encoding="utf-8")
    r = _corre(repo)
    assert r.returncode == 2
    assert "no existe" in r.stderr


def test_un_import_que_sale_de_static_revienta(tmp_path: Path) -> None:
    """El panel vive bajo static/. Un import que se escapa no es el panel."""
    repo = _arbol_de_modulos(tmp_path)
    (repo / "static" / "medio.js").write_text("import '../fuera.js';\n", encoding="utf-8")
    (repo / "fuera.js").write_text("const X = 1;\n", encoding="utf-8")
    r = _corre(repo)
    assert r.returncode == 2
    assert "FUERA de static" in r.stderr
