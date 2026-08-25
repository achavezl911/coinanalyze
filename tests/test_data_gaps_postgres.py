from __future__ import annotations

import asyncio
import getpass
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import asyncpg
import pytest

import app.scalp_collector as scalp
from app.api import mask_gapped_series_rows
from app.config import Settings
from app.data_gaps import (
    GapRequirement,
    RecoveryObservation,
    RecoveryValidationError,
    archive_beyond_source_horizon,
    blocking_requirement_keys,
    reconcile_cadence_coverage,
    record_data_gap,
    recover_gap,
)
from app.db import ServiceOwnershipLost, acquire_service_lock
from app.metrics import compute_snapshot
from app.scalp_collector import (
    persist_liquidation_event_loss,
    persist_liquidation_health_snapshot,
    safe_liq_put,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "sql/migrations/20260809_data_gap_integrity.sql").read_text(
    encoding="utf-8"
)
ROLLBACK = (ROOT / "sql/migrations/20260809_data_gap_integrity.down.sql").read_text(
    encoding="utf-8"
)


async def _connect() -> asyncpg.Connection:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    conn = await asyncpg.connect(dsn)
    await conn.execute(MIGRATION)
    return conn


async def _cadence_gap(
    conn: asyncpg.Connection,
    *,
    start: datetime,
    end: datetime,
    symbol: str = "BTCUSDT_PERP.A",
    exchange: str = "binance",
) -> int:
    return await record_data_gap(
        conn,
        feed="ohlcv_1min",
        feed_class="cadence",
        exchange=exchange,
        market="perpetual",
        symbol=symbol,
        granularity="1min",
        start=start,
        end=end,
        expected_cadence=timedelta(minutes=1),
        evidence_type="missing_interval",
        detection_reason="configured cadence bucket absent",
        detection_source="test cadence detector",
    )


def _test_settings(dsn: str) -> Settings:
    parsed = urlparse(dsn)
    query = parse_qs(parsed.query)
    return Settings(
        # El directorio del socket viaja en la QUERY (?host=/var/run/postgresql),
        # no en el authority, asi que parsed.hostname es None y sin esta linea se
        # perdia el parametro y se conectaba por TCP a 127.0.0.1.
        PG_HOST=query.get("host", [""])[0] or parsed.hostname or "127.0.0.1",
        PG_PORT=parsed.port or 5432,
        PG_DB=parsed.path.lstrip("/"),
        # Sin usuario en el DSN NO se inventa "postgres": con auth peer el usuario
        # correcto es el del proceso, y "postgres" daba InvalidPasswordError.
        PG_USER=unquote(parsed.username or "") or getpass.getuser(),
        PG_PASSWORD=unquote(parsed.password or ""),
        PG_SSLMODE=query.get("sslmode", ["disable"])[0],
    )


def _chart_rows(start: datetime) -> list[dict[str, object]]:
    return [
        {"bucket": start, "delta": 1.0, "cvd": 1.0},
        {"bucket": start + timedelta(minutes=2), "delta": 2.0, "cvd": 3.0},
    ]


async def _mask_chart(conn: asyncpg.Connection, rows: list[dict[str, object]]) -> None:
    await mask_gapped_series_rows(
        conn,
        rows,
        bucket=timedelta(minutes=1),
        feed="ohlcv_1min",
        exchanges=("binance",),
        market="perpetual",
        symbol="BTCUSDT_PERP.A",
        value_keys=("delta",),
        cumulative_keys=("cvd",),
    )


