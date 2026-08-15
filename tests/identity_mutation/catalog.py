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
"""

from __future__ import annotations

from dataclasses import dataclass

# --- required effects -------------------------------------------------------

MUST_MOVE = "MUST_MOVE"
MUST_NOT_MOVE = "MUST_NOT_MOVE"
MUST_REJECT = "MUST_REJECT"
MUST_NOT_MOVE_CODE_MUST_MOVE_ENV = "MUST_NOT_MOVE_CODE_MUST_MOVE_ENV"

# --- observed classes -------------------------------------------------------

GUARD = "GUARD"
ESCAPE = "ESCAPE"
SKIPPED = "SKIPPED"

# --- additional requirements, ANDed with the required effect ----------------

REQUIRE_FORGED_REJECTED = "forged_object_rejected"


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
    """

    path: str
    needle: str


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
    skip_if: str | None = None
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

_NEW_PARTICIPANT = '''\
"""A participant nobody enumerated, on the raw write path."""

from app import scalp_collector


def divert_realtime_buckets(symbol: str) -> None:
    """Drop whatever the collector observed for one internal key."""

    scalp_collector.TRADE_STORE.rt_buckets.clear()
    scalp_collector.TRADE_STORE.buckets.pop(symbol, None)
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
        expected_effect=MUST_MOVE,
        also_requires=(REQUIRE_FORGED_REJECTED,),
        mandated_class=ESCAPE,
        steps=(RuntimePatch(name="neutralize_identity_validator"),),
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
        expected_effect=MUST_REJECT,
        mandated_class=ESCAPE,
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
        expected_effect=MUST_MOVE,
        mandated_class=ESCAPE,
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
        expected_effect=MUST_MOVE,
        steps=(
            AstEdit(
                path=_WS,
                symbol="valid_trade",
                part="body",
                replacement=_VALID_TRADE_BODY,
            ),
        ),
        anchor_rationale=(
            "valid_trade decides which trades reach the buckets at all; the "
            "staleness window moves from 120s to 900s."
        ),
    ),
    Mutation(
        id="M-05",
        summary="reassign __code__ of a material symbol to another function's",
        mechanism="runtime_patch",
        expected_effect=MUST_MOVE,
        steps=(RuntimePatch(name="swap_code_object"),),
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
        expected_effect=MUST_REJECT,
        steps=(RuntimePatch(name="inject_synthetic_module"),),
        anchor_rationale=(
            "app.ws_collector is a whole-module component, so a synthetic "
            "stand-in for it is the sharpest form of the escape."
        ),
    ),
    Mutation(
        id="M-07",
        summary="mutate config/market_symbols.json",
        mechanism="file_edit",
        expected_effect=MUST_MOVE,
        steps=(
            TextEdit(
                path="config/market_symbols.json",
                needle='"futures_pair": "ETHUSDT"',
                replacement='"futures_pair": "BNBUSDT"',
            ),
        ),
        anchor_rationale=(
            "The versioned catalog path config/market_symbols.json does not "
            "exist at the baseline revision; the mutation is kept verbatim and "
            "fails closed on the missing anchor rather than being silently "
            "replaced by an approximation."
        ),
    ),
    Mutation(
        id="M-08",
        summary=(
            "point MARKET_SYMBOL_CATALOG_FILE at a catalog with different "
            "content"
        ),
        mechanism="env + file_create",
        expected_effect=MUST_MOVE,
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
        expected_effect=MUST_MOVE,
        steps=(
            EnvChange(
                values=(
                    ("COLLECTOR_SHARD_INDEX", "1"),
                    ("COLLECTOR_SHARD_COUNT", "3"),
                )
            ),
        ),
    ),
    Mutation(
        id="M-10",
        summary="change HARD_DATA_RETENTION_DAYS",
        mechanism="env",
        expected_effect=MUST_MOVE,
        steps=(EnvChange(values=(("HARD_DATA_RETENTION_DAYS", "21"),)),),
    ),
    Mutation(
        id="M-11",
        summary="change SCALP_MINUTE_RETENTION_HOURS",
        mechanism="env",
        expected_effect=MUST_MOVE,
        steps=(EnvChange(values=(("SCALP_MINUTE_RETENTION_HOURS", "48"),)),),
    ),
    Mutation(
        id="M-12",
        summary="add app/nuevo_participante.py with material content",
        mechanism="file_create",
        expected_effect=MUST_MOVE,
        steps=(
            CreateFile(
                path="app/nuevo_participante.py",
                content=_NEW_PARTICIPANT,
            ),
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
        expected_effect=MUST_REJECT,
        steps=(SymlinkOutOfTree(path=_WS),),
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
        expected_effect=MUST_MOVE,
        steps=(
            TextEdit(
                path="sql/schema.sql",
                needle="evidence_coverage_pct BETWEEN 0 AND 100",
                replacement="evidence_coverage_pct BETWEEN -1 AND 100",
            ),
        ),
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
        expected_effect=MUST_MOVE,
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
    ),
    Mutation(
        id="M-16",
        summary="run the same tree under 3.11 and under 3.12/3.13",
        mechanism="interpreter",
        expected_effect=MUST_NOT_MOVE_CODE_MUST_MOVE_ENV,
        steps=(AlternateInterpreter(),),
        skip_if="alternative_interpreter_unavailable",
    ),
    Mutation(
        id="M-17",
        summary="vary PYTHONHASHSEED (0 -> 12345)",
        mechanism="env",
        expected_effect=MUST_NOT_MOVE,
        steps=(EnvChange(values=(("PYTHONHASHSEED", "12345"),)),),
    ),
    Mutation(
        id="M-18",
        summary="two consecutive runs with no mutation",
        mechanism="none",
        expected_effect=MUST_NOT_MOVE,
        steps=(),
    ),
    Mutation(
        id="M-19",
        summary="reorder two top-level functions in a material file",
        mechanism="file_edit",
        expected_effect=MUST_MOVE,
        steps=(AstReorder(path=_WS, first="spot_pairs", second="binance_url"),),
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
        expected_effect=MUST_NOT_MOVE,
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
    ),
    Mutation(
        id="M-21",
        summary="alter spacing and line breaks without altering the AST",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE,
        steps=(
            WhitespaceEdit(
                path=_WS,
                symbol="valid_trade",
                blank_lines=3,
                trailing_spaces=4,
            ),
        ),
    ),
    Mutation(
        id="M-22",
        summary="edit a file under tests/",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE,
        steps=(
            TextEdit(
                path="tests/test_ws_collector.py",
                needle="def test_valid_trade_rejects_bad_values(monkeypatch):",
                replacement="def test_valid_trade_rejects_bad_values_renamed(monkeypatch):",
            ),
        ),
    ),
    Mutation(
        id="M-23",
        summary="edit README.md",
        mechanism="file_edit",
        expected_effect=MUST_NOT_MOVE,
        steps=(
            TextEdit(
                path="README.md",
                needle="# Coinalyze Operator Dashboard v1.5.0",
                replacement="# Coinalyze Operator Dashboard v1.5.0 (mutated)",
            ),
        ),
    ),
)

CATALOG_BY_ID: dict[str, Mutation] = {mutation.id: mutation for mutation in CATALOG}

MANDATED_ESCAPES: tuple[str, ...] = tuple(
    mutation.id for mutation in CATALOG if mutation.mandated_class == ESCAPE
)

# Kept out of ``Mutation`` on purpose: the boundary decisions are a property of
# the catalog as a whole, and commit 3 documents them from here.
MATERIALITY_BOUNDARY_IDS: tuple[str, ...] = ("M-19", "M-20", "M-21")
