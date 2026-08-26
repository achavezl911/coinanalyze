"""El CVD por sesión describe agresión ejecutada, no inventario institucional.

cvd_fut_usd sale del perp de Binance (`.A`) y cvd_spot_usd de Binance+Bybit. El perp mueve
mucho más volumen, así que el diferencial no es una señal comparable. Estos tests blindan
que la interfaz publique los signos factuales de ambas patas, muestre la respuesta del
precio y no vuelva a llamar "acumulación" a una única sesión de compras agresivas.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.api import daily_data
from app.daily_agg import SESSION_MIN_COVERAGE_RATIO, SESSION_QUERY
from app.scalp_logic import (
    _complete_tail_values,
    _conditional_outcome,
    _contiguous_measured_suffix,
    _forward_returns,
    _slope_pct,
    divergence_scan,
)

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def test_panel_uses_factual_flow_names_instead_of_wyckoff_labels() -> None:
    assert "Acumulación / distribución" not in HTML
    assert "Verde = spot compra más que futuros (acumulación)" not in JS
    daily_bars = JS[JS.index("function flowQuadrant"):JS.index("function renderDivergences")]
    assert "Acumulación" not in daily_bars
    assert "Distribución" not in daily_bars
    assert "function flowQuadrant" in JS
    assert "spot > 0 && futures > 0" in JS
    assert "spot < 0 && futures < 0" in JS
    assert "Ambos compraron" in JS
    assert "Ambos vendieron" in JS


def test_macro_structure_and_swing_use_spot_not_the_scale_biased_diff() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    market = source[source.index("async def market_structure"):source.index("# ---------------- alertas HTF")]
    trend = source[source.index("async def trend_matrix"):source.index("async def swing_score")]
    # F3 keeps the macro vote on spot CVD but exact session windows fail closed on gaps.
    assert '_complete_tail_values(daily, "cvd_spot_usd", 7)' in market
    assert '_complete_tail_values(daily, "price_close", 8)' in market
    assert '_contiguous_measured_suffix(daily, "price_close")' in market
    assert "cvd_diff_usd" not in market
    assert '_complete_tail_values(daily, "cvd_spot_usd", n_back)' in trend
    assert '_contiguous_measured_suffix(ds, "price_close")' in trend
    assert 'sum(as_float(r["cvd_spot_usd"]) or 0' not in trend
    assert '"CVD spot de fondo"' in trend


def test_daily_table_replaces_scale_biased_diffs_with_price_response() -> None:
    assert "<th>Respuesta del precio</th>" in HTML
    assert "<th>Dif. (mezcla)</th>" not in HTML
    assert "<th>Dif. 2 venues</th>" not in HTML
    render = JS[JS.index("function renderDaily(result)"):JS.index("function renderHealth")]
    assert "sessionResponse(row)" in render
    assert "cvd_diff_2v_usd" not in render


def test_session_query_measures_futures_on_the_same_venues_as_spot() -> None:
    assert "FROM futures_trades_agg" in SESSION_QUERY
    assert "exchange='combined'" in SESSION_QUERY
    assert "spot.minutes AS spot_2v_minutes" in SESSION_QUERY
    # F3: coverage is proportional to the real DST-aware session duration.
    assert 0 < SESSION_MIN_COVERAGE_RATIO <= 1
    # No rows is unknown, not a measured neutral session.
    assert "COALESCE(SUM(buy_vol_usd - sell_vol_usd),0)" not in SESSION_QUERY
    assert "COALESCE(SUM(inst_buy_usd - inst_sell_usd),0)" not in SESSION_QUERY


def test_partial_sessions_preserve_only_previously_verified_two_venue_evidence() -> None:
    """Retention loss may preserve PR20-verified evidence, never legacy/unverified evidence."""
    source = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert (
        "cvd_fut_2v_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)"
        in source
    )
    assert "THEN COALESCE(EXCLUDED.cvd_fut_2v_usd,daily_session_agg.cvd_fut_2v_usd)" in source
    assert "ELSE EXCLUDED.cvd_fut_2v_usd END" in source
    assert "complete_futures_2v = _coverage_complete(futures_2v_minutes, expected_minutes)" in source


def test_minute_retention_covers_a_full_nyse_session() -> None:
    from app.config import Settings

    settings = Settings()
    assert settings.SCALP_MINUTE_RETENTION_HOURS >= 26, "una sesion son 24h y el job corre cada hora"
    collector = (ROOT / "app" / "scalp_collector.py").read_text(encoding="utf-8")
    assert "DELETE FROM futures_trades_agg" in collector
    assert "SETTINGS.SCALP_MINUTE_RETENTION_HOURS" in collector


def test_verdicts_are_persisted_so_the_model_can_be_audited_later() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    source = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS daily_verdict" in schema
    assert "async def persist_verdicts" in source
    assert "verdicts = await persist_verdicts" in source


@pytest.mark.parametrize(
    ("closes", "horizon", "expected"),
    [
        ([100.0, 110.0, 121.0], 1, [10.0, 10.0, None]),
        ([100.0, 110.0, 121.0], 2, [21.0, None, None]),
    ],
)
def test_forward_returns(closes, horizon, expected) -> None:
    got = _forward_returns(closes, horizon)
    assert len(got) == len(expected)
    for a, b in zip(got, expected, strict=True):
        assert a is None if b is None else a == pytest.approx(b)


def test_conditional_outcome_needs_a_real_sample() -> None:
    assert _conditional_outcome([1.0] * 5, [100.0] * 5, 1.0) == {}
    series = [float(i) for i in range(60)]
    closes = [100.0 + i for i in range(60)]
    out = _conditional_outcome(series, closes, 59.0)
    assert set(out) == {"h7", "h14"}
    for block in out.values():
        assert block["n"] >= 0
        if not block.get("insufficient_sample"):
            assert "median_pct" in block and "positive_pct" in block


def test_slope_sign_detects_direction() -> None:
    assert _slope_pct([1.0, 2.0, 3.0, 4.0, 5.0]) > 0
    assert _slope_pct([5.0, 4.0, 3.0, 2.0, 1.0]) < 0
    assert _slope_pct([1.0, 2.0]) is None


class _DivergenceConnection:
    """Solo sesiones: la consulta intradia (spot_trades_agg) devuelve vacio."""

    def __init__(self, rows):
        self._rows = rows

    async def fetch(self, query, *_args):
        return [] if "spot_trades_agg" in query else self._rows


@pytest.mark.asyncio
async def test_divergence_flags_price_up_with_spot_cvd_down() -> None:
    # 60 sesiones: precio subiendo, CVD spot negativo constante (acumulado cayendo).
    rows = [
        {"session_date": f"d{i}", "price_close": 100.0 + i, "cvd_spot_usd": -1_000_000.0}
        for i in range(59, -1, -1)
    ]
    result = await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A")
    assert result["available"] is True
    assert result["windows"]["4s"]["divergence"] == "bajista"
    assert result["summary"].startswith("bajista")
    # Las cortas tambien se calculan, pero no cuentan para el resumen.
    assert result["windows"]["1d"]["divergence"] == "bajista"
    assert result["sustained_windows_evaluated"] == 5


@pytest.mark.asyncio
async def test_short_windows_use_endpoints_and_are_not_counted_as_sustained() -> None:
    rows = [
        {"session_date": f"d{i}", "price_close": 100.0 + i, "cvd_spot_usd": -1_000_000.0}
        for i in range(59, -1, -1)
    ]
    windows = (await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A"))["windows"]
    assert set(windows) == {"1d", "2d", "3d", "6d", "9d", "2s", "4s", "6s"}
    for label in ("1d", "2d", "3d"):
        assert windows[label]["method"] == "cambio_extremos"
        assert windows[label]["sustained"] is False
        assert windows[label]["price_slope"] is None
        assert "ventana corta" in windows[label]["reading"]
    for label in ("6d", "9d", "2s", "4s", "6s"):
        assert windows[label]["method"] == "pendiente"
        assert windows[label]["sustained"] is True
        assert windows[label]["price_slope"] is not None


@pytest.mark.asyncio
async def test_window_change_is_measured_over_n_sessions_not_n_minus_one() -> None:
    """La ventana de n sesiones compara el cierre actual contra n sesiones atras."""
    rows = [
        {"session_date": f"d{i}", "price_close": 100.0 * (1.10 ** i), "cvd_spot_usd": 1.0}
        for i in range(9, -1, -1)
    ]
    windows = (await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A"))["windows"]
    # +10% compuesto por sesion: una ventana de 1 sesion son exactamente +10%.
    assert windows["1d"]["price_change_pct"] == pytest.approx(10.0, abs=0.01)
    assert windows["2d"]["price_change_pct"] == pytest.approx(21.0, abs=0.01)
    assert windows["3d"]["price_change_pct"] == pytest.approx(33.1, abs=0.01)


@pytest.mark.asyncio
async def test_noise_sized_moves_do_not_flag_a_short_window_divergence() -> None:
    """BTC marcaba 'bajista' en 1d con el precio en +0.0003%: cruzar el cero no basta."""
    rows = [
        {"session_date": f"d{i}", "price_close": 63056.0 if i == 0 else 63055.8,
         "cvd_spot_usd": -2_800_000.0}
        for i in range(9, -1, -1)
    ]
    windows = (await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A"))["windows"]
    assert abs(windows["1d"]["price_change_pct"]) < 0.1
    assert windows["1d"]["divergence"] == "sin_divergencia"


class _IntradayConnection:
    """fetch() distingue la consulta intradia de la de sesiones por su texto."""

    def __init__(self, intraday_rows, session_rows):
        self._intraday = intraday_rows
        self._sessions = session_rows

    async def fetch(self, query, *_args):
        return self._intraday if "spot_trades_agg" in query else self._sessions


def _bar(minute, close, delta, lag=240.0):
    from datetime import UTC, datetime, timedelta
    return {"ts": datetime(2026, 8, 3, tzinfo=UTC) + timedelta(minutes=minute),
            "close": close, "delta": delta, "lag_seconds": lag}


@pytest.mark.asyncio
async def test_intraday_windows_are_anchored_to_the_last_complete_minute() -> None:
    # 17h de velas: precio subiendo, CVD spot vendiendo -> divergencia bajista.
    bars = [_bar(i, 60000.0 + i * 2.0, -50_000.0) for i in range(1020)]
    result = await divergence_scan(_IntradayConnection(bars, []), "BTCUSDT_PERP.A")
    intra = result["intraday"]
    assert intra["available"] is True
    assert set(intra["windows"]) == {"9m", "15m", "1h", "2h", "4h", "8h", "16h"}
    assert intra["anchored_at"] == bars[-1]["ts"].isoformat()
    assert intra["windows"]["1h"]["divergence"] == "bajista"
    assert intra["windows"]["16h"]["bars"] > intra["windows"]["9m"]["bars"]


@pytest.mark.asyncio
async def test_intraday_freshness_degrades_on_short_windows() -> None:
    """4 min de retraso son media ventana en 9m e irrelevantes en 16h."""
    bars = [_bar(i, 60000.0 + i * 2.0, -50_000.0, lag=240.0) for i in range(1020)]
    intra = (await divergence_scan(_IntradayConnection(bars, []), "BTCUSDT_PERP.A"))["intraday"]
    assert intra["windows"]["9m"]["freshness"] == "stale"
    assert intra["windows"]["16h"]["freshness"] == "fresh"


@pytest.mark.asyncio
async def test_intraday_ignores_moves_inside_their_own_noise() -> None:
    """Precio plano con ruido: no hay movimiento que divergir aunque la pendiente cruce."""
    bars = [_bar(i, 60000.0 + (1.0 if i % 2 else -1.0), -50_000.0) for i in range(1020)]
    intra = (await divergence_scan(_IntradayConnection(bars, []), "BTCUSDT_PERP.A"))["intraday"]
    for label in ("9m", "15m", "1h"):
        assert intra["windows"][label]["above_noise"] is False
        assert intra["windows"][label]["divergence"] == "sin_divergencia"


@pytest.mark.asyncio
async def test_intraday_reports_unavailable_without_bars() -> None:
    result = await divergence_scan(_IntradayConnection([], []), "BTCUSDT_PERP.A")
    assert result["intraday"]["available"] is False


def test_intraday_uses_the_same_two_venue_spot_universe() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    start = source.index("async def _intraday_divergences")
    body = source[start:source.index("async def divergence_scan", start)]
    assert "FROM spot_trades_agg" in body
    assert "exchange='combined'" in body
    # Anclado al ultimo minuto con ambas series, no a now().
    assert "complete_until" in body
    assert "cvd_diff_usd" not in body


@pytest.mark.asyncio
async def test_intraday_block_can_be_omitted_for_cheap_ai_profiles() -> None:
    bars = [_bar(i, 60000.0 + i * 2.0, -50_000.0) for i in range(1020)]
    result = await divergence_scan(
        _IntradayConnection(bars, []), "BTCUSDT_PERP.A", include_intraday=False
    )
    assert result["intraday"]["available"] is False
    assert result["intraday"]["windows"] == {}
    assert "omitted" in result["intraday"]


def test_solo_lite_se_queda_sin_las_divergencias_intradia() -> None:
    """Antes solo pro y max lo llevaban. El 2026-08-26 ALEJANDRO abrio la puerta y entro
    tambien en el perfil por defecto, que es el que sirve la foto sin argumentos.

    No es una relajacion del test para que pase el codigo: es una decision tomada con las
    dos salidas medidas -797 tokens por envio al modelo, con cinco envios en dos meses,
    frente a 98 MB/dia si el panel tuviera que pedir profile=pro para conseguir lo mismo-.
    lite se queda fuera a proposito: es el perfil que se pide cuando el presupuesto manda.
    """
    from app.ai_context import PROFILE_LIMITS

    assert PROFILE_LIMITS["lite"]["include_intraday_divergences"] is False
    assert PROFILE_LIMITS["default"]["include_intraday_divergences"] is True
    assert PROFILE_LIMITS["pro"]["include_intraday_divergences"] is True
    assert PROFILE_LIMITS["max"]["include_intraday_divergences"] is True


def test_daily_history_only_ships_on_the_expensive_profiles() -> None:
    """La serie sesion a sesion es lo que deja al modelo ver estructura, pero pesa."""
    from app.ai_context import PROFILE_LIMITS

    assert PROFILE_LIMITS["lite"]["daily_sessions"] == 0
    assert PROFILE_LIMITS["default"]["daily_sessions"] == 0
    assert PROFILE_LIMITS["pro"]["daily_sessions"] >= 30, "al menos un mes de sesiones"
    assert PROFILE_LIMITS["max"]["daily_sessions"] >= 90
    # Cada perfil debe declarar las dos llaves, aunque sea por defecto.
    for name, limits in PROFILE_LIMITS.items():
        assert "daily_sessions" in limits, name
        assert "include_verdicts" in limits, name


def test_dates_survive_json_serialisation() -> None:
    """session_date es `date`, que NO es subclase de datetime: sin rama propia llegaba
    intacto a json.dumps() en rough_token_estimate y reventaba el endpoint."""
    import json
    from datetime import date as _date
    from datetime import datetime as _datetime

    from app.ai_context import compact_dict, rough_token_estimate

    row = compact_dict({"session_date": _date(2026, 8, 4), "ts": _datetime(2026, 8, 4, 12, 30)})
    assert row["session_date"] == "2026-08-04"
    assert row["ts"].startswith("2026-08-04T12:30")
    json.dumps(row)                       # no debe lanzar
    assert rough_token_estimate(row) > 0


def test_daily_history_declares_where_each_leg_comes_from() -> None:
    source = (ROOT / "app" / "ai_context.py").read_text(encoding="utf-8")
    start = source.index("async def daily_history")
    body = source[start:source.index("async def verdict_history", start)]
    assert "field_notes" in body
    # El modelo debe recibir la advertencia sobre el diferencial, no solo el numero.
    assert "no es un agregado" in body.lower() or "no un agregado" in body.lower()
    assert "92-95%" in body
    assert "percent_rank" in source


def test_no_module_still_claims_the_futures_leg_is_a_multi_venue_aggregate() -> None:
    """`.A` en Coinalyze es Binance: verificado contra su catalogo y contra el OI real."""
    for name in ("app/api.py", "app/scalp_logic.py", "app/ai_context.py"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "coinalyze_aggregate" not in text, name
        assert "todos los venues" not in text, name
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "TODOS los venues" not in schema


def test_front_renders_both_divergence_groups() -> None:
    for key in ("'9m'", "'15m'", "'1h'", "'2h'", "'4h'", "'8h'", "'16h'"):
        assert key in JS
    assert "group-row" in JS
    assert "result.intraday" in JS


def test_session_bars_are_labelled_with_their_date() -> None:
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    start = JS.index("function renderDailyBars")
    body = JS[start:JS.index("function renderDivergences", start)]
    # Una etiqueta por barra, alineada con la misma cuenta de columnas que el SVG.
    assert "bars-dates" in body
    assert "gridTemplateColumns = `repeat(${n}" in body
    assert "iso.slice(5)" in body and "iso.slice(8)" in body
    assert ".bars-dates" in css
    # El detalle por barra va en <title>, que es texto y no markup.
    assert "createElementNS(NS, 'title')" in body
    assert "tip.textContent" in body


def test_time_axis_labels_always_carry_the_date() -> None:
    """El formateador del motor solo pone fecha al cambiar de dia: 48 h de velas de 5 min
    dejaban el eje lleno de HH:MM y sin fechas."""
    assert "function tickMarkFormatter" in JS
    assert "tickMarkFormatter: tickMarkFormatter(withTime)" in JS
    # La marca de hora tambien lleva dia/mes, no solo HH:MM.
    assert "return `${dia} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`" in JS
    # El crosshair muestra la fecha completa y declara la zona.
    assert "function crosshairFormatter" in JS
    assert "timeFormatter: crosshairFormatter(withTime)" in JS
    assert "UTC" in JS


def test_daily_chart_axis_shows_dates_without_a_meaningless_hour() -> None:
    """daily_session_agg se grafica a las 12:00Z: mostrar la hora seria ruido."""
    # El segundo argumento es withTime: en false el eje no imprime hora. El tercero, cuando
    # existe, es el formateador de importes y no toca esta garantia.
    assert "newChart('daily-chart', false" in JS
    assert "newChart('daily-chart', true" not in JS
    # Y los paneles intradia declaran que su eje va en UTC, no en hora local.
    for panel in ("CVD spot vs futuros", "Open Interest", "Operaciones spot de gran tamaño"):
        index = HTML.index(panel)
        assert "eje UTC" in HTML[index:index + 220], panel


def test_render_functions_replace_their_container_instead_of_appending() -> None:
    """refresh() repinta cada 15 s: quien solo hace append apila una copia por ciclo.

    renderDailyBars perdio su replaceChildren al reescribirse con DOM y el panel salia
    duplicado, triplicado, etc. hasta recargar. Esto vigila todas las funciones render*.
    """
    import re

    # Las guardas de salida temprana (`if (...) { x.replaceChildren(); return; }`) se
    # quitan antes de analizar: limpian solo en el camino vacio y darian por bueno un
    # append sin limpiar en el camino normal, que es exactamente como se colo el bug.
    guard = re.compile(r"if\s*\([^)]*\)\s*\{[^{}]*return[^{}]*\}")
    names = list(re.finditer(r"^function (render\w+)", JS, re.M))
    offenders: list[str] = []
    for index, match in enumerate(names):
        end = names[index + 1].start() if index + 1 < len(names) else len(JS)
        body = guard.sub("", JS[match.start():end])
        containers = set(re.findall(r"(?:const|let)\s+(\w+)\s*=\s*\$\('[^']+'\)", body))
        appended = set(re.findall(r"\b(\w+)\.append\(", body))
        for name in sorted(containers & appended):
            if f"{name}.replaceChildren" not in body:
                offenders.append(f"{match.group(1)} hace {name}.append() sin limpiar {name}")
    assert not offenders, offenders


def test_session_bars_never_build_markup_from_api_strings() -> None:
    """Las fechas vienen de la API y acaban dentro del SVG: nada de innerHTML aqui."""
    start = JS.index("function renderDailyBars")
    body = JS[start:JS.index("function renderDivergences", start)]
    assert ".innerHTML" not in body
    assert "createElementNS" in body


def test_divergence_panel_spans_the_full_grid_width() -> None:
    """Sin grid-column caia a span 1 de 12 y la tabla salia aplastada."""
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert ".divergence-panel { grid-column: span 12; }" in css
    assert "min-width: 220px" not in css


@pytest.mark.asyncio
async def test_divergence_reports_unavailable_without_history() -> None:
    result = await divergence_scan(_DivergenceConnection([]), "BTCUSDT_PERP.A")
    assert result["available"] is False


@pytest.mark.asyncio
async def test_divergence_uses_spot_cvd_not_the_mixed_diff() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    start = source.index("async def divergence_scan")
    body = source[start:source.index("# ---------------- Fase 1", start)]
    assert "cvd_spot_usd" in body
    assert "cvd_diff_usd" not in body


def test_api_exposes_provenance_for_the_daily_table() -> None:
    source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    assert "DAILY_SOURCES" in source
    assert "flow_direction" in source
    assert "spot_compra_futuros_venden" in source
    assert "spot_vende_futuros_compran" in source
    assert "price_response" in source
    assert "venta_sin_caida" in source
    assert "compra_sin_subida" in source
    assert "cvd_spot_percentile" in source
    assert '"sources": DAILY_SOURCES' in source
    assert "async def divergences_endpoint" in source
    assert "async def verdicts" in source


class _DailyProjectionConnection:
    def __init__(self):
        self.query = ""
        self.args = ()

    async def fetch(self, query, *args):
        self.query = query
        self.args = args
        return []


@pytest.mark.asyncio
async def test_daily_date_limit_applies_to_current_projection_only() -> None:
    """The date limit constrains every view of the mutable current projection."""
    from datetime import date

    conn = _DailyProjectionConnection()
    cutoff = date(2026, 6, 24)
    result = await daily_data(conn, "BTCUSDT_PERP.A", 60, cutoff)
    query = conn.query
    spot_hist = query[query.index("spot_hist AS"):query.index("), diff_hist AS")]
    diff_hist = query[query.index("diff_hist AS"):query.index("), selected AS")]
    selected = query[query.index("selected AS"):query.index("), segmented AS")]
    assert "session_date <= $3" in spot_hist
    assert "session_date <= $3" in diff_hist
    assert "session_date <= $3" in selected
    assert "cvd_spot_usd IS NOT NULL" in spot_hist
    assert "cvd_diff_usd IS NOT NULL" in diff_hist
    assert conn.args == ("BTCUSDT_PERP.A", 60, cutoff)
    assert result["temporal_semantics"] == "mutable_current_projection"
    assert result["knowledge_time_replay"] is False
    assert result["quick_read"]["available"] is False
def test_pr20_v7_daily_tail_helpers_do_not_bridge_missingness() -> None:
    rows = [
        {"session_date": "d1", "price_close": 101.0, "cvd_spot_usd": 1.0},
        {"session_date": "d2", "price_close": None, "cvd_spot_usd": None},
        {"session_date": "d3", "price_close": 103.0, "cvd_spot_usd": 2.0},
        {"session_date": "d4", "price_close": 104.0, "cvd_spot_usd": 3.0},
    ]
    assert _complete_tail_values(rows, "cvd_spot_usd", 3) is None
    assert _complete_tail_values(rows, "cvd_spot_usd", 2) == [2.0, 3.0]
    suffix = _contiguous_measured_suffix(rows, "price_close")
    assert [(row["session_date"], value) for row, value in suffix] == [
        ("d3", 103.0),
        ("d4", 104.0),
    ]


def test_pr20_v7_all_daily_structure_consumers_use_contiguous_price_suffixes() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    detail_start = source.index("async def structure_detail")
    detail = source[detail_start:source.index("_CONFIRMATION_TF", detail_start)]
    trend_start = source.index("async def trend_matrix")
    trend = source[trend_start:source.index("async def swing_score", trend_start)]
    assert '_contiguous_measured_suffix(ds, "price_close")' in detail
    assert '_contiguous_measured_suffix(ds, "price_close")' in trend


@pytest.mark.asyncio
async def test_pr20_v7_divergence_fails_closed_on_internal_spot_cvd_gap() -> None:
    rows = [
        {
            "session_date": f"d{i:02d}",
            "price_close": 100.0 + i,
            "cvd_spot_usd": -1_000_000.0,
        }
        for i in range(59, -1, -1)
    ]
    rows[2]["cvd_spot_usd"] = None
    result = await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A")
    assert result["windows"]["2d"]["available"] is True
    assert result["windows"]["3d"]["available"] is False
    assert result["windows"]["3d"]["reason"] == "missing_daily_evidence"
    assert result["windows"]["3d"]["missing_cvd_spot"] is True
    assert result["windows"]["3d"]["missing_price"] is False
    assert result["windows"]["4s"]["available"] is False
    assert result["sustained_windows_evaluated"] == 0


@pytest.mark.asyncio
async def test_pr20_v7_divergence_fails_closed_on_internal_price_gap() -> None:
    rows = [
        {
            "session_date": f"d{i:02d}",
            "price_close": 100.0 + i,
            "cvd_spot_usd": -1_000_000.0,
        }
        for i in range(59, -1, -1)
    ]
    rows[2]["price_close"] = None
    result = await divergence_scan(_DivergenceConnection(rows), "BTCUSDT_PERP.A")
    assert result["windows"]["1d"]["available"] is True
    assert result["windows"]["2d"]["available"] is False
    assert result["windows"]["2d"]["reason"] == "missing_daily_evidence"
    assert result["windows"]["2d"]["missing_price"] is True
    assert result["windows"]["2d"]["missing_cvd_spot"] is False
    assert result["windows"]["4s"]["available"] is False
