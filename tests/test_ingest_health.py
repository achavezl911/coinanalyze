from __future__ import annotations

from datetime import UTC, datetime

import pytest

import app.ai_context as ai_context
import app.api as api
from app.ai_context import data_confidence_row
from app.db import (
    DEFAULT_HEARTBEAT_MAX_AGE,
    INGEST_COMPONENT_MAX_AGES,
    heartbeat_max_age,
    required_heartbeat_failures,
)


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


async def test_healthz_and_data_confidence_degrade_the_same_heartbeat_from_db_clock_skew(
    monkeypatch: pytest.MonkeyPatch,
):
    """DB=12:10, application/python clock=12:05, ws heartbeat updated_at=12:06.

    lag_seconds must come from PostgreSQL's own now(), so both endpoints see the same
    240s-stale "ws" heartbeat even though the naive `app_now - updated_at` (using a
    behind-DB python clock) would read as fresh. Every row's lag_seconds is provided by
    the fake connection exactly as PostgreSQL would compute it; the fake also asserts
    the pipeline_heartbeat query actually requests it, so this fails if a caller falls
    back to Python's datetime.now(UTC) instead.
    """
    db_now = datetime(2026, 8, 9, 12, 10, tzinfo=UTC)
    heartbeat_ts = datetime(2026, 8, 9, 12, 6, tzinfo=UTC)
    stale_lag = (db_now - heartbeat_ts).total_seconds()

    def rows() -> list[dict[str, object]]:
        result = [
            {"service": "ws", "status": "ok", "updated_at": heartbeat_ts, "lag_seconds": stale_lag},
            {"service": "scalp", "status": "ok", "updated_at": db_now, "lag_seconds": 0.0},
            {"service": "daily", "status": "ok", "updated_at": db_now, "lag_seconds": 0.0},
            {"service": "api", "status": "ok", "updated_at": db_now, "lag_seconds": 0.0},
        ]
        for component in INGEST_COMPONENT_MAX_AGES:
            result.append(
                {
                    "service": f"ingest:{component}",
                    "status": "ok",
                    "updated_at": db_now,
                    "lag_seconds": 0.0,
                }
            )
        result.append(
            {"service": "ingest", "status": "ok", "updated_at": db_now, "lag_seconds": 0.0}
        )
        return result

    class _ClockSkewConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def fetchval(self, _query, *_args):
            return 1

        async def fetch(self, query, *_args):
            if "pipeline_heartbeat" in query:
                assert "lag_seconds" in query, (
                    "heartbeat freshness must be derived from PostgreSQL, not app time"
                )
                return rows()
            if "metrics_snapshot" in query:
                return [
                    {"symbol": symbol, "latest_snapshot": db_now, "lag_seconds": 0.0}
                    for symbol in api.SETTINGS.SYMBOLS
                ]
            raise AssertionError(query)

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

    conn = _ClockSkewConnection()
    monkeypatch.setattr(api.app.state, "pool", _Pool(conn), raising=False)

    async def heartbeat_noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(api, "heartbeat", heartbeat_noop)

    async def complete_spot(*_args, **_kwargs):
        return {"8h": {"combined": {"complete": True, "source": "test", "end_gap_seconds": 1}}}

    monkeypatch.setattr(ai_context, "spot_flow_windows", complete_spot)

    health = await api.health()
    confidence = await data_confidence_row(conn, "BTCUSDT_PERP.A")  # type: ignore[arg-type]

    assert "ws" in required_heartbeat_failures(rows(), {"ws": 90.0})
    assert health["status"] == "degraded"
    assert confidence["collectors_stale"] is True
    assert confidence["status"] == "degraded"


async def test_healthz_governs_every_heartbeat_not_only_the_hand_written_list(
    monkeypatch: pytest.MonkeyPatch,
):
    """Caso real medido en 140 el 2026-08-25: 'ws-bybit' llevaba 1303034 s (15 dias)
    sin latir, con status 'ok', y /api/healthz decia lo mismo que si estuviera vivo.

    La causa era que required_heartbeat_failures solo itera sobre los umbrales, y esos
    umbrales eran 7 claves escritas a mano (ingest, ws, scalp, daily, api y las dos de
    INGEST_COMPONENT_MAX_AGES) frente a las 14 filas de pipeline_heartbeat. Un servicio
    que no estuviera en la lista no podia poner degraded ni aunque llevara semanas
    muerto. Ahora los umbrales se derivan de la tabla, asi que el latido desconocido se
    vigila solo, y healthz declara en 'governed_services' que es lo que mira.
    """
    now = datetime.now(UTC)
    muerto = 15 * 24 * 3600.0
    rows: list[dict[str, object]] = [
        {"service": "api", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "daily", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "ws", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "scalp", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "ingest", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        # Ni este ni el siguiente aparecen en la lista escrita a mano.
        {"service": "ws:0/1", "status": "ok", "updated_at": now, "lag_seconds": 0.0},
        {"service": "ws-bybit", "status": "ok", "updated_at": now, "lag_seconds": muerto},
    ]
    for component in INGEST_COMPONENT_MAX_AGES:
        rows.append(
            {
                "service": f"ingest:{component}",
                "status": "ok",
                "updated_at": now,
                "lag_seconds": 0.0,
            }
        )

    monkeypatch.setattr(api.app.state, "pool", _Pool(_HealthConnection(rows)), raising=False)

    async def heartbeat_noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(api, "heartbeat", heartbeat_noop)
    health = await api.health()

    # 1. healthz declara que vigila, y cubre TODA la tabla. Es lo que comprueba K05.
    gobernados = set(health["governed_services"])
    assert {str(row["service"]) for row in rows} <= gobernados
    assert "ws-bybit" in gobernados
    # 2. y el latido muerto que no estaba en la lista degrada de verdad.
    assert health["status"] == "degraded"
    # 3. el shard hereda el umbral de su servicio base, no el por defecto.
    assert heartbeat_max_age("ws:0/1", {"ws": 90.0}) == 90.0
    assert heartbeat_max_age("desconocido", {"ws": 90.0}) == DEFAULT_HEARTBEAT_MAX_AGE
    # 4. missing_services sigue siendo "lo que TIENE que existir y no esta", asi que
    #    derivar de la tabla no puede vaciarlo por construccion.
    sin_ingest = [row for row in rows if row["service"] != "ingest"]
    monkeypatch.setattr(
        api.app.state, "pool", _Pool(_HealthConnection(sin_ingest)), raising=False
    )
    assert "ingest" in (await api.health())["missing_services"]
