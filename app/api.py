from __future__ import annotations

import asyncio
import hmac
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Annotated, Any

import asyncpg
import orjson
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.ai_context import (
    build_ai_context,
    build_ai_symbol_context,
    data_confidence_row,
    normalize_profile,
)
from app.config import SUPPORTED_SYMBOLS, WS_SYMBOL_MAP, get_settings
from app.data_gaps import GapRequirement, blocking_requirement_keys
from app.db import (
    INGEST_COMPONENT_MAX_AGES,
    create_pool,
    heartbeat,
    required_heartbeat_failures,
)
from app.delta_profile import delta_profile
from app.external_macro import align_with_internal, external_macro_context
from app.interpretation import cvd_swing_read, daily_flow_read, evaluate_setups
from app.logging_setup import configure_logging
from app.scalp_logic import (
    ABSORPTION_MIN_RATIO,
    EXECUTION_PROFILES,
    HYPOTHESES,
    TRADING_PROFILES,
    as_float,
    baseline_band,
    basis_quality,
    classify_absorption,
    compute_scalp_summary,
    context_metadata,
    cross_asset,
    cvd_matrix,
    data_quality,
    delta_matrix,
    divergence_scan,
    execution_assessment,
    execution_cost,
    feed_quality,
    funding_context,
    hypothesis_evidence,
    level_breakout,
    liquidation_map,
    load_baselines,
    macro_context,
    market_impact,
    market_memory,
    market_structure,
    metric_quality,
    oi_context,
    passive_flow,
    positioning_context,
    price_barriers,
    profile_view,
    range_validate,
    reference_levels,
    scalp_context,
    setup_confirmation_bundle,
    spot_perp_flow,
    structure_detail,
    swing_score,
    trend_matrix,
    volatility_context,
    volume_profile,
    wyckoff_context,
    zone_analysis,
)
from app.setups import DIRECTIONS, SETUP_LABELS, build_setup_context, split_hypothesis

LOGGER = logging.getLogger(__name__)
SETTINGS = get_settings()
configure_logging(SETTINGS.LOG_LEVEL)
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if not STATIC_DIR.is_dir():
    # update.sh instala el paquete en el venv ademas de copiar el arbol; la copia
    # de site-packages no lleva static/. Al importarse desde ahi, resolver contra
    # el WorkingDirectory del servicio en vez de reventar en el mount.
    STATIC_DIR = Path.cwd() / "static"
# Los dos intervalos con buy_volume y con historia util: 4h llega a ~300 dias y 5min a ~9.
DELTA_PROFILE_INTERVALS = {"4hour", "5min"}
HISTORICAL_INTERVALS = {
    "1min": timedelta(minutes=1),
    "3min": timedelta(minutes=3),
    "5min": timedelta(minutes=5),
    "15min": timedelta(minutes=15),
    # 18min no existe en Coinalyze (la API responde 400: solo 1min/5min/15min/30min/1hour/
    # 2hour/4hour/6hour/12hour/daily), asi que se construye resampleando 1min. La cuenta sale
    # exacta: 1440/18 = 80 velas por dia UTC, y como date_bin ancla en 1970-01-01T00:00:00Z
    # cada medianoche UTC cae justo en un limite de vela. No hay bucket a caballo entre dias.
    "18min": timedelta(minutes=18),
    "30min": timedelta(minutes=30),
    "1hour": timedelta(hours=1),
    "4hour": timedelta(hours=4),
}


# Ventanas que alimentan la jerarquia de perfiles y la hipotesis. Una sola definicion: si
# /api/profile y /api/hypothesis usaran listas distintas podrian contradecirse.
PROFILE_WINDOWS = [
    ("30s", 30),
    ("1m", 60),
    ("5m", 300),
    ("15m", 900),
    ("18m", 1080),
    ("1h", 3600),
    ("4h", 14400),
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    pool = await create_pool(SETTINGS, application_name="coinalyze-api")
    app.state.pool = pool
    async with pool.acquire() as conn:
        await heartbeat(conn, "api")
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Coinalyze Operator Dashboard",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    default_response_class=JSONResponse,
    lifespan=lifespan,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(SETTINGS.TRUSTED_HOSTS))


def valid_internal_token(request: Request) -> bool:
    token = request.headers.get("X-Internal-Token") or ""
    return bool(SETTINGS.API_INTERNAL_TOKEN) and hmac.compare_digest(
        token, SETTINGS.API_INTERNAL_TOKEN
    )


def client_ip_allowed(request: Request) -> bool:
    allowed_cidrs = tuple(SETTINGS.API_INTERNAL_ALLOWED_CIDRS or ())
    if not allowed_cidrs:
        return True
    host = request.client.host if request.client else ""
    if not host:
        return False
    try:
        client_ip = ip_address(host)
    except ValueError:
        return False
    return any(client_ip in ip_network(cidr, strict=False) for cidr in allowed_cidrs)


@app.middleware("http")
async def response_headers(request: Request, call_next):
    protected = request.url.path.startswith("/api/") or request.url.path == "/metrics"
    if protected:
        if not SETTINGS.API_INTERNAL_TOKEN:
            return JSONResponse(
                status_code=503,
                content={"error": "API_INTERNAL_TOKEN is not configured"},
            )
        if not client_ip_allowed(request):
            return JSONResponse(status_code=403, content={"error": "Forbidden source address"})
        if not valid_internal_token(request):
            return JSONResponse(status_code=403, content={"error": "Forbidden"})
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
        "font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = (
        "no-store" if request.url.path.startswith("/api/") else "no-cache"
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, __: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "Invalid parameters"})


def validate_symbol(symbol: str) -> str:
    if symbol not in SETTINGS.SYMBOLS or symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=404, detail="Unknown symbol")
    return symbol


def historical_interval_value(interval: str) -> timedelta:
    value = HISTORICAL_INTERVALS.get(interval)
    if value is None:
        raise HTTPException(status_code=422, detail="Invalid interval for historical endpoint")
    return value


