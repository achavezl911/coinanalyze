"""PR27-R05, third correction: whole-module identity for the three raw modules.

``e84ebe81`` and ``9b2e082c`` were both offered as the R05 closure and both were
refuted by independent review.  The refutation is not about a missing symbol: it
is about the *shape* of the closure property.  While the identity is built from
marker-delimited regions plus a list of material symbol names, the property it
can support is "the enumerated things did not change", and an enumeration is
exactly what an attacker -- or an honest mistake -- escapes.

Five mutations were demonstrated to keep the digest unchanged on ``9b2e082c``:

1. A direct write into ``TRADE_STORE`` from code outside every protected region.
   ``TRADE_STORE`` is defined at ``app/scalp_collector.py:442``, outside every
   region, and ``monitor()`` is outside every region too, so a statement that
   fabricates buckets there never reaches the digest.
2. A new helper that writes to the store and is started from ``main()``.
   ``main()`` (``app/scalp_collector.py:1817``) is entirely outside the
   identity, so both the helper and its ``create_task`` are invisible.
3. Inverting the buy/sell classification in ``TradeBucket.add``
   (``app/scalp_collector.py:125``).  Aggression is what the whole
   microstructure result is computed from, and the method sits outside every
   region.
4. Widening the realtime bucket from 5 to 10 seconds
   (``rt_ts = floor_ts_seconds(event_ms, 5)``, ``app/scalp_collector.py:149``).
   The observation grid changes and the digest does not.
5. Substituting the ``from functools import partial`` import
   (``app/scalp_collector.py:12``) for a look-alike that silently drops the last
   bound argument -- which is the attested ``routing`` in every producer
   binding.  The import line is above every marker.

None of these is fixed by adding names to ``MATERIAL_SYMBOLS``: 1 and 2 are new
code, 3 and 4 are arithmetic inside existing code, and 5 replaces a name the
sweep treats as a builtin of the language.  The correction therefore changes the
component *kind*: a ``python_module`` component canonicalizes the complete AST
of a file, with no BEGIN/END markers and no symbol list, and replaces every
partial component that overlapped that file.

Every mutation below is anchored through the AST to the real definition site --
the ``ast.If`` inside ``TradeBucket.add``, the ``ast.Constant`` inside the
``rt_ts`` assignment, the ``ast.ImportFrom`` node itself -- and rewritten at the
node's own byte offsets.  A duplicate expression moved into a region cannot
satisfy them, which is precisely how ``700f7695`` and ``450cf2fb`` went green
while the executed code stayed unprotected.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from app.signal_runtime_contract import (
    REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    compute_scientific_runtime_contract,
)
from app.signal_scientific_identity import (
    SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS,
    compute_scientific_implementation_identity,
)
from tests.test_pr27_r05_routing_closure import IDENTITY_FILES

ROOT = Path(__file__).resolve().parents[1]

# The three modules the correction covers in full.  Everything that can change
# what the raw collectors observe, classify, bucket, store or deliver lives in
# one of them.
FULL_MODULE_FILES = (
    "app/scalp_collector.py",
    "app/signal_runtime_contract.py",
    "app/ws_collector.py",
)

# The digest observed on 9b2e082c while each of the five mutations was applied.
# Recorded as history only: no assertion compares against it, because the
# correction recomputes identity-v1.
REFUTED_UNMOVED_DIGEST = (
    "c939add3055ea2a8b0edd1ea93630682043a2b98b4ac33425bc49acc47cf156c"
)


# --------------------------------------------------------------------------
# Tree, digest and region helpers
# --------------------------------------------------------------------------


def _identity_tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    for relative in IDENTITY_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / relative, target)
    return root


def _digest(root: Path) -> str:
    return compute_scientific_implementation_identity(root=root)["digest"]


def _read(root: Path, relative: str) -> str:
    return (root / relative).read_text(encoding="utf-8")


def _write(root: Path, relative: str, source: str) -> None:
    (root / relative).write_text(source, encoding="utf-8")


def _region_spans(root: Path, relative: str) -> list[tuple[int, int]]:
    """Line spans of every BEGIN/END marker pair still present in the file.

    The markers survive the correction as inert comments so the structural
    sweep that reads them keeps working, but they no longer decide what the
    identity covers.  Asserting a mutation lands outside them therefore stays
    meaningful in both directions: before the correction it proves the mutation
    was unprotected, after it proves module coverage is what caught it.
    """

    spans: list[tuple[int, int]] = []
    begin: int | None = None
    for number, line in enumerate(_read(root, relative).splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("# PR"):
            continue
        if stripped.endswith("_BEGIN"):
            begin = number
        elif stripped.endswith("_END") and begin is not None:
            spans.append((begin, number))
            begin = None
    return spans


def _assert_outside_every_region(root: Path, relative: str, lineno: int) -> None:
    for start, end in _region_spans(root, relative):
        assert not start <= lineno <= end, (
            f"{relative}:{lineno} is inside the marked region {start}..{end}; "
            "this mutation must exercise unmarked code"
        )


# --------------------------------------------------------------------------
# AST anchoring -- the node, never the first textual occurrence
# --------------------------------------------------------------------------


def _tree(root: Path, relative: str) -> ast.Module:
    return ast.parse(_read(root, relative))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return node
    raise AssertionError(f"module-level function {name!r} not found")


def _method(
    tree: ast.Module, class_name: str, method_name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == method_name
            ):
                return item
    raise AssertionError(f"method {class_name}.{method_name} not found")


def _body_anchor(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.stmt:
    """First executable statement, skipping a docstring if there is one.

    Inserting *before* a docstring would displace it out of position 0 and turn
    it into an ordinary expression statement, which moves the digest for a
    documentation reason.  These are material mutations and must not be able to
    pass for that reason.
    """

    body = node.body
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
        and len(body) > 1
    ):
        return body[1]
    return body[0]


def _insert_before(source: str, lineno: int, block: str) -> str:
    lines = source.splitlines(keepends=True)
    lines.insert(lineno - 1, block)
    return "".join(lines)


def _replace_span(source: str, first: int, last: int, block: str) -> str:
    lines = source.splitlines(keepends=True)
    lines[first - 1 : last] = [block]
    return "".join(lines)


def _rewrite_at(source: str, node: ast.AST, spelling: str, replacement: str) -> str:
    """Rewrite ``spelling`` at exactly the node's own byte offsets."""

    lineno = node.lineno  # type: ignore[attr-defined]
    col = node.col_offset  # type: ignore[attr-defined]
    lines = source.splitlines(keepends=True)
    raw = lines[lineno - 1].encode("utf-8")
    assert raw[col : col + len(spelling)] == spelling.encode("utf-8"), (
        f"AST position {lineno}:{col} does not spell {spelling!r}"
    )
    lines[lineno - 1] = (
        raw[:col] + replacement.encode("utf-8") + raw[col + len(spelling) :]
    ).decode("utf-8")
    return "".join(lines)


