"""Declarative catalog of identity mutations.  Data only -- no behaviour.

Every entry states *what* is mutated and *what effect the mutation is required
to have*.  How a step is carried out lives in :mod:`harness`; how a runtime
escape is reproduced lives in :mod:`probe`.  Keeping the three apart is what
makes the catalog reviewable without reading an executor.

The observed class is **not** written by hand except for the three mutations
that carry ``mandated_class``: those were demonstrated by the independent audit
and a harness that classifies them as ``GUARD`` is a harness that is measuring
the wrong thing.  For every other entry the first run over the baseline
revision decides, and the answer is frozen in ``known_escapes.json``.

Vocabulary
----------

Moving the digest is necessary and **not sufficient**.  A digest that moves
without anyone refusing to operate is not a control, so every material mutation
demands rejection as well as movement.  ``MUST_MOVE`` and ``MUST_REJECT`` are
therefore gone; the four effects below replace them.

Rejection is decided by the *combined* validator -- the single entry point that
validates both halves at once.  Until that entry point exists, the acceptance
half of every effect is unprovable and the row fails closed; ``closes_with``
records which addendum item is expected to close it.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- required effects -------------------------------------------------------

MUST_MOVE_AND_REJECT = "MUST_MOVE_AND_REJECT"
MUST_REJECT_ONLY = "MUST_REJECT_ONLY"
MUST_NOT_MOVE_AND_ACCEPT = "MUST_NOT_MOVE_AND_ACCEPT"
MUST_NOT_MOVE_CODE_MUST_MOVE_ENV = "MUST_NOT_MOVE_CODE_MUST_MOVE_ENV"

REQUIRED_EFFECTS = frozenset(
    {
        MUST_MOVE_AND_REJECT,
        MUST_REJECT_ONLY,
        MUST_NOT_MOVE_AND_ACCEPT,
        MUST_NOT_MOVE_CODE_MUST_MOVE_ENV,
    }
)

# --- observed classes -------------------------------------------------------

GUARD = "GUARD"
ESCAPE = "ESCAPE"

# Retained as a *forbidden* value, not as an outcome.  The catalog declares no
# skip condition and the harness never emits one, so ``skipped`` in the
# declaration is empty by construction; keeping the constant is what lets the
# suite assert that instead of assuming it.
SKIPPED = "SKIPPED"

# --- additional requirements, ANDed with the required effect ----------------

REQUIRE_FORGED_REJECTED = "forged_object_rejected"

# --- addendum items a declared escape can be closed by ----------------------
#
# ``closes_with`` ties an escape to the thing that must close it, so a closure
# claim in commit 3 is checkable against the row it claims to close.

CLOSES_A = "A"  # surface and environment
CLOSES_B = "B"  # canonicalization by an explicit list of fields
CLOSES_C1 = "C.1"  # verification of sys.modules
CLOSES_C2 = "C.2"  # hash of the bound object
CLOSES_D = "D"  # registry anchor

CLOSES_WITH_VALUES = frozenset({CLOSES_A, CLOSES_B, CLOSES_C1, CLOSES_C2, CLOSES_D})

# --- the anchor layout the anchor mutations interrogate ---------------------
#
# Neither artefact exists at the baseline revision, which is the whole point:
# M-28 and M-29 ask what happens when the thing that anchors the registry from
# outside the tree is removed or swapped, and on ``c60e2ee6`` the answer is that
# there is nothing to remove.  Commit 3 must place its anchor at one of these
# paths, or extend this tuple as part of the same change.

ANCHOR_ARTIFACT_PATHS: tuple[str, ...] = (
    "identity/anchor.json",
    "identity/anchor.sig",
)
ANCHOR_PUBLIC_KEY_PATHS: tuple[str, ...] = ("identity/anchor_public_key.pem",)


# --- mutation steps ---------------------------------------------------------
#
# Each step is an inert record.  ``harness.apply_step`` is the only place that
# knows how to carry one out, and it fails closed on every anchor it cannot
# resolve exactly once.


@dataclass(frozen=True, slots=True)
class TextEdit:
    """Replace an exact, unique needle in a file.

    The uniqueness requirement is deliberate.  Rewriting the *first textual
    occurrence* of an expression is precisely the methodological error that
    made three earlier closures look green while the executed code stayed
    untouched, so an ambiguous anchor is a failure, never a guess.
    """

    path: str
    needle: str
    replacement: str


@dataclass(frozen=True, slots=True)
class AstEdit:
    """Rewrite one span of a top-level Python symbol, located by AST.

    ``part`` is ``"body"`` (every statement after the docstring) or
    ``"docstring"`` (the docstring literal itself).  The span is resolved from
    the parsed tree and rewritten at that node's byte offsets, so a duplicated
    expression elsewhere in the file cannot pass for the real one.
    """

    path: str
    symbol: str
    part: str
    replacement: str


@dataclass(frozen=True, slots=True)
class AstReorder:
    """Swap the source blocks of two top-level Python symbols."""

    path: str
    first: str
    second: str


@dataclass(frozen=True, slots=True)
class WhitespaceEdit:
    """Insert blank lines and trailing spaces without touching the AST."""

    path: str
    symbol: str
    blank_lines: int
    trailing_spaces: int


@dataclass(frozen=True, slots=True)
class CreateFile:
    """Add a file that does not exist in the target tree."""

    path: str
    content: str


@dataclass(frozen=True, slots=True)
class DeleteFile:
    """Remove a tracked file from the target tree."""

    path: str


@dataclass(frozen=True, slots=True)
class DeleteTree:
    """Remove a whole directory from the target tree."""

    path: str


@dataclass(frozen=True, slots=True)
class ProductionLaunchProtocol:
    """Measure under the launch protocol the services actually use.

    The harness runs the probe with ``PYTHONSAFEPATH=1`` and an explicit
    ``PYTHONPATH`` so that resolution order is stated rather than inherited.
    Production does neither: the systemd units run ``python -m app.<mod>`` with
    ``WorkingDirectory=/opt/coinalyze``.  If the two disagree about the identity
    or the verdict, the instrument is auditing a system that is not the one that
    ships, and that is worse news than anything else in the catalog.
    """

    reason: str = "the harness launch protocol must not change what is measured"


@dataclass(frozen=True, slots=True)
class SymlinkOutOfTree:
    """Replace a tracked file with a symlink to a byte-identical copy outside.

    Identical bytes on purpose: differing content would only re-test the
    content mutation.  What this isolates is whether a component may be read
    through a link that leaves the surface at all.
    """

    path: str


@dataclass(frozen=True, slots=True)
class ReregisterIdentityDigest:
    """Recompute the identity in the mutated tree and register the new value.

    This is the forger's move: change the code, then move the goalpost.  It can
    only be carried out after the code edit, so the harness computes the digest
    in a throw-away subprocess between the two steps.

    The forger modelled here is competent, so *where* the registry lives is not
    part of the mutation.  When the tree carries a registration script, the step
    runs it and the whole registry -- digest, per-component manifest, authorized
    profiles -- is regenerated exactly as a maintainer would.  Rewriting one
    literal and leaving a manifest that contradicts it would test whether the
    forger is careless, which is not a property of the system under audit.  When
    the tree has no such script, the step falls back to replacing ``needle`` in
    ``path``, which is how the registry was expressed before it moved out of the
    code.
    """

    path: str
    needle: str
    script: str = "scripts/register_identity.py"


@dataclass(frozen=True, slots=True)
class PythonPathShadow:
    """Put an altered copy of one ``app.*`` module ahead of the real one.

    The shadow directory carries its own ``app/__init__.py`` which re-exports
    the real package directory on ``__path__``, so exactly one module resolves
    from outside the tree and every other one still comes from it.  A wholesale
    copy of ``app/`` would test a different thing -- that the entire package
    moved -- and would drag the identity computation's own root along with it.
    """

    module: str
    relative_path: str
    symbol: str
    replacement: str


@dataclass(frozen=True, slots=True)
class RemoveAnchorArtifact:
    """Delete whichever declared anchor artefact the tree carries.

    A tree with no anchor artefact at all is not an anchor that survived the
    deletion: it is a tree that never had one, and the probe reports it as
    ``anchor_mechanism_absent`` rather than as a resolved anchor.
    """

    paths: tuple[str, ...] = ANCHOR_ARTIFACT_PATHS


@dataclass(frozen=True, slots=True)
class ReanchorWithOwnKey:
    """Swap the versioned public key and re-anchor the registry with it.

    Two edits, one meaning: an anchor whose key the mutator may replace is an
    anchor the mutator controls, so it cannot decide anything about the tree it
    is supposed to certify.
    """

    key_paths: tuple[str, ...] = ANCHOR_PUBLIC_KEY_PATHS
    artifact_paths: tuple[str, ...] = ANCHOR_ARTIFACT_PATHS


@dataclass(frozen=True, slots=True)
class EnvChange:
    """Set environment variables for the probe subprocess."""

    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class RuntimePatch:
    """Run one of :mod:`probe`'s in-process escapes before measuring."""

    name: str


