"""v1.5.0 — la ausencia de dato NO se convierte en cero en `compute_scalp_summary()`.

Cada caso aisla UN insumo: se parte de un contexto con los siete componentes medidos
(cobertura 100 %) y se retira solo lo que se quiere probar, de forma que la caida de
`evidence_coverage_pct` es exactamente el peso del componente retirado. Si un componente
ausente siguiera votando 0, la cobertura no bajaria y estos tests fallarian.
"""

from __future__ import annotations

import pytest

from app.scalp_logic import compute_scalp_summary

# Pesos declarados en compute_scalp_summary(); suman 100.
W_FUT_DELTA = 20
W_DIVERGENCE = 15
W_BOOK = 20
W_ABSORPTION = 20
W_LIQUIDATIONS = 10
W_OI = 10
W_VWAP = 5


def ctx_completo(**overrides: object) -> dict[str, object]:
    """Contexto con los 7 componentes medibles. `None` explicito retira un insumo."""
    base: dict[str, object] = {
        "fut_delta_1m": 100.0,
        "fut_volume_1m": 1_000.0,
        "fut_delta_3m": 300.0,
        "fut_volume_3m": 1_000.0,
        "spot_delta_3m": 50.0,
        "spot_volume_3m": 500.0,
        "imbalance_l5": 0.6,
        "first_px_3m": 100.0,
        "last_px_3m": 100.2,
        "price": 100.2,
        "book_status": "ok",
        "spread_bps": 1.0,
        # Heartbeat del colector de WS vivo => la ventana de liquidaciones SI se midio.
        "liq_feed_status": "ok",
        "liq_feed_lag_s": 3.0,
        "long_liq": 20_000.0,
        "short_liq": 5_000.0,
        "oi_now": 1_000.0,
        "oi_start": 990.0,
        # Ventana de precio de 15 m (misma que el OI): sube, y con OI en expansion el OI aporta
        # direccion. `bars_15m` completa la cobertura. Sin estos campos el OI no podria leerse.
        "first_px_15m": 100.0,
        "last_px_15m": 100.3,
        "bars_15m": 15,
        "session_vwap": 100.0,
    }
    base.update(overrides)
    return base


def test_contexto_completo_mide_los_siete_componentes() -> None:
    out = compute_scalp_summary(ctx_completo())
    assert out["missing_components"] == []
    assert out["evidence_coverage_pct"] == 100.0
    assert out["measured_weight"] == 100.0


# ---------------- Open Interest ----------------


@pytest.mark.parametrize(
    ("caso", "overrides"),
    [
        ("ambos_ausentes", {"oi_now": None, "oi_start": None}),
        ("solo_oi_inicial", {"oi_now": None}),
        ("solo_oi_final", {"oi_start": None}),
    ],
)
def test_oi_incompleto_no_se_mide_ni_suma_peso(caso: str, overrides: dict) -> None:
    out = compute_scalp_summary(ctx_completo(**overrides))
    assert out["oi_chg_15m_pct"] is None, caso
    assert "oi" in out["missing_components"], caso
    assert out["measured_weight"] == 100 - W_OI, caso
    assert out["evidence_coverage_pct"] == 90.0, caso


def test_oi_sin_variacion_real_si_se_mide() -> None:
    """OI medido dos veces con el mismo valor es un CERO real: cuenta y vale 0 %."""
    out = compute_scalp_summary(ctx_completo(oi_now=1_000.0, oi_start=1_000.0))
    assert out["oi_chg_15m_pct"] == 0.0
    assert "oi" not in out["missing_components"]
    assert out["measured_weight"] == 100.0


def test_oi_inicial_cero_no_divide_entre_cero() -> None:
    out = compute_scalp_summary(ctx_completo(oi_start=0.0))
    assert out["oi_chg_15m_pct"] is None
    assert "oi" in out["missing_components"]


# ---------------- VWAP ----------------


def test_vwap_ausente_no_es_precio_sobre_vwap() -> None:
    out = compute_scalp_summary(ctx_completo(session_vwap=None))
    assert out["vwap_dist_pct"] is None
    assert out["session_vwap"] is None
    assert "vwap" in out["missing_components"]
    assert out["measured_weight"] == 100 - W_VWAP


def test_precio_exactamente_sobre_vwap_publica_cero() -> None:
    out = compute_scalp_summary(ctx_completo(price=100.0, last_px_3m=100.0, session_vwap=100.0))
    assert out["vwap_dist_pct"] == 0.0
    assert "vwap" not in out["missing_components"]


# ---------------- liquidaciones ----------------


@pytest.mark.parametrize(
    ("caso", "overrides"),
    [
        ("sin_heartbeat", {"liq_feed_status": None, "liq_feed_lag_s": None}),
        ("heartbeat_en_error", {"liq_feed_status": "error"}),
        ("heartbeat_viejo", {"liq_feed_lag_s": 3_600.0}),
    ],
)
def test_liquidaciones_sin_ventana_medida_quedan_en_none(caso: str, overrides: dict) -> None:
    out = compute_scalp_summary(ctx_completo(**overrides))
    assert out["long_liq_5m"] is None, caso
    assert out["short_liq_5m"] is None, caso
    assert out["liquidations_measured"] is False, caso
    assert "liquidations" in out["missing_components"], caso
    assert out["measured_weight"] == 100 - W_LIQUIDATIONS, caso
    assert "liq S-L N/D" in out["reason"], caso


