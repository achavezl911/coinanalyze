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
from app.signal_backtest import (
    ALLOWED_GROUP_DIMENSIONS,
    DEFAULT_EVIDENCE_VERSION,
    DENSE_PERIODIC,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
    BacktestOptions,
    build_signal_backtest_report,
)
from app.signal_ledger import SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION


def _parse_csv_tuple(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _sampling_modes(value: str) -> tuple[str, ...]:
    if value == "both":
        return SAMPLING_MODES
    if value == DENSE_PERIODIC:
        return (DENSE_PERIODIC,)
    if value == UTC_NONOVERLAP:
        return (UTC_NONOVERLAP,)
    raise ValueError(f"unsupported sampling mode: {value}")


def _json_default(value: object) -> str:
    return str(value)


def _csv_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mode, view in report["views"].items():
        for row in view["groups"]:
            rows.append({"sampling_mode": mode, **row})
    return rows


def _write_csv(path: Path, report: dict[str, Any]) -> None:
    rows = _csv_rows(report)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    preferred = [
        "sampling_mode",
        *report["group_by"],
        "horizon_minutes",
        "mature_outcomes",
        "outcome_evaluated_n",
        "outcome_pending_n",
        "outcome_not_evaluable_n",
        "decision_evaluable_n",
        "decision_not_evaluable_n",
        "actionable_mature_n",
        "actionable_evaluated_n",
        "actionable_outcome_coverage_pct",
        "gross_expectancy_pct",
        "gross_hit_rate_pct",
        "directional_return_median_pct",
        "directional_return_p10_pct",
        "directional_return_p90_pct",
        "average_winner_pct",
        "average_loser_pct",
        "payoff_ratio",
        "observation_profit_factor",
        "mfe_median_pct",
        "mfe_p90_pct",
        "mae_median_pct",
        "mae_p90_pct",
        "neutral_evaluated_n",
        "neutral_abs_market_return_median_pct",
        "neutral_abs_market_return_p90_pct",
        "actionable_meets_min_group_n",
        "neutral_meets_min_group_n",
    ]
    all_fields = set().union(*(row.keys() for row in rows))
    fieldnames = [field for field in preferred if field in all_fields]
    fieldnames.extend(sorted(all_fields - set(fieldnames)))

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def _run(args: argparse.Namespace) -> None:
    settings = get_settings()
    horizons = tuple(args.horizon or OUTCOME_HORIZONS_MINUTES)
    symbols = tuple(args.symbol or ())
    group_by = _parse_csv_tuple(args.group_by)

    options = BacktestOptions(
        lookback_days=args.days,
        symbols=symbols,
        horizons=horizons,
        group_by=group_by,
        sampling_modes=_sampling_modes(args.mode),
        min_group_n=args.min_group_n,
        logic_version=args.logic_version,
        evidence_version=args.evidence_version,
        sampling_version=args.sampling_version,
        context_version=args.context_version,
        outcome_version=args.outcome_version,
    )

    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        # One consistent read snapshot while collectors keep writing.
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_backtest_report(conn, options)
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
        "Backtest report written:",
        args.output,
        f"compatible_periodic={corpus.get('compatible_periodic_observations', 0)}",
        f"mature_outcomes={corpus.get('mature_outcome_rows', 0)}",
        f"missing_outcomes={corpus.get('missing_or_wrong_version_outcome_rows', 0)}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Research backtest over immutable signal_observation + "
            "signal_replay_frame + signal_outcome."
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
        "--mode",
        choices=("both", DENSE_PERIODIC, UTC_NONOVERLAP),
        default="both",
    )
    parser.add_argument(
        "--group-by",
        default="symbol,state,confidence,direction",
        help=(
            "Comma-separated dimensions. Allowed: "
            + ",".join(sorted(ALLOWED_GROUP_DIMENSIONS))
        ),
    )
    parser.add_argument("--min-group-n", type=int, default=30)
    parser.add_argument("--logic-version", default=SCALP_SIGNAL_LOGIC_VERSION)
    parser.add_argument("--evidence-version", type=int, default=DEFAULT_EVIDENCE_VERSION)
    parser.add_argument("--sampling-version", type=int, default=SIGNAL_SAMPLING_VERSION)
    parser.add_argument("--context-version", type=int, default=REPLAY_CONTEXT_VERSION)
    parser.add_argument("--outcome-version", type=int, default=OUTCOME_VERSION)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("signal_backtest_report.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
