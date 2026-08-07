from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)


class CoinalyzeError(RuntimeError):
    pass


class SlidingWindowRateLimiter:
    """Counts Coinalyze billing units, where each requested symbol consumes one unit."""

    def __init__(self, max_units: int, window_seconds: float = 60.0) -> None:
        self.max_units = max_units
        self.window_seconds = window_seconds
        self._events: deque[tuple[float, int]] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, cost: int) -> None:
        if cost > self.max_units:
            raise ValueError("Request cost exceeds rate limiter capacity")
        while True:
            async with self._lock:
                now = time.monotonic()
                while self._events and now - self._events[0][0] >= self.window_seconds:
                    self._events.popleft()
                used = sum(item[1] for item in self._events)
                if used + cost <= self.max_units:
                    self._events.append((now, cost))
                    return
                sleep_for = self.window_seconds - (now - self._events[0][0]) + 0.05
            await asyncio.sleep(max(sleep_for, 0.05))


class CoinalyzeClient:
    def __init__(self, base_url: str, api_key: str, max_units: int = 35) -> None:
        if not api_key:
            raise CoinalyzeError("API_KEY is empty")
        self._limiter = SlidingWindowRateLimiter(max_units=max_units)
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
        await self._limiter.acquire(cost=len(symbols))
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
