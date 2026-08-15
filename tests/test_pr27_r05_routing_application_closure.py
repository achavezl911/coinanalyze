"""PR27-R05 correction: the points where the routing is *actually applied*.

``c879bdec`` closed A-01 but left A-02 open.  Its identity regions cover the
helpers that build streams and the handlers that convert an external pair into
an internal key, but not the code that decides *which index those helpers and
handlers receive*: ``binance_loop``, ``binance_market_loop``, ``bybit_loop``,
``binance_consumer``, ``bybit_consumer``, and the routing injection in
``main``/``run``.  Nor the handoff from the in-memory stores to the gated raw
delivery functions.

An independent review demonstrated the consequence.  Replacing, outside every
protected region::

    index = routing.futures_index(ACTIVE_SYMBOLS)

with an index equivalent to::

    FuturesRoutingIndex(
        pairs=("ETHUSDT",),
        symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"},
    )

left the scientific digest at
``25f6c2e541f9e0f5d467be1e600810809890d95f7263f2433f0639de85ac53e2``.  The same
holds for the spot mutation with ``SpotRoutingIndex``.  The handler then files
ETH trades under BTC's internal key, and the delivery gate -- which validates
only the internal key -- accepts them, so the bypass reaches the store and the
write with no trace in the identity.

These tests were written red against ``c879bdec``.  They force two things at
once: every line that applies the routing must live inside a scientific
identity region, and an index that a routing did not produce must be
structurally impossible rather than merely undocumented.

**They were not sufficient.**  ``_mutate`` below rewrites the *first textual
occurrence* of each expression, and after ``700f7695``/``450cf2fb`` that first
occurrence is always the one already inside a region -- so the suite went green
while the real call sites in ``binance_loop``, ``binance_consumer``, ``main``
and ``run`` stayed unprotected.  A second independent review reproduced the
bypass through exactly that gap.  The mutations here are kept, and
``test_pr27_r05_routing_wiring_closure.py`` adds the anchored ones: it locates
every reference through the AST, so a duplicate expression inside a region can
no longer stand in for the real one.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.signal_runtime_contract import (
    FuturesRoutingIndex,
    RawMarketProducerContractError,
    SpotRoutingIndex,
    attest_raw_market_producer,
    require_routed_internal_keys,
)
from app.signal_scientific_identity import (
    compute_scientific_implementation_identity,
)
from tests.test_pr27_r05_routing_closure import IDENTITY_FILES, _identity_tree

ROOT = Path(__file__).resolve().parents[1]

# The digest the independent review observed while both mutations below were
# applied.  It is recorded as history, not as an expectation: the correction
# recomputes identity-v1, and the assertions here never compare against it.
REVIEWED_UNMOVED_DIGEST = (
    "25f6c2e541f9e0f5d467be1e600810809890d95f7263f2433f0639de85ac53e2"
)


# --------------------------------------------------------------------------
# Mutation tests on the exact application lines the review exercised
# --------------------------------------------------------------------------
#
# Every ``old`` below is a routing-material expression that exists both before
# and after the correction; only its *location* changes.  On ``c879bdec`` the
# first occurrence sits in an unprotected loop or entrypoint, so the mutation
# is invisible to the identity.  After the correction the first occurrence is
# inside a region and the digest must move.

SCALP_APPLICATION_MUTATIONS = (
    (
        "scalp-index-construction",
        "binance_loop",
        "app/scalp_collector.py",
        "routing.futures_index(ACTIVE_SYMBOLS)",
        'FuturesRoutingIndex(pairs=("ETHUSDT",), symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"})',
    ),
    (
        "scalp-binance-stream-selection",
        "binance_loop",
        "app/scalp_collector.py",
        "binance_futures_streams(index)",
        "binance_force_order_streams(index)",
    ),
    (
        "scalp-binance-dispatch",
        "binance_loop",
        "app/scalp_collector.py",
        "handle_binance(json.loads(raw), index)",
        "handle_bybit(json.loads(raw), index)",
    ),
    (
        "scalp-market-stream-selection",
        "binance_market_loop",
        "app/scalp_collector.py",
        "binance_force_order_streams(index)",
        "binance_futures_streams(index)",
    ),
    (
        "scalp-bybit-topic-selection",
        "bybit_loop",
        "app/scalp_collector.py",
        "bybit_linear_topics(index)",
        "bybit_linear_topics(index)[:1]",
    ),
    (
        "scalp-bybit-dispatch",
        "bybit_loop",
        "app/scalp_collector.py",
        "handle_bybit(message, index)",
        "handle_binance(message, index)",
    ),
    (
        "scalp-routing-injection",
        "scalp_routing_producers",
        "app/scalp_collector.py",
        "binance_loop(connect=partial(binance_futures_session, routing))",
        "binance_loop(connect=partial(binance_futures_session, UNATTESTED_ROUTING))",
    ),
    (
        "scalp-trade-store-handoff",
        "flush_trades",
        "app/scalp_collector.py",
        "deliver_futures_trades(conn, routing, snapshots, minute_snapshots)",
        "deliver_futures_trades(conn, routing, minute_snapshots, snapshots)",
    ),
    (
        "scalp-book-store-handoff",
        "flush_books",
        "app/scalp_collector.py",
        "deliver_orderbook_state(conn, routing, rows, ladders)",
        "deliver_orderbook_state(conn, routing, rows, [])",
    ),
    (
        "scalp-liquidation-store-handoff",
        "flush_liquidations",
        "app/scalp_collector.py",
        "deliver_liquidations(conn, routing, buffer)",
        "deliver_liquidations(conn, routing, buffer[:1])",
    ),
)

WS_APPLICATION_MUTATIONS = (
    (
        "ws-index-construction",
        "binance_consumer",
        "app/ws_collector.py",
        "routing.spot_index(symbols)",
        'SpotRoutingIndex(pairs=("ETHUSDT",), base_asset_by_pair={"ETHUSDT": "BTC"})',
    ),
    (
        "ws-binance-url-selection",
        "binance_consumer",
        "app/ws_collector.py",
        "binance_url(symbols, routing)",
        "binance_url(tuple(reversed(symbols)), routing)",
    ),
    (
        "ws-binance-dispatch",
        "binance_consumer",
        "app/ws_collector.py",
        "handle_binance_spot(json.loads(raw), index)",
        "handle_bybit_spot(json.loads(raw), index)",
    ),
    (
        "ws-bybit-topic-selection",
        "bybit_consumer",
        "app/ws_collector.py",
        "bybit_subscription_args(index)",
        "bybit_subscription_args(index)[:1]",
    ),
    (
        "ws-bybit-dispatch",
        "bybit_consumer",
        "app/ws_collector.py",
        "handle_bybit_spot(json.loads(raw), index)",
        "handle_binance_spot(json.loads(raw), index)",
    ),
    (
        "ws-routing-injection",
        "ws_routing_producers",
        "app/ws_collector.py",
        "connect=partial(binance_spot_session, symbols, routing)",
        "connect=partial(binance_spot_session, symbols, UNATTESTED_ROUTING)",
    ),
    (
        "ws-minute-store-handoff",
        "flush_minute",
        "app/ws_collector.py",
        "deliver_spot_minute(conn, routing, snapshots)",
        "deliver_spot_minute(conn, routing, snapshots[:1])",
    ),
    (
        "ws-realtime-store-handoff",
        "flush_realtime",
        "app/ws_collector.py",
        "deliver_spot_realtime(conn, routing, snapshots)",
        "deliver_spot_realtime(conn, routing, snapshots[:1])",
    ),
)

APPLICATION_MUTATIONS = SCALP_APPLICATION_MUTATIONS + WS_APPLICATION_MUTATIONS


def _mutate(root: Path, relative: str, old: str, new: str) -> str:
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1, f"missing routing-material source {old!r}"
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    return compute_scientific_implementation_identity(root=root)["digest"]


@pytest.mark.parametrize(
    ("label", "reviewed_function", "relative", "old", "new"),
    APPLICATION_MUTATIONS,
    ids=[case[0] for case in APPLICATION_MUTATIONS],
)
def test_routing_application_mutation_moves_the_scientific_identity(
    tmp_path: Path,
    label: str,
    reviewed_function: str,
    relative: str,
    old: str,
    new: str,
) -> None:
    """Red on c879bdec: these mutations left the digest at 25f6c2e5...."""

    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert baseline == compute_scientific_implementation_identity()["digest"]
    assert _mutate(root, relative, old, new) != baseline, (
        f"{label}: mutating the routing applied by {reviewed_function}() left "
        f"the scientific identity unchanged"
    )


# --------------------------------------------------------------------------
# Structural coverage: no routing-material construct outside a region
# --------------------------------------------------------------------------


COLLECTOR_MODULES = ("app/scalp_collector.py", "app/ws_collector.py")

# Calls that select an external market, convert it to an internal key, open the
# subscription that carries it, or hand a store's contents to a raw delivery.
ROUTING_MATERIAL_CALLS = frozenset(
    {
        "futures_index",
        "spot_index",
        "FuturesRoutingIndex",
        "SpotRoutingIndex",
        "binance_futures_streams",
        "binance_force_order_streams",
        "bybit_linear_topics",
        "binance_url",
        "spot_pairs",
        "bybit_subscription_args",
        "handle_binance",
        "handle_bybit",
        "handle_binance_spot",
        "handle_bybit_spot",
        "deliver_futures_trades",
        "deliver_orderbook_state",
        "deliver_liquidations",
        "deliver_spot_minute",
        "deliver_spot_realtime",
    }
)

# Endpoint constants: which venue the routed pairs are read from is as
# result-material as the pairs themselves.
ROUTING_MATERIAL_ENDPOINTS = {
    "app/scalp_collector.py": (
        "BINANCE_STREAM_BASE",
        "BINANCE_MARKET_STREAM_BASE",
        "BYBIT_LINEAR_WS",
    ),
    "app/ws_collector.py": ("BINANCE_STREAM_BASE", "BYBIT_URL"),
}


def _identity_line_spans(relative: str) -> list[tuple[int, int]]:
    """Marker spans, read from the file itself rather than from the registry.

    Both collectors are covered as whole ``python_module`` components since the
    third R05 correction, so they contribute no *region* components.  Keying
    this sweep on the component list would therefore find nothing and pass
    vacuously; reading the markers from the source keeps it load-bearing.
    """

    lines = (ROOT / relative).read_text(encoding="utf-8").splitlines()
    spans: list[tuple[int, int]] = []
    begin: int | None = None
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped.startswith("# PR27_SCIENTIFIC_"):
            continue
        if stripped.endswith("_BEGIN"):
            assert begin is None, f"{relative}:{index} opens a region inside a region"
            begin = index
        elif stripped.endswith("_END"):
            assert begin is not None, f"{relative}:{index} closes an unopened region"
            spans.append((begin, index))
            begin = None
    assert begin is None, f"{relative} leaves a scientific region unclosed"
    assert spans, f"{relative} declares no scientific identity region"
    return spans


def _inside_identity(spans: list[tuple[int, int]], lineno: int) -> bool:
    return any(begin < lineno < end for begin, end in spans)


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_no_routing_material_call_sits_outside_an_identity_region(relative: str) -> None:
    """Red on c879bdec: the loops and entrypoints applied routing unprotected."""

    spans = _identity_line_spans(relative)
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    escaped = sorted(
        {
            (_called_name(node), node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _called_name(node) in ROUTING_MATERIAL_CALLS
            and not _inside_identity(spans, node.lineno)
        }
    )
    assert not escaped, (
        f"{relative}: routing-material calls outside every identity region: {escaped}"
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_endpoint_constants_are_inside_an_identity_region(relative: str) -> None:
    """Red on c879bdec: the venue endpoints were plain module constants."""

    spans = _identity_line_spans(relative)
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    expected = set(ROUTING_MATERIAL_ENDPOINTS[relative])
    protected = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and _inside_identity(spans, node.lineno)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert expected <= protected, (
        f"{relative}: endpoint constants outside the identity: "
        f"{sorted(expected - protected)}"
    )


def test_producer_entrypoints_wire_the_routing_inside_the_identity() -> None:
    """The single place that decides which routing each producer task gets."""

    for relative, wiring in (
        ("app/scalp_collector.py", "scalp_routing_producers"),
        ("app/ws_collector.py", "ws_routing_producers"),
    ):
        spans = _identity_line_spans(relative)
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        definitions = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == wiring
        ]
        assert definitions, f"{relative} does not define {wiring}()"
        assert all(_inside_identity(spans, lineno) for lineno in definitions), (
            f"{relative}: {wiring}() is outside every identity region"
        )


# --------------------------------------------------------------------------
# The bypass itself: a forged index converts ETH into BTC's internal key
# --------------------------------------------------------------------------


def test_a_forged_futures_index_cannot_map_an_eth_pair_onto_a_btc_key() -> None:
    """Red on c879bdec: this construction succeeded and misrouted silently."""

    routing = attest_raw_market_producer("scalp_collector")
    with pytest.raises(RawMarketProducerContractError) as excinfo:
        FuturesRoutingIndex(
            pairs=("ETHUSDT",),
            symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"},
            routing=routing,
        )
    assert "ETHUSDT" in str(excinfo.value)


def test_a_forged_spot_index_cannot_map_an_eth_pair_onto_a_btc_key() -> None:
    routing = attest_raw_market_producer("ws_collector")
    with pytest.raises(RawMarketProducerContractError) as excinfo:
        SpotRoutingIndex(
            pairs=("ETHUSDT",),
            base_asset_by_pair={"ETHUSDT": "BTC"},
            routing=routing,
        )
    assert "ETHUSDT" in str(excinfo.value)


def test_a_routing_index_cannot_be_built_without_its_attested_routing() -> None:
    """An index is a provenance record, not a bag of strings."""

    with pytest.raises(TypeError):
        FuturesRoutingIndex(  # type: ignore[call-arg]
            pairs=("ETHUSDT",), symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"}
        )
    with pytest.raises(TypeError):
        SpotRoutingIndex(  # type: ignore[call-arg]
            pairs=("ETHUSDT",), base_asset_by_pair={"ETHUSDT": "BTC"}
        )


def test_internal_key_validation_alone_misses_the_external_provenance() -> None:
    """Why the delivery gate needed a second question, not a stricter first one.

    ``BTCUSDT_PERP.A`` is a perfectly routed internal key, so the key gate is
    satisfied by construction.  Only the external pair that produced it reveals
    the misrouting, and that question did not exist on ``c879bdec``.
    """

    from app.signal_runtime_contract import require_routed_pair_origins

    routing = attest_raw_market_producer("scalp_collector")

    # The key gate cannot see anything wrong: the key is genuinely routed.
    require_routed_internal_keys(routing, "scalp_collector", {"BTCUSDT_PERP.A"})

    # The provenance gate rejects the conversion that produced it.
    with pytest.raises(RawMarketProducerContractError) as excinfo:
        require_routed_pair_origins(
            routing, "scalp_collector", [("ETHUSDT", "BTCUSDT_PERP.A")]
        )
    assert "ETHUSDT" in str(excinfo.value)

    require_routed_pair_origins(
        routing, "scalp_collector", [("BTCUSDT", "BTCUSDT_PERP.A")]
    )

    require_routed_internal_keys(routing, "ws_collector", {"BTC"})
    with pytest.raises(RawMarketProducerContractError):
        require_routed_pair_origins(routing, "ws_collector", [("ETHUSDT", "BTC")])
    require_routed_pair_origins(routing, "ws_collector", [("BTCUSDT", "BTC")])

    with pytest.raises(ValueError):
        require_routed_pair_origins(routing, "ingest", [("BTCUSDT", "BTCUSDT_PERP.A")])


# --------------------------------------------------------------------------
# Phase 3: the config.py region protects the projections, not the thresholds
# --------------------------------------------------------------------------


PROJECTION_MUTATIONS = (
    (
        "symbol-to-base-asset",
        "WS_SYMBOL_MAP = {item.symbol: item.base_asset for item in MARKET_SYMBOL_CATALOG}",
        "WS_SYMBOL_MAP = {item.symbol: item.spot_history_symbol for item in MARKET_SYMBOL_CATALOG}",
    ),
    (
        "symbol-to-futures-pair",
        "FUTURES_PAIR_MAP = {item.symbol: item.futures_pair for item in MARKET_SYMBOL_CATALOG}",
        "FUTURES_PAIR_MAP = {item.symbol: item.bybit_oi_symbol for item in MARKET_SYMBOL_CATALOG}",
    ),
    (
        "base-asset-to-spot-pair",
        "SPOT_PAIR_MAP = {item.base_asset: item.spot_pair for item in MARKET_SYMBOL_CATALOG}",
        "SPOT_PAIR_MAP = {item.base_asset: item.futures_pair for item in MARKET_SYMBOL_CATALOG}",
    ),
    (
        "futures-pair-to-symbol",
        "PAIR_SYMBOL_MAP = {item.futures_pair: item.symbol for item in MARKET_SYMBOL_CATALOG}",
        "PAIR_SYMBOL_MAP = {item.bybit_oi_symbol: item.symbol for item in MARKET_SYMBOL_CATALOG}",
    ),
)


@pytest.mark.parametrize(
    ("label", "old", "new"),
    PROJECTION_MUTATIONS,
    ids=[case[0] for case in PROJECTION_MUTATIONS],
)
def test_changing_a_routing_projection_moves_the_identity(
    tmp_path: Path, label: str, old: str, new: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert _mutate(root, "app/config.py", old, new) != baseline, label


NON_MATERIAL_CATALOG_MUTATIONS = (
    ("whale-threshold", "5_000_000.0, 1_000_000.0", "5_000_001.0, 1_000_000.0"),
    ("large-trade-threshold", "5_000_000.0, 1_000_000.0", "5_000_000.0, 1_000_001.0"),
    ("bybit-oi-symbol", '"BTCUSDT.6"', '"BTCUSDT.7"'),
    ("spot-history-symbol", '"BTCUSD.A"', '"BTCUSD.B"'),
)


@pytest.mark.parametrize(
    ("label", "old", "new"),
    NON_MATERIAL_CATALOG_MUTATIONS,
    ids=[case[0] for case in NON_MATERIAL_CATALOG_MUTATIONS],
)
def test_non_material_catalog_values_stay_outside_the_runtime_contract(
    tmp_path: Path, label: str, old: str, new: str
) -> None:
    """Red on c879bdec: whale_threshold_usd moved 25f6c2e5... to 06da5f1f....

    The finding R05 made is about *result materiality*, and it is intact: none
    of these four fields reaches the confirmatory result, so none of them may
    change the runtime contract.  That half is asserted here directly.

    What changed with the discovered surface is the other half.  app/config.py
    used to be covered by a region narrowed to the four routing projections, so
    editing a threshold literal beside them moved nothing.  The whole file is
    covered now, so it does move the *code* digest -- not because the value
    became result-material, but because the source changed and the surface no
    longer has a fence somebody has to keep drawing in the right place.  The
    cost is a re-registration for an operational edit; the thing it buys is that
    no future edit can be placed outside the fence.
    """

    from dataclasses import replace

    from app.config import DEFAULT_MARKET_CATALOG
    from app.signal_runtime_contract import compute_scientific_runtime_contract

    field = {
        "whale-threshold": ("whale_threshold_usd", 5_000_001.0),
        "large-trade-threshold": ("large_trade_threshold_usd", 1_000_001.0),
        "bybit-oi-symbol": ("bybit_oi_symbol", "BTCUSDT.7"),
        "spot-history-symbol": ("spot_history_symbol", "BTCUSD.B"),
    }[label]
    mutated_catalog = tuple(
        replace(item, **{field[0]: field[1]})
        if item.symbol == "BTCUSDT_PERP.A"
        else item
        for item in DEFAULT_MARKET_CATALOG
    )
    symbols = tuple(item.symbol for item in DEFAULT_MARKET_CATALOG)
    assert compute_scientific_runtime_contract(
        catalog=mutated_catalog, symbols=symbols
    )["digest"] == compute_scientific_runtime_contract(
        catalog=DEFAULT_MARKET_CATALOG, symbols=symbols
    )["digest"], label

    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert _mutate(root, "app/config.py", old, new) != baseline, (
        f"{label}: editing app/config.py must move the code digest now that the "
        "file is covered whole"
    )


OPERATIONAL_MUTATIONS = (
    (
        "scalp-backoff",
        "app/scalp_collector.py",
        "backoff = min(backoff * 2, WS_RECONNECT_MAX_SECONDS)",
        "backoff = min(backoff * 3, WS_RECONNECT_MAX_SECONDS)",
    ),
    (
        "ws-backoff",
        "app/ws_collector.py",
        "backoff = min(backoff * 2, 60.0)",
        "backoff = min(backoff * 3, 60.0)",
    ),
    (
        "scalp-disconnect-logging",
        "app/scalp_collector.py",
        'LOGGER.warning("binance_futures_disconnected error=%s retry=%.1fs"',
        'LOGGER.error("binance_futures_disconnected error=%s retry=%.1fs"',
    ),
    (
        "ws-disconnect-logging",
        "app/ws_collector.py",
        'LOGGER.warning("binance_disconnected retry=%.1fs", backoff)',
        'LOGGER.error("binance_disconnected retry=%.1fs", backoff)',
    ),
    (
        "scalp-feed-health",
        "app/scalp_collector.py",
        'LIQ_FEED_CONNECTED["binance"] = True',
        'LIQ_FEED_CONNECTED["binance"] = bool(True)',
    ),
    (
        "ws-heartbeat-health",
        "app/ws_collector.py",
        "age <= 90.0 for age in ages.values()",
        "age <= 91.0 for age in ages.values()",
    ),
)


@pytest.mark.parametrize(
    ("label", "relative", "old", "new"),
    OPERATIONAL_MUTATIONS,
    ids=[case[0] for case in OPERATIONAL_MUTATIONS],
)
def test_operational_plumbing_now_moves_the_identity(
    tmp_path: Path, label: str, relative: str, old: str, new: str
) -> None:
    """Reversed deliberately by the third R05 correction -- see ADR-012.

    Backoff, logging level, feed-health flags and heartbeat thresholds used to
    be neutral, and that neutrality is what required the collectors' scientific
    surface to be an enumerated set of regions.  Three reviews walked around
    that enumeration.  Both collectors are hashed whole now, so every
    executable edit to them is material -- this suite states the cost instead
    of hiding it.
    """

    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert _mutate(root, relative, old, new) != baseline, label


def test_the_mutation_tree_covers_every_file_the_mutations_touch() -> None:
    """Guard against a mutation silently landing outside the copied tree."""

    touched = {case[2] for case in APPLICATION_MUTATIONS} | {
        case[1] for case in OPERATIONAL_MUTATIONS
    } | {"app/config.py"}
    assert touched <= set(IDENTITY_FILES)
