from __future__ import annotations

import asyncio
import getpass
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import asyncpg
import pytest

from app.config import MarketSymbol, Settings
from app.db import (
    INGEST_COMPONENT_MAX_AGES,
    ServiceOwnershipLost,
    acquire_service_lock,
    fenced_transaction,
    heartbeat_component,
    heartbeat_shard,
    monitor_service_lock,
    sync_market_catalog,
)


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


class _LostLockConnection:
    async def fetchval(self, _query: str):
        raise ConnectionError("database connection closed")


@pytest.mark.asyncio
async def test_service_lock_monitor_fails_process_on_connection_loss():
    with pytest.raises(
        RuntimeError,
        match="service lock connection lost: coinanalyze:scalp:1:2",
    ):
        await monitor_service_lock(
            _LostLockConnection(),  # type: ignore[arg-type]
            "scalp",
            1,
            2,
            poll_seconds=0,
        )


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
    assert "CREATE TABLE IF NOT EXISTS service_ownership" in source


def test_horizontal_rollback_removes_shard_heartbeats_before_legacy_check():
    source = Path(
        "sql/migrations/20260809_horizontal_safe_collectors.down.sql"
    ).read_text(encoding="utf-8")
    delete = "DELETE FROM pipeline_heartbeat"
    legacy_check = "ALTER TABLE pipeline_heartbeat ADD CONSTRAINT"

    assert delete in source
    assert "(ws|ws-binance|ws-bybit|scalp):[0-9]+/[0-9]+" in source
    assert source.index(delete) < source.index(legacy_check)


def test_final_review_migration_is_idempotent_and_has_rollback():
    upgrade = Path("sql/migrations/20260809_final_review_fixes.sql").read_text(
        encoding="utf-8"
    )
    rollback = Path("sql/migrations/20260809_final_review_fixes.down.sql").read_text(
        encoding="utf-8"
    )

    assert "ADD COLUMN IF NOT EXISTS price_cutoff_at" in upgrade
    assert "ADD COLUMN IF NOT EXISTS metrics_cutoff_at" in upgrade
    assert "CREATE TABLE IF NOT EXISTS service_ownership" in upgrade
    assert "DROP TABLE IF EXISTS service_ownership" in rollback
    assert "DROP COLUMN IF EXISTS metrics_cutoff_at" in rollback
    assert upgrade.startswith("BEGIN;") and upgrade.rstrip().endswith("COMMIT;")
    assert "BEGIN;" in rollback and rollback.rstrip().endswith("COMMIT;")


class _HeartbeatConnection:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append((query, args))

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


@pytest.mark.asyncio
async def test_shard_heartbeat_publishes_instance_and_aggregate():
    conn = _HeartbeatConnection()

    await heartbeat_shard(conn, "ws", 1, 3, status="ok", detail="symbols=ETH")

    assert conn.calls[0][1][0] == "coinanalyze:heartbeat-shards:ws:3"
    assert conn.calls[1][1][0] == "ws:1/3"
    assert conn.calls[2][1] == ("ws", "ws:%/3", 3)
    assert "COUNT(*) <> $3" in conn.calls[2][0]


