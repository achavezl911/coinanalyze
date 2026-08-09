from __future__ import annotations

import asyncio

import asyncpg

from app.config import MARKET_SYMBOL_CATALOG, MarketSymbol, Settings


async def create_pool(settings: Settings, *, application_name: str) -> asyncpg.Pool:
    async def init_connection(conn: asyncpg.Connection) -> None:
        await conn.execute("SET TIME ZONE 'UTC'")
        await conn.execute("SET statement_timeout = '20s'")
        await conn.execute("SET lock_timeout = '3s'")
        await conn.execute("SET idle_in_transaction_session_timeout = '30s'")
        await conn.execute("SELECT set_config('application_name', $1, false)", application_name)

    pool = await asyncpg.create_pool(
        dsn=settings.pg_dsn,
        min_size=settings.PG_POOL_MIN,
        max_size=settings.PG_POOL_MAX,
        max_inactive_connection_lifetime=300,
        command_timeout=30,
        init=init_connection,
    )
    await sync_market_catalog(pool)
    return pool


async def sync_market_catalog(
    pool: asyncpg.Pool,
    catalog: tuple[MarketSymbol, ...] = MARKET_SYMBOL_CATALOG,
) -> None:
    assets = [(item.base_asset,) for item in catalog]
    symbols = [(item.symbol, item.base_asset, True) for item in catalog]
    symbols.extend((item.spot_history_symbol, item.base_asset, False) for item in catalog)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.executemany(
                "INSERT INTO market_assets(base_asset) VALUES($1) ON CONFLICT DO NOTHING",
                assets,
            )
            await conn.executemany(
                """
                INSERT INTO symbols(symbol,base_asset,is_perpetual)
                VALUES($1,$2,$3)
                ON CONFLICT(symbol) DO UPDATE SET
                  base_asset=EXCLUDED.base_asset,
                  is_perpetual=EXCLUDED.is_perpetual
                """,
                symbols,
            )


async def acquire_service_lock(
    settings: Settings,
    service: str,
    shard_index: int = 0,
    shard_count: int = 1,
) -> asyncpg.Connection:
    conn = await asyncpg.connect(
        dsn=settings.pg_dsn,
        server_settings={"application_name": f"coinalyze-lock-{service}"},
    )
    key = f"coinanalyze:{service}:{shard_index}:{shard_count}"
    try:
        locked = await conn.fetchval(
            "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
            key,
        )
        if not locked:
            raise RuntimeError(f"service shard already active: {key}")
    except BaseException:
        await conn.close()
        raise
    return conn


async def monitor_service_lock(
    conn: asyncpg.Connection,
    service: str,
    shard_index: int = 0,
    shard_count: int = 1,
    *,
    poll_seconds: float = 10.0,
    query_timeout: float = 10.0,
) -> None:
    """Fail when the PostgreSQL session that owns a service lock is lost."""
    key = f"coinanalyze:{service}:{shard_index}:{shard_count}"
    while True:
        await asyncio.sleep(poll_seconds)
        try:
            await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=query_timeout)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(f"service lock connection lost: {key}") from exc


