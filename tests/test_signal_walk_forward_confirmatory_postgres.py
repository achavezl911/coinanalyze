"""PR26 spec v3 and PR27 spec v4: real PostgreSQL 17 end-to-end tests.

Follows this project's established convention (see
tests/test_signal_walk_forward_postgres.py, tests/test_pr25_research_knowledge_time_postgres.py):
no conftest.py, local per-file fixtures, a fresh uuid-suffixed schema per
test, TEST_DATABASE_URL required (tests skip cleanly without it).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.scalp_logic import compute_scalp_summary
from app.signal_confirmatory import ConfirmatoryContract, confirmatory_block_key
from app.signal_confirmatory_v2 import (
    CONJUNCTIVE_DECISION_POLICY_V2,
    ConfirmatoryContractV2,
)
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG, outcome_window
from app.signal_replay import (
    SCALP_SIGNAL_LOGIC_VERSION,
    canonical_json_hash,
    canonical_json_object,
    classify_signal_observation,
    replay_context_as_of,
)
from app.signal_runtime_contract import (
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    scientific_runtime_contract,
)
from app.signal_visibility import certify_final_outcomes, certify_research_bundles
from app.signal_walk_forward import (
    WALK_FORWARD_REPORT_VERSION_V3,
    WALK_FORWARD_SPEC_VERSION_V3,
    WALK_FORWARD_SPEC_VERSION_V4,
    ConfirmatoryReproducibilityError,
    ConfirmatoryScientificIntegrityError,
    WalkForwardManifestOptions,
    _expected_utc_nonoverlap_slot_count,
    _full_spec,
    compute_folds,
    evaluate_walk_forward,
    evaluate_walk_forward_authoritative,
    freeze_walk_forward_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")
PR27_MIGRATION_SQL = (
    ROOT / "sql/migrations/20260816_pr27_confirmatory_integrity.sql"
).read_text(encoding="utf-8")
PR27_R03_MIGRATION_SQL = (
    ROOT / "sql/migrations/20260817_pr27_r03_runtime_contract.sql"
).read_text(encoding="utf-8")
# Evidence produced under the registered routing.  An adversarial test passes a
# different digest, or None/None, to model evidence produced under routing B.
_REGISTERED_RUNTIME_CONTRACT_DIGEST = scientific_runtime_contract()["digest"]


def _ddl(marker: str) -> str:
    return SCHEMA_SQL.split(f"-- {marker}_BEGIN", 1)[1].split(f"-- {marker}_END", 1)[0]


LEDGER_DDL = _ddl("PR4_SIGNAL_OBSERVATION_LEDGER")
OUTCOME_DDL = _ddl("PR5_SIGNAL_OUTCOMES")
REPLAY_DDL = _ddl("PR6_SIGNAL_REPLAY")
EXECUTION_DDL = _ddl("PR10_SIGNAL_EXECUTION")
WALK_FORWARD_DDL = _ddl("PR11_SIGNAL_WALK_FORWARD")
BUNDLE_VISIBILITY_DDL = _ddl("PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY")
FINAL_VISIBILITY_DDL = _ddl("PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY")
AUTHORITATIVE_RESULT_DDL = _ddl("PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT")

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
    regime_logic_version smallint,
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
    return f"test_signal_walk_forward_confirmatory_{uuid.uuid4().hex}"


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
    await conn.execute(BUNDLE_VISIBILITY_DDL)
    await conn.execute(FINAL_VISIBILITY_DDL)
    await conn.execute(AUTHORITATIVE_RESULT_DDL)
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


@pytest.mark.asyncio
async def test_pr27_forward_migration_applies_idempotently_on_legacy_schema() -> None:
    schema = _schema_name()
    connection = await asyncpg.connect(_dsn())
    try:
        await connection.execute(f'CREATE SCHEMA "{schema}"')
        await connection.execute(f'SET search_path TO "{schema}", public')
        await connection.execute("SET TIME ZONE 'UTC'")
        resolved_schema = await connection.fetchval("SELECT current_schema()")
        await connection.execute(BASE_SQL)
        await connection.execute(LEDGER_DDL)
        await connection.execute(OUTCOME_DDL)
        await connection.execute(REPLAY_DDL)
        await connection.execute(EXECUTION_DDL)
        await connection.execute(WALK_FORWARD_DDL)
        await connection.execute(BUNDLE_VISIBILITY_DDL)
        await connection.execute(FINAL_VISIBILITY_DDL)

        assert await connection.fetchval(
            "SELECT to_regclass($1)",
            f"{resolved_schema}.signal_walk_forward_confirmatory_result",
        ) is None
        await connection.execute(PR27_MIGRATION_SQL)
        await connection.execute(PR27_MIGRATION_SQL)
        # PR27-R03 stacks on top and must be a no-op on a schema the PR27
        # migration already created with the runtime contract column.
        await connection.execute(PR27_R03_MIGRATION_SQL)
        columns = await connection.fetch(
            """
            SELECT column_name,data_type
            FROM information_schema.columns
            WHERE table_schema=$1
              AND table_name='signal_walk_forward_confirmatory_result'
            ORDER BY ordinal_position
            """,
            resolved_schema,
        )
        assert [(row["column_name"], row["data_type"]) for row in columns] == [
            ("result_id", "bigint"),
            ("result_version", "smallint"),
            ("manifest_id", "bigint"),
            ("manifest_hash", "text"),
            ("scientific_implementation_digest", "text"),
            ("scientific_runtime_contract_digest", "text"),
            ("confirmatory_knowledge_cutoff", "timestamp with time zone"),
            ("evaluation_not_before", "timestamp with time zone"),
            ("evaluated_at", "timestamp with time zone"),
            ("canonical_result_json", "text"),
            ("result_hash", "text"),
        ]
    finally:
        await _drop_schema(connection, schema)


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
) -> list[dict]:
    """Fixture-only helper: freeze a manifest whose schedule already sits at
    an arbitrary point in the past/future relative to the real DB clock,
    while still obeying the production cutoff formula."""

    created_at = cutoff_at - timedelta(days=options.warmup_days) - timedelta(seconds=30)
    folds = compute_folds(
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        test_days=options.test_days,
        fold_count=options.fold_count,
        horizons=options.horizons,
    )
    spec = _full_spec(
        options,
        created_at=created_at,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
        folds=folds,
    )
    manifest_hash = hashlib.sha256(_canonical_json(spec).encode("utf-8")).hexdigest()

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
    return folds


def _decision_replay_fixture(
    observed_at: datetime,
    direction: str,
) -> tuple[dict[str, object], dict[str, object]]:
    now_ms = observed_at.timestamp() * 1000.0
    context: dict[str, object] = {
        "now_ms": now_ms,
        "price": 100.0,
        "ohlcv_price": 99.9,
        "fut_price": 100.0,
        "spot_price": 99.9,
        "fut_event_ms": now_ms - 1_000.0,
        "spot_event_ms": now_ms - 1_200.0,
        "fut_delta_1m": 100.0,
        "fut_volume_1m": 1_000.0,
        "fut_delta_3m": 150.0,
        "fut_volume_3m": 3_000.0,
        "spot_delta_3m": 50.0,
        "spot_volume_3m": 2_000.0,
        "imbalance_l1": 0.05,
        "imbalance_l5": 0.10,
        "imbalance_l10": 0.08,
        "spread_bps": 1.5,
        "book_status": "ok",
        "book_lag_seconds": 1.0,
        "first_px_3m": 99.8,
        "last_px_3m": 100.0,
        "bars_15m": 0,
        "price_move_15m_coverage": "none",
        "oi_window_status": "unavailable",
        "optional": None,
    }
    if direction == "long":
        context.update(
            {
                "fut_delta_1m": -100.0,
                "fut_delta_3m": -150.0,
                "spot_delta_3m": 100.0,
                "imbalance_l5": 0.9,
                "first_px_3m": 100.2,
                "last_px_3m": 100.0,
            }
        )
    elif direction == "neutral":
        context.update(
            {
                "fut_delta_1m": 0.0,
                "fut_delta_3m": 0.0,
                "spot_delta_3m": 0.0,
                "imbalance_l5": 0.5,
                "first_px_3m": 100.0,
                "last_px_3m": 100.0,
            }
        )
    elif direction != "short":
        raise ValueError(f"unsupported fixture replay direction: {direction}")

    summary = compute_scalp_summary(context)
    _, replayed_direction, _ = classify_signal_observation(summary)
    assert replayed_direction == direction
    return context, summary


async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    direction: str,
    reference_price: float = 100.0,
    evidence_version: int = 6,
    actionable: bool | None = None,
    state: str | None = None,
    regime_label: str = "trend_up",
    replay_direction: str | None = None,
    evidence_overrides: dict[str, object] | None = None,
    runtime_contract_version: int | None = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    runtime_contract_digest: str | None = _REGISTERED_RUNTIME_CONTRACT_DIGEST,
) -> tuple[int, dict[str, object]]:
    """``direction`` may be ``"long"``/``"short"`` (actionable) or
    ``"neutral"`` (non-actionable, periodic-only) -- the latter is how
    PR26's confirmatory baseline cohort fixtures insert rows that must be
    evaluated but must never become an actionable primary row. ``actionable``
    and ``state`` default from ``direction`` but can be overridden
    independently (e.g. to prove the baseline cohort is insensitive to
    ``state``/``regime_label``)."""

    replay_context, replayed_summary = _decision_replay_fixture(
        observed_at,
        replay_direction or direction,
    )
    evidence = {**replayed_summary, **(evidence_overrides or {})}
    if actionable is None:
        actionable = direction in ("long", "short")
    if state is None:
        state = str(evidence["state"])
    observation_id = int(
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
              decision_fingerprint,evidence,
              runtime_contract_version,runtime_contract_digest
            ) VALUES(
              $1,date_trunc('minute',$1::timestamptz),$1,
              'BTCUSDT_PERP.A','scalp',
              true,false,
              'scalp-summary-v1',$3,1,
              'evaluable',$2,$5,$6,$8,$9,
              $4,'futures_realtime_combined',
              $10,$11,$12,
              $7,
              0,1,
              repeat('a',64),$13::jsonb,
              $14,$15
            )
            RETURNING observation_id
            """,
            observed_at,
            direction,
            evidence_version,
            reference_price,
            actionable,
            state,
            regime_label,
            str(evidence["confidence"]),
            str(evidence["reason"]),
            float(evidence["long_score"]),
            float(evidence["short_score"]),
            float(evidence["evidence_coverage_pct"]),
            canonical_json_object(evidence),
            runtime_contract_version,
            runtime_contract_digest,
        )
    )
    return observation_id, replay_context


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    context: dict[str, object],
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context,created_at
        ) VALUES($1,1,$2,$3,$4::jsonb,$5)
        """,
        observation_id,
        replay_context_as_of(context),
        canonical_json_hash(context),
        canonical_json_object(context),
        observed_at,
    )


async def _insert_outcome(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    window_start: datetime,
    horizon_minutes: int,
    directional_return_pct: float,
    status: str = "evaluated",
    outcome_end_price: float | None = None,
) -> None:
    observation = await conn.fetchrow(
        "SELECT direction,reference_price FROM signal_observation WHERE observation_id=$1",
        observation_id,
    )
    assert observation is not None
    direction = observation["direction"]
    reference_price = float(observation["reference_price"])

    # "long"/"neutral" apply no sign flip (a neutral row has no directional
    # convention of its own, so its market_return_pct is just the supplied
    # value directly); "short" flips it, matching the live sign convention
    # PR5 applies for a short signal.
    market_return_pct = (
        directional_return_pct
        if direction in ("long", "neutral")
        else -directional_return_pct
    )
    end_price = (
        reference_price * (1.0 + market_return_pct / 100.0)
        if outcome_end_price is None
        else outcome_end_price
    )
    window_end = window_start + timedelta(minutes=horizon_minutes)
    due_at = window_end + OUTCOME_SETTLEMENT_LAG
    row_created_at = window_start - timedelta(minutes=1)

    if status == "pending":
        await conn.execute(
            """
            INSERT INTO signal_outcome(
              observation_id,horizon_minutes,window_start,window_end,due_at,
              next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
              outcome_version,status,attempts,created_at
            ) VALUES($1,$2,$3,$4,$5,$5,30,$2,0,1,'pending',0,$6)
            """,
            observation_id,
            horizon_minutes,
            window_start,
            window_end,
            due_at,
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
              1,'not_evaluable',1,$5,$5,
              'fixture_not_evaluable',$6
            )
            """,
            observation_id,
            horizon_minutes,
            window_start,
            window_end,
            due_at,
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
          1,'evaluated',1,$5,$5,
          $6,$7,$8,$9,
          $10,2,-1,
          $10,1.5,0.4,$11
        )
        """,
        observation_id,
        horizon_minutes,
        window_start,
        window_end,
        due_at,
        reference_price,
        end_price,
        max(reference_price, end_price) * 1.02,
        min(reference_price, end_price) * 0.98,
        market_return_pct,
        row_created_at,
    )


async def _insert_execution_snapshot(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    observed_at: datetime,
    exchange: str,
    status: str = "valid",
    cost_bps: float = 5.0,
) -> None:
    def leg(*, side: str, insufficient: bool) -> dict[str, object]:
        if side == "buy":
            avg_price = 100.0 * (1.0 + cost_bps / 10_000.0)
        else:
            avg_price = 100.0 * (1.0 - cost_bps / 10_000.0)
        return {
            "avg_price": avg_price,
            "market_cost_bps_vs_mid": None if insufficient else cost_bps,
            "insufficient_depth": insufficient,
        }

    curve = (
        {
            str(int(size)): {
                "buy": leg(side="buy", insufficient=False),
                "sell": leg(side="sell", insufficient=False),
            }
            for size in (1_000, 10_000, 50_000, 100_000)
        }
        if status == "valid"
        else {}
    )
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


async def _insert_confirmatory_bundle(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    directional_return_pct: float,
    primary_horizon: int = 15,
    both_venues: bool = True,
    snapshot_status: str = "valid",
    direction: str = "long",
    state: str | None = None,
    regime_label: str = "trend_up",
    reference_price: float = 100.0,
    snapshot_cost_bps: float = 5.0,
    outcome_end_price: float | None = None,
    replay_direction: str | None = None,
    evidence_overrides: dict[str, object] | None = None,
    actionable: bool | None = None,
    runtime_contract_version: int | None = SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    runtime_contract_digest: str | None = _REGISTERED_RUNTIME_CONTRACT_DIGEST,
) -> int:
    """A complete evidence_version=6 bundle: one observation, replay frame,
    all 8 outcome horizons (only ``primary_horizon`` evaluated with a real
    return; the rest pending placeholders, matching the certification
    completeness requirement), and execution snapshots for both venues.

    ``direction`` defaults to ``"long"`` (an actionable primary row) but may
    be ``"short"`` (actionable, opposite side) or ``"neutral"`` (a
    non-actionable periodic row -- used to build a confirmatory baseline
    cohort observation distinct from the actionable primary rows). For
    ``"neutral"`` rows, ``directional_return_pct`` is applied with no sign
    flip -- see ``_insert_outcome`` -- i.e. it directly sets that row's
    ``market_return_pct``."""

    observation_id, replay_context = await _insert_observation(
        conn,
        observed_at=observed_at,
        direction=direction,
        state=state,
        regime_label=regime_label,
        reference_price=reference_price,
        replay_direction=replay_direction,
        evidence_overrides=evidence_overrides,
        actionable=actionable,
        runtime_contract_version=runtime_contract_version,
        runtime_contract_digest=runtime_contract_digest,
    )
    await _insert_frame(conn, observation_id, observed_at, replay_context)

    window_start = observed_at + timedelta(minutes=1)
    for horizon in OUTCOME_HORIZONS_MINUTES:
        if horizon == primary_horizon:
            await _insert_outcome(
                conn,
                observation_id=observation_id,
                window_start=window_start,
                horizon_minutes=horizon,
                directional_return_pct=directional_return_pct,
                outcome_end_price=outcome_end_price,
            )
        else:
            await _insert_outcome(
                conn,
                observation_id=observation_id,
                window_start=window_start,
                horizon_minutes=horizon,
                directional_return_pct=0.0,
                status="pending",
            )

    await _insert_execution_snapshot(
        conn,
        observation_id=observation_id,
        observed_at=observed_at,
        exchange="binance",
        status=snapshot_status,
        cost_bps=snapshot_cost_bps,
    )
    if both_venues:
        await _insert_execution_snapshot(
            conn,
            observation_id=observation_id,
            observed_at=observed_at,
            exchange="bybit",
            cost_bps=snapshot_cost_bps,
        )
    return observation_id


async def _insert_confirmatory_bundle_with_primary_status(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    primary_status: str,
    primary_horizon: int = 15,
    direction: str = "long",
) -> tuple[int, int]:
    """A4-08 fixture: like ``_insert_confirmatory_bundle``, but the PRIMARY
    horizon's own outcome row is left ``pending``/``not_evaluable`` instead
    of evaluated. The bundle is still fully complete (all 8 horizon rows
    present, both execution venues present), so it IS certifiable and
    grid-visible -- only its outcome is unresolved. Returns
    ``(observation_id, horizon_minutes)`` for later use with
    ``_finalize_pending_outcome``.
    """

    observation_id, replay_context = await _insert_observation(
        conn,
        observed_at=observed_at,
        direction=direction,
    )
    await _insert_frame(conn, observation_id, observed_at, replay_context)

    window_start = observed_at + timedelta(minutes=1)
    for horizon in OUTCOME_HORIZONS_MINUTES:
        await _insert_outcome(
            conn,
            observation_id=observation_id,
            window_start=window_start,
            horizon_minutes=horizon,
            directional_return_pct=0.0,
            status=primary_status if horizon == primary_horizon else "pending",
        )

    await _insert_execution_snapshot(
        conn, observation_id=observation_id, observed_at=observed_at, exchange="binance"
    )
    await _insert_execution_snapshot(
        conn, observation_id=observation_id, observed_at=observed_at, exchange="bybit"
    )
    return observation_id, primary_horizon


async def _finalize_pending_outcome(
    conn: asyncpg.Connection,
    *,
    observation_id: int,
    horizon_minutes: int,
    directional_return_pct: float,
) -> None:
    """A4-08 late-recovery fixture: transitions a still-``pending``
    ``signal_outcome`` row to ``evaluated`` well after it was originally
    inserted. ``signal_outcome_guard_update_delete`` permits this (it only
    forbids mutating a row whose OLD.status is already final), matching how
    a real late-arriving outcome would be finalized in production."""

    observation = await conn.fetchrow(
        "SELECT direction,reference_price FROM signal_observation WHERE observation_id=$1",
        observation_id,
    )
    assert observation is not None
    direction = observation["direction"]
    reference_price = float(observation["reference_price"])
    market_return_pct = (
        directional_return_pct if direction in ("long", "neutral") else -directional_return_pct
    )
    end_price = reference_price * (1.0 + market_return_pct / 100.0)
    finalized_at = await conn.fetchval("SELECT clock_timestamp()")

    await conn.execute(
        """
        UPDATE signal_outcome
        SET status='evaluated', attempts=attempts+1, last_attempt_at=$3,
            finalized_at=$3, bars_found=bars_expected,
            entry_reference_price=$4, end_price=$5,
            max_high=$6, min_low=$7,
            market_return_pct=$8, up_excursion_pct=2, down_excursion_pct=-1,
            directional_return_pct=$8, mfe_pct=1.5, mae_pct=0.4
        WHERE observation_id=$1 AND horizon_minutes=$2
        """,
        observation_id,
        horizon_minutes,
        finalized_at,
        reference_price,
        end_price,
        max(reference_price, end_price) * 1.02,
        min(reference_price, end_price) * 0.98,
        market_return_pct,
    )


def _enumerate_expected_slots(fold: dict, *, horizon_minutes: int) -> list[datetime]:
    """Test-only enumeration of the exact deterministic ``utc_nonoverlap``
    slot timestamps ``_expected_utc_nonoverlap_slot_count`` counts for one
    fold -- used to place bundles at KNOWN slot positions and to omit others
    by construction, and to independently cross-check the deterministic
    count end-to-end through the real database."""

    candidate = _align_forward(fold["test_start"], minutes=horizon_minutes)
    slots: list[datetime] = []
    while candidate < fold["test_end"]:
        if outcome_window(candidate, horizon_minutes).end <= fold["test_end"]:
            slots.append(candidate)
        candidate += timedelta(minutes=horizon_minutes)
    return slots


def _confirmatory_contract(**overrides: object) -> ConfirmatoryContract:
    fields: dict[str, object] = {
        "primary_endpoint_version": 1,
        "primary_symbol": "BTCUSDT_PERP.A",
        "primary_horizon_minutes": 15,
        "primary_sampling_mode": "utc_nonoverlap",
        "primary_exchange": "binance",
        "primary_size_usd": 1_000.0,
        "primary_taker_fee_bps": 0.0,
        "baseline_version": 1,
        "unmodeled_execution_stress_bps": 0.0,
        "inference_version": 1,
        "block_unit": "day",
        "block_length": 1,
        "bootstrap_repetitions": 500,
        "bootstrap_seed": 42,
        "confidence_level": 0.95,
        "minimum_effect_bps": 100.0,
        "minimum_primary_blocks": 5,
        "minimum_execution_data_coverage_pct": 50.0,
        # A4-08: intentionally near-zero. research_data_coverage_pct is a
        # DENSE ratio (every deterministic utc_nonoverlap slot across the
        # whole fold window, not just the handful of bundles a given fixture
        # inserts), so any fixture that isn't specifically exercising this
        # gate would otherwise trip it by construction. There is no
        # production default (TASK.md: chosen at pre-freeze calibration
        # time) -- this is a test-only no-op floor. Tests that DO exercise
        # this gate override it explicitly.
        "minimum_research_data_coverage_pct": 0.0001,
        "confirmatory_decision_policy": "two_sided_block_bootstrap_ci_vs_minimum_effect_v1",
    }
    fields.update(overrides)
    return ConfirmatoryContract(**fields)


def _v3_options(*, name: str, contract: ConfirmatoryContract, **overrides: object) -> WalkForwardManifestOptions:
    fields: dict[str, object] = {
        "name": name,
        "warmup_days": 1,
        "test_days": 10,
        "fold_count": 1,
        "min_group_n": 1,
        "horizons": (15,),
        "symbols": ("BTCUSDT_PERP.A",),
        "logic_version": SCALP_SIGNAL_LOGIC_VERSION,
        "evidence_version": 6,
        "sampling_version": 1,
        "context_version": 1,
        "outcome_version": 1,
        "execution_snapshot_version": 1,
        "spec_version": WALK_FORWARD_SPEC_VERSION_V3,
        "research_visibility_version": 1,
        "fee_bps_per_side": (("binance", contract.primary_taker_fee_bps),),
        "confirmatory_contract": contract,
    }
    fields.update(overrides)
    return WalkForwardManifestOptions(**fields)


def _confirmatory_contract_v2(**overrides: object) -> ConfirmatoryContractV2:
    fields: dict[str, object] = {
        "primary_endpoint_version": 2,
        "primary_symbol": "BTCUSDT_PERP.A",
        "primary_horizon_minutes": 15,
        "primary_sampling_mode": "utc_nonoverlap",
        "primary_exchange": "binance",
        "outcome_price_venue": "binance",
        "primary_size_usd": 1_000.0,
        "primary_taker_fee_bps": 0.0,
        "baseline_version": 2,
        "unmodeled_execution_stress_bps": 0.0,
        "funding_semantics": "excluded_v1",
        "inference_version": 2,
        "block_unit": "day",
        "block_length": 1,
        "bootstrap_repetitions": 500,
        "bootstrap_seed": 42,
        "confidence_level": 0.95,
        "minimum_effect_bps": 10.0,
        "minimum_primary_blocks": 2,
        "minimum_execution_data_coverage_pct": 50.0,
        "minimum_research_data_coverage_pct": 0.0001,
        "evaluation_settlement_grace_seconds": 1,
        "confirmatory_decision_policy": CONJUNCTIVE_DECISION_POLICY_V2,
    }
    fields.update(overrides)
    return ConfirmatoryContractV2(**fields)


def _v4_options(
    *,
    name: str,
    contract: ConfirmatoryContractV2,
    **overrides: object,
) -> WalkForwardManifestOptions:
    fields: dict[str, object] = {
        "name": name,
        "warmup_days": 1,
        "test_days": 10,
        "fold_count": 1,
        "min_group_n": 1,
        "horizons": (15,),
        "symbols": ("BTCUSDT_PERP.A",),
        "logic_version": SCALP_SIGNAL_LOGIC_VERSION,
        "evidence_version": 6,
        "sampling_version": 1,
        "context_version": 1,
        "outcome_version": 1,
        "execution_snapshot_version": 1,
        "spec_version": WALK_FORWARD_SPEC_VERSION_V4,
        "research_visibility_version": 1,
        "fee_bps_per_side": (("binance", contract.primary_taker_fee_bps),),
        "confirmatory_contract_v2": contract,
    }
    fields.update(overrides)
    return WalkForwardManifestOptions(**fields)


_TEST_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


async def _matured_v3_schedule(
    conn: asyncpg.Connection,
    *,
    options: WalkForwardManifestOptions,
    margin: timedelta = timedelta(seconds=2),
) -> tuple[datetime, datetime]:
    """(discovery_start, cutoff_at) for a v3 manifest whose LAST fold's
    ``test_maturity_at`` -- i.e. ``confirmatory_knowledge_cutoff`` -- lands
    ``margin`` after the real DB clock at call time.

    Unlike v1/v2 fixtures, a confirmatory schedule CANNOT be backdated to an
    arbitrary historical date (e.g. year 2020) if the test wants real,
    present-day certification to actually count: ``certify_research_
    bundles``/``certify_final_outcomes`` always stamp ``verified_visible_at``
    with the real current wall clock, so a historically-backdated
    ``confirmatory_knowledge_cutoff`` would exclude ANY real certification
    performed *today*, no matter how "matured" the fold's own clock_state
    otherwise looks -- that would be testing the exact adversarial late-
    certificate scenario, not a normal matured-and-certified-on-time one.
    Callers must insert and certify their data, then await real wall-clock
    time past the returned schedule's maturity (see ``_wait_past``) before
    evaluating.
    """

    now = await conn.fetchval("SELECT clock_timestamp()")
    max_horizon = max(options.horizons)
    total_test_span = timedelta(days=options.test_days) * options.fold_count
    # _insert_backdated_manifest derives created_at from cutoff_at via
    # _next_minute_strictly_after(created_at + warmup_days), which truncates
    # to a whole MINUTE -- cutoff_at must already be minute-aligned for that
    # round-trip to check out in _validate_manifest_row. Round UP (never
    # down) so the result never falls short of the requested margin past
    # "now" -- deliberately only minute-aligned here (not the coarser
    # utc_nonoverlap epoch-multiple-of-horizon alignment a bundle's own
    # observed_minute needs), so the wait this forces stays bounded to
    # under a minute rather than under a full horizon: see _align_forward,
    # used separately to place bundles within this window.
    target = now + margin - timedelta(minutes=max_horizon) - OUTCOME_SETTLEMENT_LAG
    last_test_end = target.replace(second=0, microsecond=0)
    if last_test_end < target:
        last_test_end += timedelta(minutes=1)
    cutoff_at = last_test_end - total_test_span
    discovery_start = cutoff_at - timedelta(days=5)
    return discovery_start, cutoff_at


def _align_forward(moment: datetime, *, minutes: int) -> datetime:
    """Smallest multiple-of-``minutes``-since-epoch instant that is `>=
    ``moment``.

    ``_sample_grid``'s ``utc_nonoverlap`` mode keeps only rows whose
    ``observed_minute`` is an exact multiple of the row's horizon in minutes
    SINCE THE UNIX EPOCH. A schedule anchored to the real "now" (see
    ``_matured_v3_schedule``) is essentially never on that grid, so bundles
    placed at an arbitrary offset from its ``test_start`` would silently be
    dropped by sampling. This never moves a fold's own maturity/cutoff --
    only where WITHIN the already-frozen `[test_start, test_end)` window a
    test places its bundles -- so it never risks the large (up-to-a-full-
    horizon) real-time wait that aligning the schedule itself would force.
    """

    bucket_seconds = minutes * 60
    elapsed = (moment - _TEST_EPOCH).total_seconds()
    bucket_index = math.ceil(elapsed / bucket_seconds)
    return _TEST_EPOCH + timedelta(seconds=bucket_index * bucket_seconds)


async def _wait_past(conn: asyncpg.Connection, target: datetime) -> None:
    """Block (real wall-clock sleep, polling the DB clock) until the DB's
    own clock has passed ``target``."""

    while True:
        now = await conn.fetchval("SELECT clock_timestamp()")
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        await asyncio.sleep(min(remaining + 0.05, 1.0))


async def _backdated_ready_schedule(
    conn: asyncpg.Connection,
    *,
    options: WalkForwardManifestOptions,
) -> tuple[datetime, datetime]:
    now = await conn.fetchval("SELECT clock_timestamp()")
    contract_v2 = options.confirmatory_contract_v2
    grace_seconds = (
        0
        if contract_v2 is None
        else contract_v2.evaluation_settlement_grace_seconds
    )
    last_test_end = (
        now
        - timedelta(minutes=max(options.horizons))
        - OUTCOME_SETTLEMENT_LAG
        - timedelta(seconds=grace_seconds + 5)
    ).replace(second=0, microsecond=0)
    cutoff_at = last_test_end - timedelta(days=options.test_days * options.fold_count)
    return cutoff_at - timedelta(days=5), cutoff_at


async def _insert_direct_visibility_certificates(
    conn: asyncpg.Connection,
    *,
    observation_ids: list[int],
    verified_visible_at: datetime,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_research_bundle_visibility(
          observation_id,visibility_version,evidence_version,context_version,
          outcome_version,execution_snapshot_version,verified_visible_at
        )
        SELECT observation_id,1,6,1,1,1,$2
        FROM unnest($1::bigint[]) AS ids(observation_id)
        """,
        observation_ids,
        verified_visible_at,
    )
    await conn.execute(
        """
        INSERT INTO signal_outcome_final_visibility(
          outcome_id,visibility_version,outcome_version,source_status,
          source_finalized_at,verified_visible_at
        )
        SELECT outcome_id,1,outcome_version,status,finalized_at,$2
        FROM signal_outcome
        WHERE observation_id=ANY($1::bigint[])
          AND status IN ('evaluated','not_evaluable')
        """,
        observation_ids,
        verified_visible_at,
    )


# ---------------------------------------------------------------------------
# Not-ready / final-maturity gating.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_not_ready_until_the_last_fold_matures(
    conn: asyncpg.Connection,
) -> None:
    now = await conn.fetchval("SELECT clock_timestamp()")
    # fold1: [cutoff, cutoff+1d) matures ~1h3m before "now".
    # fold2: [cutoff+1d, cutoff+2d) matures ~22h AFTER "now" -- not mature.
    # Truncated to a whole minute: _insert_backdated_manifest's created_at
    # derivation must satisfy the exact next_minute_strictly_after formula.
    cutoff_at = (now - timedelta(days=1, hours=2)).replace(second=0, microsecond=0)
    discovery_start = cutoff_at - timedelta(days=5)

    contract = _confirmatory_contract(minimum_primary_blocks=2)
    options = _v3_options(
        name="pr26-not-ready-test",
        contract=contract,
        test_days=1,
        fold_count=2,
    )
    folds = await _insert_backdated_manifest(
        conn,
        name=options.name,
        options=options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    fold1 = folds[0]

    # An overwhelming positive-return OOS bundle inside fold1 -- if fold1
    # alone were evaluated as final, this would obviously PASS.
    observed_at = fold1["test_start"] + timedelta(hours=1)
    await _insert_confirmatory_bundle(conn, observed_at=observed_at, directional_return_pct=10.0)
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    assert report["folds"][0]["clock_state"] == "ready_by_clock"
    assert report["folds"][1]["clock_state"] != "ready_by_clock"
    assert report["confirmatory_state"] == "not_ready"
    assert report["confirmatory_result"]["ci_lower_bps"] is None
    assert report["confirmatory_result"]["primary_block_count"] == 0
    # confirmatory_knowledge_cutoff is exposed regardless of not_ready state,
    # and is the LAST fold's own frozen test_maturity_at (fold2 here) --
    # never derived from any live clock_state.
    assert report["confirmatory_knowledge_cutoff"] == folds[1]["test_maturity_at"]
    assert (
        report["confirmatory_result"]["confirmatory_knowledge_cutoff"]
        == folds[1]["test_maturity_at"]
    )


# ---------------------------------------------------------------------------
# PASS / FAIL / INCONCLUSIVE at final frozen maturity.
# ---------------------------------------------------------------------------


async def _insert_spread_bundles(
    conn: asyncpg.Connection,
    *,
    test_start: datetime,
    directional_return_pct: float,
    day_count: int,
    direction: str = "long",
) -> None:
    for day in range(day_count):
        observed_at = test_start + timedelta(days=day, hours=1)
        await _insert_confirmatory_bundle(
            conn,
            observed_at=observed_at,
            directional_return_pct=directional_return_pct,
            direction=direction,
        )


async def _insert_diluted_spread_bundles(
    conn: asyncpg.Connection,
    *,
    test_start: datetime,
    actionable_direction: str,
    actionable_directional_return_pct: float,
    dilution_market_return_pct: float,
    day_count: int,
) -> None:
    """Per calendar-day block: one actionable primary-eligible bundle AND one
    non-actionable ("neutral") baseline-only bundle at a DIFFERENT
    market_return_pct. This makes the block's unconditional baseline a real,
    independent control instead of numerically collapsing onto the
    actionable row's own return (which is what a single-row-per-block
    fixture does -- see the P1-01 regression test above)."""

    # Start on the next complete UTC calendar day. The real-clock schedule
    # can place test_start near 23:00 UTC; adding one/two hours directly would
    # split the intended pair across two block keys and make this fixture
    # wall-clock dependent.
    first_complete_day = (test_start + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for day in range(day_count):
        day_start = first_complete_day + timedelta(days=day)
        await _insert_confirmatory_bundle(
            conn,
            observed_at=day_start + timedelta(hours=1),
            directional_return_pct=actionable_directional_return_pct,
            direction=actionable_direction,
        )
        await _insert_confirmatory_bundle(
            conn,
            observed_at=day_start + timedelta(hours=2),
            directional_return_pct=dilution_market_return_pct,
            direction="neutral",
        )


@pytest.mark.asyncio
async def test_confirmatory_positive_raw_expectancy_cannot_pass_once_baseline_is_subtracted(
    conn: asyncpg.Connection,
) -> None:
    """P1-01 canonical regression. Before the fix, this exact fixture (one
    actionable row per calendar block, a strongly positive raw return) made
    ``clock_direction_matched_baseline_bps`` numerically equal the row's own
    return -- so the "baseline" was reported but never subtracted, and PASS
    fired purely because raw modeled return was positive.

    Under the corrected baseline, the block-unconditional cohort for a block
    containing only that one actionable row is that row itself, so the
    baseline still numerically cancels almost the entire raw edge -- leaving
    only the entry/exit cost drag, which is negative. A strongly positive
    raw signal must NOT produce PASS.
    """

    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-raw-positive-not-pass-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # 6 distinct calendar-day blocks, each with a strongly positive raw
    # return (~490bps net of the 5bps entry cost, at zero fee/stress) --
    # this is the exact fixture shape that used to PASS before the fix.
    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=5.0, day_count=6
    )
    # A discovery-only extreme outlier: must never affect the confirmatory
    # decision (OOS-only enforcement).
    discovery_observed_at = folds[0]["discovery_end"] - timedelta(days=1)
    await _insert_confirmatory_bundle(
        conn, observed_at=discovery_observed_at, directional_return_pct=999.0
    )

    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    assert report["report_version"] == WALK_FORWARD_REPORT_VERSION_V3
    assert report["walk_forward_spec_version"] == WALK_FORWARD_SPEC_VERSION_V3
    result = report["confirmatory_result"]
    assert result["primary_block_count"] == 6
    assert result["n_evaluated_actionable"] == 6
    # Each block's baseline cohort is exactly the primary row itself (only
    # one evaluated observation per block), so the block-unconditional
    # market mean numerically equals that row's own 5.0% market return.
    assert result["baseline_mean_bps"] == pytest.approx(500.0, abs=0.01)
    # The pre-fix code reported this same raw quantity as ~489.75bps
    # (baseline_mean_bps was diagnostic-only, never subtracted) and called
    # it PASS. The corrected excess subtracts the baseline, leaving only the
    # entry/exit cost drag -- negative, not PASS.
    assert result["primary_excess_mean_bps"] == pytest.approx(489.75 - 500.0, abs=1.0)
    assert result["primary_excess_mean_bps"] < 0
    assert report["confirmatory_state"] != "pass"
    assert report["confirmatory_state"] == "fail"

    # Exploratory positive_oos_gate_count is 0 (n=1/day-group is below the
    # default min_group_n reporting guardrail) while the confirmatory
    # decision is a clean, deterministic FAIL -- proof the two are
    # structurally decoupled.
    assert report["gates"]["positive_oos_gate_count"] == 0


@pytest.mark.asyncio
async def test_confirmatory_pass_with_genuine_excess_over_diluted_baseline(
    conn: asyncpg.Connection,
) -> None:
    """A genuine PASS is still reachable once the baseline cohort is a real,
    independent control: each block also contains a non-actionable "neutral"
    row whose market_return_pct is the exact negative of the actionable
    row's own return, so the block-unconditional baseline is 0.0 and the
    excess reduces to (approximately) the actionable row's own modeled net
    return, comfortably above minimum_effect_bps."""

    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-pass-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    await _insert_diluted_spread_bundles(
        conn,
        test_start=test_start,
        actionable_direction="long",
        actionable_directional_return_pct=5.0,
        dilution_market_return_pct=-5.0,
        day_count=6,
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "pass"
    assert result["primary_block_count"] == 6
    assert result["n_evaluated_actionable"] == 6
    assert result["ci_lower_bps"] > contract.minimum_effect_bps
    assert result["baseline_mean_bps"] == pytest.approx(0.0, abs=0.5)
    assert result["primary_excess_mean_bps"] == pytest.approx(489.75, abs=1.0)


@pytest.mark.asyncio
async def test_confirmatory_fail_at_final_maturity_with_consistent_negative_edge(
    conn: asyncpg.Connection,
) -> None:
    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-fail-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=-5.0, day_count=6
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "fail"
    assert result["ci_upper_bps"] <= 0.0


@pytest.mark.asyncio
async def test_confirmatory_inconclusive_when_matured_blocks_below_minimum(
    conn: asyncpg.Connection,
) -> None:
    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-inconclusive-blocks-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # Only 2 distinct calendar-day blocks -- strongly positive, but below
    # minimum_primary_blocks=5, so this must stay inconclusive regardless of
    # how extreme the observed edge is.
    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=5.0, day_count=2
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "inconclusive"
    assert result["primary_block_count"] == 2
    assert result["ci_lower_bps"] is None  # bootstrap never ran


# ---------------------------------------------------------------------------
# P1-01: the baseline sign convention and cohort membership.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_baseline_sign_flips_for_a_short_primary_row(
    conn: asyncpg.Connection,
) -> None:
    """Mirror of the P1-01 regression test above, but for a SHORT primary
    row: the single-row-per-block baseline cohort's own market_return_pct is
    NEGATIVE (a winning short means price fell), and the baseline must be
    negated -- not applied as-is -- to correctly compare a short signal
    against the block's unconditional drift."""

    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-short-baseline-sign-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # A "winning" short every day: price falls 5%, so market_return_pct is
    # -5.0% (negative) for every block's lone (self-referential) baseline
    # cohort row.
    await _insert_spread_bundles(
        conn,
        test_start=test_start,
        directional_return_pct=5.0,
        day_count=2,
        direction="short",
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert result["n_evaluated_actionable"] == 2
    # The cohort's own raw mean is -500bps (market fell 5%); sign-matched to
    # this row's own "short" direction, the applied baseline must be +500bps
    # -- the negation, never the raw -500bps unchanged.
    assert result["baseline_mean_bps"] == pytest.approx(500.0, abs=0.5)
    # Same cost-drag-only cancellation pattern as the long-direction
    # regression test: never PASS from a self-referential cohort.
    assert result["primary_excess_mean_bps"] < 0
    assert report["confirmatory_state"] == "fail"


@pytest.mark.asyncio
async def test_confirmatory_baseline_cohort_includes_non_actionable_rows_regardless_of_state_or_regime(
    conn: asyncpg.Connection,
) -> None:
    """P1-01: the baseline cohort for one block must include a non-actionable
    ("neutral") row even though it is never itself a primary/actionable row,
    and must include it regardless of that row's state/regime_label
    differing from the actionable primary row's own state/regime_label."""

    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-baseline-cohort-membership-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # Single calendar-day block: one actionable long row (default
    # state/regime) plus one non-actionable neutral row with a DIFFERENT
    # state/regime_label and a very different market_return_pct.
    complete_day = (test_start + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    await _insert_confirmatory_bundle(
        conn,
        observed_at=complete_day + timedelta(hours=1),
        directional_return_pct=5.0,
        direction="long",
    )
    await _insert_confirmatory_bundle(
        conn,
        observed_at=complete_day + timedelta(hours=2),
        directional_return_pct=-15.0,
        direction="neutral",
        state="Diagnostic Sweep State",
        regime_label="unrelated_diagnostic_regime",
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    # Only the long row is actionable -- the neutral row never becomes a
    # primary row.
    assert result["n_evaluated_actionable"] == 1
    # If the baseline cohort were (incorrectly) restricted to the actionable
    # row alone, the block's unconditional mean would be the row's own
    # +5.0% (+500bps), and the sign-matched (long) baseline would be
    # +500bps. Because the neutral row IS included, the block's true
    # unconditional mean is (5.0 + -15.0) / 2 = -5.0% (-500bps), and the
    # long-direction baseline is -500bps -- the opposite sign from what an
    # actionable-only cohort would have produced.
    assert result["baseline_mean_bps"] == pytest.approx(-500.0, abs=0.5)
    assert result["primary_block_count"] == 1
    # Below this contract's minimum_primary_blocks=2 -- inconclusive by
    # construction, but the diagnostic baseline_mean_bps above is computed
    # unconditionally, before that gate.
    assert report["confirmatory_state"] == "inconclusive"


@pytest.mark.asyncio
async def test_confirmatory_missing_nonvalid_and_insufficient_depth_stay_distinct(
    conn: asyncpg.Connection,
) -> None:
    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-coverage-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # Day 0: valid snapshot, cost-evaluable.
    await _insert_confirmatory_bundle(
        conn, observed_at=test_start + timedelta(days=0, hours=1), directional_return_pct=1.0
    )
    # Day 1: snapshot missing entirely (both_venues=False AND binance itself
    # never written) -- simulate via a bundle whose binance snapshot is
    # simply absent by using a nonvalid status snapshot instead for binance,
    # while still keeping the bundle certifiable (needs both venues present
    # at all, certification requires two rows -- so we make binance
    # "nonvalid", not literally missing, to keep the bundle certifiable and
    # isolate the "nonvalid vs missing" distinction downstream).
    obs_nonvalid = await _insert_confirmatory_bundle(
        conn,
        observed_at=test_start + timedelta(days=1, hours=1),
        directional_return_pct=1.0,
        snapshot_status="stale",
    )
    del obs_nonvalid

    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    coverage = report["confirmatory_result"]["coverage"]
    assert coverage["n_evaluated_actionable"] == 2
    assert coverage["snapshot_nonvalid_n"] == 1
    assert coverage["snapshot_missing_n"] == 0
    assert coverage["insufficient_depth_n"] == 0
    assert coverage["n_cost_evaluable"] == 1
    assert coverage["cost_evaluable_pct"] == pytest.approx(50.0)

    # P2-02: coverage_characteristics keeps the same 4 cohorts distinct, each
    # with its own n and diagnostics -- computed from BOTH rows regardless of
    # cost-evaluability (gross_directional_return_bps/market_return_bps are
    # always derivable straight from the outcome row, independent of the
    # execution snapshot).
    characteristics = report["confirmatory_result"]["coverage_characteristics"]
    assert characteristics["cost_evaluable"]["n"] == 1
    assert characteristics["cost_evaluable"]["gross_directional_mean_bps"] == pytest.approx(100.0)
    assert characteristics["cost_evaluable"]["gross_directional_median_bps"] == pytest.approx(100.0)
    assert characteristics["cost_evaluable"]["abs_market_return_mean_bps"] == pytest.approx(100.0)
    assert characteristics["snapshot_nonvalid"]["n"] == 1
    assert characteristics["snapshot_nonvalid"]["gross_directional_mean_bps"] == pytest.approx(100.0)
    assert characteristics["insufficient_depth"]["n"] == 0
    assert characteristics["insufficient_depth"]["gross_directional_mean_bps"] is None
    assert characteristics["snapshot_missing"]["n"] == 0
    assert characteristics["snapshot_missing"]["gross_directional_mean_bps"] is None


# ---------------------------------------------------------------------------
# No adaptive/optional stopping: re-evaluating a matured manifest later must
# return an identical confirmatory_result.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_result_is_identical_across_repeated_evaluations(
    conn: asyncpg.Connection,
) -> None:
    contract = _confirmatory_contract(minimum_primary_blocks=3, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-repeatable-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))
    # Diluted baseline (see test_confirmatory_pass_with_genuine_excess_over_
    # diluted_baseline) so this is a genuine, baseline-adjusted PASS -- not
    # merely a positive raw return -- making the idempotence check below
    # meaningful under the corrected baseline semantics.
    await _insert_diluted_spread_bundles(
        conn,
        test_start=test_start,
        actionable_direction="long",
        actionable_directional_return_pct=5.0,
        dilution_market_return_pct=-5.0,
        day_count=4,
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        first = await evaluate_walk_forward(conn, options.name)
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        second = await evaluate_walk_forward(conn, options.name)

    assert first["confirmatory_result"] == second["confirmatory_result"]
    assert first["confirmatory_state"] == second["confirmatory_state"] == "pass"


# ---------------------------------------------------------------------------
# v1/v2 reports stay byte-for-byte unaffected by a v3 manifest existing in
# the same database.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v1_and_v2_reports_have_no_confirmatory_keys_alongside_a_v3_manifest(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=2)
    v3_options = _v3_options(name="pr26-coexist-v3-test", contract=contract)
    await _insert_backdated_manifest(
        conn,
        name=v3_options.name,
        options=v3_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    v1_options = WalkForwardManifestOptions(name="pr26-coexist-v1-test", fold_count=1)
    await _insert_backdated_manifest(
        conn,
        name=v1_options.name,
        options=v1_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    v2_options = WalkForwardManifestOptions(
        name="pr26-coexist-v2-test",
        fold_count=1,
        logic_version=SCALP_SIGNAL_LOGIC_VERSION,
        evidence_version=6,
        sampling_version=1,
        context_version=1,
        outcome_version=1,
        execution_snapshot_version=1,
        spec_version=2,
        research_visibility_version=1,
    )
    await _insert_backdated_manifest(
        conn,
        name=v2_options.name,
        options=v2_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        v1_report = await evaluate_walk_forward(conn, v1_options.name)
    async with conn.transaction(isolation="repeatable_read", readonly=True):
        v2_report = await evaluate_walk_forward(conn, v2_options.name)

    for report in (v1_report, v2_report):
        assert "confirmatory_contract" not in report
        assert "confirmatory_state" not in report
        assert "confirmatory_result" not in report
        assert "confirmatory_knowledge_cutoff" not in report
    assert v1_report["report_version"] == 1
    assert v2_report["report_version"] == 2


# ---------------------------------------------------------------------------
# P1-02: the confirmatory sample is fixed as of confirmatory_knowledge_cutoff
# -- a source/certificate that becomes visible AFTER that frozen cutoff must
# permanently stay outside the experiment, even after it is certified and
# the manifest is re-evaluated.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_late_bundle_certificate_after_frozen_cutoff_never_enters_sample(
    conn: asyncpg.Connection,
) -> None:
    """1. frozen final maturity is in the past (manifest backdated to 2020).
    2. an eligible OOS source (a fully complete bundle) exists.
    3. its bundle-visibility certificate is absent at the first evaluation.
    4. evaluate -> a fixed (empty) result.
    5. certify the bundle -- verified_visible_at is real "now" (2020s later),
       necessarily AFTER the frozen confirmatory_knowledge_cutoff.
    6. evaluate again later.
    7. confirmatory_result must remain byte-identical: the late-certified
    bundle must never enter the primary sample."""

    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-late-bundle-cert-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]

    # A fully complete, certifiable bundle inside the OOS window -- but left
    # UNCERTIFIED for now.
    await _insert_confirmatory_bundle(
        conn, observed_at=test_start + timedelta(hours=1), directional_return_pct=5.0
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        first = await evaluate_walk_forward(conn, options.name)

    # confirmatory_knowledge_cutoff (2020s) is already far in the past
    # relative to the real DB clock, so this is already past the not_ready
    # gate -- yet the uncertified bundle contributes nothing.
    assert first["confirmatory_state"] == "inconclusive"
    assert first["confirmatory_result"]["n_evaluated_actionable"] == 0

    # Certify now -- verified_visible_at is real "now", necessarily after
    # the frozen (2020s) confirmatory_knowledge_cutoff.
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        second = await evaluate_walk_forward(conn, options.name)

    assert second["confirmatory_result"] == first["confirmatory_result"]
    assert second["confirmatory_result"]["n_evaluated_actionable"] == 0


@pytest.mark.asyncio
async def test_confirmatory_late_final_outcome_certificate_after_frozen_cutoff_never_enters_sample(
    conn: asyncpg.Connection,
) -> None:
    """True two-stage isolation of the final-OUTCOME visibility certificate,
    as distinct from bundle visibility.

    The old (2020-backdated) version of this test could not actually prove
    what its docstring claimed: ``certify_research_bundles``/
    ``certify_final_outcomes`` always stamp ``verified_visible_at`` with the
    REAL wall clock (see ``_matured_v3_schedule``'s own docstring), so a
    historically-backdated ``confirmatory_knowledge_cutoff`` (2020s) made
    ANY real-time certification -- bundle OR outcome -- land after cutoff.
    The observed ``n_evaluated_actionable == 0`` was therefore equally
    explainable by a late BUNDLE certificate, never isolating late-outcome-
    only visibility.

    This version uses the near-real-time ``_matured_v3_schedule`` pattern
    (already used elsewhere in this file) instead:

    1. certify the BUNDLE genuinely BEFORE the frozen cutoff matures --
       ``verified_visible_at <= confirmatory_knowledge_cutoff`` truly holds;
    2. wait past the cutoff;
    3. evaluate -- the observation is grid-visible (bundle certified) but its
       outcome is still projected to "pending": confirmatory_outcome_integrity
       must show it as pending, not simply absent, and the result must be
       inconclusive with no bootstrap CI;
    4. certify the final outcome only NOW, strictly AFTER the frozen cutoff
       has already passed -- its ``verified_visible_at`` is necessarily
       ``> confirmatory_knowledge_cutoff``;
    5. evaluate again -- the result must be byte-identical: the final outcome
       never becomes confirmatory-eligible no matter how much later it is
       certified.
    """

    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-late-outcome-cert-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    observed_at = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    await _insert_confirmatory_bundle(conn, observed_at=observed_at, directional_return_pct=5.0)
    # Certify the BUNDLE genuinely BEFORE the frozen cutoff matures -- the
    # observation is now visible in the grid -- but do NOT certify the final
    # outcome yet.
    await certify_research_bundles(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        first = await evaluate_walk_forward(conn, options.name)

    assert first["confirmatory_state"] == "inconclusive"
    assert first["confirmatory_result"]["n_evaluated_actionable"] == 0
    assert first["confirmatory_result"]["ci_lower_bps"] is None
    # A4-08: the observation IS visible (bundle certified before cutoff), but
    # its outcome is still projected to pending -- not simply absent from
    # the denominator.
    integrity = first["confirmatory_result"]["confirmatory_outcome_integrity"]
    assert integrity["outcome_complete"] is False
    assert integrity["eligible_sampled_periodic_n"] >= 1
    assert integrity["pending_periodic_n"] >= 1
    assert integrity["evaluated_periodic_n"] == 0

    # Certify the final outcome now -- strictly AFTER the frozen cutoff has
    # already passed, so its verified_visible_at is necessarily after
    # confirmatory_knowledge_cutoff.
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        second = await evaluate_walk_forward(conn, options.name)

    assert second["confirmatory_result"] == first["confirmatory_result"]
    assert second["confirmatory_result"]["n_evaluated_actionable"] == 0


# ---------------------------------------------------------------------------
# A4-08: outcome completeness -- a manifest whose evaluated-only subset would
# PASS must go inconclusive if any other eligible boundary-safe row at the
# same frozen experiment is still pending/not_evaluable, and late recovery
# after the frozen cutoff must never change that.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_selective_pending_outcomes_force_inconclusive_and_survive_late_recovery(
    conn: asyncpg.Connection,
) -> None:
    """Enough OOS blocks exist to PASS from the evaluated subset alone (the
    exact diluted-baseline PASS shape as
    ``test_confirmatory_pass_with_genuine_excess_over_diluted_baseline``),
    but several additional eligible primary rows at the SAME frozen
    experiment -- one ``pending``, one ``not_evaluable`` -- exist at
    ``confirmatory_knowledge_cutoff``. Before the fix, ``_actionable_evaluated``/
    ``_all_periodic_evaluated`` would have silently dropped these and let the
    remaining positive subset PASS. The confirmatory layer must instead
    inspect the full sampled grid and go inconclusive with no bootstrap CI.
    Finalizing/certifying the pending outcome AFTER the frozen cutoff (late
    recovery) must never change the result."""

    contract = _confirmatory_contract(minimum_primary_blocks=2, minimum_effect_bps=0.0)
    options = _v3_options(name="pr26-selective-pending-test", contract=contract)
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = _align_forward(folds[0]["test_start"], minutes=max(options.horizons))

    # 2 fully-evaluated, diluted-baseline calendar-day blocks -- would PASS
    # on the evaluated-only subset alone.
    await _insert_diluted_spread_bundles(
        conn,
        test_start=test_start,
        actionable_direction="long",
        actionable_directional_return_pct=5.0,
        dilution_market_return_pct=-5.0,
        day_count=2,
    )

    # Additional eligible primary rows at the SAME frozen experiment, left
    # unresolved at confirmatory_knowledge_cutoff -- execution coverage of
    # the evaluated subset above is otherwise sufficient on its own.
    pending_observation_id, pending_horizon = await _insert_confirmatory_bundle_with_primary_status(
        conn,
        observed_at=test_start + timedelta(days=0, hours=5),
        primary_status="pending",
        direction="long",
    )
    await _insert_confirmatory_bundle_with_primary_status(
        conn,
        observed_at=test_start + timedelta(days=1, hours=5),
        primary_status="not_evaluable",
        direction="long",
    )

    await certify_research_bundles(conn)
    # certify_final_outcomes certifies every row whose status is already
    # 'evaluated' or 'not_evaluable' -- the 4 diluted-spread rows (so they
    # actually project as evaluated, not pending) AND the not_evaluable row
    # (a terminal status, certified once). The still-pending row is
    # untouched -- not_evaluable/evaluated only -- and stays projected to
    # pending, exactly the scenario under test.
    await certify_final_outcomes(conn)
    await _wait_past(conn, folds[-1]["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        first = await evaluate_walk_forward(conn, options.name)

    assert first["confirmatory_state"] == "inconclusive"
    assert first["confirmatory_result"]["ci_lower_bps"] is None
    assert first["confirmatory_result"]["ci_upper_bps"] is None
    integrity = first["confirmatory_result"]["confirmatory_outcome_integrity"]
    assert integrity["outcome_complete"] is False
    assert integrity["pending_periodic_n"] >= 1
    assert integrity["not_evaluable_periodic_n"] >= 1

    # Finalize/certify the pending outcome AFTER the frozen cutoff has
    # already passed (late recovery). not_evaluable is a terminal status in
    # production -- it is never "recovered" -- so only the pending row is
    # finalized here.
    await _finalize_pending_outcome(
        conn,
        observation_id=pending_observation_id,
        horizon_minutes=pending_horizon,
        directional_return_pct=50.0,
    )
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        second = await evaluate_walk_forward(conn, options.name)

    # Byte-identical: late recovery after the frozen cutoff can never flip
    # INCONCLUSIVE to PASS.
    assert second["confirmatory_result"] == first["confirmatory_result"]
    assert second["confirmatory_state"] == "inconclusive"


# ---------------------------------------------------------------------------
# A4-08: research-source coverage -- deterministic expected utc_nonoverlap
# slots that were never even certified-visible (a research-source gap, not
# an outcome-status gap) must gate inference too, and a fully-covered
# fixture must reach the normal bootstrap path.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_missing_research_slots_gate_inference(
    conn: asyncpg.Connection,
) -> None:
    """Strong positive evaluated rows exist that would otherwise PASS, but
    several deterministic expected ``utc_nonoverlap`` slots are deliberately
    never populated at all -- no row whatsoever, not even pending -- a
    research-source coverage gap, distinct from ``confirmatory_outcome_integrity``
    (which only sees rows that already made it into the certificate-gated
    grid). Freezing ``minimum_research_data_coverage_pct`` above the achieved
    ratio must gate inference to inconclusive, using the FULL deterministic
    ``expected_sample_slots`` count -- proving omitted slots are not silently
    removed from the denominator. See
    ``test_confirmatory_full_research_coverage_allows_bootstrap`` for the
    fully-covered sibling proof (a separate manifest/schema, so its
    real-time-anchored utc_nonoverlap slots can never collide with this
    one's)."""

    horizon = 240
    contract = _confirmatory_contract(
        minimum_primary_blocks=2,
        minimum_effect_bps=0.0,
        primary_horizon_minutes=horizon,
        minimum_research_data_coverage_pct=60.0,
    )
    options = _v3_options(
        name="pr26-missing-slots-test",
        contract=contract,
        horizons=(horizon,),
        test_days=2,
        fold_count=1,
    )
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    fold = folds[0]

    expected_slots = _enumerate_expected_slots(fold, horizon_minutes=horizon)
    # Independent cross-check: the pure-Python deterministic count must agree
    # with this test's own enumeration.
    assert len(expected_slots) == _expected_utc_nonoverlap_slot_count(
        test_start=fold["test_start"], test_end=fold["test_end"], horizon_minutes=horizon
    )
    assert len(expected_slots) >= 4

    # Populate only 2 pairs (actionable + same-block dilution) out of the
    # full deterministic slot grid -- widely spaced so they land in two
    # DISTINCT calendar-day blocks, deliberately omitting every other
    # expected slot (no row at all, not even pending).
    block_a = expected_slots[0], expected_slots[1]
    block_b = expected_slots[-2], expected_slots[-1]
    assert confirmatory_block_key(
        block_a[0], block_unit=contract.block_unit, block_length=contract.block_length
    ) != confirmatory_block_key(
        block_b[0], block_unit=contract.block_unit, block_length=contract.block_length
    )

    for actionable_slot, dilution_slot in (block_a, block_b):
        await _insert_confirmatory_bundle(
            conn,
            observed_at=actionable_slot,
            directional_return_pct=5.0,
            direction="long",
            primary_horizon=horizon,
        )
        await _insert_confirmatory_bundle(
            conn,
            observed_at=dilution_slot,
            directional_return_pct=-5.0,
            direction="neutral",
            primary_horizon=horizon,
        )
    populated_slots = 4

    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, fold["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    coverage = report["confirmatory_result"]["research_data_coverage"]
    assert coverage["expected_sample_slots"] == len(expected_slots)
    assert coverage["certified_visible_sample_slots"] == populated_slots
    achieved_pct = populated_slots / len(expected_slots) * 100.0
    assert coverage["research_data_coverage_pct"] == pytest.approx(achieved_pct)
    assert achieved_pct < contract.minimum_research_data_coverage_pct
    assert report["confirmatory_state"] == "inconclusive"
    assert report["confirmatory_result"]["ci_lower_bps"] is None


@pytest.mark.asyncio
async def test_confirmatory_full_research_coverage_allows_bootstrap(
    conn: asyncpg.Connection,
) -> None:
    """Sibling proof to
    ``test_confirmatory_missing_research_slots_gate_inference``: populate
    EVERY deterministic expected ``utc_nonoverlap`` slot (full research
    coverage) and confirm the normal bootstrap path is reached -- full
    coverage must not be incorrectly gated."""

    horizon = 240
    contract = _confirmatory_contract(
        minimum_primary_blocks=2,
        minimum_effect_bps=0.0,
        primary_horizon_minutes=horizon,
        minimum_research_data_coverage_pct=100.0,
    )
    options = _v3_options(
        name="pr26-full-research-coverage-test",
        contract=contract,
        horizons=(horizon,),
        test_days=2,
        fold_count=1,
    )
    discovery_start, cutoff_at = await _matured_v3_schedule(conn, options=options)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    fold = folds[0]
    slots = _enumerate_expected_slots(fold, horizon_minutes=horizon)
    assert len(slots) >= 4

    # Alternate direction per slot so every calendar-day block gets both an
    # actionable row and a dilution row, keeping the baseline a real,
    # independent control (same pattern as _insert_diluted_spread_bundles).
    for index, slot in enumerate(slots):
        await _insert_confirmatory_bundle(
            conn,
            observed_at=slot,
            directional_return_pct=5.0 if index % 2 == 0 else -5.0,
            direction="long" if index % 2 == 0 else "neutral",
            primary_horizon=horizon,
        )

    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)
    await _wait_past(conn, fold["test_maturity_at"])

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    coverage = report["confirmatory_result"]["research_data_coverage"]
    assert coverage["expected_sample_slots"] == len(slots)
    assert coverage["certified_visible_sample_slots"] == len(slots)
    assert coverage["research_data_coverage_pct"] == pytest.approx(100.0)
    assert report["confirmatory_result"]["confirmatory_outcome_integrity"]["outcome_complete"] is True
    # Full coverage must reach the normal bootstrap path -- not gated.
    assert report["confirmatory_result"]["ci_lower_bps"] is not None
    # Statistical ambiguity remains valid after bootstrap; this test is about
    # reaching inference, not forcing a scientifically decisive interval.
    assert report["confirmatory_state"] in ("pass", "fail", "inconclusive")


# ---------------------------------------------------------------------------
# Missing confirmatory_contract fails closed before any DB write.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_freeze_spec_v3_without_confirmatory_contract_fails_closed(
    conn: asyncpg.Connection,
) -> None:
    options = WalkForwardManifestOptions(
        name="pr26-missing-contract-test",
        logic_version=SCALP_SIGNAL_LOGIC_VERSION,
        evidence_version=6,
        sampling_version=1,
        context_version=1,
        outcome_version=1,
        execution_snapshot_version=1,
        spec_version=WALK_FORWARD_SPEC_VERSION_V3,
        research_visibility_version=1,
        confirmatory_contract=None,
    )
    with pytest.raises(ValueError):
        async with conn.transaction():
            await freeze_walk_forward_manifest(conn, options)

    count = await conn.fetchval("SELECT count(*) FROM signal_walk_forward_manifest")
    assert count == 0


# ---------------------------------------------------------------------------
# PR27 spec v4: corrected economics and authoritative result evidence.
# ---------------------------------------------------------------------------


async def _prepare_ready_v4(
    conn: asyncpg.Connection,
    *,
    name: str,
    contract: ConfirmatoryContractV2 | None = None,
    row_specs: list[dict[str, object]] | None = None,
) -> tuple[WalkForwardManifestOptions, list[dict], list[int]]:
    resolved_contract = contract or _confirmatory_contract_v2()
    options = _v4_options(
        name=name,
        contract=resolved_contract,
        test_days=4,
    )
    discovery_start, cutoff_at = await _backdated_ready_schedule(
        conn, options=options
    )
    folds = await _insert_backdated_manifest(
        conn,
        name=name,
        options=options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    specs = row_specs or [
        {"day": 0, "direction": "long", "return_pct": 2.0},
        {"day": 1, "direction": "long", "return_pct": 2.0},
    ]
    observation_ids: list[int] = []
    for index, spec in enumerate(specs):
        slot = _align_forward(
            folds[0]["test_start"]
            + timedelta(days=int(spec.get("day", index)), hours=1)
            + timedelta(minutes=int(spec.get("minute_offset", 0))),
            minutes=resolved_contract.primary_horizon_minutes,
        )
        observation_ids.append(
            await _insert_confirmatory_bundle(
                conn,
                observed_at=slot,
                directional_return_pct=float(spec.get("return_pct", 2.0)),
                primary_horizon=resolved_contract.primary_horizon_minutes,
                direction=str(spec.get("direction", "long")),
                reference_price=float(spec.get("reference_price", 100.0)),
                snapshot_cost_bps=float(spec.get("snapshot_cost_bps", 0.0)),
                snapshot_status=str(spec.get("snapshot_status", "valid")),
                state=(
                    None if spec.get("state") is None else str(spec["state"])
                ),
                regime_label=str(spec.get("regime_label", "trend_up")),
                replay_direction=(
                    None
                    if spec.get("replay_direction") is None
                    else str(spec["replay_direction"])
                ),
                evidence_overrides=(
                    dict(spec["evidence_overrides"])
                    if isinstance(spec.get("evidence_overrides"), dict)
                    else None
                ),
                actionable=(
                    None
                    if spec.get("actionable") is None
                    else bool(spec["actionable"])
                ),
                outcome_end_price=(
                    None
                    if spec.get("outcome_end_price") is None
                    else float(spec["outcome_end_price"])
                ),
                # Absent keys mean "produced under the registered contract".
                # A spec may pass None/None (no provenance at all) or a foreign
                # digest to model evidence written while routing B was active.
                **(
                    {
                        "runtime_contract_version": spec[
                            "runtime_contract_version"
                        ],
                        "runtime_contract_digest": spec[
                            "runtime_contract_digest"
                        ],
                    }
                    if "runtime_contract_digest" in spec
                    else {}
                ),
            )
        )
    await _insert_direct_visibility_certificates(
        conn,
        observation_ids=observation_ids,
        verified_visible_at=(
            folds[-1]["test_maturity_at"] - timedelta(seconds=1)
        ),
    )
    return options, folds, observation_ids


@pytest.mark.asyncio
async def test_p1_01_old_v3_keeps_reference_offset_but_v4_cannot_pass_from_it(
    conn: asyncpg.Connection,
) -> None:
    v4_contract = _confirmatory_contract_v2(
        minimum_effect_bps=10.0,
        minimum_primary_blocks=2,
    )
    v4_options = _v4_options(
        name="pr27-reference-offset-v4",
        contract=v4_contract,
        test_days=4,
    )
    discovery_start, cutoff_at = await _backdated_ready_schedule(
        conn, options=v4_options
    )
    v4_folds = await _insert_backdated_manifest(
        conn,
        name=v4_options.name,
        options=v4_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    v3_contract = _confirmatory_contract(
        minimum_effect_bps=10.0,
        minimum_primary_blocks=2,
        minimum_research_data_coverage_pct=0.0001,
        primary_taker_fee_bps=0.0,
    )
    v3_options = _v3_options(
        name="pr27-reference-offset-v3-control",
        contract=v3_contract,
        test_days=4,
    )
    await _insert_backdated_manifest(
        conn,
        name=v3_options.name,
        options=v3_options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )

    observation_ids: list[int] = []
    stale_reference_by_direction = {"long": 101.0, "short": 99.0}
    for day, direction in enumerate(("long", "short", "long", "short")):
        slot = _align_forward(
            v4_folds[0]["test_start"] + timedelta(days=day, hours=1),
            minutes=15,
        )
        reference_price = stale_reference_by_direction[direction]
        reference_feed_return_pct = (100.0 / reference_price - 1.0) * 100.0
        directional_return_pct = (
            reference_feed_return_pct
            if direction == "long"
            else -reference_feed_return_pct
        )
        observation_ids.append(
            await _insert_confirmatory_bundle(
                conn,
                observed_at=slot,
                direction=direction,
                directional_return_pct=directional_return_pct,
                reference_price=reference_price,
                outcome_end_price=100.0,
                snapshot_cost_bps=0.0,
            )
        )
    await _insert_direct_visibility_certificates(
        conn,
        observation_ids=observation_ids,
        verified_visible_at=(
            v4_folds[-1]["test_maturity_at"] - timedelta(seconds=1)
        ),
    )

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        legacy_report = await evaluate_walk_forward(conn, v3_options.name)
    corrected_report = await evaluate_walk_forward_authoritative(
        conn, v4_options.name
    )

    assert legacy_report["confirmatory_state"] == "pass"
    assert legacy_report["confirmatory_result"]["primary_excess_mean_bps"] > 90.0
    assert legacy_report["confirmatory_result"]["n_evaluated_actionable"] == 4
    corrected = corrected_report["confirmatory_result"]
    assert corrected_report["confirmatory_state"] != "pass"
    assert corrected["absolute_stressed_mean_bps"] == pytest.approx(0.0)
    assert corrected["baseline_mean_bps"] == pytest.approx(0.0)
    assert corrected["excess_mean_bps"] == pytest.approx(0.0)
    assert corrected_report["authoritative_result"]["persisted"] is True


@pytest.mark.asyncio
async def test_p1_02_absolute_loss_relative_alpha_is_joint_fail_in_postgres(
    conn: asyncpg.Connection,
) -> None:
    rows: list[dict[str, object]] = []
    for day in (0, 1, 2):
        rows.extend(
            [
                {
                    "day": day,
                    "minute_offset": 0,
                    "direction": "short",
                    "return_pct": -1.0,
                    "snapshot_cost_bps": 0.0,
                },
                {
                    "day": day,
                    "minute_offset": 15,
                    "direction": "neutral",
                    "return_pct": 5.0,
                    "snapshot_cost_bps": 0.0,
                },
            ]
        )
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-absolute-loss-relative-alpha",
        contract=_confirmatory_contract_v2(
            minimum_effect_bps=100.0,
            minimum_primary_blocks=2,
        ),
        row_specs=rows,
    )
    report = await evaluate_walk_forward_authoritative(conn, options.name)
    result = report["confirmatory_result"]
    assert result["absolute_stressed_mean_bps"] < 0.0
    assert result["excess_mean_bps"] > 100.0
    assert result["absolute_component_state"] == "fail"
    assert result["excess_component_state"] == "pass"
    assert report["confirmatory_state"] == "fail"


@pytest.mark.asyncio
async def test_v4_pass_requires_both_absolute_and_excess_components_in_postgres(
    conn: asyncpg.Connection,
) -> None:
    rows: list[dict[str, object]] = []
    for day in (0, 1, 2):
        rows.extend(
            [
                {
                    "day": day,
                    "minute_offset": 0,
                    "direction": "long",
                    "return_pct": 2.0,
                    "snapshot_cost_bps": 0.0,
                },
                {
                    "day": day,
                    "minute_offset": 15,
                    "direction": "neutral",
                    "return_pct": -2.0,
                    "snapshot_cost_bps": 0.0,
                },
            ]
        )
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-joint-positive-pass",
        contract=_confirmatory_contract_v2(
            minimum_effect_bps=10.0,
            minimum_primary_blocks=2,
        ),
        row_specs=rows,
    )
    report = await evaluate_walk_forward_authoritative(conn, options.name)
    result = report["confirmatory_result"]
    assert result["absolute_stressed_mean_bps"] > 0.0
    assert result["excess_mean_bps"] > 10.0
    assert result["absolute_ci_lower_bps"] > 0.0
    assert result["excess_ci_lower_bps"] > 10.0
    assert result["absolute_component_state"] == "pass"
    assert result["excess_component_state"] == "pass"
    assert report["confirmatory_state"] == "pass"
    assert result["signal_replay_integrity"] == {
        "population": (
            "certified_visible_utc_nonoverlap_"
            "outcome_window_complete_periodic_v1"
        ),
        "checked_observation_n": 6,
        "complete": True,
    }


def _favorable_replay_integrity_rows(
    mismatching_row: dict[str, object],
) -> list[dict[str, object]]:
    return [
        {
            "day": 0,
            "minute_offset": 0,
            "direction": "long",
            "return_pct": 2.0,
            **mismatching_row,
        },
        {
            "day": 0,
            "minute_offset": 15,
            "direction": "neutral",
            "return_pct": -2.0,
        },
        {
            "day": 1,
            "minute_offset": 0,
            "direction": "long",
            "return_pct": 2.0,
        },
        {
            "day": 1,
            "minute_offset": 15,
            "direction": "neutral",
            "return_pct": -2.0,
        },
    ]


async def _assert_replay_integrity_failure_without_result(
    conn: asyncpg.Connection,
    *,
    name: str,
    mismatching_row: dict[str, object],
    error_match: str,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name=name,
        row_specs=_favorable_replay_integrity_rows(mismatching_row),
    )
    with pytest.raises(ConfirmatoryScientificIntegrityError, match=error_match):
        await evaluate_walk_forward_authoritative(conn, options.name)
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 0


@pytest.mark.asyncio
async def test_v4_favorable_stored_evidence_mismatch_fails_before_persistence(
    conn: asyncpg.Connection,
) -> None:
    """A -> B -> A: B-only evidence can never turn the favorable sample PASS."""

    await _assert_replay_integrity_failure_without_result(
        conn,
        name="pr27-replay-evidence-mismatch",
        mismatching_row={"evidence_overrides": {"kernel_b_only": True}},
        error_match="evidence_match=False",
    )


@pytest.mark.asyncio
async def test_v4_actionability_population_mismatch_cannot_be_silently_excluded(
    conn: asyncpg.Connection,
) -> None:
    # Frozen evidence/context replay as actionable long, while the stored row
    # claims neutral/non-actionable and would otherwise disappear from primary_rows.
    await _assert_replay_integrity_failure_without_result(
        conn,
        name="pr27-replay-actionability-mismatch",
        mismatching_row={"direction": "neutral", "replay_direction": "long"},
        error_match="field_mismatches=direction,actionable",
    )


@pytest.mark.asyncio
async def test_v4_direction_changing_replay_mismatch_fails_closed(
    conn: asyncpg.Connection,
) -> None:
    await _assert_replay_integrity_failure_without_result(
        conn,
        name="pr27-replay-direction-mismatch",
        mismatching_row={"direction": "short", "replay_direction": "long"},
        error_match="field_mismatches=direction",
    )


@pytest.mark.asyncio
async def test_valid_evidence_v6_replay_is_usable_without_backfill_or_mutation(
    conn: asyncpg.Connection,
) -> None:
    options, _, observation_ids = await _prepare_ready_v4(
        conn,
        name="pr27-valid-evidence-v6-replay",
    )
    before = [
        dict(row)
        for row in await conn.fetch(
            """
            SELECT obs.observation_id,obs.evidence::text,
                   frame.context_hash,frame.context::text
            FROM signal_observation AS obs
            JOIN signal_replay_frame AS frame USING(observation_id)
            WHERE obs.observation_id=ANY($1::bigint[])
            ORDER BY obs.observation_id
            """,
            observation_ids,
        )
    ]

    report = await evaluate_walk_forward_authoritative(conn, options.name)

    after = [
        dict(row)
        for row in await conn.fetch(
            """
            SELECT obs.observation_id,obs.evidence::text,
                   frame.context_hash,frame.context::text
            FROM signal_observation AS obs
            JOIN signal_replay_frame AS frame USING(observation_id)
            WHERE obs.observation_id=ANY($1::bigint[])
            ORDER BY obs.observation_id
            """,
            observation_ids,
        )
    ]
    assert after == before
    assert report["confirmatory_result"]["signal_replay_integrity"][
        "checked_observation_n"
    ] == len(observation_ids)
    assert report["authoritative_result"]["persisted"] is True


@pytest.mark.asyncio
async def test_baseline_snapshot_missingness_is_counted_and_forces_inconclusive(
    conn: asyncpg.Connection,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-baseline-missingness",
        row_specs=[
            {"day": 0, "direction": "long", "return_pct": 2.0},
            {
                "day": 1,
                "direction": "neutral",
                "return_pct": -3.0,
                "snapshot_status": "stale",
            },
            {"day": 2, "direction": "long", "return_pct": 2.0},
        ],
    )
    report = await evaluate_walk_forward_authoritative(conn, options.name)
    integrity = report["confirmatory_result"]["baseline_input_integrity"]
    assert integrity["expected_evaluated_periodic_n"] == 3
    assert integrity["baseline_evaluable_n"] == 2
    assert integrity["snapshot_nonvalid_n"] == 1
    assert integrity["baseline_complete"] is False
    assert report["confirmatory_state"] == "inconclusive"


@pytest.mark.asyncio
async def test_first_authoritative_result_persists_and_identical_recompute_verifies(
    conn: asyncpg.Connection,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-authoritative-idempotency",
    )
    first = await evaluate_walk_forward_authoritative(conn, options.name)
    second = await evaluate_walk_forward_authoritative(conn, options.name)
    assert first["confirmatory_result"] == second["confirmatory_result"]
    assert first["authoritative_result"]["persisted"] is True
    assert first["authoritative_result"]["reused_existing"] is False
    assert second["authoritative_result"]["reused_existing"] is True
    assert (
        first["authoritative_result"]["result_hash"]
        == second["authoritative_result"]["result_hash"]
    )
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 1


@pytest.mark.asyncio
async def test_authoritative_result_update_delete_and_truncate_are_rejected(
    conn: asyncpg.Connection,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-authoritative-immutable",
    )
    report = await evaluate_walk_forward_authoritative(conn, options.name)
    result_id = report["authoritative_result"]["result_id"]

    with pytest.raises(asyncpg.CheckViolationError):
        await conn.execute(
            """
            INSERT INTO signal_walk_forward_confirmatory_result(
              result_version,manifest_id,manifest_hash,
              scientific_implementation_digest,
              scientific_runtime_contract_digest,
              confirmatory_knowledge_cutoff,evaluation_not_before,
              canonical_result_json,result_hash
            )
            SELECT
              result_version,manifest_id,manifest_hash,
              scientific_implementation_digest,
              scientific_runtime_contract_digest,
              confirmatory_knowledge_cutoff,evaluation_not_before,
              canonical_result_json,$2
            FROM signal_walk_forward_confirmatory_result
            WHERE result_id=$1
            """,
            result_id,
            "0" * 64,
        )
    with pytest.raises(asyncpg.PostgresError) as update_error:
        await conn.execute(
            "UPDATE signal_walk_forward_confirmatory_result SET result_version=1 "
            "WHERE result_id=$1",
            result_id,
        )
    assert update_error.value.sqlstate == "55000"
    with pytest.raises(asyncpg.PostgresError) as delete_error:
        await conn.execute(
            "DELETE FROM signal_walk_forward_confirmatory_result WHERE result_id=$1",
            result_id,
        )
    assert delete_error.value.sqlstate == "55000"
    with pytest.raises(asyncpg.PostgresError) as truncate_error:
        await conn.execute("TRUNCATE signal_walk_forward_confirmatory_result")
    assert truncate_error.value.sqlstate == "55000"
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 1


@pytest.mark.asyncio
async def test_artificial_recomputation_divergence_fails_closed(
    conn: asyncpg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-authoritative-divergence",
    )
    await evaluate_walk_forward_authoritative(conn, options.name)

    import app.signal_walk_forward as walk_forward

    original = walk_forward.paired_block_bootstrap_ci_v2

    def divergent_ci(*args, **kwargs):
        result = original(*args, **kwargs)
        return {
            **result,
            "absolute_ci_lower_bps": result["absolute_ci_lower_bps"] + 0.5,
            "absolute_ci_upper_bps": result["absolute_ci_upper_bps"] + 0.5,
        }

    monkeypatch.setattr(walk_forward, "paired_block_bootstrap_ci_v2", divergent_ci)
    with pytest.raises(
        ConfirmatoryReproducibilityError,
        match="disagrees",
    ):
        await evaluate_walk_forward_authoritative(conn, options.name)
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 1


@pytest.mark.asyncio
async def test_runtime_scientific_digest_mismatch_fails_before_result_is_trusted(
    conn: asyncpg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-implementation-mismatch",
    )
    import app.signal_scientific_identity as identity

    registry = dict(identity.load_identity_registry())
    registry["code_digest"] = "0" * 64
    monkeypatch.setattr(identity, "load_identity_registry", lambda *a, **k: registry)
    with pytest.raises(RuntimeError, match="does not match"):
        await evaluate_walk_forward_authoritative(conn, options.name)
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 0


@pytest.mark.asyncio
async def test_concurrent_first_evaluations_serialize_to_one_result(
    conn: asyncpg.Connection,
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-authoritative-concurrency",
    )
    schema = await conn.fetchval("SELECT current_schema()")
    second_conn = await asyncpg.connect(_dsn())
    await second_conn.execute(f'SET search_path TO "{schema}", public')
    await second_conn.execute("SET TIME ZONE 'UTC'")
    try:
        first, second = await asyncio.gather(
            evaluate_walk_forward_authoritative(conn, options.name),
            evaluate_walk_forward_authoritative(second_conn, options.name),
        )
    finally:
        await second_conn.close()
    assert first["confirmatory_result"] == second["confirmatory_result"]
    assert (
        first["authoritative_result"]["result_hash"]
        == second["authoritative_result"]["result_hash"]
    )
    assert sorted(
        [
            first["authoritative_result"]["reused_existing"],
            second["authoritative_result"]["reused_existing"],
        ]
    ) == [False, True]
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 1


@pytest.mark.asyncio
async def test_certificate_commit_during_settlement_is_deterministic_and_late_stamp_excluded(
    conn: asyncpg.Connection,
) -> None:
    contract = _confirmatory_contract_v2(
        evaluation_settlement_grace_seconds=3,
        minimum_primary_blocks=2,
    )
    options = _v4_options(
        name="pr27-certificate-settlement",
        contract=contract,
        test_days=4,
    )
    discovery_start, cutoff_at = await _matured_v3_schedule(
        conn,
        options=options,
        margin=timedelta(seconds=2),
    )
    folds = await _insert_backdated_manifest(
        conn,
        name=options.name,
        options=options,
        discovery_start=discovery_start,
        cutoff_at=cutoff_at,
    )
    knowledge_cutoff = folds[-1]["test_maturity_at"]
    evaluation_not_before = knowledge_cutoff + timedelta(seconds=3)

    visible_ids: list[int] = []
    for day in (0, 1):
        slot = _align_forward(
            folds[0]["test_start"] + timedelta(days=day, hours=1),
            minutes=15,
        )
        visible_ids.append(
            await _insert_confirmatory_bundle(
                conn,
                observed_at=slot,
                directional_return_pct=2.0,
                snapshot_cost_bps=0.0,
            )
        )
    late_slot = _align_forward(
        folds[0]["test_start"] + timedelta(days=2, hours=1),
        minutes=15,
    )
    late_id = await _insert_confirmatory_bundle(
        conn,
        observed_at=late_slot,
        directional_return_pct=100.0,
        snapshot_cost_bps=0.0,
    )

    schema = await conn.fetchval("SELECT current_schema()")
    cert_conn = await asyncpg.connect(_dsn())
    await cert_conn.execute(f'SET search_path TO "{schema}", public')
    await cert_conn.execute("SET TIME ZONE 'UTC'")
    transaction = cert_conn.transaction()
    await transaction.start()
    try:
        # Read committed source first, then obtain the real DB clock, matching
        # production certification order.  Keep the certificate transaction
        # open across the frozen cutoff to reproduce the narrow commit window.
        source_count = await cert_conn.fetchval(
            "SELECT count(*) FROM signal_observation WHERE observation_id=ANY($1::bigint[])",
            visible_ids,
        )
        assert source_count == len(visible_ids)
        verified_visible_at = await cert_conn.fetchval("SELECT clock_timestamp()")
        assert verified_visible_at <= knowledge_cutoff
        await _insert_direct_visibility_certificates(
            cert_conn,
            observation_ids=visible_ids,
            verified_visible_at=verified_visible_at,
        )

        await _wait_past(conn, knowledge_cutoff)
        during_grace = await evaluate_walk_forward_authoritative(conn, options.name)
        assert during_grace["confirmatory_state"] == "not_ready"
        assert during_grace["confirmatory_result"]["readiness_reason"] == (
            "certificate_settlement_grace"
        )
        assert during_grace["authoritative_result"]["persisted"] is False
        await transaction.commit()
    except BaseException:
        if cert_conn.is_in_transaction():
            await transaction.rollback()
        raise
    finally:
        await cert_conn.close()

    await _wait_past(conn, evaluation_not_before)
    authoritative = await evaluate_walk_forward_authoritative(conn, options.name)
    assert authoritative["authoritative_result"]["persisted"] is True
    assert authoritative["confirmatory_result"]["n_evaluated_actionable"] == 2

    # A certificate stamped after the knowledge cutoff remains excluded even
    # though it commits before this later recomputation.
    late_verified_at = await conn.fetchval("SELECT clock_timestamp()")
    assert late_verified_at > knowledge_cutoff
    await _insert_direct_visibility_certificates(
        conn,
        observation_ids=[late_id],
        verified_visible_at=late_verified_at,
    )
    recomputed = await evaluate_walk_forward_authoritative(conn, options.name)
    assert recomputed["authoritative_result"]["reused_existing"] is True
    assert recomputed["confirmatory_result"]["n_evaluated_actionable"] == 2
    assert (
        recomputed["authoritative_result"]["result_hash"]
        == authoritative["authoritative_result"]["result_hash"]
    )
