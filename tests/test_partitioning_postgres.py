from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "sql/migrations/20260809_temporal_partitioning.sql").read_text(
    encoding="utf-8"
)
ROLLBACK = (
    ROOT / "sql/migrations/20260809_temporal_partitioning.down.sql"
).read_text(encoding="utf-8")
MANAGED = (
    "futures_trades_realtime",
    "spot_trades_realtime",
    "orderbook_snapshot",
    "liquidations_realtime",
    "scalp_signal_snapshot",
)


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"phase_b_{uuid4().hex}"


async def _setup_legacy(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}",public')
    await conn.execute(
        """
        CREATE TABLE market_assets(base_asset text PRIMARY KEY);
        INSERT INTO market_assets VALUES('BTC');
        CREATE TABLE symbols(symbol text PRIMARY KEY, base_asset text NOT NULL
            REFERENCES market_assets(base_asset));
        INSERT INTO symbols VALUES('BTCUSDT_PERP.A','BTC');

        CREATE TABLE futures_trades_realtime (
            LIKE public.futures_trades_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION
            INCLUDING COMMENTS
        );
        ALTER TABLE futures_trades_realtime
            ADD PRIMARY KEY(symbol,exchange,ts),
            ADD FOREIGN KEY(symbol) REFERENCES symbols(symbol);
        CREATE INDEX futures_trades_realtime_ts_idx ON futures_trades_realtime(ts DESC);
        CREATE INDEX futures_trades_realtime_symbol_exchange_ts_idx
            ON futures_trades_realtime(symbol,exchange,ts DESC);

        CREATE TABLE spot_trades_realtime (
            LIKE public.spot_trades_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION
            INCLUDING COMMENTS
        );
        ALTER TABLE spot_trades_realtime
            ADD PRIMARY KEY(symbol,exchange,ts),
            ADD FOREIGN KEY(symbol) REFERENCES market_assets(base_asset);
        CREATE INDEX spot_trades_realtime_ts_idx ON spot_trades_realtime(ts DESC);
        CREATE INDEX spot_trades_realtime_symbol_exchange_ts_idx
            ON spot_trades_realtime(symbol,exchange,ts DESC);

        CREATE TABLE orderbook_snapshot (
            LIKE public.orderbook_snapshot INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION
            INCLUDING COMMENTS
        );
        ALTER TABLE orderbook_snapshot
            ADD PRIMARY KEY(symbol,exchange,ts),
            ADD FOREIGN KEY(symbol) REFERENCES symbols(symbol);
        ALTER TABLE orderbook_snapshot
            DROP CONSTRAINT orderbook_snapshot_non_crossed_check;
        ALTER TABLE orderbook_snapshot
            ADD CONSTRAINT orderbook_snapshot_non_crossed_check
            CHECK (bid_px IS NULL OR ask_px IS NULL OR ask_px >= bid_px) NOT VALID;
        CREATE INDEX orderbook_snapshot_ts_idx ON orderbook_snapshot(ts DESC);
        CREATE INDEX orderbook_snapshot_symbol_exchange_ts_idx
            ON orderbook_snapshot(symbol,exchange,ts DESC);

        CREATE TABLE liquidations_realtime (
            LIKE public.liquidations_realtime INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION
            INCLUDING COMMENTS
        );
        ALTER TABLE liquidations_realtime
            ADD PRIMARY KEY(exchange,event_id),
            ADD FOREIGN KEY(symbol) REFERENCES symbols(symbol);
        CREATE INDEX liquidations_realtime_symbol_ts_idx
            ON liquidations_realtime(symbol,ts DESC);

        CREATE TABLE scalp_signal_snapshot (
            LIKE public.scalp_signal_snapshot INCLUDING DEFAULTS INCLUDING CONSTRAINTS
            INCLUDING GENERATED INCLUDING IDENTITY INCLUDING STORAGE INCLUDING COMPRESSION
            INCLUDING COMMENTS
        );
        ALTER TABLE scalp_signal_snapshot
            ADD PRIMARY KEY(symbol,ts),
            ADD FOREIGN KEY(symbol) REFERENCES symbols(symbol);
        CREATE INDEX scalp_signal_snapshot_latest_idx
            ON scalp_signal_snapshot(symbol,ts DESC);
        CREATE INDEX scalp_signal_snapshot_state_idx
            ON scalp_signal_snapshot(symbol,state,ts DESC);

        CREATE TABLE orderbook_depth (
            LIKE public.orderbook_depth INCLUDING ALL
        );
        """
    )
    base = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    before_boundary = base - timedelta(microseconds=1)
    at_boundary = base
    await conn.execute(
        """
        INSERT INTO futures_trades_realtime(
          ts,symbol,exchange,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,
          trade_count,last_px,last_event_ms
        ) VALUES
          ($1,'BTCUSDT_PERP.A','binance',10,4,2,1,3,100,1),
          ($2,'BTCUSDT_PERP.A','binance',11,5,3,1,4,101,2)
        """,
        before_boundary,
        at_boundary,
    )
    await conn.execute(
        """
        INSERT INTO spot_trades_realtime(
          ts,symbol,exchange,buy_vol_usd,sell_vol_usd,inst_buy_usd,inst_sell_usd,
          trade_count,last_px,last_event_ms
        ) VALUES($1,'BTC','binance',9,3,2,1,2,100,2)
        """,
        at_boundary,
    )
    await conn.execute(
        """
        INSERT INTO orderbook_snapshot(
          ts,symbol,exchange,bid_px,ask_px,mid_px,spread_bps
        ) VALUES($1,'BTCUSDT_PERP.A','binance',99,101,100,200)
        """,
        at_boundary,
    )
    await conn.execute(
        """
        INSERT INTO liquidations_realtime(
          ts,symbol,exchange,side,notional_usd,price,qty,event_id
        ) VALUES($1,'BTCUSDT_PERP.A','binance','long',1000,100,10,'legacy-event')
        """,
        at_boundary,
    )
    await conn.execute(
        """
        INSERT INTO scalp_signal_snapshot(
          ts,symbol,long_score,short_score,state,confidence,reason
        ) VALUES($1,'BTCUSDT_PERP.A',60,40,'No Trade','baja','legacy row')
        """,
        at_boundary,
    )


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


