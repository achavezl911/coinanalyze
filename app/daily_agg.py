from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter, validate_rate_budget
from app.config import SPOT_HISTORY_MAP, WS_SYMBOL_MAP, get_settings
from app.db import (
    acquire_service_lock,
    create_pool,
    heartbeat,
    monitor_service_lock,
    wait_for_stop_or_lock_loss,
)
from app.ingest import seconds_until_aligned_run, upsert_ohlcv
from app.interpretation import evaluate_setups
from app.logging_setup import configure_logging
from app.metrics import session_bounds
from app.scalp_logic import swing_score

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


def latest_closed_session_date(now_utc: datetime | None = None) -> date:
    now_et = (now_utc or datetime.now(UTC)).astimezone(NY)
    if now_et.timetz().replace(tzinfo=None) >= time(9, 30):
        return now_et.date()
    return now_et.date() - timedelta(days=1)


# Una sesion NYSE son 1440 minutos. Por debajo de esta cobertura el CVD de futuros de
# 2 venues seria una suma parcial disfrazada de total, asi que se guarda NULL y el UPSERT
# conserva el valor bueno que se escribio cuando la sesion acababa de cerrar.
MIN_2V_COVERAGE_MINUTES = 1368  # 95% de 1440


SESSION_QUERY = """
WITH fut AS (
  SELECT
    SUM(delta * close) AS cvd_fut,
    (array_agg(open ORDER BY ts ASC))[1] AS price_open,
    (array_agg(close ORDER BY ts DESC))[1] AS price_close,
    MAX(high) AS price_high,
    MIN(low) AS price_low,
    SUM(volume * close) AS volume_usd,
    SUM(tx) AS tx_count,
    COUNT(*) AS samples
  FROM ohlcv
  WHERE symbol=$1 AND interval='1min' AND ts >= $3 AND ts < $4
),
-- Misma pata de futuros que fut.cvd_fut pero restringida a Binance+Bybit, el mismo
-- universo de venues que spot_trades_agg. Es la unica comparacion legitima; ohlcv es el
-- perp de BINANCE (el sufijo .A de Coinalyze es Binance, no un agregado). El perp mueve
-- ~10x el spot, asi que restarle el spot de dos exchanges producia un "diferencial" que en
-- 92-95% de las sesiones era simplemente el CVD de futuros con el signo cambiado.
fut2v AS (
  SELECT
    SUM(buy_vol_usd - sell_vol_usd) AS cvd_fut_2v,
    COUNT(*) AS minutes
  FROM futures_trades_agg
  WHERE symbol=$1 AND exchange='combined' AND interval='1min' AND ts >= $3 AND ts < $4
),
spot AS (
  SELECT
    COALESCE(SUM(buy_vol_usd - sell_vol_usd),0) AS cvd_spot,
    COALESCE(SUM(inst_buy_usd - inst_sell_usd),0) AS inst_delta
  FROM spot_trades_agg
  WHERE symbol=$2 AND exchange='combined' AND interval='1min' AND ts >= $3 AND ts < $4
),
oi AS (
  SELECT
    (array_agg(oi_open ORDER BY ts ASC))[1] AS oi_open,
    (array_agg(oi_close ORDER BY ts DESC))[1] AS oi_close,
    MAX(oi_high) AS oi_high,
    MIN(oi_low) AS oi_low
  FROM open_interest
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
),
liq AS (
  SELECT SUM(long_liq) AS long_liq, SUM(short_liq) AS short_liq
  FROM liquidations
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
),
fr AS (
  SELECT AVG(fr_close) AS fr_avg
  FROM funding_rate
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
)
SELECT fut.cvd_fut, fut.price_open, fut.price_close, fut.samples,
       fut.price_high, fut.price_low, fut.volume_usd, fut.tx_count,
       fut2v.cvd_fut_2v, fut2v.minutes AS fut_2v_minutes,
       spot.cvd_spot, spot.inst_delta,
       oi.oi_open, oi.oi_close, oi.oi_high, oi.oi_low,
       liq.long_liq, liq.short_liq, fr.fr_avg
FROM fut CROSS JOIN fut2v CROSS JOIN spot CROSS JOIN oi CROSS JOIN liq CROSS JOIN fr
"""


