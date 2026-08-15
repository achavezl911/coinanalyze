"""Tree materialization, mutation application and isolated measurement.

Contract
--------

* The target tree is materialized once per run with ``git worktree add
  --detach``.  Every mutation then works on its own ``shutil.copytree`` of that
  base.  The base worktree is never mutated and the user's working tree is
  never touched.
* Every measurement runs in its own subprocess.  Environment mutations and
  runtime patches contaminate an interpreter in ways that cannot be reliably
  undone in process, so sharing one would silently couple the rows.
* The harness fails closed.  A missing anchor, a subprocess that never emitted
  the sentinel, unparseable JSON, a null digest on both sides or a timeout are
  all a FAIL of that mutation -- never a skip.  The only admitted skip is a
  ``skip_if`` declared in the catalog.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from shutil import ignore_patterns
from typing import Any

from tests.identity_mutation import catalog as cat

PROBE_FILENAME = "_identity_mutation_probe.py"
STORED_IDENTITY_FILE = "_identity_mutation_stored.json"
SENTINEL = "===PROBE_JSON==="
RUNTIME_PATCH_ENV = "IDENTITY_MUTATION_RUNTIME_PATCH"
SANITIZE_ENV = "IDENTITY_MUTATION_SANITIZE"
OUTSIDE_ENV = "IDENTITY_MUTATION_OUTSIDE"
PROBE_TIMEOUT_SECONDS = 180

# Supported interpreters per pyproject's requires-python.
CANDIDATE_INTERPRETERS = ("python3.11", "python3.12", "python3.13")

# Failure reasons.  Kept as a closed vocabulary so evidence stays diffable.
REASON_EFFECT_NOT_MET = "effect_not_met"
REASON_ANCHOR_NOT_FOUND = "anchor_not_found"
REASON_NO_SENTINEL = "probe_emitted_no_sentinel"
REASON_BAD_JSON = "probe_json_unparseable"
REASON_TIMEOUT = "probe_timeout"
REASON_DIGEST_UNAVAILABLE = "digest_unavailable"
REASON_BOTH_DIGESTS_NULL = "baseline_and_mutant_digest_both_null"
REASON_PATCH_INEFFECTIVE = "runtime_patch_ineffective"

# The probe formats an ineffective runtime patch with this prefix.  A patch that
# silently did nothing must never be reported as a finding: that is the exact
# failure mode -- a green result over code that was never actually touched --
# that refuted three earlier closures in this series.
PATCH_FAILURE_PREFIX = "runtime_patch "


class AnchorError(RuntimeError):
    """An edit anchor could not be resolved exactly once."""


class ProbeError(RuntimeError):
    """The subprocess produced no usable measurement."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(slots=True)
class Measurement:
    """One probe result, already stripped of anything machine-specific."""

    code_digest: str | None
    environment_digest: str | None
    total_digest: str | None
    validation_accepted: bool
    validation_error: str | None
    forged_object_accepted: bool
    exception: str | None
    identity_object: dict[str, Any] | None = None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "code_digest": self.code_digest,
            "environment_digest": self.environment_digest,
            "total_digest": self.total_digest,
            "validation_accepted": self.validation_accepted,
            "validation_error": self.validation_error,
            "forged_object_accepted": self.forged_object_accepted,
            "exception": self.exception,
        }


@dataclass(slots=True)
class StepOutcome:
    """What applying the catalog steps asks of the subprocess."""

    env: dict[str, str] = field(default_factory=dict)
    runtime_patch: str = ""
    interpreter: str = ""


# --- byte-accurate AST spans ------------------------------------------------


def _line_offsets(data: bytes) -> list[int]:
    offsets = [0]
    for index, byte in enumerate(data):
        if byte == 0x0A:
            offsets.append(index + 1)
    return offsets


def _position(offsets: list[int], lineno: int, col_offset: int) -> int:
    # ``col_offset`` is a UTF-8 byte offset, so spans are resolved on bytes.
    return offsets[lineno - 1] + col_offset


