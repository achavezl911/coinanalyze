"""Contratos de presentacion introducidos en v1.4.5.

Cubren lo que la vista promete al operador: ejes en dinero compacto, perfil de liquidaciones
etiquetado como densidad ya ejecutada, analizadores en un solo panel con precarga, sparklines
alimentadas del tramo lento y ausencia de whale contada, no dibujada como cero.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")


def slice_js(name, next_name):
    start = JS.index(f"function {name}")
    return JS[start : JS.index(f"function {next_name}", start)]


def test_money_axes_replace_raw_floats_on_every_usd_chart():
    # El eje por defecto imprimia 418951166.51; las cuatro series en USD llevan formateador.
    assert "function axisMoney" in JS
    init = slice_js("initCharts", "renderTabs")
    for chart in ("cvd-chart", "oi-chart", "whale-chart"):
        assert f"newChart('{chart}', true, axisMoney)" in init
    assert "newChart('daily-chart', false, axisMoney)" in init
    assert "priceFormatter" in slice_js("chartOptions", "newChart")


def test_price_axis_keeps_price_formatting_when_switching_mode():
    active = slice_js("renderActivePriceChart", "renderPriceChart")
    assert "priceFormatter: axisPrice" in active


def test_liquidation_profile_is_dom_safe_and_declares_realized_density():
    assert 'id="liq-levels-body" class="liq-profile"' in HTML
    assert "Densidad ya ejecutada" in HTML
    profile = slice_js("renderLiquidationLevels", "liqProfileMark")
    assert "body.replaceChildren()" in profile
    assert ".innerHTML" not in profile
    # La lectura es historica: no debe venderse como prediccion de liquidaciones futuras.
    assert "Densidad ya ejecutada" in profile
    assert ".liq-profile" in CSS


def test_liquidation_profile_orders_by_price_and_marks_the_current_one():
    profile = slice_js("renderLiquidationLevels", "liqProfileMark")
    assert "sort((a, b) => b.price - a.price)" in profile
    assert "liqProfileMark(current)" in profile
    assert "precio actual" in slice_js("liqProfileMark", "renderBarrierZone")


def test_level_analyzers_share_one_panel_with_tabs():
    for pane in ("analyzer-zone", "analyzer-range", "analyzer-breakout"):
        assert f'id="{pane}"' in HTML
    for tab in ("analyzer-tab-zone", "analyzer-tab-range", "analyzer-tab-breakout"):
        assert f'id="{tab}"' in HTML
    assert ".analyzer-panel { grid-column: span 12; }" in CSS
    assert ".analyzer-pane[hidden] { display: none; }" in CSS
    # Los tres formularios siguen existiendo: se reagruparon, no se recortaron.
    for form in ("zone-form", "range-form", "breakout-form"):
        assert f'id="{form}"' in HTML


def test_analyzer_prefill_never_overwrites_a_typed_value():
    preset = slice_js("presetInput", "presetAnalyzer")
    assert "input.dataset.auto !== '1'" in preset
    assert "input.dataset.auto = '1'" in preset
    init = slice_js("initAnalyzer", "releaseAnalyzerInputs")
    assert "delete input.dataset.auto" in init


def test_analyzer_prefill_is_released_when_the_symbol_changes():
    select = JS[JS.index("async function selectSymbol") : JS.index("function initSectionNav")]
    assert "releaseAnalyzerInputs()" in select


def test_summary_sparklines_come_from_the_slow_refresh_tier():
    refresh = JS[JS.index("async function refreshOverview") : JS.index("async function loadSection")]
    context = refresh[refresh.index("contextRequest = contextExpired") : refresh.index("const [dashboard")]
    # El rollup diario cambia una vez por sesion: no puede colarse al ciclo de 15 s.
    assert "/api/daily?symbol=${q}&days=60" in context
    summary = slice_js("renderSummary", "rowDL")
    assert summary.count("card(") == 4
    for field in ("price_close", "cumulative_spot", "oi_close", "fr_avg"):
        assert f"dailySeries('{field}')" in summary


def test_sparkline_needs_real_points_and_is_decorative_only():
    spark = slice_js("sparkline", "card")
    assert "points.length < 3" in spark
    assert "aria-hidden" in spark


def test_absent_whale_activity_is_counted_not_drawn_as_zero():
    whale = slice_js("renderWhaleActivity", "setConnection")
    assert "bars.filter(bar => bar.value !== 0)" in whale
    assert "ventanas de 15 min" in whale
    assert 'id="whale-note"' in HTML


def test_delta_profile_panel_is_svg_and_declares_its_limits():
    assert 'id="profile-chart"' in HTML
    assert 'id="profile-note"' in HTML
    assert ".profile-panel { grid-column: span 12; }" in CSS
    render = slice_js("renderDeltaProfile", "loadDeltaProfile")
    assert ".innerHTML" not in render
    assert "createElementNS" in slice_js("svgEl", "profileRowY")
    # POC y area de valor son las dos referencias estandar; sin ellas el perfil es decorativo.
    assert "value_area_low" in render
    assert "result.poc" in render
    assert "result.warning" in render


def test_delta_profile_offers_the_windows_that_have_coverage():
    # 4h llega a ~300 dias; 5min solo a ~9. Ofrecer 300 d en 5min prometeria lo que no hay.
    for days in ("30", "90", "300"):
        assert f'data-interval="4hour" data-days="{days}"' in HTML
    assert 'data-interval="5min" data-days="9"' in HTML
    loader = slice_js("loadDeltaProfile", "initDeltaProfile")
    assert "/api/delta-profile?" in loader
    assert "state.profileWindow.interval" in loader
    assert "symbol !== state.symbol" in loader


def test_panels_size_to_their_content():
    # Estirados a la altura del vecino mas alto encerraban franjas vacias dentro del borde.
    grids = CSS[CSS.index(".flow-grid,") : CSS.index(".chart-mode {")]
    assert "align-items: start" in grids
