"""PR27-R03 adversarial PostgreSQL suite: A -> B -> A must stay detectable.

Replay proves the frozen kernel reproduces the stored context.  It cannot prove
the stored context was built from the right market data, because the routing
that selected it is a runtime value the context never captured.  These tests
exercise the two enforcement points that close it: producer-time attestation and
evaluation-time row provenance.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime

import asyncpg
import pytest

from app import config
from app.config import DEFAULT_MARKET_CATALOG
from app.scalp_logic import compute_scalp_summary
from app.signal_ledger import persist_signal_observations
from app.signal_runtime_contract import (
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    compute_scientific_runtime_contract,
    scientific_runtime_contract,
)
from app.signal_walk_forward import (
    ConfirmatoryScientificIntegrityError,
    evaluate_walk_forward_authoritative,
)
from tests.test_signal_replay_postgres import _ctx
from tests.test_signal_walk_forward_confirmatory_postgres import (
    _REGISTERED_RUNTIME_CONTRACT_DIGEST,
    PR27_R03_MIGRATION_SQL,
    _connect_schema,
    _drop_schema,
    _favorable_replay_integrity_rows,
    _prepare_ready_v4,
    _schema_name,
)

FOREIGN_DIGEST = "b" * 64


@pytest.fixture
async def conn():
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        yield connection
    finally:
        await _drop_schema(connection, schema)


def _routing_b() -> tuple:
    """Catalog B: BTC's spot leg repointed, everything else identical."""

    return tuple(
        replace(item, base_asset="ETH") if item.symbol == "BTCUSDT_PERP.A" else item
        for item in DEFAULT_MARKET_CATALOG
    )


# --------------------------------------------------------------------------
# TEST 5 -- a future spec-v4 OOS row lacking prospective provenance
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_runtime_contract_provenance_fails_hard_not_inconclusive(
    conn: asyncpg.Connection,  # noqa: F811
) -> None:
    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-r03-missing-provenance",
        row_specs=_favorable_replay_integrity_rows(
            {
                "runtime_contract_version": None,
                "runtime_contract_digest": None,
            }
        ),
    )

    with pytest.raises(
        ConfirmatoryScientificIntegrityError, match="lack the scientific runtime contract"
    ):
        await evaluate_walk_forward_authoritative(conn, options.name)

    # Not filtered out of the denominator, not downgraded to INCONCLUSIVE.
    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 0


# --------------------------------------------------------------------------
# TEST 4 -- persisted provenance disagrees with the frozen manifest
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_divergent_runtime_contract_provenance_blocks_authoritative_insert(
    conn: asyncpg.Connection,  # noqa: F811
) -> None:
    """The row is economically favorable; it still cannot become a result."""

    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-r03-divergent-provenance",
        row_specs=_favorable_replay_integrity_rows(
            {
                "runtime_contract_version": SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
                "runtime_contract_digest": FOREIGN_DIGEST,
            }
        ),
    )

    with pytest.raises(
        ConfirmatoryScientificIntegrityError,
        match="produced under a different scientific",
    ):
        await evaluate_walk_forward_authoritative(conn, options.name)

    assert await conn.fetchval(
        "SELECT count(*) FROM signal_walk_forward_confirmatory_result"
    ) == 0


@pytest.mark.asyncio
async def test_matching_provenance_persists_and_records_both_digests(
    conn: asyncpg.Connection,  # noqa: F811
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
        name="pr27-r03-matching-provenance",
        row_specs=rows,
    )

    report = await evaluate_walk_forward_authoritative(conn, options.name)
    frozen = scientific_runtime_contract()
    assert report["scientific_runtime_contract"] == frozen
    assert report["confirmatory_result"][
        "scientific_runtime_contract_integrity"
    ] == {
        "runtime_contract_version": SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
        "runtime_contract_digest": frozen["digest"],
        "checked_observation_n": 6,
        "complete": True,
    }

    stored = await conn.fetchrow(
        """
        SELECT scientific_implementation_digest,scientific_runtime_contract_digest
        FROM signal_walk_forward_confirmatory_result
        """
    )
    assert stored["scientific_runtime_contract_digest"] == frozen["digest"]
    assert stored["scientific_implementation_digest"] != frozen["digest"]


# --------------------------------------------------------------------------
# TESTS 1 and 3 -- producer-time attestation and A -> B -> A
# --------------------------------------------------------------------------


async def _persist_once(connection: asyncpg.Connection) -> int:
    ctx = _ctx()
    return await persist_signal_observations(
        connection,
        "BTCUSDT_PERP.A",
        ctx,
        compute_scalp_summary(ctx),
        collector_generation=1,
        collector_shard_index=0,
        collector_shard_count=1,
    )


@pytest.mark.asyncio
async def test_a_then_b_then_a_leaves_no_b_evidence(monkeypatch) -> None:
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        # --- routing A: evidence is written and stamped with A's digest.
        assert await _persist_once(connection) == 1
        first = await connection.fetchrow(
            """
            SELECT observation_id,runtime_contract_version,runtime_contract_digest
            FROM signal_observation
            """
        )
        assert first["runtime_contract_digest"] == _REGISTERED_RUNTIME_CONTRACT_DIGEST
        assert first["runtime_contract_version"] == SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1

        # --- routing B: the producer refuses before any row is written.
        monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", _routing_b())
        assert (
            compute_scientific_runtime_contract()["digest"]
            != _REGISTERED_RUNTIME_CONTRACT_DIGEST
        )
        with pytest.raises(RuntimeError, match="not an authorized environment profile"):
            await _persist_once(connection)
        assert await connection.fetchval(
            "SELECT count(*) FROM signal_observation"
        ) == 1

        # --- routing restored to A: still exactly one row, still A's digest.
        monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", DEFAULT_MARKET_CATALOG)
        digests = await connection.fetch(
            "SELECT DISTINCT runtime_contract_digest FROM signal_observation"
        )
        assert [row["runtime_contract_digest"] for row in digests] == [
            _REGISTERED_RUNTIME_CONTRACT_DIGEST
        ]
    finally:
        await _drop_schema(connection, schema)