# --------------------------------------------------------------------------
# The five refuted mutations
# --------------------------------------------------------------------------


def _mutate_direct_store_write(root: Path) -> None:
    """1. Fabricate buckets straight into ``TRADE_STORE`` from unmarked code."""

    relative = "app/scalp_collector.py"
    source = _read(root, relative)
    anchor = _body_anchor(_function(_tree(root, relative), "monitor"))
    _assert_outside_every_region(root, relative, anchor.lineno)
    indent = " " * anchor.col_offset
    block = (
        f"{indent}TRADE_STORE.realtime[('BTCUSDT_PERP.A', 'binance', 0)] = "
        "TradeBucket(\n"
        f"{indent}    buy_vol_usd=1e9, sell_vol_usd=0.0, trade_count=1, last_px=1.0\n"
        f"{indent})\n"
    )
    _write(root, relative, _insert_before(source, anchor.lineno, block))


def _mutate_store_helper_started_from_main(root: Path) -> None:
    """2. A new store-writing helper, created as a task by ``main()``."""

    relative = "app/scalp_collector.py"
    source = _read(root, relative)
    tree = _tree(root, relative)
    main_node = _function(tree, "main")
    anchor = _body_anchor(main_node)
    _assert_outside_every_region(root, relative, main_node.lineno)
    _assert_outside_every_region(root, relative, anchor.lineno)
    indent = " " * anchor.col_offset
    call_block = (
        f"{indent}asyncio.create_task(_shadow_store_feed(), name='shadow-store')\n"
    )
    helper_block = (
        "\n"
        "async def _shadow_store_feed() -> None:\n"
        "    while True:\n"
        "        await TRADE_STORE.add(\n"
        "            'BTCUSDT_PERP.A', 'binance', now_ms(), 1.0, 1.0, True\n"
        "        )\n"
        "        await asyncio.sleep(1)\n"
        "\n"
    )
    # Highest line first: the second insertion sits above the first, so the
    # offsets the AST reported stay valid.
    source = _insert_before(source, anchor.lineno, call_block)
    source = _insert_before(source, main_node.lineno, helper_block)
    _write(root, relative, source)


