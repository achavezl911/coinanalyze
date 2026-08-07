"""Reorganización del dashboard en 8 pestañas + hipótesis manual.

Los paneles se movieron VERBATIM entre secciones; estas pruebas fijan que la navegación
existe, que ningún panel se perdió por el camino y que la hipótesis clasifica evidencia sin
emitir recomendaciones.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.scalp_logic import HYPOTHESES, hypothesis_evidence
from app.setups import split_hypothesis

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")

SECCIONES = ["mesa", "estructura", "flujo", "derivados", "liquidez", "contexto", "calidad", "replay"]


def test_existen_las_ocho_pestanas() -> None:
    for ident in SECCIONES:
        assert f'<section id="{ident}" class="market-section"' in HTML, ident
    assert HTML.count('class="market-section"') == len(SECCIONES)


def test_la_navegacion_apunta_a_las_ocho() -> None:
    enlaces = re.findall(r'<a href="#([a-z]+)"[^>]*data-tab="([a-z]+)"', HTML)
    assert [a for a, _ in enlaces] == SECCIONES
    assert all(a == b for a, b in enlaces)


def test_solo_la_mesa_arranca_visible() -> None:
    for ident in SECCIONES:
        bloque = HTML.split(f'<section id="{ident}" class="market-section"')[1][:40]
        oculto = "hidden" in bloque
        assert oculto is (ident != "mesa"), f"{ident} deberia {'ocultarse' if ident != 'mesa' else 'verse'}"


def test_la_barra_global_es_permanente() -> None:
    """Vive en <header class="topbar">, fuera de las secciones: se ve en las 8."""
    topbar = HTML.split('<div class="app-shell">')[0]
    # v1.5.0: `hypothesis-select` se dividio en `direction-select` + `setup-select`.
    for ident in ("symbol-tabs", "profile-tabs", "direction-select", "setup-select",
                  "live-price", "data-confidence", "live-sources", "live-latency",
                  "live-error"):
        assert f'id="{ident}"' in topbar, ident
    assert 'id="hypothesis-select"' not in HTML, "el selector unico ya no debe existir"


def test_ningun_panel_se_perdio_en_la_mudanza() -> None:
    """Los paneles que existían antes siguen existiendo, aunque en otra pestaña."""
    for panel in ("delta-matrix", "orderbook-body", "structure-body", "trend-body",
                  "liq-matrix", "basis-details", "health-services", "price-chart",
                  "oi-chart", "cvd-chart", "whale-chart", "summary", "barrier-map"):
        assert f'id="{panel}"' in HTML, f"panel perdido: {panel}"


def test_cada_pestana_nueva_tiene_su_cargador() -> None:
    for ident in ("derivados", "calidad", "replay"):
        assert f"id === '{ident}'" in JS, ident
    # La mesa se sirve del ciclo de contexto, no de loadSection.
    assert "if (id === 'mesa') return;" in JS


def test_el_oi_no_se_borra_al_pintar_flujo() -> None:
    """El panel de OI se mudó a Derivados; Flujo ya no debe vaciar su serie."""
    assert "if (oi !== null) renderOiChart(oi);" in JS


# ---------------- hipótesis manual ----------------
def perfil(**capas: str) -> dict:
    return {
        "profile": "intradia",
        "coverage_pct": 100.0,
        "layers": {
            nombre: {
                "bias": bias,
                "measurable_timeframes": 2,
                "expected_timeframes": 2,
                "effective_weight": 30,
            }
            for nombre, bias in capas.items()
        },
        "contradictions": [],
    }


SCALP_OK = {
    "absorption": "Sin señal",
    "basis_status": "VALID",
    "book_status": "ok",
    "evidence_coverage_pct": 100.0,
    "spread_bps": 1.0,
    "missing_components": [],
}


def test_long_con_todo_alcista_va_a_favor() -> None:
    out = hypothesis_evidence("long", perfil(contexto="alcista", gatillo="alcista"), SCALP_OK)
    assert out["counts"]["a_favor"] == 2
    assert out["counts"]["en_contra"] == 0


def test_la_misma_evidencia_se_invierte_para_short() -> None:
    """La clasificación depende de la hipótesis del operador, no de un sesgo del sistema."""
    p = perfil(contexto="alcista", gatillo="alcista")
    assert hypothesis_evidence("short", p, SCALP_OK)["counts"]["en_contra"] == 2


def test_una_hipotesis_de_espera_no_reparte_direccion() -> None:
    out = hypothesis_evidence("esperando_ruptura", perfil(contexto="alcista", gatillo="bajista"), SCALP_OK)
    assert out["counts"]["a_favor"] == 0
    assert out["counts"]["en_contra"] == 0
    assert out["counts"]["pendiente"] == 2


def test_lo_que_no_se_puede_medir_no_vota() -> None:
    scalp = {**SCALP_OK, "absorption": "No evaluable", "basis_status": "STALE",
             "book_status": "stale", "missing_components": ["vwap"]}
    out = hypothesis_evidence("long", perfil(contexto="sin_datos"), scalp)
    assert out["counts"]["a_favor"] == 0
    señales = {e["signal"] for e in out["evidence"]["no_evaluable"]}
    assert {"Capa contexto", "Absorción 3m", "Basis", "Order book", "Componente vwap"} <= señales


def test_la_absorcion_de_ventas_favorece_al_comprador() -> None:
    scalp = {**SCALP_OK, "absorption": "Absorción de ventas"}
    assert any(
        e["signal"] == "Absorción 3m"
        for e in hypothesis_evidence("long", perfil(contexto="alcista"), scalp)["evidence"]["a_favor"]
    )
    assert any(
        e["signal"] == "Absorción 3m"
        for e in hypothesis_evidence("short", perfil(contexto="bajista"), scalp)["evidence"]["en_contra"]
    )


def test_las_contradicciones_se_separan_en_invalidacion_y_espera() -> None:
    p = perfil(contexto="alcista")
    p["contradictions"] = [
        {"detalle": "A", "motivo": "m1", "efecto": "invalida"},
        {"detalle": "B", "motivo": "m2", "efecto": "esperar"},
    ]
    out = hypothesis_evidence("long", p, SCALP_OK)
    assert len(out["invalidations"]) == 1
    assert len(out["pending_conditions"]) == 1


def test_no_emite_recomendaciones() -> None:
    out = hypothesis_evidence("long", perfil(contexto="alcista"), SCALP_OK)
    assert "no ejecuta ninguna operacion" in out["note"]
    texto = str(out).lower()
    for prohibido in ("compra ahora", "vende ahora", "entra en", "recomendamos"):
        assert prohibido not in texto


def test_hipotesis_desconocida_es_error() -> None:
    with pytest.raises(ValueError, match="hipotesis desconocida"):
        hypothesis_evidence("moon", perfil(contexto="alcista"), SCALP_OK)


def test_las_siete_hipotesis_siguen_siendo_expresables() -> None:
    """v1.5.0 separa direccion y setup; las siete hipotesis viejas siguen representables.

    El selector unico desaparecio del HTML, pero ningun valor guardado queda huerfano: cada
    uno se traduce a un par (direccion, setup) que el operador tambien puede componer a mano.
    """
    assert set(HYPOTHESES) == {
        "long", "short", "neutral", "esperando_ruptura", "esperando_rechazo",
        "esperando_reversion", "esperando_continuacion",
    }
    opciones = set(re.findall(r'<option value="([a-z_]+)"', HTML))
    assert {"long", "short", "neutral"} <= opciones, "faltan direcciones"
    assert {"ninguno", "ruptura", "rechazo", "reversion", "continuacion"} <= opciones
    for legacy in HYPOTHESES:
        direccion, setup = split_hypothesis(legacy)
        assert direccion in opciones and setup in opciones, legacy


def test_cada_seccion_tiene_su_rejilla_de_12_columnas() -> None:
    """La reorganización dejó los <article> como hijos directos de <section>.

    Sin el contenedor `.context-grid` cada panel ocupaba una tira estrecha: el CSS del
    proyecto reparte el ancho con `grid-column: span N` sobre esa rejilla de 12 columnas.
    """
    for ident in SECCIONES:
        bloque = HTML.split(f'<section id="{ident}" class="market-section"')[1].split("</section>")[0]
        assert 'class="context-grid"' in bloque, f"{ident} sin rejilla"


def test_los_paneles_nuevos_declaran_ancho() -> None:
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    for clase in ("funding-panel", "positioning-panel", "execution-panel", "impact-panel",
                  "overview-price", "levels-panel"):
        assert f'class="panel {clase}"' in HTML or f"{clase}" in HTML, clase
        assert re.search(rf"\.{clase} {{[^}}]*grid-column: span \d+", css), f"{clase} sin span"


def test_las_listas_usan_una_clase_que_existe_en_el_css() -> None:
    """`level-list` no existía: etiqueta y valor salían apilados y sin separador."""
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert 'class="level-list"' not in HTML
    for clase in re.findall(r'<dl[^>]*class="([^"]+)"', HTML):
        principal = clase.split()[0]
        assert f".{principal}" in css, f"clase de <dl> sin estilo: {principal}"
