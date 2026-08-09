from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


@dataclass(frozen=True, slots=True)
class MarketSymbol:
    symbol: str
    base_asset: str
    futures_pair: str
    bybit_oi_symbol: str
    spot_pair: str
    spot_history_symbol: str
    whale_threshold_usd: float
    large_trade_threshold_usd: float


# Catálogo único por defecto. Los umbrales reproducen los valores actuales; no son una
# recalibración. MARKET_SYMBOL_CATALOG_FILE puede apuntar a un JSON versionado que extienda o
# reemplace estas filas sin contener credenciales.
DEFAULT_MARKET_CATALOG = (
    MarketSymbol(
        "BTCUSDT_PERP.A", "BTC", "BTCUSDT", "BTCUSDT.6", "BTCUSDT", "BTCUSD.A",
        5_000_000.0, 1_000_000.0,
    ),
    MarketSymbol(
        "ETHUSDT_PERP.A", "ETH", "ETHUSDT", "ETHUSDT.6", "ETHUSDT", "ETHUSD.A",
        1_000_000.0, 400_000.0,
    ),
    MarketSymbol(
        "SOLUSDT_PERP.A", "SOL", "SOLUSDT", "SOLUSDT.6", "SOLUSDT", "SOLUSD.A",
        200_000.0, 150_000.0,
    ),
)


def load_market_catalog(path: str | os.PathLike[str] | None = None) -> tuple[MarketSymbol, ...]:
    catalog = {item.symbol: item for item in DEFAULT_MARKET_CATALOG}
    if path:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("market symbol catalog must be an object with version=1")
        mode = payload.get("mode", "extend")
        if mode not in {"extend", "replace"}:
            raise ValueError("market symbol catalog mode must be extend or replace")
        rows = payload.get("symbols")
        if not isinstance(rows, list):
            raise ValueError("market symbol catalog symbols must be a list")
        if mode == "replace":
            catalog.clear()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("market symbol catalog rows must be objects")
            item = MarketSymbol(**row)
            catalog[item.symbol] = item

    items = tuple(catalog.values())
    if not items:
        raise ValueError("market symbol catalog cannot be empty")
    for item in items:
        values = asdict(item)
        if any(not isinstance(values[field], str) or not values[field].strip() for field in (
            "symbol", "base_asset", "futures_pair", "bybit_oi_symbol", "spot_pair",
            "spot_history_symbol",
        )):
            raise ValueError("market symbol identifiers cannot be empty")
        if (
            not math.isfinite(item.whale_threshold_usd)
            or not math.isfinite(item.large_trade_threshold_usd)
            or item.whale_threshold_usd <= 0
            or item.large_trade_threshold_usd <= 0
        ):
            raise ValueError("market symbol thresholds must be positive")
    for field in (
        "base_asset",
        "futures_pair",
        "bybit_oi_symbol",
        "spot_pair",
        "spot_history_symbol",
    ):
        values = [getattr(item, field) for item in items]
        if len(values) != len(set(values)):
            raise ValueError(f"market symbol catalog has duplicate {field}")
    return items


_VERSIONED_CATALOG_PATH = Path("config/market_symbols.json")
MARKET_SYMBOL_CATALOG_FILE = os.environ.get("MARKET_SYMBOL_CATALOG_FILE", "").strip()
if not MARKET_SYMBOL_CATALOG_FILE and _VERSIONED_CATALOG_PATH.is_file():
    MARKET_SYMBOL_CATALOG_FILE = str(_VERSIONED_CATALOG_PATH)
