from __future__ import annotations

import asyncio
import json
import logging
import math
import signal
import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.coinalyze import (
    CoinalyzeClient,
    PostgresSlidingWindowRateLimiter,
    validate_rate_budget,
)
from app.config import BYBIT_SYMBOL_MAP, Settings, get_settings
from app.cutoffs import OHLCV_1M_REFRESH_LOOKBACK_SECONDS, ClosedCutoff
from app.data_gaps import CadenceCoverage, reconcile_cadence_coverage
from app.db import (
    INGEST_COMPONENT_MAX_AGES,
    ServiceOwnership,
    ServiceOwnershipLost,
    acquire_service_lock,
    create_pool,
    fenced_transaction,
    heartbeat,
    heartbeat_component,
    monitor_service_lock,
    wait_for_stop_or_lock_loss,
)
from app.external_macro import refresh_external_macro
from app.logging_setup import configure_logging
from app.metrics import compute_and_store_all

LOGGER = logging.getLogger(__name__)

# Shared by both the OHLCV and metrics cycles so snapshot publication is serialized
# process-wide, not just per-cycle. See publish_snapshot() for why this is required.
SNAPSHOT_PUBLISH_LOCK_KEY = "coinanalyze:metrics-snapshot-publish"


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
    if ts < start_ts - tolerance or ts > end_ts:
        raise ValueError("timestamp outside requested window")
    return datetime.fromtimestamp(ts, tz=UTC)


