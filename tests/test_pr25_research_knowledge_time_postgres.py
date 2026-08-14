from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_replay import SCALP_SIGNAL_LOGIC_VERSION
from app.signal_visibility import (
    _CERTIFIED_EXECUTION_EXCHANGES,
    _CERTIFIED_OUTCOME_HORIZONS,
    RESEARCH_VISIBILITY_VERSION,
    certify_final_outcomes,
    certify_research_bundles,
)
from app.signal_walk_forward import WalkForwardManifestOptions, _fetch_period_grid_v2

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
UP_SQL = (
    ROOT / "sql/migrations/20260815_pr25_research_knowledge_time.sql"
).read_text(encoding="utf-8")
DOWN_SQL = (
    ROOT / "sql/migrations/20260815_pr25_research_knowledge_time_down.sql"
).read_text(encoding="utf-8")


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_pr25_visibility_{uuid.uuid4().hex}"


async def _new_schema_conn() -> tuple[asyncpg.Connection, str]:
    """Create a fresh schema, connect one connection, apply the full current schema."""

    schema = _schema_name()
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(SCHEMA_SQL)
    return conn, schema


async def _join_schema(schema: str) -> asyncpg.Connection:
    """A second/third connection pointed at the SAME already-created schema."""

    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


async def _teardown(setup: asyncpg.Connection, schema: str, *others: asyncpg.Connection) -> None:
    for conn in others:
        if not conn.is_closed():
            await conn.close()
    await _drop_schema(setup, schema)


@pytest.fixture
async def conn():
    connection, schema = await _new_schema_conn()
    try:
        yield connection
    finally:
        await _drop_schema(connection, schema)


# ---------------------------------------------------------------------------
# Fixture helpers: a complete evidence_version=6 periodic research bundle.
# ---------------------------------------------------------------------------

_ALL_HORIZONS = (1, 3, 5, 15, 30, 60, 120, 240)


async def _insert_v6_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    direction: str = "long",
    state: str = "Long Momentum",
    reference_price: float = 100.0,
    created_at: datetime | None = None,
) -> int:
    row_created_at = created_at or observed_at
    return int(
        await conn.fetchval(
            """
            INSERT INTO signal_observation(
              observed_at,observed_minute,created_at,symbol,signal_family,
              is_periodic,is_transition,
              logic_version,evidence_version,sampling_version,
              decision_status,direction,actionable,state,confidence,reason,
              reference_price,reference_price_source,reference_price_at,
              long_score,short_score,evidence_coverage_pct,
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,date_trunc('minute',$1::timestamptz),$5,
              'BTCUSDT_PERP.A','scalp',
              true,false,
              $6,6,1,
              'evaluable',$2,true,$3,'media','test',
              $4,'futures_realtime_combined',$1,
              70,30,90,
              0,1,
              repeat('a',64),'{}'::jsonb
            )
            RETURNING observation_id
            """,
            observed_at,
            direction,
            state,
            reference_price,
            row_created_at,
            SCALP_SIGNAL_LOGIC_VERSION,
        )
    )


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    created_at: datetime | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context,created_at
        ) VALUES($1,1,$2,repeat('b',64),'{"now_ms":1}'::jsonb,$3)
        """,
        observation_id,
        observed_at,
        created_at or observed_at,
    )


async def _insert_outcome_schedule(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
) -> None:
    """Schedule every OUTCOME_HORIZONS_MINUTES horizon as a pending row."""

    for horizon in _ALL_HORIZONS:
        start = observed_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
        end = start + timedelta(minutes=horizon)
        due = end + timedelta(minutes=43)
        await conn.execute(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,outcome_version
            ) VALUES($1,$2,$3,$4,$5,$5,30,$2,1)
            """,
            observation_id,
            horizon,
            start,
            end,
            due,
        )


