"""PR27-3.2: what the AST on disk cannot say about what is running.

The surface of commit 3.1 hashes files.  Two things diverge from those files
after import without touching a byte of them, and this module is the test for
both:

* **C.1** -- the module a name resolves to.  A stand-in registered in
  ``sys.modules`` and a copy that wins a ``PYTHONPATH`` race both leave the
  tree untouched.
* **C.2** -- the object a symbol is bound to.  An attribute reassignment, a
  ``__code__`` transplant and a loader wrapped before the module ever existed in
  memory all leave the source describing a function that is not the one running.

Both are computed at *evaluation* time.  A fingerprint taken at import cannot
see a reassignment performed afterwards, which is the whole of M-01.

Also here, because they are the repairs the same commit owes: the bounded
component cache (B-7), the registry logic that moved into the surface (B-8), the
interpreter the project declares (B-6), the marker manifest (D-1) and the
systemd controls that mitigate what no in-process check can close (section 4).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

from app import config
from app.signal_runtime_contract import AUTHORIZED_INTERPRETERS
from app.signal_scientific_identity import (
    _CACHE_ENTRIES_PER_COMPONENT,
    _CACHE_KIND_COMPONENT,
    _COMPONENT_CACHE,
    BINDING_CODE_MISMATCH,
    BINDING_MISSING,
    BINDING_NOT_A_FUNCTION,
    PROVENANCE_NO_FILE,
    PROVENANCE_OUTSIDE_SURFACE,
    PROVENANCE_PATH_MISMATCH,
    _material_symbols,
    build_identity_registry,
    check_identity_registry,
    compute_scientific_implementation_identity,
    discover_scientific_surface,
    serialize_identity_registry,
    verify_bound_objects,
    verify_loaded_module_provenance,
)

ROOT = Path(__file__).resolve().parents[1]

# Units that actually start an interpreter.  A timer or a shell script is not a
# process a sitecustomize could ever run inside.
INTERPRETER_MARKERS = ("/bin/python", "/bin/uvicorn")


@pytest.fixture
def restore_identity_module():
    """Undo in-process mutations, whatever the test did to the module."""

    import app.signal_scientific_identity as identity_module

    saved = dict(vars(identity_module))
    modules = dict(sys.modules)
    yield identity_module
    for name in [n for n in vars(identity_module) if n not in saved]:
        delattr(identity_module, name)
    for name, value in saved.items():
        setattr(identity_module, name, value)
    sys.modules.clear()
    sys.modules.update(modules)
    _COMPONENT_CACHE.clear()


# --------------------------------------------------------------------------
# C.1 -- provenance of the loaded modules
# --------------------------------------------------------------------------


def test_an_honest_process_reports_no_provenance_anomaly() -> None:
    """The control.  Without it every assertion below is unfalsifiable.

    If a clean tree produced anomalies, the checks would be refusing on noise
    and the digest would depend on which modules a caller happened to import.
    """

    assert verify_loaded_module_provenance() == ()
    assert compute_scientific_implementation_identity()["module_provenance"] == []


def test_a_module_whose_file_is_outside_the_surface_is_an_anomaly(
    restore_identity_module,
) -> None:
    """M-06 in miniature: a stand-in registered under a real module's name."""

    import app.ws_collector  # noqa: F401  (ensure the real one is loaded first)

    before = compute_scientific_implementation_identity()["digest"]
    synthetic = types.ModuleType("app.ws_collector")
    synthetic.__file__ = "/nonexistent/outside/ws_collector.py"
    sys.modules["app.ws_collector"] = synthetic

    assert ["app.ws_collector", PROVENANCE_OUTSIDE_SURFACE] in [
        list(item) for item in verify_loaded_module_provenance()
    ]
    # The divergence must *move the identity*, not merely be reported beside it.
    assert compute_scientific_implementation_identity()["digest"] != before


def test_a_module_with_no_file_at_all_is_an_anomaly(restore_identity_module) -> None:
    sys.modules["app.no_file_at_all"] = types.ModuleType("app.no_file_at_all")
    assert ["app.no_file_at_all", PROVENANCE_NO_FILE] in [
        list(item) for item in verify_loaded_module_provenance()
    ]


