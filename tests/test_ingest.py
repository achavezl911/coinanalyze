from datetime import UTC, datetime

import app.ingest as ingest
from app.config import Settings
from app.cutoffs import ClosedCutoff
from app.ingest import rollup_ohlcv_5m, seconds_until_aligned_run, upsert_ohlcv


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


class _CyclePool:
    def __init__(self):
        self.conn = _CycleConnection()

    def acquire(self):
        return self.conn


class _CycleClient:
    async def history(self, *_args, **_kwargs):
        return {}


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

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(ingest, "upsert_ohlc_metric", fake_metric)
    monkeypatch.setattr(ingest, "upsert_liquidations", fake_metric)
    monkeypatch.setattr(ingest, "upsert_long_short", fake_metric)
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

    assert events[:7] == ["metric"] * 6 + ["snapshot"]
    assert events[7] == "heartbeat"


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

    monkeypatch.setattr(ingest, "heartbeat_component", no_op)
    monkeypatch.setattr(ingest, "refresh_external_macro", no_op)
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
    assert pool.conn.snapshot_args[-2] == datetime(2026, 8, 9, 12, 4, tzinfo=UTC)
    assert pool.conn.snapshot_args[-1] == datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
