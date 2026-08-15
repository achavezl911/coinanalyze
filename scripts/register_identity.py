#!/usr/bin/env python3
"""Regenerate identity/registry.json from the tree it is run in.

The registry is generated, never hand-written: the code digest, the per
component manifest and the enumerated environment profiles all come from the
same functions the runtime validates with, so a registry that disagrees with
the code is a registry that could not have been produced by this script.

    python scripts/register_identity.py [--check]

``--check`` regenerates in memory and exits non-zero if the committed registry
differs, which is what CI runs.  Without it the file is rewritten, which is what
a legitimate change to the scientific surface requires -- and, precisely
because a legitimate change and a forgery are indistinguishable from inside the
tree, what commit 3.3 anchors from outside it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover - script entry point
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.signal_runtime_contract import (  # noqa: E402
    AUTHORIZED_COLLECTOR_SHARD_PROFILES,
    AUTHORIZED_ENVIRONMENT_FIXED,
    AUTHORIZED_INTERPRETERS,
    SCIENTIFIC_RUNTIME_CONTRACT_CANONICALIZER,
    SCIENTIFIC_RUNTIME_CONTRACT_VERSION_V1,
    enumerate_authorized_environment_profiles,
)
from app.signal_scientific_identity import (  # noqa: E402
    IDENTITY_REGISTRY_SCHEMA_VERSION,
    SCIENTIFIC_IDENTITY_CANONICALIZER,
    SCIENTIFIC_IDENTITY_VERSION_V1,
    compute_scientific_implementation_identity,
    identity_registry_path,
    resolve_surface_root,
)


def build_registry() -> dict[str, object]:
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


def serialize(registry: dict[str, object]) -> str:
    return json.dumps(registry, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/register_identity.py")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting when the committed registry is stale",
    )
    args = parser.parse_args(argv)

    serialized = serialize(build_registry())
    path = identity_registry_path()
    if args.check:
        if not path.is_file():
            print(f"{path} does not exist", file=sys.stderr)
            return 1
        if path.read_text(encoding="utf-8") != serialized:
            print(
                f"{path} is stale: the tree no longer computes the registered "
                "identity.  Run scripts/register_identity.py and review the diff.",
                file=sys.stderr,
            )
            return 1
        print(f"{path} matches the tree")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")
    print(f"registered {resolve_surface_root()} in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
