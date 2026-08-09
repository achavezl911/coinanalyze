from __future__ import annotations

import math
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from app.config import WHALE_THRESHOLD_MAP, WS_SYMBOL_MAP
from app.cutoffs import ClosedCutoff

NY = ZoneInfo("America/New_York")
WHALE_ACTIVITY_MIN = WHALE_THRESHOLD_MAP


def current_nyse_start(now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(UTC)
    now_et = now_utc.astimezone(NY)
    candidate = datetime.combine(now_et.date(), time(9, 30), tzinfo=NY)
    if candidate > now_et:
        candidate -= timedelta(days=1)
    # Crypto opera 24/7 y daily_session_agg conserva una fila por dia natural. Saltar
    # sabado/domingo hacia el viernes convertia la "sesion" del fin de semana en 48-72 h.
    return candidate.astimezone(UTC)


def session_bounds(session_date: date) -> tuple[datetime, datetime]:
    end_et = datetime.combine(session_date, time(9, 30), tzinfo=NY)
    start_et = datetime.combine(session_date - timedelta(days=1), time(9, 30), tzinfo=NY)
    return start_et.astimezone(UTC), end_et.astimezone(UTC)


def _safe(value: object, default: float = 0.0) -> float:
    """Convierte a float con un default. SOLO donde ese default es legitimo.

    No usar para publicar una metrica: `default=0.0` sobre un dato ausente fabrica un cero
    medido. Para publicar esta `optional_finite()`, que conserva la ausencia.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def optional_finite(value: object) -> float | None:
    """float finito o None. La ausencia se propaga; nunca se convierte en cero.

    Un 0.0 inventado se lee como "medimos y salio cero", que es una afirmacion distinta de
    "no hay dato". Afectaba a CVD, funding, liquidaciones, flujo institucional y al regimen,
    que se publicaba como "Lateral / Indecision" sin una sola observacion detras.
    """
    if value is None:
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def whale_classification(inst_buy: float, inst_sell: float, asset: str) -> tuple[float, str]:
    total = inst_buy + inst_sell
    if total < WHALE_ACTIVITY_MIN[asset]:
        # El tamano de una orden NO identifica a quien la manda: se habla de operaciones
        # grandes, que es lo unico que el feed permite afirmar.
        return 0.0, "Sin operaciones spot de gran tamaño relevantes"
    delta = inst_buy - inst_sell
    ratio = abs(delta) / total if total else 0.0
    intensity = math.copysign(ratio, delta) if delta else 0.0
    if ratio > 0.6:
        return intensity, "Acumulación agresiva" if delta > 0 else "Distribución agresiva"
    if ratio > 0.3:
        return intensity, "Acumulando" if delta > 0 else "Distribuyendo"
    return intensity, "Neutro"


REGIME_WEIGHTS = {"cvd": 25.0, "oi": 15.0, "funding": 15.0, "liquidations": 15.0, "whale": 30.0}
REGIME_MIN_COVERAGE = 0.5
"""Fraccion minima del peso que debe estar medida para publicar un regimen.

Por debajo de esto el score seria la opinion de uno o dos componentes presentada como si
fuese el balance completo. Antes se sumaba 0 por cada componente ausente, asi que
`compute_regime({})` devolvia (0.0, 'Lateral / Indecision'): un veredicto neutral que
parecia medido y no lo estaba.
"""


def compute_regime(
    snap: dict[str, float | str | int | None],
) -> tuple[float | None, str]:
    """Balance de evidencia del regimen, renormalizado sobre los componentes MEDIBLES.

    Devuelve `(None, 'Sin datos suficientes')` cuando no hay peso medido bastante. Es la
    misma regla que ya se aplicaba al swing score y a las barreras desde v1.3.8.
    """
    components: dict[str, float] = {}

    vol_24h = optional_finite(snap.get("vol_24h"))
    cvd_diff = optional_finite(snap.get("cvd_diff_24h"))
    if cvd_diff is not None and vol_24h is not None and vol_24h > 0:
        components["cvd"] = max(-1.0, min(1.0, cvd_diff / (vol_24h * 0.10)))

    oi_chg = optional_finite(snap.get("oi_chg_24h_pct"))
    if oi_chg is not None:
        components["oi"] = max(-1.0, min(1.0, oi_chg / 5.0))

    # Coinalyze entrega funding en puntos porcentuales: 0.01 equivale a 0.01%,
    # no a una fraccion 0.01. Una tasa de 0.10% satura este componente.
    fr_avg = optional_finite(snap.get("fr_avg"))
    if fr_avg is not None:
        components["funding"] = max(-1.0, min(1.0, -fr_avg * 10.0))

    long_liq = optional_finite(snap.get("long_liq_24h"))
    short_liq = optional_finite(snap.get("short_liq_24h"))
    if long_liq is not None and short_liq is not None:
        liq_total = long_liq + short_liq
        # total 0 con ambas patas MEDIDAS si es una observacion: nadie fue liquidado.
        components["liquidations"] = (
            max(-1.0, min(1.0, (short_liq - long_liq) / liq_total)) if liq_total > 0 else 0.0
        )

    whale = optional_finite(snap.get("whale_intensity"))
    if whale is not None:
        components["whale"] = max(-1.0, min(1.0, whale))

    measured = sum(REGIME_WEIGHTS[name] for name in components)
    total = sum(REGIME_WEIGHTS.values())
    if measured < total * REGIME_MIN_COVERAGE:
        return None, "Sin datos suficientes"

    # Renormalizar sobre lo medido: un componente ausente no vota cero, no vota.
    raw = sum(value * REGIME_WEIGHTS[name] for name, value in components.items())
    score = round(max(-100.0, min(100.0, raw * total / measured)), 2)
    label = str(snap.get("whale_label") or "Neutro")
    diff = cvd_diff if cvd_diff is not None else 0.0

    if score > 60 and "Acumulación agresiva" in label and diff > 0:
        regime = "Continuación alcista orgánica"
    elif score > 40 and "Distribu" in label:
        regime = "Euforia / Sobreextensión bullish"
    elif score > 20 and diff <= 0 and "Acumul" not in label:
        regime = "Squeeze inminente bullish"
    elif score < -60 and "Distribución agresiva" in label:
        regime = "Capitulación (Bearish)"
    elif score < -30 and "Distribu" in label:
        regime = "Distribución (Bearish)"
    elif score < -20 and diff > 0:
        regime = "Absorción de compras (Bearish)"
    elif abs(score) < 15 and "Acumul" in label:
        regime = "Compresión / Acumulación silenciosa"
    else:
        regime = "Lateral / Indecisión"
    return score, regime


SNAPSHOT_QUERY = """
WITH
fut AS (
    SELECT
      (array_agg(close ORDER BY ts DESC))[1] AS price,
      (array_agg(ts ORDER BY ts DESC))[1] AS price_ts,
      -- Explicit cast on the first use of $4/$5: PostgreSQL's parameter-type inference
      -- resolves each parameter number once for the whole statement, but if the first
      -- usage it encounters is `$N - interval` it can infer $N itself as `interval`
      -- (interval - interval = interval), which then fails everywhere else $N is
      -- compared to a timestamptz column. The cast fixes inference without changing
      -- the value bound at execution time (still the caller's timestamptz).
      SUM(volume * close) FILTER (WHERE ts >= $4::timestamptz - interval '24 hours') AS vol_24h,
      SUM(delta * close) FILTER (WHERE ts >= $4 - interval '24 hours') AS cvd_24h,
      SUM(delta * close) FILTER (WHERE ts >= $3) AS cvd_session,
      SUM(delta * close) FILTER (WHERE ts >= $4 - interval '3 minutes') AS delta_3min,
      (SUM(btx) FILTER (WHERE ts >= $4 - interval '15 minutes'))::double precision /
        NULLIF(SUM(tx) FILTER (WHERE ts >= $4 - interval '15 minutes'), 0) AS btr_15m,
      (SUM(btx) FILTER (WHERE ts >= $4 - interval '1 hour'))::double precision /
        NULLIF(SUM(tx) FILTER (WHERE ts >= $4 - interval '1 hour'), 0) AS btr_1h,
      (SUM(btx) FILTER (WHERE ts >= $4 - interval '24 hours'))::double precision /
        NULLIF(SUM(tx) FILTER (WHERE ts >= $4 - interval '24 hours'), 0) AS btr_24h
    FROM ohlcv
    WHERE symbol = $1 AND interval = '1min'
      AND ts >= $4 - interval '25 hours' AND ts < $4
),
price_1h AS (
    SELECT close AS value FROM ohlcv
    WHERE symbol = $1 AND interval = '1min' AND ts <= $4 - interval '1 hour'
    ORDER BY ts DESC LIMIT 1
),
spot AS (
    SELECT
      SUM(buy_vol_usd - sell_vol_usd) FILTER (WHERE ts >= $4 - interval '24 hours') AS cvd_24h,
      SUM(buy_vol_usd - sell_vol_usd) FILTER (WHERE ts >= $3) AS cvd_session,
      SUM(inst_buy_usd) FILTER (WHERE ts >= $4 - interval '24 hours') AS inst_buy,
      SUM(inst_sell_usd) FILTER (WHERE ts >= $4 - interval '24 hours') AS inst_sell
    FROM spot_trades_agg
    WHERE symbol = $2 AND exchange = 'combined' AND interval = '1min'
      AND ts >= $4 - interval '25 hours' AND ts < $4
),
oi_now AS (
    SELECT oi_close AS value, ts FROM open_interest
    WHERE symbol = $1 AND interval = '5min' AND ts < $5::timestamptz ORDER BY ts DESC LIMIT 1
),
oi_old AS (
    SELECT oi_close AS value FROM open_interest
    WHERE symbol = $1 AND interval = '5min' AND ts < $5 - interval '24 hours'
    ORDER BY ts DESC LIMIT 1
),
oi_b AS (
    SELECT oi_close AS value FROM oi_bybit
    WHERE symbol = $1 AND interval = '5min' AND ts < $5 ORDER BY ts DESC LIMIT 1
),
fund AS (
    SELECT AVG(fr_close) AS value FROM funding_rate
    WHERE symbol = $1 AND interval = '5min'
      AND ts >= $5 - interval '24 hours' AND ts < $5
),
pfund AS (
    SELECT AVG(pfr_close) AS value FROM predicted_funding_rate
    WHERE symbol = $1 AND interval = '5min'
      AND ts >= $5 - interval '24 hours' AND ts < $5
),
liq AS (
    SELECT SUM(long_liq) AS long_value, SUM(short_liq) AS short_value
    FROM liquidations
    WHERE symbol = $1 AND interval = '5min'
      AND ts >= $5 - interval '24 hours' AND ts < $5
)
SELECT
  fut.price, fut.price_ts, fut.vol_24h, fut.cvd_24h, fut.cvd_session, fut.delta_3min,
  fut.btr_15m, fut.btr_1h, fut.btr_24h,
  price_1h.value AS price_1h,
  spot.cvd_24h AS spot_cvd_24h, spot.cvd_session AS spot_cvd_session,
  spot.inst_buy, spot.inst_sell,
  oi_now.value AS oi_now, oi_now.ts AS oi_ts, oi_old.value AS oi_old,
  oi_b.value AS oi_bybit,
  fund.value AS fr_avg, pfund.value AS pfr_avg,
  liq.long_value AS long_liq, liq.short_value AS short_liq
FROM fut
LEFT JOIN price_1h ON true
LEFT JOIN spot ON true
LEFT JOIN oi_now ON true
LEFT JOIN oi_old ON true
LEFT JOIN oi_b ON true
LEFT JOIN fund ON true
LEFT JOIN pfund ON true
LEFT JOIN liq ON true
"""


async def compute_snapshot(
    conn: asyncpg.Connection,
    symbol: str,
    ws_symbol: str,
    now_utc: datetime | None = None,
    *,
    price_cutoff: datetime | None = None,
    metrics_cutoff: datetime | None = None,
) -> dict[str, float | str | int | None]:
    now_utc = now_utc or datetime.now(UTC)
    session_start = current_nyse_start(now_utc)
    price_cutoff = price_cutoff or ClosedCutoff.at(now_utc, 60).exclusive_boundary
    metrics_cutoff = metrics_cutoff or ClosedCutoff.at(now_utc, 300).exclusive_boundary
    row = await conn.fetchrow(
        SNAPSHOT_QUERY,
        symbol,
        ws_symbol,
        session_start,
        price_cutoff,
        metrics_cutoff,
    )
    data = dict(row) if row else {}

    price = optional_finite(data.get("price"))
    price_1h = optional_finite(data.get("price_1h"))
    price_dir = 0
    if price and price_1h:
        change = (price - price_1h) / price_1h
        price_dir = 1 if change > 0.002 else -1 if change < -0.002 else 0

    oi_now = optional_finite(data.get("oi_now"))
    oi_old = optional_finite(data.get("oi_old"))
    oi_chg = ((oi_now - oi_old) / oi_old * 100.0) if oi_now and oi_old else None
    vol_24h = optional_finite(data.get("vol_24h"))
    oi_vol_ratio = (oi_now / vol_24h) if oi_now and vol_24h else None

    # Cada pata conserva su ausencia: un CVD que no se pudo medir no es un CVD de cero.
    fut_24h = optional_finite(data.get("cvd_24h"))
    fut_session = optional_finite(data.get("cvd_session"))
    spot_24h = optional_finite(data.get("spot_cvd_24h"))
    spot_session = optional_finite(data.get("spot_cvd_session"))
    inst_buy = optional_finite(data.get("inst_buy"))
    inst_sell = optional_finite(data.get("inst_sell"))
    if inst_buy is None or inst_sell is None:
        whale_intensity, whale_label = None, "Sin datos"
    else:
        whale_intensity, whale_label = whale_classification(inst_buy, inst_sell, ws_symbol)

    long_liq = optional_finite(data.get("long_liq"))
    short_liq = optional_finite(data.get("short_liq"))
    if long_liq is None or short_liq is None:
        liq_ratio = None
    elif short_liq > 0:
        liq_ratio = min(long_liq / short_liq, 1000.0)
    else:
        liq_ratio = 10.0 if long_liq > 0 else 1.0
    fr_avg = optional_finite(data.get("fr_avg"))
    pfr_avg = optional_finite(data.get("pfr_avg"))

    snap: dict[str, float | str | int | None] = {
        "symbol": symbol,
        "price": price,
        "oi": oi_now,
        "oi_chg_24h_pct": oi_chg,
        "oi_vol_24h_ratio": oi_vol_ratio,
        "vol_24h": vol_24h,
        "delta_3min": optional_finite(data.get("delta_3min")),
        # Compatibility names: cvd_session is 24h; cvd_nyse_session is current NYSE session.
        "cvd_session": fut_24h,
        "cvd_nyse_session": fut_session,
        "cvd_spot_24h": spot_24h,
        "cvd_spot_session": spot_session,
        "oi_bybit": optional_finite(data.get("oi_bybit")),
        "liq_ratio_24h": liq_ratio,
        # Un diferencial exige AMBAS patas: restar contra una ausencia publicaria la pata
        # presente con el signo cambiado y la llamaria "diferencial".
        "cvd_diff_24h": (spot_24h - fut_24h) if None not in (spot_24h, fut_24h) else None,
        "cvd_diff_ses": (
            (spot_session - fut_session) if None not in (spot_session, fut_session) else None
        ),
        "fr_avg": fr_avg,
        "pfr_avg": pfr_avg,
        "long_liq_24h": long_liq,
        "short_liq_24h": short_liq,
        "whale_intensity": whale_intensity,
        "whale_label": whale_label,
        "price_dir_1h": price_dir,
        "btr_15m": data.get("btr_15m"),
        "btr_1h": data.get("btr_1h"),
        "btr_24h": data.get("btr_24h"),
        "pfr_fr_div": (pfr_avg - fr_avg) if None not in (pfr_avg, fr_avg) else None,
        "price_cutoff_at": data.get("price_ts"),
        "metrics_cutoff_at": data.get("oi_ts"),
    }
    score, label = compute_regime(snap)
    snap["regime_score"] = score
    snap["regime_label"] = label
    return snap


async def insert_snapshot(conn: asyncpg.Connection, snap: dict[str, object]) -> None:
    # clock_timestamp() is read when the statement executes, not when the transaction
    # began (now()/CURRENT_TIMESTAMP are frozen at BEGIN). Combined with the exclusive
    # advisory lock in publish_snapshot(), this keeps `ts` ordering equal to real
    # publication order across both the OHLCV and metrics cycles.
    await conn.execute(
        """
        INSERT INTO metrics_snapshot(
          ts, symbol, price, oi, oi_chg_24h_pct, oi_vol_24h_ratio, vol_24h,
          delta_3min, cvd_session, cvd_nyse_session, cvd_spot_24h,
          cvd_spot_session, oi_bybit, liq_ratio_24h, cvd_diff_24h,
          cvd_diff_ses, fr_avg, pfr_avg, long_liq_24h, short_liq_24h,
          whale_intensity, whale_label, regime_score, regime_label, price_dir_1h,
          btr_15m, btr_1h, btr_24h, pfr_fr_div, price_cutoff_at,
          metrics_cutoff_at
        ) VALUES (
          clock_timestamp(), $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,
          $18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30
        )
        """,
        snap["symbol"], snap["price"], snap["oi"], snap["oi_chg_24h_pct"],
        snap["oi_vol_24h_ratio"], snap["vol_24h"], snap["delta_3min"],
        snap["cvd_session"], snap["cvd_nyse_session"], snap["cvd_spot_24h"],
        snap["cvd_spot_session"], snap["oi_bybit"], snap["liq_ratio_24h"],
        snap["cvd_diff_24h"], snap["cvd_diff_ses"], snap["fr_avg"], snap["pfr_avg"],
        snap["long_liq_24h"], snap["short_liq_24h"], snap["whale_intensity"],
        snap["whale_label"], snap["regime_score"], snap["regime_label"],
        snap["price_dir_1h"], snap["btr_15m"], snap["btr_1h"], snap["btr_24h"],
        snap["pfr_fr_div"], snap["price_cutoff_at"], snap["metrics_cutoff_at"],
    )


async def compute_and_store_all(
    conn: asyncpg.Connection,
    symbols: tuple[str, ...],
    *,
    now_utc: datetime | None = None,
    price_cutoff: datetime | None = None,
    metrics_cutoff: datetime | None = None,
) -> None:
    for symbol in symbols:
        snap = await compute_snapshot(
            conn,
            symbol,
            WS_SYMBOL_MAP[symbol],
            now_utc,
            price_cutoff=price_cutoff,
            metrics_cutoff=metrics_cutoff,
        )
        await insert_snapshot(conn, snap)