def source_response_buckets(
    payload: dict[str, list[dict[str, Any]]],
    symbol_map: dict[str, str],
    start_ts: int,
    end_ts: int,
) -> dict[str, set[datetime]]:
    """Los buckets que la FUENTE devolvio, antes de que validemos nada.

    No es lo mismo que el `observed` de los upsert_*, que son los que ACEPTAMOS: los
    upsert descartan la fila incoherente y no la apuntan. La diferencia entre los dos
    conjuntos es exactamente la fila que tiramos nosotros, y esa nunca es culpa de la
    fuente. Sin esta distincion, un descarte nuestro se archivaria como "la fuente no
    lo publica", que es la mentira contraria a la que arreglamos.
    """
    devueltos: dict[str, set[datetime]] = {}
    for symbol, row in rows_for(payload, symbol_map):
        try:
            devueltos.setdefault(symbol, set()).add(valid_ts(row["t"], start_ts, end_ts))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    return devueltos


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
    observed: dict[str, set[datetime]] | None = None,
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
            row_ts = valid_ts(row["t"], start_ts, end_ts, tolerance)
            record = (
                row_ts,
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
            if observed is not None:
                observed.setdefault(symbol, set()).add(row_ts)
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


# El unico eje que cambia entre la pasada viva y el barrido de recuperacion. Se elige de
# este diccionario y NUNCA se compone con texto de fuera: la consulta es una sola y por
# tanto la guarda de los cinco minutos es la MISMA para los dos caminos. Ese es el punto
# del diseno y no un detalle de estilo -- dos consultas serian dos guardas, y la segunda
# es la que algun dia se olvida.
_CONFLICTO_5M = {
    # Pasada viva: el bucket en curso cambia segun llegan minutos, asi que se reescribe.
    False: """ON CONFLICT(symbol,interval,ts) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, volume=EXCLUDED.volume,
            buy_volume=EXCLUDED.buy_volume, tx=EXCLUDED.tx, btx=EXCLUDED.btx""",
    # Barrido historico: lo cerrado ya no cambia. Reescribir 31473 filas cada hora con
    # los mismos valores solo produce tuplas muertas y WAL, y el thin pool del nodo no
    # tiene margen para eso (VFree 4.00 MiB el 2026-08-30).
    True: "ON CONFLICT(symbol,interval,ts) DO NOTHING",
}


async def rollup_ohlcv_5m(
    conn: asyncpg.Connection,
    symbols: tuple[str, ...],
    start_ts: int,
    end_ts: int,
    *,
    only_missing: bool = False,
) -> int:
    """Build 5-minute candles locally from stored 1-minute rows, without API quota.

    ``only_missing`` no relaja NADA de la validacion: solo cambia si un bucket que ya
    existe se reescribe o se deja en paz. La exigencia de los cinco minutos vive en el
    HAVING de mas abajo y la comparten los dos caminos.
    """
    count = await conn.fetchval(
        f"""
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
          {_CONFLICTO_5M[only_missing]}
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
    observed: dict[str, set[datetime]] | None = None,
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
            row_ts = valid_ts(row["t"], start_ts, end_ts)
            records.append((row_ts, symbol, "5min", *values))
            if observed is not None:
                observed.setdefault(symbol, set()).add(row_ts)
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
    observed: dict[str, set[datetime]] | None = None,
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
            row_ts = valid_ts(row["t"], start_ts, end_ts)
            records.append((row_ts, symbol, "5min", long_pct, short_pct, ratio))
            if observed is not None:
                observed.setdefault(symbol, set()).add(row_ts)
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


async def publish_snapshot(
    conn: asyncpg.Connection,
    ownership: ServiceOwnership | None,
    symbols: tuple[str, ...],
    *,
    now_utc: datetime | None,
    price_cutoff: datetime | None,
    metrics_cutoff: datetime | None,
) -> None:
    """Serialize metrics_snapshot publication across the OHLCV and metrics cycles.

    Must be called AFTER the caller's own feed-write transaction already committed.
    Without this, two concurrent cycles (A=OHLCV, B=metrics) can interleave so that: A
    starts writing a new closed price but has not committed yet; B starts later, cannot
    see A's uncommitted price under READ COMMITTED, computes a snapshot from the older
    price, and commits first; A then commits its own (correct, newer) snapshot, but if
    that snapshot were written with `now()` its `ts` is fixed at A's transaction BEGIN,
    which was earlier than B's, so ORDER BY ts DESC would surface B's stale snapshot as
    "latest" even though A committed the correct one afterwards.

    This function opens a fresh transaction, takes one exclusive advisory lock shared by
    both cycles (serializing publication process-wide), re-reads already-committed
    market data, and inserts with clock_timestamp() (evaluated at execution, not BEGIN).
    Serialization + a real-time clock together guarantee `ts` ordering matches actual
    publication order. Changing only now() to clock_timestamp() without the lock and the
    fresh transaction would not be enough: a still-open feed-write transaction would
    keep hiding committed data from re-reads until it committed.
    """
    async with fenced_transaction(conn, ownership):
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            SNAPSHOT_PUBLISH_LOCK_KEY,
        )
        await compute_and_store_all(
            conn,
            symbols,
            now_utc=now_utc,
            price_cutoff=price_cutoff,
            metrics_cutoff=metrics_cutoff,
        )


_CADENCE_TABLES = frozenset({
    "ohlcv", "open_interest", "oi_bybit", "funding_rate",
    "predicted_funding_rate", "long_short_ratio",
})
PERSISTED_CADENCE_DETECTION_SOURCE = "historical_ingest_persisted_cadence_v2"
RESPONSE_CADENCE_DETECTION_SOURCE = "historical_ingest_response_cadence_v2"
LIQUIDATION_HISTORY_HEARTBEAT = "ingest:liquidations_history"


async def _reconcile_persisted_cadence(
    conn: asyncpg.Connection,
    *,
    table: str,
    feed: str,
    exchange: str,
    market: str,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    cadence: timedelta,
    omitir_ya_declarados: bool = False,
) -> CadenceCoverage:
    if table not in _CADENCE_TABLES:
        raise ValueError("unsupported cadence source table")
    rows = await conn.fetch(
        f"SELECT ts FROM {table} WHERE symbol=$1 AND interval=$2 "
        "AND ts >= $3 AND ts < $4 ORDER BY ts",
        symbol, interval, start, end,
    )
    return await reconcile_cadence_coverage(
        conn,
        observations=(row["ts"] for row in rows),
        feed=feed,
        exchange=exchange,
        market=market,
        symbol=symbol,
        granularity=interval,
        start=start,
        end=end,
        cadence=cadence,
        detection_source=PERSISTED_CADENCE_DETECTION_SOURCE,
        omitir_ya_declarados=omitir_ya_declarados,
    )


# EL BARRIDO ANCHO · tabla, feed, exchange, interval, cadencia, margen de autocuracion.
#
# POR QUE EXISTE. El detector vivo mira 24 h atras. Un corte mas largo que eso deja todo
# lo anterior a las ultimas 24 h SIN NI UNA FILA: no es un hueco sin resolver, es un
# hueco que para el sistema nunca existio. Medido el 2026-08-30 en 140 tras el apagon
# de 37.4 h del 28: 2099 buckets de metricas y 636 de ohlcv sin una sola fila que los
# cubriera. La ventana del detector no puede ser mas corta que el corte mas largo, y
# como no se sabe cuanto durara el proximo, la unica ventana que no se queda corta es
# LA VIDA ENTERA DE LA SERIE RETENIDA.
#
# Y POR QUE SOBRE NUESTRAS FILAS Y NO SOBRE LA RESPUESTA. Son dos detectores distintos:
# el de respuesta solo ve lo que la fuente se salto DENTRO de un tramo que contesto, asi
# que un bucket que nunca le pedimos -porque estabamos caidos y al volver pedimos 26 h-
# no esta en la respuesta, no esta en la ventana y no existe. El persistido compara
# contra la TABLA, y ahi un bucket que no tenemos falta se le pregunte a quien se
# pregunte. La funcion persistida ya aceptaba las SEIS tablas y se la llamaba con UNA.
#
# EL MARGEN NO ES UNO SOLO, porque la ventana que se cura sola es distinta por familia:
# el ciclo de ohlcv pide 40 min y el de metricas 26 h -ingest.py, start_ohlcv y
# start_history-. Apuntar dentro de ese margen seria apuntar algo que el proximo ciclo
# va a rellenar. El de 5min de ohlcv hereda el de 1min porque su vela se construye de
# esos cinco minutos, y por eso ESTE BARRIDO VA DESPUES DEL ROLLUP ANCHO: al reves
# apuntaria como hueco lo que el rollup estaba a punto de construir.
BARRIDO_CADENCIA: tuple[tuple[str, str, str, str, timedelta, timedelta], ...] = (
    ("ohlcv", "ohlcv_1min", "binance", "1min", timedelta(minutes=1), timedelta(minutes=45)),
    ("ohlcv", "ohlcv_5min", "binance", "5min", timedelta(minutes=5), timedelta(minutes=45)),
    ("open_interest", "open_interest_5min", "binance", "5min",
     timedelta(minutes=5), timedelta(hours=27)),
    ("oi_bybit", "open_interest_5min", "bybit", "5min",
     timedelta(minutes=5), timedelta(hours=27)),
    ("funding_rate", "funding_rate", "binance", "5min",
     timedelta(minutes=5), timedelta(hours=27)),
    ("predicted_funding_rate", "predicted_funding_rate", "binance", "5min",
     timedelta(minutes=5), timedelta(hours=27)),
    ("long_short_ratio", "long_short_ratio", "binance", "5min",
     timedelta(minutes=5), timedelta(hours=27)),
)


def _piso(momento: datetime, cadencia: timedelta) -> datetime:
    """Baja el instante al bucket cerrado de esa cadencia. Sin esto la ventana no
    empieza ni acaba en frontera y generate_series interno apuntaria huecos falsos de
    un bucket en cada extremo."""
    segundos = int(cadencia.total_seconds())
    marca = int(momento.timestamp()) // segundos * segundos
    return datetime.fromtimestamp(marca, tz=UTC)


def ventana_barrido_cadencia(
    ahora: datetime, primera: datetime | None, hard_days: int,
    cadencia: timedelta, margen: timedelta,
) -> tuple[datetime, datetime] | None:
    """La ventana del barrido ancho, o None si no hay nada que barrer.

    EL LIMITE POR DETRAS SALE DE LA PROPIA SERIE y se topa en la retencion, por dos
    motivos que no son el mismo: antes de que la serie exista no hay ausencia que
    reprochar -contarlo daria un ROJO gigante y falso-, y lo que apply_retention borra
    por politica no es un hueco. Con el tope explicito, el ORDEN respecto a la purga
    deja de importar: la ventana es la misma se ejecute antes o despues.

    PUNTO CIEGO DECLARADO, porque descubrirlo dentro de tres meses seria peor: hard_days
    es el tope CORRECTO para las cinco series de metricas y para ohlcv 1min, pero NO para
    ohlcv 5min ni 4hour, que apply_retention borra a HTF_DATA_RETENTION_DAYS (400 en 140,
    contra 90 de HARD). O sea que entre los 90 y los 400 dias hay serie 5min retenida que
    este barrido no mira. HOY NO MUERDE -- ohlcv 5min empieza el 2026-07-23, 38 dias --
    y K68 trae el mismo tope por el mismo motivo, asi que check y barrido coinciden y
    ninguno miente sobre el otro. Cuando la serie pase de 90 dias hay que subir los dos
    a la vez o el check pedira declaraciones que el barrido no puede hacer.
    """
    if primera is None:
        return None
    fin = _piso(ahora - margen, cadencia)
    inicio = _piso(max(primera, ahora - timedelta(days=hard_days)), cadencia)
    if inicio >= fin:
        return None
    return inicio, fin


async def barrido_cadencia_persistido(
    conn: asyncpg.Connection,
    symbols: Iterable[str],
    *,
    hard_days: int,
    ahora: datetime,
) -> dict[str, int]:
    """Declara TODA discontinuidad de las siete series de cadencia que nadie haya visto.

    CORRE CADA HORA, no una vez al dia pese al nombre del servicio: el bucle de
    daily_agg usa timeout 45 s en la primera vuelta y luego alinea a 3600 s
    (daily_agg.py, bucle de servicio), asi que ademas se ejecuta 45 s despues de cada
    arranque. Lo escribo porque la primera version de este docstring decia "una vez al
    dia" y era falso: cambia a <=1 h la latencia con que se declara un tramo mudo, y
    hace que un despliegue dispare un barrido.
    No pide nada al proveedor: solo mira lo que tenemos y apunta lo que falta, que es
    justo lo que ningun detector hacia mas alla de 24 h.
    """
    resumen = {"ventanas": 0, "omitidas": 0, "recuperadas": 0, "series": 0}
    # Los simbolos se fijan UNA vez: se recorren dentro de siete bucles y un iterador se
    # habria vaciado en el primero, barriendo seis series con cero simbolos y saliendo
    # con todo a cero. Un barrido que no barre nada imprime lo mismo que uno limpio.
    simbolos = tuple(symbols)
    for tabla, feed, exchange, interval, cadencia, margen in BARRIDO_CADENCIA:
        # La tabla entra en un f-string, asi que la lista blanca se comprueba AQUI y no
        # solo dentro de _reconcile_persisted_cadence.
        if tabla not in _CADENCE_TABLES:
            raise ValueError("unsupported cadence source table")
        primera = await conn.fetchval(
            f"SELECT min(ts) FROM {tabla} WHERE interval=$1", interval
        )
        ventana = ventana_barrido_cadencia(ahora, primera, hard_days, cadencia, margen)
        if ventana is None:
            continue
        inicio, fin = ventana
        for symbol in simbolos:
            cobertura = await _reconcile_persisted_cadence(
                conn, table=tabla, feed=feed, exchange=exchange, market="perpetual",
                symbol=symbol, interval=interval, start=inicio, end=fin,
                cadence=cadencia,
                # Sin esto, long_short_ratio -que ya tiene 371 filas de otro detector-
                # se llevaria 371 duplicadas en la primera pasada.
                omitir_ya_declarados=True,
            )
            resumen["series"] += 1
            resumen["ventanas"] += len(cobertura.missing_windows) - cobertura.omitted_gaps
            resumen["omitidas"] += cobertura.omitted_gaps
            resumen["recuperadas"] += cobertura.recovered_gaps
    return resumen


async def _reconcile_response_cadence(
    conn: asyncpg.Connection,
    *,
    observations: dict[str, set[datetime]],
    feed: str,
    exchange: str,
    market: str,
    symbol: str,
    interval: str,
    start: datetime,
    end: datetime,
    cadence: timedelta,
    devueltos: dict[str, set[datetime]] | None = None,
) -> CadenceCoverage:
    return await reconcile_cadence_coverage(
        conn,
        observations=observations.get(symbol, set()),
        feed=feed,
        exchange=exchange,
        market=market,
        symbol=symbol,
        granularity=interval,
        start=start,
        end=end,
        cadence=cadence,
        detection_source=RESPONSE_CADENCE_DETECTION_SOURCE,
        source_response_buckets=None if devueltos is None else devueltos.get(symbol),
    )


def _liquidation_history_observation(
    payload: dict[str, list[dict[str, Any]]],
    requested_symbols: tuple[str, ...],
    *,
    accepted_rows: int,
    source_start: datetime,
    source_cutoff: datetime,
) -> tuple[str, str]:
    """Validate event-history observation without inventing cadence from silence."""
    requested = set(requested_symbols)
    observed_symbols = requested & set(payload)
    missing_symbols = sorted(requested - observed_symbols)
    returned_rows = sum(len(payload[symbol]) for symbol in requested_symbols if symbol in payload)
    reasons: list[str] = []
    if missing_symbols:
        reasons.append("missing_symbols")
    if accepted_rows != returned_rows:
        reasons.append("rejected_rows")
    status = "degraded" if reasons else "ok"
    detail = json.dumps(
        {
            "source_start_ts": int(source_start.timestamp()),
            "source_cutoff_ts": int(source_cutoff.timestamp()),
            "requested_symbols": len(requested_symbols),
            "observed_symbols": len(observed_symbols),
            "requested_symbol_names": sorted(requested),
            "observed_symbol_names": sorted(observed_symbols),
            "missing_symbols": missing_symbols,
            "returned_rows": returned_rows,
            "accepted_rows": accepted_rows,
            "reason": "+".join(reasons) if reasons else "complete_observation",
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    return status, detail[:500]


def _coverage_heartbeat_detail(
    *,
    feed: str,
    cutoff: datetime,
    rows: int | dict[str, int],
    coverages: list[tuple[str, CadenceCoverage]],
    extra: str | None = None,
    rejected: int | None = None,
) -> tuple[str, str]:
    expected = sum(item.expected_buckets for _, item in coverages)
    observed = sum(item.observed_buckets for _, item in coverages)
    missing = sum(item.missing_buckets for _, item in coverages)
    grouped: dict[str, list[int]] = {}
    for label, item in coverages:
        total = grouped.setdefault(label, [0, 0, 0])
        total[0] += item.observed_buckets
        total[1] += item.expected_buckets
        total[2] += item.missing_buckets
    source_text = "|".join(
        f"{label}:{v[0]}/{v[1]}:m{v[2]}" for label, v in sorted(grouped.items())
    )
    detail = (
        f"feed={feed},source_cutoff={cutoff.isoformat()},coverage={observed}/{expected},"
        f"missing={missing},sources={source_text},rows={rows}"
    )
    if rejected is not None:
        detail += f",rejected={rejected}"
    if extra:
        detail += f",{extra}"
    if rejected is None:
        return ("ok" if missing == 0 else "degraded"), detail[:500]
    # Un bucket que el proveedor no publica NO es un fallo nuestro; una fila que el
    # proveedor SI mando y nosotros tiramos, si. Es la misma distincion que ya hace
    # _liquidation_history_observation con returned_rows/accepted_rows.
    #
    # Medido el 2026-08-25: en 24 h la fuente devolvio 261 de 289 buckets de
    # long_short_ratio para SOL y 285 de 289 para BTC, y nuestra base tenia
    # EXACTAMENTE 261 y 285. O sea que el 'missing=29' que mantenia a
    # ingest:metrics_5m -y con el a healthz entero- en degraded desde hace semanas
    # estaba midiendo la completitud del PROVEEDOR como si fuera un defecto nuestro,
    # y por algo que nadie puede arreglar. Un indicador que no se puede apagar deja
    # de ser un indicador.
    #
    # Sigue degradando lo que si importa: filas rechazadas por nosotros, y una fuente
    # que se calla del todo (observed==0), que es una caida de verdad.
    nuestro = rejected > 0 or (expected > 0 and observed == 0)
    return ("degraded" if nuestro else "ok"), detail[:500]


async def ingest_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
    ownership: ServiceOwnership | None = None,
) -> None:
    await ingest_ohlcv_cycle(pool, client, settings, ownership=ownership)
    await ingest_metrics_cycle(pool, client, settings, ownership=ownership)


async def ingest_ohlcv_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
    ownership: ServiceOwnership | None = None,
    now_utc: datetime | None = None,
) -> None:
    now_utc = now_utc or datetime.now(UTC)
    cutoff = ClosedCutoff.at(now_utc, 60)
    metrics_cutoff = ClosedCutoff.at(now_utc, 300)
    end_ts = cutoff.api_end_ts
    start_ohlcv = cutoff.boundary_ts - OHLCV_1M_REFRESH_LOOKBACK_SECONDS
    symbols = tuple(settings.SYMBOLS)
    identity = {symbol: symbol for symbol in symbols}
    ohlcv = await client.history(
        "ohlcv-history", symbols, interval="1min", start_ts=start_ohlcv, end_ts=end_ts
    )
    ohlcv_observed: dict[str, set[datetime]] = {}
    async with pool.acquire() as conn:
        async with fenced_transaction(conn, ownership):
            count = await upsert_ohlcv(
                conn, ohlcv, identity, start_ohlcv, end_ts, "1min", observed=ohlcv_observed
            )
            rolled_up = await rollup_ohlcv_5m(conn, symbols, start_ohlcv, end_ts)
            coverage_start = cutoff.exclusive_boundary - timedelta(hours=24)
            response_start = datetime.fromtimestamp(start_ohlcv, tz=UTC)
            ohlcv_coverages: list[tuple[str, CadenceCoverage]] = []
            for symbol in symbols:
                persisted = await _reconcile_persisted_cadence(
                    conn, table="ohlcv", feed="ohlcv_1min", exchange="binance",
                    market="perpetual", symbol=symbol, interval="1min",
                    start=coverage_start, end=cutoff.exclusive_boundary,
                    cadence=timedelta(minutes=1),
                )
                current = await _reconcile_response_cadence(
                    conn, observations=ohlcv_observed, feed="ohlcv_1min",
                    exchange="binance", market="perpetual", symbol=symbol, interval="1min",
                    start=response_start, end=cutoff.exclusive_boundary,
                    cadence=timedelta(minutes=1),
                )
                ohlcv_coverages.append(("ohlcv_1min@binance:persisted24h", persisted))
                ohlcv_coverages.append(("ohlcv_1min@binance:response40m", current))
            ohlcv_status, ohlcv_detail = _coverage_heartbeat_detail(
                feed="ohlcv_1m", cutoff=cutoff.exclusive_boundary, rows=count,
                coverages=ohlcv_coverages, extra=f"rollup_5m={rolled_up}",
            )
        # Feed data and cadence truth are committed above; publish_snapshot opens its own
        # re-reads committed state, serialized against the metrics cycle.
        await publish_snapshot(
            conn,
            ownership,
            symbols,
            now_utc=now_utc,
            price_cutoff=cutoff.exclusive_boundary,
            metrics_cutoff=metrics_cutoff.exclusive_boundary,
        )
        await heartbeat_component(
            conn,
            "ingest",
            "ohlcv_1m",
            INGEST_COMPONENT_MAX_AGES,
            status=ohlcv_status,
            detail=ohlcv_detail,
            ownership=ownership,
        )
    LOGGER.info("ingest_ohlcv_cycle_complete rows=%d rollup_5m=%d", count, rolled_up)


async def ingest_metrics_cycle(
    pool: asyncpg.Pool,
    client: CoinalyzeClient,
    settings: Settings,
    ownership: ServiceOwnership | None = None,
    now_utc: datetime | None = None,
) -> None:
    now_utc = now_utc or datetime.now(UTC)
    cutoff = ClosedCutoff.at(now_utc, 300)
    price_cutoff = ClosedCutoff.at(now_utc, 60)
    end_ts = cutoff.api_end_ts
    start_history = cutoff.boundary_ts - 26 * 60 * 60
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
    metric_observations: dict[str, dict[str, set[datetime]]] = {
        "oi": {}, "oi_bybit": {}, "funding": {}, "predicted": {}, "long_short": {},
    }
    async with pool.acquire() as conn:
        async with fenced_transaction(conn, ownership):
            counts["oi"] = await upsert_ohlc_metric(
                conn, "open_interest", "oi", oi, identity, start_history, end_ts,
                observed=metric_observations["oi"],
            )
            counts["oi_bybit"] = await upsert_ohlc_metric(
                conn, "oi_bybit", "oi", oi_bybit, bybit_inverse, start_history, end_ts,
                observed=metric_observations["oi_bybit"],
            )
            counts["funding"] = await upsert_ohlc_metric(
                conn, "funding_rate", "fr", funding, identity, start_history, end_ts,
                observed=metric_observations["funding"],
            )
            counts["predicted"] = await upsert_ohlc_metric(
                conn, "predicted_funding_rate", "pfr", predicted, identity, start_history, end_ts,
                observed=metric_observations["predicted"],
            )
            counts["liquidations"] = await upsert_liquidations(
                conn, liquidations, identity, start_history, end_ts
            )
            counts["long_short"] = await upsert_long_short(
                conn, long_short, identity, start_history, end_ts,
                observed=metric_observations["long_short"],
            )

            source_start = datetime.fromtimestamp(start_history, tz=UTC)
            liq_status, liq_detail = _liquidation_history_observation(
                liquidations, symbols, accepted_rows=counts["liquidations"],
                source_start=source_start, source_cutoff=cutoff.exclusive_boundary,
            )
            # Event observation truth and accepted rows commit atomically before publication.
            await heartbeat(
                conn, LIQUIDATION_HISTORY_HEARTBEAT, status=liq_status, detail=liq_detail
            )

            coverage_start = cutoff.exclusive_boundary - timedelta(hours=24)
            metrics_coverages: list[tuple[str, CadenceCoverage]] = []
            cadence_sources = (
                ("oi", "open_interest_5min", "binance"),
                ("oi_bybit", "open_interest_5min", "bybit"),
                ("funding", "funding_rate", "binance"),
                ("predicted", "predicted_funding_rate", "binance"),
                ("long_short", "long_short_ratio", "binance"),
            )
            # Lo que la fuente DEVOLVIO, por fuente y por simbolo. Es la prueba con la que
            # se puede afirmar que un bucket no lo publica ella: si contesto antes y
            # despues del hueco y no lo mando, la ausencia es suya y el hueco se archiva
            # diciendo eso. Si se calla, si trunca, o si el bucket vino y lo descartamos
            # nosotros, no hay prueba y el hueco se queda pendiente.
            devueltos_por_fuente = {
                "oi": source_response_buckets(oi, identity, start_history, end_ts),
                "oi_bybit": source_response_buckets(
                    oi_bybit, bybit_inverse, start_history, end_ts
                ),
                "funding": source_response_buckets(funding, identity, start_history, end_ts),
                "predicted": source_response_buckets(
                    predicted, identity, start_history, end_ts
                ),
                "long_short": source_response_buckets(
                    long_short, identity, start_history, end_ts
                ),
            }
            for observation_key, feed, exchange in cadence_sources:
                for symbol in symbols:
                    proof = await _reconcile_response_cadence(
                        conn, observations=metric_observations[observation_key],
                        feed=feed, exchange=exchange, market="perpetual", symbol=symbol,
                        interval="5min", start=coverage_start, end=cutoff.exclusive_boundary,
                        cadence=timedelta(minutes=5),
                        devueltos=devueltos_por_fuente[observation_key],
                    )
                    metrics_coverages.append((f"{feed}@{exchange}:response24h", proof))
            # Cuantas filas mando la fuente frente a cuantas aceptamos. Si sobran,
            # las tiramos nosotros y eso SI es nuestro. Se cuenta aqui y no dentro de
            # cada upsert_* para no cambiarles la firma.
            cadence_payloads = (
                ("oi", oi, symbols),
                ("oi_bybit", oi_bybit, bybit_symbols),
                ("funding", funding, symbols),
                ("predicted", predicted, symbols),
                ("long_short", long_short, symbols),
            )
            rechazadas = 0
            for clave, payload, simbolos in cadence_payloads:
                devueltas = sum(len(payload[s]) for s in simbolos if s in payload)
                rechazadas += max(0, devueltas - counts.get(clave, 0))
            dense_status, metrics_detail = _coverage_heartbeat_detail(
                feed="metrics_5m", cutoff=cutoff.exclusive_boundary,
                rows=counts, coverages=metrics_coverages,
                extra=f"liquidations_history={liq_status}",
                rejected=rechazadas,
            )
            metrics_status = (
                "ok" if dense_status == "ok" and liq_status == "ok" else "degraded"
            )
        # Feed data, event observation health and cadence truth are committed above;
        # publish_snapshot opens its own transaction and
        # re-reads committed state, serialized against the OHLCV cycle.
        await publish_snapshot(
            conn,
            ownership,
            symbols,
            now_utc=now_utc,
            price_cutoff=price_cutoff.exclusive_boundary,
            metrics_cutoff=cutoff.exclusive_boundary,
        )
        await heartbeat_component(
            conn,
            "ingest",
            "metrics_5m",
            INGEST_COMPONENT_MAX_AGES,
            status=metrics_status,
            detail=metrics_detail,
            ownership=ownership,
        )
    LOGGER.info("ingest_metrics_cycle_complete counts=%s", counts)
    # Este contexto cambia despacio y no consume cuota de Coinalyze. Cada fuente se degrada
    # por separado: un calendario externo caído nunca invalida la ingestión de mercado.
    try:
        await refresh_external_macro(pool, settings, ownership=ownership)
    except ServiceOwnershipLost:
        raise
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
    on_error=None,
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
        except ServiceOwnershipLost:
            raise
        except Exception as exc:
            LOGGER.exception("ingest_feed_failed feed=%s", name)
            if on_error is not None:
                await on_error(exc)


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
    pool = await create_pool(
        settings,
        application_name="coinalyze-ingest",
        ownership=service_lock,
    )
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
        async with pool.acquire() as conn:
            for feed in INGEST_COMPONENT_MAX_AGES:
                await heartbeat_component(
                    conn,
                    "ingest",
                    feed,
                    INGEST_COMPONENT_MAX_AGES,
                    status="degraded",
                    detail="collector starting; awaiting successful cycle",
                    ownership=service_lock,
                )
        limiter = PostgresSlidingWindowRateLimiter(
            pool,
            settings.COINALYZE_RATE_LIMIT_UNITS,
            ownership=service_lock,
        )
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            async def mark_error(feed: str, exc: Exception) -> None:
                async with pool.acquire() as conn:
                    await heartbeat_component(
                        conn,
                        "ingest",
                        feed,
                        INGEST_COMPONENT_MAX_AGES,
                        status="error",
                        detail=f"{type(exc).__name__}: {exc}"[:500],
                        ownership=service_lock,
                    )

            tasks = (
                asyncio.create_task(
                    run_aligned_feed(
                        stop,
                        lambda: ingest_ohlcv_cycle(
                            pool, client, settings, ownership=service_lock
                        ),
                        cadence_seconds=settings.INGEST_INTERVAL_SECONDS,
                        offset_seconds=5,
                        name="ohlcv_1m",
                        on_error=lambda exc: mark_error("ohlcv_1m", exc),
                    )
                ),
                asyncio.create_task(
                    run_aligned_feed(
                        stop,
                        lambda: ingest_metrics_cycle(
                            pool, client, settings, ownership=service_lock
                        ),
                        cadence_seconds=300,
                        offset_seconds=15,
                        name="metrics_5m",
                        on_error=lambda exc: mark_error("metrics_5m", exc),
                    )
                ),
            )
            await wait_for_stop_or_lock_loss(
                stop,
                lock_monitor,
                critical_tasks=tasks,
            )
    finally:
        for task in tasks:
            task.cancel()
        lock_monitor.cancel()
        await asyncio.gather(*tasks, lock_monitor, return_exceptions=True)
        await pool.close()
        await service_lock.close()


if __name__ == "__main__":
    asyncio.run(run())
