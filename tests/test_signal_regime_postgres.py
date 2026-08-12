from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
import pytest

from app.signal_backtest import DENSE_PERIODIC, UTC_NONOVERLAP
from app.signal_regime import (
    RegimeAnalysisOptions,
    _regime_status_sql,
    build_signal_regime_report,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

LEDGER_DDL = (
    SCHEMA_SQL.split("-- PR4_SIGNAL_OBSERVATION_LEDGER_BEGIN", 1)[1]
    .split("-- PR4_SIGNAL_OBSERVATION_LEDGER_END", 1)[0]
)
OUTCOME_DDL = (
    SCHEMA_SQL.split("-- PR5_SIGNAL_OUTCOMES_BEGIN", 1)[1]
    .split("-- PR5_SIGNAL_OUTCOMES_END", 1)[0]
)
REPLAY_DDL = (
    SCHEMA_SQL.split("-- PR6_SIGNAL_REPLAY_BEGIN", 1)[1]
    .split("-- PR6_SIGNAL_REPLAY_END", 1)[0]
)

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

INSERT INTO symbols(symbol)
VALUES ('BTCUSDT_PERP.A'),('ETHUSDT_PERP.A');
"""


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


def _schema_name() -> str:
    return f"test_signal_regime_{uuid.uuid4().hex}"


async def _connect_schema(schema: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(_dsn())
    await conn.execute(f'CREATE SCHEMA "{schema}"')
    await conn.execute(f'SET search_path TO "{schema}", public')
    await conn.execute("SET TIME ZONE 'UTC'")
    await conn.execute(BASE_SQL)
    await conn.execute(LEDGER_DDL)
    await conn.execute(OUTCOME_DDL)
    await conn.execute(REPLAY_DDL)
    return conn


async def _drop_schema(conn: asyncpg.Connection, schema: str) -> None:
    await conn.execute("ROLLBACK")
    await conn.execute("SET search_path TO public")
    await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    await conn.close()


async def _reader_status(
    *, evidence_version: int, regime_logic_version: int | None
) -> str:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    observed_at = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
    try:
        return str(
            await conn.fetchval(
                f"""
                SELECT {_regime_status_sql("obs")}
                FROM (
                  SELECT
                    $1::smallint AS evidence_version,
                    $2::smallint AS regime_logic_version,
                    25.0::float8 AS regime_score,
                    'measured regime'::text AS regime_label,
                    $3::timestamptz AS metrics_snapshot_ts,
                    $3::timestamptz AS price_cutoff_at,
                    $3::timestamptz AS metrics_cutoff_at,
                    $4::timestamptz AS observed_at
                ) AS obs
                """,
                evidence_version,
                regime_logic_version,
                observed_at - timedelta(minutes=1),
                observed_at,
            )
        )
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_pr22_regime_reader_v3_requires_regime_logic_v2() -> None:
    assert await _reader_status(evidence_version=3, regime_logic_version=1) == "unavailable"
    assert await _reader_status(evidence_version=3, regime_logic_version=2) == "available"


@pytest.mark.asyncio
async def test_pr23_regime_reader_v4_requires_regime_logic_v2() -> None:
    assert await _reader_status(evidence_version=4, regime_logic_version=1) == "unavailable"
    assert await _reader_status(evidence_version=4, regime_logic_version=2) == "available"


@pytest.mark.asyncio
async def test_pr22_regime_reader_v3_null_version_is_unavailable() -> None:
    assert await _reader_status(evidence_version=3, regime_logic_version=None) == "unavailable"
    assert await _reader_status(evidence_version=4, regime_logic_version=None) == "unavailable"


@pytest.mark.asyncio
async def test_pr22_regime_reader_legacy_evidence_keeps_legacy_semantics() -> None:
    assert await _reader_status(evidence_version=1, regime_logic_version=None) == "available"
    assert await _reader_status(evidence_version=2, regime_logic_version=None) == "available"


def _evidence(
    *,
    imbalance_l5: float | None,
    missing_components: list[str] | None = None,
) -> dict[str, object]:
    return {
        "fut_delta_1m": 10.0,
        "fut_delta_3m": 20.0,
        "fut_volume_1m": 100.0,
        "spot_fut_divergence_norm": 0.2,
        "imbalance_l5": imbalance_l5,
        "absorption": "Neutra",
        "long_liq_5m": 0.0,
        "short_liq_5m": 0.0,
        "liquidations_measured": True,
        "oi_chg_15m_pct": 0.1,
        "price_move_15m_pct": 0.2,
        "oi_contributes_direction": True,
        "oi_directional_support": 1.0,
        "vwap_dist_pct": 0.05,
        "missing_components": missing_components or [],
    }


def _context() -> dict[str, object]:
    return {
        "now_ms": 1_700_000_000_000.0,
        "fut_volume_3m": 200.0,
    }


async def _insert_observation(
    conn: asyncpg.Connection,
    *,
    observed_at: datetime,
    symbol: str,
    state: str,
    direction: str,
    actionable: bool,
    evidence: dict[str, object],
    regime_score: float | None,
    regime_label: str | None,
    metrics_snapshot_ts: datetime | None = None,
    price_cutoff_at: datetime | None = None,
    metrics_cutoff_at: datetime | None = None,
    is_periodic: bool = True,
    is_transition: bool = False,
    confidence: str = "media",
) -> int:
    observed_minute = observed_at.replace(second=0, microsecond=0)
    metrics_snapshot_ts = (
        metrics_snapshot_ts
        if metrics_snapshot_ts is not None
        else observed_at - timedelta(seconds=30)
    )
    price_cutoff_at = (
        price_cutoff_at
        if price_cutoff_at is not None
        else observed_at - timedelta(minutes=1)
    )
    metrics_cutoff_at = (
        metrics_cutoff_at
        if metrics_cutoff_at is not None
        else observed_at - timedelta(minutes=5)
    )

    return int(
        await conn.fetchval(
            """
            INSERT INTO signal_observation(
              observed_at,observed_minute,symbol,signal_family,
              is_periodic,is_transition,
              logic_version,evidence_version,sampling_version,
              decision_status,direction,actionable,state,confidence,reason,
              reference_price,reference_price_source,
              long_score,short_score,evidence_coverage_pct,
              metrics_snapshot_ts,regime_score,regime_label,
              price_cutoff_at,metrics_cutoff_at,
              collector_shard_index,collector_shard_count,
              decision_fingerprint,evidence
            ) VALUES(
              $1,$2,$3,'scalp',
              $4,$5,
              'scalp-summary-v1',1,1,
              'evaluable',$6,$7,$8,$9,'test observation',
              100.0,'futures_realtime_combined',
              60.0,40.0,100.0,
              $10,$11,$12,$13,$14,
              0,1,
              repeat('a',64),$15::jsonb
            )
            RETURNING observation_id
            """,
            observed_at,
            observed_minute,
            symbol,
            is_periodic,
            is_transition,
            direction,
            actionable,
            state,
            confidence,
            metrics_snapshot_ts,
            regime_score,
            regime_label,
            price_cutoff_at,
            metrics_cutoff_at,
            json.dumps(evidence),
        )
    )


async def _insert_frame(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
) -> None:
    await conn.execute(
        """
        INSERT INTO signal_replay_frame(
          observation_id,context_version,context_as_of,context_hash,context
        ) VALUES($1,1,$2,repeat('b',64),$3::jsonb)
        """,
        observation_id,
        observed_at,
        json.dumps(_context()),
    )


async def _insert_outcome(
    conn: asyncpg.Connection,
    observation_id: int,
    observed_at: datetime,
    *,
    horizon: int,
    market_return: float,
    directional_return: float | None,
    mfe: float | None,
    mae: float | None,
) -> None:
    start = observed_at.replace(second=0, microsecond=0) + timedelta(minutes=1)
    end = start + timedelta(minutes=horizon)
    due = end + timedelta(minutes=42)
    await conn.execute(
        """
        INSERT INTO signal_outcome(
          observation_id,horizon_minutes,window_start,window_end,due_at,
          next_attempt_at,path_start_delay_seconds,bars_expected,bars_found,
          outcome_version,status,attempts,last_attempt_at,finalized_at,
          entry_reference_price,end_price,max_high,min_low,
          market_return_pct,up_excursion_pct,down_excursion_pct,
          directional_return_pct,mfe_pct,mae_pct
        ) VALUES(
          $1,$2,$3,$4,$5,
          $5,30,$2,$2,
          1,'evaluated',1,$5,$5,
          100,101,102,99,
          $6,2,-1,
          $7,$8,$9
        )
        """,
        observation_id,
        horizon,
        start,
        end,
        due,
        market_return,
        directional_return,
        mfe,
        mae,
    )


def _quarter_hour_anchor(now: datetime) -> datetime:
    ref = now.astimezone(UTC) - timedelta(days=2)
    return ref.replace(
        minute=(ref.minute // 15) * 15,
        second=0,
        microsecond=0,
    )


@pytest.mark.asyncio
async def test_regime_report_preserves_provenance_and_measures_alignment() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        anchor = _quarter_hour_anchor(datetime.now(UTC))

        # A: aligned long winner in a strong bullish regime.
        a_at = anchor + timedelta(seconds=30)
        a = await _insert_observation(
            conn,
            observed_at=a_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.75),
            regime_score=70.0,
            regime_label="Continuación alcista orgánica",
        )
        await _insert_frame(conn, a, a_at)
        await _insert_outcome(
            conn,
            a,
            a_at,
            horizon=15,
            market_return=1.0,
            directional_return=1.0,
            mfe=1.5,
            mae=0.2,
        )

        # B: one minute later; contrarian long loser in a bearish regime.
        # Dense includes it. UTC 15m non-overlap excludes it by clock only.
        b_at = anchor + timedelta(minutes=1, seconds=30)
        b = await _insert_observation(
            conn,
            observed_at=b_at,
            symbol="BTCUSDT_PERP.A",
            state="Long Pullback",
            direction="long",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.25),
            regime_score=-50.0,
            regime_label="Distribución (Bearish)",
        )
        await _insert_frame(conn, b, b_at)
        await _insert_outcome(
            conn,
            b,
            b_at,
            horizon=15,
            market_return=-0.5,
            directional_return=-0.5,
            mfe=0.8,
            mae=0.6,
        )

        # C: available balanced regime with a neutral final decision.
        c_at = anchor + timedelta(seconds=30)
        c = await _insert_observation(
            conn,
            observed_at=c_at,
            symbol="ETHUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
            evidence=_evidence(imbalance_l5=0.5),
            regime_score=0.0,
            regime_label="Lateral / Indecisión",
        )
        await _insert_frame(conn, c, c_at)
        await _insert_outcome(
            conn,
            c,
            c_at,
            horizon=15,
            market_return=0.4,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        # D: truthfully unavailable regime; not relabeled as lateral.
        d_at = anchor - timedelta(minutes=15) + timedelta(seconds=30)
        d = await _insert_observation(
            conn,
            observed_at=d_at,
            symbol="ETHUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
            evidence=_evidence(imbalance_l5=0.5),
            regime_score=None,
            regime_label="Sin datos suficientes",
        )
        await _insert_frame(conn, d, d_at)
        await _insert_outcome(
            conn,
            d,
            d_at,
            horizon=15,
            market_return=-0.2,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        # E: a future metrics snapshot is a provenance anomaly and must not enter
        # available regime performance even though score/label look valid.
        e_at = anchor - timedelta(minutes=30) + timedelta(seconds=30)
        e = await _insert_observation(
            conn,
            observed_at=e_at,
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
            evidence=_evidence(imbalance_l5=0.6),
            regime_score=70.0,
            regime_label="Continuación alcista orgánica",
            metrics_snapshot_ts=e_at + timedelta(minutes=1),
        )
        await _insert_frame(conn, e, e_at)
        await _insert_outcome(
            conn,
            e,
            e_at,
            horizon=15,
            market_return=0.3,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        # Pre-PR6 periodic observation: diagnostic only.
        await _insert_observation(
            conn,
            observed_at=anchor - timedelta(hours=1),
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
            evidence=_evidence(imbalance_l5=0.5),
            regime_score=0.0,
            regime_label="Lateral / Indecisión",
        )

        # Transition-only observation: never enters regular regime grid.
        t_at = anchor - timedelta(minutes=45) + timedelta(seconds=30)
        t = await _insert_observation(
            conn,
            observed_at=t_at,
            symbol="BTCUSDT_PERP.A",
            state="Short Momentum",
            direction="short",
            actionable=True,
            evidence=_evidence(imbalance_l5=0.0),
            regime_score=-80.0,
            regime_label="Capitulación (Bearish)",
            is_periodic=False,
            is_transition=True,
        )
        await _insert_frame(conn, t, t_at)
        await _insert_outcome(
            conn,
            t,
            t_at,
            horizon=15,
            market_return=-9.0,
            directional_return=9.0,
            mfe=9.0,
            mae=0.1,
        )

        options = RegimeAnalysisOptions(
            lookback_days=30,
            horizons=(15,),
            components=("book",),
            sampling_modes=(DENSE_PERIODIC, UTC_NONOVERLAP),
            min_group_n=2,
        )

        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_regime_report(conn, options)

        corpus = report["corpus"]
        assert corpus["periodic_observations"] == 6
        assert corpus["periodic_without_replay_frame"] == 1
        assert corpus["compatible_periodic_observations"] == 5
        assert corpus["transition_only_observations_excluded"] == 1
        assert corpus["regime_available_periodic_observations"] == 3
        assert corpus["regime_unavailable_periodic_observations"] == 1
        assert corpus["regime_invalid_future_provenance_observations"] == 1
        assert corpus["future_metrics_snapshot_anomalies"] == 1
        assert corpus["future_price_cutoff_anomalies"] == 0
        assert corpus["future_metrics_cutoff_anomalies"] == 0
        assert corpus["expected_outcome_rows"] == 5
        assert corpus["requested_outcome_rows"] == 5
        assert corpus["missing_or_wrong_version_outcome_rows"] == 0

        dense = report["views"][DENSE_PERIODIC]

        by_label = dense["signal_by_regime_label"]
        bullish = next(
            row
            for row in by_label
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_label"] == "Continuación alcista orgánica"
        )
        bearish = next(
            row
            for row in by_label
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_label"] == "Distribución (Bearish)"
        )
        assert bullish["gross_expectancy_pct"] == pytest.approx(1.0)
        assert bearish["gross_expectancy_pct"] == pytest.approx(-0.5)
        # BTC actionable baseline is (1.0 + -0.5) / 2 = 0.25.
        assert bullish["baseline_gross_expectancy_pct"] == pytest.approx(0.25)
        assert bullish["expectancy_lift_vs_symbol_pct"] == pytest.approx(0.75)
        assert bearish["expectancy_lift_vs_symbol_pct"] == pytest.approx(-0.75)

        by_band = dense["signal_by_regime_score_band"]
        strong_bullish = next(
            row
            for row in by_band
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_score_band"] == "strong_bullish"
        )
        bearish_band = next(
            row
            for row in by_band
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_score_band"] == "bearish"
        )
        assert strong_bullish["gross_expectancy_pct"] == pytest.approx(1.0)
        assert bearish_band["gross_expectancy_pct"] == pytest.approx(-0.5)

        alignment = dense["signal_regime_alignment"]
        aligned = next(
            row
            for row in alignment
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_alignment"] == "aligned"
        )
        contrarian = next(
            row
            for row in alignment
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["regime_alignment"] == "contrarian"
        )
        assert aligned["gross_expectancy_pct"] == pytest.approx(1.0)
        assert contrarian["gross_expectancy_pct"] == pytest.approx(-0.5)

        component = dense["component_by_regime_label"]
        book_bull = next(
            row
            for row in component
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["component"] == "book"
            and row["regime_label"] == "Continuación alcista orgánica"
        )
        book_bear = next(
            row
            for row in component
            if row["symbol"] == "BTCUSDT_PERP.A"
            and row["component"] == "book"
            and row["regime_label"] == "Distribución (Bearish)"
        )
        assert book_bull["missing_semantics_mismatch_observations"] == 0
        assert book_bear["missing_semantics_mismatch_observations"] == 0
        assert book_bull["standalone_directional_expectancy_pct"] == pytest.approx(1.0)
        assert book_bear["standalone_directional_expectancy_pct"] == pytest.approx(0.5)

        sparse = report["views"][UTC_NONOVERLAP]
        sparse_alignment = sparse["signal_regime_alignment"]
        btc_sparse = [
            row for row in sparse_alignment
            if row["symbol"] == "BTCUSDT_PERP.A"
        ]
        assert len(btc_sparse) == 1
        assert btc_sparse[0]["regime_alignment"] == "aligned"
        assert btc_sparse[0]["gross_expectancy_pct"] == pytest.approx(1.0)

        distribution = report["regime_distribution"]
        assert any(
            row["regime_status"] == "unavailable"
            and row["regime_label"] == "Sin datos suficientes"
            for row in distribution
        )
        assert any(
            row["regime_status"] == "invalid_future_provenance"
            for row in distribution
        )
    finally:
        await _drop_schema(conn, schema)


@pytest.mark.asyncio
async def test_component_missing_mismatch_surfaces_inside_regime_analysis() -> None:
    schema = _schema_name()
    conn = await _connect_schema(schema)
    try:
        observed_at = _quarter_hour_anchor(datetime.now(UTC)) + timedelta(seconds=30)

        observation_id = await _insert_observation(
            conn,
            observed_at=observed_at,
            symbol="BTCUSDT_PERP.A",
            state="No Trade",
            direction="neutral",
            actionable=False,
            confidence="baja",
            evidence=_evidence(
                imbalance_l5=None,
                missing_components=[],
            ),
            regime_score=0.0,
            regime_label="Lateral / Indecisión",
        )
        await _insert_frame(conn, observation_id, observed_at)
        await _insert_outcome(
            conn,
            observation_id,
            observed_at,
            horizon=15,
            market_return=0.1,
            directional_return=None,
            mfe=None,
            mae=None,
        )

        options = RegimeAnalysisOptions(
            lookback_days=30,
            horizons=(15,),
            components=("book",),
            sampling_modes=(DENSE_PERIODIC,),
        )
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_regime_report(conn, options)

        row = report["views"][DENSE_PERIODIC]["component_by_regime_label"][0]
        assert row["missing_semantics_mismatch_observations"] == 1
    finally:
        await _drop_schema(conn, schema)
