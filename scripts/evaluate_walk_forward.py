#!/usr/bin/env python3
"""Read-only PR11 walk-forward / out-of-sample report."""

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
        common = {
            "fold_index": fold["fold_index"],
            "fold_state": fold["state"],
            "evaluation_ready": fold["evaluation_ready"],
        }

        for mode, views in fold["gross_views"].items():
            for view_name, view_rows in views.items():
                for row in view_rows:
                    rows.append(
                        {
                            **common,
                            "sampling_mode": mode,
                            "view": f"gross_{view_name}",
                            "symbol": row.get("symbol"),
                            "state": row.get("state"),
                            "regime_label": row.get("regime_label"),
                            "direction": row.get("direction"),
                            "exchange": None,
                            "size_usd": None,
                            "horizon_minutes": row.get("horizon_minutes"),
                            "label": row.get("label"),
                            "positive_oos_gate_passed": row.get(
                                "positive_oos_gate_passed"
                            ),
                            "discovery_n": row["discovery"]["n"],
                            "test_n": row["test"]["n"],
                            "discovery_gross_expectancy_pct": row[
                                "discovery"
                            ]["expectancy_gross_pct"],
                            "test_gross_expectancy_pct": row["test"][
                                "expectancy_gross_pct"
                            ],
                            "expectancy_diff_pct": row.get(
                                "expectancy_diff_pct"
                            ),
                            "expectancy_retention_ratio": row.get(
                                "expectancy_retention_ratio"
                            ),
                            "sign_preserved": row.get("sign_preserved"),
                        }
                    )

        for mode, view_rows in fold["execution_views"].items():
            for row in view_rows:
                rows.append(
                    {
                        **common,
                        "sampling_mode": mode,
                        "view": "execution",
                        "symbol": row.get("symbol"),
                        "state": None,
                        "regime_label": None,
                        "direction": None,
                        "exchange": row.get("exchange"),
                        "size_usd": row.get("size_usd"),
                        "horizon_minutes": row.get("horizon_minutes"),
                        "label": row.get("label"),
                        "positive_oos_gate_passed": row.get(
                            "positive_market_cost_oos_gate_passed"
                        ),
                        "discovery_n": row["discovery"][
                            "n_cost_evaluable"
                        ],
                        "test_n": row["test"]["n_cost_evaluable"],
                        "discovery_market_net_expectancy_bps": row[
                            "discovery"
                        ]["symmetric_market_net_expectancy_bps"],
                        "test_market_net_expectancy_bps": row["test"][
                            "symmetric_market_net_expectancy_bps"
                        ],
                        "market_net_diff_bps": row.get(
                            "net_expectancy_diff_bps"
                        ),
                        "market_net_retention_ratio": row.get(
                            "net_expectancy_retention_ratio"
                        ),
                        "fee_bps_per_side_applied": row.get(
                            "fee_bps_per_side_applied"
                        ),
                        "discovery_net_after_fees_bps": row["discovery"][
                            "modeled_net_after_fees_expectancy_bps"
                        ],
                        "test_net_after_fees_bps": row["test"][
                            "modeled_net_after_fees_expectancy_bps"
                        ],
                    }
                )
    return rows


def _write_csv(path: Path, report: dict[str, Any]) -> None:
    rows = _csv_rows(report)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fields = set().union(*(row.keys() for row in rows))
    preferred = [
        "fold_index",
        "fold_state",
        "evaluation_ready",
        "sampling_mode",
        "view",
        "symbol",
        "state",
        "regime_label",
        "direction",
        "exchange",
        "size_usd",
        "horizon_minutes",
        "label",
        "positive_oos_gate_passed",
        "discovery_n",
        "test_n",
        "discovery_gross_expectancy_pct",
        "test_gross_expectancy_pct",
        "expectancy_diff_pct",
        "expectancy_retention_ratio",
        "sign_preserved",
        "discovery_market_net_expectancy_bps",
        "test_market_net_expectancy_bps",
        "market_net_diff_bps",
        "market_net_retention_ratio",
        "fee_bps_per_side_applied",
        "discovery_net_after_fees_bps",
        "test_net_after_fees_bps",
    ]
    fieldnames = [name for name in preferred if name in fields]
    fieldnames.extend(sorted(fields - set(fieldnames)))

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _evidence_stamp(selection: dict[str, Any]) -> str:
    """evidence=6(OVERRIDE,manifiesto=1) o evidence=1(manifiesto)."""
    aplicada = selection["applied_evidence_version"]
    if not selection["override_applied"]:
        return f"evidence={aplicada}(manifiesto)"
    return (
        f"evidence={aplicada}"
        f"(OVERRIDE,manifiesto={selection['manifest_evidence_version']})"
    )