def records(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


async def mask_gapped_series_rows(
    conn: asyncpg.Connection,
    rows: list[dict[str, Any]],
    *,
    bucket: timedelta,
    feed: str,
    exchanges: tuple[str, ...],
    market: str,
    symbol: str,
    value_keys: tuple[str, ...] = (),
    cumulative_keys: tuple[str, ...] = (),
) -> None:
    """Expose gap buckets as null and never continue an incomplete cumulative value."""
    requirements: list[GapRequirement] = []
    for index, row in enumerate(rows):
        start = row.get("bucket")
        if not isinstance(start, datetime):
            continue
        for exchange in exchanges:
            requirements.append(
                GapRequirement(
                    str(index), feed, exchange, market, symbol, start, start + bucket,
                )
            )
    blocked_indexes = sorted(
        int(key) for key in await blocking_requirement_keys(conn, requirements)
    )
    for index in blocked_indexes:
        row = rows[index]
        for value_key in value_keys:
            row[value_key] = None
    if blocked_indexes:
        for row in rows[blocked_indexes[0] :]:
            for cumulative_key in cumulative_keys:
                row[cumulative_key] = None


async def latest_snapshot(conn: asyncpg.Connection, symbol: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT * FROM metrics_snapshot WHERE symbol=$1 ORDER BY ts DESC LIMIT 1", symbol
    )
    return dict(row) if row else None


DAILY_SOURCES = {
    "cvd_spot_usd": {"venues": "binance+bybit", "table": "spot_trades_agg"},
    "cvd_fut_usd": {"venues": "binance (simbolo Coinalyze .A)", "table": "ohlcv"},
    "cvd_diff_usd": {
        "venues": "DESIGUAL: spot de binance+bybit menos futuros de binance",
        "warning": (
            "el perp mueve ~10x el spot ($9.7B vs $1.0B/24h en BTC), asi que el signo de esta "
            "columna lo manda la pata de futuros: en 92-95% de las sesiones equivale al CVD de "
            "futuros con el signo cambiado. No la leas como acumulacion spot; usa cvd_spot_usd."
        ),
    },
    "cvd_diff_2v_usd": {
        "venues": "binance+bybit en ambas patas",
        "note": "alinea los venues de las dos patas, pero NO corrige la asimetria de escala: "
        "el volumen de perp sigue siendo ~10x el de spot, asi que el diff sigue "
        "dominado por futuros. Solo existe desde v1.3.3, sin historico previo.",
    },
}


async def daily_data(
    conn: asyncpg.Connection, symbol: str, days: int, as_of: date | None = None
) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        WITH hist AS (
          SELECT session_date,
                 percent_rank() OVER (ORDER BY cvd_spot_usd) * 100 AS pct_spot,
                 percent_rank() OVER (ORDER BY cvd_diff_usd) * 100 AS pct_diff
          FROM daily_session_agg
          WHERE symbol=$1 AND ($3::date IS NULL OR session_date <= $3)
        ), selected AS (
          SELECT * FROM daily_session_agg
          WHERE symbol=$1 AND ($3::date IS NULL OR session_date <= $3)
          ORDER BY session_date DESC LIMIT $2
        )
        SELECT s.session_date,s.symbol,s.cvd_spot_usd,s.cvd_fut_usd,s.cvd_diff_usd,
               s.cvd_fut_2v_usd,s.cvd_diff_2v_usd,s.cvd_fut_2v_minutes,
               s.inst_delta_usd,s.price_open,s.price_close,s.price_chg_pct,
               s.oi_open,s.oi_close,s.oi_chg_usd,s.fr_avg,
               s.volume_usd,s.long_liq_usd,s.short_liq_usd,
               SUM(s.cvd_diff_usd) OVER (ORDER BY s.session_date) AS cumulative_diff,
               SUM(s.cvd_spot_usd) OVER (ORDER BY s.session_date) AS cumulative_spot,
               round(h.pct_spot::numeric,0)::float8 AS cvd_spot_percentile,
               round(h.pct_diff::numeric,0)::float8 AS cvd_diff_percentile,
               -- Una sesion de CVD describe agresion ejecutada, no acumulacion/distribucion
               -- institucional. Publicamos los signos factuales de ambas patas y la respuesta
               -- del precio; la UI no tiene que reinterpretar el diferencial sesgado por escala.
               CASE
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0 THEN 'ambos_compran'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0 THEN 'ambos_venden'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd < 0 THEN 'spot_compra_futuros_venden'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd > 0 THEN 'spot_vende_futuros_compran'
                 ELSE 'sin_dato'
               END AS flow_direction,
               CASE
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0
                      AND s.price_chg_pct >= 0 THEN 'venta_sin_caida'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0 THEN 'venta_con_caida'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0
                      AND s.price_chg_pct <= 0 THEN 'compra_sin_subida'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0 THEN 'compra_con_subida'
                 WHEN s.cvd_spot_usd * s.cvd_fut_usd < 0 THEN 'flujo_dividido'
                 ELSE 'sin_dato'
               END AS price_response
        FROM selected s JOIN hist h USING (session_date)
        ORDER BY s.session_date
        """,
        symbol,
        days,
        as_of,
    )
    values = records(rows)
    streak = 0
    for row in reversed(values):
        spot = float(row["cvd_spot_usd"])
        sign = 1 if spot > 0 else -1 if spot < 0 else 0
        if sign == 0:
            break
        if streak == 0:
            streak = sign
        elif (streak > 0 and sign > 0) or (streak < 0 and sign < 0):
            streak += sign
        else:
            break
    return {
        "symbol": symbol,
        "streak": streak,
        "streak_source": "cvd_spot_usd",
        "rows": values,
        "as_of": str(values[-1]["session_date"]) if values else None,
        "quick_read": daily_flow_read(values),
        "sources": DAILY_SOURCES,
    }


@app.get("/api/symbols")
async def symbols() -> list[dict[str, str]]:
    return [{"symbol": symbol, "asset": WS_SYMBOL_MAP[symbol]} for symbol in SETTINGS.SYMBOLS]


@app.get("/api/snapshot")
async def snapshot(symbol: str | None = None) -> Any:
    async with app.state.pool.acquire() as conn:
        if symbol:
            selected = validate_symbol(symbol)
            result = await latest_snapshot(conn, selected)
            if result is None:
                raise HTTPException(status_code=404, detail="No data")
            return result
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (symbol) * FROM metrics_snapshot
            WHERE symbol = ANY($1::text[])
            ORDER BY symbol, ts DESC
            """,
            list(SETTINGS.SYMBOLS),
        )
        return records(rows)


@app.get("/api/ohlcv")
async def ohlcv(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=2000)] = 288,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                (array_agg(open ORDER BY ts))[1] AS open,
                MAX(high) AS high, MIN(low) AS low,
                (array_agg(close ORDER BY ts DESC))[1] AS close,
                SUM(volume * close) AS volume_usd,
                COUNT(*)::int AS sample_count,
                $4::int AS expected_count,
                MAX(ts) AS last_sample
              FROM ohlcv WHERE symbol=$1 AND interval='1min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            )
            SELECT *,
              -- Una vela derivada no es una vela cerrada. Sin estos campos, un bucket con
              -- 2 de 5 minutos (o el que esta abriendose ahora) era indistinguible de uno
              -- completo y alimentaba ATR, estructura, rupturas y perfiles.
              (sample_count = expected_count) AS is_complete,
              (bucket + $2::interval <= now()) AS is_closed,
              round(sample_count::numeric * 100 / expected_count, 1) AS coverage_pct
            FROM grouped ORDER BY bucket
            """,
            selected,
            bucket,
            limit,
            int(bucket.total_seconds() // 60),
        )
    return records(rows)


@app.get("/api/cvd")
async def cvd(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(delta * close) AS delta_usd
              FROM ohlcv WHERE symbol=$1 AND interval='1min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            )
            SELECT bucket,delta_usd,SUM(delta_usd) OVER (ORDER BY bucket) AS cvd
            FROM grouped ORDER BY bucket
            """,
            selected,
            bucket,
            limit,
        )
        result = records(rows)
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
            value_keys=("delta_usd",),
            cumulative_keys=("cvd",),
        )
    return result


@app.get("/api/cvd/spot")
async def cvd_spot(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    ws_symbol = WS_SYMBOL_MAP[selected]
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(buy_vol_usd-sell_vol_usd) AS delta_usd
              FROM spot_trades_agg
              WHERE symbol=$1 AND exchange='combined' AND interval='1min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            )
            SELECT bucket,delta_usd,SUM(delta_usd) OVER (ORDER BY bucket) AS cvd
            FROM grouped ORDER BY bucket
            """,
            ws_symbol,
            bucket,
            limit,
        )
        result = records(rows)
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="spot_trades",
            exchanges=("binance", "bybit", "combined"),
            market="spot",
            symbol=ws_symbol,
            value_keys=("delta_usd",),
            cumulative_keys=("cvd",),
        )
    return result


@app.get("/api/cvd/divergence")
async def cvd_divergence(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    ws_symbol = WS_SYMBOL_MAP[selected]
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH bounds AS (
              SELECT LEAST(
                (SELECT MAX(ts)+interval '1 minute' FROM ohlcv
                 WHERE symbol=$1 AND interval='1min'),
                (SELECT MAX(ts)+interval '1 minute' FROM spot_trades_agg
                 WHERE symbol=$2 AND exchange='combined' AND interval='1min')
              ) AS complete_until
            ), fut AS (
              SELECT date_bin($3::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(delta*close) AS value
              FROM ohlcv WHERE symbol=$1 AND interval='1min'
              GROUP BY 1
            ), spot AS (
              SELECT date_bin($3::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(buy_vol_usd-sell_vol_usd) AS value
              FROM spot_trades_agg
              WHERE symbol=$2 AND exchange='combined' AND interval='1min'
              GROUP BY 1
            ), joined AS (
              SELECT fut.bucket,fut.value AS fut_delta,spot.value AS spot_delta
              FROM fut JOIN spot USING(bucket),bounds
              WHERE fut.bucket+$3::interval <= bounds.complete_until
              ORDER BY fut.bucket DESC LIMIT $4
            ), cumulative AS (
              SELECT bucket,
                SUM(fut_delta) OVER (ORDER BY bucket) AS cvd_fut,
                SUM(spot_delta) OVER (ORDER BY bucket) AS cvd_spot
              FROM joined
            )
            SELECT bucket,cvd_fut,cvd_spot,cvd_spot-cvd_fut AS cvd_diff
            FROM cumulative ORDER BY bucket
            """,
            selected,
            ws_symbol,
            bucket,
            limit,
        )
        result = records(rows)
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
            cumulative_keys=("cvd_fut", "cvd_diff"),
        )
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="spot_trades",
            exchanges=("binance", "bybit", "combined"),
            market="spot",
            symbol=ws_symbol,
            cumulative_keys=("cvd_spot", "cvd_diff"),
        )
    return result


