"""v1.5.0 — la pestaña Calidad separa servicios, feeds y métricas."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.scalp_logic import (
    FEED_DEFINITIONS,
    GAP_MEASURABLE_TABLES,
    _feed_status,
    _liquidation_feed_quality_status,
    feed_quality,
    max_internal_gap,
    metric_quality,
)

RAIZ = Path(__file__).resolve().parent.parent
HTML = (RAIZ / "static" / "index.html").read_text(encoding="utf-8")
JS = (RAIZ / "static" / "app.js").read_text(encoding="utf-8")

SECCION = HTML.split('<section id="calidad"')[1].split("</section>\n\n      <section")[0]


# ---------------- separacion de los tres niveles ----------------


def test_la_pestana_separa_servicios_feeds_y_metricas() -> None:
    for titulo in ("Salud de servicios", "Calidad de feeds", "Calidad por métrica"):
        assert titulo in SECCION, titulo
    for cuerpo in ('id="quality-body"', 'id="feeds-body"', 'id="metrics-quality-body"'):
        assert cuerpo in SECCION, cuerpo


def test_fuentes_de_datos_ya_no_titula_procesos_internos() -> None:
    """El titulo solo puede usarse para feeds reales; los procesos son otra cosa.

    Se comprueba sobre los ENCABEZADOS, no sobre el texto suelto: el comentario que explica
    por que se retiro el titulo tiene que poder nombrarlo.
    """
    assert "<h3>Fuentes de datos</h3>" not in HTML
    assert "<h3>Salud de servicios</h3>" in SECCION


def test_la_tabla_de_feeds_declara_los_campos_pedidos() -> None:
    cabeceras = (
        "Exchange", "Mercado", "Símbolo", "Tipo de dato", "Estado", "Último ts",
        "Latencia", "Cobertura", "Muestras", "Esperadas", "Hueco int.",
        "Fuentes ausentes", "Último error",
    )
    for cabecera in cabeceras:
        assert f"<th>{cabecera}</th>" in SECCION, cabecera


def test_solo_se_mide_hueco_donde_max_internal_gap_lo_acepta() -> None:
    """Cazado en producción: `feed_quality` decidía por el sufijo `_realtime` y llamaba a
    `max_internal_gap` con `liquidations_realtime`, que la función rechaza con ValueError.
    El endpoint entero devolvía 500. La lista blanca tiene que coincidir con la de la
    función, y además dejar fuera el feed de eventos por diseño.
    """
    fuente = inspect.getsource(max_internal_gap)
    for tabla in GAP_MEASURABLE_TABLES:
        assert tabla in fuente, tabla
    assert "liquidations_realtime" not in GAP_MEASURABLE_TABLES
    # Y ninguna definición de feed fuera de esa lista puede acabar pidiendo el hueco.
    tablas_evento = {
        d["table"] for d in FEED_DEFINITIONS if d["table"] not in GAP_MEASURABLE_TABLES
    }
    assert "liquidations_realtime" in tablas_evento
    cuerpo = inspect.getsource(feed_quality)
    assert "GAP_MEASURABLE_TABLES" in cuerpo
    assert "endswith" not in cuerpo, "volver al sufijo reintroduce el fallo"


def test_los_feeds_definidos_son_de_mercado_no_procesos() -> None:
    nombres = {d["feed"] for d in FEED_DEFINITIONS}
    assert nombres == {
        "ohlcv_1min", "open_interest_5min", "funding_rate",
        "futures_trades", "spot_trades", "liquidations", "orderbook",
    }
    for definicion in FEED_DEFINITIONS:
        assert definicion["market"] in {"spot", "perpetuo"}
        assert definicion["exchanges"], definicion["feed"]
        assert definicion["collector"] in {"ingest", "ws", "scalp", "daily"}


# ---------------- el estado no confunde calma con caida ----------------


def _hb(status: str = "ok", lag: float = 2.0, detail: str | None = None) -> dict:
    return {"ws": (status, lag, detail), "ingest": (status, lag, detail),
            "scalp": (status, lag, detail)}


LIQUIDACIONES = next(d for d in FEED_DEFINITIONS if d["feed"] == "liquidations")
OHLCV = next(d for d in FEED_DEFINITIONS if d["feed"] == "ohlcv_1min")


def test_un_feed_de_eventos_sin_eventos_no_es_un_feed_caido() -> None:
    """Liquidaciones: colector vivo y cero eventos es CALMA, no fallo."""
    estado, _ = _feed_status(LIQUIDACIONES, _hb(), latencia=3600.0, muestras=0, ausentes=[])
    assert estado == "OK"


def test_calidad_de_liquidaciones_exige_continuidad_de_toda_la_ventana() -> None:
    now = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    complete = {
        exchange: {
            "status": "ok",
            "healthy_since": now - timedelta(minutes=20),
            "last_loss_at": now - timedelta(minutes=20),
            "updated_at": now - timedelta(seconds=10),
            "detail": None,
        }
        for exchange in ("binance", "bybit")
    }
    assert _liquidation_feed_quality_status(
        complete,
        ("binance", "bybit"),
        now,
        900,
    ) == ("OK", None)

    reconnected = {exchange: dict(row) for exchange, row in complete.items()}
    reconnected["bybit"]["healthy_since"] = now - timedelta(minutes=2)
    status, detail = _liquidation_feed_quality_status(
        reconnected,
        ("binance", "bybit"),
        now,
        900,
    )
    assert status == "PARTIAL"
    assert "reconectó" in str(detail)

    lost = {exchange: dict(row) for exchange, row in complete.items()}
    lost["binance"]["last_loss_at"] = now - timedelta(minutes=1)
    status, detail = _liquidation_feed_quality_status(
        lost,
        ("binance", "bybit"),
        now,
        900,
    )
    assert status == "PARTIAL"
    assert "pérdida" in str(detail)


def test_un_feed_continuo_sin_registros_si_esta_stale() -> None:
    estado, motivo = _feed_status(OHLCV, _hb(), latencia=None, muestras=0, ausentes=None)
    assert estado == "STALE"
    assert "sin registros" in motivo


def test_el_colector_caido_manda_sobre_todo_lo_demas() -> None:
    estado, motivo = _feed_status(
        OHLCV, _hb(status="error", detail="conexión perdida"), latencia=1.0, muestras=15, ausentes=None
    )
    assert estado == "DOWN"
    assert motivo == "conexión perdida"


def test_sin_heartbeat_el_feed_es_unavailable_no_ok() -> None:
    estado, motivo = _feed_status(OHLCV, {}, latencia=1.0, muestras=15, ausentes=None)
    assert estado == "UNAVAILABLE"
    assert "sin heartbeat" in motivo


def test_un_venue_ausente_degrada_a_parcial() -> None:
    estado, motivo = _feed_status(
        LIQUIDACIONES, _hb(), latencia=5.0, muestras=10, ausentes=["bybit"]
    )
    assert estado == "PARTIAL"
    assert "bybit" in motivo


# ---------------- calidad por metrica ----------------


MATRIZ = [
    {"window": "5m", "spot_delta": 100.0, "fut_delta": 900.0, "coverage_status": "complete",
     "spot_source": "spot_trades_realtime", "spot_end_gap_seconds": 4.0},
    {"window": "1h", "spot_delta": None, "fut_delta": 5000.0, "coverage_status": "partial",
     "spot_source": "spot_trades_agg", "spot_end_gap_seconds": 260.0},
]
SCALP = {
    "basis_status": "STALE", "basis_bps": None, "basis_detail": {"max_age_seconds": 42.0},
    "oi_chg_15m_pct": None, "book_status": "ok", "imbalance_l5": 0.55,
    "book_lag_seconds": 1.2,
}
FEEDS = {"feeds": [
    {"feed": "open_interest_5min", "exchange": "binance", "coverage_pct": 100.0, "latency_seconds": 30.0},
    {"feed": "funding_rate", "exchange": "binance", "status": "OK", "coverage_pct": None,
     "latency_seconds": 900.0},
    {"feed": "orderbook", "exchange": "binance + bybit"},
]}


@pytest.fixture()
def metricas() -> dict:
    return {m["metric"]: m for m in metric_quality(MATRIZ, SCALP, FEEDS)["metrics"]}


def test_estan_las_metricas_que_pide_el_prompt(metricas: dict) -> None:
    for nombre in ("Delta spot", "Delta futuros", "CVD futuros", "Basis perp-spot",
                   "Open interest", "Funding", "Order book"):
        assert nombre in metricas, nombre


def test_una_ventana_completa_y_otra_parcial_no_se_publican_igual(metricas: dict) -> None:
    assert metricas["Delta spot"]["status"] == "OK"
    assert metricas["Delta spot"]["timeframe"] == "5m"
    assert metricas["CVD futuros"]["status"] == "PARTIAL"


def test_el_basis_reutiliza_su_propio_semaforo(metricas: dict) -> None:
    """Su estado depende de la EDAD de cada pata, no de que las dos existan."""
    assert metricas["Basis perp-spot"]["status"] == "STALE"
    assert metricas["Basis perp-spot"]["value"] is None


def test_una_metrica_sin_dato_es_unavailable_y_no_cero(metricas: dict) -> None:
    oi = metricas["Open interest"]
    assert oi["status"] == "UNAVAILABLE"
    assert oi["value"] is None


def test_ninguna_metrica_publica_cero_por_ausencia(metricas: dict) -> None:
    for nombre, m in metricas.items():
        if m["status"] in ("UNAVAILABLE", "STALE"):
            assert m["value"] is None, nombre


# ---------------- el frontend dice N/D, no cero ----------------


def test_el_frontend_no_pinta_cero_donde_no_hay_dato() -> None:
    bloque = JS[JS.index("function renderFeedQuality"):JS.index("function renderReplay")]
    assert "'N/D'" in bloque
    # Cobertura ausente se declara; no se sustituye por 0%.
    assert "cob === null ? 'N/D'" in bloque
    assert "lat === null ? 'N/D'" in bloque


def test_una_latencia_desconocida_no_se_pinta_sana() -> None:
    bloque = JS[JS.index("function renderQuality"):JS.index("function renderFeedQuality")]
    assert "lag === null || lag > 120" in bloque
