"""PR27-R05, second correction: the wiring, not the first textual occurrence.

``700f7695`` and ``450cf2fb`` were both offered as the R05 closure and both were
refuted by independent review.  The mutation suite they shipped
(``test_pr27_r05_routing_application_closure.py``) rewrites the *first textual
occurrence* of a routing-material expression.  After that correction the first
occurrence sits inside a region -- ``routing.futures_index(ACTIVE_SYMBOLS)``
lives in ``scalp_futures_index()``, ``binance_loop(routing=routing)`` lives in
``scalp_routing_producers()`` -- so the digest moves and the suite goes green
while the *real* call sites remain unprotected somewhere else in the file.

The review demonstrated three consequences on ``450cf2fb``:

1. The real invocations -- ``scalp_routing_producers()`` in ``main()`` and
   ``ws_routing_producers()`` in ``run()`` -- are outside the identity.
   Replacing them with hand-rolled wiring that gives the *producer* a forged
   routing and the *flusher* the correct one left the digest at
   ``5a5cb09f80ce17903409daf8fc90e7d05e060a578183aed629d680f37280f05f``.
2. The real session selection is outside the identity.  Swapping
   ``binance_futures_session`` for ``binance_market_session`` in
   ``binance_loop()``, and ``binance_spot_session`` for ``bybit_spot_session``
   in ``binance_consumer()``, left the digest unchanged.
3. ``EffectiveMarketRouting`` is constructible by hand.  A forged one whose
   rows read ``symbol=BTCUSDT_PERP.A, futures_pair=ETHUSDT`` is internally
   self-consistent, so it produces a ``FuturesRoutingIndex`` /
   ``SpotRoutingIndex`` that maps ETH's market onto BTC's internal key, and the
   delivery gate -- handed the *correct* routing -- accepts the resulting key.

Every mutation below is anchored through the AST to the symbol's real reference
sites, never to a text offset, so a future correction cannot satisfy it by
moving a duplicate expression into a region.  The structural sweep states the
invariant positively: after the correction *no* routing-material symbol is
referenced anywhere outside a scientific identity region in either collector,
so there is nothing material left outside for a mutation to reach.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from app.signal_runtime_contract import (
    REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    EffectiveMarketRouting,
    FuturesRoutingIndex,
    MarketRoute,
    RawMarketProducerContractError,
    SpotRoutingIndex,
    attest_raw_market_producer,
    require_routed_internal_keys,
)
from app.signal_scientific_identity import (
    SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS,
    compute_scientific_implementation_identity,
)
from tests.test_pr27_r05_routing_closure import IDENTITY_FILES

ROOT = Path(__file__).resolve().parents[1]

COLLECTOR_MODULES = ("app/scalp_collector.py", "app/ws_collector.py")

# The digest the independent review observed while each of the three mutations
# was applied to 450cf2fb.  Recorded as history: no assertion compares against
# it, because the correction recomputes identity-v1.
REVIEWED_UNMOVED_DIGEST = (
    "5a5cb09f80ce17903409daf8fc90e7d05e060a578183aed629d680f37280f05f"
)

REGISTERED_CONTRACT_DIGEST = REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS[
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
]


# --------------------------------------------------------------------------
# AST-anchored mutation of the *real* reference sites
# --------------------------------------------------------------------------


def _identity_tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for relative in IDENTITY_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    return root


def _load_positions(source: str, symbol: str) -> list[tuple[int, int]]:
    """Every position where ``symbol`` is *read*, per the AST.

    Definitions, imports and attribute keys are excluded on purpose: what the
    review substituted was a use, and a use is what must be protected.
    """

    tree = ast.parse(source)
    return sorted(
        {
            (node.lineno, node.col_offset)
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.id == symbol
            and isinstance(node.ctx, ast.Load)
        }
    )


def _rewrite_load_sites(source: str, symbol: str, replacement: str) -> tuple[str, int]:
    """Replace ``symbol`` at exactly its AST read positions, byte-accurately."""

    positions = _load_positions(source, symbol)
    lines = source.splitlines(keepends=True)
    for lineno, col in reversed(positions):
        raw = lines[lineno - 1].encode("utf-8")
        assert raw[col : col + len(symbol)] == symbol.encode("utf-8"), (
            f"AST position {lineno}:{col} does not spell {symbol!r}"
        )
        lines[lineno - 1] = (
            raw[:col] + replacement.encode("utf-8") + raw[col + len(symbol) :]
        ).decode("utf-8")
    return "".join(lines), len(positions)


def _mutate_real_uses(
    root: Path, relative: str, symbol: str, replacement: str
) -> tuple[str, int]:
    path = root / relative
    mutated, count = _rewrite_load_sites(
        path.read_text(encoding="utf-8"), symbol, replacement
    )
    path.write_text(mutated, encoding="utf-8")
    return compute_scientific_implementation_identity(root=root)["digest"], count


# Finding 2: the real session selection.  Pre-correction the single read of each
# session name sits in a reconnect loop or a consumer, both outside every
# region, so swapping venues is invisible.  Post-correction the single read is
# the binding the identity covers.
SESSION_SELECTION_MUTATIONS = (
    (
        "scalp-binance-futures-session",
        "app/scalp_collector.py",
        "binance_futures_session",
        "binance_market_session",
    ),
    (
        "scalp-binance-market-session",
        "app/scalp_collector.py",
        "binance_market_session",
        "binance_futures_session",
    ),
    (
        "scalp-bybit-linear-session",
        "app/scalp_collector.py",
        "bybit_linear_session",
        "binance_futures_session",
    ),
    (
        "ws-binance-spot-session",
        "app/ws_collector.py",
        "binance_spot_session",
        "bybit_spot_session",
    ),
    (
        "ws-bybit-spot-session",
        "app/ws_collector.py",
        "bybit_spot_session",
        "binance_spot_session",
    ),
)


@pytest.mark.parametrize(
    ("label", "relative", "symbol", "replacement"),
    SESSION_SELECTION_MUTATIONS,
    ids=[case[0] for case in SESSION_SELECTION_MUTATIONS],
)
def test_swapping_the_real_session_selection_moves_the_identity(
    tmp_path: Path, label: str, relative: str, symbol: str, replacement: str
) -> None:
    """Red on 450cf2fb: the loops chose the venue outside the identity."""

    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    assert baseline == compute_scientific_implementation_identity()["digest"]
    digest, count = _mutate_real_uses(root, relative, symbol, replacement)
    assert count >= 1, f"{label}: {symbol} is never read in {relative}"
    assert digest != baseline, (
        f"{label}: swapping every real read of {symbol}() for {replacement}() "
        f"left the scientific identity unchanged"
    )


# Finding 1: the real routing injection.  ``main()`` and ``run()`` are the only
# callers of the per-process wiring, and on 450cf2fb both calls are outside the
# identity, so the entrypoint is free to wire a forged routing into the
# subscriptions and the attested one into the flushes.
ROUTING_INJECTION_MUTATIONS = (
    (
        "scalp-routing-producers-invocation",
        "app/scalp_collector.py",
        "scalp_routing_producers",
        "_forged_scalp_wiring",
    ),
    (
        "ws-routing-producers-invocation",
        "app/ws_collector.py",
        "ws_routing_producers",
        "_forged_ws_wiring",
    ),
    (
        "scalp-index-factory-invocation",
        "app/scalp_collector.py",
        "scalp_futures_index",
        "_forged_scalp_index",
    ),
    (
        "ws-index-factory-invocation",
        "app/ws_collector.py",
        "ws_spot_index",
        "_forged_ws_index",
    ),
)


@pytest.mark.parametrize(
    ("label", "relative", "symbol", "replacement"),
    ROUTING_INJECTION_MUTATIONS,
    ids=[case[0] for case in ROUTING_INJECTION_MUTATIONS],
)
def test_substituting_the_real_routing_injection_moves_the_identity(
    tmp_path: Path, label: str, relative: str, symbol: str, replacement: str
) -> None:
    """Red on 450cf2fb: main()/run() invoked the wiring outside the identity."""

    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    digest, count = _mutate_real_uses(root, relative, symbol, replacement)
    assert count >= 1, f"{label}: {symbol} is never read in {relative}"
    assert digest != baseline, (
        f"{label}: substituting every real invocation of {symbol}() left the "
        f"scientific identity unchanged"
    )


# --------------------------------------------------------------------------
# The structural sweep: nothing material may live outside a region
# --------------------------------------------------------------------------
#
# Anything that can change which venue is read, which pairs are subscribed,
# which session is opened, which external pair becomes which internal key,
# which store's contents are delivered, or which routing a task receives.
#
# ``binance_loop`` and the flush loops appear here as *symbols*: their bodies
# stay outside the identity because they hold backoff, logging, feed health and
# sleeps, but the wiring that decides what they run may not.
MATERIAL_SYMBOLS = frozenset(
    {
        # Sessions: the line that chooses a venue and opens the connection.
        "binance_futures_session",
        "binance_market_session",
        "bybit_linear_session",
        "binance_spot_session",
        "bybit_spot_session",
        # Index construction: external pair -> internal key.
        "scalp_futures_index",
        "ws_spot_index",
        "futures_index",
        "spot_index",
        "FuturesRoutingIndex",
        "SpotRoutingIndex",
        # Subscription surface.
        "binance_futures_streams",
        "binance_force_order_streams",
        "bybit_linear_topics",
        "binance_url",
        "spot_pairs",
        "bybit_subscription_args",
        # Venue endpoints.
        "BINANCE_STREAM_BASE",
        "BINANCE_MARKET_STREAM_BASE",
        "BYBIT_LINEAR_WS",
        "BYBIT_URL",
        # Dispatch.
        "handle_binance",
        "handle_bybit",
        "handle_binance_spot",
        "handle_bybit_spot",
        # Store -> raw delivery.
        "flush_trades_cycle",
        "flush_books_cycle",
        "flush_liquidations_cycle",
        "flush_minute_cycle",
        "flush_realtime_cycle",
        "deliver_futures_trades",
        "deliver_orderbook_state",
        "deliver_liquidations",
        "deliver_spot_minute",
        "deliver_spot_realtime",
        # The routing itself and its attestation.
        "EffectiveMarketRouting",
        "MarketRoute",
        "attest_raw_market_producer",
        "effective_market_routing_from_contract",
        "require_routed_internal_keys",
        "require_routed_pair_origins",
        "RAW_PRODUCER",
        # The single injection and the material tasks it creates.
        "scalp_routing_producers",
        "ws_routing_producers",
        "binance_loop",
        "binance_market_loop",
        "bybit_loop",
        "binance_consumer",
        "bybit_consumer",
        "flush_trades",
        "flush_books",
        "flush_liquidations",
        "flush_minute",
        "flush_realtime",
    }
)

# The only material names an entrypoint may name.  Both are defined inside a
# region, neither accepts or returns a routing, so ``main()``/``run()`` cannot
# hold one and therefore cannot inject one.
ENTRYPOINT_STARTERS = {
    "app/scalp_collector.py": (
        "main",
        ("require_attested_scalp_routing", "start_scalp_routing_producers"),
    ),
    "app/ws_collector.py": (
        "run",
        ("require_attested_ws_routing", "start_ws_routing_producers"),
    ),
}

ALLOWED_OUTSIDE = frozenset(
    starter for _entry, starters in ENTRYPOINT_STARTERS.values() for starter in starters
)


def _identity_spans(root: Path, relative: str) -> list[tuple[int, int]]:
    lines = (root / relative).read_text(encoding="utf-8").splitlines()
    spans: list[tuple[int, int]] = []
    for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS:
        if component.relative_path != relative:
            continue
        begin = next(
            index for index, line in enumerate(lines, 1) if component.begin_marker in line
        )
        end = next(
            index for index, line in enumerate(lines, 1) if component.end_marker in line
        )
        spans.append((begin, end))
    assert spans, f"{relative} declares no scientific identity region"
    return spans


def _inside_identity(spans: list[tuple[int, int]], lineno: int) -> bool:
    return any(begin < lineno < end for begin, end in spans)


def _annotation_nodes(tree: ast.AST) -> set[int]:
    """Nodes that only describe a type.

    ``from __future__ import annotations`` makes annotations non-evaluated, so a
    parameter typed ``EffectiveMarketRouting`` neither holds one nor can forge
    one.  Excluding them keeps the sweep about behaviour.
    """

    annotated: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for argument in (
                *args.posonlyargs,
                *args.args,
                *args.kwonlyargs,
                args.vararg,
                args.kwarg,
            ):
                if argument is not None and argument.annotation is not None:
                    annotated.append(argument.annotation)
            if node.returns is not None:
                annotated.append(node.returns)
        elif isinstance(node, ast.AnnAssign):
            annotated.append(node.annotation)
    excluded: set[int] = set()
    for annotation in annotated:
        for node in ast.walk(annotation):
            excluded.add(id(node))
    return excluded


def _material_escapes(root: Path, relative: str) -> list[tuple[str, int]]:
    """Every material symbol read outside every identity region."""

    source = (root / relative).read_text(encoding="utf-8")
    spans = _identity_spans(root, relative)
    tree = ast.parse(source)
    annotations = _annotation_nodes(tree)
    return sorted(
        {
            (node.id, node.lineno)
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in MATERIAL_SYMBOLS
            and node.id not in ALLOWED_OUTSIDE
            and id(node) not in annotations
            and not _inside_identity(spans, node.lineno)
        }
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_no_material_symbol_is_read_outside_an_identity_region(relative: str) -> None:
    """Red on 450cf2fb: the loops, the consumers and main()/run() all were.

    This is the invariant the two refuted candidates asserted in prose and never
    enforced: if nothing material is reachable outside a region, there is
    nothing outside for a mutation to substitute.
    """

    escapes = _material_escapes(ROOT, relative)
    assert not escapes, (
        f"{relative}: routing-material symbols read outside every identity "
        f"region: {escapes}"
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_the_entrypoint_names_only_its_region_exported_starters(relative: str) -> None:
    """Red on 450cf2fb: main()/run() named the wiring and held the routing."""

    entrypoint, starters = ENTRYPOINT_STARTERS[relative]
    source = (ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source)
    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == entrypoint
    ]
    assert len(definitions) == 1, f"{relative} does not define a single {entrypoint}()"
    named = {
        node.id
        for node in ast.walk(definitions[0])
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    material = named & (MATERIAL_SYMBOLS | ALLOWED_OUTSIDE)
    assert material == set(starters), (
        f"{relative}: {entrypoint}() may name only {sorted(starters)}, "
        f"it names {sorted(material)}"
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_the_region_exported_starters_are_defined_inside_the_identity(
    relative: str,
) -> None:
    """The two names the entrypoint may call must themselves be protected."""

    _entrypoint, starters = ENTRYPOINT_STARTERS[relative]
    source = (ROOT / relative).read_text(encoding="utf-8")
    spans = _identity_spans(ROOT, relative)
    tree = ast.parse(source)
    for starter in starters:
        definitions = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == starter
        ]
        assert definitions, f"{relative} does not define {starter}()"
        assert all(_inside_identity(spans, lineno) for lineno in definitions), (
            f"{relative}: {starter}() is outside every identity region"
        )


def _create_task_lines(tree: ast.AST) -> list[int]:
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_task"
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_material_producer_tasks_are_created_inside_the_identity(relative: str) -> None:
    """Red on 450cf2fb: main()/run() created the producer tasks themselves.

    Creating the task is the moment a producer becomes real.  While that
    happens outside the identity the entrypoint decides what actually runs, and
    the digest never sees the decision.
    """

    source = (ROOT / relative).read_text(encoding="utf-8")
    spans = _identity_spans(ROOT, relative)
    tree = ast.parse(source)
    assert any(_inside_identity(spans, lineno) for lineno in _create_task_lines(tree)), (
        f"{relative}: no producer task is created inside an identity region"
    )


@pytest.mark.parametrize("relative", COLLECTOR_MODULES)
def test_the_entrypoint_creates_no_task_from_a_material_producer(
    relative: str,
) -> None:
    """The entrypoint may still start its monitors -- nothing routing-material."""

    entrypoint, _starters = ENTRYPOINT_STARTERS[relative]
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    definition = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == entrypoint
    )
    offenders = sorted(
        {
            (name.id, call.lineno)
            for call in ast.walk(definition)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "create_task"
            for name in ast.walk(call)
            if isinstance(name, ast.Name) and name.id in MATERIAL_SYMBOLS
        }
    )
    assert not offenders, (
        f"{relative}: {entrypoint}() creates tasks from material producers: "
        f"{offenders}"
    )


# --------------------------------------------------------------------------
# Runtime fail-closed, before the subscription and before the store
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("map_name", "key", "value"),
    (
        ("FUTURES_PAIR_MAP", "BTCUSDT_PERP.A", "ETHUSDT"),
        ("WS_SYMBOL_MAP", "BTCUSDT_PERP.A", "ETH"),
    ),
    ids=["futures-pair-map", "ws-symbol-map"],
)
def test_an_index_cannot_be_built_once_the_runtime_stops_matching(
    map_name: str, key: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A routing attested a minute ago is not a routing attested now.

    The producer holds one frozen routing for the life of the process.  If the
    effective maps drift underneath it, every index built from it afterwards
    must fail closed -- before a subscription, before a store, before a write.
    """

    from app import config

    attested = attest_raw_market_producer("scalp_collector")
    monkeypatch.setitem(getattr(config, map_name), key, value)
    with pytest.raises(RawMarketProducerContractError):
        attested.futures_index(attested.symbols)
    with pytest.raises(RawMarketProducerContractError):
        attested.spot_index(attested.symbols)


