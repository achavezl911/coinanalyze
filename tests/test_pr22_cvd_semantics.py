from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app import api, scalp_logic
from app.ai_context import DAILY_HISTORY_QUERY, daily_data, daily_history
from app.metrics import (
    REGIME_LOGIC_VERSION,
    SNAPSHOT_QUERY,
    compute_regime,
    insert_snapshot,
    normalized_cvd_imbalance,
    regime_cvd_component,
)
from app.signal_ledger import SIGNAL_EVIDENCE_VERSION


def _regime_score(spot: float, futures: float, raw_diff: float) -> float:
    score, _ = compute_regime(
        {
            "cvd_spot_imbalance_24h": spot,
            "cvd_fut_imbalance_24h": futures,
            "cvd_diff_24h": raw_diff,
            "whale_intensity": 0.0,
            "whale_label": "Neutro",
        }
    )
    assert score is not None
    return score


def test_pr22_regime_uses_normalized_same_window_imbalances() -> None:
    snap = {
        "cvd_spot_imbalance_24h": 0.2,
        "cvd_fut_imbalance_24h": 0.4,
    }
    assert regime_cvd_component(snap) == pytest.approx(0.3)
    assert "SUM(buy_vol_usd + sell_vol_usd)" in SNAPSHOT_QUERY
    assert "exchange = 'combined' AND venue_count = 2" in SNAPSHOT_QUERY


def test_pr22_both_markets_buy_cannot_be_bearish_due_to_raw_notional_scale() -> None:
    spot_net = 10_047.0
    futures_net = 8_152_135.0
    spot = normalized_cvd_imbalance(spot_net, 100_470.0)
    futures = normalized_cvd_imbalance(futures_net, 81_521_350.0)
    assert spot is not None and futures is not None
    assert spot_net - futures_net < 0
    assert regime_cvd_component(
        {
            "cvd_spot_imbalance_24h": spot,
            "cvd_fut_imbalance_24h": futures,
        }
    ) > 0
    assert _regime_score(spot, futures, spot_net - futures_net) > 0


def test_pr22_both_markets_sell_produces_negative_cvd_component() -> None:
    assert regime_cvd_component(
        {
            "cvd_spot_imbalance_24h": -0.25,
            "cvd_fut_imbalance_24h": -0.5,
        }
    ) == pytest.approx(-0.375)
    assert _regime_score(-0.25, -0.5, 9_000_000.0) < 0


def test_pr22_conflicting_normalized_legs_are_combined_without_raw_notional_dominance() -> None:
    assert regime_cvd_component(
        {
            "cvd_spot_imbalance_24h": 0.8,
            "cvd_fut_imbalance_24h": -0.2,
        }
    ) == pytest.approx(0.3)
    assert _regime_score(0.8, -0.2, -1_000_000_000.0) > 0


def test_pr22_missing_spot_gross_makes_cvd_component_unavailable() -> None:
    assert normalized_cvd_imbalance(10.0, None) is None
    assert regime_cvd_component(
        {"cvd_spot_imbalance_24h": None, "cvd_fut_imbalance_24h": 0.1}
    ) is None


def test_pr22_missing_futures_gross_makes_cvd_component_unavailable() -> None:
    assert normalized_cvd_imbalance(10.0, None) is None
    assert regime_cvd_component(
        {"cvd_spot_imbalance_24h": 0.1, "cvd_fut_imbalance_24h": None}
    ) is None


def test_pr22_zero_gross_does_not_become_neutral_evidence() -> None:
    assert normalized_cvd_imbalance(0.0, 0.0) is None


def test_pr22_raw_cvd_diff_remains_backward_compatible_but_does_not_drive_regime() -> None:
    positive_raw = _regime_score(0.2, 0.4, 1_000_000_000.0)
    negative_raw = _regime_score(0.2, 0.4, -1_000_000_000.0)
    assert positive_raw == negative_raw
    assert "cvd_diff_24h" in SNAPSHOT_QUERY or "cvd_24h" in SNAPSHOT_QUERY


