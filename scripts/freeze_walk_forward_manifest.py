#!/usr/bin/env python3
"""Stage A (Freeze): create or idempotently reuse a PR11 walk-forward manifest.

This is the only production write authorized for PR11. It never accepts a
retroactive cutoff: the first OOS cutoff is always the next UTC minute after
``manifest created_at + warmup_days``, computed from the PostgreSQL clock.

PR25 (A3-02) exposes the full scientific version tuple, including the new
``spec_version``/``research_visibility_version`` pair, as explicit flags.
Running the legacy/default command is unchanged: it still resolves spec v1
and ``evidence_version=1`` for ``pr11-fixed-kernel-v1``. Creating a spec-v2
manifest requires explicit operator intent -- every scientific version flag
must be supplied by hand; there is no "latest/current" fallback and spec v1
is never silently mapped onto the spec-v2 tuple.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import asyncpg

from app.config import get_settings
from app.signal_execution import EXECUTION_EXCHANGES, EXECUTION_SIZES_USD
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES
from app.signal_walk_forward import (
    DEFAULT_FOLD_COUNT,
    DEFAULT_MANIFEST_NAME,
    DEFAULT_MIN_GROUP_N,
    DEFAULT_TEST_DAYS,
    DEFAULT_WARMUP_DAYS,
    SUPPORTED_WALK_FORWARD_SPEC_VERSIONS,
    WALK_FORWARD_SPEC_VERSION,
    WalkForwardManifestOptions,
    freeze_walk_forward_manifest,
)

# Spec v1 legacy defaults, preserved exactly so the bare/legacy CLI
# invocation keeps resolving what it always resolved.
_SPEC_V1_DEFAULT_LOGIC_VERSION = WalkForwardManifestOptions().logic_version
_SPEC_V1_DEFAULT_EVIDENCE_VERSION = WalkForwardManifestOptions().evidence_version
_SPEC_V1_DEFAULT_SAMPLING_VERSION = WalkForwardManifestOptions().sampling_version
_SPEC_V1_DEFAULT_CONTEXT_VERSION = WalkForwardManifestOptions().context_version
_SPEC_V1_DEFAULT_OUTCOME_VERSION = WalkForwardManifestOptions().outcome_version
_SPEC_V1_DEFAULT_EXECUTION_SNAPSHOT_VERSION = (
    WalkForwardManifestOptions().execution_snapshot_version
)

# Scientific-version CLI flags that spec v2 requires the operator to supply
# explicitly (argparse dest -> human label used in the fail-closed message).
_SPEC_V2_REQUIRED_FLAGS = (
    ("logic_version", "--logic-version"),
    ("evidence_version", "--evidence-version"),
    ("sampling_version", "--sampling-version"),
    ("context_version", "--context-version"),
    ("outcome_version", "--outcome-version"),
    ("execution_snapshot_version", "--execution-snapshot-version"),
    ("research_visibility_version", "--research-visibility-version"),
)


def _parse_fee(value: str) -> tuple[str, float]:
    exchange, separator, raw_fee = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("fee must use EXCHANGE=BPS")
    exchange = exchange.strip()
    if exchange not in EXECUTION_EXCHANGES:
        raise argparse.ArgumentTypeError(f"exchange must be one of {','.join(EXECUTION_EXCHANGES)}")
    try:
        fee = float(raw_fee)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("fee BPS must be numeric") from exc
    return exchange, fee


def _json_default(value: object) -> str:
    return str(value)


def _build_options(args: argparse.Namespace) -> WalkForwardManifestOptions:
    spec_version = args.spec_version

    if spec_version == WALK_FORWARD_SPEC_VERSION:
        # Legacy/default path: an omitted flag falls back to the exact
        # historical spec-v1 default, never to whatever is "current".
        logic_version = args.logic_version or _SPEC_V1_DEFAULT_LOGIC_VERSION
        evidence_version = (
            args.evidence_version
            if args.evidence_version is not None
            else _SPEC_V1_DEFAULT_EVIDENCE_VERSION
        )
        sampling_version = (
            args.sampling_version
            if args.sampling_version is not None
            else _SPEC_V1_DEFAULT_SAMPLING_VERSION
        )
        context_version = (
            args.context_version
            if args.context_version is not None
            else _SPEC_V1_DEFAULT_CONTEXT_VERSION
        )
        outcome_version = (
            args.outcome_version
            if args.outcome_version is not None
            else _SPEC_V1_DEFAULT_OUTCOME_VERSION
        )
        execution_snapshot_version = (
            args.execution_snapshot_version
            if args.execution_snapshot_version is not None
            else _SPEC_V1_DEFAULT_EXECUTION_SNAPSHOT_VERSION
        )
        if args.research_visibility_version is not None:
            raise SystemExit(
                "--research-visibility-version requires --spec-version 2"
            )
        research_visibility_version = None
    else:
        # Spec v2: fail closed unless every scientific version flag was
        # explicitly supplied. No default, no inference, no mapping from v1.
        missing = [
            flag
            for dest, flag in _SPEC_V2_REQUIRED_FLAGS
            if getattr(args, dest) is None
        ]
        if missing:
            raise SystemExit(
                "--spec-version 2 requires explicit "
                f"{', '.join(missing)}; refusing to infer a scientific version tuple"
            )
        logic_version = args.logic_version
        evidence_version = args.evidence_version
        sampling_version = args.sampling_version
        context_version = args.context_version
        outcome_version = args.outcome_version
        execution_snapshot_version = args.execution_snapshot_version
        research_visibility_version = args.research_visibility_version

    return WalkForwardManifestOptions(
        name=args.name,
        warmup_days=args.warmup_days,
        test_days=args.test_days,
        fold_count=args.fold_count,
        min_group_n=args.min_group_n,
        horizons=tuple(args.horizon or OUTCOME_HORIZONS_MINUTES),
        symbols=tuple(args.symbol or ()),
        exchanges=tuple(args.exchange or EXECUTION_EXCHANGES),
        sizes_usd=tuple(args.size_usd or EXECUTION_SIZES_USD),
        fee_bps_per_side=tuple(args.fee_bps_per_side or ()),
        logic_version=logic_version,
        evidence_version=evidence_version,
        sampling_version=sampling_version,
        context_version=context_version,
        outcome_version=outcome_version,
        execution_snapshot_version=execution_snapshot_version,
        spec_version=spec_version,
        research_visibility_version=research_visibility_version,
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    options = _build_options(args)
    settings = get_settings()

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        async with conn.transaction(isolation="serializable"):
            manifest = await freeze_walk_forward_manifest(conn, options)
    finally:
        await conn.close()
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze (or idempotently reuse) an immutable PR11 walk-forward "
            "manifest. The first OOS cutoff is always in the future; there "
            "is no retroactive-cutoff option."
        )
    )
    parser.add_argument("--name", default=DEFAULT_MANIFEST_NAME)
    parser.add_argument("--warmup-days", type=int, default=DEFAULT_WARMUP_DAYS)
    parser.add_argument("--test-days", type=int, default=DEFAULT_TEST_DAYS)
    parser.add_argument("--fold-count", type=int, default=DEFAULT_FOLD_COUNT)
    parser.add_argument("--min-group-n", type=int, default=DEFAULT_MIN_GROUP_N)
    parser.add_argument(
        "--horizon", type=int, choices=OUTCOME_HORIZONS_MINUTES, action="append", default=None
    )
    parser.add_argument("--symbol", action="append", default=None)
    parser.add_argument("--exchange", choices=EXECUTION_EXCHANGES, action="append", default=None)
    parser.add_argument(
        "--size-usd", type=float, choices=EXECUTION_SIZES_USD, action="append", default=None
    )
    parser.add_argument(
        "--fee-bps-per-side",
        type=_parse_fee,
        action="append",
        default=None,
        metavar="EXCHANGE=BPS",
        help="Optional explicit taker fee scenario to freeze into the manifest. Empty by default.",
    )
    parser.add_argument(
        "--spec-version",
        type=int,
        choices=SUPPORTED_WALK_FORWARD_SPEC_VERSIONS,
        default=WALK_FORWARD_SPEC_VERSION,
        help=(
            "PR11 evaluation spec version. Defaults to the frozen spec v1 "
            "contract. Spec v2 (the certificate-gated knowledge-time "
            "contract) requires every scientific version flag below to be "
            "supplied explicitly."
        ),
    )
    parser.add_argument(
        "--logic-version",
        default=None,
        help="Defaults to the historical spec-v1 logic_version when omitted under --spec-version 1.",
    )
    parser.add_argument(
        "--evidence-version",
        type=int,
        default=None,
        help="Defaults to the historical spec-v1 evidence_version (1) when omitted under --spec-version 1.",
    )
    parser.add_argument(
        "--sampling-version",
        type=int,
        default=None,
        help="Defaults to the historical spec-v1 sampling_version when omitted under --spec-version 1.",
    )
    parser.add_argument(
        "--context-version",
        type=int,
        default=None,
        help="Defaults to the historical spec-v1 context_version when omitted under --spec-version 1.",
    )
    parser.add_argument(
        "--outcome-version",
        type=int,
        default=None,
        help="Defaults to the historical spec-v1 outcome_version when omitted under --spec-version 1.",
    )
    parser.add_argument(
        "--execution-snapshot-version",
        type=int,
        default=None,
        help=(
            "Defaults to the historical spec-v1 execution_snapshot_version "
            "when omitted under --spec-version 1."
        ),
    )
    parser.add_argument(
        "--research-visibility-version",
        type=int,
        default=None,
        help="Required under --spec-version 2; must not be set under spec v1.",
    )
    parser.add_argument("--output", type=Path, default=Path("walk_forward_manifest.json"))
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    manifest = asyncio.run(_run(args))
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    print(
        "Walk-forward manifest written:",
        args.output,
        f"manifest_id={manifest['manifest_id']}",
        f"manifest_name={manifest['manifest_name']}",
        f"manifest_hash={manifest['manifest_hash']}",
        f"cutoff_at={manifest['cutoff_at']}",
        f"reused_existing={manifest['reused_existing']}",
    )


if __name__ == "__main__":
    main()