async def _insert_execution_snapshot(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    observed_at: datetime,
    exchange: str,
) -> None:
    curve = {
        "1000": {
            "buy": {"avg_price": 100.05, "market_cost_bps_vs_mid": 5.0, "insufficient_depth": False},
            "sell": {"avg_price": 99.95, "market_cost_bps_vs_mid": 5.0, "insufficient_depth": False},
        },
        "10000": {
            "buy": {"avg_price": 100.08, "market_cost_bps_vs_mid": 8.0, "insufficient_depth": False},
            "sell": {"avg_price": 99.92, "market_cost_bps_vs_mid": 8.0, "insufficient_depth": False},
        },
        "50000": {
            "buy": {"avg_price": 100.2, "market_cost_bps_vs_mid": None, "insufficient_depth": True},
            "sell": {"avg_price": 99.8, "market_cost_bps_vs_mid": None, "insufficient_depth": True},
        },
        "100000": {
            "buy": {"avg_price": 100.3, "market_cost_bps_vs_mid": None, "insufficient_depth": True},
            "sell": {"avg_price": 99.7, "market_cost_bps_vs_mid": None, "insufficient_depth": True},
        },
    }
    await conn.execute(
        """
        INSERT INTO signal_execution_snapshot(
          observation_id,snapshot_version,exchange,captured_at,
          book_ts,book_age_seconds,status,
          levels_reported,bid_levels_valid,ask_levels_valid,
          best_bid_px,best_ask_px,mid_px,spread_bps,
          bid_depth_usd,ask_depth_usd,source_book_hash,cost_curve
        ) VALUES(
          $1,1,$2,$3::timestamptz,
          $3::timestamptz-interval '1 second',1,'valid',
          2,2,2,99.9,100.1,100.0,20.0,
          200000,200000,repeat('c',64),$4::jsonb
        )
        """,
        observation_id,
        exchange,
        observed_at,
        json.dumps(curve),
    )


async def _insert_complete_bundle(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    created_at: datetime | None = None,
) -> int:
    observation_id = await _insert_v6_observation(
        conn, observed_at=observed_at, created_at=created_at
    )
    await _insert_frame(conn, observation_id, observed_at, created_at=created_at)
    await _insert_outcome_schedule(conn, observation_id, observed_at)
    await _insert_execution_snapshot(
        conn, observation_id=observation_id, observed_at=observed_at, exchange="binance"
    )
    await _insert_execution_snapshot(
        conn, observation_id=observation_id, observed_at=observed_at, exchange="bybit"
    )
    return observation_id


async def _finalize_outcome(
    conn: asyncpg.Connection,
    observation_id: int,
    horizon_minutes: int,
    *,
    finalized_at: datetime,
    status: str = "evaluated",
) -> None:
    if status == "evaluated":
        reference_price = float(
            await conn.fetchval(
                "SELECT reference_price FROM signal_observation WHERE observation_id=$1",
                observation_id,
            )
        )
        await conn.execute(
            """
            UPDATE signal_outcome
            SET status='evaluated',
                finalized_at=$3,
                bars_found=bars_expected,
                entry_reference_price=$4,
                end_price=$4,
                max_high=$4,
                min_low=$4,
                market_return_pct=0,
                up_excursion_pct=0,
                down_excursion_pct=0,
                directional_return_pct=0,
                mfe_pct=0,
                mae_pct=0
            WHERE observation_id=$1 AND horizon_minutes=$2
            """,
            observation_id,
            horizon_minutes,
            finalized_at,
            reference_price,
        )
    else:
        await conn.execute(
            """
            UPDATE signal_outcome
            SET status='not_evaluable', finalized_at=$3, final_reason='fixture', bars_found=0
            WHERE observation_id=$1 AND horizon_minutes=$2
            """,
            observation_id,
            horizon_minutes,
            finalized_at,
        )


