#!/usr/bin/env python3
"""Archivar un hueco que la fuente no sirve, con la prueba MEDIDA aqui mismo.

POR QUE EXISTE. app/data_gaps.py escribe los DOS unicos archivados que K04 acepta -- los
que dejan en recovery_metadata una prueba re-derivable. Estaban escritos y probados y no
los llamaba nadie por esta via: el unico camino con entrada era recover_gaps.py, cuyo
_mark_unrecoverable escribe recovery_metadata='{}', o sea SIN prueba, que es justo lo que
K04 v3 rechaza. La noche del 2026-08-29 eso archivo 10 filas sin prueba con un solo
--limit. Una funcion honesta sin puerta de entrada no protege de nada.

LA PRUEBA SE MIDE AQUI, NO SE ACEPTA POR PARAMETRO. Si los conteos vinieran de la linea de
ordenes, la "prueba re-derivable" seria lo que alguien tecleo, y el archivado en falso
volveria por la puerta grande con mejor letra.

SE PIDE UNA VENTANA ANCHA, NO LA DEL HUECO, Y ESO ES EL CAMBIO DE FONDO. Una ventana de
cinco minutos que vuelve vacia es AMBIGUA: se lee igual si el horizonte se agoto que si la
fuente sirve el tramo y no publica ese bucket. Son dos hechos distintos sobre el dato y
solo uno es "horizonte". La ventana ancha los separa, y de paso da los dos numeros con UNA
sola respuesta: lo que hay dentro del hueco y lo que hay alrededor. Medido en 140 el
2026-08-30 sobre las 99 filas sin resolver: 80 son horizonte -- la ancha vuelve vacia -- y
4 son ausencia -- la ancha trae 44 y 47 filas rodeando el hueco --. Archivar esas 4 como
"horizonte" habria pasado K04 igual, porque K04 re-deriva lo que hay ESCRITO, y habria
sido falso.

LAS TRES NEGATIVAS, y las tres importan mas que el caso bueno:
  1. Si la ventana del hueco DEVUELVE FILAS, no se archiva: el dato existe y archivarlo
     seria mentir y ademas tirar la oportunidad de recuperarlo. Va a recuperacion.
  2. Si el control reciente NO devuelve filas, no se archiva: una fuente callada no es
     prueba de ausencia, solo de silencio. Esa distincion es la que impide que una caida
     del proveedor barra el backlog entero a 'unrecoverable'.
  3. Si la ancha devuelve algo pero NO rodea el hueco, no se archiva NI POR UNA VIA NI POR
     LA OTRA. Es el caso de un hueco pegado a la frontera del proveedor: hay respuesta,
     asi que no es horizonte, y no cubre el tramo, asi que no prueba ausencia. COLA.md ya
     lo tenia contado -- las "11 fuera de frontera, todas del 08-17, en la ventana que
     CRUZA la frontera" --. Se dice y se deja sin tocar.

EL MAPA SE INDEXA POR (feed, exchange), NO POR feed. data_gap distingue
open_interest_5min@binance de open_interest_5min@bybit porque exchange esta dentro de la
clave del ON CONFLICT, pero guarda el simbolo CANONICO en los dos: BTCUSDT_PERP.A. El
proveedor no: mismo endpoint open-interest-history, BTCUSDT_PERP.A para binance y
BTCUSDT.6 para bybit. Un mapa por feed le pediria el canonico a los dos, recibiria 200 con
datos y archivaria el hueco de BYBIT con una prueba medida sobre BINANCE. No es un error
que se vea: es una respuesta PLAUSIBLE sobre el feed equivocado. Y no es cosmetico --
medido en 140 el 2026-08-30, las dos bolsas difieren 54.3 % en BTC, 67.9 % en ETH y 16.5 %
en SOL sobre el mismo ts. harness/checks/K71 lo vigila EJECUTANDO la traduccion.

UN FEED QUE NO ESTE EN EL MAPA SE RECHAZA en vez de adivinarle un endpoint: adivinarlo mal
da cero filas por la razon equivocada, y eso es exactamente una prueba falsa.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import BYBIT_SYMBOL_MAP, get_settings
from app.data_gaps import (
    DataGap,
    archive_beyond_source_horizon,
    archive_source_response_absence,
)
from app.db import create_pool

# (feed, exchange) -> (endpoint del proveedor, intervalo). Declarado, nunca deducido.
# Los endpoints son los que usa el ciclo vivo en app/ingest.py:725 y :793-825, no otros:
# si la sonda pidiera por un camino distinto del que llena la tabla, estaria midiendo otra
# cosa y la prueba no diria nada sobre nuestro dato.
SONDA_POR_FEED: dict[tuple[str, str], tuple[str, str]] = {
    ("ohlcv_1min", "binance"): ("ohlcv-history", "1min"),
    ("ohlcv_5min", "binance"): ("ohlcv-history", "5min"),
    ("long_short_ratio", "binance"): ("long-short-ratio-history", "5min"),
    ("funding_rate", "binance"): ("funding-rate-history", "5min"),
    ("predicted_funding_rate", "binance"): ("predicted-funding-rate-history", "5min"),
    ("open_interest_5min", "binance"): ("open-interest-history", "5min"),
    ("open_interest_5min", "bybit"): ("open-interest-history", "5min"),
}

# Cuanto se mira hacia atras para el control. Tiene que caber holgadamente dentro del
# horizonte mas corto medido -- el de 1min ronda las 29 h -- y terminar hace un rato para
# no depender del bucket en curso.
CONTROL_SPAN = timedelta(hours=2)
CONTROL_RETRASO = timedelta(minutes=10)

# Margen a cada lado del hueco para la ventana ancha. No hace falta que sea grande: al
# straddle le basta UN bucket antes y otro en/despues del final. 2 h son 24 buckets de
# 5min y 120 de 1min, de sobra, y mantiene la peticion barata.
MARGEN_ANCHO = timedelta(hours=2)

PROOF_SOURCE = "archive_beyond_horizon.wide_window_probe"


def simbolo_de_proveedor(feed: str, exchange: str, canonico: str) -> str:
    """Traducir el simbolo CANONICO de data_gap al que pide el proveedor para ESE exchange.

    Es una funcion y no un diccionario a proposito: K71 la EJECUTA. Comprobar que existe un
    mapa no distingue este codigo del que le pedia el canonico a las dos bolsas.
    """
    if exchange == "bybit":
        traducido = BYBIT_SYMBOL_MAP.get(canonico)
        if not traducido:
            raise KeyError(
                f"'{canonico}' no tiene simbolo de bybit en el catalogo: sondearlo con el "
                f"canonico mediria binance y archivaria el hueco de bybit con esa prueba"
            )
        return traducido
    return canonico


@dataclass(frozen=True)
class Sondeo:
    """Lo que devolvio UNA peticion ancha. Todo lo que sigue se decide con esto."""

    filas_dentro: int  # buckets devueltos DENTRO de la ventana del hueco
    ancha_filas: int  # buckets devueltos en toda la ventana ancha
    primera: datetime | None
    ultima: datetime | None


@dataclass(frozen=True)
class Veredicto:
    accion: str  # "archivar_horizonte" | "archivar_ausencia" | "rechazar"
    motivo: str


def decidir(
    gap: DataGap,
    *,
    sondeo: Sondeo | None,
    filas_control: int,
) -> Veredicto:
    """Decision pura, para poder probarla sin proveedor ni base."""
    if (gap.feed, gap.exchange) not in SONDA_POR_FEED:
        return Veredicto(
            "rechazar",
            f"la pareja ('{gap.feed}','{gap.exchange}') no esta declarada en "
            f"SONDA_POR_FEED: adivinarle endpoint o simbolo daria cero filas por la razon "
            f"equivocada, que es una prueba falsa",
        )
    if gap.feed_class != "cadence":
        return Veredicto("rechazar", "solo se archivan huecos de cadencia")
    if sondeo is None:
        return Veredicto("rechazar", "no hay sondeo: no hay nada que probar")
    if sondeo.filas_dentro > 0:
        return Veredicto(
            "rechazar",
            f"la fuente SI sirve la ventana ({sondeo.filas_dentro} filas dentro del "
            f"hueco): esto no es un archivado, es un hueco recuperable",
        )
    if filas_control <= 0:
        return Veredicto(
            "rechazar",
            "el control reciente tampoco devuelve filas: la fuente esta callada, y "
            "silencio no es prueba de ausencia",
        )
    if sondeo.ancha_filas == 0:
        return Veredicto(
            "archivar_horizonte",
            f"la ventana ANCHA vuelve vacia y el control reciente trae {filas_control} "
            f"filas: la fuente ya no sirve ese tramo",
        )
    if (
        sondeo.primera is not None
        and sondeo.ultima is not None
        and sondeo.primera < gap.start
        and sondeo.ultima >= gap.end
    ):
        return Veredicto(
            "archivar_ausencia",
            f"la ventana ANCHA trae {sondeo.ancha_filas} filas que RODEAN el hueco "
            f"({sondeo.primera:%Y-%m-%d %H:%M} .. {sondeo.ultima:%Y-%m-%d %H:%M}) y "
            f"CERO dentro: la fuente cubre el tramo y no publica esos buckets",
        )
    return Veredicto(
        "rechazar",
        f"la ventana ANCHA trae {sondeo.ancha_filas} filas pero NO rodea el hueco "
        f"(primera={sondeo.primera}, ultima={sondeo.ultima}): hay respuesta, asi que no es "
        f"horizonte, y no cubre el tramo, asi que no prueba ausencia. Es un hueco pegado a "
        f"la frontera del proveedor y se deja sin tocar",
    )


async def _pide(
    client: CoinalyzeClient, gap: DataGap, desde: datetime, hasta: datetime
) -> list[datetime]:
    endpoint, interval = SONDA_POR_FEED[(gap.feed, gap.exchange)]
    pedido = simbolo_de_proveedor(gap.feed, gap.exchange, gap.symbol)
    payload = await client.history(
        endpoint,
        [pedido],
        interval=interval,
        start_ts=int(desde.timestamp()),
        end_ts=int(hasta.timestamp()) - 1,
    )
    marcas = [
        datetime.fromtimestamp(int(fila["t"]), UTC)
        for fila in payload.get(pedido, [])
        if "t" in fila
    ]
    return sorted(marcas)


async def _sondea_ancho(client: CoinalyzeClient, gap: DataGap) -> Sondeo:
    """UNA peticion ancha da los dos numeros: lo de dentro del hueco y lo de alrededor.

    Derivar lo de dentro de la MISMA respuesta que prueba la cobertura es mas fuerte que
    pedirlo aparte: las dos afirmaciones salen del mismo hecho observado, y no puede
    pasar que una peticion vea el tramo servido y la otra no.
    """
    marcas = await _pide(client, gap, gap.start - MARGEN_ANCHO, gap.end + MARGEN_ANCHO)
    dentro = [m for m in marcas if gap.start <= m < gap.end]
    return Sondeo(
        filas_dentro=len(dentro),
        ancha_filas=len(marcas),
        primera=marcas[0] if marcas else None,
        ultima=marcas[-1] if marcas else None,
    )


async def _procesar(
    conn,
    client: CoinalyzeClient,
    gap_id: int,
    control_cache: dict[tuple[str, str, str], int],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT id,feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,"
        "expected_cadence,status,recovery_metadata->>'method' AS metodo FROM data_gap "
        "WHERE id=$1",
        gap_id,
    )
    if row is None:
        return {"gap": gap_id, "accion": "rechazar", "motivo": "no existe"}
    gap = DataGap.from_record(row)
    # Se acepta 'unresolved' y tambien una fila ya archivada SIN method: esa es la
    # reparacion de las 10 del 2026-08-29. Una fila con method escrito no se toca aunque
    # su prueba sea mala: se mira, no se reescribe en silencio.
    if gap.status == "unrecoverable" and row["metodo"] is None:
        reparando = True
    elif gap.status == "unresolved":
        reparando = False
    else:
        return {
            "gap": gap_id,
            "accion": "rechazar",
            "motivo": f"estado '{gap.status}' con method '{row['metodo']}': no se reescribe",
        }
    if (gap.feed, gap.exchange) not in SONDA_POR_FEED:
        return {"gap": gap_id, **decidir(gap, sondeo=None, filas_control=0).__dict__}

    ahora = datetime.now(UTC)
    control_fin = ahora - CONTROL_RETRASO
    control_ini = control_fin - CONTROL_SPAN

    sondeo = await _sondea_ancho(client, gap)
    clave = (gap.feed, gap.exchange, gap.symbol)
    if clave not in control_cache:
        # El control es la MISMA ventana reciente para toda la identidad, asi que se pide
        # una vez. Cachearlo no relaja la prueba: cada fila archivada guarda ese conteo.
        control_cache[clave] = len(await _pide(client, gap, control_ini, control_fin))
    filas_control = control_cache[clave]

    veredicto = decidir(gap, sondeo=sondeo, filas_control=filas_control)
    salida: dict[str, object] = {
        "gap": gap_id,
        "feed": gap.feed,
        "exchange": gap.exchange,
        "symbol": gap.symbol,
        "reparando": reparando,
        "dentro": sondeo.filas_dentro,
        "ancha": sondeo.ancha_filas,
        "control": filas_control,
        "accion": veredicto.accion,
        "motivo": veredicto.motivo,
    }

    if veredicto.accion == "archivar_horizonte":
        salida["filas_archivadas"] = await archive_beyond_source_horizon(
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
    elif veredicto.accion == "archivar_ausencia":
        assert sondeo.primera is not None and sondeo.ultima is not None
        salida["filas_archivadas"] = await archive_source_response_absence(
            conn,
            feed=gap.feed,
            exchange=gap.exchange,
            market=gap.market,
            symbol=gap.symbol,
            granularity=gap.granularity,
            window_start=gap.start,
            window_end=gap.end,
            response_first_bucket=sondeo.primera,
            response_last_bucket=sondeo.ultima,
            # Los dos conteos salen del MISMO Sondeo que dio las dos marcas. No hay
            # opcion de linea de ordenes para ellos y no la va a haber: si se pudieran
            # teclear, la prueba re-derivable seria lo que alguien escribio.
            window_returned_rows=sondeo.filas_dentro,
            response_returned_rows=sondeo.ancha_filas,
            proof_source=PROOF_SOURCE,
        )
    return salida


async def run(gap_ids: list[int]) -> list[dict[str, object]]:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-archive-horizon")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    control_cache: dict[tuple[str, str, str], int] = {}
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL, settings.API_KEY, limiter
        ) as client:
            async with pool.acquire() as conn:
                salidas = []
                for gap_id in gap_ids:
                    salidas.append(await _procesar(conn, client, gap_id, control_cache))
                return salidas
    finally:
        await pool.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archivar huecos que la fuente no sirve, con prueba medida"
    )
    # A PROPOSITO NO HAY --limit NI --all. El unico modo es nombrar los huecos uno a uno:
    # un archivado en masa es como se perdieron 10 filas la noche del 29, y esta
    # herramienta escribe justo en la tabla que aquello ensucio. Que la lista sea larga no
    # es una molestia: es la propiedad. Nadie decide por barrido a quien tocar.
    parser.add_argument("--gap-id", type=int, action="append", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(json.dumps(asyncio.run(run(args.gap_id)), sort_keys=True, default=str))


if __name__ == "__main__":
    main()
