from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal

import asyncpg

from app.analysis_prompt import ANALYSIS_PROMPT
from app.config import WS_SYMBOL_MAP, get_settings
from app.db import INGEST_COMPONENT_MAX_AGES, required_heartbeat_failures
from app.external_macro import align_with_internal, external_macro_context
from app.interpretation import cvd_swing_read, evaluate_setups
from app.scalp_logic import (
    EXECUTION_PROFILES,
    as_float,
    compute_scalp_summary,
    context_metadata,
    cross_asset,
    cvd_matrix,
    data_quality,
    delta_matrix,
    divergence_scan,
    funding_context,
    horizon_structure,
    liquidation_burst,
    liquidation_map,
    macro_context,
    market_memory,
    market_structure,
    oi_context,
    price_barriers,
    reference_levels,
    scalp_context,
    spot_flow_windows,
    structure_detail,
    volatility_context,
    volume_profile,
)
from app.scalp_logic import compute_swing_score as _compute_swing_score
from app.scalp_logic import passive_flow as _passive_flow
from app.scalp_logic import trend_matrix as _trend_matrix

AIProfile = Literal["lite", "default", "pro", "max"]

PROFILE_LIMITS: dict[AIProfile, dict[str, Any]] = {
    "lite": {
        "signals": 3,
        "liq_levels": 5,
        "liq_minutes": 30,
        "delta_windows": [("1m", 60), ("3m", 180), ("15m", 900)],
        "include_setup": False,
        "include_recent_signals": True,
        # El bloque intradia de divergencias cuesta ~1.9k tokens y solapa con delta_matrix
        # y cvd_matrix, que el modelo ya recibe. Solo se manda bajo demanda explicita.
        "include_intraday_divergences": False,
    },
    "default": {
        "signals": 6,
        "liq_levels": 8,
        "liq_minutes": 60,
        "delta_windows": [("15s", 15), ("1m", 60), ("3m", 180), ("5m", 300), ("15m", 900)],
        "include_setup": True,
        "include_recent_signals": True,
        "include_intraday_divergences": False,
    },
    "pro": {
        "signals": 12,
        "liq_levels": 15,
        "liq_minutes": 180,
        "delta_windows": [
            ("15s", 15),
            ("30s", 30),
            ("1m", 60),
            ("3m", 180),
            ("5m", 300),
            ("15m", 900),
        ],
        "include_setup": True,
        "include_recent_signals": True,
        "include_intraday_divergences": True,
        "daily_sessions": 30,
    },
    # Sin recortes: para pegar el JSON en una IA por web, donde el coste en tokens no
    # es la restriccion. Trae el trimestre de sesiones para que el modelo pueda juzgar
    # estructura y no solo la foto de hoy.
    "max": {
        "signals": 24,
        "liq_levels": 25,
        "liq_minutes": 240,
        "delta_windows": [
            ("15s", 15),
            ("30s", 30),
            ("1m", 60),
            ("3m", 180),
            ("5m", 300),
            ("15m", 900),
            ("30m", 1800),
            ("1h", 3600),
            ("4h", 14400),
        ],
        "include_setup": True,
        "include_recent_signals": True,
        "include_intraday_divergences": True,
        "daily_sessions": 90,
        "include_verdicts": True,
    },
}
for _name, _limits in PROFILE_LIMITS.items():
    _limits.setdefault("daily_sessions", 0)
    _limits.setdefault("include_verdicts", False)

SIGNIFICANT_FIELDS = {
    "price",
    "oi",
    "oi_chg_24h_pct",
    "oi_vol_24h_ratio",
    "vol_24h",
    "delta_3min",
    "cvd_session",
    "cvd_nyse_session",
    "cvd_spot_24h",
    "cvd_spot_session",
    "cvd_diff_24h",
    "cvd_diff_ses",
    "fr_avg",
    "pfr_avg",
    "pfr_fr_div",
    "long_liq_24h",
    "short_liq_24h",
    "whale_intensity",
    "whale_label",
    "regime_score",
    "regime_label",
    "price_dir_1h",
    "btr_15m",
    "btr_1h",
    "btr_24h",
}


def normalize_profile(profile: str) -> AIProfile:
    value = profile.strip().lower()
    if value in PROFILE_LIMITS:
        return value  # type: ignore[return-value]
    raise ValueError(f"profile must be one of: {', '.join(PROFILE_LIMITS)}")


