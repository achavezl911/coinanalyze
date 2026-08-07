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