async def wait_for_stop_or_lock_loss(
    stop: asyncio.Event,
    lock_monitor: asyncio.Task[None],
    *,
    timeout: float | None = None,
) -> bool:
    """Return whether shutdown was requested, and propagate lock loss immediately."""
    stop_wait = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait(
            (stop_wait, lock_monitor),
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if lock_monitor in done:
            await lock_monitor
        return stop_wait in done
    finally:
        stop_wait.cancel()
        await asyncio.gather(stop_wait, return_exceptions=True)


async def heartbeat(
    pool: asyncpg.Pool,
    service: str,
    *,
    status: str = "ok",
    detail: str | None = None,
) -> None:
    await pool.execute(
        """
        INSERT INTO pipeline_heartbeat(service, updated_at, status, detail)
        VALUES ($1, now(), $2, $3)
        ON CONFLICT (service) DO UPDATE
          SET updated_at = EXCLUDED.updated_at,
              status = EXCLUDED.status,
              detail = EXCLUDED.detail
        """,
        service,
        status,
        detail,
    )


async def heartbeat_shard(
    conn: asyncpg.Connection,
    service: str,
    shard_index: int,
    shard_count: int,
    *,
    status: str = "ok",
    detail: str | None = None,
) -> None:
    instance = f"{service}:{shard_index}/{shard_count}"
    await heartbeat(conn, instance, status=status, detail=detail)
    await conn.execute(
        """
        INSERT INTO pipeline_heartbeat(service,updated_at,status,detail)
        SELECT $1,
               COALESCE(MIN(updated_at),now()),
               CASE
                 WHEN COUNT(*) <> $3 THEN 'degraded'
                 WHEN bool_or(status='error') THEN 'error'
                 WHEN bool_or(status='degraded') THEN 'degraded'
                 ELSE 'ok'
               END,
               CASE
                 WHEN $3=1 THEN MAX(detail)
                 ELSE left(string_agg(service || '=' || COALESCE(detail,''), ';'),500)
               END
        FROM pipeline_heartbeat
        WHERE service LIKE $2
        ON CONFLICT(service) DO UPDATE SET
          updated_at=EXCLUDED.updated_at,
          status=EXCLUDED.status,
          detail=EXCLUDED.detail
        """,
        service,
        f"{service}:%/{shard_count}",
        shard_count,
    )


async def mark_feed_connected(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    detail: str | None = None,
) -> None:
    """Mark a market feed healthy without resetting an existing healthy period."""
    await conn.execute(
        """
        INSERT INTO market_feed_health(
          feed, exchange, status, healthy_since, updated_at, detail
        ) VALUES($1, $2, 'ok', now(), now(), $3)
        ON CONFLICT (feed, exchange) DO UPDATE
          SET status = 'ok',
              healthy_since = CASE
                WHEN market_feed_health.status = 'ok'
                  THEN market_feed_health.healthy_since
                ELSE now()
              END,
              updated_at = now(),
              detail = EXCLUDED.detail
        """,
        feed,
        exchange,
        detail,
    )


async def _mark_feed_unhealthy(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    status: str,
    detail: str | None,
    data_loss: bool,
) -> None:
    await conn.execute(
        """
        INSERT INTO market_feed_health(
          feed, exchange, status, last_loss_at, updated_at, detail
        ) VALUES($1, $2, $3, CASE WHEN $5 THEN now() END, now(), $4)
        ON CONFLICT (feed, exchange) DO UPDATE
          SET status = EXCLUDED.status,
              last_loss_at = CASE
                WHEN $5 THEN now()
                ELSE market_feed_health.last_loss_at
              END,
              updated_at = now(),
              detail = EXCLUDED.detail
        """,
        feed,
        exchange,
        status,
        detail,
        data_loss,
    )


async def mark_feed_degraded(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    detail: str | None = None,
    data_loss: bool = False,
) -> None:
    await _mark_feed_unhealthy(conn, feed, exchange, "degraded", detail, data_loss)


async def mark_feed_error(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    detail: str | None = None,
    data_loss: bool = False,
) -> None:
    await _mark_feed_unhealthy(conn, feed, exchange, "error", detail, data_loss)


async def _mark_feed_shard_health(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    shard_index: int,
    shard_count: int,
    expected_shards: tuple[int, ...],
    status: str,
    detail: str | None,
    data_loss: bool,
) -> None:
    """Persist one shard and refresh the fail-closed feed/exchange aggregate."""
    if shard_index not in expected_shards:
        raise ValueError("feed health cannot be written by a shard without symbols")
    lock_key = f"coinanalyze:feed-health:{feed}:{exchange}:{shard_count}"
    async with conn.transaction():
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            lock_key,
        )
        await conn.execute(
            """
            INSERT INTO market_feed_health_shard(
              feed, exchange, shard_index, shard_count, status,
              healthy_since, last_loss_at, updated_at, detail
            ) VALUES(
              $1, $2, $3, $4, $5,
              CASE WHEN $5='ok' THEN now() END,
              CASE WHEN $7 THEN now() END,
              now(), $6
            )
            ON CONFLICT(feed, exchange, shard_index, shard_count) DO UPDATE SET
              status=EXCLUDED.status,
              healthy_since=CASE
                WHEN EXCLUDED.status='ok' AND market_feed_health_shard.status='ok'
                  THEN market_feed_health_shard.healthy_since
                WHEN EXCLUDED.status='ok' THEN now()
                ELSE market_feed_health_shard.healthy_since
              END,
              last_loss_at=CASE
                WHEN $7 THEN now()
                ELSE market_feed_health_shard.last_loss_at
              END,
              updated_at=now(),
              detail=EXCLUDED.detail
            """,
            feed,
            exchange,
            shard_index,
            shard_count,
            status,
            detail,
            data_loss,
        )
        await conn.execute(
            """
            WITH aggregate AS (
              SELECT
                COUNT(*)::int AS observed_shards,
                bool_or(status='error') AS has_error,
                bool_or(status='degraded') AS has_degraded,
                bool_and(status='ok') AS all_ok,
                MAX(healthy_since) AS healthy_since,
                MAX(last_loss_at) AS last_loss_at,
                MIN(updated_at) AS updated_at,
                left(
                  string_agg(
                    'shard_' || shard_index || '=' || status || ':' || COALESCE(detail,''),
                    ';' ORDER BY shard_index
                  ),
                  500
                ) AS detail
              FROM market_feed_health_shard
              WHERE feed=$1 AND exchange=$2 AND shard_count=$3
                AND shard_index=ANY($4::integer[])
            )
            INSERT INTO market_feed_health(
              feed, exchange, status, healthy_since, last_loss_at, updated_at, detail
            )
            SELECT
              $1,
              $2,
              CASE
                WHEN observed_shards <> cardinality($4::integer[]) THEN 'degraded'
                WHEN has_error THEN 'error'
                WHEN has_degraded THEN 'degraded'
                ELSE 'ok'
              END,
              CASE
                WHEN observed_shards = cardinality($4::integer[]) AND all_ok
                  THEN healthy_since
              END,
              last_loss_at,
              COALESCE(updated_at, now()),
              CASE
                WHEN observed_shards <> cardinality($4::integer[])
                  THEN left(
                    'missing shard health: expected=' || cardinality($4::integer[]) ||
                    ',observed=' || observed_shards,
                    500
                  )
                ELSE detail
              END
            FROM aggregate
            ON CONFLICT(feed, exchange) DO UPDATE SET
              status=EXCLUDED.status,
              healthy_since=EXCLUDED.healthy_since,
              last_loss_at=EXCLUDED.last_loss_at,
              updated_at=EXCLUDED.updated_at,
              detail=EXCLUDED.detail
            """,
            feed,
            exchange,
            shard_count,
            list(expected_shards),
        )


async def mark_feed_shard_connected(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    shard_index: int,
    shard_count: int,
    expected_shards: tuple[int, ...],
    detail: str | None = None,
) -> None:
    await _mark_feed_shard_health(
        conn,
        feed,
        exchange,
        shard_index,
        shard_count,
        expected_shards,
        "ok",
        detail,
        False,
    )


async def mark_feed_shard_degraded(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    shard_index: int,
    shard_count: int,
    expected_shards: tuple[int, ...],
    detail: str | None = None,
    data_loss: bool = False,
) -> None:
    await _mark_feed_shard_health(
        conn,
        feed,
        exchange,
        shard_index,
        shard_count,
        expected_shards,
        "degraded",
        detail,
        data_loss,
    )


async def mark_feed_shard_error(
    conn: asyncpg.Connection,
    feed: str,
    exchange: str,
    shard_index: int,
    shard_count: int,
    expected_shards: tuple[int, ...],
    detail: str | None = None,
    data_loss: bool = False,
) -> None:
    await _mark_feed_shard_health(
        conn,
        feed,
        exchange,
        shard_index,
        shard_count,
        expected_shards,
        "error",
        detail,
        data_loss,
    )
