from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap


def test_fourth_versioned_asset_flows_through_config_sharding_persistence_and_api(tmp_path):
    symbol = {
        "symbol": "XRPUSDT_PERP.A",
        "base_asset": "XRP",
        "futures_pair": "XRPUSDT",
        "bybit_oi_symbol": "XRPUSDT.6",
        "spot_pair": "XRPUSDT",
        "spot_history_symbol": "XRPUSD.A",
        "whale_threshold_usd": 100_000.0,
        "large_trade_threshold_usd": 50_000.0,
    }
    catalog_path = tmp_path / "market-symbols.json"
    catalog_path.write_text(
        json.dumps({"version": 1, "mode": "extend", "symbols": [symbol]}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["MARKET_SYMBOL_CATALOG_FILE"] = str(catalog_path)
    env["SYMBOLS"] = json.dumps(
        ["BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A", "XRPUSDT_PERP.A"]
    )
    program = textwrap.dedent(
        """
        import asyncio
        from app.api import symbols as api_symbols, validate_symbol
        from app.config import MARKET_SYMBOL_CATALOG, SUPPORTED_SYMBOLS, Settings
        from app.db import sync_market_catalog
        from app.sharding import assigned_symbols
        from app.signal_runtime_contract import (
            compute_scientific_runtime_contract,
            effective_market_routing_from_contract,
        )
        from app.ws_collector import binance_url

        configured = Settings().SYMBOLS
        assert "XRPUSDT_PERP.A" in SUPPORTED_SYMBOLS
        assert "XRPUSDT_PERP.A" in configured
        assert validate_symbol("XRPUSDT_PERP.A") == "XRPUSDT_PERP.A"
        assert {row["symbol"] for row in asyncio.run(api_symbols())} == set(configured)
        shards = [assigned_symbols(configured, index, 3) for index in range(3)]
        assert set().union(*(set(shard) for shard in shards)) == set(configured)
        # An extended catalog resolves an unregistered contract, so the routing
        # here is built from the computed projection, never from the gate.
        routing = effective_market_routing_from_contract(
            compute_scientific_runtime_contract()
        )
        assert "xrpusdt@aggTrade" in binance_url(("XRPUSDT_PERP.A",), routing)

        class Conn:
            def __init__(self):
                self.rows = []
            async def __aenter__(self): return self
            async def __aexit__(self, *args): return None
            def transaction(self): return self
            async def executemany(self, query, rows): self.rows.extend(rows)
        class Pool:
            def __init__(self): self.conn = Conn()
            def acquire(self): return self.conn

        pool = Pool()
        asyncio.run(sync_market_catalog(pool, MARKET_SYMBOL_CATALOG))
        assert ("XRP",) in pool.conn.rows
        assert ("XRPUSDT_PERP.A", "XRP", True) in pool.conn.rows
        """
    )

    subprocess.run([sys.executable, "-c", program], env=env, check=True, text=True)