def _scan_relations(plan: dict[str, object]) -> set[str]:
    found: set[str] = set()
    relation = plan.get("Relation Name")
    if isinstance(relation, str):
        found.add(relation)
    for child in plan.get("Plans", []):
        if isinstance(child, dict):
            found.update(_scan_relations(child))
    return found


@pytest.mark.asyncio
async def test_partition_migration_routes_boundaries_prunes_and_preserves_schema() -> None:
    conn = await asyncpg.connect(_dsn())
    schema = _schema_name()
    try:
        await _setup_legacy(conn, schema)
        before = {
            table: await conn.fetchrow(
                f"SELECT count(*) AS count,min(ts) AS min,max(ts) AS max FROM {table}"
            )
            for table in MANAGED
        }
        await conn.execute(MIGRATION)

        kinds = dict(
            await conn.fetch(
                """
                SELECT c.relname,c.relkind
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=$1 AND c.relname=ANY($2::text[])
                """,
                schema,
                [*MANAGED, "orderbook_depth"],
            )
        )
        assert all(kinds[table] == b"p" for table in MANAGED)
        assert kinds["orderbook_depth"] == b"r"

        for table in MANAGED:
            assert await conn.fetchrow(
                f"SELECT count(*) AS count,min(ts) AS min,max(ts) AS max FROM {table}"
            ) == before[table]
            assert await conn.fetchrow(
                f"SELECT count(*) AS count,min(ts) AS min,max(ts) AS max "
                f"FROM {table}_unpartitioned_backup"
            ) == before[table]

        routed = await conn.fetch(
            "SELECT ts,tableoid::regclass::text AS child "
            "FROM futures_trades_realtime ORDER BY ts"
        )
        assert len(routed) == 2
        assert routed[0]["child"] != routed[1]["child"]
        assert routed[0]["child"].endswith(routed[0]["ts"].strftime("_p%Y%m%d"))
        assert routed[1]["child"].endswith(routed[1]["ts"].strftime("_p%Y%m%d"))

        plan_json = await conn.fetchval(
            "EXPLAIN (FORMAT JSON, COSTS OFF) "
            "SELECT * FROM futures_trades_realtime WHERE ts >= $1 AND ts < $2",
            routed[1]["ts"],
            routed[1]["ts"] + timedelta(days=1),
        )
        plan = json.loads(plan_json)[0]["Plan"]
        scans = _scan_relations(plan)
        assert routed[1]["child"].split(".")[-1] in scans
        assert routed[0]["child"].split(".")[-1] not in scans

        constraints = await conn.fetch(
            """
            SELECT c.contype,array_agg(a.attname ORDER BY key.ordinality) AS columns
            FROM pg_constraint c
            JOIN unnest(c.conkey) WITH ORDINALITY AS key(attnum,ordinality) ON true
            JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=key.attnum
            WHERE c.conrelid='liquidations_realtime'::regclass
            GROUP BY c.oid,c.contype
            """
        )
        assert any(row["contype"] == b"p" and "ts" in row["columns"] for row in constraints)
        assert any(row["contype"] == b"f" for row in constraints)
        assert await conn.fetchval(
            "SELECT count(*) FROM pg_indexes WHERE schemaname=$1 "
            "AND tablename LIKE 'futures_trades_realtime_p%'",
            schema,
        ) >= 3

        # The redesigned PK includes ts, while the trigger preserves the original global
        # source-event identity across partitions.
        later = routed[1]["ts"] + timedelta(hours=1)
        await conn.execute(
            """
            INSERT INTO liquidations_realtime(
              ts,symbol,exchange,side,notional_usd,price,qty,event_id
            ) VALUES($1,'BTCUSDT_PERP.A','binance','long',2,100,1,'legacy-event')
            ON CONFLICT(exchange,event_id,ts) DO NOTHING
            """,
            later,
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM liquidations_realtime WHERE event_id='legacy-event'"
        ) == 1

        await conn.execute(MIGRATION)
        assert await conn.fetchval("SELECT count(*) FROM futures_trades_realtime") == 2
    finally:
        await _drop_schema(conn, schema)
        await conn.close()


