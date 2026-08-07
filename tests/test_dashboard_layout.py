import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")


class DashboardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.section_ids = []
        self.section_links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.append(element_id)
        classes = values.get("class", "").split()
        if tag == "section" and element_id and "market-section" in classes:
            self.section_ids.append(element_id)
        if tag == "a" and values.get("href", "").startswith("#"):
            self.section_links.append(values["href"][1:])


def parsed_dashboard():
    parser = DashboardParser()
    parser.feed(HTML)
    return parser


def function_source(name, next_name):
    start = JS.index(f"function {name}")
    end = JS.index(f"function {next_name}", start)
    return JS[start:end]


def test_dashboard_has_unique_ids_and_market_reading_order():
    parsed = parsed_dashboard()
    # Orden de lectura de la reorganizacion: primero la decision, al final la validacion.
    expected = [
        "mesa",
        "estructura",
        "flujo",
        "derivados",
        "liquidez",
        "contexto",
        "calidad",
        "replay",
    ]
    assert parsed.section_ids == expected
    assert parsed.section_links == expected
    assert len(parsed.ids) == len(set(parsed.ids))


def test_javascript_only_references_existing_literal_ids():
    referenced_ids = set(re.findall(r"\$\('([^']+)'\)", JS))
    missing = referenced_ids - set(parsed_dashboard().ids)
    assert not missing


def test_summary_is_limited_to_four_supporting_indicators():
    summary = function_source("renderSummary", "rowDL")
    assert summary.count("card(") == 4


def test_decision_board_is_dom_safe_and_covers_three_horizons():
    assert 'id="decision-horizons"' in HTML
    decision = function_source("renderDecisionBoard", "refreshOverview")
    assert decision.count("horizonCard({") == 3
    assert ".innerHTML" not in decision
    assert "Confirmar" in JS
    assert "Salir si" in JS


def test_quick_flow_read_is_visible_on_entry_and_dom_safe():
    assert 'id="quick-read-body"' in HTML
    quick = function_source("renderQuickRead", "renderDaily")
    assert "body.replaceChildren()" in quick
    assert ".innerHTML" not in quick
    assert "Qué ocurre · qué significa · qué falta" in HTML
    refresh = JS[JS.index("async function refreshOverview") : JS.index("async function loadSection")]
    assert "renderQuickRead(state.daily)" in refresh


def test_cvd_90_session_read_has_a_full_width_safe_panel():
    assert 'id="market-reading"' in HTML
    assert ".reading-panel { grid-column: span 12; }" in CSS
    reading = function_source("renderMarketReading", "withScale")
    assert "body.replaceChildren()" in reading
    assert ".innerHTML" not in reading
    assert "dashboard.cvd_swing" in JS


def test_external_macro_is_separate_from_internal_percentiles_and_dom_safe():
    assert 'id="external-macro-body"' in HTML
    assert "Régimen macro externo" in HTML
    assert "Percentiles internos" in HTML
    assert ".external-macro-panel { grid-column: span 12; }" in CSS
    render = function_source("renderExternalMacro", "renderMacro")
    assert "body.replaceChildren()" in render
    assert ".innerHTML" not in render
    refresh = JS[JS.index("async function refreshOverview") : JS.index("async function loadSection")]
    assert "/api/external-macro?symbol=${q}" in refresh


def test_price_barriers_have_a_full_width_safe_panel():
    assert 'id="barrier-map"' in HTML
    assert ".barrier-panel { grid-column: span 12; }" in CSS
    barriers = function_source("renderBarriers", "horizonCard")
    assert "body.replaceChildren()" in barriers
    assert ".innerHTML" not in barriers
    assert "dashboard.barriers" in JS


def test_overview_is_light_and_stale_responses_are_rejected():
    refresh = JS[JS.index("async function refreshOverview") : JS.index("async function loadSection")]
    for endpoint in ("dashboard/state", "ohlcv", "data-confidence", "healthz"):
        assert endpoint in refresh
    for endpoint in ("passive-flow", "trend-matrix", "swing-score", "structure-detail"):
        if endpoint != "passive-flow":
            assert endpoint in refresh
    assert "scalp/alerts" not in refresh
    assert "scalp/signals" not in JS
    assert "requestId !== state.refreshSeq" in refresh


def test_sections_are_hidden_and_loaded_on_demand():
    assert ".market-section[hidden] { display: none; }" in CSS
    navigation = JS[JS.index("function initSectionNav") : JS.index("async function boot")]
    assert "section.hidden = section.id !== id" in navigation
    loader = JS[JS.index("async function loadSection") : JS.index("function connectStream")]
    for section in ("flujo", "liquidez", "estructura", "contexto", "derivados", "calidad", "replay"):
        assert f"id === '{section}'" in loader


def test_funding_is_rendered_in_coinalyze_percentage_points():
    rate = function_source("rate", "dateTime")
    assert "n.toFixed(4)" in rate
    assert "n * 100" not in rate


def test_swing_rendering_does_not_inject_api_html():
    swing = function_source("renderSwing", "renderDailyBars")
    assert ".innerHTML" not in swing
    assert "textContent" in swing


def test_dashboard_removes_fixed_desktop_width_and_has_mobile_layouts():
    assert "min-width: 1180px" not in CSS
    assert "@media (max-width: 900px)" in CSS
    assert "@media (max-width: 700px)" in CSS
    assert "@media (max-width: 430px)" in CSS


def test_delta_matrix_exposes_window_coverage_and_oi_resolution():
    delta = function_source("renderDeltaMatrix", "renderAbsorption")
    assert "<th>Cobertura</th>" in HTML
    # v1.5.0: la matriz prioriza cada pata y su delta/volumen; la cabecera dejo de ser
    # "Spot | Futuros | Diferencia" porque la diferencia ya no encabeza la lectura.
    assert "<th>Horizonte</th><th>Cobertura</th><th>Δ spot</th><th>Δ futuros</th>" in HTML
    assert "<th>Δ/vol spot</th><th>Δ/vol fut</th><th>Cuadrante</th>" in HTML
    assert "ΔOI (5m+)" in HTML
    assert "coverage_status" in delta
    assert "Cobertura 8h:" in JS
    assert ".summary-card .value { overflow-wrap: anywhere" in CSS


def test_el_diferencial_spot_fut_es_columna_de_auditoria_no_direccional():
    """No encabeza la tabla, no lleva color de signo y viene oculta por defecto."""
    delta = function_source("renderDeltaMatrix", "renderAbsorption")
    # La columna existe pero detras de un interruptor explicito.
    assert 'id="show-diff"' in HTML
    assert '<th class="diff-col" hidden>Diferencia</th>' in HTML
    # Se pinta en neutro: nunca recibe signClass, que es lo que la haria direccional.
    assert "diffCell.className = 'neutral diff-col'" in delta
    assert "signClass(r.diff)" not in delta
    # Y se declara que compara mercados de escala distinta.
    assert "escalas distintas" in HTML or "escala distinta" in HTML
