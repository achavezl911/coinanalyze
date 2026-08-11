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
from app.signal_attribution import SCALP_COMPONENTS
from app.signal_backtest import DENSE_PERIODIC, SAMPLING_MODES, UTC_NONOVERLAP
from app.signal_ledger import SIGNAL_SAMPLING_VERSION
from app.signal_outcomes import OUTCOME_HORIZONS_MINUTES, OUTCOME_VERSION
from app.signal_regime import (
    DEFAULT_EVIDENCE_VERSION,
    RegimeAnalysisOptions,
    build_signal_regime_report,
)
from app.signal_replay import REPLAY_CONTEXT_VERSION, SCALP_SIGNAL_LOGIC_VERSION


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

    for row in report["regime_distribution"]:
        rows.append({"sampling_mode": "all_periodic", "view": "regime_distribution", **row})

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
        "regime_status",
        "regime_label",
        "regime_score_band",
        "regime_alignment",
        "component",
        "configured_weight",
        "horizon_minutes",
        "observations",
        "observation_share_pct",
        "actionable_evaluated_n",
        "gross_expectancy_pct",
        "gross_hit_rate_pct",
        "expectancy_lift_vs_symbol_pct",
        "hit_rate_lift_vs_symbol_pp",
        "standalone_directional_n",
        "standalone_directional_expectancy_pct",
        "standalone_expectancy_lift_vs_available_regimes_pct",
        "component_market_return_corr",
        "supports_decision_n",
        "supports_decision_expectancy_pct",
        "opposes_decision_n",
        "opposes_decision_expectancy_pct",
        "missing_semantics_mismatch_observations",
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
    options = RegimeAnalysisOptions(
        lookback_days=args.days,
        symbols=tuple(args.symbol or ()),
        horizons=tuple(args.horizon or OUTCOME_HORIZONS_MINUTES),
        components=tuple(args.component or SCALP_COMPONENTS),
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
            report = await build_signal_regime_report(conn, options)
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
        "Regime analysis written:",
        args.output,
        f"compatible_periodic={corpus.get('compatible_periodic_observations', 0)}",
        f"regime_available={corpus.get('regime_available_periodic_observations', 0)}",
        f"mature_outcomes={corpus.get('mature_outcome_rows', 0)}",
        f"missing_outcomes={corpus.get('missing_or_wrong_version_outcome_rows', 0)}",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only regime dependence over immutable PR4+PR5+PR6 research data, "
            "with PR8 component attribution conditioned on the stored decision-time regime."
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
    parser.add_argument("--min-group-n", type=int, default=30)
    parser.add_argument("--logic-version", default=SCALP_SIGNAL_LOGIC_VERSION)
    parser.add_argument("--evidence-version", type=int, default=DEFAULT_EVIDENCE_VERSION)
    parser.add_argument("--sampling-version", type=int, default=SIGNAL_SAMPLING_VERSION)
    parser.add_argument("--context-version", type=int, default=REPLAY_CONTEXT_VERSION)
    parser.add_argument("--outcome-version", type=int, default=OUTCOME_VERSION)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("signal_regime_report.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
