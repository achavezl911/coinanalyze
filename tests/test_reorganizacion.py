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

# LA LISTA SE DERIVA DEL DOCUMENTO, no se escribe a mano. Cuando la campaña «Mesa de posicion»
# añadio `coste` y bajo `liquidez` al final, estos tests enrojecieron por tener la lista vieja
# clavada; el arreglo no es cambiar ocho nombres por nueve, es que no haya nombres que cambiar.
# Lo que se vigila -que la navegacion apunte a secciones REALES y en el MISMO orden- no se
# afloja: sigue siendo una igualdad de listas, y sigue enrojeciendo si alguien añade un enlace
# a una seccion que no existe o cambia el orden sin querer.
SECCIONES = re.findall(r'<section id="([a-z]+)" class="market-section"', HTML)
ORDEN_NAV = [a for a, _ in re.findall(r'<a href="#([a-z]+)"[^>]*data-tab="([a-z]+)"', HTML)]


def test_existen_las_secciones_declaradas() -> None:
    """Nueve desde la campaña «Mesa de posicion»: entro `coste` -el gasto va antes que la
    estructura- y `liquidez` bajo a una lista aparte, rotulada «para ejecutar, no para decidir»."""
    assert len(SECCIONES) == 9, SECCIONES
    assert "coste" in SECCIONES
    assert HTML.count('class="market-section"') == len(SECCIONES)
    assert len(set(SECCIONES)) == len(SECCIONES), "hay ids repetidos"


def test_la_navegacion_apunta_a_secciones_REALES_y_no_sobra_ninguna() -> None:
    """El brazo que importa, y no se afloja: cada enlace tiene que llevar a una seccion que
    existe, y toda seccion que existe tiene que tener enlace. Un enlace a una seccion borrada
    deja al operador en blanco sin que nada falle."""
    enlaces = re.findall(r'<a href="#([a-z]+)"[^>]*data-tab="([a-z]+)"', HTML)
    assert all(a == b for a, b in enlaces), "href y data-tab discrepan"
    assert sorted(ORDEN_NAV) == sorted(SECCIONES), (
        f"la navegacion y las secciones no coinciden: solo en nav {set(ORDEN_NAV) - set(SECCIONES)}, "
        f"solo en documento {set(SECCIONES) - set(ORDEN_NAV)}"
    )


def test_el_coste_va_antes_que_la_estructura() -> None:
    """No es cosmetica: es la tesis de la campaña. Para dias-a-semanas en perpetuos el funding
    es el gasto principal, y se paga tres veces al dia se mire o no. Si vuelve a quedar detras,
    el dashboard ha vuelto a tener la señal como eje."""
    assert ORDEN_NAV.index("coste") < ORDEN_NAV.index("estructura")
    assert ORDEN_NAV.index("coste") == 1, f"el coste deberia ser lo segundo: {ORDEN_NAV}"


def test_lo_de_menos_de_una_hora_no_compite() -> None:
    """`liquidez` -libro, absorcion de 3 min, coste de ejecucion- sigue estando y sigue siendo
    alcanzable, pero fuera de la lista principal y rotulada por su funcion."""
    assert "liquidez" in SECCIONES, "no se borra: deja de competir"
    assert "Para ejecutar, no para decidir" in HTML
    principal = HTML.split("nav-title-secundario")[0]
    assert 'data-tab="liquidez"' not in principal, "liquidez sigue en la lista principal"


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