def _mutate_aggression_classification(root: Path) -> None:
    """3. Invert buy/sell inside ``TradeBucket.add``."""

    relative = "app/scalp_collector.py"
    source = _read(root, relative)
    method = _method(_tree(root, relative), "TradeBucket", "add")
    tests = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "is_buy"
    ]
    assert len(tests) == 1, f"expected one `if is_buy:` in TradeBucket.add, got {len(tests)}"
    branch = tests[0]
    _assert_outside_every_region(root, relative, branch.lineno)
    _write(root, relative, _rewrite_at(source, branch.test, "is_buy", "not is_buy"))


def _mutate_realtime_bucket_seconds(root: Path) -> None:
    """4. Widen the realtime observation grid from 5 to 10 seconds."""

    relative = "app/scalp_collector.py"
    source = _read(root, relative)
    method = _method(_tree(root, relative), "TradeStore", "add")
    constants: list[ast.Constant] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "rt_ts":
            continue
        call = node.value
        assert isinstance(call, ast.Call), "rt_ts must be assigned from a call"
        assert isinstance(call.func, ast.Name) and call.func.id == "floor_ts_seconds"
        width = call.args[1]
        assert isinstance(width, ast.Constant) and width.value == 5
        constants.append(width)
    assert len(constants) == 1, f"expected one rt_ts grid, got {len(constants)}"
    _assert_outside_every_region(root, relative, constants[0].lineno)
    _write(root, relative, _rewrite_at(source, constants[0], "5", "10"))


def _mutate_partial_import(root: Path) -> None:
    """5. Swap ``functools.partial`` for a look-alike that drops the routing."""

    relative = "app/scalp_collector.py"
    source = _read(root, relative)
    imports = [
        node
        for node in _tree(root, relative).body
        if isinstance(node, ast.ImportFrom)
        and node.module == "functools"
        and any(alias.name == "partial" for alias in node.names)
    ]
    assert len(imports) == 1, f"expected one functools/partial import, got {len(imports)}"
    node = imports[0]
    _assert_outside_every_region(root, relative, node.lineno)
    # Drops the last bound argument, which is the attested ``routing`` in every
    # ``partial(session, routing)`` / ``partial(cycle, pool, ownership, routing)``
    # binding the entrypoint builds.
    replacement = (
        "def partial(func, *bound, **bound_kwargs):\n"
        "    def _apply(*args, **kwargs):\n"
        "        return func(*bound[:-1], *args, **{**bound_kwargs, **kwargs})\n"
        "\n"
        "    return _apply\n"
    )
    _write(root, relative, _replace_span(source, node.lineno, node.end_lineno, replacement))


REFUTED_MUTATIONS = (
    ("direct-trade-store-write", _mutate_direct_store_write),
    ("store-helper-started-from-main", _mutate_store_helper_started_from_main),
    ("tradebucket-aggression-inverted", _mutate_aggression_classification),
    ("realtime-bucket-5s-to-10s", _mutate_realtime_bucket_seconds),
    ("functools-partial-substituted", _mutate_partial_import),
)


