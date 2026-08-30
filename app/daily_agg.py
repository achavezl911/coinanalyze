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
    ServiceOwnership,
    ServiceOwnershipLost,
    acquire_service_lock,
    create_pool,
    fenced_transaction,
    heartbeat,
    heartbeat_owned,
    monitor_service_lock,
    wait_for_stop_or_lock_loss,
)
from app.ingest import (
    barrido_cadencia_persistido,
    rollup_ohlcv_5m,
    seconds_until_aligned_run,
    upsert_ohlcv,
)
from app.interpretation import evaluate_setups
from app.logging_setup import configure_logging
from app.metrics import (
    REGIME_LOGIC_VERSION,
    liquidation_history_observation,
    session_bounds,
)
from app.partitioning import apply_temporal_retention
from app.scalp_logic import swing_score

LOGGER = logging.getLogger(__name__)
NY = ZoneInfo("America/New_York")


def latest_closed_session_date(now_utc: datetime | None = None) -> date:
    now_et = (now_utc or datetime.now(UTC)).astimezone(NY)
    if now_et.timetz().replace(tzinfo=None) >= time(9, 30):
        return now_et.date()
    return now_et.date() - timedelta(days=1)


# PR20/F3: una sesion NYSE no siempre dura 1440 minutos en UTC. El cambio de DST
# produce sesiones de 23 h y 25 h. La cobertura se mide contra la duracion REAL de
# session_bounds() y por fuente; 0 sigue significando una medicion cuyo neto fue cero.
SESSION_MIN_COVERAGE_RATIO = 0.95
SESSION_COVERAGE_VERSION = 2
DAILY_VERDICT_SNAPSHOT_VERSION = 1
LIQUIDATION_COVERAGE_VERSION = 1
DAILY_VERDICT_LOGIC_VERSION = "daily-verdict-v4"
DAILY_VERDICT_OUTCOME_VERSION = 1
DAILY_VERDICT_OUTCOME_HORIZONS = (7, 14)


def _expected_session_samples(start: datetime, end: datetime, cadence_seconds: int) -> int:
    if cadence_seconds <= 0:
        raise ValueError("cadence_seconds must be positive")
    seconds = (end - start).total_seconds()
    if seconds <= 0 or seconds % cadence_seconds:
        raise ValueError("session window must be a positive exact multiple of cadence")
    return int(seconds // cadence_seconds)


def _coverage_complete(observed: int, expected: int) -> bool:
    return expected > 0 and observed * 100 >= expected * int(SESSION_MIN_COVERAGE_RATIO * 100)


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
    COUNT(*)::int AS samples
  FROM ohlcv
  WHERE symbol=$1 AND interval='1min' AND ts >= $3 AND ts < $4
),
fut2v AS (
  SELECT
    SUM(buy_vol_usd - sell_vol_usd) AS cvd_fut_2v,
    COUNT(*)::int AS minutes
  FROM futures_trades_agg
  WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
    AND ts >= $3 AND ts < $4
),
spot AS (
  SELECT
    -- Ausencia de filas = NULL. COALESCE(...,0) fabricaba una sesion spot neutral.
    SUM(buy_vol_usd - sell_vol_usd) AS cvd_spot,
    SUM(inst_buy_usd - inst_sell_usd) AS inst_delta,
    COUNT(*)::int AS minutes
  FROM spot_trades_agg
  WHERE symbol=$2 AND exchange='combined' AND venue_count=2 AND interval='1min'
    AND ts >= $3 AND ts < $4
),
oi AS (
  SELECT
    (array_agg(oi_open ORDER BY ts ASC))[1] AS oi_open,
    (array_agg(oi_close ORDER BY ts DESC))[1] AS oi_close,
    MAX(oi_high) AS oi_high,
    MIN(oi_low) AS oi_low,
    COUNT(*)::int AS samples
  FROM open_interest
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
),
liq AS (
  -- Feed de eventos: no hay COALESCE. Cero no se deduce de ausencia de eventos persistidos.
  SELECT SUM(long_liq) AS long_liq, SUM(short_liq) AS short_liq
  FROM liquidations
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
),
fr AS (
  SELECT AVG(fr_close) AS fr_avg, COUNT(*)::int AS samples
  FROM funding_rate
  WHERE symbol=$1 AND interval='5min' AND ts >= $3 AND ts < $4
)
SELECT fut.cvd_fut, fut.price_open, fut.price_close, fut.samples,
       fut.price_high, fut.price_low, fut.volume_usd, fut.tx_count,
       fut2v.cvd_fut_2v, fut2v.minutes AS fut_2v_minutes,
       spot.cvd_spot, spot.inst_delta, spot.minutes AS spot_2v_minutes,
       oi.oi_open, oi.oi_close, oi.oi_high, oi.oi_low, oi.samples AS oi_5m_samples,
       liq.long_liq, liq.short_liq,
       fr.fr_avg, fr.samples AS funding_5m_samples