def test_a_module_loaded_from_another_surface_file_is_an_anomaly(
    restore_identity_module,
) -> None:
    """Inside the surface is not enough; it must be the file the name denotes.

    A stand-in that borrows another *hashed* component's path would pass a check
    that only asked "is this file part of the surface", and every byte of both
    files would still be accounted for in the digest.
    """

    impostor = types.ModuleType("app.ws_collector")
    impostor.__file__ = str(ROOT / "app" / "scalp_collector.py")
    sys.modules["app.ws_collector"] = impostor
    assert ["app.ws_collector", PROVENANCE_PATH_MISMATCH] in [
        list(item) for item in verify_loaded_module_provenance()
    ]


def test_provenance_exempts_no_module_by_name() -> None:
    """An allowlist here would be an allowlist for exactly one attacker.

    The check is written over ``sys.modules`` with a prefix and nothing else, so
    this asserts on the source: a name-keyed exemption cannot be added without
    this test seeing it.
    """

    source = (ROOT / "app" / "signal_scientific_identity.py").read_text(encoding="utf-8")
    body = source.split("def verify_loaded_module_provenance")[1].split("\ndef ")[0]
    for forbidden in ("app.signal_", "app.ws_", "app.scalp_", "EXEMPT", "ALLOWLIST"):
        assert forbidden not in body, f"provenance exempts {forbidden!r} by name"


# --------------------------------------------------------------------------
# C.2 -- the object actually bound
# --------------------------------------------------------------------------


def test_an_honest_process_reports_no_binding_anomaly() -> None:
    assert verify_bound_objects() == ()
    assert compute_scientific_implementation_identity()["bound_objects"] == []


def test_reassigning_a_validator_at_runtime_moves_the_identity(
    restore_identity_module,
) -> None:
    """M-01.  Evaluated now, not captured at import -- that is the whole point.

    A hash taken while the module was importing would have recorded the real
    function and would still record it after this line.
    """

    identity_module = restore_identity_module
    before = compute_scientific_implementation_identity()["digest"]

    identity_module.validate_scientific_implementation_identity = lambda stored: stored

    assert [
        "app.signal_scientific_identity",
        "validate_scientific_implementation_identity",
        BINDING_CODE_MISMATCH,
    ] in [list(item) for item in verify_bound_objects()]
    assert compute_scientific_implementation_identity()["digest"] != before


def test_transplanting_a_code_object_moves_the_identity(restore_identity_module) -> None:
    """M-05.  The file keeps every byte; only the bound object changes."""

    import app.ws_collector as ws_collector

    before = compute_scientific_implementation_identity()["digest"]
    original = ws_collector.spot_pairs.__code__

    def _decoy(symbols: tuple[str, ...], routing: object) -> tuple[str, ...]:
        return tuple("ETHUSDT" for _ in symbols)

    ws_collector.spot_pairs.__code__ = _decoy.__code__
    try:
        assert ["app.ws_collector", "spot_pairs", BINDING_CODE_MISMATCH] in [
            list(item) for item in verify_bound_objects()
        ]
        assert compute_scientific_implementation_identity()["digest"] != before
    finally:
        ws_collector.spot_pairs.__code__ = original


def test_replacing_a_symbol_with_a_non_function_is_an_anomaly(
    restore_identity_module,
) -> None:
    identity_module = restore_identity_module
    identity_module.canonical_python_module_v2 = "not a function at all"
    assert [
        "app.signal_scientific_identity",
        "canonical_python_module_v2",
        BINDING_NOT_A_FUNCTION,
    ] in [list(item) for item in verify_bound_objects()]


def test_deleting_a_symbol_is_an_anomaly(restore_identity_module) -> None:
    identity_module = restore_identity_module
    delattr(identity_module, "canonical_python_module_v2")
    assert [
        "app.signal_scientific_identity",
        "canonical_python_module_v2",
        BINDING_MISSING,
    ] in [list(item) for item in verify_bound_objects()]


