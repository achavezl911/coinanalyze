"""P2: los umbrales salen de la distribucion medida, no de una constante.

Medicion del 2026-08-06 sobre 20 021 velas de 1 min y 1 808 de 4 h (3 simbolos):
|delta|/volumen tiene p50 = 0.34 a 1 m y 0.045 a 4 h. El ABSORPTION_MIN_RATIO=0.10 que
introdujo P0 dejaba pasar el 78 % de las ventanas de 3 m y habria rechazado el 87 % de las
de 4 h. El ratio decae al alargar la ventana, asi que el umbral depende de la ventana.
"""
from __future__ import annotations

import pytest

from app.daily_agg import BASELINE_WINDOWS
from app.scalp_logic import ABSORPTION_MIN_RATIO, baseline_band, classify_absorption

# Baseline sintetica con la forma real de una ventana de 3 m en BTC.
BASE_3M = {
    "sample_count": 6671,
    "p50": 0.2377,
    "p75": 0.3893,
    "p90": 0.5333,
    "p95": 0.6191,
    "mad": 0.11,
}


@pytest.mark.parametrize(
    ("ratio", "esperado"),
    [
        (0.05, "bajo"),
        (0.2376, "bajo"),
        (0.30, "normal"),
        (0.45, "elevado"),
        (0.58, "alto"),
        (0.70, "extremo"),
    ],
)
def test_la_banda_situa_el_valor_en_su_distribucion(ratio, esperado) -> None:
    assert baseline_band(ratio, BASE_3M)["band"] == esperado


def test_el_zscore_es_robusto_no_media_y_sigma() -> None:
    """(x - mediana) / (1.4826 * MAD): la cola de esta distribucion rompe media y sigma."""
    out = baseline_band(BASE_3M["p50"], BASE_3M)
    assert out["robust_z"] == 0.0
    esperado = (0.5 - BASE_3M["p50"]) / (1.4826 * BASE_3M["mad"])
    assert baseline_band(0.5, BASE_3M)["robust_z"] == pytest.approx(round(esperado, 2))


def test_sin_baseline_no_se_inventa_contexto() -> None:
    for baseline in (None, {}, {"sample_count": 0}):
        out = baseline_band(0.3, baseline)
        assert out["band"] is None
        assert out["robust_z"] is None
        assert out["status"] == "sin_baseline"


def test_mad_cero_no_divide_entre_cero() -> None:
    out = baseline_band(0.3, {**BASE_3M, "mad": 0.0})
    assert out["robust_z"] is None
    assert out["band"] == "normal"


def test_el_umbral_medido_es_mas_exigente_que_la_constante_en_ventanas_cortas() -> None:
    """El caso concreto que motiva P2: 0.10 en 3 m no filtraba practicamente nada."""
    delta, volumen, move = 25_000.0, 100_000.0, 0.01  # ratio 0.25
    # Con la constante heredada la lectura pasaba...
    assert classify_absorption(delta, move, volumen, ABSORPTION_MIN_RATIO)[1] != "Sin señal"
    # ...y con el p75 medido de esa ventana (0.3893) se queda fuera.
    assert classify_absorption(delta, move, volumen, BASE_3M["p75"])[1] == "Sin señal"


def test_el_umbral_medido_es_mas_permisivo_que_la_constante_en_4h() -> None:
    """A 4 h el p75 medido es ~0.07: la constante 0.10 habria tirado lecturas validas."""
    p75_4h = 0.0713
    delta, volumen, move = 8_000.0, 100_000.0, 0.01  # ratio 0.08
    assert classify_absorption(delta, move, volumen, ABSORPTION_MIN_RATIO)[1] == "Sin señal"
    assert classify_absorption(delta, move, volumen, p75_4h)[1] != "Sin señal"


def test_sin_umbral_explicito_se_usa_el_fallback() -> None:
    delta, volumen, move = 5_000.0, 100_000.0, 0.01  # ratio 0.05
    assert classify_absorption(delta, move, volumen)[1] == "Sin señal"
    assert classify_absorption(delta, move, volumen, 0.01)[1] != "Sin señal"


def test_las_ventanas_con_baseline_cubren_las_que_publica_la_matriz() -> None:
    etiquetas = {label for label, _, _ in BASELINE_WINDOWS}
    assert {"1m", "3m", "5m", "15m", "18m", "30m", "1h", "4h"} <= etiquetas


def test_las_ventanas_largas_no_se_miden_sobre_1min() -> None:
    """A 4 h sobre 14 dias de 1min saldrian ~80 observaciones: se usa el 4hour (300 dias)."""
    fuente = {label: source for label, _, source in BASELINE_WINDOWS}
    assert fuente["4h"] == "4hour"
    assert fuente["1d"] == "4hour"
    assert fuente["1h"] == "1min"


def test_el_refresco_exige_muestra_minima() -> None:
    """Una muestra corta no es una distribucion: mejor sin baseline que con una mentira."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "daily_agg.py").read_text(
        encoding="utf-8"
    )
    assert 'row["n"] < 30' in source


def test_el_posicionamiento_declara_que_cuenta_cuentas_no_notional() -> None:
    """El ratio long/short reparte CUENTAS: leerlo como dinero es el error tipico."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "scalp_logic.py").read_text(
        encoding="utf-8"
    )
    bloque = source.split("async def positioning_context")[1].split("async def ")[0]
    assert "no de notional" in bloque
    # Muestra corta -> sin percentil, no un percentil sobre cuatro filas.
    assert "n >= 288" in bloque


def test_el_ingest_descarta_reparto_incoherente() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ingest.py").read_text(
        encoding="utf-8"
    )
    bloque = source.split("async def upsert_long_short")[1].split("async def ")[0]
    assert "long_pct + short_pct - 100" in bloque


def test_el_percentil_no_dice_30_dias_si_no_los_tiene() -> None:
    """La serie empieza vacia: llamar '30 dias' a 26 horas de historia es precision falsa."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "scalp_logic.py").read_text(
        encoding="utf-8"
    )
    bloque = source.split("async def positioning_context")[1].split("async def ")[0]
    assert "percentile_30d" not in bloque, "el nombre promete un mes que puede no existir"
    assert "sample_days" in bloque and "sample_is_full_month" in bloque
