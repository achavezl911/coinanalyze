#!/usr/bin/env python3
"""Stage A (Freeze): create or idempotently reuse a PR11 walk-forward manifest.

This is the only production write authorized for PR11. It never accepts a
retroactive cutoff: the first OOS cutoff is always the next UTC minute after
``manifest created_at + warmup_days``, computed from the PostgreSQL clock.
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
    WalkForwardManifestOptions,
    freeze_walk_forward_manifest,
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


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    options = WalkForwardManifestOptions(
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
    )

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        async with conn.transaction(isolation="serializable"):
            manifest = await freeze_walk_forward_manifest(conn, options)
    finally:
        await conn.close()
    return manifest


def main() -> None:
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
    parser.add_argument("--output", type=Path, default=Path("walk_forward_manifest.json"))
    args = parser.parse_args()

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