@pytest.mark.asyncio
async def test_postgres_phase_a_migration_is_idempotent_and_rollback_preserves_market_data() -> None:
    conn = await _connect()
    try:
        await conn.execute("DROP SCHEMA IF EXISTS phase_a_migration_test CASCADE")
        await conn.execute("CREATE SCHEMA phase_a_migration_test")
        await conn.execute("SET search_path TO phase_a_migration_test,public")
        await conn.execute("CREATE TABLE market_probe(id integer PRIMARY KEY)")
        await conn.execute("INSERT INTO market_probe VALUES(1)")
        await conn.execute(MIGRATION)
        await conn.execute(MIGRATION)
        assert await conn.fetchval(
            "SELECT to_regclass('phase_a_migration_test.data_gap') IS NOT NULL"
        ) is True
        await conn.execute(ROLLBACK)
        assert await conn.fetchval(
            "SELECT to_regclass('phase_a_migration_test.data_gap') IS NULL"
        ) is True
        assert await conn.fetchval("SELECT count(*) FROM market_probe") == 1
    finally:
        await conn.execute("SET search_path TO public")
        await conn.execute("DROP SCHEMA IF EXISTS phase_a_migration_test CASCADE")
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_gap_creation_overlap_boundaries_and_source_isolation() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        end = start + timedelta(minutes=1)
        gap_id = await _cadence_gap(conn, start=start, end=end)
        same_id = await _cadence_gap(conn, start=start, end=end)
        assert same_id == gap_id
        blocked = await blocking_requirement_keys(
            conn,
            [
                GapRequirement(
                    "ends_at_gap", "ohlcv_1min", "binance", "perpetual",
                    "BTCUSDT_PERP.A", start - timedelta(minutes=1), start,
                ),
                GapRequirement(
                    "starts_at_end", "ohlcv_1min", "binance", "perpetual",
                    "BTCUSDT_PERP.A", end, end + timedelta(minutes=1),
                ),
                GapRequirement(
                    "inside", "ohlcv_1min", "binance", "perpetual",
                    "BTCUSDT_PERP.A", start, end,
                ),
                GapRequirement(
                    "other_exchange", "ohlcv_1min", "bybit", "perpetual",
                    "BTCUSDT_PERP.A", start, end,
                ),
                GapRequirement(
                    "other_symbol", "ohlcv_1min", "binance", "perpetual",
                    "ETHUSDT_PERP.A", start, end,
                ),
            ],
        )
        assert blocked == {"inside"}

        await conn.execute(
            "UPDATE data_gap SET status='recovered',resolved_at=now(),recovered_at=now() "
            "WHERE id=$1",
            gap_id,
        )
        assert not await blocking_requirement_keys(
            conn,
            [
                GapRequirement(
                    "inside", "ohlcv_1min", "binance", "perpetual",
                    "BTCUSDT_PERP.A", start, end,
                )
            ],
        )
        await conn.execute(
            "UPDATE data_gap SET status='unrecoverable',resolved_at=now(),recovered_at=NULL "
            "WHERE id=$1",
            gap_id,
        )
        assert await blocking_requirement_keys(
            conn,
            [
                GapRequirement(
                    "inside", "ohlcv_1min", "binance", "perpetual",
                    "BTCUSDT_PERP.A", start, end,
                )
            ],
        ) == {"inside"}
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_missing_bucket_breaks_later_cvd_continuity() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        await _cadence_gap(
            conn,
            start=start + timedelta(minutes=1),
            end=start + timedelta(minutes=2),
        )
        rows = _chart_rows(start)

        await _mask_chart(conn, rows)

        assert rows == [
            {"bucket": start, "delta": 1.0, "cvd": 1.0},
            {
                "bucket": start + timedelta(minutes=2),
                "delta": 2.0,
                "cvd": None,
            },
        ]
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_chart_ignores_outside_unrelated_and_recovered_gaps() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        missing_start = start + timedelta(minutes=1)
        missing_end = start + timedelta(minutes=2)
        await _cadence_gap(
            conn,
            start=start - timedelta(minutes=1),
            end=start,
        )
        for feed, exchange, market, symbol in (
            ("ohlcv_1min", "bybit", "perpetual", "BTCUSDT_PERP.A"),
            ("spot_trades", "binance", "perpetual", "BTCUSDT_PERP.A"),
            ("ohlcv_1min", "binance", "spot", "BTCUSDT_PERP.A"),
            ("ohlcv_1min", "binance", "perpetual", "ETHUSDT_PERP.A"),
        ):
            await record_data_gap(
                conn,
                feed=feed,
                feed_class="cadence",
                exchange=exchange,
                market=market,
                symbol=symbol,
                granularity="1min",
                start=missing_start,
                end=missing_end,
                expected_cadence=timedelta(minutes=1),
                evidence_type="missing_interval",
                detection_reason="unrelated test source",
                detection_source="test chart isolation",
            )
        recovered_id = await _cadence_gap(
            conn,
            start=missing_start,
            end=missing_end,
        )
        await conn.execute(
            """
            UPDATE data_gap
            SET status='recovered',resolved_at=now(),recovered_at=now()
            WHERE id=$1
            """,
            recovered_id,
        )
        rows = _chart_rows(start)

        await _mask_chart(conn, rows)

        assert rows == _chart_rows(start)
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_unrecoverable_missing_bucket_remains_non_evaluable() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        gap_id = await _cadence_gap(
            conn,
            start=start + timedelta(minutes=1),
            end=start + timedelta(minutes=2),
        )
        await conn.execute(
            """
            UPDATE data_gap
            SET status='unrecoverable',resolved_at=now(),recovered_at=NULL
            WHERE id=$1
            """,
            gap_id,
        )
        rows = _chart_rows(start)

        await _mask_chart(conn, rows)

        assert rows[0]["cvd"] == 1.0
        assert rows[1]["delta"] == 2.0
        assert rows[1]["cvd"] is None
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_metric_cvd_fails_closed_only_for_related_blocking_gap() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        now = datetime(2026, 8, 9, 12, 5, 15, tzinfo=UTC)
        candle = datetime(2026, 8, 9, 12, 4, tzinfo=UTC)
        await conn.execute(
            """
            INSERT INTO ohlcv(
              ts,symbol,interval,open,high,low,close,volume,buy_volume,tx,btx
            ) VALUES($1,'BTCUSDT_PERP.A','1min',100,101,99,100,10,7,10,7)
            ON CONFLICT(symbol,interval,ts) DO UPDATE SET buy_volume=EXCLUDED.buy_volume
            """,
            candle,
        )
        healthy = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)
        assert healthy["cvd_session"] is not None

        unrelated_id = await _cadence_gap(
            conn,
            start=candle,
            end=candle + timedelta(minutes=1),
            symbol="ETHUSDT_PERP.A",
        )
        unrelated = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)
        assert unrelated["cvd_session"] == healthy["cvd_session"]
        await conn.execute("DELETE FROM data_gap WHERE id=$1", unrelated_id)

        gap_id = await _cadence_gap(
            conn,
            start=candle,
            end=candle + timedelta(minutes=1),
        )
        blocked = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)
        assert blocked["cvd_session"] is None
        assert blocked["cvd_diff_24h"] is None
        assert blocked["regime_score"] is None

        await conn.execute(
            "UPDATE data_gap SET status='recovered',resolved_at=now(),recovered_at=now() "
            "WHERE id=$1",
            gap_id,
        )
        recovered = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)
        assert recovered["cvd_session"] == healthy["cvd_session"]

        await conn.execute(
            "UPDATE data_gap SET status='unrecoverable',resolved_at=now(),recovered_at=NULL "
            "WHERE id=$1",
            gap_id,
        )
        unrecoverable = await compute_snapshot(conn, "BTCUSDT_PERP.A", "BTC", now)
        assert unrecoverable["cvd_session"] is None
    finally:
        await tx.rollback()
        await conn.close()


