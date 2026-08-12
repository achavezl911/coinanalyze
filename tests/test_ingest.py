import asyncio
import os
from datetime import UTC, datetime

import asyncpg
import pytest

import app.ingest as ingest
import app.metrics as metrics
from app.config import Settings
from app.cutoffs import ClosedCutoff
from app.ingest import publish_snapshot, rollup_ohlcv_5m, seconds_until_aligned_run, upsert_ohlcv


class FakeConnection:
    def __init__(self):
        self.records = None

    async def executemany(self, _query, records):
        self.records = records


async def test_upsert_ohlcv_skips_invalid_candles():
    conn = FakeConnection()
    payload = {
        "BTCUSDT_PERP.A": [
            {"t": 1000, "o": 10, "h": 12, "l": 9, "c": 11, "v": 100, "bv": 60, "tx": 10, "btx": 6},
            {"t": 1000, "o": 10, "h": 8, "l": 9, "c": 11, "v": 100, "bv": 60, "tx": 10, "btx": 6},
        ]
    }
    count = await upsert_ohlcv(
        conn,
        payload,
        {"BTCUSDT_PERP.A": "BTCUSDT_PERP.A"},
        900,
        1100,
    )
    assert count == 1
    assert len(conn.records) == 1


async def test_upsert_ohlcv_rejects_timestamp_after_closed_upper_cutoff():
    conn = FakeConnection()
    candle = {"o": 10, "h": 12, "l": 9, "c": 11, "v": 100, "bv": 60, "tx": 10, "btx": 6}
    payload = {
        "BTCUSDT_PERP.A": [
            {**candle, "t": 1140},
            {**candle, "t": 1200},
        ]
    }

    count = await upsert_ohlcv(
        conn,
        payload,
        {"BTCUSDT_PERP.A": "BTCUSDT_PERP.A"},
        900,
        1199,
        "1min",
    )

    assert count == 1
    assert conn.records[0][0] == datetime.fromtimestamp(1140, tz=UTC)


def test_closed_cutoffs_exclude_new_buckets_after_five_minute_boundary():
    for now in (
        datetime(2026, 8, 9, 12, 5, 5, tzinfo=UTC),
        datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
    ):
        minute = ClosedCutoff.at(now, 60)
        metrics = ClosedCutoff.at(now, 300)

        assert datetime.fromtimestamp(minute.latest_bucket_ts, tz=UTC) == datetime(
            2026, 8, 9, 12, 4, tzinfo=UTC
        )
        assert datetime.fromtimestamp(metrics.latest_bucket_ts, tz=UTC) == datetime(
            2026, 8, 9, 12, 0, tzinfo=UTC
        )
        assert minute.api_end_ts == minute.boundary_ts - 1
        assert metrics.api_end_ts == metrics.boundary_ts - 1


class FakeRollupConnection:
    def __init__(self):
        self.query = ""
        self.args = ()

    async def fetchval(self, query, *args):
        self.query = query
        self.args = args
        return 6


async def test_rollup_ohlcv_5m_uses_local_one_minute_bars():
    conn = FakeRollupConnection()
    symbols = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A")

    count = await rollup_ohlcv_5m(conn, symbols, 1000, 2000)

    assert count == 6
    assert "date_bin('5 minutes'" in conn.query
    assert "interval = '1min'" in conn.query
    assert conn.args == (list(symbols), 1000, 2000)


def test_feed_schedules_align_after_closed_buckets():
    assert seconds_until_aligned_run(61.0, 60, 5) == 64.0
    assert seconds_until_aligned_run(301.0, 300, 15) == 314.0


class _CycleConnection:
    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, *_args, **_kwargs):
        return None


class _CyclePool:
    def __init__(self):
        self.conn = _CycleConnection()

    def acquire(self):
        return self.conn


class _CycleClient:
    async def history(self, *_args, **_kwargs):
        return {}