def _spec_v2_options(*, horizons: tuple[int, ...] = (15,)) -> WalkForwardManifestOptions:
    return WalkForwardManifestOptions(
        name="pr25-spec-v2-fetch-test",
        horizons=horizons,
        logic_version=SCALP_SIGNAL_LOGIC_VERSION,
        evidence_version=6,
        sampling_version=1,
        context_version=1,
        outcome_version=1,
        execution_snapshot_version=1,
        spec_version=2,
        research_visibility_version=1,
    )


# ---------------------------------------------------------------------------
# A3-01.1 Uncommitted observation bundle.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_certification_cannot_see_uncommitted_bundle_then_certifies_after_commit() -> None:
    setup, schema = await _new_schema_conn()
    conn_a = await _join_schema(schema)
    conn_b = await _join_schema(schema)
    try:
        observed_at = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)

        tx_a = conn_a.transaction()
        await tx_a.start()
        observation_id = await _insert_v6_observation(conn_a, observed_at=observed_at)
        await _insert_frame(conn_a, observation_id, observed_at)
        await _insert_outcome_schedule(conn_a, observation_id, observed_at)
        await _insert_execution_snapshot(
            conn_a, observation_id=observation_id, observed_at=observed_at, exchange="binance"
        )
        await _insert_execution_snapshot(
            conn_a, observation_id=observation_id, observed_at=observed_at, exchange="bybit"
        )
        # Deliberately NOT committed yet.

        assert await certify_research_bundles(conn_b) == 0
        assert (
            await conn_b.fetchval("SELECT count(*) FROM signal_research_bundle_visibility") == 0
        )

        await tx_a.commit()

        source_created_at = await conn_b.fetchval(
            "SELECT created_at FROM signal_observation WHERE observation_id=$1", observation_id
        )
        assert await certify_research_bundles(conn_b) == 1
        rows = await conn_b.fetch(
            "SELECT observation_id,visibility_version,verified_visible_at "
            "FROM signal_research_bundle_visibility"
        )
        assert len(rows) == 1
        assert rows[0]["observation_id"] == observation_id
        assert rows[0]["visibility_version"] == RESEARCH_VISIBILITY_VERSION
        # The certificate timestamp is obtained AFTER the successful committed
        # source read -- it can never precede the source's own commit-visible
        # created_at provenance.
        assert rows[0]["verified_visible_at"] >= source_created_at

        # Idempotent/safe retry: a repeated pass produces exactly one row.
        assert await certify_research_bundles(conn_b) == 0
        assert (
            await conn_b.fetchval("SELECT count(*) FROM signal_research_bundle_visibility") == 1
        )
    finally:
        await _teardown(setup, schema, conn_a, conn_b)


# ---------------------------------------------------------------------------
# A3-01.2 Fixed cutoff between created_at and certification.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fixed_cutoff_between_created_at_and_verified_visible_at_excludes_row() -> None:
    conn, schema = await _new_schema_conn()
    try:
        observed_at = datetime(2020, 1, 1, 0, 0, tzinfo=UTC)
        observation_id = await _insert_complete_bundle(conn, observed_at=observed_at)

        assert await certify_research_bundles(conn) == 1
        verified_visible_at = await conn.fetchval(
            "SELECT verified_visible_at FROM signal_research_bundle_visibility "
            "WHERE observation_id=$1",
            observation_id,
        )

        options = _spec_v2_options(horizons=(15,))
        period_start = observed_at - timedelta(hours=1)
        period_end = observed_at + timedelta(hours=1)

        # source created_at (2020-01-01) < cutoff < verified_visible_at (real
        # certification wall-clock time, necessarily "now" or later).
        excluding_cutoff = verified_visible_at - timedelta(microseconds=1)
        excluded_grid = await _fetch_period_grid_v2(
            conn,
            period_start=period_start,
            period_end=period_end,
            knowledge_cutoff=excluding_cutoff,
            options=options,
        )
        assert excluded_grid == []

        included_grid = await _fetch_period_grid_v2(
            conn,
            period_start=period_start,
            period_end=period_end,
            knowledge_cutoff=verified_visible_at,
            options=options,
        )
        assert len(included_grid) == 1
        assert included_grid[0]["observation_id"] == observation_id
    finally:
        await _drop_schema(conn, schema)


