from datetime import UTC, date, datetime

import pytest

from app.metrics import (
    SNAPSHOT_QUERY,
    compute_regime,
    compute_snapshot,
    current_nyse_start,
    session_bounds,
    whale_classification,
)


def test_current_nyse_start_before_open_uses_previous_calendar_day():
    # Crypto opera 24/7: lunes 08:00 ET -> domingo 09:30 ET, no viernes.
    now = datetime(2026, 6, 22, 12, 0, tzinfo=UTC)
    result = current_nyse_start(now)
    assert result == datetime(2026, 6, 21, 13, 30, tzinfo=UTC)


def test_current_nyse_start_does_not_merge_weekend_sessions():
    # Domingo 12:00 ET empieza el mismo domingo a las 09:30 ET.
    now = datetime(2026, 6, 21, 16, 0, tzinfo=UTC)
    assert current_nyse_start(now) == datetime(2026, 6, 21, 13, 30, tzinfo=UTC)


def test_session_bounds_follow_dst():
    start, end = session_bounds(date(2026, 3, 8))
    assert start < end
    # DST changed on March 8; calendar session is 23 hours in UTC.
    assert (end - start).total_seconds() == 23 * 3600


@pytest.mark.parametrize(
    ("buy", "sell", "asset", "expected_label", "sign"),
    [
        (5_000_000, 500_000, "ETH", "Acumulación agresiva", 1),
        (100_000, 900_000, "SOL", "Distribución agresiva", -1),
        (600_000, 400_000, "SOL", "Neutro", 1),
    ],
)
def test_whale_classification(buy, sell, asset, expected_label, sign):
    intensity, label = whale_classification(buy, sell, asset)
    assert label == expected_label
    assert (intensity > 0) - (intensity < 0) == sign


def test_whale_below_threshold_does_not_vote_zero():
    # K59: sin operaciones por encima del umbral no hay desequilibrio que medir. El 0.0
    # de antes hacia votar al componente de mas peso (30 de 100) contra la regla que
    # compute_regime documenta, y dejaba el score en 0.7 exacto del suyo.
    intensity, label = whale_classification(4_000_000, 500_000, "BTC")
    assert intensity is None
    assert label == "Sin operaciones spot de gran tamaño relevantes"


def test_whale_zero_with_real_activity_is_still_a_measurement():
    # CONTROL POSITIVO del arreglo: un delta EXACTAMENTE cero con actividad por encima
    # del umbral SI es una medicion, y tiene que seguir votando 0.0.
    intensity, label = whale_classification(500_000, 500_000, "SOL")
    assert intensity == 0.0
    assert label == "Neutro"


def test_absent_whale_stops_voting_and_renormalizes():
    base = {
        "cvd_spot_imbalance_24h": 0.4,
        "cvd_fut_imbalance_24h": 0.4,
        "oi_chg_24h_pct": 5.0,
        "fr_avg": 0.0,
        "long_liq_24h": 0.0,
        "short_liq_24h": 0.0,
    }
    votando_cero, _ = compute_regime({**base, "whale_intensity": 0.0})
    ausente, _ = compute_regime({**base, "whale_intensity": None})
    # Con el ausente votando cero, el peso medido es 100 y el score se diluye a 0.7 del
    # que manda la regla; sin el, se renormaliza sobre 70.
    # compute_regime redondea a 2 decimales: la tolerancia es la del propio productor.
    assert ausente == pytest.approx(votando_cero / 0.7, abs=0.01)
    assert ausente > votando_cero


def test_compute_regime_organic_bullish():
    score, label = compute_regime(
        {
            "vol_24h": 100_000_000,
            "cvd_diff_24h": 10_000_000,
            "cvd_spot_imbalance_24h": 0.4,
            "cvd_fut_imbalance_24h": 0.2,
            "oi_chg_24h_pct": 5,
            "fr_avg": -0.001,
            "liq_ratio_24h": 0,
            "whale_intensity": 1,
            "whale_label": "Acumulación agresiva",
        }
    )
    assert score > 60
    assert label == "Continuación alcista orgánica"


class _SnapshotConnection:
    def __init__(self) -> None:
        self.args = ()

    async def fetchrow(self, _query, *args):
        self.args = args
        return {
            "price": 100.0,
            "price_ts": datetime(2026, 8, 9, 12, 4, tzinfo=UTC),
            "price_1h": 99.0,
            "oi_now": 250.0,
            "oi_ts": datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
            "oi_old": 100.0,
        }

    async def fetch(self, _query, *_args):
        return []


async def test_snapshot_scoring_uses_separate_closed_price_and_oi_cutoffs():
    conn = _SnapshotConnection()
    now = datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC)

    snapshot = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)

    assert conn.args[3] == datetime(2026, 8, 9, 12, 5, tzinfo=UTC)
    assert conn.args[4] == datetime(2026, 8, 9, 12, 5, tzinfo=UTC)
    assert snapshot["price"] == 100.0
    assert snapshot["oi"] == 250.0
    assert snapshot["oi_chg_24h_pct"] == 150.0
    assert snapshot["price_cutoff_at"] == datetime(2026, 8, 9, 12, 4, tzinfo=UTC)
    assert snapshot["metrics_cutoff_at"] == datetime(2026, 8, 9, 12, 0, tzinfo=UTC)


def test_snapshot_query_has_strict_closed_upper_bounds():
    assert "ts < $4" in SNAPSHOT_QUERY
    assert SNAPSHOT_QUERY.count("ts < $5") >= 5
    assert "now() - interval '24 hours'" not in SNAPSHOT_QUERY
