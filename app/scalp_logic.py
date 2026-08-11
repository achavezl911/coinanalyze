from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any

import asyncpg

from app.breakout import breakout_read
from app.config import SPOT_HISTORY_MAP, WS_SYMBOL_MAP
from app.data_gaps import GapRequirement, blocking_requirement_keys
from app.interpretation import (
    BARRIER_INTRADAY_TARGET_BARS,
    MARKET_MEMORY_DAYS,
    market_memory_read,
    price_barrier_read,
)
from app.metrics import current_nyse_start
from app.setups import (
    DIRECTIONS,
    LEGACY_HYPOTHESES,
    SETUP_LABELS,
    SETUP_SPECS,
    classify_oi,
    evaluate_setup,
    oi_price_reading,
    split_hypothesis,
)
from app.wyckoff import wyckoff_auto_read
from app.zones import VISIT_GAP_DAYS, range_validate_read, zone_character_read

ABSORPTION_FLAT_PCT = 0.04
"""|%| maximo de movimiento que cuenta como "el precio no se movio"."""

ABSORPTION_MIN_RATIO = 0.10
"""FALLBACK de |delta|/volumen cuando no hay baseline medida para (simbolo, ventana).

Sirve solo para no quedarse sin puerta; NO es un umbral defendible por si mismo. Medido el
2026-08-06 sobre 20 021 velas de 1 min, |delta|/volumen tiene p50 = 0.34 a 1 m y 0.045 a 4 h,
asi que este 0.10 dejaba pasar el 78 % de las ventanas de 3 m y habria rechazado el 87 % de
las de 4 h. El umbral real sale de `metric_baseline` (percentil p75 por simbolo y ventana) y
esta constante queda como red de seguridad, siempre etiquetada como tal en la respuesta.
"""

OI_SCORE_FULL_PCT = 0.5
"""|Δ%| de OI 15m que satura la contribucion direccional del OI al score.

Solo escala la MAGNITUD del voto cuando el OI ya aporta direccion (expansion coherente con
precio y flujo). No decide la direccion: eso lo hace `oi_price_reading()` en app/positioning
(hoy en app/setups). Un mismo umbral que el viejo `oi_chg_15m_pct / 0.5`, pero ahora el signo
lo pone el cuadrante precio+OI, no el signo de ΔOI.
"""

OI_15M_EXPECTED_BARS = 15
"""Velas de 1 min esperadas en la ventana de 15 m; base de la cobertura de price_move_15m."""

OI_15M_EXPECTED_SAMPLES = 4
"""Observaciones OI 5m necesarias para medir dos cierres separados exactamente 15m."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _closed_1m_window_bounds(
    now: datetime | None = None,
    minutes: int = 15,
) -> tuple[datetime, datetime]:
    """Ventana exacta formada exclusivamente por velas 1m ya cerradas.

    Ejemplo:
        now = 11:49:37
        start = 11:34:00
        end   = 11:49:00

    La vela 11:49:00-11:49:59 NO entra porque sigue abierta.
    """
    ref = now or datetime.now(UTC)
    ref = ref.replace(tzinfo=UTC) if ref.tzinfo is None else ref.astimezone(UTC)

    end = ref.replace(second=0, microsecond=0)
    start = end - timedelta(minutes=minutes)

    return start, end


def _closed_5m_oi_bounds(
    now: datetime | None = None,
) -> tuple[datetime, datetime, datetime]:
    """Límites para cuatro buckets OI 5m cerrados y su intervalo efectivo.

    Coinalyze etiqueta los buckets OHLC con su inicio. A las 11:49:37, los cuatro
    buckets OI cerrados empiezan 11:25, 11:30, 11:35 y 11:40; sus cierres efectivos
    comparables son 11:30 y 11:45. El precio usa por ello [11:30, 11:45).
    """
    ref = now or _utc_now()
    ref = ref.replace(tzinfo=UTC) if ref.tzinfo is None else ref.astimezone(UTC)
    end = ref.replace(minute=(ref.minute // 5) * 5, second=0, microsecond=0)
    source_start = end - timedelta(minutes=20)
    effective_start = end - timedelta(minutes=15)
    return source_start, effective_start, end

COLLECTOR_THRESHOLDS: dict[str, tuple[int, int]] = {
    "ingest": (60, 300),
    "ws": (5, 60),
    "scalp": (10, 120),
    "daily": (600, 5400),
    "api": (60, 300),
}
"""(intervalo esperado, segundos tras los que el heartbeat se considera muerto) por servicio.

Fuente unica: la usa `data_quality()` para pintar salud y `compute_scalp_summary()` para
decidir si una ventana de liquidaciones se llego a MEDIR. Si los dos usaran umbrales
distintos, el panel podria decir "feed sano" mientras el resumen publica un cero fabricado.
"""

BASELINE_BANDS = (
    ("bajo", "p50"),
    ("normal", "p75"),
    ("elevado", "p90"),
    ("alto", "p95"),
)
"""Bandas por percentil. Se publica la BANDA, no un percentil interpolado: con cuatro
cuantiles guardados, dar 'percentil 83.7' seria precision inventada."""


def baseline_band(value: float | None, baseline: dict[str, Any] | None) -> dict[str, Any]:
    """Situa un valor en su distribucion historica: banda + z-score robusto.

    Robusto = (x - mediana) / (1.4826 * MAD), no (x - media) / sigma: la distribucion de
    |delta|/volumen tiene cola larga y un solo pico deforma media y sigma.
    """
    if value is None or not baseline or not baseline.get("sample_count"):
        return {"band": None, "robust_z": None, "status": "sin_baseline"}
    band = "extremo"
    for name, key in BASELINE_BANDS:
        if value < baseline[key]:
            band = name
            break
    mad = baseline.get("mad") or 0.0
    scale = 1.4826 * mad
    return {
        "band": band,
        "robust_z": round((value - baseline["p50"]) / scale, 2) if scale > 0 else None,
        "status": "ok",
        "sample_count": baseline["sample_count"],
        "reference": {key: round(baseline[key], 4) for _, key in BASELINE_BANDS},
    }


async def load_baselines(
    conn: asyncpg.Connection, symbol: str, metric: str = "delta_ratio"
) -> dict[str, dict[str, Any]]:
    """Baselines medidas por ventana. Devuelve {} si el job diario aun no las ha calculado."""
    rows = await conn.fetch(
        "SELECT window_label,window_seconds,source_interval,sample_count,p50,p75,p90,p95,mad,"
        "sample_start,sample_end FROM metric_baseline WHERE symbol=$1 AND metric=$2",
        symbol,
        metric,
    )
    return {str(row["window_label"]): dict(row) for row in rows}

CLOCK_TOLERANCE_SECONDS = 0.5
"""Margen para desajustes menores de reloj entre el exchange y este host.

Medido: la edad de ambas patas ronda 5-9 s POSITIVOS, asi que un margen estrecho no
produce falsos positivos. No se acepta
como "muy fresco": una edad negativa nunca es una lectura valida.
"""

REALTIME_STALE_SECONDS = 30.0
"""Edad maxima de un evento realtime antes de considerarlo no utilizable.

