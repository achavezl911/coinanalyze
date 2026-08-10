#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any

import asyncpg

from app.config import get_settings
from app.signal_execution import (
    DENSE_PERIODIC,
    EXECUTION_EXCHANGES,
    EXECUTION_SIZES_USD,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
    ExecutionCostOptions,
    build_execution_cost_report,
)
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES


def _sampling_modes(value: str) -> tuple[str, ...]:
    if value == "both":
        return SAMPLING_MODES
    if value == DENSE_PERIODIC:
        return (DENSE_PERIODIC,)
    if value == UTC_NONOVERLAP:
        return (UTC_NONOVERLAP,)
    raise ValueError(f"unsupported sampling mode: {value}")


def _parse_fee(value: str) -> tuple[str, float]:
    exchange, separator, raw_fee = value.partition("=")
    if not separator:
        raise argparse.ArgumentTypeError("fee must use EXCHANGE=BPS")
    exchange = exchange.strip()
    if exchange not in EXECUTION_EXCHANGES:
        raise argparse.ArgumentTypeError(
            f"exchange must be one of {','.join(EXECUTION_EXCHANGES)}"
        )
    try:
        fee = float(raw_fee)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("fee BPS must be numeric") from exc
    return exchange, fee


def _json_default(value: object) -> str:
    return str(value)


def _csv_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for row in report["snapshot_status"]:
        rows.append(
            {
                "sampling_mode": "all_execution_snapshots",
                "view": "snapshot_status",
                **row,
            }
        )

    for row in report["snapshot_cost_distribution"]:
        rows.append(
            {
                "sampling_mode": "all_execution_snapshots",
                "view": "snapshot_cost_distribution",
                **row,
            }
        )

    for mode, view_set in report["views"].items():
        for view_name, view_rows in view_set.items():
            for row in view_rows:
                rows.append(
                    {
                        "sampling_mode": mode,
                        "view": view_name,
                        **row,
                    }
                )
    return rows


def _write_csv(path: Path, report: dict[str, Any]) -> None:
    rows = _csv_rows(report)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    all_fields = set().union(*(row.keys() for row in rows))
    preferred = [
        "sampling_mode",
        "view",
        "symbol",
        "exchange",
        "status",
        "size_usd",
        "horizon_minutes",
        "snapshots",
        "valid_snapshot_n",
        "actionable_evaluated_n",
        "cost_evaluable_n",
        "insufficient_depth_n",
        "gross_expectancy_bps",
        "entry_market_cost_median_bps",
        "entry_market_cost_p90_bps",
        "entry_implementation_shortfall_median_bps",
        "entry_implementation_shortfall_p90_bps",
        "entry_only_market_net_expectancy_bps",
        "symmetric_market_net_expectancy_bps",
        "symmetric_market_net_hit_rate_pct",
        "fee_bps_per_side",
        "modeled_net_after_fees_expectancy_bps",
        "modeled_net_after_fees_hit_rate_pct",
        "gross_positive_survives_market_cost_pct",
        "break_even_fee_per_side_median_bps",
        "meets_min_group_n",
    ]
    fieldnames = [name for name in preferred if name in all_fields]
    fieldnames.extend(sorted(all_fields - set(fieldnames)))

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    options = ExecutionCostOptions(
        lookback_days=args.days,
        symbols=tuple(args.symbol or ()),
        horizons=tuple(args.horizon or OUTCOME_HORIZONS_MINUTES),
        sizes_usd=tuple(args.size_usd or EXECUTION_SIZES_USD),
        sampling_modes=_sampling_modes(args.mode),
        fee_bps_per_side=tuple(args.fee_bps_per_side or ()),
        min_group_n=args.min_group_n,
    )

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_execution_cost_report(conn, options)
    finally:
        await conn.close()

    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    if args.csv:
        _write_csv(args.csv, report)

    corpus = report["corpus"]
    print(
        "Execution-cost report written:",
        args.output,
        f"execution_covered_periodic="
        f"{corpus.get('execution_covered_periodic_observations', 0)}",
        f"mature_outcomes={corpus.get('mature_outcome_rows', 0)}",
        f"missing_outcomes={corpus.get('missing_or_wrong_version_outcome_rows', 0)}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only PR10 taker execution-cost overlay using prospectively frozen "
            "per-venue depth snapshots."
        )
    )
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--symbol", action="append", default=None)
    parser.add_argument(
        "--horizon",
        type=int,
        choices=OUTCOME_HORIZONS_MINUTES,
        action="append",
        default=None,
    )
    parser.add_argument(
        "--size-usd",
        type=float,
        choices=EXECUTION_SIZES_USD,
        action="append",
        default=None,
        help=(
            "Versioned snapshot grid only: "
            + ",".join(str(int(size)) for size in EXECUTION_SIZES_USD)
        ),
    )
    parser.add_argument(
        "--fee-bps-per-side",
        type=_parse_fee,
        action="append",
        default=None,
        metavar="EXCHANGE=BPS",
        help=(
            "Optional explicit taker fee input. Repeat per venue, e.g. "
            "--fee-bps-per-side binance=5. Fees are never invented."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("both", DENSE_PERIODIC, UTC_NONOVERLAP),
        default="both",
    )
    parser.add_argument("--min-group-n", type=int, default=30)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("signal_execution_cost_report.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