async def _complete_cadence_proof(_conn, **kwargs):
    start = kwargs["start"]
    end = kwargs["end"]
    cadence = kwargs["cadence"]
    expected_buckets = int((end - start) // cadence)
    return ingest.CadenceCoverage(
        start=start,
        end=end,
        cadence=cadence,
        expected_buckets=expected_buckets,
        observed_buckets=expected_buckets,
        missing_buckets=0,
        missing_windows=(),
        recovered_gaps=0,
    )


async def _healthy_liquidation_history(*_args, **_kwargs):
    return True


async def test_one_minute_cycle_refreshes_metrics_snapshots(monkeypatch):
    refreshed: list[tuple[str, ...]] = []

    async def fake_upsert(*_args, **_kwargs):
        return 0

    async def fake_rollup(*_args, **_kwargs):
        return 0

    async def fake_compute(_conn, symbols, **_kwargs):
        refreshed.append(symbols)

    async def fake_heartbeat(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ingest, "upsert_ohlcv", fake_upsert)
    monkeypatch.setattr(ingest, "rollup_ohlcv_5m", fake_rollup)
    monkeypatch.setattr(ingest, "_reconcile_persisted_cadence", _complete_cadence_proof)
    monkeypatch.setattr(ingest, "_reconcile_response_cadence", _complete_cadence_proof)
    monkeypatch.setattr(ingest, "compute_and_store_all", fake_compute)
    monkeypatch.setattr(ingest, "heartbeat_component", fake_heartbeat)
    settings = Settings(SYMBOLS=("BTCUSDT_PERP.A",))

    await ingest.ingest_ohlcv_cycle(_CyclePool(), _CycleClient(), settings)

    assert refreshed == [("BTCUSDT_PERP.A",)]


async def test_five_minute_cycle_refreshes_metrics_snapshots_after_upserts(monkeypatch):
    events: list[str] = []

    async def fake_metric(*_args, **_kwargs):
        events.append("metric")
        return 1

    async def fake_compute(_conn, _symbols, **kwargs):
        events.append("snapshot")
        assert kwargs["price_cutoff"] == datetime(2026, 8, 9, 12, 5, tzinfo=UTC)
        assert kwargs["metrics_cutoff"] == datetime(2026, 8, 9, 12, 5, tzinfo=UTC)

    async def fake_heartbeat(*_args, **_kwargs):
        events.append("heartbeat")

    async def fake_liquidation_observation(*_args, **_kwargs):
        events.append("observation")
        return 1

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(ingest, "upsert_ohlc_metric", fake_metric)
    monkeypatch.setattr(ingest, "upsert_liquidations", fake_metric)
    monkeypatch.setattr(ingest, "upsert_long_short", fake_metric)
    monkeypatch.setattr(
        ingest,
        "persist_liquidation_history_observations",
        fake_liquidation_observation,
    )
    monkeypatch.setattr(ingest, "_reconcile_response_cadence", _complete_cadence_proof)
    monkeypatch.setattr(ingest, "compute_and_store_all", fake_compute)
    monkeypatch.setattr(ingest, "heartbeat_component", fake_heartbeat)
    monkeypatch.setattr(ingest, "refresh_external_macro", fake_heartbeat)
    monkeypatch.setattr(ingest.asyncio, "sleep", no_sleep)

    await ingest.ingest_metrics_cycle(
        _CyclePool(),
        _CycleClient(),
        Settings(SYMBOLS=("BTCUSDT_PERP.A",)),
        now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
    )

    assert events[:8] == ["metric"] * 6 + ["observation", "snapshot"]
    assert events[8] == "heartbeat"


class _StatefulMetricsConnection(_CycleConnection):
    def __init__(self) -> None:
        self.oi = None
        self.oi_ts = None
        self.snapshot_args = None

    async def executemany(self, query, records):
        if "INSERT INTO open_interest" in query and records:
            latest = max(records, key=lambda record: record[0])
            self.oi_ts = latest[0]
            self.oi = latest[6]

    async def fetchrow(self, _query, *_args):
        return {
            "price": 101.0,
            "price_ts": datetime(2026, 8, 9, 12, 4, tzinfo=UTC),
            "price_1h": 100.0,
            "oi_now": self.oi,
            "oi_ts": self.oi_ts,
            "oi_old": 100.0,
        }

    async def fetch(self, query, *_args):
        assert "data_gap" in query
        return []

    async def execute(self, query, *args):
        if "INSERT INTO metrics_snapshot" in query:
            self.snapshot_args = args


class _StatefulMetricsPool(_CyclePool):
    def __init__(self):
        self.conn = _StatefulMetricsConnection()


class _BoundaryMetricsClient:
    def __init__(self) -> None:
        self.ends: list[int] = []

    async def history(self, endpoint, symbols, **kwargs):
        self.ends.append(kwargs["end_ts"])
        if endpoint != "open-interest-history" or str(symbols[0]).endswith(".6"):
            return {}
        closed = {"t": 1_786_276_800, "o": 100, "h": 200, "l": 100, "c": 200}
        open_bucket = {"t": 1_786_277_100, "o": 200, "h": 999, "l": 200, "c": 999}
        return {symbols[0]: [closed, open_bucket]}


async def test_oi_jump_in_latest_closed_bucket_is_in_immediate_metrics_snapshot(monkeypatch):
    pool = _StatefulMetricsPool()
    client = _BoundaryMetricsClient()

    async def no_op(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ingest, "_reconcile_response_cadence", _complete_cadence_proof)
    monkeypatch.setattr(metrics, "_liquidation_history_observed", _healthy_liquidation_history)
    monkeypatch.setattr(ingest, "heartbeat_component", no_op)
    monkeypatch.setattr(ingest, "refresh_external_macro", no_op)
    monkeypatch.setattr(ingest, "persist_liquidation_history_observations", no_op)
    monkeypatch.setattr(ingest.asyncio, "sleep", no_op)

    await ingest.ingest_metrics_cycle(
        pool,
        client,
        Settings(SYMBOLS=("BTCUSDT_PERP.A",)),
        now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
    )

    assert set(client.ends) == {1_786_277_099}
    assert pool.conn.oi == 200
    assert pool.conn.oi_ts == datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    assert pool.conn.snapshot_args is not None
    assert pool.conn.snapshot_args[1] == 101.0
    assert pool.conn.snapshot_args[2] == 200.0
    assert pool.conn.snapshot_args[28] == datetime(2026, 8, 9, 12, 4, tzinfo=UTC)
    assert pool.conn.snapshot_args[29] == datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    assert pool.conn.snapshot_args[-1] == metrics.REGIME_LOGIC_VERSION


def _test_dsn() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest.mark.asyncio
async def test_postgres_snapshot_publication_is_serialized_across_ohlcv_and_metrics_cycles():
    """Reproduces the confirmed race: A(OHLCV) writes a new closed price without
    committing; B(metrics) starts later, cannot see it, persists OI and publishes a
    snapshot with the older price, then commits; A commits afterwards. Without
    serialization + a real-time clock at insert time, B's snapshot could sort as
    "latest" even though A's is the correct, more recent one.
    """
    dsn = _test_dsn()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    # WS_SYMBOL_MAP/BYBIT_SYMBOL_MAP only cover the catalog symbols, so this must reuse
    # one of them (pre-seeded by sql/schema.sql) rather than a synthetic name.
    symbol = "BTCUSDT_PERP.A"
    conn_a = conn_b = control = None
    try:
        control = await asyncpg.connect(dsn)
        # Baseline committed state: an old closed candle and the latest committed OI.
        await control.execute(
            """
            INSERT INTO ohlcv(ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx)
            VALUES(to_timestamp(1786276980),$1,'1min',99,100,98,100,10,5,10,5)
            """,
            symbol,
        )
        await control.execute(
            """
            INSERT INTO open_interest(ts,symbol,interval,oi_open,oi_high,oi_low,oi_close)
            VALUES(to_timestamp(1786276800),$1,'5min',250,250,250,250)
            """,
            symbol,
        )

        conn_a = await asyncpg.connect(dsn)
        conn_b = await asyncpg.connect(dsn)

        # A (OHLCV cycle): begins writing the new closed price (12:04) but does not
        # commit yet.
        tx_a = conn_a.transaction()
        await tx_a.start()
        await conn_a.execute(
            """
            INSERT INTO ohlcv(ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx)
            VALUES(to_timestamp(1786277040),$1,'1min',100,105,100,104,10,5,10,5)
            """,
            symbol,
        )

        # B (metrics cycle): runs its own publish_snapshot concurrently while A is still
        # uncommitted. Under READ COMMITTED it must not see A's new price.
        await publish_snapshot(
            conn_b,
            None,
            (symbol,),
            now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
            price_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
            metrics_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
        )
        stale_row = await control.fetchrow(
            "SELECT price, oi FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts DESC LIMIT 1",
            symbol,
        )
        assert stale_row["price"] == 100.0
        assert stale_row["oi"] == 250.0

        # A commits its OHLCV write, then publishes its own (correct) snapshot.
        await tx_a.commit()
        await publish_snapshot(
            conn_a,
            None,
            (symbol,),
            now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
            price_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
            metrics_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
        )

        latest = await control.fetchrow(
            """
            SELECT price, oi, price_cutoff_at, metrics_cutoff_at
            FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts DESC LIMIT 1
            """,
            symbol,
        )
        assert latest["price"] == 104.0
        assert latest["oi"] == 250.0
        assert latest["price_cutoff_at"] == datetime(2026, 8, 9, 12, 4, tzinfo=UTC)
        assert latest["metrics_cutoff_at"] == datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    finally:
        if control is not None:
            await control.execute(
                "DELETE FROM metrics_snapshot WHERE symbol=$1 AND ts > $2",
                symbol,
                datetime(2026, 8, 9, tzinfo=UTC),
            )
            await control.execute(
                "DELETE FROM ohlcv WHERE symbol=$1 AND ts > $2",
                symbol,
                datetime(2026, 8, 9, tzinfo=UTC),
            )
            await control.execute(
                "DELETE FROM open_interest WHERE symbol=$1 AND ts > $2",
                symbol,
                datetime(2026, 8, 9, tzinfo=UTC),
            )
        for connection in (conn_a, conn_b, control):
            if connection is not None and not connection.is_closed():
                await connection.close()


@pytest.mark.asyncio
async def test_postgres_snapshot_publish_lock_serializes_concurrent_cycles():
    """The advisory lock must force one publish_snapshot() call to wait for the other:
    this is what keeps clock_timestamp() ordering equal to real completion order instead
    of depending on scheduling luck.
    """
    dsn = _test_dsn()
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    symbol = "ETHUSDT_PERP.A"
    conn_a = conn_b = control = None
    try:
        control = await asyncpg.connect(dsn)
        await control.execute(
            """
            INSERT INTO ohlcv(ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx)
            VALUES(to_timestamp(1786276980),$1,'1min',99,100,98,100,10,5,10,5)
            """,
            symbol,
        )
        conn_a = await asyncpg.connect(dsn)
        conn_b = await asyncpg.connect(dsn)

        held = asyncio.Event()
        release = asyncio.Event()
        real_lock_query = "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))"

        class _PacedConnection:
            """Delegates to a real asyncpg connection, pausing right after it takes
            the shared advisory lock so the test can prove a concurrent publish
            attempt actually blocks on it (asyncpg.Connection attributes are
            read-only, so this wraps rather than monkeypatches)."""

            def __init__(self, conn: asyncpg.Connection) -> None:
                self._conn = conn

            def transaction(self):
                return self._conn.transaction()

            async def execute(self, query, *args):
                result = await self._conn.execute(query, *args)
                if query == real_lock_query:
                    held.set()
                    await release.wait()
                return result

            async def fetchrow(self, query, *args):
                return await self._conn.fetchrow(query, *args)

            async def fetch(self, query, *args):
                return await self._conn.fetch(query, *args)

        async def slow_publish() -> None:
            await publish_snapshot(
                _PacedConnection(conn_a),  # type: ignore[arg-type]
                None,
                (symbol,),
                now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
                price_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
                metrics_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
            )

        task_a = asyncio.create_task(slow_publish())
        await asyncio.wait_for(held.wait(), timeout=3)

        task_b = asyncio.create_task(
            publish_snapshot(
                conn_b,
                None,
                (symbol,),
                now_utc=datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC),
                price_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
                metrics_cutoff=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
            )
        )
        await asyncio.sleep(0.2)
        assert not task_b.done(), "B must block on the shared advisory lock while A holds it"
        release.set()
        await asyncio.gather(task_a, task_b)

        rows = await control.fetch(
            "SELECT ts FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts", symbol
        )
        assert len(rows) == 2
        assert rows[0]["ts"] < rows[1]["ts"]
    finally:
        if control is not None:
            await control.execute(
                "DELETE FROM metrics_snapshot WHERE symbol=$1 AND ts > $2",
                symbol,
                datetime(2026, 8, 9, tzinfo=UTC),
            )
            await control.execute(
                "DELETE FROM ohlcv WHERE symbol=$1 AND ts > $2",
                symbol,
                datetime(2026, 8, 9, tzinfo=UTC),
            )
        for connection in (conn_a, conn_b, control):
            if connection is not None and not connection.is_closed():
                await connection.close()
