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

Requiring *an* ``EffectiveMarketRouting`` is still not enough, which is what the
second review demonstrated: the class is constructible by hand, a forged row set
is self-consistent, and the registered digest is only a string it can carry.
``require_attested_routing`` closes that last door by re-deriving the contract
from the live configuration and requiring it to reproduce the routing being
used, so an index can exist only where the registry agrees -- before a
subscription, before a store and before a write.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from app import config
from app.config import MarketSymbol

SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1 = 1
SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER = (
    "scientific_runtime_contract_canonicalization_v2"
)


# PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_BEGIN

# There is no registered digest constant here any more, and its absence is the
# design.  A sharded deployment resolves a *different* environment digest per
# instance, so a single registered value would mean no shard other than 0 could
# ever validate.  ``identity/registry.json`` enumerates the authorized profiles
# instead, generated from declared axes, and validation is membership in that
# set.  See ``authorized_environment_digests``.

# The settings whose effective values decide what the science covers, how long
# it is kept, and which slice of the symbol set this instance observes.  Listed
# one by one rather than projected from ``vars(settings)``: a field added to
# Settings tomorrow must not enter the identity because somebody forgot that it
# would.
_SCIENTIFIC_ENVIRONMENT_SETTINGS_V1 = (
    "COLLECTOR_SHARD_INDEX",
    "COLLECTOR_SHARD_COUNT",
    "HARD_DATA_RETENTION_DAYS",
    "SCALP_MINUTE_RETENTION_HOURS",
)

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


# --- the authorized environment profiles ------------------------------------
#
# Declared here, inside the scientific surface, so that authorizing a new
# deployment profile is itself a material change that has to be re-registered.
# The set is generated from these axes, never written by hand.

AUTHORIZED_COLLECTOR_SHARD_PROFILES: tuple[Mapping[str, int], ...] = (
    MappingProxyType({"COLLECTOR_SHARD_INDEX": 0, "COLLECTOR_SHARD_COUNT": 1}),
)

# One interpreter, deliberately.  The interpreter is an axis of the profile, and
# every value enumerated here is a runtime the science is certified to produce
# the same results under.  Certifying a second one is a decision with evidence
# behind it -- the same walk-forward run, reproduced -- not a consequence of
# `requires-python` being permissive.  Until that evidence exists, a process on
# any other interpreter refuses to operate rather than quietly producing results
# nobody validated.
AUTHORIZED_INTERPRETERS: tuple[Mapping[str, str], ...] = (
    MappingProxyType({"python": "3.13", "implementation": "cpython"}),
)

# The environment settings that are not axes: one authorized value each.
AUTHORIZED_ENVIRONMENT_FIXED: Mapping[str, int] = MappingProxyType(
    {
        "HARD_DATA_RETENTION_DAYS": 14,
        "SCALP_MINUTE_RETENTION_HOURS": 36,
    }
)


def enumerate_authorized_environment_profiles(
    *,
    shard_profiles: Sequence[Mapping[str, int]] | None = None,
    interpreters: Sequence[Mapping[str, str]] | None = None,
    fixed: Mapping[str, int] | None = None,
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> tuple[dict[str, Any], ...]:
    """The cartesian product of the declared axes, with its digests.

    The routing half of each profile is whatever this tree resolves now, so
    re-registering after adding a versioned catalog registers that catalog.  The
    settings half is declarative and does not depend on the environment of
    whoever runs the generator: a stray ``HARD_DATA_RETENTION_DAYS`` in the
    shell must not be able to authorize itself.
    """

    profiles: list[dict[str, Any]] = []
    for shard in shard_profiles or AUTHORIZED_COLLECTOR_SHARD_PROFILES:
        for interpreter in interpreters or AUTHORIZED_INTERPRETERS:
            settings = {**dict(fixed or AUTHORIZED_ENVIRONMENT_FIXED), **dict(shard)}
            contract = compute_scientific_runtime_contract(
                environment_settings=settings,
                interpreter=interpreter,
                contract_version=contract_version,
            )
            profiles.append(
                {
                    "environment_settings": settings,
                    "interpreter": dict(interpreter),
                    "market_catalog_source": contract["market_catalog_source"],
                    "digest": contract["digest"],
                }
            )
    return tuple(profiles)


def authorized_environment_digests() -> frozenset[str]:
    """The enumerated environment profiles the registry authorizes.

    Read through the identity module so there is exactly one reader of the
    registry, and imported here rather than at module scope because the identity
    module imports this one back when it validates both halves together.
    """

    from app.signal_scientific_identity import load_identity_registry

    registry = load_identity_registry()
    return frozenset(
        str(item["digest"])
        for item in registry["authorized_environment_digests"]
        if isinstance(item, dict) and isinstance(item.get("digest"), str)
    )


def resolved_market_catalog_source(root: Path | None = None) -> str:
    """Where the routing catalog was actually read from, relative to the root.

    Relative on purpose: an absolute path would make the digest depend on which
    directory the tree happens to sit in, and the question this answers is
    *which file inside the deployment was read*, not where the deployment is
    installed.  A catalog configured outside the root keeps its absolute path,
    because that is a materially different -- and unauthorized -- deployment.
    """

    configured = config.MARKET_SYMBOL_CATALOG_FILE
    if not configured:
        return "default"
    source_root = Path(os.path.realpath(root or config.resolve_project_root()))
    path = Path(os.path.realpath(configured))
    if path.is_relative_to(source_root):
        return path.relative_to(source_root).as_posix()
    return path.as_posix()


def _resolved_environment_settings() -> dict[str, int]:
    settings = config.get_settings()
    return {name: int(getattr(settings, name)) for name in _SCIENTIFIC_ENVIRONMENT_SETTINGS_V1}


def _resolved_interpreter() -> dict[str, str]:
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "implementation": sys.implementation.name,
    }