def _round_number(value: object, digits: int = 4) -> object:
    number = as_float(value)
    if number is None:
        return value
    if abs(number) >= 1000:
        return round(number, 2)
    if abs(number) >= 10:
        return round(number, 3)
    return round(number, digits)


def compact_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    # date NO es subclase de datetime (es al reves): sin esta rama, session_date llegaba
    # intacto a json.dumps() en rough_token_estimate y reventaba el endpoint.
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return compact_dict(value)
    if isinstance(value, list):
        return [compact_value(item) for item in value]
    return _round_number(value)


def compact_dict(row: dict[str, Any], allowed_fields: set[str] | None = None) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        if allowed_fields is not None and key not in allowed_fields:
            continue
        if value is None:
            continue
        output[key] = compact_value(value)
    return output


def rough_token_estimate(payload: dict[str, Any]) -> int:
    import json

    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    try:
        import tiktoken

        encoder = tiktoken.get_encoding("cl100k_base")
        return max(1, len(encoder.encode(raw)))
    except Exception:
        # Deployment-safe fallback only. tiktoken is declared as a dependency; this
        # path keeps tests/imports alive if the optional wheel is temporarily absent.
        return max(1, int(len(raw.encode("utf-8")) / 4))


async def latest_snapshot(conn: asyncpg.Connection, symbol: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT * FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts DESC LIMIT 1", symbol
    )
    return dict(row) if row else None


async def daily_data(conn: asyncpg.Connection, symbol: str, days: int = 60) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        WITH selected AS (
          SELECT * FROM daily_session_agg WHERE symbol=$1
          ORDER BY session_date DESC LIMIT $2
        )
        SELECT session_date,symbol,cvd_spot_usd,cvd_fut_usd,cvd_diff_usd,
               inst_delta_usd,price_open,price_close,price_chg_pct,
               oi_open,oi_close,oi_chg_usd,fr_avg,
               SUM(cvd_diff_usd) OVER (ORDER BY session_date) AS cumulative_diff,
               SUM(cvd_spot_usd) OVER (ORDER BY session_date) AS cumulative_spot
        FROM selected ORDER BY session_date
        """,
        symbol,
        days,
    )
    return [dict(row) for row in rows]


DAILY_HISTORY_QUERY = """
WITH hist AS (
  SELECT session_date,
         percent_rank() OVER (ORDER BY cvd_spot_usd) * 100 AS pct_spot,
         percent_rank() OVER (ORDER BY cvd_diff_usd) * 100 AS pct_diff,
         percent_rank() OVER (ORDER BY price_chg_pct) * 100 AS pct_ret
  FROM daily_session_agg WHERE symbol=$1
), selected AS (
  SELECT * FROM daily_session_agg WHERE symbol=$1
  ORDER BY session_date DESC LIMIT $2
)
SELECT s.session_date,s.price_open,s.price_close,s.price_chg_pct,
       s.cvd_spot_usd,s.cvd_fut_usd,s.cvd_diff_usd,s.cvd_fut_2v_usd,s.cvd_diff_2v_usd,
       s.oi_close,s.oi_chg_usd,s.fr_avg,s.volume_usd,s.long_liq_usd,s.short_liq_usd,
       SUM(s.cvd_spot_usd) OVER (ORDER BY s.session_date) AS cum_spot,
       SUM(s.cvd_fut_usd)  OVER (ORDER BY s.session_date) AS cum_fut,
       SUM(s.cvd_diff_usd) OVER (ORDER BY s.session_date) AS cum_diff,
       round(h.pct_spot::numeric,0)::float8 AS pct_spot,
       round(h.pct_diff::numeric,0)::float8 AS pct_diff,
       round(h.pct_ret::numeric,0)::float8  AS pct_ret,
       CASE
         WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0 THEN 'ambos_compran'
         WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0 THEN 'ambos_venden'
         ELSE 'opuestos'
       END AS flow_direction