def _top_level_symbol(tree: ast.Module, name: str) -> ast.stmt:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and node.name == name
    ]
    if len(matches) != 1:
        raise AnchorError(
            f"expected exactly one top-level symbol named {name!r}, found {len(matches)}"
        )
    return matches[0]


def _has_docstring(node: ast.stmt) -> bool:
    body = getattr(node, "body", [])
    return bool(
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )


# --- step application -------------------------------------------------------


def _read_bytes(tree: Path, relative: str) -> bytes:
    path = tree / relative
    if not path.is_file():
        raise AnchorError(f"target file {relative!r} does not exist in the tree")
    return path.read_bytes()


def _write_bytes(tree: Path, relative: str, data: bytes) -> None:
    """Write a mutated file, refusing a no-op or a broken parse.

    A step that changes nothing would turn a ``MUST_NOT_MOVE`` row into a
    vacuous green -- the digest would hold because nothing was mutated, not
    because the canonicalizer is neutral about what was.
    """

    path = tree / relative
    if path.read_bytes() == data:
        raise AnchorError(f"the edit on {relative!r} changed no bytes")
    if relative.endswith(".py"):
        try:
            ast.parse(data.decode("utf-8"))
        except SyntaxError as exc:
            raise AnchorError(f"mutated {relative!r} no longer parses: {exc}") from exc
    path.write_bytes(data)


def _apply_text_edit(tree: Path, step: cat.TextEdit) -> None:
    data = _read_bytes(tree, step.path)
    needle = step.needle.encode("utf-8")
    occurrences = data.count(needle)
    if occurrences != 1:
        raise AnchorError(
            f"needle for {step.path!r} matched {occurrences} times, expected exactly one"
        )
    _write_bytes(tree, step.path, data.replace(needle, step.replacement.encode("utf-8")))


def _apply_ast_edit(tree: Path, step: cat.AstEdit) -> None:
    data = _read_bytes(tree, step.path)
    source = data.decode("utf-8")
    offsets = _line_offsets(data)
    node = _top_level_symbol(ast.parse(source), step.symbol)
    body = getattr(node, "body", [])
    if step.part == "docstring":
        if not _has_docstring(node):
            raise AnchorError(f"{step.symbol!r} in {step.path!r} has no docstring")
        literal = body[0].value
        start = _position(offsets, literal.lineno, literal.col_offset)
        end = _position(offsets, literal.end_lineno, literal.end_col_offset)
    elif step.part == "body":
        first = body[1] if _has_docstring(node) else body[0]
        if first is None:
            raise AnchorError(f"{step.symbol!r} in {step.path!r} has an empty body")
        # Start at the beginning of the line so the replacement carries its own
        # indentation instead of inheriting a partial one.
        start = offsets[first.lineno - 1]
        end = _position(offsets, body[-1].end_lineno, body[-1].end_col_offset)
    else:
        raise AnchorError(f"unsupported AST edit part: {step.part!r}")
    mutated = data[:start] + step.replacement.encode("utf-8") + data[end:]
    if mutated == data:
        raise AnchorError(f"AST edit on {step.symbol!r} in {step.path!r} changed nothing")
    _write_bytes(tree, step.path, mutated)


def _apply_ast_reorder(tree: Path, step: cat.AstReorder) -> None:
    data = _read_bytes(tree, step.path)
    source = data.decode("utf-8")
    module = ast.parse(source)
    first = _top_level_symbol(module, step.first)
    second = _top_level_symbol(module, step.second)
    if first.end_lineno is None or second.end_lineno is None:
        raise AnchorError("reorder anchors are missing end positions")
    if first.end_lineno >= second.lineno:
        raise AnchorError(
            f"{step.first!r} must appear strictly before {step.second!r} in {step.path!r}"
        )
    lines = source.splitlines(keepends=True)
    block_first = lines[first.lineno - 1 : first.end_lineno]
    block_second = lines[second.lineno - 1 : second.end_lineno]
    between = lines[first.end_lineno : second.lineno - 1]
    reordered = (
        lines[: first.lineno - 1]
        + block_second
        + between
        + block_first
        + lines[second.end_lineno :]
    )
    _write_bytes(tree, step.path, "".join(reordered).encode("utf-8"))