@pytest.mark.asyncio
async def test_future_ensure_is_concurrent_and_retention_drops_only_complete_days() -> None:
    owner = await asyncpg.connect(_dsn())
    schema = _schema_name()
    first: asyncpg.Connection | None = None
    second: asyncpg.Connection | None = None
    try:
        await _setup_legacy(owner, schema)
        await owner.execute(MIGRATION)
        first = await asyncpg.connect(_dsn())
        second = await asyncpg.connect(_dsn())
        await first.execute(f'SET search_path TO "{schema}",public')
        await second.execute(f'SET search_path TO "{schema}",public')
        reference = datetime.now(UTC) + timedelta(days=20)
        results = await asyncio.gather(
            first.fetchval("SELECT ensure_temporal_partitions($1,0,1)", reference),
            second.fetchval("SELECT ensure_temporal_partitions($1,0,1)", reference),
        )
        assert sorted(results) == [0, 10]
        assert await owner.fetchval(
            """
            SELECT count(*) FROM pg_inherits i
            JOIN pg_class c ON c.oid=i.inhrelid
            WHERE i.inhparent='futures_trades_realtime'::regclass
              AND c.relname LIKE $1
            """,
            f"futures_trades_realtime_p{reference:%Y%m}%",
        ) >= 2

        cutoff = datetime.now(UTC).replace(
            hour=12, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        full_old_day = cutoff.date() - timedelta(days=1)
        boundary_day = cutoff.date()
        await owner.fetchval(
            "SELECT ensure_temporal_partitions($1,0,0)",
            datetime.combine(full_old_day, datetime.min.time(), tzinfo=UTC),
        )
        full_child = f"futures_trades_realtime_p{full_old_day:%Y%m%d}"
        boundary_child = f"futures_trades_realtime_p{boundary_day:%Y%m%d}"
        assert await owner.fetchval(
            "SELECT drop_expired_temporal_partitions('futures_trades_realtime',$1)",
            cutoff,
        ) >= 1
        assert await owner.fetchval("SELECT to_regclass($1) IS NULL", full_child) is True
        assert await owner.fetchval("SELECT to_regclass($1) IS NOT NULL", boundary_child) is True
    finally:
        if first is not None:
            await first.close()
        if second is not None:
            await second.close()
        await _drop_schema(owner, schema)
        await owner.close()


@pytest.mark.asyncio
async def test_partition_rollback_restores_legacy_tables_when_rows_are_unchanged() -> None:
    conn = await asyncpg.connect(_dsn())
    schema = _schema_name()
    try:
        await _setup_legacy(conn, schema)
        expected = await conn.fetch("SELECT * FROM futures_trades_realtime ORDER BY ts")
        await conn.execute(MIGRATION)
        await conn.execute(ROLLBACK)
        assert await conn.fetchval(
            "SELECT relkind FROM pg_class WHERE oid='futures_trades_realtime'::regclass"
        ) == b"r"
        assert await conn.fetch("SELECT * FROM futures_trades_realtime ORDER BY ts") == expected
        assert await conn.fetchval(
            "SELECT to_regclass($1) IS NULL",
            f"{schema}.futures_trades_realtime_unpartitioned_backup",
        ) is True
    finally:
        await _drop_schema(conn, schema)
        await conn.close()


@pytest.mark.asyncio
async def test_partition_rollback_refuses_to_discard_post_migration_writes() -> None:
    conn = await asyncpg.connect(_dsn())
    schema = _schema_name()
    try:
        await _setup_legacy(conn, schema)
        await conn.execute(MIGRATION)
        ts = datetime.now(UTC).replace(minute=30, second=0, microsecond=0)
        await conn.execute(
            """
            INSERT INTO futures_trades_realtime(
              ts,symbol,exchange,buy_vol_usd,sell_vol_usd,large_buy_usd,large_sell_usd,
              trade_count,last_px,last_event_ms
            ) VALUES($1,'BTCUSDT_PERP.A','binance',1,1,0,0,1,100,3)
            ON CONFLICT(symbol,exchange,ts) DO NOTHING
            """,
            ts,
        )
        with pytest.raises(asyncpg.RaiseError, match="unsafe rollback refused"):
            await conn.execute(ROLLBACK)
        await conn.execute("ROLLBACK")
        assert await conn.fetchval(
            "SELECT relkind FROM pg_class WHERE oid='futures_trades_realtime'::regclass"
        ) == b"p"
        assert await conn.fetchval(
            "SELECT count(*) FROM futures_trades_realtime WHERE ts=$1", ts
        ) == 1
    finally:
        await _drop_schema(conn, schema)
        await conn.close()
