"""Regresiones de la auditoria v1.3.1.

/metrics devolvia 500 (KeyError: 'detail') porque prometheus_metrics leia una columna
que su propio SELECT no pedia. El smoke test no cubria /metrics, asi que paso inadvertido
durante varias versiones. Estos tests ejercitan el endpoint de verdad, no su texto.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import api
from app.scalp_logic import classify_absorption

ROOT = Path(__file__).resolve().parents[1]


class FakeRecord(dict):
    """dict lanza KeyError igual que asyncpg.Record ante una columna no pedida."""


class FakeConnection:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def fetch(self, query: str, *_args: object) -> list[FakeRecord]:
        self.queries.append(query)
        if "pipeline_heartbeat" in query:
            row = {"service": "scalp", "status": "ok", "lag_seconds": 1.0}
            # Solo se expone lo que el SELECT realmente pide.
            if "detail" in query:
                row["detail"] = "liq_dropped:3,trade_buckets_rt:12,binance_reconnects:7"
            return [FakeRecord(row)]
        if "metrics_snapshot" in query:
            return [FakeRecord({"symbol": "BTCUSDT_PERP.A", "lag_seconds": 2.0})]
        return [FakeRecord({"table_name": "futures_trades_realtime", "rows": 10})]


class FakePool:
    def __init__(self) -> None:
        self.conn = FakeConnection()

    def acquire(self):
        pool = self

        class Ctx:
            async def __aenter__(self):
                return pool.conn

            async def __aexit__(self, *_exc: object) -> None:
                return None

        return Ctx()


@pytest.mark.asyncio
async def test_prometheus_metrics_renders_scalp_runtime_values(monkeypatch: pytest.MonkeyPatch) -> None:
    pool = FakePool()
    monkeypatch.setattr(api.app.state, "pool", pool, raising=False)
    monkeypatch.setattr(api.SETTINGS, "METRICS_ENABLED", True)

    response = await api.prometheus_metrics()
    body = response.body.decode()

    assert response.status_code == 200
    assert 'coinalyze_heartbeat_lag_seconds{service="scalp"} 1.000' in body
    assert 'coinalyze_service_ok{service="scalp"} 1' in body
    assert 'coinalyze_symbol_snapshot_lag_seconds{symbol="BTCUSDT_PERP.A"} 2.000' in body
    assert 'coinalyze_table_rows{table="futures_trades_realtime"} 10' in body
    # Estas solo aparecen si el detail del heartbeat llego hasta el render.
    assert "coinalyze_scalp_liquidations_dropped_total 3" in body
    assert "coinalyze_scalp_tradestore_realtime_buckets 12" in body
    assert "coinalyze_scalp_binance_book_reconnect_total 7" in body


def test_lag_columns_are_cast_to_float8_so_json_stays_numeric() -> None:
    """EXTRACT(EPOCH ...) devuelve numeric -> asyncpg da Decimal -> el JSON sale como string."""
    for name in ("app/api.py", "app/ai_context.py", "app/scalp_logic.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        for line in source.splitlines():
            upper = line.upper()
            if "EXTRACT(EPOCH" in upper and " AS " in upper:
                assert "::float8" in line, f"{name}: falta cast ::float8 en {line.strip()}"


@pytest.mark.parametrize(
    ("delta", "move", "volume", "expected_score", "expected_label"),
    [
        (0.0, 0.0, 1_000.0, 0.0, "Neutra"),
        (None, 1.0, 1_000.0, 0.0, "Neutra"),
        # El delta pesa el 20% del volumen: por encima de ABSORPTION_MIN_RATIO.
        (1_000.0, 0.01, 5_000.0, -1.0, "Absorción de compras"),
        (-1_000.0, -0.01, 5_000.0, 1.0, "Absorción de ventas"),
        (1_000.0, -0.5, 5_000.0, -1.0, "Absorción fuerte de compras"),
        (-1_000.0, 0.5, 5_000.0, 1.0, "Absorción fuerte de ventas"),
        (1_000.0, 0.5, 5_000.0, 0.0, "Neutra"),
        # Sin volumen la magnitud no se puede juzgar: no se inventa una lectura.
        (1_000.0, 0.01, None, 0.0, "Sin datos"),
        (1_000.0, 0.01, 0.0, 0.0, "Sin datos"),
    ],
)
def test_classify_absorption(delta, move, volume, expected_score, expected_label) -> None:
    score, label = classify_absorption(delta, move, volume)
    assert (score, label) == (expected_score, expected_label)


@pytest.mark.parametrize("move", [0.01, -0.5, 0.5])
def test_absorption_requires_meaningful_magnitude(move) -> None:
    """1 USD de delta neto sobre 10M de volumen es ruido de redondeo, no absorcion.

    Antes bastaba con que delta y precio tuvieran signos opuestos para publicar
    "Absorcion fuerte", sin mirar cuanto pesaba ese delta.
    """
    score, label = classify_absorption(1.0, move, 10_000_000.0)
    assert (score, label) == (0.0, "Sin señal")


def test_absorption_has_a_single_definition() -> None:
    """El endpoint y el resumen de scalp usaban umbrales distintos (0.02 vs 0.04).

    Desde P2 el umbral ya no es una constante compartida sino el p75 MEDIDO de cada ventana
    (`metric_baseline`). Lo que hay que fijar es que ninguna de las dos rutas se quede con un
    literal: ambas tienen que leer la baseline.
    """
    api_source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    logic_source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    # Se fija el CONTRATO, no el formato exacto de la llamada: ambas rutas tienen que leer
    # el p75 de la baseline y ninguna puede clasificar sin delta y sin movimiento medidos.
    assert "classify_absorption(" in api_source
    assert '(baseline or {}).get("p75")' in api_source
    assert "if delta is None or move is None:" in api_source
    assert '(baseline_3m or {}).get("p75"),' in logic_source
    assert "if price_move_3m is None:" in logic_source
    assert logic_source.count("Absorción fuerte de compras") == 1
    assert "0.02" not in api_source.split("scalp_absorption")[1].split("@app.get")[1]
    # La constante sigue existiendo SOLO como fallback declarado, definida una vez.
    assert logic_source.count("ABSORPTION_MIN_RATIO = ") == 1
    assert "FALLBACK" in logic_source.split("ABSORPTION_MIN_RATIO = ")[1][:200]


def test_trend_matrix_oi_window_matches_the_timeframe() -> None:
    """1d/3d median el OI sobre n sesiones, no sobre toda la ventana cargada."""
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    start = source.index("async def trend_matrix")
    body = source[start:source.index("def compute_swing_score", start)]
    assert "daily[-n_back - 1][\"oi_close\"]" in body
    assert 'ds[0]["oi_close"]' not in body


def test_smoke_test_covers_metrics_and_a_symbol_endpoint() -> None:
    source = (ROOT / "scripts" / "smoke_test.sh").read_text(encoding="utf-8")
    assert "$BASE_URL/metrics" in source
    assert "/api/dashboard/state" in source


def test_update_refuses_an_incomplete_source_tree() -> None:
    """rsync --delete con un paquete solo-app borraba sql/, scripts/ y deploy/."""
    source = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")
    guard = source.split("rsync -a --delete")[0]
    assert "REQUIRED_PATHS=(" in guard
    for path in ("requirements.lock", "sql/schema.sql", "scripts/backup.sh", "scripts/update.sh"):
        assert path in guard
    assert "Directorio fuente incompleto" in guard
    # el historico local de despliegues no vive en el repo: --delete lo borraria
    assert "--exclude '.deploy-backups'" in source


def test_vendor_checksums_are_verifiable_from_the_repo() -> None:
    """SHA256SUMS traia la ruta absoluta de la maquina de build; no verificaba nada."""
    sums = (ROOT / "static" / "vendor" / "SHA256SUMS").read_text(encoding="utf-8")
    for line in sums.splitlines():
        if not line.strip():
            continue
        name = line.split(maxsplit=1)[1].lstrip("*")
        assert not name.startswith("/"), f"ruta absoluta en SHA256SUMS: {name}"
        assert (ROOT / "static" / "vendor" / name).is_file()