async def compute_session(
    conn: asyncpg.Connection,
    symbol: str,
    ws_symbol: str,
    session_date_value: date,
) -> bool:
    start, end = session_bounds(session_date_value)
    row = await conn.fetchrow(SESSION_QUERY, symbol, ws_symbol, start, end)
    if not row or not row["samples"] or row["price_open"] is None or row["price_close"] is None:
        return False
    minutes_2v = int(row["fut_2v_minutes"] or 0)
    complete_2v = minutes_2v >= MIN_2V_COVERAGE_MINUTES
    await conn.execute(
        """
        INSERT INTO daily_session_agg(
          session_date,symbol,cvd_spot_usd,cvd_fut_usd,inst_delta_usd,
          price_open,price_close,oi_open,oi_close,fr_avg,
          cvd_fut_2v_usd,cvd_fut_2v_minutes,
          volume_usd,price_high,price_low,long_liq_usd,short_liq_usd,
          oi_high,oi_low,tx_count,created_at
        ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,now())
        ON CONFLICT(symbol,session_date) DO UPDATE SET
          cvd_spot_usd=EXCLUDED.cvd_spot_usd,
          cvd_fut_usd=EXCLUDED.cvd_fut_usd,
          inst_delta_usd=EXCLUDED.inst_delta_usd,
          price_open=EXCLUDED.price_open,
          price_close=EXCLUDED.price_close,
          oi_open=EXCLUDED.oi_open,
          oi_close=EXCLUDED.oi_close,
          fr_avg=EXCLUDED.fr_avg,
          -- Estas dependen de tablas de retencion corta: al recalcular una sesion vieja el
          -- dato ya no existe y EXCLUDED viene NULL. COALESCE conserva el valor bueno que
          -- se escribio cuando la sesion acababa de cerrar, en vez de borrarlo.
          cvd_fut_2v_usd=COALESCE(EXCLUDED.cvd_fut_2v_usd, daily_session_agg.cvd_fut_2v_usd),
          cvd_fut_2v_minutes=COALESCE(EXCLUDED.cvd_fut_2v_minutes, daily_session_agg.cvd_fut_2v_minutes),
          volume_usd=COALESCE(EXCLUDED.volume_usd, daily_session_agg.volume_usd),
          price_high=COALESCE(EXCLUDED.price_high, daily_session_agg.price_high),
          price_low=COALESCE(EXCLUDED.price_low, daily_session_agg.price_low),
          long_liq_usd=COALESCE(EXCLUDED.long_liq_usd, daily_session_agg.long_liq_usd),
          short_liq_usd=COALESCE(EXCLUDED.short_liq_usd, daily_session_agg.short_liq_usd),
          oi_high=COALESCE(EXCLUDED.oi_high, daily_session_agg.oi_high),
          oi_low=COALESCE(EXCLUDED.oi_low, daily_session_agg.oi_low),
          tx_count=COALESCE(EXCLUDED.tx_count, daily_session_agg.tx_count),
          created_at=now()
        """,
        session_date_value,
        symbol,
        row["cvd_spot"],
        row["cvd_fut"],
        row["inst_delta"],
        row["price_open"],
        row["price_close"],
        row["oi_open"],
        row["oi_close"],
        row["fr_avg"],
        row["cvd_fut_2v"] if complete_2v else None,
        minutes_2v if complete_2v else None,
        row["volume_usd"],
        row["price_high"],
        row["price_low"],
        row["long_liq"],
        row["short_liq"],
        row["oi_high"],
        row["oi_low"],
        int(row["tx_count"]) if row["tx_count"] is not None else None,
    )
    return True


async def backfill(conn: asyncpg.Connection, symbols: tuple[str, ...], lookback: int) -> int:
    latest = latest_closed_session_date()
    inserted = 0
    for offset in range(lookback):
        session_date_value = latest - timedelta(days=offset)
        for symbol in symbols:
            exists = await conn.fetchval(
                "SELECT 1 FROM daily_session_agg WHERE symbol=$1 AND session_date=$2",
                symbol,
                session_date_value,
            )
            if exists and offset >= 2:
                continue
            if await compute_session(conn, symbol, WS_SYMBOL_MAP[symbol], session_date_value):
                inserted += 1
    return inserted


