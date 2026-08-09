from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter, validate_rate_budget


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