# ---------------------------------------------------------------------------
# A3-01.3 Final outcome race.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_final_outcome_race_projects_pending_until_final_certificate() -> None:
    setup, schema = await _new_schema_conn()
    conn_a = await _join_schema(schema)
    conn_b = await _join_schema(schema)
    try:
        observed_at = datetime(2021, 6, 1, 8, 0, tzinfo=UTC)
        observation_id = await _insert_complete_bundle(setup, observed_at=observed_at)
        assert await certify_research_bundles(setup) == 1

        tx_a = conn_a.transaction()
        await tx_a.start()
        finalized_at = datetime.now(UTC)
        await _finalize_outcome(conn_a, observation_id, 15, finalized_at=finalized_at)
        # Deliberately NOT committed yet.

        assert await certify_final_outcomes(conn_b) == 0

        await tx_a.commit()

        options = _spec_v2_options(horizons=(15,))
        period_start = observed_at - timedelta(hours=1)
        period_end = observed_at + timedelta(hours=1)

        cutoff_after_finalized_before_cert = datetime.now(UTC)
        grid_before_cert = await _fetch_period_grid_v2(
            setup,
            period_start=period_start,
            period_end=period_end,
            knowledge_cutoff=cutoff_after_finalized_before_cert,
            options=options,
        )
        row_before_cert = next(row for row in grid_before_cert if row["horizon_minutes"] == 15)
        assert row_before_cert["status"] == "pending"
        assert row_before_cert["directional_return_pct"] is None

        assert await certify_final_outcomes(setup) == 1
        outcome_id = await setup.fetchval(
            "SELECT outcome_id FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=15",
            observation_id,
        )
        verified_visible_at = await setup.fetchval(
            "SELECT verified_visible_at FROM signal_outcome_final_visibility WHERE outcome_id=$1",
            outcome_id,
        )

        grid_still_before = await _fetch_period_grid_v2(
            setup,
            period_start=period_start,
            period_end=period_end,
            knowledge_cutoff=verified_visible_at - timedelta(microseconds=1),
            options=options,
        )
        row_still_pending = next(
            row for row in grid_still_before if row["horizon_minutes"] == 15
        )
        assert row_still_pending["status"] == "pending"

        grid_after = await _fetch_period_grid_v2(
            setup,
            period_start=period_start,
            period_end=period_end,
            knowledge_cutoff=verified_visible_at,
            options=options,
        )
        row_after = next(row for row in grid_after if row["horizon_minutes"] == 15)
        assert row_after["status"] == "evaluated"
        assert row_after["directional_return_pct"] == 0
    finally:
        await _teardown(setup, schema, conn_a, conn_b)


# ---------------------------------------------------------------------------
# A3-01.4 Crash gap / retry.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_committed_evidence_without_certificate_excluded_then_certified_on_retry(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2022, 3, 1, 9, 0, tzinfo=UTC)
    observation_id = await _insert_complete_bundle(conn, observed_at=observed_at)

    options = _spec_v2_options(horizons=(15,))
    period_start = observed_at - timedelta(hours=1)
    period_end = observed_at + timedelta(hours=1)
    far_future_cutoff = observed_at + timedelta(days=3650)

    grid_before = await _fetch_period_grid_v2(
        conn,
        period_start=period_start,
        period_end=period_end,
        knowledge_cutoff=far_future_cutoff,
        options=options,
    )
    assert grid_before == []

    assert await certify_research_bundles(conn) == 1
    assert await certify_research_bundles(conn) == 0
    assert await conn.fetchval("SELECT count(*) FROM signal_research_bundle_visibility") == 1

    grid_after = await _fetch_period_grid_v2(
        conn,
        period_start=period_start,
        period_end=period_end,
        knowledge_cutoff=far_future_cutoff,
        options=options,
    )
    assert len(grid_after) == 1
    assert grid_after[0]["observation_id"] == observation_id


