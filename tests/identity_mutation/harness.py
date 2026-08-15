"""Tree materialization, mutation application and isolated measurement.

Contract
--------

* The target tree is materialized once per run with ``git worktree add
  --detach``.  Every mutation then works on its own ``shutil.copytree`` of that
  base.  The base worktree is never mutated and the user's working tree is
  never touched.
* Every measurement runs in its own subprocess, launched with
  ``PYTHONSAFEPATH=1`` and an explicit ``PYTHONPATH``.  Environment mutations
  and runtime patches contaminate an interpreter in ways that cannot be
  reliably undone in process, so sharing one would silently couple the rows.
* The harness fails closed.  A missing anchor, a subprocess that never emitted
  the sentinel, unparseable JSON, a null digest where the effect needs one, a
  timeout, an unprovisioned second interpreter, an anchor that was never
  supplied and a mutation that turned out to be inert are all a FAIL of that
  mutation -- never a skip.  The catalog declares no skip condition and this
  module can emit none.

Why the path configuration is explicit
--------------------------------------

``python probe.py`` puts the script's directory at ``sys.path[0]``, ahead of
every ``PYTHONPATH`` entry, and runs ``site`` before that entry exists at all.
Under that invocation M-27 could never win the path race and the
``sitecustomize`` of M-31 would never be imported: both mutations would be
applied, measured and filed as findings without having had any effect.  Running
the probe with ``PYTHONSAFEPATH=1`` and ``PYTHONPATH`` naming the tree makes
resolution order a thing the harness states rather than a thing it inherits.
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
from functools import cache
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
SHADOWED_MODULE_ENV = "IDENTITY_MUTATION_SHADOWED_MODULE"
ANCHOR_ENV = "IDENTITY_ANCHOR_FINGERPRINT"
INTERPRETERS_ENV = "IDENTITY_MUTATION_INTERPRETERS"
PROBE_TIMEOUT_SECONDS = 180

# Variables the harness owns.  A catalog step that set one of them would be
# rewriting the instrument rather than the tree.
RESERVED_ENV = frozenset({"PYTHONPATH", "PYTHONSAFEPATH", ANCHOR_ENV})

# Supported runtimes per pyproject's requires-python.  A declared interpreter
# outside this set is ignored: measuring under a runtime the project does not
# support would answer a question nobody asked.
SUPPORTED_INTERPRETER_VERSIONS = ("3.11", "3.12", "3.13")

# Failure reasons.  Kept as a closed vocabulary so evidence stays diffable.
REASON_EFFECT_NOT_MET = "effect_not_met"
REASON_ANCHOR_NOT_FOUND = "anchor_not_found"
REASON_NO_SENTINEL = "probe_emitted_no_sentinel"
REASON_BAD_JSON = "probe_json_unparseable"
REASON_TIMEOUT = "probe_timeout"
REASON_DIGEST_UNAVAILABLE = "digest_unavailable"
REASON_PATCH_INEFFECTIVE = "runtime_patch_ineffective"
REASON_MUTATION_INEFFECTIVE = "mutation_ineffective"
REASON_DIGEST_DID_NOT_MOVE = "digest_did_not_move"
REASON_DIGEST_MOVED = "digest_moved"
REASON_CODE_DIGEST_MOVED = "code_digest_moved"
REASON_ENV_DIGEST_DID_NOT_MOVE = "environment_digest_did_not_move"
REASON_COMBINED_VALIDATOR_ABSENT = "combined_validator_absent"
REASON_ANCHOR_MECHANISM_ABSENT = "anchor_mechanism_absent"
REASON_ANCHOR_NOT_SUPPLIED = "anchor_not_supplied"
REASON_FORGED_OBJECT_ACCEPTED = "forged_object_accepted"
REASON_ALT_INTERPRETER_UNAVAILABLE = "alternative_interpreter_unavailable"
REASON_ALT_INTERPRETER_UNUSABLE = "alternative_interpreter_unusable"

FAILURE_REASONS = frozenset(
    {
        "",
        REASON_EFFECT_NOT_MET,
        REASON_ANCHOR_NOT_FOUND,
        REASON_NO_SENTINEL,
        REASON_BAD_JSON,
        REASON_TIMEOUT,
        REASON_DIGEST_UNAVAILABLE,
        REASON_PATCH_INEFFECTIVE,
        REASON_MUTATION_INEFFECTIVE,
        REASON_DIGEST_DID_NOT_MOVE,
        REASON_DIGEST_MOVED,
        REASON_CODE_DIGEST_MOVED,
        REASON_ENV_DIGEST_DID_NOT_MOVE,
        REASON_COMBINED_VALIDATOR_ABSENT,
        REASON_ANCHOR_MECHANISM_ABSENT,
        REASON_ANCHOR_NOT_SUPPLIED,
        REASON_FORGED_OBJECT_ACCEPTED,
        REASON_ALT_INTERPRETER_UNAVAILABLE,
        REASON_ALT_INTERPRETER_UNUSABLE,
    }
)

# The probe formats an ineffective runtime patch with this prefix.  A patch that
# silently did nothing must never be reported as a finding: that is the exact
# failure mode -- a green result over code that was never actually touched --
# that refuted three earlier closures in this series.
PATCH_FAILURE_PREFIX = "runtime_patch "

# The key a mutator would install if the anchor's trust root lived in the tree.
_MUTATOR_PUBLIC_KEY = """\
-----BEGIN PUBLIC KEY-----
aWRlbnRpdHktbXV0YXRpb24tbWF0cml4LW11dGF0b3Ita2V5LW5vdC1hLXJlYWwt
a2V5LXVzZWQtb25seS10by1hc2std2hldGhlci10aGUtdHJlZS10cnVzdHMtaXQ=
-----END PUBLIC KEY-----
"""


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
    combined_validation_accepted: bool
    combined_validator_absent: bool
    rejection_kind: str | None
    anchor_mechanism_absent: bool
    exception: str | None
    sitecustomize_active: bool = False
    pythonpath_shadow_active: bool = False
    identity_object: dict[str, Any] | None = None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "code_digest": self.code_digest,
            "environment_digest": self.environment_digest,
            "total_digest": self.total_digest,
            "validation_accepted": self.validation_accepted,
            "validation_error": self.validation_error,
            "forged_object_accepted": self.forged_object_accepted,
            "combined_validation_accepted": self.combined_validation_accepted,
            "combined_validator_absent": self.combined_validator_absent,
            "rejection_kind": self.rejection_kind,
            "anchor_mechanism_absent": self.anchor_mechanism_absent,
            # Recorded, not merely checked: these are the only fields that say a
            # mutation actually took effect, and a reader of the frozen evidence
            # must be able to tell an escape from an inert mutation without
            # re-running anything.
            "sitecustomize_active": self.sitecustomize_active,
            "pythonpath_shadow_active": self.pythonpath_shadow_active,
            "exception": self.exception,
        }

    def probe_flag(self, name: str) -> bool:
        return bool(getattr(self, name, False))

    @property
    def rejected(self) -> bool:
        """Did the system, as mutated, refuse to operate?

        Three shapes count, all decided by the probe: a falsy return from the
        combined validator, an exception propagated out of it, and a failure
        caused by the mutation that stops the tree from producing an identity
        at all.  An absent combined validator is not one of them.
        """

        return self.rejection_kind is not None


def _unavailable_measurement(exception: str | None) -> Measurement:
    """What a row carries when no measurement could be taken at all."""

    return Measurement(
        code_digest=None,
        environment_digest=None,
        total_digest=None,
        validation_accepted=False,
        validation_error=None,
        forged_object_accepted=False,
        combined_validation_accepted=False,
        combined_validator_absent=False,
        rejection_kind=None,
        anchor_mechanism_absent=True,
        exception=exception,
    )


@dataclass(slots=True)
class StepOutcome:
    """What applying the catalog steps asks of the subprocess."""

    env: dict[str, str] = field(default_factory=dict)
    runtime_patch: str = ""
    interpreter: str = ""
    pythonpath_prefix: list[str] = field(default_factory=list)
    shadowed_module: str = ""


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

    A step that changes nothing would turn a ``MUST_NOT_MOVE_AND_ACCEPT`` row
    into a vacuous green -- the digest would hold because nothing was mutated,
    not because the canonicalizer is neutral about what was.
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


def _ast_edited_source(data: bytes, symbol: str, part: str, replacement: str, label: str) -> bytes:
    source = data.decode("utf-8")
    offsets = _line_offsets(data)
    node = _top_level_symbol(ast.parse(source), symbol)
    body = getattr(node, "body", [])
    if part == "docstring":
        if not _has_docstring(node):
            raise AnchorError(f"{symbol!r} in {label!r} has no docstring")
        literal = body[0].value
        start = _position(offsets, literal.lineno, literal.col_offset)
        end = _position(offsets, literal.end_lineno, literal.end_col_offset)
    elif part == "body":
        first = body[1] if _has_docstring(node) else body[0]
        if first is None:
            raise AnchorError(f"{symbol!r} in {label!r} has an empty body")
        # Start at the beginning of the line so the replacement carries its own
        # indentation instead of inheriting a partial one.
        start = offsets[first.lineno - 1]
        end = _position(offsets, body[-1].end_lineno, body[-1].end_col_offset)
    else:
        raise AnchorError(f"unsupported AST edit part: {part!r}")
    mutated = data[:start] + replacement.encode("utf-8") + data[end:]
    if mutated == data:
        raise AnchorError(f"AST edit on {symbol!r} in {label!r} changed nothing")
    return mutated


def _apply_ast_edit(tree: Path, step: cat.AstEdit) -> None:
    data = _read_bytes(tree, step.path)
    mutated = _ast_edited_source(data, step.symbol, step.part, step.replacement, step.path)
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


def _apply_delete_file(tree: Path, step: cat.DeleteFile) -> None:
    path = tree / step.path
    if not path.is_file() or path.is_symlink():
        raise AnchorError(f"{step.path!r} is not a regular file in the tree")
    path.unlink()


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


def _apply_pythonpath_shadow(
    tree: Path, step: cat.PythonPathShadow, outcome: StepOutcome, outside: Path
) -> None:
    """Put an altered copy of one module ahead of the tree's own.

    The shadow package re-exports the real ``app`` directory on ``__path__``,
    so exactly one module resolves from outside and every other one -- the
    identity module included, whose ``__file__`` decides which tree gets hashed
    -- still comes from the tree under test.
    """

    shadow_root = outside / "pythonpath_shadow"
    package, _, module_name = step.module.rpartition(".")
    if not package or not module_name:
        raise AnchorError(f"{step.module!r} is not a submodule of a package")
    package_dir = shadow_root / Path(*package.split("."))
    package_dir.mkdir(parents=True, exist_ok=True)

    real_package_dir = tree / Path(*package.split("."))
    real_init = real_package_dir / "__init__.py"
    if not real_init.is_file():
        raise AnchorError(f"{package!r} is not a regular package in the tree")
    (package_dir / "__init__.py").write_text(
        real_init.read_text(encoding="utf-8")
        + f"\n__path__.append({str(real_package_dir)!r})\n",
        encoding="utf-8",
    )

    altered = _ast_edited_source(
        _read_bytes(tree, step.relative_path),
        step.symbol,
        "body",
        step.replacement,
        step.relative_path,
    )
    (package_dir / f"{module_name}.py").write_bytes(altered)

    outcome.pythonpath_prefix.append(str(shadow_root))
    outcome.shadowed_module = step.module


def _existing_paths(tree: Path, paths: tuple[str, ...]) -> list[str]:
    return [relative for relative in paths if (tree / relative).is_file()]


def _apply_remove_anchor_artifact(tree: Path, step: cat.RemoveAnchorArtifact) -> None:
    """Delete the anchor artefact, if the tree carries one at all.

    Absence is not an error here and must not be reported as a missing edit
    anchor: a tree with nothing to delete is a tree with no anchor, which the
    probe reports as ``anchor_mechanism_absent``.  Reporting it as
    ``anchor_not_found`` would blame the instrument for the finding.
    """

    for relative in _existing_paths(tree, step.paths):
        (tree / relative).unlink()


def _apply_reanchor_with_own_key(
    tree: Path, step: cat.ReanchorWithOwnKey, python: str, outside: Path
) -> None:
    """Install the mutator's own key and re-anchor the registry with it.

    The re-anchoring reuses the re-registration machinery: whatever digest the
    artefact pins is replaced by the one this tree now computes.  When commit 3
    defines the artefact's real format, this step is where that format has to
    be taught -- and if it is not, the artefact keeps its old digest and the row
    goes red instead of quietly passing.
    """

    for relative in _existing_paths(tree, step.key_paths):
        (tree / relative).write_text(_MUTATOR_PUBLIC_KEY, encoding="utf-8")
    for relative in _existing_paths(tree, step.artifact_paths):
        registered = _registered_digest(tree)
        if registered and registered.encode("utf-8") in (tree / relative).read_bytes():
            _apply_reregister(
                tree,
                cat.ReregisterIdentityDigest(path=relative, needle=registered),
                python,
                outside,
            )


def _registered_digest(tree: Path) -> str:
    """The digest literal the tree registers, read without importing it."""

    source = (tree / "app" / "signal_scientific_identity.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name)
            and target.id == "REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS"
            for target in node.targets
        ):
            for value in getattr(node.value, "values", []):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    return value.value
    return ""


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
        elif isinstance(step, cat.DeleteFile):
            _apply_delete_file(tree, step)
        elif isinstance(step, cat.SymlinkOutOfTree):
            _apply_symlink(tree, step, outside)
        elif isinstance(step, cat.ReregisterIdentityDigest):
            _apply_reregister(tree, step, python, outside)
        elif isinstance(step, cat.PythonPathShadow):
            _apply_pythonpath_shadow(tree, step, outcome, outside)
        elif isinstance(step, cat.RemoveAnchorArtifact):
            _apply_remove_anchor_artifact(tree, step)
        elif isinstance(step, cat.ReanchorWithOwnKey):
            _apply_reanchor_with_own_key(tree, step, python, outside)
        elif isinstance(step, cat.EnvChange):
            reserved = RESERVED_ENV & {name for name, _ in step.values}
            if reserved:
                raise AnchorError(
                    f"catalog step may not set harness-owned variables: {sorted(reserved)}"
                )
            outcome.env.update(dict(step.values))
        elif isinstance(step, cat.RuntimePatch):
            outcome.runtime_patch = step.name
        elif isinstance(step, cat.AlternateInterpreter):
            alternative = find_alternate_interpreter()
            if alternative is None:
                raise ProbeError(REASON_ALT_INTERPRETER_UNAVAILABLE)
            outcome.interpreter = alternative
        else:  # pragma: no cover - the catalog is a closed vocabulary
            raise AnchorError(f"unsupported catalog step: {type(step).__name__}")
    return outcome


# --- interpreters -----------------------------------------------------------


@cache
def interpreter_version(executable: str) -> str:
    """``major.minor`` of an interpreter, or an empty string if it will not run."""

    try:
        completed = subprocess.run(
            [
                executable,
                "-c",
                "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def configured_interpreters() -> tuple[str, ...]:
    """Interpreters named by explicit path, in the order they were declared.

    Explicit paths are the whole contract: a runner that resolved ``python3.11``
    to whatever happened to be first on ``PATH`` would be a runner whose M-16
    measurement meant something different every time it was provisioned.
    """

    raw = os.environ.get(INTERPRETERS_ENV, "")
    return tuple(part for part in raw.split(os.pathsep) if part.strip())


def find_alternate_interpreter() -> str | None:
    """A declared, supported interpreter whose minor differs from the current one.

    There is no ``PATH`` fallback, and its absence is the point.  An interpreter
    that merely happens to be installed is not one anybody chose: it may be a
    shim with none of the project's dependencies, in which case it imports
    nothing, measures nothing, and turns M-16 red for a reason that has no
    relation to the code under audit -- which is what it did here before this
    was removed.  An interpreter nobody declared does not exist for this matrix,
    and the row fails closed with ``alternative_interpreter_unavailable``.
    """

    current = f"{sys.version_info.major}.{sys.version_info.minor}"
    for candidate in configured_interpreters():
        version = interpreter_version(candidate)
        if version in SUPPORTED_INTERPRETER_VERSIONS and version != current:
            return candidate
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


def _base_environment(tree: Path, outside: Path, pythonpath_prefix: list[str]) -> dict[str, str]:
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
        # Resolution order is stated, never inherited.  See the module docstring.
        "PYTHONSAFEPATH": "1",
        "PYTHONPATH": os.pathsep.join([*pythonpath_prefix, str(tree)]),
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
    pythonpath_prefix: list[str] | None = None,
    shadowed_module: str = "",
    anchor: str = "",
) -> Measurement:
    shutil.copy2(_probe_source(), tree / PROBE_FILENAME)
    stored_path = tree / STORED_IDENTITY_FILE
    if stored is None:
        stored_path.unlink(missing_ok=True)
    else:
        stored_path.write_text(
            json.dumps(stored, sort_keys=True, separators=(",", ":")), encoding="utf-8"
        )

    env = _base_environment(tree, outside, pythonpath_prefix or [])
    if runtime_patch:
        env[RUNTIME_PATCH_ENV] = runtime_patch
    if shadowed_module:
        env[SHADOWED_MODULE_ENV] = shadowed_module
    if anchor:
        # The anchor reaches the tree only through the environment of the
        # auditing process.  No file of the target tree is ever consulted for
        # it: a fingerprint the mutator can rewrite anchors nothing.
        env[ANCHOR_ENV] = anchor
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
        combined_validation_accepted=bool(parsed.get("combined_validation_accepted")),
        combined_validator_absent=bool(parsed.get("combined_validator_absent")),
        rejection_kind=parsed.get("rejection_kind"),
        anchor_mechanism_absent=bool(parsed.get("anchor_mechanism_absent")),
        exception=parsed.get("exception"),
        sitecustomize_active=bool(parsed.get("sitecustomize_active")),
        pythonpath_shadow_active=bool(parsed.get("pythonpath_shadow_active")),
        identity_object=parsed.get("identity_object"),
    )


# --- evaluation -------------------------------------------------------------


def _rejection_reason(mutation: cat.Mutation, observed: Measurement) -> str:
    """Why nothing refused to operate.

    The three answers are different findings and commit 3 closes them by
    different means, so they are not collapsed into ``effect_not_met``.
    """

    if mutation.requires_anchor and observed.anchor_mechanism_absent:
        return REASON_ANCHOR_MECHANISM_ABSENT
    if observed.combined_validator_absent:
        return REASON_COMBINED_VALIDATOR_ABSENT
    return REASON_EFFECT_NOT_MET


def evaluate(
    mutation: cat.Mutation, baseline: Measurement, observed: Measurement
) -> tuple[str, str]:
    """Return ``(observed_class, failure_reason)``.

    ``failure_reason`` is empty when the required effect is met.  Each effect is
    checked in the order it states its conjuncts, so the reason names the first
    thing that failed rather than the last thing that was looked at.
    """

    effect = mutation.expected_effect
    digests_available = (
        observed.code_digest is not None and observed.environment_digest is not None
    )

    if effect == cat.MUST_MOVE_AND_REJECT:
        if not digests_available:
            # A collapsed measurement is not movement.  Claiming one without a
            # digest would be inventing the result.
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        if observed.total_digest == baseline.total_digest:
            return cat.ESCAPE, REASON_DIGEST_DID_NOT_MOVE
        if not observed.rejected:
            return cat.ESCAPE, _rejection_reason(mutation, observed)
    elif effect == cat.MUST_REJECT_ONLY:
        if not observed.rejected:
            return cat.ESCAPE, _rejection_reason(mutation, observed)
    elif effect == cat.MUST_NOT_MOVE_AND_ACCEPT:
        if not digests_available:
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        if observed.total_digest != baseline.total_digest:
            return cat.ESCAPE, REASON_DIGEST_MOVED
        if not observed.combined_validation_accepted:
            if observed.combined_validator_absent:
                return cat.ESCAPE, REASON_COMBINED_VALIDATOR_ABSENT
            return cat.ESCAPE, REASON_EFFECT_NOT_MET
    elif effect == cat.MUST_NOT_MOVE_CODE_MUST_MOVE_ENV:
        if not digests_available:
            return cat.ESCAPE, REASON_DIGEST_UNAVAILABLE
        if observed.code_digest != baseline.code_digest:
            return cat.ESCAPE, REASON_CODE_DIGEST_MOVED
        if observed.environment_digest == baseline.environment_digest:
            return cat.ESCAPE, REASON_ENV_DIGEST_DID_NOT_MOVE
        if not observed.rejected:
            return cat.ESCAPE, _rejection_reason(mutation, observed)
    else:  # pragma: no cover - the vocabulary is closed
        raise ValueError(f"unsupported expected effect: {effect!r}")

    if (
        cat.REQUIRE_FORGED_REJECTED in mutation.also_requires
        and observed.forged_object_accepted
    ):
        return cat.ESCAPE, REASON_FORGED_OBJECT_ACCEPTED

    return cat.GUARD, ""


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
        measurement = self.measurement or _unavailable_measurement(None)
        body.update(measurement.as_evidence())
        body["failure_reason"] = self.failure_reason
        body["observed_class"] = self.observed_class
        return body


def resolve_anchor(anchor: str | None = None) -> str:
    """The external anchor, from the auditing process -- never from the tree."""

    return (anchor if anchor is not None else os.environ.get(ANCHOR_ENV, "")).strip()


def run_matrix(
    *,
    revision: str,
    only: tuple[str, ...] = (),
    repo: Path | None = None,
    python: str | None = None,
    anchor: str | None = None,
) -> dict[str, Any]:
    """Materialize, mutate, measure and classify.  Returns the evidence body."""

    repo_root = repo or resolve_repo_root()
    interpreter = python or sys.executable
    resolved_anchor = resolve_anchor(anchor)
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
            anchor=resolved_anchor,
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
            anchor=resolved_anchor,
        )
        # The control is stated on the half validator on purpose: an untouched
        # tree must be able to validate its own frozen identity with what it
        # has today, and the combined entry point does not exist yet.  Asserting
        # the combined one here would make the whole matrix unrunnable until
        # commit 3 lands.
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
                    anchor=resolved_anchor,
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


def _failed_row(mutation: cat.Mutation, reason: str, detail: str | None = None) -> Row:
    return Row(
        id=mutation.id,
        expected_effect=mutation.expected_effect,
        observed_class=cat.ESCAPE,
        failure_reason=reason,
        measurement=_unavailable_measurement(detail if detail is not None else reason),
    )


def _run_one(
    mutation: cat.Mutation,
    *,
    base: Path,
    workspace: Path,
    outside_root: Path,
    interpreter: str,
    frozen_identity: dict[str, Any] | None,
    baseline: Measurement,
    anchor: str,
) -> Row:
    if mutation.requires_anchor and not anchor:
        # Fails closed, never skipped: a mutation that interrogates the anchor
        # and is not given one has not been measured, and saying nothing about
        # it would be indistinguishable from saying it passed.
        return _failed_row(mutation, REASON_ANCHOR_NOT_SUPPLIED)

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
            pythonpath_prefix=outcome.pythonpath_prefix,
            shadowed_module=outcome.shadowed_module,
            anchor=anchor,
        )
    except AnchorError as exc:
        return _failed_row(mutation, REASON_ANCHOR_NOT_FOUND, _scrub(str(exc), workspace))
    except ProbeError as exc:
        return _failed_row(mutation, exc.reason)

    if (measurement.exception or "").startswith(PATCH_FAILURE_PREFIX):
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=REASON_PATCH_INEFFECTIVE,
            measurement=measurement,
        )

    if mutation.requires_probe_flag and not measurement.probe_flag(
        mutation.requires_probe_flag
    ):
        # The mutation was applied and had no effect.  Filing that as a finding
        # would credit the tree with a guard it never exercised, which is the
        # error that refuted three earlier closures in this series.
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=REASON_MUTATION_INEFFECTIVE,
            measurement=measurement,
        )

    if outcome.interpreter and (
        measurement.code_digest is None or measurement.environment_digest is None
    ):
        # A second interpreter that cannot import the tree measures nothing.
        # That is an unprovisioned runner, not a property of the code.
        return Row(
            id=mutation.id,
            expected_effect=mutation.expected_effect,
            observed_class=cat.ESCAPE,
            failure_reason=REASON_ALT_INTERPRETER_UNUSABLE,
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