@app.get("/api/oi")
async def oi(
    symbol: str,
    interval: str = "15min",
    limit: Annotated[int, Query(ge=10, le=2000)] = 384,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     (array_agg(oi_close ORDER BY ts DESC))[1] AS oi
              FROM open_interest WHERE symbol=$1 AND interval='5min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            ) SELECT * FROM grouped ORDER BY bucket
            """,
            selected,
            bucket,
            limit,
        )
    return records(rows)


@app.get("/api/liquidations")
async def liquidation_series(
    symbol: str,
    interval: str = "1hour",
    limit: Annotated[int, Query(ge=10, le=1000)] = 336,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(long_liq) AS long_liq,SUM(short_liq) AS short_liq
              FROM liquidations WHERE symbol=$1 AND interval='5min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            ) SELECT * FROM grouped ORDER BY bucket
            """,
            selected,
            bucket,
            limit,
        )
    return records(rows)


@app.get("/api/whale/delta")
async def whale_delta(
    symbol: str,
    interval: str = "15min",
    limit: Annotated[int, Query(ge=10, le=2000)] = 384,
) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    ws_symbol = WS_SYMBOL_MAP[selected]
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(inst_buy_usd-inst_sell_usd) AS whale_delta
              FROM spot_trades_agg
              WHERE symbol=$1 AND exchange='combined' AND interval='1min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            ) SELECT * FROM grouped ORDER BY bucket
            """,
            ws_symbol,
            bucket,
            limit,
        )
    return records(rows)


@app.get("/api/scalp/summary")
async def scalp_summary(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        ctx = await scalp_context(conn, selected)
    return {"symbol": selected, **compute_scalp_summary(ctx)}


@app.get("/api/scalp/delta-matrix")
async def scalp_delta_matrix(symbol: str) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    # 18m es una VENTANA MOVIL de 1080 s, no la vela de 18 m: para la vela cerrada y
    # alineada a medianoche UTC esta /api/ohlcv?interval=18min. Son cosas distintas y el
    # dashboard no debe mezclarlas.
    # 3d no entra aqui: futures_trades_agg retiene 36 h (SCALP_MINUTE_RETENTION_HOURS), asi
    # que solo podria devolver `partial`. El horizonte de varios dias vive en daily_session_agg.
    windows = [
        ("15s", 15),
        ("30s", 30),
        ("1m", 60),
        ("3m", 180),
        ("5m", 300),
        ("15m", 900),
        ("18m", 1080),
        ("30m", 1800),
        ("1h", 3600),
        ("4h", 14400),
        ("8h", 28800),
        ("1d", 86400),
    ]
    async with app.state.pool.acquire() as conn:
        return await delta_matrix(conn, selected, windows)


@app.get("/api/market-impact")
async def market_impact_endpoint(symbol: str) -> dict[str, Any]:
    """Impacto realizado (bps por millon de delta neto) contra su distribucion medida."""
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await market_impact(conn, selected)


@app.get("/api/positioning")
async def positioning(symbol: str) -> dict[str, Any]:
    """Reparto long/short con percentil contra su propio historico de 30 dias."""
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await positioning_context(conn, selected)


@app.get("/api/hypothesis")
async def hypothesis(
    symbol: str,
    profile: str = "intradia",
    direction: str | None = None,
    setup: str = "ninguno",
    hypothesis: str | None = None,
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    size_usd: float | None = None,
    fee_bps_per_side: float | None = None,
    order_type: str | None = None,
    exchange: str | None = None,
    slippage_bps: float | None = None,
    funding_bps: float | None = None,
) -> dict[str, Any]:
    """Clasifica la evidencia disponible frente a la tesis del operador.

    `direction` y `setup` son independientes. `hypothesis` sigue aceptandose para los valores
    guardados de la version anterior y se traduce al par correspondiente.
    """
    selected = validate_symbol(symbol)
    if hypothesis is not None and hypothesis not in HYPOTHESES:
        raise HTTPException(
            status_code=422, detail=f"hipotesis debe ser una de: {', '.join(HYPOTHESES)}"
        )
    if direction is not None and direction not in DIRECTIONS:
        raise HTTPException(
            status_code=422, detail=f"direccion debe ser una de: {', '.join(DIRECTIONS)}"
        )
    if setup not in SETUP_LABELS:
        raise HTTPException(
            status_code=422, detail=f"setup debe ser uno de: {', '.join(SETUP_LABELS)}"
        )
    if profile not in TRADING_PROFILES:
        raise HTTPException(
            status_code=422, detail=f"perfil debe ser uno de: {', '.join(TRADING_PROFILES)}"
        )
    if direction is None and hypothesis is None:
        direction = "long"
    async with app.state.pool.acquire() as conn:
        trend = await trend_matrix(conn, selected)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS)
        ctx = await scalp_context(conn, selected)
        barriers = await price_barriers(conn, selected)
        structure = await structure_detail(conn, selected)
        observ_bundle = await setup_confirmation_bundle(conn, selected, profile)
    view = profile_view(trend, matrix, profile)
    scalp = compute_scalp_summary(ctx)
    return {
        "symbol": selected,
        **hypothesis_evidence(
            hypothesis,
            view,
            scalp,
            direction=direction,
            setup=setup,
            setup_context=build_setup_context(
                scalp, view, trend, barriers, structure,
                direction=direction or split_hypothesis(hypothesis)[0],
                setup=setup if setup != "ninguno" else split_hypothesis(hypothesis)[1],
                observ_bundle=observ_bundle,
            ),
            plan={
                "entry": entry,
                "target": target,
                "stop": stop,
                "size_usd": size_usd,
                "fee_bps_per_side": fee_bps_per_side,
                "order_type": order_type,
                "exchange": exchange,
                "slippage_bps": slippage_bps,
                "funding_bps": funding_bps,
            },
        ),
    }


@app.get("/api/desk/state")
async def desk_state(
    symbol: str,
    profile: str = "intradia",
    direction: str | None = None,
    setup: str = "ninguno",
) -> dict[str, Any]:
    """Snapshot COHERENTE de la Mesa: un solo calculo, un solo ancla temporal.

    La Mesa pedia `/api/trend-matrix`, `/api/profile`, `/api/hypothesis` y
    `/api/dashboard/state` por separado. Cada uno volvia a calcular `trend_matrix`,
    `delta_matrix` y `scalp_context` con su propio `now()`, asi que dos paneles contiguos
    podian estar describiendo instantes distintos y contradecirse sin que se viera por que.

    Aqui los componentes compartidos se calculan UNA vez, en una sola conexion, y todos se
    publican bajo el mismo `as_of`. Los endpoints originales siguen existiendo: otras vistas
    los usan y no todas necesitan el paquete completo.
    """
    selected = validate_symbol(symbol)
    if profile not in TRADING_PROFILES:
        raise HTTPException(
            status_code=422, detail=f"perfil debe ser uno de: {', '.join(TRADING_PROFILES)}"
        )
    if direction is not None and direction not in DIRECTIONS:
        raise HTTPException(
            status_code=422, detail=f"direccion debe ser una de: {', '.join(DIRECTIONS)}"
        )
    if setup not in SETUP_LABELS:
        raise HTTPException(
            status_code=422, detail=f"setup debe ser uno de: {', '.join(SETUP_LABELS)}"
        )
    as_of = datetime.now(UTC)
    async with app.state.pool.acquire() as conn:
        trend = await trend_matrix(conn, selected)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS)
        ctx = await scalp_context(conn, selected)
        quality = await data_quality(conn, selected)
        barriers = await price_barriers(conn, selected)
        structure = await structure_detail(conn, selected)
        observ_bundle = await setup_confirmation_bundle(conn, selected, profile)
    scalp = compute_scalp_summary(ctx)
    view = profile_view(trend, matrix, profile)
    evidence = hypothesis_evidence(
        None,
        view,
        scalp,
        direction=direction or "long",
        setup=setup,
        setup_context=build_setup_context(
            scalp, view, trend, barriers, structure,
            direction=direction or "long",
            setup=setup,
            observ_bundle=observ_bundle,
        ),
    )
    stamp = as_of.isoformat()
    componentes = {
        "trend_matrix": trend,
        "delta_matrix": matrix,
        "profile": view,
        "hypothesis": evidence,
        "scalp": scalp,
        "data_quality": quality,
    }
    # Cada componente lleva el MISMO `computed_at`: es la prueba de que salieron del mismo
    # calculo. La frescura de cada FUENTE va aparte, porque un dato viejo no se vuelve actual
    # por haberse leido ahora.
    for bloque in componentes.values():
        if isinstance(bloque, dict):
            bloque["computed_at"] = stamp
    return {
        "symbol": selected,
        "as_of": stamp,
        "profile": profile,
        "direction": direction or "long",
        "setup": setup,
        "components": componentes,
        "source_timestamps": {
            "book_lag_seconds": scalp.get("book_lag_seconds"),
            "book_status": scalp.get("book_status"),
            "basis_status": scalp.get("basis_status"),
            "liquidations_measured": scalp.get("liquidations_measured"),
            "collectors": quality.get("collectors"),
            "liquidations_last_event_age_s": (quality.get("event_recency") or {}).get(
                "liquidations_last_event_age_s"
            ),
        },
        "partial": {
            "scalp_missing_components": scalp.get("missing_components"),
            "profile_missing_data": view.get("missing_data"),
            "scalp_coverage_pct": scalp.get("evidence_coverage_pct"),
            "profile_coverage_pct": view.get("coverage_pct"),
        },
        "note": (
            "Todos los componentes comparten `as_of`. Los estados parciales NO se ocultan: "
            "se declaran en `partial` y en el propio bloque."
        ),
    }


@app.get("/api/quality/feeds")
async def quality_feeds(symbol: str) -> dict[str, Any]:
    """Calidad de los FEEDS de mercado y de cada METRICA publicada.

    La pestana de calidad mostraba la salud de los procesos internos bajo el titulo "Fuentes
    de datos". Son cosas distintas: un colector vivo puede estar alimentando un feed al que
    le falta un venue, y un feed completo puede sostener una metrica cuya ventana esta a
    medias. Aqui van los tres niveles separados: servicios, feeds y metricas.
    """
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        feeds = await feed_quality(conn, selected)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS)
        ctx = await scalp_context(conn, selected)
        quality = await data_quality(conn, selected)
    scalp = compute_scalp_summary(ctx)
    return {
        **feeds,
        **metric_quality(matrix, scalp, feeds),
        "collectors": quality.get("collectors"),
        "contexts": {
            "scalp": quality.get("scalp"),
            "intraday": quality.get("intraday"),
            "macro": quality.get("macro"),
        },
    }


@app.get("/api/baselines")
async def metric_baselines(symbol: str, metric: str = "delta_ratio") -> dict[str, Any]:
    """Distribucion medida que sustenta cada umbral. Sin esto el score seria caja negra."""
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await load_baselines(conn, selected, metric)
    return {
        "symbol": selected,
        "metric": metric,
        "fallback_min_ratio": ABSORPTION_MIN_RATIO,
        "note": (
            "El umbral de magnitud es el p75 de cada ventana. |delta|/volumen decae al alargar "
            "la ventana, asi que una constante unica o pasa casi todo o no pasa nada."
        ),
        "windows": rows,
    }


@app.get("/api/profile")
async def trading_profile(symbol: str, profile: str = "intradia") -> dict[str, Any]:
    """Jerarquia de temporalidades del perfil elegido. No altera ningun dato bruto."""
    selected = validate_symbol(symbol)
    if profile not in TRADING_PROFILES:
        raise HTTPException(
            status_code=422,
            detail=f"perfil debe ser uno de: {', '.join(TRADING_PROFILES)}",
        )
    async with app.state.pool.acquire() as conn:
        trend = await trend_matrix(conn, selected)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS)
    return {"symbol": selected, **profile_view(trend, matrix, profile)}


@app.get("/api/scalp/execution-cost")
async def scalp_execution_cost(
    symbol: str,
    sizes: str = "1000,5000,10000,25000,50000",
    profile: str = "intradia",
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    size_usd: float | None = None,
    fee_bps_per_side: float | None = None,
    order_type: str | None = None,
    exchange: str | None = None,
    funding_bps: float | None = None,
) -> dict[str, Any]:
    """Slippage por tamanio sobre la escalera real, y coste TOTAL contra objetivo y riesgo.

    El slippage por venue es una medicion del libro. El veredicto de si la operacion sale
    cara depende ademas del objetivo, del stop y de las comisiones, que el sistema no conoce:
    si no se pasan, `assessment` responde SIN EVALUAR y enumera lo que falta.
    """
    selected = validate_symbol(symbol)
    if profile not in EXECUTION_PROFILES:
        raise HTTPException(
            status_code=422, detail=f"perfil debe ser uno de: {', '.join(EXECUTION_PROFILES)}"
        )
    try:
        parsed = [float(part) for part in sizes.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="sizes debe ser una lista de numeros") from None
    if not parsed or len(parsed) > 8 or any(s <= 0 or s > 5_000_000 for s in parsed):
        raise HTTPException(
            status_code=422, detail="hasta 8 tamanios, cada uno entre 0 y 5.000.000 USD"
        )
    async with app.state.pool.acquire() as conn:
        base = await execution_cost(conn, selected, parsed)
        ctx = await scalp_context(conn, selected)
    summary = compute_scalp_summary(ctx)
    # El slippage que entra en el coste total es el del tamano declarado, no el de un tamano
    # cualquiera de la lista: sin `size_usd` no se elige ninguno.
    slippage = _slippage_para(base, size_usd, exchange)
    base["assessment"] = execution_assessment(
        profile=profile,
        spread_bps=as_float(summary.get("spread_bps")),
        slippage_bps=slippage,
        fee_bps_per_side=fee_bps_per_side,
        order_type=order_type,
        size_usd=size_usd,
        exchange=exchange,
        entry=entry if entry is not None else as_float(summary.get("fut_price")),
        target=target,
        stop=stop,
        funding_bps=funding_bps,
    )
    base["profiles"] = EXECUTION_PROFILES
    return base


def _slippage_para(
    base: dict[str, Any], size_usd: float | None, exchange: str | None
) -> float | None:
    """Slippage publicado para ESE tamano y venue, o None si no se puede identificar."""
    if size_usd is None:
        return None
    candidatos = [
        v for v in base.get("venues", []) if v.get("status") == "VALID" and (exchange in (None, v.get("exchange")))
    ]
    valores = [
        fila.get("slippage_bps")
        for venue in candidatos
        for fila in (venue.get("buy") or [])
        if fila.get("size_usd") == size_usd and fila.get("slippage_bps") is not None
    ]
    return min(valores) if valores else None


@app.get("/api/flow/spot-vs-perp")
async def flow_spot_vs_perp(
    symbol: str,
    interval: str = "4hour",
    days: Annotated[int, Query(ge=1, le=730)] = 90,
) -> dict[str, Any]:
    """Spot vs perp del mismo venue con historia real (300 d a 4hour, ~2 anios a daily)."""
    selected = validate_symbol(symbol)
    if interval not in {"4hour", "daily"}:
        raise HTTPException(
            status_code=422,
            detail="interval debe ser 4hour o daily: son los que Coinalyze sirve con historia",
        )
    async with app.state.pool.acquire() as conn:
        return await spot_perp_flow(conn, selected, interval, days)


@app.get("/api/scalp/orderbook")
async def scalp_orderbook(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (exchange) * FROM orderbook_snapshot
            WHERE symbol=$1 AND ts >= now()-interval '30 seconds'
            ORDER BY exchange,ts DESC
            """,
            selected,
        )
    return {"symbol": selected, "rows": records(rows)}