def _apply_whitespace_edit(tree: Path, step: cat.WhitespaceEdit) -> None:
    data = _read_bytes(tree, step.path)
    source = data.decode("utf-8")
    module = ast.parse(source)
    node = _top_level_symbol(module, step.symbol)
    body = getattr(node, "body", [])
    if not body:
        raise AnchorError(f"{step.symbol!r} in {step.path!r} has an empty body")
    first = body[1] if _has_docstring(node) else body[0]
    insert_at = first.lineno - 1
    lines = source.splitlines(keepends=True)
    header = lines[insert_at - 1]
    if header.endswith("\n"):
        lines[insert_at - 1] = header[:-1] + " " * step.trailing_spaces + "\n"
    mutated = lines[:insert_at] + ["\n"] * step.blank_lines + lines[insert_at:]
    mutated_source = "".join(mutated)
    if ast.dump(ast.parse(mutated_source)) != ast.dump(module):
        raise AnchorError(
            f"whitespace edit on {step.path!r} altered the AST, which it must not"
        )
    _write_bytes(tree, step.path, mutated_source.encode("utf-8"))


def _apply_create_file(tree: Path, step: cat.CreateFile) -> None:
    path = tree / step.path
    if path.exists():
        raise AnchorError(f"{step.path!r} already exists; the mutation would not add it")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(step.content, encoding="utf-8")


def _apply_symlink(tree: Path, step: cat.SymlinkOutOfTree, outside: Path) -> None:
    source = tree / step.path
    if not source.is_file() or source.is_symlink():
        raise AnchorError(f"{step.path!r} is not a regular file in the tree")
    outside.mkdir(parents=True, exist_ok=True)
    external = outside / Path(step.path).name
    shutil.copy2(source, external)
    original = source.read_bytes()
    source.unlink()
    source.symlink_to(external)
    if not source.is_symlink():
        raise AnchorError(f"{step.path!r} was not replaced by a symlink")
    if source.resolve().is_relative_to(tree.resolve()):
        raise AnchorError(f"{step.path!r} still resolves inside the tree")
    if source.read_bytes() != original:
        raise AnchorError(f"{step.path!r} no longer reads back byte-identically")


def _apply_reregister(
    tree: Path, step: cat.ReregisterIdentityDigest, python: str, outside: Path
) -> None:
    """Recompute the identity here and register whatever it now produces."""

    measurement = run_probe(tree, python=python, extra_env={}, stored=None, outside=outside)
    if measurement.code_digest is None:
        raise AnchorError("cannot re-register: the mutated tree produced no code digest")
    if measurement.code_digest == step.needle:
        raise AnchorError(
            "cannot re-register: the preceding edit left the digest unchanged, so "
            "this step would be a no-op dressed up as a forgery"
        )
    data = _read_bytes(tree, step.path)
    needle = step.needle.encode("utf-8")
    if data.count(needle) != 1:
        raise AnchorError(
            f"registered digest anchor matched {data.count(needle)} times in {step.path!r}"
        )
    _write_bytes(
        tree, step.path, data.replace(needle, measurement.code_digest.encode("utf-8"))
    )


