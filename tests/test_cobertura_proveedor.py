"""Un hueco del proveedor no puede degradarnos a nosotros; que nos callemos, si.

Medido contra 140 el 2026-08-25: en 24 h la fuente devolvio 261 de 289 buckets de
long_short_ratio para SOLUSDT_PERP.A y 285 de 289 para BTCUSDT_PERP.A, y nuestra base
tenia EXACTAMENTE 261 y 285. Aceptamos el 100% de lo que llega. Aun asi,
ingest:metrics_5m llevaba semanas en 'degraded' por ese missing=29, y arrastraba a
/api/healthz entero: un indicador encendido por algo que nadie puede apagar.

Lo que estos tests fijan es la distincion, no el numero: se degrada por lo NUESTRO.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.data_gaps import CadenceCoverage
from app.ingest import _coverage_heartbeat_detail


def _cobertura(esperados: int, observados: int) -> CadenceCoverage:
    inicio = datetime(2026, 8, 25, tzinfo=UTC)
    return CadenceCoverage(
        start=inicio,
        end=inicio + timedelta(hours=24),
        cadence=timedelta(minutes=5),
        expected_buckets=esperados,
        observed_buckets=observados,
        missing_buckets=esperados - observados,
        missing_windows=(),
        recovered_gaps=0,
    )


def test_un_hueco_del_proveedor_no_nos_degrada() -> None:
    """El caso real: faltan 28 buckets de 289 y no rechazamos ni una fila."""
    estado, detalle = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 261},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 261))],
        rejected=0,
    )
    assert estado == "ok"
    # Pero el hueco NO se esconde: sigue publicado para quien lo quiera mirar.
    assert "missing=28" in detalle
    assert "rejected=0" in detalle


def test_si_tiramos_filas_que_la_fuente_mando_eso_si_degrada() -> None:
    estado, detalle = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 260},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 260))],
        rejected=1,
    )
    assert estado == "degraded"
    assert "rejected=1" in detalle


def test_una_fuente_que_se_calla_del_todo_degrada() -> None:
    """Sin esto el arreglo seria una tapadera: cero filas tambien da rejected=0."""
    estado, _ = _coverage_heartbeat_detail(
        feed="metrics_5m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows={"long_short": 0},
        coverages=[("long_short_ratio@binance:response24h", _cobertura(289, 0))],
        rejected=0,
    )
    assert estado == "degraded"


def test_sin_el_dato_de_rechazadas_se_mantiene_el_comportamiento_viejo() -> None:
    """ohlcv sigue llamando sin rejected: no se le cambia el criterio por la espalda."""
    estado, _ = _coverage_heartbeat_detail(
        feed="ohlcv_1m",
        cutoff=datetime(2026, 8, 25, tzinfo=UTC),
        rows=100,
        coverages=[("ohlcv@binance:response24h", _cobertura(289, 261))],
    )
    assert estado == "degraded"
