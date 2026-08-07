"""Fase 1 — carácter de zona (acumulación / distribución / rotación).

Los escenarios están calcados de visitas reales medidas sobre la base del LXC 140 el
2026-08-04, para que los tests fijen el comportamiento frente a datos que de verdad ocurrieron
y no frente a un caso inventado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.zones import MIN_ZONE_BARS, zone_character_read

BASELINE = {
    "median_abs_cvd_spot": 50_000_000.0,
    "median_bar_volume_usd": 1_000_000_000.0,
    # Medido en produccion: mediana de |delta|/volumen de UNA vela 4h = 0.0412 (BTC),
    # 0.0343 (ETH), 0.0340 (SOL).
    "effort_scale": 0.0412,
    # muestra sintetica centrada en 0.004 con cola a ambos lados, 60 valores
    "funding_sample": [(-30 + i) / 5000 for i in range(60)],
}


def _bars(count, *, start_px, end_px, buy_share, span_pct=0.6, close_pos=0.5, bar_vol=1e9):
    """Serie de velas 4h con delta y forma controlados.

    buy_share = fraccion del volumen que fue compra agresiva. 0.5 -> delta cero.
    close_pos = donde cierra dentro de la barra (0 = minimo, 1 = maximo).
    """
    out = []
    t0 = datetime(2026, 6, 1, tzinfo=UTC)
    for i in range(count):
        px = start_px + (end_px - start_px) * (i / max(count - 1, 1))
        half = px * span_pct / 200
        low, high = px - half, px + half
        out.append(
            {
                "ts": t0 + timedelta(hours=4 * i),
                "open": px,
                "high": high,
                "low": low,
                "close": low + (high - low) * close_pos,
                "volume": bar_vol / px,
                "buy_volume": bar_vol / px * buy_share,
            }
        )
    return out


def _visit(bars, *, cvd_spot=None, n=10, oi_first=None, oi_last=None, funding=None):
    return {
        "bars": bars,
        "from": "2026-06-01",
        "to": "2026-06-10",
        "sessions": {
            "count": n,
            "cvd_spot_usd": cvd_spot,
            "oi_first": oi_first,
            "oi_last": oi_last,
            "funding_avg": funding,
        },
    }


# ------------------------------------------------------------------ cobertura minima
def test_too_few_bars_returns_unavailable_not_a_verdict() -> None:
    result = zone_character_read(_visit(_bars(5, start_px=60000, end_px=60000, buy_share=0.4)), BASELINE)
    assert result["available"] is False
    assert str(MIN_ZONE_BARS) in result["reason"]


# ------------------------------------------------------------------ acumulacion
def test_absorbed_selling_with_flat_price_reads_accumulation() -> None:
    """Firma medida en la visita del 06-feb-2026: futuros vendiendo, precio aguantando,
    spot comprando y funding negativo."""
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46, close_pos=0.75)
    result = zone_character_read(
        _visit(bars, cvd_spot=+440_000_000, n=10, oi_first=6.0e9, oi_last=6.2e9, funding=-0.0055),
        BASELINE,
    )
    assert result["available"] is True
    assert result["character"] == "acumulacion"
    assert result["score"] > 0
    effort = next(c for c in result["components"] if c["key"] == "esfuerzo_resultado")
    assert effort["value"] > 0, "venta agresiva absorbida debe puntuar ALCISTA"


def test_narrative_names_the_cause_with_figures() -> None:
    """La narrativa habla en magnitudes relativas ('5.7x lo normal', 'el 4% de lo habitual')
    y no en unidades de jerga como ATR: un novato tiene que poder leer la causa."""
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46, close_pos=0.75)
    result = zone_character_read(_visit(bars, cvd_spot=+440_000_000, funding=-0.0055), BASELINE)
    joined = " ".join(result["narrative"])
    assert "M USD" in joined
    assert "lo normal" in joined and "lo habitual" in joined
    assert "ATR" not in joined, "el panel no debe exigir jerga para entenderse"


# ------------------------------------------------------------------ distribucion
def test_aggressive_buying_without_advance_reads_distribution() -> None:
    """Firma medida en la zona roja de abr-may 2026: +2 770 M de compra agresiva de futuros
    que no movio el precio, y despues -13%. El CVD spot era POSITIVO, asi que una regla
    'spot comprando = acumulacion' la habria pintado verde."""
    bars = _bars(60, start_px=79000, end_px=79050, buy_share=0.54, close_pos=0.3)
    result = zone_character_read(
        _visit(bars, cvd_spot=+160_000_000, n=40, oi_first=6.0e9, oi_last=6.0e9, funding=0.0),
        BASELINE,
    )
    assert result["character"] == "distribucion"
    effort = next(c for c in result["components"] if c["key"] == "esfuerzo_resultado")
    assert effort["value"] < 0
    spot = next(c for c in result["components"] if c["key"] == "cvd_spot")
    assert spot["value"] > 0, "el spot fue comprador; el modelo debe verlo y aun asi concluir distribucion"


# ------------------------------------------------------------------ sin caracter
def test_flow_that_moves_price_normally_has_no_character() -> None:
    """Delta grande QUE SI mueve el precio no es absorcion: es solo tendencia.

    buy_share=0.515 son 3 puntos de flujo direccional, cerca del maximo real observado en
    ventanas de este tamaño; valores mayores no existen en los datos y probarlos mediria una
    situacion imposible.
    """
    bars = _bars(40, start_px=60000, end_px=64000, buy_share=0.515, close_pos=0.5)
    result = zone_character_read(_visit(bars, cvd_spot=0.0, funding=0.004), BASELINE)
    effort = next(c for c in result["components"] if c["key"] == "esfuerzo_resultado")
    assert effort["value"] == 0.0


def test_still_price_with_negligible_flow_is_not_absorption() -> None:
    """Si casi nadie empujo, que el precio no se moviera no dice nada de quien habia al otro
    lado. Sin EFFORT_MINIMUM el suelo del denominador convertia cualquier zona quieta en
    'absorcion', que es un falso positivo grave."""
    bars = _bars(40, start_px=60000, end_px=60010, buy_share=0.502)
    result = zone_character_read(_visit(bars, cvd_spot=0.0), BASELINE)
    effort = next(c for c in result["components"] if c["key"] == "esfuerzo_resultado")
    assert effort["value"] == 0.0


# ---------------------------------------------------- normalizacion por tamaño de ventana
def test_effort_component_survives_long_windows() -> None:
    """Regresión dura. La primera versión comparaba la fracción direccional contra un umbral
    ABSOLUTO (2 %) y el recorrido contra el ATR de UNA vela. Sobre datos reales eso dejaba el
    componente de peso 35 en 0.0 en las cuatro visitas medidas: un componente muerto, que es
    justo el defecto que la auditoría v1.3.8 había corregido en las barreras."""
    # 155 velas, replica de la zona roja abr-may 2026: fraccion direccional 0.0101 y
    # recorrido de solo el 29 % de lo normal para esa longitud.
    long_zone = _bars(155, start_px=79000, end_px=79120, buy_share=0.5075, close_pos=0.45)
    result = zone_character_read(_visit(long_zone, cvd_spot=+160_000_000, n=40), BASELINE)
    effort = next(c for c in result["components"] if c["key"] == "esfuerzo_resultado")
    assert effort["value"] is not None
    assert effort["value"] != 0.0, "una ventana larga no puede anular el componente principal"
    assert effort["value"] < 0, "compra agresiva sin avance es distribución"


def test_same_signature_scores_alike_at_any_window_length() -> None:
    """La normalización tiene que hacer comparables ventanas de tamaños muy distintos."""
    short = _bars(24, start_px=60000, end_px=60020, buy_share=0.47, close_pos=0.7)
    long = _bars(150, start_px=60000, end_px=60050, buy_share=0.47, close_pos=0.7)
    a = zone_character_read(_visit(short, cvd_spot=1e8), BASELINE)
    b = zone_character_read(_visit(long, cvd_spot=1e8), BASELINE)
    ea = next(c for c in a["components"] if c["key"] == "esfuerzo_resultado")["value"]
    eb = next(c for c in b["components"] if c["key"] == "esfuerzo_resultado")["value"]
    assert ea > 0 and eb > 0, "la misma firma debe leerse igual en ambas longitudes"


# ------------------------------------------------------------------ renormalizacion
def test_missing_components_renormalise_instead_of_scoring_zero() -> None:
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46, close_pos=0.75)
    full = zone_character_read(
        _visit(bars, cvd_spot=+440_000_000, oi_first=6.0e9, oi_last=6.2e9, funding=-0.0055),
        BASELINE,
    )
    partial = zone_character_read(_visit(bars, cvd_spot=None, funding=None), BASELINE)
    assert full["evidence_coverage_pct"] == 100.0
    assert partial["evidence_coverage_pct"] < 100.0
    unavailable = [c["key"] for c in partial["components"] if c["status"] == "unavailable"]
    assert "cvd_spot" in unavailable and "funding" in unavailable
    # el score renormalizado no se hunde solo por faltar componentes
    assert partial["score"] > 0


def test_low_coverage_forces_low_confidence() -> None:
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46, close_pos=0.75)
    result = zone_character_read(_visit(bars, cvd_spot=None, funding=None), BASELINE)
    if result["evidence_coverage_pct"] < 50:
        assert result["confidence"] == "baja"


def test_no_measurable_component_is_sin_datos() -> None:
    flat = _bars(40, start_px=60000, end_px=60000, buy_share=0.5, span_pct=0.0)
    result = zone_character_read(_visit(flat, cvd_spot=None, funding=None), BASELINE)
    assert result["character"] in {"sin_datos", "sin_caracter"}


# ------------------------------------------------------------------ trazabilidad
def test_verdict_declares_its_clocks_and_that_absorption_is_inferred() -> None:
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46)
    result = zone_character_read(_visit(bars, cvd_spot=1.0, funding=0.001), BASELINE)
    assert "No se suman" in result["method"]["clocks"]
    assert "infiere" in result["warning"]
    assert result["method"]["weights_basis"].startswith("heur")


def test_no_forward_looking_field_leaks_into_the_score() -> None:
    """El veredicto solo puede mirar barras DENTRO de la zona.

    Allowlist explicita en vez de buscar subcadenas: 'delta_futuros_usd' se refiere al
    instrumento (perpetuo), no a datos posteriores, y un filtro por 'futuro' lo confundiria.
    """
    bars = _bars(40, start_px=60000, end_px=60050, buy_share=0.46)
    result = zone_character_read(_visit(bars, cvd_spot=1.0), BASELINE)
    assert set(result["measurements"]) == {
        "delta_futuros_usd",
        "volumen_usd",
        "fraccion_direccional",
        "esfuerzo_vs_normal",
        "recorrido_vs_normal_pct",
        "eficiencia_absorcion",
        "precio_cambio_pct",
        "atr_zona_pct",
        "cvd_spot_usd",
        "oi_cambio_pct",
        "funding_medio",
        "funding_percentil",
        "volumen_relativo",
    }, "todo campo nuevo debe revisarse: ninguno puede depender de barras posteriores a la zona"


@pytest.mark.parametrize("share", [0.30, 0.46, 0.54, 0.70])
def test_score_stays_inside_bounds(share: float) -> None:
    bars = _bars(30, start_px=60000, end_px=60100, buy_share=share)
    result = zone_character_read(_visit(bars, cvd_spot=1e9, oi_first=6e9, oi_last=7e9, funding=-0.006), BASELINE)
    assert -100.0 <= result["score"] <= 100.0
