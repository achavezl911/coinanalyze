"""CLI entrypoint for the identity mutation matrix.

    python -m tests.identity_mutation.runner --target <rev|HEAD> \\
        [--identity-anchor <fingerprint>] [--json <path>] [--only M-XX,...]

Exit code is ``0`` only when every mutation either meets the effect the catalog
demands, or is already declared in ``known_escapes.json``.  The declaration is
checked in both directions: an undeclared escape is a regression or an
unrecorded finding, and a declared escape that no longer reproduces is a
closure nobody wrote down.

Every declared escape also carries ``closes_with``: the item of the addendum
that is expected to close it.  An escape that fits none of them is reported as
such rather than filed under the nearest label, because that would mean the
addendum is incomplete and the plan is missing a step.

The anchor is read from ``--identity-anchor`` or from
``IDENTITY_ANCHOR_FINGERPRINT`` in the environment of *this* process, never from
a file of the tree under audit.  A fingerprint the mutator can rewrite anchors
nothing, so the mutations that interrogate it fail closed when it is absent --
and so does the run: a runner without an anchor, or without the second
interpreter M-16 needs, exits non-zero before measuring anything rather than
reporting green over rows nobody could measure.

The emitted evidence is deterministic by construction.  It carries ids, the
required effect, digests, validation flags, the failure reason and the observed
class -- no temporary paths, no timestamps, no durations, no pids, no
interpreter or anchor values -- so two runs over the same revision produce
byte-identical files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tests.identity_mutation import catalog as cat
from tests.identity_mutation import harness

KNOWN_ESCAPES_PATH = Path(__file__).resolve().parent / "known_escapes.json"
EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"


def load_known_escapes(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or KNOWN_ESCAPES_PATH).read_text(encoding="utf-8"))


def serialize_evidence(evidence: dict[str, Any]) -> str:
    return json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def observed_sets(evidence: dict[str, Any]) -> tuple[set[str], set[str]]:
    escapes = {
        row["id"] for row in evidence["mutations"] if row["observed_class"] == cat.ESCAPE
    }
    skipped = {
        row["id"] for row in evidence["mutations"] if row["observed_class"] == cat.SKIPPED
    }
    return escapes, skipped


def compare_with_declaration(
    evidence: dict[str, Any], declared: dict[str, Any], selected: set[str]
) -> list[str]:
    """Both directions.  Returns the list of problems; empty means green."""

    observed_escapes, observed_skipped = observed_sets(evidence)
    declared_escapes = set(declared.get("escapes", {})) & selected
    problems: list[str] = []
    for mutation_id in sorted(observed_escapes - declared_escapes):
        problems.append(
            f"{mutation_id}: escape observed but not declared in known_escapes.json"
        )
    for mutation_id in sorted(declared_escapes - observed_escapes):
        problems.append(
            f"{mutation_id}: escape declared but not observed -- it was closed without "
            "updating the declaration"
        )
    for mutation_id in sorted(observed_skipped):
        problems.append(
            f"{mutation_id}: observed as SKIPPED -- the catalog admits no skip, so a "
            "skipped row is a hole in the audit"
        )
    if declared.get("skipped"):
        problems.append(
            "known_escapes.json declares skipped mutations; the catalog admits none"
        )
    return problems


def closes_with_violations(evidence: dict[str, Any], declared: dict[str, Any]) -> list[str]:
    """Every escape must name what closes it, in the catalog and in the file."""

    observed_escapes, _ = observed_sets(evidence)
    declared_escapes = declared.get("escapes", {})
    problems: list[str] = []
    for mutation_id in sorted(observed_escapes):
        mutation = cat.CATALOG_BY_ID.get(mutation_id)
        if mutation is None or not mutation.closes_with:
            problems.append(
                f"{mutation_id}: escape observed with no closes_with in the catalog -- "
                "it fits no item of the addendum, which means the addendum is incomplete"
            )
            continue
        if mutation.closes_with not in cat.CLOSES_WITH_VALUES:
            problems.append(
                f"{mutation_id}: closes_with {mutation.closes_with!r} is not an "
                f"admitted value {sorted(cat.CLOSES_WITH_VALUES)}"
            )
        entry = declared_escapes.get(mutation_id)
        if not isinstance(entry, dict):
            continue
        if entry.get("closes_with") != mutation.closes_with:
            problems.append(
                f"{mutation_id}: known_escapes.json says closes_with "
                f"{entry.get('closes_with')!r}, the catalog says {mutation.closes_with!r}"
            )
    return problems


def provisioning_problems(anchor: str, selected: set[str]) -> list[str]:
    """Refuse to certify a run that could not measure part of the catalog.

    Both conditions fail the *row* closed already, and a row that fails closed
    into an escape which is also a declared escape would otherwise let the
    pipeline exit green over something nobody measured.  That is the shape of
    the empty green this instrument exists to refuse, so the run itself is red:
    the audit gate is not the place to discover the runner was half provisioned.
    """

    problems: list[str] = []
    if not anchor and set(cat.ANCHOR_DEPENDENT_IDS) & selected:
        problems.append(
            "no external anchor was supplied, so "
            f"{', '.join(sorted(set(cat.ANCHOR_DEPENDENT_IDS) & selected))} could not be "
            "measured; pass --identity-anchor or set IDENTITY_ANCHOR_FINGERPRINT"
        )
    interpreter_rows = {
        mutation.id
        for mutation in cat.CATALOG
        if any(isinstance(step, cat.AlternateInterpreter) for step in mutation.steps)
    } & selected
    if interpreter_rows and harness.find_alternate_interpreter() is None:
        problems.append(
            f"no second interpreter is installed, so {', '.join(sorted(interpreter_rows))} "
            "could not be measured; provision one and name it in "
            f"{harness.INTERPRETERS_ENV}"
        )
    return problems


def mandated_class_violations(evidence: dict[str, Any]) -> list[str]:
    by_id = {row["id"]: row for row in evidence["mutations"]}
    violations: list[str] = []
    for mutation in cat.CATALOG:
        if mutation.mandated_class is None:
            continue
        row = by_id.get(mutation.id)
        if row is None:
            continue
        if row["observed_class"] != mutation.mandated_class:
            violations.append(
                f"{mutation.id}: mandated {mutation.mandated_class}, observed "
                f"{row['observed_class']} -- the harness is measuring the wrong thing"
            )
    return violations


def render_table(evidence: dict[str, Any]) -> str:
    lines = [
        f"{'ID':<6} {'EXPECTED EFFECT':<34} {'OBSERVED':<8} {'REJECTION':<12} REASON",
        f"{'-' * 6} {'-' * 34} {'-' * 8} {'-' * 12} {'-' * 30}",
    ]
    for row in evidence["mutations"]:
        lines.append(
            f"{row['id']:<6} {row['expected_effect']:<34} "
            f"{row['observed_class']:<8} {str(row['rejection_kind'] or '-'):<12} "
            f"{row['failure_reason']}"
        )
    return "\n".join(lines)


def emit_known_escapes(evidence: dict[str, Any], revision_label: str) -> str:
    escapes, skipped = observed_sets(evidence)
    body = {
        "baseline_rev": revision_label,
        "escapes": {
            mutation_id: {
                "closes_with": cat.CATALOG_BY_ID[mutation_id].closes_with,
                "note": cat.CATALOG_BY_ID[mutation_id].closes_note,
            }
            for mutation_id in sorted(escapes)
        },
        "skipped": sorted(skipped),
    }
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tests.identity_mutation.runner")
    parser.add_argument("--target", required=True, help="revision to audit (rev or HEAD)")
    parser.add_argument(
        "--identity-anchor",
        dest="identity_anchor",
        help=(
            "the external anchor fingerprint; defaults to IDENTITY_ANCHOR_FINGERPRINT "
            "in this process's environment and is never read from the target tree"
        ),
    )
    parser.add_argument("--json", dest="json_path", help="write the evidence here")
    parser.add_argument("--only", help="comma-separated mutation ids")
    parser.add_argument(
        "--emit-known-escapes",
        dest="emit_known_escapes",
        help=(
            "write the observed classification here instead of comparing against "
            "the declaration; used once to freeze a new baseline"
        ),
    )
    parser.add_argument(
        "--compare-evidence",
        dest="compare_evidence",
        help="require the emitted evidence to match this file byte for byte",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    only = tuple(
        part.strip() for part in (args.only or "").split(",") if part.strip()
    )
    anchor = harness.resolve_anchor(args.identity_anchor)

    # Before anything is measured, and before any artefact can be frozen from a
    # half provisioned run: a catalog that cannot be measured whole is not an
    # audit, and finding that out afterwards is finding it out too late.
    unprovisioned = provisioning_problems(
        anchor, {m.id for m in cat.CATALOG if not only or m.id in only}
    )
    if unprovisioned:
        print("FAILURES", file=sys.stderr)
        for problem in unprovisioned:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    evidence = harness.run_matrix(revision=args.target, only=only, anchor=anchor)
    selected = {row["id"] for row in evidence["mutations"]}
    serialized = serialize_evidence(evidence)

    print(render_table(evidence))
    escapes, skipped = observed_sets(evidence)
    print(f"\nescapes observed : {len(escapes)} -> {', '.join(sorted(escapes)) or '-'}")
    print(f"skipped          : {len(skipped)} -> {', '.join(sorted(skipped)) or '-'}")
    print(f"guards           : {len(selected) - len(escapes) - len(skipped)}")
    print(f"anchor supplied  : {'yes' if anchor else 'no'}")

    if args.json_path:
        target = Path(args.json_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
        print(f"evidence written : {target}")

    if args.emit_known_escapes:
        target = Path(args.emit_known_escapes)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(emit_known_escapes(evidence, args.target), encoding="utf-8")
        print(f"declaration written: {target}")
        return 0

    problems = mandated_class_violations(evidence)

    if args.compare_evidence:
        expected = Path(args.compare_evidence)
        if not expected.is_file():
            problems.append(f"evidence file {expected} does not exist")
        elif expected.read_text(encoding="utf-8") != serialized:
            problems.append(
                f"regenerated evidence differs from {expected} -- the matrix is not "
                "reproducible or the tree changed"
            )

    declared = load_known_escapes()
    problems.extend(compare_with_declaration(evidence, declared, selected))
    problems.extend(closes_with_violations(evidence, declared))

    if problems:
        print("\nFAILURES", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nOK: observed escapes match known_escapes.json in both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
