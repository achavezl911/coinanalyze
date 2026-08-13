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
from app.signal_confirmatory import CONFIRMATORY_BLOCK_UNITS, ConfirmatoryContract
from app.signal_execution import EXECUTION_EXCHANGES, EXECUTION_SIZES_USD, UTC_NONOVERLAP
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES
from app.signal_walk_forward import (
    DEFAULT_FOLD_COUNT,
    DEFAULT_MANIFEST_NAME,
    DEFAULT_MIN_GROUP_N,
    DEFAULT_TEST_DAYS,
    DEFAULT_WARMUP_DAYS,
    SUPPORTED_WALK_FORWARD_SPEC_VERSIONS,
    WALK_FORWARD_SPEC_VERSION,
    WALK_FORWARD_SPEC_VERSION_V2,
    WALK_FORWARD_SPEC_VERSION_V3,
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

# PR26: spec v3 inherits every _SPEC_V2_REQUIRED_FLAGS entry above exactly
# (the identical PR25 evidence6/research_visibility1 tuple) PLUS one flag
# per ConfirmatoryContract field below -- every one of the 19 confirmatory
# fields must be supplied explicitly, no default, no inference, no mapping
# from a "current/live" constant.
_CONFIRMATORY_REQUIRED_FLAGS = (
    ("primary_endpoint_version", "--primary-endpoint-version"),
    ("primary_symbol", "--primary-symbol"),
    ("primary_horizon_minutes", "--primary-horizon"),
    ("primary_sampling_mode", "--primary-sampling-mode"),
    ("primary_exchange", "--primary-exchange"),
    ("primary_size_usd", "--primary-size-usd"),
    ("primary_taker_fee_bps", "--primary-taker-fee-bps"),
    ("baseline_version", "--confirmatory-baseline-version"),
    ("unmodeled_execution_stress_bps", "--unmodeled-execution-stress-bps"),
    ("inference_version", "--confirmatory-inference-version"),
    ("block_unit", "--confirmatory-block-unit"),
    ("block_length", "--confirmatory-block-length"),
    ("bootstrap_repetitions", "--bootstrap-repetitions"),
    ("bootstrap_seed", "--bootstrap-seed"),
    ("confidence_level", "--confidence-level"),
    ("minimum_effect_bps", "--minimum-effect-bps"),
    ("minimum_primary_blocks", "--minimum-primary-blocks"),
    ("minimum_execution_data_coverage_pct", "--minimum-execution-data-coverage-pct"),
    ("confirmatory_decision_policy", "--confirmatory-decision-policy"),
)
_SPEC_V3_REQUIRED_FLAGS = _SPEC_V2_REQUIRED_FLAGS + _CONFIRMATORY_REQUIRED_FLAGS


def _reject_confirmatory_flags_outside_v3(args: argparse.Namespace) -> None:
    provided = [
        flag
        for dest, flag in _CONFIRMATORY_REQUIRED_FLAGS
        if getattr(args, dest) is not None
    ]
    if args.acknowledge_confirmatory_primary_hypothesis:
        provided.append("--acknowledge-confirmatory-primary-hypothesis")
    if provided:
        raise SystemExit(
            "confirmatory contract flags require --spec-version 3; unexpected: "
            f"{', '.join(provided)}"
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
    confirmatory_contract: ConfirmatoryContract | None = None

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
                "--research-visibility-version requires --spec-version 2 or 3"
            )
        research_visibility_version = None
        _reject_confirmatory_flags_outside_v3(args)
    elif spec_version == WALK_FORWARD_SPEC_VERSION_V2:
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
        _reject_confirmatory_flags_outside_v3(args)
    else:
        assert spec_version == WALK_FORWARD_SPEC_VERSION_V3
        # Spec v3 (PR26): fail closed unless every v2 scientific-version flag
        # AND every confirmatory-contract flag was explicitly supplied, and
        # the operator affirmatively acknowledged the single primary
        # hypothesis being frozen. No silent v1/v2 default anywhere here.
        missing = [
            flag
            for dest, flag in _SPEC_V3_REQUIRED_FLAGS
            if getattr(args, dest) is None
        ]
        if missing:
            raise SystemExit(
                "--spec-version 3 requires explicit "
                f"{', '.join(missing)}; refusing to infer a scientific version "
                "tuple or a confirmatory contract"
            )
        if not args.acknowledge_confirmatory_primary_hypothesis:
            raise SystemExit(
                "--spec-version 3 requires "
                "--acknowledge-confirmatory-primary-hypothesis, naming the single "
                f"primary hypothesis about to be frozen: symbol={args.primary_symbol!r} "
                f"horizon_minutes={args.primary_horizon_minutes!r} "
                f"sampling_mode={args.primary_sampling_mode!r} "
                f"exchange={args.primary_exchange!r} size_usd={args.primary_size_usd!r}"
            )
        logic_version = args.logic_version
        evidence_version = args.evidence_version
        sampling_version = args.sampling_version
        context_version = args.context_version
        outcome_version = args.outcome_version
        execution_snapshot_version = args.execution_snapshot_version
        research_visibility_version = args.research_visibility_version
        confirmatory_contract = ConfirmatoryContract(
            primary_endpoint_version=args.primary_endpoint_version,
            primary_symbol=args.primary_symbol,
            primary_horizon_minutes=args.primary_horizon_minutes,
            primary_sampling_mode=args.primary_sampling_mode,
            primary_exchange=args.primary_exchange,
            primary_size_usd=args.primary_size_usd,
            primary_taker_fee_bps=args.primary_taker_fee_bps,
            baseline_version=args.baseline_version,
            unmodeled_execution_stress_bps=args.unmodeled_execution_stress_bps,
            inference_version=args.inference_version,
            block_unit=args.block_unit,
            block_length=args.block_length,
            bootstrap_repetitions=args.bootstrap_repetitions,
            bootstrap_seed=args.bootstrap_seed,
            confidence_level=args.confidence_level,
            minimum_effect_bps=args.minimum_effect_bps,
            minimum_primary_blocks=args.minimum_primary_blocks,
            minimum_execution_data_coverage_pct=(
                args.minimum_execution_data_coverage_pct
            ),
            confirmatory_decision_policy=args.confirmatory_decision_policy,
        )

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
        confirmatory_contract=confirmatory_contract,
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
            "supplied explicitly. Spec v3 (PR26, the confirmatory "
            "walk-forward contract) requires those same flags PLUS every "
            "confirmatory-contract flag below, plus "
            "--acknowledge-confirmatory-primary-hypothesis."
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
        help="Required under --spec-version 2 or 3; must not be set under spec v1.",
    )

    # PR26: spec v3 confirmatory contract. Every flag below is required
    # under --spec-version 3 and forbidden under spec v1/v2 -- no default,
    # no inference, no "latest/current" fallback.
    parser.add_argument(
        "--primary-endpoint-version",
        type=int,
        default=None,
        help="Confirmatory primary economic endpoint version. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--primary-symbol",
        default=None,
        help="The single confirmatory primary symbol. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--primary-horizon",
        type=int,
        choices=OUTCOME_HORIZONS_MINUTES,
        default=None,
        dest="primary_horizon_minutes",
        help="The single confirmatory primary horizon. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--primary-sampling-mode",
        choices=(UTC_NONOVERLAP,),
        default=None,
        help=(
            "The single confirmatory primary sampling mode; must be "
            "utc_nonoverlap -- dense_periodic is descriptive only and can "
            "never be primary. Required under --spec-version 3."
        ),
    )
    parser.add_argument(
        "--primary-exchange",
        choices=EXECUTION_EXCHANGES,
        default=None,
        help="The single confirmatory primary exchange. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--primary-size-usd",
        type=float,
        choices=EXECUTION_SIZES_USD,
        default=None,
        help="The single confirmatory primary execution size. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--primary-taker-fee-bps",
        type=float,
        default=None,
        help=(
            "Explicit confirmatory taker fee in bps; must equal the "
            "--fee-bps-per-side value frozen for --primary-exchange. "
            "Required under --spec-version 3."
        ),
    )
    parser.add_argument(
        "--confirmatory-baseline-version",
        type=int,
        default=None,
        dest="baseline_version",
        help="Clock/direction-matched baseline algorithm version. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--unmodeled-execution-stress-bps",
        type=float,
        default=None,
        help=(
            "Frozen non-negative bps stress for unmodeled exit/funding/latency "
            "risk. PR26 does not choose this value -- the operator freezing "
            "the manifest must supply it explicitly. Required under --spec-version 3."
        ),
    )
    parser.add_argument(
        "--confirmatory-inference-version",
        type=int,
        default=None,
        dest="inference_version",
        help="Block-bootstrap inference algorithm version. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--confirmatory-block-unit",
        choices=CONFIRMATORY_BLOCK_UNITS,
        default=None,
        dest="block_unit",
        help="Calendar block unit for the block bootstrap. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--confirmatory-block-length",
        type=int,
        default=None,
        dest="block_length",
        help="Calendar block length multiplier. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--bootstrap-repetitions",
        type=int,
        default=None,
        help="Number of block-bootstrap resampling repetitions. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=None,
        help="Frozen deterministic seed for the block bootstrap. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--confidence-level",
        type=float,
        default=None,
        help="Confidence level (0,1) for the block-bootstrap CI. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--minimum-effect-bps",
        type=float,
        default=None,
        help=(
            "Minimum economically relevant effect in bps compared against the "
            "CI lower bound. Required under --spec-version 3."
        ),
    )
    parser.add_argument(
        "--minimum-primary-blocks",
        type=int,
        default=None,
        help="Minimum matured primary blocks required to decide. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--minimum-execution-data-coverage-pct",
        type=float,
        default=None,
        help="Minimum execution-data coverage percent required to decide. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--confirmatory-decision-policy",
        default=None,
        help="Fixed confirmatory decision policy identifier. Required under --spec-version 3.",
    )
    parser.add_argument(
        "--acknowledge-confirmatory-primary-hypothesis",
        action="store_true",
        default=False,
        help=(
            "Required under --spec-version 3: explicit operator acknowledgement "
            "of the single primary symbol/horizon/sampling-mode/exchange/size "
            "hypothesis about to be frozen. Forbidden under spec v1/v2."
        ),
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