def test_the_material_symbols_come_from_the_surface_not_from_a_list() -> None:
    """A symbol added to a module must participate by existing.

    The refuted closures of this series all failed the same way: an enumeration
    covers what somebody remembered.  This asserts the enumeration is derived,
    by adding a symbol to a source and seeing it appear.
    """

    source = "def alpha():\n    return 1\n\n\nclass Holder:\n    def beta(self):\n        return 2\n"
    assert _material_symbols(source) == (("Holder.beta", False), ("alpha", False))

    grown = source + "\n\ndef nobody_enumerated_this():\n    return 3\n"
    assert ("nobody_enumerated_this", False) in _material_symbols(grown)


def test_a_function_nested_in_a_function_is_not_addressed_separately() -> None:
    """It cannot be reassigned on its own, and its enclosing fingerprint has it."""

    source = "def outer():\n    def inner():\n        return 1\n    return inner\n"
    assert _material_symbols(source) == (("outer", False),)


def test_the_bound_object_check_survives_a_randomized_hash_seed() -> None:
    """Constants are compared by structure, never by ``repr``.

    A set literal becomes a ``frozenset`` constant, and two frozensets holding
    the same elements iterate in an order that depends on the process's hash
    seed.  Fingerprinting their ``repr`` made this check accuse a different
    innocent function on every run, so the regression is pinned here rather than
    rediscovered.
    """

    program = (
        "import app.api, app.db, app.ws_collector, app.scalp_collector, app.metrics;"
        "from app.signal_scientific_identity import verify_bound_objects as v,"
        "compute_scientific_implementation_identity as c;"
        "print(len(v()), c()['digest'])"
    )
    results = set()
    for seed in ("0", "12345", "99999"):
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ROOT), "PYTHONHASHSEED": seed},
        )
        assert completed.returncode == 0, completed.stderr[-500:]
        results.add(completed.stdout.strip())
    assert len(results) == 1, f"the identity depends on the hash seed: {results}"
    assert results.pop().startswith("0 "), "a clean tree reported binding anomalies"


# --------------------------------------------------------------------------
# The digest stays the same under every certified interpreter
# --------------------------------------------------------------------------