@dataclass(frozen=True, slots=True)
class AlternateInterpreter:
    """Measure the same tree under a different supported Python."""

    excluded_current: bool = True


# --- one catalog entry ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Mutation:
    id: str
    summary: str
    mechanism: str
    expected_effect: str
    steps: tuple[object, ...] = ()
    also_requires: tuple[str, ...] = ()
    mandated_class: str | None = None
    requires_anchor: bool = False
    requires_probe_flag: str = ""
    closes_with: str = ""
    closes_note: str = ""
    anchor_rationale: str = ""


# --- shared mutation payloads ----------------------------------------------

_WS = "app/ws_collector.py"

_VALID_TRADE_BODY = """\
    try:
        price = float(price_raw)  # type: ignore[arg-type]
        qty = float(qty_raw)  # type: ignore[arg-type]
        ts_ms = int(ts_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(price) or not math.isfinite(qty) or price <= 0 or qty <= 0:
        return None
    if price > 10_000_000 or qty > 100_000_000 or price * qty > MAX_NOTIONAL_USD:
        return None
    now_ms = int(time.time() * 1000)
    if ts_ms < now_ms - 900_000 or ts_ms > now_ms:
        return None
    return price, qty, ts_ms"""

_SPOT_PAIRS_BODY = """\
    return tuple("ETHUSDT" for _ in symbols)"""