# --------------------------------------------------------------------------
# Schema: additive, append-only, no backfill
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recorded_provenance_is_append_only() -> None:
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        await _persist_once(connection)
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                "UPDATE signal_observation SET runtime_contract_digest=$1",
                FOREIGN_DIGEST,
            )
    finally:
        await _drop_schema(connection, schema)


@pytest.mark.asyncio
async def test_version_and_digest_must_be_set_or_absent_together() -> None:
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        await _persist_once(connection)
        with pytest.raises(asyncpg.PostgresError):
            await connection.execute(
                """
                INSERT INTO signal_observation(
                  observed_at,observed_minute,symbol,signal_family,
                  is_periodic,is_transition,
                  logic_version,evidence_version,sampling_version,
                  decision_status,direction,actionable,state,confidence,reason,
                  long_score,short_score,evidence_coverage_pct,
                  collector_shard_index,collector_shard_count,
                  decision_fingerprint,evidence,
                  runtime_contract_version
                ) VALUES(
                  now(),date_trunc('minute',now()),'BTCUSDT_PERP.A','scalp',
                  true,false,
                  'scalp-summary-v1',6,1,
                  'evaluable','neutral',false,'x','baja','y',
                  1,1,100,
                  0,1,
                  repeat('a',64),'{}'::jsonb,
                  1
                )
                """
            )
    finally:
        await _drop_schema(connection, schema)


@pytest.mark.asyncio
async def test_legacy_rows_keep_null_provenance_without_backfill() -> None:
    """Evidence-v6 is not reinterpreted: no CHECK ties it to the new columns."""

    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        await connection.execute(
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
              now(),date_trunc('minute',now()),'BTCUSDT_PERP.A','scalp',
              true,false,
              'scalp-summary-v1',6,1,
              'evaluable','neutral',false,'x','baja','y',
              1,1,100,
              0,1,
              repeat('a',64),'{}'::jsonb
            )
            """
        )
        row = await connection.fetchrow(
            """
            SELECT evidence_version,runtime_contract_version,runtime_contract_digest
            FROM signal_observation
            """
        )
        assert row["evidence_version"] == 6
        assert row["runtime_contract_version"] is None
        assert row["runtime_contract_digest"] is None

        # Re-applying the migration must not invent a digest for it.
        await connection.execute(PR27_R03_MIGRATION_SQL)
        assert await connection.fetchval(
            "SELECT count(*) FROM signal_observation "
            "WHERE runtime_contract_digest IS NOT NULL"
        ) == 0
    finally:
        await _drop_schema(connection, schema)


@pytest.mark.asyncio
async def test_forward_migration_is_idempotent_on_an_already_migrated_schema() -> None:
    schema = _schema_name()
    connection = await _connect_schema(schema)
    try:
        for _ in range(2):
            await connection.execute(PR27_R03_MIGRATION_SQL)
        columns = await connection.fetch(
            """
            SELECT column_name,is_nullable
            FROM information_schema.columns
            WHERE table_schema=current_schema()
              AND table_name='signal_observation'
              AND column_name IN
                ('runtime_contract_version','runtime_contract_digest')
            ORDER BY column_name
            """
        )
        assert [(row["column_name"], row["is_nullable"]) for row in columns] == [
            ("runtime_contract_digest", "YES"),
            ("runtime_contract_version", "YES"),
        ]
        assert await _persist_once(connection) == 1
    finally:
        await _drop_schema(connection, schema)


@pytest.mark.asyncio
async def test_authoritative_result_rejects_a_digest_the_manifest_did_not_freeze(
    conn: asyncpg.Connection,  # noqa: F811
) -> None:
    """Even a direct SQL INSERT cannot declare a foreign runtime contract."""

    options, _, _ = await _prepare_ready_v4(
        conn,
        name="pr27-r03-direct-sql-guard",
    )
    manifest = await conn.fetchrow(
        "SELECT manifest_id,manifest_hash,spec FROM signal_walk_forward_manifest "
        "WHERE manifest_name=$1",
        options.name,
    )
    spec = json.loads(str(manifest["spec"]))
    # Every other frozen value agrees, so the runtime contract is the only
    # thing the trigger can be rejecting.
    with pytest.raises(asyncpg.PostgresError, match="runtime contract digest"):
        await conn.execute(
            """
            INSERT INTO signal_walk_forward_confirmatory_result(
              result_version,manifest_id,manifest_hash,
              scientific_implementation_digest,
              scientific_runtime_contract_digest,
              confirmatory_knowledge_cutoff,evaluation_not_before,
              canonical_result_json,result_hash
            ) VALUES(
              1,$1,$2,$3,$4,$5::timestamptz,$6::timestamptz,
              '{}',encode(sha256(convert_to('{}','UTF8')),'hex')
            )
            """,
            int(manifest["manifest_id"]),
            str(manifest["manifest_hash"]),
            str(spec["scientific_implementation"]["digest"]),
            FOREIGN_DIGEST,
            datetime.fromisoformat(str(spec["confirmatory_knowledge_cutoff"])),
            datetime.fromisoformat(str(spec["evaluation_not_before"])),
        )
