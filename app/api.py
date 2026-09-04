from __future__ import annotations

import asyncio
import hmac
import json
import logging
from collections.abc import AsyncIterator, Callable
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
    ORDERBOOK_EDAD_SQL,
    ORDERBOOK_FRESCAS_SQL,
    ORDERBOOK_MAX_AGE_SECONDS,
    build_ai_context,
    build_ai_symbol_context,
    data_confidence_row,
    normalize_profile,
    orderbook_freshness,
)
from app.config import SUPPORTED_SYMBOLS, WS_SYMBOL_MAP, get_settings
from app.daily_agg import (
    DAILY_VERDICT_LOGIC_VERSION,
    DAILY_VERDICT_OUTCOME_VERSION,
)
from app.data_gaps import (
    GapRequirement,
    blocking_requirement_keys,
    coverage_entry,
    declared_gap_windows,
    expected_buckets,
)
from app.db import (
    INGEST_COMPONENT_MAX_AGES,
    create_pool,
    db_identity,
    heartbeat,
    heartbeat_max_age,
    required_heartbeat_failures,
)
from app.delta_profile import delta_profile
from app.external_macro import align_with_internal, external_macro_context
from app.interpretation import cvd_swing_read, daily_flow_read, evaluate_setups
from app.logging_setup import configure_logging
from app.metrics import session_bounds
from app.scalp_logic import (
    ABSORPTION_MIN_RATIO,
    EXECUTION_PROFILES,
    HYPOTHESES,
    PROFILE_WINDOWS,
    TRADING_PROFILES,
    as_float,
    compute_scalp_summary,
    context_metadata,
    cross_asset,
    cvd_matrix,
    data_quality,
    delta_matrix,
    divergence_scan,
    execution_assessment,
    execution_cost,
    feed_quality_view,
    funding_context,
    hypothesis_evidence,
    level_breakout,
    liquidation_map,
    load_baselines,
    macro_context,
    market_impact,
    market_memory,
    market_structure,
    oi_context,
    passive_flow,
    positioning_context,
    price_barriers,
    profile_view,
    range_validate,
    reference_levels,
    resolve_matrix_as_of,
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
from app.scalp_logic import (
    scalp_absorption as scalp_absorption_read,
)
from app.scalp_logic import (
    scalp_basis as scalp_basis_read,
)
from app.scalp_logic import (
    scalp_liquidations as scalp_liquidations_read,
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
    row_window: Callable[[dict[str, Any]], tuple[datetime, datetime] | None] | None = None,
) -> None:
    """Expose gap buckets as null and never continue an incomplete cumulative value.

    ``row_window`` resolves each row's real window when it is not ``[bucket, bucket+size)``.
    /api/daily lo necesita: su fila NO es un dia UTC sino una sesion de Nueva York, de
    09:30 a 09:30 ET (app/metrics.py:31), que ademas no siempre dura 24 h por los cambios
    de horario. Enmascararla con medianoche UTC y un tamano fijo taparia el DIA
    EQUIVOCADO, que es peor que no enmascarar: pondria a null un dia sano y dejaria
    intacto el roto.
    """
    indexed_starts: list[tuple[int, datetime, datetime]] = []
    for index, row in enumerate(rows):
        if row_window is not None:
            ventana = row_window(row)
            if ventana is None:
                continue
            inicio, fin = ventana
        else:
            candidato = row.get("bucket")
            if not isinstance(candidato, datetime):
                continue
            inicio, fin = candidato, candidato + bucket
        indexed_starts.append((index, inicio, fin))
    if not indexed_starts:
        return
    source_window_start = min(inicio for _, inicio, _ in indexed_starts)
    requirements: list[GapRequirement] = []
    for index, inicio, fin in indexed_starts:
        for exchange in exchanges:
            requirements.append(
                GapRequirement(
                    f"value:{index}",
                    feed,
                    exchange,
                    market,
                    symbol,
                    inicio,
                    fin,
                )
            )
            if cumulative_keys:
                requirements.append(
                    GapRequirement(
                        f"cumulative:{index}",
                        feed,
                        exchange,
                        market,
                        symbol,
                        source_window_start,
                        fin,
                    )
                )
    blocked = await blocking_requirement_keys(conn, requirements)
    blocked_values = {
        int(key.removeprefix("value:")) for key in blocked if key.startswith("value:")
    }
    blocked_cumulative = {
        int(key.removeprefix("cumulative:"))
        for key in blocked
        if key.startswith("cumulative:")
    }
    for index in blocked_values:
        row = rows[index]
        for value_key in value_keys:
            row[value_key] = None
    for index in blocked_cumulative:
        row = rows[index]
        for cumulative_key in cumulative_keys:
            row[cumulative_key] = None


# --- EL HUECO SE DECLARA, NO SE ADIVINA ------------------------------------------
# K02 puso a null lo que no se sabe. Un null es honrado pero es MUDO: no dice de cuando
# a cuando, ni si volvera, ni quien lo apunto. Y hay una perdida que el null ni siquiera
# puede ensenar, medida en 140 el 2026-08-25: en /api/ohlcv de BTC con interval=1hour,
# las 15:00 del 2026-08-14 traen 60 barras, las 16:00 traen 47, las 18:00 traen 47, las
# 19:00 traen 60 y LAS 17:00 NO APARECEN. La serie salta de 16 a 18 sin una fila que
# poner a null, asi que el panel dibuja una linea continua sobre una hora que no existe.
# Lo unico que lo destapa es comparar los buckets servidos contra los esperados.
#
# Asi que la respuesta lleva dos bloques, y son dos preguntas distintas:
#   coverage.served_window  cuantos buckets deberia haber en la ventana que te sirvo y
#                           cuantos hay. Aqui sale el bucket AUSENTE.
#   data_gaps               que ventanas estan declaradas como hueco, con su estado y
#                           quien las apunto. Aqui sale el POR QUE.
# El sistema ya sabia las dos cosas: data_gap las tiene desde el ingest. K03 no detecta
# nada nuevo; deja de esconderlo.
GAP_STATUS_NO_DATA = "no_data"
GAP_STATUS_CLEAN = "clean"
GAP_STATUS_DECLARED = "declared"
GAP_STATUS_UNDECLARED = "undeclared"
# Tope de la comprobacion bucket a bucket. Con los limites de los endpoints la ventana
# mas larga son 3000 buckets; si alguna vez sale de aqui es que una fila trae un bucket
# absurdo, y entonces se devuelven las cuentas sin el detalle en vez de barrer un millon
# de instantes.
MAX_BUCKET_SWEEP = 20000


async def declared_series_response(
    conn: asyncpg.Connection,
    rows: list[dict[str, Any]],
    *,
    interval: str,
    bucket: timedelta,
    feed: str,
    exchanges: tuple[str, ...],
    market: str,
    symbol: str,
    gap_symbol: str | None = None,
) -> dict[str, Any]:
    """El sobre de una serie: las filas, la cobertura de su ventana y sus huecos.

    ``gap_symbol`` es la identidad con la que se apunto el hueco cuando no coincide con
    el simbolo pedido: las series de spot se guardan con el simbolo de websocket.
    """
    identidad = gap_symbol or symbol
    starts = sorted(
        row["bucket"].astimezone(UTC) for row in rows if isinstance(row.get("bucket"), datetime)
    )
    if not starts:
        return {
            "symbol": symbol,
            "interval": interval,
            "rows": rows,
            "coverage": {"served_window": None},
            "data_gaps": {
                "feed": feed,
                "exchanges": list(exchanges),
                "market": market,
                "symbol": identidad,
                "window_start": None,
                "window_end": None,
                "status": GAP_STATUS_NO_DATA,
                "declared": [],
                "undeclared_buckets": None,
            },
        }
    window_start, window_end = starts[0], starts[-1] + bucket
    esperados = expected_buckets(window_start, window_end, bucket)
    declared = await declared_gap_windows(
        conn,
        feed=feed,
        exchanges=exchanges,
        market=market,
        symbol=identidad,
        start=window_start,
        end=window_end,
    )
    ventanas = [
        (datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"]))
        for item in declared
    ]
    presentes = set(starts)
    undeclared: int | None = 0
    if esperados > MAX_BUCKET_SWEEP:
        undeclared = None
    else:
        instante = window_start
        while instante < window_end:
            fin = instante + bucket
            if instante not in presentes and not any(
                inicio < fin and final > instante for inicio, final in ventanas
            ):
                undeclared += 1
            instante = fin
    if undeclared:
        # Faltan buckets que NADIE apunto. Es el caso de /api/whale/delta: spot_trades_agg
        # pierde minutos y no hay detector que los escriba en data_gap, asi que "no hay
        # huecos declarados" no significa "no falta nada" y aqui se dice cual de las dos.
        status = GAP_STATUS_UNDECLARED
    elif declared:
        status = GAP_STATUS_DECLARED
    else:
        status = GAP_STATUS_CLEAN
    return {
        "symbol": symbol,
        "interval": interval,
        "rows": rows,
        "coverage": {
            "served_window": coverage_entry(
                window_start, window_end, sources=((feed, esperados, len(starts)),)
            )
        },
        "data_gaps": {
            "feed": feed,
            "exchanges": list(exchanges),
            "market": market,
            "symbol": identidad,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "status": status,
            "declared": declared,
            "undeclared_buckets": undeclared,
        },
    }


def _session_window(row: dict[str, Any]) -> tuple[datetime, datetime] | None:
    """La ventana REAL de una fila de /api/daily: la sesion de Nueva York que agrego.

    session_bounds la define de 09:30 a 09:30 ET, asi que no empieza a medianoche y no
    siempre mide 24 h. La fila puede traer session_date como date o como str segun por
    donde haya pasado; si no se puede resolver, se devuelve None y esa fila no se
    enmascara, que es preferible a enmascarar una ventana inventada.
    """
    valor = row.get("session_date")
    if isinstance(valor, str):
        try:
            valor = date.fromisoformat(valor)
        except ValueError:
            return None
    if not isinstance(valor, date) or isinstance(valor, datetime):
        return None
    return session_bounds(valor)


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
    conn: asyncpg.Connection,
    symbol: str,
    days: int,
    through_session_date: date | None = None,
) -> dict[str, Any]:
    rows = await conn.fetch(
        """
        WITH spot_hist AS (
          SELECT session_date, percent_rank() OVER (ORDER BY cvd_spot_usd) * 100 AS pct_spot
          FROM daily_session_agg
          WHERE symbol=$1 AND cvd_spot_usd IS NOT NULL
            AND ($3::date IS NULL OR session_date <= $3)
        ), diff_hist AS (
          SELECT session_date, percent_rank() OVER (ORDER BY cvd_diff_usd) * 100 AS pct_diff
          FROM daily_session_agg
          WHERE symbol=$1 AND cvd_diff_usd IS NOT NULL
            AND ($3::date IS NULL OR session_date <= $3)
        ), selected AS (
          SELECT * FROM daily_session_agg
          WHERE symbol=$1 AND ($3::date IS NULL OR session_date <= $3)
          ORDER BY session_date DESC LIMIT $2
        ), segmented AS (
          SELECT selected.*,
                 SUM(CASE WHEN cvd_spot_usd IS NULL THEN 1 ELSE 0 END)
                   OVER (ORDER BY session_date) AS spot_gap_group,
                 SUM(CASE WHEN cvd_diff_usd IS NULL THEN 1 ELSE 0 END)
                   OVER (ORDER BY session_date) AS diff_gap_group
          FROM selected
        )
        SELECT s.session_date,s.symbol,s.cvd_spot_usd,s.cvd_fut_usd,s.cvd_diff_usd,
               s.cvd_fut_2v_usd,s.cvd_diff_2v_usd,s.cvd_fut_2v_minutes,
               s.session_coverage_version,s.session_expected_minutes,
               s.futures_ohlcv_minutes,s.spot_2v_minutes,s.session_expected_5m_samples,
               s.oi_5m_samples,s.funding_5m_samples,
               s.liquidation_coverage_version,s.liquidation_observed_at,
               s.liquidation_source_start_at,s.liquidation_source_cutoff_at,
               s.created_at,s.updated_at,
               s.inst_delta_usd,s.price_open,s.price_high,s.price_low,s.price_close,s.price_chg_pct,
               s.oi_open,s.oi_close,s.oi_chg_usd,s.fr_avg,
               s.volume_usd,s.long_liq_usd,s.short_liq_usd,
               CASE WHEN s.cvd_diff_usd IS NULL THEN NULL
                    ELSE SUM(s.cvd_diff_usd) OVER (
                      PARTITION BY s.diff_gap_group ORDER BY s.session_date) END AS cumulative_diff,
               CASE WHEN s.cvd_spot_usd IS NULL THEN NULL
                    ELSE SUM(s.cvd_spot_usd) OVER (
                      PARTITION BY s.spot_gap_group ORDER BY s.session_date) END AS cumulative_spot,
               round(dh.pct_diff::numeric,0)::float8 AS cvd_diff_percentile,
               round(sh.pct_spot::numeric,0)::float8 AS cvd_spot_percentile,
               CASE
                 WHEN s.cvd_spot_usd IS NULL OR s.cvd_fut_usd IS NULL THEN 'sin_dato'
                 WHEN s.cvd_spot_usd = 0 OR s.cvd_fut_usd = 0 THEN 'neutral'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0 THEN 'ambos_compran'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0 THEN 'ambos_venden'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd < 0 THEN 'spot_compra_futuros_venden'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd > 0 THEN 'spot_vende_futuros_compran'
                 ELSE 'neutral'
               END AS flow_direction,
               CASE
                 WHEN s.cvd_spot_usd IS NULL OR s.cvd_fut_usd IS NULL THEN 'sin_dato'
                 WHEN s.cvd_spot_usd = 0 OR s.cvd_fut_usd = 0 THEN 'neutral'
                 WHEN s.price_chg_pct IS NULL THEN 'sin_dato'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0
                      AND s.price_chg_pct >= 0 THEN 'venta_sin_caida'
                 WHEN s.cvd_spot_usd < 0 AND s.cvd_fut_usd < 0 THEN 'venta_con_caida'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0
                      AND s.price_chg_pct <= 0 THEN 'compra_sin_subida'
                 WHEN s.cvd_spot_usd > 0 AND s.cvd_fut_usd > 0 THEN 'compra_con_subida'
                 WHEN s.cvd_spot_usd * s.cvd_fut_usd < 0 THEN 'flujo_dividido'
                 ELSE 'sin_dato'
               END AS price_response
        FROM segmented s
        LEFT JOIN spot_hist sh USING (session_date)
        LEFT JOIN diff_hist dh USING (session_date)
        ORDER BY s.session_date
        """,
        symbol, days, through_session_date,
    )
    values = records(rows)
    streak = 0
    for row in reversed(values):
        spot = as_float(row.get("cvd_spot_usd"))
        if spot is None or spot == 0:
            break
        sign = 1 if spot > 0 else -1
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
        "through_session_date": (
            str(through_session_date) if through_session_date is not None else None
        ),
        "projection_latest_session_date": (
            str(values[-1]["session_date"]) if values else None
        ),
        "temporal_semantics": "mutable_current_projection",
        "knowledge_time_replay": False,
        "quick_read": daily_flow_read(values),
        "sources": DAILY_SOURCES,
        "coverage_note": (
            "session_coverage_version=NULL significa legacy/unverified. En v1/v2 cada pata densa "
            "se publica solo con >=95% de sus muestras esperadas para la duracion DST real; "
            "NULL no significa cero. liquidation_coverage_version=NULL significa que una suma "
            "de liquidaciones no es publicable como total de sesion."
        ),
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
) -> dict[str, Any]:
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
        result = records(rows)
        # Un bucket con hueco declarado no puede seguir devolviendo precios como si
        # nada: sample_count y coverage_pct son material para ADIVINAR la cobertura,
        # y adivinar es justo lo que el panel no debe tener que hacer. Aqui la vela
        # entera se pone a null, que es una afirmacion y no una pista.
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
            value_keys=("open", "high", "low", "close", "volume_usd"),
        )
        return await declared_series_response(
            conn,
            result,
            interval=interval,
            bucket=bucket,
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
        )