FROM selected s JOIN hist h USING (session_date)
ORDER BY s.session_date
"""


async def daily_history(conn: asyncpg.Connection, symbol: str, sessions: int) -> dict[str, Any]:
    """Serie sesion a sesion para que el modelo vea estructura y no solo la foto de hoy.

    El resto del contexto entrega agregados y percentiles ya digeridos; sin la serie cruda
    un modelo no puede juzgar si el CVD spot lleva semanas subiendo o si el ultimo dato es
    un pico aislado. Los percentiles van contra TODA la historia guardada, no contra la
    ventana, para que un valor no parezca extremo solo por el recorte.
    """
    rows = await conn.fetch(DAILY_HISTORY_QUERY, symbol, sessions)
    if not rows:
        return {"available": False, "sessions": 0}
    series = [compact_dict(dict(row)) for row in rows]
    spot = [as_float(r["cvd_spot_usd"]) or 0.0 for r in rows]
    fut = [as_float(r["cvd_fut_usd"]) or 0.0 for r in rows]
    closes = [as_float(r["price_close"]) for r in rows]
    up = sum(1 for r in rows if (as_float(r["price_chg_pct"]) or 0.0) > 0)
    spot_up = sum(1 for value in spot if value > 0)
    first_close, last_close = closes[0], closes[-1]
    return {
        "available": True,
        "sessions": len(rows),
        "from": str(rows[0]["session_date"]),
        "to": str(rows[-1]["session_date"]),
        "series": series,
        "totals": {
            "cvd_spot_usd": round(sum(spot), 2),
            "cvd_fut_usd": round(sum(fut), 2),
            "cvd_diff_usd": round(sum(spot) - sum(fut), 2),
            "price_change_pct": (
                round((last_close / first_close - 1) * 100, 3)
                if (first_close and last_close)
                else None
            ),
            "sessions_price_up": up,
            "sessions_price_down": len(rows) - up,
            "sessions_spot_buying": spot_up,
            "sessions_spot_selling": len(rows) - spot_up,
        },
        "field_notes": {
            "cvd_spot_usd": "spot Binance+Bybit; es la serie limpia de un solo universo",
            "cvd_fut_usd": "futuros de BINANCE (simbolo Coinalyze .A), no un agregado",
            "cvd_diff_usd": "spot menos futuros. El perp mueve ~10x el spot, asi que su signo "
            "lo manda futuros: en 92-95% de las sesiones es -CVD_fut. NO es "
            "una lectura de acumulacion spot",
            "cvd_diff_2v_usd": "misma resta con ambas patas en Binance+Bybit; solo desde "
            "v1.3.3, null en sesiones anteriores",
            "cum_*": "acumulado dentro de esta ventana, arranca en la sesion mas antigua",
            "pct_spot/pct_diff/pct_ret": "percentil del valor frente a toda la historia guardada",
            "flow_direction": "que hicieron las DOS patas; 'opuestos' es el unico caso en que "
            "el diferencial refleja discrepancia real spot vs futuros",
        },
        "note": "sesiones NYSE (09:30 ET a 09:30 ET). Para leer acumulacion o distribucion "
        "usa cvd_spot_usd y su acumulado, no el diferencial.",
    }


async def verdict_history(conn: asyncpg.Connection, symbol: str, limit: int = 90) -> dict[str, Any]:
    """Lo que dijo el modelo en sesiones pasadas y lo que hizo el precio despues."""
    rows = await conn.fetch(
        """
        WITH v AS (
          SELECT * FROM daily_verdict WHERE symbol=$1 ORDER BY session_date DESC LIMIT $2
        )
        SELECT v.session_date,v.swing_bias,v.swing_score,v.swing_conviction,v.regime_score,
               v.regime_label,v.setup_id,v.setup_state,v.setup_confidence,v.price_close,
               (SELECT (d.price_close/v.price_close-1)*100 FROM daily_session_agg d
                 WHERE d.symbol=$1 AND d.session_date>v.session_date
                 ORDER BY d.session_date OFFSET 6 LIMIT 1) AS fwd_7s_pct,
               (SELECT (d.price_close/v.price_close-1)*100 FROM daily_session_agg d
                 WHERE d.symbol=$1 AND d.session_date>v.session_date
                 ORDER BY d.session_date OFFSET 13 LIMIT 1) AS fwd_14s_pct
        FROM v ORDER BY v.session_date
        """,
        symbol,
        limit,
    )
    return {
        "available": bool(rows),
        "sessions": len(rows),
        "series": [compact_dict(dict(row)) for row in rows],
        "note": "veredictos congelados por sesion junto al retorno realizado. Se empezaron a "
        "registrar en v1.3.3 (2026-08-02), asi que la serie es corta todavia y NO "
        "alcanza para inferir tasa de acierto.",
    }


async def data_confidence_row(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    row = await conn.fetchrow(
        """
        WITH snap AS (
          SELECT MAX(ts) AS ts FROM metrics_snapshot WHERE symbol=$1
        ), spot AS (
          SELECT exchange,MAX(ts) AS ts FROM spot_trades_realtime
          WHERE symbol=$2 AND exchange IN ('binance','bybit') GROUP BY exchange
        ), fut AS (
          SELECT exchange,MAX(ts) AS ts FROM futures_trades_realtime
          WHERE symbol=$1 AND exchange IN ('binance','bybit') GROUP BY exchange
        ), fut_flow AS (
          SELECT MIN(ts) AS lo,MAX(ts) AS hi FROM futures_trades_realtime
          WHERE symbol=$1 AND exchange='combined'
        ), book AS (
          SELECT exchange,MAX(ts) AS ts FROM orderbook_snapshot
          WHERE symbol=$1 AND exchange IN ('binance','bybit','combined') GROUP BY exchange
        )
        SELECT $1::text AS symbol,
          EXTRACT(EPOCH FROM now()-(SELECT ts FROM snap))::float8 AS snapshot_lag_seconds,
          (SELECT COUNT(*) FROM spot WHERE ts >= now()-interval '30 seconds') AS spot_venues_live,
          (SELECT COUNT(*) FROM fut WHERE ts >= now()-interval '30 seconds') AS futures_venues_live,
          (SELECT COUNT(*) FROM book WHERE exchange IN ('binance','bybit') AND ts >= now()-interval '30 seconds') AS book_venues_live,
          EXTRACT(EPOCH FROM now()-(SELECT ts FROM book WHERE exchange='combined'))::float8 AS combined_book_lag_seconds,
          COALESCE((SELECT lo <= now()-interval '8 hours' AND hi >= now()-interval '30 seconds' FROM fut_flow),false) AS flow_8h_futures_complete,
          EXTRACT(EPOCH FROM now()-(SELECT hi FROM fut_flow))::float8 AS flow_8h_futures_end_gap_seconds
        """,
        symbol,
        WS_SYMBOL_MAP[symbol],
    )
    item = dict(row) if row else {"symbol": symbol}
    spot_8h = (
        (await spot_flow_windows(conn, WS_SYMBOL_MAP[symbol], [("8h", 28800)])).get("8h") or {}
    ).get("combined") or {}
    item["flow_8h_spot_complete"] = bool(spot_8h.get("complete"))
    item["flow_8h_spot_source"] = spot_8h.get("source", "unavailable")
    item["flow_8h_spot_end_gap_seconds"] = spot_8h.get("end_gap_seconds")
    item["flow_8h_futures_complete"] = bool(item.get("flow_8h_futures_complete"))
    item["flow_8h_complete"] = item["flow_8h_spot_complete"] and item["flow_8h_futures_complete"]
    snapshot_lag = as_float(item.get("snapshot_lag_seconds"))
    book_lag = as_float(item.get("combined_book_lag_seconds"))
    live_ok = (
        int(item.get("spot_venues_live") or 0) == 2
        and int(item.get("futures_venues_live") or 0) == 2
    )
    book_ok = int(item.get("book_venues_live") or 0) >= 2 and (
        book_lag is not None and book_lag <= 30
    )
    snapshot_ok = snapshot_lag is not None and snapshot_lag <= 180
    required_heartbeats = {
        "ws": 180.0,
        "scalp": 180.0,
        "ingest": max(INGEST_COMPONENT_MAX_AGES.values()),
        **{
            f"ingest:{component}": max_age
            for component, max_age in INGEST_COMPONENT_MAX_AGES.items()
        },
    }
    collector_heartbeats = await conn.fetch(
        "SELECT service,status,updated_at FROM pipeline_heartbeat "
        "WHERE service=ANY($1::text[])",
        list(required_heartbeats),
    )
    item["collectors_stale"] = bool(
        required_heartbeat_failures(collector_heartbeats, required_heartbeats)
    )
    item["status"] = (
        "ok"
        if live_ok
        and book_ok
        and snapshot_ok
        and item["flow_8h_complete"]
        and not item["collectors_stale"]
        else "degraded"
    )
    item["quality_score"] = quality_score(item)
    item["quality_score_basis"] = (
        "conectividad por simbolo + lag de book/snapshot + cobertura continua spot/futures 8h"
    )
    return item


def quality_score(confidence: dict[str, Any]) -> int:
    score = 100
    snapshot_lag = as_float(confidence.get("snapshot_lag_seconds"))
    book_lag = as_float(confidence.get("combined_book_lag_seconds"))
    if snapshot_lag is None or snapshot_lag > 180:
        score -= 35
    elif snapshot_lag > 90:
        score -= 15
    if int(confidence.get("spot_venues_live") or 0) < 2:
        score -= 20
    if int(confidence.get("futures_venues_live") or 0) < 2:
        score -= 20
    if int(confidence.get("book_venues_live") or 0) < 2:
        score -= 15
    if book_lag is None or book_lag > 30:
        score -= 10
    if confidence.get("collectors_stale"):
        score -= 40  # colector caido = staleness real
    if confidence.get("flow_8h_complete") is False:
        score -= 20
    return max(0, min(100, score))


async def latest_orderbook(conn: asyncpg.Connection, symbol: str) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (exchange)
               exchange,ts,spread_bps,imbalance_l1,imbalance_l5,imbalance_l10,
               wall_up_pct,wall_down_pct,bid_px,ask_px
        FROM orderbook_snapshot
        WHERE symbol=$1 AND exchange IN ('combined','binance','bybit')
        ORDER BY exchange,ts DESC
        """,
        symbol,
    )
    by_exchange = {str(row["exchange"]): compact_dict(dict(row)) for row in rows}
    return {
        "combined": by_exchange.get("combined"),
        "binance": by_exchange.get("binance"),
        "bybit": by_exchange.get("bybit"),
    }