@pytest.mark.asyncio
async def test_a_scalp_session_fails_closed_before_it_connects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No socket may open under a routing the registry no longer reproduces."""

    import app.scalp_collector as scalp
    from app import config

    attested = attest_raw_market_producer("scalp_collector")
    connected: list[str] = []

    def refuse(*args: object, **kwargs: object) -> object:
        connected.append("connect")
        raise AssertionError("the session opened a connection under a bad routing")

    monkeypatch.setattr(scalp.websockets, "connect", refuse)
    monkeypatch.setitem(config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A", "ETHUSDT")

    async def unreachable(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("callback ran under a bad routing")

    with pytest.raises(RawMarketProducerContractError):
        await scalp.binance_futures_session(
            attested, on_connected=unreachable, on_message=unreachable
        )
    assert connected == []


@pytest.mark.asyncio
async def test_a_ws_session_fails_closed_before_it_connects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.ws_collector as ws
    from app import config

    attested = attest_raw_market_producer("ws_collector")
    connected: list[str] = []

    def refuse(*args: object, **kwargs: object) -> object:
        connected.append("connect")
        raise AssertionError("the session opened a connection under a bad routing")

    monkeypatch.setattr(ws, "connect", refuse)
    monkeypatch.setitem(config.SPOT_PAIR_MAP, "BTC", "ETHUSDT")

    async def unreachable(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("callback ran under a bad routing")

    with pytest.raises(RawMarketProducerContractError):
        await ws.binance_spot_session(
            attested.symbols[:1],
            attested,
            on_connected=unreachable,
            on_message=unreachable,
        )
    assert connected == []


@pytest.mark.parametrize(
    ("module_name", "starter"),
    (
        ("app.scalp_collector", "start_scalp_routing_producers"),
        ("app.ws_collector", "start_ws_routing_producers"),
    ),
    ids=["scalp", "ws"],
)
def test_the_starter_refuses_to_create_tasks_under_a_bad_routing(
    module_name: str, starter: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail closed before a single producer task exists."""

    import importlib

    from app import config

    module = importlib.import_module(module_name)
    started = getattr(module, starter)
    monkeypatch.setitem(config.FUTURES_PAIR_MAP, "BTCUSDT_PERP.A", "ETHUSDT")

    created: list[object] = []
    monkeypatch.setattr(
        module.asyncio,
        "create_task",
        lambda *args, **kwargs: created.append(args) or None,
    )
    arguments: tuple[object, ...] = (object(), object())
    if module_name == "app.ws_collector":
        arguments = (*arguments, ("BTCUSDT_PERP.A",))
    with pytest.raises(RawMarketProducerContractError):
        started(*arguments)
    assert created == []