Medido el 2026-08-06 sobre 2 h y los 6 feeds (fut/spot x BTC/ETH/SOL): el hueco entre
buckets de 5 s tiene p99 de 5-10 s y maximo 20 s, y la edad del ultimo evento ronda 8-9 s.
Nada en operacion normal pasa de 30 s, asi que cruzarlo es caida del collector, no calma.
"""


def classify_absorption(
    delta: float | None,
    price_move_pct: float | None,
    volume: float | None = None,
    min_ratio: float | None = None,
) -> tuple[float, str]:
    """Clasifica absorcion desde el delta agresivo y el movimiento de precio.

    Fuente unica para /api/scalp/absorption y compute_scalp_summary. Antes cada uno
    tenia su propio umbral (0.02 vs 0.04) y el dashboard podia mostrar dos lecturas
    contradictorias del mismo simbolo. score>0 favorece long, score<0 favorece short.

    `volume` es el volumen total de la misma ventana que `delta`. Sin el la magnitud no
    se puede juzgar y la lectura se degrada a "Sin datos" en vez de fingir una senal.

    `min_ratio` debe venir de `metric_baseline` (p75 de ESA ventana y ESE simbolo). El ratio
    decae al alargar la ventana, asi que un umbral unico o pasa casi todo o no pasa nada:
    medido, 0.10 dejaba pasar el 78 % de las ventanas de 3 m y el 13 % de las de 4 h.
    # ponytail: la puerta es una ratio; ubicacion estructural y persistencia las cubre
    # passive_flow, que ya tiene POC/VAH/VAL y ATR. Aqui solo se corta el ruido.
    """
    if not delta:
        return 0.0, "Neutra"
    if not volume or volume <= 0:
        return 0.0, "Sin datos"
    threshold = ABSORPTION_MIN_RATIO if min_ratio is None else min_ratio
    if abs(delta) / volume < threshold:
        return 0.0, "Sin señal"
    move = price_move_pct or 0.0
    if abs(move) < ABSORPTION_FLAT_PCT:
        return (-1.0, "Absorción de compras") if delta > 0 else (1.0, "Absorción de ventas")
    if delta > 0 and move < 0:
        return -1.0, "Absorción fuerte de compras"
    if delta < 0 and move > 0:
        return 1.0, "Absorción fuerte de ventas"
    return 0.0, "Neutra"


def basis_quality(
    fut_px: float | None,
    spot_px: float | None,
    fut_event_ms: float | None,
    spot_event_ms: float | None,
    now_ms: float,
) -> dict[str, Any]:
    """Basis perp-spot con puerta de frescura: devuelve None cuando no se sostiene.

    El basis se calculaba con el ultimo precio negociado de cada pata y SIN mirar el
    reloj: si el feed de spot se caia, el dashboard seguia publicando un numero que en
    realidad era la deriva del perp contra un precio congelado.

    La puerta es la EDAD de cada pata, no el desfase entre ellas. Medido sobre 2 h de
    buckets emparejados, el skew fut-spot esta acotado por la propia rejilla de 5 s
    (p50 0.4-0.8 s, p99 3.4-4.3 s, maximo 4.8 s, ninguno por encima de 5 s): usarlo de
    umbral marcaria como sospechoso el 6-19 % de las muestras sanas sin distinguir nada.
    Lo que si rompe el basis es que una pata deje de actualizarse, y eso es edad.

    El skew se reporta porque es gratis, pero no invalida.
    """
    fut_age = (now_ms - fut_event_ms) / 1000.0 if fut_event_ms else None
    spot_age = (now_ms - spot_event_ms) / 1000.0 if spot_event_ms else None
    out: dict[str, Any] = {
        "basis_bps": None,
        "fut_price": fut_px,
        "spot_price": spot_px,
        "fut_age_seconds": round(fut_age, 2) if fut_age is not None else None,
        "spot_age_seconds": round(spot_age, 2) if spot_age is not None else None,
        "skew_ms": (
            round(abs(fut_event_ms - spot_event_ms))
            if fut_event_ms and spot_event_ms
            else None
        ),
        "stale_after_seconds": REALTIME_STALE_SECONDS,
    }
    if not fut_px or not spot_px or fut_age is None or spot_age is None:
        out["status"] = "UNAVAILABLE"
        out["reason"] = "falta una de las dos patas"
        return out
    # Una edad negativa es un evento con marca de tiempo en el futuro: reloj desincronizado
    # o timestamp corrupto. No es "muy fresco", es un dato que no se puede situar.
    if min(fut_age, spot_age) < -CLOCK_TOLERANCE_SECONDS:
        out["status"] = "ERROR"
        out["reason"] = (
            f"timestamp futuro: fut {fut_age:.1f}s / spot {spot_age:.1f}s "
            f"(tolerancia de reloj {CLOCK_TOLERANCE_SECONDS:.0f}s)"
        )
        return out
    if max(fut_age, spot_age) > REALTIME_STALE_SECONDS:
        out["status"] = "STALE"
        out["reason"] = (
            f"pata desfasada: fut {fut_age:.1f}s / spot {spot_age:.1f}s "
            f"(limite {REALTIME_STALE_SECONDS:.0f}s)"
        )
        return out
    out["basis_bps"] = (fut_px - spot_px) / spot_px * 10000
    out["status"] = "VALID"
    return out


def scalp_bias_label(long_score: float, short_score: float) -> tuple[str, str]:
    """Etiqueta de sesgo por BALANCE DE EVIDENCIA, sin mirar el coste de ejecucion.

    Ya no recibe el spread. Vetar con `spread_bps > 5` era un umbral universal: ignoraba
    activo, venue, tamano, tipo de orden y sobre todo el objetivo (5 bps se comen un cuarto
    de un scalp de 20 bps y son ruido en un swing de 400). Si la operacion sale cara lo dice
    `execution_assessment()`, que compara el coste TOTAL contra objetivo y riesgo; el sesgo
    y el coste son dos lecturas distintas y mezclarlas ocultaba las dos.
    """
    edge = abs(long_score - short_score)
    if edge < 12:
        return "No Trade", "baja"
    if long_score > short_score:
        if long_score >= 70:
            return "Long Momentum", "alta"
        if long_score >= 58:
            return "Long Pullback", "media"
    else:
        if short_score >= 70:
            return "Short Momentum", "alta"
        if short_score >= 58:
            return "Short Rejection", "media"
    return "No Trade", "baja"


def score_component(value: float | None) -> tuple[float, float]:
    if value is None:
        return 0.0, 0.0
    clamped = max(-1.0, min(1.0, value))
    bull = (clamped + 1.0) / 2.0
    return bull, 1.0 - bull


async def scalp_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    session_start = current_nyse_start()
    as_of = _utc_now()
    oi_source_start, oi_window_start, oi_window_end = _closed_5m_oi_bounds(as_of)
    liquidation_window_start = as_of - timedelta(minutes=5)

    row = await conn.fetchrow(
        """
        WITH price AS (
          SELECT close AS price FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1
        ), fut_px AS (
          SELECT last_px AS fut_px,last_event_ms AS fut_event_ms FROM futures_trades_realtime
          WHERE symbol=$1 AND exchange='combined' AND venue_count=2 ORDER BY ts DESC LIMIT 1
        ), spot_px AS (
          SELECT last_px AS spot_px,last_event_ms AS spot_event_ms FROM spot_trades_realtime
          WHERE symbol=$2 AND exchange='combined' AND venue_count=2 ORDER BY ts DESC LIMIT 1
        ), fut_1m AS (
          SELECT SUM(buy_vol_usd-sell_vol_usd) AS delta,SUM(buy_vol_usd+sell_vol_usd) AS volume,
                 SUM(trade_count) AS trades,(array_agg(last_px ORDER BY ts DESC))[1] AS last_px
          FROM futures_trades_realtime WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND ts >= now()-interval '1 minute'
        ), fut_3m AS (
          SELECT SUM(buy_vol_usd-sell_vol_usd) AS delta,SUM(buy_vol_usd+sell_vol_usd) AS volume,
                 (array_agg(last_px ORDER BY ts ASC))[1] AS first_px,(array_agg(last_px ORDER BY ts DESC))[1] AS last_px
          FROM futures_trades_realtime WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND ts >= now()-interval '3 minutes'
        ), spot_3m AS (
          SELECT SUM(buy_vol_usd-sell_vol_usd) AS delta,SUM(buy_vol_usd+sell_vol_usd) AS volume
          FROM spot_trades_realtime WHERE symbol=$2 AND exchange='combined' AND venue_count=2 AND ts >= now()-interval '3 minutes'
        ), book AS (
          SELECT * FROM orderbook_snapshot WHERE symbol=$1 AND exchange='combined' AND venue_count=2 ORDER BY ts DESC LIMIT 1
        ), liq AS (
          SELECT SUM(CASE WHEN side='long' THEN notional_usd ELSE 0 END) AS long_liq,
                 SUM(CASE WHEN side='short' THEN notional_usd ELSE 0 END) AS short_liq
          FROM liquidations_realtime
          WHERE symbol=$1 AND ts >= $7 AND ts < $8
        ), oi_raw AS (
          SELECT (array_agg(oi_close ORDER BY ts DESC))[1] AS oi_now,
                 (array_agg(oi_close ORDER BY ts ASC))[1] AS oi_start,
                 COUNT(*)::int AS oi_samples,
                 MIN(ts) AS first_bucket,
                 MAX(ts) AS last_bucket
          FROM open_interest
          WHERE symbol=$1 AND interval='5min' AND ts >= $4 AND ts < $6
        ), oi AS (
          SELECT
            CASE WHEN oi_samples=4 AND last_bucket-first_bucket=interval '15 minutes'
                 THEN oi_now END AS oi_now,
            CASE WHEN oi_samples=4 AND last_bucket-first_bucket=interval '15 minutes'
                 THEN oi_start END AS oi_start,
            oi_samples,
            CASE
              WHEN oi_samples=4 AND last_bucket-first_bucket=interval '15 minutes'
                THEN 'complete'
              WHEN oi_samples>0 THEN 'partial'
              ELSE 'unavailable'
            END AS oi_window_status
          FROM oi_raw
        ), px_15m AS (
          SELECT
                 (array_agg(open  ORDER BY ts ASC))[1]  AS first_px_15m,
                 (array_agg(close ORDER BY ts DESC))[1] AS last_px_15m,
                 COUNT(*)::int AS bars_15m,
                 MIN(ts) AS first_bar,
                 MAX(ts) AS last_bar
          FROM ohlcv
          WHERE symbol = $1
            AND interval = '1min'
            AND ts >= $5
            AND ts <  $6
        ), vwap AS (
          SELECT SUM(close*volume)/NULLIF(SUM(volume),0) AS session_vwap
          FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts >= $3
        ), liq_feed AS (
          SELECT
            MAX(status) FILTER (WHERE exchange='binance') AS liq_binance_status,
            MAX(healthy_since) FILTER (WHERE exchange='binance') AS liq_binance_healthy_since,
            MAX(last_loss_at) FILTER (WHERE exchange='binance') AS liq_binance_last_loss_at,
            MAX(updated_at) FILTER (WHERE exchange='binance') AS liq_binance_updated_at,
            MAX(status) FILTER (WHERE exchange='bybit') AS liq_bybit_status,
            MAX(healthy_since) FILTER (WHERE exchange='bybit') AS liq_bybit_healthy_since,
            MAX(last_loss_at) FILTER (WHERE exchange='bybit') AS liq_bybit_last_loss_at,
            MAX(updated_at) FILTER (WHERE exchange='bybit') AS liq_bybit_updated_at
          FROM market_feed_health
          WHERE feed='liquidations' AND exchange IN ('binance','bybit')
        ), base AS (SELECT 1 AS anchor)
        SELECT COALESCE(fut_px.fut_px, price.price) AS price,
               price.price AS ohlcv_price,
               fut_px.fut_px AS fut_price,
               spot_px.spot_px AS spot_price,
               -- El basis lo decide basis_quality(): aqui solo viajan los insumos. Calcularlo
               -- en SQL lo publicaba sin mirar la edad de cada pata.
               fut_px.fut_event_ms AS fut_event_ms,
               spot_px.spot_event_ms AS spot_event_ms,
               (EXTRACT(EPOCH FROM $8::timestamptz)*1000)::float8 AS now_ms,
               fut_1m.delta AS fut_delta_1m,fut_1m.volume AS fut_volume_1m,fut_1m.trades AS fut_trades_1m,
               fut_3m.delta AS fut_delta_3m,fut_3m.volume AS fut_volume_3m,fut_3m.first_px AS first_px_3m,fut_3m.last_px AS last_px_3m,
               spot_3m.delta AS spot_delta_3m,spot_3m.volume AS spot_volume_3m,
               book.spread_bps,book.imbalance_l1,book.imbalance_l5,book.imbalance_l10,book.wall_up_pct,book.wall_down_pct,
               CASE
                 WHEN book.ts IS NULL THEN 'missing'
                 WHEN book.ts < now()-interval '10 seconds' THEN 'stale'
                 ELSE 'ok'
               END AS book_status,
               EXTRACT(EPOCH FROM now()-book.ts)::float8 AS book_lag_seconds,
               liq.long_liq,liq.short_liq,oi.oi_now,oi.oi_start,vwap.session_vwap,
               $5::timestamptz AS oi_window_start,
               $6::timestamptz AS oi_window_end,
               oi.oi_samples AS oi_window_samples,
               oi.oi_window_status,
               px_15m.first_px_15m,px_15m.last_px_15m,px_15m.bars_15m,
               CASE
                 WHEN px_15m.bars_15m=15
                  AND px_15m.last_bar-px_15m.first_bar=interval '14 minutes'
                   THEN 'complete'
                 WHEN px_15m.bars_15m>0 THEN 'partial'
                 ELSE 'none'
               END AS price_move_15m_coverage,
               $7::timestamptz AS liquidation_window_start,
               liq_feed.*
        FROM base
        LEFT JOIN price ON true
        LEFT JOIN fut_px ON true
        LEFT JOIN spot_px ON true
        LEFT JOIN fut_1m ON true
        LEFT JOIN fut_3m ON true
        LEFT JOIN spot_3m ON true
        LEFT JOIN book ON true
        LEFT JOIN liq ON true
        LEFT JOIN oi ON true
        LEFT JOIN px_15m ON true
        LEFT JOIN vwap ON true
        LEFT JOIN liq_feed ON true
        """,
        symbol,
        WS_SYMBOL_MAP[symbol],
        session_start,
        oi_source_start,
        oi_window_start,
        oi_window_end,
        liquidation_window_start,
        as_of,
    )
    ctx = dict(row) if row else {}
    # La puerta de absorcion del resumen mira la ventana de 3 m: su umbral sale de la
    # distribucion medida de ESA ventana, no de una constante compartida con 1 m y 4 h.
    baselines = await load_baselines(conn, symbol)
    ctx["baseline_3m"] = baselines.get("3m")
    return ctx


def _first_present(*values: float | None) -> float | None:
    """Primer valor NO nulo.

    Sustituye a `a or b`, que en Python descarta tambien el 0.0 legitimo y cae al siguiente
    candidato. Aqui un cero medido gana, que es lo correcto.
    """
    for value in values:
        if value is not None:
            return value
    return None


def _liquidation_window_measured(ctx: dict[str, Any]) -> bool:
    """¿Se estaba ESCUCHANDO el feed de liquidaciones durante la ventana?

    Las liquidaciones son un stream de eventos: la ausencia de filas puede significar calma
    (dato legitimo: cero liquidado) o un stream caido (dato inexistente). Ambos venues deben
    haber permanecido sanos durante toda la ventana, sin pérdidas y con estado fresco.
    """
    now = _as_utc_datetime(ctx.get("now_ms"), milliseconds=True)
    window_start = _as_utc_datetime(ctx.get("liquidation_window_start"))
    if now is None or window_start is None:
        return False
    freshness = timedelta(seconds=COLLECTOR_THRESHOLDS["scalp"][1])
    for exchange in ("binance", "bybit"):
        prefix = f"liq_{exchange}_"
        healthy_since = _as_utc_datetime(ctx.get(prefix + "healthy_since"))
        last_loss_at = _as_utc_datetime(ctx.get(prefix + "last_loss_at"))
        updated_at = _as_utc_datetime(ctx.get(prefix + "updated_at"))
        if (
            ctx.get(prefix + "status") != "ok"
            or healthy_since is None
            or updated_at is None
            or not (now - freshness <= updated_at <= now + timedelta(seconds=1))
            or healthy_since > window_start
            or (last_loss_at is not None and last_loss_at >= window_start)
        ):
            return False
    return True


def _as_utc_datetime(value: object, *, milliseconds: bool = False) -> datetime | None:
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    if milliseconds:
        number = as_float(value)
        return datetime.fromtimestamp(number / 1000, UTC) if number is not None else None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return None


def _measured_event_sum(raw: object, measured: bool) -> float | None:
    """Suma de un feed de eventos: 0.0 solo si la ventana se midio, si no None."""
    if not measured:
        return None
    value = as_float(raw)
    return 0.0 if value is None else value


def _coverage_status(bars: object, expected: int) -> str:
    """Cobertura estricta de una ventana temporal.

    complete = exactamente todas las velas esperadas
    partial  = existe al menos una, pero falta alguna
    none     = no existe ninguna

    Una ventana parcial nunca se promociona a completa por porcentaje:
    13/15 o 14/15 siguen siendo PARTIAL.
    """
    try:
        n = int(bars) if bars is not None else 0
    except (TypeError, ValueError):
        n = 0

    if n <= 0:
        return "none"

    if n == expected:
        return "complete"

    return "partial"


def _closed_window_move_pct(
    first_px: float | None,
    last_px: float | None,
    bars: object,
    expected_bars: int,
) -> tuple[float | None, str, str]:
    """Movimiento de precio sólo cuando la ventana está completamente cubierta.

    Returns:
        (move_pct, status, coverage)

    status:
        MEASURED    ventana completa + precios válidos
        PARTIAL     faltan velas
        UNAVAILABLE ninguna vela
        ERROR       cobertura completa pero precios inválidos
    """
    coverage = _coverage_status(bars, expected_bars)

    if coverage == "none":
        return None, "UNAVAILABLE", coverage

    if coverage != "complete":
        return None, "PARTIAL", coverage

    if (
        first_px is None
        or last_px is None
        or first_px <= 0
        or last_px <= 0
    ):
        return None, "ERROR", coverage

    move_pct = (last_px - first_px) / first_px * 100.0

    return move_pct, "MEASURED", coverage


def compute_scalp_summary(ctx: dict[str, Any]) -> dict[str, Any]:
    fut_delta_1m = as_float(ctx.get("fut_delta_1m"))
    fut_volume_1m = as_float(ctx.get("fut_volume_1m"))
    fut_delta_3m = as_float(ctx.get("fut_delta_3m"))
    fut_volume_3m = as_float(ctx.get("fut_volume_3m"))
    spot_delta_3m = as_float(ctx.get("spot_delta_3m"))
    spot_volume_3m = as_float(ctx.get("spot_volume_3m"))
    imb_l5 = as_float(ctx.get("imbalance_l5"))
    spread_bps = as_float(ctx.get("spread_bps"))
    first_px = as_float(ctx.get("first_px_3m"))
    last_px = _first_present(as_float(ctx.get("last_px_3m")), as_float(ctx.get("price")))
    oi_now = as_float(ctx.get("oi_now"))
    oi_start = as_float(ctx.get("oi_start"))
    oi_window_status = str(ctx.get("oi_window_status") or "unavailable")
    # Movimiento de precio de la MISMA ventana que el OI (15 m), no el de 3 m. Sale de velas
    # 1 min CERRADAS de esos 15 minutos; su cobertura viaja aparte. Nunca se aproxima con 3 m.
    first_px_15m = as_float(ctx.get("first_px_15m"))
    last_px_15m = as_float(ctx.get("last_px_15m"))
    bars_15m = ctx.get("bars_15m")
    vwap = as_float(ctx.get("session_vwap"))
    price = _first_present(as_float(ctx.get("price")), last_px)

    # Liquidaciones: la SUMA es NULL tanto si no hubo eventos como si nadie estaba
    # escuchando. Un cero solo es publicable cuando el collector de WS confirma que la
    # ventana SI se midio; en cualquier otro caso el valor es None (desconocido), no 0.
    liq_measured = _liquidation_window_measured(ctx)
    long_liq = _measured_event_sum(ctx.get("long_liq"), liq_measured)
    short_liq = _measured_event_sum(ctx.get("short_liq"), liq_measured)

    fut_norm = fut_delta_1m / fut_volume_1m if fut_volume_1m else 0.0
    fut_norm3 = fut_delta_3m / fut_volume_3m if fut_volume_3m else 0.0
    # None, no 0.0: sin pata spot no hay nada contra lo que comparar los futuros.
    spot_norm3 = (
        spot_delta_3m / spot_volume_3m
        if spot_delta_3m is not None and spot_volume_3m
        else None
    )
    # Sin precios de la ventana el movimiento es DESCONOCIDO. Un 0.0 inventado se lee como
    # "el precio aguanto" y dispara absorcion falsa. passive_flow ya lo hacia asi.
    price_move_3m = (
        ((last_px - first_px) / first_px * 100) if first_px and last_px else None
    )
    # Faltando CUALQUIERA de las dos lecturas de OI no hay variacion que medir. El `if oi_now
    # and oi_start else 0.0` anterior publicaba "OI plano" cada vez que el feed callaba, y ese
    # 0.0 entraba al score como un voto neutral con peso 10 que nadie habia medido.
    oi_chg_15m_pct = (
        ((oi_now - oi_start) / oi_start * 100)
        if oi_window_status == "complete"
        and oi_now is not None
        and oi_start is not None
        and oi_start != 0
        else None
    )
    # Sin VWAP la distancia es DESCONOCIDA. Un 0.0 se lee como "el precio esta justo sobre el
    # VWAP", que es una afirmacion fuerte y falsa.
    vwap_dist_pct = (
        ((price - vwap) / vwap * 100)
        if price is not None and vwap is not None and vwap != 0
        else None
    )

    book_norm = ((imb_l5 - 0.5) * 2.0) if imb_l5 is not None else None
    spot_fut_divergence_norm = (
        max(-1.0, min(1.0, (spot_norm3 - fut_norm3) / 2.0)) if spot_norm3 is not None else None
    )
    # Ventana medida y sin eventos = cero REAL (mercado en calma), y vota como neutral.
    # Ventana no medida = None y el componente queda fuera del peso.
    liq_total = (long_liq + short_liq) if liq_measured else None
    if liq_total is None:
        liq_norm = None
    elif liq_total == 0:
        liq_norm = 0.0
    else:
        liq_norm = (short_liq - long_liq) / liq_total
    baseline_3m = ctx.get("baseline_3m")
    if price_move_3m is None:
        # Sin movimiento medido no se puede afirmar absorcion ni descartarla.
        absorption, absorption_label = None, "No evaluable"
    else:
        absorption, absorption_label = classify_absorption(
            fut_delta_3m,
            price_move_3m,
            fut_volume_3m,
            (baseline_3m or {}).get("p75"),
        )
    delta_ratio_3m = (
        abs(fut_delta_3m) / fut_volume_3m
        if fut_delta_3m is not None and fut_volume_3m
        else None
    )
    absorption_context = baseline_band(delta_ratio_3m, baseline_3m)
    absorption_context["threshold_source"] = (
        "baseline_p75_medido" if baseline_3m else "fallback_constante_0.10"
    )
    basis = basis_quality(
        as_float(ctx.get("fut_price")),
        as_float(ctx.get("spot_price")),
        as_float(ctx.get("fut_event_ms")),
        as_float(ctx.get("spot_event_ms")),
        as_float(ctx.get("now_ms")) or 0.0,
    )

    weights = {
        "fut_delta": 20,
        "spot_fut_divergence": 15,
        "book": 20,
        "absorption": 20,
        "liquidations": 10,
        "oi": 10,
        "vwap": 5,
    }
    # Un componente sin dato NO vota 0 (eso es un voto neutral fabricado): queda fuera y el
    # score se renormaliza sobre el peso realmente medido, que ademas se publica.
    #
    # OPEN INTEREST — reemplaza `clamp(oi_chg_15m/0.5) * dir(price_3m)`, que trataba ΔOI como un
    # delta direccional y ademas comparaba OI de 15 m con precio de 3 m (ventanas distintas).
    # Ahora:
    #   1) el movimiento de precio es de la MISMA ventana de 15 m (`price_move_15m_pct`);
    #   2) el OI se clasifica como ESTADO (expansion/contraccion/plano) sin direccion propia;
    #   3) `oi_price_reading()` compone precio+OI+flujo y dice con QUE direccion es compatible.
    # El OI solo vota direccion cuando hay POSICIONAMIENTO NUEVO (expansion) coherente con el
    # precio y el flujo no lo contradice. Una contraccion (cierre/desapalancamiento) NO vota al
    # lado contrario: es medida pero neutral (0.0). El OI ausente, o sin precio 15 m con que
    # leerlo, NO cuenta peso (None).
    (
        price_move_15m_pct,
        price_move_15m_status,
        coverage_15m,
    ) = _closed_window_move_pct(
        first_px_15m,
        last_px_15m,
        bars_15m,
        OI_15M_EXPECTED_BARS,
    )
    declared_price_coverage = ctx.get("price_move_15m_coverage")
    if declared_price_coverage in {"complete", "partial", "none"}:
        coverage_15m = str(declared_price_coverage)
        if coverage_15m != "complete":
            price_move_15m_pct = None
            price_move_15m_status = (
                "PARTIAL" if coverage_15m == "partial" else "UNAVAILABLE"
            )
    oi_state = classify_oi(oi_chg_15m_pct, oi_to_volume=None, timeframe="15m")
    oi_reading = oi_price_reading(
        price_move_15m_pct, oi_state, fut_delta=fut_delta_3m, spot_delta=spot_delta_3m
    )
    oi_price_status = (
        "MEASURED"
        if oi_chg_15m_pct is not None
        and price_move_15m_pct is not None
        else "NO_EVALUABLE"
    )
    oi_supports = oi_reading["supports"]
    oi_directional = bool(
        oi_reading.get("new_positioning")
        and oi_supports is not None
        and oi_reading.get("flow_agrees") is not False
    )
    if oi_chg_15m_pct is None or price_move_15m_pct is None:
        # OI no medido, o sin precio de la MISMA ventana: no hay lectura -> no cuenta peso.
        oi_component = None
    elif oi_directional:
        strength = min(1.0, abs(oi_chg_15m_pct) / OI_SCORE_FULL_PCT)
        oi_component = oi_supports * strength
    else:
        # Medido pero sin direccion (plano, contraccion, o flujo que contradice): vota neutral,
        # NUNCA al lado contrario. Cuenta peso como una lectura real de "sin posicionamiento".
        oi_component = 0.0
    long_score = short_score = 0.0
    measured_weight = 0.0
    missing: list[str] = []
    for name, norm in [
        ("fut_delta", (fut_norm * 0.65 + fut_norm3 * 0.35) if fut_volume_1m else None),
        ("spot_fut_divergence", spot_fut_divergence_norm),
        ("book", book_norm),
        ("absorption", absorption),
        ("liquidations", liq_norm),
        ("oi", oi_component),
        (
            "vwap",
            max(-1.0, min(1.0, vwap_dist_pct / 0.25)) if vwap_dist_pct is not None else None,
        ),
    ]:
        if norm is None:
            missing.append(name)
            continue
        bull, bear = score_component(norm)
        long_score += bull * weights[name]
        short_score += bear * weights[name]
        measured_weight += weights[name]
    expected_weight = float(sum(weights.values()))
    if measured_weight > 0:
        long_score *= expected_weight / measured_weight
        short_score *= expected_weight / measured_weight
    coverage_pct = round(measured_weight / expected_weight * 100, 1)
    book_status = str(ctx.get("book_status") or "missing")
    state, confidence = scalp_bias_label(long_score, short_score)
    if book_status != "ok":
        state, confidence = "No Trade", "baja"
    # Con menos de la mitad del peso medido el score no representa un balance de evidencia.
    if coverage_pct < 50:
        state, confidence = "Sin datos suficientes", "baja"
    # Los textos no rellenan huecos con ceros: lo que no se midio se dice N/D.
    div_txt = (
        f"{spot_fut_divergence_norm:+.2f}" if spot_fut_divergence_norm is not None else "N/D"
    )
    fut_txt = f"{fut_delta_1m:.0f}" if fut_delta_1m is not None else "N/D"
    l5_txt = f"{imb_l5:.2f}" if imb_l5 is not None else "N/D"
    liq_txt = f"{short_liq - long_liq:.0f}" if liq_measured else "N/D"
    reason = (
        f"ΔFut1m {fut_txt}, div spot-fut {div_txt}, book {book_status}"
        f"/L5 {l5_txt}, {absorption_label}, "
        f"liq S-L {liq_txt}, evidencia {coverage_pct:.0f}%"
    )
    return {
        "long_score": round(long_score, 1),
        "short_score": round(short_score, 1),
        "state": state,
        "confidence": confidence,
        "reason": reason,
        "fut_delta_1m": fut_delta_1m,
        "fut_delta_3m": fut_delta_3m,
        "fut_volume_1m": fut_volume_1m,
        "spot_delta_3m": spot_delta_3m,
        # Un diferencial exige las DOS patas. Restar contra una ausencia publicaba la pata
        # presente con el signo cambiado y la llamaba "diferencial spot-futuros".
        "diff_3m": (
            spot_delta_3m - fut_delta_3m
            if spot_delta_3m is not None and fut_delta_3m is not None
            else None
        ),
        "spot_fut_divergence_norm": spot_fut_divergence_norm,
        "measured_weight": round(measured_weight, 1),
        "expected_weight": expected_weight,
        "evidence_coverage_pct": coverage_pct,
        "missing_components": missing,
        "fut_price": as_float(ctx.get("fut_price")),
        "spot_price": as_float(ctx.get("spot_price")),
        "basis_bps": basis["basis_bps"],
        "basis_status": basis["status"],
        "basis_detail": basis,
        "book_status": str(ctx.get("book_status") or "missing"),
        "book_lag_seconds": as_float(ctx.get("book_lag_seconds")),
        "price_move_3m_pct": price_move_3m,
        "spread_bps": spread_bps,
        "imbalance_l1": as_float(ctx.get("imbalance_l1")),
        "imbalance_l5": imb_l5,
        "imbalance_l10": as_float(ctx.get("imbalance_l10")),
        "wall_up_pct": as_float(ctx.get("wall_up_pct")),
        "wall_down_pct": as_float(ctx.get("wall_down_pct")),
        "long_liq_5m": long_liq,
        "short_liq_5m": short_liq,
        # Permite al consumidor distinguir "0 USD liquidados" de "no se midio": sin esta
        # marca los dos casos llegan indistinguibles y el frontend pinta un cero.
        "liquidations_measured": liq_measured,
        "liquidations_window": "5m",
        "liquidation_feed_health": {
            exchange: {
                "status": ctx.get(f"liq_{exchange}_status"),
                "healthy_since": ctx.get(f"liq_{exchange}_healthy_since"),
                "last_loss_at": ctx.get(f"liq_{exchange}_last_loss_at"),
                "updated_at": ctx.get(f"liq_{exchange}_updated_at"),
            }
            for exchange in ("binance", "bybit")
        },
        "oi_chg_15m_pct": oi_chg_15m_pct,
        "oi_start": oi_start,
        "oi_now": oi_now,
        "oi_window_start": ctx.get("oi_window_start"),
        "oi_window_end": ctx.get("oi_window_end"),
        "oi_window_samples": int(ctx.get("oi_window_samples") or 0),
        "oi_window_status": oi_window_status,
        # Lectura de OI: permite ver POR QUE el OI contribuyo o no al score (spec 2.5).
        "oi_state": oi_state["state"],
        "oi_price_quadrant": oi_reading["quadrant"],
        "oi_reading": oi_reading["reading"],
        "oi_directional_support": oi_supports,
        "oi_new_positioning": oi_reading.get("new_positioning"),
        "oi_timeframe": "15m",
        "oi_contributes_direction": oi_directional,
        "price_move_15m_pct": price_move_15m_pct,
        "price_move_15m_status": price_move_15m_status,
        "price_move_15m_coverage": coverage_15m,
        "oi_price_status": oi_price_status,
        "session_vwap": vwap,
        "vwap_dist_pct": vwap_dist_pct,
        "absorption": absorption_label,
        "absorption_delta_ratio": round(delta_ratio_3m, 4) if delta_ratio_3m is not None else None,
        "absorption_context": absorption_context,
    }


def as_float(value: object) -> float | None:
    """float FINITO o None.

    `result == result` solo descartaba NaN: los infinitos pasaban y contaminan cualquier
    media, percentil o ratio aguas abajo sin lanzar excepcion.
    """
    try:
        if value is None:
            return None
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


# ---------------- estructura de mercado (micro / mid / macro) ----------------
def _pivot_structure(highs: list, lows: list, k: int = 3) -> str | None:
    """HH/HL vs LH/LL comparando los dos ultimos swing highs/lows (fractal de ancho k)."""
    highs = [as_float(v) for v in highs]
    lows = [as_float(v) for v in lows]
    if any(v is None for v in highs) or any(v is None for v in lows):
        return None
    ph = [highs[i] for i in range(k, len(highs) - k) if highs[i] == max(highs[i - k : i + k + 1])]
    pl = [lows[i] for i in range(k, len(lows) - k) if lows[i] == min(lows[i - k : i + k + 1])]
    if len(ph) < 2 or len(pl) < 2:
        return None
    hh, hl = ph[-1] > ph[-2], pl[-1] > pl[-2]
    if hh and hl:
        return "HH/HL"
    if not hh and not hl:
        return "LH/LL"
    return "mixta"


def _sign_vote(value: float | None) -> bool | None:
    if value is None or value == 0:
        return None
    return value > 0


def _structure_layer(
    name: str, horizon: str, components: dict, price_structure: str | None
) -> dict[str, Any]:
    votes = [v for v in components.values() if v is not None]
    up = sum(1 for v in votes if v)
    down = len(votes) - up
    bias = "alcista" if up > down else ("bajista" if down > up else "neutral")
    return {
        "layer": name,
        "horizon": horizon,
        "bias": bias,
        "votes_up": up,
        "votes_total": len(votes),
        "method": "multi_signal_vote",
        "distinct_from": "structure_detail (pivotes puros por horizonte); esta capa es voto multi-senal",
        "price_structure": price_structure,
        "price_structure_note": "patron de pivotes del timeframe base de la capa; el resultado del voto es 'bias', no este campo",
        "components": components,
    }


_PIV_VOTE = {"HH/HL": True, "LH/LL": False}


async def _cvd_fut_window(conn: asyncpg.Connection, symbol: str, seconds: int) -> float | None:
    return as_float(
        await conn.fetchval(
            "SELECT SUM(buy_vol_usd-sell_vol_usd) FROM futures_trades_realtime "
            "WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND ts >= now()-($2::int * interval '1 second')",
            symbol,
            seconds,
        )
    )


async def market_structure(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Bias determinista por horizonte: order flow + OI + liquidaciones + pivotes de precio.

    Micro 1m-15m (ws), Mid 30m-4h (ws + historico), Macro sesiones diarias.
    Cada componente vota alcista/bajista/sin-dato; bias = mayoria simple, sin pesos.
    """
    m1_rows = await conn.fetch(
        "SELECT high, low, close FROM ohlcv WHERE symbol=$1 AND interval='1min' "
        "ORDER BY ts DESC LIMIT 120",
        symbol,
    )
    m1 = [dict(r) for r in reversed(m1_rows)]
    m15_rows = await conn.fetch(
        """
        WITH b AS (
          SELECT date_bin('15 minutes'::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                 MAX(high) AS high, MIN(low) AS low,
                 (array_agg(close ORDER BY ts DESC))[1] AS close
          FROM ohlcv WHERE symbol=$1 AND interval='1min'
          GROUP BY 1 ORDER BY 1 DESC LIMIT 192
        ) SELECT * FROM b ORDER BY bucket
        """,
        symbol,
    )
    m15 = [dict(r) for r in m15_rows]
    daily_rows = await conn.fetch(
        "SELECT session_date, price_close, price_chg_pct, cvd_spot_usd FROM daily_session_agg "
        "WHERE symbol=$1 ORDER BY session_date DESC LIMIT 30",
        symbol,
    )
    daily = [dict(r) for r in reversed(daily_rows)]

    def px_change(rows: list, back: int) -> float | None:
        if len(rows) <= back:
            return None
        last, prev = as_float(rows[-1]["close"]), as_float(rows[-1 - back]["close"])
        if last is None or prev is None:
            return None
        return last - prev

    # ---- micro (1m-15m)
    liq_rt = await conn.fetchrow(
        "SELECT SUM(CASE WHEN side='long' THEN notional_usd ELSE 0 END) AS long_liq,"
        "SUM(CASE WHEN side='short' THEN notional_usd ELSE 0 END) AS short_liq "
        "FROM liquidations_realtime WHERE symbol=$1 AND ts >= now()-interval '15 minutes'",
        symbol,
    )
    micro_liq = None
    if liq_rt and ((as_float(liq_rt["long_liq"]) or 0) or (as_float(liq_rt["short_liq"]) or 0)):
        # se liquidan shorts -> presion compradora
        micro_liq = (as_float(liq_rt["short_liq"]) or 0) > (as_float(liq_rt["long_liq"]) or 0)
    micro_ps = (
        _pivot_structure([r["high"] for r in m1], [r["low"] for r in m1]) if len(m1) > 10 else None
    )
    micro = _structure_layer(
        "micro",
        "1m-15m",
        {
            "cvd15m": _sign_vote(await _cvd_fut_window(conn, symbol, 900)),
            "px15m": _sign_vote(px_change(m1, 15)),
            "liq15m": micro_liq,
            "piv": _PIV_VOTE.get(micro_ps),
        },
        micro_ps,
    )

    # ---- mid (30m-4h)
    oi_rows = await conn.fetch(
        "SELECT oi_close FROM open_interest WHERE symbol=$1 AND interval='5min' "
        "AND ts >= now()-interval '250 minutes' ORDER BY ts",
        symbol,
    )
    oi_vals = [as_float(r["oi_close"]) for r in oi_rows if as_float(r["oi_close"]) is not None]
    px4h = px_change(m15, 16)
    oi_conf = None
    if len(oi_vals) >= 2 and oi_vals[-1] > oi_vals[0] and px4h is not None and px4h != 0:
        oi_conf = (
            px4h > 0
        )  # OI subiendo confirma la direccion del precio; OI bajando = unwind, sin voto
    liq_hist = await conn.fetchrow(
        "SELECT SUM(long_liq) AS long_liq, SUM(short_liq) AS short_liq FROM liquidations "
        "WHERE symbol=$1 AND interval='5min' AND ts >= now()-interval '4 hours'",
        symbol,
    )
    mid_liq = None
    if liq_hist and (
        (as_float(liq_hist["long_liq"]) or 0) or (as_float(liq_hist["short_liq"]) or 0)
    ):
        mid_liq = (as_float(liq_hist["short_liq"]) or 0) > (as_float(liq_hist["long_liq"]) or 0)
    mid_ps = (
        _pivot_structure([r["high"] for r in m15], [r["low"] for r in m15])
        if len(m15) > 10
        else None
    )
    mid = _structure_layer(
        "mid",
        "30m-4h",
        {
            "cvd1h": _sign_vote(await _cvd_fut_window(conn, symbol, 3600)),
            "cvd4h": _sign_vote(await _cvd_fut_window(conn, symbol, 14400)),
            "oi": oi_conf,
            "liq4h": mid_liq,
            "piv": _PIV_VOTE.get(mid_ps),
        },
        mid_ps,
    )

    # ---- macro (sesiones diarias)
    closes_d = [as_float(r["price_close"]) for r in daily if as_float(r["price_close"]) is not None]
    px7 = (closes_d[-1] - closes_d[-8]) if len(closes_d) >= 8 else None
    cvd_tail = [as_float(r["cvd_spot_usd"]) for r in daily[-7:]]
    cvd7 = sum(v for v in cvd_tail if v is not None) if len(cvd_tail) == 7 and all(v is not None for v in cvd_tail) else None
    racha = None
    price_tail = [as_float(r["price_chg_pct"]) for r in daily[-3:]]
    if len(price_tail) == 3 and all(v is not None for v in price_tail):
        racha = sum(1 for v in price_tail if v > 0) >= 2
    macro_ps = _pivot_structure(closes_d, closes_d, k=2) if len(closes_d) >= 10 else None
    macro = _structure_layer(
        "macro",
        "1d-7d",
        {
            "px7d": _sign_vote(px7),
            "cvd7d": _sign_vote(cvd7),
            "racha": racha,
            "piv": _PIV_VOTE.get(macro_ps),
        },
        macro_ps,
    )

    layers = [micro, mid, macro]
    biases = {item["bias"] for item in layers}
    alignment = (
        f"alineado_{layers[0]['bias']}" if len(biases) == 1 and "neutral" not in biases else "mixto"
    )
    return {"symbol": symbol, "layers": layers, "alignment": alignment}


# ---------------- alertas HTF: estructura por horizonte + liquidaciones masivas ----------------
# (1h/4h/8h intradia por resample de ohlcv 1min; 1d/3d/9d por cierres de daily_session_agg)
_ALERT_HORIZONS = (
    ("1h", 3600, "med"),
    ("4h", 14400, "med"),
    ("8h", 28800, "med"),
    ("1d", 1, "long"),
    ("3d", 3, "long"),
    ("9d", 9, "long"),
)


async def _resample_highs_lows(
    conn: asyncpg.Connection,
    symbol: str,
    secs: int,
    limit: int,
    source_interval: str = "1min",
    as_of: datetime | None = None,
) -> list[dict]:
    """Resamplea exclusivamente buckets TARGET ya cerrados.

    El collector conserva la vela abierta; esta frontera pertenece al consumidor historico.
    El filtro ocurre ANTES de LIMIT para que la vela abierta no robe una muestra cerrada.
    """
    if source_interval not in {"1min", "5min", "4hour", "daily"}:
        raise ValueError("unsupported OHLCV interval")
    cutoff = as_of or datetime.now(UTC)
    rows = await conn.fetch(
        """
        WITH b AS (
          SELECT date_bin(make_interval(secs => $2::int), ts, '1970-01-01'::timestamptz) AS bucket,
                 MAX(high) AS high, MIN(low) AS low,
                 (array_agg(close ORDER BY ts DESC))[1] AS close,
                 SUM(volume * close) AS volume_usd
          FROM ohlcv WHERE symbol=$1 AND interval=$4
          GROUP BY 1
        ), closed AS (
          SELECT * FROM b
          WHERE bucket + make_interval(secs => $2::int) <= $5
          ORDER BY bucket DESC LIMIT $3
        )
        SELECT * FROM closed ORDER BY bucket
        """,
        symbol, secs, limit, source_interval, cutoff,
    )
    return [dict(r) for r in rows]