def _gate_count(value: int | None) -> str:
    """NO EVALUABLE no es cero. Imprimirlo como 0 es el defecto de K60."""
    return "NO_EVALUABLE" if value is None else str(value)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    settings = get_settings()
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        async with conn.transaction(
            isolation="repeatable_read",
            readonly=True,
        ):
            return await evaluate_walk_forward(
                conn,
                args.manifest_name,
                evidence_version_override=args.evidence_version_override,
            )
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate an immutable PR11 walk-forward manifest in a "
            "REPEATABLE READ READ ONLY transaction."
        )
    )
    parser.add_argument("--manifest-name", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("walk_forward_report.json"),
    )
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument(
        "--evidence-version-override",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Evalua con este evidence_version en vez del que congelo el manifiesto. "
            "El manifiesto NO se toca y su hash se sigue verificando contra su propio "
            "valor. Existe porque el manifiesto congelo v1 y esa cohorte murio el "
            "2026-08-11T23:28:41Z, asi que una corrida fiel selecciona cero filas. Con "
            "la bandera puesta lo que selecciona es la bandera, y el informe lo dice: "
            "evidence_selection en el JSON y evidence=... en esta linea."
        ),
    )
    args = parser.parse_args()

    report = asyncio.run(_run(args))
    args.output.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=_json_default,
        ),
        encoding="utf-8",
    )
    if args.csv:
        _write_csv(args.csv, report)

    gates = report["gates"]
    print(
        "Walk-forward report written:",
        args.output,
        f"manifest={report['manifest']['manifest_name']}",
        # QUE SELECCIONO LAS FILAS, siempre y en la primera linea. Con el manifiesto
        # congelado en una cohorte muerta, esto es lo que decide que se mide; un informe
        # que no lo diga miente por omision aunque cada cifra suya sea correcta.
        _evidence_stamp(report["evidence_selection"]),
        f"ready_by_clock={gates['ready_by_clock_fold_count']}",
        f"evaluation_ready={gates['evaluation_ready_fold_count']}",
        # K60: el conteo de puertas viaja SIEMPRE con cuantas celdas eran
        # evaluables. Sin ese denominador, un 0 se lee como "evaluado, sin
        # ventaja" cuando lo que hubo fue nada que evaluar.
        f"gross_positive_oos_gates={_gate_count(gates['positive_oos_gate_count'])}",
        (
            "oos_gate_evaluable="
            f"{gates['oos_gate_evaluable_cell_count']}"
            f"/{gates['oos_gate_evaluable_cell_count'] + gates['oos_gate_not_evaluable_cell_count']}"
        ),
        (
            "execution_positive_oos_gates="
            f"{_gate_count(gates['positive_execution_oos_gate_count'])}"
        ),
        (
            "execution_oos_gate_evaluable="
            f"{gates['execution_oos_gate_evaluable_cell_count']}"
            f"/{gates['execution_oos_gate_evaluable_cell_count'] + gates['execution_oos_gate_not_evaluable_cell_count']}"
        ),
    )
    if "confirmatory_state" in report:
        # PR26 spec v3: surface the confirmatory decision explicitly. This
        # never influences (and is never influenced by) the exploratory
        # gates printed above.
        print(f"confirmatory_state={report['confirmatory_state']}")


if __name__ == "__main__":
    main()
