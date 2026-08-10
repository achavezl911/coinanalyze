#!/usr/bin/env python3
"""Stage B (Evaluate): read-only PR11 walk-forward / out-of-sample report.

Runs strictly inside a PostgreSQL REPEATABLE READ READ ONLY transaction.
Performs no INSERT/UPDATE/DELETE/DDL and never mutates live scoring.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import Any

import asyncpg

from app.config import get_settings
from app.signal_walk_forward import evaluate_walk_forward


def _json_default(value: object) -> str:
    return str(value)


def _csv_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold in report["folds"]:
        base = {
            "fold_index": fold["fold_index"],
            "state": fold["state"],
            "evaluation_ready": fold["evaluation_ready"],
        }
        for view_name, view_rows in fold["gross_views"].items():
            for row in view_rows:
                flat = {
                    "view": view_name,
                    **base,
                    "symbol": row.get("symbol"),
                    "horizon_minutes": row.get("horizon_minutes"),
                    "state_dim": row.get("state"),
                    "regime_label": row.get("regime_label"),
                    "direction": row.get("direction"),
                    "label": row.get("label"),
                    "discovery_n": row["discovery"]["n"],
                    "discovery_expectancy_gross_pct": row["discovery"]["expectancy_gross_pct"],
                    "test_n": row["test"]["n"],
                    "test_expectancy_gross_pct": row["test"]["expectancy_gross_pct"],
                    "expectancy_diff_pct": row.get("expectancy_diff_pct"),
                    "expectancy_retention_ratio": row.get("expectancy_retention_ratio"),
                    "sign_preserved": row.get("sign_preserved"),
                }
                rows.append(flat)
        for row in fold["execution_view"]:
            rows.append(
                {
                    "view": "execution",
                    **base,
                    "symbol": row.get("symbol"),
                    "exchange": row.get("exchange"),
                    "size_usd": row.get("size_usd"),
                    "horizon_minutes": row.get("horizon_minutes"),
                    "discovery_n": row["discovery"]["n_cost_evaluable"],
                    "discovery_net_expectancy_bps": row["discovery"]["net_expectancy_bps"],
                    "test_n": row["test"]["n_cost_evaluable"],
                    "test_net_expectancy_bps": row["test"]["net_expectancy_bps"],
                    "net_expectancy_diff_bps": row.get("net_expectancy_diff_bps"),
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
        "view",
        "fold_index",
        "state",
        "evaluation_ready",
        "symbol",
        "exchange",
        "size_usd",
        "horizon_minutes",
        "state_dim",
        "regime_label",
        "direction",
        "label",
        "discovery_n",
        "discovery_expectancy_gross_pct",
        "discovery_net_expectancy_bps",
        "test_n",
        "test_expectancy_gross_pct",
        "test_net_expectancy_bps",
        "expectancy_diff_pct",
        "net_expectancy_diff_bps",
        "expectancy_retention_ratio",
        "sign_preserved",
    ]
    fieldnames = [name for name in preferred if name in all_fields]
    fieldnames.extend(sorted(all_fields - set(fieldnames)))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            report = await evaluate_walk_forward(conn, args.manifest_name)
    finally:
        await conn.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only PR11 walk-forward / out-of-sample evaluation over an "
            "existing immutable manifest. Produces no true-positive OOS "
            "claims until a frozen fold has actually matured by the clock."
        )
    )
    parser.add_argument("--manifest-name", required=True)
    parser.add_argument("--output", type=Path, default=Path("walk_forward_report.json"))
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()

    report = asyncio.run(_run(args))
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )
    if args.csv:
        _write_csv(args.csv, report)

    print(
        "Walk-forward report written:",
        args.output,
        f"manifest={report['manifest']['manifest_name']}",
        f"ready_by_clock_fold_count={report['ready_by_clock_fold_count']}",
        f"evaluation_ready_fold_count={report['evaluation_ready_fold_count']}",
        f"first_oos_cutoff_in_future={report['first_oos_cutoff_in_future']}",
    )


if __name__ == "__main__":
    main()
