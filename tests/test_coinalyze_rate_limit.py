from __future__ import annotations

import getpass
import os
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import asyncpg
import pytest

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter, validate_rate_budget
from app.config import Settings
from app.db import ServiceOwnershipLost, acquire_service_lock


class _Transaction:
    def __init__(self, conn) -> None:
        self.conn = conn

    async def __aenter__(self):
        self.conn.in_transaction = True

    async def __aexit__(self, *_args):
        self.conn.in_transaction = False


class _Connection:
    def __init__(self) -> None:
        self.in_transaction = False
        self.fetch_count = 0
        self.inserted: list[int] = []
        self.now = datetime(2026, 8, 9, tzinfo=UTC)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def transaction(self):
        return _Transaction(self)

    async def execute(self, query, *args):
        if "INSERT INTO external_api_rate_event" in query:
            self.inserted.append(args[1])

    async def fetch(self, _query, _provider):
        self.fetch_count += 1
        if self.fetch_count == 1:
            return [
                {"ts": self.now - timedelta(seconds=59), "units": 8, "db_now": self.now}
            ]
        return []


class _Pool:
    def __init__(self, conn) -> None:
        self.conn = conn

    def acquire(self):
        return self.conn


@pytest.mark.asyncio
async def test_global_limiter_commits_before_sleeping(monkeypatch):
    conn = _Connection()
    sleep_transactions: list[bool] = []

    async def fake_sleep(_delay):
        sleep_transactions.append(conn.in_transaction)

    monkeypatch.setattr("app.coinalyze.asyncio.sleep", fake_sleep)
    limiter = PostgresSlidingWindowRateLimiter(_Pool(conn), max_units=10)

    await limiter.acquire(3)

    assert sleep_transactions == [False]
    assert conn.inserted == [3]


def test_rate_budget_reports_cycles_and_rejects_impossible_configuration():
    budget = validate_rate_budget(4, 35)
    assert budget.ohlcv_units_per_cycle == 4
    assert budget.metrics_units_per_cycle == 24
    assert budget.daily_units_per_cycle == 16
    assert budget.projected_units_per_minute == pytest.approx(9.066666, rel=1e-5)

    with pytest.raises(RuntimeError, match="cannot satisfy"):
        validate_rate_budget(20, 35)


class _RecordingLimiter:
    def __init__(self) -> None:
        self.units = []

    async def acquire(self, units):
        self.units.append(units)


class _Response:
    def __init__(self, status_code, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = {}
        self.text = ""

    def json(self):
        return self._payload


class _RetryingHttpClient:
    def __init__(self) -> None:
        self.responses = [
            _Response(500),
            _Response(200, [{"symbol": "BTCUSDT_PERP.A", "history": []}]),
        ]

    async def get(self, *_args, **_kwargs):
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_each_http_retry_acquires_global_units(monkeypatch):
    async def no_sleep(_delay):
        return None

    monkeypatch.setattr("app.coinalyze.asyncio.sleep", no_sleep)
    limiter = _RecordingLimiter()
    client = CoinalyzeClient("https://example.invalid", "test-key", limiter)
    await client._client.aclose()
    client._client = _RetryingHttpClient()

    result = await client.history(
        "ohlcv-history",
        ["BTCUSDT_PERP.A"],
        interval="1min",
        start_ts=1,
        end_ts=2,
    )

    assert result == {"BTCUSDT_PERP.A": []}
    assert limiter.units == [1, 1]


def _test_settings(dsn: str) -> Settings:
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    return Settings(
        # El directorio del socket viaja en la QUERY (?host=/var/run/postgresql),
        # no en el authority, asi que parsed.hostname es None y sin esta linea se
        # perdia el parametro y se conectaba por TCP a 127.0.0.1.
        PG_HOST=query.get("host", [""])[0] or parsed.hostname or "127.0.0.1",
        PG_PORT=parsed.port or 5432,
        PG_DB=parsed.path.lstrip("/"),
        # Sin usuario en el DSN NO se inventa "postgres": con auth peer el usuario
        # correcto es el del proceso, y "postgres" daba InvalidPasswordError.
        PG_USER=unquote(parsed.username or "") or getpass.getuser(),
        PG_PASSWORD=unquote(parsed.password or ""),
        PG_SSLMODE=query.get("sslmode", ["disable"])[0],
    )


@pytest.mark.asyncio
async def test_postgres_rate_limiter_fences_reservations_after_ownership_takeover():
    """A reserves; B takes over the shard; A's next acquire() must be fenced instead of
    reserving a unit, and B must still be able to reserve afterwards.
    """
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = _test_settings(dsn)
    provider = f"fence-rate-{uuid4().hex}"
    owner_a = owner_b = pool = control = None
    try:
        control = await asyncpg.connect(dsn)
        owner_a = await acquire_service_lock(settings, provider)
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)

        limiter_a = PostgresSlidingWindowRateLimiter(
            pool, 10, provider=provider, ownership=owner_a
        )
        await limiter_a.acquire(3)

        terminated = await control.fetchval(
            "SELECT pg_terminate_backend($1)", owner_a.connection.get_server_pid()
        )
        assert terminated is True
        owner_b = await acquire_service_lock(settings, provider)
        assert owner_b.generation > owner_a.generation

        with pytest.raises(ServiceOwnershipLost, match="generation"):
            await limiter_a.acquire(2)

        rows = await control.fetch(
            "SELECT units FROM external_api_rate_event WHERE provider=$1 ORDER BY ts",
            provider,
        )
        assert [row["units"] for row in rows] == [3]

        limiter_b = PostgresSlidingWindowRateLimiter(
            pool, 10, provider=provider, ownership=owner_b
        )
        await limiter_b.acquire(2)

        rows = await control.fetch(
            "SELECT units FROM external_api_rate_event WHERE provider=$1 ORDER BY ts",
            provider,
        )
        assert [row["units"] for row in rows] == [3, 2]
    finally:
        if control is not None:
            await control.execute(
                "DELETE FROM external_api_rate_event WHERE provider=$1", provider
            )
            await control.execute(
                "DELETE FROM service_ownership WHERE service=$1", provider
            )
        if pool is not None:
            await pool.close()
        for owner in (owner_a, owner_b):
            if owner is not None and not owner.is_closed():
                await owner.close()
        if control is not None:
            await control.close()