FROM fut CROSS JOIN fut2v CROSS JOIN spot CROSS JOIN oi CROSS JOIN liq CROSS JOIN fr
"""


async def compute_session(
    conn: asyncpg.Connection,
    symbol: str,
    ws_symbol: str,
    session_date_value: date,
) -> bool:
    start, end = session_bounds(session_date_value)
    expected_minutes = _expected_session_samples(start, end, 60)
    expected_5m = _expected_session_samples(start, end, 300)
    liquidation_observation = await liquidation_history_observation(
        conn,
        symbol=symbol,
        required_start=start,
        required_end=end,
    )
    row = await conn.fetchrow(SESSION_QUERY, symbol, ws_symbol, start, end)
    if not row:
        return False

    futures_minutes = int(row["samples"] or 0)
    spot_minutes = int(row["spot_2v_minutes"] or 0)
    futures_2v_minutes = int(row["fut_2v_minutes"] or 0)
    oi_samples = int(row["oi_5m_samples"] or 0)
    funding_samples = int(row["funding_5m_samples"] or 0)

    complete_futures = _coverage_complete(futures_minutes, expected_minutes)
    complete_spot = _coverage_complete(spot_minutes, expected_minutes)
    complete_futures_2v = _coverage_complete(futures_2v_minutes, expected_minutes)
    complete_oi = _coverage_complete(oi_samples, expected_5m)
    complete_funding = _coverage_complete(funding_samples, expected_5m)
    complete_liquidations = liquidation_observation is not None

    # No se persiste una fila totalmente vacia. Una sesion parcial SI puede existir: cada
    # grupo de metricas viaja NULL si su propia fuente no alcanza cobertura.
    if (
        not any((futures_minutes, spot_minutes, futures_2v_minutes, oi_samples, funding_samples))
        and not complete_liquidations
    ):
        return False

    cvd_fut = row["cvd_fut"] if complete_futures else None
    price_open = row["price_open"] if complete_futures else None
    price_close = row["price_close"] if complete_futures else None
    price_high = row["price_high"] if complete_futures else None
    price_low = row["price_low"] if complete_futures else None
    volume_usd = row["volume_usd"] if complete_futures else None
    tx_count = int(row["tx_count"]) if complete_futures and row["tx_count"] is not None else None

    cvd_spot = row["cvd_spot"] if complete_spot else None
    inst_delta = row["inst_delta"] if complete_spot else None
    cvd_fut_2v = row["cvd_fut_2v"] if complete_futures_2v else None

    oi_open = row["oi_open"] if complete_oi else None
    oi_close = row["oi_close"] if complete_oi else None
    oi_high = row["oi_high"] if complete_oi else None
    oi_low = row["oi_low"] if complete_oi else None
    fr_avg = row["fr_avg"] if complete_funding else None
    long_liq = (row["long_liq"] or 0.0) if complete_liquidations else None
    short_liq = (row["short_liq"] or 0.0) if complete_liquidations else None
    liquidation_coverage_version = (
        LIQUIDATION_COVERAGE_VERSION if complete_liquidations else None
    )

    await conn.execute(
        """
        INSERT INTO daily_session_agg(
          session_date,symbol,cvd_spot_usd,cvd_fut_usd,inst_delta_usd,
          price_open,price_close,oi_open,oi_close,fr_avg,
          cvd_fut_2v_usd,cvd_fut_2v_minutes,
          volume_usd,price_high,price_low,long_liq_usd,short_liq_usd,
          oi_high,oi_low,tx_count,
          session_coverage_version,session_expected_minutes,futures_ohlcv_minutes,
          spot_2v_minutes,session_expected_5m_samples,oi_5m_samples,funding_5m_samples,
          liquidation_coverage_version,liquidation_observed_at,
          liquidation_source_start_at,liquidation_source_cutoff_at,created_at,updated_at
        ) VALUES(
          $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
          $21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,clock_timestamp(),clock_timestamp()
        )
        ON CONFLICT(symbol,session_date) DO UPDATE SET
          -- Si la fila previa es legacy/unverified, EXCLUDED (incluso NULL) manda. Solo una
          -- medicion PR20 ya verificada puede sobrevivir a una recarga posterior sin retencion.
          cvd_spot_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.cvd_spot_usd,daily_session_agg.cvd_spot_usd)
            ELSE EXCLUDED.cvd_spot_usd END,
          cvd_fut_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.cvd_fut_usd,daily_session_agg.cvd_fut_usd)
            ELSE EXCLUDED.cvd_fut_usd END,
          inst_delta_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.inst_delta_usd,daily_session_agg.inst_delta_usd)
            ELSE EXCLUDED.inst_delta_usd END,
          price_open=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.price_open,daily_session_agg.price_open)
            ELSE EXCLUDED.price_open END,
          price_close=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.price_close,daily_session_agg.price_close)
            ELSE EXCLUDED.price_close END,
          oi_open=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.oi_open,daily_session_agg.oi_open) ELSE EXCLUDED.oi_open END,
          oi_close=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.oi_close,daily_session_agg.oi_close) ELSE EXCLUDED.oi_close END,
          fr_avg=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.fr_avg,daily_session_agg.fr_avg) ELSE EXCLUDED.fr_avg END,
          cvd_fut_2v_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.cvd_fut_2v_usd,daily_session_agg.cvd_fut_2v_usd)
            ELSE EXCLUDED.cvd_fut_2v_usd END,
          volume_usd=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.volume_usd,daily_session_agg.volume_usd) ELSE EXCLUDED.volume_usd END,
          price_high=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.price_high,daily_session_agg.price_high) ELSE EXCLUDED.price_high END,
          price_low=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.price_low,daily_session_agg.price_low) ELSE EXCLUDED.price_low END,
          -- v2 never carries a legacy or stale event total without the current proof.
          long_liq_usd=EXCLUDED.long_liq_usd,
          short_liq_usd=EXCLUDED.short_liq_usd,
          oi_high=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.oi_high,daily_session_agg.oi_high) ELSE EXCLUDED.oi_high END,
          oi_low=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.oi_low,daily_session_agg.oi_low) ELSE EXCLUDED.oi_low END,
          tx_count=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN COALESCE(EXCLUDED.tx_count,daily_session_agg.tx_count) ELSE EXCLUDED.tx_count END,
          cvd_fut_2v_minutes=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN GREATEST(COALESCE(daily_session_agg.cvd_fut_2v_minutes,0),EXCLUDED.cvd_fut_2v_minutes)
            ELSE EXCLUDED.cvd_fut_2v_minutes END,
          session_coverage_version=EXCLUDED.session_coverage_version,
          session_expected_minutes=EXCLUDED.session_expected_minutes,
          futures_ohlcv_minutes=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN GREATEST(COALESCE(daily_session_agg.futures_ohlcv_minutes,0),EXCLUDED.futures_ohlcv_minutes)
            ELSE EXCLUDED.futures_ohlcv_minutes END,
          spot_2v_minutes=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN GREATEST(COALESCE(daily_session_agg.spot_2v_minutes,0),EXCLUDED.spot_2v_minutes)
            ELSE EXCLUDED.spot_2v_minutes END,
          session_expected_5m_samples=EXCLUDED.session_expected_5m_samples,
          oi_5m_samples=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN GREATEST(COALESCE(daily_session_agg.oi_5m_samples,0),EXCLUDED.oi_5m_samples)
            ELSE EXCLUDED.oi_5m_samples END,
          funding_5m_samples=CASE WHEN daily_session_agg.session_coverage_version IN (1,2)
            THEN GREATEST(COALESCE(daily_session_agg.funding_5m_samples,0),EXCLUDED.funding_5m_samples)
            ELSE EXCLUDED.funding_5m_samples END,
          liquidation_coverage_version=EXCLUDED.liquidation_coverage_version,
          liquidation_observed_at=EXCLUDED.liquidation_observed_at,
          liquidation_source_start_at=EXCLUDED.liquidation_source_start_at,
          liquidation_source_cutoff_at=EXCLUDED.liquidation_source_cutoff_at,
          updated_at=clock_timestamp()
        """,
        session_date_value, symbol, cvd_spot, cvd_fut, inst_delta,
        price_open, price_close, oi_open, oi_close, fr_avg,
        cvd_fut_2v, futures_2v_minutes, volume_usd, price_high, price_low,
        long_liq, short_liq, oi_high, oi_low, tx_count,
        SESSION_COVERAGE_VERSION, expected_minutes, futures_minutes, spot_minutes,
        expected_5m, oi_samples, funding_samples, liquidation_coverage_version,
        liquidation_observation.observed_at if liquidation_observation else None,
        liquidation_observation.source_start_at if liquidation_observation else None,
        liquidation_observation.source_cutoff_at if liquidation_observation else None,
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
), ordered AS (
  SELECT *,
         SUM(CASE WHEN cvd_spot_usd IS NULL THEN 1 ELSE 0 END)
           OVER (ORDER BY session_date) AS spot_gap_group
  FROM selected
)
SELECT session_date, cvd_spot_usd,
       CASE WHEN cvd_spot_usd IS NULL THEN NULL
            ELSE SUM(cvd_spot_usd) OVER (PARTITION BY spot_gap_group ORDER BY session_date)
       END AS cumulative_spot
FROM ordered ORDER BY session_date
"""