def apply_steps(
    tree: Path, mutation: cat.Mutation, *, python: str, outside: Path
) -> StepOutcome:
    outcome = StepOutcome()
    for step in mutation.steps:
        if isinstance(step, cat.TextEdit):
            _apply_text_edit(tree, step)
        elif isinstance(step, cat.AstEdit):
            _apply_ast_edit(tree, step)
        elif isinstance(step, cat.AstReorder):
            _apply_ast_reorder(tree, step)
        elif isinstance(step, cat.WhitespaceEdit):
            _apply_whitespace_edit(tree, step)
        elif isinstance(step, cat.CreateFile):
            _apply_create_file(tree, step)
        elif isinstance(step, cat.SymlinkOutOfTree):
            _apply_symlink(tree, step, outside)
        elif isinstance(step, cat.ReregisterIdentityDigest):
            _apply_reregister(tree, step, python, outside)
        elif isinstance(step, cat.EnvChange):
            outcome.env.update(dict(step.values))
        elif isinstance(step, cat.RuntimePatch):
            outcome.runtime_patch = step.name
        elif isinstance(step, cat.AlternateInterpreter):
            alternative = find_alternate_interpreter()
            if alternative is None:
                raise AnchorError("no alternative interpreter is installed")
            outcome.interpreter = alternative
        else:  # pragma: no cover - the catalog is a closed vocabulary
            raise AnchorError(f"unsupported catalog step: {type(step).__name__}")
    return outcome


# --- interpreters -----------------------------------------------------------


def find_alternate_interpreter() -> str | None:
    """A supported interpreter whose minor version differs from the current one."""

    current = f"python{sys.version_info.major}.{sys.version_info.minor}"
    for name in CANDIDATE_INTERPRETERS:
        if name == current:
            continue
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


# --- tree materialization ---------------------------------------------------


def resolve_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_revision(repo: Path, revision: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", revision],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def materialize_base(repo: Path, revision: str, destination: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "add", "--detach", str(destination), revision],
        check=True,
        capture_output=True,
    )


def remove_base(repo: Path, destination: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", "--force", str(destination)],
        check=False,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "worktree", "prune"], check=False, capture_output=True
    )


def copy_tree(base: Path, destination: Path) -> None:
    shutil.copytree(
        base,
        destination,
        symlinks=True,
        ignore=ignore_patterns(".git", "__pycache__", ".venv"),
    )


# --- measurement ------------------------------------------------------------


def _probe_source() -> Path:
    return Path(__file__).resolve().parent / "probe.py"


def _base_environment(tree: Path, outside: Path) -> dict[str, str]:
    """A fixed environment, not the ambient one.

    Inheriting ``os.environ`` would let an operator's ``COLLECTOR_SHARD_INDEX``
    or ``MARKET_SYMBOL_CATALOG_FILE`` decide what the matrix measures, so the
    base is built from nothing and every variation is an explicit catalog step.
    """

    sanitize = json.dumps(
        [[str(tree), "<TREE>"], [str(outside), "<OUTSIDE>"], [str(tree.parent), "<TMP>"]]
    )
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        SANITIZE_ENV: sanitize,
        OUTSIDE_ENV: str(outside),
    }


def _parse_probe_output(stdout: bytes) -> dict[str, Any]:
    text = stdout.decode("utf-8", errors="replace")
    marker = text.rfind(SENTINEL)
    if marker < 0:
        raise ProbeError(REASON_NO_SENTINEL, text[-400:])
    payload = text[marker + len(SENTINEL) :].strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProbeError(REASON_BAD_JSON, str(exc)) from exc
    if not isinstance(parsed, dict):
        raise ProbeError(REASON_BAD_JSON, "payload is not an object")
    return parsed