DAILY_ROWS_QUERY = """
WITH selected AS (
  SELECT * FROM daily_session_agg WHERE symbol=$1
  ORDER BY session_date DESC LIMIT 60
)
SELECT session_date, cvd_spot_usd,
       SUM(cvd_spot_usd) OVER (ORDER BY session_date) AS cumulative_spot
FROM selected ORDER BY session_date
"""


async def persist_verdicts(conn: asyncpg.Connection, symbols: tuple[str, ...]) -> int:
    """Congela el veredicto del modelo para la sesion recien cerrada.

    swing_score, regime y setups se calculaban al vuelo y se descartaban: metrics_snapshot
    solo retiene 30 dias y scalp_signal_snapshot 72 horas, asi que no habia manera de
    preguntar despues si el modelo acerto. Esta fila sobrevive con daily_session_agg.
    """
    session_date_value = latest_closed_session_date()
    stored = 0
    for symbol in symbols:
        session = await conn.fetchrow(
            "SELECT price_close FROM daily_session_agg WHERE symbol=$1 AND session_date=$2",
            symbol,
            session_date_value,
        )
        if session is None:
            continue  # la sesion todavia no esta agregada; se guardara en el proximo ciclo
        swing = await swing_score(conn, symbol)
        snapshot = await conn.fetchrow(
            "SELECT * FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts DESC LIMIT 1", symbol
        )
        primary: dict[str, object] = {}
        streak = None
        if snapshot is not None:
            daily_rows = [dict(r) for r in await conn.fetch(DAILY_ROWS_QUERY, symbol)]
            setups = evaluate_setups(dict(snapshot), daily_rows)
            primary = setups.get("primary") or {}
            streak = setups.get("daily_streak")
        await conn.execute(
            """
            INSERT INTO daily_verdict(
              session_date,symbol,swing_bias,swing_score,swing_conviction,long_share_pct,
              swing_components,regime_score,regime_label,setup_id,setup_name,setup_state,
              setup_confidence,daily_streak,price_close,created_at,updated_at
            ) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12,$13,$14,$15,now(),now())
            ON CONFLICT(symbol,session_date) DO UPDATE SET
              swing_bias=EXCLUDED.swing_bias,
              swing_score=EXCLUDED.swing_score,
              swing_conviction=EXCLUDED.swing_conviction,
              long_share_pct=EXCLUDED.long_share_pct,
              swing_components=EXCLUDED.swing_components,
              regime_score=EXCLUDED.regime_score,
              regime_label=EXCLUDED.regime_label,
              setup_id=EXCLUDED.setup_id,
              setup_name=EXCLUDED.setup_name,
              setup_state=EXCLUDED.setup_state,
              setup_confidence=EXCLUDED.setup_confidence,
              daily_streak=EXCLUDED.daily_streak,
              price_close=EXCLUDED.price_close,
              updated_at=now()
            """,
            session_date_value,
            symbol,
            # swing_score puede devolver SIN_DATOS/"sin datos" cuando ningun componente pudo
            # medirse. La columna solo admite LONG/SHORT/NEUTRAL y baja/media/alta, y NULL ya
            # significa exactamente "no hubo veredicto": se guarda NULL en vez de inventar uno.
            swing.get("bias") if swing.get("bias") in ("LONG", "SHORT", "NEUTRAL") else None,
            swing.get("score"),
            swing.get("conviction")
            if swing.get("conviction") in ("baja", "media", "alta")
            else None,
            swing.get("long_share_pct"),
            json.dumps(swing.get("components") or [], ensure_ascii=False),
            snapshot["regime_score"] if snapshot is not None else None,
            snapshot["regime_label"] if snapshot is not None else None,
            primary.get("id"),
            primary.get("name"),
            primary.get("state"),
            primary.get("confidence"),
            streak,
            session["price_close"],
        )
        stored += 1
    return stored