# --------------------------------------------------------------------------
# Finding 3: a forged EffectiveMarketRouting is not provenance
# --------------------------------------------------------------------------


def _forged_routing(attested: EffectiveMarketRouting) -> EffectiveMarketRouting:
    """BTC's internal keys pointed at ETH's external markets.

    Self-consistent by construction, and carrying the *registered* digest
    string, which is exactly why a self-consistency check cannot see it.
    """

    return EffectiveMarketRouting(
        contract_version=attested.contract_version,
        contract_digest=attested.contract_digest,
        routes=(
            MarketRoute(
                symbol="BTCUSDT_PERP.A",
                base_asset="BTC",
                futures_pair="ETHUSDT",
                spot_pair="ETHUSDT",
            ),
        ),
    )


def test_a_forged_routing_cannot_produce_a_futures_index() -> None:
    """Red on 450cf2fb: this returned ETHUSDT -> BTCUSDT_PERP.A happily."""

    attested = attest_raw_market_producer("scalp_collector")
    forged = _forged_routing(attested)
    assert forged.contract_digest == REGISTERED_CONTRACT_DIGEST
    with pytest.raises(RawMarketProducerContractError):
        forged.futures_index(("BTCUSDT_PERP.A",))


def test_a_forged_routing_cannot_produce_a_spot_index() -> None:
    attested = attest_raw_market_producer("ws_collector")
    forged = _forged_routing(attested)
    with pytest.raises(RawMarketProducerContractError):
        forged.spot_index(("BTCUSDT_PERP.A",))


