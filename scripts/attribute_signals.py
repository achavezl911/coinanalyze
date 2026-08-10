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
from app.signal_attribution import (
    DEFAULT_GROUP_BY,
    SCALP_COMPONENTS,
    AttributionOptions,
    build_signal_attribution_report,
)
from app.signal_backtest import (
    ALLOWED_GROUP_DIMENSIONS,
    DENSE_PERIODIC,
    SAMPLING_MODES,
    UTC_NONOVERLAP,
)
from app.signal_ledger import SIGNAL_EVIDENCE_VERSION, SIGNAL_SAMPLING_VERSION
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
        "component",
        "configured_weight",
        "horizon_minutes",
        "mature_outcomes",
        "outcome_evaluated_n",
        "component_measured_evaluated_n",
        "component_missing_evaluated_n",
        "component_measured_pct",
        "missing_semantics_mismatch_observations",
        "standalone_directional_n",
        "standalone_directional_expectancy_pct",
        "standalone_directional_hit_rate_pct",
        "component_market_return_corr",
        "actionable_evaluated_n",
        "decision_component_measured_n",
        "aligned_strength_directional_return_corr",
        "supports_decision_n",
        "supports_decision_expectancy_pct",
        "supports_decision_hit_rate_pct",
        "opposes_decision_n",
        "opposes_decision_expectancy_pct",
        "opposes_decision_hit_rate_pct",
        "support_minus_oppose_expectancy_pct",
        "support_minus_oppose_hit_rate_pp",
        "standalone_meets_min_group_n",
        "market_corr_meets_min_group_n",
        "decision_lens_meets_min_group_n",
        "support_vs_oppose_meets_min_group_n",
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
    components = tuple(args.component or SCALP_COMPONENTS)
    group_by = _parse_csv_tuple(args.group_by)

    options = AttributionOptions(
        lookback_days=args.days,
        symbols=symbols,
        horizons=horizons,
        components=components,
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
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await build_signal_attribution_report(conn, options)
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
        "Attribution report written:",
        args.output,
        f"compatible_periodic={corpus.get('compatible_periodic_observations', 0)}",
        f"mature_outcomes={corpus.get('mature_outcome_rows', 0)}",
        f"missing_outcomes={corpus.get('missing_or_wrong_version_outcome_rows', 0)}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only univariate attribution over immutable "
            "signal_observation + signal_replay_frame + signal_outcome."
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
        "--component",
        choices=SCALP_COMPONENTS,
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
        default=",".join(DEFAULT_GROUP_BY),
        help=(
            "Comma-separated dimensions. Allowed: "
            + ",".join(sorted(ALLOWED_GROUP_DIMENSIONS))
        ),
    )
    parser.add_argument("--min-group-n", type=int, default=30)
    parser.add_argument("--logic-version", default=SCALP_SIGNAL_LOGIC_VERSION)
    parser.add_argument("--evidence-version", type=int, default=SIGNAL_EVIDENCE_VERSION)
    parser.add_argument("--sampling-version", type=int, default=SIGNAL_SAMPLING_VERSION)
    parser.add_argument("--context-version", type=int, default=REPLAY_CONTEXT_VERSION)
    parser.add_argument("--outcome-version", type=int, default=OUTCOME_VERSION)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("signal_attribution_report.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
