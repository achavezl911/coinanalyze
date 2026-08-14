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
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from typing import Any

from app import config
from app.config import MarketSymbol

SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1 = 1
SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER = (
    "scientific_runtime_contract_canonicalization_v1"
)


# Filled only after the resolved projection below has been implemented and the
# deterministic digest independently reproduced by tests.  Never mutate an
# existing key: register a new contract version instead.
REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS = {
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1: (
        "c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00"
    ),
}

# PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_BEGIN

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
        for field in _SCIENTIFIC_ROUTING_FIELDS_V1:
            value = getattr(item, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"scientific runtime routing field {field!r} for symbol "
                    f"{symbol!r} must be a non-empty string"
                )
            routing[field] = value
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


def scientific_runtime_contract(
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> dict[str, Any]:
    """Return the contract only when runtime resolution matches its registry.

    This is the producer-time gate.  While a non-registered routing is active no
    new scientific evidence may be written, so an A -> B -> A history cannot
    leave behind B rows that later pass as valid A evidence.
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


def attest_raw_market_producer(
    producer: str,
    contract_version: int = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
) -> dict[str, Any]:
    """Gate a raw producer before it may route or write result-material data.

    Correctness outranks availability here.  A service whose result-material
    routing is not the registered one must produce nothing at all rather than
    write scientifically misrouted rows that a later, legitimately registered
    configuration would silently consume.
    """

    tables = _RESULT_MATERIAL_RAW_PRODUCERS_V1.get(producer)
    if tables is None:
        raise ValueError(f"unknown result-material raw producer: {producer!r}")
    try:
        return scientific_runtime_contract(contract_version)
    except RuntimeError as exc:
        raise RawMarketProducerContractError(
            f"raw market producer {producer!r} may not subscribe to or write "
            f"{', '.join(tables)} while the resolved scientific runtime "
            f"configuration is unregistered: {exc}"
        ) from exc


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