async def persist_verdicts(conn: asyncpg.Connection, symbols: tuple[str, ...]) -> int:
    """Persist the latest verdict and the first forward-only observed snapshot.

    ``daily_verdict`` remains the mutable operational projection. PR21 additionally records
    one immutable ``daily_verdict_snapshot`` per session, without reconstructing legacy rows.
    """
    session_date_value = latest_closed_session_date()
    stored = 0
    for symbol in symbols:
        session = await conn.fetchrow(
            """
            SELECT price_close,session_coverage_version
            FROM daily_session_agg
            WHERE symbol=$1 AND session_date=$2
            """,
            symbol,
            session_date_value,
        )
        if session is None or session["price_close"] is None:
            continue  # sin cierre medido no existe un veredicto diario evaluable
        swing = await swing_score(conn, symbol)
        snapshot = await conn.fetchrow(
            """
            SELECT * FROM metrics_snapshot
            WHERE symbol=$1 AND regime_logic_version=$2
            ORDER BY ts DESC
            LIMIT 1
            """,
            symbol,
            REGIME_LOGIC_VERSION,
        )
        primary: dict[str, object] = {}
        streak = None
        if snapshot is not None:
            daily_rows = [dict(r) for r in await conn.fetch(DAILY_ROWS_QUERY, symbol)]
            setups = evaluate_setups(dict(snapshot), daily_rows)
            primary = setups.get("primary") or {}
            streak = setups.get("daily_streak")

        swing_bias = (
            swing.get("bias")
            if swing.get("bias") in ("LONG", "SHORT", "NEUTRAL")
            else None
        )
        swing_conviction = (
            swing.get("conviction")
            if swing.get("conviction") in ("baja", "media", "alta")
            else None
        )
        swing_components = json.dumps(
            swing.get("components") or [], ensure_ascii=False
        )
        regime_score = snapshot["regime_score"] if snapshot is not None else None
        regime_label = snapshot["regime_label"] if snapshot is not None else None
        metrics_snapshot_ts = snapshot["ts"] if snapshot is not None else None
        regime_logic_version = (
            snapshot["regime_logic_version"] if snapshot is not None else None
        )

        observed_at = await conn.fetchval("SELECT clock_timestamp()")
        _, session_end_at = session_bounds(session_date_value)
        reference = await conn.fetchrow(
            """
            SELECT
                ts + interval '1 minute' AS reference_price_at,
                close AS reference_price
            FROM ohlcv
            WHERE symbol=$1
              AND interval='1min'
              AND ts + interval '1 minute' <= $2
            ORDER BY ts DESC
            LIMIT 1
            """,
            symbol,
            observed_at,
        )
        reference_price = reference["reference_price"] if reference is not None else None
        reference_price_at = (
            reference["reference_price_at"] if reference is not None else None
        )

        await conn.execute(
            """
            INSERT INTO daily_verdict_snapshot(
              session_date,symbol,snapshot_version,logic_version,
              observed_at,session_end_at,metrics_snapshot_ts,regime_logic_version,
              session_coverage_version,
              swing_bias,swing_score,swing_conviction,long_share_pct,swing_components,
              regime_score,regime_label,setup_id,setup_name,setup_state,setup_confidence,
              daily_streak,session_price_close,reference_price,reference_price_at
            ) VALUES(
              $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,$15,$16,$17,$18,
              $19,$20,$21,$22,$23,$24
            )
            ON CONFLICT(symbol,session_date) DO NOTHING
            """,
            session_date_value,
            symbol,
            DAILY_VERDICT_SNAPSHOT_VERSION,
            DAILY_VERDICT_LOGIC_VERSION,
            observed_at,
            session_end_at,
            metrics_snapshot_ts,
            regime_logic_version,
            session["session_coverage_version"],
            swing_bias,
            swing.get("score"),
            swing_conviction,
            swing.get("long_share_pct"),
            swing_components,
            regime_score,
            regime_label,
            primary.get("id"),
            primary.get("name"),
            primary.get("state"),
            primary.get("confidence"),
            streak,
            session["price_close"],
            reference_price,
            reference_price_at,
        )

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
            swing_bias,
            swing.get("score"),
            swing_conviction,
            swing.get("long_share_pct"),
            swing_components,
            regime_score,
            regime_label,
            primary.get("id"),
            primary.get("name"),
            primary.get("state"),
            primary.get("confidence"),
            streak,
            session["price_close"],
        )
        stored += 1
    return stored


