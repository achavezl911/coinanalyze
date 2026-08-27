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
        CREATE TABLE market_assets(
            base_asset text PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        INSERT INTO market_assets(base_asset) VALUES('BTC');
        CREATE TABLE symbols(
            symbol text PRIMARY KEY,
            base_asset text NOT NULL REFERENCES market_assets(base_asset),
            quote_asset text NOT NULL DEFAULT 'USDT',
            is_perpetual boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        INSERT INTO symbols(symbol,base_asset) VALUES('BTCUSDT_PERP.A','BTC');

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
        CREATE UNIQUE INDEX liquidations_realtime_exchange_event_ts_uidx
            ON liquidations_realtime(exchange,event_id,ts);

        CREATE OR REPLACE FUNCTION enforce_liquidation_event_unique()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(
                hashtextextended(NEW.exchange || E'\x1f' || NEW.event_id, 0)
            );
            IF EXISTS (
                SELECT 1 FROM liquidations_realtime
                WHERE exchange=NEW.exchange AND event_id=NEW.event_id
            ) THEN
                RETURN NULL;
            END IF;
            RETURN NEW;
        END
        $$;
        CREATE TRIGGER liquidations_realtime_event_unique_trigger
        BEFORE INSERT ON liquidations_realtime
        FOR EACH ROW EXECUTE FUNCTION enforce_liquidation_event_unique();

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

        CREATE TABLE schema_migration(
            name text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
        );
        INSERT INTO schema_migration(name)
        VALUES('20260809_partition_compatibility_bridge');
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


async def _run_supported_schema_deployment(schema: str) -> tuple[int, str]:
    environment = os.environ.copy()
    environment["PGOPTIONS"] = f"-c search_path={schema},public"
    process = await asyncio.create_subprocess_exec(
        "psql",
        _dsn(),
        "-v",
        "ON_ERROR_STOP=1",
        "-X",
        "-q",
        "-f",
        str(ROOT / "sql/schema.sql"),
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode or 0, (stdout + stderr).decode()


def _scan_relations(plan: dict[str, object]) -> set[str]:
    found: set[str] = set()
    relation = plan.get("Relation Name")
    if isinstance(relation, str):
        found.add(relation)
    for child in plan.get("Plans", []):
        if isinstance(child, dict):
            found.update(_scan_relations(child))
    return found


def test_supported_deployment_path_includes_the_real_partition_migration() -> None:
    # schema.sql must be self-contained: the production deploy wrapper
    # (deploy-coinalyze, outside this repo) copies ONLY schema.sql to a
    # scratch path before running `psql -f` on it -- no sibling
    # sql/migrations/ directory exists there. A relative \ir include would
    # silently fail to find its target in that environment (psql exits 0 on
    # a missing \ir target, so ON_ERROR_STOP does not catch it), which would
    # make the deploy wrapper report success while the real partition
    # migration never ran. The migration is inlined directly instead.
    schema = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
    update = (ROOT / "scripts/update.sh").read_text(encoding="utf-8")

    assert r"\ir migrations/20260809_temporal_partitioning.sql" not in schema
    assert MIGRATION.strip() in schema
    assert schema.index(
        "SELECT ensure_temporal_partitions();"
    ) < schema.index(MIGRATION.strip())
    assert "sql/migrations/20260809_temporal_partitioning.sql" in update
    assert "sql/migrations/20260809_temporal_partitioning.down.sql" in update


@pytest.mark.asyncio
async def test_supported_schema_deployment_executes_and_records_real_conversion() -> None:
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

        return_code, output = await _run_supported_schema_deployment(schema)
        assert return_code == 0, output
        assert await conn.fetchval(
            """
            SELECT count(*) = $2
            FROM pg_class AS relation
            JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=$1
              AND relation.relname=ANY($3::text[])
              AND relation.relkind='p'
            """,
            schema,
            len(MANAGED),
            list(MANAGED),
        )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM schema_migration
            WHERE name='20260809_temporal_partitioning'
            """
        ) == 1
        for table in MANAGED:
            assert await conn.fetchrow(
                f"SELECT count(*) AS count,min(ts) AS min,max(ts) AS max FROM {table}"
            ) == before[table]
    finally:
        await _drop_schema(conn, schema)
        await conn.close()


@pytest.mark.asyncio
async def test_supported_schema_deployment_fails_before_swap_without_bridge() -> None:
    conn = await asyncpg.connect(_dsn())
    schema = _schema_name()
    try:
        await _setup_legacy(conn, schema)
        await conn.execute(
            "DELETE FROM schema_migration "
            "WHERE name='20260809_partition_compatibility_bridge'"
        )

        return_code, output = await _run_supported_schema_deployment(schema)
        assert return_code != 0
        assert "requires the partition compatibility bridge release" in output
        assert await conn.fetchval(
            """
            SELECT count(*) = $2
            FROM pg_class AS relation
            JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=$1
              AND relation.relname=ANY($3::text[])
              AND relation.relkind='r'
            """,
            schema,
            len(MANAGED),
            list(MANAGED),
        )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM pg_class AS relation
            JOIN pg_namespace AS namespace ON namespace.oid=relation.relnamespace
            WHERE namespace.nspname=$1
              AND right(relation.relname, length('_unpartitioned_backup')) =
                  '_unpartitioned_backup'
            """,
            schema,
        ) == 0
    finally:
        await _drop_schema(conn, schema)
        await conn.close()


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
        assert await conn.fetchval(
            """
            SELECT count(*) FROM schema_migration
            WHERE name='20260809_temporal_partitioning'
            """
        ) == 1
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
        assert await owner.fetchval(
            "SELECT to_regclass($1) IS NULL", f"{schema}.{full_child}"
        ) is True
        assert await owner.fetchval(
            "SELECT to_regclass($1) IS NOT NULL", f"{schema}.{boundary_child}"
        ) is True
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
        assert await conn.fetchval(
            "SELECT to_regprocedure('enforce_liquidation_event_unique()') IS NOT NULL"
        ) is True
        assert await conn.fetchval(
            """
            SELECT count(*) FROM schema_migration
            WHERE name='20260809_partition_compatibility_bridge'
            """
        ) == 1
        assert await conn.fetchval(
            """
            SELECT count(*) FROM schema_migration
            WHERE name='20260809_temporal_partitioning'
            """
        ) == 0
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


@pytest.mark.asyncio
async def test_retention_through_app_partitioning_deletes_exactly_what_it_claims() -> None:
    """K16 · lo que borra, borra lo que dice: ni una fila mas, ni una menos.

    El test de arriba comprueba que la particion de un dia ENTERAMENTE vencido
    desaparece y que la de la frontera sobrevive COMO OBJETO. Eso no dice nada de las
    filas de dentro de la frontera, que es justo donde vive el riesgo: apply_temporal_
    retention promete "drop complete expired partitions, then trim the one boundary
    partition", o sea que ademas del DROP hace un DELETE ... WHERE ts < cutoff.

    Aqui se mide esa promesa fila a fila y a traves de app.partitioning, que es el
    modulo que la aplicacion llama de verdad y que hasta hoy no importaba ningun test.
    """

    from app.partitioning import apply_temporal_retention

    owner = await asyncpg.connect(_dsn())
    schema = _schema_name()
    try:
        await _setup_legacy(owner, schema)
        await owner.execute(MIGRATION)

        retention_hours = 48
        now = datetime.now(UTC)
        # Cuatro filas elegidas alrededor del corte que la funcion calculara
        # (statement_timestamp() - 48h). El margen de 1 h a cada lado absorbe el tiempo
        # que tarde el test: sin margen, esto seria una carrera contra el reloj.
        marcas = {
            "dia_entero_vencido": now - timedelta(hours=96),
            "justo_fuera": now - timedelta(hours=49),
            "justo_dentro": now - timedelta(hours=47),
            "reciente": now - timedelta(hours=1),
        }
        # Las particiones de esos dias tienen que existir antes de insertar: una tabla
        # particionada rechaza la fila para la que no hay hija.
        for marca in marcas.values():
            await owner.fetchval("SELECT ensure_temporal_partitions($1,0,0)", marca)

        # Exchange propio: _setup_legacy ya deja dos filas de 'binance' dentro del
        # horizonte, y mezclarlas con las mias haria que el test dependiera de ese
        # montaje en vez de de la regla que mide. 'bybit' y no un nombre inventado
        # porque futures_trades_realtime_exchange_check solo admite binance, bybit
        # y combined: la base rechaza cualquier otro.
        for i, (_nombre, ts) in enumerate(sorted(marcas.items())):
            await owner.execute(
                """
                INSERT INTO futures_trades_realtime(
                  ts,symbol,exchange,buy_vol_usd,sell_vol_usd,large_buy_usd,
                  large_sell_usd,trade_count,last_px,last_event_ms
                ) VALUES($1,'BTCUSDT_PERP.A','bybit',1,1,0,0,1,100,$2)
                """,
                ts,
                i,
            )
        assert (
            await owner.fetchval(
                "SELECT count(*) FROM futures_trades_realtime WHERE exchange='bybit'"
            )
            == 4
        )

        await apply_temporal_retention(owner, "futures_trades_realtime", retention_hours)

        quedan = [
            fila["ts"]
            for fila in await owner.fetch(
                "SELECT ts FROM futures_trades_realtime WHERE exchange='bybit' ORDER BY ts"
            )
        ]
        # LO QUE DICE: se van las anteriores al corte, se quedan las posteriores.
        assert quedan == [marcas["justo_dentro"], marcas["reciente"]]

        # Y el dia enteramente vencido no se queda como particion huerfana y vacia:
        # esa es la mitad DROP de la promesa, y sin ella la tabla acumula objetos.
        dia_vencido = marcas["dia_entero_vencido"].date()
        assert (
            await owner.fetchval(
                "SELECT to_regclass($1)",
                f"{schema}.futures_trades_realtime_p{dia_vencido:%Y%m%d}",
            )
            is None
        )
        # La frontera SIGUE existiendo aunque se le hayan quitado filas por debajo del
        # corte: si tambien se dropeara, se llevaria por delante las de "justo_dentro".
        dia_frontera = marcas["justo_dentro"].date()
        assert (
            await owner.fetchval(
                "SELECT to_regclass($1)",
                f"{schema}.futures_trades_realtime_p{dia_frontera:%Y%m%d}",
            )
            is not None
        )
    finally:
        await _drop_schema(owner, schema)
        await owner.close()