async def price_barriers(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Barreras de precio de dos años + pivotes 4h, con esfuerzo vivo de 15m."""
    as_of = datetime.now(UTC)
    daily_bars = await _resample_highs_lows(conn, symbol, 86400, MARKET_MEMORY_DAYS, "daily", as_of)
    daily_rows = [
        {
            "session_date": row["bucket"],
            "price_high": row["high"],
            "price_low": row["low"],
            "price_close": row["close"],
            "volume_usd": row["volume_usd"],
            "cvd_spot_usd": None,
        }
        for row in daily_bars
    ]
    if len(daily_rows) < 120:
        fallback = await conn.fetch(
            "SELECT session_date,price_high,price_low,price_close,volume_usd,cvd_spot_usd "
            "FROM daily_session_agg WHERE symbol=$1 "
            "AND price_high IS NOT NULL AND price_low IS NOT NULL AND price_close IS NOT NULL "
            "ORDER BY session_date DESC LIMIT 730",
            symbol,
        )
        daily_rows = [dict(row) for row in reversed(fallback)]
    # Orden de preferencia por profundidad real de cada fuente (medido contra la API):
    # 4hour llega a ~300 dias, 5min solo a ~8-9, y 1min es el ultimo recurso local. Las velas
    # 4hour nativas ya vienen alineadas a limites de 4 h desde epoch, asi que el date_bin del
    # resample es identidad y no deforma nada.
    bars_4h = await _resample_highs_lows(conn, symbol, 14400, BARRIER_INTRADAY_TARGET_BARS, "4hour", as_of)
    intraday_source = "4hour"
    if len(bars_4h) < 120:
        bars_4h = await _resample_highs_lows(
            conn, symbol, 14400, BARRIER_INTRADAY_TARGET_BARS, "5min", as_of
        )
        intraday_source = "5min"
    if len(bars_4h) < 20:
        bars_4h = await _resample_highs_lows(conn, symbol, 14400, 120, "1min", as_of)
        intraday_source = "1min"
    # CVD spot por bucket de 4h: spot_trades_agg comparte reloj con las velas (ambos se
    # agrupan por date_bin desde epoch), asi que la absorcion de los pivotes 4h es medible.
    # Las velas diarias NO pueden llevar CVD: daily_session_agg va en sesion NYSE
    # (D-1 09:30 ET -> D 09:30 ET), desalineada ~14.5 h del dia UTC de ohlcv.
    cvd_4h = {
        row["bucket"]: as_float(row["cvd"])
        for row in await conn.fetch(
            """
            SELECT date_bin('4 hours'::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                   SUM(buy_vol_usd - sell_vol_usd) AS cvd
            FROM spot_trades_agg
            WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
            GROUP BY 1
            """,
            WS_SYMBOL_MAP[symbol],
        )
    }
    for bar in bars_4h:
        bar["cvd_spot_usd"] = cvd_4h.get(bar["bucket"])
    current_price = as_float(
        await conn.fetchval(
            "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    flow = await conn.fetchrow(
        """
        WITH buckets AS (
          SELECT date_bin('15 minutes'::interval,ts,'1970-01-01'::timestamptz) AS bucket,
                 SUM(buy_vol_usd+sell_vol_usd) AS volume
          FROM futures_trades_agg
          WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
            AND ts >= now()-interval '36 hours'
          GROUP BY 1
        ), baseline AS (
          SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY volume) AS normal_volume,
                 COUNT(*)::int AS buckets
          FROM buckets
          WHERE bucket < date_bin('15 minutes'::interval,now(),'1970-01-01'::timestamptz)
        ), recent AS (
          SELECT SUM(buy_vol_usd+sell_vol_usd) AS volume,
                 SUM(buy_vol_usd-sell_vol_usd) AS delta
          FROM futures_trades_agg
          WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
            AND ts >= now()-interval '15 minutes'
        ), price AS (
          SELECT (array_agg(close ORDER BY ts ASC))[1] AS first_px,
                 (array_agg(close ORDER BY ts DESC))[1] AS last_px
          FROM ohlcv
          WHERE symbol=$1 AND interval='1min' AND ts >= now()-interval '15 minutes'
        ), book AS (
          SELECT imbalance_l5,
                 CASE WHEN ts >= now()-interval '10 seconds' THEN 'ok' ELSE 'stale' END AS status
          FROM orderbook_snapshot
          WHERE symbol=$1 AND exchange='combined' AND venue_count=2 ORDER BY ts DESC LIMIT 1
        )
        SELECT recent.volume,recent.delta,baseline.normal_volume,baseline.buckets,
               price.first_px,price.last_px,book.imbalance_l5,COALESCE(book.status,'missing') AS book_status
        FROM recent CROSS JOIN baseline CROSS JOIN price LEFT JOIN book ON true
        """,
        symbol,
    )
    live: dict[str, Any] = {}
    if flow:
        volume = as_float(flow["volume"])
        normal_volume = as_float(flow["normal_volume"])
        delta = as_float(flow["delta"])
        first_px = as_float(flow["first_px"])
        last_px = as_float(flow["last_px"])
        live = {
            "volume_15m_usd": round(volume, 2) if volume is not None else None,
            "normal_volume_15m_usd": round(normal_volume, 2) if normal_volume is not None else None,
            "volume_multiple_15m": volume / normal_volume if volume and normal_volume else None,
            "delta_ratio_15m": delta / volume if delta is not None and volume else None,
            "price_move_15m_pct": (last_px / first_px - 1) * 100 if first_px and last_px else None,
            "imbalance_l5": as_float(flow["imbalance_l5"]),
            "book_status": str(flow["book_status"]),
            "baseline_buckets": int(flow["buckets"] or 0),
        }
    return {
        "symbol": symbol,
        "intraday_source_interval": intraday_source,
        **price_barrier_read(
            daily_rows,
            bars_4h,
            current_price,
            live,
        ),
    }


async def zone_analysis(
    conn: asyncpg.Connection,
    symbol: str,
    zone_low: float,
    zone_high: float,
    days: int = 365,
) -> dict[str, Any]:
    """Caracter de cada visita del precio a una zona: acumulacion, distribucion o rotacion.

    Se apoya en `ohlcv` a 4h (~300 dias, con buy_volume -> delta de futuros REAL) y en
    `daily_session_agg` (392 sesiones: CVD spot, OI y funding). El libro de ordenes y el flujo
    a nivel de trade no llegan a estas profundidades, asi que no participan del veredicto.
    """
    if zone_low >= zone_high:
        raise ValueError("zone_low must be below zone_high")
    as_of = datetime.now(UTC)
    bars = await conn.fetch(
        """
        SELECT ts, open, high, low, close, volume, buy_volume
        FROM ohlcv
        WHERE symbol=$1 AND interval='4hour'
          AND ts >= $5 - make_interval(days => $2)
          AND ts + interval '4 hours' <= $5
          AND low <= $4 AND high >= $3
        ORDER BY ts
        """,
        symbol,
        days,
        zone_low,
        zone_high,
        as_of,
    )
    baseline_row = await conn.fetchrow(
        """
        SELECT
          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY abs(cvd_spot_usd))
             FROM daily_session_agg WHERE symbol=$1) AS median_abs_cvd_spot,
          (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY volume*close)
             FROM ohlcv WHERE symbol=$1 AND interval='4hour'
               AND ts >= $2 - interval '90 days'
               AND ts + interval '4 hours' <= $2) AS median_bar_volume_usd,
          -- Escala de esfuerzo POR SIMBOLO: mediana de la fraccion direccional de UNA vela.
          -- El modelo A*n^-0.292 la extiende a ventanas de n velas; medido, la mediana
          -- empirica queda entre 0.77x y 1.17x de esa prediccion en BTC, ETH y SOL.
          (SELECT percentile_cont(0.5) WITHIN GROUP (
             ORDER BY abs(2*buy_volume - volume) / volume)
             FROM ohlcv WHERE symbol=$1 AND interval='4hour' AND volume > 0
               AND ts + interval '4 hours' <= $2) AS effort_scale
        """,
        symbol,
        as_of,
    )
    funding_sample = [
        as_float(r["fr_avg"])
        for r in await conn.fetch(
            "SELECT fr_avg FROM daily_session_agg WHERE symbol=$1 AND fr_avg IS NOT NULL "
            "ORDER BY session_date DESC LIMIT 365",
            symbol,
        )
    ]
    baseline = {
        "median_abs_cvd_spot": as_float(baseline_row["median_abs_cvd_spot"])
        if baseline_row
        else None,
        "median_bar_volume_usd": as_float(baseline_row["median_bar_volume_usd"])
        if baseline_row
        else None,
        "effort_scale": as_float(baseline_row["effort_scale"]) if baseline_row else None,
        "funding_sample": [f for f in funding_sample if f is not None],
    }

    # Dos pasos por el mismo nivel con semanas de por medio son episodios distintos y
    # merecen veredictos distintos: una zona no tiene un unico caracter durante meses.
    visits: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for row in bars:
        item = dict(row)
        if current and (item["ts"] - current[-1]["ts"]).total_seconds() > VISIT_GAP_DAYS * 86400:
            visits.append(current)
            current = []
        current.append(item)
    if current:
        visits.append(current)

    results: list[dict[str, Any]] = []
    for visit_bars in visits:
        start_date = visit_bars[0]["ts"].date()
        end_date = visit_bars[-1]["ts"].date()
        session = await conn.fetchrow(
            """
            SELECT CASE WHEN COUNT(cvd_spot_usd)=COUNT(*) THEN SUM(cvd_spot_usd) END AS cvd_spot, COUNT(*)::int AS n,
                   (array_agg(oi_close ORDER BY session_date)
                      FILTER (WHERE oi_close IS NOT NULL))[1] AS oi_first,
                   (array_agg(oi_close ORDER BY session_date DESC)
                      FILTER (WHERE oi_close IS NOT NULL))[1] AS oi_last,
                   AVG(fr_avg) AS fr
            FROM daily_session_agg
            WHERE symbol=$1 AND session_date BETWEEN $2 AND $3
            """,
            symbol,
            start_date,
            end_date,
        )
        visit = {
            "bars": visit_bars,
            "from": start_date,
            "to": end_date,
            "sessions": {
                "count": int(session["n"] or 0) if session else 0,
                "cvd_spot_usd": as_float(session["cvd_spot"]) if session else None,
                "oi_first": as_float(session["oi_first"]) if session else None,
                "oi_last": as_float(session["oi_last"]) if session else None,
                "funding_avg": as_float(session["fr"]) if session else None,
            },
        }
        results.append(zone_character_read(visit, baseline))

    scored = [r for r in results if r.get("available")]
    characters = {r["character"] for r in scored}
    return {
        "symbol": symbol,
        "zone": {"low": zone_low, "high": zone_high},
        "lookback_days": days,
        "visits": results,
        "visit_count": len(results),
        "scored_visits": len(scored),
        "summary": (
            "La zona no tiene un caracter unico: cada visita se juzga por separado."
            if len(characters) > 1
            else (next(iter(characters)) if characters else "sin_datos")
        ),
        "sources": {
            "delta_futuros": "ohlcv 4h (buy_volume real, ~300 d)",
            "cvd_spot": "daily_session_agg (sesion NYSE, 392 sesiones)",
            "no_disponible": [
                "libro de ordenes (6 h de retencion)",
                "flujo a nivel de trade (14 d)",
                "liquidaciones historicas (4 de 185 sesiones del rango)",
            ],
        },
    }


async def range_validate(
    conn: asyncpg.Connection,
    symbol: str,
    low: float,
    high: float,
    days: int = 180,
    end_days_ago: int = 0,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Valida si un tramo es un rango con cinco tests de umbral medido.

    Usa velas diarias: un rango se juzga en sesiones, no en minutos, y `ohlcv` diario tiene
    730 dias. Las 90 sesiones anteriores al tramo sirven de referencia de volatilidad.
    Se puede acotar de dos formas: por fechas (`start_date`/`end_date`, que es como se lee un
    grafico) o por ventana movil (`days` + `end_days_ago`). Las fechas mandan si vienen ambas.
    """
    if low >= high:
        raise ValueError("low must be below high")
    as_of = datetime.now(UTC)
    if start_date is not None and end_date is not None:
        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")
        bars = [
            dict(r)
            for r in await conn.fetch(
                "SELECT ts, open, high, low, close FROM ohlcv "
                "WHERE symbol=$1 AND interval='daily' AND ts::date >= $2 AND ts::date <= $3 "
                "AND ts + interval '1 day' <= $4 ORDER BY ts",
                symbol,
                start_date,
                end_date,
                as_of,
            )
        ]
        # La referencia de volatilidad son las 90 sesiones anteriores al INICIO del tramo.
        prior = [
            dict(r)
            for r in reversed(
                await conn.fetch(
                    "SELECT ts, open, high, low, close FROM ohlcv "
                    "WHERE symbol=$1 AND interval='daily' AND ts::date < $2 "
                    "AND ts + interval '1 day' <= $3 ORDER BY ts DESC LIMIT 90",
                    symbol,
                    start_date,
                    as_of,
                )
            )
        ]
        window: dict[str, Any] = {
            "mode": "fechas",
            "start_date": str(start_date),
            "end_date": str(end_date),
        }
    else:
        start_days = days + end_days_ago
        bars = [
            dict(r)
            for r in await conn.fetch(
                "SELECT ts, open, high, low, close FROM ohlcv "
                "WHERE symbol=$1 AND interval='daily' "
                "  AND ts >= $4 - make_interval(days => $2) "
                "  AND ts <  $4 - make_interval(days => $3) "
                "  AND ts + interval '1 day' <= $4 ORDER BY ts",
                symbol,
                start_days,
                end_days_ago,
                as_of,
            )
        ]
        prior = [
            dict(r)
            for r in await conn.fetch(
                "SELECT ts, open, high, low, close FROM ohlcv "
                "WHERE symbol=$1 AND interval='daily' "
                "  AND ts <  $3 - make_interval(days => $2) "
                "  AND ts >= $3 - make_interval(days => $2 + 90) "
                "  AND ts + interval '1 day' <= $3 ORDER BY ts",
                symbol,
                start_days,
                as_of,
            )
        ]
        window = {"mode": "sesiones", "end_days_ago": end_days_ago}
    result = range_validate_read(bars, prior, low, high)
    return {
        "symbol": symbol,
        **window,
        "window_days": days,
        "from": str(bars[0]["ts"].date()) if bars else None,
        "to": str(bars[-1]["ts"].date()) if bars else None,
        "prior_bars": len(prior),
        **result,
    }


async def wyckoff_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Rango automatico reciente con lectura Wyckoff + flujo y barras para dibujarlo."""
    as_of = datetime.now(UTC)
    daily = [
        dict(row)
        for row in await conn.fetch(
            "SELECT ts,open,high,low,close,volume,buy_volume FROM ohlcv "
            "WHERE symbol=$1 AND interval='daily' AND ts + interval '1 day' <= $2 "
            "ORDER BY ts DESC LIMIT 730",
            symbol,
            as_of,
        )
    ]
    daily.reverse()
    sessions = [
        dict(row)
        for row in await conn.fetch(
            "SELECT session_date,cvd_spot_usd,oi_close,fr_avg FROM daily_session_agg "
            "WHERE symbol=$1 ORDER BY session_date DESC LIMIT 730",
            symbol,
        )
    ]
    sessions.reverse()
    return {"symbol": symbol, **wyckoff_auto_read(daily, sessions)}


async def level_breakout(
    conn: asyncpg.Connection,
    symbol: str,
    level: float,
    upward: bool,
) -> dict[str, Any]:
    """Tasa base historica de ruptura de un nivel, mas el estado del intento en curso.

    El corpus agrupa los tres simbolos porque su tasa base es homogenea (36-42% medido); con
    uno solo la muestra se queda en ~40 intentos y ningun estrato llegaria al minimo de 10.
    """
    as_of = datetime.now(UTC)
    bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for candidate in WS_SYMBOL_MAP:
        bars_by_symbol[candidate] = [
            dict(r)
            for r in await conn.fetch(
                "SELECT ts, high, low, close, volume, buy_volume FROM ohlcv "
                "WHERE symbol=$1 AND interval='4hour' AND ts + interval '4 hours' <= $2 "
                "ORDER BY ts",
                candidate,
                as_of,
            )
        ]
    subject = bars_by_symbol.get(symbol) or []
    return {"symbol": symbol, **breakout_read(bars_by_symbol, subject, level, upward)}


async def market_memory(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    as_of = datetime.now(UTC)
    rows = await conn.fetch(
        """
        SELECT ts::date AS date,open,high,low,close,
               volume*close AS volume_usd,
               (2*buy_volume-volume)*close AS cvd_futures_usd
        FROM ohlcv
        WHERE symbol=$1 AND interval='daily'
          AND ts + interval '1 day' <= $3
        ORDER BY ts DESC LIMIT $2
        """,
        symbol,
        MARKET_MEMORY_DAYS,
        as_of,
    )
    return {"symbol": symbol, **market_memory_read([dict(row) for row in reversed(rows)])}


async def horizon_structure(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Bias por horizonte DERIVADO de structure_detail (fuente unica de pivotes), para que
    structure_horizons y structure_detail nunca se contradigan."""
    det = await structure_detail(conn, symbol)
    bias_map = {"HH_HL": "alcista", "LH_LL": "bajista"}
    out = {}
    for label, d in det["horizons"].items():
        state = d.get("state")
        out[label] = {
            "group": d.get("group"),
            "structure": state,
            "bias": bias_map.get(state),
            "close": d.get("close"),
        }
    return out


async def liquidation_burst(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Liquidaciones 5m + baseline (mediana de buckets 5m en 3h) para detectar cascadas."""
    cur = await conn.fetchrow(
        "SELECT COALESCE(SUM(CASE WHEN side='long' THEN notional_usd END),0) AS long_liq,"
        " COALESCE(SUM(CASE WHEN side='short' THEN notional_usd END),0) AS short_liq,"
        " COUNT(*) AS events"
        " FROM liquidations_realtime WHERE symbol=$1 AND ts >= now()-interval '5 minutes'",
        symbol,
    )
    base = await conn.fetchval(
        """
        SELECT COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY tot), 0) FROM (
          SELECT date_bin('5 minutes', ts, '1970-01-01'::timestamptz) AS b, SUM(notional_usd) AS tot
          FROM liquidations_realtime
          WHERE symbol=$1 AND ts >= now()-interval '3 hours' AND ts < now()-interval '5 minutes'
          GROUP BY 1
        ) q
        """,
        symbol,
    )
    long_l = as_float(cur["long_liq"]) or 0.0
    short_l = as_float(cur["short_liq"]) or 0.0
    return {
        "window": "5m",
        "long_liq": long_l,
        "short_liq": short_l,
        "total": long_l + short_l,
        "events": int(cur["events"] or 0),
        "baseline_5m": as_float(base) or 0.0,
    }


# ---------------- contexto macro por percentiles (~1 anio de daily_session_agg) ----------------
# Cada metrica de la sesion mas reciente se expresa como su percentil dentro de la ventana anual.
# Percentiles extremos (>=95 / <=5) marcan regimenes que suelen preceder movimientos grandes.
_MACRO_METRICS = (
    ("cvd_fut_usd", "CVD futuros"),
    ("cvd_spot_usd", "CVD spot"),
    ("cvd_diff_usd", "CVD diff (spot-fut)"),
    ("oi_close", "Open Interest"),
    ("oi_chg_usd", "Cambio de OI"),
    ("fr_avg", "Funding"),
    ("price_chg_pct", "Retorno diario"),
)


def _pct_rank(series: list, value) -> float | None:
    """Percentil (0-100) de value dentro de series. None si no hay muestra util."""
    xs = [x for x in series if x is not None]
    if value is None or len(xs) < 20:
        return None
    below = sum(1 for x in xs if x <= value)
    return round(below / len(xs) * 100.0, 1)


def _regime(p: float | None) -> str:
    if p is None:
        return "s/d"
    if p >= 95:
        return "extremo alto"
    if p <= 5:
        return "extremo bajo"
    if p >= 80:
        return "alto"
    if p <= 20:
        return "bajo"
    return "normal"


CONDITIONAL_HORIZONS = (7, 14)
CONDITIONAL_BAND = 10.0  # +-10 puntos de percentil cuenta como "el mismo estado"
CONDITIONAL_MIN_SAMPLE = 10


def _forward_returns(closes: list, horizon: int) -> list:
    """closes en orden ascendente; devuelve el retorno % a `horizon` sesiones, o None."""
    out: list[float | None] = []
    for i in range(len(closes)):
        j = i + horizon
        a, b = closes[i], closes[j] if j < len(closes) else None
        out.append(((b / a) - 1) * 100 if (a and b and a > 0) else None)
    return out


def _conditional_outcome(
    series_asc: list, closes_asc: list, current: float | None
) -> dict[str, Any]:
    """Que paso historicamente las veces anteriores que la metrica estuvo donde esta hoy.

    Percentil plano dice "el funding esta en el 95"; no dice si eso precedio subidas o
    bajadas. Aqui se toman las sesiones cuyo percentil cayo en la misma banda y se reporta
    la distribucion empirica del retorno posterior. Es descriptivo, no predictivo.
    """
    clean = [(i, v) for i, v in enumerate(series_asc) if v is not None]
    if current is None or len(clean) < 20:
        return {}
    values = [v for _, v in clean]
    target = _pct_rank(values, current)
    if target is None:
        return {}
    matches = [
        i for i, v in clean if abs((_pct_rank(values, v) or 0.0) - target) <= CONDITIONAL_BAND
    ]
    out: dict[str, Any] = {}
    for horizon in CONDITIONAL_HORIZONS:
        fwd = _forward_returns(closes_asc, horizon)
        sample = [fwd[i] for i in matches if i < len(fwd) and fwd[i] is not None]
        if len(sample) < CONDITIONAL_MIN_SAMPLE:
            out[f"h{horizon}"] = {"n": len(sample), "insufficient_sample": True}
            continue
        sample.sort()
        mid = len(sample) // 2
        median = sample[mid] if len(sample) % 2 else (sample[mid - 1] + sample[mid]) / 2
        out[f"h{horizon}"] = {
            "n": len(sample),
            "median_pct": round(median, 2),
            "mean_pct": round(sum(sample) / len(sample), 2),
            "positive_pct": round(100.0 * sum(1 for x in sample if x > 0) / len(sample), 1),
            "worst_pct": round(sample[0], 2),
            "best_pct": round(sample[-1], 2),
        }
    return out


async def macro_context(conn: asyncpg.Connection, symbol: str, days: int = 365) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        SELECT session_date, cvd_fut_usd, cvd_spot_usd, cvd_diff_usd, oi_close, oi_chg_usd,
               fr_avg, price_chg_pct, price_close
        FROM daily_session_agg WHERE symbol=$1 ORDER BY session_date DESC LIMIT $2
        """,
        symbol,
        days,
    )
    if not rows:
        return {"symbol": symbol, "sessions": 0, "metrics": [], "tension": 0}
    latest = rows[0]
    asc = list(reversed(rows))
    closes_asc = [as_float(r["price_close"]) for r in asc]
    metrics = []
    tension = 0
    for key, label in _MACRO_METRICS:
        series = [as_float(r[key]) for r in rows]
        cur = as_float(latest[key])
        p = _pct_rank(series, cur)
        reg = _regime(p)
        if reg.startswith("extremo"):
            tension += 1
        entry = {"key": key, "label": label, "value": cur, "percentile": p, "regime": reg}
        # Solo en regimenes no-normales: condicionar a una banda centrada en el percentil 50
        # devuelve practicamente la distribucion incondicional, asi que no aporta informacion
        # y si ocupa payload (el bundle ya ronda los 37k tokens).
        if reg not in ("normal", "s/d"):
            entry["conditional"] = _conditional_outcome(
                [as_float(r[key]) for r in asc], closes_asc, cur
            )
        metrics.append(entry)
    return {
        "symbol": symbol,
        "sessions": len(rows),
        "session_date": str(latest["session_date"]),
        "metrics": metrics,
        "tension": tension,
        "conditional_note": (
            f"'conditional' = retorno posterior en las sesiones historicas cuyo percentil "
            f"cayo a +-{CONDITIONAL_BAND:.0f} puntos del actual (minimo "
            f"{CONDITIONAL_MIN_SAMPLE} muestras). Solo se incluye cuando el regimen NO es "
            f"normal: en el centro de la distribucion equivale a la incondicional y no "
            f"informa. Es la distribucion observada, NO una prediccion: la muestra es de "
            f"~1 anio y mayormente de un solo regimen."
        ),
    }


# ---------------- divergencias sostenidas precio vs CVD spot acumulado ----------------
# Usa cvd_spot_usd a proposito, NO cvd_diff_usd: el diff resta el CVD de futuros de
# Binance (simbolo .A) al spot de Binance+Bybit. El perp mueve ~10x el spot ($9.7B vs
# $1.0B/24h en BTC), asi que el signo del diff lo manda casi siempre la pata de futuros.
# El CVD spot es una sola serie limpia, de un solo universo de venues.
_DIVERGENCE_WINDOWS = (
    ("1d", 1),
    ("2d", 2),
    ("3d", 3),
    ("6d", 6),
    ("9d", 9),
    ("2s", 14),
    ("4s", 28),
    ("6s", 42),
)
# Por debajo de esto no hay puntos suficientes para una regresion, asi que la ventana se
# resuelve comparando extremos. Se declara en `method` para no mezclar dos cosas distintas.
MIN_SLOPE_SESSIONS = 5
# 1-3 sesiones es una observacion puntual, no una divergencia sostenida. Se calculan igual
# porque sirven de termometro corto, pero el resumen solo cuenta las ventanas largas.
SUSTAINED_MIN_SESSIONS = 6
# Comparar extremos hace que cualquier movimiento cruce el cero: BTC llego a marcar
# divergencia con el precio en +0.0003%. Por debajo de esto no hay nada que divergir.
MIN_ENDPOINT_MOVE_PCT = 0.1


def _slope_pct(values: list) -> float | None:
    """Pendiente por minimos cuadrados, normalizada por la escala de la serie."""
    clean = [v for v in values if v is not None]
    n = len(clean)
    if n < 5:
        return None
    mean_x = (n - 1) / 2.0
    mean_y = sum(clean) / n
    denom = sum((i - mean_x) ** 2 for i in range(n))
    if denom <= 0:
        return None
    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(clean)) / denom
    scale = max(abs(max(clean)), abs(min(clean)), 1e-9)
    return slope / scale * 100.0


_INTRADAY_WINDOWS = (
    ("9m", 540),
    ("15m", 900),
    ("1h", 3600),
    ("2h", 7200),
    ("4h", 14400),
    ("8h", 28800),
    ("16h", 57600),
)
# Un movimiento de precio dentro del ruido propio de la ventana no es una divergencia.
# Se compara contra el recorrido esperado de un paseo aleatorio con la volatilidad
# observada en esa misma ventana (sigma_1min * sqrt(n)), asi la barrera se auto-escala:
# lo que es ruido en 9m no lo es en 16h, y no hace falta un umbral fijo por horizonte.
INTRADAY_NOISE_FACTOR = 0.5


def _return_stdev_pct(closes: list) -> float | None:
    rets = []
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        if a and b and a > 0 and b > 0:
            rets.append((b / a - 1) * 100.0)
    if len(rets) < 3:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return var**0.5


async def _intraday_divergences(
    conn: asyncpg.Connection, symbol: str, ws_symbol: str
) -> dict[str, Any]:
    """Mismo contraste que en sesiones, pero sobre velas de 1 minuto.

    Precio desde ohlcv (lag ~60 s) y CVD spot desde spot_trades_agg (lag ~240 s: el
    colector espera la ventana de trades tardios). Se ancla al ultimo minuto que tiene
    AMBAS series en vez de a now(), porque si no la parte final de cada ventana seria un
    hueco disfrazado de flujo cero, que es justo el error que ya nos costo caro.
    """
    rows = await conn.fetch(
        """
        WITH px AS (
          SELECT ts, close FROM ohlcv
          WHERE symbol=$1 AND interval='1min' AND ts >= now()-interval '17 hours'
        ), sp AS (
          SELECT ts, buy_vol_usd-sell_vol_usd AS delta FROM spot_trades_agg
          WHERE symbol=$2 AND exchange='combined' AND venue_count=2 AND interval='1min'
            AND ts >= now()-interval '17 hours'
        ), bound AS (
          SELECT LEAST((SELECT MAX(ts) FROM px),(SELECT MAX(ts) FROM sp)) AS complete_until
        )
        SELECT px.ts, px.close, sp.delta,
               EXTRACT(EPOCH FROM now()-bound.complete_until)::float8 AS lag_seconds
        FROM px JOIN sp USING(ts), bound
        WHERE px.ts <= bound.complete_until
        ORDER BY px.ts
        """,
        symbol,
        ws_symbol,
    )
    if not rows:
        return {"available": False, "windows": {}}
    lag = as_float(rows[0]["lag_seconds"])
    anchor = rows[-1]["ts"]
    windows: dict[str, Any] = {}
    for label, secs in _INTRADAY_WINDOWS:
        start = anchor - timedelta(seconds=secs)
        chunk = [r for r in rows if r["ts"] >= start]
        closes = [as_float(r["close"]) for r in chunk]
        if len(chunk) < MIN_SLOPE_SESSIONS or not closes[0] or not closes[-1]:
            windows[label] = {
                "available": False,
                "bars": len(chunk),
                "required": MIN_SLOPE_SESSIONS,
            }
            continue
        cum, running = [], 0.0
        for r in chunk:
            running += as_float(r["delta"]) or 0.0
            cum.append(running)
        px_change = (closes[-1] / closes[0] - 1) * 100.0
        px_slope, cvd_slope = _slope_pct(closes), _slope_pct(cum)
        sigma = _return_stdev_pct(closes)
        noise = (sigma * math.sqrt(max(len(closes) - 1, 1))) if sigma else 0.0
        significant = abs(px_change) >= INTRADAY_NOISE_FACTOR * noise
        state, reading = "sin_divergencia", None
        if significant and px_slope is not None and cvd_slope is not None:
            if px_slope > 0 and cvd_slope < 0:
                state = "bajista"
                reading = (
                    "el precio sube mientras el CVD spot acumulado cae: la subida no "
                    "la sostiene compra spot"
                )
            elif px_slope < 0 and cvd_slope > 0:
                state = "alcista"
                reading = (
                    "el precio baja mientras el CVD spot acumulado sube: hay compra "
                    "spot absorbiendo la caida"
                )
        # El lag es fijo (~4 min); en 9m se come media ventana y en 16h es irrelevante.
        share = (lag / secs) if (lag and secs) else 0.0
        freshness = "fresh" if share <= 0.1 else ("degraded" if share <= 0.35 else "stale")
        windows[label] = {
            "available": True,
            "bars": len(chunk),
            "window_seconds": secs,
            "price_change_pct": round(px_change, 3),
            "cvd_spot_change_usd": round(cum[-1], 2),
            "price_slope": round(px_slope, 3) if px_slope is not None else None,
            "cvd_slope": round(cvd_slope, 3) if cvd_slope is not None else None,
            "noise_threshold_pct": round(INTRADAY_NOISE_FACTOR * noise, 3),
            "above_noise": significant,
            "divergence": state,
            "reading": reading,
            "lag_seconds": round(lag, 1) if lag is not None else None,
            "freshness": freshness,
        }
    active = [
        lab
        for lab, w in windows.items()
        if w.get("divergence") in ("alcista", "bajista") and w.get("freshness") != "stale"
    ]
    biases = {windows[lab]["divergence"] for lab in active}
    summary = "sin_divergencia"
    if len(biases) == 1 and active:
        summary = f"{biases.pop()}_en_{len(active)}_ventanas"
    elif active:
        summary = "mixta"
    return {
        "available": True,
        "bars": len(rows),
        "anchored_at": anchor.isoformat(),
        "lag_seconds": round(lag, 1) if lag is not None else None,
        "windows": windows,
        "summary": summary,
        "windows_confirming": len(active),
        "note": "velas de 1 min; precio de ohlcv (Binance) y CVD spot de "
        "spot_trades_agg (Binance+Bybit). Anclado al ultimo minuto con ambas series, "
        "no a now(). freshness compara el lag contra el tamano de la ventana: en 9m "
        "cuatro minutos de retraso pesan, en 16h no. Para flujo mas fresco que esto "
        "usa la matriz delta (15s-8h, desde las tablas realtime).",
    }