@pytest.mark.parametrize(
    ("label", "mutate"),
    REFUTED_MUTATIONS,
    ids=[case[0] for case in REFUTED_MUTATIONS],
)
def test_refuted_mutation_moves_the_scientific_identity(
    tmp_path: Path, label: str, mutate
) -> None:
    root = _identity_tree(tmp_path)
    baseline = _digest(root)
    assert baseline == _digest(ROOT), "the copied tree must reproduce the repository digest"
    mutate(root)
    mutated = _digest(root)
    assert mutated != baseline, (
        f"{label}: the mutation left the scientific identity at {baseline}; "
        "material code outside the identity is exactly what was refuted"
    )


# --------------------------------------------------------------------------
# The same class of defect on the other two covered modules
# --------------------------------------------------------------------------


def _mutate_ws_realtime_grid(root: Path) -> None:
    """``ws_collector`` writes the same 5-second grid by hand."""

    relative = "app/ws_collector.py"
    source = _read(root, relative)
    method = _method(_tree(root, relative), "BucketStore", "add")
    constants: list[ast.Constant] = []
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != "rt_ts":
            continue
        for child in ast.walk(node.value):
            if isinstance(child, ast.Constant) and child.value == 5_000:
                constants.append(child)
    assert len(constants) == 1, f"expected one rt grid divisor, got {len(constants)}"
    _assert_outside_every_region(root, relative, constants[0].lineno)
    _write(root, relative, _rewrite_at(source, constants[0], "5_000", "10_000"))


def _mutate_ws_aggression(root: Path) -> None:
    """``RtBucket.add`` splits the same aggression the scalp side does."""

    relative = "app/ws_collector.py"
    source = _read(root, relative)
    method = _method(_tree(root, relative), "RtBucket", "add")
    branches = [
        node
        for node in ast.walk(method)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "is_buy"
    ]
    assert branches, "no `if is_buy:` branch found in RtBucket.add"
    # Highest position first, so the earlier rewrites keep their offsets.
    for branch in sorted(
        branches, key=lambda node: (node.test.lineno, node.test.col_offset), reverse=True
    ):
        _assert_outside_every_region(root, relative, branch.lineno)
        source = _rewrite_at(source, branch.test, "is_buy", "not is_buy")
    _write(root, relative, source)


def _mutate_contract_version_constant(root: Path) -> None:
    """The contract version constant sits above the marker in its own module."""

    relative = "app/signal_runtime_contract.py"
    source = _read(root, relative)
    constants: list[ast.Constant] = []
    for node in _tree(root, relative).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id != "SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1":
            continue
        assert isinstance(node.value, ast.Constant)
        constants.append(node.value)
    assert len(constants) == 1
    _assert_outside_every_region(root, relative, constants[0].lineno)
    _write(root, relative, _rewrite_at(source, constants[0], "1", "2"))


ADJACENT_MUTATIONS = (
    ("ws-realtime-grid-5s-to-10s", _mutate_ws_realtime_grid),
    ("ws-rtbucket-aggression-inverted", _mutate_ws_aggression),
    ("contract-version-constant", _mutate_contract_version_constant),
)


@pytest.mark.parametrize(
    ("label", "mutate"),
    ADJACENT_MUTATIONS,
    ids=[case[0] for case in ADJACENT_MUTATIONS],
)
def test_adjacent_module_mutation_moves_the_scientific_identity(
    tmp_path: Path, label: str, mutate
) -> None:
    root = _identity_tree(tmp_path)
    baseline = _digest(root)
    mutate(root)
    assert _digest(root) != baseline, (
        f"{label}: the mutation left the scientific identity at {baseline}"
    )


# --------------------------------------------------------------------------
# Structure: full-module coverage, and no partial component left overlapping
# --------------------------------------------------------------------------


def test_the_three_modules_are_covered_as_whole_python_modules() -> None:
    by_path: dict[str, list[object]] = {}
    for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS:
        by_path.setdefault(component.relative_path, []).append(component)
    for relative in FULL_MODULE_FILES:
        components = by_path.get(relative, [])
        assert len(components) == 1, (
            f"{relative} must be covered by exactly one component, "
            f"found {len(components)}"
        )
        component = components[0]
        assert component.language == "python_module", (
            f"{relative} must be covered as a whole module, not as a region"
        )
        assert component.begin_marker == "", f"{relative} must not carry a begin marker"
        assert component.end_marker == "", f"{relative} must not carry an end marker"


