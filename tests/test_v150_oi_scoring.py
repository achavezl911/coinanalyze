"""Open Interest en `compute_scalp_summary()`: ya NO vota direccion por el signo de ΔOI, y
compara precio y OI en la MISMA ventana de 15 m.

Reglas duras de la especificacion (§2.3):
- precio ↑ + OI ↑ + flujo comprador  -> evidencia alcista;
- precio ↓ + OI ↑ + flujo vendedor   -> evidencia bajista;
- precio ↑ + OI ↓ (short covering)   -> NO vota SHORT;
- precio ↓ + OI ↓ (desapalancamiento)-> NO vota LONG;
- OI plano / ausente / precio 15 m ausente -> no aporta direccion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.scalp_logic import (
    _closed_1m_window_bounds,
    _closed_5m_oi_bounds,
    compute_scalp_summary,
    scalp_context,
)

W_OI = 10


def ctx(**over):
    """Contexto minimo y NEUTRO salvo el OI y su ventana de 15 m, para aislar la contribucion.

    Sin flujo, libro, absorcion, etc.: asi long_score/short_score reflejan SOLO el OI.
    """
    base = {
        "oi_now": None, "oi_start": None,
        "oi_window_status": "complete", "oi_window_samples": 4,
        "first_px_15m": None, "last_px_15m": None, "bars_15m": 0,
        "fut_delta_3m": None, "spot_delta_3m": None,
        "book_status": "ok",
    }
    base.update(over)
    return base


def _oi(chg_pct: float, oi_start: float = 1_000.0):
    """oi_now/oi_start que producen un Δ% dado."""
    return {"oi_start": oi_start, "oi_now": oi_start * (1 + chg_pct / 100)}


def _px15(pct: float, first: float = 100.0, bars: int = 15):
    return {"first_px_15m": first, "last_px_15m": first * (1 + pct / 100), "bars_15m": bars}


# ---------------- expansion coherente: SI vota direccion ----------------


def test_precio_sube_oi_sube_flujo_compra_es_alcista() -> None:
    out = compute_scalp_summary(ctx(**_oi(0.6), **_px15(0.4), fut_delta_3m=800.0))
    assert out["oi_contributes_direction"] is True
    assert out["oi_directional_support"] == 1
    assert out["long_score"] > out["short_score"]
    assert "oi" not in out["missing_components"]


def test_precio_baja_oi_sube_flujo_vende_es_bajista() -> None:
    out = compute_scalp_summary(ctx(**_oi(0.6), **_px15(-0.4), fut_delta_3m=-800.0))
    assert out["oi_contributes_direction"] is True
    assert out["oi_directional_support"] == -1
    assert out["short_score"] > out["long_score"]


# ---------------- contraccion: NUNCA vota al lado contrario ----------------


def test_precio_sube_oi_baja_no_genera_evidencia_short() -> None:
    out = compute_scalp_summary(ctx(**_oi(-0.6), **_px15(0.4)))
    # short covering: no demuestra compras NI ventas nuevas.
    assert out["oi_contributes_direction"] is False
    assert out["oi_directional_support"] is None
    # medido pero NEUTRAL: no inclina el score a NINGUN lado (no vota SHORT).
    assert out["long_score"] == out["short_score"]
    assert "oi" not in out["missing_components"]
    assert out["measured_weight"] >= W_OI


def test_precio_baja_oi_baja_no_genera_evidencia_long() -> None:
    out = compute_scalp_summary(ctx(**_oi(-0.6), **_px15(-0.4)))
    # desapalancamiento / cierre de largos: no demuestra ventas NI compras nuevas.
    assert out["oi_contributes_direction"] is False
    assert out["oi_directional_support"] is None
    # medido pero NEUTRAL: no inclina el score a NINGUN lado (no vota LONG).
    assert out["long_score"] == out["short_score"]
    assert "oi" not in out["missing_components"]


# ---------------- plano / ausente / sin precio 15 m ----------------


def test_oi_plano_no_aporta_direccion_pero_se_mide() -> None:
    out = compute_scalp_summary(ctx(**_oi(0.0), **_px15(0.4)))
    assert out["oi_state"] == "FLAT"
    assert out["oi_contributes_direction"] is False
    assert out["long_score"] == out["short_score"]  # sin inclinacion direccional
    assert "oi" not in out["missing_components"]


def test_oi_ausente_no_aporta_peso() -> None:
    out = compute_scalp_summary(ctx(oi_now=None, oi_start=None, **_px15(0.4)))
    assert out["oi_state"] == "NO_EVALUABLE"
    assert "oi" in out["missing_components"]


def test_bucket_oi_faltante_no_aporta_peso_aunque_haya_extremos() -> None:
    out = compute_scalp_summary(
        ctx(
            **_oi(0.6),
            **_px15(0.4),
            oi_window_status="partial",
            oi_window_samples=3,
        )
    )
    assert out["oi_chg_15m_pct"] is None
    assert out["oi_window_status"] == "partial"
    assert "oi" in out["missing_components"]


def test_precio_15m_ausente_no_hay_lectura_de_oi() -> None:
    # OI presente pero SIN precio de la misma ventana: no se puede leer -> no cuenta peso.
    out = compute_scalp_summary(ctx(**_oi(0.6), first_px_15m=None, last_px_15m=None, bars_15m=0))
    assert out["price_move_15m_pct"] is None
    assert out["price_move_15m_coverage"] == "none"
    assert "oi" in out["missing_components"]


def test_ventana_15m_termina_antes_de_la_vela_1m_abierta() -> None:
    now = datetime(
        2026, 8, 8,
        17, 49, 37,
        tzinfo=UTC,
    )

    start, end = _closed_1m_window_bounds(now, minutes=15)

    assert start == datetime(
        2026, 8, 8,
        17, 34, 0,
        tzinfo=UTC,
    )

    assert end == datetime(
        2026, 8, 8,
        17, 49, 0,
        tzinfo=UTC,
    )

    assert (end - start).total_seconds() == 15 * 60

    # 17:49 es la vela abierta y queda fuera porque el SQL utiliza ts < end.
    assert end < now


def test_oi_cerrado_delimita_exactamente_la_misma_ventana_de_precio() -> None:
    now = datetime(2026, 8, 9, 11, 49, 37, tzinfo=UTC)

    source_start, window_start, window_end = _closed_5m_oi_bounds(now)

    assert source_start == datetime(2026, 8, 9, 11, 25, tzinfo=UTC)
    assert window_start == datetime(2026, 8, 9, 11, 30, tzinfo=UTC)
    assert window_end == datetime(2026, 8, 9, 11, 45, tzinfo=UTC)
    assert window_end - window_start == timedelta(minutes=15)


def test_cobertura_15m_completa_permite_lectura_oi() -> None:
    out = compute_scalp_summary(
        ctx(
            **_oi(0.6),
            **_px15(0.4, bars=15),
            fut_delta_3m=800.0,
        )
    )

    assert out["price_move_15m_coverage"] == "complete"
    assert out["price_move_15m_status"] == "MEASURED"
    assert out["price_move_15m_pct"] == pytest.approx(0.4)

    assert out["oi_price_status"] == "MEASURED"
    assert out["oi_contributes_direction"] is True
    assert "oi" not in out["missing_components"]


def test_cobertura_15m_parcial_no_permite_scoring_de_oi() -> None:
    out = compute_scalp_summary(
        ctx(
            **_oi(0.6),
            **_px15(0.4, bars=3),
            fut_delta_3m=800.0,
        )
    )

    assert out["price_move_15m_coverage"] == "partial"
    assert out["price_move_15m_status"] == "PARTIAL"

    # El 0.4 % calculable matemáticamente NO representa una ventana de 15 m
    # completa, así que no se publica.
    assert out["price_move_15m_pct"] is None

    # Sin precio 15m válido no existe cuadrante precio + OI.
    assert out["oi_price_status"] == "NO_EVALUABLE"
    assert out["oi_price_quadrant"] is None
    assert out["oi_directional_support"] is None
    assert out["oi_contributes_direction"] is False

    # Fundamental: OI no consume peso cuando la ventana está incompleta.
    assert "oi" in out["missing_components"]

    # Y por supuesto tampoco inclina el score.
    assert out["long_score"] == out["short_score"]


class _ScalpContextConnection:
    def __init__(self) -> None:
        self.query = ""
        self.args = ()

    async def fetchrow(self, query, *args):
        self.query = query
        self.args = args
        return {
            "oi_window_start": args[4],
            "oi_window_end": args[5],
            "oi_window_samples": 4,
            "oi_window_status": "complete",
            "bars_15m": 15,
            "price_move_15m_coverage": "complete",
        }

    async def fetch(self, *_args):
        return []


@pytest.mark.asyncio
async def test_consulta_alinea_oi_y_precio_a_114937_sin_velas_abiertas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 8, 9, 11, 49, 37, tzinfo=UTC)
    conn = _ScalpContextConnection()
    monkeypatch.setattr("app.scalp_logic._utc_now", lambda: now)

    out = await scalp_context(conn, "BTCUSDT_PERP.A")  # type: ignore[arg-type]

    assert out["oi_window_start"] == datetime(2026, 8, 9, 11, 30, tzinfo=UTC)
    assert out["oi_window_end"] == datetime(2026, 8, 9, 11, 45, tzinfo=UTC)
    assert out["oi_window_samples"] == 4
    assert out["oi_window_status"] == "complete"
    assert out["price_move_15m_coverage"] == "complete"
    assert "ts >= $5" in conn.query and "ts <  $6" in conn.query
    assert "oi_samples=4" in conn.query
    assert "last_bucket-first_bucket=interval '15 minutes'" in conn.query
    assert "last_bar-px_15m.first_bar=interval '14 minutes'" in conn.query
    assert conn.args[5] < now


def test_expansion_pero_flujo_contradice_no_vota_direccion() -> None:
    # precio ↑ + OI ↑ pero flujo VENDEDOR: la incoherencia anula el voto direccional.
    out = compute_scalp_summary(ctx(**_oi(0.6), **_px15(0.4), fut_delta_3m=-800.0))
    assert out["oi_contributes_direction"] is False
    assert out["long_score"] == out["short_score"]  # incoherencia -> voto neutral
