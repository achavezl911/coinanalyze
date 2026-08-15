"""PR27-R04: the runtime contract at the raw producer boundary.

R03 attests the contract before scientific *evidence* is written.  That is too
late: ``futures_pair`` and ``spot_pair`` never appear in a row key, so a
collector running under an unregistered routing writes a foreign market's data
under the internal key the frozen kernel reads.  Restoring the registered
routing then makes the contract pass again while ``scalp_context`` still has
those rows inside its realtime windows.

These tests pin the guard itself and its wiring into the only two producers the
audit found capable of that.  The end-to-end contamination proof needs real
PostgreSQL and lives in ``test_pr27_r04_raw_producer_closure_postgres.py``.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import replace
from functools import partial
from pathlib import Path

import pytest

import app.scalp_collector as scalp
import app.ws_collector as ws
from app import config
from app.config import DEFAULT_MARKET_CATALOG, MarketSymbol
from app.signal_runtime_contract import (
    _RESULT_MATERIAL_RAW_PRODUCERS_V1,
    REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    RawMarketProducerContractError,
    attest_raw_market_producer,
    compute_scientific_runtime_contract,
    effective_market_routing_from_contract,
    scientific_runtime_contract,
)
from app.signal_scientific_identity import SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS

PRODUCERS = ("scalp_collector", "ws_collector")


def _swapped(field: str) -> tuple[MarketSymbol, ...]:
    """Routing B: swap one result-material selector between BTC and ETH.

    A swap rather than an arbitrary value keeps ``load_market_catalog``'s
    per-field uniqueness check satisfied while making the misrouting maximal:
    the BTC key would receive ETH's market data and vice versa.
    """

    pairs = {item.symbol: getattr(item, field) for item in DEFAULT_MARKET_CATALOG}
    swap = {
        "BTCUSDT_PERP.A": pairs["ETHUSDT_PERP.A"],
        "ETHUSDT_PERP.A": pairs["BTCUSDT_PERP.A"],
    }
    return tuple(
        replace(item, **{field: swap[item.symbol]}) if item.symbol in swap else item
        for item in DEFAULT_MARKET_CATALOG
    )


def _activate_routing_b(monkeypatch: pytest.MonkeyPatch, field: str = "futures_pair") -> None:
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", _swapped(field))


def _catalog_file(tmp_path, field: str) -> str:
    """A real catalog file so a fresh interpreter resolves routing B for real."""

    rows = [
        {
            "symbol": item.symbol,
            "base_asset": item.base_asset,
            "futures_pair": item.futures_pair,
            "bybit_oi_symbol": item.bybit_oi_symbol,
            "spot_pair": item.spot_pair,
            "spot_history_symbol": item.spot_history_symbol,
            "whale_threshold_usd": item.whale_threshold_usd,
            "large_trade_threshold_usd": item.large_trade_threshold_usd,
        }
        for item in _swapped(field)
    ]
    path = tmp_path / "routing-b.json"
    path.write_text(
        json.dumps({"version": 1, "mode": "replace", "symbols": rows}),
        encoding="utf-8",
    )
    return str(path)


# --------------------------------------------------------------------------
# The guard itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize("producer", PRODUCERS)
def test_registered_routing_lets_a_raw_producer_run(producer: str) -> None:
    # R05: the attestation returns the frozen routing derived from the
    # validated contract -- exactly the object the producer must apply.
    assert attest_raw_market_producer(producer) == (
        effective_market_routing_from_contract(scientific_runtime_contract())
    )


@pytest.mark.parametrize("producer", PRODUCERS)
@pytest.mark.parametrize("field", ["futures_pair", "spot_pair", "base_asset", "symbol"])
def test_unregistered_routing_blocks_every_raw_producer(
    producer: str, field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _activate_routing_b(monkeypatch, field)
    assert (
        compute_scientific_runtime_contract()["digest"]
        != REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS[
            SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
        ]
    )
    with pytest.raises(RawMarketProducerContractError) as excinfo:
        attest_raw_market_producer(producer)
    message = str(excinfo.value)
    assert producer in message
    for table in _RESULT_MATERIAL_RAW_PRODUCERS_V1[producer]:
        assert table in message


def test_blocking_error_is_a_runtime_error_so_r03_callers_still_fail_closed() -> None:
    assert issubclass(RawMarketProducerContractError, RuntimeError)


def test_unknown_producer_fails_closed_rather_than_passing_silently() -> None:
    with pytest.raises(ValueError, match="unknown result-material raw producer"):
        attest_raw_market_producer("ingest")


def test_guarded_tables_are_exactly_the_routed_raw_inputs_of_the_frozen_kernel() -> None:
    # futures_trades_realtime, orderbook_snapshot and liquidations_realtime are
    # read by scalp_context; orderbook_depth by the execution snapshot;
    # spot_trades_realtime is $2 of the context query.  The *_agg tables share a
    # transaction and a routing with their realtime twins.
    assert _RESULT_MATERIAL_RAW_PRODUCERS_V1 == {
        "scalp_collector": (
            "futures_trades_agg",
            "futures_trades_realtime",
            "liquidations_realtime",
            "orderbook_depth",
            "orderbook_snapshot",
        ),
        "ws_collector": (
            "spot_trades_agg",
            "spot_trades_realtime",
        ),
    }


def test_guard_is_frozen_by_the_scientific_identity() -> None:
    """Stricter since the third R05 correction: coverage is the whole file.

    The guard used to be inside a marked region, which meant "the guard is
    frozen" was really "the guard is frozen *while it stays between these two
    comments*".  The module component removes that qualifier: the covered text
    is the file, so the guard cannot be moved out of coverage at all.
    """

    component = next(
        item
        for item in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS
        if item.name == "scientific_runtime_contract_module"
    )
    assert component.relative_path == "app/signal_runtime_contract.py"
    assert component.language == "python_module"
    root = Path(__file__).resolve().parents[1]
    covered = (root / component.relative_path).read_text(encoding="utf-8")
    # Deleting or narrowing the guard changes the identity digest.
    assert "def attest_raw_market_producer" in covered
    assert "_RESULT_MATERIAL_RAW_PRODUCERS_V1" in covered


# --------------------------------------------------------------------------
# Collector wiring: the guard runs before the write, not after
# --------------------------------------------------------------------------


class _RecordingPool:
    """Fails loudly if a flush reaches the database at all."""

    def __init__(self) -> None:
        self.acquired = 0

    def acquire(self) -> _RecordingPool:
        self.acquired += 1
        return self

    async def __aenter__(self):
        # BaseException: `except Exception` in the flush loops must not swallow
        # it, so the loop terminates instead of retrying forever.
        raise asyncio.CancelledError

    async def __aexit__(self, *_args):
        return None


def _bounded_sleep(module, monkeypatch: pytest.MonkeyPatch) -> None:
    """Let exactly one loop iteration run, then stop the loop."""

    calls = {"n": 0}

    async def sleep(_delay: float) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            raise asyncio.CancelledError

    monkeypatch.setattr(module.asyncio, "sleep", sleep)


SLEEPING_FLUSHES = (
    (scalp, "flush_trades"),
    (scalp, "flush_books"),
    (ws, "flush_minute"),
    (ws, "flush_realtime"),
)


def _bound_cycle(module, name: str, pool, routing):
    """The delivery cycle the entrypoint binds, exactly as it binds it.

    Since the R05 wiring closure the flush loops receive a bound cycle instead
    of a routing: a loop that cannot name a store, a routing or a delivery
    cannot substitute one.  The gate under test is unchanged -- it lives in the
    cycle -- so these tests bind the cycle the same way ``*_routing_producers``
    does and keep asserting that nothing reaches the pool.
    """

    return partial(getattr(module, f"{name}_cycle"), pool, None, routing)


@pytest.mark.parametrize(
    ("module", "name"),
    SLEEPING_FLUSHES,
    ids=[f"{module.__name__.rsplit('.', 1)[-1]}.{name}" for module, name in SLEEPING_FLUSHES],
)
@pytest.mark.asyncio
async def test_flush_loop_writes_nothing_under_an_unregistered_routing(
    module, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The routing was attested while A was active; then the catalog resolves B.
    routing = attest_raw_market_producer(module.RAW_PRODUCER)
    _bounded_sleep(module, monkeypatch)
    _activate_routing_b(monkeypatch)
    pool = _RecordingPool()

    with pytest.raises(RawMarketProducerContractError):
        await getattr(module, name)(cycle=_bound_cycle(module, name, pool, routing))

    assert pool.acquired == 0


@pytest.mark.parametrize(
    ("module", "name"),
    SLEEPING_FLUSHES,
    ids=[f"{module.__name__.rsplit('.', 1)[-1]}.{name}" for module, name in SLEEPING_FLUSHES],
)
@pytest.mark.asyncio
async def test_flush_loop_survives_the_guard_under_the_registered_routing(
    module, name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Control: the guard is not a blanket stop.  Under routing A the loop runs
    # past the attestation and only the bounded sleep ends it.
    routing = attest_raw_market_producer(module.RAW_PRODUCER)
    _bounded_sleep(module, monkeypatch)
    pool = _RecordingPool()

    with pytest.raises(asyncio.CancelledError):
        await getattr(module, name)(cycle=_bound_cycle(module, name, pool, routing))


@pytest.mark.asyncio
async def test_liquidation_flush_writes_nothing_under_an_unregistered_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer(scalp.RAW_PRODUCER)
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait(("ts", "BTCUSDT_PERP.A", "binance", "long", 1.0, 2.0, 3.0, "e1"))
    monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
    _activate_routing_b(monkeypatch)
    pool = _RecordingPool()

    with pytest.raises(RawMarketProducerContractError):
        await scalp.flush_liquidations(
            cycle=partial(scalp.flush_liquidations_cycle, pool, None, routing)
        )

    assert pool.acquired == 0


@pytest.mark.asyncio
async def test_liquidation_flush_survives_the_guard_under_the_registered_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer(scalp.RAW_PRODUCER)
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait(("ts", "BTCUSDT_PERP.A", "binance", "long", 1.0, 2.0, 3.0, "e1"))
    monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
    pool = _RecordingPool()

    with pytest.raises(asyncio.CancelledError):
        await scalp.flush_liquidations(
            cycle=partial(scalp.flush_liquidations_cycle, pool, None, routing)
        )

    assert pool.acquired == 1


# --------------------------------------------------------------------------
# Service start, in a fresh interpreter that really resolved routing B
# --------------------------------------------------------------------------


def _run_child(tmp_path, field: str, program: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MARKET_SYMBOL_CATALOG_FILE"] = _catalog_file(tmp_path, field)
    env.pop("SYMBOLS", None)
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(program)],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )


def test_scalp_collector_start_is_blocked_by_a_real_routing_b_catalog(tmp_path) -> None:
    # monkeypatch cannot reach the collectors: they bind FUTURES_PAIR_MAP with
    # `from app.config import ...` at import time.  Only a fresh interpreter
    # with a different catalog file reproduces the production binding.
    result = _run_child(
        tmp_path,
        "futures_pair",
        """
        import app.scalp_collector as scalp
        from app.config import FUTURES_PAIR_MAP
        from app.signal_runtime_contract import RawMarketProducerContractError

        assert FUTURES_PAIR_MAP["BTCUSDT_PERP.A"] == "ETHUSDT", FUTURES_PAIR_MAP
        try:
            scalp.attest_raw_market_producer(scalp.RAW_PRODUCER)
        except RawMarketProducerContractError as exc:
            assert "futures_trades_realtime" in str(exc)
            print("BLOCKED")
        else:
            raise SystemExit("scalp_collector started under an unregistered routing")
        """,
    )
    assert "BLOCKED" in result.stdout


def test_ws_collector_start_is_blocked_by_a_real_routing_b_catalog(tmp_path) -> None:
    result = _run_child(
        tmp_path,
        "spot_pair",
        """
        import app.ws_collector as ws
        from app.config import SPOT_PAIR_MAP
        from app.signal_runtime_contract import RawMarketProducerContractError

        assert SPOT_PAIR_MAP["BTC"] == "ETHUSDT", SPOT_PAIR_MAP
        try:
            ws.attest_raw_market_producer(ws.RAW_PRODUCER)
        except RawMarketProducerContractError as exc:
            assert "spot_trades_realtime" in str(exc)
            print("BLOCKED")
        else:
            raise SystemExit("ws_collector started under an unregistered routing")
        """,
    )
    assert "BLOCKED" in result.stdout


@pytest.mark.parametrize(
    ("module", "field", "gate"),
    [
        (scalp, "futures_pair", "require_attested_scalp_routing"),
        (ws, "spot_pair", "require_attested_ws_routing"),
    ],
)
def test_collector_entrypoint_attests_before_any_lock_pool_or_subscription(
    module, field: str, gate: str
) -> None:
    """Stricter since the R05 wiring closure.

    The entrypoint used to bind the attested routing itself, which is what let
    the review inject a forged one per task.  It now calls a gate that lives
    inside the scientific identity and returns nothing, so the ordering claim
    survives *and* the entrypoint provably holds no routing at all.
    """

    import inspect

    entrypoint = module.main if module is scalp else module.run
    body = inspect.getsource(entrypoint)
    gated = body.index(f"{gate}()")
    for later in ("acquire_service_lock", "create_pool"):
        assert gated < body.index(later), later

    # The gate must really attest, and the entrypoint must not attest by hand.
    assert "attest_raw_market_producer" in inspect.getsource(getattr(module, gate))
    assert "attest_raw_market_producer" not in body
    assert inspect.signature(getattr(module, gate)).return_annotation == "None"