MARKET_SYMBOL_CATALOG = load_market_catalog(MARKET_SYMBOL_CATALOG_FILE or None)
SUPPORTED_SYMBOLS = tuple(item.symbol for item in MARKET_SYMBOL_CATALOG)
WS_SYMBOL_MAP = {item.symbol: item.base_asset for item in MARKET_SYMBOL_CATALOG}
BYBIT_SYMBOL_MAP = {item.symbol: item.bybit_oi_symbol for item in MARKET_SYMBOL_CATALOG}
SPOT_PAIR_MAP = {item.base_asset: item.spot_pair for item in MARKET_SYMBOL_CATALOG}
SPOT_HISTORY_MAP = {item.symbol: item.spot_history_symbol for item in MARKET_SYMBOL_CATALOG}
FUTURES_PAIR_MAP = {item.symbol: item.futures_pair for item in MARKET_SYMBOL_CATALOG}
PAIR_SYMBOL_MAP = {item.futures_pair: item.symbol for item in MARKET_SYMBOL_CATALOG}
WHALE_THRESHOLD_MAP = {
    item.base_asset: item.whale_threshold_usd for item in MARKET_SYMBOL_CATALOG
}
LARGE_TRADE_THRESHOLD_MAP = {
    item.symbol: item.large_trade_threshold_usd for item in MARKET_SYMBOL_CATALOG
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    API_KEY: str = ""
    COINALYZE_BASE_URL: str = "https://api.coinalyze.net/v1"
    INGEST_INTERVAL_SECONDS: int = Field(default=60, ge=60, le=60)
    COINALYZE_RATE_LIMIT_UNITS: int = Field(default=35, ge=1, le=40)
    EXTERNAL_MACRO_ENABLED: bool = True
    EXTERNAL_MACRO_REFRESH_SECONDS: int = Field(default=3600, ge=900, le=21600)
    # Opcional: las series oficiales y el calendario funcionan sin credenciales.
    # CoinGlass solo añade la pata de flujos ETF cuando el operador configura su clave.
    COINGLASS_API_KEY: str = ""

    PG_HOST: str = "127.0.0.1"
    PG_PORT: int = Field(default=5432, ge=1, le=65535)
    PG_DB: str = "coinalyze"
    PG_USER: str = "coinalyze"
    PG_PASSWORD: str = ""
    PG_POOL_MIN: int = Field(default=1, ge=1, le=10)
    PG_POOL_MAX: int = Field(default=4, ge=1, le=30)
    PG_SSLMODE: str = "disable"

    COLLECTOR_SHARD_INDEX: int = Field(default=0, ge=0)
    COLLECTOR_SHARD_COUNT: int = Field(default=1, ge=1)

    API_HOST: str = "127.0.0.1"
    API_PORT: int = Field(default=8000, ge=1, le=65535)
    API_INTERNAL_TOKEN: str = ""
    API_INTERNAL_ALLOWED_CIDRS: Annotated[tuple[str, ...], NoDecode] = (
        "127.0.0.1/32",
        "::1/128",
        "10.10.100.0/28",
    )
    METRICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    TRUSTED_HOSTS: Annotated[tuple[str, ...], NoDecode] = ("127.0.0.1", "localhost")

    SCALP_ENABLED: bool = True
    SCALP_FLUSH_SECONDS: int = Field(default=2, ge=1, le=10)
    SCALP_ORDERBOOK_FLUSH_SECONDS: int = Field(default=2, ge=1, le=10)
    SCALP_TRADE_RETENTION_HOURS: int = Field(default=6, ge=1, le=72)
    # futures_trades_agg alimenta el CVD diario de futuros restringido a Binance+Bybit.
    # La sesion NYSE dura 24h y el job diario corre cada hora, asi que hay que cubrirla
    # entera con holgura. Va separado de SCALP_TRADE_RETENTION_HOURS porque los buckets
    # de 1 min son ~300x mas baratos de retener que los de 5 s.
    SCALP_MINUTE_RETENTION_HOURS: int = Field(default=36, ge=26, le=168)
    SCALP_ORDERBOOK_RETENTION_HOURS: int = Field(default=6, ge=1, le=72)
    SCALP_SIGNAL_INTERVAL_SECONDS: int = Field(default=10, ge=2, le=60)
    SCALP_SIGNAL_RETENTION_HOURS: int = Field(default=72, ge=1, le=720)
    TRADESTORE_MAX_BUCKET_MINUTES: int = Field(default=20, ge=5, le=240)
    TRADESTORE_MAX_BUCKETS_PER_KEY: int = Field(default=30, ge=5, le=240)
    BINANCE_BOOK_MAX_EVENT_LAG_SECONDS: int = Field(default=10, ge=2, le=60)
    BINANCE_BOOK_STALE_SECONDS: int = Field(default=15, ge=3, le=120)
    BINANCE_BOOK_FORCE_RECONNECT_SECONDS: int = Field(default=300, ge=60, le=3600)

    HARD_DATA_RETENTION_DAYS: int = Field(default=14, ge=2, le=365)
    HTF_DATA_RETENTION_DAYS: int = Field(default=400, ge=30, le=3650)
    SNAPSHOT_RETENTION_DAYS: int = Field(default=30, ge=2, le=730)
    REALTIME_RETENTION_HOURS: int = Field(default=2, ge=1, le=48)
    DAILY_LOOKBACK_DAYS: int = Field(default=13, ge=2, le=60)
    DAILY_SESSION_RETENTION_DAYS: int = Field(
        default=0, ge=0, le=3650
    )  # 0 = conservar indefinidamente

    SYMBOLS: Annotated[tuple[str, ...], NoDecode] = SUPPORTED_SYMBOLS

    @field_validator("SYMBOLS", "TRUSTED_HOSTS", "API_INTERNAL_ALLOWED_CIDRS", mode="before")
    @classmethod
    def parse_csv_or_json(cls, value: object) -> object:
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("[") and text.endswith("]"):
                import json

                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("Expected JSON list")
                return tuple(str(item).strip() for item in parsed if str(item).strip())
            return tuple(item.strip() for item in text.split(",") if item.strip())
        return value

    @field_validator("SYMBOLS")
    @classmethod
    def validate_symbols(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = sorted(set(value) - set(SUPPORTED_SYMBOLS))
        if unknown:
            raise ValueError(f"Unsupported symbols: {', '.join(unknown)}")
        if not value:
            raise ValueError("At least one symbol is required")
        return value

    @field_validator("PG_SSLMODE")
    @classmethod
    def validate_pg_sslmode(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
        if normalized not in allowed:
            raise ValueError(f"PG_SSLMODE must be one of: {', '.join(sorted(allowed))}")
        return normalized

    @field_validator("API_INTERNAL_ALLOWED_CIDRS")
    @classmethod
    def validate_internal_cidrs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for cidr in value:
            ip_network(cidr, strict=False)
        return value

    @field_validator("PG_POOL_MAX")
    @classmethod
    def validate_pool(cls, value: int, info):
        pool_min = info.data.get("PG_POOL_MIN", 1)
        if value < pool_min:
            raise ValueError("PG_POOL_MAX must be >= PG_POOL_MIN")
        return value

    @model_validator(mode="after")
    def validate_shard(self) -> Settings:
        if self.COLLECTOR_SHARD_INDEX >= self.COLLECTOR_SHARD_COUNT:
            raise ValueError("COLLECTOR_SHARD_INDEX must be less than COLLECTOR_SHARD_COUNT")
        return self

    @property
    def pg_dsn(self) -> str:
        # Keep disable as the local-LXC default, but allow encrypted PostgreSQL traffic
        # when the DB is moved to another container/node.
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}@"
            f"{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}?sslmode={self.PG_SSLMODE}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