async def materialize_daily_verdict_outcomes(conn: asyncpg.Connection) -> int:
    """Record due v4 forward outcomes from one exact measured calendar target."""
    inserted = await conn.fetchval(
        """
        WITH due AS (
          SELECT
            verdict.snapshot_id,
            horizon.horizon_sessions,
            target.session_date AS target_session_date,
            target.price_close AS target_price_close,
            target.session_coverage_version AS target_session_coverage_version,
            target.updated_at AS source_projection_updated_at,
            (target.price_close / verdict.reference_price - 1) * 100 AS return_pct
          FROM daily_verdict_snapshot AS verdict
          CROSS JOIN unnest($3::integer[]) AS horizon(horizon_sessions)
          JOIN daily_session_agg AS target
            ON target.symbol=verdict.symbol
           AND target.session_date=verdict.session_date+horizon.horizon_sessions
          WHERE verdict.logic_version=$1
            AND verdict.reference_price IS NOT NULL
            AND target.session_coverage_version=2
            AND target.price_close IS NOT NULL
            AND target.updated_at IS NOT NULL
        ), stored AS (
          INSERT INTO daily_verdict_outcome(
            snapshot_id,outcome_version,horizon_sessions,target_session_date,
            target_price_close,target_session_coverage_version,
            source_projection_updated_at,return_pct,recorded_at
          )
          SELECT
            snapshot_id,$2,horizon_sessions,target_session_date,
            target_price_close,target_session_coverage_version,
            source_projection_updated_at,return_pct,clock_timestamp()
          FROM due
          ON CONFLICT(snapshot_id,outcome_version,horizon_sessions) DO NOTHING
          RETURNING 1
        )
        SELECT count(*)::int FROM stored
        """,
        DAILY_VERDICT_LOGIC_VERSION,
        DAILY_VERDICT_OUTCOME_VERSION,
        list(DAILY_VERDICT_OUTCOME_HORIZONS),
    )
    return int(inserted or 0)


