#!/usr/bin/env python3
"""Entry point for regenerating and checking identity/registry.json.

    python scripts/register_identity.py [--check]

``--check`` regenerates in memory and exits non-zero if the committed registry
differs, which is what CI runs.  Without it the file is rewritten, which is what
a legitimate change to the scientific surface requires -- and, precisely
because a legitimate change and a forgery are indistinguishable from inside the
tree, what commit 3.3 anchors from outside it.

**No decision is taken here.**  What gets registered and what ``--check``
compares live in :mod:`app.signal_scientific_identity`, inside the scientific
surface, so that altering either moves the code digest.  While both halves lived
in this file, whoever could edit it controlled the generator *and* the check,
and a tree that had been rewritten agreed with itself -- the same failure mode
as M-02, one directory across.  This module parses two arguments and prints.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # pragma: no cover - script entry point
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.signal_scientific_identity import (  # noqa: E402
    check_identity_registry,
    resolve_surface_root,
    write_identity_registry,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/register_identity.py")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of rewriting when the committed registry is stale",
    )
    args = parser.parse_args(argv)

    if args.check:
        ok, message = check_identity_registry()
        print(message, file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1

    print(f"registered {resolve_surface_root()} in {write_identity_registry()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