# ---------------------------------------------------------------------------
# A3-01.5 Append-only enforcement on both new visibility surfaces.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bundle_visibility_rejects_update_delete_truncate(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 1, 1, 0, 0, tzinfo=UTC)
    observation_id = await _insert_complete_bundle(conn, observed_at=observed_at)
    assert await certify_research_bundles(conn) == 1

    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "UPDATE signal_research_bundle_visibility SET evidence_version=6 "
            "WHERE observation_id=$1",
            observation_id,
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "DELETE FROM signal_research_bundle_visibility WHERE observation_id=$1",
            observation_id,
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute("TRUNCATE signal_research_bundle_visibility")


@pytest.mark.asyncio
async def test_final_visibility_rejects_update_delete_truncate(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 2, 1, 0, 0, tzinfo=UTC)
    observation_id = await _insert_complete_bundle(conn, observed_at=observed_at)
    assert await certify_research_bundles(conn) == 1
    await _finalize_outcome(conn, observation_id, 15, finalized_at=datetime.now(UTC))
    assert await certify_final_outcomes(conn) == 1
    outcome_id = await conn.fetchval(
        "SELECT outcome_id FROM signal_outcome WHERE observation_id=$1 AND horizon_minutes=15",
        observation_id,
    )

    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "UPDATE signal_outcome_final_visibility SET source_status='not_evaluable' "
            "WHERE outcome_id=$1",
            outcome_id,
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "DELETE FROM signal_outcome_final_visibility WHERE outcome_id=$1", outcome_id
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute("TRUNCATE signal_outcome_final_visibility")


# ---------------------------------------------------------------------------
# No v1-v5 certification, no backfill.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_evidence_versions_are_never_certified(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 3, 1, 0, 0, tzinfo=UTC)
    for legacy_evidence_version in (1, 2, 3, 4, 5):
        await conn.execute(
            """
            INSERT INTO signal_observation(
              observed_at,observed_minute,symbol,signal_family,
              is_periodic,is_transition,
              logic_version,evidence_version,sampling_version,
              decision_status,direction,actionable,state,confidence,reason,
              long_score,short_score,evidence_coverage_pct,
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,date_trunc('minute',$1::timestamptz),
              'BTCUSDT_PERP.A','scalp',
              true,false,
              $2,$3,1,
              'evaluable','long',true,'Long Momentum','media','test',
              70,30,90,
              0,1,
              repeat('a',64),'{}'::jsonb
            )
            """,
            observed_at + timedelta(minutes=legacy_evidence_version),
            SCALP_SIGNAL_LOGIC_VERSION,
            legacy_evidence_version,
        )
    assert await certify_research_bundles(conn) == 0
    assert await conn.fetchval("SELECT count(*) FROM signal_research_bundle_visibility") == 0


# ---------------------------------------------------------------------------
# Migration: fresh schema / UP / UP twice / DOWN empty / re-UP.
# ---------------------------------------------------------------------------


async def _table_exists(conn: asyncpg.Connection, name: str) -> bool:
    # Schema-qualified deliberately: an unqualified to_regclass()/regclass
    # cast falls through `search_path` to `public`, and some OTHER Postgres
    # test files in this repo (e.g. tests/test_db.py) assume `public` on
    # TEST_DATABASE_URL permanently carries a full schema.sql deploy. This
    # check must only ever look at THIS test's own uuid-suffixed schema.
    return bool(
        await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
            "WHERE table_schema=current_schema() AND table_name=$1)",
            name,
        )
    )


async def _constraint_exists(conn: asyncpg.Connection, table: str, name: str) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_constraint c "
            "JOIN pg_class t ON t.oid=c.conrelid "
            "JOIN pg_namespace n ON n.oid=t.relnamespace "
            "WHERE n.nspname=current_schema() AND t.relname=$1 AND c.conname=$2)",
            table,
            name,
        )
    )