# El dia de OI es UTC y no la sesion NYSE: el interes abierto no cierra a las 16:00 de
# Nueva York. 288 buckets de 5 min es el dia entero.
OI_DAILY_SOURCES: tuple[tuple[str, str], ...] = (
    ("open_interest", "coinalyze"),
    ("oi_bybit", "bybit"),
)
OI_DAILY_EXPECTED_SAMPLES = 288


async def rollup_open_interest_daily(conn: asyncpg.Connection) -> int:
    """Consolida en open_interest_daily cada dia UTC YA CERRADO que siga en los 5min.

    RECALCULA TODOS los dias vivos en cada pasada, y eso es deliberado por tres motivos
    que se pagan con una sola sentencia:
      · RELLENA HACIA ATRAS sin codigo aparte. El dia que esto se despliegue consolida de
        golpe todo lo que haya desde el 2026-07-23, que es justo lo que hay que salvar
        antes del 2026-10-21.
      · SE CURA SOLA. Si el rebarrido recupera 5min de un dia viejo, su resumen se rehace
        en la siguiente pasada en vez de quedarse con la version pobre.
      · ES IDEMPOTENTE por construccion, no por cuidado del llamante.
    El coste es un GROUP BY sobre lo que quepa en la retencion: con 90 dias son ~78 k filas
    y 540 de salida. Es mas barato que ohlcv 'daily', que ya se guarda para siempre.

    EL DIA EN CURSO NO SE ESCRIBE. Un dia abierto tiene un oi_close que todavia va a
    cambiar, y una fila que se reescribe sola no es un resumen: es una copia con retraso.
    """

    total = 0
    for tabla, fuente in OI_DAILY_SOURCES:
        # array_agg ORDER BY para open/close porque son el PRIMER y el ULTIMO bucket del
        # dia, no su minimo ni su maximo: min(oi_open) daria un numero que nunca existio.
        filas = await conn.execute(
            f"""
            INSERT INTO open_interest_daily(
              day,symbol,source,oi_open,oi_high,oi_low,oi_close,samples,expected_samples,built_at
            )
            SELECT
              (ts AT TIME ZONE 'UTC')::date,
              symbol,
              $1,
              (array_agg(oi_open ORDER BY ts ASC))[1],
              max(oi_high),
              min(oi_low),
              (array_agg(oi_close ORDER BY ts DESC))[1],
              count(*)::int,
              $2,
              now()
            FROM {tabla}
            WHERE interval='5min'
              AND (ts AT TIME ZONE 'UTC')::date < (now() AT TIME ZONE 'UTC')::date
            GROUP BY 1,2
            ON CONFLICT (symbol,source,day) DO UPDATE SET
              oi_open=EXCLUDED.oi_open, oi_high=EXCLUDED.oi_high,
              oi_low=EXCLUDED.oi_low, oi_close=EXCLUDED.oi_close,
              samples=EXCLUDED.samples, expected_samples=EXCLUDED.expected_samples,
              built_at=EXCLUDED.built_at
            """,  # noqa: S608 - {tabla} sale de OI_DAILY_SOURCES, nunca del exterior
            fuente,
            OI_DAILY_EXPECTED_SAMPLES,
        )
        total += int(filas.split()[-1])
    return total