@pytest.mark.asyncio
async def test_pr22_new_metrics_snapshot_has_regime_logic_version_2() -> None:
    class Connection:
        query = ""
        args: tuple[Any, ...] = ()

        async def execute(self, query: str, *args: Any) -> str:
            self.query = query
            self.args = args
            return "INSERT 0 1"

    snap = {
        key: None
        for key in (
            "price",
            "oi",
            "oi_chg_24h_pct",
            "oi_vol_24h_ratio",
            "vol_24h",
            "delta_3min",
            "cvd_session",
            "cvd_nyse_session",
            "cvd_spot_24h",
            "cvd_spot_session",
            "oi_bybit",
            "liq_ratio_24h",
            "cvd_diff_24h",
            "cvd_diff_ses",
            "fr_avg",
            "pfr_avg",
            "long_liq_24h",
            "short_liq_24h",
            "whale_intensity",
            "regime_score",
            "price_dir_1h",
            "btr_15m",
            "btr_1h",
            "btr_24h",
            "pfr_fr_div",
            "price_cutoff_at",
            "metrics_cutoff_at",
            "spot_vol_24h",
            "cvd_spot_imbalance_24h",
            "cvd_fut_imbalance_24h",
        )
    }
    snap.update(
        symbol="BTCUSDT_PERP.A",
        whale_label="Sin datos",
        regime_label="Sin datos suficientes",
        regime_logic_version=REGIME_LOGIC_VERSION,
    )
    conn = Connection()
    await insert_snapshot(conn, snap)  # type: ignore[arg-type]
    assert "regime_logic_version" in conn.query
    assert conn.args[-1] == 2


def test_pr22_new_signal_observation_has_evidence_version_3() -> None:
    assert SIGNAL_EVIDENCE_VERSION == 3


class _NoopConnection:
    pass


async def _delta_rows(
    monkeypatch: pytest.MonkeyPatch,
    *,
    spot_volume: float | None = 6_000.0,
    futures_volume: float | None = 12_000.0,
    futures_complete: bool = True,
) -> tuple[list[dict[str, Any]], datetime, list[datetime]]:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    seen: list[datetime] = []
    windows = [("30s", 30), ("1m", 60)]

    async def fake_spot(_conn, _symbol, requested, as_of=None):
        seen.append(as_of)
        return {
            label: {
                "combined": {
                    "delta": 600.0 * (seconds / 60),
                    "volume": (
                        spot_volume * (seconds / 60)
                        if spot_volume is not None
                        else None
                    ),
                    "trades": 10,
                    "source_rows": 10,
                    "source": "agg_1min+realtime",
                    "complete": True,
                    "coverage_status": "complete",
                    "end_gap_seconds": 5.0,
                }
            }
            for label, seconds in requested
        }

    async def fake_futures(_conn, _table, _symbol, seconds, as_of=None):
        seen.append(as_of)
        return {
            "delta": 1_200.0 * (seconds / 60),
            "volume": (
                futures_volume * (seconds / 60)
                if futures_volume is not None
                else None
            ),
            "trades": 20,
            "source_rows": 20,
            "complete": futures_complete,
            "coverage_status": "complete" if futures_complete else "unavailable",
            "end_gap_seconds": 5.0,
            "max_gap_seconds": 5.0,
        }

    async def fake_oi(_conn, _symbol, _seconds, as_of=None):
        seen.append(as_of)
        return None

    async def fake_baselines(_conn, _symbol):
        return {}

    monkeypatch.setattr(scalp_logic, "spot_flow_windows", fake_spot)
    monkeypatch.setattr(scalp_logic, "_realtime_flow", fake_futures)
    monkeypatch.setattr(scalp_logic, "_oi_change_pct", fake_oi)
    monkeypatch.setattr(scalp_logic, "load_baselines", fake_baselines)
    rows = await scalp_logic.delta_matrix(
        _NoopConnection(), "BTCUSDT_PERP.A", windows, cutoff  # type: ignore[arg-type]
    )
    return rows, cutoff, seen


@pytest.mark.asyncio
async def test_pr22_delta_matrix_uses_one_as_of_for_all_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, cutoff, seen = await _delta_rows(monkeypatch)
    assert seen and set(seen) == {cutoff}
    assert {row["as_of"] for row in rows} == {cutoff.isoformat()}


