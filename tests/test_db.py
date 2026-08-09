from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import asyncpg
import pytest

from app.config import MarketSymbol, Settings
from app.db import acquire_service_lock, heartbeat_shard, sync_market_catalog


class _LockConnection:
    def __init__(self, locked: bool) -> None:
        self.locked = locked
        self.closed = False
        self.key = None

    async def fetchval(self, _query: str, key: str) -> bool:
        self.key = key
        return self.locked

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_service_lock_closes_connection_when_shard_is_owned(monkeypatch):
    conn = _LockConnection(False)

    async def fake_connect(**_kwargs):
        return conn

    monkeypatch.setattr("app.db.asyncpg.connect", fake_connect)

    with pytest.raises(RuntimeError, match="coinanalyze:ws:1:3"):
        await acquire_service_lock(Settings(), "ws", 1, 3)

    assert conn.closed is True
    assert conn.key == "coinanalyze:ws:1:3"


class _CatalogConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[tuple[object, ...]]]] = []

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def executemany(self, query, rows):
        self.calls.append((query, list(rows)))


class _CatalogPool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        return self.conn


@pytest.mark.asyncio
async def test_fourth_catalog_asset_is_registered_for_persistence():
    item = MarketSymbol(
        "XRPUSDT_PERP.A",
        "XRP",
        "XRPUSDT",
        "XRPUSDT.6",
        "XRPUSDT",
        "XRPUSD.A",
        100_000.0,
        50_000.0,
    )
    conn = _CatalogConnection()

    await sync_market_catalog(_CatalogPool(conn), (item,))

    assert conn.calls[0][1] == [("XRP",)]
    assert ("XRPUSDT_PERP.A", "XRP", True) in conn.calls[1][1]
    assert ("XRPUSD.A", "XRP", False) in conn.calls[1][1]


def _test_settings(dsn: str) -> Settings:
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    return Settings(
        PG_HOST=parsed.hostname or "127.0.0.1",
        PG_PORT=parsed.port or 5432,
        PG_DB=parsed.path.lstrip("/"),
        PG_USER=unquote(parsed.username or "postgres"),
        PG_PASSWORD=unquote(parsed.password or ""),
        PG_SSLMODE=query.get("sslmode", ["disable"])[0],
    )


@pytest.mark.asyncio
async def test_postgres_service_lock_excludes_same_shard_and_releases_on_close():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = _test_settings(dsn)
    first = other = reacquired = None
    try:
        first = await acquire_service_lock(settings, "ws", 0, 2)
        with pytest.raises(RuntimeError, match="already active"):
            await acquire_service_lock(settings, "ws", 0, 2)
        other = await acquire_service_lock(settings, "ws", 1, 2)
        await first.close()
        first = None
        reacquired = await acquire_service_lock(settings, "ws", 0, 2)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"test PostgreSQL unavailable: {exc}")
    finally:
        for conn in (first, other, reacquired):
            if conn is not None and not conn.is_closed():
                await conn.close()


def test_schema_removes_literal_asset_checks_and_adds_foreign_keys():
    source = Path("sql/schema.sql").read_text(encoding="utf-8")

    assert "base_asset text NOT NULL CHECK (base_asset IN" not in source
    assert "symbol text NOT NULL CHECK (symbol IN ('BTC','ETH','SOL'))" not in source
    assert source.count("REFERENCES market_assets(base_asset)") >= 3
    assert "CREATE TABLE IF NOT EXISTS external_api_rate_event" in source


class _HeartbeatConnection:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append((query, args))


@pytest.mark.asyncio
async def test_shard_heartbeat_publishes_instance_and_aggregate():
    conn = _HeartbeatConnection()

    await heartbeat_shard(conn, "ws", 1, 3, status="ok", detail="symbols=ETH")

    assert conn.calls[0][1][0] == "ws:1/3"
    assert conn.calls[1][1] == ("ws", "ws:%/3", 3)
    assert "COUNT(*) <> $3" in conn.calls[1][0]
