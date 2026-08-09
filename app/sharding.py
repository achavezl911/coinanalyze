from __future__ import annotations

import hashlib


def symbol_shard(symbol: str, shard_count: int) -> int:
    if shard_count < 1:
        raise ValueError("shard_count must be >= 1")
    digest = hashlib.sha256(symbol.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % shard_count


def assigned_symbols(
    symbols: tuple[str, ...],
    shard_index: int,
    shard_count: int,
) -> tuple[str, ...]:
    if not 0 <= shard_index < shard_count:
        raise ValueError("invalid shard index")
    return tuple(
        symbol
        for symbol in symbols
        if symbol_shard(symbol, shard_count) == shard_index
    )
