import app.ingest as ingest
from app.config import Settings
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

    async def fake_compute(_conn, symbols):
        refreshed.append(symbols)

    async def fake_heartbeat(*_args, **_kwargs):
        return None

    monkeypatch.setattr(ingest, "upsert_ohlcv", fake_upsert)
    monkeypatch.setattr(ingest, "rollup_ohlcv_5m", fake_rollup)
    monkeypatch.setattr(ingest, "compute_and_store_all", fake_compute)
    monkeypatch.setattr(ingest, "heartbeat", fake_heartbeat)
    settings = Settings(SYMBOLS=("BTCUSDT_PERP.A",))

    await ingest.ingest_ohlcv_cycle(_CyclePool(), _CycleClient(), settings)

    assert refreshed == [("BTCUSDT_PERP.A",)]
