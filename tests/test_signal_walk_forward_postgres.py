from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_execution import DENSE_PERIODIC
from app.signal_outcomes import OUTCOME_SETTLEMENT_LAG
from app.signal_walk_forward import (
    WalkForwardManifestOptions,
    _actionable_evaluated,
    _build_gross_views,
    _fetch_period_grid,
    _integrity_counters,
    _static_options_spec,
    compute_folds,
    evaluate_walk_forward,
    freeze_walk_forward_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")


def _ddl(marker: str) -> str:
    return SCHEMA_SQL.split(f"-- {marker}_BEGIN", 1)[1].split(f"-- {marker}_END", 1)[0]


LEDGER_DDL = _ddl("PR4_SIGNAL_OBSERVATION_LEDGER")
OUTCOME_DDL = _ddl("PR5_SIGNAL_OUTCOMES")
REPLAY_DDL = _ddl("PR6_SIGNAL_REPLAY")
EXECUTION_DDL = _ddl("PR10_SIGNAL_EXECUTION")
WALK_FORWARD_DDL = _ddl("PR11_SIGNAL_WALK_FORWARD")

BASE_SQL = """
CREATE OR REPLACE FUNCTION finite_float8(value double precision)
RETURNS boolean
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT value NOT IN (
        'NaN'::double precision,
        'Infinity'::double precision,
        '-Infinity'::double precision
    )
$$;

CREATE TABLE symbols (
    symbol text PRIMARY KEY
);

INSERT INTO symbols(symbol) VALUES ('BTCUSDT_PERP.A');

CREATE TABLE metrics_snapshot (
    ts timestamptz NOT NULL,
    symbol text NOT NULL REFERENCES symbols(symbol),
    regime_score double precision,
    regime_label text,
    price_cutoff_at timestamptz,
    metrics_cutoff_at timestamptz,
    PRIMARY KEY(symbol, ts)
);

CREATE TABLE orderbook_depth (
    symbol text NOT NULL REFERENCES symbols(symbol),
    exchange text NOT NULL CHECK (exchange IN ('binance','bybit')),
    ts timestamptz NOT NULL,
    bids jsonb NOT NULL,
    asks jsonb NOT NULL,
    levels integer NOT NULL CHECK (levels >= 0),
    PRIMARY KEY(symbol,exchange)
);
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_signal_walk_forward_{uuid.uuid4().hex}"


async def _connect_schema(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(BASE_SQL)
    await conn.execute(LEDGER_DDL)
    await conn.execute(OUTCOME_DDL)
    await conn.execute(REPLAY_DDL)
    await conn.execute(EXECUTION_DDL)
    await conn.execute(WALK_FORWARD_DDL)
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


@pytest.fixture
async def conn():
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        yield connection
    finally:
        await _drop_schema(connection, schema)


# ---------------------------------------------------------------------------
# Freeze (Stage A)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freeze_creates_manifest_with_future_cutoff(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        manifest = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-future-cutoff-test")
        )

    now = await conn.fetchval("SELECT clock_timestamp()")
    assert manifest["cutoff_at"] > now
    assert manifest["created_at"] < manifest["cutoff_at"]
    assert manifest["reused_existing"] is False
    assert manifest["selection_policy"] == "fixed_kernel_no_selection_v1"

    row = await conn.fetchrow(
        "SELECT count(*) AS n FROM signal_walk_forward_manifest"
    )
    assert row["n"] == 1


@pytest.mark.asyncio
async def test_freeze_same_name_same_spec_is_idempotent(conn: asyncpg.Connection) -> None:
    options = WalkForwardManifestOptions(name="pr11-idempotent-test")
    async with conn.transaction():
        first = await freeze_walk_forward_manifest(conn, options)
    async with conn.transaction():
        second = await freeze_walk_forward_manifest(conn, options)

    assert second["reused_existing"] is True
    assert second["manifest_id"] == first["manifest_id"]
    assert second["manifest_hash"] == first["manifest_hash"]

    count = await conn.fetchval("SELECT count(*) FROM signal_walk_forward_manifest")
    assert count == 1


@pytest.mark.asyncio
async def test_freeze_same_name_different_spec_fails_closed(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-conflict-test", fold_count=4)
        )

    with pytest.raises(ValueError):
        async with conn.transaction():
            await freeze_walk_forward_manifest(
                conn, WalkForwardManifestOptions(name="pr11-conflict-test", fold_count=2)
            )

    count = await conn.fetchval("SELECT count(*) FROM signal_walk_forward_manifest")
    assert count == 1


@pytest.mark.asyncio
async def test_freeze_never_reads_outcome_or_performance_tables(
    conn: asyncpg.Connection,
) -> None:
    """Freeze must succeed identically whether or not outcome/performance
    rows exist, because it is contractually forbidden from reading them."""

    async with conn.transaction():
        without_outcomes = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-no-outcomes-test")
        )
    assert without_outcomes["manifest_id"] is not None


# ---------------------------------------------------------------------------
# Append-only enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manifest_table_rejects_update(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        manifest = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-update-test")
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "UPDATE signal_walk_forward_manifest SET fold_count=99 WHERE manifest_id=$1",
            manifest["manifest_id"],
        )


@pytest.mark.asyncio
async def test_manifest_table_rejects_delete(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        manifest = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-delete-test")
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute(
            "DELETE FROM signal_walk_forward_manifest WHERE manifest_id=$1",
            manifest["manifest_id"],
        )


@pytest.mark.asyncio
async def test_manifest_table_rejects_truncate(conn: asyncpg.Connection) -> None:
    async with conn.transaction():
        await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-truncate-test")
        )
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute("TRUNCATE signal_walk_forward_manifest")


@pytest.mark.asyncio
async def test_schema_deploy_creates_no_manifest(conn: asyncpg.Connection) -> None:
    count = await conn.fetchval("SELECT count(*) FROM signal_walk_forward_manifest")
    assert count == 0


# ---------------------------------------------------------------------------
# Hash verification / tamper detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_fails_closed_on_hash_tamper(conn: asyncpg.Connection) -> None:
    now = await conn.fetchval("SELECT clock_timestamp()")
    cutoff = now + timedelta(days=7)
    spec = {"spec_version": 1, "tampered": True}
    await conn.execute(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version,manifest_name,created_at,cutoff_at,warmup_days,
          test_days,fold_count,min_group_n,selection_policy,manifest_hash,spec
        ) VALUES(1,'pr11-tamper-test',$1,$2,7,7,4,30,
          'fixed_kernel_no_selection_v1',repeat('0',64),$3::jsonb)
        """,
        now,
        cutoff,
        json.dumps(spec),
    )
    with pytest.raises(ValueError):
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            await evaluate_walk_forward(conn, "pr11-tamper-test")