@pytest.mark.asyncio
async def test_pr22_constant_flow_has_equal_net_rate_across_nested_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch)
    assert {row["spot_net_rate_usd_per_min"] for row in rows} == {600.0}
    assert {row["fut_net_rate_usd_per_min"] for row in rows} == {1_200.0}


@pytest.mark.asyncio
async def test_pr22_constant_flow_does_not_publish_acceleration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch)
    assert all(row["acceleration_measured"] is False for row in rows)
    assert all("acceleration" not in row for row in rows)


@pytest.mark.asyncio
async def test_pr22_normalized_imbalance_is_window_comparable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch)
    assert {row["spot_imbalance"] for row in rows} == {0.1}
    assert {row["fut_imbalance"] for row in rows} == {0.1}


@pytest.mark.asyncio
async def test_pr22_zero_gross_keeps_imbalance_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch, spot_volume=0.0)
    assert all(row["spot_imbalance"] is None for row in rows)


@pytest.mark.asyncio
async def test_pr22_missing_source_keeps_normalized_fields_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch, futures_complete=False)
    assert all(row["fut_delta"] is None for row in rows)
    assert all(row["fut_imbalance"] is None for row in rows)
    assert all(row["fut_net_rate_usd_per_min"] is None for row in rows)


@pytest.mark.asyncio
async def test_pr22_raw_fields_keep_original_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch)
    one_minute = next(row for row in rows if row["window"] == "1m")
    assert one_minute["spot_delta"] == 600.0
    assert one_minute["fut_delta"] == 1_200.0
    assert one_minute["diff"] == -600.0


@pytest.mark.asyncio
async def test_pr22_nested_window_metadata_marks_non_independence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, _, _ = await _delta_rows(monkeypatch)
    assert all(row["window_type"] == "rolling" for row in rows)
    assert all(row["windows_are_nested"] is True for row in rows)
    assert all(row["independent_confirmations"] is False for row in rows)


@pytest.mark.asyncio
async def test_pr22_cvd_matrix_uses_one_as_of_for_all_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    seen: list[datetime] = []

    async def fake_cvd(_conn, _table, _symbol, _is_agg, as_of=None):
        seen.append(as_of)
        values = {
            exchange: {
                label: {"delta": seconds * 2.0, "volume": seconds * 10.0, "n": 1}
                for label, seconds in scalp_logic._CVD_WINDOWS
            }
            for exchange in ("combined", "binance", "bybit")
        }
        return values, cutoff - timedelta(days=8), cutoff - timedelta(seconds=5)

    async def fake_spot(_conn, _symbol, windows, as_of=None):
        seen.append(as_of)
        return {
            label: {
                exchange: {
                    "delta": seconds,
                    "volume": seconds * 10.0,
                    "source_rows": 1,
                    "complete": True,
                    "source": "realtime",
                    "end_gap_seconds": 5.0,
                    "precision_seconds": 1,
                }
                for exchange in ("combined", "binance", "bybit")
            }
            for label, seconds in windows
        }

    async def no_gaps(_conn, requirements):
        assert {requirement.end for requirement in requirements} == {cutoff}
        return set()

    monkeypatch.setattr(scalp_logic, "_cvd_src", fake_cvd)
    monkeypatch.setattr(scalp_logic, "spot_flow_windows", fake_spot)
    monkeypatch.setattr(scalp_logic, "blocking_requirement_keys", no_gaps)
    result = await scalp_logic.cvd_matrix(
        _NoopConnection(), "BTCUSDT_PERP.A", cutoff  # type: ignore[arg-type]
    )
    assert seen and set(seen) == {cutoff}
    assert result["as_of"] == cutoff.isoformat()
    assert result["window_meta"]["as_of"] == cutoff.isoformat()
    assert result["window_meta"]["acceleration_measured"] is False
    one_minute = result["windows"]["1m"]
    assert one_minute["spot_imbalance"] == pytest.approx(0.1)
    assert one_minute["fut_imbalance"] == pytest.approx(0.2)
    assert one_minute["spot_net_rate_usd_per_min"] == pytest.approx(60.0)
    assert one_minute["fut_net_rate_usd_per_min"] == pytest.approx(120.0)