@pytest.mark.asyncio
async def test_migration_fresh_schema_up_twice_down_empty_reup(
    conn: asyncpg.Connection,
) -> None:
    # Fresh schema: sql/schema.sql already contains the PR25 UP block
    # appended (schema.sql is itself append-only/sequential), so a brand
    # new deploy is coherent with the PR25 invariants from the start.
    assert await _table_exists(conn, "signal_research_bundle_visibility")
    assert await _table_exists(conn, "signal_outcome_final_visibility")
    assert await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr25_regime_provenance_check"
    )
    assert await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr25_reference_time_check"
    )

    # UP once / UP twice: the standalone migration file is idempotent when
    # (re-)applied against an already-migrated database.
    await conn.execute(UP_SQL)
    await conn.execute(UP_SQL)
    assert await _table_exists(conn, "signal_research_bundle_visibility")

    # DOWN with no PR25 evidence succeeds.
    await conn.execute(DOWN_SQL)
    assert not await _table_exists(conn, "signal_research_bundle_visibility")
    assert not await _table_exists(conn, "signal_outcome_final_visibility")
    assert not await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr25_regime_provenance_check"
    )
    assert await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr24_regime_provenance_check"
    )
    assert await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr24_reference_time_check"
    )

    # Re-UP restores the PR25 surfaces.
    await conn.execute(UP_SQL)
    assert await _table_exists(conn, "signal_research_bundle_visibility")
    assert await _table_exists(conn, "signal_outcome_final_visibility")
    assert await _constraint_exists(
        conn, "signal_observation", "signal_observation_pr25_regime_provenance_check"
    )