# ---------------------------------------------------------------------------
# Synthetic mature-fold gating scenario
# ---------------------------------------------------------------------------


def _canonical_json(value: object) -> str:
    def default(v: object) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        raise TypeError

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default
    )


async def _insert_backdated_manifest(
    conn: asyncpg.Connection,
    *,
    name: str,
    options: WalkForwardManifestOptions,
    discovery_start: datetime,
    cutoff_at: datetime,
) -> dict:
    """Fixture-only helper for a mature historical fold.

    The stored schedule still obeys the production cutoff formula:
    next_minute(created_at + warmup_days) == cutoff_at.
    """

    created_at = (
        cutoff_at
        - timedelta(days=options.warmup_days)
        - timedelta(seconds=30)
    )
    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=options.test_days,
        fold_count=options.fold_count,
        horizons=options.horizons,
    )
    spec = {
        **_static_options_spec(options),
        "name": name,
        "created_at": created_at,
        "discovery_start": discovery_start,
        "cutoff_at": cutoff_at,
        "folds": folds,
    }
    manifest_hash = hashlib.sha256(
        _canonical_json(spec).encode("utf-8")
    ).hexdigest()

    await conn.execute(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version,manifest_name,created_at,cutoff_at,warmup_days,
          test_days,fold_count,min_group_n,selection_policy,manifest_hash,spec
        ) VALUES(
          1,$1,$2,$3,$4,$5,$6,$7,
          'fixed_kernel_no_selection_v1',$8,$9::jsonb
        )
        """,
        name,
        created_at,
        cutoff_at,
        options.warmup_days,
        options.test_days,
        options.fold_count,
        options.min_group_n,
        manifest_hash,
        _canonical_json(spec),
    )
    return folds[0]

async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    direction: str,
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
              reference_price,reference_price_source,
              long_score,short_score,evidence_coverage_pct,
              regime_label,
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,date_trunc('minute',$1::timestamptz),$5,
              'BTCUSDT_PERP.A','scalp',
              true,false,
              'scalp-summary-v1',1,1,
              'evaluable',$2,true,$3,'media','test',
              $4,'futures_realtime_combined',
              70,30,90,
              'trend_up',
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


async def _insert_outcome(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    window_start: datetime,
    horizon_minutes: int,
    directional_return_pct: float,
    status: str = "evaluated",
    due_at: datetime | None = None,
    outcome_version: int = 1,
    created_at: datetime | None = None,
    finalized_at: datetime | None = None,
) -> None:
    observation = await conn.fetchrow(
        """
        SELECT direction,reference_price
        FROM signal_observation
        WHERE observation_id=$1
        """,
        observation_id,
    )
    assert observation is not None
    direction = observation["direction"]
    reference_price = float(observation["reference_price"])

    market_return_pct = (
        directional_return_pct
        if direction == "long"
        else -directional_return_pct
    )
    end_price = reference_price * (1.0 + market_return_pct / 100.0)

    window_end = window_start + timedelta(minutes=horizon_minutes)
    resolved_due_at = (
        due_at
        if due_at is not None
        else window_end + OUTCOME_SETTLEMENT_LAG
    )
    row_created_at = created_at or window_start - timedelta(minutes=1)
    row_finalized_at = finalized_at or resolved_due_at

    if status == "pending":
        await conn.execute(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
              outcome_version,status,attempts,created_at
            ) VALUES(
              $1,$2,$3,$4,$5,
              $5,30,$2,0,
              $6,'pending',0,$7
            )
            """,
            observation_id,
            horizon_minutes,
            window_start,
            window_end,
            resolved_due_at,
            outcome_version,
            row_created_at,
        )
        return

    if status == "not_evaluable":
        await conn.execute(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
              outcome_version,status,attempts,last_attempt_at,finalized_at,
              final_reason,created_at
            ) VALUES(
              $1,$2,$3,$4,$5,
              $5,30,$2,0,
              $6,'not_evaluable',1,$7,$7,
              'fixture_not_evaluable',$8
            )
            """,
            observation_id,
            horizon_minutes,
            window_start,
            window_end,
            resolved_due_at,
            outcome_version,
            row_finalized_at,
            row_created_at,
        )
        return

    await conn.execute(
        """
        INSERT INTO signal_outcome(
          observation_id,horizon_minutes,window_start,window_end,due_at,
          next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
          outcome_version,status,attempts,last_attempt_at,finalized_at,
          entry_reference_price,end_price,max_high,min_low,
          market_return_pct,up_excursion_pct,down_excursion_pct,
          directional_return_pct,mfe_pct,mae_pct,created_at
        ) VALUES(
          $1,$2,$3,$4,$5,
          $5,30,$2,$2,
          $6,$7,1,$14,$14,
          $8,$9,$10,$11,
          $12,2,-1,
          $13,1.5,0.4,$15
        )
        """,
        observation_id,
        horizon_minutes,
        window_start,
        window_end,
        resolved_due_at,
        outcome_version,
        status,
        reference_price,
        end_price,
        reference_price * 1.02,
        reference_price * 0.99,
        market_return_pct,
        directional_return_pct,
        row_finalized_at,
        row_created_at,
    )

async def _insert_execution_snapshot(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    observed_at: datetime,
    exchange: str,
    status: str = "valid",
) -> None:
    def leg(cost_bps: float, *, side: str, insufficient: bool) -> dict[str, object]:
        if side == "buy":
            avg_price = 100.0 * (1.0 + cost_bps / 10_000.0)
        else:
            avg_price = 100.0 * (1.0 - cost_bps / 10_000.0)
        return {
            "avg_price": avg_price,
            "market_cost_bps_vs_mid": None if insufficient else cost_bps,
            "insufficient_depth": insufficient,
        }

    curve = {
        "1000": {
            "buy": leg(5.0, side="buy", insufficient=False),
            "sell": leg(5.0, side="sell", insufficient=False),
        },
        "10000": {
            "buy": leg(8.0, side="buy", insufficient=False),
            "sell": leg(8.0, side="sell", insufficient=False),
        },
        "50000": {
            "buy": leg(20.0, side="buy", insufficient=True),
            "sell": leg(20.0, side="sell", insufficient=True),
        },
        "100000": {
            "buy": leg(30.0, side="buy", insufficient=True),
            "sell": leg(30.0, side="sell", insufficient=True),
        },
    }
    reason = None if status == "valid" else "fixture_nonvalid"
    await conn.execute(
        """
        INSERT INTO signal_execution_snapshot(
          observation_id,snapshot_version,exchange,captured_at,
          book_ts,book_age_seconds,status,reason,
          levels_reported,bid_levels_valid,ask_levels_valid,
          best_bid_px,best_ask_px,mid_px,spread_bps,
          bid_depth_usd,ask_depth_usd,source_book_hash,cost_curve
        ) VALUES(
          $1,1,$2,$3::timestamptz,
          $3::timestamptz-interval '1 second',1,$4,$5,
          2,2,2,99.9,100.1,100.0,20.0,
          200000,200000,repeat('c',64),$6::jsonb
        )
        """,
        observation_id,
        exchange,
        observed_at,
        status,
        reason,
        json.dumps(curve),
    )


# ---------------------------------------------------------------------------
# PR21 bitemporal knowledge-state projection
# ---------------------------------------------------------------------------


PR21_PERIOD_START = datetime(2026, 1, 2, 11, 0, tzinfo=UTC)
PR21_PERIOD_END = datetime(2026, 1, 2, 14, 0, tzinfo=UTC)
PR21_OBSERVED_AT = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
PR21_CUTOFF = datetime(2026, 1, 2, 12, 30, tzinfo=UTC)
PR21_DUE_AT = datetime(2026, 1, 2, 12, 20, tzinfo=UTC)


async def _pr21_observation_and_frame(
    conn: asyncpg.Connection,
    *,
    observation_created_at: datetime | None = None,
    frame_created_at: datetime | None = None,
) -> int:
    observation_id = await _insert_observation(
        conn,
        observed_at=PR21_OBSERVED_AT,
        direction="long",
        created_at=observation_created_at,
    )
    await _insert_frame(
        conn,
        observation_id,
        PR21_OBSERVED_AT,
        created_at=frame_created_at,
    )
    return observation_id


async def _pr21_grid(
    conn: asyncpg.Connection,
    *,
    cutoff: datetime = PR21_CUTOFF,
    horizons: tuple[int, ...] = (15,),
) -> list[dict]:
    return await _fetch_period_grid(
        conn,
        period_start=PR21_PERIOD_START,
        period_end=PR21_PERIOD_END,
        knowledge_cutoff=cutoff,
        options=WalkForwardManifestOptions(
            fold_count=1,
            horizons=horizons,
            symbols=("BTCUSDT_PERP.A",),
            min_group_n=1,
        ),
    )


@pytest.mark.asyncio
async def test_pr21_discovery_late_finalized_evaluated_projects_to_pending(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=9.0,
        due_at=PR21_DUE_AT,
        finalized_at=PR21_CUTOFF + timedelta(minutes=12),
    )

    row = (await _pr21_grid(conn))[0]
    assert row["usable"] is True
    assert row["status"] == "pending"
    assert row["finalized_at"] is None
    for field in (
        "end_price",
        "directional_return_pct",
        "mfe_pct",
        "mae_pct",
        "market_return_pct",
    ):
        assert row[field] is None


@pytest.mark.asyncio
async def test_pr21_late_not_evaluable_projects_to_pending(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=0.0,
        status="not_evaluable",
        due_at=PR21_DUE_AT,
        finalized_at=PR21_CUTOFF + timedelta(minutes=1),
    )
    row = (await _pr21_grid(conn))[0]
    assert row["usable"] is True
    assert row["status"] == "pending"
    assert row["finalized_at"] is None


@pytest.mark.asyncio
async def test_pr21_finalized_before_cutoff_is_evaluated(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=2.5,
        due_at=PR21_DUE_AT,
        finalized_at=PR21_CUTOFF - timedelta(seconds=1),
    )
    row = (await _pr21_grid(conn))[0]
    assert row["usable"] is True
    assert row["status"] == "evaluated"
    assert row["directional_return_pct"] == pytest.approx(2.5)


@pytest.mark.asyncio
async def test_pr21_finalized_exactly_at_cutoff_is_known(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=3.0,
        due_at=PR21_DUE_AT,
        finalized_at=PR21_CUTOFF,
    )
    row = (await _pr21_grid(conn))[0]
    assert row["usable"] is True
    assert row["status"] == "evaluated"
    assert row["finalized_at"] == PR21_CUTOFF


@pytest.mark.asyncio
async def test_pr21_due_after_cutoff_is_not_knowledge_eligible(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=4.0,
        due_at=PR21_CUTOFF + timedelta(seconds=1),
        finalized_at=PR21_CUTOFF + timedelta(minutes=2),
    )
    row = (await _pr21_grid(conn))[0]
    assert row["status"] == "pending"
    assert row["usable"] is False


@pytest.mark.asyncio
async def test_pr21_outcome_created_after_cutoff_is_not_visible(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=5.0,
        due_at=PR21_DUE_AT,
        created_at=PR21_CUTOFF + timedelta(microseconds=1),
        finalized_at=PR21_CUTOFF + timedelta(minutes=2),
    )
    row = (await _pr21_grid(conn))[0]
    assert row["status"] is None
    assert row["outcome_version"] is None
    assert row["outcome_created_at"] is None
    assert row["usable"] is False


@pytest.mark.asyncio
async def test_pr21_observation_created_after_cutoff_is_not_visible(
    conn: asyncpg.Connection,
) -> None:
    await _pr21_observation_and_frame(
        conn,
        observation_created_at=PR21_CUTOFF + timedelta(microseconds=1),
    )
    assert await _pr21_grid(conn) == []


@pytest.mark.asyncio
async def test_pr21_replay_frame_created_after_cutoff_is_not_visible(
    conn: asyncpg.Connection,
) -> None:
    await _pr21_observation_and_frame(
        conn,
        frame_created_at=PR21_CUTOFF + timedelta(microseconds=1),
    )
    assert await _pr21_grid(conn) == []


@pytest.mark.asyncio
async def test_pr21_integrity_counts_late_final_as_pending(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=7.0,
        due_at=PR21_DUE_AT,
        finalized_at=PR21_CUTOFF + timedelta(minutes=10),
    )
    counters = _integrity_counters(
        await _pr21_grid(conn),
        period_end=PR21_PERIOD_END,
        expected_outcome_version=1,
    )
    assert counters["knowledge_eligible_outcome_rows"] == 1
    assert counters["pending_outcome_rows"] == 1
    assert counters["evaluated_outcome_rows"] == 0
    assert counters["not_evaluable_outcome_rows"] == 0
    assert counters["missing_or_wrong_version_outcome_rows"] == 0


@pytest.mark.asyncio
async def test_pr21_late_final_excluded_from_fold1_metrics_but_available_later(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    finalized_at = PR21_CUTOFF + timedelta(minutes=10)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=8.0,
        due_at=PR21_DUE_AT,
        finalized_at=finalized_at,
    )
    early = await _pr21_grid(conn)
    early_views = _build_gross_views(
        discovery_grid=early,
        test_grid=early,
        min_group_n=1,
        fold_state="ready_by_clock",
    )
    assert _actionable_evaluated(early) == []
    assert early_views["overall"] == []

    later = await _pr21_grid(conn, cutoff=finalized_at)
    assert len(_actionable_evaluated(later)) == 1
    later_views = _build_gross_views(
        discovery_grid=later,
        test_grid=later,
        min_group_n=1,
        fold_state="ready_by_clock",
    )
    assert later_views["overall"][0]["discovery"]["n"] == 1
    assert later_views["overall"][0]["test"]["n"] == 1


@pytest.mark.asyncio
async def test_pr21_multiple_horizons_project_independently(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    cutoff = PR21_CUTOFF + timedelta(minutes=20)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.5,
        due_at=PR21_DUE_AT,
        finalized_at=cutoff - timedelta(seconds=1),
    )
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=30,
        directional_return_pct=30.0,
        due_at=PR21_CUTOFF + timedelta(minutes=10),
        finalized_at=cutoff + timedelta(minutes=10),
    )
    rows = {
        row["horizon_minutes"]: row
        for row in await _pr21_grid(conn, cutoff=cutoff, horizons=(15, 30))
    }
    assert rows[15]["status"] == "evaluated"
    assert rows[15]["directional_return_pct"] == pytest.approx(1.5)
    assert rows[30]["status"] == "pending"
    assert rows[30]["directional_return_pct"] is None


@pytest.mark.asyncio
async def test_pr21_wrong_outcome_version_remains_excluded(
    conn: asyncpg.Connection,
) -> None:
    observation_id = await _pr21_observation_and_frame(conn)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=PR21_OBSERVED_AT + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=6.0,
        due_at=PR21_DUE_AT,
        outcome_version=2,
        finalized_at=PR21_CUTOFF - timedelta(seconds=1),
    )
    row = (await _pr21_grid(conn))[0]
    assert row["status"] == "evaluated"
    assert row["usable"] is False
    counters = _integrity_counters(
        [row], period_end=PR21_PERIOD_END, expected_outcome_version=1
    )
    assert counters["missing_or_wrong_version_outcome_rows"] == 1

@pytest.fixture
def single_fold_options() -> WalkForwardManifestOptions:
    return WalkForwardManifestOptions(
        fold_count=1,
        horizons=(15,),
        symbols=("BTCUSDT_PERP.A",),
    )


@pytest.mark.asyncio
async def test_synthetic_mature_fold_pairs_discovery_and_oos(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-synthetic-mature-fold"
    fold = await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    discovery_end = fold["discovery_end"]
    test_start = fold["test_start"]

    # 1. Legitimate discovery row: comfortably inside discovery, matures
    #    well before discovery_end.
    legit_obs = await _insert_observation(
        conn, observed_at=discovery_end - timedelta(days=2), direction="long"
    )
    await _insert_frame(conn, legit_obs, discovery_end - timedelta(days=2))
    await _insert_outcome(
        conn,
        observation_id=legit_obs,
        window_start=discovery_end - timedelta(days=2) + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=2.0,
    )

    # 2. Spectacular row right at the discovery boundary: its price path
    #    (window_end) finished before discovery_end, but PR5's settlement
    #    gate (window_end + 42m buffer = due_at) had not yet passed at the
    #    discovery cutoff. Rule 5 says it was not knowledge-eligible at the
    #    discovery cutoff, so it must be excluded even though its path never
    #    crossed the boundary.
    late_observed_at = discovery_end - timedelta(minutes=20)
    late_obs = await _insert_observation(conn, observed_at=late_observed_at, direction="long")
    await _insert_frame(conn, late_obs, late_observed_at)
    await _insert_outcome(
        conn,
        observation_id=late_obs,
        window_start=late_observed_at + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=99.0,  # would badly distort expectancy if included
        # default due_at = window_end + 42m settlement lag, which lands
        # after discovery_end even though window_end itself does not.
    )

    # The near-cutoff discovery observation is outcome-ineligible, but it
    # still belongs to the PR10 execution era and must retain its exact
    # Binance+Bybit snapshot cardinality.
    for exchange in ("binance", "bybit"):
        await _insert_execution_snapshot(
            conn,
            observation_id=late_obs,
            observed_at=late_observed_at,
            exchange=exchange,
        )

    # 3. OOS row, well inside the test window.
    oos_obs = await _insert_observation(
        conn, observed_at=test_start + timedelta(days=1), direction="long"
    )
    await _insert_frame(conn, oos_obs, test_start + timedelta(days=1))
    await _insert_outcome(
        conn,
        observation_id=oos_obs,
        window_start=test_start + timedelta(days=1) + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
    )

    for obs_id, ts in ((legit_obs, discovery_end - timedelta(days=2)), (oos_obs, test_start + timedelta(days=1))):
        await _insert_execution_snapshot(conn, observation_id=obs_id, observed_at=ts, exchange="binance")
        await _insert_execution_snapshot(conn, observation_id=obs_id, observed_at=ts, exchange="bybit")

    # Evaluate now; the synthetic fold is anchored in 2020 so it is already
    # far past its test_maturity_at relative to the real database clock.
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    fold_report = report["folds"][0]
    # The evaluation clock is the real DB clock (2026, per lab date), which
    # is already far past this synthetic 2020 fold, so it must be mature.
    assert fold_report["clock_state"] == "ready_by_clock"
    assert fold_report["evaluation_ready"] is True

    overall = fold_report["gross_views"][DENSE_PERIODIC]["overall"]
    matching = [row for row in overall if row["horizon_minutes"] == 15]
    assert matching, "expected an overall/15m row"
    row = matching[0]

    # The late/near-boundary row must be excluded: discovery n stays at 1,
    # not 2, and expectancy is exactly the legitimate row's return.
    assert row["discovery"]["n"] == 1
    assert row["discovery"]["expectancy_gross_pct"] == pytest.approx(2.0)
    assert row["test"]["n"] == 1
    assert row["test"]["expectancy_gross_pct"] == pytest.approx(1.0)
    # Both discovery and test expectancy are positive (sign-consistent), but
    # n=1 is below the default min_group_n=30 reporting guardrail, so the
    # label must be the sample-size gate rather than a generalization claim.
    assert row["label"] == "insufficient_sample"
    assert row["sign_preserved"] is True

    execution_rows = fold_report["execution_views"][DENSE_PERIODIC]
    binance_1k = [
        r
        for r in execution_rows
        if r["exchange"] == "binance" and r["size_usd"] == 1000.0 and r["horizon_minutes"] == 15
    ]
    assert binance_1k, "expected a binance/1000usd/15m execution row"
    exec_row = binance_1k[0]
    assert exec_row["discovery"]["n_cost_evaluable"] == 1
    assert exec_row["test"]["n_cost_evaluable"] == 1
    # PR10-equivalent math: frozen venue entry fill + PR5 end price,
    # with the symmetric modeled exit cost. Do not use gross - 2*cost.
    expected = (
        (102.0 * (1.0 - 5.0 / 10_000.0)) / 100.05 - 1.0
    ) * 10_000.0
    assert exec_row["discovery"][
        "symmetric_market_net_expectancy_bps"
    ] == pytest.approx(expected)


@pytest.mark.asyncio
async def test_future_fold_cannot_pass_oos_gate(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    async with conn.transaction():
        manifest = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-future-fold-gate", fold_count=1)
        )
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, manifest["manifest_name"])

    fold = report["folds"][0]
    assert fold["evaluation_ready"] is False
    assert fold["state"] in ("discovery_collecting", "test_collecting", "test_settling")
    assert report["ready_by_clock_fold_count"] == 0
    assert report["evaluation_ready_fold_count"] == 0


@pytest.mark.asyncio
async def test_outcome_recovery_pending_blocks_ready_by_clock(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-recovery-pending-fold"
    fold = await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    test_start = fold["test_start"]
    pending_obs = await _insert_observation(
        conn, observed_at=test_start + timedelta(hours=1), direction="long"
    )
    await _insert_frame(conn, pending_obs, test_start + timedelta(hours=1))
    await _insert_outcome(
        conn,
        observation_id=pending_obs,
        window_start=test_start + timedelta(hours=1, minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
        status="pending",
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    fold_report = report["folds"][0]
    assert fold_report["clock_state"] == "ready_by_clock"
    assert fold_report["state"] == "outcome_recovery_pending"
    assert fold_report["evaluation_ready"] is False


@pytest.mark.asyncio
async def test_execution_view_never_reads_current_orderbook_depth(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    """No row is ever written to orderbook_depth in this test; the execution
    view must still work purely off the frozen PR10 snapshot table."""

    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-execution-immutable-source"
    fold = await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    test_start = fold["test_start"]
    obs = await _insert_observation(conn, observed_at=test_start + timedelta(hours=1), direction="long")
    await _insert_frame(conn, obs, test_start + timedelta(hours=1))
    await _insert_outcome(
        conn,
        observation_id=obs,
        window_start=test_start + timedelta(hours=1, minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
    )
    await _insert_execution_snapshot(conn, observation_id=obs, observed_at=test_start + timedelta(hours=1), exchange="binance")
    await _insert_execution_snapshot(conn, observation_id=obs, observed_at=test_start + timedelta(hours=1), exchange="bybit")

    orderbook_rows = await conn.fetchval("SELECT count(*) FROM orderbook_depth")
    assert orderbook_rows == 0

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    execution_rows = report["folds"][0]["execution_views"][DENSE_PERIODIC]
    assert any(r["test"]["n_cost_evaluable"] >= 1 for r in execution_rows)


@pytest.mark.asyncio
async def test_no_fee_adjusted_metric_without_a_frozen_fee(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-no-fee-default"
    await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,  # fee_bps_per_side is empty by default
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    for row in report["folds"][0]["execution_views"][DENSE_PERIODIC]:
        assert row["fee_bps_per_side_applied"] is None


@pytest.mark.asyncio
async def test_evaluator_performs_no_writes(
    conn: asyncpg.Connection, single_fold_options: WalkForwardManifestOptions
) -> None:
    async with conn.transaction():
        manifest = await freeze_walk_forward_manifest(
            conn, WalkForwardManifestOptions(name="pr11-read-only-test")
        )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        await evaluate_walk_forward(conn, manifest["manifest_name"])
        with pytest.raises(asyncpg.PostgresError):
            await conn.execute("INSERT INTO symbols(symbol) VALUES('SHOULD_FAIL_PERP.A')")


@pytest.mark.asyncio
async def test_wrong_outcome_version_blocks_mature_fold(
    conn: asyncpg.Connection,
    single_fold_options: WalkForwardManifestOptions,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-wrong-outcome-version"
    fold = await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    observed_at = fold["discovery_end"] - timedelta(days=2)
    observation_id = await _insert_observation(
        conn,
        observed_at=observed_at,
        direction="long",
    )
    await _insert_frame(conn, observation_id, observed_at)
    await _insert_outcome(
        conn,
        observation_id=observation_id,
        window_start=observed_at + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
        outcome_version=2,
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    fold_report = report["folds"][0]
    assert fold_report["clock_state"] == "ready_by_clock"
    assert fold_report["state"] == "integrity_blocked"
    assert fold_report["evaluation_ready"] is False
    assert (
        fold_report["integrity"]["discovery"][
            "missing_or_wrong_version_outcome_rows"
        ]
        == 1
    )
    assert report["gates"]["positive_oos_gate_count"] == 0
    assert report["gates"]["positive_execution_oos_gate_count"] == 0


@pytest.mark.asyncio
async def test_execution_era_missing_second_venue_blocks_mature_fold(
    conn: asyncpg.Connection,
    single_fold_options: WalkForwardManifestOptions,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    name = "pr11-execution-cardinality-block"
    fold = await _insert_backdated_manifest(
        conn,
        name=name,
        options=single_fold_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    discovery_at = fold["discovery_end"] - timedelta(days=2)
    discovery_obs = await _insert_observation(
        conn,
        observed_at=discovery_at,
        direction="long",
    )
    await _insert_frame(conn, discovery_obs, discovery_at)
    await _insert_outcome(
        conn,
        observation_id=discovery_obs,
        window_start=discovery_at + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
    )
    for exchange in ("binance", "bybit"):
        await _insert_execution_snapshot(
            conn,
            observation_id=discovery_obs,
            observed_at=discovery_at,
            exchange=exchange,
        )

    test_at = fold["test_start"] + timedelta(days=1)
    test_obs = await _insert_observation(
        conn,
        observed_at=test_at,
        direction="long",
    )
    await _insert_frame(conn, test_obs, test_at)
    await _insert_outcome(
        conn,
        observation_id=test_obs,
        window_start=test_at + timedelta(minutes=1),
        horizon_minutes=15,
        directional_return_pct=1.0,
    )
    await _insert_execution_snapshot(
        conn,
        observation_id=test_obs,
        observed_at=test_at,
        exchange="binance",
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, name)

    fold_report = report["folds"][0]
    assert fold_report["state"] == "integrity_blocked"
    assert fold_report["evaluation_ready"] is False
    execution_integrity = fold_report["integrity"]["execution"]
    assert (
        execution_integrity[
            "execution_snapshot_cardinality_or_version_anomalies"
        ]
        == 1
    )
    assert (
        execution_integrity["execution_era_observations_without_two_snapshots"]
        == 1
    )
    assert report["gates"]["positive_oos_gate_count"] == 0


@pytest.mark.asyncio
async def test_frozen_fee_scenario_is_applied_only_to_matching_venue(
    conn: asyncpg.Connection,
) -> None:
    options = WalkForwardManifestOptions(
        name="pr11-fee-scenario",
        fold_count=1,
        horizons=(15,),
        symbols=("BTCUSDT_PERP.A",),
        min_group_n=1,
        fee_bps_per_side=(("binance", 2.5),),
    )
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)
    fold = await _insert_backdated_manifest(
        conn,
        name=options.name,
        options=options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    pairs = (
        (fold["discovery_end"] - timedelta(days=2), 2.0),
        (fold["test_start"] + timedelta(days=1), 1.0),
    )
    for observed_at, directional_return_pct in pairs:
        observation_id = await _insert_observation(
            conn,
            observed_at=observed_at,
            direction="long",
        )
        await _insert_frame(conn, observation_id, observed_at)
        await _insert_outcome(
            conn,
            observation_id=observation_id,
            window_start=observed_at + timedelta(minutes=1),
            horizon_minutes=15,
            directional_return_pct=directional_return_pct,
        )
        for exchange in ("binance", "bybit"):
            await _insert_execution_snapshot(
                conn,
                observation_id=observation_id,
                observed_at=observed_at,
                exchange=exchange,
            )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    dense = report["folds"][0]["execution_views"][DENSE_PERIODIC]
    binance = next(
        row
        for row in dense
        if row["exchange"] == "binance"
        and row["size_usd"] == 1000.0
        and row["horizon_minutes"] == 15
    )
    bybit = next(
        row
        for row in dense
        if row["exchange"] == "bybit"
        and row["size_usd"] == 1000.0
        and row["horizon_minutes"] == 15
    )

    assert binance["fee_bps_per_side_applied"] == pytest.approx(2.5)
    assert binance["discovery"]["modeled_net_after_fees_n"] == 1
    assert binance["test"]["modeled_net_after_fees_n"] == 1
    assert (
        binance["discovery"]["modeled_net_after_fees_expectancy_bps"]
        == pytest.approx(
            binance["discovery"]["symmetric_market_net_expectancy_bps"] - 5.0
        )
    )

    assert bybit["fee_bps_per_side_applied"] is None
    assert bybit["discovery"]["modeled_net_after_fees_n"] == 0
    assert bybit["test"]["modeled_net_after_fees_n"] == 0
    assert bybit["discovery"]["modeled_net_after_fees_expectancy_bps"] is None


@pytest.mark.asyncio
async def test_schedule_tamper_with_valid_hash_still_fails_closed(
    conn: asyncpg.Connection,
) -> None:
    now = await conn.fetchval("SELECT clock_timestamp()")
    options = WalkForwardManifestOptions(
        name="pr11-invalid-schedule",
        fold_count=1,
        horizons=(15,),
    )
    created_at = now - timedelta(days=30)
    # Deliberately violates next_minute(created_at + warmup_days).
    cutoff_at = created_at + timedelta(days=8)
    discovery_start = created_at - timedelta(days=1)
    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=options.test_days,
        fold_count=options.fold_count,
        horizons=options.horizons,
    )
    spec = {
        **_static_options_spec(options),
        "name": options.name,
        "created_at": created_at,
        "discovery_start": discovery_start,
        "cutoff_at": cutoff_at,
        "folds": folds,
    }
    manifest_hash = hashlib.sha256(
        _canonical_json(spec).encode("utf-8")
    ).hexdigest()

    await conn.execute(
        """
        INSERT INTO signal_walk_forward_manifest(
          manifest_version,manifest_name,created_at,cutoff_at,warmup_days,
          test_days,fold_count,min_group_n,selection_policy,manifest_hash,spec
        ) VALUES(
          1,$1,$2,$3,$4,$5,$6,$7,
          'fixed_kernel_no_selection_v1',$8,$9::jsonb
        )
        """,
        options.name,
        created_at,
        cutoff_at,
        options.warmup_days,
        options.test_days,
        options.fold_count,
        options.min_group_n,
        manifest_hash,
        _canonical_json(spec),
    )

    with pytest.raises(ValueError, match="prospective cutoff"):
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            await evaluate_walk_forward(conn, options.name)
