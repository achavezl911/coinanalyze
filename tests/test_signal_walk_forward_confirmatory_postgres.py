"""PR26 spec v3 confirmatory contract: real PostgreSQL 17 end-to-end tests.

Follows this project's established convention (see
tests/test_signal_walk_forward_postgres.py, tests/test_pr25_research_knowledge_time_postgres.py):
no conftest.py, local per-file fixtures, a fresh uuid-suffixed schema per
test, TEST_DATABASE_URL required (tests skip cleanly without it).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_confirmatory import ConfirmatoryContract
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG
from app.signal_replay import SCALP_SIGNAL_LOGIC_VERSION
from app.signal_visibility import certify_final_outcomes, certify_research_bundles
from app.signal_walk_forward import (
    WALK_FORWARD_REPORT_VERSION_V3,
    WALK_FORWARD_SPEC_VERSION_V3,
    WalkForwardManifestOptions,
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
BUNDLE_VISIBILITY_DDL = _ddl("PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY")
FINAL_VISIBILITY_DDL = _ddl("PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY")

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
    spec = {
        **_static_options_spec(options),
        "name": name,
        "created_at": created_at,
        "discovery_start": discovery_start,
        "cutoff_at": cutoff_at,
        "folds": folds,
    }
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


async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    direction: str,
    reference_price: float = 100.0,
    evidence_version: int = 6,
) -> int:
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
              $1,date_trunc('minute',$1::timestamptz),$1,
              'BTCUSDT_PERP.A','scalp',
              true,false,
              'scalp-summary-v1',$3,1,
              'evaluable',$2,true,'Long Momentum','media','test',
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
            evidence_version,
            reference_price,
        )
    )


async def _insert_frame(conn: asyncpg.Connection, observation_id: int, observed_at: datetime) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context,created_at
        ) VALUES($1,1,$2,repeat('b',64),'{"now_ms":1}'::jsonb,$2)
        """,
        observation_id,
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
) -> None:
    observation = await conn.fetchrow(
        "SELECT direction,reference_price FROM signal_observation WHERE observation_id=$1",
        observation_id,
    )
    assert observation is not None
    direction = observation["direction"]
    reference_price = float(observation["reference_price"])

    market_return_pct = (
        directional_return_pct if direction == "long" else -directional_return_pct
    )
    end_price = reference_price * (1.0 + market_return_pct / 100.0)
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
) -> int:
    """A complete evidence_version=6 bundle: one observation, replay frame,
    all 8 outcome horizons (only ``primary_horizon`` evaluated with a real
    return; the rest pending placeholders, matching the certification
    completeness requirement), and execution snapshots for both venues."""

    observation_id = await _insert_observation(conn, observed_at=observed_at, direction="long")
    await _insert_frame(conn, observation_id, observed_at)

    window_start = observed_at + timedelta(minutes=1)
    for horizon in OUTCOME_HORIZONS_MINUTES:
        if horizon == primary_horizon:
            await _insert_outcome(
                conn,
                observation_id=observation_id,
                window_start=window_start,
                horizon_minutes=horizon,
                directional_return_pct=directional_return_pct,
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
    )
    if both_venues:
        await _insert_execution_snapshot(
            conn, observation_id=observation_id, observed_at=observed_at, exchange="bybit"
        )
    return observation_id


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

    contract = _confirmatory_contract(minimum_primary_blocks=1)
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


# ---------------------------------------------------------------------------
# PASS / FAIL / INCONCLUSIVE at final frozen maturity.
# ---------------------------------------------------------------------------


async def _insert_spread_bundles(
    conn: asyncpg.Connection,
    *,
    test_start: datetime,
    directional_return_pct: float,
    day_count: int,
) -> None:
    for day in range(day_count):
        observed_at = test_start + timedelta(days=day, hours=1)
        await _insert_confirmatory_bundle(
            conn, observed_at=observed_at, directional_return_pct=directional_return_pct
        )


@pytest.mark.asyncio
async def test_confirmatory_pass_at_final_maturity_with_consistent_positive_edge(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-pass-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]

    # 6 distinct calendar-day blocks, each with a strongly positive return
    # (~490bps net of the 5bps entry cost, at zero fee/stress).
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

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    assert report["report_version"] == WALK_FORWARD_REPORT_VERSION_V3
    assert report["walk_forward_spec_version"] == WALK_FORWARD_SPEC_VERSION_V3
    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "pass"
    assert result["primary_block_count"] == 6
    assert result["n_evaluated_actionable"] == 6
    assert result["ci_lower_bps"] > contract.minimum_effect_bps
    assert result["primary_estimate_mean_bps"] == pytest.approx(489.75, abs=1.0)

    # Exploratory positive_oos_gate_count is 0 (n=1/day-group is below the
    # default min_group_n reporting guardrail) while the confirmatory
    # decision is a clean PASS -- proof the two are structurally decoupled.
    assert report["gates"]["positive_oos_gate_count"] == 0


@pytest.mark.asyncio
async def test_confirmatory_fail_at_final_maturity_with_consistent_negative_edge(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-fail-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]

    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=-5.0, day_count=6
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "fail"
    assert result["ci_upper_bps"] <= 0.0


@pytest.mark.asyncio
async def test_confirmatory_inconclusive_when_matured_blocks_below_minimum(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=5, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-inconclusive-blocks-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]

    # Only 2 distinct calendar-day blocks -- strongly positive, but below
    # minimum_primary_blocks=5, so this must stay inconclusive regardless of
    # how extreme the observed edge is.
    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=5.0, day_count=2
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    result = report["confirmatory_result"]
    assert report["confirmatory_state"] == "inconclusive"
    assert result["primary_block_count"] == 2
    assert result["ci_lower_bps"] is None  # bootstrap never ran


@pytest.mark.asyncio
async def test_confirmatory_missing_nonvalid_and_insufficient_depth_stay_distinct(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=1, minimum_effect_bps=-1_000_000.0)
    options = _v3_options(name="pr26-coverage-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]

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

    async with conn.transaction(isolation="repeatable_read", readonly=True):
        report = await evaluate_walk_forward(conn, options.name)

    coverage = report["confirmatory_result"]["coverage"]
    assert coverage["n_evaluated_actionable"] == 2
    assert coverage["snapshot_nonvalid_n"] == 1
    assert coverage["snapshot_missing_n"] == 0
    assert coverage["insufficient_depth_n"] == 0
    assert coverage["n_cost_evaluable"] == 1
    assert coverage["cost_evaluable_pct"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# No adaptive/optional stopping: re-evaluating a matured manifest later must
# return an identical confirmatory_result.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmatory_result_is_identical_across_repeated_evaluations(
    conn: asyncpg.Connection,
) -> None:
    discovery_start = datetime(2020, 1, 1, tzinfo=UTC)
    cutoff_at = discovery_start + timedelta(days=7)

    contract = _confirmatory_contract(minimum_primary_blocks=3, minimum_effect_bps=100.0)
    options = _v3_options(name="pr26-repeatable-test", contract=contract)
    folds = await _insert_backdated_manifest(
        conn, name=options.name, options=options, discovery_start=discovery_start, cutoff_at=cutoff_at
    )
    test_start = folds[0]["test_start"]
    await _insert_spread_bundles(
        conn, test_start=test_start, directional_return_pct=5.0, day_count=4
    )
    await certify_research_bundles(conn)
    await certify_final_outcomes(conn)

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

    contract = _confirmatory_contract(minimum_primary_blocks=1)
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
    assert v1_report["report_version"] == 1
    assert v2_report["report_version"] == 2


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
