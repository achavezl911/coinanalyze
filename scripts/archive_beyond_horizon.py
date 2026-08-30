#!/usr/bin/env python3
"""Archivar un hueco que la fuente ya no sirve, con la prueba MEDIDA aqui mismo.

POR QUE EXISTE. app/data_gaps.py:archive_beyond_source_horizon escribe el unico
archivado que K04 acepta -- el que deja en recovery_metadata una prueba re-derivable con
el metodo 'provider_horizon_exhausted'. Estaba escrita y probada desde hace semanas y NO
LA LLAMABA NADIE: solo la nombran los tests. El unico camino con entrada era
recover_gaps.py, cuyo _mark_unrecoverable escribe recovery_metadata='{}', o sea SIN
prueba, que es justo lo que K04 v3 rechaza. La noche del 2026-08-29 eso archivo 10 filas
de long_short_ratio sin prueba con un solo --limit. Una funcion honesta sin puerta de
entrada no protege de nada: lo que se usa es lo que se puede ejecutar.

LA PRUEBA SE MIDE AQUI, NO SE ACEPTA POR PARAMETRO. Si los conteos vinieran de la linea
de ordenes, la "prueba re-derivable" seria lo que alguien tecleo, y el archivado en falso
volveria por la puerta grande con mejor letra. El guion sondea las dos ventanas contra el
proveedor y solo entonces escribe.

LAS DOS NEGATIVAS, y las dos importan mas que el caso bueno:
  1. Si la ventana del hueco DEVUELVE FILAS, no se archiva: el dato existe y archivarlo
     seria mentir y ademas tirar la oportunidad de recuperarlo. Va a recover_gaps.py.
  2. Si el control reciente NO devuelve filas, no se archiva: una fuente callada no es
     prueba de ausencia, solo de silencio. Esa distincion es la que impide que una caida
     del proveedor barra el backlog entero a 'unrecoverable'. La funcion de la base ya la
     exige; aqui se comprueba antes para no gastar la escritura y para decir por que.

EL MAPA DE FEEDS SE DECLARA POR PLAN. Un feed que no este aqui se RECHAZA en vez de
adivinarle un endpoint: adivinarlo mal daria cero filas por la razon equivocada y eso es
exactamente una prueba falsa. Es la misma regla que el "method desconocido" de K04.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.data_gaps import DataGap, archive_beyond_source_horizon
from app.db import create_pool

# feed -> (endpoint del proveedor, intervalo). Declarado, nunca deducido.
SONDA_POR_FEED: dict[str, tuple[str, str]] = {
    "ohlcv_1min": ("ohlcv-history", "1min"),
}

# Cuanto se mira hacia atras para el control. Tiene que caber holgadamente dentro del
# horizonte mas corto medido -- el de 1min ronda las 29 h -- y terminar hace un rato para
# no depender del bucket en curso.
CONTROL_SPAN = timedelta(hours=2)
CONTROL_RETRASO = timedelta(minutes=10)


@dataclass(frozen=True)
class Veredicto:
    accion: str  # "archivar" | "rechazar"
    motivo: str


def decidir(gap: DataGap, filas_ventana: int, filas_control: int) -> Veredicto:
    """Decision pura, para poder probarla sin proveedor ni base."""
    if gap.feed not in SONDA_POR_FEED:
        return Veredicto("rechazar", f"feed '{gap.feed}' no declarado en SONDA_POR_FEED")
    if gap.feed_class != "cadence":
        return Veredicto("rechazar", "solo se archivan huecos de cadencia")
    if filas_ventana > 0:
        return Veredicto(
            "rechazar",
            f"la fuente SI sirve la ventana ({filas_ventana} filas): esto no es un "
            "horizonte agotado, es un hueco recuperable. Va a recover_gaps.py",
        )
    if filas_control <= 0:
        return Veredicto(
            "rechazar",
            "el control reciente tampoco devuelve filas: la fuente esta callada, y "
            "silencio no es prueba de ausencia",
        )
    return Veredicto("archivar", f"ventana 0 filas, control {filas_control} filas")


async def _contar(client: CoinalyzeClient, gap: DataGap, desde: datetime, hasta: datetime) -> int:
    endpoint, interval = SONDA_POR_FEED[gap.feed]
    payload = await client.history(
        endpoint,
        [gap.symbol],
        interval=interval,
        start_ts=int(desde.timestamp()),
        end_ts=int(hasta.timestamp()) - 1,
    )
    return len(payload.get(gap.symbol, []))


async def _procesar(conn, client: CoinalyzeClient, gap_id: int) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT id,feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,"
        "expected_cadence,status FROM data_gap WHERE id=$1",
        gap_id,
    )
    if row is None:
        return {"gap": gap_id, "accion": "rechazar", "motivo": "no existe"}
    gap = DataGap.from_record(row)
    if gap.status != "unresolved":
        return {"gap": gap_id, "accion": "rechazar", "motivo": f"ya esta '{gap.status}'"}
    if gap.feed not in SONDA_POR_FEED:
        return {"gap": gap_id, **decidir(gap, 0, 0).__dict__}

    ahora = datetime.now(UTC)
    control_fin = ahora - CONTROL_RETRASO
    control_ini = control_fin - CONTROL_SPAN

    filas_ventana = await _contar(client, gap, gap.start, gap.end)
    filas_control = await _contar(client, gap, control_ini, control_fin)
    veredicto = decidir(gap, filas_ventana, filas_control)

    salida: dict[str, object] = {
        "gap": gap_id,
        "symbol": gap.symbol,
        "ventana_filas": filas_ventana,
        "control_filas": filas_control,
        "accion": veredicto.accion,
        "motivo": veredicto.motivo,
    }
    if veredicto.accion != "archivar":
        return salida

    archivadas = await archive_beyond_source_horizon(
        conn,
        feed=gap.feed,
        exchange=gap.exchange,
        market=gap.market,
        symbol=gap.symbol,
        granularity=gap.granularity,
        window_start=gap.start,
        window_end=gap.end,
        control_start=control_ini,
        control_end=control_fin,
        control_returned_rows=filas_control,
    )
    salida["filas_archivadas"] = archivadas
    return salida


async def run(gap_ids: list[int]) -> list[dict[str, object]]:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-archive-horizon")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL, settings.API_KEY, limiter
        ) as client:
            async with pool.acquire() as conn:
                return [await _procesar(conn, client, gap_id) for gap_id in gap_ids]
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archivar huecos fuera del horizonte de la fuente, con prueba medida"
    )
    # A PROPOSITO NO HAY --limit NI --all. El unico modo es nombrar los huecos uno a uno:
    # un archivado en masa es como se perdieron 10 filas la noche del 29, y esta
    # herramienta escribe justo en la tabla que aquello ensucio.
    parser.add_argument("--gap-id", type=int, action="append", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(asyncio.run(run(args.gap_id)), sort_keys=True))


if __name__ == "__main__":
    main()