_FORGED_CATALOG = """\
{
  "version": 1,
  "mode": "extend",
  "symbols": [
    {
      "symbol": "ETHUSDT_PERP.A",
      "base_asset": "ETH",
      "futures_pair": "BNBUSDT",
      "bybit_oi_symbol": "ETHUSDT.6",
      "spot_pair": "ETHUSDT",
      "spot_history_symbol": "ETHUSD.A",
      "whale_threshold_usd": 1000000.0,
      "large_trade_threshold_usd": 400000.0
    }
  ]
}
"""

# M-07 creates the versioned catalog the baseline revision does not carry.  It
# has to differ from DEFAULT_MARKET_CATALOG in a projected routing field, or
# resolving it would be indistinguishable from not resolving it at all.
_VERSIONED_CATALOG = """\
{
  "version": 1,
  "mode": "extend",
  "symbols": [
    {
      "symbol": "SOLUSDT_PERP.A",
      "base_asset": "SOL",
      "futures_pair": "SOLUSDC",
      "bybit_oi_symbol": "SOLUSDT.6",
      "spot_pair": "SOLUSDC",
      "spot_history_symbol": "SOLUSD.A",
      "whale_threshold_usd": 200000.0,
      "large_trade_threshold_usd": 150000.0
    }
  ]
}
"""

_NEW_PARTICIPANT = '''\
"""A participant nobody enumerated, on the raw write path."""

from app import scalp_collector


def divert_realtime_buckets(symbol: str) -> None:
    """Drop whatever the collector observed for one internal key."""

    scalp_collector.TRADE_STORE.rt_buckets.clear()
    scalp_collector.TRADE_STORE.buckets.pop(symbol, None)
'''

# M-31: neutralization installed from the tree *before* the identity module is
# executed, by wrapping the loader rather than by reassigning an attribute
# afterwards.  Anything that captured the validator at import time captured the
# replacement, which is what makes it a different question from M-01.
_SITECUSTOMIZE = '''\
"""Neutralize the identity validators before the module exists in memory."""

import importlib.util
import os
import sys

_TARGET = "app.signal_scientific_identity"


class _PreImportNeutralizer:
    """A meta path finder that patches the module as it is executed."""

    def find_spec(self, fullname, path=None, target=None):
        if fullname != _TARGET:
            return None
        sys.meta_path.remove(self)
        try:
            spec = importlib.util.find_spec(fullname)
        finally:
            sys.meta_path.insert(0, self)
        if spec is None or spec.loader is None:
            return None
        original_exec_module = spec.loader.exec_module

        def exec_module(module, _original=original_exec_module):
            _original(module)
            module.validate_scientific_implementation_identity = lambda stored: stored
            if hasattr(module, "validate_scientific_identity"):
                module.validate_scientific_identity = lambda *args, **kwargs: True

        spec.loader.exec_module = exec_module
        return spec


sys.meta_path.insert(0, _PreImportNeutralizer())
os.environ["IDENTITY_MUTATION_SITECUSTOMIZE_ACTIVE"] = "1"
'''