async def divergence_scan(
    conn: asyncpg.Connection, symbol: str, *, include_intraday: bool = True
) -> dict[str, Any]:
    """Precio subiendo mientras el CVD spot acumulado baja (o al reves), sostenido.

    Una sesion suelta no dice nada; lo que informa es que la discrepancia aguante semanas.

    include_intraday se apaga en los perfiles de IA baratos: el bloque intradia cuesta
    ~1.9k tokens y el modelo ya recibe delta_matrix y cvd_matrix para ese horizonte.
    """
    intraday = (
        await _intraday_divergences(conn, symbol, WS_SYMBOL_MAP[symbol])
        if include_intraday
        else {"available": False, "windows": {}, "omitted": "perfil sin bloque intradia"}
    )
    rows = await conn.fetch(
        "SELECT session_date, price_close, cvd_spot_usd FROM daily_session_agg "
        "WHERE symbol=$1 ORDER BY session_date DESC LIMIT 90",
        symbol,
    )
    asc = list(reversed(rows))
    if len(asc) < 2:
        return {"symbol": symbol, "available": False, "sessions": len(asc), "intraday": intraday}
    closes = [as_float(r["price_close"]) for r in asc]
    cum, running = [], 0.0
    for r in asc:
        running += as_float(r["cvd_spot_usd"]) or 0.0
        cum.append(running)

    windows: dict[str, Any] = {}
    for label, size in _DIVERGENCE_WINDOWS:
        # size sesiones de cambio necesitan size+1 cierres (el ancla y el actual).
        if len(asc) < size + 1:
            windows[label] = {"available": False, "sessions": len(asc), "required": size + 1}
            continue
        first_px, last_px = closes[-size - 1], closes[-1]
        px_change = ((last_px / first_px - 1) * 100) if (first_px and last_px) else None
        cvd_change = cum[-1] - cum[-size - 1]
        if size >= MIN_SLOPE_SESSIONS:
            px_signal, cvd_signal = _slope_pct(closes[-size:]), _slope_pct(cum[-size:])
            method = "pendiente"
        else:
            # Con 1-3 sesiones no hay regresion posible: se compara extremo contra extremo,
            # con banda muerta para que un movimiento de ruido no marque divergencia.
            px_signal, cvd_signal, method = px_change, cvd_change, "cambio_extremos"
            if px_signal is not None and abs(px_signal) < MIN_ENDPOINT_MOVE_PCT:
                px_signal = 0.0
        sustained = size >= SUSTAINED_MIN_SESSIONS
        state, reading = "sin_divergencia", None
        if px_signal is not None and cvd_signal is not None:
            if px_signal > 0 and cvd_signal < 0:
                state = "bajista"
                reading = (
                    "el precio sube mientras el CVD spot acumulado cae: la subida no "
                    "la sostiene compra spot"
                )
            elif px_signal < 0 and cvd_signal > 0:
                state = "alcista"
                reading = (
                    "el precio baja mientras el CVD spot acumulado sube: hay compra "
                    "spot absorbiendo la caida"
                )
        if reading and not sustained:
            reading += " (ventana corta: observacion puntual, no divergencia sostenida)"
        windows[label] = {
            "available": True,
            "sessions": size,
            "sustained": sustained,
            "method": method,
            "price_change_pct": round(px_change, 2) if px_change is not None else None,
            "cvd_spot_change_usd": round(cvd_change, 2),
            "price_slope": round(px_signal, 3)
            if (method == "pendiente" and px_signal is not None)
            else None,
            "cvd_slope": round(cvd_signal, 3)
            if (method == "pendiente" and cvd_signal is not None)
            else None,
            "divergence": state,
            "reading": reading,
        }
    # El resumen solo mira ventanas sostenidas: que el precio y el flujo discrepen un dia
    # es ruido normal, lo que informa es que la discrepancia aguante semanas.
    sustained_windows = [
        lab for lab, w in windows.items() if w.get("available") and w.get("sustained")
    ]
    active = [
        lab for lab in sustained_windows if windows[lab]["divergence"] in ("alcista", "bajista")
    ]
    biases = {windows[lab]["divergence"] for lab in active}
    summary = "sin_divergencia"
    if len(biases) == 1 and active:
        summary = f"{biases.pop()}_en_{len(active)}_de_{len(sustained_windows)}_ventanas"
    elif active:
        summary = "mixta"
    return {
        "symbol": symbol,
        "available": True,
        "sessions": len(asc),
        "windows": windows,
        "summary": summary,
        "windows_confirming": len(active),
        "sustained_windows_evaluated": len(sustained_windows),
        "intraday": intraday,
        "note": "precio vs CVD spot ACUMULADO (solo Binance+Bybit) sobre sesiones NYSE. "
        "Se usa cvd_spot y no cvd_diff porque el diff lo domina la pata de futuros. "
        f"Ventanas de <{MIN_SLOPE_SESSIONS} sesiones se resuelven por cambio entre "
        f"extremos (method) y las de <{SUSTAINED_MIN_SESSIONS} no cuentan para el "
        "resumen. Una divergencia no es una senal de entrada: indica que el "
        "movimiento no esta respaldado por flujo spot, no cuando gira.",
    }


# ---------------- Fase 1: pivotes verificables + matriz CVD por-venue ----------------
def _swings(highs, lows, times, k):
    """Devuelve (swing_highs, swing_lows) como listas (timestamp, precio), fractal ancho k."""
    sh, sl = [], []
    n = len(highs)
    for i in range(k, n - k):
        seg_h = [x for x in highs[i - k : i + k + 1] if x is not None]
        seg_l = [x for x in lows[i - k : i + k + 1] if x is not None]
        if highs[i] is not None and seg_h and highs[i] == max(seg_h):
            sh.append((times[i], highs[i]))
        if lows[i] is not None and seg_l and lows[i] == min(seg_l):
            sl.append((times[i], lows[i]))
    return sh, sl


def _structure_from_swings(highs, lows, times, close, k=2) -> dict[str, Any]:
    """Estructura auditable: swings, estado, BOS/CHoCH e invalidación con distancias %."""
    sh, sl = _swings(highs, lows, times, k)

    def pt(x):
        return {"timestamp": x[0], "price": round(x[1], 6)} if x else None

    last_sh = sh[-1] if sh else None
    prev_sh = sh[-2] if len(sh) >= 2 else None
    last_sl = sl[-1] if sl else None
    prev_sl = sl[-2] if len(sl) >= 2 else None
    state = None
    if last_sh and prev_sh and last_sl and prev_sl:
        hh = last_sh[1] > prev_sh[1]
        hl = last_sl[1] > prev_sl[1]
        state = "HH_HL" if (hh and hl) else ("LH_LL" if (not hh and not hl) else "mixed")
    # niveles: en alcista el BOS es romper el ultimo high (continuacion), CHoCH/invalidacion romper
    # el ultimo low; en bajista al reves. Mixed usa high/low como referencia neutral.
    bos = choch = None
    if state == "HH_HL":
        bos = last_sh[1] if last_sh else None
        choch = last_sl[1] if last_sl else None
    elif state == "LH_LL":
        bos = last_sl[1] if last_sl else None
        choch = last_sh[1] if last_sh else None
    elif state == "mixed":
        bos = last_sh[1] if last_sh else None
        choch = last_sl[1] if last_sl else None
    inval = choch  # el nivel cuyo rompimiento cambia el caracter es la invalidacion del sesgo

    def dist(level):
        return round((close / level - 1) * 100, 3) if (level and close) else None

    return {
        "state": state,
        "last_swing_high": pt(last_sh),
        "previous_swing_high": pt(prev_sh),
        "last_swing_low": pt(last_sl),
        "previous_swing_low": pt(prev_sl),
        "bos_level": bos,
        "choch_level": choch,
        "invalidation_level": inval,
        "distance_to_bos_pct": dist(bos),
        "distance_to_invalidation_pct": dist(inval),
        "close": close,
        "swing_count": {"highs": len(sh), "lows": len(sl)},
    }


def _dsr(rows_desc, n):
    """Downsample de filas (mas reciente primero) tomando cada n-esima, anclado al final."""
    r = list(reversed(rows_desc))
    if n <= 1:
        return r
    return [r[i] for i in range(len(r) - 1, -1, -n)][::-1]


