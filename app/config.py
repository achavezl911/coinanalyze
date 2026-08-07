from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_network
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SUPPORTED_SYMBOLS = (
    "BTCUSDT_PERP.A",
    "ETHUSDT_PERP.A",
    "SOLUSDT_PERP.A",
)

WS_SYMBOL_MAP = {
    "BTCUSDT_PERP.A": "BTC",
    "ETHUSDT_PERP.A": "ETH",
    "SOLUSDT_PERP.A": "SOL",
}

BYBIT_SYMBOL_MAP = {
    "BTCUSDT_PERP.A": "BTCUSDT.6",
    "ETHUSDT_PERP.A": "ETHUSDT.6",
    "SOLUSDT_PERP.A": "SOLUSDT.6",
}

SPOT_PAIR_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
}

# Coinalyze SI sirve mercados spot con delta real: /spot-markets los marca con
# `has_buy_sell_data: true` y ohlcv-history devuelve bv/btx, con la misma profundidad por
# intervalo que el perp (4hour ~300 d, daily ~2 anios). Hasta ahora el CVD spot solo salia de
# los colectores WS propios, limitados por retencion (14 d el agg, 2 h el realtime).
#
# Se usa el spot del MISMO venue que el perp (sufijo .A = Binance en ambos) a proposito: la
# asimetria documentada en v1.3.4 era comparar perp de Binance contra spot de Binance+Bybit.
# Con las dos patas en Binance, la comparacion es entre mercados, no entre venues.
# El spot de Bybit (sBTCUSDT.6 etc.) existe y tambien trae delta; no se ingiere porque
# duplicaria la cuota sin cambiar la lectura.
SPOT_HISTORY_MAP = {
    "BTCUSDT_PERP.A": "BTCUSD.A",
    "ETHUSDT_PERP.A": "ETHUSD.A",
    "SOLUSDT_PERP.A": "SOLUSD.A",
}

FUTURES_PAIR_MAP = {
    "BTCUSDT_PERP.A": "BTCUSDT",
    "ETHUSDT_PERP.A": "ETHUSDT",
    "SOLUSDT_PERP.A": "SOLUSDT",
}

PAIR_SYMBOL_MAP = {value: key for key, value in FUTURES_PAIR_MAP.items()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    API_KEY: str = ""
    COINALYZE_BASE_URL: str = "https://api.coinalyze.net/v1"
    INGEST_INTERVAL_SECONDS: int = Field(default=60, ge=30, le=900)
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
