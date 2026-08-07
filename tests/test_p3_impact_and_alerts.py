"""P3: impacto de mercado realizado y alertas contra la distribucion, no contra un umbral.

Lo que NO entra en P3 y por que: la persistencia de paredes y la conducta compatible con
spoofing necesitan que el libro publicado abarque precio. Medido el 2026-08-06, los 50
niveles de Bybit cubren 1.2-1.5 bps en BTC y 2.6 en ETH (los 10 de Binance, 0.2-0.5 bps).
Sobre ~8 USD de rango en BTC no hay "muro a distancia" que vigilar. Solo SOL llega a 67 bps.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.api import statistical_alerts
from app.daily_agg import BASELINE_METRICS
from app.scalp_logic import IMPACT_WINDOWS

ROOT = Path(__file__).resolve().parents[1]


def impacto(band: str | None, *, completa: bool = True, window: str = "15m") -> dict:
    return {
        "windows": [
            {
                "window": window,
                "impact_bps_per_musd": 12.5,
                "coverage_complete": completa,
                "context": {"band": band, "robust_z": 3.1},
                "reading": "libro muy fino",
            }
        ]
    }


def test_el_impacto_se_mide_no_se_modela() -> None:
    assert "impact_bps_per_musd" in BASELINE_METRICS
    expr = BASELINE_METRICS["impact_bps_per_musd"]
    # Precio contra delta neto, ambos del mismo bucket.
    assert "px_close-px_open" in expr and "abs(delta)" in expr
    # Delta despreciable => NULL, no un impacto enorme sin significado.
    assert "abs(delta)*px_close/1e6 > 0.01" in expr


def test_las_ventanas_de_impacto_tienen_baseline() -> None:
    from app.daily_agg import BASELINE_WINDOWS

    con_baseline = {label for label, _, _ in BASELINE_WINDOWS}
    assert {label for label, _ in IMPACT_WINDOWS} <= con_baseline


def test_solo_alerta_el_extremo_de_liquidez() -> None:
    """'alto' aparece por definicion el 5-10% del tiempo: alertarlo seria ruido constante."""
    assert statistical_alerts({}, impacto("alto")) == []
    assert statistical_alerts({}, impacto("elevado")) == []
    assert len(statistical_alerts({}, impacto("extremo"))) == 1


def test_no_alerta_sobre_una_ventana_incompleta() -> None:
    """Menos minutos = menos flujo, y el ratio sale inflado por construccion."""
    assert statistical_alerts({}, impacto("extremo", completa=False)) == []


def test_sin_baseline_no_hay_alerta() -> None:
    """Callar es correcto: sin distribucion no se puede decir que algo sea extremo."""
    assert statistical_alerts({}, impacto(None)) == []
    assert statistical_alerts({}, {"windows": []}) == []


@pytest.mark.parametrize(("band", "espera"), [("bajo", 0), ("normal", 0), ("alto", 1), ("extremo", 1)])
def test_alerta_de_flujo_agresivo_por_banda(band, espera) -> None:
    summary = {
        "absorption_context": {"band": band, "robust_z": 2.4, "sample_count": 6673},
        "absorption_delta_ratio": 0.51,
    }
    assert len(statistical_alerts(summary, {"windows": []})) == espera


def test_la_alerta_lleva_la_evidencia_no_solo_el_veredicto() -> None:
    summary = {
        "absorption_context": {"band": "extremo", "robust_z": 3.9, "sample_count": 6673},
        "absorption_delta_ratio": 0.72,
    }
    alerta = statistical_alerts(summary, {"windows": []})[0]
    assert "0.72" in alerta["detail"]
    assert "3.9" in alerta["detail"]
    assert "6673" in alerta["detail"]


def test_el_basis_no_utilizable_se_avisa() -> None:
    """P0 dejo de publicar el numero; sin aviso el operador solo ve un hueco."""
    source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    bloque = source.split("async def scalp_alerts")[1].split("def statistical_alerts")[0]
    assert 'summary.get("basis_status") in {"STALE", "UNAVAILABLE"}' in bloque


def test_el_impacto_declara_que_no_es_el_slippage_de_tu_orden() -> None:
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    bloque = source.split("async def market_impact")[1].split("async def ")[0]
    assert "no es el slippage" in bloque.lower()
    assert "execution-cost" in bloque


def test_no_se_afirma_spoofing_en_ninguna_parte() -> None:
    """El feed no da profundidad que abarque precio: no se puede sostener esa afirmacion."""
    for name in ("scalp_logic.py", "api.py", "scalp_collector.py"):
        source = (ROOT / "app" / name).read_text(encoding="utf-8")
        for linea in source.splitlines():
            texto = linea.lower()
            if "spoof" in texto:
                assert texto.lstrip().startswith("#"), f"{name}: spoofing fuera de un comentario"
