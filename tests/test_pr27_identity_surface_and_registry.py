"""PR27-3.1: the discovered surface, the enumerated environment, the registry.

What these fix, in one sentence each:

* The surface is discovered, so nothing is covered because somebody listed it.
* A component that is missing, or that leaves the root through a link, stops the
  identity from being computed at all.
* The canonical AST field list is an allow-list, so a future interpreter cannot
  add a field that silently changes the digest.
* The environment half is a *set*: one authorized profile per shard, or no
  sharded deployment could ever validate.
* Nothing accepts without going through the combined entry point.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app import config
from app.signal_runtime_contract import (
    AUTHORIZED_COLLECTOR_SHARD_PROFILES,
    AUTHORIZED_ENVIRONMENT_FIXED,
    AUTHORIZED_INTERPRETERS,
    authorized_environment_digests,
    compute_scientific_runtime_contract,
    enumerate_authorized_environment_profiles,
    resolved_market_catalog_source,
)
from app.signal_scientific_identity import (
    _CANONICAL_AST_FIELDS,
    CANONICALIZER_PYTHON_MODULE,
    SURFACE_REQUIRED_FILES,
    ScientificIdentityError,
    compute_scientific_implementation_identity,
    discover_scientific_surface,
    load_identity_registry,
    validate_scientific_identity,
    validate_scientific_implementation_identity,
)

ROOT = Path(__file__).resolve().parents[1]

# Fields that exist on some supported interpreters and not others.  Hashing any
# of them would make the code digest depend on the runtime, which is the one
# thing the environment half is there to carry instead.
INTERPRETER_DEPENDENT_AST_FIELDS = frozenset({"type_params", "type_comment", "type_ignores"})
LOCATION_AST_FIELDS = frozenset({"lineno", "col_offset", "end_lineno", "end_col_offset"})


def _surface_tree(destination: Path) -> Path:
    root = destination / "tree"
    for entry in discover_scientific_surface():
        target = root / entry.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / entry.relative_path, target)
    return root


# --------------------------------------------------------------------------
# Surface discovery
# --------------------------------------------------------------------------


def test_every_python_module_under_app_is_discovered_without_an_allowlist() -> None:
    covered = {entry.relative_path for entry in discover_scientific_surface()}
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "app").rglob("*.py")
        if "__pycache__" not in path.parts
    }
    assert on_disk, "app/ must contain Python modules"
    assert on_disk <= covered, sorted(on_disk - covered)
    for required in SURFACE_REQUIRED_FILES:
        assert required in covered
    assert "config/market_symbols.example.json" in covered
    # Tests are not part of the surface: editing them must not move the digest.
    assert not [path for path in covered if path.startswith("tests/")]


def test_a_new_module_participates_by_existing(tmp_path: Path) -> None:
    root = _surface_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]
    (root / "app" / "nobody_enumerated_this.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    assert compute_scientific_implementation_identity(root=root)["digest"] != baseline


def test_a_missing_required_component_stops_the_identity_being_computed(
    tmp_path: Path,
) -> None:
    """H-4, made explicit.

    This is the only structural control the mutation matrix ever found: with the
    surface enumerated, deleting a component made the identity impossible to
    compute rather than merely different.  Any tolerance for absent components
    -- "skip the ones that are not there so startup does not break" -- turns
    deleting the file that implements a guard into a way of passing.
    """

    for required in SURFACE_REQUIRED_FILES:
        root = _surface_tree(tmp_path / required.replace("/", "_"))
        (root / required).unlink()
        with pytest.raises(ScientificIdentityError, match="missing"):
            compute_scientific_implementation_identity(root=root)

    root = _surface_tree(tmp_path / "no_config")
    shutil.rmtree(root / "config")
    with pytest.raises(ScientificIdentityError, match="config/"):
        compute_scientific_implementation_identity(root=root)

    root = _surface_tree(tmp_path / "no_app")
    shutil.rmtree(root / "app")
    with pytest.raises(ScientificIdentityError, match="app/"):
        compute_scientific_implementation_identity(root=root)


def test_a_component_reached_through_a_symlink_out_of_the_root_fails_closed(
    tmp_path: Path,
) -> None:
    root = _surface_tree(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    target = root / "app" / "ws_collector.py"
    external = outside / "ws_collector.py"
    shutil.copyfile(target, external)
    target.unlink()
    target.symlink_to(external)

    # Byte-identical on purpose: what is refused is the link, not the content.
    assert target.read_text(encoding="utf-8") == external.read_text(encoding="utf-8")
    with pytest.raises(ScientificIdentityError, match="outside the scientific surface"):
        compute_scientific_implementation_identity(root=root)


# --------------------------------------------------------------------------
# Canonicalization
# --------------------------------------------------------------------------


def test_the_canonical_field_list_hashes_nothing_interpreter_dependent() -> None:
    """The invariant that keeps the code digest the same under 3.11 and 3.13.

    It used to hold because the deny-list happened to name ``type_params``.
    With an allow-list it holds because no node lists it, and this test is what
    keeps that true when somebody regenerates the map from a newer interpreter.
    """

    for node_type, fields in _CANONICAL_AST_FIELDS.items():
        forbidden = set(fields) & (INTERPRETER_DEPENDENT_AST_FIELDS | LOCATION_AST_FIELDS)
        assert not forbidden, f"{node_type} hashes {sorted(forbidden)}"


def test_every_node_type_in_the_surface_is_declared_and_unknown_ones_fail_closed() -> None:
    seen: set[str] = set()
    for entry in discover_scientific_surface():
        if entry.canonicalizer != CANONICALIZER_PYTHON_MODULE:
            continue
        tree = ast.parse((ROOT / entry.relative_path).read_text(encoding="utf-8"))
        seen.update(type(node).__name__ for node in ast.walk(tree))
    assert seen <= set(_CANONICAL_AST_FIELDS), sorted(seen - set(_CANONICAL_AST_FIELDS))

    class _UnknownNode(ast.AST):
        _fields = ()

    from app.signal_scientific_identity import _canonical_ast_value

    with pytest.raises(ScientificIdentityError, match="not in the canonical field list"):
        _canonical_ast_value(_UnknownNode())


def test_the_component_cache_is_keyed_by_content_not_by_timestamp(tmp_path: Path) -> None:
    """Canonicalizing forty modules is slow enough to be worth caching, and a
    cache is worth exactly what its key is worth.

    Keyed by mtime and size, a mutator who edits a component and restores its
    timestamp would keep the stale digest for the life of the process -- against
    a mutator with write access, which is the only threat this guard has.  Keyed
    by the content hash, the edit below is caught even though the file keeps its
    size and its timestamp to the nanosecond.
    """

    root = _surface_tree(tmp_path)
    baseline = compute_scientific_implementation_identity(root=root)["digest"]

    target = root / "app" / "ws_collector.py"
    before = target.stat()
    source = target.read_text(encoding="utf-8")
    mutated = source.replace("def spot_pairs(", "def spot_pairz(", 1)
    assert mutated != source and len(mutated) == len(source)
    target.write_text(mutated, encoding="utf-8")
    os.utime(target, ns=(before.st_atime_ns, before.st_mtime_ns))

    after = target.stat()
    assert after.st_size == before.st_size
    assert after.st_mtime_ns == before.st_mtime_ns
    assert compute_scientific_implementation_identity(root=root)["digest"] != baseline


def test_the_code_digest_is_identical_under_every_provisioned_interpreter() -> None:
    """Both branches assert; a runner with one interpreter still says so.

    The matrix measures this as M-16, but only when a second interpreter is
    provisioned.  Here the same invariant is checked directly, so that the
    reason a run did not check it is visible instead of implied.
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
        "compute_scientific_implementation_identity as c;print(c()['digest'])"
    )
    completed = subprocess.run(
        [alternate, "-c", program],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr[-400:]
    assert completed.stdout.strip() == (
        compute_scientific_implementation_identity()["digest"]
    )


# --------------------------------------------------------------------------
# The registry and the enumerated environment
# --------------------------------------------------------------------------


def test_the_registry_is_generated_and_matches_the_tree() -> None:
    registry = load_identity_registry()
    assert registry["code_digest"] == (
        compute_scientific_implementation_identity()["digest"]
    )
    manifest = {item["source"]: item["digest"] for item in registry["surface_manifest"]}
    computed = {
        component["source"]: component["digest"]
        for component in compute_scientific_implementation_identity()["components"]
    }
    assert manifest == computed


def test_the_registered_digest_constant_is_gone_from_app() -> None:
    """It moved out of the code, and it must not grow back.

    While the registry was a literal inside the module it described, changing
    both together was a two-line edit in one file.  It is still forgeable --
    that is M-02, and only the anchor of commit 3.3 closes it -- but it is no
    longer *invisible*.
    """

    for path in (ROOT / "app").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "REGISTERED_SCIENTIFIC_IMPLEMENTATION_DIGESTS" not in source, path
        assert "REGISTERED_SCIENTIFIC_RUNTIME_CONTRACT_DIGESTS" not in source, path


def test_the_authorized_environment_set_is_generated_from_its_axes() -> None:
    generated = enumerate_authorized_environment_profiles()
    registry = load_identity_registry()
    assert [item["digest"] for item in generated] == [
        item["digest"] for item in registry["authorized_environment_digests"]
    ]
    assert authorized_environment_digests() == {item["digest"] for item in generated}


def test_the_profile_set_is_the_cartesian_product_of_the_declared_axes() -> None:
    """Cardinality one today, and one *by deployment*, not by design.

    A single shard and a single certified interpreter make the product a set of
    one, which is why this checks the generator against a synthetic three-shard
    axis instead: the mechanism has to produce one authorized digest per shard
    the day the deployment grows, because requiring equality to a single value
    is what would keep every shard but the first from validating.
    """

    assert len(AUTHORIZED_COLLECTOR_SHARD_PROFILES) * len(AUTHORIZED_INTERPRETERS) == len(
        enumerate_authorized_environment_profiles()
    )

    three_shards = tuple(
        {"COLLECTOR_SHARD_INDEX": index, "COLLECTOR_SHARD_COUNT": 3} for index in range(3)
    )
    scaled = enumerate_authorized_environment_profiles(shard_profiles=three_shards)
    assert len(scaled) == 3 * len(AUTHORIZED_INTERPRETERS)
    assert len({item["digest"] for item in scaled}) == len(scaled)
    assert not {item["digest"] for item in scaled} & authorized_environment_digests()


def test_the_environment_half_carries_the_interpreter_settings_and_catalog_source() -> None:
    contract = compute_scientific_runtime_contract()
    assert contract["interpreter"] == {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "implementation": sys.implementation.name,
    }
    assert set(contract["environment_settings"]) == {
        "COLLECTOR_SHARD_INDEX",
        "COLLECTOR_SHARD_COUNT",
        "HARD_DATA_RETENTION_DAYS",
        "SCALP_MINUTE_RETENTION_HOURS",
    }
    assert contract["market_catalog_source"] == resolved_market_catalog_source()
    # A field added to Settings must not enter the identity by accident.
    assert set(contract["environment_settings"]) == (
        set(AUTHORIZED_ENVIRONMENT_FIXED) | {"COLLECTOR_SHARD_INDEX", "COLLECTOR_SHARD_COUNT"}
    )


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("COLLECTOR_SHARD_COUNT", 3),
        ("HARD_DATA_RETENTION_DAYS", 21),
        ("SCALP_MINUTE_RETENTION_HOURS", 48),
    ],
)
def test_an_unenumerated_environment_value_is_refused(setting: str, value: int) -> None:
    settings = {
        **dict(AUTHORIZED_ENVIRONMENT_FIXED),
        **dict(AUTHORIZED_COLLECTOR_SHARD_PROFILES[0]),
        setting: value,
    }
    contract = compute_scientific_runtime_contract(environment_settings=settings)
    assert contract["digest"] not in authorized_environment_digests()


