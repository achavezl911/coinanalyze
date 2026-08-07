"""v1.3.9 — velas 4h nativas como fuente de los pivotes de barreras.

Medido contra la API de Coinalyze el 2026-08-04 (BTC, ventana de 5 dias, esperado 30 velas):
`4hour` responde 30 a 30d/120d/200d/300d y 0 a 365d; `5min` responde 0 ya a 20 dias. Una
peticion unica de 120 dias a 4hour devuelve exactamente 720 velas, que es el objetivo de
BARRIER_INTRADAY_TARGET_BARS.
"""

from __future__ import annotations

import pathlib

import pytest

from app.ingest import OHLCV_INTERVAL_SECONDS, upsert_ohlcv, valid_ts

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_schema_accepts_the_4hour_interval() -> None:
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    assert "CHECK (interval IN ('1min','5min','4hour','daily'))" in schema


def test_ingest_knows_the_4hour_interval() -> None:
    assert OHLCV_INTERVAL_SECONDS["4hour"] == 14400


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_intervals() -> None:
    with pytest.raises(ValueError):
        await upsert_ohlcv(None, {}, {}, 0, 1, "3hour")  # type: ignore[arg-type]


def test_bucket_tolerance_scales_with_the_interval() -> None:
    """Una vela se etiqueta con el inicio de su bucket. Con la tolerancia fija de 300 s, el
    primer bucket de 4 h caia fuera de rango y se descartaba en silencio."""
    start, end = 1_000_000, 2_000_000
    bucket_start = start - 14_000  # dentro del bucket de 4 h que contiene a start
    with pytest.raises(ValueError):
        valid_ts(bucket_start, start, end)
    assert valid_ts(bucket_start, start, end, 14400).timestamp() == bucket_start


def test_retention_covers_4hour_bars() -> None:
    """Sin regla propia las velas 4h crecerian sin limite."""
    source = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert "(interval='4hour' AND ts < now() - make_interval(days => $2))" in source


def test_daily_cycle_refreshes_4hour_bars() -> None:
    """El backfill las trae una vez; el borde necesita reescribirse cada ciclo."""
    source = (ROOT / "app" / "daily_agg.py").read_text(encoding="utf-8")
    assert 'interval="4hour"' in source
    assert "h4_candles" in source


def test_barriers_prefer_native_4h_over_the_5min_resample() -> None:
    """5min solo llega a ~8-9 dias; preferirlo dejaba los pivotes en el 6.7% del objetivo."""
    source = (ROOT / "app" / "scalp_logic.py").read_text(encoding="utf-8")
    body = source[source.index("async def price_barriers") : source.index("async def market_memory")]
    native = body.index('"4hour"')
    fallback = body.index('"5min"')
    assert native < fallback, "la fuente 4h nativa debe intentarse antes que el resample 5min"
    assert "BARRIER_INTRADAY_TARGET_BARS" in body


def test_backfill_script_caps_at_the_measured_horizon() -> None:
    """Pedir 365 dias devuelve chunks vacios que se leen como un backfill exitoso."""
    source = (ROOT / "scripts" / "backfill_ohlcv_4h.py").read_text(encoding="utf-8")
    assert "MAX_SUPPORTED_DAYS = 300" in source
