"""Pruebas de regresión propuestas para Coinalyze v1.4.9-P0-P3.

Origen: auditoría externa del 2026-08-06. Los 9 casos se reprodujeron contra el código
desplegado antes de tocar nada; los 9 se confirmaron. Estas pruebas fijan el comportamiento
corregido para que ninguna de las regresiones pueda volver a entrar.
"""
from __future__ import annotations

import math

from app.scalp_logic import as_float, basis_quality, compute_scalp_summary, profile_view, walk_book


def _ctx_base() -> dict:
    return {
        "fut_delta_1m": 100_000.0,
        "fut_volume_1m": 100_000.0,
        "fut_delta_3m": 300_000.0,
        "fut_volume_3m": 300_000.0,
        "spot_delta_3m": None,
        "spot_volume_3m": None,
        "imbalance_l5": 0.50,
        "spread_bps": 1.0,
        "first_px_3m": None,
        "last_px_3m": None,
        "price": 100.0,
        "long_liq": None,
        "short_liq": None,
        "oi_now": None,
        "oi_start": None,
        "session_vwap": None,
        "book_status": "ok",
        "book_lag_seconds": 1.0,
        "fut_price": 100.0,
        "spot_price": 100.0,
        "fut_event_ms": 100_000.0,
        "spot_event_ms": 100_000.0,
        "now_ms": 101_000.0,
        "baseline_3m": {
            "p50": 0.05,
            "p75": 0.10,
            "p90": 0.50,
            "p95": 0.80,
            "mad": 0.01,
            "sample_count": 100,
        },
    }


def test_numeric_parser_rejects_non_finite_values() -> None:
    assert as_float(float("inf")) is None
    assert as_float(float("-inf")) is None
    assert as_float(float("nan")) is None


def test_basis_rejects_future_timestamps() -> None:
    out = basis_quality(101.0, 100.0, 102_000.0, 102_000.0, 101_000.0)
    assert out["status"] in {"DEGRADED", "UNAVAILABLE", "ERROR"}
    assert out["basis_bps"] is None


def test_walk_book_uses_first_valid_level_as_best_price() -> None:
    out = walk_book([[0.0, 10.0], [100.0, 1.0], [101.0, 1.0]], 50.0)
    assert out["best_price"] == 100.0
    assert math.isfinite(out["slippage_bps"])


def test_missing_spot_does_not_create_divergence_or_difference() -> None:
    out = compute_scalp_summary(_ctx_base())
    assert out["spot_fut_divergence_norm"] is None
    assert out["diff_3m"] is None


def test_missing_price_does_not_create_absorption() -> None:
    out = compute_scalp_summary(_ctx_base())
    assert out["price_move_3m_pct"] is None
    assert out["absorption"] in {"Sin datos", "No evaluable", None}


def test_score_exposes_measured_evidence_weight() -> None:
    out = compute_scalp_summary(_ctx_base())
    assert "measured_weight" in out
    assert "expected_weight" in out
    assert "evidence_coverage_pct" in out
    assert out["measured_weight"] < out["expected_weight"]


def test_profile_coverage_scales_with_each_timeframe() -> None:
    trend = {
        "timeframes": {
            "4h": {"bias": "alcista", "flow_state": "ambas_compran"},
            "18m": {"bias": "alcista", "flow_state": "ambas_compran"},
            "1m": {"bias": "alcista", "flow_state": "ambas_compran"},
        }
    }
    out = profile_view(trend, [], "intradia")
    # Cobertura esperada: 30*(1/2) + 45*(1/3) + 25*(1/2) = 42.5%.
    assert out["coverage_pct"] == 42.5
    assert out["confidence"] == "baja"


