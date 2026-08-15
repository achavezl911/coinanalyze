"""PR27-R03: the scientific runtime configuration contract.

These reproduce the real R03 mechanism: runtime configuration that changes the
signal context without changing the scientific source digest.  Replay alone
cannot detect it, because the resolved routing never reaches the stored context.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from app.config import DEFAULT_MARKET_CATALOG, MarketSymbol, load_market_catalog
from app.signal_runtime_contract import (
    REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS,
    SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    compute_scientific_runtime_contract,
    scientific_runtime_contract,
    validate_scientific_runtime_contract,
)
from app.signal_scientific_identity import (
    SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS,
    compute_scientific_implementation_identity,
)
from app.signal_walk_forward import (
    WALK_FORWARD_SPEC_VERSION_V4,
    WalkForwardManifestOptions,
    _static_options_spec,
)
from tests.test_signal_walk_forward import (
    _spec_v2_kwargs,
    _spec_v3_kwargs,
    _spec_v4_kwargs,
)

DEFAULT_SYMBOLS = tuple(item.symbol for item in DEFAULT_MARKET_CATALOG)


def _catalog_payload(rows: list[dict[str, object]]) -> str:
    return json.dumps({"version": 1, "mode": "replace", "symbols": rows})


def _row(item: MarketSymbol, **overrides: object) -> dict[str, object]:
    row = {
        "symbol": item.symbol,
        "base_asset": item.base_asset,
        "futures_pair": item.futures_pair,
        "bybit_oi_symbol": item.bybit_oi_symbol,
        "spot_pair": item.spot_pair,
        "spot_history_symbol": item.spot_history_symbol,
        "whale_threshold_usd": item.whale_threshold_usd,
        "large_trade_threshold_usd": item.large_trade_threshold_usd,
    }
    row.update(overrides)
    return row


def _digest(catalog, symbols=DEFAULT_SYMBOLS) -> str:
    return compute_scientific_runtime_contract(
        catalog=catalog, symbols=symbols
    )["digest"]


# --------------------------------------------------------------------------
# Contract shape and determinism
# --------------------------------------------------------------------------


def test_contract_is_deterministic_and_canonically_hashed() -> None:
    first = compute_scientific_runtime_contract()
    second = compute_scientific_runtime_contract()
    assert first == second

    payload = {
        key: value for key, value in first.items() if key != "digest"
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert first["digest"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert first["canonicalizer"] == SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER
    assert first["runtime_contract_version"] == SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1


def test_contract_freezes_only_the_result_material_routing_fields() -> None:
    contract = compute_scientific_runtime_contract()
    for routing in contract["market_routing"]:
        assert set(routing) == {
            "symbol",
            "base_asset",
            "futures_pair",
            "spot_pair",
        }


def test_runtime_contract_matches_its_registered_digest() -> None:
    contract = scientific_runtime_contract()
    assert contract["digest"] == REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS[
        SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
    ]


def test_unregistered_contract_version_fails_closed() -> None:
    with pytest.raises(ValueError):
        compute_scientific_runtime_contract(contract_version=2)
    with pytest.raises(ValueError):
        scientific_runtime_contract(2)


# --------------------------------------------------------------------------
# TEST 1 -- same scientific source, changed runtime spot routing
# --------------------------------------------------------------------------


def test_changed_spot_routing_changes_the_contract_under_identical_source(
    tmp_path,
) -> None:
    """The exact R03 mechanism: BTCUSDT_PERP.A -> BTC repointed at another asset."""

    baseline_identity = compute_scientific_implementation_identity()

    repointed = tuple(
        replace(item, base_asset="ETH")
        if item.symbol == "BTCUSDT_PERP.A"
        else item
        for item in DEFAULT_MARKET_CATALOG
    )

    # The scientific source is untouched...
    assert compute_scientific_implementation_identity() == baseline_identity
    # ...but the runtime contract is not.
    assert _digest(repointed) != _digest(DEFAULT_MARKET_CATALOG)


def test_producer_attestation_fails_while_a_foreign_routing_is_active(
    monkeypatch,
) -> None:
    from app import config

    repointed = tuple(
        replace(item, spot_pair="ETHUSDT")
        if item.symbol == "BTCUSDT_PERP.A"
        else item
        for item in DEFAULT_MARKET_CATALOG
    )
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", repointed)

    with pytest.raises(RuntimeError, match="registered contract"):
        scientific_runtime_contract()


# --------------------------------------------------------------------------
# TEST 2 -- external catalog files
# --------------------------------------------------------------------------


def test_two_catalog_paths_with_identical_routing_share_one_contract(
    tmp_path,
) -> None:
    rows = [_row(item) for item in DEFAULT_MARKET_CATALOG]
    first = tmp_path / "a" / "market_symbols.json"
    second = tmp_path / "b" / "different_name.json"
    for path in (first, second):
        path.parent.mkdir(parents=True)
        path.write_text(_catalog_payload(rows), encoding="utf-8")

    assert first != second
    assert _digest(load_market_catalog(first)) == _digest(load_market_catalog(second))
    # And identical to the in-source default: only resolved values matter.
    assert _digest(load_market_catalog(first)) == _digest(DEFAULT_MARKET_CATALOG)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_asset", "XBT"),
        ("futures_pair", "BTCBUSD"),
        ("spot_pair", "BTCBUSD"),
    ],
)
def test_mutating_one_result_material_value_changes_the_contract(
    tmp_path, field: str, value: str
) -> None:
    rows = [
        _row(item, **({field: value} if item.symbol == "BTCUSDT_PERP.A" else {}))
        for item in DEFAULT_MARKET_CATALOG
    ]
    path = tmp_path / "mutated.json"
    path.write_text(_catalog_payload(rows), encoding="utf-8")

    assert _digest(load_market_catalog(path)) != _digest(DEFAULT_MARKET_CATALOG)


# --------------------------------------------------------------------------
# TEST 6 -- operational configuration is provably excluded
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        # Reaches only the separate oi_bybit table; no scientific region reads it
        # and endpoint-v2 requires Binance.
        ("bybit_oi_symbol", "BTCUSDT.9"),
        # Reaches only spot_perp_flow and the daily aggregate, both outside the
        # scientific surface.
        ("spot_history_symbol", "BTCUSD.Z"),
        # buy_vol_usd/sell_vol_usd accumulate unconditionally before the
        # threshold test; the threshold only partitions inst_/mid_/retail_
        # columns, which scalp_context never selects.
        ("whale_threshold_usd", 42_000_000.0),
        ("large_trade_threshold_usd", 7.0),
    ],
)
def test_operational_catalog_fields_do_not_change_the_contract(
    tmp_path, field: str, value: object
) -> None:
    rows = [
        _row(item, **({field: value} if item.symbol == "BTCUSDT_PERP.A" else {}))
        for item in DEFAULT_MARKET_CATALOG
    ]
    path = tmp_path / "operational.json"
    path.write_text(_catalog_payload(rows), encoding="utf-8")

    mutated = load_market_catalog(path)
    assert mutated != DEFAULT_MARKET_CATALOG
    assert _digest(mutated) == _digest(DEFAULT_MARKET_CATALOG)


# --------------------------------------------------------------------------
# TEST 6b -- scope is the resolved symbol set, not its spelling or sharding
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spelling",
    [
        DEFAULT_SYMBOLS,
        tuple(reversed(DEFAULT_SYMBOLS)),
        DEFAULT_SYMBOLS + DEFAULT_SYMBOLS,
        tuple(f"  {symbol}  " for symbol in DEFAULT_SYMBOLS),
    ],
)
def test_symbol_scope_depends_on_the_resolved_set_not_its_spelling(
    spelling: tuple[str, ...],
) -> None:
    assert _digest(DEFAULT_MARKET_CATALOG, symbols=spelling) == _digest(
        DEFAULT_MARKET_CATALOG
    )


def test_changing_the_resolved_symbol_set_changes_the_contract() -> None:
    narrowed = _digest(DEFAULT_MARKET_CATALOG, symbols=("BTCUSDT_PERP.A",))
    assert narrowed != _digest(DEFAULT_MARKET_CATALOG)


def test_symbol_outside_the_resolved_catalog_fails_closed() -> None:
    with pytest.raises(ValueError, match="absent from the resolved"):
        compute_scientific_runtime_contract(
            catalog=DEFAULT_MARKET_CATALOG, symbols=("DOGEUSDT_PERP.A",)
        )


def test_empty_symbol_scope_fails_closed() -> None:
    with pytest.raises(ValueError, match="at least one symbol"):
        compute_scientific_runtime_contract(
            catalog=DEFAULT_MARKET_CATALOG, symbols=()
        )


# --------------------------------------------------------------------------
# Frozen-contract validation
# --------------------------------------------------------------------------


def test_validate_accepts_the_live_contract_and_rejects_a_drifted_one() -> None:
    frozen = scientific_runtime_contract()
    assert validate_scientific_runtime_contract(frozen) == frozen

    drifted = dict(frozen)
    drifted["market_routing"] = [
        {**routing, "base_asset": "ETH"} for routing in frozen["market_routing"]
    ]
    with pytest.raises(ValueError, match="does not match runtime configuration"):
        validate_scientific_runtime_contract(drifted)


@pytest.mark.parametrize(
    "stored",
    ["not-an-object", None, 7, {}, {"runtime_contract_version": "1"},
     {"runtime_contract_version": True}],
)
def test_validate_rejects_malformed_frozen_contracts(stored: object) -> None:
    with pytest.raises(ValueError):
        validate_scientific_runtime_contract(stored)


# --------------------------------------------------------------------------
# Identity coverage and spec placement
# --------------------------------------------------------------------------


def test_contract_mechanics_are_covered_by_the_scientific_identity() -> None:
    """Stricter since the third R05 correction: the whole file, not a region."""

    names = {component.name for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS}
    assert "scientific_runtime_contract_module" in names
    covering = [
        item
        for item in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS
        if item.relative_path == "app/signal_runtime_contract.py"
    ]
    assert len(covering) == 1, "the contract module must be covered exactly once"
    component = covering[0]
    assert component.name == "scientific_runtime_contract_module"
    assert component.language == "python_module"
    # No markers: the imports and the constants above the old BEGIN marker are
    # inside the identity now, so the coverage cannot be narrowed by moving
    # code above a marker.
    assert component.begin_marker == ""
    assert component.end_marker == ""


def test_only_spec_v4_freezes_the_runtime_contract() -> None:
    assert "scientific_runtime_contract" not in _static_options_spec(
        WalkForwardManifestOptions()
    )
    assert "scientific_runtime_contract" not in _static_options_spec(
        WalkForwardManifestOptions(**_spec_v2_kwargs())
    )
    assert "scientific_runtime_contract" not in _static_options_spec(
        WalkForwardManifestOptions(**_spec_v3_kwargs())
    )


def test_spec_v4_static_spec_carries_the_frozen_runtime_contract() -> None:
    spec = _static_options_spec(WalkForwardManifestOptions(**_spec_v4_kwargs()))
    assert spec["spec_version"] == WALK_FORWARD_SPEC_VERSION_V4
    frozen = spec["scientific_runtime_contract"]
    assert frozen == scientific_runtime_contract()
    assert len(frozen["digest"]) == 64
