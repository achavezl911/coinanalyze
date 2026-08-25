#!/usr/bin/env python3
"""Repaso: volver a pedirle a la fuente las ventanas de los huecos historicos.

POR QUE HACE FALTA. reconcile_cadence_coverage solo clasifica lo que la ingesta le
pone delante, y la ingesta solo pide ventanas recientes: la ventana response24h. Los
huecos que se quedaron atras no los vuelve a mirar nadie nunca. Medido el 2026-08-25
en 140: los 23 archivados eran del 24-25 de agosto y se marcaron en UNA sola pasada,
mientras 502 unresolved del 10 al 24 seguian intactos.

QUE HACE. Por cada identidad (feed/exchange/market/symbol/granularity) con huecos sin
resolver, recorre sus ventanas y se las vuelve a pedir a la fuente. Lo que la fuente
devuelve SE GUARDA -por eso 'recovered' no miente: el dato esta- y lo que no devuelve
lo clasifica el MISMO clasificador de siempre, con la misma prueba y el mismo motivo.
Aqui no hay una segunda verdad: solo se le da de comer al clasificador lo que la
ingesta no le da.

EL TECHO, Y ES REAL. La fuente sirve long_short_ratio 5min hasta 200 h atras y ohlcv
1min entre 24 y 48 h. Mas alla no contesta, y sin respuesta reconcile_cadence_coverage
SE ABSTIENE, que es lo correcto: no contestar no es lo mismo que no tenerlo. Para esa
parte esta --archive-exhausted, que exige la otra prueba: ventana vacia MAS un control
reciente de la misma identidad que SI devuelve serie. Sin control positivo no archiva
nada, y eso es lo que impide que una caida del proveedor barra el atraso entero.

    scripts/resweep_cadence_gaps.py --feed long_short_ratio --dry-run
    scripts/resweep_cadence_gaps.py --feed ohlcv_1min --archive-exhausted
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.data_gaps import (  # noqa: E402
    archive_beyond_source_horizon,
    reconcile_cadence_coverage,
)
from app.db import create_pool  # noqa: E402
from app.ingest import (  # noqa: E402
    source_response_buckets,
    upsert_long_short,
    upsert_ohlcv,
)

RESWEEP_DETECTION_SOURCE = "historical_resweep_cadence_v1"
CONTROL_HOURS = 6


class FeedPlan:
    """Como se le pide a la fuente este feed y donde se guarda lo que devuelve."""

    def __init__(self, endpoint: str, interval: str, cadence: timedelta, chunk: timedelta):
        self.endpoint = endpoint
        self.interval = interval
        self.cadence = cadence
        self.chunk = chunk

    async def store(self, conn, payload, symbol_map, start_ts, end_ts, observed) -> int:
        raise NotImplementedError


class LongShortPlan(FeedPlan):
    async def store(self, conn, payload, symbol_map, start_ts, end_ts, observed) -> int:
        return await upsert_long_short(
            conn, payload, symbol_map, start_ts, end_ts, observed=observed
        )


class Ohlcv1mPlan(FeedPlan):
    async def store(self, conn, payload, symbol_map, start_ts, end_ts, observed) -> int:
        return await upsert_ohlcv(
            conn, payload, symbol_map, start_ts, end_ts, "1min", observed=observed
        )


PLANS: dict[tuple[str, str], FeedPlan] = {
    ("long_short_ratio", "5min"): LongShortPlan(
        "long-short-ratio-history", "5min", timedelta(minutes=5), timedelta(hours=24)
    ),
    ("ohlcv_1min", "1min"): Ohlcv1mPlan(
        "ohlcv-history", "1min", timedelta(minutes=1), timedelta(hours=6)
    ),
}


async def _identities(conn: asyncpg.Connection, feed: str | None) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT feed,exchange,market,symbol,granularity,
               min(start_ts) AS desde, max(end_ts) AS hasta, count(*) AS pendientes
        FROM data_gap
        WHERE status='unresolved' AND feed_class='cadence'
          AND ($1::text IS NULL OR feed=$1)
        GROUP BY 1,2,3,4,5
        ORDER BY count(*) DESC
        """,
        feed,
    )


def _windows(desde: datetime, hasta: datetime, chunk: timedelta) -> list[tuple[datetime, datetime]]:
    ventanas: list[tuple[datetime, datetime]] = []
    cursor = desde
    while cursor < hasta:
        fin = min(cursor + chunk, hasta)
        ventanas.append((cursor, fin))
        cursor = fin
    return ventanas


async def _pendientes_en(conn, ident, inicio, fin) -> int:
    return await conn.fetchval(
        """
        SELECT count(*) FROM data_gap
        WHERE status='unresolved' AND feed_class='cadence'
          AND feed=$1 AND exchange=$2 AND market=$3 AND symbol=$4 AND granularity=$5
          AND start_ts >= $6 AND end_ts <= $7
        """,
        ident["feed"], ident["exchange"], ident["market"], ident["symbol"],
        ident["granularity"], inicio, fin,
    )