def test_profile_does_not_count_same_timeframe_twice() -> None:
    trend = {
        "timeframes": {
            "3d": {"bias": "alcista"},
            "1d": {"bias": "alcista"},
            "8h": {"bias": "alcista"},
            "4h": {"bias": "alcista"},
            "1h": {"bias": "alcista"},
        }
    }
    out = profile_view(trend, [], "swing")
    used = []
    for layer in out["layers"].values():
        used.extend(tf["timeframe"] for tf in layer["timeframes"] if tf["source"] != "ninguna")
    assert len(used) == len(set(used)), "una temporalidad no puede aportar a dos capas"


def test_swing_layers_are_disjoint_by_construction() -> None:
    """El §6.2 original repetía 8h/4h en contexto y confirmación, y 1h en dos capas."""
    from app.scalp_logic import TRADING_PROFILES

    for profile, spec in TRADING_PROFILES.items():
        vistos: list[str] = []
        for conf in spec["layers"].values():
            vistos.extend(conf["timeframes"])
        assert len(vistos) == len(set(vistos)), f"{profile} repite temporalidades: {vistos}"


def test_regime_without_components_is_unavailable() -> None:
    from app.metrics import compute_regime

    score, label = compute_regime({})
    assert score is None
    assert "Sin datos" in label


def test_snapshot_missing_source_stays_null() -> None:
    """optional_finite conserva la ausencia; _safe solo vale donde el default es legítimo."""
    from app.metrics import optional_finite

    for ausente in (None, "abc", float("nan"), float("inf")):
        assert optional_finite(ausente) is None
    assert optional_finite(0.0) == 0.0


def test_execution_cost_unknown_age_is_not_valid() -> None:
    """Sin saber de cuándo es el libro, el coste calculado sobre él no significa nada."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "scalp_logic.py").read_text(
        encoding="utf-8"
    )
    bloque = source.split("async def execution_cost")[1].split("async def ")[0]
    assert 'usable, status = False, "UNAVAILABLE"' in bloque


def test_rollup_requires_all_constituent_minutes() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "app" / "ingest.py").read_text(
        encoding="utf-8"
    )
    assert "HAVING COUNT(*) = 5" in source


def test_frontend_surfaces_endpoint_error() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    assert "state.errors[path]" in source
    assert "function lastEndpointError" in source


def test_liquidation_null_is_not_zero() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(
        encoding="utf-8"
    )
    bloque = source.split("function renderLiquidations")[1].split("function ")[0]
    assert "asNumber(r.long_liq) || 0" not in bloque
    assert "Sin dato" in bloque


async def test_execution_cost_declara_el_instante_mas_viejo_que_usa() -> None:
    """K43 · DEMANDA: la respuesta trae su propio as_of, y es el del libro MAS VIEJO.

    La tabla mezcla un libro por venue. Etiquetarla con el mas fresco prometeria una
    frescura que la otra mitad no tiene; sin ningun venue usable no hay instante y va a
    null, que es "no evaluable" y no "de ahora".
    """
    from datetime import UTC, datetime, timedelta

    from app.scalp_logic import execution_cost

    ahora = datetime.now(UTC)
    libro = [[100.0, 10.0], [101.0, 10.0]]

    class _Conn:
        def __init__(self, filas):
            self.filas = filas

        async def fetch(self, _q, *_a):
            return self.filas

    def fila(exchange, edad):
        return {"exchange": exchange, "ts": ahora - timedelta(seconds=edad),
                "bids": libro, "asks": libro, "levels": 2, "age_seconds": edad}

    salida = await execution_cost(_Conn([fila("binance", 2.0), fila("bybit", 9.0)]), "S", [1000.0])
    assert salida["as_of"] == (ahora - timedelta(seconds=9.0)).isoformat()
    assert [v["status"] for v in salida["venues"]] == ["VALID", "VALID"]

    # Ningun venue usable: la edad desconocida ya no es valida, asi que tampoco hay as_of.
    ciego = dict(fila("binance", 2.0), age_seconds=None)
    assert (await execution_cost(_Conn([ciego]), "S", [1000.0]))["as_of"] is None