def test_a_shard_index_inside_the_authorized_set_is_accepted() -> None:
    for shard in AUTHORIZED_COLLECTOR_SHARD_PROFILES:
        settings = {**dict(AUTHORIZED_ENVIRONMENT_FIXED), **dict(shard)}
        contract = compute_scientific_runtime_contract(environment_settings=settings)
        assert contract["digest"] in authorized_environment_digests()


def test_a_malformed_registry_fails_closed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "tree"
    (root / "identity").mkdir(parents=True)
    registry = root / "identity" / "registry.json"

    with pytest.raises(ScientificIdentityError, match="missing"):
        load_identity_registry(root)

    registry.write_text("{not json", encoding="utf-8")
    with pytest.raises(ScientificIdentityError, match="unreadable"):
        load_identity_registry(root)

    body = dict(load_identity_registry())
    body["schema_version"] = 99
    registry.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ScientificIdentityError, match="schema_version"):
        load_identity_registry(root)

    body = dict(load_identity_registry())
    body["authorized_environment_digests"] = []
    registry.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ScientificIdentityError, match="authorizes no environment"):
        load_identity_registry(root)


# --------------------------------------------------------------------------
# The combined entry point
# --------------------------------------------------------------------------


def test_the_combined_validator_accepts_this_tree_in_this_environment() -> None:
    validated = validate_scientific_identity()
    assert set(validated) == {"scientific_implementation", "scientific_runtime_contract"}
    assert validated["scientific_implementation"]["digest"] == (
        load_identity_registry()["code_digest"]
    )
    assert validated["scientific_runtime_contract"]["digest"] in (
        authorized_environment_digests()
    )