@app.get("/api/cvd")
async def cvd(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> dict[str, Any]:
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
        return await declared_series_response(
            conn,
            result,
            interval=interval,
            bucket=bucket,
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
        )


@app.get("/api/cvd/spot")
async def cvd_spot(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> dict[str, Any]:
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
              WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
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
        return await declared_series_response(
            conn,
            result,
            interval=interval,
            bucket=bucket,
            feed="spot_trades",
            exchanges=("binance", "bybit", "combined"),
            market="spot",
            symbol=selected,
            gap_symbol=ws_symbol,
        )


@app.get("/api/cvd/divergence")
async def cvd_divergence(
    symbol: str,
    interval: str = "5min",
    limit: Annotated[int, Query(ge=10, le=3000)] = 576,
) -> dict[str, Any]:
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
                 WHERE symbol=$2 AND exchange='combined' AND venue_count=2 AND interval='1min')
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
              WHERE symbol=$2 AND exchange='combined' AND venue_count=2 AND interval='1min'
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
        # K43 · esta ruta servia un ARRAY PELADO: no tenia donde declarar su ventana, que es
        # justo lo que la familia SERIE promete. Ahora va en sobre. La cobertura lleva las DOS
        # patas por separado porque la serie es un JOIN de futuros y contado: un bucket falta
        # si falta en CUALQUIERA de los dos, y con una sola cifra no se sabria cual fallo.
        # Los observados se cuentan contra las tablas FUENTE y no contra las filas servidas:
        # las filas ya vienen enmascaradas por el hueco declarado, o sea que contarlas diria
        # que esta todo mientras se pinta un null.
        cobertura = None
        if result:
            ventana_ini = result[0]["bucket"]
            ventana_fin = result[-1]["bucket"] + bucket
            esperados = expected_buckets(ventana_ini, ventana_fin, bucket)
            patas = await conn.fetchrow(
                """
                SELECT (SELECT count(DISTINCT date_bin($3::interval, ts, '1970-01-01'::timestamptz))
                          FROM ohlcv WHERE symbol=$1 AND interval='1min'
                           AND ts >= $4 AND ts < $5) AS fut,
                       -- OJO al repetir esta consulta a mano: el simbolo de la pata de
                       -- contado es el de websocket ('BTC'), no el de derivados
                       -- ('BTCUSDT_PERP.A'). Con el de derivados devuelve 0 y la pata
                       -- parece muerta cuando esta sana.
                       (SELECT count(DISTINCT date_bin($3::interval, ts, '1970-01-01'::timestamptz))
                          FROM spot_trades_agg
                         WHERE symbol=$2 AND exchange='combined' AND venue_count=2
                           AND interval='1min' AND ts >= $4 AND ts < $5) AS spot
                """,
                selected,
                ws_symbol,
                bucket,
                ventana_ini,
                ventana_fin,
            )
            cobertura = coverage_entry(
                ventana_ini,
                ventana_fin,
                sources=(
                    ("ohlcv_1min", esperados, int(patas["fut"])),
                    ("spot_trades", esperados, int(patas["spot"])),
                ),
            )
    return {
        "symbol": selected,
        "interval": interval,
        "rows": result,
        "coverage": {"served_window": cobertura, "status": None if result else "no_data"},
    }


@app.get("/api/oi")
async def oi(
    symbol: str,
    interval: str = "15min",
    limit: Annotated[int, Query(ge=10, le=2000)] = 384,
) -> dict[str, Any]:
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
        result = records(rows)
        # open_interest sale de la fuente binance (upsert_ohlc_metric con la clave
        # "oi"); la de bybit va a su propia tabla y no la sirve este endpoint, asi
        # que enmascarar por bybit aqui bloquearia por un hueco que no afecta al dato
        # que se esta devolviendo.
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="open_interest_5min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
            value_keys=("oi",),
        )
        return await declared_series_response(
            conn,
            result,
            interval=interval,
            bucket=bucket,
            feed="open_interest_5min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
        )


