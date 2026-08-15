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
import sys
import textwrap
import types
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


# Canonicalizing forty-odd modules costs about three quarters of a second, and
# the identity is validated on the hot path of every authoritative evaluation.
# The cache is keyed by the **content hash** of the file, never by its mtime or
# size: a mutator who edits a component and restores its timestamp would defeat
# an mtime key, and this guard exists precisely against a mutator with write
# access.  Re-reading and hashing every component still happens on every call,
# so a file that changes is recanonicalized; what is reused is only the parse of
# bytes already seen.
#
# It is **bounded**, which an unbounded dict keyed by content hash is not: in a
# long-lived collector every edit to a component would add an entry that nothing
# ever removes.  The bound is the surface itself -- one live entry per component
# path -- so the cache can never hold more than the tree it describes.
#
# What the bound does *not* buy is authenticity.  Any in-process cache consulted
# by the authoritative path can be poisoned by an attacker who already executes
# code in that process, and the measurement in the report says the authoritative
# path cannot afford to run without one: 744 ms per uncached computation against
# a 990 ms ceiling for the three an authoritative evaluation performs.  That is
# M-34, and it is declared RESIDUAL rather than pretended closed.
_CACHE_ENTRIES_PER_COMPONENT = 2


class _BoundedContentCache:
    """A content-addressed cache that cannot outgrow the surface it describes.

    Kept as an object rather than a module-level ``dict`` so that the mapping is
    reached through one place with one insertion policy.  It is not a security
    boundary and does not pretend to be one -- see M-34.
    """

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}

    def get(self, path: str, content_sha: str, kind: str) -> Any | None:
        return self._entries.get(path, {}).get(f"{kind}:{content_sha}")

    def put(self, path: str, content_sha: str, kind: str, value: Any) -> None:
        slot = self._entries.setdefault(path, {})
        slot[f"{kind}:{content_sha}"] = value
        # One component keeps at most the current bytes and the ones it just
        # replaced; anything older is a generation nobody will ask about again.
        while len(slot) > _CACHE_ENTRIES_PER_COMPONENT:
            slot.pop(next(iter(slot)))

    def retain(self, paths: frozenset[str]) -> None:
        """Drop every component that is no longer part of the surface."""

        for path in [name for name in self._entries if name not in paths]:
            del self._entries[path]

    def clear(self) -> None:
        self._entries.clear()

    def __len__(self) -> int:
        return sum(len(slot) for slot in self._entries.values())


_COMPONENT_CACHE = _BoundedContentCache()

_CACHE_KIND_COMPONENT = "component"
_CACHE_KIND_BINDINGS = "bindings"


def _component_digest(root: Path, entry: ScientificSurfaceEntry) -> str:
    path = root / entry.relative_path
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ScientificIdentityError(
            f"scientific surface component {entry.relative_path!r} cannot be read: {exc}"
        ) from exc
    content_sha = hashlib.sha256(raw).hexdigest()
    cached = _COMPONENT_CACHE.get(entry.relative_path, content_sha, _CACHE_KIND_COMPONENT)
    if cached is not None:
        return str(cached)
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScientificIdentityError(
            f"scientific surface component {entry.relative_path!r} is not UTF-8: {exc}"
        ) from exc
    canonical = _canonical_payload(source, entry)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    _COMPONENT_CACHE.put(entry.relative_path, content_sha, _CACHE_KIND_COMPONENT, digest)
    return digest


# --- post-import verification ------------------------------------------------
#
# The AST on disk does not describe what runs.  Two things can diverge from it
# after import and neither touches a byte of the surface: the module a name
# resolves to (C.1) and the object a symbol is bound to (C.2).
#
# Both are computed **at evaluation time**, never at import.  A fingerprint
# taken while importing cannot see a reassignment performed afterwards, which is
# exactly M-01, and a provenance check performed at import cannot see a module
# swapped into ``sys.modules`` later.
#
# Both are computed against the root the process actually imports from --
# ``resolve_surface_root()`` -- and not against the ``root`` argument used to
# hash components.  The question they answer is "where did *this process* get
# its code", which is a property of the process and not of whichever tree a
# caller asked to have hashed.
#
# What enters the digest is the list of **anomalies**, not the membership.  The
# set of loaded ``app.*`` modules differs legitimately between the API, the
# collectors and a script, so hashing it would give every process a different
# identity and no registry could hold one value.  The anomaly list is empty
# whenever the process is honest, so it is constant across deployments -- and
# the moment anything diverges it becomes non-empty, which moves the identity
# *and* makes it stop matching the registry.  Divergence therefore both moves
# the identity and refuses to operate, which is what section 2.1 requires.