def test_ventana_medida_sin_eventos_conserva_el_cero_real() -> None:
    """Colector vivo y ninguna liquidacion = mercado en calma, no falta de dato."""
    out = compute_scalp_summary(ctx_completo(long_liq=None, short_liq=None))
    assert out["long_liq_5m"] == 0.0
    assert out["short_liq_5m"] == 0.0
    assert out["liquidations_measured"] is True
    assert "liquidations" not in out["missing_components"]
    assert out["measured_weight"] == 100.0
    assert "liq S-L 0" in out["reason"]


def test_liquidaciones_asimetricas_votan_con_su_signo() -> None:
    solo_shorts = compute_scalp_summary(ctx_completo(long_liq=None, short_liq=1_000_000.0))
    solo_longs = compute_scalp_summary(ctx_completo(long_liq=1_000_000.0, short_liq=None))
    assert solo_shorts["long_score"] > solo_longs["long_score"]


# ---------------- libro y absorcion ----------------


def test_libro_ausente_no_vota_neutral() -> None:
    out = compute_scalp_summary(ctx_completo(imbalance_l5=None))
    assert "book" in out["missing_components"]
    assert out["measured_weight"] == 100 - W_BOOK
    assert "/L5 N/D" in out["reason"]


def test_sin_precios_de_ventana_la_absorcion_no_se_evalua() -> None:
    out = compute_scalp_summary(ctx_completo(first_px_3m=None, last_px_3m=None, price=None))
    assert out["price_move_3m_pct"] is None
    assert out["absorption"] == "No evaluable"
    assert "absorption" in out["missing_components"]
    # Sin precio de 3 m caen absorcion y VWAP. El OI YA NO depende de la ventana de 3 m: su
    # signo lo pone el precio de 15 m (que sigue presente), asi que sigue votando. Comparar OI
    # de 15 m con precio de 3 m era justamente el error corregido.
    assert "oi" not in out["missing_components"]
    assert out["measured_weight"] == 100 - W_ABSORPTION - W_VWAP


# ---------------- combinaciones parciales ----------------


def test_combinacion_parcial_resta_exactamente_los_pesos_ausentes() -> None:
    out = compute_scalp_summary(
        ctx_completo(
            oi_now=None,
            session_vwap=None,
            liq_feed_status=None,
            liq_feed_lag_s=None,
        )
    )
    assert set(out["missing_components"]) == {"oi", "vwap", "liquidations"}
    esperado = 100 - W_OI - W_VWAP - W_LIQUIDATIONS
    assert out["measured_weight"] == esperado
    assert out["evidence_coverage_pct"] == float(esperado)


def test_bajo_el_50_por_ciento_de_peso_no_hay_lectura() -> None:
    out = compute_scalp_summary(
        {
            "book_status": "ok",
            "imbalance_l5": 0.6,
            "liq_feed_status": "ok",
            "liq_feed_lag_s": 2.0,
        }
    )
    assert out["evidence_coverage_pct"] < 50
    assert out["state"] == "Sin datos suficientes"


def test_contexto_vacio_no_publica_ningun_cero_fabricado() -> None:
    out = compute_scalp_summary({})
    for campo in (
        "long_liq_5m",
        "short_liq_5m",
        "oi_chg_15m_pct",
        "vwap_dist_pct",
        "session_vwap",
        "diff_3m",
        "price_move_3m_pct",
    ):
        assert out[campo] is None, campo
    assert out["evidence_coverage_pct"] == 0.0
    assert out["measured_weight"] == 0.0
    assert sorted(out["missing_components"]) == sorted(
        [
            "fut_delta",
            "spot_fut_divergence",
            "book",
            "absorption",
            "liquidations",
            "oi",
            "vwap",
        ]
    )


def test_los_componentes_ausentes_coinciden_con_missing_components() -> None:
    """`missing_components` no puede ser decorativo: debe cuadrar con el peso medido."""
    pesos = {
        "fut_delta": W_FUT_DELTA,
        "spot_fut_divergence": W_DIVERGENCE,
        "book": W_BOOK,
        "absorption": W_ABSORPTION,
        "liquidations": W_LIQUIDATIONS,
        "oi": W_OI,
        "vwap": W_VWAP,
    }
    for overrides in (
        {"oi_now": None},
        {"session_vwap": None},
        {"imbalance_l5": None},
        {"spot_delta_3m": None},
        {"fut_volume_1m": None},
        {"liq_feed_status": None},
    ):
        out = compute_scalp_summary(ctx_completo(**overrides))
        ausente = sum(pesos[name] for name in out["missing_components"])
        assert out["measured_weight"] == 100 - ausente, overrides