class _ExactAdapter:
    name = "exact-test-source"
    feed = "ohlcv_1min"
    exchange = "binance"
    market = "perpetual"
    granularity = "1min"

    def __init__(self, *, complete: bool = True, persistable: bool = True) -> None:
        self.complete = complete
        self.persistable = persistable
        self.fetch_count = 0

    async def fetch(self, gap):
        self.fetch_count += 1
        timestamps = [gap.start]
        if self.complete:
            timestamps.append(gap.start + timedelta(minutes=1))
        return [
            RecoveryObservation(
                timestamp,
                timestamp.isoformat(),
                gap.feed,
                gap.exchange,
                gap.market,
                gap.symbol,
                gap.granularity,
                {"value": index + 1},
            )
            for index, timestamp in enumerate(timestamps)
        ]

    async def persist(self, conn, observations):
        if not self.persistable:
            raise RecoveryValidationError("provider rows failed market-data validation")
        await conn.executemany(
            "INSERT INTO recovery_probe(source_key,value) VALUES($1,$2) "
            "ON CONFLICT(source_key) DO UPDATE SET value=EXCLUDED.value",
            [(item.key, item.payload["value"]) for item in observations],
        )


@pytest.mark.asyncio
async def test_postgres_exact_recovery_validates_coverage_and_is_idempotent() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(
            "CREATE TEMP TABLE recovery_probe(source_key text PRIMARY KEY,value integer NOT NULL)"
        )
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        gap_id = await _cadence_gap(
            conn,
            start=start,
            end=start + timedelta(minutes=2),
        )
        adapter = _ExactAdapter()
        assert await recover_gap(conn, gap_id, adapter) == "recovered"
        assert await conn.fetchval("SELECT count(*) FROM recovery_probe") == 2
        assert await recover_gap(conn, gap_id, adapter) == "recovered"
        assert adapter.fetch_count == 1
        assert await conn.fetchval("SELECT count(*) FROM recovery_probe") == 2
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_incomplete_recovery_stays_unresolved_and_unavailable_is_explicit() -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        await conn.execute(
            "CREATE TEMP TABLE recovery_probe(source_key text PRIMARY KEY,value integer NOT NULL)"
        )
        start = datetime(2026, 8, 9, 12, tzinfo=UTC)
        incomplete_id = await _cadence_gap(
            conn,
            start=start,
            end=start + timedelta(minutes=2),
        )
        assert await recover_gap(conn, incomplete_id, _ExactAdapter(complete=False)) == "unresolved"
        assert await conn.fetchval("SELECT count(*) FROM recovery_probe") == 0
        assert await conn.fetchval(
            "SELECT status FROM data_gap WHERE id=$1", incomplete_id
        ) == "unresolved"

        invalid_payload_id = await _cadence_gap(
            conn,
            start=start + timedelta(minutes=10),
            end=start + timedelta(minutes=12),
        )
        assert await recover_gap(
            conn,
            invalid_payload_id,
            _ExactAdapter(persistable=False),
        ) == "unresolved"
        assert await conn.fetchval("SELECT count(*) FROM recovery_probe") == 0
        assert await conn.fetchval(
            "SELECT status FROM data_gap WHERE id=$1", invalid_payload_id
        ) == "unresolved"

        unavailable_id = await _cadence_gap(
            conn,
            start=start + timedelta(hours=1),
            end=start + timedelta(hours=1, minutes=1),
        )
        assert await recover_gap(conn, unavailable_id, None) == "unrecoverable"
        assert await conn.fetchval(
            "SELECT status FROM data_gap WHERE id=$1", unavailable_id
        ) == "unrecoverable"
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_liquidation_silence_creates_no_gap_but_queue_loss_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        async def no_health_write(*_args, **_kwargs):
            return None

        monkeypatch.setattr(scalp, "mark_feed_shard_connected", no_health_write)
        monkeypatch.setattr(scalp, "mark_feed_shard_degraded", no_health_write)
        monkeypatch.setattr(scalp, "LIQ_FEED_CONNECTED", {"binance": True})
        monkeypatch.setattr(scalp, "LIQ_LOSS_PENDING", {})
        monkeypatch.setattr(scalp, "LIQ_GAP_PENDING", set())
        queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        monkeypatch.setattr(scalp, "LIQ_QUEUE", queue)

        # A connected event stream can be silent; no timer or empty queue creates a gap.
        await persist_liquidation_health_snapshot(conn)
        assert await conn.fetchval("SELECT count(*) FROM data_gap") == 0

        event_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
        item = (
            event_at,
            "BTCUSDT_PERP.A",
            "binance",
            "long",
            100.0,
            100.0,
            1.0,
            "event",
        )
        await safe_liq_put(item)
        await safe_liq_put(item)
        await persist_liquidation_health_snapshot(conn)
        row = await conn.fetchrow(
            "SELECT feed,exchange,symbol,evidence_type,status,start_ts,end_ts FROM data_gap"
        )
        assert dict(row) == {
            "feed": "liquidations",
            "exchange": "binance",
            "symbol": "BTCUSDT_PERP.A",
            "evidence_type": "queue_full",
            "status": "unresolved",
            "start_ts": event_at,
            "end_ts": event_at + timedelta(microseconds=1),
        }
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_takeover_fences_event_loss_gap_in_the_insert_transaction() -> None:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    settings = _test_settings(dsn)
    service = f"gap-fence-{uuid4().hex}"
    owner_a = owner_b = None
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    event_at = datetime(2026, 8, 9, 12, tzinfo=UTC)
    try:
        owner_a = await acquire_service_lock(settings, service)
        generation_a = owner_a.generation
        await owner_a.close()
        owner_b = await acquire_service_lock(settings, service)
        assert owner_b.generation == generation_a + 1

        with pytest.raises(ServiceOwnershipLost, match="generation"):
            await persist_liquidation_event_loss(
                conn,
                "BTCUSDT_PERP.A",
                "binance",
                event_at,
                ownership=owner_a,
            )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM data_gap
            WHERE feed='liquidations' AND exchange='binance'
              AND market='perpetual' AND symbol='BTCUSDT_PERP.A'
              AND start_ts=$1
            """,
            event_at,
        ) == 0

        await persist_liquidation_event_loss(
            conn,
            "BTCUSDT_PERP.A",
            "binance",
            event_at,
            ownership=owner_b,
        )
        assert await conn.fetchval(
            """
            SELECT count(*) FROM data_gap
            WHERE feed='liquidations' AND exchange='binance'
              AND market='perpetual' AND symbol='BTCUSDT_PERP.A'
              AND start_ts=$1 AND status='unresolved'
            """,
            event_at,
        ) == 1
    finally:
        await tx.rollback()
        if owner_b is not None and not owner_b.is_closed():
            await owner_b.close()
        cleanup = await asyncpg.connect(dsn)
        await cleanup.execute("DELETE FROM service_ownership WHERE service=$1", service)
        await cleanup.close()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_source_absence_is_archived_against_the_real_constraint() -> None:
    """El SQL de verdad: la maquina de estados de data_gap tiene que aceptar el archivado.

    Los tests de tests/test_cobertura_proveedor.py fijan la REGLA con una conexion falsa.
    Este fija que la escritura pasa por data_gap_check2 y deja el motivo y la prueba
    guardados, que es lo que no se puede comprobar sin Postgres.
    """
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        inicio = datetime(2026, 8, 9, 12, tzinfo=UTC)
        fin = inicio + timedelta(minutes=30)
        cadencia = timedelta(minutes=5)
        rejilla = [inicio + cadencia * i for i in range(6)]
        saltado = inicio + timedelta(minutes=10)
        devueltos = [t for t in rejilla if t != saltado]

        cobertura = await reconcile_cadence_coverage(
            conn,
            observations=devueltos,
            feed="long_short_ratio",
            exchange="binance",
            market="perpetual",
            symbol="SOLUSDT_PERP.A",
            granularity="5min",
            start=inicio,
            end=fin,
            cadence=cadencia,
            detection_source="historical_ingest_response_cadence_v2",
            source_response_buckets=devueltos,
        )
        assert cobertura.missing_buckets == 1

        fila = await conn.fetchrow(
            """
            SELECT status,resolved_at,recovered_at,resolution_reason,recovery_metadata
            FROM data_gap
            WHERE feed='long_short_ratio' AND symbol='SOLUSDT_PERP.A' AND start_ts=$1
            """,
            saltado,
        )
        assert fila["status"] == "unrecoverable"
        assert fila["resolved_at"] is not None
        assert fila["recovered_at"] is None
        assert "source does not publish this bucket" in fila["resolution_reason"]
        assert '"method": "source_response_absence"' in fila["recovery_metadata"]

        # Segunda pasada: lo ya archivado no se reescribe ni se vuelve a contar.
        antes = fila["resolved_at"]
        await reconcile_cadence_coverage(
            conn,
            observations=devueltos,
            feed="long_short_ratio",
            exchange="binance",
            market="perpetual",
            symbol="SOLUSDT_PERP.A",
            granularity="5min",
            start=inicio,
            end=fin,
            cadence=cadencia,
            detection_source="historical_ingest_response_cadence_v2",
            source_response_buckets=devueltos,
        )
        despues = await conn.fetchval(
            "SELECT resolved_at FROM data_gap WHERE start_ts=$1 AND symbol='SOLUSDT_PERP.A'",
            saltado,
        )
        assert despues == antes, "una clasificacion no se reescribe en la pasada siguiente"
    finally:
        await tx.rollback()
        await conn.close()


# El predicado de harness/checks/K04-huecos.sh, copiado a proposito. Es duplicacion y
# se sabe: si el check cambia y esto no, el test deja de decir la verdad. Se acepta
# porque lo que fija es lo unico que no se puede fijar de otra forma -que QUIEN ESCRIBE
# la prueba y QUIEN LA VERIFICA sigan de acuerdo-, y un desacuerdo ahi es justo el
# fallo que nadie ve: el check se pondria VERDE sobre filas que no prueban nada.
K04_PRUEBA_SE_SOSTIENE = """
    coalesce(
      CASE recovery_metadata->>'method'
        WHEN 'source_response_absence' THEN
              recovery_metadata->>'response_first_bucket' IS NOT NULL
          AND recovery_metadata->>'response_last_bucket'  IS NOT NULL
          AND (recovery_metadata->>'response_first_bucket')::timestamptz <  start_ts
          AND (recovery_metadata->>'response_last_bucket')::timestamptz  >= end_ts
        WHEN 'provider_horizon_exhausted' THEN
              recovery_metadata->>'window_returned_rows'  IS NOT NULL
          AND recovery_metadata->>'control_returned_rows' IS NOT NULL
          AND (recovery_metadata->>'window_returned_rows')::int  =  0
          AND (recovery_metadata->>'control_returned_rows')::int >  0
        ELSE false
      END, false)