@app.get("/api/liquidations")
async def liquidation_series(
    symbol: str,
    interval: str = "1hour",
    limit: Annotated[int, Query(ge=10, le=1000)] = 336,
) -> dict[str, Any]:
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
        result = records(rows)
        # Las liquidaciones son un flujo de EVENTOS, y su hueco se apunta como
        # event_stream desde scalp_collector.safe_liq_put (queue_full) en binance y
        # bybit. Una suma a la que le falta un evento no es una suma menor: es una
        # suma que no se sabe. Los dos exchanges cuentan porque el endpoint suma los
        # dos, asi que perder uno ya invalida el bucket.
        await mask_gapped_series_rows(
            conn,
            result,
            bucket=bucket,
            feed="liquidations",
            exchanges=("binance", "bybit"),
            market="perpetual",
            symbol=selected,
            value_keys=("long_liq", "short_liq"),
        )
        return await declared_series_response(
            conn,
            result,
            interval=interval,
            bucket=bucket,
            feed="liquidations",
            exchanges=("binance", "bybit"),
            market="perpetual",
            symbol=selected,
        )


@app.get("/api/whale/delta")
async def whale_delta(
    symbol: str,
    interval: str = "15min",
    limit: Annotated[int, Query(ge=10, le=2000)] = 384,
) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    ws_symbol = WS_SYMBOL_MAP[selected]
    bucket = historical_interval_value(interval)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH grouped AS (
              SELECT date_bin($2::interval, ts, '1970-01-01'::timestamptz) AS bucket,
                     SUM(inst_buy_usd-inst_sell_usd) AS whale_delta,
                     -- K52: el minuto que contiene un arranque del colector se escribe
                     -- CORTO. Sin esto la fila es indistinguible de una completa y quien
                     -- lee el delta no puede saber que le faltan segundos de mercado.
                     MIN(covered_seconds) AS covered_seconds_min,
                     count(*) FILTER (WHERE covered_seconds < 60) AS short_minutes,
                     -- K52b: y los NULOS hay que contarlos APARTE. Un filtro
                     -- covered_seconds < 60 no los satisface, asi que sin esta linea un
                     -- bucket de legado salia covered_seconds_min=null short_minutes=0,
                     -- IDENTICO a uno completo de verdad. "No falta nada" y "no lo se"
                     -- no pueden ser la misma respuesta: es la regla de K03 aplicada a
                     -- una columna nueva, y la incumplio el codigo que la anadio.
                     count(*) FILTER (WHERE covered_seconds IS NULL) AS unknown_minutes,
                     -- K52c: las tres cuentas de arriba solo saben de minutos PRESENTES.
                     -- El minuto que no llega a EXISTIR como 'combined' -un arranque a
                     -- las 05:20:58 deja a bybit sin operar en el resto del minuto, y
                     -- ws_collector.py:288 exige los dos venues para emitirlo- no suma en
                     -- ninguna de las tres, y el bucket sale IDENTICO a uno completo.
                     -- count(*) es exacto: la PK (symbol,exchange,interval,ts) hace que
                     -- cada minuto aparezca una sola vez bajo este WHERE.
                     count(*) AS minutes_present
              FROM spot_trades_agg
              WHERE symbol=$1 AND exchange='combined' AND venue_count=2 AND interval='1min'
              GROUP BY 1 ORDER BY 1 DESC LIMIT $3
            ) SELECT * FROM grouped ORDER BY bucket
            """,
            ws_symbol,
            bucket,
            limit,
        )
        # LA MARCA NO ES UN FACTOR DE ESCALA, y quien la use para "reparar" el volumen se
        # pasa. Medido sobre los 21 arranques del 2026-08-26 con bucket presente: la
        # fraccion DECLARADA -covered_seconds/60- tiene mediana 0.367 y la fraccion de
        # VOLUMEN observada contra los vecinos, 0.182; la razon entre las dos es 0.452 y
        # 17 de 21 quedan por debajo de lo declarado. Los primeros segundos tras
        # reconectar no son productivos. covered_seconds dice QUE falta, no CUANTO.
        #
        # Aqui NO se enmascara -y es deliberado-: spot_trades_agg no tiene detector que
        # escriba sus huecos en data_gap (COLA.md), asi que no hay identidad de hueco que
        # consultar y llamar a mask_gapped_series_rows seria una llamada hueca. Pero la
        # cobertura SI se puede medir contra la cadencia, y por eso este endpoint es el que
        # sale con status "undeclared": faltan buckets y nadie los ha apuntado. Es la
        # diferencia entre "no falta nada" y "no lo estamos mirando".
        return await declared_series_response(
            conn,
            records(rows),
            interval=interval,
            bucket=bucket,
            feed="spot_trades",
            exchanges=("binance", "bybit", "combined"),
            market="spot",
            symbol=selected,
            gap_symbol=ws_symbol,
        )


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
        as_of = await resolve_matrix_as_of(conn)
        return await delta_matrix(conn, selected, windows, as_of)


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
        as_of = await resolve_matrix_as_of(conn)
        trend = await trend_matrix(conn, selected, as_of)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS, as_of)
        ctx = await scalp_context(conn, selected, as_of)
        barriers = await price_barriers(conn, selected)
        structure = await structure_detail(conn, selected, as_of)
        observ_bundle = await setup_confirmation_bundle(conn, selected, profile)
    view = profile_view(trend, matrix, profile)
    scalp = compute_scalp_summary(ctx)
    return {
        "symbol": selected,
        "as_of": as_of.isoformat(),
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
    """Evaluacion de Mesa con un cutoff de tiempo de evento compartido.

    La Mesa pedia `/api/trend-matrix`, `/api/profile`, `/api/hypothesis` y
    `/api/dashboard/state` por separado. Cada uno volvia a calcular `trend_matrix`,
    `delta_matrix` y `scalp_context` con su propio `now()`, asi que dos paneles contiguos
    podian estar describiendo instantes distintos y contradecirse sin que se viera por que.

    Aqui los componentes compartidos se calculan UNA vez, en una sola conexion, y trend y
    delta reciben el mismo `as_of` de PostgreSQL. Esto alinea el cutoff de tiempo de evento;
    varias sentencias autocommit NO constituyen un snapshot MVCC atomico. Los endpoints
    originales siguen existiendo: otras vistas los usan y no todas necesitan el paquete completo.
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
    async with app.state.pool.acquire() as conn:
        as_of = await resolve_matrix_as_of(conn)
        trend = await trend_matrix(conn, selected, as_of)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS, as_of)
        ctx = await scalp_context(conn, selected, as_of)
        quality = await data_quality(conn, selected)
        barriers = await price_barriers(conn, selected)
        structure = await structure_detail(conn, selected, as_of)
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
            "`as_of` es el cutoff de tiempo de evento compartido por trend y delta, no un "
            "snapshot MVCC atomico de las sentencias autocommit. Los estados parciales NO se "
            "ocultan: se declaran en `partial` y en el propio bloque."
        ),
    }


