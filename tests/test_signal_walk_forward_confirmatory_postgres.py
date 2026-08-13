"""PR26 spec v3 confirmatory contract: real PostgreSQL 17 end-to-end tests.

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

from app.signal_confirmatory import ConfirmatoryContract, confirmatory_block_key
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_SETTLEMENT_LAG, outcome_window
from app.signal_replay import SCALP_SIGNAL_LOGIC_VERSION
from app.signal_visibility import certify_final_outcomes, certify_research_bundles
from app.signal_walk_forward import (
    WALK_FORWARD_REPORT_VERSION_V3,
    WALK_FORWARD_SPEC_VERSION_V3,
    WalkForwardManifestOptions,
    _expected_utc_nonoverlap_slot_count,
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


_DIRECTION_STATE_DEFAULTS = {
    "long": "Long Momentum",
    "short": "Short Momentum",
    "neutral": "Neutral Range",
}


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
) -> int:
    """``direction`` may be ``"long"``/``"short"`` (actionable) or
    ``"neutral"`` (non-actionable, periodic-only) -- the latter is how
    PR26's confirmatory baseline cohort fixtures insert rows that must be
    evaluated but must never become an actionable primary row. ``actionable``
    and ``state`` default from ``direction`` but can be overridden
    independently (e.g. to prove the baseline cohort is insensitive to
    ``state``/``regime_label``)."""

    if actionable is None:
        actionable = direction in ("long", "short")
    if state is None:
        state = _DIRECTION_STATE_DEFAULTS.get(direction, "Neutral Range")
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
              'evaluable',$2,$5,$6,'media','test',
              $4,'futures_realtime_combined',
              70,30,90,
              $7,
              0,1,
              repeat('a',64),'{}'::jsonb
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

    # "long"/"neutral" apply no sign flip (a neutral row has no directional
    # convention of its own, so its market_return_pct is just the supplied
    # value directly); "short" flips it, matching the live sign convention
    # PR5 applies for a short signal.
    market_return_pct = (
        directional_return_pct
        if direction in ("long", "neutral")
        else -directional_return_pct
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

    observation_id = await _insert_observation(
        conn,
        observed_at=observed_at,
        direction=direction,
        state=state,
        regime_label=regime_label,
    )
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

    observation_id = await _insert_observation(conn, observed_at=observed_at, direction=direction)
    await _insert_frame(conn, observation_id, observed_at)

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

    for day in range(day_count):
        await _insert_confirmatory_bundle(
            conn,
            observed_at=test_start + timedelta(days=day, hours=1),
            directional_return_pct=actionable_directional_return_pct,
            direction=actionable_direction,
        )
        await _insert_confirmatory_bundle(
            conn,
            observed_at=test_start + timedelta(days=day, hours=2),
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
    await _insert_confirmatory_bundle(
        conn,
        observed_at=test_start + timedelta(hours=1),
        directional_return_pct=5.0,
        direction="long",
    )
    await _insert_confirmatory_bundle(
        conn,
        observed_at=test_start + timedelta(hours=2),
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
    assert report["confirmatory_state"] in ("pass", "fail")


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