async def recent_signals(conn: asyncpg.Connection, symbol: str, limit: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT ts,state,confidence,long_score,short_score,reason,
               fut_delta_1m,fut_delta_3m,spot_delta_3m,diff_3m,
               spot_fut_divergence_norm,book_status,book_lag_seconds,basis_bps,absorption
        FROM scalp_signal_snapshot
        WHERE symbol=$1
        ORDER BY ts DESC LIMIT $2
        """,
        symbol,
        limit,
    )
    return [compact_dict(dict(row)) for row in rows]


async def liquidation_levels(
    conn: asyncpg.Connection, symbol: str, *, minutes: int, bucket_bps: int, limit: int
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        WITH ref AS (
          SELECT COALESCE(
            (SELECT last_px FROM futures_trades_realtime WHERE symbol=$1 AND exchange='combined' ORDER BY ts DESC LIMIT 1),
            (SELECT close FROM ohlcv WHERE symbol=$1 AND interval='1min' ORDER BY ts DESC LIMIT 1)
          ) AS px
        ), levels AS (
          SELECT
            ROUND(price / NULLIF(ref.px * ($3::float8 / 10000.0),0)) * ref.px * ($3::float8 / 10000.0) AS price_bucket,
            SUM(CASE WHEN side='long' THEN notional_usd ELSE 0 END) AS long_liq,
            SUM(CASE WHEN side='short' THEN notional_usd ELSE 0 END) AS short_liq,
            SUM(notional_usd) AS total_notional,
            COUNT(*) AS events
          FROM liquidations_realtime, ref
          WHERE symbol=$1 AND ts >= now()-($2::int * interval '1 minute') AND ref.px > 0
          GROUP BY 1
        )
        SELECT price_bucket,long_liq,short_liq,total_notional,events,
               CASE
                 WHEN short_liq > long_liq THEN 'historical_short_liq_cluster'
                 WHEN long_liq > short_liq THEN 'historical_long_liq_cluster'
                 ELSE 'mixed'
               END AS cluster_type
        FROM levels
        ORDER BY total_notional DESC NULLS LAST
        LIMIT $4
        """,
        symbol,
        minutes,
        bucket_bps,
        limit,
    )
    return [compact_dict(dict(row)) for row in rows]