@app.get("/api/quality/feeds")
async def quality_feeds(symbol: str) -> dict[str, Any]:
    """Calidad de los FEEDS de mercado y de cada METRICA publicada.

    La pestana de calidad mostraba la salud de los procesos internos bajo el titulo "Fuentes
    de datos". Son cosas distintas: un colector vivo puede estar alimentando un feed al que
    le falta un venue, y un feed completo puede sostener una metrica cuya ventana esta a
    medias. Los tres niveles -servicios, feeds y metricas- los arma feed_quality_view, que
    vive en scalp_logic desde el 2026-08-26 para que /api/ai/context sirva LA MISMA
    respuesta: api.py importa ai_context, asi que al reves seria un ciclo.
    """
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await feed_quality_view(conn, selected)


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
        as_of = await resolve_matrix_as_of(conn)
        trend = await trend_matrix(conn, selected, as_of)
        matrix = await delta_matrix(conn, selected, PROFILE_WINDOWS, as_of)
    return {
        "symbol": selected,
        "as_of": as_of.isoformat(),
        **profile_view(trend, matrix, profile),
    }


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
    # Las dos consultas y los tres estados viven en ai_context y los comparte con la
    # seccion orderbook de la foto: si se separan, la foto vuelve a servir libro viejo
    # sin declararlo y K13 se pierde para quien beba de ella.
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(ORDERBOOK_FRESCAS_SQL, selected, ORDERBOOK_MAX_AGE_SECONDS)
        as_of = await conn.fetchval(ORDERBOOK_EDAD_SQL, selected)
    return {
        "symbol": selected,
        "rows": records(rows),
        "freshness": orderbook_freshness(as_of, bool(rows)),
    }