# --- the catalog ------------------------------------------------------------

CATALOG: tuple[Mutation, ...] = (
    Mutation(
        id="M-01",
        summary=(
            "reassign validate_scientific_implementation_identity to "
            "`lambda stored: stored` at runtime"
        ),
        mechanism="runtime_patch",
        expected_effect=MUST_REJECT_ONLY,
        also_requires=(REQUIRE_FORGED_REJECTED,),
        mandated_class=ESCAPE,
        steps=(RuntimePatch(name="neutralize_identity_validator"),),
        closes_with=CLOSES_C2,
        closes_note=(
            "the validator that runs must be hashed as a bound object, not "
            "resolved by name at call time"
        ),
        anchor_rationale=(
            "The probe resolves the validator through the module attribute at "
            "call time, so the reassignment is on the executed path, not on a "
            "stale reference captured at import."
        ),
    ),
    Mutation(
        id="M-02",
        summary=(
            "mutate app/ws_collector.py and rewrite the registered digest to "
            "the new value"
        ),
        mechanism="file_edit x2",
        expected_effect=MUST_REJECT_ONLY,
        mandated_class=ESCAPE,
        requires_anchor=True,
        steps=(
            AstEdit(
                path=_WS,
                symbol="spot_pairs",
                part="body",
                replacement=_SPOT_PAIRS_BODY,
            ),
            ReregisterIdentityDigest(
                path="app/signal_scientific_identity.py",
                needle=(
                    "c7bf8e5b4f5280ff767e4e07e573b4c9a51e18011ebcaf8bc4b26a04c4b49c04"
                ),
            ),
        ),
        closes_with=CLOSES_D,
        closes_note=(
            "a tree whose code and registry were rewritten together is "
            "self-consistent; only an anchor the mutator does not control can "
            "tell it from a legitimate new version"
        ),
        anchor_rationale=(
            "spot_pairs() is the routing conversion every Binance spot "
            "subscription is built from; the registry literal is the only "
            "thing the runtime compares the recomputed digest against."
        ),
    ),
    Mutation(
        id="M-03",
        summary="alter the docstring of a material symbol in app/ws_collector.py",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        # The mandate is gone because the escape is: commit 3.1 makes docstrings
        # material and this row closes.  What replaced it is stronger than a
        # mandate, not weaker -- the suite names M-03 among the rows that must
        # be observed GUARD, so the harness cannot pass by failing to measure
        # it, and the frozen evidence over c60e2ee6 still records the ESCAPE the
        # independent audit demonstrated.
        steps=(
            AstEdit(
                path=_WS,
                symbol="deliver_spot_minute",
                part="docstring",
                replacement=(
                    '"""Buckets may also be persisted by any other path; this one '
                    'is advisory."""'
                ),
            ),
        ),
        closes_with=CLOSES_B,
        closes_note=(
            "the canonicalizer drops docstrings wholesale; an explicit field "
            "list is what decides that a documented contract is material"
        ),
        anchor_rationale=(
            "deliver_spot_minute is the only path from minute buckets to raw "
            "persistence, so its documented contract is material even though "
            "the canonicalizer drops docstrings."
        ),
    ),
    Mutation(
        id="M-04",
        summary="alter the body of a material function in app/ws_collector.py",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            AstEdit(
                path=_WS,
                symbol="valid_trade",
                part="body",
                replacement=_VALID_TRADE_BODY,
            ),
        ),
        closes_with=CLOSES_A,
        closes_note="the digest already moves; nothing refuses to operate on it",
        anchor_rationale=(
            "valid_trade decides which trades reach the buckets at all; the "
            "staleness window moves from 120s to 900s."
        ),
    ),
    Mutation(
        id="M-05",
        summary="reassign __code__ of a material symbol to another function's",
        mechanism="runtime_patch",
        expected_effect=MUST_REJECT_ONLY,
        steps=(RuntimePatch(name="swap_code_object"),),
        closes_with=CLOSES_C2,
        closes_note=(
            "the file is untouched, so only a hash of the object actually bound "
            "at runtime can see the transplant"
        ),
        anchor_rationale=(
            "Same target as M-02 (spot_pairs) but performed in memory, so the "
            "two differ only in whether the escape touches the filesystem."
        ),
    ),
    Mutation(
        id="M-06",
        summary=(
            "register a synthetic app.<mod> in sys.modules whose __file__ is "
            "outside the surface"
        ),
        mechanism="runtime_patch",
        expected_effect=MUST_REJECT_ONLY,
        steps=(RuntimePatch(name="inject_synthetic_module"),),
        closes_with=CLOSES_C1,
        closes_note="sys.modules must be checked against the hashed surface",
        anchor_rationale=(
            "app.ws_collector is a whole-module component, so a synthetic "
            "stand-in for it is the sharpest form of the escape."
        ),
    ),
    Mutation(
        id="M-07",
        summary="create the versioned catalog config/market_symbols.json",
        mechanism="file_create",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            CreateFile(
                path="config/market_symbols.json",
                content=_VERSIONED_CATALOG,
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "the presence and content of the versioned routing catalog is part "
            "of the environment half of the surface"
        ),
        anchor_rationale=(
            "resolve_market_catalog_path() returns the versioned path as soon "
            "as config/market_symbols.json exists, so creating it is what makes "
            "load_market_catalog() read it.  The row it adds overrides "
            "SOLUSDT_PERP.A's futures_pair and spot_pair, both projected "
            "routing fields, so the substitution is result-material rather than "
            "decorative.  A file_edit could never have an anchor here: the "
            "baseline revision does not carry the file at all."
        ),
    ),
    Mutation(
        id="M-08",
        summary=(
            "point MARKET_SYMBOL_CATALOG_FILE at a catalog with different "
            "content"
        ),
        mechanism="env + file_create",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            CreateFile(
                path="config/mutation_matrix_catalog.json",
                content=_FORGED_CATALOG,
            ),
            EnvChange(
                values=(
                    (
                        "MARKET_SYMBOL_CATALOG_FILE",
                        "config/mutation_matrix_catalog.json",
                    ),
                )
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "the environment digest moves and no combined validation looks at "
            "it, so the runtime resolution is recorded and never enforced"
        ),
        anchor_rationale=(
            "futures_pair for ETHUSDT_PERP.A is one of the four projected "
            "routing fields, so the substitution is result-material by "
            "construction."
        ),
    ),
    Mutation(
        id="M-09",
        summary="change COLLECTOR_SHARD_INDEX / COLLECTOR_SHARD_COUNT",
        mechanism="env",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            EnvChange(
                values=(
                    ("COLLECTOR_SHARD_INDEX", "1"),
                    ("COLLECTOR_SHARD_COUNT", "3"),
                )
            ),
        ),
        closes_with=CLOSES_A,
        closes_note="the environment half must be part of what is validated",
    ),
    Mutation(
        id="M-10",
        summary="change HARD_DATA_RETENTION_DAYS",
        mechanism="env",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(EnvChange(values=(("HARD_DATA_RETENTION_DAYS", "21"),)),),
        closes_with=CLOSES_A,
        closes_note="the environment half must be part of what is validated",
    ),
    Mutation(
        id="M-11",
        summary="change SCALP_MINUTE_RETENTION_HOURS",
        mechanism="env",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(EnvChange(values=(("SCALP_MINUTE_RETENTION_HOURS", "48"),)),),
        closes_with=CLOSES_A,
        closes_note="the environment half must be part of what is validated",
    ),
    Mutation(
        id="M-12",
        summary="add app/nuevo_participante.py with material content",
        mechanism="file_create",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            CreateFile(
                path="app/nuevo_participante.py",
                content=_NEW_PARTICIPANT,
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "the surface enumerates components; a module nobody enumerated is "
            "outside it by construction"
        ),
        anchor_rationale=(
            "The new module reaches TRADE_STORE, which is the store the raw "
            "collectors write through."
        ),
    ),
    Mutation(
        id="M-13",
        summary=(
            "replace an app/ file with a symlink to a copy outside the tree"
        ),
        mechanism="symlink",
        expected_effect=MUST_REJECT_ONLY,
        steps=(SymlinkOutOfTree(path=_WS),),
        closes_with=CLOSES_A,
        closes_note=(
            "the surface must be defined over resolved paths, not over names "
            "that may leave it"
        ),
        anchor_rationale=(
            "app/ws_collector.py is a whole-module component and the copy is "
            "byte-identical, so the only thing under test is whether a "
            "component may be read from outside the surface."
        ),
    ),
    Mutation(
        id="M-14",
        summary="mutate sql/schema.sql",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            TextEdit(
                path="sql/schema.sql",
                needle="evidence_coverage_pct BETWEEN 0 AND 100",
                replacement="evidence_coverage_pct BETWEEN -1 AND 100",
            ),
        ),
        closes_with=CLOSES_A,
        closes_note="the digest already moves; nothing refuses to operate on it",
        anchor_rationale=(
            "Anchored inside PR4_SIGNAL_OBSERVATION_LEDGER, a declared "
            "scientific boundary, so the measurement tests the guard where the "
            "identity claims to have one.  The needle is unique in the file; "
            "the obvious alternative -- the confidence CHECK -- occurs twice "
            "and was rejected by the uniqueness gate rather than guessed at.  "
            "Regions of sql/schema.sql outside the eight declared boundaries "
            "are not covered; that is the enumeration limit already recorded "
            "in HANDOFF_IA.md 8.1, not something this entry measures."
        ),
    ),
    Mutation(
        id="M-15",
        summary="mutate pyproject.toml (a dependency version) and the lock file",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            TextEdit(
                path="pyproject.toml",
                needle='"httpx==0.28.1",',
                replacement='"httpx==0.28.0",',
            ),
            TextEdit(
                path="requirements.lock",
                needle="httpx==0.28.1",
                replacement="httpx==0.28.0",
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "the resolved dependency set is part of the environment half and is "
            "projected nowhere today"
        ),
    ),
    Mutation(
        id="M-16",
        summary="run the same tree under 3.11 and under 3.12/3.13",
        mechanism="interpreter",
        expected_effect=MUST_NOT_MOVE_CODE_MUST_MOVE_ENV,
        steps=(AlternateInterpreter(),),
        closes_with=CLOSES_A,
        closes_note=(
            "the interpreter is an environment component and the runtime "
            "contract projects four routing fields per symbol and nothing else"
        ),
        anchor_rationale=(
            "No skip: an interpreter the runner does not carry is a runner that "
            "was not provisioned, which fails the mutation closed with "
            "alternative_interpreter_unavailable instead of hiding it."
        ),
    ),
    Mutation(
        id="M-17",
        summary="vary PYTHONHASHSEED (0 -> 12345)",
        mechanism="env",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(EnvChange(values=(("PYTHONHASHSEED", "12345"),)),),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-18",
        summary="two consecutive runs with no mutation",
        mechanism="none",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-19",
        summary="reorder two top-level functions in a material file",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(AstReorder(path=_WS, first="spot_pairs", second="binance_url"),),
        closes_with=CLOSES_A,
        closes_note="the digest already moves; nothing refuses to operate on it",
        anchor_rationale=(
            "Both are top level and neither is called at definition time, so "
            "the swap is behaviour-preserving at runtime and isolates whether "
            "declaration order is material to the digest."
        ),
    ),
    Mutation(
        id="M-20",
        summary="alter a # comment (not a docstring)",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(
            TextEdit(
                path=_WS,
                needle=(
                    "# Transport tuning, not routing: which venue is read is "
                    "result-material and"
                ),
                replacement=(
                    "# Transport tuning, and also routing: this comment claims "
                    "the opposite and"
                ),
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-21",
        summary="alter spacing and line breaks without altering the AST",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(
            WhitespaceEdit(
                path=_WS,
                symbol="valid_trade",
                blank_lines=3,
                trailing_spaces=4,
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-22",
        summary="edit a file under tests/",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(
            TextEdit(
                path="tests/test_ws_collector.py",
                needle="def test_valid_trade_rejects_bad_values(monkeypatch):",
                replacement="def test_valid_trade_rejects_bad_values_renamed(monkeypatch):",
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-23",
        summary="edit README.md",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(
            TextEdit(
                path="README.md",
                needle="# Coinalyze Operator Dashboard v1.5.0",
                replacement="# Coinalyze Operator Dashboard v1.5.0 (mutated)",
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
    ),
    Mutation(
        id="M-24",
        summary="mutate config/market_symbols.example.json",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            TextEdit(
                path="config/market_symbols.example.json",
                needle='"futures_pair": "XRPUSDT"',
                replacement='"futures_pair": "XRPUSDC"',
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "the versioned config directory is part of the environment half; "
            "whether an example is material is a boundary the surface must "
            "state, not one it may leave undecided"
        ),
        anchor_rationale=(
            "The example is the documented shape of the versioned catalog and "
            "the only routing configuration the repository carries at the "
            "baseline revision.  It is mutated in a projected routing field so "
            "that, if anything read it, the environment digest would move."
        ),
    ),
    Mutation(
        id="M-25",
        summary="mutate DEFAULT_MARKET_CATALOG in app/config.py",
        mechanism="file_edit",
        expected_effect=MUST_MOVE_AND_REJECT,
        steps=(
            TextEdit(
                path="app/config.py",
                needle='"BTCUSDT_PERP.A", "BTC", "BTCUSDT", "BTCUSDT.6", "BTCUSDT", "BTCUSD.A",',
                replacement=(
                    '"BTCUSDT_PERP.A", "BTC", "BTCUSDC", "BTCUSDT.6", "BTCUSDC", "BTCUSD.A",'
                ),
            ),
        ),
        closes_with=CLOSES_A,
        closes_note="the digest already moves; nothing refuses to operate on it",
        anchor_rationale=(
            "The needle is the full BTC row of the default catalog and is "
            "unique in the file.  futures_pair and spot_pair are two of the "
            "four projected routing fields, so the default routing every "
            "deployment without a versioned catalog resolves is what moves."
        ),
    ),
    Mutation(
        id="M-26",
        summary="delete a material app/ file from the tree",
        mechanism="file_delete",
        expected_effect=MUST_REJECT_ONLY,
        steps=(DeleteFile(path="app/signal_replay.py"),),
        anchor_rationale=(
            "app/signal_replay.py is the signal_replay_integrity component and "
            "is imported by neither app.signal_scientific_identity nor "
            "app.signal_runtime_contract, so the probe still starts and reaches "
            "the evaluation instead of dying at import.  Every material file is "
            "a hashed component, so its absence necessarily stops the identity "
            "from being computed at all; per section 3 that propagated "
            "exception is a valid rejection and is recorded as one."
        ),
    ),
    Mutation(
        id="M-27",
        summary=(
            "PYTHONPATH pointing at a directory with an altered copy of an "
            "app.* module that resolves before the real one"
        ),
        mechanism="env + file_create",
        expected_effect=MUST_REJECT_ONLY,
        requires_probe_flag="pythonpath_shadow_active",
        steps=(
            PythonPathShadow(
                module="app.ws_collector",
                relative_path=_WS,
                symbol="spot_pairs",
                replacement=_SPOT_PAIRS_BODY,
            ),
        ),
        closes_with=CLOSES_C1,
        closes_note=(
            "the file on disk is untouched, so only checking where the loaded "
            "module actually came from can see it"
        ),
        anchor_rationale=(
            "Same symbol as M-02 and M-05, reached by a third route: the file "
            "in the tree keeps its original bytes and the module that executes "
            "is a different file entirely.  The probe imports the shadowed "
            "module and reports whether it resolved outside the tree, so an "
            "inert shadow fails the mutation instead of being reported as a "
            "finding."
        ),
    ),
    Mutation(
        id="M-28",
        summary="delete the anchor artefact from the tree",
        mechanism="file_delete",
        expected_effect=MUST_REJECT_ONLY,
        requires_anchor=True,
        steps=(RemoveAnchorArtifact(),),
        closes_with=CLOSES_D,
        closes_note=(
            "an anchor that can be deleted from the tree it certifies is not "
            "an anchor; its absence must stop the system"
        ),
        anchor_rationale=(
            "The baseline revision carries no anchor artefact at any declared "
            "path, so the mutation reports anchor_mechanism_absent rather than "
            "pretending to have removed something."
        ),
    ),
    Mutation(
        id="M-29",
        summary=(
            "replace the versioned public key with one of the mutator's own and "
            "re-anchor the registry with it"
        ),
        mechanism="file_edit x2",
        expected_effect=MUST_REJECT_ONLY,
        requires_anchor=True,
        steps=(ReanchorWithOwnKey(),),
        closes_with=CLOSES_D,
        closes_note=(
            "the trusted key must arrive from outside the tree; a versioned key "
            "the mutator may replace anchors nothing"
        ),
        anchor_rationale=(
            "The baseline revision carries neither a versioned public key nor "
            "an anchored registry record, so the mutation reports "
            "anchor_mechanism_absent instead of a resolved anchor."
        ),
    ),
    Mutation(
        id="M-30",
        summary="mutate .github/workflows/ci.yml",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        steps=(
            TextEdit(
                path=".github/workflows/ci.yml",
                needle="pytest -q",
                replacement="pytest -q --deselect tests/test_ws_collector.py || true",
            ),
        ),
        closes_with=CLOSES_A,
        closes_note=(
            "negative control: the digest is already stable, and acceptance "
            "cannot be demonstrated until the combined entry point exists"
        ),
        anchor_rationale=(
            "A deliberate boundary decision, declared rather than discovered: "
            "the integrity of the workflow is repository governance -- branch "
            "protection and CODEOWNERS -- and not scientific identity.  The "
            "anchor of section 4.2 arrives from outside the tree precisely so "
            "that a mutator who can rewrite the workflow still cannot rewrite "
            "what the workflow is checked against."
        ),
    ),
    Mutation(
        id="M-31",
        summary=(
            "inject sitecustomize.py into the tree, neutralizing the validator "
            "before the identity module is imported"
        ),
        mechanism="file_create",
        expected_effect=MUST_REJECT_ONLY,
        requires_probe_flag="sitecustomize_active",
        steps=(CreateFile(path="sitecustomize.py", content=_SITECUSTOMIZE),),
        closes_with=CLOSES_C2,
        closes_note=(
            "the neutralization is installed before any reference exists, so "
            "resolving the validator by name cannot help; the object that runs "
            "must itself be hashed"
        ),
        anchor_rationale=(
            "Distinct from M-01: M-01 reassigns an attribute after the module "
            "is in memory, so a validator captured at import would survive it.  "
            "This one wraps the loader, so the module is already neutralized "
            "the first time anybody sees it.  The probe reports whether "
            "sitecustomize actually ran, so an inert file fails the mutation "
            "instead of being reported as a finding."
        ),
    ),
    Mutation(
        id="M-32",
        summary="delete the config/ directory and measure which root the catalog resolves against",
        mechanism="file_delete",
        expected_effect=MUST_REJECT_ONLY,
        steps=(DeleteTree(path="config"),),
        closes_with=CLOSES_A,
        closes_note=(
            "the root the raw inputs are selected from is part of the environment "
            "half; resolving it against an absolute path elsewhere must stop the "
            "process, not proceed quietly"
        ),
        anchor_rationale=(
            "Written against the finding that resolve_project_root() fell back to "
            "/opt/coinalyze whenever <root>/config was absent, at import time and "
            "without saying so.  A source tree without config/ is a broken "
            "deployment, and the mutation measures which root it resolves.  On the "
            "baseline revision the fallback is silent and nothing refuses; the "
            "measurement there depends on the auditing machine not carrying a "
            "populated /opt/coinalyze, which is recorded in the report."
        ),
    ),
    Mutation(
        id="M-33",
        summary="run the probe under the production launch protocol, with no mutation at all",
        mechanism="launch_protocol",
        expected_effect=MUST_NOT_MOVE_AND_ACCEPT,
        requires_probe_flag="production_launch_protocol",
        steps=(ProductionLaunchProtocol(),),
        closes_with=CLOSES_A,
        closes_note=(
            "control of the instrument itself: it closes when the combined "
            "validator exists, exactly like the other negative controls"
        ),
        anchor_rationale=(
            "The one row that audits the auditor.  Every other row is measured "
            "under PYTHONSAFEPATH=1 with an explicit PYTHONPATH, which is what "
            "makes M-27 and M-31 able to bite; production runs neither.  If the "
            "identity or the verdict differed between the two, every other row "
            "would be a statement about a system nobody deploys."
        ),
    ),
)

CATALOG_BY_ID: dict[str, Mutation] = {mutation.id: mutation for mutation in CATALOG}

MANDATED_ESCAPES: tuple[str, ...] = tuple(
    mutation.id for mutation in CATALOG if mutation.mandated_class == ESCAPE
)

ANCHOR_DEPENDENT_IDS: tuple[str, ...] = tuple(
    mutation.id for mutation in CATALOG if mutation.requires_anchor
)

# Kept out of ``Mutation`` on purpose: the boundary decisions are a property of
# the catalog as a whole, and commit 3 documents them from here.
MATERIALITY_BOUNDARY_IDS: tuple[str, ...] = ("M-19", "M-20", "M-21", "M-30")
