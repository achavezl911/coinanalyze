"""Deterministic identity for versioned confirmatory scientific mechanics.

The identity is deliberately narrower than a Git commit and stronger than a
human-maintained version label.  It has two halves and both must hold before
the system may operate:

*Code.*  Every file that can change what the science computes, hashed from a
canonical AST.  The surface is **discovered**, not enumerated: ``app/**/*.py``
participates by existing, so a module nobody remembered to list is inside by
construction.  ``sql/schema.sql``, ``pyproject.toml``, ``requirements.lock`` and
``config/**/*.json`` complete it -- the schema constrains what may be written,
the two dependency files decide which library code runs, and the versioned
routing catalog decides which market's data is read.

*Environment.*  The interpreter and the effective settings that decide coverage,
retention and sharding, plus the routing catalog as actually resolved and the
path it was resolved from.  See :mod:`app.signal_runtime_contract`.

Neither half is compared against a constant in this file.  Both are compared
against ``identity/registry.json``, a declarative registry outside the code, and
the environment half is compared by **membership in an enumerated set**: a
sharded deployment has one legitimate environment digest per shard, so requiring
equality to a single value would mean no instance other than shard 0 could ever
validate.

What is *not* material: ``#`` comments, blank lines, indentation width and
source positions.  What *is* material and was not before: docstrings.  A
docstring states the contract a symbol claims to honour, and a scientific
surface that lets the claim change silently while the code stays fixed is not
describing the system it audits.

Fail-closed is the rule, everywhere.  A component that cannot be read, a surface
entry that resolves outside the root through a symlink, a registry that is
missing or malformed, or an environment profile nobody authorized all produce a
refusal to operate.  There is no path in this module that accepts by default.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app import config

SCIENTIFIC_IDENTITY_VERSION_V1 = 1
SCIENTIFIC_IDENTITY_CANONICALIZER = "scientific_source_canonicalization_v2"

IDENTITY_REGISTRY_RELATIVE_PATH = "identity/registry.json"
IDENTITY_REGISTRY_SCHEMA_VERSION = 1


class ScientificIdentityError(RuntimeError):
    """The identity could not be computed, or does not match its registry."""


# --- the surface ------------------------------------------------------------
#
# Declared as roots and patterns, never as a list of files.  An allowlist is a
# thing somebody has to remember to update, and the audit of this project has
# already refuted three closures whose defect was exactly that.

SURFACE_PYTHON_ROOT = "app"
SURFACE_JSON_ROOT = "config"
SURFACE_REQUIRED_FILES: tuple[str, ...] = (
    "sql/schema.sql",
    "pyproject.toml",
    "requirements.lock",
)
SURFACE_EXCLUDED_DIRECTORIES = frozenset({"__pycache__"})

CANONICALIZER_PYTHON_MODULE = "canonical_python_module_v2"
CANONICALIZER_SQL = "canonical_sql_source_v1"
CANONICALIZER_TEXT = "canonical_text_source_v1"


@dataclass(frozen=True, slots=True)
class ScientificSurfaceEntry:
    """One discovered file of the scientific surface."""

    relative_path: str
    canonicalizer: str

    @property
    def name(self) -> str:
        return self.relative_path


def resolve_surface_root() -> Path:
    """The tree whose files are the surface.

    Resolved through :func:`app.config.resolve_project_root`, so an installed
    package hashes the deployment it actually reads its inputs from rather than
    the site-packages directory it happens to live in.
    """

    return config.resolve_project_root()


def _canonicalizer_for(relative_path: str) -> str:
    if relative_path.endswith(".py"):
        return CANONICALIZER_PYTHON_MODULE
    if relative_path.endswith(".sql"):
        return CANONICALIZER_SQL
    return CANONICALIZER_TEXT


def _assert_inside_root(root: Path, path: Path) -> None:
    """Refuse a surface entry that leaves the root through a link.

    A byte-identical component read through a symlink is not the same claim as
    a byte-identical component read from the tree: whoever controls the link
    target controls what runs, and the digest cannot see it.
    """

    real_root = Path(os.path.realpath(root))
    real_path = Path(os.path.realpath(path))
    if not real_path.is_relative_to(real_root):
        raise ScientificIdentityError(
            f"surface entry {path.name!r} resolves to {real_path}, outside the "
            f"scientific surface root {real_root}"
        )


def _discovered_python_sources(root: Path) -> list[str]:
    package = root / SURFACE_PYTHON_ROOT
    if not package.is_dir():
        raise ScientificIdentityError(
            f"scientific surface root {root} has no {SURFACE_PYTHON_ROOT}/ package"
        )
    found: list[str] = []
    for path in package.rglob("*.py"):
        if SURFACE_EXCLUDED_DIRECTORIES & set(path.parts):
            continue
        _assert_inside_root(root, path)
        found.append(path.relative_to(root).as_posix())
    if not found:
        raise ScientificIdentityError(
            f"scientific surface root {root} has no Python sources under "
            f"{SURFACE_PYTHON_ROOT}/"
        )
    return found


def _discovered_json_configs(root: Path) -> list[str]:
    directory = root / SURFACE_JSON_ROOT
    if not directory.is_dir():
        raise ScientificIdentityError(
            f"scientific surface root {root} has no {SURFACE_JSON_ROOT}/ directory"
        )
    found: list[str] = []
    for path in directory.rglob("*.json"):
        if SURFACE_EXCLUDED_DIRECTORIES & set(path.parts):
            continue
        _assert_inside_root(root, path)
        found.append(path.relative_to(root).as_posix())
    return found


def discover_scientific_surface(root: Path | None = None) -> tuple[ScientificSurfaceEntry, ...]:
    """Every file of the surface, in a deterministic order.

    Absence is fatal on purpose.  A required component that is simply missing
    must stop the system from computing any identity at all; tolerating it would
    turn "delete the file that implements the guard" into a way of passing.
    """

    source_root = root or resolve_surface_root()
    relative_paths = list(_discovered_python_sources(source_root))
    for required in SURFACE_REQUIRED_FILES:
        path = source_root / required
        if not path.is_file():
            raise ScientificIdentityError(
                f"scientific surface component {required!r} is missing from {source_root}"
            )
        _assert_inside_root(source_root, path)
        relative_paths.append(required)
    relative_paths.extend(_discovered_json_configs(source_root))
    return tuple(
        ScientificSurfaceEntry(relative_path=relative, canonicalizer=_canonicalizer_for(relative))
        for relative in sorted(set(relative_paths))
    )


# PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_BEGIN

# --- canonicalization -------------------------------------------------------
#
# An explicit list of the fields hashed for each AST node type, rather than
# "every field except the ignored ones".  The difference is not cosmetic: a
# deny-list silently absorbs whatever a future interpreter adds, so the identity
# would change under a new Python without anybody deciding that it should.  With
# an allow-list, an unknown node type or a missing field is a refusal.
#
# The lists below are exactly the fields ``ast`` exposes for these nodes under
# both 3.11 and 3.13, minus location metadata (``lineno`` and friends) and minus
# the type-only fields ``type_comment``, ``type_ignores`` and ``type_params``.
# ``type_params`` is the one that matters: it exists only from 3.12, so hashing
# it would make the digest depend on the interpreter and break the invariant
# that the code half is the same under every supported runtime.

_CANONICAL_AST_FIELDS: dict[str, tuple[str, ...]] = {
    "Add": (),
    "And": (),
    "AnnAssign": ("target", "annotation", "value", "simple"),
    "Assert": ("test", "msg"),
    "Assign": ("targets", "value"),
    "AsyncFor": ("target", "iter", "body", "orelse"),
    "AsyncFunctionDef": ("name", "args", "body", "decorator_list", "returns"),
    "AsyncWith": ("items", "body"),
    "Attribute": ("value", "attr", "ctx"),
    "AugAssign": ("target", "op", "value"),
    "Await": ("value",),
    "BinOp": ("left", "op", "right"),
    "BitAnd": (),
    "BitOr": (),
    "BitXor": (),
    "BoolOp": ("op", "values"),
    "Break": (),
    "Call": ("func", "args", "keywords"),
    "ClassDef": ("name", "bases", "keywords", "body", "decorator_list"),
    "Compare": ("left", "ops", "comparators"),
    "Constant": ("value", "kind"),
    "Continue": (),
    "Del": (),
    "Delete": ("targets",),
    "Dict": ("keys", "values"),
    "DictComp": ("key", "value", "generators"),
    "Div": (),
    "Eq": (),
    "ExceptHandler": ("type", "name", "body"),
    "Expr": ("value",),
    "FloorDiv": (),
    "For": ("target", "iter", "body", "orelse"),
    "FormattedValue": ("value", "conversion", "format_spec"),
    "FunctionDef": ("name", "args", "body", "decorator_list", "returns"),
    "GeneratorExp": ("elt", "generators"),
    "Global": ("names",),
    "Gt": (),
    "GtE": (),
    "If": ("test", "body", "orelse"),
    "IfExp": ("test", "body", "orelse"),
    "Import": ("names",),
    "ImportFrom": ("module", "names", "level"),
    "In": (),
    "Invert": (),
    "Is": (),
    "IsNot": (),
    "JoinedStr": ("values",),
    "LShift": (),
    "Lambda": ("args", "body"),
    "List": ("elts", "ctx"),
    "ListComp": ("elt", "generators"),
    "Load": (),
    "Lt": (),
    "LtE": (),
    "MatMult": (),
    "Mod": (),
    "Module": ("body",),
    "Mult": (),
    "Name": ("id", "ctx"),
    "NamedExpr": ("target", "value"),
    "Nonlocal": ("names",),
    "Not": (),
    "NotEq": (),
    "NotIn": (),
    "Or": (),
    "Pass": (),
    "Pow": (),
    "RShift": (),
    "Raise": ("exc", "cause"),
    "Return": ("value",),
    "Set": ("elts",),
    "SetComp": ("elt", "generators"),
    "Slice": ("lower", "upper", "step"),
    "Starred": ("value", "ctx"),
    "Store": (),
    "Sub": (),
    "Subscript": ("value", "slice", "ctx"),
    "Try": ("body", "handlers", "orelse", "finalbody"),
    "TryStar": ("body", "handlers", "orelse", "finalbody"),
    "Tuple": ("elts", "ctx"),
    "UAdd": (),
    "USub": (),
    "UnaryOp": ("op", "operand"),
    "While": ("test", "body", "orelse"),
    "With": ("items", "body"),
    "Yield": ("value",),
    "YieldFrom": ("value",),
    "alias": ("name", "asname"),
    "arg": ("arg", "annotation"),
    "arguments": (
        "posonlyargs",
        "args",
        "vararg",
        "kwonlyargs",
        "kw_defaults",
        "kwarg",
        "defaults",
    ),
    "comprehension": ("target", "iter", "ifs", "is_async"),
    "keyword": ("arg", "value"),
    "withitem": ("context_expr", "optional_vars"),
}

_SQL_PREFIXES = ("SELECT ", "WITH ", "INSERT ", "UPDATE ", "DELETE ")


def _normalize_sql_whitespace_v1(value: str) -> str:
    """Collapse layout whitespace while preserving quoted SQL contents."""

    source = value.strip()
    output: list[str] = []
    pending_space = False
    quote: str | None = None
    dollar_quote: str | None = None
    index = 0
    while index < len(source):
        if dollar_quote is not None:
            if source.startswith(dollar_quote, index):
                output.append(dollar_quote)
                index += len(dollar_quote)
                dollar_quote = None
            else:
                output.append(source[index])
                index += 1
            continue

        character = source[index]
        if quote is not None:
            output.append(character)
            index += 1
            if character == quote:
                if index < len(source) and source[index] == quote:
                    output.append(source[index])
                    index += 1
                else:
                    quote = None
            continue

        if character.isspace():
            pending_space = bool(output)
            index += 1
            continue
        if pending_space:
            output.append(" ")
            pending_space = False
        if character in ("'", '"'):
            quote = character
            output.append(character)
            index += 1
            continue
        if character == "$":
            tag_end = source.find("$", index + 1)
            if tag_end >= 0:
                candidate = source[index : tag_end + 1]
                tag_body = candidate[1:-1]
                if not tag_body or tag_body.replace("_", "a").isalnum():
                    dollar_quote = candidate
                    output.append(candidate)
                    index = tag_end + 1
                    continue
        output.append(character)
        index += 1
    return "".join(output)


def canonical_sql_source_v1(source: str) -> str:
    """Preserve SQL/comment semantics while normalizing platform newlines."""

    return source.replace("\r\n", "\n").replace("\r", "\n").strip()


def canonical_text_source_v1(source: str) -> str:
    """Normalize platform newlines for files hashed as text.

    ``pyproject.toml``, ``requirements.lock`` and the versioned JSON catalogs
    are hashed as text on purpose.  Parsing them would mean deciding which
    formatting is meaningless, and for a dependency pin or a routing row there
    is no such thing.
    """

    return source.replace("\r\n", "\n").replace("\r", "\n").strip()


def _canonical_constant(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        if any(stripped.upper().startswith(prefix) for prefix in _SQL_PREFIXES):
            # SQL formatting is not scientific semantics.  Collapse it while
            # retaining whitespace inside quoted values and identifiers.
            return {"string": _normalize_sql_whitespace_v1(stripped)}
        return {"string": value}
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("scientific implementation source contains non-finite float")
        return {"float": value.hex()}
    if isinstance(value, complex):
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if value is Ellipsis:
        return {"ellipsis": True}
    raise TypeError(f"unsupported AST constant: {type(value).__name__}")


def _canonical_ast_value(value: object) -> object:
    if isinstance(value, ast.Constant):
        return {
            "node": "Constant",
            "fields": [
                ["value", _canonical_constant(value.value)],
                ["kind", value.kind],
            ],
        }
    if isinstance(value, ast.AST):
        node_type = type(value).__name__
        allowed = _CANONICAL_AST_FIELDS.get(node_type)
        if allowed is None:
            raise ScientificIdentityError(
                f"AST node {node_type!r} is not in the canonical field list; the "
                "identity must state what it hashes instead of absorbing it"
            )
        fields: list[list[object]] = []
        for field_name in allowed:
            if not hasattr(value, field_name):
                raise ScientificIdentityError(
                    f"AST node {node_type!r} has no field {field_name!r} on this "
                    "interpreter; the canonical field list and the runtime disagree"
                )
            fields.append([field_name, _canonical_ast_value(getattr(value, field_name))])
        return {"node": node_type, "fields": fields}
    if isinstance(value, list):
        return [_canonical_ast_value(item) for item in value]
    if isinstance(value, tuple):
        return {"tuple": [_canonical_ast_value(item) for item in value]}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _canonical_constant(value)
    raise TypeError(f"unsupported AST field: {type(value).__name__}")


def _canonical_ast_json(tree: ast.AST) -> str:
    return json.dumps(
        _canonical_ast_value(tree),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_python_ast(source: str) -> str:
    """Canonicalize Python semantics independently of harmless formatting."""

    return _canonical_ast_json(ast.parse(textwrap.dedent(source)))


def canonical_python_module_v2(source: str) -> str:
    """Canonicalize a complete Python file.

    The whole module is parsed, so imports, module constants, class bodies,
    helper functions, entrypoints and anything added later are all inside the
    payload by construction.  There is nothing to enumerate and therefore
    nothing to forget: coverage is the file.

    Docstrings are part of the payload.  Comments, blank lines, indentation
    width and source positions are not.
    """

    return _canonical_ast_json(ast.parse(source))


# --- computing the two halves ----------------------------------------------


def _canonical_payload(source: str, entry: ScientificSurfaceEntry) -> str:
    if entry.canonicalizer == CANONICALIZER_PYTHON_MODULE:
        return canonical_python_module_v2(source)
    if entry.canonicalizer == CANONICALIZER_SQL:
        return canonical_sql_source_v1(source)
    if entry.canonicalizer == CANONICALIZER_TEXT:
        return canonical_text_source_v1(source)
    raise ScientificIdentityError(
        f"unsupported canonicalizer {entry.canonicalizer!r} for {entry.relative_path!r}"
    )


# Canonicalizing forty-odd modules costs about a second, and the identity is
# validated on the hot path of every authoritative evaluation.  The cache is
# keyed by the **content hash** of the file, never by its mtime or size: a
# mutator who edits a component and restores its timestamp would defeat an mtime
# key, and this guard exists precisely against a mutator with write access.
# Re-reading and hashing every component still happens on every call, so a file
# that changes is recanonicalized; what is reused is only the parse of bytes
# already seen.
_COMPONENT_DIGEST_CACHE: dict[tuple[str, str], str] = {}


def _component_digest(root: Path, entry: ScientificSurfaceEntry) -> str:
    path = root / entry.relative_path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ScientificIdentityError(
            f"scientific surface component {entry.relative_path!r} cannot be read: {exc}"
        ) from exc
    key = (entry.relative_path, hashlib.sha256(raw).hexdigest())
    cached = _COMPONENT_DIGEST_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScientificIdentityError(
            f"scientific surface component {entry.relative_path!r} is not UTF-8: {exc}"
        ) from exc
    canonical = _canonical_payload(source, entry)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _COMPONENT_DIGEST_CACHE[key] = digest
    return digest


def compute_scientific_implementation_identity(
    *,
    root: Path | None = None,
    identity_version: int = SCIENTIFIC_IDENTITY_VERSION_V1,
) -> dict[str, Any]:
    """Compute, without trusting the registry, one deterministic identity."""

    if identity_version != SCIENTIFIC_IDENTITY_VERSION_V1:
        raise ValueError(f"unsupported scientific identity version: {identity_version}")
    source_root = root or resolve_surface_root()

    component_records: list[dict[str, str]] = []
    for entry in discover_scientific_surface(source_root):
        component_records.append(
            {
                "name": entry.name,
                "source": entry.relative_path,
                "canonicalizer": entry.canonicalizer,
                "digest": _component_digest(source_root, entry),
            }
        )

    payload = {
        "identity_version": identity_version,
        "canonicalizer": SCIENTIFIC_IDENTITY_CANONICALIZER,
        "components": component_records,
    }
    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return {
        **payload,
        "digest": hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest(),
    }


# --- the registry -----------------------------------------------------------


def identity_registry_path(root: Path | None = None) -> Path:
    return (root or resolve_surface_root()) / IDENTITY_REGISTRY_RELATIVE_PATH


def load_identity_registry(root: Path | None = None) -> dict[str, Any]:
    """Read the declarative registry.  Every failure is a refusal.

    The registry is not read through the surface and is not part of it: a file
    that declares what the surface must be cannot also be one of the things it
    declares.  Commit 3.3 anchors it from outside the tree; until then a mutator
    who can write the tree can write this file, which is precisely why M-02
    remains an escape.
    """

    path = identity_registry_path(root)
    if not path.is_file():
        raise ScientificIdentityError(
            f"scientific identity registry {IDENTITY_REGISTRY_RELATIVE_PATH!r} is "
            f"missing from {path.parent.parent}"
        )
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScientificIdentityError(
            f"scientific identity registry is unreadable: {exc}"
        ) from exc
    if not isinstance(body, dict):
        raise ScientificIdentityError("scientific identity registry must be an object")
    if body.get("schema_version") != IDENTITY_REGISTRY_SCHEMA_VERSION:
        raise ScientificIdentityError(
            "scientific identity registry schema_version is not "
            f"{IDENTITY_REGISTRY_SCHEMA_VERSION}: {body.get('schema_version')!r}"
        )
    for key, expected_type in (
        ("code_digest", str),
        ("authorized_environment_digests", list),
        ("surface_manifest", list),
        ("supported_interpreters", list),
    ):
        if not isinstance(body.get(key), expected_type):
            raise ScientificIdentityError(
                f"scientific identity registry field {key!r} is missing or malformed"
            )
    if not body["authorized_environment_digests"]:
        raise ScientificIdentityError(
            "scientific identity registry authorizes no environment profile, so no "
            "deployment could ever validate"
        )
    return body


def _require_registered_code_identity(
    implementation: dict[str, Any], registry: dict[str, Any]
) -> None:
    registered = registry["code_digest"]
    if implementation["digest"] == registered:
        return
    # The manifest exists so that a divergence names the component instead of
    # only reporting that something, somewhere, moved.
    declared = {
        str(item.get("source")): str(item.get("digest"))
        for item in registry["surface_manifest"]
        if isinstance(item, dict)
    }
    observed = {item["source"]: item["digest"] for item in implementation["components"]}
    added = sorted(set(observed) - set(declared))
    removed = sorted(set(declared) - set(observed))
    changed = sorted(
        source
        for source in set(declared) & set(observed)
        if declared[source] != observed[source]
    )
    detail = "; ".join(
        part
        for part in (
            f"added: {', '.join(added)}" if added else "",
            f"removed: {', '.join(removed)}" if removed else "",
            f"changed: {', '.join(changed)}" if changed else "",
        )
        if part
    )
    raise ScientificIdentityError(
        "runtime confirmatory scientific implementation does not match its "
        f"registered identity: expected {registered}, computed "
        f"{implementation['digest']}"
        + (f" ({detail})" if detail else "")
    )


def _require_authorized_environment(
    contract: dict[str, Any], registry: dict[str, Any]
) -> None:
    authorized = {
        str(item.get("digest"))
        for item in registry["authorized_environment_digests"]
        if isinstance(item, dict)
    }
    if contract["digest"] not in authorized:
        # Worded exactly like the producer-side gate in
        # app.signal_runtime_contract: one refusal, one phrase, so a caller
        # matching on it cannot pass one path and miss the other.
        raise ScientificIdentityError(
            "runtime scientific configuration is not an authorized environment "
            f"profile: resolved {contract['digest']}, which is none of the "
            f"{len(authorized)} enumerated in the identity registry"
        )


def _require_presented_matches(presented: object, runtime: dict[str, Any]) -> None:
    if not isinstance(presented, dict):
        raise ValueError("presented scientific identity must be an object")
    unknown = sorted(set(presented) - set(runtime))
    if unknown:
        raise ValueError(
            f"presented scientific identity carries unknown halves: {', '.join(unknown)}"
        )
    for half, value in presented.items():
        if value != runtime[half]:
            raise ValueError(
                f"frozen scientific identity does not match runtime semantics: {half}"
            )


def validate_scientific_identity(presented: object = None) -> dict[str, Any]:
    """The single entry point.  Both halves, or nothing.

    Every failure below is a refusal to operate, never a warning: an identity
    that cannot be computed is not an identity that matches.  ``presented`` is
    optional so that a caller with nothing frozen can still ask whether *this*
    tree, in *this* environment, is one the registry authorizes.
    """

    registry = load_identity_registry()
    implementation = compute_scientific_implementation_identity()
    _require_registered_code_identity(implementation, registry)

    # Imported here rather than at module scope: the contract module reads the
    # resolved configuration, and the identity module must stay importable by
    # tooling that only wants to hash sources.
    from app.signal_runtime_contract import compute_scientific_runtime_contract

    contract = compute_scientific_runtime_contract()
    _require_authorized_environment(contract, registry)

    runtime = {
        "scientific_implementation": implementation,
        "scientific_runtime_contract": contract,
    }
    if presented is not None:
        _require_presented_matches(presented, runtime)
    return runtime


def scientific_implementation_identity(
    identity_version: int = SCIENTIFIC_IDENTITY_VERSION_V1,
) -> dict[str, Any]:
    """Return the identity only when both halves match the registry."""

    if identity_version != SCIENTIFIC_IDENTITY_VERSION_V1:
        raise ValueError(f"unsupported scientific identity version: {identity_version}")
    return validate_scientific_identity()["scientific_implementation"]


def validate_scientific_implementation_identity(stored: object) -> dict[str, Any]:
    """Fail closed when a frozen identity differs from runtime semantics.

    Kept for the callers that froze an implementation half before the combined
    entry point existed.  It **delegates**: leaving it able to accept on its own
    would rebuild the hole M-08 demonstrated, where the code half validated
    while the environment half was never looked at.
    """

    if not isinstance(stored, dict):
        raise ValueError("scientific_implementation must be an object")
    try:
        raw_identity_version = stored["identity_version"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("scientific_implementation identity_version is invalid") from exc
    if isinstance(raw_identity_version, bool) or not isinstance(
        raw_identity_version, int
    ):
        raise ValueError("scientific_implementation identity_version must be an integer")
    if raw_identity_version != SCIENTIFIC_IDENTITY_VERSION_V1:
        raise ValueError(
            f"unsupported scientific identity version: {raw_identity_version}"
        )
    validated = validate_scientific_identity({"scientific_implementation": stored})
    return validated["scientific_implementation"]


# PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_END
