#!/usr/bin/env python3
"""Partir un hueco que la fuente cubre A MEDIAS, y cerrarlo cuando sus trozos esten.

EL AGUJERO QUE CIERRA, medido y no razonado. Las 3 filas de long_short_ratio del bloque
2026-08-28 07:45-19:05 piden 136 buckets de 5min y el proveedor sirve 135 (BTC), 135
(ETH) y 127 (SOL) -- hechos.tsv:969, sonda propia del operador contra api.coinalyze.net
--. Con una sola fila para todo el tramo, las tres vias existentes fallan Y HACEN BIEN:

  recover_gaps.py       validate_recovery exige timestamps == expected (data_gaps.py),
                        o sea IGUALDAD DE CONJUNTOS, asi que rechaza las tres enteras y
                        los 135 buckets que SI existen se quedan fuera de la base.
  archivar ausencia     exige window_returned_rows = 0 y aqui son 135: archivarlo
                        afirmaria que la fuente no publica lo que si publica, y encima
                        tiraria el dato. Esa guarda es de #109 y esta haciendo su trabajo.
  archivar horizonte    falso de plano: la ventana devuelve 135 filas.

El problema no es de metodo, es de GRANULARIDAD: el detector escribio UNA fila para un
tramo que la fuente cubre a trozos. La respuesta honesta no es elegir la excusa menos
mala, es partir la fila por donde la MEDICION la parte.

DOS PASOS, Y LA SEPARACION ES LA PROPIEDAD:
  1  --gap-id N          sondea la ventana EXACTA, escribe los hijos que la teselan y
                         DEJA al padre 'unresolved'.
  2  (fuera de aqui)     cada hijo por su via ya existente y ya auditada:
                            servido  -> scripts/recover_gaps.py   --gap-id H
                            ausente  -> scripts/archive_beyond_horizon.py --gap-id H
                         Aqui NO se recupera ni se archiva. Copiar esas dos rutinas
                         seria fabricar una segunda prueba que nadie vigila; K04 ya
                         re-deriva las suyas.
  3  --close --gap-id N  cierra al padre SOLO si sus hijos teselan la ventana y ninguno
                         sigue abierto. La comprobacion la rehace close_partitioned_gap
                         contra la tabla, no contra lo que diga este script.

Entre el paso 1 y el 3 la contabilidad esta ABIERTA y se ve: el padre sigue sin
resolver y los hijos nacen sin resolver. Es transitorio y es honesto. Cerrar el padre en
el paso 1 escribiria "cada trozo esta resuelto" cuando todavia es falso, y este proyecto
tiene medido lo que cuesta una prueba escrita antes de ser cierta.

A PROPOSITO NO HAY --limit NI --all, por lo mismo que las otras dos herramientas que
escriben en esta tabla: la noche del 2026-08-29 un barrido dejo 10 filas archivadas sin
prueba. Que la lista sea larga no es una molestia, es la propiedad.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.data_gaps import (
    DataGap,
    close_partitioned_gap,
    partition_gap_by_source_coverage,
)
from app.db import create_pool

# La sonda y la traduccion de simbolo salen de la herramienta de archivado, no de una
# copia: si esta pidiera por otro camino, mediria otra cosa y la particion se apoyaria en
# una cobertura que no es la que llena la tabla.
from scripts.archive_beyond_horizon import SONDA_POR_FEED, pide_marcas

PROOF_SOURCE = "partition_partial_gaps.exact_window_probe"


async def _sondea_exacto(client: CoinalyzeClient, gap: DataGap) -> list:
    """Los buckets que la fuente sirve DENTRO de la ventana del hueco, y solo esos.

    Ventana EXACTA y no ancha: aqui no se prueba cobertura -- eso lo hace cada hijo
    ausente con su propia sonda ancha cuando lo archive archive_beyond_horizon.py --,
    aqui solo se necesita saber POR DONDE parte la fuente el tramo.
    """
    if (gap.feed, gap.exchange) not in SONDA_POR_FEED:
        raise ValueError(
            f"no hay sonda declarada para {gap.feed}@{gap.exchange}: partir sin medir "
            "seria trocear por una frontera inventada"
        )
    return await pide_marcas(client, gap, gap.start, gap.end)


async def _partir(conn, client: CoinalyzeClient, gap_id: int) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT id,feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,"
        "expected_cadence,status FROM data_gap WHERE id=$1",
        gap_id,
    )
    if row is None:
        return {"gap": gap_id, "accion": "rechazar", "motivo": "no existe"}
    gap = DataGap.from_record(row)
    marcas = await _sondea_exacto(client, gap)
    salida = await partition_gap_by_source_coverage(
        conn,
        gap_id=gap_id,
        present_buckets=marcas,
        proof_source=PROOF_SOURCE,
    )
    return {"accion": "partir", "symbol": gap.symbol, **salida}


async def run(gap_ids: list[int], *, cerrar: bool) -> list[dict[str, object]]:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-partition-gaps")
    try:
        if cerrar:
            async with pool.acquire() as conn:
                return [
                    {
                        "gap": gap_id,
                        "accion": "cerrar",
                        "estado": await close_partitioned_gap(
                            conn, gap_id=gap_id, proof_source=PROOF_SOURCE
                        ),
                    }
                    for gap_id in gap_ids
                ]
        limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL, settings.API_KEY, limiter
        ) as client:
            async with pool.acquire() as conn:
                return [await _partir(conn, client, gap_id) for gap_id in gap_ids]
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Partir huecos que la fuente cubre a medias, con la particion medida"
    )
    parser.add_argument("--gap-id", type=int, action="append", required=True)
    parser.add_argument(
        "--close",
        action="store_true",
        help="cerrar el padre ya partido en vez de partirlo (paso 3)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    salidas = asyncio.run(run(args.gap_id, cerrar=args.close))
    print(json.dumps(salidas, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
