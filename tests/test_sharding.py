import pytest

from app.sharding import assigned_symbols, symbol_shard


def test_default_single_shard_preserves_order_and_all_symbols():
    symbols = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")
    assert assigned_symbols(symbols, 0, 1) == symbols


def test_shards_are_deterministic_disjoint_and_complete_with_fourth_asset():
    symbols = (
        "BTCUSDT_PERP.A",
        "ETHUSDT_PERP.A",
        "SOLUSDT_PERP.A",
        "XRPUSDT_PERP.A",
    )
    shards = [assigned_symbols(symbols, index, 3) for index in range(3)]

    assert tuple(symbol for shard in shards for symbol in shard) != symbols
    assert set().union(*(set(shard) for shard in shards)) == set(symbols)
    assert sum(len(shard) for shard in shards) == len(symbols)
    assert shards == [assigned_symbols(symbols, index, 3) for index in range(3)]


def test_invalid_shard_arguments_fail_explicitly():
    with pytest.raises(ValueError, match=">= 1"):
        symbol_shard("BTCUSDT_PERP.A", 0)
    with pytest.raises(ValueError, match="invalid shard index"):
        assigned_symbols(("BTCUSDT_PERP.A",), 1, 1)
