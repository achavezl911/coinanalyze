from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT"


def _marked_ddl(path: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    return source.split(f"-- {MARKER}_BEGIN", 1)[1].split(
        f"-- {MARKER}_END", 1
    )[0].strip()


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


def test_pr27_documentation_states_ex_funding_and_no_calibration_selection() -> None:
    documentation = (
        ROOT / "docs/PR27_CONFIRMATORY_ENDPOINT_INTEGRITY.md"
    ).read_text(encoding="utf-8")
    assert "funding_semantics = excluded_v1" in documentation
    assert "No selecciona símbolo, horizonte, MES" in documentation
    assert "no crea manifest de producción" in documentation
