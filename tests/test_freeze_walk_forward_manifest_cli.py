from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest

import scripts.freeze_walk_forward_manifest as cli
from app.signal_walk_forward import EXECUTION_EXCHANGES

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL = (ROOT / "sql/schema.sql").read_text(encoding="utf-8")

# K65 · el congelador ya no acepta un manifiesto que declare operar en un exchange sin
# tarifarlo, y estos flags no son decorado: sin ellos, estas mismas pruebas de regresion
# congelaban manifiestos que afirmaban en silencio que operar sale gratis en los dos
# sitios. Se derivan de EXECUTION_EXCHANGES para que anadir un exchange no las deje a
# medio tarifar sin ruido. binance conserva su 2.0 porque --primary-taker-fee-bps la ancla.
_FEE_FLAGS = [
    argumento
    for exchange in EXECUTION_EXCHANGES
    for argumento in (
        "--fee-bps-per-side",
        f"{exchange}={2.0 if exchange == 'binance' else 4.0}",
    )
]

_SPEC_V2_FLAGS = {
    "--logic-version": "scalp-summary-v1",
    "--evidence-version": "6",
    "--sampling-version": "1",
    "--context-version": "1",
    "--outcome-version": "1",
    "--execution-snapshot-version": "1",
    "--research-visibility-version": "1",
}

_CONFIRMATORY_FLAGS = {
    "--primary-endpoint-version": "1",
    "--primary-symbol": "BTCUSDT_PERP.A",
    "--primary-horizon": "15",
    "--primary-sampling-mode": "utc_nonoverlap",
    "--primary-exchange": "binance",
    "--primary-size-usd": "1000",
    "--primary-taker-fee-bps": "2.0",
    "--confirmatory-baseline-version": "1",
    "--unmodeled-execution-stress-bps": "1.5",
    "--confirmatory-inference-version": "1",
    "--confirmatory-block-unit": "day",
    "--confirmatory-block-length": "1",
    "--bootstrap-repetitions": "500",
    "--bootstrap-seed": "42",
    "--confidence-level": "0.95",
    "--minimum-effect-bps": "0.0",
    "--minimum-primary-blocks": "5",
    "--minimum-execution-data-coverage-pct": "50.0",
    "--minimum-research-data-coverage-pct": "50.0",
    "--confirmatory-decision-policy": "two_sided_block_bootstrap_ci_vs_minimum_effect_v1",
}
_SPEC_V3_FLAGS = {**_SPEC_V2_FLAGS, **_CONFIRMATORY_FLAGS}


def _spec_v3_args(
    *, name: str, output: Path, omit_flag: str | None = None, acknowledge: bool = True
) -> list[str]:
    args = [
        "--name",
        name,
        "--spec-version",
        "3",
        "--symbol",
        "BTCUSDT_PERP.A",
        "--output",
        str(output),
    ] + _FEE_FLAGS
    if acknowledge:
        args.append("--acknowledge-confirmatory-primary-hypothesis")
    for flag, value in _SPEC_V3_FLAGS.items():
        if flag == omit_flag:
            continue
        args += [flag, value]
    return args


def _dsn() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_DATABASE_URL is not configured")
    return dsn


async def _reset_public_schema(dsn: str) -> None:
    """Give the CLI's own (unconfigurable-schema) connection a clean, current
    ``public`` schema on the disposable test database. This exercises the
    actual CLI/parser/options path end-to-end -- including its own DSN
    resolution and asyncpg.connect() call -- against a real, disposable
    Postgres, never a mock connection."""

    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute(SCHEMA_SQL)
    finally:
        await conn.close()


# A handful of OTHER Postgres test files (e.g. tests/test_coinalyze_rate_limit.py,
# tests/test_db.py, tests/test_data_gaps_postgres.py) connect with no schema
# isolation at all and assume ``public`` on TEST_DATABASE_URL already carries
# a full, current schema.sql deploy persistently -- they never create their
# own uuid-suffixed schema. The CLI under test has no schema-override hook
# either -- it always targets the real ``public`` schema, matching
# production -- so every test here must leave ``public`` back in that SAME
# "schema.sql applied" baseline afterward, not empty, or an unqualified
# lookup in one of those other files (run later against the same disposable
# database) would find nothing.
_restore_public_schema = _reset_public_schema