def test_post_import_verification_did_not_make_the_digest_interpreter_dependent() -> None:
    """C.2 compiles source in-process precisely so that this stays true.

    Bytecode differs between 3.11 and 3.13.  Recording fingerprints in the
    registry would have made the code digest disagree with itself across
    runtimes, which is the invariant M-16 exists to defend; comparing live
    objects against source compiled *here* keeps the anomaly list empty under
    both, and the anomaly list is what enters the digest.
    """

    from tests.identity_mutation import harness

    alternate = harness.find_alternate_interpreter()
    if alternate is None:
        assert not harness.configured_interpreters(), (
            "an interpreter was declared but none of them is usable"
        )
        return

    program = (
        "from app.signal_scientific_identity import "
        "compute_scientific_implementation_identity as c;"
        "i=c();print(i['digest'], len(i['module_provenance']), len(i['bound_objects']))"
    )
    completed = subprocess.run(
        [alternate, "-c", program],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr[-500:]
    digest = compute_scientific_implementation_identity()["digest"]
    assert completed.stdout.strip() == f"{digest} 0 0"


# --------------------------------------------------------------------------
# B-7 -- the component cache is bounded
# --------------------------------------------------------------------------


def test_the_component_cache_cannot_outgrow_the_surface() -> None:
    """An unbounded dict keyed by content hash grows for the life of a collector.

    Every edit to a component used to add an entry that nothing removed.  The
    bound is the surface: at most a fixed number of generations per component
    path, and nothing at all for a path that has left the surface.
    """

    _COMPONENT_CACHE.clear()
    compute_scientific_implementation_identity()
    surface = {entry.relative_path for entry in discover_scientific_surface()}
    assert len(_COMPONENT_CACHE) <= len(surface) * _CACHE_ENTRIES_PER_COMPONENT

    for generation in range(50):
        _COMPONENT_CACHE.put(
            "app/ws_collector.py", f"{generation:064x}", _CACHE_KIND_COMPONENT, "x"
        )
    assert len(_COMPONENT_CACHE) <= len(surface) * _CACHE_ENTRIES_PER_COMPONENT

    _COMPONENT_CACHE.put("app/gone.py", "0" * 64, _CACHE_KIND_COMPONENT, "x")
    _COMPONENT_CACHE.retain(frozenset(surface))
    assert _COMPONENT_CACHE.get("app/gone.py", "0" * 64, _CACHE_KIND_COMPONENT) is None


def test_the_cache_is_still_keyed_by_content_and_not_by_timestamp() -> None:
    """B-7 bounded the cache; it must not have loosened the key doing it."""

    source = (ROOT / "app" / "signal_scientific_identity.py").read_text(encoding="utf-8")
    body = source.split("def _component_digest")[1].split("\ndef ")[0]
    assert "sha256" in body
    for forbidden in ("st_mtime", "st_size", "stat()"):
        assert forbidden not in body, f"the component cache key reads {forbidden}"


# --------------------------------------------------------------------------
# B-8 -- the registry logic is inside the surface
# --------------------------------------------------------------------------


def test_the_registry_generator_lives_in_a_hashed_component() -> None:
    """H-7: while it lived in scripts/, one editor owned both sides.

    ``--check`` compared the tree against a registry produced by a generator
    nobody hashed, so whoever could edit the script could make the comparison
    agree with itself -- M-02's failure mode, one directory across.
    """

    covered = {entry.relative_path for entry in discover_scientific_surface()}
    assert "app/signal_scientific_identity.py" in covered
    assert not [path for path in covered if path.startswith("scripts/")], (
        "scripts/ must not be dragged into the identity wholesale"
    )

    entry_point = (ROOT / "scripts" / "register_identity.py").read_text(encoding="utf-8")
    for decision in ("surface_manifest", "code_digest", "schema_version"):
        assert decision not in entry_point, (
            f"the entry point still decides {decision!r}; it must only parse and print"
        )


def test_the_committed_registry_is_what_this_tree_computes() -> None:
    ok, message = check_identity_registry()
    assert ok, message
    assert serialize_identity_registry(build_identity_registry()) == (
        (ROOT / "identity" / "registry.json").read_text(encoding="utf-8")
    )


# --------------------------------------------------------------------------
# B-6 -- one declared interpreter, in both documents
# --------------------------------------------------------------------------


def test_pyproject_declares_only_interpreters_the_registry_will_operate_under() -> None:
    """H-2's class of defect: a repository document contradicting the code.

    ``requires-python`` said 3.11 through 3.13 while the registry authorized
    3.13 alone, so a reader could install under a runtime the system then
    refuses to run on -- and an auditor who finds that is right to distrust the
    rest.
    """

    declared = re.search(
        r'^requires-python\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert declared, "pyproject.toml declares no requires-python"
    authorized = sorted({item["python"] for item in AUTHORIZED_INTERPRETERS})
    assert len(authorized) == 1, authorized
    major, minor = authorized[0].split(".")
    assert declared.group(1) == f">={major}.{minor},<{major}.{int(minor) + 1}"


# --------------------------------------------------------------------------
# D-1 -- the markers are a contract, so they are pinned
# --------------------------------------------------------------------------

MARKER_MANIFEST = Path(__file__).resolve().parent / "pr27_marker_manifest.json"
MARKER_PATTERN = re.compile(r"\bPR27_[A-Z0-9_]+?_(?:BEGIN|END)\b")


def _markers_on_disk() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for sub in ("app", "sql"):
        for path in sorted((ROOT / sub).rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.suffix not in (".py", ".sql"):
                continue
            markers = sorted(
                set(MARKER_PATTERN.findall(path.read_text(encoding="utf-8")))
            )
            if markers:
                found[path.relative_to(ROOT).as_posix()] = markers
    return found


def test_the_region_markers_match_their_manifest_in_both_directions() -> None:
    """H-10.  They no longer decide the digest, and the sweeps still read them.

    A contract that can be deleted without anything noticing is not a contract:
    removing a marker would silently disarm the structural sweeps that read it,
    and the digest would not move because a comment is not material.  The
    manifest is what makes the deletion visible.  Both directions, because a
    marker added without recording it is a boundary nobody reviewed.
    """

    declared = json.loads(MARKER_MANIFEST.read_text(encoding="utf-8"))
    on_disk = _markers_on_disk()
    assert on_disk == declared, {
        "missing_from_tree": {
            path: sorted(set(declared[path]) - set(on_disk.get(path, [])))
            for path in declared
            if set(declared[path]) - set(on_disk.get(path, []))
        },
        "absent_from_manifest": {
            path: sorted(set(on_disk[path]) - set(declared.get(path, [])))
            for path in on_disk
            if set(on_disk[path]) - set(declared.get(path, []))
        },
    }


def test_every_marker_is_a_balanced_begin_end_pair() -> None:
    for path, markers in json.loads(MARKER_MANIFEST.read_text(encoding="utf-8")).items():
        begins = {name[: -len("_BEGIN")] for name in markers if name.endswith("_BEGIN")}
        ends = {name[: -len("_END")] for name in markers if name.endswith("_END")}
        assert begins == ends, f"{path}: unbalanced {sorted(begins ^ ends)}"


# --------------------------------------------------------------------------
# Section 4 -- the controls that mitigate what no in-process check can close
# --------------------------------------------------------------------------


def _interpreter_units() -> list[Path]:
    return [
        unit
        for unit in sorted((ROOT / "deploy" / "systemd").glob("coinalyze-*.service"))
        if any(marker in unit.read_text(encoding="utf-8") for marker in INTERPRETER_MARKERS)
    ]


def test_every_unit_that_starts_an_interpreter_carries_the_compensating_controls() -> None:
    """M-38 is RESIDUAL, and a residual without controls is an unmitigated risk.

    Nothing running inside the process can detect a ``sitecustomize`` that
    replaced the combined validator before the module existed in memory.  What
    can be done is to make it impossible to place one: no user site directory,
    a tree the service user cannot write, and no way to acquire privileges.
    Enumerating those in a document is not doing them, so they are asserted on
    the units that ship.
    """

    units = _interpreter_units()
    assert units, "no systemd unit starts an interpreter"
    for unit in units:
        source = unit.read_text(encoding="utf-8")
        for directive in (
            "Environment=PYTHONNOUSERSITE=1",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
            "ReadOnlyPaths=/opt/coinalyze",
        ):
            assert directive in source, f"{unit.name} is missing {directive}"


def test_the_service_user_is_not_the_owner_of_the_tree_it_runs() -> None:
    """Separating them is what makes the read-only tree more than a setting.

    A service that owned its own deployment could rewrite the files the
    read-only mount protects and restart itself into them.
    """

    installer = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")
    owners = re.findall(r"chown\s+-R\s+([A-Za-z0-9_.-]+):", installer)
    assert owners, "update.sh never states who owns the deployed tree"
    for unit in _interpreter_units():
        service_user = re.search(
            r"^User=(.+)$", unit.read_text(encoding="utf-8"), re.MULTILINE
        )
        assert service_user, f"{unit.name} does not declare User="
        assert service_user.group(1).strip() not in owners, (
            f"{unit.name} runs as the owner of the tree it reads"
        )


def test_the_deployment_root_the_controls_protect_is_the_one_the_code_resolves() -> None:
    """The units would protect nothing if they named a different directory."""

    assert config.DEPLOYMENT_ROOT == "/opt/coinalyze"
    for unit in _interpreter_units():
        source = unit.read_text(encoding="utf-8")
        assert f"ReadOnlyPaths={config.DEPLOYMENT_ROOT}" in source, unit.name
        assert f"Environment={config.PROJECT_ROOT_ENV}={config.DEPLOYMENT_ROOT}" in source
