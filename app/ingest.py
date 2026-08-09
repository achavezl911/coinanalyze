from __future__ import annotations

import asyncio
import logging
import math
import signal
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import asyncpg

from app.coinalyze import (
    CoinalyzeClient,
    PostgresSlidingWindowRateLimiter,
    validate_rate_budget,
)
from app.config import BYBIT_SYMBOL_MAP, Settings, get_settings
from app.db import (
    acquire_service_lock,
    create_pool,
    heartbeat,
    monitor_service_lock,
    wait_for_stop_or_lock_loss,
)
from app.external_macro import refresh_external_macro
from app.logging_setup import configure_logging
from app.metrics import compute_and_store_all

LOGGER = logging.getLogger(__name__)


def finite(value: object) -> float:
    number = float(value)  # type: ignore[arg-type]
    if not math.isfinite(number):
        raise ValueError("non-finite number")
    return number


# Una vela se etiqueta con el inicio de su bucket, asi que la primera que devuelve la API
# puede empezar antes del start_ts pedido si este no cae en un limite. Con la tolerancia fija
# de 300 s, un bucket de 4 h o diario quedaba fuera de rango y se descartaba en silencio.
OHLCV_INTERVAL_SECONDS = {"1min": 60, "5min": 300, "4hour": 14400, "daily": 86400}


def valid_ts(value: object, start_ts: int, end_ts: int, tolerance: int = 300) -> datetime:
    ts = int(value)  # type: ignore[arg-type]
    if ts < start_ts - tolerance or ts > end_ts + tolerance:
        raise ValueError("timestamp outside requested window")
    return datetime.fromtimestamp(ts, tz=UTC)


def rows_for(
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
) -> Iterable[tuple[str, dict[str, Any]]]:
    for source_symbol, history in payload.items():
        target = symbol_map.get(source_symbol)
        if not target:
            continue
        for row in history:
            yield target, row


async def upsert_ohlcv(
    conn: asyncpg.Connection,
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
    start_ts: int,
    end_ts: int,
    interval: str = "1min",
) -> int:
    if interval not in OHLCV_INTERVAL_SECONDS:
        raise ValueError("unsupported OHLCV interval")
    tolerance = max(300, OHLCV_INTERVAL_SECONDS[interval])
    records: list[tuple[object, ...]] = []
    for symbol, row in rows_for(payload, symbol_map):
        try:
            volume = finite(row["v"])
            buy_volume = finite(row["bv"])
            tx = int(row.get("tx", 0))
            btx = int(row.get("btx", 0))
            open_px, high_px, low_px, close_px = (finite(row[key]) for key in ("o", "h", "l", "c"))
            if (
                min(open_px, high_px, low_px, close_px) <= 0
                or high_px < max(open_px, close_px, low_px)
                or low_px > min(open_px, close_px, high_px)
                or volume < 0
                or not 0 <= buy_volume <= volume
                or tx < 0
                or not 0 <= btx <= tx
            ):
                continue
            record = (
                valid_ts(row["t"], start_ts, end_ts, tolerance),
                symbol,
                interval,
                open_px,
                high_px,
                low_px,
                close_px,
                volume,
                buy_volume,
                tx,
                btx,
            )
            records.append(record)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not records:
        return 0
    await conn.executemany(
        """
        INSERT INTO ohlcv(ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        ON CONFLICT(symbol,interval,ts) DO UPDATE SET
          open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low, close=EXCLUDED.close,
          volume=EXCLUDED.volume, buy_volume=EXCLUDED.buy_volume,
          tx=EXCLUDED.tx, btx=EXCLUDED.btx
        """,
        records,
    )
    return len(records)


