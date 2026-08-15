"""One identity measurement, executed inside a mutated tree.

The harness copies this file to the root of the tree under test and runs it as
a standalone script with ``cwd`` set to that root, so ``import app`` resolves to
the mutated sources and nothing else.  It must therefore not import anything
from :mod:`tests.identity_mutation`.

Output protocol: arbitrary library logging on stdout, then the sentinel line
``===PROBE_JSON===``, then exactly one JSON object.  Everything before the
sentinel is discarded by the harness.

What is measured
----------------

``code_digest``
    ``compute_scientific_implementation_identity()`` -- what the code computes.

``environment_digest``
    ``compute_scientific_runtime_contract()`` -- which raw inputs the code
    selected, resolved at call time from the environment and the versioned
    market catalog.  This is the identity's environment half; it is a separate
    registered digest, not a component of the code one.

``total_digest``
    A deterministic hash over both, and ``null`` if either half is unavailable.
    A missing half is never silently reported as movement.

``validation_accepted``
    Whether a *previously frozen* identity object -- the one measured on the
    pristine baseline tree, handed to this process as a file -- is still
    accepted here.  After a material mutation it must not be.

``forged_object_accepted``
    Whether an identity object recomputed *in this tree* is accepted.  It is
    self-consistent by construction, so this is the question a digest chain
    cannot answer: is there anything anchoring the registry outside the tree it
    describes?

Exceptions are reported as data.  A crashed measurement is a result, not a
silent zero.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import types
from pathlib import Path

SENTINEL = "===PROBE_JSON==="
STORED_IDENTITY_FILE = "_identity_mutation_stored.json"
RUNTIME_PATCH_ENV = "IDENTITY_MUTATION_RUNTIME_PATCH"
SANITIZE_ENV = "IDENTITY_MUTATION_SANITIZE"


# --- deterministic reporting ------------------------------------------------


def _sanitize(text: str) -> str:
    """Strip anything that would make the evidence machine-specific.

    Temporary roots, the interpreter path and any other absolute path would
    otherwise leak into ``validation_error`` and make byte-for-byte
    regeneration impossible.
    """

    if not text:
        return text
    replacements = json.loads(os.environ.get(SANITIZE_ENV) or "[]")
    for needle, placeholder in replacements:
        if needle:
            text = text.replace(needle, placeholder)
    cleaned: list[str] = []
    for token in text.split(" "):
        stripped = token.strip("'\"()[],")
        if stripped.startswith("/") and "/" in stripped[1:]:
            token = token.replace(stripped, "<PATH>")
        cleaned.append(token)
    return " ".join(cleaned)


def _describe(exc: BaseException) -> str:
    return _sanitize(f"{type(exc).__name__}: {exc}")


# --- runtime escapes --------------------------------------------------------
#
# These reproduce escapes that do not touch the filesystem.  Attribute
# reassignment, ``__code__`` transplants and ``sys.modules`` surgery are
# authorized here and nowhere else: an in-process escape cannot be demonstrated
# without performing it.


def _patch_neutralize_identity_validator() -> None:
    """M-01: replace the validator with a function that accepts anything.

    The post-condition is behavioural, not an attribute comparison: the
    untouched validator raises ``ValueError`` on this input, so getting the
    object back proves the replacement is on the path the probe executes.
    """

    import app.signal_scientific_identity as identity_module

    identity_module.validate_scientific_implementation_identity = lambda stored: stored

    sentinel = {"identity_version": "not-an-integer"}
    if identity_module.validate_scientific_implementation_identity(sentinel) is not sentinel:
        raise RuntimeError("validator reassignment did not take effect")


def _patch_swap_code_object() -> None:
    """M-05: transplant another function's code into a material symbol.

    The post-condition calls the symbol.  ``spot_pairs`` would raise on a
    ``None`` routing, so a plain return value proves the transplanted code is
    what actually runs.
    """

    import app.ws_collector as ws_collector

    def _decoy(symbols: tuple[str, ...], routing: object) -> tuple[str, ...]:
        return tuple("ETHUSDT" for _ in symbols)

    ws_collector.spot_pairs.__code__ = _decoy.__code__

    if ws_collector.spot_pairs(("BTCUSDT_PERP.A",), None) != ("ETHUSDT",):
        raise RuntimeError("__code__ transplant did not take effect")


def _patch_inject_synthetic_module() -> None:
    """M-06: register a stand-in module whose file lives outside the surface.

    The post-condition resolves the name through ``importlib``, so what is
    verified is that an importer of ``app.ws_collector`` gets the stand-in --
    not merely that a dictionary key was set.
    """

    import importlib

    outside = Path(os.environ.get("IDENTITY_MUTATION_OUTSIDE", "/nonexistent"))
    synthetic = types.ModuleType("app.ws_collector")
    synthetic.__file__ = str(outside / "ws_collector.py")
    synthetic.spot_pairs = lambda symbols, routing: tuple("ETHUSDT" for _ in symbols)
    sys.modules["app.ws_collector"] = synthetic

    resolved = importlib.import_module("app.ws_collector")
    if resolved is not synthetic:
        raise RuntimeError("synthetic module was not the one importers resolve")
    if Path(resolved.__file__).resolve().is_relative_to(Path.cwd().resolve()):
        raise RuntimeError("synthetic module __file__ is inside the surface")


_RUNTIME_PATCHES = {
    "neutralize_identity_validator": _patch_neutralize_identity_validator,
    "swap_code_object": _patch_swap_code_object,
    "inject_synthetic_module": _patch_inject_synthetic_module,
}


# --- measurement ------------------------------------------------------------


def _total_digest(code_digest: str | None, environment_digest: str | None) -> str | None:
    if code_digest is None or environment_digest is None:
        return None
    payload = json.dumps(
        {"code_digest": code_digest, "environment_digest": environment_digest},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def measure() -> dict[str, object]:
    result: dict[str, object] = {
        "code_digest": None,
        "environment_digest": None,
        "total_digest": None,
        "validation_accepted": False,
        "validation_error": None,
        "forged_object_accepted": False,
        "exception": None,
        "identity_object": None,
        "interpreter": f"{sys.version_info.major}.{sys.version_info.minor}",
    }
    failures: list[str] = []

    patch_name = os.environ.get(RUNTIME_PATCH_ENV) or ""
    if patch_name:
        try:
            _RUNTIME_PATCHES[patch_name]()
        except Exception as exc:  # pragma: no cover - reported, never raised
            failures.append(f"runtime_patch {patch_name} failed -> {_describe(exc)}")

    identity_module = None
    identity: dict[str, object] | None = None
    try:
        import app.signal_scientific_identity as identity_module

        identity = identity_module.compute_scientific_implementation_identity()
        result["code_digest"] = identity["digest"]
        result["identity_object"] = identity
    except Exception as exc:  # pragma: no cover - reported, never raised
        failures.append(f"code digest failed -> {_describe(exc)}")

    try:
        from app.signal_runtime_contract import compute_scientific_runtime_contract

        result["environment_digest"] = compute_scientific_runtime_contract()["digest"]
    except Exception as exc:  # pragma: no cover - reported, never raised
        failures.append(f"environment digest failed -> {_describe(exc)}")

    result["total_digest"] = _total_digest(
        result["code_digest"],  # type: ignore[arg-type]
        result["environment_digest"],  # type: ignore[arg-type]
    )

    stored_path = Path(STORED_IDENTITY_FILE)
    if identity_module is None:
        result["validation_error"] = "identity module unavailable"
    elif not stored_path.is_file():
        result["validation_error"] = "no frozen identity supplied"
    else:
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        validator = identity_module.validate_scientific_implementation_identity
        try:
            validator(stored)
            result["validation_accepted"] = True
        except Exception as exc:
            result["validation_accepted"] = False
            result["validation_error"] = _describe(exc)

    if identity_module is not None and identity is not None:
        # The forger's object: recomputed here, internally consistent, and
        # carrying whatever digest this tree happens to produce.
        validator = identity_module.validate_scientific_implementation_identity
        try:
            validator(json.loads(json.dumps(identity)))
            result["forged_object_accepted"] = True
        except Exception:
            result["forged_object_accepted"] = False

    if failures:
        result["exception"] = _sanitize(" | ".join(failures))
    return result


def main() -> int:
    try:
        payload = measure()
    except BaseException as exc:  # pragma: no cover - a crash is still a result
        payload = {
            "code_digest": None,
            "environment_digest": None,
            "total_digest": None,
            "validation_accepted": False,
            "validation_error": None,
            "forged_object_accepted": False,
            "exception": _describe(exc),
            "identity_object": None,
            "interpreter": f"{sys.version_info.major}.{sys.version_info.minor}",
        }
    sys.stdout.write(SENTINEL + "\n")
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