SURFACE_PACKAGE = "app"

PROVENANCE_NO_FILE = "no_file"
PROVENANCE_OUTSIDE_SURFACE = "outside_surface"
PROVENANCE_PATH_MISMATCH = "path_mismatch"

BINDING_MISSING = "missing"
BINDING_NOT_A_FUNCTION = "not_a_function"
BINDING_CODE_MISMATCH = "code_mismatch"
BINDING_SOURCE_UNAVAILABLE = "source_unavailable"

# How deep ``__wrapped__`` is followed for a symbol the source shows decorated.
_MAX_WRAPPER_DEPTH = 8


def _loaded_surface_modules() -> tuple[tuple[str, types.ModuleType], ...]:
    """Every ``app.*`` module currently in ``sys.modules``, name-ordered.

    Snapshotted before iterating: importing anything while walking
    ``sys.modules`` would mutate it underneath us.
    """

    snapshot = list(sys.modules.items())
    return tuple(
        sorted(
            (
                (name, module)
                for name, module in snapshot
                if module is not None
                and (name == SURFACE_PACKAGE or name.startswith(f"{SURFACE_PACKAGE}."))
            ),
            key=lambda item: item[0],
        )
    )


def _candidate_relative_paths(module_name: str) -> tuple[str, ...]:
    joined = "/".join(module_name.split("."))
    return (f"{joined}.py", f"{joined}/__init__.py")


def verify_loaded_module_provenance(root: Path | None = None) -> tuple[list[str], ...]:
    """C.1 -- where every loaded ``app.*`` module was really loaded from.

    A module with no ``__file__``, one whose file resolves outside the root, and
    one whose file is not the file its own name denotes are all anomalies.
    There are **no exemptions by name**: a module that would like to be excused
    is exactly the module an attacker would name.

    The anomaly carries the module name and the reason, never the offending
    path.  A path would be machine-specific, and the digest this feeds must be
    reproducible on the auditor's machine as well as on the one that wrote it.
    """

    source_root = Path(os.path.realpath(root or resolve_surface_root()))
    anomalies: list[list[str]] = []
    for name, module in _loaded_surface_modules():
        origin = getattr(module, "__file__", None)
        if not origin:
            anomalies.append([name, PROVENANCE_NO_FILE])
            continue
        resolved = Path(os.path.realpath(origin))
        if not resolved.is_relative_to(source_root):
            anomalies.append([name, PROVENANCE_OUTSIDE_SURFACE])
            continue
        if resolved.relative_to(source_root).as_posix() not in _candidate_relative_paths(
            name
        ):
            anomalies.append([name, PROVENANCE_PATH_MISMATCH])
    return tuple(sorted(anomalies))