async def structure_detail(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Estructura por horizonte con pivotes reales (reemplaza la etiqueta HH/HL por datos)."""
    out: dict[str, Any] = {}
    for label, unit, group in _ALERT_HORIZONS:
        if group == "med":
            bars = await _resample_highs_lows(conn, symbol, unit, 120)
            highs = [as_float(b["high"]) for b in bars]
            lows = [as_float(b["low"]) for b in bars]
            times = [b["bucket"].isoformat() for b in bars]
            close = as_float(bars[-1]["close"]) if bars else None
            det = _structure_from_swings(highs, lows, times, close, k=2)
        else:
            rows = await conn.fetch(
                "SELECT session_date, price_close FROM daily_session_agg WHERE symbol=$1 "
                "ORDER BY session_date DESC LIMIT 400",
                symbol,
            )
            ds = _dsr(rows, unit)
            closes = [as_float(r["price_close"]) for r in ds]
            times = [str(r["session_date"]) for r in ds]
            close = closes[-1] if closes else None
            det = _structure_from_swings(closes, closes, times, close, k=2)
        det["timeframe"] = label
        det["group"] = group
        out[label] = det
    return {"symbol": symbol, "horizons": out}


_CONFIRMATION_TF: dict[str, tuple[str, int]] = {
    # Timeframe de CONFIRMACION de ruptura por perfil (spec 1.2). Intradia usa 15 m, coherente
    # con la definicion del sistema ("Cierre 15m sobre ..." en price_barrier_read); swing sube a
    # 4 h, la capa de confirmacion de su perfil.
    "intradia": ("15m", 900),
    "swing": ("4h", 14400),
}


async def setup_confirmation_bundle(
    conn: asyncpg.Connection, symbol: str, profile: str
) -> dict[str, Any]:
    """Velas CERRADAS del timeframe de confirmacion + pivotes + ATR para `setup_observables`.

    Reutiliza `_resample_highs_lows`, `_swings` y `_atr` (no duplica logica) y EXCLUYE la vela
    aun abierta: su cierre todavia puede cambiar, y usarla como cierre seria justo lo que la
    especificacion prohibe. `bars` viaja con `ts` en segundos epoch para que el helper puro
    detecte huecos por la separacion entre velas.
    """
    tf_label, secs = _CONFIRMATION_TF.get(profile, _CONFIRMATION_TF["intradia"])
    # 15 m se remuestrea desde 5min (~8-9 dias, sobra para la confirmacion); 4 h es nativo.
    source = "5min" if secs < 14400 else "4hour"
    raw = await _resample_highs_lows(conn, symbol, secs, 400, source)
    now = datetime.now(UTC)
    now_epoch = now.timestamp()
    bars: list[dict[str, Any]] = []
    for r in raw:
        bucket = r.get("bucket")
        if bucket is None:
            continue
        start = bucket.timestamp()
        if start + secs > now_epoch:
            # Vela AUN ABIERTA: no cuenta como cierre.
            continue
        close = as_float(r.get("close"))
        if close is None:
            continue
        bars.append(
            {
                "ts": int(start),
                "open": None,
                "high": as_float(r.get("high")),
                "low": as_float(r.get("low")),
                "close": close,
            }
        )
    highs_seq = [b["high"] for b in bars]
    lows_seq = [b["low"] for b in bars]
    times_seq = [b["ts"] for b in bars]
    sh, sl = _swings(highs_seq, lows_seq, times_seq, k=2)
    atr = _atr(bars) if len(bars) >= 2 else None
    return {
        "timeframe": tf_label,
        "bar_seconds": secs,
        "source": f"ohlcv:{tf_label} (resample de {source}, velas cerradas)",
        "as_of": now.isoformat(),
        "bars": bars,
        "pivots": {"highs": sh, "lows": sl},
        "atr": atr,
        "sample_count": len(bars),
    }


_CVD_WINDOWS = (
    ("1m", 60),
    ("5m", 300),
    ("15m", 900),
    ("30m", 1800),
    ("1h", 3600),
    ("4h", 14400),
    ("8h", 28800),
    ("24h", 86400),
    ("3d", 259200),
    ("7d", 604800),
)


async def spot_flow_windows(
    conn: asyncpg.Connection,
    symbol: str,
    windows: tuple[tuple[str, int], ...] | list[tuple[str, int]],
) -> dict[str, dict[str, dict[str, Any]]]:
    """Rolling spot flow with a complete 1-minute history plus a non-overlapping live tail."""
    labels = [label for label, _ in windows]
    seconds = [value for _, value in windows]
    rows = await conn.fetch(
        """
        WITH requested AS (
          SELECT * FROM unnest($2::text[], $3::int[]) AS r(horizon, seconds)
        ), exchanges(exchange) AS (
          VALUES ('combined'),('binance'),('bybit')
        ), rt_span AS (
          SELECT exchange,MIN(ts) AS lo,MAX(ts) AS hi
          FROM spot_trades_realtime
          WHERE symbol=$1 AND exchange IN ('combined','binance','bybit')
            AND (exchange <> 'combined' OR venue_count=2)
          GROUP BY exchange
        ), agg_span AS (
          SELECT exchange,MIN(ts) AS lo,MAX(ts) AS hi
          FROM spot_trades_agg
          WHERE symbol=$1 AND exchange IN ('combined','binance','bybit') AND interval='1min'
            AND (exchange <> 'combined' OR venue_count=2)
          GROUP BY exchange
        ), choice AS (
          SELECT r.horizon,r.seconds,e.exchange,
                 now()-(r.seconds*interval '1 second') AS window_start,
                 rt.lo AS rt_lo,rt.hi AS rt_hi,agg.lo AS agg_lo,agg.hi AS agg_hi,
                 COALESCE(
                   rt.lo <= now()-(r.seconds*interval '1 second')
                   AND rt.hi >= now()-interval '30 seconds',false
                 ) AS realtime_complete
          FROM requested r CROSS JOIN exchanges e
          LEFT JOIN rt_span rt USING(exchange)
          LEFT JOIN agg_span agg USING(exchange)
        ), parts AS (
          SELECT c.horizon,c.exchange,
                 SUM(t.buy_vol_usd-t.sell_vol_usd) AS delta,
                 SUM(t.buy_vol_usd+t.sell_vol_usd) AS volume,
                 SUM(t.trade_count) AS trades,COUNT(*)::bigint AS rows
          FROM choice c
          JOIN spot_trades_realtime t ON t.symbol=$1 AND t.exchange=c.exchange
          WHERE c.realtime_complete
            AND (c.exchange <> 'combined' OR t.venue_count=2)
            AND t.ts >= c.window_start
          GROUP BY c.horizon,c.exchange
          UNION ALL
          SELECT c.horizon,c.exchange,
                 SUM(t.buy_vol_usd-t.sell_vol_usd) AS delta,
                 SUM(t.buy_vol_usd+t.sell_vol_usd) AS volume,
                 SUM(t.trade_count) AS trades,COUNT(*)::bigint AS rows
          FROM choice c
          JOIN spot_trades_agg t ON t.symbol=$1 AND t.exchange=c.exchange AND t.interval='1min'
          WHERE NOT c.realtime_complete
            AND (c.exchange <> 'combined' OR t.venue_count=2)
            AND t.ts >= c.window_start AND t.ts <= c.agg_hi
          GROUP BY c.horizon,c.exchange
          UNION ALL
          SELECT c.horizon,c.exchange,
                 SUM(t.buy_vol_usd-t.sell_vol_usd) AS delta,
                 SUM(t.buy_vol_usd+t.sell_vol_usd) AS volume,
                 SUM(t.trade_count) AS trades,COUNT(*)::bigint AS rows
          FROM choice c
          JOIN spot_trades_realtime t ON t.symbol=$1 AND t.exchange=c.exchange
          WHERE NOT c.realtime_complete
            AND (c.exchange <> 'combined' OR t.venue_count=2)
            AND t.ts >= GREATEST(
              c.window_start,COALESCE(c.agg_hi+interval '1 minute',c.window_start)
            )
          GROUP BY c.horizon,c.exchange
        )
        SELECT c.horizon,c.seconds,c.exchange,
               CASE WHEN COALESCE(SUM(p.rows),0)>0 THEN SUM(p.delta) END AS delta,
               CASE WHEN COALESCE(SUM(p.rows),0)>0 THEN SUM(p.volume) END AS volume,
               CASE WHEN COALESCE(SUM(p.rows),0)>0 THEN SUM(p.trades) END AS trades,
               COALESCE(SUM(p.rows),0)::bigint AS source_rows,
               CASE
                 WHEN c.realtime_complete THEN 'realtime'
                 WHEN c.agg_hi IS NOT NULL AND c.rt_hi IS NOT NULL THEN 'agg_1min+realtime'
                 WHEN c.agg_hi IS NOT NULL THEN 'agg_1min_partial'
                 WHEN c.rt_hi IS NOT NULL THEN 'realtime_partial'
                 ELSE 'unavailable'
               END AS source,
               CASE
                 WHEN c.realtime_complete THEN true
                 ELSE COALESCE(
                   c.agg_lo <= c.window_start
                   AND c.agg_hi IS NOT NULL
                   AND c.rt_hi >= now()-interval '30 seconds'
                   AND c.rt_lo <= c.agg_hi+interval '1 minute',false
                 )
               END AS complete,
               CASE WHEN c.rt_hi IS NOT NULL
                    THEN EXTRACT(EPOCH FROM now()-c.rt_hi)::float8 END AS end_gap_seconds,
               CASE WHEN c.realtime_complete THEN 1 ELSE 60 END AS precision_seconds
        FROM choice c
        LEFT JOIN parts p ON p.horizon=c.horizon AND p.exchange=c.exchange
        GROUP BY c.horizon,c.seconds,c.exchange,c.window_start,c.rt_lo,c.rt_hi,
                 c.agg_lo,c.agg_hi,c.realtime_complete
        ORDER BY array_position($2::text[],c.horizon),c.exchange
        """,
        symbol,
        labels,
        seconds,
    )
    now = datetime.now(UTC)
    requirements: list[GapRequirement] = []
    for label, window_seconds in windows:
        start = now - timedelta(seconds=window_seconds)
        for exchange in ("binance", "bybit"):
            requirements.append(
                GapRequirement(
                    f"{label}:{exchange}", "spot_trades", exchange, "spot", symbol,
                    start, now,
                )
            )
        for exchange in ("binance", "bybit", "combined"):
            requirements.append(
                GapRequirement(
                    f"{label}:combined", "spot_trades", exchange, "spot", symbol,
                    start, now,
                )
            )
    blocked = await blocking_requirement_keys(conn, requirements)
    result: dict[str, dict[str, dict[str, Any]]] = {label: {} for label in labels}
    for row in rows:
        item = dict(row)
        gap_key = f"{item['horizon']}:{item['exchange']}"
        explicit_gap = gap_key in blocked
        complete = bool(item.get("complete")) and not explicit_gap
        item["complete"] = complete
        if explicit_gap:
            item["delta"] = None
            item["volume"] = None
            item["trades"] = None
            item["gap_reason"] = "data_gap"
        item["coverage_status"] = (
            "complete"
            if complete
            else ("partial" if int(item.get("source_rows") or 0) else "unavailable")
        )
        item["delta"] = as_float(item.get("delta"))
        item["volume"] = as_float(item.get("volume"))
        item["trades"] = int(item["trades"]) if item.get("trades") is not None else None
        item["end_gap_seconds"] = (
            round(as_float(item.get("end_gap_seconds")) or 0.0, 1)
            if item.get("end_gap_seconds") is not None
            else None
        )
        result[str(item["horizon"])][str(item["exchange"])] = item
    return result


async def _cvd_src(conn: asyncpg.Connection, table: str, symbol: str, is_agg: bool):
    """Delta por exchange y ventana desde una tabla de trades, con ts min/max (cobertura+end_gap)."""
    parts = []
    for lab, sec in _CVD_WINDOWS:
        parts.append(
            f"SUM(CASE WHEN ts >= now()-interval '{sec} seconds' THEN d ELSE 0 END) AS w_{lab}"
        )
        parts.append(f"COUNT(*) FILTER (WHERE ts >= now()-interval '{sec} seconds') AS n_{lab}")
    cols = ", ".join(parts)
    iv = "AND interval='1min' " if is_agg else ""
    rows = await conn.fetch(
        f"SELECT exchange, {cols} FROM ("
        f"  SELECT exchange, ts, buy_vol_usd - sell_vol_usd AS d FROM {table} "
        f"  WHERE symbol=$1 {iv}AND ts >= now()-interval '7 days' "
        f"    AND (exchange <> 'combined' OR venue_count=2)"
        f") s GROUP BY exchange",
        symbol,
    )
    span = await conn.fetchrow(
        f"SELECT min(ts) AS lo, max(ts) AS hi FROM {table} WHERE symbol=$1 {iv}", symbol
    )
    out = {
        r["exchange"]: {
            lab: {"delta": as_float(r[f"w_{lab}"]), "n": int(r[f"n_{lab}"] or 0)}
            for lab, _ in _CVD_WINDOWS
        }
        for r in rows
    }
    return out, (span["lo"] if span else None), (span["hi"] if span else None)


async def cvd_matrix(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """CVD por ventana (1m-7d) spot/fut/diff por-venue. Ventanas cortas desde *_trades_realtime
    y spot largo desde agg 1min mas una cola realtime sin solapamiento."""
    ws = WS_SYMBOL_MAP[symbol]
    now = datetime.now(UTC)
    rt_fut, rtf_lo, rtf_hi = await _cvd_src(conn, "futures_trades_realtime", symbol, False)
    spot_flows = await spot_flow_windows(conn, ws, _CVD_WINDOWS)
    futures_requirements: list[GapRequirement] = []
    for label, seconds in _CVD_WINDOWS:
        start = now - timedelta(seconds=seconds)
        for exchange in ("binance", "bybit"):
            futures_requirements.append(
                GapRequirement(
                    f"{label}:{exchange}", "futures_trades", exchange, "perpetual",
                    symbol, start, now,
                )
            )
        for exchange in ("binance", "bybit", "combined"):
            futures_requirements.append(
                GapRequirement(
                    f"{label}:combined", "futures_trades", exchange, "perpetual",
                    symbol, start, now,
                )
            )
    blocked_futures = await blocking_requirement_keys(conn, futures_requirements)

    def obs(lo):
        return (now - lo).total_seconds() if lo else 0.0

    def gap(hi):
        return round((now - hi).total_seconds(), 1) if hi else None

    def fresh(end_gap):
        if end_gap is None:
            return "unavailable"
        return "fresh" if end_gap <= 90 else ("degraded" if end_gap <= 180 else "stale")

    rtf_obs = obs(rtf_lo)

    def pick_fut(sec):
        if rtf_obs >= sec:
            return rt_fut, gap(rtf_hi), "realtime", None
        return None, None, None, "insufficient_retention"

    def get(srcmap, ex, lab):
        c = (srcmap.get(ex) or {}).get(lab) or {}
        return c.get("delta"), c.get("n") or 0

    windows = {}
    for lab, sec in _CVD_WINDOWS:
        fsrc, fgap, fsource, freason = pick_fut(sec)
        spot_window = spot_flows.get(lab) or {}
        spot_combined = spot_window.get("combined") or {}
        spot_complete = bool(spot_combined.get("complete"))
        sgap = spot_combined.get("end_gap_seconds")
        ssource = spot_combined.get("source")
        sreason = (
            "data_gap"
            if spot_combined.get("gap_reason") == "data_gap"
            else None
            if spot_complete
            else (
                "missing_recent_bucket"
                if not spot_combined.get("source_rows")
                else "partial_coverage"
            )
        )
        f = s = None
        if fsrc is not None:
            fd, fn = get(fsrc, "combined", lab)
            f = fd if fn > 0 and f"{lab}:combined" not in blocked_futures else None
            freason = (
                "data_gap"
                if f"{lab}:combined" in blocked_futures
                else ("missing_recent_bucket" if fn == 0 else None)
            )
        if spot_complete and spot_combined.get("source_rows"):
            s = as_float(spot_combined.get("delta"))
        by_venue = {}
        for v in ("binance", "bybit"):
            fv, fvn = get(fsrc, v, lab) if fsrc is not None else (None, 0)
            spot_venue = spot_window.get(v) or {}
            sv = as_float(spot_venue.get("delta")) if spot_venue.get("complete") else None
            by_venue[v] = {
                "spot": sv,
                "futures": fv if fvn > 0 and f"{lab}:{v}" not in blocked_futures else None,
            }
        windows[lab] = {
            "window": lab,
            "window_seconds": sec,
            "spot": s,
            "futures": f,
            "diff_spot_futures": (s - f) if (s is not None and f is not None) else None,
            "by_venue": by_venue,
            "spot_status": {
                "available": s is not None,
                "source": ssource,
                "reason": sreason,
                "end_gap_seconds": sgap if s is not None else None,
                "freshness": fresh(sgap) if s is not None else "unavailable",
                "precision_seconds": spot_combined.get("precision_seconds"),
            },
            "futures_status": {
                "available": f is not None,
                "source": fsource,
                "reason": freason,
                "end_gap_seconds": fgap if f is not None else None,
                "freshness": fresh(fgap) if f is not None else "unavailable",
            },
        }
    return {
        "symbol": symbol,
        "windows": windows,
        "window_meta": {
            "window_type": "rolling",
            "reset_timezone": "UTC",
            "venues": ["binance", "bybit"],
            "definition": "delta = SUM(buy_vol_usd - sell_vol_usd), USD",
            "sources": "spot usa realtime cuando cubre la ventana; si no, agg 1min historico + cola realtime sin solapamiento. Futures usa realtime (~12h)",
            "freshness_rule": "end_gap<=90s fresh, <=180 degraded, >180 stale",
            "null_reasons": "insufficient_retention o missing_recent_bucket; null != flujo balanceado",
        },
    }


# ---------------- Fase 2: contexto de OI y de volatilidad ----------------
async def _closes_1min(conn: asyncpg.Connection, symbol: str, seconds: int) -> list:
    rows = await conn.fetch(
        "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' "
        "AND ts >= now()-($2::int * interval '1 second') ORDER BY ts",
        symbol,
        seconds,
    )
    return [as_float(r["close"]) for r in rows]


def _tr_series(bars: list) -> list:
    trs = []
    for i in range(1, len(bars)):
        hi, lo = as_float(bars[i]["high"]), as_float(bars[i]["low"])
        pc = as_float(bars[i - 1]["close"])
        if None in (hi, lo, pc):
            continue
        trs.append(max(hi - lo, abs(hi - pc), abs(lo - pc)))
    return trs


def _atr(bars: list, n: int = 14):
    trs = _tr_series(bars)
    if not trs:
        return None
    tail = trs[-n:]
    return sum(tail) / len(tail)


def _realized_vol(closes: list):
    """Volatilidad realizada anualizada (%), sobre retornos log de velas 1min, cripto 24/7."""
    rets = []
    for i in range(1, len(closes)):
        a, b = closes[i - 1], closes[i]
        if a and b and a > 0 and b > 0:
            rets.append(math.log(b / a))
    if len(rets) < 2:
        return None
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return (var**0.5) * math.sqrt(525600.0) * 100.0


def _oi_quadrant(px_chg, oi_chg):
    """Interpretacion probable (no certeza: cada contrato nuevo tiene un long y un short)."""
    if px_chg is None or oi_chg is None:
        return None
    up_p, up_oi = px_chg > 0, oi_chg > 0
    if up_p and up_oi:
        return "OI y precio suben: creacion de posiciones, iniciativa compradora probable"
    if up_p and not up_oi:
        return "precio sube, OI baja: cierre de shorts (short covering), rally de menor calidad"
    if not up_p and up_oi:
        return "precio baja, OI sube: creacion de posiciones, iniciativa vendedora probable"
    return "precio y OI bajan: cierre / liquidacion de longs (desapalancamiento)"


_OI_WINDOWS = (("5m", 300), ("15m", 900), ("1h", 3600), ("4h", 14400), ("24h", 86400))


async def oi_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    oi_rows = await conn.fetch(
        "SELECT oi_close FROM open_interest WHERE symbol=$1 AND interval='5min' "
        "AND ts >= now()-interval '24 hours' ORDER BY ts",
        symbol,
    )
    px = await _closes_1min(conn, symbol, 86400)
    if not oi_rows or not px:
        return {"symbol": symbol, "available": False}
    oi = [as_float(r["oi_close"]) for r in oi_rows]
    oi_latest, px_latest = oi[-1], px[-1]

    def back(series, per_bar_s, sec):
        return series[max(0, len(series) - 1 - round(sec / per_bar_s))]

    windows = {}
    for lab, sec in _OI_WINDOWS:
        oi0, px0 = back(oi, 300, sec), back(px, 60, sec)
        oi_chg = (oi_latest / oi0 - 1) * 100 if (oi0 and oi_latest) else None
        px_chg = (px_latest / px0 - 1) * 100 if (px0 and px_latest) else None
        windows[lab] = {
            "oi_change_pct": round(oi_chg, 3) if oi_chg is not None else None,
            "price_change_pct": round(px_chg, 3) if px_chg is not None else None,
            "quadrant": _oi_quadrant(px_chg, oi_chg),
        }

    daily = [
        as_float(r["oi_close"])
        for r in await conn.fetch(
            "SELECT oi_close FROM daily_session_agg WHERE symbol=$1 ORDER BY session_date DESC LIMIT 365",
            symbol,
        )
    ]
    clean = [x for x in daily if x is not None]
    z = None
    if len(clean) >= 20 and oi_latest is not None:
        mean = sum(clean) / len(clean)
        sd = (sum((x - mean) ** 2 for x in clean) / len(clean)) ** 0.5
        z = round((oi_latest - mean) / sd, 2) if sd > 0 else None

    bybit = as_float(
        await conn.fetchval(
            "SELECT oi_close FROM oi_bybit WHERE symbol=$1 AND interval='5min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    return {
        "symbol": symbol,
        "available": True,
        "oi_total_usd": oi_latest,
        "windows": windows,
        "percentile_1y": _pct_rank(clean, oi_latest),
        "zscore_1y": z,
        "by_venue": {
            "binance_oi_usd": oi_latest,
            "bybit_oi_usd": bybit,
            "two_venue_total_usd": round(oi_latest + bybit, 2)
            if (bybit and oi_latest)
            else oi_latest,
            "bybit_share_of_two_venues_pct": (
                round(bybit / (oi_latest + bybit) * 100, 1) if (bybit and oi_latest) else None
            ),
            "note": "open_interest viene del simbolo Coinalyze .A, que es BINANCE (no un "
            "agregado): verificado contra la API de Binance. oi_bybit es .6 = Bybit. "
            "Solo se cubren esos dos venues; OKX, Gate y demas no estan aqui.",
        },
        "quadrant_note": "el cuadrante es interpretacion probable; el signo del OI no identifica al iniciador con certeza",
    }


async def volatility_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    atr = {}
    for lab, sec in (("5m", 300), ("15m", 900), ("1h", 3600), ("4h", 14400), ("1d", 86400)):
        bars = await _resample_highs_lows(conn, symbol, sec, 60)
        a = _atr(bars, 14)
        close = as_float(bars[-1]["close"]) if bars else None
        atr[lab] = {
            "atr": round(a, 4) if a else None,
            "atr_pct": round(a / close * 100, 3) if (a and close) else None,
        }

    rv = {}
    for lab, sec in (("1h", 3600), ("24h", 86400), ("7d", 604800)):
        v = _realized_vol(await _closes_1min(conn, symbol, sec))
        rv[lab] = round(v, 1) if v else None

    # percentil del |retorno diario| de hoy vs el ultimo anio
    drows = [
        as_float(r["price_chg_pct"])
        for r in await conn.fetch(
            "SELECT price_chg_pct FROM daily_session_agg WHERE symbol=$1 ORDER BY session_date DESC LIMIT 365",
            symbol,
        )
    ]
    absret = [abs(x) for x in drows if x is not None]
    cur_abs = abs(drows[0]) if (drows and drows[0] is not None) else None
    daily_range_pct = _pct_rank(absret, cur_abs)

    # compresion/expansion sobre velas 1h
    bars1h = await _resample_highs_lows(conn, symbol, 3600, 60)
    trs = _tr_series(bars1h)
    recent = sum(trs[-5:]) / len(trs[-5:]) if len(trs) >= 5 else None
    base = sum(trs[-20:]) / len(trs[-20:]) if len(trs) >= 20 else None
    comp = round(recent / base, 3) if (recent and base) else None
    last_tr = trs[-1] if trs else None
    return {
        "symbol": symbol,
        "atr": atr,
        "realized_vol_annualized_pct": rv,
        "daily_range_percentile_1y": daily_range_pct,
        "compression_score": comp,  # <1 comprimido (rango reciente < rango base 1h)
        "range_expansion": bool(last_tr and base and last_tr > 1.5 * base),
        "note": "realized vol anualizada desde velas 1min; compresion = ATR(5) / ATR(20) en 1h",
    }


# ---------------- Fase 3: niveles de referencia + sesiones, y cross-asset ----------------
_SESSIONS_UTC = (("asia", 0, 8), ("london", 7, 16), ("new_york", 13, 22))


async def reference_levels(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week0 = day0 - timedelta(days=day0.weekday())
    month0 = day0.replace(day=1)

    async def first_open(since):
        return as_float(
            await conn.fetchval(
                "SELECT open FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts >= $2 ORDER BY ts LIMIT 1",
                symbol,
                since,
            )
        )

    async def hl(a, b):
        r = await conn.fetchrow(
            "SELECT max(high) h, min(low) l FROM ohlcv WHERE symbol=$1 AND interval='1min' "
            "AND ts >= $2 AND ts < $3",
            symbol,
            a,
            b,
        )
        return (as_float(r["h"]), as_float(r["l"])) if r else (None, None)

    pd_h, pd_l = await hl(day0 - timedelta(days=1), day0)
    pd_close = as_float(
        await conn.fetchval(
            "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts >= $2 AND ts < $3 "
            "ORDER BY ts DESC LIMIT 1",
            symbol,
            day0 - timedelta(days=1),
            day0,
        )
    )
    cd_h, cd_l = await hl(day0, now + timedelta(minutes=1))
    daily_open = await first_open(day0)

    sessions = {}
    for name, a, b in _SESSIONS_UTC:
        sh, sl = await hl(day0 + timedelta(hours=a), day0 + timedelta(hours=b))
        sessions[name] = {"high": sh, "low": sl, "window_utc": f"{a:02d}:00-{b:02d}:00"}

    return {
        "symbol": symbol,
        "previous_day": {"high": pd_h, "low": pd_l, "close": pd_close},
        "current_day": {"high": cd_h, "low": cd_l, "open": daily_open},
        "opens": {
            "daily": daily_open,
            "weekly": await first_open(week0),
            "monthly": await first_open(month0),
        },
        "sessions_today_utc": sessions,
        "note": "niveles desde ohlcv 1min (retencion ~14d; opens fuera de rango = null); dia = UTC",
    }


def _returns(vals: list) -> list:
    out = []
    for i in range(1, len(vals)):
        a, b = vals[i - 1], vals[i]
        out.append(math.log(b / a) if (a and b and a > 0 and b > 0) else None)
    return out


def _pearson(x: list, y: list):
    pairs = [(a, b) for a, b in zip(x, y, strict=False) if a is not None and b is not None]
    if len(pairs) < 10:
        return None
    n = len(pairs)
    mx = sum(a for a, _ in pairs) / n
    my = sum(b for _, b in pairs) / n
    cov = sum((a - mx) * (b - my) for a, b in pairs)
    vx = sum((a - mx) ** 2 for a, _ in pairs)
    vy = sum((b - my) ** 2 for _, b in pairs)
    return round(cov / (vx * vy) ** 0.5, 3) if (vx > 0 and vy > 0) else None


def _beta(asset_ret: list, base_ret: list):
    pairs = [
        (a, b) for a, b in zip(asset_ret, base_ret, strict=False) if a is not None and b is not None
    ]
    if len(pairs) < 10:
        return None
    n = len(pairs)
    ma = sum(a for a, _ in pairs) / n
    mb = sum(b for _, b in pairs) / n
    cov = sum((a - ma) * (b - mb) for a, b in pairs)
    vb = sum((b - mb) ** 2 for _, b in pairs)
    return round(cov / vb, 3) if vb > 0 else None


async def _binned(conn: asyncpg.Connection, symbol: str, seconds: int, bucket_s: int) -> list:
    rows = await conn.fetch(
        "SELECT date_bin(make_interval(secs => $2::int), ts, '1970-01-01'::timestamptz) AS b, "
        "(array_agg(close ORDER BY ts DESC))[1] AS c FROM ohlcv "
        "WHERE symbol=$1 AND interval='1min' AND ts >= now()-($3::int * interval '1 second') "
        "GROUP BY 1 ORDER BY 1",
        symbol,
        bucket_s,
        seconds,
    )
    return [(r["b"], as_float(r["c"])) for r in rows]


async def cross_asset(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Correlacion, beta y fuerza relativa del `symbol` frente a los otros y a BTC."""
    assets = list(WS_SYMBOL_MAP.keys())
    base = next((s for s in assets if s.startswith("BTC")), assets[0])
    data = {s: dict(await _binned(conn, s, 86400, 300)) for s in assets}
    if not all(data.values()):
        return {"symbol": symbol, "available": False}
    common = sorted(set.intersection(*[set(d.keys()) for d in data.values()]))
    closes = {s: [data[s][b] for b in common] for s in assets}

    def short(s):
        return s.split("USDT")[0].lower()

    corr, beta, rs = {}, {}, {}
    for lab, k in (("1h", 12), ("4h", 48), ("24h", 288)):
        w = {s: closes[s][-k:] for s in assets}
        rets = {s: _returns(w[s]) for s in assets}
        corr[lab] = {short(o): _pearson(rets[symbol], rets[o]) for o in assets if o != symbol}
        beta[lab] = 1.0 if symbol == base else _beta(rets[symbol], rets[base])
        if symbol != base and w[symbol] and w[base] and w[symbol][0] and w[base][0]:
            rs_now = w[symbol][-1] / w[base][-1]
            rs_then = w[symbol][0] / w[base][0]
            rs[lab] = round((rs_now / rs_then - 1) * 100, 3) if rs_then else None
        else:
            rs[lab] = None
    return {
        "symbol": symbol,
        "base": base,
        "available": True,
        "correlation": corr,
        "beta_vs_base": beta,
        "relative_strength_vs_base_pct": rs,
        "note": "correlacion Pearson de retornos 5min; RS>0 = el activo supera a BTC en la ventana",
    }


# ---------------- Fase 4: funding, liq map, volume profile y metadata ----------------
async def funding_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    cur = as_float(
        await conn.fetchval(
            "SELECT fr_close FROM funding_rate WHERE symbol=$1 AND interval='5min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    pred = as_float(
        await conn.fetchval(
            "SELECT pfr_close FROM predicted_funding_rate WHERE symbol=$1 AND interval='5min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    hist = {}
    for lab, sec in (("8h", 28800), ("24h", 86400), ("7d", 604800)):
        v = as_float(
            await conn.fetchval(
                "SELECT avg(fr_close) FROM funding_rate WHERE symbol=$1 AND interval='5min' "
                "AND ts >= now()-($2::int * interval '1 second')",
                symbol,
                sec,
            )
        )
        hist[lab] = round(v, 6) if v is not None else None
    now = datetime.now(UTC)
    cands = [now.replace(hour=h, minute=0, second=0, microsecond=0) for h in (0, 8, 16)]
    cands.append(cands[0] + timedelta(days=1))
    nxt = next(c for c in cands if c > now)
    return {
        "symbol": symbol,
        "current_pct": cur,
        "predicted_pct": pred,
        "divergence_pred_minus_current": round(pred - cur, 6)
        if (pred is not None and cur is not None)
        else None,
        "annualized_pct": round(cur * 3 * 365, 3) if cur is not None else None,
        "history_avg_pct": hist,
        "next_funding_time_utc": nxt.isoformat(),
        "regime": (
            "longs pagan (sesgo largo apalancado)"
            if (cur or 0) > 0
            else "shorts pagan (sesgo corto)"
            if (cur or 0) < 0
            else "neutro"
        ),
        "note": "funding % por periodo 8h; anualizado = fr x 3 x 365",
    }


async def liquidation_map(
    conn: asyncpg.Connection, symbol: str, bucket_bps: int = 10, minutes: int = 180
) -> dict[str, Any]:
    """Densidad de liquidaciones YA EJECUTADAS (historico ultimas 3h), agregadas por precio.
    NO es un mapa proyectado de liquidaciones futuras."""
    px = as_float(
        await conn.fetchval(
            "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    if not px:
        return {"symbol": symbol, "available": False}
    atr = _atr(await _resample_highs_lows(conn, symbol, 3600, 60), 14)
    bsize = px * bucket_bps / 10000.0
    rows = await conn.fetch(
        "SELECT round(price / $3::float8) * $3::float8 AS bucket, "
        " SUM(CASE WHEN side='long' THEN notional_usd ELSE 0 END) AS long_liq, "
        " SUM(CASE WHEN side='short' THEN notional_usd ELSE 0 END) AS short_liq, "
        " SUM(notional_usd) AS total FROM liquidations_realtime "
        " WHERE symbol=$1 AND ts >= now()-($2::int * interval '1 minute') GROUP BY 1 ORDER BY total DESC",
        symbol,
        minutes,
        bsize,
    )
    levels = []
    for r in rows[:12]:
        b = as_float(r["bucket"])
        levels.append(
            {
                "price": round(b, 2),
                "long_liq": as_float(r["long_liq"]),
                "short_liq": as_float(r["short_liq"]),
                "total_notional": as_float(r["total"]),
                "distance_pct": round((b / px - 1) * 100, 3),
                "distance_atr": round((b - px) / atr, 2) if atr else None,
            }
        )
    cumulative = {}
    for pct in (0.5, 1.0, 2.0):
        up, dn = px * (1 + pct / 100), px * (1 - pct / 100)
        cumulative[f"long_liq_within_{pct}pct"] = round(
            sum(as_float(r["long_liq"]) or 0 for r in rows if dn <= as_float(r["bucket"]) <= up), 2
        )
        cumulative[f"short_liq_within_{pct}pct"] = round(
            sum(as_float(r["short_liq"]) or 0 for r in rows if dn <= as_float(r["bucket"]) <= up), 2
        )
    return {
        "symbol": symbol,
        "available": True,
        "type": "historical_realized_density_3h",
        "current_price": px,
        "atr_1h": round(atr, 4) if atr else None,
        "levels": levels,
        "cumulative_within_band": cumulative,
        "note": "liquidaciones YA EJECUTADAS en 3h por precio (historico, no proyeccion). Un cluster "
        "puede quedar arriba o abajo del precio actual segun como se movio el precio desde su "
        "ejecucion. distance_pct/atr = del precio actual al nivel donde ocurrieron.",
    }


def _profile(prices: list, vols: list, nb: int = 50):
    clean = [(p, v) for p, v in zip(prices, vols, strict=True) if p is not None and v]
    if len(clean) < 5:
        return None
    ps = [p for p, _ in clean]
    lo, hi = min(ps), max(ps)
    if hi <= lo:
        return None
    width = (hi - lo) / nb
    buckets = [0.0] * nb
    for p, v in clean:
        buckets[min(nb - 1, int((p - lo) / width))] += v
    total = sum(buckets)
    if total <= 0:
        return None

    def center(i):
        return lo + (i + 0.5) * width

    order = sorted(range(nb), key=lambda i: buckets[i], reverse=True)
    acc, sel = 0.0, []
    for i in order:
        sel.append(i)
        acc += buckets[i]
        if acc >= 0.7 * total:
            break
    va = [center(i) for i in sel]
    nonzero = [i for i in range(nb) if buckets[i] > 0]
    return {
        "poc": round(center(order[0]), 2),
        "vah": round(max(va), 2),
        "val": round(min(va), 2),
        "hvn": [round(center(i), 2) for i in order[:3]],
        "lvn": [round(center(i), 2) for i in sorted(nonzero, key=lambda i: buckets[i])[:3]],
    }


async def volume_profile(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week0 = day0 - timedelta(days=day0.weekday())
    rows = await conn.fetch(
        "SELECT close, volume FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts >= $2 ORDER BY ts",
        symbol,
        day0,
    )
    prices = [as_float(r["close"]) for r in rows]
    vols = [as_float(r["volume"]) or 0.0 for r in rows]
    prof = _profile(prices, vols)
    total = sum(vols)
    vwap_s = sum(p * v for p, v in zip(prices, vols, strict=True) if p) / total if total else None
    sd = None
    if vwap_s and total:
        var = sum(v * (p - vwap_s) ** 2 for p, v in zip(prices, vols, strict=True) if p) / total
        sd = var**0.5
    wr = await conn.fetch(
        "SELECT close, volume FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts >= $2",
        symbol,
        week0,
    )
    wp = [as_float(r["close"]) for r in wr]
    wv = [as_float(r["volume"]) or 0.0 for r in wr]
    wt = sum(wv)
    vwap_w = sum(p * v for p, v in zip(wp, wv, strict=True) if p) / wt if wt else None
    bands = {}
    if vwap_s and sd:
        bands = {
            "plus_1sigma": round(vwap_s + sd, 2),
            "minus_1sigma": round(vwap_s - sd, 2),
            "plus_2sigma": round(vwap_s + 2 * sd, 2),
            "minus_2sigma": round(vwap_s - 2 * sd, 2),
        }
    return {
        "symbol": symbol,
        "available": prof is not None,
        "session": prof,
        "vwap": {
            "utc_day": round(vwap_s, 2) if vwap_s else None,
            "weekly": round(vwap_w, 2) if vwap_w else None,
            "bands": bands,
            "market": "futures (close de velas 1min)",
            "session_convention": "dia UTC 00:00",
            "distinct_from": "scalp.session_vwap (usa sesion NYSE y trades en vivo; puede diferir ~1%)",
        },
        "note": "aprox: volumen-a-precio desde close de velas 1min (no footprint real); VA=70%; dia UTC",
    }


async def context_metadata(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    ws = WS_SYMBOL_MAP[symbol]
    feed_defs = (
        ("ohlcv", "ohlcv", symbol, "binance", "continuous"),
        ("open_interest", "open_interest", symbol, "binance", "continuous"),
        ("funding", "funding_rate", symbol, "binance", "continuous"),
        ("liquidations", "liquidations_realtime", symbol, "binance+bybit", "event_stream"),
        ("futures_trades", "futures_trades_agg", symbol, "binance+bybit", "continuous"),
        ("spot_trades", "spot_trades_agg", ws, "binance+bybit", "continuous"),
    )
    now = datetime.now(UTC)
    feeds = {}
    for name, table, sym, ven, ftype in feed_defs:
        hi = await conn.fetchval(f"SELECT max(ts) FROM {table} WHERE symbol=$1", sym)
        age = round((now - hi).total_seconds(), 1) if hi else None
        entry = {"last_record_age_seconds": age, "venues": ven, "feed_type": ftype}
        entry["note"] = (
            "feed de EVENTOS: age alto = sin eventos recientes (calma), NO staleness; "
            "ver data_quality.collectors para salud real"
            if ftype == "event_stream"
            else "feed continuo: age alto = posible atraso del feed"
        )
        feeds[name] = entry
    return {
        "symbol": symbol,
        "calc_version": "context-2026.07",
        "generated_at": now.isoformat(),
        "feeds": feeds,
        "venues_note": "ohlcv/OI/funding vienen del simbolo Coinalyze .A = BINANCE (no es un agregado multi-venue, pese al nombre); trades y liquidaciones en vivo = binance+bybit",
        "note": "frescura: usa last_record_age solo para feed_type=continuous; para event_stream mira data_quality.collectors (heartbeat)",
    }


# ---------------- calidad POR FEED (feeds reales de mercado, no procesos internos) ----------------
# Cada entrada declara: de que tabla sale, que mercado y venues cubre, cada cuanto DEBERIA
# llegar un registro y que colector la alimenta. Sin la cadencia esperada no se puede hablar
# de cobertura, asi que los feeds que no la tienen la declaran `None` en vez de fingirla.
FEED_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "feed": "ohlcv_1min", "table": "ohlcv", "market": "perpetuo", "data_type": "velas",
        "exchanges": ("binance",), "interval_seconds": 60, "collector": "ingest",
        "symbol_space": "perp", "filter": "interval='1min'", "exchange_column": None,
    },
    {
        "feed": "open_interest_5min", "table": "open_interest", "market": "perpetuo",
        "data_type": "open interest", "exchanges": ("binance",), "interval_seconds": 300,
        "collector": "ingest", "symbol_space": "perp", "filter": "interval='5min'",
        "exchange_column": None,
    },
    {
        "feed": "funding_rate", "table": "funding_rate", "market": "perpetuo",
        "data_type": "funding", "exchanges": ("binance",), "interval_seconds": None,
        "collector": "ingest", "symbol_space": "perp", "filter": None, "exchange_column": None,
    },
    {
        "feed": "futures_trades", "table": "futures_trades_realtime", "market": "perpetuo",
        "data_type": "trades agregados", "exchanges": ("binance", "bybit"),
        "interval_seconds": None, "collector": "ws", "symbol_space": "perp",
        "filter": None, "exchange_column": "exchange",
    },
    {
        "feed": "spot_trades", "table": "spot_trades_realtime", "market": "spot",
        "data_type": "trades agregados", "exchanges": ("binance", "bybit"),
        "interval_seconds": None, "collector": "ws", "symbol_space": "spot",
        "filter": None, "exchange_column": "exchange",
    },
    {
        "feed": "liquidations", "table": "liquidations_realtime", "market": "perpetuo",
        "data_type": "liquidaciones (eventos)", "exchanges": ("binance", "bybit"),
        "interval_seconds": None, "collector": "scalp", "symbol_space": "perp",
        "filter": None, "exchange_column": "exchange",
    },
    {
        "feed": "orderbook", "table": "orderbook_depth", "market": "perpetuo",
        "data_type": "libro (escalera)", "exchanges": ("binance", "bybit"),
        "interval_seconds": None, "collector": "scalp", "symbol_space": "perp",
        "filter": None, "exchange_column": "exchange",
    },
)

FEED_QUALITY_WINDOW_SECONDS = 900

GAP_MEASURABLE_TABLES = frozenset({"spot_trades_realtime", "futures_trades_realtime"})
"""Tablas donde `max_internal_gap()` esta definido y ademas SIGNIFICA algo.

Es la misma lista blanca que la funcion valida por dentro; se declara aqui para no llamarla
con una tabla que rechaza. En `liquidations_realtime` no aplica por diseno: un hueco en un
feed de eventos es calma, no perdida.
"""


async def feed_quality(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Estado real de cada FEED de mercado, uno por uno.

    Distinto de `data_quality()`, que mide la salud de los PROCESOS (heartbeat de los
    colectores). El panel de calidad llamaba "Fuentes de datos" a esa lista de procesos; un
    feed es otra cosa: un venue, un mercado, un tipo de dato y una cadencia.

    Nada se inventa: la cobertura solo se calcula donde existe cadencia esperada, y los
    huecos internos solo donde la tabla los permite medir. Lo demas viaja como `null`.
    """
    ws_symbol = WS_SYMBOL_MAP[symbol]
    now = datetime.now(UTC)
    ventana = FEED_QUALITY_WINDOW_SECONDS
    heartbeats = {
        r["service"]: (r["status"], as_float(r["lag"]), r["detail"])
        for r in await conn.fetch(
            "SELECT service, status, EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag, "
            "detail FROM pipeline_heartbeat"
        )
    }
    liquidation_health = {
        str(r["exchange"]): dict(r)
        for r in await conn.fetch(
            "SELECT exchange,status,healthy_since,last_loss_at,updated_at,detail,"
            "EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag "
            "FROM market_feed_health WHERE feed='liquidations'"
        )
    }
    filas: list[dict[str, Any]] = []
    for spec in FEED_DEFINITIONS:
        sym = ws_symbol if spec["symbol_space"] == "spot" else symbol
        extra = f" AND {spec['filter']}" if spec["filter"] else ""
        fila = await conn.fetchrow(
            f"SELECT max(ts) AS ultimo, COUNT(*)::int AS muestras "  # noqa: S608
            f"FROM {spec['table']} "
            f"WHERE symbol=$1{extra} AND ts >= now()-($2::int * interval '1 second')",
            sym,
            ventana,
        )
        ultimo = fila["ultimo"] if fila else None
        muestras = int(fila["muestras"] or 0) if fila else 0
        # `orderbook_depth` guarda SOLO el estado actual (se sobrescribe): contar filas ahi
        # no mide cobertura de la ventana, mide venues vivos.
        if spec["table"] == "orderbook_depth":
            muestras = None
        latencia = round((now - ultimo).total_seconds(), 1) if ultimo else None
        esperadas = ventana // spec["interval_seconds"] if spec["interval_seconds"] else None
        cobertura = (
            round(min(muestras / esperadas, 1.0) * 100, 1)
            if esperadas and muestras is not None
            else None
        )
        # Venues presentes vs esperados: solo donde la tabla distingue exchange.
        ausentes: list[str] | None = None
        if spec["exchange_column"]:
            vistos = {
                r["exchange"]
                for r in await conn.fetch(
                    f"SELECT DISTINCT exchange FROM {spec['table']} "  # noqa: S608
                    f"WHERE symbol=$1 AND ts >= now()-($2::int * interval '1 second')",
                    sym,
                    ventana,
                )
            }
            ausentes = sorted(set(spec["exchanges"]) - vistos)
        if spec["feed"] == "liquidations":
            # Un venue sin eventos puede estar perfectamente sano; la presencia de filas no
            # prueba conectividad. Para liquidaciones manda la salud específica del stream.
            ausentes = None
        # Hueco interno mayor: SOLO en las dos tablas de trades en tiempo real, que es donde
        # `max_internal_gap` esta definido. En `liquidations_realtime` no significa nada: es
        # un feed de eventos y un hueco ahi es mercado tranquilo, no pérdida de datos. Antes
        # se decidia por el sufijo `_realtime`, que la incluia y hacia reventar la consulta.
        hueco = None
        if spec["table"] in GAP_MEASURABLE_TABLES:
            hueco = await max_internal_gap(conn, spec["table"], sym, "combined", ventana)

        if spec["feed"] == "liquidations":
            estado, ultimo_error = _liquidation_feed_quality_status(
                liquidation_health,
                spec["exchanges"],
                now,
                ventana,
            )
        else:
            estado, ultimo_error = _feed_status(
                spec,
                heartbeats,
                latencia,
                muestras,
                ausentes,
            )
        filas.append(
            {
                "feed": spec["feed"],
                "exchange": " + ".join(spec["exchanges"]),
                "market": spec["market"],
                "symbol": sym,
                "data_type": spec["data_type"],
                "status": estado,
                "last_ts": ultimo.isoformat() if ultimo else None,
                "latency_seconds": latencia,
                "coverage_pct": cobertura,
                "samples_observed": muestras,
                "samples_expected": esperadas,
                "max_internal_gap_seconds": hueco,
                "missing_sources": ausentes,
                "last_error": ultimo_error,
                "collector": spec["collector"],
                "expected_interval_seconds": spec["interval_seconds"],
            }
        )
    return {
        "symbol": symbol,
        "generated_at": now.isoformat(),
        "window_seconds": ventana,
        "feeds": filas,
        "note": (
            "Feeds de MERCADO (venue + mercado + tipo de dato). La salud de los procesos "
            "internos va aparte, en data_quality/healthz. Cobertura solo donde hay cadencia "
            "esperada; el resto se publica como null, no como cero."
        ),
    }


def _liquidation_feed_quality_status(
    health: dict[str, dict[str, Any]],
    exchanges: tuple[str, ...],
    now: datetime,
    window_seconds: int,
) -> tuple[str, str | None]:
    """Evaluate operational state and continuity across the displayed quality window."""
    rows = [(exchange, health.get(exchange)) for exchange in exchanges]
    if any(row is None for _, row in rows):
        return "UNAVAILABLE", "sin salud de todos los streams"

    freshness = timedelta(seconds=COLLECTOR_THRESHOLDS["scalp"][1])
    continuity_start = now - timedelta(seconds=window_seconds)
    for exchange, row in rows:
        assert row is not None
        updated_at = _as_utc_datetime(row.get("updated_at"))
        if (
            row.get("status") != "ok"
            or updated_at is None
            or not (now - freshness <= updated_at <= now + timedelta(seconds=1))
        ):
            detail = row.get("detail")
            return "DOWN", str(detail) if detail else f"stream {exchange} no saludable"

    for exchange, row in rows:
        assert row is not None
        healthy_since = _as_utc_datetime(row.get("healthy_since"))
        last_loss_at = _as_utc_datetime(row.get("last_loss_at"))
        if healthy_since is None or healthy_since > continuity_start:
            return "PARTIAL", f"continuidad incompleta: {exchange} reconectó dentro de la ventana"
        if last_loss_at is not None and last_loss_at >= continuity_start:
            return "PARTIAL", f"continuidad incompleta: pérdida reciente en {exchange}"
    return "OK", None


def _feed_status(
    spec: dict[str, Any],
    heartbeats: dict[str, tuple],
    latencia: float | None,
    muestras: int | None,
    ausentes: list[str] | None,
) -> tuple[str, str | None]:
    """Estado del feed y su ultimo error, sin confundir calma con caida.

    Las liquidaciones son un feed de EVENTOS: que lleve rato sin llegar ninguna significa
    mercado tranquilo, no colector muerto. Ahi el estado lo decide el heartbeat, no la edad.
    """
    hb = heartbeats.get(spec["collector"])
    hb_status, hb_lag, hb_detail = hb if hb else (None, None, None)
    error = hb_detail if hb_status not in (None, "ok") else None
    limite = COLLECTOR_THRESHOLDS.get(spec["collector"], (None, None))[1]
    if hb_status is None:
        return "UNAVAILABLE", "sin heartbeat del colector"
    if hb_status != "ok" or (hb_lag is not None and limite is not None and hb_lag > limite):
        return "DOWN", error or f"colector {spec['collector']} sin latido reciente"
    if muestras == 0 and spec["interval_seconds"]:
        return "STALE", "colector vivo pero sin registros en la ventana"
    if latencia is not None and spec["interval_seconds"] and latencia > spec["interval_seconds"] * 3:
        return "STALE", f"ultimo registro hace {latencia:.0f} s"
    if ausentes:
        return "PARTIAL", f"sin datos de: {', '.join(ausentes)}"
    return "OK", error


def metric_quality(
    matrix: list[dict[str, Any]], scalp: dict[str, Any], feeds: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Calidad POR METRICA publicada, no por feed ni por proceso.

    PURA: recibe bloques ya calculados. Un feed sano no garantiza que una metrica concreta
    sea utilizable — la ventana de 5 m puede estar incompleta mientras la de 1 h esta entera,
    y el basis puede ser inutilizable con las dos patas vivas si van desfasadas.

    Cada metrica declara su estado y DE DONDE sale. Lo que no se puede saber va como `null`.
    """
    por_ventana = {str(r.get("window")): r for r in matrix or []}
    por_feed = {f["feed"]: f for f in ((feeds or {}).get("feeds") or [])}

    def de_matriz(ventana: str, pata: str, etiqueta: str) -> dict[str, Any]:
        fila = por_ventana.get(ventana) or {}
        valor = fila.get(f"{pata}_delta")
        cobertura = fila.get("coverage_status")
        return {
            "metric": etiqueta,
            "timeframe": ventana,
            "status": (
                "UNAVAILABLE" if not fila or cobertura == "unavailable"
                else "OK" if cobertura == "complete" and valor is not None
                else "PARTIAL"
            ),
            "value": valor,
            "coverage": cobertura,
            "source": fila.get(f"{pata}_source"),
            "latency_seconds": fila.get(f"{pata}_end_gap_seconds"),
        }

    def de_feed(nombre: str, etiqueta: str, tf: str | None = None) -> dict[str, Any]:
        feed = por_feed.get(nombre) or {}
        return {
            "metric": etiqueta,
            "timeframe": tf,
            "status": feed.get("status", "UNAVAILABLE"),
            "value": None,
            "coverage": (
                f"{feed.get('coverage_pct')}%" if feed.get("coverage_pct") is not None else None
            ),
            "source": feed.get("exchange"),
            "latency_seconds": feed.get("latency_seconds"),
        }

    metricas = [
        de_matriz("5m", "spot", "Delta spot"),
        de_matriz("5m", "fut", "Delta futuros"),
        de_matriz("1h", "fut", "CVD futuros"),
        de_matriz("1h", "spot", "CVD spot"),
        {
            "metric": "Basis perp-spot",
            "timeframe": "vivo",
            # El basis tiene su propio semaforo: depende de la EDAD de cada pata, no de que
            # existan. Se reutiliza tal cual en vez de recalcular otro criterio.
            "status": scalp.get("basis_status") or "UNAVAILABLE",
            "value": scalp.get("basis_bps"),
            "coverage": None,
            "source": "futures+spot realtime",
            "latency_seconds": (scalp.get("basis_detail") or {}).get("max_age_seconds"),
        },
        {
            "metric": "Open interest",
            "timeframe": "15m",
            "status": "OK" if scalp.get("oi_chg_15m_pct") is not None else "UNAVAILABLE",
            "value": scalp.get("oi_chg_15m_pct"),
            "coverage": (por_feed.get("open_interest_5min") or {}).get("coverage_pct"),
            "source": (por_feed.get("open_interest_5min") or {}).get("exchange"),
            "latency_seconds": (por_feed.get("open_interest_5min") or {}).get("latency_seconds"),
        },
        de_feed("funding_rate", "Funding"),
        {
            "metric": "Order book",
            "timeframe": "vivo",
            "status": {"ok": "OK", "stale": "STALE", "missing": "UNAVAILABLE"}.get(
                str(scalp.get("book_status")), "UNAVAILABLE"
            ),
            "value": scalp.get("imbalance_l5"),
            "coverage": None,
            "source": (por_feed.get("orderbook") or {}).get("exchange"),
            "latency_seconds": scalp.get("book_lag_seconds"),
        },
    ]
    return {
        "metrics": metricas,
        "note": (
            "Estado de cada metrica PUBLICADA. Un feed sano no implica que toda ventana que "
            "se apoya en el sea utilizable; sin dato se dice UNAVAILABLE, nunca cero."
        ),
    }


# ---------------- calidad por contexto (heartbeat de colectores, no recencia de eventos) ----------------
async def data_quality(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    now = datetime.now(UTC)
    hb = {
        r["service"]: (r["status"], as_float(r["lag"]))
        for r in await conn.fetch(
            "SELECT service, status, EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag "
            "FROM pipeline_heartbeat"
        )
    }
    # (expected_interval_s, stale_after_s) por colector. Compartido con
    # compute_scalp_summary(), que usa el de 'ws' para decidir si una ventana de
    # liquidaciones se midio de verdad.
    thr = COLLECTOR_THRESHOLDS

    def ok(svc):
        st = hb.get(svc)
        return bool(st and st[0] == "ok" and st[1] is not None and st[1] <= thr[svc][1])

    ws_ok, scalp_ok, ingest_ok, daily_ok = ok("ws"), ok("scalp"), ok("ingest"), ok("daily")
    liq_hi = await conn.fetchval(
        "SELECT max(ts) FROM liquidations_realtime WHERE symbol=$1", symbol
    )
    liq_age = round((now - liq_hi).total_seconds(), 1) if liq_hi else None

    def status(flag):
        return "ok" if flag else "degraded"

    return {
        "symbol": symbol,
        "collectors": {
            sv: {
                "status": (hb.get(sv) or [None])[0],
                "lag_seconds": (hb.get(sv) or [None, None])[1],
                "expected_interval_seconds": thr[sv][0],
                "stale_after_seconds": thr[sv][1],
            }
            for sv in ("ingest", "ws", "scalp", "daily", "api")
        },
        "scalp": {"status": status(ws_ok and scalp_ok), "depends_on": ["ws", "scalp"]},
        "intraday": {"status": status(ws_ok and ingest_ok), "depends_on": ["ws", "ingest"]},
        "macro": {"status": status(ingest_ok and daily_ok), "depends_on": ["ingest", "daily"]},
        "event_recency": {
            "liquidations_last_event_age_s": liq_age,
            "note": "feed de EVENTOS: lag alto suele ser SIN eventos (calma), no feed caido. "
            "long_liq/short_liq=0 es lectura valida si ws esta vivo.",
        },
        "note": "calidad = conectividad (heartbeat vs stale_after_seconds), NO recencia de eventos.",
    }


# ---------------- manos silenciosas (flujo pasivo: absorcion + diff + value area + OI) ----------------
_PF_HORIZONS = (("15m", 900), ("1h", 3600), ("4h", 14400), ("8h", 28800))


def _gap_too_large(max_gap_seconds: float | None) -> bool:
    return max_gap_seconds is not None and max_gap_seconds > REALTIME_STALE_SECONDS


async def max_internal_gap(
    conn: asyncpg.Connection, table: str, symbol: str, exchange: str, seconds: int
) -> float | None:
    """Mayor hueco entre buckets consecutivos DENTRO de la ventana, en segundos.

    La cobertura se decidia solo con MIN(ts)/MAX(ts), asi que una ventana que atravesaba
    una caida del collector se publicaba como `complete`: los extremos estaban, el centro
    no. Medido en la BD, `ohlcv` 1min acumula 3 huecos en 14 dias y el mayor es de 2 h 44,
    justo el caso que los extremos no ven.

    El borde de entrada de la ventana entra como una fila mas, para que un collector caido
    al principio cuente igual que uno caido en medio sin necesidad de un caso especial.
    """
    if table not in {"spot_trades_realtime", "futures_trades_realtime"}:
        raise ValueError("unsupported realtime flow table")
    return as_float(
        await conn.fetchval(
            f"""
            WITH edges AS (
              SELECT ts FROM {table}
              WHERE symbol=$1 AND exchange=$2
                AND ($2 <> 'combined' OR venue_count=2)
                AND ts >= now()-($3::int*interval '1 second')
              UNION ALL SELECT now()-($3::int*interval '1 second')
            )
            SELECT MAX(EXTRACT(EPOCH FROM ts-prev))::float8
            FROM (SELECT ts,lag(ts) OVER (ORDER BY ts) AS prev FROM edges) d
            WHERE prev IS NOT NULL
            """,
            symbol,
            exchange,
            seconds,
        )
    )


async def _realtime_flow(
    conn: asyncpg.Connection, table: str, symbol: str, seconds: int
) -> dict[str, Any]:
    if table not in {"spot_trades_realtime", "futures_trades_realtime"}:
        raise ValueError("unsupported realtime flow table")
    row = await conn.fetchrow(
        f"""
        WITH source AS (
          SELECT ts,buy_vol_usd,sell_vol_usd,trade_count
          FROM {table} WHERE symbol=$1 AND exchange='combined' AND venue_count=2
        ), span AS (
          SELECT MIN(ts) AS lo,MAX(ts) AS hi FROM source
        ), flow AS (
          SELECT SUM(buy_vol_usd-sell_vol_usd) AS delta,
                 SUM(buy_vol_usd+sell_vol_usd) AS volume,
                 SUM(trade_count) AS trades,COUNT(*)::bigint AS source_rows
          FROM source WHERE ts >= now()-($2::int*interval '1 second')
        )
        SELECT flow.*,span.lo,span.hi,
               COALESCE(
                 span.lo <= now()-($2::int*interval '1 second')
                 AND span.hi >= now()-interval '30 seconds',false
               ) AS span_ok,
               CASE WHEN span.hi IS NOT NULL
                    THEN EXTRACT(EPOCH FROM now()-span.hi)::float8 END AS end_gap_seconds
        FROM flow CROSS JOIN span
        """,
        symbol,
        seconds,
    )
    item = dict(row) if row else {}
    now = datetime.now(UTC)
    feed = "spot_trades" if table == "spot_trades_realtime" else "futures_trades"
    market = "spot" if table == "spot_trades_realtime" else "perpetual"
    blocked = await blocking_requirement_keys(
        conn,
        [
            GapRequirement(
                "flow", feed, exchange, market, symbol,
                now - timedelta(seconds=seconds), now,
            )
            for exchange in ("binance", "bybit", "combined")
        ],
    )
    item["max_gap_seconds"] = await max_internal_gap(conn, table, symbol, "combined", seconds)
    item["complete"] = bool(item.get("span_ok")) and not _gap_too_large(
        item["max_gap_seconds"]
    )
    item["complete"] = item["complete"] and "flow" not in blocked
    if "flow" in blocked:
        item["delta"] = None
        item["volume"] = None
        item["trades"] = None
        item["gap_reason"] = "data_gap"
    item["delta"] = as_float(item.get("delta"))
    item["volume"] = as_float(item.get("volume"))
    item["trades"] = int(item["trades"]) if item.get("trades") is not None else None
    item["coverage_status"] = (
        "complete"
        if item["complete"]
        else ("partial" if int(item.get("source_rows") or 0) else "unavailable")
    )
    item["end_gap_seconds"] = (
        round(as_float(item.get("end_gap_seconds")) or 0.0, 1)
        if item.get("end_gap_seconds") is not None
        else None
    )
    return item


async def _oi_change_pct(conn: asyncpg.Connection, symbol: str, seconds: int) -> float | None:
    if seconds < 300:
        return None
    return as_float(
        await conn.fetchval(
            """
        WITH cur AS (
          SELECT ts,oi_close FROM open_interest
          WHERE symbol=$1 AND interval='5min' ORDER BY ts DESC LIMIT 1
        ), ago AS (
          SELECT oi.oi_close FROM open_interest oi,cur
          WHERE oi.symbol=$1 AND oi.interval='5min'
            AND oi.ts <= cur.ts-($2::int*interval '1 second')
          ORDER BY oi.ts DESC LIMIT 1
        )
        SELECT CASE WHEN ago.oi_close>0 THEN (cur.oi_close/ago.oi_close-1)*100 END
        FROM cur LEFT JOIN ago ON true
        """,
            symbol,
            seconds,
        )
    )


async def delta_matrix(
    conn: asyncpg.Connection, symbol: str, windows: list[tuple[str, int]]
) -> list[dict[str, Any]]:
    spot_windows = await spot_flow_windows(conn, WS_SYMBOL_MAP[symbol], windows)
    baselines = await load_baselines(conn, symbol)
    rows: list[dict[str, Any]] = []
    for label, seconds in windows:
        spot = (spot_windows.get(label) or {}).get("combined") or {}
        futures = await _realtime_flow(conn, "futures_trades_realtime", symbol, seconds)
        # El chequeo de huecos solo aplica a la pata servida por realtime (buckets de 5 s).
        # Cuando spot viene del agg de 1 min el umbral de 30 s no significa nada, y la fila
        # ya lo declara en `spot_source`.
        spot_gap = (
            await max_internal_gap(
                conn, "spot_trades_realtime", WS_SYMBOL_MAP[symbol], "combined", seconds
            )
            if spot.get("source") == "realtime"
            else None
        )
        spot_complete = bool(spot.get("complete")) and not _gap_too_large(spot_gap)
        futures_complete = bool(futures.get("complete"))
        spot_delta = as_float(spot.get("delta")) if spot_complete else None
        futures_delta = as_float(futures.get("delta")) if futures_complete else None
        complete = spot_complete and futures_complete
        rows.append(
            {
                "window": label,
                "spot_delta": spot_delta,
                "fut_delta": futures_delta,
                "diff": (
                    spot_delta - futures_delta
                    if spot_delta is not None and futures_delta is not None
                    else None
                ),
                "spot_volume": as_float(spot.get("volume")) if spot_complete else None,
                "fut_volume": as_float(futures.get("volume")) if futures_complete else None,
                "spot_trades": spot.get("trades") if spot_complete else None,
                "fut_trades": futures.get("trades") if futures_complete else None,
                "oi_change_pct": await _oi_change_pct(conn, symbol, seconds),
                "coverage_status": (
                    "complete"
                    if complete
                    else (
                        "partial"
                        if (spot.get("source") != "unavailable" or futures.get("source_rows"))
                        else "unavailable"
                    )
                ),
                "spot_coverage_status": (
                    "partial" if _gap_too_large(spot_gap) else spot.get("coverage_status", "unavailable")
                ),
                "futures_coverage_status": futures.get("coverage_status", "unavailable"),
                "spot_source": spot.get("source", "unavailable"),
                "spot_end_gap_seconds": spot.get("end_gap_seconds"),
                "futures_end_gap_seconds": futures.get("end_gap_seconds"),
                "spot_max_gap_seconds": spot_gap,
                "futures_max_gap_seconds": futures.get("max_gap_seconds"),
                # Sin referencia historica, "-45 M USD" no dice si es mucho o poco.
                "fut_delta_ratio": (
                    round(abs(futures_delta) / as_float(futures.get("volume")), 4)
                    if futures_delta is not None and as_float(futures.get("volume"))
                    else None
                ),
                "fut_delta_context": baseline_band(
                    (
                        abs(futures_delta) / as_float(futures.get("volume"))
                        if futures_delta is not None and as_float(futures.get("volume"))
                        else None
                    ),
                    baselines.get(label),
                ),
            }
        )
    return rows


def flow_confirmation(spot_delta: float | None, fut_delta: float | None) -> dict[str, Any]:
    """Clasifica el flujo por el signo de AMBAS patas, nunca por su diferencia.

    spot_delta - fut_delta no es una direccion: la pata de futuros (perp de Binance) mueve
    ~10x la de spot (Binance+Bybit), asi que el signo del diferencial es el del CVD de
    futuros invertido en 93-94% de las sesiones y coincide con el spot en solo 28-38%.
    Medido sobre las ultimas 90 sesiones x 3 simbolos, en 69-81% de ellas AMBAS patas
    tienen el mismo signo mientras el diferencial apunta al contrario. Votar con el
    diferencial equivale a votar contra los futuros; aqui el desacuerdo entre patas se
    reporta como conflicto (voto 0), que es lo que realmente informa.
    """
    if spot_delta is None or fut_delta is None:
        return {"vote": None, "state": "sin_datos", "agreement": None}
    if spot_delta > 0 and fut_delta > 0:
        return {"vote": 1, "state": "spot_y_futuros_compran", "agreement": True}
    if spot_delta < 0 and fut_delta < 0:
        return {"vote": -1, "state": "spot_y_futuros_venden", "agreement": True}
    if spot_delta == 0 or fut_delta == 0:
        return {"vote": 0, "state": "una_pata_plana", "agreement": None}
    state = (
        "spot_compra_futuros_vende" if spot_delta > 0 else "spot_vende_futuros_compra"
    )
    return {"vote": 0, "state": state, "agreement": False}


# ---------------- perfil intradia / swing (jerarquia explicita de temporalidades) ----------------
# Cada capa pesa distinto segun el perfil. Los pesos son una CONVENCION declarada, no un
# resultado medido: por eso viajan en la respuesta y se puede ver la contribucion de cada capa.
# El punto no es que el numero sea optimo, es que sea auditable y que 30s no mande en un swing.
TRADING_PROFILES: dict[str, dict[str, Any]] = {
    "intradia": {
        "label": "Intradía ≤ 4 h",
        "layers": {
            "contexto": {"timeframes": ("4h", "1h"), "weight": 30},
            "confirmacion": {"timeframes": ("18m", "15m", "5m"), "weight": 45},
            "gatillo": {"timeframes": ("1m", "30s"), "weight": 25},
        },
        "reference_only": ("8h", "1d", "3d"),
        # En intradia el gatillo SI puede invalidar: la operacion dura minutos u horas.
        "trigger_can_invalidate": True,
    },
    "swing": {
        "label": "Swing varios días",
        # Capas DISJUNTAS. El §6.2 original ponia 8h y 4h en contexto y en confirmacion, y 1h
        # en confirmacion y en entrada: la misma observacion votaba dos veces e inflaba la
        # confluencia. Se reparten sin repetir; el conjunto de temporalidades no cambia.
        "layers": {
            "contexto": {"timeframes": ("3d", "1d", "8h"), "weight": 50},
            "confirmacion": {"timeframes": ("4h", "1h"), "weight": 35},
            "entrada": {"timeframes": ("18m", "15m", "5m"), "weight": 15},
            # 30s y 1m ejecutan: afinan el precio de entrada y NUNCA tumban una tesis de
            # varios dias. Tienen capa propia con peso 0 para que aparezcan en la jerarquia
            # sin votar; antes vivian en `reference_only` y no se veian como capa.
            "ejecucion": {"timeframes": ("1m", "30s"), "weight": 0},
        },
        # `5m` pertenece a la capa de ENTRADA: repetirlo aqui lo describia a la vez como
        # entrada y como referencia secundaria, dos cosas incompatibles.
        "reference_only": (),
        # El prompt maestro lo pide explicito: 30s/1m no tumban una tesis de varios dias.
        "trigger_can_invalidate": False,
    },
}

_BIAS_VOTE = {"alcista": 1, "bajista": -1, "neutral": 0}


def _flow_bias(row: dict[str, Any]) -> tuple[str, str]:
    """Sesgo de una fila de delta_matrix por el signo de AMBAS patas."""
    if row.get("coverage_status") == "unavailable":
        return "sin_datos", "sin cobertura"
    confirm = flow_confirmation(as_float(row.get("spot_delta")), as_float(row.get("fut_delta")))
    vote = confirm["vote"]
    if vote is None:
        return "sin_datos", confirm["state"]
    if vote == 0:
        return "conflicto", confirm["state"]
    return ("alcista" if vote > 0 else "bajista"), confirm["state"]


def profile_view(
    trend: dict[str, Any], matrix: list[dict[str, Any]], profile: str
) -> dict[str, Any]:
    """Compone trend_matrix y delta_matrix en la jerarquia del perfil elegido.

    PURA a proposito: recibe los bloques ya calculados. No cambia ningun dato bruto, solo
    decide que marco manda, cual confirma y cual solo ejecuta. `medium_term_alignment` de
    trend_matrix devolvia "mixto" y ahi se acababa la explicacion; aqui la contradiccion se
    localiza en una capa concreta y se dice si invalida o solo obliga a esperar.
    """
    if profile not in TRADING_PROFILES:
        raise ValueError(f"perfil desconocido: {profile}")
    spec = TRADING_PROFILES[profile]
    tf_struct = trend.get("timeframes") or {}
    tf_flow = {str(row.get("window")): row for row in matrix}

    layers: dict[str, Any] = {}
    total_weight = 0.0
    weighted = 0.0
    for name, conf in spec["layers"].items():
        entries = []
        votes = []
        for tf in conf["timeframes"]:
            if tf in tf_struct:
                bias = str(tf_struct[tf].get("bias") or "neutral")
                detail = tf_struct[tf].get("flow_state")
                source = "trend_matrix"
            elif tf in tf_flow:
                bias, detail = _flow_bias(tf_flow[tf])
                source = "delta_matrix"
            else:
                bias, detail, source = "sin_datos", "temporalidad no disponible", "ninguna"
            entries.append(
                {"timeframe": tf, "bias": bias, "detail": detail, "source": source}
            )
            if bias in _BIAS_VOTE:
                votes.append(_BIAS_VOTE[bias])
        up = sum(1 for v in votes if v > 0)
        down = sum(1 for v in votes if v < 0)
        measurable = len(votes)
        if not measurable:
            layer_bias, score = "sin_datos", None
        elif up > down:
            layer_bias, score = "alcista", (up - down) / measurable
        elif down > up:
            layer_bias, score = "bajista", (up - down) / measurable
        else:
            layer_bias, score = ("neutral" if up == 0 else "conflicto"), 0.0
        # El peso de la capa se escala por la fraccion de marcos MEDIDOS. Antes bastaba una
        # sola temporalidad para que la capa aportara su peso completo, asi que 1/2 + 1/3 +
        # 1/2 se publicaba como cobertura 100%: la ponderada real de ese caso es 42.5%.
        share = (measurable / len(conf["timeframes"])) if conf["timeframes"] else 0.0
        effective = conf["weight"] * share
        if score is not None:
            total_weight += effective
            weighted += score * effective
        layers[name] = {
            "weight": conf["weight"],
            "effective_weight": round(effective, 2),
            "timeframes": entries,
            "bias": layer_bias,
            "score": None if score is None else round(score, 3),
            "contribution": None if score is None else round(score * effective, 2),
            "measurable_timeframes": measurable,
            "expected_timeframes": len(conf["timeframes"]),
        }

    net = (weighted / total_weight) if total_weight else None
    if net is None:
        bias = "sin_datos"
    elif net > 0.15:
        bias = "alcista"
    elif net < -0.15:
        bias = "bajista"
    else:
        bias = "neutral"

    ordered = list(spec["layers"])
    context_layer_name = ordered[0]
    context_bias = layers[context_layer_name]["bias"]
    confirm_layer_name = ordered[1]
    exec_layer = ordered[-1]

    directional = ("alcista", "bajista")
    contradictions = []
    # TODA capa se contrasta contra la de contexto, no solo la segunda y la ultima. Con tres
    # capas daba igual; el perfil swing tiene cuatro (contexto, confirmacion, entrada,
    # ejecucion) y la de entrada se quedaba sin comprobar.
    #
    # El EFECTO depende de que capa discrepe:
    #   confirmacion -> invalida: contradice el marco que manda en este perfil;
    #   ejecucion/gatillo -> invalida solo si el perfil deja que el gatillo mande;
    #   capas intermedias (entrada) -> esperar: piden mejor precio, no cambian la tesis.
    for name in ordered[1:]:
        layer_bias = layers[name]["bias"]
        if (
            context_bias not in directional
            or layer_bias not in directional
            or layer_bias == context_bias
        ):
            continue
        if name == confirm_layer_name:
            efecto = "invalida"
            motivo = "la confirmacion contradice el marco que manda en este perfil"
        elif name == exec_layer:
            efecto = "invalida" if spec["trigger_can_invalidate"] else "esperar"
            motivo = (
                "en intradia el gatillo manda la entrada"
                if spec["trigger_can_invalidate"]
                else "ruido de ejecucion: no tumba una tesis de varios dias, "
                "solo aconseja esperar mejor entrada"
            )
        else:
            efecto = "esperar"
            motivo = (
                f"la capa de {name} discrepa del contexto: aconseja esperar mejor precio, "
                "no cambia la tesis"
            )
        contradictions.append(
            {
                "entre": f"{context_layer_name} vs {name}",
                "detalle": f"contexto {context_bias} contra {name} {layer_bias}",
                "efecto": efecto,
                "motivo": motivo,
            }
        )
    for name, layer in layers.items():
        if layer["bias"] == "conflicto":
            contradictions.append(
                {
                    "entre": name,
                    "detalle": "las temporalidades de la capa se contradicen entre si",
                    "efecto": "esperar",
                    "motivo": "sin acuerdo dentro de la propia capa no hay lectura",
                }
            )

    missing = [
        f"{name}: {layer['measurable_timeframes']}/{layer['expected_timeframes']}"
        for name, layer in layers.items()
        if layer["measurable_timeframes"] < layer["expected_timeframes"]
    ]
    coverage = round(total_weight / sum(c["weight"] for c in spec["layers"].values()) * 100, 1)
    if coverage >= 90 and not contradictions:
        confidence = "alta"
    elif coverage >= 60:
        confidence = "media"
    else:
        confidence = "baja"
    if any(c["efecto"] == "invalida" for c in contradictions):
        confidence = "baja"

    return {
        "profile": profile,
        "profile_label": spec["label"],
        "bias": bias,
        "net_score": None if net is None else round(net, 3),
        "confidence": confidence,
        "coverage_pct": coverage,
        "layers": layers,
        "reference_only": list(spec["reference_only"]),
        "contradictions": contradictions,
        "missing_data": missing,
        "weights_note": (
            "Los pesos por capa son una convencion declarada, no un resultado backtesteado. "
            "Se publican junto a la contribucion de cada capa para que el sesgo sea auditable."
        ),
        "invalidation": (
            "La tesis se invalida si la capa de contexto cambia de signo"
            + (
                " o si el gatillo se gira en contra."
                if spec["trigger_can_invalidate"]
                else "; el flujo de 30s/1m NO la invalida por si solo."
            )
        ),
    }


# ---------------- hipotesis manual: clasificar evidencia, nunca emitir una orden ----------------
HYPOTHESES = {
    "long": {"label": "Long", "direction": 1},
    "short": {"label": "Short", "direction": -1},
    "neutral": {"label": "Neutral", "direction": 0},
    "esperando_ruptura": {"label": "Esperando ruptura", "direction": None},
    "esperando_rechazo": {"label": "Esperando rechazo", "direction": None},
    "esperando_reversion": {"label": "Esperando reversión", "direction": None},
    "esperando_continuacion": {"label": "Esperando continuación", "direction": None},
}

_BIAS_DIRECTION = {"alcista": 1, "bajista": -1}


def hypothesis_evidence(
    hypothesis: str | None = None,
    profile: dict[str, Any] | None = None,
    scalp: dict[str, Any] | None = None,
    *,
    direction: str | None = None,
    setup: str = "ninguno",
    setup_context: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Reparte la evidencia disponible respecto de la tesis que pone el OPERADOR.

    PURA: recibe bloques ya calculados. No decide la operacion ni emite una orden; ordena lo
    que hay en A FAVOR / EN CONTRA / NEUTRAL / PENDIENTE / NO EVALUABLE, que es lo que hace
    falta para confirmar o descartar una tesis propia.

    La tesis son ahora DOS cosas: la `direction` (long/short/neutral), que decide como votan
    las capas del perfil, y el `setup` (ruptura/rechazo/reversion/continuacion), que decide
    QUE tiene que pasar para confirmarla y se evalua en `app.setups` con logica propia. El
    parametro `hypothesis` se mantiene para los valores guardados de la version anterior.
    """
    profile = profile or {}
    scalp = scalp or {}
    if direction is None:
        if hypothesis is not None and hypothesis not in LEGACY_HYPOTHESES:
            raise ValueError(f"hipotesis desconocida: {hypothesis}")
        direction, setup_legacy = split_hypothesis(hypothesis)
        if setup == "ninguno":
            setup = setup_legacy
    if direction not in DIRECTIONS:
        raise ValueError(f"direccion desconocida: {direction}")
    if setup != "ninguno" and setup not in SETUP_SPECS:
        raise ValueError(f"setup desconocido: {setup}")
    # Como votan las capas del perfil:
    #   long/short  -> +1 / -1, la evidencia se reparte a favor y en contra;
    #   neutral SIN setup -> 0, tesis explicitamente lateral: un marco direccional la
    #     contradice (es el comportamiento que ya tenia la hipotesis "neutral");
    #   neutral CON setup -> None, el operador espera un gatillo y todavia no ha elegido
    #     lado, asi que ningun marco vota: quedan PENDIENTES (las viejas "esperando_*").
    if direction == "neutral":
        direction_sign: int | None = None if setup != "ninguno" else 0
    else:
        direction_sign = DIRECTIONS[direction]["sign"]
    buckets: dict[str, list[dict[str, Any]]] = {
        "a_favor": [],
        "en_contra": [],
        "neutral": [],
        "pendiente": [],
        "no_evaluable": [],
    }

    def add(bucket: str, signal: str, detail: str, source: str) -> None:
        buckets[bucket].append({"signal": signal, "detail": detail, "source": source})

    layers = profile.get("layers") or {}
    for name, layer in layers.items():
        bias = layer.get("bias")
        detail = (
            f"{bias} · {layer.get('measurable_timeframes')}/"
            f"{layer.get('expected_timeframes')} marcos · peso efectivo "
            f"{layer.get('effective_weight')}"
        )
        if bias in ("sin_datos", None):
            add("no_evaluable", f"Capa {name}", "sin marcos medibles", "perfil")
        elif bias == "conflicto":
            add("pendiente", f"Capa {name}", "las temporalidades se contradicen", "perfil")
        elif direction_sign is None:
            add("pendiente", f"Capa {name}", f"{detail}; la tesis aun no tiene direccion", "perfil")
        elif direction_sign == 0:
            add(
                "en_contra" if bias in _BIAS_DIRECTION else "a_favor",
                f"Capa {name}",
                detail,
                "perfil",
            )
        elif _BIAS_DIRECTION.get(bias) == direction_sign:
            add("a_favor", f"Capa {name}", detail, "perfil")
        else:
            add("en_contra", f"Capa {name}", detail, "perfil")

    absorption = str(scalp.get("absorption") or "")
    if absorption in ("No evaluable", "Sin datos", ""):
        add("no_evaluable", "Absorción 3m", absorption or "sin lectura", "scalp")
    elif absorption == "Sin señal":
        add("neutral", "Absorción 3m", "delta por debajo del umbral medido", "scalp")
    elif direction_sign is None or direction_sign == 0:
        add("pendiente", "Absorción 3m", absorption, "scalp")
    else:
        # Absorcion de VENTAS favorece al comprador; la de COMPRAS, al vendedor.
        add(
            "a_favor" if (1 if "ventas" in absorption else -1) == direction_sign else "en_contra",
            "Absorción 3m",
            absorption,
            "scalp",
        )

    basis_status = scalp.get("basis_status")
    if basis_status != "VALID":
        add("no_evaluable", "Basis", f"estado {basis_status}", "scalp")

    book_status = scalp.get("book_status")
    if book_status != "ok":
        add("no_evaluable", "Order book", f"estado {book_status}", "scalp")

    for name in scalp.get("missing_components") or []:
        add("no_evaluable", f"Componente {name}", "sin dato en la ventana", "scalp")

    contradictions = profile.get("contradictions") or []
    invalidations = [
        f"{c['detalle']} — {c['motivo']}" for c in contradictions if c.get("efecto") == "invalida"
    ]
    pending_conditions = [
        f"{c['detalle']} — {c['motivo']}" for c in contradictions if c.get("efecto") == "esperar"
    ]

    # El SETUP se evalua aparte y con su propia logica: sus requisitos, sus pendientes y sus
    # invalidaciones son distintos en ruptura, rechazo, reversion y continuacion.
    setup_read = evaluate_setup(setup, direction, setup_context or {})
    invalidations = [*invalidations, *setup_read["invalidaciones"]]
    pending_conditions = [
        *pending_conditions,
        *(f"{setup_read['label']}: falta {p}" for p in setup_read["pendientes"]),
    ]
    for nombre in setup_read.get("no_evaluables", []):
        add("no_evaluable", f"{setup_read['label']} · {nombre}", "sin observable", "setup")

    ordered = list(layers)
    context_layer = layers.get(ordered[0]) if ordered else {}
    timing_layer = layers.get(ordered[-1]) if ordered else {}
    spread = as_float(scalp.get("spread_bps"))
    plan = plan or {}
    execution = execution_assessment(
        profile=str(profile.get("profile") or "intradia"),
        spread_bps=spread,
        slippage_bps=as_float(plan.get("slippage_bps")),
        fee_bps_per_side=as_float(plan.get("fee_bps_per_side")),
        order_type=plan.get("order_type"),
        size_usd=as_float(plan.get("size_usd")),
        side=plan.get("side") or (direction if direction != "neutral" else None),
        exchange=plan.get("exchange"),
        entry=as_float(plan.get("entry")),
        target=as_float(plan.get("target")),
        stop=as_float(plan.get("stop")),
        funding_bps=as_float(plan.get("funding_bps")),
    )
    setup_ctx = setup_context or {}
    return {
        "hypothesis": hypothesis,
        "direction": direction,
        "direction_label": DIRECTIONS[direction]["label"],
        "setup": setup,
        "setup_label": SETUP_LABELS.get(setup, setup),
        "setup_state": setup_read["state"],
        "setup_evaluation": setup_read,
        "label": (
            DIRECTIONS[direction]["label"]
            if setup == "ninguno"
            else f"{DIRECTIONS[direction]['label']} · {SETUP_LABELS.get(setup, setup)}"
        ),
        "profile": profile.get("profile"),
        "context": (context_layer or {}).get("bias"),
        "timing": (timing_layer or {}).get("bias"),
        "data_coverage_pct": scalp.get("evidence_coverage_pct"),
        "profile_coverage_pct": profile.get("coverage_pct"),
        # Antes esto era una etiqueta binaria decidida por un umbral fijo de spread, y se
        # publicaba con vocabulario intradia incluso sobre una tesis swing de varios dias.
        # Ahora la ejecucion se evalua con el coste completo y, mientras no haya
        # objetivo/stop/comision/tamano, queda explicitamente SIN EVALUAR.
        "execution": execution,
        "spread_bps": spread,
        "evidence": buckets,
        "counts": {key: len(value) for key, value in buckets.items()},
        "pending_conditions": pending_conditions,
        "invalidations": invalidations,
        "setup_observables": setup_ctx.get("observables"),
        "setup_zone": {
            "zone_low": setup_ctx.get("zone_low"),
            "zone_high": setup_ctx.get("zone_high"),
            "zone_center": setup_ctx.get("zone_center"),
            "breakout_boundary": setup_ctx.get("breakout_boundary"),
        },
        "note": (
            "Clasificacion de evidencia sobre una hipotesis del operador. No es una "
            "recomendacion y no ejecuta ninguna operacion."
        ),
    }


def walk_book(levels: list[list[float]], size_usd: float) -> dict[str, Any]:
    """Consume la escalera hasta cubrir size_usd y devuelve el precio medio de ejecucion.

    `levels` viene ordenada de mejor a peor (bids descendente, asks ascendente). El ultimo
    nivel se consume PARCIALMENTE si sobra, que es como se ejecuta de verdad.

    Si la profundidad publicada no alcanza, NO se extrapola: se devuelve `insufficient` con
    lo que faltaba. Inventar el resto seria justo el tipo de precision falsa que el resto del
    dashboard evita.
    """
    if size_usd <= 0:
        raise ValueError("size_usd must be positive")
    # El primer nivel PUBLICADO puede ser basura (precio 0, cantidad 0, no finito). Tomarlo
    # como referencia daba best_price=0 y, al ser falsy, dejaba el slippage en None mientras
    # el precio medio si se calculaba: una fila con precio medio y sin coste.
    valid = [
        (p, q)
        for p, q in levels
        if as_float(p) is not None and as_float(q) is not None and p > 0 and q > 0
    ]
    best = valid[0][0] if valid else None
    remaining = size_usd
    base_qty = 0.0
    used = 0
    for price, qty in valid:
        available = price * qty
        take = min(remaining, available)
        base_qty += take / price
        used += 1
        remaining -= take
        if remaining <= 1e-6:
            remaining = 0.0
            break
    filled = size_usd - remaining
    avg_price = (filled / base_qty) if base_qty > 0 else None
    slippage_bps = (
        (avg_price - best) / best * 10_000 if avg_price is not None and best else None
    )
    return {
        "size_usd": size_usd,
        "best_price": best,
        "avg_price": avg_price,
        "levels_used": used,
        "levels_available": len(valid),
        "levels_discarded": len(levels) - len(valid),
        "filled_usd": round(filled, 2),
        "shortfall_usd": round(remaining, 2),
        "insufficient_depth": remaining > 0,
        # En una compra se recorre el ask hacia arriba y en una venta el bid hacia abajo, asi
        # que el signo sale positivo en ambos casos: siempre es coste.
        "slippage_bps": abs(slippage_bps) if slippage_bps is not None else None,
    }


# Aviso SECUNDARIO de spread ancho, por perfil. NO es un veto y no clasifica la operacion:
# solo marca que el spread esta fuera de lo habitual para ese horizonte. Los numeros son una
# convencion declarada (se publican en la respuesta), no un resultado medido; la decision de
# ejecucion la toma el cociente coste/objetivo.
EXECUTION_PROFILES: dict[str, dict[str, Any]] = {
    "intradia": {
        "label": "Intradía ≤ 4 h",
        "spread_warn_bps": 5.0,
        "horizon": "≤ 4 h",
        "note": "objetivos de decenas de bps: el coste pesa mucho en proporcion",
    },
    "swing": {
        "label": "Swing varios días",
        "spread_warn_bps": 25.0,
        "horizon": "días",
        "note": "objetivos de cientos de bps: el mismo spread pesa un orden de magnitud menos",
    },
}

# Fracciones del OBJETIVO que se come el coste total de ida y vuelta. Convencion declarada.
COST_TO_TARGET_BANDS = ((0.10, "aceptable"), (0.25, "ajustado"))
COST_TO_RISK_BANDS = ((0.15, "aceptable"), (0.35, "ajustado"))


def _bps(desde: float | None, hasta: float | None) -> float | None:
    """Distancia entre dos precios en puntos basicos, o None si falta alguno."""
    if desde is None or hasta is None or desde == 0:
        return None
    return abs(hasta - desde) / desde * 10_000


def _banda(ratio: float | None, bandas: tuple[tuple[float, str], ...]) -> str | None:
    if ratio is None:
        return None
    for limite, etiqueta in bandas:
        if ratio <= limite:
            return etiqueta
    return "prohibitivo"


def execution_assessment(
    *,
    profile: str,
    spread_bps: float | None = None,
    slippage_bps: float | None = None,
    fee_bps_per_side: float | None = None,
    order_type: str | None = None,
    size_usd: float | None = None,
    side: str | None = None,
    exchange: str | None = None,
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    funding_bps: float | None = None,
    spread_percentile: float | None = None,
) -> dict[str, Any]:
    """¿Cuanto se come la ejecucion del objetivo y del riesgo de ESTA operacion?

    PURA. Sustituye a la clasificacion universal `spread > 5 bps`, que decia "caro para
    intradía" incluso sobre una tesis swing de varios dias. Aqui la pregunta correcta no es
    cuanto vale el spread sino que FRACCION del objetivo se lleva el coste total de ida y
    vuelta, y esa fraccion depende del objetivo, del tamano, del venue y de las comisiones.

    Fail-closed: si falta objetivo, stop, comision o tamano, el veredicto es SIN EVALUAR y se
    enumera lo que falta. No se inventan comisiones "tipicas" ni un objetivo por defecto.
    """
    spec = EXECUTION_PROFILES.get(profile) or EXECUTION_PROFILES["intradia"]
    faltan: list[str] = []
    if entry is None:
        faltan.append("entrada")
    if target is None:
        faltan.append("objetivo")
    if stop is None:
        faltan.append("stop")
    if fee_bps_per_side is None:
        faltan.append("comision")
    if size_usd is None:
        faltan.append("tamaño")

    # Coste de IDA Y VUELTA. El spread se cruza una vez (entrar a mercado) y el slippage se
    # paga en las dos patas; la comision, en las dos. El funding solo aplica si se declara.
    componentes: dict[str, float | None] = {
        "spread_bps": spread_bps,
        "fees_bps": None if fee_bps_per_side is None else fee_bps_per_side * 2,
        "slippage_bps": None if slippage_bps is None else slippage_bps * 2,
        "funding_bps": funding_bps,
    }
    medidos = [v for v in componentes.values() if v is not None]
    total_cost_bps = round(sum(medidos), 3) if medidos else None
    componentes_ausentes = [k for k, v in componentes.items() if v is None]

    target_bps = _bps(entry, target)
    risk_bps = _bps(entry, stop)
    cost_to_target = (
        total_cost_bps / target_bps
        if total_cost_bps is not None and target_bps is not None and target_bps > 0
        else None
    )
    cost_to_risk = (
        total_cost_bps / risk_bps
        if total_cost_bps is not None and risk_bps is not None and risk_bps > 0
        else None
    )
    banda_objetivo = _banda(cost_to_target, COST_TO_TARGET_BANDS)
    banda_riesgo = _banda(cost_to_risk, COST_TO_RISK_BANDS)

    if faltan or cost_to_target is None:
        status, verdict = "SIN EVALUAR", "SIN EVALUAR"
    else:
        # Manda la peor de las dos lecturas: una operacion cuyo coste se come el objetivo no
        # se salva porque el stop este lejos.
        orden = ("aceptable", "ajustado", "prohibitivo")
        peor = max(
            (b for b in (banda_objetivo, banda_riesgo) if b is not None),
            key=orden.index,
        )
        status, verdict = "EVALUADO", peor

    aviso = None
    umbral = spec["spread_warn_bps"]
    if spread_bps is not None and spread_bps > umbral:
        aviso = (
            f"spread {spread_bps:.2f} bps por encima del aviso de {umbral:.0f} bps "
            f"para perfil {profile} ({spec['horizon']}). Es un AVISO, no un veto: "
            "el veredicto sale del coste sobre el objetivo."
        )
    return {
        "profile": profile,
        "profile_label": spec["label"],
        "horizon": spec["horizon"],
        "status": status,
        "verdict": verdict,
        "total_cost_bps": total_cost_bps,
        "cost_components_bps": componentes,
        "cost_components_missing": componentes_ausentes,
        "target_bps": None if target_bps is None else round(target_bps, 2),
        "risk_bps": None if risk_bps is None else round(risk_bps, 2),
        "cost_to_target": None if cost_to_target is None else round(cost_to_target, 4),
        "cost_to_risk": None if cost_to_risk is None else round(cost_to_risk, 4),
        "cost_to_target_band": banda_objetivo,
        "cost_to_risk_band": banda_riesgo,
        "missing_inputs": faltan,
        "inputs": {
            "entry": entry,
            "target": target,
            "stop": stop,
            "size_usd": size_usd,
            "side": side,
            "order_type": order_type,
            "exchange": exchange,
            "fee_bps_per_side": fee_bps_per_side,
            "spread_percentile": spread_percentile,
        },
        "spread_warning": aviso,
        "spread_warn_bps": umbral,
        "bands_note": (
            "Bandas sobre coste/objetivo "
            f"({COST_TO_TARGET_BANDS[0][0]:.0%} aceptable, {COST_TO_TARGET_BANDS[1][0]:.0%} "
            "ajustado) y coste/riesgo. Son una convencion declarada, no un resultado "
            "backtesteado, y por eso viajan en la respuesta."
        ),
        "note": (
            "Coste de ida y vuelta contra el objetivo de ESTA operacion. Sin objetivo, stop, "
            "comision o tamano no hay veredicto: SIN EVALUAR."
        ),
    }


async def execution_cost(
    conn: asyncpg.Connection, symbol: str, sizes_usd: list[float]
) -> dict[str, Any]:
    """Coste de ejecutar cada tamanio, POR VENUE.

    Deliberadamente no hay venue 'combined': una orden se ejecuta en un solo sitio. El libro
    agregado de `orderbook_snapshot` suma profundidad de los dos venues pero toma el spread
    del mas estrecho, lo que no corresponde a nada ejecutable.
    """
    rows = await conn.fetch(
        "SELECT exchange,ts,bids,asks,levels,"
        "EXTRACT(EPOCH FROM now()-ts)::float8 AS age_seconds "
        "FROM orderbook_depth WHERE symbol=$1 ORDER BY exchange",
        symbol,
    )
    venues: list[dict[str, Any]] = []
    for row in rows:
        age = as_float(row["age_seconds"])
        # Edad desconocida no es edad valida: sin saber de cuando es el libro, el coste que
        # se calcule sobre el no significa nada.
        if age is None:
            usable, status = False, "UNAVAILABLE"
        elif age < -CLOCK_TOLERANCE_SECONDS:
            usable, status = False, "ERROR"
        elif age > REALTIME_STALE_SECONDS:
            usable, status = False, "STALE"
        else:
            usable, status = True, "VALID"
        bids = json.loads(row["bids"]) if isinstance(row["bids"], str) else row["bids"]
        asks = json.loads(row["asks"]) if isinstance(row["asks"], str) else row["asks"]
        venues.append(
            {
                "exchange": row["exchange"],
                "ts": row["ts"],
                "age_seconds": round(age, 1) if age is not None else None,
                "levels": row["levels"],
                "status": status,
                # Un libro desfasado o sin edad conocida no sirve para estimar coste.
                "buy": [walk_book(asks, s) for s in sizes_usd] if usable else None,
                "sell": [walk_book(bids, s) for s in sizes_usd] if usable else None,
            }
        )
    return {
        "symbol": symbol,
        "unit": "USD",
        "sizes_usd": sizes_usd,
        "stale_after_seconds": REALTIME_STALE_SECONDS,
        "note": "coste por venue; no existe 'combined' porque una orden se ejecuta en uno solo",
        "venues": venues,
        "status": "VALID" if any(v["status"] == "VALID" for v in venues) else "UNAVAILABLE",
    }


IMPACT_WINDOWS = (("5m", 300), ("15m", 900), ("18m", 1080), ("1h", 3600))


async def market_impact(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Impacto REALIZADO: bps que se movio el precio por cada 1M USD de delta neto.

    Medido, no modelado: la referencia sale de `metric_baseline` sobre la misma serie. A 15 m
    la mediana historica es 0.93 bps/M en BTC, 1.67 en ETH y 10.25 en SOL, o sea que el mismo
    flujo mueve SOL once veces mas; comparar activos sin esa escala no significa nada.

    Como leerlo: impacto MUY por debajo de su mediana = el mercado esta absorbiendo el flujo
    (hay contrapartida); muy por encima = el libro esta fino y cualquier orden mueve el precio.
    No dice direccion, dice cuanto cuesta empujar.

    OJO con lo que NO es: no es el slippage de tu orden (eso es /api/scalp/execution-cost,
    que recorre el libro actual). Esto es el comportamiento agregado del mercado.
    """
    baselines = await load_baselines(conn, symbol, "impact_bps_per_musd")
    windows: list[dict[str, Any]] = []
    for label, seconds in IMPACT_WINDOWS:
        row = await conn.fetchrow(
            """
            SELECT (array_agg(open ORDER BY ts))[1] AS px_open,
                   (array_agg(close ORDER BY ts DESC))[1] AS px_close,
                   SUM(delta) AS delta, SUM(volume) AS volume, COUNT(*)::int AS mins,
                   -- Contar filas no prueba continuidad: un minuto de mas en un borde puede
                   -- compensar a uno que falta en medio. El span mide el hueco de verdad.
                   (EXTRACT(EPOCH FROM max(ts)-min(ts))/60.0)::float8 AS span_minutes
            FROM ohlcv
            WHERE symbol=$1 AND interval='1min' AND ts >= now()-($2::int*interval '1 second')
            """,
            symbol,
            seconds,
        )
        mins = int(row["mins"] or 0) if row else 0
        span = as_float(row["span_minutes"]) if row else None
        expected_minutes = seconds // 60
        contiguous = (
            mins >= expected_minutes
            and span is not None
            and abs(span - (mins - 1)) < 0.5
        )
        px_open = as_float(row["px_open"]) if row else None
        px_close = as_float(row["px_close"]) if row else None
        delta = as_float(row["delta"]) if row else None
        expected = seconds // 60
        impact = None
        delta_musd = None
        if px_open and px_close and delta is not None:
            delta_musd = abs(delta) * px_close / 1e6
            # Dividir por un delta despreciable da un impacto enorme que no significa nada.
            if delta_musd > 0.01:
                impact = (abs(px_close - px_open) / px_open * 10000) / delta_musd
        context = baseline_band(impact, baselines.get(label))
        windows.append(
            {
                "window": label,
                "impact_bps_per_musd": round(impact, 3) if impact is not None else None,
                "net_delta_musd": round(delta_musd, 3) if delta_musd is not None else None,
                "price_move_bps": (
                    round(abs(px_close - px_open) / px_open * 10000, 2)
                    if px_open and px_close
                    else None
                ),
                # La ventana incompleta se declara: menos minutos = menos flujo y el ratio
                # sale inflado por construccion.
                "coverage": f"{mins}/{expected}",
                # Completa = tantas velas como minutos Y contiguas (span = n-1 minutos).
                "coverage_complete": contiguous,
                "internal_gap_minutes": (
                    round(span - (mins - 1), 1) if span is not None and mins > 1 else None
                ),
                "context": context,
                "reading": (
                    None
                    if context.get("band") is None
                    else {
                        "bajo": "el mercado absorbe: mucho flujo movio poco precio",
                        "normal": "impacto en su rango habitual",
                        "elevado": "el libro empieza a ceder mas de lo normal",
                        "alto": "libro fino: el precio se mueve facil con poco flujo",
                        "extremo": "libro muy fino o movimiento no explicado por el flujo agresivo",
                    }[context["band"]]
                ),
            }
        )
    return {
        "symbol": symbol,
        "metric": "impact_bps_per_musd",
        "definition": "|cambio de precio en bps| / (|delta neto| en millones de USD)",
        "windows": windows,
        "limitations": [
            "Es impacto agregado del mercado, no el slippage de una orden concreta.",
            "Correlacion, no causalidad: el precio tambien se mueve por flujo pasivo y noticias.",
            "El delta sale del perp de Binance (ohlcv .A), no de los dos venues.",
        ],
    }


async def positioning_context(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    """Reparto long/short de la multitud, con percentil contra su propia historia.

    Es informacion que NO se deduce de OI, funding ni CVD: esos dicen cuanto notional hay y
    a que precio se agrede, no como esta repartida la posicion. El valor absoluto dice poco
    (el ratio suele vivir por encima de 1 casi siempre); lo que informa es donde cae respecto
    de su propio historico, por eso se publica el percentil y no solo el numero.
    """
    row = await conn.fetchrow(
        """
        WITH cur AS (
          SELECT ts,long_pct,short_pct,ratio FROM long_short_ratio
          WHERE symbol=$1 AND interval='5min' ORDER BY ts DESC LIMIT 1
        ), hist AS (
          SELECT ratio, ts FROM long_short_ratio
          WHERE symbol=$1 AND interval='5min' AND ts >= now()-interval '30 days'
        ), ago AS (
          -- Anclado a la fila VIGENTE, no a now(): si la serie va retrasada, comparar contra
          -- "hace 24 h desde ahora" mide una ventana distinta de 24 h.
          SELECT l.ratio FROM long_short_ratio l, cur
          WHERE l.symbol=$1 AND l.interval='5min' AND l.ts <= cur.ts-interval '24 hours'
          ORDER BY l.ts DESC LIMIT 1
        )
        SELECT cur.ts,cur.long_pct,cur.short_pct,cur.ratio,
               ago.ratio AS ratio_24h_ago,
               (SELECT count(*) FROM hist)::int AS sample_count,
               (SELECT count(*) FROM hist WHERE hist.ratio <= cur.ratio)::int AS below,
               (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY ratio) FROM hist) AS median,
               -- Span REAL de la muestra: la ingesta empieza vacia y llamar "30 dias" a 26
               -- horas de historia seria exactamente la precision falsa que esto evita.
               (SELECT (EXTRACT(EPOCH FROM max(ts)-min(ts))/86400.0)::float8 FROM hist) AS sample_days,
               EXTRACT(EPOCH FROM now()-cur.ts)::float8 AS age_seconds
        FROM cur LEFT JOIN ago ON true
        """,
        symbol,
    )
    if not row or row["ratio"] is None:
        return {"symbol": symbol, "status": "UNAVAILABLE", "reason": "sin datos de posicionamiento"}
    n = int(row["sample_count"] or 0)
    ratio = as_float(row["ratio"])
    prev = as_float(row["ratio_24h_ago"])
    age = as_float(row["age_seconds"])
    # Con menos de 24 h no hay percentil: se publica el dato crudo y se dice que el contexto
    # aun no existe, en vez de calcular un percentil sobre cuatro filas.
    percentile = round(int(row["below"]) / n * 100, 1) if n >= 288 else None
    sample_days = as_float(row["sample_days"])
    limitations = [
        "Es reparto de CUENTAS, no de notional: muchas cuentas pequenas pesan igual que una grande.",
        "Un ratio alto no implica que el precio deba bajar; solo dice como esta repartida la multitud.",
    ]
    # El percentil se compara contra lo ACUMULADO, no contra 30 dias, hasta que los haya.
    if percentile is not None and (sample_days or 0) < 25:
        limitations.append(
            f"El percentil se calcula sobre {sample_days:.1f} dias acumulados, no sobre 30: "
            "la serie empezo a ingerirse hace poco y aun no cubre un mes."
        )
    return {
        "symbol": symbol,
        "status": "STALE" if age is not None and age > 1800 else "VALID",
        "unit": "porcentaje de cuentas",
        "long_pct": as_float(row["long_pct"]),
        "short_pct": as_float(row["short_pct"]),
        "ratio": ratio,
        "ratio_24h_ago": prev,
        # `prev is not None`: un ratio 0 es una lectura, no una ausencia.
        "ratio_change_24h": (
            round(ratio - prev, 4) if ratio is not None and prev is not None else None
        ),
        "median_sample": round(as_float(row["median"]), 4) if row["median"] is not None else None,
        "percentile_sample": percentile,
        "sample_count": n,
        "sample_days": round(sample_days, 2) if sample_days is not None else None,
        "sample_is_full_month": bool(sample_days and sample_days >= 25),
        "ts": row["ts"],
        "age_seconds": round(age, 1) if age is not None else None,
        "limitations": limitations,
    }


async def spot_perp_flow(
    conn: asyncpg.Connection, symbol: str, interval: str, days: int
) -> dict[str, Any]:
    """Delta spot vs perp del MISMO venue (Binance), vela a vela, con historia real.

    Hasta v1.4.7 la pata spot solo existia en los colectores WS propios: 14 dias en
    `spot_trades_agg` y 2 h en el realtime. Coinalyze sirve spot con delta (`bv`/`btx`) a la
    misma profundidad que el perp, asi que aqui hay 300 dias a 4hour y ~2 anios a daily.

    Las dos patas son Binance (sufijo .A): la asimetria de v1.3.4 era comparar perp de
    Binance contra spot de Binance+Bybit. Aun asi el perp mueve ~10x el spot, por eso cada
    pata lleva su `delta_ratio` (delta/volumen) y la direccion la vota `flow_confirmation`
    con el signo de AMBAS, nunca con la resta.
    """
    spot_symbol = SPOT_HISTORY_MAP.get(symbol)
    if not spot_symbol:
        return {"symbol": symbol, "status": "UNAVAILABLE", "reason": "sin spot mapeado", "rows": []}
    if interval not in {"4hour", "daily"}:
        raise ValueError("unsupported interval for spot_perp_flow")
    as_of = datetime.now(UTC)
    rows = await conn.fetch(
        """
        WITH p AS (
          SELECT ts,close,delta*close AS delta_usd,volume*close AS volume_usd
          FROM ohlcv WHERE symbol=$1 AND interval=$3
            AND ts >= $5-($4::int*interval '1 day')
            AND ts + CASE WHEN $3='4hour' THEN interval '4 hours' ELSE interval '1 day' END <= $5
        ), s AS (
          SELECT ts,delta*close AS delta_usd,volume*close AS volume_usd
          FROM ohlcv WHERE symbol=$2 AND interval=$3
            AND ts >= $5-($4::int*interval '1 day')
            AND ts + CASE WHEN $3='4hour' THEN interval '4 hours' ELSE interval '1 day' END <= $5
        )
        -- LEFT JOIN a proposito: un bucket sin spot debe verse como hueco, no desaparecer.
        SELECT p.ts,p.close,
               p.delta_usd AS perp_delta_usd,p.volume_usd AS perp_volume_usd,
               s.delta_usd AS spot_delta_usd,s.volume_usd AS spot_volume_usd
        FROM p LEFT JOIN s ON s.ts=p.ts
        ORDER BY p.ts
        """,
        symbol,
        spot_symbol,
        interval,
        days,
        as_of,
    )
    out: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    both = 0
    for row in rows:
        perp_delta = as_float(row["perp_delta_usd"])
        spot_delta = as_float(row["spot_delta_usd"])
        perp_vol = as_float(row["perp_volume_usd"])
        spot_vol = as_float(row["spot_volume_usd"])
        confirm = flow_confirmation(spot_delta, perp_delta)
        counts[confirm["state"]] = counts.get(confirm["state"], 0) + 1
        if spot_delta is not None and perp_delta is not None:
            both += 1
        out.append(
            {
                "ts": row["ts"],
                "close": as_float(row["close"]),
                "perp_delta_usd": perp_delta,
                "spot_delta_usd": spot_delta,
                "perp_volume_usd": perp_vol,
                "spot_volume_usd": spot_vol,
                "perp_delta_ratio": (perp_delta / perp_vol) if perp_delta is not None and perp_vol else None,
                "spot_delta_ratio": (spot_delta / spot_vol) if spot_delta is not None and spot_vol else None,
                # El perp mueve mucho mas notional: sin esta escala el lector compara
                # magnitudes que no son comparables.
                "perp_over_spot_volume": (perp_vol / spot_vol) if perp_vol and spot_vol else None,
                "flow_state": confirm["state"],
                "legs_agree": confirm["agreement"],
                "vote": confirm["vote"],
            }
        )
    return {
        "symbol": symbol,
        "spot_symbol": spot_symbol,
        "venue": "binance (perp .A vs spot .A)",
        "interval": interval,
        "unit": "USD",
        "buckets": len(out),
        "buckets_with_both_legs": both,
        "coverage_pct": round(both / len(out) * 100, 1) if out else 0.0,
        "status": "COMPLETE" if out and both == len(out) else ("PARTIAL" if both else "UNAVAILABLE"),
        "state_counts": counts,
        "rows": out,
    }


def _classify_passive(fut_delta, fut_vol, price_move_pct, spot_delta, location, atr_pct):
    """Detecta absorcion por limites pasivos y la mapea a reacumulacion/redistribucion.

    La confirmacion es el signo del CVD **spot**, no el del diferencial spot-futuros: con
    el perp moviendo ~10x el spot, `diff < 0` se cumple casi siempre que los futuros compran,
    asi que exigirlo junto a `fut_delta > 0` era contar dos veces la misma observacion. El
    spot es la unica pata independiente del flujo agresivo que se esta absorbiendo.
    # ponytail: umbral de movimiento fijo (1/2 ATR). El de magnitud lo comparte con
    # classify_absorption via ABSORPTION_MIN_RATIO. Ajustar si da ruido."""
    directional = (abs(fut_delta) / fut_vol) if fut_vol > 0 else 0.0
    move_tol = 0.5 * (atr_pct or 0.4)  # "no se movio" = menos de medio ATR% de la ventana
    absorbed = None
    if directional >= ABSORPTION_MIN_RATIO and fut_vol > 0:
        if fut_delta < 0 and price_move_pct >= -move_tol:
            absorbed = "ventas"  # venden agresivo y el precio aguanta -> bids limite absorben
        elif fut_delta > 0 and price_move_pct <= move_tol:
            absorbed = "compras"  # compran agresivo y el precio no sube -> asks limite absorben
    reading, conf = "neutral", "baja"
    if spot_delta is None:
        return absorbed, reading, conf, round(directional, 3)
    if absorbed == "ventas" and spot_delta > 0 and location in ("bajo_valor", "en_valor"):
        reading, conf = (
            "reacumulacion_silenciosa",
            ("alta" if location == "bajo_valor" else "media"),
        )
    elif absorbed == "compras" and spot_delta < 0 and location in ("alto_valor", "en_valor"):
        reading, conf = (
            "redistribucion_silenciosa",
            ("alta" if location == "alto_valor" else "media"),
        )
    return absorbed, reading, conf, round(directional, 3)


async def passive_flow(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    vp = await volume_profile(conn, symbol)
    prof = (vp or {}).get("session") or {}
    poc, vah, val = prof.get("poc"), prof.get("vah"), prof.get("val")
    px_now = as_float(
        await conn.fetchval(
            "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    if px_now and poc is not None and vah is not None and val is not None:
        loc = "alto_valor" if px_now >= vah else ("bajo_valor" if px_now <= val else "en_valor")
    else:
        loc = "s/d"
    ws = WS_SYMBOL_MAP[symbol]
    spot_flows = await spot_flow_windows(conn, ws, _PF_HORIZONS)
    counts = {"reacumulacion_silenciosa": 0, "redistribucion_silenciosa": 0, "neutral": 0}
    out = {}
    for lab, sec in _PF_HORIZONS:
        futures = await _realtime_flow(conn, "futures_trades_realtime", symbol, sec)
        spot = (spot_flows.get(lab) or {}).get("combined") or {}
        flow_complete = bool(futures.get("complete")) and bool(spot.get("complete"))
        fut_delta = as_float(futures.get("delta")) if futures.get("complete") else None
        fut_vol = as_float(futures.get("volume")) if futures.get("complete") else None
        spot_delta = as_float(spot.get("delta")) if spot.get("complete") else None
        diff = spot_delta - fut_delta if spot_delta is not None and fut_delta is not None else None
        bars = await _resample_highs_lows(conn, symbol, sec, 40)
        atr = _atr(bars, 14)
        close = as_float(bars[-1]["close"]) if bars else px_now
        atr_pct = (atr / close * 100) if (atr and close) else None
        px_ago = as_float(
            await conn.fetchval(
                "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts <= now()-($2::int*interval '1 second') "
                "ORDER BY ts DESC LIMIT 1",
                symbol,
                sec,
            )
        )
        # Sin precio de referencia el movimiento es DESCONOCIDO, no cero: un 0.0 inventado
        # hace que _classify_passive lea "el precio aguanto" y dispare absorcion falsa.
        price_move_pct = ((px_now / px_ago - 1) * 100) if (px_now and px_ago) else None
        oi_chg = await _oi_change_pct(conn, symbol, sec)
        if (
            flow_complete
            and fut_delta is not None
            and fut_vol is not None
            and spot_delta is not None
            and price_move_pct is not None
        ):
            absorbed, reading, conf, directional = _classify_passive(
                fut_delta, fut_vol, price_move_pct, spot_delta, loc, atr_pct
            )
        else:
            absorbed, reading, conf, directional = None, "neutral", "baja", 0.0
        counts[reading] += 1
        confirm = flow_confirmation(spot_delta, fut_delta)
        out[lab] = {
            "fut_delta_usd": round(fut_delta) if fut_delta is not None else None,
            "spot_delta_usd": round(spot_delta) if spot_delta is not None else None,
            "diff_usd": round(diff) if diff is not None else None,
            "flow_state": confirm["state"],
            "legs_agree": confirm["agreement"],
            "price_move_pct": round(price_move_pct, 3) if price_move_pct is not None else None,
            "absorption": absorbed or "ninguna",
            "absorbed_usd_per_pct": (
                round(abs(fut_delta) / max(abs(price_move_pct), 0.02))
                if fut_delta is not None
                and fut_vol
                and fut_vol > 0
                and price_move_pct is not None
                else None
            ),
            "directional_ratio": directional,
            "oi_change_pct": round(oi_chg, 3) if oi_chg is not None else None,
            "reading": reading,
            "confidence": conf,
            "coverage_status": "complete" if flow_complete else "partial",
            "spot_source": spot.get("source", "unavailable"),
        }
    dom = max(("reacumulacion_silenciosa", "redistribucion_silenciosa"), key=lambda k: counts[k])
    summary = dom if counts[dom] >= 2 else "neutral"
    return {
        "symbol": symbol,
        "price": px_now,
        "location": loc,
        "value_area": {"poc": poc, "vah": vah, "val": val},
        "horizons": out,
        "summary": summary,
        "counts": counts,
        "note": "manos silenciosas inferidas por absorcion de flujo agresivo (limites pasivos) + diff spot/fut + "
        "ubicacion en value area + OI. absorbed_usd_per_pct = delta agresivo USD por cada % de precio. "
        "NO detecta icebergs reales (requiere libro por-orden).",
    }


# ---------------- tendencia multi-timeframe (15m-3d): sesgo por marco ----------------
_TREND_TF = (
    ("15m", 900, "intra"),
    ("1h", 3600, "intra"),
    ("4h", 14400, "intra"),
    ("8h", 28800, "intra"),
    ("1d", 1, "daily"),
    ("3d", 3, "daily"),
)


async def trend_matrix(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    ws = WS_SYMBOL_MAP[symbol]
    px_now = as_float(
        await conn.fetchval(
            "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1",
            symbol,
        )
    )
    drows = [
        dict(r)
        for r in await conn.fetch(
            "SELECT session_date, price_close, cvd_spot_usd, oi_close FROM daily_session_agg "
            "WHERE symbol=$1 ORDER BY session_date DESC LIMIT 60",
            symbol,
        )
    ]
    daily = list(reversed(drows))
    spot_flows = await spot_flow_windows(
        conn, ws, [(label, unit) for label, unit, kind in _TREND_TF if kind == "intra"]
    )
    tfs = {}
    for lab, unit, kind in _TREND_TF:
        st = None
        cvd_flow = oi_chg = mom = None
        flow_status = None
        spot_d = fut_d = None
        confirm: dict[str, Any] = {"vote": None, "state": "sin_datos", "agreement": None}
        if kind == "intra":
            sec = unit
            bars = await _resample_highs_lows(conn, symbol, sec, 60)
            if len(bars) >= 7:
                st = _structure_from_swings(
                    [as_float(b["high"]) for b in bars],
                    [as_float(b["low"]) for b in bars],
                    [b["bucket"].isoformat() for b in bars],
                    as_float(bars[-1]["close"]),
                    k=2,
                )["state"]
            futures = await _realtime_flow(conn, "futures_trades_realtime", symbol, sec)
            spot = (spot_flows.get(lab) or {}).get("combined") or {}
            flow_complete = bool(futures.get("complete")) and bool(spot.get("complete"))
            flow_status = "complete" if flow_complete else "partial"
            fut_d = as_float(futures.get("delta")) if futures.get("complete") else None
            spot_d = as_float(spot.get("delta")) if spot.get("complete") else None
            # cvd_flow se conserva como dato descriptivo, pero el VOTO sale de
            # flow_confirmation (signo de ambas patas), no del diferencial: ver su docstring.
            cvd_flow = spot_d - fut_d if spot_d is not None and fut_d is not None else None
            confirm = flow_confirmation(spot_d, fut_d)
            oi_chg = await _oi_change_pct(conn, symbol, sec)
            px_ago = as_float(
                await conn.fetchval(
                    "SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' AND ts <= now()-($2::int*interval '1 second') ORDER BY ts DESC LIMIT 1",
                    symbol,
                    sec,
                )
            )
            # Sin precio de referencia el momentum es desconocido; 0.0 lo haria pasar por
            # "plano" y ademas se publicaba como si fuera una medicion real.
            mom = ((px_now / px_ago - 1) * 100) if (px_now and px_ago) else None
        else:
            flow_status = "daily_aggregate"
            n = unit
            ds = [daily[i] for i in range(len(daily) - 1, -1, -n)][::-1]
            closes = [as_float(r["price_close"]) for r in ds if r["price_close"] is not None]
            if len(closes) >= 5:
                st = _structure_from_swings(
                    closes, closes, [str(r["session_date"]) for r in ds], closes[-1], k=1
                )["state"]
            n_back = max(n, 1)
            cvd_flow = sum(as_float(r["cvd_spot_usd"]) or 0 for r in daily[-n_back:])
            # el OI debe medirse sobre las mismas n sesiones que el CVD: usar ds[0]
            # tomaba el extremo de toda la ventana cargada (~60 sesiones).
            if len(daily) > n_back:
                oi_first = as_float(daily[-n_back - 1]["oi_close"])
                oi_last = as_float(daily[-1]["oi_close"])
                if oi_first and oi_last:
                    oi_chg = (oi_last / oi_first - 1) * 100
            mom = (closes[-1] / closes[-2] - 1) * 100 if len(closes) >= 2 else None
            # En 1d/3d el flujo es CVD spot puro: es una sola pata, no hay confirmacion
            # cruzada que medir, asi que el voto sale directo de su signo.
            if cvd_flow is not None:
                confirm = {
                    "vote": 1 if cvd_flow > 0 else (-1 if cvd_flow < 0 else 0),
                    "state": "cvd_spot_comprador" if cvd_flow > 0 else (
                        "cvd_spot_vendedor" if cvd_flow < 0 else "cvd_spot_plano"
                    ),
                    "agreement": None,
                }
        votes = []
        if st == "HH_HL":
            votes.append(1)
        elif st == "LH_LL":
            votes.append(-1)
        if confirm["vote"]:
            votes.append(confirm["vote"])
        if mom is not None and mom != 0:
            votes.append(1 if mom > 0 else -1)
        up, dn = sum(1 for v in votes if v > 0), sum(1 for v in votes if v < 0)
        bias = "alcista" if up > dn else ("bajista" if dn > up else "neutral")
        tfs[lab] = {
            "structure": st,
            "cvd_diff": round(cvd_flow) if kind == "intra" and cvd_flow is not None else None,
            "cvd_spot": round(cvd_flow) if kind == "daily" and cvd_flow is not None else None,
            "spot_delta_usd": round(spot_d) if spot_d is not None else None,
            "fut_delta_usd": round(fut_d) if fut_d is not None else None,
            "flow_state": confirm["state"],
            "legs_agree": confirm["agreement"],
            "oi_change_pct": round(oi_chg, 2) if oi_chg is not None else None,
            "momentum_pct": round(mom, 3) if mom is not None else None,
            "bias": bias,
            "votes_up": up,
            "votes_down": dn,
            "flow_status": flow_status,
            "flow_source": "spot_y_futuros_por_signo" if kind == "intra" else "cvd_spot",
        }
    mid = [tfs[t]["bias"] for t in ("4h", "8h", "1d") if t in tfs]
    align = (
        "alcista"
        if mid and all(b == "alcista" for b in mid)
        else ("bajista" if mid and all(b == "bajista" for b in mid) else "mixto")
    )
    return {
        "symbol": symbol,
        "timeframes": tfs,
        "medium_term_alignment": align,
        "note": "sesgo por marco = estructura(pivotes)+flujo+momentum. En 1d/3d el flujo es "
        "CVD spot; intradia vota por el SIGNO de ambas patas (spot y futuros) y marca "
        "conflicto cuando discrepan, en vez de votar por el diferencial spot-futuros, que "
        "el perp domina ~10x. Para holds de 2-3 dias mira 4h/8h/1d alineados.",
    }


# ---------------- swing score largo plazo (balance de evidencia long vs short) ----------------
def compute_swing_score(blocks: dict) -> dict[str, Any]:
    """Puro: lee los bloques ya calculados y sintetiza sesgo largo plazo. NO es probabilidad
    de acierto backtesteada; es el balance ponderado de evidencia alcista/bajista."""

    def g(k):
        return blocks.get(k) or {}

    sd = g("structure_detail").get("horizons") or {}
    metrics = {m.get("key"): m for m in (g("macro_context").get("metrics") or [])}
    ca, pf, tm = g("cross_asset"), g("passive_flow"), g("trend_matrix")
    comps = []

    def add(name, signed, weight, why, status):
        comps.append(
            {
                "name": name,
                "direction": "long" if signed > 0 else ("short" if signed < 0 else "neutral"),
                "contribution": round(signed * weight, 1),
                "weight": weight,
                "status": status,
                "why": why,
            }
        )

    def pair(a, b):
        """Combina dos sub-senales distinguiendo 'no hay dato' de 'apuntan al contrario'."""
        if a is None and b is None:
            return 0.0, "unavailable"
        known = [v for v in (a, b) if v is not None]
        if len(known) == 1:
            return float(known[0]), "partial" if known[0] else "neutral"
        if a * b < 0:
            return 0.0, "conflict"
        combined = (a + b) / 2
        return combined, "signal" if combined else "neutral"

    def stb(lab):
        entry = sd.get(lab)
        if not entry or entry.get("state") is None:
            return None
        s = entry.get("state")
        return 1 if s == "HH_HL" else (-1 if s == "LH_LL" else 0)

    signed, status = pair(stb("1d"), stb("3d"))
    add(
        "Estructura 1d/3d",
        signed,
        25,
        "Maximos/minimos ascendentes (HH/HL)=alcista; descendentes (LH/LL)=bajista",
        status,
    )
    al = tm.get("medium_term_alignment")
    add(
        "Alineacion 4h/8h/1d",
        1 if al == "alcista" else (-1 if al == "bajista" else 0),
        15,
        "Marcos de mediano plazo apuntando al mismo lado",
        "unavailable" if al is None else ("conflict" if al == "mixto" else "signal"),
    )
    tf = tm.get("timeframes") or {}

    def cs(lab):
        entry = tf.get(lab)
        if not entry or entry.get("cvd_spot") is None:
            return None
        v = entry.get("cvd_spot")
        return 1 if v > 0 else (-1 if v < 0 else 0)

    signed, status = pair(cs("1d"), cs("3d"))
    add(
        "CVD spot de fondo",
        signed,
        20,
        "CVD spot comprador=acumulacion; vendedor=distribucion",
        status,
    )
    ps = pf.get("summary")
    add(
        "Manos silenciosas",
        1 if ps == "reacumulacion_silenciosa" else (-1 if ps == "redistribucion_silenciosa" else 0),
        10,
        "Absorcion de ventas en zona baja=reacumulacion; de compras en zona alta=redistribucion",
        "unavailable" if ps is None else ("neutral" if ps == "neutral" else "signal"),
    )
    fp = (metrics.get("fr_avg") or {}).get("percentile")
    add(
        "Funding (posicionamiento)",
        (-1 if fp >= 80 else (1 if fp <= 20 else 0)) if fp is not None else 0,
        15,
        "Funding extremo alto=longs amontonados (riesgo caida); bajo/negativo=espacio para subir",
        "unavailable" if fp is None else ("signal" if (fp >= 80 or fp <= 20) else "neutral"),
    )
    cp = (metrics.get("cvd_spot_usd") or {}).get("percentile")
    add(
        "CVD spot vs 1 anio",
        (1 if cp >= 80 else (-1 if cp <= 20 else 0)) if cp is not None else 0,
        10,
        "Compra spot inusualmente fuerte (long) o debil (short) vs el anio",
        "unavailable" if cp is None else ("signal" if (cp >= 80 or cp <= 20) else "neutral"),
    )
    rs = (ca.get("relative_strength_vs_base_pct") or {}).get("4h")
    # Para BTC el activo base ES BTC: cross_asset devuelve null y el componente no puede
    # existir. Marcarlo 'unavailable' evita que un 0 estructural pase por "neutral medido".
    add(
        "Fuerza relativa vs BTC",
        1 if (rs and rs > 0) else (-1 if (rs and rs < 0) else 0),
        5,
        "El activo supera a BTC (long) o va rezagado (short)",
        "unavailable" if rs is None else ("signal" if rs else "neutral"),
    )

    total = round(sum(c["contribution"] for c in comps), 1)
    total_weight = sum(c["weight"] for c in comps)
    lp = sum(c["contribution"] for c in comps if c["contribution"] > 0)
    sp = -sum(c["contribution"] for c in comps if c["contribution"] < 0)
    measured = sum(c["weight"] for c in comps if c["status"] != "unavailable")
    conflicts = [c["name"] for c in comps if c["status"] == "conflict"]
    # Las cuotas se calculan sobre el peso TOTAL, no sobre la evidencia que resulto no nula.
    # Antes long_share = lp/(lp+sp) daba "100% long" con un solo componente activo y seis
    # mudos, que se pintaba como consenso unanime en el medidor del panel.
    long_share = round(lp / total_weight * 100, 1) if total_weight else 0.0
    short_share = round(sp / total_weight * 100, 1) if total_weight else 0.0
    coverage = round(measured / total_weight * 100, 1) if total_weight else 0.0
    if measured == 0:
        bias, conviction = "SIN_DATOS", "sin datos"
    else:
        bias = "LONG" if total > 15 else ("SHORT" if total < -15 else "NEUTRAL")
        conviction = "alta" if abs(total) >= 50 else ("media" if abs(total) >= 25 else "baja")
        if coverage < 50:
            conviction = "baja"
    return {
        "bias": bias,
        "score": total,
        "conviction": conviction,
        "long_share_pct": long_share,
        "short_share_pct": short_share,
        "neutral_share_pct": round(100 - long_share - short_share, 1),
        "evidence_coverage_pct": coverage,
        "measured_weight": measured,
        "total_weight": total_weight,
        "conflicts": conflicts,
        "components": sorted(comps, key=lambda c: -abs(c["contribution"])),
        "horizon": "largo plazo (dias-semanas)",
        "note": "score = suma ponderada de evidencia alcista/bajista (-100..+100). NO es "
        "probabilidad de acierto; es el balance de senales. long_share/short_share/neutral_share "
        "reparten el peso TOTAL (100), asi que la parte sin senal es visible. "
        "evidence_coverage_pct = % del peso que si pudo medirse; por debajo de 50 la conviccion "
        "se degrada a baja. 'conflicts' lista los componentes cuyas sub-senales se contradicen.",
    }


async def swing_score(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    blocks = {
        "structure_detail": await structure_detail(conn, symbol),
        "macro_context": await macro_context(conn, symbol),
        "cross_asset": await cross_asset(conn, symbol),
        "passive_flow": await passive_flow(conn, symbol),
        "trend_matrix": await trend_matrix(conn, symbol),
    }
    return {"symbol": symbol, **compute_swing_score(blocks)}