def test_no_marker_region_component_overlaps_a_full_module_file() -> None:
    for component in SCIENTIFIC_IMPLEMENTATION_V1_COMPONENTS:
        if component.relative_path not in FULL_MODULE_FILES:
            continue
        assert component.language == "python_module", (
            f"{component.name} still extracts a region from "
            f"{component.relative_path}; partial and full coverage of the same "
            "file would hash the same lines twice and reintroduce the "
            "enumeration the correction removes"
        )


def test_full_module_component_covers_code_outside_every_marker() -> None:
    """The covered payload must include lines the markers never enclosed."""

    identity = compute_scientific_implementation_identity()
    covered = {
        component["source"]
        for component in identity["components"]
        if component["canonicalizer"] == "canonical_python_module_v1"
    }
    assert covered == {relative for relative in FULL_MODULE_FILES}


# --------------------------------------------------------------------------
# Neutrality: documentation and layout must not move the digest
# --------------------------------------------------------------------------


@pytest.mark.parametrize("relative", FULL_MODULE_FILES)
def test_comment_and_blank_line_changes_do_not_move_the_identity(
    tmp_path: Path, relative: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = _digest(root)
    source = _read(root, relative)
    lines = source.splitlines(keepends=True)
    # A comment on top, a comment at the end, and blank lines in between.
    rewritten = ["# identity neutrality probe: a comment is not semantics\n"]
    for index, line in enumerate(lines):
        rewritten.append(line)
        if line.strip() == "" and index % 7 == 0:
            rewritten.append("\n")
    rewritten.append("\n# trailing commentary, equally irrelevant\n")
    _write(root, relative, "".join(rewritten))
    assert _digest(root) == baseline, (
        f"{relative}: comments and blank lines moved the identity; "
        "canonicalization must be AST-based"
    )


@pytest.mark.parametrize("relative", FULL_MODULE_FILES)
def test_docstring_changes_do_not_move_the_identity(
    tmp_path: Path, relative: str
) -> None:
    root = _identity_tree(tmp_path)
    baseline = _digest(root)
    source = _read(root, relative)
    # Neither collector opens with a module docstring, so target the first
    # documented definition instead: what must be neutral is documentation,
    # wherever it is attached.
    documented: list[ast.Expr] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            documented.append(body[0])
    assert documented, f"{relative} carries no docstring to rewrite"
    docstring = min(documented, key=lambda node: node.lineno)
    indent = " " * docstring.col_offset
    replacement = f'{indent}"""Rewritten documentation, semantically identical."""\n'
    _write(
        root,
        relative,
        _replace_span(source, docstring.lineno, docstring.end_lineno, replacement),
    )
    assert _digest(root) == baseline, (
        f"{relative}: rewriting a docstring moved the identity"
    )


# --------------------------------------------------------------------------
# Determinism and the digests that must not move
# --------------------------------------------------------------------------


def test_the_identity_is_deterministic(tmp_path: Path) -> None:
    root = _identity_tree(tmp_path)
    digests = {_digest(root) for _ in range(4)}
    assert len(digests) == 1
    assert digests == {_digest(ROOT)}


def test_the_runtime_contract_digest_is_unchanged() -> None:
    registered = REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS[
        SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1
    ]
    assert registered == (
        "c9cbe967b1f256644c0caf1ec851ea5a73d67029286afe0bb04461f582a21b00"
    )
    assert compute_scientific_runtime_contract()["digest"] == registered


def test_the_identity_matches_its_registry() -> None:
    from app.signal_scientific_identity import (
        REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS,
        SCIENTIFIC_IDENTITY_VERSION_V1,
    )

    computed = compute_scientific_implementation_identity()["digest"]
    assert (
        computed
        == REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS[SCIENTIFIC_IDENTITY_VERSION_V1]
    )
    assert computed != REFUTED_UNMOVED_DIGEST, (
        "the correction changes what the identity covers, so it must not "
        "reproduce the digest the review refuted"
    )