def _canonical_code_const(value: object) -> Any:
    """A constant of a code object, canonicalized by structure rather than repr.

    ``repr`` is not usable here and the reason is a real defect this check hit
    before it was written this way: the peephole optimizer turns ``x in {"a",
    "b"}`` into a ``frozenset`` constant, and two frozensets carrying the same
    elements iterate in an order that depends on their build history and on the
    process's hash seed.  Fingerprinting their ``repr`` made C.2 report a
    different innocent function on every run.  Sets are therefore compared as
    sorted element canonicalizations, and every other type carries a tag so that
    ``1``, ``True`` and ``1.0`` cannot collide.
    """

    if isinstance(value, types.CodeType):
        return {"code": _code_fingerprint(value)}
    if isinstance(value, tuple):
        return {"tuple": [_canonical_code_const(item) for item in value]}
    if isinstance(value, frozenset | set):
        return {
            "set": sorted(
                json.dumps(
                    _canonical_code_const(item),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                for item in value
            )
        }
    if value is None:
        return {"none": True}
    if value is Ellipsis:
        return {"ellipsis": True}
    if isinstance(value, bool):
        return {"bool": value}
    if isinstance(value, int):
        return {"int": str(value)}
    if isinstance(value, float):
        return {"float": value.hex() if math.isfinite(value) else repr(value)}
    if isinstance(value, complex):
        return {"complex": [repr(value.real), repr(value.imag)]}
    if isinstance(value, str):
        return {"str": value}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    return {"repr": repr(value)}


def _code_fingerprint(code: types.CodeType) -> list[Any]:
    """The parts of a code object that decide what it computes.

    ``co_code``, ``co_consts``, ``co_names`` and ``co_varnames`` -- bytecode,
    literals, the globals it reaches for and its locals.  Nested code objects
    are fingerprinted recursively, so a lambda or a comprehension inside the
    function is inside the fingerprint too.  Positions, filenames and line
    tables are left out: they are the same metadata the canonical AST already
    refuses to hash.
    """

    return [
        {"co_code": code.co_code.hex()},
        {"co_consts": [_canonical_code_const(const) for const in code.co_consts]},
        {"co_names": list(code.co_names)},
        {"co_varnames": list(code.co_varnames)},
    ]


def _symbol_fingerprint(module: str, qualname: str, code: list[Any]) -> str:
    """One fingerprint, built identically for the live side and the source side.

    The module and the qualname are hashed alongside the code so that a function
    transplanted from somewhere else is caught even in the case where it happens
    to compile to the same bytes as the one it replaced.
    """

    payload = json.dumps(
        {"module": module, "qualname": qualname, "code": code},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _bound_object_fingerprint(function: types.FunctionType) -> str:
    return _symbol_fingerprint(
        function.__module__,
        function.__qualname__,
        _code_fingerprint(function.__code__),
    )


def _material_symbols(source: str) -> tuple[tuple[str, bool], ...]:
    """Every addressable function the source defines, and whether it is decorated.

    Derived from the surface, never from a hand-written list: a symbol added to
    a module participates by existing, exactly as a module added to ``app/``
    participates by existing.  Functions nested inside functions are skipped --
    they carry ``<locals>`` in their qualname, are not reachable as attributes
    and cannot be reassigned independently of the function that closes over
    them, whose own fingerprint already contains them.
    """

    def walk(body: list[ast.stmt], prefix: str) -> list[tuple[str, bool]]:
        found: list[tuple[str, bool]] = []
        for node in body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                found.append((f"{prefix}{node.name}", bool(node.decorator_list)))
            elif isinstance(node, ast.ClassDef):
                found.extend(walk(node.body, f"{prefix}{node.name}."))
        return found

    return tuple(sorted(set(walk(ast.parse(source).body, ""))))


def _expected_fingerprints(source: str, filename: str, module: str) -> dict[str, str]:
    """What the surface source compiles to, in *this* interpreter.

    Compiled here rather than recorded in the registry, and that is not an
    implementation detail.  Bytecode differs between 3.11 and 3.13; a registry
    carrying fingerprints from one of them would make the code digest disagree
    with itself under the other, which is the invariant M-16 exists to defend.
    Comparing live objects against source compiled in the same process is the
    only form of this check that is interpreter-independent.
    """

    fingerprints: dict[str, str] = {}
    pending = [compile(source, filename, "exec")]
    while pending:
        code = pending.pop()
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                fingerprints[const.co_qualname] = _symbol_fingerprint(
                    module, const.co_qualname, _code_fingerprint(const)
                )
                pending.append(const)
    return fingerprints


def _resolve_attribute(module: types.ModuleType, qualname: str) -> Any:
    current: Any = module
    for part in qualname.split("."):
        try:
            current = getattr(current, part)
        except AttributeError:
            return None
    return current


def _undescribe(candidate: Any) -> Any:
    """Step through the descriptor protocols that wrap a plain function."""

    if isinstance(candidate, property):
        return candidate.fget
    if isinstance(candidate, staticmethod | classmethod):
        return candidate.__func__
    if isinstance(candidate, types.MethodType):
        # ``getattr(Cls, name)`` on a classmethod hands back a bound method.
        return candidate.__func__
    return candidate


def _unwrap(candidate: Any, decorated: bool) -> types.FunctionType | None:
    """The plain function behind a binding, if the source says one is expected.

    ``__wrapped__`` is followed **only** for symbols the source shows carrying a
    decorator, and for those it is followed *first*.  ``@asynccontextmanager``
    replaces the attribute with a plain function of its own that
    ``functools.wraps`` has given the original's name and module, so stopping at
    "it is already a function" would compare the decorator's body against the
    source and call the difference an attack.

    An *undecorated* symbol gets no such courtesy: following ``__wrapped__``
    there would let a mutator hide a replacement by pointing it back at the
    original, which is the whole trick.  Nothing can make a symbol look
    decorated without editing the decorator list in the source, and that is
    hashed by the canonical AST.
    """

    candidate = _undescribe(candidate)
    if decorated:
        for _ in range(_MAX_WRAPPER_DEPTH):
            unwrapped = getattr(candidate, "__wrapped__", None)
            if unwrapped is None:
                break
            candidate = _undescribe(unwrapped)
    if isinstance(candidate, types.FunctionType):
        return candidate
    return None


def verify_bound_objects(root: Path | None = None) -> tuple[list[str], ...]:
    """C.2 -- what every material symbol of a loaded module is bound to now.

    For each loaded ``app.*`` module the surface source is compiled and each
    addressable function it defines is compared against the object the live
    module actually exposes under that name.  A missing symbol, one bound to
    something that is not a function, and one whose code fingerprint differs
    from what the source compiles to are all anomalies.

    This is what an attribute reassignment, a ``__code__`` transplant and a
    loader wrapped before the module ever existed in memory all have in common:
    the file is untouched and the object is not the one the file describes.
    """

    source_root = Path(os.path.realpath(root or resolve_surface_root()))
    anomalies: list[list[str]] = []
    for name, module in _loaded_surface_modules():
        relative = next(
            (
                candidate
                for candidate in _candidate_relative_paths(name)
                if (source_root / candidate).is_file()
            ),
            None,
        )
        if relative is None:
            # Provenance already reports this module; adding a second anomaly
            # for the same fact would double-count one divergence.
            continue
        raw = (source_root / relative).read_bytes()
        content_sha = hashlib.sha256(raw).hexdigest()
        cached = _COMPONENT_CACHE.get(relative, content_sha, _CACHE_KIND_BINDINGS)
        if cached is None:
            source = raw.decode("utf-8")
            cached = {
                "symbols": _material_symbols(source),
                "expected": _expected_fingerprints(source, relative, name),
            }
            _COMPONENT_CACHE.put(relative, content_sha, _CACHE_KIND_BINDINGS, cached)
        expected: dict[str, str] = cached["expected"]
        for qualname, decorated in cached["symbols"]:
            if qualname not in expected:
                anomalies.append([name, qualname, BINDING_SOURCE_UNAVAILABLE])
                continue
            target = _resolve_attribute(module, qualname)
            bound = _unwrap(target, decorated)
            if bound is None:
                if decorated and target is not None:
                    # A decorator may legitimately replace the binding with an
                    # object that keeps no reference to the compiled function --
                    # a pydantic validator proxy is one.  Those symbols are
                    # outside what C.2 can compare, and saying so is honest;
                    # calling them attacks would make the check unusable.  They
                    # are not thereby unprotected: the decorator list is part of
                    # the canonical AST, so nothing can move a symbol into this
                    # bucket without moving the code digest.
                    continue
                anomalies.append(
                    [
                        name,
                        qualname,
                        BINDING_MISSING if target is None else BINDING_NOT_A_FUNCTION,
                    ]
                )
                continue
            if _bound_object_fingerprint(bound) != expected[qualname]:
                anomalies.append([name, qualname, BINDING_CODE_MISMATCH])
    return tuple(sorted(anomalies))


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
    surface = discover_scientific_surface(source_root)
    for entry in surface:
        component_records.append(
            {
                "name": entry.name,
                "source": entry.relative_path,
                "canonicalizer": entry.canonicalizer,
                "digest": _component_digest(source_root, entry),
            }
        )
    _COMPONENT_CACHE.retain(frozenset(entry.relative_path for entry in surface))

    payload = {
        "identity_version": identity_version,
        "canonicalizer": SCIENTIFIC_IDENTITY_CANONICALIZER,
        "components": component_records,
        # C.1 and C.2.  Empty on an honest process, and part of the payload
        # rather than a check beside it, so that a divergence moves the identity
        # instead of only being reported.
        "module_provenance": [list(item) for item in verify_loaded_module_provenance()],
        "bound_objects": [list(item) for item in verify_bound_objects()],
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


# --- generating the registry -------------------------------------------------
#
# This lives in ``app/`` -- inside the scientific surface -- and not in
# ``scripts/``, which is outside it.  With both the generator and its ``--check``
# in an unhashed script, whoever could edit the script controlled both sides of
# the comparison and the result was self-consistent by construction: the same
# failure mode as M-02, one directory across.  Here, altering what gets
# registered or what ``--check`` compares moves the code digest, so the forgery
# has to survive the very check it is trying to subvert.
#
# ``scripts/register_identity.py`` stays as an entry point that parses two
# arguments and decides nothing.


def build_identity_registry() -> dict[str, Any]:
    """The registry this tree computes, in the shape the runtime validates."""

    from app.signal_runtime_contract import (
        AUTHORIZED_COLLECTOR_SHARD_PROFILES,
        AUTHORIZED_ENVIRONMENT_FIXED,
        AUTHORIZED_INTERPRETERS,
        SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER,
        SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
        enumerate_authorized_environment_profiles,
    )

    identity = compute_scientific_implementation_identity()
    profiles = enumerate_authorized_environment_profiles()
    return {
        "schema_version": IDENTITY_REGISTRY_SCHEMA_VERSION,
        "identity_version": SCIENTIFIC_IDENTITY_VERSION_V1,
        "canonicalizer": SCIENTIFIC_IDENTITY_CANONICALIZER,
        "code_digest": identity["digest"],
        "runtime_contract_version": SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
        "runtime_contract_canonicalizer": SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER,
        "supported_interpreters": [dict(item) for item in AUTHORIZED_INTERPRETERS],
        "environment_profile_axes": {
            "collector_shard": [dict(item) for item in AUTHORIZED_COLLECTOR_SHARD_PROFILES],
            "interpreter": [dict(item) for item in AUTHORIZED_INTERPRETERS],
            "fixed": dict(AUTHORIZED_ENVIRONMENT_FIXED),
        },
        "authorized_environment_digests": list(profiles),
        "surface_manifest": [
            {
                "source": component["source"],
                "canonicalizer": component["canonicalizer"],
                "digest": component["digest"],
            }
            for component in identity["components"]
        ],
    }


def serialize_identity_registry(registry: dict[str, Any]) -> str:
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def write_identity_registry(root: Path | None = None) -> Path:
    """Rewrite the registry from what this tree computes now."""

    path = identity_registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_identity_registry(build_identity_registry()), encoding="utf-8")
    return path


def check_identity_registry(root: Path | None = None) -> tuple[bool, str]:
    """Is the committed registry the one this tree computes?

    Returns ``(ok, message)`` rather than printing or exiting, so that the entry
    point stays free of decisions and the suite can assert on the outcome
    without capturing a subprocess.
    """

    path = identity_registry_path(root)
    if not path.is_file():
        return False, f"{path} does not exist"
    expected = serialize_identity_registry(build_identity_registry())
    if path.read_text(encoding="utf-8") != expected:
        return False, (
            f"{path} is stale: the tree no longer computes the registered "
            "identity.  Run scripts/register_identity.py and review the diff."
        )
    return True, f"{path} matches the tree"


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