@app.get("/api/scalp/absorption")
async def scalp_absorption(symbol: str) -> list[dict[str, Any]]:
    # El SQL vive en scalp_logic desde el 2026-08-26 para que /api/ai/context pueda servir
    # LA MISMA respuesta: api.py importa ai_context, asi que al reves seria un ciclo.
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await scalp_absorption_read(conn, selected)


@app.get("/api/scalp/liquidations")
async def scalp_liquidations(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await scalp_liquidations_read(conn, selected)


@app.get("/api/scalp/alerts")
async def scalp_alerts(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        as_of = await resolve_matrix_as_of(conn)
        ctx = await scalp_context(conn, selected, as_of)
        impact = await market_impact(conn, selected, as_of)
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
        as_of = await resolve_matrix_as_of(conn)
        return await cvd_matrix(conn, selected, as_of)


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
    logic_version: Annotated[str, Query(min_length=1, max_length=80)] = (
        DAILY_VERDICT_LOGIC_VERSION
    ),
) -> dict[str, Any]:
    """First immutable observed verdict snapshot for each captured session.

    The snapshot is evidence of what the system emitted and when it became knowable; it is
    not represented as an exact reconstruction of the session-close state.
    """
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH v AS (
              SELECT * FROM daily_verdict_snapshot
              WHERE symbol=$1 AND logic_version=$2
              ORDER BY session_date DESC LIMIT $3
            )
            SELECT v.session_date,v.swing_bias,v.swing_score,v.swing_conviction,
                   v.long_share_pct,v.regime_score,v.regime_label,
                   v.setup_id,v.setup_name,v.setup_state,v.setup_confidence,
                   v.daily_streak,
                   v.session_price_close,v.session_price_close AS price_close,
                   v.observed_at,v.session_end_at,v.snapshot_version,v.logic_version,
                   v.reference_price,v.reference_price_at,v.metrics_snapshot_ts,
                   v.session_coverage_version,v.regime_logic_version,
                   d7.return_pct AS fwd_return_7s_pct,
                   d14.return_pct AS fwd_return_14s_pct
            FROM v
            LEFT JOIN daily_verdict_outcome d7
              ON d7.snapshot_id=v.snapshot_id
             AND d7.outcome_version=$4
             AND d7.horizon_sessions=7
            LEFT JOIN daily_verdict_outcome d14
              ON d14.snapshot_id=v.snapshot_id
             AND d14.outcome_version=$4
             AND d14.horizon_sessions=14
            ORDER BY v.session_date DESC
            """,
            selected,
            logic_version,
            limit,
            DAILY_VERDICT_OUTCOME_VERSION,
        )
    filas = records(rows)
    # K43 · es una SERIE y su ventana es su coverage. Declaraba las filas y una nota en prosa,
    # o sea QUE se sirvio pero no cuanto falta: medido el 2026-08-26, entre la primera y la
    # ultima sesion servidas hay 13 fechas y solo 12 filas, y no habia forma de verlo desde la
    # respuesta. La ventana son las sesiones SERVIDAS -de la primera a la ultima- y no las
    # `limit` pedidas: pedir 90 cuando el ledger tiene 12 no es un hueco, es un ledger corto, y
    # medirlo contra lo pedido daria incompletos falsos (el mismo motivo de api.py:1990).
    # Los bordes salen de session_bounds y no de medianoche UTC: la sesion va de 09:30 a 09:30
    # de Nueva York, asi que una ventana de dias UTC describiria otra cosa.
    # AVISO A QUIEN AUDITE ESTA CIFRA: por dia NATURAL sale lo contrario. Medido el
    # 2026-08-26, la unica sesion ausente de las 13 es la etiquetada 2026-08-15, que va de
    # 08-14 13:30Z a 08-15 13:30Z y contiene el hueco de ohlcv_1min de 08-14 16:47 a 18:13:
    # tiene 1354 velas de 1440, mientras las cuatro sesiones vecinas tienen 1440 de 1440 y
    # las cuatro SI tienen veredicto. Correspondencia 1 a 1: la unica sesion con velas
    # ausentes es la unica sin veredicto, o sea hueco de DATO y no de calculo, y el motor
    # hizo bien en no publicarla. Agrupando por dia natural el 08-15 tiene sus 1440 velas y
    # se concluye justo lo contrario. El borde esta a las 13:30Z. Y los esperados se
    # cuentan por FECHA de sesion, no dividiendo la ventana entre 24 h, porque con el cambio de
    # horario una sesion no siempre dura 24 h y la division truncaria una sesion entera.
    cobertura = None
    ventanas = [v for v in (_session_window(fila) for fila in filas) if v]
    if ventanas:
        ini, fin = min(v[0] for v in ventanas), max(v[1] for v in ventanas)
        fechas = {str(fila.get("session_date"))[:10] for fila in filas}
        esperadas = (date.fromisoformat(max(fechas)) - date.fromisoformat(min(fechas))).days + 1
        cobertura = coverage_entry(
            ini, fin, sources=(("daily_verdict_snapshot", esperadas, len(fechas)),)
        )
    return {
        "symbol": selected,
        "logic_version": logic_version,
        "rows": filas,
        "coverage": {"served_window": cobertura},
        "note": (
            "snapshot = primera emision inmutable capturada para la sesion; observed_at = "
            "momento en que fue conocible; reference_price_at = anchor de fwd_return_*_pct. "
            "Los retornos usan exclusivamente daily_verdict_outcome inmutable en la fecha "
            "calendario exacta +7/+14; un target no medido deja el retorno null."
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
    through_session_date: date | None = None,
    as_of: Annotated[date | None, Query(deprecated=True)] = None,
) -> dict[str, Any]:
    if as_of is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "PIT replay is not supported by /api/daily; use "
                "through_session_date to limit the current mutable projection"
            ),
        )
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        result = await daily_data(conn, selected, days, through_session_date)
        # La sesion NO es un dia UTC: va de 09:30 a 09:30 de Nueva York
        # (app/metrics.py:31 session_bounds), y por los cambios de horario ni siquiera
        # dura siempre 24 h. Por eso la ventana se pide FILA A FILA en vez de derivarla
        # de un tamano fijo: con medianoche UTC se enmascararia el dia equivocado, que
        # es peor que no enmascarar -pondria a null un dia sano y dejaria intacto el
        # roto-.
        # Solo se anulan las claves que dependen del ohlcv de FUTUROS. Las de spot
        # (cvd_spot_usd, cumulative_spot, inst_delta_usd) y las de otros feeds (oi_*,
        # fr_avg, *_liq_usd) tienen su propia identidad de hueco y no las invalida esto.
        await mask_gapped_series_rows(
            conn,
            result["rows"],
            bucket=timedelta(days=1),  # inerte: manda row_window
            feed="ohlcv_1min",
            exchanges=("binance",),
            market="perpetual",
            symbol=selected,
            value_keys=(
                "price_open", "price_high", "price_low", "price_close",
                "price_chg_pct", "price_response", "volume_usd",
                "cvd_fut_usd", "cvd_fut_2v_usd",
                "cvd_diff_usd", "cvd_diff_2v_usd", "cvd_diff_percentile",
            ),
            cumulative_keys=("cumulative_diff",),
            row_window=_session_window,
        )
        # El hueco declarado, sobre la union de las sesiones servidas. Aqui NO se anade
        # coverage por bucket: la fila de /api/daily ya trae futures_ohlcv_minutes contra
        # session_expected_minutes, que es su propia cuenta de cobertura y esta medida
        # sobre la sesion de verdad. Inventar un "expected de sesiones" a partir de days
        # daria falsos incompletos cada vez que el historico es mas corto que lo pedido.
        ventanas = [v for v in (_session_window(row) for row in result["rows"]) if v]
        inicio = min((v[0] for v in ventanas), default=None)
        fin = max((v[1] for v in ventanas), default=None)
        declarados = (
            await declared_gap_windows(
                conn,
                feed="ohlcv_1min",
                exchanges=("binance",),
                market="perpetual",
                symbol=selected,
                start=inicio,
                end=fin,
            )
            if inicio and fin
            else []
        )
        result["data_gaps"] = {
            "feed": "ohlcv_1min",
            "exchanges": ["binance"],
            "market": "perpetual",
            "symbol": selected,
            "window_start": inicio.astimezone(UTC).isoformat() if inicio else None,
            "window_end": fin.astimezone(UTC).isoformat() if fin else None,
            "status": (
                GAP_STATUS_NO_DATA
                if not ventanas
                else GAP_STATUS_DECLARED
                if declarados
                else GAP_STATUS_CLEAN
            ),
            "declared": declarados,
            "undeclared_buckets": None,
        }
    return result


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


def _utc_iso(value: datetime | None) -> str | None:
    """El ledger no filtra la zona horaria del servidor: siempre UTC y siempre con Z."""
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


LEDGER_MAX_WINDOW = timedelta(hours=24)

# Las columnas del ledger se nombran una a una a proposito. Un SELECT * ata la
# respuesta publica a lo que schema.sql tenga ese dia: una columna nueva se filtraria
# sola y una renombrada romperia al cliente sin que nada lo dijera.
LEDGER_COLUMNS = """
    observation_id, observed_at, observed_minute, symbol, signal_family,
    is_periodic, is_transition, logic_version, evidence_version, sampling_version,
    decision_status, direction, actionable, state, confidence, reason,
    reference_price, reference_price_source, reference_price_at,
    long_score, short_score, evidence_coverage_pct, metrics_snapshot_ts,
    regime_score, regime_label, regime_logic_version
"""
LEDGER_TIMESTAMPS = (
    "observed_at",
    "observed_minute",
    "reference_price_at",
    "metrics_snapshot_ts",
)


def rechaza_parametros_desconocidos(request: Request, conocidos: tuple[str, ...]) -> None:
    """Un filtro que nadie reconoce no puede parecer un filtro que se honra.

    FastAPI ignora en silencio lo que no declara, asi que ?hour=15 se cae por el desague
    y la ruta devuelve OTRA ventana sin decir nada. Lo unico que salvaba al llamante era
    leerse el since/until que la respuesta declara. Aqui se le dice.
    """
    sobran = sorted(set(request.query_params) - set(conocidos))
    if sobran:
        raise HTTPException(
            status_code=422,
            detail=f"parametros no reconocidos: {', '.join(sobran)}. Admitidos: {', '.join(conocidos)}",
        )


@app.get("/api/signals/ledger")
async def signals_ledger(
    request: Request,
    symbol: str,
    since: str | None = None,
    until: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict[str, Any]:
    """signal_observation, el ledger de senales, servido tal cual se escribio.

    Una observacion es una fila y se devuelven todas las de la ventana. Lo que la base
    guarda como NULL se sirve como null: la clave no se borra nunca, porque "no lo se"
    y "esta metrica no existe" no pueden ser la misma respuesta.
    """
    rechaza_parametros_desconocidos(request, ("symbol", "since", "until", "limit"))
    selected = validate_symbol(symbol)
    try:
        end = datetime.fromisoformat(until) if until else datetime.now(UTC)
        start = (
            datetime.fromisoformat(since) if since else end - timedelta(hours=1)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"since/until no son ISO-8601: {exc}") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="since/until necesitan zona horaria explicita")
    if end <= start:
        raise HTTPException(status_code=422, detail="until tiene que ser posterior a since")
    if end - start > LEDGER_MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail=f"la ventana maxima es {int(LEDGER_MAX_WINDOW.total_seconds() // 3600)} h",
        )

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {LEDGER_COLUMNS}
            FROM signal_observation
            WHERE symbol=$1 AND observed_at >= $2 AND observed_at < $3
            ORDER BY observed_at, observation_id
            LIMIT $4
            """,
            selected,
            start,
            end,
            limit + 1,
        )
    # Se pide una fila de mas: es la unica forma de saber si el LIMIT corto sin
    # volver a contar. Un ledger que corta en silencio miente sobre la ventana.
    truncated = len(rows) > limit
    observations = records(rows[:limit])
    for observation in observations:
        for column in LEDGER_TIMESTAMPS:
            observation[column] = _utc_iso(observation[column])

    return {
        "symbol": selected,
        "since": _utc_iso(start),
        "until": _utc_iso(end),
        "limit": limit,
        "count": len(observations),
        "truncated": truncated,
        "observations": observations,
    }


