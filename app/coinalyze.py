from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import asyncpg
import httpx

LOGGER = logging.getLogger(__name__)


class CoinalyzeError(RuntimeError):
    pass


class RateLimiter(Protocol):
    async def acquire(self, units: int) -> None: ...


class PostgresSlidingWindowRateLimiter:
    """Global billing-unit window shared by every process using the same PostgreSQL."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        max_units: int,
        *,
        provider: str = "coinalyze",
        window_seconds: float = 60.0,
    ) -> None:
        if max_units < 1:
            raise ValueError("max_units must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.pool = pool
        self.max_units = max_units
        self.provider = provider
        self.window_seconds = window_seconds

    async def acquire(self, units: int) -> None:
        if units < 1:
            raise ValueError("requested units must be >= 1")
        if units > self.max_units:
            raise ValueError("Request cost exceeds rate limiter capacity")
        while True:
            sleep_for = 0.05
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                        f"rate:{self.provider}",
                    )
                    await conn.execute(
                        """
                        DELETE FROM external_api_rate_event
                        WHERE provider=$1
                          AND ts <= now() - make_interval(secs => $2::double precision)
                        """,
                        self.provider,
                        self.window_seconds,
                    )
                    rows = await conn.fetch(
                        """
                        SELECT ts,units,now() AS db_now
                        FROM external_api_rate_event
                        WHERE provider=$1
                        ORDER BY ts
                        """,
                        self.provider,
                    )
                    used = sum(int(row["units"]) for row in rows)
                    if used + units <= self.max_units:
                        await conn.execute(
                            "INSERT INTO external_api_rate_event(provider,units) VALUES($1,$2)",
                            self.provider,
                            units,
                        )
                        return

                    units_to_expire = used + units - self.max_units
                    expired_units = 0
                    for row in rows:
                        expired_units += int(row["units"])
                        if expired_units >= units_to_expire:
                            event_ts: datetime = row["ts"]
                            db_now: datetime = row["db_now"]
                            sleep_for = (
                                self.window_seconds - (db_now - event_ts).total_seconds() + 0.05
                            )
                            break
            await asyncio.sleep(max(sleep_for, 0.05))


@dataclass(frozen=True, slots=True)
class CoinalyzeRateBudget:
    symbol_count: int
    ohlcv_units_per_cycle: int
    metrics_units_per_cycle: int
    daily_units_per_cycle: int
    projected_units_per_minute: float


def validate_rate_budget(
    symbol_count: int,
    configured_limit: int,
    *,
    ohlcv_cadence_seconds: int = 60,
    metrics_cadence_seconds: int = 300,
    daily_cadence_seconds: int = 3600,
) -> CoinalyzeRateBudget:
    if symbol_count < 1:
        raise ValueError("symbol_count must be >= 1")
    ohlcv_units = symbol_count
    metrics_units = 6 * symbol_count
    daily_units = 4 * symbol_count
    projected = (
        ohlcv_units * 60 / ohlcv_cadence_seconds
        + metrics_units * 60 / metrics_cadence_seconds
        + daily_units * 60 / daily_cadence_seconds
    )
    if symbol_count > configured_limit or projected > configured_limit:
        raise RuntimeError(
            "Coinalyze quota cannot satisfy configured workload: "
            f"symbols={symbol_count} ohlcv_units/cycle={ohlcv_units} "
            f"metrics_units/cycle={metrics_units} daily_units/cycle={daily_units} "
            f"projected_units/min={projected:.2f} limit={configured_limit}"
        )
    return CoinalyzeRateBudget(
        symbol_count,
        ohlcv_units,
        metrics_units,
        daily_units,
        projected,
    )


class CoinalyzeClient:
    def __init__(self, base_url: str, api_key: str, limiter: RateLimiter) -> None:
        if not api_key:
            raise CoinalyzeError("API_KEY is empty")
        self._limiter = limiter
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "api_key": api_key,
                "Accept": "application/json",
                "User-Agent": "coinalyze-operator-dashboard/1.0",
            },
            timeout=httpx.Timeout(25.0, connect=10.0),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            follow_redirects=False,
        )

    async def __aenter__(self) -> CoinalyzeClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def history(
        self,
        endpoint: str,
        symbols: tuple[str, ...] | list[str],
        *,
        interval: str,
        start_ts: int,
        end_ts: int,
        convert_to_usd: bool | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        symbols = list(symbols)
        params: dict[str, Any] = {
            "symbols": ",".join(symbols),
            "interval": interval,
            "from": start_ts,
            "to": end_ts,
        }
        if convert_to_usd is not None:
            params["convert_to_usd"] = "true" if convert_to_usd else "false"

        delay = 1.0
        for attempt in range(1, 6):
            await self._limiter.acquire(len(symbols))
            try:
                response = await self._client.get(f"/{endpoint}", params=params)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 5:
                    raise CoinalyzeError(f"Network failure calling {endpoint}: {exc}") from exc
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15)
                continue

            if response.status_code == 429:
                try:
                    retry_after = min(float(response.headers.get("Retry-After", "5")), 60.0)
                except ValueError:
                    retry_after = 5.0
                LOGGER.warning("Coinalyze 429 endpoint=%s retry_after=%s", endpoint, retry_after)
                await asyncio.sleep(max(retry_after, 1.0))
                continue
            if response.status_code in {500, 502, 503, 504}:
                if attempt == 5:
                    raise CoinalyzeError(
                        f"Coinalyze {response.status_code} calling {endpoint}"
                    )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 15)
                continue
            if response.status_code != 200:
                body = response.text[:300]
                raise CoinalyzeError(
                    f"Coinalyze {response.status_code} calling {endpoint}: {body}"
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise CoinalyzeError(f"Invalid JSON from {endpoint}") from exc
            if not isinstance(payload, list):
                raise CoinalyzeError(f"Unexpected payload from {endpoint}")
            result: dict[str, list[dict[str, Any]]] = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                symbol = item.get("symbol")
                history = item.get("history")
                if isinstance(symbol, str) and isinstance(history, list):
                    result[symbol] = [row for row in history if isinstance(row, dict)]
            return result

        raise CoinalyzeError(f"Retries exhausted calling {endpoint}")
