"""Pytest wrapper over the permanent mutation matrix.

The matrix is run once per session against ``HEAD`` and every assertion reads
that single result.  ``HEAD`` rather than a pinned revision on purpose: the
regeneration of the frozen evidence over ``c60e2ee6`` needs the full history and
lives in ``.github/workflows/identity-mutation.yml``, which checks out with
``fetch-depth: 0``.  This wrapper must keep working on the shallow checkout the
main CI uses.

Nothing here is allowed to soften a result.  There is no ``xfail`` and no
``skip``: the catalog declares no skip condition, the harness can emit none, and
the two conditions that depend on how the runner was provisioned -- a second
interpreter and the external anchor -- are asserted in *both* branches instead
of excusing one of them.
"""

from __future__ import annotations

import dataclasses
import json
import types
from typing import Any

import pytest

from tests.identity_mutation import catalog as cat
from tests.identity_mutation import harness, probe, runner


@pytest.fixture(scope="module")
def evidence() -> dict[str, Any]:
    return harness.run_matrix(revision="HEAD")


@pytest.fixture(scope="module")
def declared() -> dict[str, Any]:
    return runner.load_known_escapes()


def _row(evidence: dict[str, Any], mutation_id: str) -> dict[str, Any]:
    return next(row for row in evidence["mutations"] if row["id"] == mutation_id)


def test_catalog_holds_every_mutation_exactly_once():
    ids = [mutation.id for mutation in cat.CATALOG]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert ids == [f"M-{index:02d}" for index in range(1, 32)]


def test_catalog_never_declares_an_unknown_effect():
    for mutation in cat.CATALOG:
        assert mutation.expected_effect in cat.REQUIRED_EFFECTS, mutation.id


def test_the_catalog_cannot_declare_a_skip_at_all():
    """A skip is a hole in the audit, so the field that allowed one is gone."""

    field_names = {field.name for field in dataclasses.fields(cat.Mutation)}
    assert "skip_if" not in field_names


def test_every_declared_closes_with_is_an_admitted_addendum_item():
    for mutation in cat.CATALOG:
        if mutation.closes_with:
            assert mutation.closes_with in cat.CLOSES_WITH_VALUES, mutation.id
            assert mutation.closes_note, mutation.id


def test_no_catalog_step_may_rewrite_the_harness_environment():
    """The tree is what mutations rewrite; the instrument is not."""

    for mutation in cat.CATALOG:
        for step in mutation.steps:
            if isinstance(step, cat.EnvChange):
                names = {name for name, _ in step.values}
                assert not (names & harness.RESERVED_ENV), mutation.id


def test_the_probe_is_launched_with_an_explicit_resolution_order(tmp_path):
    """The invariant M-27 and M-31 exist to interrogate.

    Under an implicit ``sys.path[0]`` a PYTHONPATH shadow cannot win and a
    ``sitecustomize`` in the tree is never imported, so both mutations would be
    applied and measured without having had any effect.
    """

    env = harness._base_environment(tmp_path, tmp_path / "outside", [])
    assert env["PYTHONSAFEPATH"] == "1"
    assert env["PYTHONPATH"] == str(tmp_path)

    shadowed = harness._base_environment(tmp_path, tmp_path / "outside", ["/shadow"])
    assert shadowed["PYTHONPATH"].split(":")[0] == "/shadow"


def test_an_undeclared_interpreter_does_not_exist_for_the_matrix(monkeypatch):
    """No PATH fallback, on any machine.

    An interpreter that merely happens to be installed may be a shim carrying
    none of the project's dependencies; measuring M-16 against it turns the row
    red for a reason unrelated to the code under audit.  Only what the runner
    declared counts, and nothing declared means the row fails closed.
    """

    monkeypatch.delenv(harness.INTERPRETERS_ENV, raising=False)
    assert harness.find_alternate_interpreter() is None

    monkeypatch.setenv(harness.INTERPRETERS_ENV, "/nonexistent/python")
    assert harness.find_alternate_interpreter() is None


