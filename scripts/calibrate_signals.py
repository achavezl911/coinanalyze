#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

import asyncpg

from app.config import get_settings

HORIZONS = {"1h": "1 hour", "4h": "4 hours", "1d": "1 day"}
SamplingMode = Literal["raw", "episode", "non_overlap"]


def pct(entry: float | None, exit_: float | None) -> float | None:
    if entry is None or exit_ is None or entry <= 0:
        return None
    return (exit_ - entry) / entry * 100.0


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"n": 0, "hit_rate": None, "avg": None, "median": None, "p25": None, "p75": None}
    ordered = sorted(values)
    n = len(values)
    return {
        "n": n,
        "hit_rate": sum(1 for value in values if value > 0) / n,
        "avg": sum(values) / n,
        "median": statistics.median(values),
        "p25": ordered[int((n - 1) * 0.25)],
        "p75": ordered[int((n - 1) * 0.75)],
    }


def signal_side(row: dict[str, Any]) -> str:
    state = str(row.get("state") or "")
    if state == "No Trade":
        return "neutral"
    return "long" if float(row.get("long_score") or 0) >= float(row.get("short_score") or 0) else "short"


def sample_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("symbol") or ""),
        str(row.get("state") or ""),
        str(row.get("confidence") or ""),
        signal_side(row),
    )


def select_samples(
    rows: list[dict[str, Any]],
    mode: SamplingMode,
    non_overlap_minutes: int,
) -> list[dict[str, Any]]:
    if mode == "raw":
        return rows
    selected: list[dict[str, Any]] = []
    if mode == "episode":
        last_by_symbol: dict[str, tuple[str, str, str, str]] = {}
        for row in rows:
            key = sample_key(row)
            symbol = key[0]
            if last_by_symbol.get(symbol) != key:
                selected.append(row)
                last_by_symbol[symbol] = key
        return selected
    spacing = timedelta(minutes=non_overlap_minutes)
    last_seen: dict[tuple[str, str, str, str], Any] = {}
    for row in rows:
        key = sample_key(row)
        ts = row.get("ts")
        if ts is None:
            continue
        previous = last_seen.get(key)
        if previous is None or ts >= previous + spacing:
            selected.append(row)
            last_seen[key] = ts
    return selected


async def fetch_rows(conn: asyncpg.Connection, days: int) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        WITH sig AS (
          SELECT * FROM scalp_signal_snapshot
          WHERE ts >= now()-($1::int * interval '1 day')
        ), px AS (
          SELECT ts,symbol,close FROM ohlcv WHERE interval='1min'
        )
        SELECT sig.ts,sig.symbol,sig.state,sig.confidence,sig.long_score,sig.short_score,
               entry.close AS entry_px,
               px1.close AS px_1h,px4.close AS px_4h,pxd.close AS px_1d
        FROM sig
        LEFT JOIN LATERAL (
          SELECT close FROM px WHERE px.symbol=sig.symbol AND px.ts >= sig.ts ORDER BY px.ts ASC LIMIT 1
        ) entry ON true
        LEFT JOIN LATERAL (
          SELECT close FROM px WHERE px.symbol=sig.symbol AND px.ts >= sig.ts + interval '1 hour' ORDER BY px.ts ASC LIMIT 1
        ) px1 ON true
        LEFT JOIN LATERAL (
          SELECT close FROM px WHERE px.symbol=sig.symbol AND px.ts >= sig.ts + interval '4 hours' ORDER BY px.ts ASC LIMIT 1
        ) px4 ON true
        LEFT JOIN LATERAL (
          SELECT close FROM px WHERE px.symbol=sig.symbol AND px.ts >= sig.ts + interval '1 day' ORDER BY px.ts ASC LIMIT 1
        ) pxd ON true
        ORDER BY sig.ts
        """,
        days,
    )
    return [dict(row) for row in rows]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        side = signal_side(row)
        key = f'{row["symbol"]}|{row["state"]}|{row["confidence"]}|{side}'
        bucket = buckets.setdefault(key, {"1h": [], "4h": [], "1d": []})
        for label, column in (("1h", "px_1h"), ("4h", "px_4h"), ("1d", "px_1d")):
            ret = pct(row.get("entry_px"), row.get(column))
            if ret is None:
                continue
            if side == "short":
                ret = -ret
            bucket[label].append(ret)
    result: dict[str, Any] = {}
    for key, horizons in buckets.items():
        symbol, state, confidence, side = key.split("|")
        result[key] = {
            "symbol": symbol,
            "state": state,
            "confidence": confidence,
            "side": side,
            "forward": {label: stats(values) for label, values in horizons.items()},
        }
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="Calibra señales scalp contra forward returns.")
    parser.add_argument("--days", type=int, default=None, help="Días solicitados. Default: retención efectiva de OHLCV.")
    parser.add_argument("--mode", choices=["raw", "episode", "non_overlap"], default="episode")
    parser.add_argument("--non-overlap-minutes", type=int, default=60, help="Separación mínima por bucket cuando --mode=non_overlap.")
    parser.add_argument("--output", type=Path, default=Path("calibration_report.json"))
    parser.add_argument("--csv", type=Path, default=None)
    args = parser.parse_args()
    settings = get_settings()
    requested_days = int(args.days or settings.HARD_DATA_RETENTION_DAYS)
    effective_days = min(requested_days, settings.HARD_DATA_RETENTION_DAYS)
    conn = await asyncpg.connect(settings.pg_dsn)
    try:
        raw_rows = await fetch_rows(conn, effective_days)
    finally:
        await conn.close()
    rows = select_samples(raw_rows, args.mode, args.non_overlap_minutes)
    report = {
        "requested_days": requested_days,
        "effective_days": effective_days,
        "ohlcv_retention_days": settings.HARD_DATA_RETENTION_DAYS,
        "sampling_mode": args.mode,
        "non_overlap_minutes": args.non_overlap_minutes if args.mode == "non_overlap" else None,
        "raw_rows": len(raw_rows),
        "effective_rows": len(rows),
        "coverage_pct": (len(rows) / len(raw_rows) * 100.0) if raw_rows else None,
        "groups": summarize(rows),
    }
    args.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["symbol", "state", "confidence", "side", "horizon", "n", "hit_rate", "avg", "median", "p25", "p75"])
            for group in report["groups"].values():
                for horizon, values in group["forward"].items():
                    writer.writerow([
                        group["symbol"], group["state"], group["confidence"], group["side"], horizon,
                        values["n"], values["hit_rate"], values["avg"], values["median"], values["p25"], values["p75"],
                    ])
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