async def rollup_ohlcv_5m(
    conn: asyncpg.Connection,
    symbols: tuple[str, ...],
    start_ts: int,
    end_ts: int,
) -> int:
    """Build recent 5-minute candles locally without spending API quota."""
    count = await conn.fetchval(
        """
        WITH bars AS (
          SELECT
            date_bin('5 minutes'::interval, ts, TIMESTAMPTZ '1970-01-01') AS bucket,
            symbol,
            (array_agg(open ORDER BY ts))[1] AS open,
            max(high) AS high,
            min(low) AS low,
            (array_agg(close ORDER BY ts DESC))[1] AS close,
            sum(volume) AS volume,
            sum(buy_volume) AS buy_volume,
            sum(tx)::bigint AS tx,
            sum(btx)::bigint AS btx
          FROM ohlcv
          WHERE interval = '1min'
            AND symbol = ANY($1::text[])
            AND ts >= to_timestamp($2)
            AND ts <= to_timestamp($3)
          GROUP BY bucket, symbol
          -- Una vela de 5 min exige sus 5 minutos. Sin esto se persistian velas de 2 o 3
          -- minutos (incluida la del bucket en curso) indistinguibles de una vela cerrada:
          -- menos volumen, menos rango y un delta que alimentaba ATR, estructura y perfiles.
          HAVING COUNT(*) = 5
        ), upserted AS (
          INSERT INTO ohlcv(
            ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
          )
          SELECT bucket,symbol,'5min',open,high,low,close,volume,buy_volume,tx,btx
          FROM bars
          ON CONFLICT(symbol,interval,ts) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, volume=EXCLUDED.volume,
            buy_volume=EXCLUDED.buy_volume, tx=EXCLUDED.tx, btx=EXCLUDED.btx
          RETURNING 1
        )
        SELECT count(*) FROM upserted
        """,
        list(symbols),
        start_ts,
        end_ts,
    )
    return int(count or 0)


async def upsert_ohlc_metric(
    conn: asyncpg.Connection,
    table: str,
    prefix: str,
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
    start_ts: int,
    end_ts: int,
) -> int:
    allowed = {
        ("open_interest", "oi"),
        ("oi_bybit", "oi"),
        ("funding_rate", "fr"),
        ("predicted_funding_rate", "pfr"),
    }
    if (table, prefix) not in allowed:
        raise ValueError("invalid metric table")
    records: list[tuple[object, ...]] = []
    for symbol, row in rows_for(payload, symbol_map):
        try:
            values = [finite(row[key]) for key in ("o", "h", "l", "c")]
            open_value, high_value, low_value, close_value = values
            if (
                (prefix == "oi" and any(value < 0 for value in values))
                or high_value < max(open_value, close_value, low_value)
                or low_value > min(open_value, close_value, high_value)
            ):
                continue
            records.append((valid_ts(row["t"], start_ts, end_ts), symbol, "5min", *values))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not records:
        return 0
    columns = f"{prefix}_open,{prefix}_high,{prefix}_low,{prefix}_close"
    await conn.executemany(
        f"""
        INSERT INTO {table}(ts,symbol,interval,{columns})
        VALUES($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT(symbol,interval,ts) DO UPDATE SET
          {prefix}_open=EXCLUDED.{prefix}_open,
          {prefix}_high=EXCLUDED.{prefix}_high,
          {prefix}_low=EXCLUDED.{prefix}_low,
          {prefix}_close=EXCLUDED.{prefix}_close
        """,
        records,
    )
    return len(records)


