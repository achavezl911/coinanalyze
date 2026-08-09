from __future__ import annotations

import asyncpg

from app.config import Settings


async def create_pool(settings: Settings, *, application_name: str) -> asyncpg.Pool:
    async def init_connection(conn: asyncpg.Connection) -> None:
        await conn.execute("SET TIME ZONE 'UTC'")
        await conn.execute("SET statement_timeout = '20s'")
        await conn.execute("SET lock_timeout = '3s'")
        await conn.execute("SET idle_in_transaction_session_timeout = '30s'")
        await conn.execute("SELECT set_config('application_name', $1, false)", application_name)

    return await asyncpg.create_pool(
        dsn=settings.pg_dsn,
        min_size=settings.PG_POOL_MIN,
        max_size=settings.PG_POOL_MAX,
        max_inactive_connection_lifetime=300,
        command_timeout=30,
        init=init_connection,
    )


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