def test_the_combined_validator_refuses_an_unauthorized_environment(monkeypatch) -> None:
    from dataclasses import replace

    repointed = tuple(
        replace(item, spot_pair="ETHUSDT") if item.symbol == "BTCUSDT_PERP.A" else item
        for item in config.MARKET_SYMBOL_CATALOG
    )
    monkeypatch.setattr(config, "MARKET_SYMBOL_CATALOG", repointed)
    with pytest.raises(ScientificIdentityError, match="not an authorized environment profile"):
        validate_scientific_identity()


def test_the_compatibility_validator_has_no_independent_accept_path(monkeypatch) -> None:
    """It delegates, and the delegation is what is asserted.

    Leaving ``validate_scientific_implementation_identity`` able to accept on
    its own would rebuild the hole M-08 demonstrated: the code half validating
    while the environment half was never looked at.
    """

    identity = compute_scientific_implementation_identity()
    assert validate_scientific_implementation_identity(identity) == identity

    calls: list[object] = []

    def _refuse(presented: object = None) -> dict[str, object]:
        calls.append(presented)
        raise ScientificIdentityError("combined validation refused")

    monkeypatch.setattr(
        "app.signal_scientific_identity.validate_scientific_identity", _refuse
    )
    with pytest.raises(ScientificIdentityError, match="refused"):
        validate_scientific_implementation_identity(identity)
    assert calls, "the compatibility validator never consulted the combined one"