def build_operator_read(summary: dict[str, Any], confidence: dict[str, Any]) -> dict[str, Any]:
    long_score = as_float(summary.get("long_score")) or 0.0
    short_score = as_float(summary.get("short_score")) or 0.0
    state = str(summary.get("state") or "No Trade")
    confidence_label = str(summary.get("confidence") or "baja")
    bias = (
        "Long" if long_score > short_score else "Short" if short_score > long_score else "No Trade"
    )
    edge = abs(long_score - short_score)
    quality = int(confidence.get("quality_score") or 0)
    no_trade_reasons: list[str] = []
    if confidence.get("status") != "ok":
        no_trade_reasons.append("data_confidence_degraded")
    if summary.get("book_status") != "ok":
        no_trade_reasons.append("book_not_ok")
    if state == "No Trade" or edge < 12:
        no_trade_reasons.append("score_edge_low")
    # El spread ANCHO deja de ser motivo de no-trade: es un aviso dependiente del perfil.
    # Vetar con un umbral universal declaraba "caro" un spread irrelevante para un swing.
    # El veredicto de ejecucion sale de `execution_assessment()` (coste sobre objetivo).
    spread = as_float(summary.get("spread_bps"))
    umbral = EXECUTION_PROFILES["intradia"]["spread_warn_bps"]
    warnings: list[str] = []
    if spread is not None and spread > umbral:
        warnings.append(f"spread_above_intraday_warning_{umbral:g}bps")
    return {
        "state": state,
        "bias": bias,
        "confidence": confidence_label,
        "edge": round(edge, 2),
        "quality_score": quality,
        "no_trade_reasons": no_trade_reasons,
        "warnings": warnings,
        "spread_warning_note": (
            "El spread NO veta: el umbral es un aviso por perfil, no una clasificacion. "
            "La ejecucion se juzga con coste_total/objetivo, no con bps sueltos."
        ),
        "invalidates_long": [
            "price_rejects_below_vwap",
            "spot_delta_turns_negative_with_futures_follow_through",
            "book_l5_turns_offer_dominant",
        ],
        "invalidates_short": [
            "price_recovers_vwap_with_spot_delta_positive",
            "futures_sell_delta_gets_absorbed",
            "book_l5_turns_bid_dominant",
        ],
    }


