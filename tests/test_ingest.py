from app.ingest import rollup_ohlcv_5m, upsert_ohlcv


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