OUTCOME_COLUMNS = """
    so.outcome_id, so.observation_id, o.symbol, o.direction, o.observed_at,
    so.horizon_minutes, so.window_start, so.window_end, so.due_at,
    so.status, so.outcome_version, so.attempts, so.bars_expected, so.bars_found,
    so.finalized_at, so.final_reason,
    so.entry_reference_price, so.end_price, so.max_high, so.min_low,
    so.market_return_pct, so.up_excursion_pct, so.down_excursion_pct,
    so.directional_return_pct, so.mfe_pct, so.mae_pct, so.created_at
"""
OUTCOME_TIMESTAMPS = (
    "observed_at",
    "window_start",
    "window_end",
    "due_at",
    "finalized_at",
    "created_at",
)
HORIZONS = (1, 3, 5, 15, 30, 60, 120, 240)


@app.get("/api/signals/outcomes")
async def signals_outcomes(
    request: Request,
    symbol: str,
    since: str | None = None,
    until: str | None = None,
    horizon: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict[str, Any]:
    """signal_outcome: que paso a 1, 3, 5, 15, 30, 60, 120 y 240 minutos de cada senal.

    La ventana filtra por window_start, que es lo que define el periodo del resultado, y
    no por observed_at: dos observaciones del mismo minuto tienen ventanas distintas
    segun el horizonte. La direccion viaja en cada fila porque sin ella las cifras
    direccionales -directional_return_pct, mfe_pct, mae_pct- no se pueden ni leer ni
    recalcular. Lo que la base guarda como NULL se sirve como null.
    """
    rechaza_parametros_desconocidos(
        request, ("symbol", "since", "until", "horizon", "limit")
    )
    selected = validate_symbol(symbol)
    if horizon is not None and horizon not in HORIZONS:
        raise HTTPException(
            status_code=422,
            detail=f"horizon tiene que ser uno de {list(HORIZONS)}",
        )
    try:
        end = datetime.fromisoformat(until) if until else datetime.now(UTC)
        start = datetime.fromisoformat(since) if since else end - timedelta(hours=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"since/until no son ISO-8601: {exc}") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="since/until necesitan zona horaria explicita")
    if end <= start:
        raise HTTPException(status_code=422, detail="until tiene que ser posterior a since")
    if end - start > LEDGER_MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail=f"la ventana maxima es {int(LEDGER_MAX_WINDOW.total_seconds() // 3600)} h",
        )

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {OUTCOME_COLUMNS}
            FROM signal_outcome so
            JOIN signal_observation o USING (observation_id)
            WHERE o.symbol=$1 AND so.window_start >= $2 AND so.window_start < $3
              AND ($4::int IS NULL OR so.horizon_minutes = $4)
            ORDER BY so.window_start, so.observation_id, so.horizon_minutes
            LIMIT $5
            """,
            selected,
            start,
            end,
            horizon,
            limit + 1,
        )
    truncated = len(rows) > limit
    outcomes = records(rows[:limit])
    for outcome in outcomes:
        for column in OUTCOME_TIMESTAMPS:
            outcome[column] = _utc_iso(outcome[column])

    return {
        "symbol": selected,
        "since": _utc_iso(start),
        "until": _utc_iso(end),
        "horizon": horizon,
        "limit": limit,
        "count": len(outcomes),
        "truncated": truncated,
        "outcomes": outcomes,
    }


EXECUTION_COLUMNS = """
    s.execution_snapshot_id, s.observation_id, o.symbol, o.direction, o.observed_at,
    s.snapshot_version, s.exchange, s.captured_at, s.book_ts, s.book_age_seconds,
    s.status, s.reason, s.levels_reported, s.bid_levels_valid, s.ask_levels_valid,
    s.best_bid_px, s.best_ask_px, s.mid_px, s.spread_bps,
    s.bid_depth_usd, s.ask_depth_usd, s.source_book_hash, s.cost_curve, s.created_at