def test_a_forged_routing_cannot_be_handed_to_an_index_directly() -> None:
    """The dataclass constructor is the same door, and must be shut too."""

    attested = attest_raw_market_producer("scalp_collector")
    forged = _forged_routing(attested)
    with pytest.raises(RawMarketProducerContractError):
        FuturesRoutingIndex(
            pairs=("ETHUSDT",),
            symbol_by_pair={"ETHUSDT": "BTCUSDT_PERP.A"},
            routing=forged,
        )
    with pytest.raises(RawMarketProducerContractError):
        SpotRoutingIndex(
            pairs=("ETHUSDT",),
            base_asset_by_pair={"ETHUSDT": "BTC"},
            routing=forged,
        )


def test_a_registered_digest_string_is_not_provenance() -> None:
    """A routing that merely *says* it matches the contract proves nothing.

    The forged routing above carries the registered digest verbatim.  What must
    be required is that the registry, recomputed now, reproduces these very
    rows -- not that the object agrees with itself.
    """

    attested = attest_raw_market_producer("scalp_collector")
    forged = _forged_routing(attested)
    assert forged.contract_digest == attested.contract_digest
    assert forged != attested
    with pytest.raises(RawMarketProducerContractError):
        forged.futures_index(("BTCUSDT_PERP.A",))