async def apply_retention(
    conn: asyncpg.Connection,
    hard_days: int,
    htf_days: int,
    snapshot_days: int,
    rt_hours: int,
    daily_days: int,
) -> None:
    # 'daily' no se purga a proposito: son 3 filas por dia y sostienen market_memory_2y.
    await conn.execute(
        "DELETE FROM ohlcv WHERE "
        "(interval='1min' AND ts < now() - make_interval(days => $1)) OR "
        "(interval='5min' AND ts < now() - make_interval(days => $2)) OR "
        "(interval='4hour' AND ts < now() - make_interval(days => $2))",
        hard_days,
        htf_days,
    )
    await conn.execute(
        "DELETE FROM open_interest WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM oi_bybit WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM funding_rate WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM predicted_funding_rate WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM liquidations WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM long_short_ratio WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM spot_trades_agg WHERE ts < now() - make_interval(days => $1)", hard_days
    )
    await conn.execute(
        "DELETE FROM metrics_snapshot WHERE ts < now() - make_interval(days => $1)", snapshot_days
    )
    if daily_days > 0:
        await conn.execute(
            "DELETE FROM daily_session_agg WHERE session_date < (current_date - $1::int)",
            daily_days,
        )
        await conn.execute(
            "DELETE FROM daily_verdict WHERE session_date < (current_date - $1::int)",
            daily_days,
        )
    await conn.execute(
        "DELETE FROM spot_trades_realtime WHERE ts < now() - make_interval(hours => $1)", rt_hours
    )


# Ventanas con baseline y de que intervalo se construyen. 1min cubre hasta 1 h; por encima el
# muestreo se queda corto (a 4 h saldrian ~80 observaciones sobre 14 dias) y se usa el 4hour,
# que tiene 300 dias. Son las mismas etiquetas que publica delta_matrix.
BASELINE_WINDOWS = (
    ("1m", 60, "1min"),
    ("3m", 180, "1min"),
    ("5m", 300, "1min"),
    ("15m", 900, "1min"),
    ("18m", 1080, "1min"),
    ("30m", 1800, "1min"),
    ("1h", 3600, "1min"),
    ("4h", 14400, "4hour"),
    ("8h", 28800, "4hour"),
    ("1d", 86400, "4hour"),
)


# Metrica -> expresion sobre el bucket agregado. Cada una se mide igual (percentiles + MAD)
# y se guarda como una fila de metric_baseline.
BASELINE_METRICS = {
    # Concentracion del flujo agresivo: |delta|/volumen.
    "delta_ratio": "abs(delta)/volume",
    # Impacto REALIZADO: bps que se movio el precio por cada 1M USD de delta neto. Medido,
    # no modelado. A 15 m la mediana es 0.93 en BTC, 1.67 en ETH y 10.25 en SOL: el mismo
    # flujo mueve SOL once veces mas. Se descarta el bucket con delta despreciable porque
    # dividir por casi cero da un impacto enorme que no significa nada (afecta al 0-1%).
    "impact_bps_per_musd": (
        "CASE WHEN abs(delta)*px_close/1e6 > 0.01 AND px_open > 0 "
        "THEN (abs(px_close-px_open)/px_open*10000)/(abs(delta)*px_close/1e6) END"
    ),
}