"""


@pytest.mark.asyncio
async def test_postgres_lo_que_archiva_la_app_pasa_la_re_derivacion_de_K04() -> None:
    """Escritor y verificador tienen que estar de acuerdo, y eso solo se ve en Postgres."""
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        inicio = datetime(2026, 8, 14, 3, tzinfo=UTC)
        gap_id = await _cadence_gap(conn, start=inicio, end=inicio + timedelta(minutes=2))
        huerfano = await _cadence_gap(
            conn, start=inicio + timedelta(hours=1), end=inicio + timedelta(hours=1, minutes=2)
        )

        # El camino honrado: ventana vacia MAS control reciente que si devuelve serie.
        tocadas = await archive_beyond_source_horizon(
            conn,
            feed="ohlcv_1min", exchange="binance", market="perpetual",
            symbol="BTCUSDT_PERP.A", granularity="1min",
            window_start=datetime(2026, 8, 14, tzinfo=UTC),
            window_end=datetime(2026, 8, 15, tzinfo=UTC),
            control_start=datetime(2026, 8, 25, 12, tzinfo=UTC),
            control_end=datetime(2026, 8, 25, 18, tzinfo=UTC),
            control_returned_rows=71,
        )
        assert tocadas == 2

        # El camino que K04 tiene que seguir cazando: archivado sin prueba ninguna.
        await conn.execute(
            "UPDATE data_gap SET recovery_metadata='{}'::jsonb WHERE id=$1", huerfano
        )

        sin_prueba = await conn.fetch(
            f"SELECT id FROM data_gap WHERE status='unrecoverable' AND NOT {K04_PRUEBA_SE_SOSTIENE}"
        )
        assert [r["id"] for r in sin_prueba] == [huerfano], (
            "K04 tiene que aceptar lo que escribe la app y rechazar el archivado mudo"
        )

        fila = await conn.fetchrow(
            "SELECT resolution_reason,recovery_metadata FROM data_gap WHERE id=$1", gap_id
        )
        assert "no longer serves this window" in fila["resolution_reason"]
        assert '"control_returned_rows": 71' in fila["recovery_metadata"]
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_postgres_una_fuente_callada_no_archiva_nada() -> None:
    """Si el proveedor esta caido, el control sale a 0 y no se puede barrer el atraso."""
    conn = await _connect()
    tx = conn.transaction()
    await tx.start()
    try:
        inicio = datetime(2026, 8, 14, 3, tzinfo=UTC)
        gap_id = await _cadence_gap(conn, start=inicio, end=inicio + timedelta(minutes=2))
        with pytest.raises(ValueError, match="control"):
            await archive_beyond_source_horizon(
                conn,
                feed="ohlcv_1min", exchange="binance", market="perpetual",
                symbol="BTCUSDT_PERP.A", granularity="1min",
                window_start=datetime(2026, 8, 14, tzinfo=UTC),
                window_end=datetime(2026, 8, 15, tzinfo=UTC),
                control_start=datetime(2026, 8, 25, 12, tzinfo=UTC),
                control_end=datetime(2026, 8, 25, 18, tzinfo=UTC),
                control_returned_rows=0,
            )
        assert await conn.fetchval(
            "SELECT status FROM data_gap WHERE id=$1", gap_id
        ) == "unresolved"
    finally:
        await tx.rollback()
        await conn.close()