async def _manifest_row(dsn: str, name: str) -> asyncpg.Record | None:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchrow(
            "SELECT * FROM signal_walk_forward_manifest WHERE manifest_name=$1", name
        )
    finally:
        await conn.close()


@pytest.fixture
def dsn(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    value = _dsn()
    asyncio.run(_reset_public_schema(value))
    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(pg_dsn=value))
    try:
        yield value
    finally:
        asyncio.run(_restore_public_schema(value))


def test_legacy_invocation_resolves_spec_v1_defaults(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "legacy.json"
    cli.main(
        ["--name", "cli-legacy-defaults-test", "--output", str(output)] + _FEE_FLAGS
    )

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["spec"]["spec_version"] == 1
    versions = manifest["spec"]["versions"]
    assert versions["logic_version"] == "scalp-summary-v1"
    assert versions["evidence_version"] == 1
    assert versions["sampling_version"] == 1
    assert versions["context_version"] == 1
    assert versions["outcome_version"] == 1
    assert versions["execution_snapshot_version"] == 1
    assert "research_visibility_version" not in versions

    row = asyncio.run(_manifest_row(dsn, "cli-legacy-defaults-test"))
    assert row is not None
    stored_spec = json.loads(row["spec"])
    assert stored_spec["spec_version"] == 1
    assert stored_spec["versions"]["evidence_version"] == 1


def test_explicit_spec_v2_invocation_uses_exact_supplied_tuple(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "spec_v2.json"
    args = [
        "--name",
        "cli-spec-v2-explicit-test",
        "--spec-version",
        "2",
        "--output",
        str(output),
    ] + _FEE_FLAGS
    for flag, value in _SPEC_V2_FLAGS.items():
        args += [flag, value]
    cli.main(args)

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["spec"]["spec_version"] == 2
    versions = manifest["spec"]["versions"]
    assert versions["evidence_version"] == 6
    assert versions["sampling_version"] == 1
    assert versions["context_version"] == 1
    assert versions["outcome_version"] == 1
    assert versions["execution_snapshot_version"] == 1
    assert versions["research_visibility_version"] == 1

    row = asyncio.run(_manifest_row(dsn, "cli-spec-v2-explicit-test"))
    assert row is not None
    stored_spec = json.loads(row["spec"])
    assert stored_spec["spec_version"] == 2
    assert stored_spec["versions"]["research_visibility_version"] == 1


@pytest.mark.parametrize("omit_flag", sorted(_SPEC_V2_FLAGS))
def test_spec_v2_missing_scientific_version_flag_fails_closed(
    dsn: str, tmp_path: Path, omit_flag: str
) -> None:
    manifest_name = f"cli-spec-v2-missing-{omit_flag.strip('-').replace('-', '_')}"
    output = tmp_path / "should-not-be-written.json"
    args = ["--name", manifest_name, "--spec-version", "2", "--output", str(output)]
    for flag, value in _SPEC_V2_FLAGS.items():
        if flag == omit_flag:
            continue
        args += [flag, value]

    with pytest.raises(SystemExit):
        cli.main(args)

    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, manifest_name))
    assert row is None


def test_research_visibility_version_under_spec_v1_fails_closed(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "should-not-be-written-either.json"
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--name",
                "cli-v1-with-research-visibility-test",
                "--research-visibility-version",
                "1",
                "--output",
                str(output),
            ]
        )
    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, "cli-v1-with-research-visibility-test"))
    assert row is None


def test_default_spec_version_is_v1(dsn: str) -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["--name", "cli-default-spec-version-test"])
    assert args.spec_version == 1


# ---------------------------------------------------------------------------
# PR26: spec v3 confirmatory contract CLI.
# ---------------------------------------------------------------------------