def test_a_declared_anchor_channel_nobody_sets_fails_closed():
    """The one mistake the instrument may never make is a false green.

    A tree that reads its anchor from a variable this harness does not set gets
    no anchor at all.  A validator that fails closed would then refuse for want
    of one and be indistinguishable from a validator that detected the
    mutation, so the escape would be reported as closed.
    """

    absent, note = probe.anchor_state(types.SimpleNamespace())
    assert (absent, note) == (True, "")

    absent, note = probe.anchor_state(
        types.SimpleNamespace(IDENTITY_ANCHOR_ENV_VAR=harness.ANCHOR_ENV)
    )
    assert absent is False and note == ""

    absent, note = probe.anchor_state(
        types.SimpleNamespace(IDENTITY_ANCHOR_ENV_VAR="A_VARIABLE_NOBODY_SETS")
    )
    assert absent is True
    assert "mismatch" in note


def test_the_anchor_is_never_read_from_the_target_tree(monkeypatch):
    monkeypatch.setenv(harness.ANCHOR_ENV, "  from-the-auditor  ")
    assert harness.resolve_anchor() == "from-the-auditor"
    assert harness.resolve_anchor("explicit") == "explicit"
    monkeypatch.delenv(harness.ANCHOR_ENV)
    assert harness.resolve_anchor() == ""


def test_every_mutation_is_measured(evidence):
    measured = [row["id"] for row in evidence["mutations"]]
    assert measured == [mutation.id for mutation in cat.CATALOG]


def test_every_row_carries_the_full_probe_schema(evidence):
    required = {
        "id",
        "expected_effect",
        "code_digest",
        "environment_digest",
        "total_digest",
        "validation_accepted",
        "validation_error",
        "forged_object_accepted",
        "combined_validation_accepted",
        "combined_validator_absent",
        "rejection_kind",
        "anchor_mechanism_absent",
        "sitecustomize_active",
        "pythonpath_shadow_active",
        "exception",
        "failure_reason",
        "observed_class",
    }
    for row in evidence["mutations"]:
        assert required <= set(row), row["id"]
        assert row["observed_class"] in {cat.GUARD, cat.ESCAPE}, row["id"]
        assert row["failure_reason"] in harness.FAILURE_REASONS, row["id"]
        assert row["rejection_kind"] in {None, "false", "exception", "import_error"}, row["id"]


def test_no_mutation_is_ever_skipped(evidence):
    for row in evidence["mutations"]:
        assert row["observed_class"] != cat.SKIPPED, row["id"]


def test_the_baseline_validates_against_its_own_frozen_identity(evidence):
    """The control that proves a green row means something.

    If an untouched tree could not validate its own frozen identity, every
    rejection below would be an artefact of the harness rather than a property
    of the code under audit.
    """

    baseline = evidence["baseline"]
    assert baseline["code_digest"] is not None
    assert baseline["environment_digest"] is not None
    assert baseline["total_digest"] is not None
    assert baseline["validation_accepted"] is True
    assert baseline["validation_error"] is None
    assert baseline["exception"] is None


def test_the_untouched_baseline_is_accepted_by_the_combined_validator(evidence):
    """An implication, so it needs no edit when the entry point arrives.

    While the combined validator does not exist the premise is false and there
    is nothing to accept.  The moment it exists, an untouched tree that it
    refuses would make every rejection below meaningless.
    """

    baseline = evidence["baseline"]
    assert baseline["combined_validator_absent"] or baseline["combined_validation_accepted"]


@pytest.mark.parametrize("mutation_id", cat.MANDATED_ESCAPES)
def test_mandated_escapes_are_observed_as_escapes(evidence, mutation_id):
    """M-01, M-02 and M-03 were demonstrated by the independent audit.

    Observing any of them as ``GUARD`` does not mean the defect was closed; it
    means this harness is measuring the wrong thing.
    """

    row = _row(evidence, mutation_id)
    assert row["observed_class"] == cat.ESCAPE, (
        f"{mutation_id} is mandated ESCAPE but was observed "
        f"{row['observed_class']}; the harness is not measuring what it claims"
    )


def test_no_mutation_was_classified_by_an_ineffective_mutation(evidence):
    """A mutation that quietly did nothing must not become a finding."""

    inert = {
        harness.REASON_PATCH_INEFFECTIVE,
        harness.REASON_MUTATION_INEFFECTIVE,
        harness.REASON_ALT_INTERPRETER_UNUSABLE,
    }
    for row in evidence["mutations"]:
        assert row["failure_reason"] not in inert, row["id"]


