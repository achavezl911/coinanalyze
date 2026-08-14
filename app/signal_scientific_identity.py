"""Deterministic identity for versioned confirmatory scientific mechanics.

The identity is deliberately narrower than a Git commit and stronger than a
human-maintained version label.  It hashes canonical ASTs from explicit source
regions that implement the scientific result.  Comments, docstrings, source
locations, indentation width, and other formatting do not affect the digest;
executable changes do.

The registered mapping is append-only by policy.  A legitimate future change
must add a new identity version and a new prospective walk-forward spec.  It
must never replace the digest registered for an existing identity version.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCIENTIFIC_IDENTITY_VERSION_V1 = 1
SCIENTIFIC_IDENTITY_CANONICALIZER = "scientific_source_canonicalization_v1"


@dataclass(frozen=True, slots=True)
class ScientificSourceComponent:
    name: str
    relative_path: str
    begin_marker: str
    end_marker: str
    language: str = "python"


# Exact scientific surface for PR27's corrected endpoint.  The marker names
# are part of the identity payload.  Keep old regions in place when adding a
# future implementation version so an already-frozen manifest remains
# verifiable without relying on a historical Git checkout.
SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS = (
    ScientificSourceComponent(
        name="scientific_identity_mechanics",
        relative_path="app/signal_scientific_identity.py",
        begin_marker="PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_END",
    ),
    ScientificSourceComponent(
        name="scientific_runtime_contract_mechanics",
        relative_path="app/signal_runtime_contract.py",
        begin_marker="PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_RUNTIME_CONTRACT_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_summary_decision_kernel",
        relative_path="app/scalp_logic.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_SUMMARY_KERNEL_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_SUMMARY_KERNEL_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_summary_oi_helpers",
        relative_path="app/setups.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_OI_HELPERS_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_OI_HELPERS_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_context_session_boundary",
        relative_path="app/metrics.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_SESSION_BOUNDARY_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_SESSION_BOUNDARY_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_context_cutoff",
        relative_path="app/scalp_logic.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_CONTEXT_CUTOFF_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_CONTEXT_CUTOFF_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_observation_generation",
        relative_path="app/signal_ledger.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_OBSERVATION_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_OBSERVATION_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_replay_integrity",
        relative_path="app/signal_replay.py",
        begin_marker="PR27_SCIENTIFIC_SIGNAL_REPLAY_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_SIGNAL_REPLAY_V1_END",
    ),
    ScientificSourceComponent(
        name="visibility_transaction_boundary",
        relative_path="app/db.py",
        begin_marker="PR27_SCIENTIFIC_VISIBILITY_TRANSACTION_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_VISIBILITY_TRANSACTION_V1_END",
    ),
    ScientificSourceComponent(
        name="visibility_certificate_production",
        relative_path="app/signal_visibility.py",
        begin_marker="PR27_SCIENTIFIC_VISIBILITY_CERTIFICATION_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_VISIBILITY_CERTIFICATION_V1_END",
    ),
    ScientificSourceComponent(
        name="outcome_data_gap_blocking",
        relative_path="app/data_gaps.py",
        begin_marker="PR27_SCIENTIFIC_OUTCOME_GAP_BLOCKING_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_OUTCOME_GAP_BLOCKING_V1_END",
    ),
    ScientificSourceComponent(
        name="knowledge_time_projection_and_grid",
        relative_path="app/signal_walk_forward.py",
        begin_marker="PR27_SCIENTIFIC_KNOWLEDGE_TIME_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_KNOWLEDGE_TIME_V1_END",
    ),
    ScientificSourceComponent(
        name="outcome_materialization_semantics",
        relative_path="app/signal_outcomes.py",
        begin_marker="PR27_SCIENTIFIC_OUTCOME_MATERIALIZATION_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_OUTCOME_MATERIALIZATION_V1_END",
    ),
    ScientificSourceComponent(
        name="execution_snapshot_semantics",
        relative_path="app/signal_execution.py",
        begin_marker="PR27_SCIENTIFIC_EXECUTION_SNAPSHOT_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_EXECUTION_SNAPSHOT_V1_END",
    ),
    ScientificSourceComponent(
        name="corrected_endpoint_and_paired_inference",
        relative_path="app/signal_confirmatory_v2.py",
        begin_marker="PR27_SCIENTIFIC_CONFIRMATORY_V2_BEGIN",
        end_marker="PR27_SCIENTIFIC_CONFIRMATORY_V2_END",
    ),
    ScientificSourceComponent(
        name="confirmatory_v4_fetch_coverage_and_persistence",
        relative_path="app/signal_walk_forward.py",
        begin_marker="PR27_SCIENTIFIC_CONFIRMATORY_V4_IO_BEGIN",
        end_marker="PR27_SCIENTIFIC_CONFIRMATORY_V4_IO_END",
    ),
    ScientificSourceComponent(
        name="authoritative_transaction_and_serialization",
        relative_path="app/signal_walk_forward.py",
        begin_marker="PR27_SCIENTIFIC_AUTHORITATIVE_EVALUATION_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_AUTHORITATIVE_EVALUATION_V1_END",
    ),
    ScientificSourceComponent(
        name="signal_observation_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR4_SIGNAL_OBSERVATION_LEDGER_BEGIN",
        end_marker="PR4_SIGNAL_OBSERVATION_LEDGER_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="signal_outcome_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR5_SIGNAL_OUTCOMES_BEGIN",
        end_marker="PR5_SIGNAL_OUTCOMES_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="signal_replay_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR6_SIGNAL_REPLAY_BEGIN",
        end_marker="PR6_SIGNAL_REPLAY_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="signal_execution_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR10_SIGNAL_EXECUTION_BEGIN",
        end_marker="PR10_SIGNAL_EXECUTION_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="outcome_data_gap_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR27_SCIENTIFIC_OUTCOME_DATA_GAP_V1_BEGIN",
        end_marker="PR27_SCIENTIFIC_OUTCOME_DATA_GAP_V1_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="research_bundle_visibility_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY_BEGIN",
        end_marker="PR25_SIGNAL_RESEARCH_BUNDLE_VISIBILITY_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="outcome_final_visibility_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY_BEGIN",
        end_marker="PR25_SIGNAL_OUTCOME_FINAL_VISIBILITY_END",
        language="sql",
    ),
    ScientificSourceComponent(
        name="authoritative_result_database_boundary",
        relative_path="sql/schema.sql",
        begin_marker="PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT_BEGIN",
        end_marker="PR27_SIGNAL_WALK_FORWARD_CONFIRMATORY_RESULT_END",
        language="sql",
    ),
)


# Filled only after the exact components above have been implemented and the
# deterministic digest has been independently reproduced by tests.  Never
# mutate an existing key: add a new identity version instead.
REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS = {
    SCIENTIFIC_IDENTITY_VERSION_V1: (
        "f696a268ee2e3154a596fecd5339086eee6e56cdaf1d918469ee9236fc4fec11"
    ),
}

# PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_BEGIN

_IGNORED_AST_FIELDS = frozenset(
    {
        # Location/formatting metadata.
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
        # Type-only metadata changed across supported Python runtimes and has
        # no effect on these runtime scientific calculations.
        "type_comment",
        "type_ignores",
        "type_params",
    }
)
_SQL_PREFIXES = ("SELECT ", "WITH ", "INSERT ", "UPDATE ", "DELETE ")


class _RemoveDocstrings(ast.NodeTransformer):
    """Remove non-executable documentation before canonical serialization."""

    @staticmethod
    def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            return body[1:]
        return body

    def visit_Module(self, node: ast.Module) -> ast.AST:
        self.generic_visit(node)
        node.body = self._without_docstring(node.body)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._without_docstring(node.body)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._without_docstring(node.body)
        return node

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        self.generic_visit(node)
        node.body = self._without_docstring(node.body)
        return node


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
        return {"node": "Constant", "value": _canonical_constant(value.value)}
    if isinstance(value, ast.AST):
        fields: list[list[object]] = []
        for field_name, field_value in ast.iter_fields(value):
            if field_name in _IGNORED_AST_FIELDS:
                continue
            fields.append([field_name, _canonical_ast_value(field_value)])
        return {"node": type(value).__name__, "fields": fields}
    if isinstance(value, list):
        return [_canonical_ast_value(item) for item in value]
    if isinstance(value, tuple):
        return {"tuple": [_canonical_ast_value(item) for item in value]}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return _canonical_constant(value)
    raise TypeError(f"unsupported AST field: {type(value).__name__}")


def canonical_python_ast(source: str) -> str:
    """Canonicalize Python semantics independently of harmless formatting."""

    tree = ast.parse(textwrap.dedent(source))
    normalized = _RemoveDocstrings().visit(tree)
    ast.fix_missing_locations(normalized)
    return json.dumps(
        _canonical_ast_value(normalized),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _extract_component_source(root: Path, component: ScientificSourceComponent) -> str:
    path = root / component.relative_path
    source = path.read_text(encoding="utf-8")
    comment_prefix = "#" if component.language == "python" else "--"
    begin = f"{comment_prefix} {component.begin_marker}"
    end = f"{comment_prefix} {component.end_marker}"
    if source.count(begin) != 1 or source.count(end) != 1:
        raise RuntimeError(
            f"scientific component {component.name!r} requires exactly one "
            f"{begin!r} and {end!r} marker"
        )
    start_index = source.index(begin) + len(begin)
    end_index = source.index(end, start_index)
    if end_index <= start_index:
        raise RuntimeError(f"scientific component {component.name!r} has invalid markers")
    return source[start_index:end_index]


def compute_scientific_implementation_identity(
    *,
    root: Path | None = None,
    identity_version: int = SCIENTIFIC_IDENTITY_VERSION_V1,
) -> dict[str, Any]:
    """Compute, without trusting the registry, one deterministic identity."""

    if identity_version != SCIENTIFIC_IDENTITY_VERSION_V1:
        raise ValueError(f"unsupported scientific identity version: {identity_version}")
    source_root = root or Path(__file__).resolve().parents[1]

    component_records: list[dict[str, str]] = []
    for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS:
        component_source = _extract_component_source(source_root, component)
        if component.language == "python":
            canonical = canonical_python_ast(component_source)
        elif component.language == "sql":
            canonical = canonical_sql_source_v1(component_source)
        else:
            raise ValueError(
                f"unsupported scientific component language: {component.language}"
            )
        component_records.append(
            {
                "name": component.name,
                "source": f"{component.relative_path}#{component.begin_marker}",
                "canonicalizer": (
                    "canonical_python_ast_v1"
                    if component.language == "python"
                    else "canonical_sql_source_v1"
                ),
                "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
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


def scientific_implementation_identity(
    identity_version: int = SCIENTIFIC_IDENTITY_VERSION_V1,
) -> dict[str, Any]:
    """Return the identity only when source matches its immutable registry."""

    identity = compute_scientific_implementation_identity(
        identity_version=identity_version
    )
    registered = REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS.get(identity_version)
    if registered is None:
        raise RuntimeError(
            f"scientific identity version {identity_version} is not registered"
        )
    if identity["digest"] != registered:
        raise RuntimeError(
            "runtime confirmatory scientific implementation does not match its "
            f"registered identity: expected {registered}, computed {identity['digest']}"
        )
    return identity


def validate_scientific_implementation_identity(stored: object) -> dict[str, Any]:
    """Fail closed when a frozen identity differs from runtime semantics."""

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
    identity_version = raw_identity_version
    runtime = scientific_implementation_identity(identity_version)
    if stored != runtime:
        raise ValueError(
            "frozen scientific implementation identity does not match runtime semantics"
        )
    return runtime


# PR27_SCIENTIFIC_IDENTITY_MECHANICS_V1_END
