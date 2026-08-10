from __future__ import annotations

from typing import Protocol

PARTITIONED_TEMPORAL_TABLES = frozenset(
    {
        "futures_trades_realtime",
        "spot_trades_realtime",
        "orderbook_snapshot",
        "liquidations_realtime",
        "scalp_signal_snapshot",
    }
)


class _ExecuteConnection(Protocol):
    async def execute(self, query: str, *args: object) -> str: ...


async def ensure_temporal_partitions(conn: _ExecuteConnection) -> None:
    """Create the current and next UTC daily partitions under one DB lock."""
    await conn.execute("SELECT ensure_temporal_partitions()")


async def apply_temporal_retention(
    conn: _ExecuteConnection,
    table: str,
    retention_hours: int,
) -> None:
    """Drop complete expired partitions, then trim the one boundary partition."""
    if table not in PARTITIONED_TEMPORAL_TABLES:
        raise ValueError(f"table is not managed by temporal partitioning: {table}")
    if retention_hours <= 0:
        raise ValueError("retention_hours must be positive")
    await conn.execute(
        "SELECT apply_temporal_retention($1, $2)", table, retention_hours
    )