def test_a_frozen_identity_that_differs_from_runtime_is_refused() -> None:
    identity = compute_scientific_implementation_identity()
    stale = json.loads(json.dumps(identity))
    stale["digest"] = "0" * 64
    with pytest.raises(ValueError, match="does not match runtime semantics"):
        validate_scientific_implementation_identity(stale)


# --------------------------------------------------------------------------
# H-1: the project root
# --------------------------------------------------------------------------


def test_a_source_tree_without_config_fails_closed_instead_of_resolving_elsewhere(
    tmp_path: Path,
) -> None:
    """The repaired H-1.

    The old fallback returned ``/opt/coinalyze`` whenever ``<root>/config`` was
    absent, at import time and without saying so, which meant a broken checkout
    read another deployment's routing catalog while looking healthy.  A tree
    with a pyproject.toml is a source tree, and a source tree without config/ is
    broken.
    """

    source_root = tmp_path / "project"
    (source_root / "app").mkdir(parents=True)
    (source_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    module = source_root / "app" / "config.py"
    module.write_text("", encoding="utf-8")

    with pytest.raises(RuntimeError, match="no config/ directory"):
        config.resolve_project_root(module)

    (source_root / "config").mkdir()
    assert config.resolve_project_root(module) == source_root


def test_an_installed_package_uses_a_declared_deployment_root(tmp_path: Path) -> None:
    installed_module = tmp_path / "venv" / "site-packages" / "app" / "config.py"
    installed_module.parent.mkdir(parents=True)
    deployment_root = tmp_path / "deployment"
    (deployment_root / "config").mkdir(parents=True)

    assert config.resolve_project_root(installed_module, deployment_root) == (
        deployment_root
    )


def test_an_installed_package_with_no_usable_root_fails_closed(tmp_path: Path) -> None:
    installed_module = tmp_path / "venv" / "site-packages" / "app" / "config.py"
    installed_module.parent.mkdir(parents=True)
    empty_root = tmp_path / "empty"
    empty_root.mkdir()

    with pytest.raises(RuntimeError, match=config.PROJECT_ROOT_ENV):
        config.resolve_project_root(installed_module, empty_root)


def test_the_deployment_root_is_declared_where_the_units_can_see_it() -> None:
    """The repair only holds if the deployment declares what it resolves.

    ``scripts/*.py`` run by path import ``app`` from site-packages, where no
    config/ exists by construction, so the installed shape needs a root and the
    unit files are where it is stated.
    """

    units = sorted((ROOT / "deploy" / "systemd").glob("coinalyze-*.service"))
    assert units, "no systemd units found"
    checked = 0
    for unit in units:
        source = unit.read_text(encoding="utf-8")
        runs_python = any(
            marker in source for marker in ("/bin/python", "/bin/uvicorn")
        )
        if not runs_python:
            continue
        checked += 1
        assert f"Environment={config.PROJECT_ROOT_ENV}={config.DEPLOYMENT_ROOT}" in source, (
            f"{unit.name} does not declare {config.PROJECT_ROOT_ENV}"
        )
    assert checked, "no unit starts the application"
