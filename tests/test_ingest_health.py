from __future__ import annotations

from datetime import UTC, datetime

import pytest

import app.ai_context as ai_context
import app.api as api
from app.ai_context import data_confidence_row
from app.db import INGEST_COMPONENT_MAX_AGES, required_heartbeat_failures


def _heartbeat_rows(failed_component: str) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    rows = [
        {"service": "api", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "daily", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "ws", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "scalp", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
    ]
    for component in INGEST_COMPONENT_MAX_AGES:
        rows.append(
            {
                "service": f"ingest:{component}",
                "status": "error" if component == failed_component else "ok",
                "updated_at": now,
                "lag_seconds": 0.0,
            }
        )
    rows.append(
        {
            "service": "ingest",
            "status": "error",
            "updated_at": min(row["updated_at"] for row in rows[-2:]),
            "lag_seconds": 0.0,
        }
    )
    return rows


class _HealthConnection:
    def __init__(self, heartbeats: list[dict[str, object]]) -> None:
        self.heartbeats = heartbeats

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def fetchval(self, _query, *_args):
        return 1

    async def fetch(self, query, *_args):
        if "pipeline_heartbeat" in query:
            return self.heartbeats
        if "metrics_snapshot" in query:
            return [
                {"symbol": symbol, "latest_snapshot": datetime.now(UTC), "lag_seconds": 0.0}
                for symbol in api.SETTINGS.SYMBOLS
            ]
        raise AssertionError(query)


class _Pool:
    def __init__(self, connection) -> None:
        self.connection = connection

    def acquire(self):
        return self.connection


class _ContextConnection(_HealthConnection):
    async def fetchrow(self, _query, *_args):
        return {
            "symbol": "BTCUSDT_PERP.A",
            "snapshot_lag_seconds": 1.0,
            "spot_venues_live": 2,
            "futures_venues_live": 2,
            "book_venues_live": 2,
            "combined_book_lag_seconds": 1.0,
            "flow_8h_futures_complete": True,
            "flow_8h_futures_end_gap_seconds": 1.0,
        }


@pytest.mark.parametrize("failed_component", ["ohlcv_1m", "metrics_5m"])
async def test_failed_ingest_subfeed_keeps_health_and_data_confidence_degraded(
    monkeypatch: pytest.MonkeyPatch,
    failed_component: str,
):
    rows = _heartbeat_rows(failed_component)
    required = {
        "ingest": max(INGEST_COMPONENT_MAX_AGES.values()),
        **{
            f"ingest:{component}": max_age
            for component, max_age in INGEST_COMPONENT_MAX_AGES.items()
        },
    }
    assert set(required_heartbeat_failures(rows, required)) == {
        "ingest",
        f"ingest:{failed_component}",
    }

    health_conn = _HealthConnection(rows)
    monkeypatch.setattr(api.app.state, "pool", _Pool(health_conn), raising=False)

    async def heartbeat_noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(api, "heartbeat", heartbeat_noop)
    health = await api.health()
    assert health["status"] == "degraded"

    context_conn = _ContextConnection(rows)

    async def complete_spot(*_args, **_kwargs):
        return {"8h": {"combined": {"complete": True, "source": "test", "end_gap_seconds": 1}}}

    monkeypatch.setattr(ai_context, "spot_flow_windows", complete_spot)
    confidence = await data_confidence_row(
        context_conn,  # type: ignore[arg-type]
        "BTCUSDT_PERP.A",
    )
    assert confidence["collectors_stale"] is True
    assert confidence["status"] == "degraded"
