"""Pytest wrapper over the permanent mutation matrix.

The matrix is run once per session against ``HEAD`` and every assertion reads
that single result.  ``HEAD`` rather than a pinned revision on purpose: the
regeneration of the frozen evidence over ``c60e2ee6`` needs the full history and
lives in ``.github/workflows/identity-mutation.yml``, which checks out with
``fetch-depth: 0``.  This wrapper must keep working on the shallow checkout the
main CI uses.

Nothing here is allowed to soften a result.  There is no ``xfail`` and no
conditional ``skip``: the only skip the design admits is declared in the catalog
and asserted to be exactly the one the declaration records.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.identity_mutation import catalog as cat
from tests.identity_mutation import harness, runner


@pytest.fixture(scope="module")
def evidence() -> dict[str, Any]:
    return harness.run_matrix(revision="HEAD")


@pytest.fixture(scope="module")
def declared() -> dict[str, Any]:
    return runner.load_known_escapes()


def test_catalog_holds_every_mutation_exactly_once():
    ids = [mutation.id for mutation in cat.CATALOG]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))
    assert ids == [f"M-{index:02d}" for index in range(1, 24)]


def test_catalog_never_declares_an_unknown_effect():
    known = {
        cat.MUST_MOVE,
        cat.MUST_NOT_MOVE,
        cat.MUST_REJECT,
        cat.MUST_NOT_MOVE_CODE_MUST_MOVE_ENV,
    }
    for mutation in cat.CATALOG:
        assert mutation.expected_effect in known, mutation.id


def test_only_the_declared_skip_condition_exists():
    """A skip is a hole in the audit, so the catalog may declare exactly one."""

    skippable = [mutation.id for mutation in cat.CATALOG if mutation.skip_if]
    assert skippable == ["M-16"]


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
        "exception",
        "failure_reason",
        "observed_class",
    }
    for row in evidence["mutations"]:
        assert required <= set(row), row["id"]
        assert row["observed_class"] in {cat.GUARD, cat.ESCAPE, cat.SKIPPED}


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


@pytest.mark.parametrize("mutation_id", cat.MANDATED_ESCAPES)
def test_mandated_escapes_are_observed_as_escapes(evidence, mutation_id):
    """M-01, M-02 and M-03 were demonstrated by the independent audit.

    Observing any of them as ``GUARD`` does not mean the defect was closed; it
    means this harness is measuring the wrong thing.
    """

    row = next(row for row in evidence["mutations"] if row["id"] == mutation_id)
    assert row["observed_class"] == cat.ESCAPE, (
        f"{mutation_id} is mandated ESCAPE but was observed "
        f"{row['observed_class']}; the harness is not measuring what it claims"
    )


def test_no_mutation_was_classified_by_an_ineffective_patch(evidence):
    """A runtime patch that quietly did nothing must not become a finding."""

    for row in evidence["mutations"]:
        assert row["failure_reason"] != harness.REASON_PATCH_INEFFECTIVE, row["id"]


def test_observed_escapes_match_the_declaration_in_both_directions(evidence, declared):
    observed, _ = runner.observed_sets(evidence)
    assert observed == set(declared["escapes"]), (
        "known_escapes.json is out of date: "
        f"undeclared={sorted(observed - set(declared['escapes']))} "
        f"declared_but_absent={sorted(set(declared['escapes']) - observed)}"
    )


def test_observed_skips_match_the_declaration(evidence, declared):
    _, skipped = runner.observed_sets(evidence)
    assert skipped == set(declared["skipped"])


def test_frozen_evidence_is_wellformed_and_agrees_with_the_declaration():
    """Read-only cross-check of the committed artefacts, no subprocess needed."""

    body = json.loads(
        (runner.EVIDENCE_DIR / "c60e2ee6.json").read_text(encoding="utf-8")
    )
    assert body["baseline_rev"].startswith("c60e2ee6")
    frozen_escapes, frozen_skipped = runner.observed_sets(body)
    declaration = runner.load_known_escapes()
    assert frozen_escapes == set(declaration["escapes"])
    assert frozen_skipped == set(declaration["skipped"])
    assert declaration["baseline_rev"] == "c60e2ee6"


def test_frozen_evidence_carries_no_machine_specific_data():
    """Determinism is a property of the file, so assert it on the bytes."""

    text = (runner.EVIDENCE_DIR / "c60e2ee6.json").read_text(encoding="utf-8")
    for forbidden in ("/tmp/", "identity-mutation-", "/srv/", "duration", "pid"):
        assert forbidden not in text, forbidden