class _RealtimeQueryConnection:
    def __init__(self) -> None:
        self.query = ""
        self.args: tuple[Any, ...] = ()

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any]:
        self.query = query
        self.args = args
        return {
            "delta": 10.0,
            "volume": 100.0,
            "trades": 1,
            "source_rows": 1,
            "lo": args[2] - timedelta(seconds=args[1]),
            "hi": args[2] - timedelta(seconds=1),
            "span_ok": True,
            "end_gap_seconds": 1.0,
        }


@pytest.mark.asyncio
async def test_pr22_trade_after_as_of_is_excluded_from_every_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conn = _RealtimeQueryConnection()

    async def no_gaps(_conn, _requirements):
        return set()

    async def no_internal_gap(*_args, **_kwargs):
        return 1.0

    monkeypatch.setattr(scalp_logic, "blocking_requirement_keys", no_gaps)
    monkeypatch.setattr(scalp_logic, "max_internal_gap", no_internal_gap)
    await scalp_logic._realtime_flow(
        conn, "futures_trades_realtime", "BTCUSDT_PERP.A", 60, cutoff  # type: ignore[arg-type]
    )
    assert "ts <= $3::timestamptz" in conn.query
    assert conn.args[2] == cutoff


@pytest.mark.asyncio
async def test_pr22_trade_before_as_of_is_consistent_across_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows, cutoff, _ = await _delta_rows(monkeypatch)
    assert len(rows) == 2
    assert all(row["as_of"] == cutoff.isoformat() for row in rows)
    assert rows[0]["spot_net_rate_usd_per_min"] == rows[1]["spot_net_rate_usd_per_min"]