async def _prepare_fencing_schema(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS service_ownership (
          service text NOT NULL,
          shard_index integer NOT NULL,
          shard_count integer NOT NULL,
          generation bigint NOT NULL,
          acquired_at timestamptz NOT NULL DEFAULT now(),
          PRIMARY KEY(service,shard_index,shard_count)
        )
        """
    )


@pytest.mark.asyncio
async def test_postgres_takeover_fences_old_writer_pool_transaction():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = _test_settings(dsn)
    service = f"fence-test-{uuid4().hex}"
    owner_a = owner_b = writer_a = writer_b = control = None
    try:
        control = await asyncpg.connect(dsn)
        await _prepare_fencing_schema(control)
        await control.execute(
            """
            CREATE TABLE IF NOT EXISTS service_fencing_test_write (
              test_key text PRIMARY KEY,
              writer text NOT NULL
            )
            """
        )
        owner_a = await acquire_service_lock(settings, service)
        writer_a = await asyncpg.connect(dsn)
        async with fenced_transaction(writer_a, owner_a):
            await writer_a.execute(
                "INSERT INTO service_fencing_test_write(test_key,writer) VALUES($1,'A')",
                service,
            )

        terminated = await control.fetchval(
            "SELECT pg_terminate_backend($1)", owner_a.connection.get_server_pid()
        )
        assert terminated is True
        owner_b = await acquire_service_lock(settings, service)
        assert owner_b.generation > owner_a.generation
        writer_b = await asyncpg.connect(dsn)

        with pytest.raises(ServiceOwnershipLost, match="generation"):
            async with fenced_transaction(writer_a, owner_a):
                await writer_a.execute(
                    "UPDATE service_fencing_test_write SET writer='OLD' WHERE test_key=$1",
                    service,
                )

        async with fenced_transaction(writer_b, owner_b):
            await writer_b.execute(
                "UPDATE service_fencing_test_write SET writer='B' WHERE test_key=$1",
                service,
            )
        assert await control.fetchval(
            "SELECT writer FROM service_fencing_test_write WHERE test_key=$1", service
        ) == "B"
    finally:
        if control is not None:
            await control.execute("DELETE FROM service_fencing_test_write WHERE test_key=$1", service)
            await control.execute("DELETE FROM service_ownership WHERE service=$1", service)
        for connection in (writer_a, writer_b, control):
            if connection is not None and not connection.is_closed():
                await connection.close()
        for owner in (owner_a, owner_b):
            if owner is not None and not owner.is_closed():
                await owner.close()


class _PausedAggregateConnection:
    def __init__(
        self,
        connection: asyncpg.Connection,
        reached: asyncio.Event,
        release: asyncio.Event,
    ) -> None:
        self.connection = connection
        self.reached = reached
        self.release = release

    def transaction(self):
        return self.connection.transaction()

    async def execute(self, query: str, *args):
        result = await self.connection.execute(query, *args)
        if "COUNT(*) <> $3" in query:
            self.reached.set()
            await self.release.wait()
        return result


@pytest.mark.asyncio
async def test_postgres_concurrent_shard_heartbeat_cannot_commit_stale_ok_last():
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    service = f"heartbeat-test-{uuid4().hex}"
    first = second = control = None
    reached = asyncio.Event()
    release = asyncio.Event()
    try:
        first = await asyncpg.connect(dsn)
        second = await asyncpg.connect(dsn)
        control = await asyncpg.connect(dsn)
        await heartbeat_shard(first, service, 0, 2, status="ok", detail="old-0")
        await heartbeat_shard(first, service, 1, 2, status="ok", detail="old-1")

        old_ok = asyncio.create_task(
            heartbeat_shard(
                _PausedAggregateConnection(first, reached, release),
                service,
                0,
                2,
                status="ok",
                detail="old-computation",
            )
        )
        await asyncio.wait_for(reached.wait(), timeout=3)
        new_degraded = asyncio.create_task(
            heartbeat_shard(
                second,
                service,
                1,
                2,
                status="degraded",
                detail="new-failure",
            )
        )
        await asyncio.sleep(0.1)
        assert not new_degraded.done()
        release.set()
        await asyncio.gather(old_ok, new_degraded)

        aggregate = await control.fetchrow(
            "SELECT status,updated_at FROM pipeline_heartbeat WHERE service=$1", service
        )
        shard_times = await control.fetch(
            "SELECT updated_at FROM pipeline_heartbeat WHERE service LIKE $1 ORDER BY service",
            f"{service}:%/2",
        )
        assert aggregate["status"] == "degraded"
        assert aggregate["updated_at"] == min(row["updated_at"] for row in shard_times)
    finally:
        release.set()
        if control is not None:
            await control.execute(
                "DELETE FROM pipeline_heartbeat WHERE service=$1 OR service LIKE $2",
                service,
                f"{service}:%/2",
            )
        for connection in (first, second, control):
            if connection is not None and not connection.is_closed():
                await connection.close()


@pytest.mark.parametrize(
    ("healthy_component", "failed_component"),
    [("ohlcv_1m", "metrics_5m"), ("metrics_5m", "ohlcv_1m")],
)
@pytest.mark.asyncio
async def test_postgres_ingest_component_failure_cannot_be_overwritten_concurrently(
    healthy_component: str,
    failed_component: str,
):
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    aggregate = f"ingest-test-{uuid4().hex}"
    first = second = control = None
    try:
        first = await asyncpg.connect(dsn)
        second = await asyncpg.connect(dsn)
        control = await asyncpg.connect(dsn)

        async def keep_writing_ok() -> None:
            for _ in range(5):
                await heartbeat_component(
                    first,
                    aggregate,
                    healthy_component,
                    INGEST_COMPONENT_MAX_AGES,
                    status="ok",
                )

        async def keep_writing_error() -> None:
            for _ in range(5):
                await heartbeat_component(
                    second,
                    aggregate,
                    failed_component,
                    INGEST_COMPONENT_MAX_AGES,
                    status="error",
                    detail="repeated failure",
                )

        await asyncio.gather(keep_writing_ok(), keep_writing_error())
        rows = await control.fetch(
            "SELECT service,status,updated_at FROM pipeline_heartbeat "
            "WHERE service=$1 OR service LIKE $2",
            aggregate,
            f"{aggregate}:%",
        )
        by_service = {row["service"]: row for row in rows}
        assert by_service[aggregate]["status"] == "error"
        assert by_service[f"{aggregate}:{failed_component}"]["status"] == "error"
        assert by_service[f"{aggregate}:{healthy_component}"]["status"] == "ok"
    finally:
        if control is not None:
            await control.execute(
                "DELETE FROM pipeline_heartbeat WHERE service=$1 OR service LIKE $2",
                aggregate,
                f"{aggregate}:%",
            )
        for connection in (first, second, control):
            if connection is not None and not connection.is_closed():
                await connection.close()


@pytest.mark.asyncio
async def test_el_apagado_no_se_lee_como_muerte_inesperada():
    """Cada despliegue dejaba a ingest en 'Failed with result exit-code' sin fallo real."""
    import asyncio

    from app.db import wait_for_stop_or_lock_loss

    stop = asyncio.Event()

    async def _tarea():
        await asyncio.sleep(0.01)

    async def _monitor():
        await asyncio.sleep(3600)

    critica = asyncio.create_task(_tarea(), name="Task-critica")
    monitor = asyncio.create_task(_monitor(), name="service-lock")
    stop.set()
    await asyncio.sleep(0.02)  # la tarea critica YA termino cuando se mira
    try:
        assert await wait_for_stop_or_lock_loss(stop, monitor, critical_tasks=(critica,)) is True
    finally:
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)


@pytest.mark.asyncio
async def test_una_tarea_critica_que_muere_SIN_apagado_sigue_saltando():
    """El brazo que debe seguir fallando: aflojar el guardia no puede apagarlo."""
    import asyncio

    import pytest as _pytest

    from app.db import wait_for_stop_or_lock_loss

    stop = asyncio.Event()  # nadie pidio parar

    async def _tarea():
        return None

    async def _monitor():
        await asyncio.sleep(3600)

    critica = asyncio.create_task(_tarea(), name="Task-7")
    monitor = asyncio.create_task(_monitor(), name="service-lock")
    await asyncio.sleep(0.01)
    try:
        with _pytest.raises(RuntimeError, match="critical task stopped unexpectedly: Task-7"):
            await wait_for_stop_or_lock_loss(stop, monitor, critical_tasks=(critica,))
    finally:
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)