def test_the_delivery_gate_alone_still_accepts_the_forged_origin_key() -> None:
    """Why the index, not the delivery, is where this had to be closed.

    ``BTCUSDT_PERP.A`` is a genuinely routed internal key.  Handed the correct
    routing, the delivery gate has nothing to object to -- which is exactly how
    the review's bypass reached the store and the write.
    """

    attested = attest_raw_market_producer("scalp_collector")
    require_routed_internal_keys(attested, "scalp_collector", {"BTCUSDT_PERP.A"})
    require_routed_internal_keys(attested, "ws_collector", {"BTC"})


def test_an_attested_routing_still_builds_its_own_indexes() -> None:
    """Fail-closed must not mean fail-always."""

    attested = attest_raw_market_producer("scalp_collector")
    futures = attested.futures_index(attested.symbols)
    assert set(futures.pairs) == set(attested.futures_pair_by_symbol.values())
    spot = attested.spot_index(attested.symbols)
    assert set(spot.pairs) == set(attested.spot_pair_by_symbol.values())


# --------------------------------------------------------------------------
# The other direction: the plumbing the closure deliberately left outside
# --------------------------------------------------------------------------
#
# A boundary is only a claim if it is fixed in both directions.  The loops now
# invoke an opaque ``connect``/``cycle``; that invocation is transport, and
# breaking it can only cost data -- a visible ``data_gap`` -- never file one
# market's data under another's key.  It must therefore stay out of the
# identity, exactly like backoff, logging and feed health already are.