@pytest.mark.asyncio
async def test_pr22_gap_requirements_use_same_as_of(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    conn = _RealtimeQueryConnection()
    captured = []
    gap_cutoffs = []

    async def capture_gaps(_conn, requirements):
        captured.extend(requirements)
        return set()

    async def capture_internal_gap(_conn, _table, _symbol, _exchange, _seconds, as_of=None):
        gap_cutoffs.append(as_of)
        return 1.0

    monkeypatch.setattr(scalp_logic, "blocking_requirement_keys", capture_gaps)
    monkeypatch.setattr(scalp_logic, "max_internal_gap", capture_internal_gap)
    await scalp_logic._realtime_flow(
        conn, "futures_trades_realtime", "BTCUSDT_PERP.A", 60, cutoff  # type: ignore[arg-type]
    )
    assert {requirement.end for requirement in captured} == {cutoff}
    assert gap_cutoffs == [cutoff]


@pytest.mark.asyncio
async def test_pr22_api_exposes_effective_matrix_as_of(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

    class Pool:
        def acquire(self):
            class Context:
                async def __aenter__(self):
                    return _NoopConnection()

                async def __aexit__(self, *_args):
                    return False

            return Context()

    async def fixed_as_of(_conn, as_of=None):
        return cutoff

    async def fake_delta(_conn, _symbol, windows, as_of=None):
        assert as_of == cutoff
        return [{"window": windows[0][0], "as_of": as_of.isoformat()}]

    monkeypatch.setattr(api.app.state, "pool", Pool(), raising=False)
    monkeypatch.setattr(api, "resolve_matrix_as_of", fixed_as_of)
    monkeypatch.setattr(api, "delta_matrix", fake_delta)
    result = await api.scalp_delta_matrix("BTCUSDT_PERP.A")
    assert result[0]["as_of"] == cutoff.isoformat()


class _DailyConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query = ""

    async def fetch(self, query: str, *_args: Any) -> list[dict[str, Any]]:
        self.query = query
        return self.rows


def _daily_row(
    day: int,
    *,
    spot: float | None,
    futures: float | None,
    price_change: float | None,
    cum_spot: float | None,
    flow_direction: str,
) -> dict[str, Any]:
    return {
        "session_date": date(2026, 8, day),
        "price_open": 100.0 if price_change is not None else None,
        "price_close": (100.0 + price_change) if price_change is not None else None,
        "price_chg_pct": price_change,
        "cvd_spot_usd": spot,
        "cvd_fut_usd": futures,
        "cvd_diff_usd": (
            spot - futures if spot is not None and futures is not None else None
        ),
        "cvd_fut_2v_usd": None,
        "cvd_diff_2v_usd": None,
        "oi_close": None,
        "oi_chg_usd": None,
        "fr_avg": None,
        "volume_usd": None,
        "long_liq_usd": None,
        "short_liq_usd": None,
        "cum_spot": cum_spot,
        "cum_fut": None,
        "cum_diff": None,
        "pct_spot": None,
        "pct_diff": None,
        "pct_ret": None,
        "flow_direction": flow_direction,
    }


@pytest.mark.asyncio
async def test_pr22_ai_daily_cumulative_breaks_on_null_gap() -> None:
    conn = _DailyConnection([])
    await daily_data(conn, "BTCUSDT_PERP.A", 30)
    assert "PARTITION BY diff_gap_group" in conn.query
    assert "PARTITION BY spot_gap_group" in conn.query
    assert "CASE WHEN cvd_spot_usd IS NULL THEN NULL" in conn.query


@pytest.mark.asyncio
async def test_pr22_ai_daily_missing_cvd_is_not_zero() -> None:
    rows = [
        _daily_row(1, spot=10.0, futures=20.0, price_change=1.0, cum_spot=10.0, flow_direction="opuestos"),
        _daily_row(2, spot=None, futures=5.0, price_change=1.0, cum_spot=None, flow_direction="sin_dato"),
    ]
    result = await daily_history(_DailyConnection(rows), "BTCUSDT_PERP.A", 2)
    assert result["totals"]["cvd_spot_usd"] is None
    assert result["series"][1]["cvd_spot_usd"] is None


@pytest.mark.asyncio
async def test_pr22_ai_daily_missing_spot_is_not_selling() -> None:
    rows = [
        _daily_row(1, spot=10.0, futures=20.0, price_change=1.0, cum_spot=10.0, flow_direction="opuestos"),
        _daily_row(2, spot=None, futures=5.0, price_change=-1.0, cum_spot=None, flow_direction="sin_dato"),
    ]
    totals = (await daily_history(_DailyConnection(rows), "BTCUSDT_PERP.A", 2))["totals"]
    assert totals["sessions_spot_selling"] == 0
    assert totals["sessions_spot_measured"] == 1
    assert totals["sessions_spot_unmeasured"] == 1


@pytest.mark.asyncio
async def test_pr22_ai_daily_real_zero_is_neutral() -> None:
    rows = [
        _daily_row(1, spot=0.0, futures=0.0, price_change=0.0, cum_spot=0.0, flow_direction="neutral")
    ]
    result = await daily_history(_DailyConnection(rows), "BTCUSDT_PERP.A", 1)
    totals = result["totals"]
    assert totals["sessions_spot_neutral"] == 1
    assert totals["sessions_spot_selling"] == 0
    assert totals["sessions_price_neutral"] == 1
    assert result["series"][0]["flow_direction"] == "neutral"
    assert "THEN 'neutral'" in DAILY_HISTORY_QUERY


def test_pr22_ai_daily_flow_direction_requires_both_legs() -> None:
    null_guard = "WHEN s.cvd_spot_usd IS NULL OR s.cvd_fut_usd IS NULL THEN 'sin_dato'"
    assert null_guard in DAILY_HISTORY_QUERY
    assert DAILY_HISTORY_QUERY.index(null_guard) < DAILY_HISTORY_QUERY.index("'ambos_compran'")


@pytest.mark.asyncio
async def test_pr22_ai_daily_window_total_fails_closed_on_missing_session() -> None:
    rows = [
        _daily_row(1, spot=10.0, futures=20.0, price_change=1.0, cum_spot=10.0, flow_direction="opuestos"),
        _daily_row(2, spot=5.0, futures=None, price_change=None, cum_spot=15.0, flow_direction="sin_dato"),
    ]
    totals = (await daily_history(_DailyConnection(rows), "BTCUSDT_PERP.A", 2))["totals"]
    assert totals["cvd_fut_usd"] is None
    assert totals["cvd_diff_usd"] is None
    assert totals["price_change_pct"] is None