"""
EXECUTION_TIMESTAMPS = ("observed_at", "captured_at", "book_ts", "created_at")


@app.get("/api/signals/execution")
async def signals_execution(
    request: Request,
    symbol: str,
    since: str | None = None,
    until: str | None = None,
    exchange: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict[str, Any]:
    """signal_execution_snapshot: el coste real de ejecutar cada senal.

    La curva de coste viaja entera. Se sirve tal cual la escribio el productor -es un
    jsonb- porque compactarla o resumirla aqui haria imposible recalcularla desde fuera,
    que es lo unico que demuestra que es correcta. Lo que la base guarda como NULL se
    sirve como null; en particular market_cost_bps_vs_mid es null cuando no hubo
    profundidad para llenar, y esa ausencia es informacion, no un hueco.
    """
    rechaza_parametros_desconocidos(
        request, ("symbol", "since", "until", "exchange", "limit")
    )
    selected = validate_symbol(symbol)
    if exchange is not None and exchange not in ("binance", "bybit"):
        raise HTTPException(status_code=422, detail="exchange tiene que ser binance o bybit")
    try:
        end = datetime.fromisoformat(until) if until else datetime.now(UTC)
        start = datetime.fromisoformat(since) if since else end - timedelta(hours=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"since/until no son ISO-8601: {exc}") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="since/until necesitan zona horaria explicita")
    if end <= start:
        raise HTTPException(status_code=422, detail="until tiene que ser posterior a since")
    if end - start > LEDGER_MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail=f"la ventana maxima es {int(LEDGER_MAX_WINDOW.total_seconds() // 3600)} h",
        )

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {EXECUTION_COLUMNS}
            FROM signal_execution_snapshot s
            JOIN signal_observation o USING (observation_id)
            WHERE o.symbol=$1 AND s.captured_at >= $2 AND s.captured_at < $3
              AND ($4::text IS NULL OR s.exchange = $4)
            ORDER BY s.captured_at, s.observation_id, s.exchange
            LIMIT $5
            """,
            selected,
            start,
            end,
            exchange,
            limit + 1,
        )
    truncated = len(rows) > limit
    snapshots = records(rows[:limit])
    for snapshot in snapshots:
        for column in EXECUTION_TIMESTAMPS:
            snapshot[column] = _utc_iso(snapshot[column])
        # asyncpg devuelve el jsonb como texto; el llamante quiere la curva, no su fuente.
        if isinstance(snapshot["cost_curve"], str):
            snapshot["cost_curve"] = json.loads(snapshot["cost_curve"])

    return {
        "symbol": selected,
        "since": _utc_iso(start),
        "until": _utc_iso(end),
        "exchange": exchange,
        "limit": limit,
        "count": len(snapshots),
        "truncated": truncated,
        "snapshots": snapshots,
    }


REPLAY_COLUMNS = """
    fr.frame_id, fr.observation_id, o.symbol, o.observed_at,
    fr.context_version, fr.context_as_of, fr.context_hash,
    o.logic_version, o.evidence_version,
    fr.context, o.evidence, fr.created_at
"""
REPLAY_TIMESTAMPS = ("observed_at", "context_as_of", "created_at")
REPLAY_JSON = ("context", "evidence")


