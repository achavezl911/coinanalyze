"""R-01 (F14 H2, plan dz5b P22): the confirmatory baseline of a block never
includes the block itself.

Synthetic hourly worlds (fable-dz4 P5 double) go through the REAL
``_compute_confirmatory_result``; only the two DB fetches are stubbed. With the
v1 own-block baseline a direction-free contrarian rule "passed" (42 % day:1,
100 % hour:4) and a +5 bps momentum edge "failed" (99 % hour:4).
"""

from __future__ import annotations

import asyncio
import random
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app import signal_confirmatory as sc
from app import signal_walk_forward as wf
from app.signal_outcomes import OUTCOME_VERSION

SYMBOL, HORIZON, SIGMA_BPS = "BTCUSDT", 60, 50.0
T0 = datetime(2026, 1, 5, tzinfo=UTC)
EXCHANGE, SIZE = sc.EXECUTION_EXCHANGES[0], sc.EXECUTION_SIZES_USD[0]
WORLDS = 40


def _row(obs_id: int, minute: int, entry: float, end: float, direction: str) -> dict[str, Any]:
    at = T0 + timedelta(minutes=minute)
    market = (end - entry) / entry * 100.0
    directional = market if direction == "long" else -market
    return {
        "observation_id": obs_id, "observed_at": at, "observed_minute": at, "symbol": SYMBOL,
        "state": "Long Setup" if direction == "long" else "Short Setup", "direction": direction,
        "regime_label": "alza", "actionable": True, "reference_price": entry,
        "horizon_minutes": HORIZON, "status": "evaluated", "usable": True,
        "outcome_version": OUTCOME_VERSION, "window_end": at + timedelta(minutes=HORIZON + 1),
        "end_price": end, "directional_return_pct": directional,
        "mfe_pct": max(directional, 0.0), "mae_pct": min(directional, 0.0),
        "market_return_pct": market,
    }


def _world(seed: int, rule: str, edge_bps: float = 0.0, drift_bps: float = 0.0, days: int = 28):
    """One always-actionable row per hour; return N(drift, 50 bps) + direction x edge.
    Rules: coin, momentum (sign of the previous 4 h), contrarian (its opposite), long."""
    rng = random.Random(seed)
    returns: list[float] = []
    rows: list[dict[str, Any]] = []
    price = 100_000.0
    for i in range(days * 24):
        noise = rng.gauss(drift_bps, SIGMA_BPS)
        coin = 1 if rng.random() < 0.5 else -1
        if rule == "long":
            sign = 1
        elif rule == "coin" or i < 4:
            sign = coin
        else:
            past = 1 if sum(returns[i - 4 : i]) > 0 else -1
            sign = past if rule == "momentum" else -past
        ret = noise + sign * edge_bps
        returns.append(ret)
        end = price * (1.0 + ret / 1e4)
        rows.append(_row(i, i * 60, price, end, "long" if sign > 0 else "short"))
        price = end
    return rows


def _contract(unit: str, length: int, **overrides: Any) -> sc.ConfirmatoryContract:
    fields: dict[str, Any] = {
        "primary_endpoint_version": sc.CONFIRMATORY_PRIMARY_ENDPOINT_VERSION,
        "primary_symbol": SYMBOL, "primary_horizon_minutes": HORIZON,
        "primary_sampling_mode": wf.UTC_NONOVERLAP, "primary_exchange": EXCHANGE,
        "primary_size_usd": SIZE, "primary_taker_fee_bps": 0.0,
        "baseline_version": sc.BLOCK_UNCONDITIONAL_DIRECTION_MATCHED_BASELINE_VERSION,
        "unmodeled_execution_stress_bps": 0.0,
        "inference_version": sc.BLOCK_BOOTSTRAP_INFERENCE_VERSION,
        "block_unit": unit, "block_length": length, "bootstrap_repetitions": 200,
        "bootstrap_seed": 14, "confidence_level": 0.95, "minimum_effect_bps": 0.0,
        "minimum_primary_blocks": 2, "minimum_execution_data_coverage_pct": 90.0,
        "minimum_research_data_coverage_pct": 90.0,
        "confirmatory_decision_policy": sc.CONFIRMATORY_DECISION_POLICY_V1,
    }
    fields.update(overrides)
    return sc.ConfirmatoryContract(**fields)