def test_explicit_spec_v3_invocation_uses_exact_supplied_contract(
    dsn: str, tmp_path: Path
) -> None:
    output = tmp_path / "spec_v3.json"
    cli.main(_spec_v3_args(name="cli-spec-v3-explicit-test", output=output))

    manifest = json.loads(output.read_text(encoding="utf-8"))
    assert manifest["spec"]["spec_version"] == 3
    versions = manifest["spec"]["versions"]
    assert versions["research_visibility_version"] == 1

    contract = manifest["spec"]["confirmatory_contract"]
    assert contract["primary_symbol"] == "BTCUSDT_PERP.A"
    assert contract["primary_horizon_minutes"] == 15
    assert contract["primary_sampling_mode"] == "utc_nonoverlap"
    assert contract["primary_exchange"] == "binance"
    assert contract["primary_size_usd"] == 1000.0
    assert contract["primary_taker_fee_bps"] == 2.0
    assert contract["unmodeled_execution_stress_bps"] == 1.5
    assert contract["block_unit"] == "day"
    assert contract["bootstrap_seed"] == 42
    assert (
        contract["confirmatory_decision_policy"]
        == "two_sided_block_bootstrap_ci_vs_minimum_effect_v1"
    )

    row = asyncio.run(_manifest_row(dsn, "cli-spec-v3-explicit-test"))
    assert row is not None
    stored_spec = json.loads(row["spec"])
    assert stored_spec["spec_version"] == 3
    assert stored_spec["confirmatory_contract"]["primary_symbol"] == "BTCUSDT_PERP.A"


@pytest.mark.parametrize("omit_flag", sorted(_SPEC_V3_FLAGS))
def test_spec_v3_missing_required_flag_fails_closed(
    dsn: str, tmp_path: Path, omit_flag: str
) -> None:
    manifest_name = f"cli-spec-v3-missing-{omit_flag.strip('-').replace('-', '_')}"
    output = tmp_path / "should-not-be-written.json"
    args = _spec_v3_args(name=manifest_name, output=output, omit_flag=omit_flag)

    with pytest.raises(SystemExit):
        cli.main(args)

    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, manifest_name))
    assert row is None


def test_spec_v3_missing_acknowledge_flag_fails_closed(dsn: str, tmp_path: Path) -> None:
    manifest_name = "cli-spec-v3-missing-acknowledge"
    output = tmp_path / "should-not-be-written-ack.json"
    args = _spec_v3_args(name=manifest_name, output=output, acknowledge=False)

    with pytest.raises(SystemExit):
        cli.main(args)

    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, manifest_name))
    assert row is None


def test_confirmatory_flag_forbidden_under_spec_v1(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "should-not-be-written-v1-confirmatory.json"
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--name",
                "cli-v1-with-primary-symbol-test",
                "--primary-symbol",
                "BTCUSDT_PERP.A",
                "--output",
                str(output),
            ]
        )
    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, "cli-v1-with-primary-symbol-test"))
    assert row is None


def test_confirmatory_flag_forbidden_under_spec_v2(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "should-not-be-written-v2-confirmatory.json"
    args = [
        "--name",
        "cli-v2-with-primary-symbol-test",
        "--spec-version",
        "2",
        "--output",
        str(output),
    ]
    for flag, value in _SPEC_V2_FLAGS.items():
        args += [flag, value]
    args += ["--primary-symbol", "BTCUSDT_PERP.A"]

    with pytest.raises(SystemExit):
        cli.main(args)
    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, "cli-v2-with-primary-symbol-test"))
    assert row is None


def test_acknowledge_flag_forbidden_under_spec_v1(dsn: str, tmp_path: Path) -> None:
    output = tmp_path / "should-not-be-written-ack-v1.json"
    with pytest.raises(SystemExit):
        cli.main(
            [
                "--name",
                "cli-v1-with-acknowledge-test",
                "--acknowledge-confirmatory-primary-hypothesis",
                "--output",
                str(output),
            ]
        )
    assert not output.exists()
    row = asyncio.run(_manifest_row(dsn, "cli-v1-with-acknowledge-test"))
    assert row is None


def test_no_production_manifest_name_is_used_by_confirmatory_cli_tests() -> None:
    # None of the manifest names this test module freezes are the fixed
    # production program names -- this PR never creates a production
    # manifest.
    from app.signal_walk_forward import DEFAULT_MANIFEST_NAME

    assert DEFAULT_MANIFEST_NAME == "pr11-fixed-kernel-v1"
    for name in (
        "cli-spec-v3-explicit-test",
        "cli-spec-v3-missing-acknowledge",
        "cli-v1-with-primary-symbol-test",
        "cli-v2-with-primary-symbol-test",
        "cli-v1-with-acknowledge-test",
    ):
        assert name != DEFAULT_MANIFEST_NAME
        assert not name.startswith("pr11-fixed-kernel")
