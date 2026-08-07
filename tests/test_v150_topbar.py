"""v1.5.0 — la barra superior reparte por AREAS, no por columnas implícitas.

La medición real (desbordamiento y solapamientos a 1920/1440/1366/1100/900/700/430 px) se
hace en Chrome headless con `scratchpad/audit.ps1`, que mide dentro de un iframe del ancho
exacto. Aquí se fija el contrato que hace esa medición posible: que cada control tenga un
área declarada en TODOS los puntos de ruptura, para que ninguno caiga en una columna
implícita que el navegador dimensione por su cuenta.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CSS = (RAIZ / "static" / "app.css").read_text(encoding="utf-8")
HTML = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")

AREAS = ("brand", "symbol", "profile", "direction", "setup", "live", "actions")
ANCHOS = (1380, 1180, 900, 700, 430)


def bloques_topbar() -> list[str]:
    """Cada declaración de `grid-template-areas` que afecta a `.topbar`."""
    return re.findall(
        r"\.topbar\s*\{[^}]*?grid-template-areas:\s*((?:\s*\"[^\"]*\")+)\s*;", CSS
    )


def test_cada_control_declara_su_area_en_el_html() -> None:
    for area in AREAS:
        assert f"tb-{area}" in HTML, area
        assert f".tb-{area} {{ grid-area: {area}; }}" in CSS, area


def test_todas_las_areas_aparecen_en_cada_punto_de_ruptura() -> None:
    """Un área que falta en una rejilla deja ese control en una columna implícita."""
    bloques = bloques_topbar()
    assert bloques, "la barra no usa grid-template-areas"
    for bloque in bloques:
        nombres = set(re.findall(r"[a-z]+", bloque))
        faltan = set(AREAS) - nombres
        assert not faltan, f"faltan {sorted(faltan)} en la rejilla: {bloque.strip()}"


def test_las_rejillas_son_rectangulares() -> None:
    """Filas de distinta longitud son `grid-template-areas` inválido y el navegador la ignora."""
    for bloque in bloques_topbar():
        filas = [f.split() for f in re.findall(r'"([^"]*)"', bloque)]
        anchos = {len(f) for f in filas}
        assert len(anchos) == 1, f"filas desiguales: {filas}"


def test_existen_los_siete_puntos_de_ruptura_medidos() -> None:
    for ancho in ANCHOS:
        assert f"@media (max-width: {ancho}px)" in CSS, ancho


def test_ningun_hijo_de_la_barra_puede_forzar_scroll_horizontal() -> None:
    assert ".topbar > * { min-width: 0; }" in CSS
    # Las pastillas se reparten solas: un número fijo de columnas desbordaría al estrecharse.
    assert "repeat(auto-fit, minmax(104px, 1fr))" in CSS


def test_el_selector_de_setup_esta_en_la_barra_permanente() -> None:
    """Si viviera dentro de una sección, no se vería en las otras siete pestañas."""
    topbar = HTML.split('<div class="app-shell">')[0]
    assert 'id="setup-select"' in topbar
    assert 'id="direction-select"' in topbar