@app.get("/api/scalp/absorption")
async def scalp_absorption(symbol: str) -> list[dict[str, Any]]:
    selected = validate_symbol(symbol)
    windows = [("1m", 60), ("3m", 180), ("5m", 300), ("15m", 900)]
    output: list[dict[str, Any]] = []
    async with app.state.pool.acquire() as conn:
        baselines = await load_baselines(conn, selected)
        for label, seconds in windows:
            row = await conn.fetchrow(
                """
                WITH fut AS (
                  SELECT SUM(buy_vol_usd-sell_vol_usd) AS delta,
                         SUM(buy_vol_usd+sell_vol_usd) AS volume,
                         COUNT(*)::int AS buckets,
                         -- El mayor hueco entre buckets dice si la ventana se midio entera:
                         -- contar buckets no basta porque TradeStore solo crea uno cuando
                         -- llega un trade, asi que su ausencia puede ser mercado quieto.
                         EXTRACT(EPOCH FROM max(ts)-min(ts))::float8 AS span_seconds,
                         (array_agg(last_px ORDER BY ts ASC))[1] AS first_px,
                         (array_agg(last_px ORDER BY ts DESC))[1] AS last_px
                  FROM futures_trades_realtime
                  WHERE symbol=$1 AND exchange='combined' AND ts >= now()-($2::int * interval '1 second')
                ) SELECT * FROM fut
                """,
                selected,
                seconds,
            )
            item = dict(row) if row else {"delta": None, "first_px": None, "last_px": None}
            # Sin delta medido no hay lectura; `or 0.0` la fabricaba.
            delta = as_float(item.get("delta"))
            volume = as_float(item.get("volume"))
            first_px = as_float(item.get("first_px"))
            last_px = as_float(item.get("last_px"))
            move = ((last_px - first_px) / first_px * 100) if first_px and last_px else None
            baseline = baselines.get(label)
            if delta is None or move is None:
                # None y no 0.0: "no evaluable" no es un score neutro medido.
                score, label_text = None, "No evaluable"
            else:
                score, label_text = classify_absorption(
                    delta, move, volume, (baseline or {}).get("p75")
                )
            ratio = (abs(delta) / volume) if delta is not None and volume else None
            output.append(
                {
                    "window": label,
                    "fut_delta": delta,
                    "fut_volume": volume,
                    "delta_ratio": ratio,
                    # El umbral es el p75 medido de ESTA ventana, no una constante global.
                    "min_ratio": (baseline or {}).get("p75", ABSORPTION_MIN_RATIO),
                    "threshold_source": (
                        "baseline_p75_medido" if baseline else "fallback_constante"
                    ),
                    "context": baseline_band(ratio, baseline),
                    "price_move_pct": move,
                    "absorption": label_text,
                    "score": score,
                    # Cobertura DECLARADA de la ventana: cuantos buckets la sostienen y que
                    # tramo cubren de verdad. Sin esto, "Absorcion fuerte" sobre dos buckets
                    # sueltos se lee igual que sobre la ventana completa.
                    "coverage": {
                        "buckets": int(item.get("buckets") or 0),
                        "span_seconds": as_float(item.get("span_seconds")),
                        "window_seconds": seconds,
                        "span_ratio": (
                            round(as_float(item["span_seconds"]) / seconds, 3)
                            if as_float(item.get("span_seconds")) is not None
                            else None
                        ),
                    },
                    "timeframe": label,
                }
            )
    return output