@pytest.fixture
def world(monkeypatch):
    state: dict[str, Any] = {"rows": []}

    async def grid(conn, *, period_start, period_end, knowledge_cutoff, options):
        return [{**r, "usable": r["window_end"] <= period_end}
                for r in state["rows"] if period_start <= r["observed_minute"] < period_end]

    async def snapshots(conn, observation_ids, *, execution_snapshot_version):
        side = {"market_cost_bps_vs_mid": 0.0, "insufficient_depth": False}
        by_id = {r["observation_id"]: r for r in state["rows"]}
        out = {}
        for obs_id in observation_ids:
            mid = by_id[obs_id]["reference_price"]
            curve = {str(int(SIZE)): {"buy": {"avg_price": mid, **side},
                                      "sell": {"avg_price": mid, **side}}}
            out[obs_id] = {EXCHANGE: {"status": "valid", "cost_curve": curve}}
        return out

    monkeypatch.setattr(wf, "_fetch_period_grid_v2", grid)
    monkeypatch.setattr(wf, "_fetch_execution_snapshots", snapshots)

    def run(rows, contract, *, weeks: int = 4) -> dict[str, Any]:
        state["rows"] = rows
        folds = [{"fold_index": k, "test_start": T0 + timedelta(days=7 * k),
                  "test_end": T0 + timedelta(days=7 * (k + 1)),
                  "test_maturity_at": T0 + timedelta(days=7 * (k + 1), hours=2)}
                 for k in range(weeks)]
        options = wf.WalkForwardManifestOptions(
            symbols=(SYMBOL,), horizons=(HORIZON,), fee_bps_per_side=((EXCHANGE, 0.0),),
            spec_version=3, confirmatory_contract=contract)
        return asyncio.run(wf._compute_confirmatory_result(
            None, options=options, contract=contract, fold_specs=folds,
            generated_at=T0 + timedelta(days=7 * weeks + 2)))

    return run


def _rates(run, rule: str, edge: float, drift: float, contract) -> Counter:
    states: Counter = Counter()
    for seed in range(WORLDS):
        states[run(_world(5000 + seed, rule, edge, drift), contract)["confirmatory_state"]] += 1
    return states


@pytest.mark.parametrize("unit,length", [("day", 1), ("hour", 4)])
def test_contrarian_rule_without_edge_no_longer_passes(world, unit, length):
    states = _rates(world, "contrarian", 0.0, 0.0, _contract(unit, length))
    assert states["pass"] <= 0.15 * WORLDS, states


@pytest.mark.parametrize("unit,length", [("day", 1), ("hour", 4)])
def test_momentum_with_real_edge_passes_most_worlds(world, unit, length):
    states = _rates(world, "momentum", 5.0, 0.0, _contract(unit, length))
    assert states["pass"] > 0.5 * WORLDS and states["fail"] <= 0.15 * WORLDS, states


@pytest.mark.parametrize("unit,length", [("day", 1), ("hour", 4)])
def test_control_coin_rule_does_not_move(world, unit, length):
    states = _rates(world, "coin", 0.0, 0.0, _contract(unit, length))
    assert states["pass"] <= 0.15 * WORLDS and states["fail"] <= 0.15 * WORLDS, states


@pytest.mark.parametrize("unit,length", [("day", 1), ("hour", 4)])
def test_dropping_the_baseline_is_not_the_fix(world, monkeypatch, unit, length):
    contract = _contract(unit, length)
    assert _rates(world, "long", 0.0, 6.0, contract)["pass"] <= 0.15 * WORLDS
    monkeypatch.setattr(wf, "block_unconditional_direction_matched_baseline_bps",
                        lambda mean, *, direction: 0.0)
    assert _rates(world, "long", 0.0, 6.0, contract)["pass"] > 0.5 * WORLDS


def test_one_block_refuses_instead_of_inventing_a_baseline(world):
    result = world(_world(1, "coin", days=1), _contract("day", 1), weeks=1)
    assert result["confirmatory_state"] == sc.CONFIRMATORY_STATE_INCONCLUSIVE
    assert result["baseline_mean_bps"] is None and result["primary_excess_mean_bps"] is None
    assert "baseline v2 needs >= 2 blocks" in result["baseline_refusal_reason"]

