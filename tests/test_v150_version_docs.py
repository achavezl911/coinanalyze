"""v1.5.0 — la versión declarada y lo que la documentación promete."""

from __future__ import annotations

import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
README = (RAIZ / "README.md").read_text(encoding="utf-8")
CHANGELOG = (RAIZ / "docs" / "CHANGES_v1.5.0.md").read_text(encoding="utf-8")

VERSION = "1.5.0"


def test_la_version_es_la_real_en_los_tres_sitios() -> None:
    assert PYPROJECT["project"]["version"] == VERSION
    assert README.startswith(f"# Coinalyze Operator Dashboard v{VERSION}")
    assert f"## v{VERSION}" in README


def test_no_queda_ninguna_referencia_a_la_version_anterior_en_el_codigo() -> None:
    """El User-Agent tambien identifica la version: si no se actualiza, miente."""
    for ruta in (RAIZ / "app").glob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        assert "1.4.9" not in texto, ruta.name


def test_el_changelog_documenta_lo_que_pide_el_prompt() -> None:
    for tema in (
        "navegación",  # nueva navegación
        "perfil",      # perfiles
        "setup",       # selector dirección/setup
        "Calidad",     # estados de calidad
        "5 bps",       # fin del umbral universal
    ):
        assert tema.lower() in CHANGELOG.lower(), tema


def test_se_declaran_los_limites_exactos_del_recuperador_de_huecos() -> None:
    for documento in (README, CHANGELOG):
        assert "recover_gaps.py" in documento
        assert "unrecoverable" in documento
        assert "order book" in documento.lower()


def test_se_declaran_las_limitaciones_conocidas() -> None:
    assert "Limitaciones conocidas" in README
    # Los umbrales por convencion se marcan como tales, no como resultados medidos.
    assert "convenciones declaradas" in README or "convención declarada" in README
    assert "backtestead" in CHANGELOG


def test_el_recuperador_de_huecos_existe_sin_inventar_endpoints() -> None:
    fuentes = "\n".join(
        ruta.read_text(encoding="utf-8") for ruta in (RAIZ / "app").glob("*.py")
    )
    assert "data_gaps" in fuentes
    assert (RAIZ / "scripts" / "recover_gaps.py").is_file()
    assert "/api/data-quality/gaps" not in fuentes
