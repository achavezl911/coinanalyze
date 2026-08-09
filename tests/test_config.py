import json

import pytest

from app.config import (
    BYBIT_SYMBOL_MAP,
    DEFAULT_MARKET_CATALOG,
    FUTURES_PAIR_MAP,
    LARGE_TRADE_THRESHOLD_MAP,
    PAIR_SYMBOL_MAP,
    SPOT_HISTORY_MAP,
    SPOT_PAIR_MAP,
    SUPPORTED_SYMBOLS,
    WHALE_THRESHOLD_MAP,
    WS_SYMBOL_MAP,
    Settings,
    load_market_catalog,
)


def test_csv_settings_parsing():
    settings = Settings(
        SYMBOLS="BTCUSDT_PERP.A,ETHUSDT_PERP.A",
        TRUSTED_HOSTS="127.0.0.1,localhost",
    )
    assert settings.SYMBOLS == ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A")
    assert settings.TRUSTED_HOSTS == ("127.0.0.1", "localhost")


def test_security_settings_parse_cidrs_and_sslmode():
    settings = Settings(
        API_INTERNAL_ALLOWED_CIDRS='["127.0.0.1/32","10.10.100.0/28"]',
        PG_SSLMODE="require",
    )
    assert settings.API_INTERNAL_ALLOWED_CIDRS == ("127.0.0.1/32", "10.10.100.0/28")
    assert settings.pg_dsn.endswith("sslmode=require")


def test_default_symbol_maps_are_generated_from_single_catalog():
    assert tuple(item.symbol for item in DEFAULT_MARKET_CATALOG) == SUPPORTED_SYMBOLS
    for item in DEFAULT_MARKET_CATALOG:
        assert WS_SYMBOL_MAP[item.symbol] == item.base_asset
        assert BYBIT_SYMBOL_MAP[item.symbol] == item.bybit_oi_symbol
        assert SPOT_PAIR_MAP[item.base_asset] == item.spot_pair
        assert SPOT_HISTORY_MAP[item.symbol] == item.spot_history_symbol
        assert FUTURES_PAIR_MAP[item.symbol] == item.futures_pair
        assert PAIR_SYMBOL_MAP[item.futures_pair] == item.symbol
        assert WHALE_THRESHOLD_MAP[item.base_asset] == item.whale_threshold_usd
        assert LARGE_TRADE_THRESHOLD_MAP[item.symbol] == item.large_trade_threshold_usd


def test_versioned_catalog_can_extend_with_fourth_asset(tmp_path):
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "mode": "extend",
                "symbols": [
                    {
                        "symbol": "XRPUSDT_PERP.A",
                        "base_asset": "XRP",
                        "futures_pair": "XRPUSDT",
                        "bybit_oi_symbol": "XRPUSDT.6",
                        "spot_pair": "XRPUSDT",
                        "spot_history_symbol": "XRPUSD.A",
                        "whale_threshold_usd": 100_000.0,
                        "large_trade_threshold_usd": 50_000.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    catalog = load_market_catalog(path)

    assert len(catalog) == 4
    assert catalog[-1].base_asset == "XRP"


def test_invalid_shard_settings_are_rejected():
    with pytest.raises(ValueError, match="less than"):
        Settings(COLLECTOR_SHARD_INDEX=2, COLLECTOR_SHARD_COUNT=2)