@pytest.mark.asyncio
async def test_migration_down_fails_closed_on_evidence_v6(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 4, 1, 0, 0, tzinfo=UTC)
    observation_id = await _insert_v6_observation(conn, observed_at=observed_at)

    with pytest.raises(asyncpg.PostgresError, match="refuses to"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")

    assert (
        await conn.fetchval(
            "SELECT count(*) FROM signal_observation WHERE observation_id=$1", observation_id
        )
        == 1
    )
    assert await _table_exists(conn, "signal_research_bundle_visibility")


@pytest.mark.asyncio
async def test_migration_down_fails_closed_on_research_bundle_certificate(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 5, 1, 0, 0, tzinfo=UTC)
    await _insert_complete_bundle(conn, observed_at=observed_at)
    assert await certify_research_bundles(conn) == 1

    with pytest.raises(asyncpg.PostgresError, match="refuses to"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")

    assert await conn.fetchval("SELECT count(*) FROM signal_research_bundle_visibility") == 1


@pytest.mark.asyncio
async def test_migration_down_fails_closed_on_final_outcome_certificate(
    conn: asyncpg.Connection,
) -> None:
    observed_at = datetime(2023, 6, 1, 0, 0, tzinfo=UTC)
    observation_id = await _insert_complete_bundle(conn, observed_at=observed_at)
    assert await certify_research_bundles(conn) == 1
    await _finalize_outcome(conn, observation_id, 15, finalized_at=datetime.now(UTC))
    assert await certify_final_outcomes(conn) == 1

    with pytest.raises(asyncpg.PostgresError, match="refuses to"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")

    assert await conn.fetchval("SELECT count(*) FROM signal_outcome_final_visibility") == 1


@pytest.mark.asyncio
async def test_migration_down_fails_closed_on_spec_v2_manifest(
    conn: asyncpg.Connection,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version,manifest_name,created_at,cutoff_at,warmup_days,
          test_days,fold_count,min_group_n,selection_policy,manifest_hash,spec
        ) VALUES(
          1,'pr25-fake-spec-v2-manifest',now(),now()+interval '1 day',7,7,4,30,
          'fixed_kernel_no_selection_v1',repeat('d',64),$1::jsonb
        )
        """,
        json.dumps({"spec_version": 2}),
    )

    with pytest.raises(asyncpg.PostgresError, match="refuses to"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")

    assert (
        await conn.fetchval(
            "SELECT count(*) FROM signal_walk_forward_manifest "
            "WHERE manifest_name='pr25-fake-spec-v2-manifest'"
        )
        == 1
    )


@pytest.mark.asyncio
async def test_migration_down_fails_closed_on_research_visibility_version_reference(
    conn: asyncpg.Connection,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version,manifest_name,created_at,cutoff_at,warmup_days,
          test_days,fold_count,min_group_n,selection_policy,manifest_hash,spec
        ) VALUES(
          1,'pr25-fake-research-visibility-manifest',now(),now()+interval '1 day',7,7,4,30,
          'fixed_kernel_no_selection_v1',repeat('e',64),$1::jsonb
        )
        """,
        json.dumps({"spec_version": 1, "versions": {"research_visibility_version": 1}}),
    )

    with pytest.raises(asyncpg.PostgresError, match="refuses to"):
        await conn.execute(DOWN_SQL)
    await conn.execute("ROLLBACK")

    assert (
        await conn.fetchval(
            "SELECT count(*) FROM signal_walk_forward_manifest "
            "WHERE manifest_name='pr25-fake-research-visibility-manifest'"
        )
        == 1
    )


@pytest.mark.asyncio
async def test_visibility_certificate_producers_require_a_new_transaction(
    conn: asyncpg.Connection,
) -> None:
    async with conn.transaction():
        with pytest.raises(RuntimeError, match="must own a new transaction"):
            await certify_research_bundles(conn)
        with pytest.raises(RuntimeError, match="must own a new transaction"):
            await certify_final_outcomes(conn)


@pytest.mark.asyncio
async def test_visibility_producers_fail_before_certificate_on_identity_mismatch(
    conn: asyncpg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _insert_complete_bundle(
        conn,
        observed_at=datetime(2023, 7, 1, 0, 0, tzinfo=UTC),
    )
    import app.signal_scientific_identity as identity

    monkeypatch.setitem(
        identity.REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS,
        1,
        "0" * 64,
    )
    with pytest.raises(RuntimeError, match="does not match"):
        await certify_research_bundles(conn)
    with pytest.raises(RuntimeError, match="does not match"):
        await certify_final_outcomes(conn)

    assert await conn.fetchval(
        "SELECT count(*) FROM signal_research_bundle_visibility"
    ) == 0
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_outcome_final_visibility"
    ) == 0


def test_visibility_v1_frozen_horizons_are_exact() -> None:
    assert _CERTIFIED_OUTCOME_HORIZONS == (1, 3, 5, 15, 30, 60, 120, 240)


def test_visibility_v1_frozen_exchanges_are_exact() -> None:
    assert _CERTIFIED_EXECUTION_EXCHANGES == ("binance", "bybit")


def test_visibility_v1_frozen_shape_survives_live_constant_monkeypatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A simulated future/current bump of OUTCOME_HORIZONS_MINUTES /
    EXECUTION_EXCHANGES must NOT silently redefine what
    RESEARCH_VISIBILITY_VERSION=1 certifies. app.signal_visibility no longer
    even imports those names -- its bundle-completeness shape is the frozen
    literal tuple below, bound at import time."""

    import app.signal_execution as signal_execution_module
    import app.signal_outcomes as signal_outcomes_module

    monkeypatch.setattr(signal_outcomes_module, "OUTCOME_HORIZONS_MINUTES", (1, 3, 5))
    monkeypatch.setattr(signal_execution_module, "EXECUTION_EXCHANGES", ("okx",))

    assert _CERTIFIED_OUTCOME_HORIZONS == (1, 3, 5, 15, 30, 60, 120, 240)
    assert _CERTIFIED_EXECUTION_EXCHANGES == ("binance", "bybit")