def test_no_mutation_failed_to_resolve_its_anchor(evidence):
    """Every mutation must bite the tree it was written against.

    A mutation whose anchor does not exist has measured nothing at all, which is
    what M-07 did at the previous revision of this catalog.
    """

    for row in evidence["mutations"]:
        assert row["failure_reason"] != harness.REASON_ANCHOR_NOT_FOUND, (
            f"{row['id']}: {row['exception']}"
        )


def test_no_probe_failed_to_report(evidence):
    unusable = {
        harness.REASON_NO_SENTINEL,
        harness.REASON_BAD_JSON,
        harness.REASON_TIMEOUT,
    }
    for row in evidence["mutations"]:
        assert row["failure_reason"] not in unusable, row["id"]


def test_the_interpreter_row_is_measured_whenever_a_second_one_is_provisioned(evidence):
    """Both branches assert.  Neither is an excuse for not measuring.

    On a runner with a single interpreter M-16 fails closed and says so; on a
    provisioned runner it must produce a real comparison instead.
    """

    row = _row(evidence, "M-16")
    if harness.find_alternate_interpreter() is None:
        assert row["failure_reason"] == harness.REASON_ALT_INTERPRETER_UNAVAILABLE
        assert row["observed_class"] == cat.ESCAPE
    else:
        assert row["failure_reason"] != harness.REASON_ALT_INTERPRETER_UNAVAILABLE
        assert row["code_digest"] is not None
        assert row["environment_digest"] is not None


def test_the_anchor_rows_are_measured_whenever_an_anchor_is_supplied(evidence):
    """Same shape: an anchor that was not supplied is stated, never assumed."""

    supplied = bool(harness.resolve_anchor())
    for mutation_id in cat.ANCHOR_DEPENDENT_IDS:
        row = _row(evidence, mutation_id)
        if supplied:
            assert row["failure_reason"] != harness.REASON_ANCHOR_NOT_SUPPLIED
        else:
            assert row["failure_reason"] == harness.REASON_ANCHOR_NOT_SUPPLIED
            assert row["observed_class"] == cat.ESCAPE


def test_observed_escapes_match_the_declaration_in_both_directions(evidence, declared):
    observed, _ = runner.observed_sets(evidence)
    assert observed == set(declared["escapes"]), (
        "known_escapes.json is out of date: "
        f"undeclared={sorted(observed - set(declared['escapes']))} "
        f"declared_but_absent={sorted(set(declared['escapes']) - observed)}"
    )


def test_every_observed_escape_names_what_closes_it(evidence, declared):
    assert runner.closes_with_violations(evidence, declared) == []


def test_the_declaration_records_no_skip(declared):
    assert declared["skipped"] == []


def test_frozen_evidence_is_wellformed_and_agrees_with_the_declaration():
    """Read-only cross-check of the committed artefacts, no subprocess needed."""

    body = json.loads(
        (runner.EVIDENCE_DIR / "c60e2ee6.json").read_text(encoding="utf-8")
    )
    assert body["baseline_rev"].startswith("c60e2ee6")
    assert [row["id"] for row in body["mutations"]] == [m.id for m in cat.CATALOG]
    frozen_escapes, frozen_skipped = runner.observed_sets(body)
    declaration = runner.load_known_escapes()
    assert frozen_escapes == set(declaration["escapes"])
    assert frozen_skipped == set()
    assert declaration["skipped"] == []
    assert declaration["baseline_rev"] == "c60e2ee6"


def test_frozen_declaration_ties_every_escape_to_what_closes_it():
    declaration = runner.load_known_escapes()
    for mutation_id, entry in declaration["escapes"].items():
        assert entry["closes_with"] in cat.CLOSES_WITH_VALUES, mutation_id
        assert entry["note"], mutation_id
        assert entry["closes_with"] == cat.CATALOG_BY_ID[mutation_id].closes_with


def test_frozen_evidence_carries_no_machine_specific_data():
    """Determinism is a property of the file, so assert it on the bytes."""

    text = (runner.EVIDENCE_DIR / "c60e2ee6.json").read_text(encoding="utf-8")
    forbidden = (
        "/tmp/",
        "identity-mutation-",
        "/srv/",
        "duration",
        "pid",
        "site-packages",
        "python3.1",
    )
    for needle in forbidden:
        assert needle not in text, needle
