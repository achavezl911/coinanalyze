from pathlib import Path

import pytest

from app.scalp_logic import _oi_change_pct, spot_flow_windows

ROOT = Path(__file__).resolve().parents[1]


class FlowConnection:
    def __init__(self):
        self.query = ""

    async def fetch(self, query, *_args):
        if "data_gap" in query:
            return []
        self.query = query
        return [
            {
                "horizon": "4h",
                "seconds": 14400,
                "exchange": "combined",
                "delta": 100.0,
                "volume": 1_000.0,
                "trades": 10,
                "source_rows": 200,
                "source": "agg_1min+realtime",
                "complete": True,
                "end_gap_seconds": 8.0,
                "precision_seconds": 60,
            },
            {
                "horizon": "8h",
                "seconds": 28800,
                "exchange": "combined",
                "delta": 240.0,
                "volume": 2_400.0,
                "trades": 24,
                "source_rows": 400,
                "source": "agg_1min+realtime",
                "complete": True,
                "end_gap_seconds": 8.0,
                "precision_seconds": 60,
            },
        ]


@pytest.mark.asyncio
async def test_long_spot_windows_stitch_history_and_live_tail_without_overlap():
    conn = FlowConnection()
    result = await spot_flow_windows(conn, "BTC", [("4h", 14400), ("8h", 28800)])

    assert result["4h"]["combined"]["delta"] == 100.0
    assert result["8h"]["combined"]["delta"] == 240.0
    assert result["8h"]["combined"]["coverage_status"] == "complete"
    assert "spot_trades_agg" in conn.query
    assert "c.agg_hi+interval '1 minute'" in conn.query
    assert "NOT c.realtime_complete" in conn.query


@pytest.mark.asyncio
async def test_explicit_spot_gap_overrides_apparent_span_completeness():
    class BlockedFlowConnection(FlowConnection):
        async def fetch(self, query, *_args):
            if "data_gap" in query:
                return [{"key": "4h:combined"}]
            return await super().fetch(query, *_args)

    result = await spot_flow_windows(
        BlockedFlowConnection(),
        "BTC",
        [("4h", 14400), ("8h", 28800)],
    )

    assert result["4h"]["combined"]["complete"] is False
    assert result["4h"]["combined"]["coverage_status"] == "partial"
    assert result["4h"]["combined"]["delta"] is None
    assert result["4h"]["combined"]["gap_reason"] == "data_gap"
    assert result["8h"]["combined"]["complete"] is True


@pytest.mark.asyncio
async def test_oi_change_is_unavailable_below_five_minute_source_resolution():
    class NoQueryConnection:
        async def fetchval(self, *_args):
            raise AssertionError("sub-5m OI must not be queried")

    assert await _oi_change_pct(NoQueryConnection(), "BTCUSDT_PERP.A", 60) is None


@pytest.mark.asyncio
async def test_oi_change_is_anchored_to_latest_sample_instead_of_wall_clock():
    class OIConnection:
        query = ""

        async def fetchval(self, query, *_args):
            self.query = query
            return 1.25

    conn = OIConnection()
    assert await _oi_change_pct(conn, "BTCUSDT_PERP.A", 300) == 1.25
    assert "cur.ts-" in conn.query
    assert "now()-" not in conn.query


def test_cvd_divergence_uses_only_common_closed_buckets():
    source = (ROOT / "app" / "api.py").read_text(encoding="utf-8")
    start = source.index("async def cvd_divergence")
    end = source.index("async def oi", start)
    endpoint = source[start:end]

    assert "complete_until" in endpoint
    assert "FROM fut JOIN spot USING(bucket)" in endpoint
    assert "FULL OUTER JOIN" not in endpoint