async def refresh_baselines(conn: asyncpg.Connection, symbols: tuple[str, ...]) -> int:
    """Mide cada metrica por simbolo y ventana y guarda su distribucion.

    Se agrupa el intervalo fuente en buckets del tamano de la ventana y solo se acepta el
    bucket COMPLETO (todas las velas presentes): un bucket a medias tiene menos volumen y
    infla artificialmente el ratio.

    Guarda MAD ademas de percentiles porque el z-score robusto ((x-mediana)/(1.4826*MAD)) es
    el que aguanta la cola de estas distribuciones; con media y sigma un solo pico la deforma.
    """
    total = 0
    for label, seconds, source in BASELINE_WINDOWS:
        source_seconds = 60 if source == "1min" else 14400
        expected = max(seconds // source_seconds, 1)
        for metric, expression in BASELINE_METRICS.items():
            total += await _store_baseline(
                conn, symbols, label, seconds, source, expected, metric, expression
            )
    return total


async def _store_baseline(
    conn: asyncpg.Connection,
    symbols: tuple[str, ...],
    label: str,
    seconds: int,
    source: str,
    expected: int,
    metric: str,
    expression: str,
) -> int:
    total = 0
    rows = await conn.fetch(
        f"""
        WITH b AS (
          SELECT symbol,
                 date_bin(make_interval(secs => $2::int), ts, '1970-01-01'::timestamptz) AS bucket,
                 SUM(delta) AS delta, SUM(volume) AS volume, COUNT(*) AS parts,
                 (array_agg(open ORDER BY ts))[1] AS px_open,
                 (array_agg(close ORDER BY ts DESC))[1] AS px_close
          FROM ohlcv
          WHERE interval=$3 AND symbol = ANY($1::text[])
          GROUP BY 1,2
        ), r AS (
          SELECT symbol, ({expression}) AS ratio, bucket
          FROM b WHERE volume > 0 AND parts = $4::int
        ), agg AS (
          SELECT symbol, count(*)::int AS n,
                 percentile_cont(0.50) WITHIN GROUP (ORDER BY ratio) AS p50,
                 percentile_cont(0.75) WITHIN GROUP (ORDER BY ratio) AS p75,
                 percentile_cont(0.90) WITHIN GROUP (ORDER BY ratio) AS p90,
                 percentile_cont(0.95) WITHIN GROUP (ORDER BY ratio) AS p95,
                 min(bucket) AS lo, max(bucket) AS hi
          -- El impacto es NULL cuando el delta es despreciable: fuera de la muestra, no cero.
          FROM r WHERE ratio IS NOT NULL GROUP BY symbol
        )
        SELECT agg.*,
               (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(r.ratio-agg.p50))
                FROM r WHERE r.symbol=agg.symbol AND r.ratio IS NOT NULL) AS mad
        FROM agg
        """,
        list(symbols),
        seconds,
        source,
        expected,
    )
    for row in rows:
        # Una muestra corta no es una distribucion: mejor sin baseline que con una mentira.
        if not row["n"] or row["n"] < 30:
            continue
        await conn.execute(
            """
            INSERT INTO metric_baseline(
              symbol,metric,window_label,window_seconds,source_interval,sample_count,
              p50,p75,p90,p95,mad,sample_start,sample_end,updated_at)
            VALUES($1,$13,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,now())
            ON CONFLICT(symbol,metric,window_label) DO UPDATE SET
              window_seconds=EXCLUDED.window_seconds,source_interval=EXCLUDED.source_interval,
              sample_count=EXCLUDED.sample_count,p50=EXCLUDED.p50,p75=EXCLUDED.p75,
              p90=EXCLUDED.p90,p95=EXCLUDED.p95,mad=EXCLUDED.mad,
              sample_start=EXCLUDED.sample_start,sample_end=EXCLUDED.sample_end,
              updated_at=now()
            """,
            row["symbol"], label, seconds, source, row["n"],
            row["p50"], row["p75"], row["p90"], row["p95"], row["mad"] or 0.0,
            row["lo"], row["hi"], metric,
        )
        total += 1
    return total


async def cycle(pool: asyncpg.Pool, client: CoinalyzeClient) -> None:
    settings = get_settings()
    end_ts = int(datetime.now(UTC).timestamp())
    start_ts = end_ts - 3 * 86400
    # Las velas 4h se refrescan con una ventana mas ancha que la diaria: el backfill las trae
    # una vez, pero el borde necesita reescribirse mientras el bucket en curso se cierra.
    start_4h = end_ts - 7 * 86400
    daily_payload: dict[str, list[dict]] = {}
    h4_payload: dict[str, list[dict]] = {}
    spot_daily_payload: dict[str, list[dict]] = {}
    spot_h4_payload: dict[str, list[dict]] = {}
    spot_symbols = tuple(SPOT_HISTORY_MAP[s] for s in settings.SYMBOLS if s in SPOT_HISTORY_MAP)
    try:
        daily_payload = await client.history(
            "ohlcv-history", settings.SYMBOLS, interval="daily", start_ts=start_ts,
            end_ts=end_ts,
        )
        await asyncio.sleep(1)
        h4_payload = await client.history(
            "ohlcv-history", settings.SYMBOLS, interval="4hour", start_ts=start_4h,
            end_ts=end_ts,
        )
        # El spot va en la MISMA rejilla temporal que el perp para que las dos patas se
        # puedan restar bucket a bucket sin realinear nada.
        if spot_symbols:
            await asyncio.sleep(1)
            spot_daily_payload = await client.history(
                "ohlcv-history", spot_symbols, interval="daily", start_ts=start_ts,
                end_ts=end_ts,
            )
            await asyncio.sleep(1)
            spot_h4_payload = await client.history(
                "ohlcv-history", spot_symbols, interval="4hour", start_ts=start_4h,
                end_ts=end_ts,
            )
    except Exception:
        LOGGER.exception("daily_ohlcv_refresh_failed")
    async with pool.acquire() as conn:
        async with conn.transaction():
            identity = {symbol: symbol for symbol in settings.SYMBOLS}
            spot_identity = {symbol: symbol for symbol in spot_symbols}
            daily_candles = await upsert_ohlcv(
                conn, daily_payload, identity, start_ts, end_ts, "daily"
            )
            h4_candles = await upsert_ohlcv(conn, h4_payload, identity, start_4h, end_ts, "4hour")
            spot_candles = await upsert_ohlcv(
                conn, spot_daily_payload, spot_identity, start_ts, end_ts, "daily"
            ) + await upsert_ohlcv(
                conn, spot_h4_payload, spot_identity, start_4h, end_ts, "4hour"
            )
            inserted = await backfill(conn, settings.SYMBOLS, settings.DAILY_LOOKBACK_DAYS)
            verdicts = await persist_verdicts(conn, settings.SYMBOLS)
            baselines = await refresh_baselines(conn, settings.SYMBOLS)
            await apply_retention(
                conn,
                settings.HARD_DATA_RETENTION_DAYS,
                settings.HTF_DATA_RETENTION_DAYS,
                settings.SNAPSHOT_RETENTION_DAYS,
                settings.REALTIME_RETENTION_HOURS,
                settings.DAILY_SESSION_RETENTION_DAYS,
            )
        await heartbeat(
            conn,
            "daily",
            detail=(
                f"daily_candles={daily_candles},h4_candles={h4_candles},"
                f"spot_candles={spot_candles},baselines={baselines},"
                f"daily_rows={inserted},verdicts={verdicts}"
            ),
        )
    LOGGER.info(
        "daily_cycle_complete daily_candles=%d h4_candles=%d inserted=%d verdicts=%d",
        daily_candles,
        h4_candles,
        inserted,
        verdicts,
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    budget = validate_rate_budget(len(settings.SYMBOLS), settings.COINALYZE_RATE_LIMIT_UNITS)
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
    service_lock = await acquire_service_lock(settings, "daily")
    pool = await create_pool(settings, application_name="coinalyze-daily")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    lock_monitor = asyncio.create_task(
        monitor_service_lock(service_lock, "daily"),
        name="service-lock",
    )
    try:
        limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            first_run = True
            while not stop.is_set():
                timeout = (
                    45.0
                    if first_run
                    else seconds_until_aligned_run(datetime.now(UTC).timestamp(), 3600, 45)
                )
                first_run = False
                if await wait_for_stop_or_lock_loss(
                    stop,
                    lock_monitor,
                    timeout=timeout,
                ):
                    continue
                cycle_task = asyncio.create_task(cycle(pool, client))
                done, _ = await asyncio.wait(
                    (cycle_task, lock_monitor),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if lock_monitor in done:
                    cycle_task.cancel()
                    await asyncio.gather(cycle_task, return_exceptions=True)
                    await lock_monitor
                try:
                    await cycle_task
                except Exception as exc:
                    LOGGER.exception("daily_cycle_failed")
                    try:
                        await heartbeat(pool, "daily", status="error", detail=str(exc)[:500])
                    except Exception:
                        LOGGER.exception("daily_heartbeat_failed")
    finally:
        lock_monitor.cancel()
        await asyncio.gather(lock_monitor, return_exceptions=True)
        await pool.close()
        await service_lock.close()


if __name__ == "__main__":
    asyncio.run(run())
