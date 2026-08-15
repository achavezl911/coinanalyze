from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT"


def _marked_ddl_for(path: str, marker: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    return source.split(f"-- {marker}_BEGIN", 1)[1].split(
        f"-- {marker}_END", 1
    )[0].strip()


def _marked_ddl(path: str) -> str:
    return _marked_ddl_for(path, MARKER)


def test_pr27_schema_and_forward_migration_have_identical_ddl() -> None:
    assert _marked_ddl("sql/schema.sql") == _marked_ddl(
        "sql/migrations/20260816_pr27_confirmatory_integrity.sql"
    )


def test_pr27_migration_creates_no_manifest_result_or_backfill() -> None:
    migration = (
        ROOT / "sql/migrations/20260816_pr27_confirmatory_integrity.sql"
    ).read_text(encoding="utf-8")
    lowered = migration.lower()
    assert "insert into signal_walk_forward_manifest" not in lowered
    assert "insert into signal_walk_forward_confirmatory_result" not in lowered
    assert "update signal_" not in lowered
    assert "delete from signal_" not in lowered


def test_pr27_result_evidence_has_database_boundary_guards() -> None:
    ddl = _marked_ddl("sql/schema.sql")
    for required in (
        "manifest_id bigint NOT NULL UNIQUE",
        "canonical_result_json text NOT NULL",
        "sha256(convert_to(canonical_result_json, 'UTF8'))",
        "evaluation_not_before timestamptz NOT NULL",
        "scientific_implementation_digest text NOT NULL",
        "scientific_runtime_contract_digest text NOT NULL",
        "BEFORE UPDATE OR DELETE",
        "BEFORE TRUNCATE",
        "ON DELETE RESTRICT",
    ):
        assert required in ddl


def test_pr27_down_migration_refuses_to_discard_scientific_evidence() -> None:
    rollback = (
        ROOT / "sql/migrations/20260816_pr27_confirmatory_integrity_down.sql"
    ).read_text(encoding="utf-8")
    assert "spec-v4 manifest" in rollback
    assert "authoritative confirmatory results" in rollback
    assert rollback.index("RAISE EXCEPTION") < rollback.index("DROP TABLE")


def test_required_ci_job_provisions_postgres_17_and_exports_test_dsn() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "Start isolated PostgreSQL 17 test cluster" in workflow
    assert "initdb" in workflow
    assert 'candidate.bind(("127.0.0.1", 0))' in workflow
    assert "listen_addresses='127.0.0.1'" in workflow
    assert "-f sql/schema.sql" in workflow
    assert "TEST_DATABASE_URL=" in workflow
    assert "pytest -q" in workflow
    assert "if: always()" in workflow


def test_pr27_r03_observation_provenance_is_additive_and_never_backfilled() -> None:
    ledger_ddl = _marked_ddl_for("sql/schema.sql", "PR4_SIGNAL_OBSERVATION_LEDGER")
    migration = (
        ROOT / "sql/migrations/20260817_pr27_r03_runtime_contract.sql"
    ).read_text(encoding="utf-8")

    for required in (
        "runtime_contract_version smallint",
        "runtime_contract_digest text",
        "signal_observation_runtime_contract_pairing_check",
    ):
        assert required in ledger_ddl
        assert required in migration

    # Nullable and unconstrained by evidence_version: tying them to evidence-v6
    # would reinterpret an already-published evidence contract.
    assert "runtime_contract_version smallint NOT NULL" not in ledger_ddl
    assert "runtime_contract_digest text NOT NULL" not in ledger_ddl
    for forbidden in (
        "evidence_version = 6 OR runtime_contract",
        "evidence_version=6 OR runtime_contract",
    ):
        assert forbidden not in ledger_ddl

    lowered = migration.lower()
    assert "update signal_observation" not in lowered
    assert "insert into signal_observation" not in lowered
    assert "delete from signal_" not in lowered


def test_pr27_r03_down_migration_refuses_to_discard_recorded_provenance() -> None:
    rollback = (
        ROOT / "sql/migrations/20260817_pr27_r03_runtime_contract_down.sql"
    ).read_text(encoding="utf-8")
    assert "spec-v4 runtime contract" in rollback
    assert "runtime contract provenance already recorded" in rollback
    assert rollback.index("RAISE EXCEPTION") < rollback.index("DROP COLUMN")


def test_pr27_r03_documentation_states_the_runtime_configuration_closure() -> None:
    documentation = (
        ROOT / "docs/PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md"
    ).read_text(encoding="utf-8")
    assert "Contrato científico de configuración en runtime" in documentation
    # The excluded-operational boundary must stay documented, not just asserted.
    for operational in (
        "whale_threshold_usd",
        "large_trade_threshold_usd",
        "bybit_oi_symbol",
        "spot_history_symbol",
    ):
        assert operational in documentation
    assert "Settings.SYMBOLS" in documentation


def test_pr27_documentation_states_ex_funding_and_no_calibration_selection() -> None:
    documentation = (
        ROOT / "docs/PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md"
    ).read_text(encoding="utf-8")
    assert "funding_semantics = excluded_v1" in documentation
    assert "No selecciona símbolo, horizonte, MES" in documentation
    assert "no crea manifest de producción" in documentation
