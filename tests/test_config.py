from app.config import Settings


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