@app.get("/api/scalp/liquidations")
async def scalp_liquidations(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    windows = [("1m", 60), ("5m", 300), ("15m", 900)]
    async with app.state.pool.acquire() as conn:
        matrix = []
        for label, seconds in windows:
            row = await conn.fetchrow(
                """
                SELECT $2::text AS window,
                       SUM(CASE WHEN side='long' THEN notional_usd ELSE 0 END) AS long_liq,
                       SUM(CASE WHEN side='short' THEN notional_usd ELSE 0 END) AS short_liq,
                       COUNT(*) AS events
                FROM liquidations_realtime WHERE symbol=$1 AND ts >= now()-($3::int * interval '1 second')
                """,
                selected,
                label,
                seconds,
            )
            matrix.append(dict(row))
        # Ventanas largas: historico multi-exchange del API de Coinalyze (buckets 5min, lag ~1-2 min)
        for label, seconds in (("30m", 1800), ("1h", 3600), ("4h", 14400)):
            row = await conn.fetchrow(
                """
                SELECT $2::text AS window,
                       SUM(long_liq) AS long_liq,SUM(short_liq) AS short_liq,NULL::bigint AS events
                FROM liquidations WHERE symbol=$1 AND interval='5min' AND ts >= now()-($3::int * interval '1 second')
                """,
                selected,
                label,
                seconds,
            )
            matrix.append(dict(row))
        recent = await conn.fetch(
            """
            SELECT ts,exchange,side,notional_usd,price,qty FROM liquidations_realtime
            WHERE symbol=$1 ORDER BY ts DESC LIMIT 20
            """,
            selected,
        )
    return {"symbol": selected, "matrix": matrix, "recent": records(recent)}


@app.get("/api/scalp/alerts")
async def scalp_alerts(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        ctx = await scalp_context(conn, selected)
        impact = await market_impact(conn, selected)
    summary = compute_scalp_summary(ctx)
    alerts: list[dict[str, Any]] = []
    if summary["state"] != "No Trade":
        alerts.append(
            {
                "priority": "P1",
                "side": "LONG" if summary["long_score"] > summary["short_score"] else "SHORT",
                "message": summary["state"],
                "detail": summary["reason"],
            }
        )
    if "Absorción" in str(summary["absorption"]):
        alerts.append(
            {
                "priority": "P2",
                "side": "LONG" if "ventas" in str(summary["absorption"]) else "SHORT",
                "message": summary["absorption"],
                "detail": "Delta agresivo sin desplazamiento proporcional del precio",
            }
        )
    if summary.get("book_status") in {"missing", "stale"}:
        alerts.append(
            {
                "priority": "P1",
                "side": "NO TRADE",
                "message": "Order book no confiable",
                "detail": f"book_status={summary.get('book_status')} lag={summary.get('book_lag_seconds')}",
            }
        )
    spread_bps = summary.get("spread_bps")
    spread_warn = EXECUTION_PROFILES["intradia"]["spread_warn_bps"]
    if spread_bps is not None and spread_bps > spread_warn:
        alerts.append(
            {
                # Aviso por perfil, no veto universal: 5 bps arruinan un scalp de 20 bps y no
                # significan nada en un swing de 400. El veredicto lo da el coste/objetivo.
                "priority": "P2",
                "side": "AVISO",
                "message": f"Spread ancho para intradía (> {spread_warn:g} bps)",
                "detail": f"Spread {spread_bps:.2f} bps · umbral de aviso, no operativo",
            }
        )
    # El basis dejo de publicarse como numero cuando las patas se desfasan (P0); si nadie lo
    # avisa, el operador solo ve un hueco y no sabe por que.
    if summary.get("basis_status") in {"STALE", "UNAVAILABLE"}:
        detail = (summary.get("basis_detail") or {}).get("reason") or ""
        alerts.append(
            {
                "priority": "P2",
                "side": "NO TRADE",
                "message": f"Basis no utilizable ({summary['basis_status']})",
                "detail": detail,
            }
        )
    alerts.extend(statistical_alerts(summary, impact))
    return {"symbol": selected, "alerts": alerts}


def statistical_alerts(summary: dict[str, Any], impact: dict[str, Any]) -> list[dict[str, Any]]:
    """Avisos que solo tienen sentido contra la distribucion historica, no contra un umbral.

    Una alerta por valor absoluto ("delta > X USD") se dispara sola en un activo liquido y no
    salta nunca en uno fino. Estas comparan cada lectura con SU propia distribucion medida, y
    por eso callan si no hay baseline en vez de inventar un umbral.
    """
    out: list[dict[str, Any]] = []
    absorption = summary.get("absorption_context") or {}
    if absorption.get("band") in {"alto", "extremo"}:
        out.append(
            {
                "priority": "P2",
                "side": "OBSERVAR",
                "message": f"Flujo agresivo {absorption['band']} en 3m",
                "detail": (
                    f"|delta|/volumen={summary.get('absorption_delta_ratio')} "
                    f"(z robusto {absorption.get('robust_z')}, n={absorption.get('sample_count')})"
                ),
            }
        )
    for window in impact.get("windows", []):
        band = (window.get("context") or {}).get("band")
        # Solo los extremos de liquidez: 'alto' aparece por definicion el 5-10% del tiempo.
        if band != "extremo" or not window.get("coverage_complete"):
            continue
        out.append(
            {
                "priority": "P2",
                "side": "OBSERVAR",
                "message": f"Impacto de mercado extremo en {window['window']}",
                "detail": (
                    f"{window['impact_bps_per_musd']} bps por millon "
                    f"(z robusto {(window.get('context') or {}).get('robust_z')}): "
                    f"{window.get('reading')}"
                ),
            }
        )
    return out


@app.get("/api/funding-context")
async def funding_context_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await funding_context(conn, selected)


@app.get("/api/liquidation-map")
async def liquidation_map_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await liquidation_map(conn, selected)


@app.get("/api/volume-profile")
async def volume_profile_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await volume_profile(conn, selected)


@app.get("/api/delta-profile")
async def delta_profile_endpoint(
    symbol: str,
    interval: str = "4hour",
    days: Annotated[int, Query(ge=1, le=400)] = 90,
    price: Annotated[float | None, Query(gt=0)] = None,
) -> dict[str, Any]:
    """Volumen y delta por nivel de precio sobre la ventana pedida.

    Distinto de /api/volume-profile, que es la sesion UTC en curso sin separar compra de venta.
    """
    selected = validate_symbol(symbol)
    if interval not in DELTA_PROFILE_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"interval must be one of {sorted(DELTA_PROFILE_INTERVALS)}",
        )
    async with app.state.pool.acquire() as conn:
        return await delta_profile(conn, selected, interval, days, price)


@app.get("/api/price-barriers")
async def price_barriers_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await price_barriers(conn, selected)


@app.get("/api/zone/analysis")
async def zone_analysis_endpoint(
    symbol: str,
    low: Annotated[float, Query(gt=0)],
    high: Annotated[float, Query(gt=0)],
    days: Annotated[int, Query(ge=7, le=365)] = 365,
) -> dict[str, Any]:
    """Caracter de una zona de precio: acumulacion, distribucion o rotacion sin caracter."""
    selected = validate_symbol(symbol)
    if low >= high:
        raise HTTPException(status_code=422, detail="low must be below high")
    if high / low > 3:
        raise HTTPException(status_code=422, detail="zone spans more than 3x; narrow it")
    async with app.state.pool.acquire() as conn:
        return await zone_analysis(conn, selected, low, high, days)


@app.get("/api/range/validate")
async def range_validate_endpoint(
    symbol: str,
    low: Annotated[float, Query(gt=0)],
    high: Annotated[float, Query(gt=0)],
    days: Annotated[int, Query(ge=40, le=730)] = 180,
    end_days_ago: Annotated[int, Query(ge=0, le=690)] = 0,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, Any]:
    """Valida si un tramo es realmente un rango, con cinco tests de umbral explicito.

    El tramo se acota por fechas (start_date/end_date) o por ventana movil (days).
    """
    selected = validate_symbol(symbol)
    if low >= high:
        raise HTTPException(status_code=422, detail="low must be below high")
    if high / low > 3:
        raise HTTPException(status_code=422, detail="range spans more than 3x; narrow it")
    if (start_date is None) != (end_date is None):
        raise HTTPException(status_code=422, detail="start_date and end_date must come together")
    if start_date is not None and end_date is not None:
        if start_date >= end_date:
            raise HTTPException(status_code=422, detail="start_date must be before end_date")
        if (end_date - start_date).days > 730:
            raise HTTPException(status_code=422, detail="span exceeds the 730 days of history")
    elif days + end_days_ago > 730:
        raise HTTPException(status_code=422, detail="days + end_days_ago exceeds daily history")
    async with app.state.pool.acquire() as conn:
        return await range_validate(
            conn, selected, low, high, days, end_days_ago, start_date, end_date
        )


@app.get("/api/level/breakout")
async def level_breakout_endpoint(
    symbol: str,
    level: Annotated[float, Query(gt=0)],
    direction: str = "up",
) -> dict[str, Any]:
    """Tasa base historica de ruptura de un nivel, con n e intervalo de confianza."""
    selected = validate_symbol(symbol)
    if direction not in {"up", "down"}:
        raise HTTPException(status_code=422, detail="direction must be 'up' or 'down'")
    async with app.state.pool.acquire() as conn:
        return await level_breakout(conn, selected, level, direction == "up")


@app.get("/api/wyckoff")
async def wyckoff_endpoint(symbol: str) -> dict[str, Any]:
    """Detecta el rango reciente y explica su sesgo Wyckoff sin entrada manual."""
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await wyckoff_context(conn, selected)


@app.get("/api/context-metadata")
async def context_metadata_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await context_metadata(conn, selected)


@app.get("/api/reference-levels")
async def reference_levels_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await reference_levels(conn, selected)


@app.get("/api/cross-asset")
async def cross_asset_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await cross_asset(conn, selected)


@app.get("/api/oi-context")
async def oi_context_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await oi_context(conn, selected)


@app.get("/api/volatility")
async def volatility_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await volatility_context(conn, selected)


@app.get("/api/swing-score")
async def swing_score_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await swing_score(conn, selected)


@app.get("/api/trend-matrix")
async def trend_matrix_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await trend_matrix(conn, selected)


@app.get("/api/passive-flow")
async def passive_flow_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await passive_flow(conn, selected)


@app.get("/api/cvd-matrix")
async def cvd_matrix_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await cvd_matrix(conn, selected)


@app.get("/api/structure-detail")
async def structure_detail_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await structure_detail(conn, selected)


@app.get("/api/macro-context")
async def macro_context_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await macro_context(conn, selected)


@app.get("/api/external-macro")
async def external_macro_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        external = await external_macro_context(
            conn, etf_configured=bool(SETTINGS.COINGLASS_API_KEY)
        )
        return align_with_internal(external, await swing_score(conn, selected))


@app.get("/api/divergences")
async def divergences_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await divergence_scan(conn, selected)


@app.get("/api/market-memory")
async def market_memory_endpoint(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await market_memory(conn, selected)


@app.get("/api/verdicts")
async def verdicts(
    symbol: str,
    limit: Annotated[int, Query(ge=1, le=730)] = 90,
) -> dict[str, Any]:
    """Veredictos que el modelo emitio en sesiones pasadas, con el retorno posterior real.

    No evalua nada por su cuenta: expone el par (lo que dijo, lo que hizo el precio) para
    que se pueda auditar. Los pesos del score siguen sin calibrar contra estos resultados.
    """
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH v AS (
              SELECT * FROM daily_verdict WHERE symbol=$1
              ORDER BY session_date DESC LIMIT $2
            )
            SELECT v.session_date,v.swing_bias,v.swing_score,v.swing_conviction,
                   v.long_share_pct,v.regime_score,v.regime_label,
                   v.setup_id,v.setup_name,v.setup_state,v.setup_confidence,
                   v.daily_streak,v.price_close,
                   (SELECT (d.price_close/v.price_close-1)*100 FROM daily_session_agg d
                     WHERE d.symbol=$1 AND d.session_date>v.session_date
                     ORDER BY d.session_date OFFSET 6 LIMIT 1) AS fwd_return_7s_pct,
                   (SELECT (d.price_close/v.price_close-1)*100 FROM daily_session_agg d
                     WHERE d.symbol=$1 AND d.session_date>v.session_date
                     ORDER BY d.session_date OFFSET 13 LIMIT 1) AS fwd_return_14s_pct
            FROM v ORDER BY v.session_date DESC
            """,
            selected,
            limit,
        )
    return {
        "symbol": selected,
        "rows": records(rows),
        "note": (
            "fwd_return_*_pct es el retorno realizado desde el cierre de esa sesion; null "
            "mientras el horizonte no se haya cumplido. Se empezo a registrar en v1.3.3, "
            "asi que la serie arranca vacia y se llena con el tiempo."
        ),
    }


@app.get("/api/structure")
async def structure(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await market_structure(conn, selected)


@app.get("/api/daily")
async def daily(
    symbol: str,
    days: Annotated[int, Query(ge=2, le=730)] = 60,
    as_of: date | None = None,
) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await daily_data(conn, selected, days, as_of)


@app.get("/api/setup")
async def setup(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        snap = await latest_snapshot(conn, selected)
        if snap is None:
            raise HTTPException(status_code=404, detail="No data")
        daily_result = await daily_data(conn, selected, 60)
    return {
        "symbol": selected,
        "snapshot_ts": snap["ts"],
        **evaluate_setups(snap, daily_result["rows"]),
    }


@app.get("/api/scalp/signals")
async def scalp_signals(
    symbol: str,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ts,symbol,long_score,short_score,state,confidence,reason,
                   fut_delta_1m,fut_delta_3m,spot_delta_3m,diff_3m,
                   spot_fut_divergence_norm,book_status,book_lag_seconds,
                   basis_bps,absorption
            FROM scalp_signal_snapshot
            WHERE symbol=$1
            ORDER BY ts DESC LIMIT $2
            """,
            selected,
            limit,
        )
    return {"symbol": selected, "rows": records(rows)}


@app.get("/api/scalp/basis")
async def scalp_basis(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    asset = WS_SYMBOL_MAP[selected]
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH fut AS (
              SELECT ts,last_px,last_event_ms FROM futures_trades_realtime
              WHERE symbol=$1 AND exchange='combined'
              ORDER BY ts DESC LIMIT 1
            ), spot AS (
              SELECT ts,last_px,last_event_ms FROM spot_trades_realtime
              WHERE symbol=$2 AND exchange='combined'
              ORDER BY ts DESC LIMIT 1
            )
            SELECT fut.ts AS fut_ts,spot.ts AS spot_ts,
                   fut.last_px AS fut_price,spot.last_px AS spot_price,
                   fut.last_event_ms AS fut_event_ms,spot.last_event_ms AS spot_event_ms,
                   (EXTRACT(EPOCH FROM now())*1000)::float8 AS now_ms,
                   EXTRACT(EPOCH FROM now()-fut.ts)::float8 AS fut_lag_seconds,
                   EXTRACT(EPOCH FROM now()-spot.ts)::float8 AS spot_lag_seconds
            FROM fut FULL JOIN spot ON true
            """,
            selected,
            asset,
        )
    item = dict(row) if row else {}
    quality = basis_quality(
        as_float(item.get("fut_price")),
        as_float(item.get("spot_price")),
        as_float(item.get("fut_event_ms")),
        as_float(item.get("spot_event_ms")),
        as_float(item.get("now_ms")) or 0.0,
    )
    return {"symbol": selected, **item, **quality}


@app.get("/api/scalp/liquidation-levels")
async def liquidation_levels(
    symbol: str,
    minutes: Annotated[int, Query(ge=1, le=1440)] = 60,
    bucket_bps: Annotated[int, Query(ge=1, le=100)] = 10,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
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
            SELECT price_bucket,long_liq,short_liq,total_notional,events
            FROM levels
            ORDER BY total_notional DESC NULLS LAST
            LIMIT $4
            """,
            selected,
            minutes,
            bucket_bps,
            limit,
        )
    return {"symbol": selected, "minutes": minutes, "bucket_bps": bucket_bps, "rows": records(rows)}


@app.get("/api/data-confidence")
async def data_confidence(symbol: str | None = None) -> dict[str, Any]:
    selected_symbols = [validate_symbol(symbol)] if symbol else list(SETTINGS.SYMBOLS)
    async with app.state.pool.acquire() as conn:
        rows = [await data_confidence_row(conn, selected) for selected in selected_symbols]
    return {"rows": rows}


@app.get("/api/dashboard/state")
async def dashboard_state(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        snap = await latest_snapshot(conn, selected)
        ctx = await scalp_context(conn, selected)
        setup_result = None
        cvd_swing = None
        barriers = await price_barriers(conn, selected)
        memory = await market_memory(conn, selected)
        if snap:
            daily_result = await daily_data(conn, selected, 730)
            setup_result = evaluate_setups(snap, daily_result["rows"][-60:])
            cvd_swing = cvd_swing_read(daily_result["rows"])
    return {
        "symbol": selected,
        "snapshot": snap,
        "scalp": compute_scalp_summary(ctx),
        "setup": setup_result,
        "cvd_swing": cvd_swing,
        "barriers": barriers,
        "market_memory": memory,
    }


@app.get("/api/ai/context")
async def ai_context(
    symbol: str,
    profile: str = "default",
    bucket_bps: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    try:
        selected_profile = normalize_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    async with app.state.pool.acquire() as conn:
        return await build_ai_symbol_context(
            conn, selected, profile=selected_profile, bucket_bps=bucket_bps
        )


@app.get("/api/ai/context/bundle")
async def ai_context_bundle(
    symbols: str | None = None,
    profile: str = "default",
    bucket_bps: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, Any]:
    if symbols:
        requested = [part.strip() for part in symbols.split(",") if part.strip()]
    else:
        requested = list(SETTINGS.SYMBOLS)
    selected_symbols = [validate_symbol(symbol) for symbol in requested]
    try:
        selected_profile = normalize_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    async with app.state.pool.acquire() as conn:
        return await build_ai_context(
            conn, selected_symbols, profile=selected_profile, bucket_bps=bucket_bps
        )


@app.get("/api/ai/profiles")
async def ai_profiles() -> dict[str, Any]:
    return {
        "profiles": {
            "lite": {"purpose": "mínimo costo y menor payload", "recommended_for": "/chatgpt-lite"},
            "default": {"purpose": "operativa diaria", "recommended_for": "/chatgpt"},
            "pro": {
                "purpose": "análisis extendido bajo demanda, incluye 30 sesiones de histórico diario",
                "recommended_for": "/chatgpt-pro",
            },
            "max": {
                "purpose": "sin recortes: 90 sesiones de CVD diario, divergencias intradía, "
                "veredictos pasados. Pensado para pegar el JSON en una IA por web, "
                "donde el coste en tokens no es la restricción",
                "recommended_for": "/preview",
            },
        },
        "endpoints": [
            "/api/ai/context?symbol=ETHUSDT_PERP.A&profile=default",
            "/api/ai/context/bundle?symbols=BTCUSDT_PERP.A,ETHUSDT_PERP.A&profile=lite",
        ],
    }


def _parse_heartbeat_detail(detail: object) -> dict[str, float]:
    if not isinstance(detail, str):
        return {}
    values: dict[str, float] = {}
    for segment in detail.replace(";", ",").split(","):
        if ":" not in segment:
            continue
        key, raw = segment.split(":", 1)
        key = key.strip().replace("-", "_")
        raw = raw.strip().rstrip("s")
        try:
            values[key] = float(raw)
        except ValueError:
            continue
    return values


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    if not SETTINGS.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    async with app.state.pool.acquire() as conn:
        heartbeats = await conn.fetch(
            """
            SELECT service,status,detail,
                   EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag_seconds
            FROM pipeline_heartbeat ORDER BY service
            """
        )
        latest = await conn.fetch(
            """
            SELECT symbol,EXTRACT(EPOCH FROM now()-MAX(ts))::float8 AS lag_seconds
            FROM metrics_snapshot GROUP BY symbol ORDER BY symbol
            """
        )
        counts = await conn.fetch(
            """
            SELECT 'futures_trades_realtime' AS table_name, COUNT(*)::bigint AS rows FROM futures_trades_realtime
            UNION ALL SELECT 'orderbook_snapshot', COUNT(*)::bigint FROM orderbook_snapshot
            UNION ALL SELECT 'liquidations_realtime', COUNT(*)::bigint FROM liquidations_realtime
            UNION ALL SELECT 'scalp_signal_snapshot', COUNT(*)::bigint FROM scalp_signal_snapshot
            """
        )
    lines = [
        "# HELP coinalyze_heartbeat_lag_seconds Seconds since service heartbeat.",
        "# TYPE coinalyze_heartbeat_lag_seconds gauge",
    ]
    for row in heartbeats:
        status_ok = 1 if row["status"] == "ok" else 0
        lines.append(
            f'coinalyze_heartbeat_lag_seconds{{service="{row["service"]}"}} {float(row["lag_seconds"]):.3f}'
        )
        lines.append(f'coinalyze_service_ok{{service="{row["service"]}"}} {status_ok}')
    lines.extend(
        [
            "# HELP coinalyze_symbol_snapshot_lag_seconds Seconds since latest metrics snapshot per symbol.",
            "# TYPE coinalyze_symbol_snapshot_lag_seconds gauge",
        ]
    )
    for row in latest:
        lines.append(
            f'coinalyze_symbol_snapshot_lag_seconds{{symbol="{row["symbol"]}"}} {float(row["lag_seconds"]):.3f}'
        )
    lines.extend(
        [
            "# HELP coinalyze_table_rows Current row count for key realtime tables.",
            "# TYPE coinalyze_table_rows gauge",
        ]
    )
    for row in counts:
        lines.append(f'coinalyze_table_rows{{table="{row["table_name"]}"}} {int(row["rows"])}')

    scalp_detail = next((row["detail"] for row in heartbeats if row["service"] == "scalp"), None)
    scalp_values = _parse_heartbeat_detail(scalp_detail)
    metric_keys = {
        "liq_dropped": "coinalyze_scalp_liquidations_dropped_total",
        "trade_dropped_buckets": "coinalyze_scalp_tradestore_dropped_buckets_total",
        "trade_dropped_trades": "coinalyze_scalp_tradestore_dropped_trades_total",
        "binance_book_stale": "coinalyze_scalp_binance_book_stale_total",
        "binance_reconnects": "coinalyze_scalp_binance_book_reconnect_total",
        "trade_buckets_rt": "coinalyze_scalp_tradestore_realtime_buckets",
        "trade_buckets_minute": "coinalyze_scalp_tradestore_minute_buckets",
    }
    lines.extend(
        [
            "# HELP coinalyze_scalp_runtime_value Runtime values published by scalp heartbeat detail.",
            "# TYPE coinalyze_scalp_runtime_value gauge",
        ]
    )
    for key, metric_name in metric_keys.items():
        if key in scalp_values:
            lines.append(f"{metric_name} {scalp_values[key]:.0f}")
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")


@app.get("/api/healthz")
async def health() -> dict[str, Any]:
    thresholds = {
        "ingest": max(INGEST_COMPONENT_MAX_AGES.values()),
        **{
            f"ingest:{component}": max_age
            for component, max_age in INGEST_COMPONENT_MAX_AGES.items()
        },
        "ws": 90.0,
        "scalp": 90.0,
        "daily": 3900.0,
        "api": 180.0,
    }
    async with app.state.pool.acquire() as conn:
        await conn.fetchval("SELECT 1")
        await heartbeat(conn, "api")
        heartbeats = await conn.fetch(
            "SELECT service,updated_at,status,detail,"
            "EXTRACT(EPOCH FROM now()-updated_at)::float8 AS lag_seconds "
            "FROM pipeline_heartbeat ORDER BY service"
        )
        latest = await conn.fetch(
            """
            SELECT symbol,MAX(ts) AS latest_snapshot,
                   EXTRACT(EPOCH FROM now()-MAX(ts))::float8 AS lag_seconds
            FROM metrics_snapshot GROUP BY symbol ORDER BY symbol
            """
        )
    by_service = {str(row["service"]): row for row in heartbeats}
    missing_services = sorted(set(thresholds) - set(by_service))
    degraded = bool(required_heartbeat_failures(heartbeats, thresholds))
    latest_by_symbol = {str(row["symbol"]): row for row in latest}
    missing_symbols = sorted(set(SETTINGS.SYMBOLS) - set(latest_by_symbol))
    if missing_symbols or any(float(row["lag_seconds"]) > 180.0 for row in latest):
        degraded = True
    return {
        "status": "degraded" if degraded else "ok",
        "missing_services": missing_services,
        "missing_symbols": missing_symbols,
        "services": records(heartbeats),
        "symbols": records(latest),
    }


async def stream_generator(request: Request) -> AsyncIterator[bytes]:
    while not await request.is_disconnected():
        try:
            async with app.state.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT ON (symbol) symbol,ts,last_px,
                      buy_vol_usd-sell_vol_usd AS delta_5s,
                      inst_buy_usd-inst_sell_usd AS whale_delta_5s,
                      trade_count
                    FROM spot_trades_realtime
                    WHERE exchange='combined' AND ts >= now()-interval '30 seconds'
                    ORDER BY symbol,ts DESC
                    """
                )
                scalp = await conn.fetch(
                    """
                    SELECT DISTINCT ON (symbol) symbol,ts,last_px,
                      buy_vol_usd-sell_vol_usd AS fut_delta_5s,
                      large_buy_usd-large_sell_usd AS large_delta_5s,
                      trade_count
                    FROM futures_trades_realtime
                    WHERE exchange='combined' AND ts >= now()-interval '30 seconds'
                    ORDER BY symbol,ts DESC
                    """
                )
                books = await conn.fetch(
                    """
                    SELECT DISTINCT ON (symbol) symbol,ts,spread_bps,imbalance_l5
                    FROM orderbook_snapshot
                    WHERE exchange='combined' AND ts >= now()-interval '30 seconds'
                    ORDER BY symbol,ts DESC
                    """
                )
                payload = {
                    "type": "tick",
                    "rows": records(rows),
                    "scalp": records(scalp),
                    "books": records(books),
                }
            yield b"data: " + orjson.dumps(payload) + b"\n\n"
        except Exception:
            LOGGER.exception("sse_iteration_failed")
            yield b'event: status\ndata: {"status":"degraded"}\n\n'
        await asyncio.sleep(3)


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    return StreamingResponse(
        stream_generator(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