async def _control(client, plan: FeedPlan, symbol: str) -> tuple[int, datetime, datetime]:
    """Una ventana RECIENTE de la misma identidad. Si esta vacia, la fuente esta muda
    y no se puede archivar nada: no sabriamos distinguir 'ya no lo sirve' de 'caida'."""
    fin = datetime.now(UTC)
    inicio = fin - timedelta(hours=CONTROL_HOURS)
    payload = await client.history(
        plan.endpoint, [symbol], interval=plan.interval,
        start_ts=int(inicio.timestamp()), end_ts=int(fin.timestamp()),
    )
    return len(payload.get(symbol, [])), inicio, fin


async def run(feed: str | None, limit: int, dry_run: bool, archive_exhausted: bool) -> dict:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-resweep-gaps")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    permitidos = frozenset(settings.SYMBOLS)
    resumen = {
        "identidades": 0, "ventanas_pedidas": 0, "ventanas_vacias": 0,
        "filas_guardadas": 0, "huecos_recuperados": 0, "huecos_archivados_ausencia": 0,
        "huecos_archivados_horizonte": 0, "sin_plan": [], "control_mudo": 0,
    }
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL, settings.API_KEY, limiter
        ) as client:
            async with pool.acquire() as conn:
                for ident in await _identities(conn, feed):
                    plan = PLANS.get((ident["feed"], ident["granularity"]))
                    if plan is None:
                        resumen["sin_plan"].append(f"{ident['feed']}/{ident['granularity']}")
                        continue
                    if ident["symbol"] not in permitidos:
                        continue
                    resumen["identidades"] += 1
                    mapa = {ident["symbol"]: ident["symbol"]}

                    for inicio, fin in _windows(ident["desde"], ident["hasta"], plan.chunk):
                        if resumen["ventanas_pedidas"] >= limit:
                            break
                        if await _pendientes_en(conn, ident, inicio, fin) == 0:
                            continue
                        resumen["ventanas_pedidas"] += 1
                        payload = await client.history(
                            plan.endpoint, [ident["symbol"]], interval=plan.interval,
                            start_ts=int(inicio.timestamp()), end_ts=int(fin.timestamp()),
                        )
                        devueltos = source_response_buckets(
                            payload, mapa, int(inicio.timestamp()), int(fin.timestamp())
                        ).get(ident["symbol"], set())

                        if not devueltos:
                            resumen["ventanas_vacias"] += 1
                            if not archive_exhausted or dry_run:
                                continue
                            filas, c_ini, c_fin = await _control(client, plan, ident["symbol"])
                            if filas <= 0:
                                # La fuente esta muda: no se archiva NADA. Ver el docstring.
                                resumen["control_mudo"] += 1
                                continue
                            resumen["huecos_archivados_horizonte"] += (
                                await archive_beyond_source_horizon(
                                    conn,
                                    feed=ident["feed"], exchange=ident["exchange"],
                                    market=ident["market"], symbol=ident["symbol"],
                                    granularity=ident["granularity"],
                                    window_start=inicio, window_end=fin,
                                    control_start=c_ini, control_end=c_fin,
                                    control_returned_rows=filas,
                                )
                            )
                            continue

                        if dry_run:
                            continue
                        # Lo que la fuente devuelve SE GUARDA antes de clasificar nada. Asi
                        # 'recovered' significa que el dato esta, no que lo vimos pasar.
                        aceptados: dict[str, set[datetime]] = {}
                        resumen["filas_guardadas"] += await plan.store(
                            conn, payload, mapa,
                            int(inicio.timestamp()), int(fin.timestamp()), aceptados,
                        )
                        cobertura = await reconcile_cadence_coverage(
                            conn,
                            observations=aceptados.get(ident["symbol"], set()),
                            feed=ident["feed"], exchange=ident["exchange"],
                            market=ident["market"], symbol=ident["symbol"],
                            granularity=ident["granularity"],
                            start=inicio, end=fin, cadence=plan.cadence,
                            detection_source=RESWEEP_DETECTION_SOURCE,
                            source_response_buckets=devueltos,
                        )
                        resumen["huecos_recuperados"] += cobertura.recovered_gaps

            async with pool.acquire() as conn:
                resumen["unresolved_restantes"] = await conn.fetchval(
                    "SELECT count(*) FROM data_gap WHERE status='unresolved'"
                )
        return resumen
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--feed", help="solo este feed; por defecto todos")
    p.add_argument("--limit", type=int, default=200, help="tope de ventanas a pedir")
    p.add_argument("--dry-run", action="store_true", help="pide y cuenta, no escribe")
    p.add_argument(
        "--archive-exhausted", action="store_true",
        help="archiva lo que quede fuera del horizonte, con control positivo obligatorio",
    )
    return p.parse_args()


def main() -> None:
    a = parse_args()
    print(json.dumps(asyncio.run(run(a.feed, a.limit, a.dry_run, a.archive_exhausted)),
                     sort_keys=True, default=str))


if __name__ == "__main__":
    main()