async def upsert_liquidations(
    conn: asyncpg.Connection,
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
    start_ts: int,
    end_ts: int,
) -> int:
    records: list[tuple[object, ...]] = []
    for symbol, row in rows_for(payload, symbol_map):
        try:
            long_liq = finite(row["l"])
            short_liq = finite(row["s"])
            if long_liq < 0 or short_liq < 0:
                continue
            records.append(
                (valid_ts(row["t"], start_ts, end_ts), symbol, "5min", long_liq, short_liq)
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not records:
        return 0
    await conn.executemany(
        """
        INSERT INTO liquidations(ts,symbol,interval,long_liq,short_liq)
        VALUES($1,$2,$3,$4,$5)
        ON CONFLICT(symbol,interval,ts) DO UPDATE SET
          long_liq=EXCLUDED.long_liq, short_liq=EXCLUDED.short_liq
        """,
        records,
    )
    return len(records)


async def upsert_long_short(
    conn: asyncpg.Connection,
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
    start_ts: int,
    end_ts: int,
) -> int:
    """Posicionamiento: l/s son porcentajes que suman 100 y r es su cociente."""
    records: list[tuple[object, ...]] = []
    for symbol, row in rows_for(payload, symbol_map):
        try:
            long_pct = finite(row["l"])
            short_pct = finite(row["s"])
            ratio = finite(row["r"])
            # Se descarta la fila incoherente en vez de normalizarla: si la fuente no cuadra,
            # inventar el reparto seria peor que no tener el dato.
            if not (0 <= long_pct <= 100 and 0 <= short_pct <= 100) or ratio < 0:
                continue
            if abs(long_pct + short_pct - 100) > 1.0:
                continue
            records.append(
                (valid_ts(row["t"], start_ts, end_ts), symbol, "5min", long_pct, short_pct, ratio)
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    if not records:
        return 0
    await conn.executemany(
        """
        INSERT INTO long_short_ratio(ts,symbol,interval,long_pct,short_pct,ratio)
        VALUES($1,$2,$3,$4,$5,$6)
        ON CONFLICT(symbol,interval,ts) DO UPDATE SET
          long_pct=EXCLUDED.long_pct, short_pct=EXCLUDED.short_pct, ratio=EXCLUDED.ratio
        """,
        records,
    )
    return len(records)


async def ingest_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
) -> None:
    await ingest_ohlcv_cycle(pool, client, settings)
    await ingest_metrics_cycle(pool, client, settings)


async def ingest_ohlcv_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
) -> None:
    end_ts = int(time.time() // 60 * 60)
    start_ohlcv = end_ts - 40 * 60
    symbols = tuple(settings.SYMBOLS)
    identity = {symbol: symbol for symbol in symbols}
    ohlcv = await client.history(
        "ohlcv-history", symbols, interval="1min", start_ts=start_ohlcv, end_ts=end_ts
    )
    async with pool.acquire() as conn:
        async with conn.transaction():
            count = await upsert_ohlcv(
                conn, ohlcv, identity, start_ohlcv, end_ts, "1min"
            )
            rolled_up = await rollup_ohlcv_5m(conn, symbols, start_ohlcv, end_ts)
            await compute_and_store_all(conn, symbols)
        await heartbeat(
            conn,
            "ingest",
            detail=f"feed=ohlcv_1m,rows={count},rollup_5m={rolled_up}",
        )
    LOGGER.info("ingest_ohlcv_cycle_complete rows=%d rollup_5m=%d", count, rolled_up)


async def ingest_metrics_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
) -> None:
    end_ts = int(time.time() // 300 * 300)
    start_history = end_ts - 26 * 60 * 60
    symbols = tuple(settings.SYMBOLS)
    identity = {symbol: symbol for symbol in symbols}
    bybit_symbols = tuple(BYBIT_SYMBOL_MAP[symbol] for symbol in symbols)
    bybit_inverse = {value: key for key, value in BYBIT_SYMBOL_MAP.items()}

    oi, oi_bybit = await asyncio.gather(
        client.history(
            "open-interest-history", symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts, convert_to_usd=True,
        ),
        client.history(
            "open-interest-history", bybit_symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts, convert_to_usd=True,
        ),
    )
    await asyncio.sleep(1)
    funding, predicted = await asyncio.gather(
        client.history(
            "funding-rate-history", symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts,
        ),
        client.history(
            "predicted-funding-rate-history", symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts,
        ),
    )
    await asyncio.sleep(1)
    liquidations, long_short = await asyncio.gather(
        client.history(
            "liquidation-history", symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts, convert_to_usd=True,
        ),
        client.history(
            "long-short-ratio-history", symbols, interval="5min", start_ts=start_history,
            end_ts=end_ts,
        ),
    )

    counts: dict[str, int] = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            counts["oi"] = await upsert_ohlc_metric(
                conn, "open_interest", "oi", oi, identity, start_history, end_ts
            )
            counts["oi_bybit"] = await upsert_ohlc_metric(
                conn, "oi_bybit", "oi", oi_bybit, bybit_inverse, start_history, end_ts
            )
            counts["funding"] = await upsert_ohlc_metric(
                conn, "funding_rate", "fr", funding, identity, start_history, end_ts
            )
            counts["predicted"] = await upsert_ohlc_metric(
                conn, "predicted_funding_rate", "pfr", predicted, identity, start_history, end_ts
            )
            counts["liquidations"] = await upsert_liquidations(
                conn, liquidations, identity, start_history, end_ts
            )
            counts["long_short"] = await upsert_long_short(
                conn, long_short, identity, start_history, end_ts
            )
        await heartbeat(conn, "ingest", status="ok", detail=f"feed=metrics_5m,{counts}"[:500])
    LOGGER.info("ingest_metrics_cycle_complete counts=%s", counts)
    # Este contexto cambia despacio y no consume cuota de Coinalyze. Cada fuente se degrada
    # por separado: un calendario externo caído nunca invalida la ingestión de mercado.
    try:
        await refresh_external_macro(pool, settings)
    except Exception:
        LOGGER.exception("external_macro_refresh_failed")


def seconds_until_aligned_run(
    now: float,
    cadence_seconds: int,
    offset_seconds: int,
) -> float:
    boundary = (int(now) // cadence_seconds + 1) * cadence_seconds
    return max(boundary + offset_seconds - now, 0.0)


async def run_aligned_feed(
    stop: asyncio.Event,
    callback,
    *,
    cadence_seconds: int,
    offset_seconds: int,
    name: str,
) -> None:
    while not stop.is_set():
        timeout = seconds_until_aligned_run(time.time(), cadence_seconds, offset_seconds)
        try:
            await asyncio.wait_for(stop.wait(), timeout=timeout)
            continue
        except TimeoutError:
            pass
        try:
            await callback()
        except Exception:
            LOGGER.exception("ingest_feed_failed feed=%s", name)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    budget = validate_rate_budget(
        len(settings.SYMBOLS),
        settings.COINALYZE_RATE_LIMIT_UNITS,
        ohlcv_cadence_seconds=settings.INGEST_INTERVAL_SECONDS,
    )
    LOGGER.info(
        "coinalyze_rate_budget symbols=%d ohlcv_units_per_cycle=%d "
        "metrics_units_per_cycle=%d daily_units_per_cycle=%d projected_units_per_minute=%.2f "
        "configured_limit=%d",
        budget.symbol_count,
        budget.ohlcv_units_per_cycle,
        budget.metrics_units_per_cycle,
        budget.daily_units_per_cycle,
        budget.projected_units_per_minute,
        settings.COINALYZE_RATE_LIMIT_UNITS,
    )
    service_lock = await acquire_service_lock(settings, "ingest")
    pool = await create_pool(settings, application_name="coinalyze-ingest")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    lock_monitor = asyncio.create_task(
        monitor_service_lock(service_lock, "ingest"),
        name="service-lock",
    )
    tasks: tuple[asyncio.Task[None], ...] = ()

    try:
        limiter = PostgresSlidingWindowRateLimiter(
            pool,
            settings.COINALYZE_RATE_LIMIT_UNITS,
        )
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            tasks = (
                asyncio.create_task(
                    run_aligned_feed(
                        stop,
                        lambda: ingest_ohlcv_cycle(pool, client, settings),
                        cadence_seconds=settings.INGEST_INTERVAL_SECONDS,
                        offset_seconds=5,
                        name="ohlcv_1m",
                    )
                ),
                asyncio.create_task(
                    run_aligned_feed(
                        stop,
                        lambda: ingest_metrics_cycle(pool, client, settings),
                        cadence_seconds=300,
                        offset_seconds=15,
                        name="metrics_5m",
                    )
                ),
            )
            await wait_for_stop_or_lock_loss(stop, lock_monitor)
    finally:
        for task in tasks:
            task.cancel()
        lock_monitor.cancel()
        await asyncio.gather(*tasks, lock_monitor, return_exceptions=True)
        await pool.close()
        await service_lock.close()


if __name__ == "__main__":
    asyncio.run(run())
