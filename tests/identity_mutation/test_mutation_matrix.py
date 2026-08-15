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


# The escapes commit 3.1 leaves open, written out here on purpose.  Reading them
# from known_escapes.json would be circular: that file is generated from the
# same run it is compared against, which was harmless while nothing closed and
# stops being harmless the moment something does.  Three of C.2, two of C.1 and
# three of D -- the in-memory escapes and the anchor, which commits 3.2 and 3.3
# close.
EXPECTED_OPEN_ESCAPES = frozenset(
    {"M-01", "M-02", "M-05", "M-06", "M-27", "M-28", "M-29", "M-31"}
)

# Reasons that mean "this runner could not measure the row", as opposed to
# "this row is an escape".  A row that failed closed for one of these has not
# been audited, and comparing it against a declaration would be comparing
# nothing.
UNMEASURED_REASONS = frozenset(
    {
        harness.REASON_ANCHOR_NOT_SUPPLIED,
        harness.REASON_ALT_INTERPRETER_UNAVAILABLE,
    }
)


def _measured_ids(evidence: dict[str, Any]) -> set[str]:
    return {
        row["id"]
        for row in evidence["mutations"]
        if row["failure_reason"] not in UNMEASURED_REASONS
    }


def test_catalog_holds_every_mutation_exactly_once():
    ids = [mutation.id for mutation in cat.CATALOG]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert ids == [f"M-{index:02d}" for index in range(1, 34)]


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
        "production_launch_protocol",
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
    """Compared among the rows this runner could actually measure.

    An unprovisioned runner fails the anchor and interpreter rows closed, which
    is honest but is not a measurement, so those rows are excluded here and
    reported by the provisioning tests instead.  The runner CLI -- the audit
    gate -- refuses such a run outright; this wrapper is the regression net and
    has to stay usable on a laptop.
    """

    observed, _ = runner.observed_sets(evidence)
    measured = _measured_ids(evidence)
    expected = set(declared["escapes"]) & measured
    assert observed & measured == expected, (
        "known_escapes.json is out of date: "
        f"undeclared={sorted((observed & measured) - expected)} "
        f"declared_but_absent={sorted(expected - observed)}"
    )


def test_the_declared_escape_set_is_exactly_the_expected_one_for_this_commit(evidence):
    """The anti-circularity check, with the set written by hand.

    If this disagrees with the measurement, the measurement wins and the
    disagreement is the finding.  Rewriting the constant to match a run would
    turn the one test that cannot be generated from the run into one that can.
    """

    observed, _ = runner.observed_sets(evidence)
    measured = _measured_ids(evidence)
    assert observed & measured == EXPECTED_OPEN_ESCAPES & measured, (
        f"unexpected_open={sorted((observed & measured) - EXPECTED_OPEN_ESCAPES)} "
        f"unexpectedly_closed={sorted((EXPECTED_OPEN_ESCAPES & measured) - observed)}"
    )


def test_the_rows_that_closed_in_this_commit_are_guards(evidence):
    """Every row outside the expected eight must be a guard, not merely absent."""

    measured = _measured_ids(evidence)
    for row in evidence["mutations"]:
        if row["id"] in EXPECTED_OPEN_ESCAPES or row["id"] not in measured:
            continue
        assert row["observed_class"] == cat.GUARD, (
            f"{row['id']}: {row['failure_reason']} -- this commit closes it"
        )


def test_the_negative_controls_recovered_their_meaning(evidence):
    """The seven MUST_NOT_MOVE_AND_ACCEPT rows must be guards again.

    While the combined entry point did not exist, "the validator accepts" was
    unprovable and every one of them failed closed.  That is what made the
    matrix unable to detect a validator that rejects on noise, and it is what
    this commit is required to give back.
    """

    controls = [
        mutation.id
        for mutation in cat.CATALOG
        if mutation.expected_effect == cat.MUST_NOT_MOVE_AND_ACCEPT
    ]
    # Seven since commit 2, eight since M-33 joined them: the row that audits
    # the auditor is a negative control like the others.
    assert len(controls) == 8
    for mutation_id in controls:
        row = _row(evidence, mutation_id)
        assert row["observed_class"] == cat.GUARD, mutation_id
        assert row["combined_validation_accepted"] is True, mutation_id
        assert row["combined_validator_absent"] is False, mutation_id


def test_deleting_a_material_module_is_still_refused(evidence):
    """H-4 must not regress: the structural control the matrix found."""

    row = _row(evidence, "M-26")
    assert row["observed_class"] == cat.GUARD
    assert row["rejection_kind"] is not None


def test_the_harness_launch_protocol_does_not_change_what_is_measured(evidence):
    """M-33.  If this fails, every other row describes a system nobody ships."""

    row = _row(evidence, "M-33")
    assert row["production_launch_protocol"] is True, (
        "M-33 did not actually run under the production launch protocol"
    )
    assert row["observed_class"] == cat.GUARD, (
        "the identity or the verdict differs between the harness launch protocol "
        "and the one the systemd units use; the instrument is auditing a system "
        "that is not the one that ships"
    )
    baseline = evidence["baseline"]
    assert row["code_digest"] == baseline["code_digest"]
    assert row["environment_digest"] == baseline["environment_digest"]
    assert row["combined_validation_accepted"] is True


def test_every_observed_escape_names_what_closes_it(evidence, declared):
    assert runner.closes_with_violations(evidence, declared) == []


def test_the_declaration_records_no_skip(declared):
    assert declared["skipped"] == []


def test_frozen_evidence_is_wellformed_and_contains_the_declaration():
    """Read-only cross-check of the committed artefacts, no subprocess needed.

    The two files stopped describing the same revision the moment escapes began
    to close: the frozen evidence is the measurement over ``c60e2ee6``, and the
    declaration is what is still open on the branch.  The relation between them
    is containment, and it is the direction that matters -- an escape open on
    the branch that was never open at the baseline would be a defect this
    series introduced.
    """

    body = json.loads(
        (runner.EVIDENCE_DIR / "c60e2ee6.json").read_text(encoding="utf-8")
    )
    assert body["baseline_rev"].startswith("c60e2ee6")
    assert [row["id"] for row in body["mutations"]] == [m.id for m in cat.CATALOG]
    frozen_escapes, frozen_skipped = runner.observed_sets(body)
    declaration = runner.load_known_escapes()
    assert set(declaration["escapes"]) <= frozen_escapes, sorted(
        set(declaration["escapes"]) - frozen_escapes
    )
    assert frozen_skipped == set()
    assert declaration["skipped"] == []
    assert declaration["baseline_rev"] == runner.AUDIT_BASELINE_REV
    assert set(declaration["escapes"]) == EXPECTED_OPEN_ESCAPES


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