def local_alerts(summary: dict[str, Any], confidence: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if confidence.get("status") != "ok":
        alerts.append(
            {
                "priority": "P1",
                "side": "NO_TRADE",
                "message": "Calidad de datos degradada",
                "detail": compact_dict(confidence),
            }
        )
    if summary.get("book_status") in {"missing", "stale"}:
        alerts.append(
            {
                "priority": "P1",
                "side": "NO_TRADE",
                "message": "Order book no confiable",
                "detail": f"book_status={summary.get('book_status')} lag={summary.get('book_lag_seconds')}",
            }
        )
    spread = as_float(summary.get("spread_bps"))
    umbral = EXECUTION_PROFILES["intradia"]["spread_warn_bps"]
    if spread is not None and spread > umbral:
        alerts.append(
            {
                # AVISO, no NO_TRADE: el mismo spread que estrangula un scalp es ruido en un
                # swing. Quien decide es el coste total contra el objetivo de la operacion.
                "priority": "P2",
                "side": "AVISO",
                "message": f"Spread ancho para intradía (> {umbral:g} bps)",
                "detail": (
                    f"spread_bps={spread:.2f}; umbral de AVISO por perfil, no un veto. "
                    "Sin objetivo/stop/comision no hay veredicto de ejecucion."
                ),
            }
        )
    if str(summary.get("state")) != "No Trade" and str(summary.get("confidence")) in {
        "media",
        "alta",
    }:
        side = (
            "LONG"
            if (as_float(summary.get("long_score")) or 0)
            > (as_float(summary.get("short_score")) or 0)
            else "SHORT"
        )
        alerts.append(
            {
                "priority": "P2" if summary.get("confidence") == "media" else "P1",
                "side": side,
                "message": summary.get("state"),
                "detail": summary.get("reason"),
            }
        )
    return alerts


async def build_ai_symbol_context(
    conn: asyncpg.Connection,
    symbol: str,
    *,
    profile: AIProfile = "default",
    bucket_bps: int = 10,
) -> dict[str, Any]:
    limits = PROFILE_LIMITS[profile]
    snap = await latest_snapshot(conn, symbol)
    ctx = await scalp_context(conn, symbol)
    summary = compute_scalp_summary(ctx)
    confidence = await data_confidence_row(conn, symbol)
    daily_rows = await daily_data(conn, symbol, 730)
    setup = None
    if snap and limits["include_setup"]:
        setup = evaluate_setups(snap, daily_rows[-60:])
    external = await external_macro_context(
        conn, etf_configured=bool(get_settings().COINGLASS_API_KEY)
    )
    payload: dict[str, Any] = {
        "schema_version": "ai_context.v2",
        "interpretation_prompt": ANALYSIS_PROMPT,
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "symbol": symbol,
        "asset": WS_SYMBOL_MAP[symbol],
        "data_confidence": compact_dict(confidence),
        "snapshot": compact_dict(snap or {}, SIGNIFICANT_FIELDS),
        "scalp": compact_dict(summary),
        "operator_read": build_operator_read(summary, confidence),
        "local_alerts": local_alerts(summary, confidence),
        "cvd_swing_90d": cvd_swing_read(daily_rows),
        "delta_matrix": await delta_matrix(conn, symbol, limits["delta_windows"]),
        "orderbook": await latest_orderbook(conn, symbol),
        "market_structure": await market_structure(conn, symbol),
        "structure_horizons": await horizon_structure(conn, symbol),
        "structure_detail": await structure_detail(conn, symbol),
        "cvd_matrix": await cvd_matrix(conn, symbol),
        "passive_flow": await _passive_flow(conn, symbol),
        "trend_matrix": await _trend_matrix(conn, symbol),
        "oi_context": await oi_context(conn, symbol),
        "volatility": await volatility_context(conn, symbol),
        "reference_levels": await reference_levels(conn, symbol),
        "cross_asset": await cross_asset(conn, symbol),
        "funding_context": await funding_context(conn, symbol),
        "liquidation_map": await liquidation_map(conn, symbol),
        "volume_profile": await volume_profile(conn, symbol),
        "price_barriers": await price_barriers(conn, symbol),
        "market_memory_2y": await market_memory(conn, symbol),
        "context_metadata": await context_metadata(conn, symbol),
        "data_quality": await data_quality(conn, symbol),
        "macro_context": await macro_context(conn, symbol),
        "external_macro_context": external,
        "divergences": await divergence_scan(
            conn, symbol, include_intraday=bool(limits["include_intraday_divergences"])
        ),
        "liq_burst": await liquidation_burst(conn, symbol),
        "liquidation_levels": await liquidation_levels(
            conn,
            symbol,
            minutes=int(limits["liq_minutes"]),
            bucket_bps=bucket_bps,
            limit=int(limits["liq_levels"]),
        ),
    }
    if setup:
        payload["setup"] = compact_dict(setup)
    if limits["include_recent_signals"]:
        payload["recent_signals"] = await recent_signals(conn, symbol, int(limits["signals"]))
    if limits["daily_sessions"]:
        payload["daily_history"] = await daily_history(conn, symbol, int(limits["daily_sessions"]))
    if limits["include_verdicts"]:
        payload["verdict_history"] = await verdict_history(conn, symbol)
    payload["swing_score"] = _compute_swing_score(payload)
    payload["external_macro_context"] = align_with_internal(
        payload["external_macro_context"], payload["swing_score"]
    )
    payload["rough_token_estimate"] = rough_token_estimate(payload)
    return payload


async def build_ai_context(
    conn: asyncpg.Connection,
    symbols: list[str],
    *,
    profile: AIProfile = "default",
    bucket_bps: int = 10,
) -> dict[str, Any]:
    symbol_payloads = [
        await build_ai_symbol_context(conn, symbol, profile=profile, bucket_bps=bucket_bps)
        for symbol in symbols
    ]
    prio = {"P1": 0, "CRITICAL": 0, "HIGH": 1, "P2": 2}
    root_alerts: list[dict[str, Any]] = []
    for p in symbol_payloads:
        for al in p.get("local_alerts") or []:
            if not isinstance(al, dict):
                continue
            root_alerts.append(
                {
                    "symbol": p.get("symbol"),
                    "asset": p.get("asset"),
                    **{k: al[k] for k in ("message", "priority", "side", "detail") if k in al},
                    "source": "symbol.local_alerts",
                }
            )
    root_alerts.sort(key=lambda x: prio.get(str(x.get("priority", "")).upper(), 9))
    for _p in symbol_payloads:
        _p.pop("interpretation_prompt", None)  # solo al root, no 3x
    payload = {
        "schema_version": "ai_context_bundle.v2",
        "interpretation_prompt": ANALYSIS_PROMPT,
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "local_alerts": root_alerts,
        "symbols": symbol_payloads,
    }
    payload["rough_token_estimate"] = rough_token_estimate(payload)
    return payload
