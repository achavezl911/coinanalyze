"""PR27-R05: the effective routing the producers apply, closed jointly.

R04 gates the raw producers on a contract recomputed from
``MARKET_SYMBOL_CATALOG``.  The producers never apply the catalog: they apply
``WS_SYMBOL_MAP``, ``FUTURES_PAIR_MAP``, ``SPOT_PAIR_MAP`` and
``PAIR_SYMBOL_MAP``, four module-level mutable dicts derived from it once at
import time (A-01).  A divergence between those effective maps and the catalog
passes every attestation while the collectors subscribe, convert and write
under it, so A -> B -> A stays reachable at the raw boundary.  And the code
that builds and applies that routing -- ``config.py``, ``ws_collector.py``,
``scalp_collector.py`` -- sits outside the scientific identity, so a semantic
change there never moves the digest (A-02).

These tests were written red against ``ee3792ca`` and force one closure for
both findings: a single frozen ``EffectiveMarketRouting`` derived from the
validated contract, returned by ``attest_raw_market_producer()``, passed
explicitly to subscriptions, handlers, flushes and writes, with the mutable
maps demoted to a projection the attestation verifies; plus identity regions
over routing construction and its application points in both collectors.
"""

from __future__ import annotations

import asyncio
import inspect
import shutil
import time
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import app.scalp_collector as scalp
import app.ws_collector as ws
from app import config
from app.signal_runtime_contract import (
    REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    EffectiveMarketRouting,
    RawMarketProducerContractError,
    attest_raw_market_producer,
    compute_scientific_runtime_contract,
    effective_market_routing_from_contract,
    require_routed_internal_keys,
    scientific_runtime_contract,
)
from app.signal_scientific_identity import (
    SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS,
    compute_scientific_implementation_identity,
)
from tests.test_pr27_r04_raw_producer_closure import (
    _bounded_sleep,
    _RecordingPool,
    _swapped,
)

ROOT = Path(__file__).resolve().parents[1]
PRODUCERS = ("scalp_collector", "ws_collector")
FOUR_MAPS = ("WS_SYMBOL_MAP", "FUTURES_PAIR_MAP", "SPOT_PAIR_MAP", "PAIR_SYMBOL_MAP")
REGISTERED_CONTRACT_DIGEST = REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS[
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
]

# One in-place divergence per effective map.  Values swap BTC's routing onto
# ETH's markets, the same maximal misrouting the R04 catalog tests use, except
# the catalog -- and therefore the R04 attestation -- never sees it.
MAP_DIVERGENCES = (
    ("WS_SYMBOL_MAP", "BTCUSDT_PERP.A", "ETH"),
    ("FUTURES_PAIR_MAP", "BTCUSDT_PERP.A", "ETHUSDT"),
    ("SPOT_PAIR_MAP", "BTC", "ETHUSDT"),
    ("PAIR_SYMBOL_MAP", "ETHUSDT", "BTCUSDT_PERP.A"),
)


def _now_ms() -> int:
    return int(time.time() * 1000)