def compute_scientific_runtime_contract(
    *,
    catalog: Sequence[MarketSymbol] | None = None,
    symbols: Sequence[str] | None = None,
    catalog_source: str | None = None,
    environment_settings: Mapping[str, int] | None = None,
    interpreter: Mapping[str, str] | None = None,
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> dict[str, Any]:
    """Compute, without trusting the registry, one deterministic contract.

    Every default is looked up when this function runs, not when the module is
    imported, so a caller always sees what the process resolved rather than what
    the source suggests.  One caveat that used to be stated the other way round
    and was simply false: ``config.MARKET_SYMBOL_CATALOG`` is itself built at
    *import* time, so what resolves at call time is the module attribute, not a
    re-read of the catalog file.  A catalog file edited after the process
    started is invisible until it restarts.

    The scope is the configured symbol set, not the shard-assigned subset: every
    collector shard must resolve the same routing or the routing half would
    differ for a reason that is not routing.  What the shard *does* change --
    which slice it observes -- is projected separately, through the environment
    settings, and the registry enumerates one authorized profile per shard.

    The overrides exist so the registry generator can enumerate the authorized
    profiles without booting one process per shard and interpreter.
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
        "market_catalog_source": (
            resolved_market_catalog_source() if catalog_source is None else catalog_source
        ),
        "interpreter": dict(
            _resolved_interpreter() if interpreter is None else interpreter
        ),
        "environment_settings": dict(
            _resolved_environment_settings()
            if environment_settings is None
            else environment_settings
        ),
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
        require_attested_routing(self.routing, "scalp_collector")
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
        require_attested_routing(self.routing, "ws_collector")
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
    authorized = authorized_environment_digests()
    if contract["digest"] not in authorized:
        raise RuntimeError(
            "runtime scientific configuration is not an authorized environment "
            f"profile: resolved {contract['digest']}, which is none of the "
            f"{len(authorized)} enumerated in the identity registry"
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


def require_attested_routing(routing: EffectiveMarketRouting, producer: str) -> None:
    """Refuse a routing the registry does not reproduce *now*.

    Self-consistency is not provenance.  The second R05 review built an
    ``EffectiveMarketRouting`` by hand whose single row read ``symbol =
    BTCUSDT_PERP.A, futures_pair = ETHUSDT``: internally consistent, carrying
    the registered digest verbatim as a plain string, and therefore accepted by
    every check that compares the object with itself or with a text.  It then
    produced an index that filed ETH's market under BTC's internal key, and the
    delivery gate -- holding the *correct* routing -- had nothing to object to,
    because the key it saw was genuinely routed.

    The only evidence a forgery cannot manufacture is the registry itself:
    recompute the contract from the live catalog, settings and effective maps,
    and require it to reproduce these very rows.  A routing that was attested
    and has since drifted fails here too, which is what makes this a gate
    rather than a constructor check.
    """

    if not isinstance(routing, EffectiveMarketRouting):
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} requires an attested "
            f"EffectiveMarketRouting, not {type(routing).__name__}"
        )
    attest_raw_market_producer(producer, routing.contract_version, expected=routing)


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