WIRING_NEUTRAL_MUTATIONS = (
    (
        "scalp-feed-invocation",
        "app/scalp_collector.py",
        "await connect(on_connected=on_connected, on_message=on_message)",
        "await connect(on_message=on_message, on_connected=on_connected)",
    ),
    (
        "scalp-flush-invocation",
        "app/scalp_collector.py",
        "if await cycle():\n                LAST_FLUSH[\"trades\"] = time.monotonic()",
        "if await cycle():\n                LAST_FLUSH[\"trades\"] = time.monotonic() + 0.0",
    ),
    (
        "ws-feed-invocation",
        "app/ws_collector.py",
        "await connect(on_connected=on_connected, on_message=on_message)",
        "await connect(on_message=on_message, on_connected=on_connected)",
    ),
    (
        "ws-flush-sleep",
        "app/ws_collector.py",
        "await asyncio.sleep(5)",
        "await asyncio.sleep(6)",
    ),
)


@pytest.mark.parametrize(
    ("label", "relative", "old", "new"),
    WIRING_NEUTRAL_MUTATIONS,
    ids=[case[0] for case in WIRING_NEUTRAL_MUTATIONS],
)
def test_the_plumbing_left_outside_never_moves_the_identity(
    tmp_path: Path, label: str, relative: str, old: str, new: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    path = root / relative
    source = path.read_text(encoding="utf-8")
    assert source.count(old) >= 1, f"{label}: missing plumbing {old!r}"
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    assert compute_scientific_implementation_identity(root=root)["digest"] == baseline, (
        f"{label}: an operational edit moved the scientific identity"
    )
