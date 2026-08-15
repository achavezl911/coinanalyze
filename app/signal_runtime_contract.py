"""Deterministic contract for result-material runtime scientific configuration.

Hashing scientific source proves *what the code computes*.  It cannot prove
*which raw inputs the code selected*, because the selection is driven by values
resolved at runtime from the environment and from the versioned market catalog.

``scalp_context`` binds ``WS_SYMBOL_MAP[symbol]`` as a query parameter.  The AST
canonicalizer hashes that expression, never its resolved value, and the resolved
value never reaches the persisted context, so it is absent from the replay frame
and from ``context_hash``.  An operator who repoints ``BTCUSDT_PERP.A`` at a
different spot asset therefore produces a different immutable context under an
identical source digest, and replay faithfully reproduces the wrong context.

This module freezes the missing half: the resolved *values* that decide which
market data is selected or how it is interpreted.  It is deliberately narrow.
It is not the environment, not the repository, and never a secret.  Every field
here was proven result-material by tracing it to a scientific read; every field
of the catalog that is absent was proven operational.  See
``docs/PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md``.

The registered mapping is append-only by policy.  A legitimate change to
result-material routing must register a new contract version; it must never
replace the digest registered for an existing one.

Freezing the contract is not the same as enforcing it early enough.  Gating only
the scientific-evidence boundary leaves the raw producers free to write a foreign
market's data under the internal key the kernel reads, so restoring the
registered routing would make an observation stamped with the registered digest
consume rows that were never produced under it.  ``attest_raw_market_producer``
therefore moves the same gate to the raw producer boundary.

Attesting the routing is in turn not the same as proving the producer applied
it.  The R05 review showed that a routing index built by hand -- one that maps
ETH's external pair onto BTC's internal key -- passes every gate that inspects
only the internal key, because the key it produces is genuinely routed.  The
two routing indexes are therefore constructible only from an attested
``EffectiveMarketRouting``, which validates each conversion at construction, and
``require_routed_pair_origins`` states the same invariant as a reusable gate.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app import config
from app.config import MarketSymbol

SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1 = 1
SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER = (
    "scientific_runtime_contract_canonicalization_v1"
)


# PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_BEGIN

# Filled only after the resolved projection below has been implemented and the
# deterministic digest independently reproduced by tests.  Never mutate an
# existing key: register a new contract version instead.  The registry lives
# inside the identity region on purpose: repointing a registered digest is a
# semantic change to what the gate accepts, so it must move the identity.
REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS = {
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1: (
        "c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00"
    ),
}

# The exact result-material projection of one resolved market catalog row.
#
#   symbol         -- $1 of the scalp_context query, and the upstream market id
#                     for ohlcv / open_interest / funding / liquidations.
#   base_asset     -- $2 of the scalp_context query; selects spot_trades_realtime
#                     and therefore spot_price, spot_delta_3m and spot_volume_3m.
#   futures_pair   -- decides which Binance futures market the collector records
#                     under `symbol` (futures_trades_realtime, orderbook_snapshot).
#   spot_pair      -- decides which Binance spot market the collector records
#                     under `base_asset`.
#
# Intentionally absent, each proven non-scientific rather than assumed:
#
#   bybit_oi_symbol        -- reaches only the separate oi_bybit table, which no
#                             scientific region reads; endpoint-v2 requires Binance.
#   spot_history_symbol    -- reaches only spot_perp_flow and the daily aggregate,
#                             both outside the scientific surface.
#   whale_threshold_usd    -- buy_vol_usd/sell_vol_usd accumulate unconditionally
#   large_trade_threshold_usd  before the threshold test; the threshold only
#                             partitions inst_/mid_/retail_ columns, which the
#                             context never selects.  Its only reach is the
#                             diagnostic regime_label, excluded from the endpoint.
#
# The catalog file path and the spelling of any environment variable are absent
# by construction: only resolved values are projected.
_SCIENTIFIC_ROUTING_FIELDS_V1 = (
    "symbol",
    "base_asset",
    "futures_pair",
    "spot_pair",
)


def compute_scientific_runtime_contract(
    *,
    catalog: Sequence[MarketSymbol] | None = None,
    symbols: Sequence[str] | None = None,
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> dict[str, Any]:
    """Compute, without trusting the registry, one deterministic contract.

    Both defaults resolve at call time, never at import time, because the whole
    point is that runtime resolution can differ from what the source suggests.

    The scope is the configured symbol set, not the shard-assigned subset: every
    collector shard must resolve the same contract or only one shard could ever
    match the registry.
    """

    if contract_version != SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1:
        raise ValueError(
            f"unsupported scientific runtime contract version: {contract_version}"
        )

    resolved_catalog = (
        config.MARKET_SYMBOL_CATALOG if catalog is None else tuple(catalog)
    )
    scope = (
        config.get_settings().SYMBOLS if symbols is None else tuple(symbols)
    )

    by_symbol = {item.symbol: item for item in resolved_catalog}
    if len(by_symbol) != len(resolved_catalog):
        raise ValueError("resolved market catalog has duplicate symbols")

    # Sorting and de-duplicating here is what keeps the digest independent of how
    # the operator spelled SYMBOLS: csv or json, any order, repeated or padded
    # entries all resolve to the same set.
    scoped_symbols = sorted({str(symbol).strip() for symbol in scope if str(symbol).strip()})
    if not scoped_symbols:
        raise ValueError("scientific runtime contract requires at least one symbol")
    missing = [symbol for symbol in scoped_symbols if symbol not in by_symbol]
    if missing:
        raise ValueError(
            "scientific runtime contract symbols are absent from the resolved "
            f"market catalog: {', '.join(missing)}"
        )

    market_routing: list[dict[str, str]] = []
    for symbol in scoped_symbols:
        item = by_symbol[symbol]
        routing: dict[str, str] = {}
        for routing_field in _SCIENTIFIC_ROUTING_FIELDS_V1:
            value = getattr(item, routing_field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"scientific runtime routing field {routing_field!r} for symbol "
                    f"{symbol!r} must be a non-empty string"
                )
            routing[routing_field] = value
        market_routing.append(routing)

    payload = {
        "runtime_contract_version": contract_version,
        "canonicalizer": SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER,
        "market_routing": market_routing,
    }
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return {
        **payload,
        "digest": hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest(),
    }


@dataclass(frozen=True, slots=True)
class MarketRoute:
    """One resolved result-material routing row of the validated contract."""

    symbol: str
    base_asset: str
    futures_pair: str
    spot_pair: str


@dataclass(frozen=True, slots=True)
class FuturesRoutingIndex:
    """The futures projection a scalp producer applies for its assigned scope.

    The index is the only object that converts an external pair into the
    internal key the frozen kernel reads, so a hand-built one *is* the A-02
    bypass: it can file ETH's trades under BTC's key, and a delivery gate that
    validates only the internal key has nothing to object to.  Construction
    therefore requires the attested routing and replays every conversion the
    index would perform through it.
    """

    pairs: tuple[str, ...]
    symbol_by_pair: Mapping[str, str]
    routing: EffectiveMarketRouting

    def __post_init__(self) -> None:
        _require_indexed_pairs(self.pairs, self.symbol_by_pair)
        require_routed_pair_origins(
            self.routing, "scalp_collector", self.symbol_by_pair.items()
        )


@dataclass(frozen=True, slots=True)
class SpotRoutingIndex:
    """The spot projection a ws producer applies for its assigned scope.

    Bound to its attested routing for the same reason as
    ``FuturesRoutingIndex``: ``base_asset`` is $2 of the ``scalp_context``
    query, so a forged spot pair -> base asset entry contaminates the endpoint
    just as effectively.
    """

    pairs: tuple[str, ...]
    base_asset_by_pair: Mapping[str, str]
    routing: EffectiveMarketRouting

    def __post_init__(self) -> None:
        _require_indexed_pairs(self.pairs, self.base_asset_by_pair)
        require_routed_pair_origins(
            self.routing, "ws_collector", self.base_asset_by_pair.items()
        )


def _require_indexed_pairs(
    pairs: Sequence[str], internal_key_by_pair: Mapping[str, str]
) -> None:
    """Refuse a subscription list the conversion table cannot resolve."""

    unresolvable = sorted(set(pairs) - set(internal_key_by_pair))
    if unresolvable:
        raise RawMarketProducerContractError(
            "routing index subscribes to external pairs it cannot convert: "
            + ", ".join(unresolvable)
        )


@dataclass(frozen=True, slots=True)
class EffectiveMarketRouting:
    """The single typed, immutable representation of the effective routing.

    Built from an already-validated contract, once per producer start, and
    passed explicitly to subscriptions, handlers, flushes and writes.  It never
    reads the module-level routing dicts, so a later mutation of those dicts
    cannot change routing that was already validated and is in use.
    """

    contract_version: int
    contract_digest: str
    routes: tuple[MarketRoute, ...]
    symbols: tuple[str, ...] = field(init=False, repr=False, compare=False)
    base_assets: tuple[str, ...] = field(init=False, repr=False, compare=False)
    base_asset_by_symbol: Mapping[str, str] = field(init=False, repr=False, compare=False)
    futures_pair_by_symbol: Mapping[str, str] = field(init=False, repr=False, compare=False)
    spot_pair_by_symbol: Mapping[str, str] = field(init=False, repr=False, compare=False)
    symbol_by_futures_pair: Mapping[str, str] = field(init=False, repr=False, compare=False)
    base_asset_by_spot_pair: Mapping[str, str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        routes = tuple(self.routes)
        object.__setattr__(self, "routes", routes)
        if not routes or not all(isinstance(route, MarketRoute) for route in routes):
            raise ValueError("effective market routing requires MarketRoute rows")
        for route_field in ("symbol", "base_asset", "futures_pair", "spot_pair"):
            values = [getattr(route, route_field) for route in routes]
            if len(values) != len(set(values)):
                raise ValueError(
                    f"effective market routing has duplicate {route_field} values"
                )
        object.__setattr__(self, "symbols", tuple(route.symbol for route in routes))
        object.__setattr__(
            self, "base_assets", tuple(route.base_asset for route in routes)
        )
        object.__setattr__(
            self,
            "base_asset_by_symbol",
            MappingProxyType({route.symbol: route.base_asset for route in routes}),
        )
        object.__setattr__(
            self,
            "futures_pair_by_symbol",
            MappingProxyType({route.symbol: route.futures_pair for route in routes}),
        )
        object.__setattr__(
            self,
            "spot_pair_by_symbol",
            MappingProxyType({route.symbol: route.spot_pair for route in routes}),
        )
        object.__setattr__(
            self,
            "symbol_by_futures_pair",
            MappingProxyType({route.futures_pair: route.symbol for route in routes}),
        )
        object.__setattr__(
            self,
            "base_asset_by_spot_pair",
            MappingProxyType({route.spot_pair: route.base_asset for route in routes}),
        )

    def _require_symbols(self, symbols: Sequence[str]) -> tuple[str, ...]:
        scoped = tuple(symbols)
        missing = sorted(set(scoped) - set(self.symbols))
        if missing:
            raise ValueError(
                "symbols outside the validated effective routing: "
                + ", ".join(missing)
            )
        return scoped

    def futures_index(self, symbols: Sequence[str]) -> FuturesRoutingIndex:
        scoped = self._require_symbols(symbols)
        return FuturesRoutingIndex(
            pairs=tuple(self.futures_pair_by_symbol[symbol] for symbol in scoped),
            symbol_by_pair=MappingProxyType(
                {self.futures_pair_by_symbol[symbol]: symbol for symbol in scoped}
            ),
            routing=self,
        )

    def spot_index(self, symbols: Sequence[str]) -> SpotRoutingIndex:
        scoped = self._require_symbols(symbols)
        return SpotRoutingIndex(
            pairs=tuple(self.spot_pair_by_symbol[symbol] for symbol in scoped),
            base_asset_by_pair=MappingProxyType(
                {
                    self.spot_pair_by_symbol[symbol]: self.base_asset_by_symbol[symbol]
                    for symbol in scoped
                }
            ),
            routing=self,
        )


def effective_market_routing_from_contract(
    contract: Mapping[str, Any],
) -> EffectiveMarketRouting:
    """Project a contract into the frozen routing the producers must apply."""

    routes = tuple(MarketRoute(**route) for route in contract["market_routing"])
    return EffectiveMarketRouting(
        contract_version=contract["runtime_contract_version"],
        contract_digest=contract["digest"],
        routes=routes,
    )


# The four module-level dicts in ``app.config`` are the projection the legacy
# consumers still import.  They are kept for operational compatibility only and
# are never authoritative: the attestation requires them to agree with the
# validated contract, in both directions that can reach a configured internal
# key.  Entries for symbols outside the configured scope arise naturally from
# an extended catalog under a narrowed SYMBOLS and cannot reach a configured
# key, so they do not block.
def _assert_effective_maps_match_contract(contract: Mapping[str, Any]) -> None:
    routes = contract["market_routing"]
    ws_symbol_map = config.WS_SYMBOL_MAP
    futures_pair_map = config.FUTURES_PAIR_MAP
    spot_pair_map = config.SPOT_PAIR_MAP
    pair_symbol_map = config.PAIR_SYMBOL_MAP

    failures: list[str] = []
    registered_pair_by_symbol: dict[str, str] = {}
    for route in routes:
        symbol = route["symbol"]
        base_asset = route["base_asset"]
        futures_pair = route["futures_pair"]
        spot_pair = route["spot_pair"]
        registered_pair_by_symbol[symbol] = futures_pair
        if ws_symbol_map.get(symbol) != base_asset:
            failures.append(
                f"WS_SYMBOL_MAP[{symbol!r}] is {ws_symbol_map.get(symbol)!r}, "
                f"contract says {base_asset!r}"
            )
        if futures_pair_map.get(symbol) != futures_pair:
            failures.append(
                f"FUTURES_PAIR_MAP[{symbol!r}] is {futures_pair_map.get(symbol)!r}, "
                f"contract says {futures_pair!r}"
            )
        if spot_pair_map.get(base_asset) != spot_pair:
            failures.append(
                f"SPOT_PAIR_MAP[{base_asset!r}] is {spot_pair_map.get(base_asset)!r}, "
                f"contract says {spot_pair!r}"
            )
        if pair_symbol_map.get(futures_pair) != symbol:
            failures.append(
                f"PAIR_SYMBOL_MAP[{futures_pair!r}] is "
                f"{pair_symbol_map.get(futures_pair)!r}, contract says {symbol!r}"
            )
    for pair, symbol in pair_symbol_map.items():
        registered_pair = registered_pair_by_symbol.get(symbol)
        if registered_pair is not None and pair != registered_pair:
            failures.append(
                f"PAIR_SYMBOL_MAP[{pair!r}] aliases a foreign pair onto the "
                f"configured symbol {symbol!r} (registered pair {registered_pair!r})"
            )
    if failures:
        raise RuntimeError(
            "effective routing maps diverge from the validated runtime contract: "
            + "; ".join(sorted(failures))
        )


def scientific_runtime_contract(
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> dict[str, Any]:
    """Return the contract only when runtime resolution matches its registry.

    This is the producer-time gate.  While a non-registered routing is active no
    new scientific evidence may be written, so an A -> B -> A history cannot
    leave behind B rows that later pass as valid A evidence.

    A registered catalog is not enough: the producers and ``scalp_context``
    apply the derived module-level dicts, so the gate additionally requires
    those effective maps to agree with the validated contract.
    """

    contract = compute_scientific_runtime_contract(contract_version=contract_version)
    registered = REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS.get(contract_version)
    if registered is None:
        raise RuntimeError(
            f"scientific runtime contract version {contract_version} is not registered"
        )
    if contract["digest"] != registered:
        raise RuntimeError(
            "runtime scientific configuration does not match its registered "
            f"contract: expected {registered}, resolved {contract['digest']}"
        )
    _assert_effective_maps_match_contract(contract)
    return contract


class RawMarketProducerContractError(RuntimeError):
    """A result-material raw producer resolved an unregistered runtime contract."""


# The producers whose routing can put a foreign market's data under the internal
# key the frozen kernel reads, and the tables through which that happens.
#
# ``futures_pair`` and ``spot_pair`` never appear in a row key: the collector
# records whatever market they select under ``symbol`` and ``base_asset``
# respectively.  So routing B writes B's data under A's key, and restoring A
# cannot distinguish it -- ``scalp_context`` still has it inside its realtime
# windows.  Attesting the evidence boundary alone is therefore not enough: the
# contamination is already committed by the time an observation is written.
#
# ``symbol`` and ``base_asset`` are keys as well as selectors, so changing one
# relocates rows instead of contaminating them; they are still covered because
# the contract hashes all four fields together.
#
# Deliberately absent, each proven rather than assumed:
#
#   ingest        -- ohlcv, open_interest, funding and the 5m liquidation
#                    history route through ``{symbol: symbol}``: the upstream
#                    market id *is* the row key, so no routing value can fill
#                    A's key with B's data.  oi_bybit is a separate table with
#                    no scientific reader.
#   daily_agg     -- writes spot rows under the disjoint ``spot_history_symbol``
#     backfills      namespace and derives daily/baseline aggregates from rows
#                    already stored; it selects no external market.
#   api           -- writes nothing.
_RESULT_MATERIAL_RAW_PRODUCERS_V1 = {
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

# The internal key namespace each producer writes under: ``symbol`` for the
# futures family, ``base_asset`` for the spot family.  A delivery keyed outside
# it can only be a bug or tampering, and must fail closed.
_RAW_PRODUCER_INTERNAL_KEY_FIELDS_V1 = {
    "scalp_collector": "symbol",
    "ws_collector": "base_asset",
}

# The external market each producer is allowed to record under each internal
# key: ``futures_pair -> symbol`` for the futures family, ``spot_pair ->
# base_asset`` for the spot family.
#
# Validating the internal key alone cannot see a misrouting, because a
# misrouted row is keyed *correctly*: an index that maps ``ETHUSDT`` onto
# ``BTCUSDT_PERP.A`` produces rows whose key is genuinely routed, and only the
# external pair that produced them reveals the substitution.  This is the
# second question the R05 review found missing.
_RAW_PRODUCER_EXTERNAL_PAIR_FIELDS_V1 = {
    "scalp_collector": ("futures_pair", "symbol"),
    "ws_collector": ("spot_pair", "base_asset"),
}


def require_routed_pair_origins(
    routing: EffectiveMarketRouting,
    producer: str,
    origins: Iterable[tuple[str, str]],
) -> None:
    """Refuse an external pair -> internal key conversion the routing denies."""

    fields = _RAW_PRODUCER_EXTERNAL_PAIR_FIELDS_V1.get(producer)
    if fields is None:
        raise ValueError(f"unknown result-material raw producer: {producer!r}")
    external_field, internal_field = fields
    authorized = {
        getattr(route, external_field): getattr(route, internal_field)
        for route in routing.routes
    }
    forged = sorted(
        f"{pair}->{internal_key}"
        for pair, internal_key in origins
        if authorized.get(pair) != internal_key
    )
    if forged:
        tables = _RESULT_MATERIAL_RAW_PRODUCERS_V1[producer]
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} may not record {', '.join(tables)} "
            f"under an internal key its attested routing does not assign to the "
            f"external market that produced them: {', '.join(forged)}"
        )


def attest_raw_market_producer(
    producer: str,
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    *,
    expected: EffectiveMarketRouting | None = None,
) -> EffectiveMarketRouting:
    """Gate a raw producer before it may route or write result-material data.

    Correctness outranks availability here.  A service whose result-material
    routing is not the registered one must produce nothing at all rather than
    write scientifically misrouted rows that a later, legitimately registered
    configuration would silently consume.

    Returns the frozen effective routing derived from the validated contract:
    exactly the object the producer must apply.  ``expected`` re-attests a
    routing already in use; a runtime that no longer resolves to it blocks.
    """

    tables = _RESULT_MATERIAL_RAW_PRODUCERS_V1.get(producer)
    if tables is None:
        raise ValueError(f"unknown result-material raw producer: {producer!r}")
    try:
        contract = scientific_runtime_contract(contract_version)
    except RuntimeError as exc:
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} may not subscribe to or write "
            f"{', '.join(tables)} while the resolved scientific runtime "
            f"configuration is unregistered or diverges from the effective "
            f"routing maps: {exc}"
        ) from exc
    routing = effective_market_routing_from_contract(contract)
    if expected is not None and routing != expected:
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} resolved a routing that no "
            f"longer matches the attested routing in use; refusing "
            f"{', '.join(tables)}"
        )
    return routing


def require_routed_internal_keys(
    routing: EffectiveMarketRouting,
    producer: str,
    keys: Iterable[str],
) -> None:
    """Refuse a raw delivery keyed outside the attested routing's namespace."""

    key_field = _RAW_PRODUCER_INTERNAL_KEY_FIELDS_V1.get(producer)
    if key_field is None:
        raise ValueError(f"unknown result-material raw producer: {producer!r}")
    routed = {getattr(route, key_field) for route in routing.routes}
    foreign = sorted(set(keys) - routed)
    if foreign:
        tables = _RESULT_MATERIAL_RAW_PRODUCERS_V1[producer]
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} may not write "
            f"{', '.join(tables)} rows keyed outside its attested routing: "
            f"{', '.join(foreign)}"
        )


def validate_scientific_runtime_contract(stored: object) -> dict[str, Any]:
    """Fail closed when a frozen contract differs from runtime configuration."""

    if not isinstance(stored, dict):
        raise ValueError("scientific_runtime_contract must be an object")
    try:
        raw_contract_version = stored["runtime_contract_version"]
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "scientific_runtime_contract runtime_contract_version is invalid"
        ) from exc
    if isinstance(raw_contract_version, bool) or not isinstance(
        raw_contract_version, int
    ):
        raise ValueError(
            "scientific_runtime_contract runtime_contract_version must be an integer"
        )
    runtime = scientific_runtime_contract(raw_contract_version)
    if stored != runtime:
        raise ValueError(
            "frozen scientific runtime contract does not match runtime configuration"
        )
    return runtime


# PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_END