def ventana_barrido_5m(ahora: datetime, hard_days: int) -> tuple[int, int]:
    """Ventana del barrido de 5min, en epoch. DEBE CONTENER lo que la purga va a borrar.

    Esta fuera de cycle() para que se pueda fijar en una prueba, porque el dia de mas es
    justo la clase de detalle que alguien simplifica de vuelta a hard_days sin ver que
    con eso el orden respecto a apply_retention deja de significar nada: lo que se va a
    borrar caeria fuera del barrido y colocarlo antes seria decorativo.
    """
    return (
        int((ahora - timedelta(days=hard_days + 1)).timestamp()),
        int(ahora.timestamp()),
    )


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
    await apply_temporal_retention(conn, "spot_trades_realtime", rt_hours)


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
    """Mide distribuciones usando exclusivamente buckets historicos ya cerrados."""
    total = 0
    as_of = datetime.now(UTC)
    for label, seconds, source in BASELINE_WINDOWS:
        source_seconds = 60 if source == "1min" else 14400
        expected = max(seconds // source_seconds, 1)
        for metric, expression in BASELINE_METRICS.items():
            total += await _store_baseline(
                conn, symbols, label, seconds, source, expected, metric, expression, as_of
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
    as_of: datetime,
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
            -- Filtra la vela fuente abierta. Es decisivo para 4h, donde parts=1 podia hacer
            -- pasar la vela en curso como una muestra historica completa.
            AND ts + CASE WHEN $3='4hour' THEN interval '4 hours' ELSE interval '1 minute' END <= $5
          GROUP BY 1,2
        ), r AS (
          SELECT symbol, ({expression}) AS ratio, bucket
          FROM b
          WHERE volume > 0 AND parts = $4::int
            -- Para 8h/1d construidos con 4h, tambien exige que el TARGET haya cerrado.
            AND bucket + make_interval(secs => $2::int) <= $5
        ), agg AS (
          SELECT symbol, count(*)::int AS n,
                 percentile_cont(0.50) WITHIN GROUP (ORDER BY ratio) AS p50,
                 percentile_cont(0.75) WITHIN GROUP (ORDER BY ratio) AS p75,
                 percentile_cont(0.90) WITHIN GROUP (ORDER BY ratio) AS p90,
                 percentile_cont(0.95) WITHIN GROUP (ORDER BY ratio) AS p95,
                 min(bucket) AS lo, max(bucket) AS hi
          FROM r WHERE ratio IS NOT NULL GROUP BY symbol
        )
        SELECT agg.*,
               (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(r.ratio-agg.p50))
                FROM r WHERE r.symbol=agg.symbol AND r.ratio IS NOT NULL) AS mad
        FROM agg
        """,
        list(symbols), seconds, source, expected, as_of,
    )
    for row in rows:
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


async def cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    ownership: ServiceOwnership | None = None,
) -> None:
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
        async with fenced_transaction(conn, ownership):
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
            outcomes = await materialize_daily_verdict_outcomes(conn)
            baselines = await refresh_baselines(conn, settings.SYMBOLS)
            # ANTES DE apply_retention Y NO DESPUES, y el orden es el arreglo entero: el dia
            # que acaba de cruzar HARD_DATA_RETENTION_DAYS se borra en esta misma pasada. Si
            # el resumen fuera despues, ese dia se perderia sin haberse consolidado jamas --
            # y en silencio, porque la serie solo empezaria un dia mas tarde.
            oi_daily = await rollup_open_interest_daily(conn)
            # EL 5min NO SE CURA SOLO, y esto se midio: el ciclo del ingest solo resume
            # su propia ventana de peticion -40 minutos-, asi que un 1min que llegue mas
            # tarde por recuperacion nunca produce su vela de 5. La noche del 2026-08-29
            # se recuperaron 4464 buckets de 1min del apagon y el 5min siguio con 1440
            # huecos, 894 de ellos con sus CINCO minutos ya guardados. El barrido mira
            # todo lo que el 1min alcanza y no lo que trajo una respuesta: es la leccion
            # de K66, y reusar la funcion viva en vez de escribir otra es la de K67.
            # VA ANTES DE apply_retention Y LA VENTANA LLEVA UN DIA DE MAS, y las dos
            # cosas son la misma decision: el 1min se borra a los
            # HARD_DATA_RETENTION_DAYS (90) y el 5min aguanta HTF (400), asi que detras
            # del DELETE ya no queda con que construir la vela y el hueco se fija en la
            # serie de 5min durante los 400 dias siguientes.
            # EL +1 ES LO QUE HACE QUE EL ORDEN IMPORTE. Con la ventana clavada en 90 lo
            # que la purga esta a punto de borrar ya cae FUERA del barrido, y colocarlo
            # antes no protegeria de nada: seria una precaucion decorativa. Con un dia de
            # margen, los minutos que cruzaron los 90 se consolidan en esta misma pasada
            # y se borran despues. Importa cuando el servicio ha estado parado y vuelve
            # con dias acumulados, que es justo cuando nadie esta mirando.
            # only_missing: lo cerrado no cambia, y reescribirlo cada hora solo produce
            # tuplas muertas contra un thin pool que no tiene margen.
            inicio_5m, fin_5m = ventana_barrido_5m(
                datetime.now(UTC), settings.HARD_DATA_RETENTION_DAYS
            )
            rolled_5m = await rollup_ohlcv_5m(
                conn, settings.SYMBOLS, inicio_5m, fin_5m, only_missing=True
            )
            # EL BARRIDO ANCHO DE CADENCIA, y va JUSTO DESPUES DEL ROLLUP a proposito:
            # al reves apuntaria como hueco de 5min lo que el rollup estaba a punto de
            # construir con minutos que ya tenemos, o sea filas de data_gap que nacen
            # resueltas. El orden respecto a apply_retention, en cambio, NO es
            # load-bearing: la ventana se topa explicitamente en
            # HARD_DATA_RETENTION_DAYS, luego lo que la purga va a borrar cae fuera de
            # todos modos. Se dice porque las dos vecindades se leen igual y solo una
            # importa.
            barrido = await barrido_cadencia_persistido(
                conn,
                settings.SYMBOLS,
                hard_days=settings.HARD_DATA_RETENTION_DAYS,
                ahora=datetime.now(UTC),
            )
            await apply_retention(
                conn,
                settings.HARD_DATA_RETENTION_DAYS,
                settings.HTF_DATA_RETENTION_DAYS,
                settings.SNAPSHOT_RETENTION_DAYS,
                settings.REALTIME_RETENTION_HOURS,
                settings.DAILY_SESSION_RETENTION_DAYS,
            )
        heartbeat_detail = (
            f"daily_candles={daily_candles},h4_candles={h4_candles},"
            f"spot_candles={spot_candles},baselines={baselines},"
            f"daily_rows={inserted},verdicts={verdicts},outcomes={outcomes},"
            f"oi_daily={oi_daily},rolled_5m={rolled_5m},"
            f"cadencia_declarada={barrido['ventanas']},"
            f"cadencia_omitida={barrido['omitidas']},"
            f"cadencia_recuperada={barrido['recuperadas']}"
        )
        if ownership is None:
            await heartbeat(conn, "daily", detail=heartbeat_detail)
        else:
            await heartbeat_owned(conn, ownership, "daily", detail=heartbeat_detail)
    LOGGER.info(
        "daily_cycle_complete daily_candles=%d h4_candles=%d inserted=%d "
        "verdicts=%d outcomes=%d",
        daily_candles,
        h4_candles,
        inserted,
        verdicts,
        outcomes,
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
    pool = await create_pool(
        settings,
        application_name="coinalyze-daily",
        ownership=service_lock,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    lock_monitor = asyncio.create_task(
        monitor_service_lock(service_lock, "daily"),
        name="service-lock",
    )
    try:
        limiter = PostgresSlidingWindowRateLimiter(
            pool, settings.COINALYZE_RATE_LIMIT_UNITS, ownership=service_lock
        )
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
                cycle_task = asyncio.create_task(cycle(pool, client, service_lock))
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
                except ServiceOwnershipLost:
                    raise
                except Exception as exc:
                    LOGGER.exception("daily_cycle_failed")
                    try:
                        async with pool.acquire() as conn:
                            await heartbeat_owned(
                                conn,
                                service_lock,
                                "daily",
                                status="error",
                                detail=str(exc)[:500],
                            )
                    except ServiceOwnershipLost:
                        raise
                    except Exception:
                        LOGGER.exception("daily_heartbeat_failed")
    finally:
        lock_monitor.cancel()
        await asyncio.gather(lock_monitor, return_exceptions=True)
        await pool.close()
        await service_lock.close()


if __name__ == "__main__":
    asyncio.run(run())
