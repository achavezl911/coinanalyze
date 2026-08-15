"""CLI entrypoint for the identity mutation matrix.

    python -m tests.identity_mutation.runner --target <rev|HEAD> \\
        [--json <path>] [--only M-XX,...]

Exit code is ``0`` only when every non-skipped mutation either meets the effect
the catalog demands, or is already declared in ``known_escapes.json``.  The
declaration is checked in both directions: an undeclared escape is a regression
or an unrecorded finding, and a declared escape that no longer reproduces is a
closure nobody wrote down.

The emitted evidence is deterministic by construction.  It carries ids, the
required effect, digests, validation flags, the failure reason and the observed
class -- no temporary paths, no timestamps, no durations, no pids -- so two runs
over the same revision produce byte-identical files.
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

    observed_escapes, _ = observed_sets(evidence)
    declared_escapes = set(declared.get("escapes", [])) & selected
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
        f"{'ID':<6} {'EXPECTED EFFECT':<34} {'OBSERVED':<8} REASON",
        f"{'-' * 6} {'-' * 34} {'-' * 8} {'-' * 30}",
    ]
    for row in evidence["mutations"]:
        lines.append(
            f"{row['id']:<6} {row['expected_effect']:<34} "
            f"{row['observed_class']:<8} {row['failure_reason']}"
        )
    return "\n".join(lines)


def emit_known_escapes(evidence: dict[str, Any], revision_label: str) -> str:
    escapes, skipped = observed_sets(evidence)
    body = {
        "baseline_rev": revision_label,
        "escapes": sorted(escapes),
        "skipped": sorted(skipped),
    }
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tests.identity_mutation.runner")
    parser.add_argument("--target", required=True, help="revision to audit (rev or HEAD)")
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
    evidence = harness.run_matrix(revision=args.target, only=only)
    selected = {row["id"] for row in evidence["mutations"]}
    serialized = serialize_evidence(evidence)

    print(render_table(evidence))
    escapes, skipped = observed_sets(evidence)
    print(f"\nescapes observed : {len(escapes)} -> {', '.join(sorted(escapes)) or '-'}")
    print(f"skipped          : {len(skipped)} -> {', '.join(sorted(skipped)) or '-'}")
    print(f"guards           : {len(selected) - len(escapes) - len(skipped)}")

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

    if problems:
        print("\nFAILURES", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nOK: observed escapes match known_escapes.json in both directions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