# --------------------------------------------------------------------------
# A-01, the defect itself: effective-map divergence must fail the attestation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("producer", PRODUCERS)
@pytest.mark.parametrize(("map_name", "key", "value"), MAP_DIVERGENCES)
def test_effective_map_divergence_blocks_every_raw_producer(
    producer: str, map_name: str, key: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Red on ee3792ca: the maps diverge, yet the attestation passed."""

    monkeypatch.setitem(getattr(config, map_name), key, value)

    # The catalog-derived contract still matches its registered digest: this is
    # exactly why R04 cannot see the divergence.
    assert (
        compute_scientific_runtime_contract()["digest"] == REGISTERED_CONTRACT_DIGEST
    )

    with pytest.raises(RawMarketProducerContractError) as excinfo:
        attest_raw_market_producer(producer)
    assert map_name in str(excinfo.value)


@pytest.mark.parametrize(("map_name", "key", "value"), MAP_DIVERGENCES)
def test_effective_map_divergence_blocks_the_evidence_boundary_too(
    map_name: str, key: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scalp_context binds WS_SYMBOL_MAP[symbol]; the shared gate must see maps."""

    monkeypatch.setitem(getattr(config, map_name), key, value)
    with pytest.raises(RuntimeError, match=map_name):
        scientific_runtime_contract()


def test_rebinding_an_effective_map_blocks_the_raw_producers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rebound = {**config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A": "ETHUSDT"}
    monkeypatch.setattr(config, "FUTURES_PAIR_MAP", rebound)
    for producer in PRODUCERS:
        with pytest.raises(RawMarketProducerContractError):
            attest_raw_market_producer(producer)


def test_a_missing_effective_map_entry_blocks_the_raw_producers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(config.SPOT_PAIR_MAP, "BTC")
    for producer in PRODUCERS:
        with pytest.raises(RawMarketProducerContractError):
            attest_raw_market_producer(producer)


def test_a_foreign_pair_aliased_onto_a_configured_symbol_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every registered entry is intact; a fifth entry routes DOGE under BTC."""

    monkeypatch.setitem(config.PAIR_SYMBOL_MAP, "DOGEUSDT", "BTCUSDT_PERP.A")
    for producer in PRODUCERS:
        with pytest.raises(RawMarketProducerContractError):
            attest_raw_market_producer(producer)


@pytest.mark.parametrize(
    ("map_name", "key", "value"),
    [
        # Entries for symbols outside the configured scope arise naturally from
        # an extended catalog under a narrowed SYMBOLS, and none of them can
        # reach a configured internal key.  They must not block production.
        ("PAIR_SYMBOL_MAP", "DOGEUSDT", "DOGEUSDT_PERP.A"),
        ("WS_SYMBOL_MAP", "DOGEUSDT_PERP.A", "DOGE"),
        ("SPOT_PAIR_MAP", "DOGE", "DOGEUSDT"),
        ("FUTURES_PAIR_MAP", "DOGEUSDT_PERP.A", "DOGEUSDT"),
    ],
)
def test_inert_extra_map_entries_do_not_block_production(
    map_name: str, key: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(getattr(config, map_name), key, value)
    for producer in PRODUCERS:
        assert attest_raw_market_producer(producer) is not None


# --------------------------------------------------------------------------
# The frozen effective routing: exactly the attested object, immutable
# --------------------------------------------------------------------------


def test_attest_returns_the_routing_derived_from_the_validated_contract() -> None:
    contract = scientific_runtime_contract()
    for producer in PRODUCERS:
        routing = attest_raw_market_producer(producer)
        assert isinstance(routing, EffectiveMarketRouting)
        assert routing == effective_market_routing_from_contract(contract)
        assert routing.contract_version == SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
        assert routing.contract_digest == contract["digest"]
        assert [
            {
                "symbol": route.symbol,
                "base_asset": route.base_asset,
                "futures_pair": route.futures_pair,
                "spot_pair": route.spot_pair,
            }
            for route in routing.routes
        ] == contract["market_routing"]


def test_attested_routing_is_frozen_and_survives_later_map_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("scalp_collector")
    assert routing.futures_pair_by_symbol["BTCUSDT_PERP.A"] == "BTCUSDT"
    assert routing.symbol_by_futures_pair["BTCUSDT"] == "BTCUSDT_PERP.A"

    with pytest.raises(FrozenInstanceError):
        routing.contract_digest = "0" * 64  # type: ignore[misc]
    with pytest.raises(TypeError):
        routing.symbol_by_futures_pair["BTCUSDT"] = "ETHUSDT_PERP.A"  # type: ignore[index]
    # A mappingproxy does not even expose mutators.
    with pytest.raises(AttributeError):
        routing.futures_pair_by_symbol.clear()  # type: ignore[attr-defined]

    # A mutation after validation cannot change routing already validated and
    # in use.
    monkeypatch.setitem(config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A", "ETHUSDT")
    monkeypatch.setitem(config.PAIR_SYMBOL_MAP, "BTCUSDT", "ETHUSDT_PERP.A")
    assert routing.futures_pair_by_symbol["BTCUSDT_PERP.A"] == "BTCUSDT"
    assert routing.symbol_by_futures_pair["BTCUSDT"] == "BTCUSDT_PERP.A"


def test_reattestation_blocks_when_runtime_no_longer_matches_the_held_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("ws_collector")

    monkeypatch.setitem(config.SPOT_PAIR_MAP, "BTC", "ETHUSDT")
    with pytest.raises(RawMarketProducerContractError):
        attest_raw_market_producer("ws_collector", expected=routing)


def test_reattestation_blocks_under_a_catalog_swap_with_the_held_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("scalp_collector")
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", _swapped("futures_pair"))
    with pytest.raises(RawMarketProducerContractError):
        attest_raw_market_producer("scalp_collector", expected=routing)


def test_internal_key_gate_accepts_only_each_producer_keyspace() -> None:
    routing = attest_raw_market_producer("scalp_collector")

    require_routed_internal_keys(routing, "scalp_collector", {"BTCUSDT_PERP.A"})
    require_routed_internal_keys(routing, "ws_collector", {"BTC"})

    with pytest.raises(RawMarketProducerContractError):
        require_routed_internal_keys(routing, "scalp_collector", {"BTC"})
    with pytest.raises(RawMarketProducerContractError):
        require_routed_internal_keys(routing, "ws_collector", {"BTCUSDT_PERP.A"})
    with pytest.raises(RawMarketProducerContractError):
        require_routed_internal_keys(
            routing, "scalp_collector", {"BTCUSDT_PERP.A", "DOGEUSDT_PERP.A"}
        )
    with pytest.raises(ValueError):
        require_routed_internal_keys(routing, "ingest", {"BTCUSDT_PERP.A"})


# --------------------------------------------------------------------------
# scalp_collector: subscriptions, conversion and writes follow the routing
# --------------------------------------------------------------------------


def test_scalp_subscription_streams_derive_from_the_attested_routing() -> None:
    routing = attest_raw_market_producer("scalp_collector")
    index = routing.futures_index(("BTCUSDT_PERP.A",))
    assert index.pairs == ("BTCUSDT",)
    assert dict(index.symbol_by_pair) == {"BTCUSDT": "BTCUSDT_PERP.A"}

    streams = scalp.binance_futures_streams(index)
    assert streams == (
        "btcusdt@trade",
        "btcusdt@depth10@100ms",
        "btcusdt@forceOrder",
    )
    assert scalp.binance_force_order_streams(index) == ("btcusdt@forceOrder",)
    assert scalp.bybit_linear_topics(index) == (
        "publicTrade.BTCUSDT",
        "orderbook.50.BTCUSDT",
        "allLiquidation.BTCUSDT",
    )


@pytest.mark.asyncio
async def test_scalp_conversion_follows_the_routing_not_the_mutable_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("scalp_collector")
    index = routing.futures_index(("BTCUSDT_PERP.A",))
    store = scalp.TradeStore()
    monkeypatch.setattr(scalp, "TRADE_STORE", store)

    # Poison the mutable map after attestation: the handler must not see it.
    monkeypatch.setitem(config.PAIR_SYMBOL_MAP, "DOGEUSDT", "BTCUSDT_PERP.A")

    now = _now_ms()
    await scalp.handle_binance(
        {
            "stream": "dogeusdt@trade",
            "data": {"e": "trade", "s": "DOGEUSDT", "p": "1.0", "q": "5", "T": now, "m": False},
        },
        index,
    )
    assert not store.minute and not store.realtime

    await scalp.handle_binance(
        {
            "stream": "btcusdt@trade",
            "data": {"e": "trade", "s": "BTCUSDT", "p": "60000", "q": "1", "T": now, "m": False},
        },
        index,
    )
    assert {key[0] for key in store.minute} == {"BTCUSDT_PERP.A"}

    await scalp.handle_bybit(
        {
            "topic": "publicTrade.BTCUSDT",
            "ts": now,
            "data": [{"p": "60001", "v": "1", "T": now, "S": "Buy"}],
        },
        index,
    )
    assert {key[:2] for key in store.minute} == {
        ("BTCUSDT_PERP.A", "binance"),
        ("BTCUSDT_PERP.A", "bybit"),
    }


@pytest.mark.asyncio
async def test_scalp_flush_loops_write_nothing_under_divergent_effective_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("scalp_collector")
    for name in ("flush_trades", "flush_books"):
        _bounded_sleep(scalp, monkeypatch)
        with monkeypatch.context() as patch:
            patch.setitem(config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A", "ETHUSDT")
            pool = _RecordingPool()
            with pytest.raises(RawMarketProducerContractError):
                await getattr(scalp, name)(pool, routing=routing)
            assert pool.acquired == 0


@pytest.mark.asyncio
async def test_scalp_liquidation_flush_writes_nothing_under_divergent_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("scalp_collector")
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait(("ts", "BTCUSDT_PERP.A", "binance", "long", 1.0, 2.0, 3.0, "e1"))
    monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)
    monkeypatch.setitem(config.PAIR_SYMBOL_MAP, "ETHUSDT", "BTCUSDT_PERP.A")
    pool = _RecordingPool()

    with pytest.raises(RawMarketProducerContractError):
        await scalp.flush_liquidations(pool, routing=routing)
    assert pool.acquired == 0


# --------------------------------------------------------------------------
# ws_collector: subscriptions, conversion and writes follow the routing
# --------------------------------------------------------------------------


def test_ws_subscriptions_derive_from_the_attested_routing() -> None:
    routing = attest_raw_market_producer("ws_collector")
    index = routing.spot_index(("BTCUSDT_PERP.A",))
    assert index.pairs == ("BTCUSDT",)
    assert dict(index.base_asset_by_pair) == {"BTCUSDT": "BTC"}

    assert ws.spot_pairs(("BTCUSDT_PERP.A",), routing) == ("BTCUSDT",)
    assert ws.binance_url(("BTCUSDT_PERP.A",), routing) == (
        ws.BINANCE_STREAM_BASE + "btcusdt@aggTrade"
    )
    assert ws.bybit_subscription_args(index) == ("publicTrade.BTCUSDT",)


@pytest.mark.asyncio
async def test_ws_conversion_follows_the_routing_not_the_mutable_map(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("ws_collector")
    index = routing.spot_index(("BTCUSDT_PERP.A",))
    store = ws.BucketStore()
    monkeypatch.setattr(ws, "STORE", store)

    monkeypatch.setitem(config.SPOT_PAIR_MAP, "BTC", "DOGEUSDT")
    now = _now_ms()

    await ws.handle_binance_spot(
        {"data": {"s": "DOGEUSDT", "p": "1.0", "q": "5", "T": now, "m": False}},
        index,
    )
    assert not store.minute and not store.realtime

    await ws.handle_binance_spot(
        {"data": {"s": "BTCUSDT", "p": "60010", "q": "1", "T": now, "m": False}},
        index,
    )
    assert {key[0] for key in store.minute} == {"BTC"}

    await ws.handle_bybit_spot(
        {
            "topic": "publicTrade.BTCUSDT",
            "ts": now,
            "data": [{"s": "BTCUSDT", "p": "60011", "v": "1", "T": now, "S": "Buy"}],
        },
        index,
    )
    assert {key[:2] for key in store.minute} == {("BTC", "binance"), ("BTC", "bybit")}


@pytest.mark.asyncio
async def test_ws_flush_loops_write_nothing_under_divergent_effective_maps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routing = attest_raw_market_producer("ws_collector")
    for name in ("flush_minute", "flush_realtime"):
        _bounded_sleep(ws, monkeypatch)
        with monkeypatch.context() as patch:
            patch.setitem(config.WS_SYMBOL_MAP, "BTCUSDT_PERP.A", "ETH")
            pool = _RecordingPool()
            with pytest.raises(RawMarketProducerContractError):
                await getattr(ws, name)(pool, routing=routing)
            assert pool.acquired == 0


# --------------------------------------------------------------------------
# No scientific path in either collector reads the four mutable maps
# --------------------------------------------------------------------------


def _global_names(func) -> set[str]:
    names: set[str] = set()
    stack = [func.__code__]
    while stack:
        code = stack.pop()
        names.update(code.co_names)
        stack.extend(const for const in code.co_consts if hasattr(const, "co_names"))
    return names


SCALP_SCIENTIFIC_FUNCTIONS = (
    "binance_futures_streams",
    "binance_force_order_streams",
    "bybit_linear_topics",
    "handle_binance",
    "handle_bybit",
    "binance_loop",
    "binance_market_loop",
    "bybit_loop",
    "flush_trades",
    "flush_books",
    "flush_liquidations",
    "deliver_futures_trades",
    "deliver_orderbook_state",
    "deliver_liquidations",
    "main",
)

WS_SCIENTIFIC_FUNCTIONS = (
    "spot_pairs",
    "binance_url",
    "bybit_subscription_args",
    "handle_binance_spot",
    "handle_bybit_spot",
    "binance_consumer",
    "bybit_consumer",
    "flush_minute",
    "flush_realtime",
    "deliver_spot_minute",
    "deliver_spot_realtime",
    "run",
)


@pytest.mark.parametrize(
    ("module", "function_names"),
    [(scalp, SCALP_SCIENTIFIC_FUNCTIONS), (ws, WS_SCIENTIFIC_FUNCTIONS)],
    ids=["scalp_collector", "ws_collector"],
)
def test_collector_scientific_paths_never_reference_the_mutable_maps(
    module, function_names: tuple[str, ...]
) -> None:
    for name in function_names:
        referenced = _global_names(getattr(module, name))
        assert not (set(FOUR_MAPS) & referenced), (name, referenced)


def test_collectors_no_longer_import_the_mutable_maps() -> None:
    for module in (scalp, ws):
        for name in FOUR_MAPS:
            assert not hasattr(module, name), (module.__name__, name)


def test_entrypoints_bind_and_explicitly_pass_the_attested_routing() -> None:
    """One attestation per process, and no per-task choice of routing.

    The R05 review showed that wiring the subscriptions from one routing and
    the flushes from another produces a misrouted store behind a delivery gate
    that sees nothing wrong.  The entrypoints therefore bind exactly one
    attested routing and hand it whole to the identity-covered wiring, which is
    the only place that decides which producer receives it.
    """

    for entrypoint, wiring in (
        (scalp.main, scalp.scalp_routing_producers),
        (ws.run, ws.ws_routing_producers),
    ):
        entrypoint_source = inspect.getsource(entrypoint)
        assert "routing = attest_raw_market_producer(RAW_PRODUCER)" in entrypoint_source
        assert entrypoint_source.count("attest_raw_market_producer") == 1
        assert f"{wiring.__name__}(" in entrypoint_source

        wiring_source = inspect.getsource(wiring)
        assert "routing=routing" in wiring_source
        # The wiring receives one routing and may not resolve another itself.
        assert "attest_raw_market_producer" not in wiring_source


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (scalp, "flush_trades"),
        (scalp, "flush_books"),
        (scalp, "flush_liquidations"),
        (ws, "flush_minute"),
        (ws, "flush_realtime"),
    ],
    ids=lambda value: getattr(value, "__name__", value),
)
def test_flush_loops_require_an_explicit_routing_with_no_fallback(module, name) -> None:
    parameter = inspect.signature(getattr(module, name)).parameters["routing"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty


def test_raw_delivery_functions_gate_inside_the_write_path() -> None:
    for function in (
        scalp.deliver_futures_trades,
        scalp.deliver_orderbook_state,
        scalp.deliver_liquidations,
        ws.deliver_spot_minute,
        ws.deliver_spot_realtime,
    ):
        source = inspect.getsource(function)
        assert "attest_raw_market_producer" in source
        assert "require_routed_internal_keys" in source


def test_flush_loops_never_retry_a_blocked_delivery_as_transient() -> None:
    for module, name in (
        (scalp, "flush_trades"),
        (scalp, "flush_books"),
        (scalp, "flush_liquidations"),
        (ws, "flush_minute"),
        (ws, "flush_realtime"),
    ):
        source = inspect.getsource(getattr(module, name))
        assert "except RawMarketProducerContractError" in source, (module.__name__, name)


# --------------------------------------------------------------------------
# A-02: routing construction and application are inside the identity
# --------------------------------------------------------------------------


ROUTING_IDENTITY_COMPONENTS = {
    "market_routing_construction": (
        "app/config.py",
        "PR27_SCIENTIFIC_MARKET_ROUTING_SOURCE_V1_BEGIN",
        "PR27_SCIENTIFIC_MARKET_ROUTING_SOURCE_V1_END",
    ),
    "scalp_routing_application": (
        "app/scalp_collector.py",
        "PR27_SCIENTIFIC_SCALP_ROUTING_APPLICATION_V1_BEGIN",
        "PR27_SCIENTIFIC_SCALP_ROUTING_APPLICATION_V1_END",
    ),
    "scalp_routing_entrypoint": (
        "app/scalp_collector.py",
        "PR27_SCIENTIFIC_SCALP_ROUTING_ENTRYPOINT_V1_BEGIN",
        "PR27_SCIENTIFIC_SCALP_ROUTING_ENTRYPOINT_V1_END",
    ),
    "scalp_raw_delivery": (
        "app/scalp_collector.py",
        "PR27_SCIENTIFIC_SCALP_RAW_DELIVERY_V1_BEGIN",
        "PR27_SCIENTIFIC_SCALP_RAW_DELIVERY_V1_END",
    ),
    "ws_routing_application": (
        "app/ws_collector.py",
        "PR27_SCIENTIFIC_WS_ROUTING_APPLICATION_V1_BEGIN",
        "PR27_SCIENTIFIC_WS_ROUTING_APPLICATION_V1_END",
    ),
    "ws_routing_entrypoint": (
        "app/ws_collector.py",
        "PR27_SCIENTIFIC_WS_ROUTING_ENTRYPOINT_V1_BEGIN",
        "PR27_SCIENTIFIC_WS_ROUTING_ENTRYPOINT_V1_END",
    ),
    "ws_raw_delivery": (
        "app/ws_collector.py",
        "PR27_SCIENTIFIC_WS_RAW_DELIVERY_V1_BEGIN",
        "PR27_SCIENTIFIC_WS_RAW_DELIVERY_V1_END",
    ),
}


def test_routing_regions_are_registered_identity_components() -> None:
    by_name = {
        component.name: component
        for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS
    }
    for name, (path, begin, end) in ROUTING_IDENTITY_COMPONENTS.items():
        component = by_name[name]
        assert component.relative_path == path
        assert component.begin_marker == begin
        assert component.end_marker == end
        assert component.language == "python"


def _region(relative_path: str, begin: str, end: str) -> str:
    text = (ROOT / relative_path).read_text(encoding="utf-8")
    return text[text.index(begin) : text.index(end)]


# Catalog fields the runtime contract does not project.  R05's review proved
# these were dragged into the identity by the original wide region: bumping
# whale_threshold_usd moved the digest, contradicting their exclusion.
NON_SCIENTIFIC_CATALOG_FIELDS = (
    "whale_threshold_usd",
    "large_trade_threshold_usd",
    "bybit_oi_symbol",
    "spot_history_symbol",
)


def test_identity_regions_contain_the_routing_material_code() -> None:
    construction = _region(*ROUTING_IDENTITY_COMPONENTS["market_routing_construction"])
    for name in (*FOUR_MAPS, "MARKET_SYMBOL_CATALOG"):
        assert name in construction
    # Narrowed to the four projections: the catalog rows, their loader and the
    # non-scientific fields alongside them are frozen by the runtime contract
    # instead, so an operational edit there cannot move the identity.
    for name in ("load_market_catalog", "DEFAULT_MARKET_CATALOG"):
        assert name not in construction
    for field in NON_SCIENTIFIC_CATALOG_FIELDS:
        assert field not in construction

    scalp_application = _region(
        *ROUTING_IDENTITY_COMPONENTS["scalp_routing_application"]
    )
    for needle in (
        "symbol_by_pair",
        "@trade",
        "@forceOrder",
        "publicTrade.",
        "orderbook.50.",
        # The index construction, the venue endpoints, the connection that
        # carries the routed streams and the handler each message reaches.
        "routing.futures_index(ACTIVE_SYMBOLS)",
        "wss://fstream.binance.com",
        "wss://stream.bybit.com",
        "websockets.connect(",
        "handle_binance(json.loads(raw), index)",
        "handle_bybit(message, index)",
    ):
        assert needle in scalp_application

    scalp_entrypoint = _region(
        *ROUTING_IDENTITY_COMPONENTS["scalp_routing_entrypoint"]
    )
    for needle in ("binance_loop(routing=routing)", "flush_trades(pool, ownership, routing=routing)"):
        assert needle in scalp_entrypoint

    scalp_delivery = _region(*ROUTING_IDENTITY_COMPONENTS["scalp_raw_delivery"])
    for needle in (
        "INSERT INTO futures_trades_realtime",
        "INSERT INTO futures_trades_agg",
        "orderbook_snapshot",
        "orderbook_depth",
        "liquidations_realtime",
        # The handoff from each store to the gated delivery.
        "TRADE_STORE.realtime_snapshot()",
        "BOOK_STORE.snapshot()",
        "deliver_futures_trades(conn, routing, snapshots, minute_snapshots)",
        "deliver_orderbook_state(conn, routing, rows, ladders)",
        "deliver_liquidations(conn, routing, buffer)",
    ):
        assert needle in scalp_delivery

    ws_application = _region(*ROUTING_IDENTITY_COMPONENTS["ws_routing_application"])
    for needle in (
        "base_asset_by_pair",
        "@aggTrade",
        "publicTrade.",
        "routing.spot_index(symbols)",
        "wss://stream.binance.com",
        "wss://stream.bybit.com",
        "connect(url, **WS_CONNECT_KWARGS)",
        "handle_binance_spot(json.loads(raw), index)",
        "handle_bybit_spot(json.loads(raw), index)",
    ):
        assert needle in ws_application

    ws_entrypoint = _region(*ROUTING_IDENTITY_COMPONENTS["ws_routing_entrypoint"])
    for needle in (
        "binance_consumer(symbols, routing)",
        "flush_minute(pool, ownership, routing=routing)",
    ):
        assert needle in ws_entrypoint

    ws_delivery = _region(*ROUTING_IDENTITY_COMPONENTS["ws_raw_delivery"])
    for needle in (
        "INSERT INTO spot_trades_agg",
        "INSERT INTO spot_trades_realtime",
        "STORE.minute_snapshot()",
        "deliver_spot_minute(conn, routing, snapshots)",
        "deliver_spot_realtime(conn, routing, snapshots)",
    ):
        assert needle in ws_delivery


def test_contract_registry_is_inside_the_identity_region() -> None:
    """Swapping the registered contract digest must move the identity."""

    region = _region(
        "app/signal_runtime_contract.py",
        "PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_BEGIN",
        "PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_END",
    )
    assert "REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS" in region
    assert "EffectiveMarketRouting" in region
    assert "effective_market_routing_from_contract" in region
    assert "require_routed_internal_keys" in region


# --------------------------------------------------------------------------
# A-02: a semantic change to routing construction or application moves the
# identity digest; operational plumbing does not
# --------------------------------------------------------------------------


IDENTITY_FILES = sorted(
    {component.relative_path for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS}
    | {"app/config.py", "app/scalp_collector.py", "app/ws_collector.py"}
)


def _identity_tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for relative in IDENTITY_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    return root


def _mutated_digest(root: Path, relative: str, old: str, new: str) -> str:
    path = root / relative
    source = path.read_text(encoding="utf-8")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    return compute_scientific_implementation_identity(root=root)["digest"]


SEMANTIC_ROUTING_MUTATIONS = (
    (
        "construction-ws-map",
        "app/config.py",
        "WS_SYMBOL_MAP = {item.symbol: item.base_asset for item in MARKET_SYMBOL_CATALOG}",
        "WS_SYMBOL_MAP = {item.symbol: item.spot_history_symbol for item in MARKET_SYMBOL_CATALOG}",
    ),
    (
        "construction-routing-object",
        "app/signal_runtime_contract.py",
        'for route in contract["market_routing"]',
        'for route in reversed(contract["market_routing"])',
    ),
    (
        "scalp-subscription",
        "app/scalp_collector.py",
        '"@trade"',
        '"@aggTrade"',
    ),
    (
        "scalp-conversion",
        "app/scalp_collector.py",
        "index.symbol_by_pair.get(pair)",
        "index.symbol_by_pair.get(pair.lower())",
    ),
    (
        "scalp-delivery",
        "app/scalp_collector.py",
        "INSERT INTO futures_trades_agg(",
        "INSERT INTO futures_trades_agg2(",
    ),
    (
        "ws-subscription",
        "app/ws_collector.py",
        "return tuple(routing.spot_pair_by_symbol[symbol] for symbol in symbols)",
        "return tuple(routing.futures_pair_by_symbol[symbol] for symbol in symbols)",
    ),
    (
        "ws-conversion",
        "app/ws_collector.py",
        "index.base_asset_by_pair.get(pair)",
        "index.base_asset_by_pair.get(pair.lower())",
    ),
    (
        "ws-delivery",
        "app/ws_collector.py",
        "INSERT INTO spot_trades_realtime(",
        "INSERT INTO spot_trades_realtime2(",
    ),
)


@pytest.mark.parametrize(
    ("label", "relative", "old", "new"),
    SEMANTIC_ROUTING_MUTATIONS,
    ids=[case[0] for case in SEMANTIC_ROUTING_MUTATIONS],
)
def test_semantic_routing_change_moves_the_scientific_identity(
    tmp_path: Path, label: str, relative: str, old: str, new: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert baseline == compute_scientific_implementation_identity()["digest"]

    source = (root / relative).read_text(encoding="utf-8")
    assert old in source, f"{label}: expected routing-material source {old!r}"
    assert _mutated_digest(root, relative, old, new) != baseline


@pytest.mark.parametrize(
    ("label", "relative", "old", "new"),
    [
        (
            "scalp-reconnect-backoff",
            "app/scalp_collector.py",
            "backoff = min(backoff * 2, WS_RECONNECT_MAX_SECONDS)",
            "backoff = min(backoff * 3, WS_RECONNECT_MAX_SECONDS)",
        ),
        (
            "ws-reconnect-backoff",
            "app/ws_collector.py",
            "backoff = min(backoff * 2, 60.0)",
            "backoff = min(backoff * 3, 60.0)",
        ),
    ],
    ids=["scalp-reconnect-backoff", "ws-reconnect-backoff"],
)
def test_operational_collector_plumbing_stays_outside_the_identity(
    tmp_path: Path, label: str, relative: str, old: str, new: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]

    source = (root / relative).read_text(encoding="utf-8")
    assert old in source, label
    assert _mutated_digest(root, relative, old, new) == baseline


# --------------------------------------------------------------------------
# Version discipline: the runtime contract payload is untouched by R05
# --------------------------------------------------------------------------


def test_runtime_contract_digest_is_unchanged_by_r05() -> None:
    assert (
        scientific_runtime_contract()["digest"]
        == "c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00"
    )


def test_recomputed_identity_matches_its_registry() -> None:
    identity = compute_scientific_implementation_identity()
    from app.signal_scientific_identity import (
        REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS,
        SCIENTIFIC_IDENTITY_VERSION_V1,
    )

    assert identity["digest"] == REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS[
        SCIENTIFIC_IDENTITY_VERSION_V1
    ]