@app.get("/api/signals/replay")
async def signals_replay(
    request: Request,
    symbol: str,
    since: str | None = None,
    until: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    """signal_replay_frame: los insumos congelados con los que se decidio.

    El context viaja ENTERO y como objeto, junto a su context_hash y a la evidence que
    produjo. Resumirlo o recortarlo dejaria la capacidad sin sentido: lo unico que
    demuestra que una decision del pasado es correcta es volver a ejecutar el nucleo
    sobre estos mismos insumos y obtener la misma evidence, y para eso hacen falta
    todos. logic_version viaja porque sin ella el llamante no sabe QUE nucleo aplicar.

    El limite por defecto es mas bajo que en las otras rutas de senales a proposito:
    cada fila arrastra dos JSON completos, no una decena de columnas.
    """
    rechaza_parametros_desconocidos(request, ("symbol", "since", "until", "limit"))
    selected = validate_symbol(symbol)
    try:
        end = datetime.fromisoformat(until) if until else datetime.now(UTC)
        start = datetime.fromisoformat(since) if since else end - timedelta(hours=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"since/until no son ISO-8601: {exc}") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="since/until necesitan zona horaria explicita")
    if end <= start:
        raise HTTPException(status_code=422, detail="until tiene que ser posterior a since")
    if end - start > LEDGER_MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail=f"la ventana maxima es {int(LEDGER_MAX_WINDOW.total_seconds() // 3600)} h",
        )

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {REPLAY_COLUMNS}
            FROM signal_replay_frame fr
            JOIN signal_observation o USING (observation_id)
            WHERE o.symbol=$1 AND fr.context_as_of >= $2 AND fr.context_as_of < $3
            ORDER BY fr.context_as_of, fr.frame_id
            LIMIT $4
            """,
            selected,
            start,
            end,
            limit + 1,
        )
    truncated = len(rows) > limit
    frames = records(rows[:limit])
    for frame in frames:
        for column in REPLAY_TIMESTAMPS:
            frame[column] = _utc_iso(frame[column])
        # asyncpg devuelve el jsonb como texto. Servirlo como cadena obligaria a cada
        # llamante a re-parsearlo, y el hash canonico dejaria de poder recalcularse
        # sobre lo que se sirve, que es justo lo que hace verificable esta ruta.
        for column in REPLAY_JSON:
            if isinstance(frame[column], str):
                frame[column] = json.loads(frame[column])

    return {
        "symbol": selected,
        "since": _utc_iso(start),
        "until": _utc_iso(end),
        "limit": limit,
        "count": len(frames),
        "truncated": truncated,
        "frames": frames,
    }


VISIBILITY_COLUMNS = """
    v.final_visibility_id, v.outcome_id, so.observation_id, o.symbol,
    so.horizon_minutes, v.visibility_version, v.outcome_version,
    v.source_status, v.source_finalized_at, v.verified_visible_at, v.created_at
"""
VISIBILITY_TIMESTAMPS = ("source_finalized_at", "verified_visible_at", "created_at")


@app.get("/api/signals/visibility")
async def signals_visibility(
    request: Request,
    symbol: str,
    since: str | None = None,
    until: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> dict[str, Any]:
    """signal_outcome_final_visibility: la prueba de que un resultado ya era visible.

    Cada fila certifica que el estado final de un signal_outcome estaba escrito y se
    podia leer desde fuera no mas tarde de verified_visible_at. Ese instante NO es el
    commit timestamp de PostgreSQL y no se puede leer como tal: el productor abre una
    transaccion nueva, lee el estado ya comprometido y solo DESPUES pide el reloj, asi
    que es una cota SUPERIOR conservadora (app/signal_visibility.py:20).

    La ventana filtra por verified_visible_at, que es el instante que la capacidad
    afirma, y no por cuando se finalizo el outcome: preguntar "que era demostrablemente
    final a las 19:00" es justo lo que esta tabla contesta.
    """
    rechaza_parametros_desconocidos(
        request, ("symbol", "since", "until", "status", "limit")
    )
    selected = validate_symbol(symbol)
    if status is not None and status not in ("evaluated", "not_evaluable"):
        raise HTTPException(
            status_code=422,
            detail="status tiene que ser evaluated o not_evaluable",
        )
    try:
        end = datetime.fromisoformat(until) if until else datetime.now(UTC)
        start = datetime.fromisoformat(since) if since else end - timedelta(hours=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"since/until no son ISO-8601: {exc}") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(status_code=422, detail="since/until necesitan zona horaria explicita")
    if end <= start:
        raise HTTPException(status_code=422, detail="until tiene que ser posterior a since")
    if end - start > LEDGER_MAX_WINDOW:
        raise HTTPException(
            status_code=422,
            detail=f"la ventana maxima es {int(LEDGER_MAX_WINDOW.total_seconds() // 3600)} h",
        )

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT {VISIBILITY_COLUMNS}
            FROM signal_outcome_final_visibility v
            JOIN signal_outcome so USING (outcome_id)
            JOIN signal_observation o USING (observation_id)
            WHERE o.symbol=$1 AND v.verified_visible_at >= $2 AND v.verified_visible_at < $3
              AND ($4::text IS NULL OR v.source_status = $4)
            ORDER BY v.verified_visible_at, v.final_visibility_id
            LIMIT $5
            """,
            selected,
            start,
            end,
            status,
            limit + 1,
        )
    truncated = len(rows) > limit
    certificates = records(rows[:limit])
    for certificate in certificates:
        for column in VISIBILITY_TIMESTAMPS:
            certificate[column] = _utc_iso(certificate[column])

    return {
        "symbol": selected,
        "since": _utc_iso(start),
        "until": _utc_iso(end),
        "status": status,
        "limit": limit,
        "count": len(certificates),
        "truncated": truncated,
        "certificates": certificates,
    }


@app.get("/api/scalp/basis")
async def scalp_basis(symbol: str) -> dict[str, Any]:
    selected = validate_symbol(symbol)
    async with app.state.pool.acquire() as conn:
        return await scalp_basis_read(conn, selected)


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
                (SELECT last_px FROM futures_trades_realtime WHERE symbol=$1 AND exchange='combined' AND venue_count=2 ORDER BY ts DESC LIMIT 1),
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
    # 'required' dice que servicios tienen que EXISTIR. No dice cuales se vigilan:
    # eso se deriva de pipeline_heartbeat mas abajo, porque un latido que no esta
    # en esta lista es exactamente un colector que puede morir en silencio.
    required = {
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
    # Todo lo que late se vigila; ademas, lo de 'required' tiene que estar.
    thresholds = {
        service: heartbeat_max_age(service, required) for service in by_service
    }
    thresholds.update(required)
    missing_services = sorted(set(required) - set(by_service))
    degraded = bool(required_heartbeat_failures(heartbeats, thresholds))
    latest_by_symbol = {str(row["symbol"]): row for row in latest}
    missing_symbols = sorted(set(SETTINGS.SYMBOLS) - set(latest_by_symbol))
    if missing_symbols or any(float(row["lag_seconds"]) > 180.0 for row in latest):
        degraded = True
    return {
        "status": "degraded" if degraded else "ok",
        # K08 · a que base esta enganchado lo que corre. Se lee UNA vez, al abrir el pool
        # (db.py create_pool) y ANTES de la primera escritura; aqui solo se publica. Sin
        # esto, un despliegue mal apuntado escribe igual y no se distingue de uno bueno.
        # No gatea el status: decir donde estas es una cosa y estar sano es otra.
        "database": db_identity(),
        "missing_services": missing_services,
        "missing_symbols": missing_symbols,
        "governed_services": sorted(thresholds),
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
                    WHERE exchange='combined' AND venue_count=2 AND ts >= now()-interval '30 seconds'
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
                    WHERE exchange='combined' AND venue_count=2 AND ts >= now()-interval '30 seconds'
                    ORDER BY symbol,ts DESC
                    """
                )
                books = await conn.fetch(
                    """
                    SELECT DISTINCT ON (symbol) symbol,ts,spread_bps,imbalance_l5
                    FROM orderbook_snapshot
                    WHERE exchange='combined' AND venue_count=2 AND ts >= now()-interval '30 seconds'
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