def run_probe(
    tree: Path,
    *,
    python: str,
    extra_env: dict[str, str],
    stored: dict[str, Any] | None,
    outside: Path,
    runtime_patch: str = "",
) -> Measurement:
    shutil.copy2(_probe_source(), tree / PROBE_FILENAME)
    stored_path = tree / STORED_IDENTITY_FILE
    if stored is None:
        stored_path.unlink(missing_ok=True)
    else:
        stored_path.write_text(
            json.dumps(stored, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )

    env = _base_environment(tree, outside)
    if runtime_patch:
        env[RUNTIME_PATCH_ENV] = runtime_patch
    env.update(extra_env)

    try:
        completed = subprocess.run(
            [python, PROBE_FILENAME],
            cwd=str(tree),
            env=env,
            capture_output=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(REASON_TIMEOUT, f"{PROBE_TIMEOUT_SECONDS}s") from exc

    parsed = _parse_probe_output(completed.stdout)
    return Measurement(
        code_digest=parsed.get("code_digest"),
        environment_digest=parsed.get("environment_digest"),
        total_digest=parsed.get("total_digest"),
        validation_accepted=bool(parsed.get("validation_accepted")),
        validation_error=parsed.get("validation_error"),
        forged_object_accepted=bool(parsed.get("forged_object_accepted")),
        exception=parsed.get("exception"),
        identity_object=parsed.get("identity_object"),
    )


# --- evaluation -------------------------------------------------------------


def evaluate(
    mutation: cat.Mutation, baseline: Measurement, observed: Measurement
) -> tuple[str, str]:
    """Return ``(observed_class, failure_reason)``.

    ``failure_reason`` is empty when the required effect is met.
    """

    if baseline.total_digest is None and observed.total_digest is None:
        return cat.ESCAPE, REASON_BOTH_DIGESTS_NULL

    effect = mutation.expected_effect
    if observed.code_digest is None:
        # A collapsed measurement is not a rejection and not a movement.  Every
        # effect in the vocabulary is a statement about a digest that exists, so
        # reporting one without it would be inventing the result.
        return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
    if effect == cat.MUST_MOVE:
        if observed.total_digest is None:
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        met = observed.total_digest != baseline.total_digest
    elif effect == cat.MUST_NOT_MOVE:
        if observed.total_digest is None:
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        met = observed.total_digest == baseline.total_digest
    elif effect == cat.MUST_REJECT:
        # Moving the digest is not enough: the question is whether a
        # self-consistent object recomputed inside the mutated tree is refused.
        met = observed.forged_object_accepted is False
    elif effect == cat.MUST_NOT_MOVE_CODE_MUST_MOVE_ENV:
        if observed.code_digest is None or observed.environment_digest is None:
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        met = (
            observed.code_digest == baseline.code_digest
            and observed.environment_digest != baseline.environment_digest
        )
    else:  # pragma: no cover - the vocabulary is closed
        raise ValueError(f"unsupported expected effect: {effect!r}")

    if met and cat.REQUIRE_FORGED_REJECTED in mutation.also_requires:
        met = observed.forged_object_accepted is False

    return (cat.GUARD, "") if met else (cat.ESCAPE, REASON_EFFECT_NOT_MET)


# --- orchestration ----------------------------------------------------------


@dataclass(slots=True)
class Row:
    id: str
    expected_effect: str
    observed_class: str
    failure_reason: str
    measurement: Measurement | None

    def as_evidence(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "id": self.id,
            "expected_effect": self.expected_effect,
        }
        if self.measurement is None:
            body.update(
                {
                    "code_digest": None,
                    "environment_digest": None,
                    "total_digest": None,
                    "validation_accepted": False,
                    "validation_error": None,
                    "forged_object_accepted": False,
                    "exception": None,
                }
            )
        else:
            body.update(self.measurement.as_evidence())
        body["failure_reason"] = self.failure_reason
        body["observed_class"] = self.observed_class
        return body


def run_matrix(
    *,
    revision: str,
    only: tuple[str, ...] = (),
    repo: Path | None = None,
    python: str | None = None,
) -> dict[str, Any]:
    """Materialize, mutate, measure and classify.  Returns the evidence body."""

    repo_root = repo or resolve_repo_root()
    interpreter = python or sys.executable
    resolved = resolve_revision(repo_root, revision)
    selected = [m for m in cat.CATALOG if not only or m.id in only]
    unknown = sorted(set(only) - {m.id for m in cat.CATALOG})
    if unknown:
        raise ValueError(f"unknown mutation ids: {', '.join(unknown)}")

    workspace = Path(tempfile.mkdtemp(prefix="identity-mutation-"))
    base = workspace / "base"
    outside_root = workspace / "outside"
    rows: list[Row] = []
    try:
        materialize_base(repo_root, resolved, base)

        # Bootstrap: the frozen object every later measurement is validated
        # against.  It is a measurement of the pristine tree, so it can only be
        # taken before any mutation exists.
        bootstrap_tree = workspace / "bootstrap"
        copy_tree(base, bootstrap_tree)
        bootstrap = run_probe(
            bootstrap_tree,
            python=interpreter,
            extra_env={},
            stored=None,
            outside=outside_root / "bootstrap",
        )
        frozen_identity = bootstrap.identity_object
        if frozen_identity is None or bootstrap.total_digest is None:
            raise RuntimeError(
                "the pristine tree produced no identity, so nothing measured "
                f"against it would mean anything: {bootstrap.exception}"
            )

        baseline_tree = workspace / "baseline"
        copy_tree(base, baseline_tree)
        baseline = run_probe(
            baseline_tree,
            python=interpreter,
            extra_env={},
            stored=frozen_identity,
            outside=outside_root / "baseline",
        )
        if baseline.total_digest is None or not baseline.validation_accepted:
            raise RuntimeError(
                "the baseline measurement is unusable -- an untouched tree must "
                "produce a digest and validate its own frozen identity: "
                f"digest={baseline.total_digest} "
                f"validation_error={baseline.validation_error}"
            )

        for mutation in selected:
            rows.append(
                _run_one(
                    mutation,
                    base=base,
                    workspace=workspace,
                    outside_root=outside_root,
                    interpreter=interpreter,
                    frozen_identity=frozen_identity,
                    baseline=baseline,
                )
            )
    finally:
        remove_base(repo_root, base)
        shutil.rmtree(workspace, ignore_errors=True)

    return {
        "baseline_rev": resolved,
        "baseline": {
            "expected_effect": "REFERENCE",
            **baseline.as_evidence(),
        },
        "mutations": [row.as_evidence() for row in rows],
    }


def _run_one(
    mutation: cat.Mutation,
    *,
    base: Path,
    workspace: Path,
    outside_root: Path,
    interpreter: str,
    frozen_identity: dict[str, Any] | None,
    baseline: Measurement,
) -> Row:
    if (
        mutation.skip_if == "alternative_interpreter_unavailable"
        and find_alternate_interpreter() is None
    ):
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.SKIPPED,
            failure_reason=mutation.skip_if,
            measurement=None,
        )

    tree = workspace / mutation.id
    outside = outside_root / mutation.id
    try:
        copy_tree(base, tree)
        outcome = apply_steps(tree, mutation, python=interpreter, outside=outside)
        measurement = run_probe(
            tree,
            python=outcome.interpreter or interpreter,
            extra_env=outcome.env,
            stored=frozen_identity,
            outside=outside,
            runtime_patch=outcome.runtime_patch,
        )
    except AnchorError as exc:
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=REASON_ANCHOR_NOT_FOUND,
            measurement=Measurement(
                code_digest=None,
                environment_digest=None,
                total_digest=None,
                validation_accepted=False,
                validation_error=None,
                forged_object_accepted=False,
                exception=_scrub(str(exc), workspace),
            ),
        )
    except ProbeError as exc:
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=exc.reason,
            measurement=Measurement(
                code_digest=None,
                environment_digest=None,
                total_digest=None,
                validation_accepted=False,
                validation_error=None,
                forged_object_accepted=False,
                exception=exc.reason,
            ),
        )

    if (measurement.exception or "").startswith(PATCH_FAILURE_PREFIX):
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=REASON_PATCH_INEFFECTIVE,
            measurement=measurement,
        )

    observed_class, reason = evaluate(mutation, baseline, measurement)
    return Row(
        id=mutation.id,
        expected_effect=mutation.expected_effect,
        observed_class=observed_class,
        failure_reason=reason,
        measurement=measurement,
    )


def _scrub(text: str, workspace: Path) -> str:
    """Keep temporary paths out of the evidence."""

    cleaned = text.replace(str(workspace), "<TMP>")
    cleaned = cleaned.replace(str(os.environ.get("TMPDIR", "/tmp")), "<TMP>")
    return cleaned
