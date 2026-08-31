#!/usr/bin/env python3
"""Recuperacion acotada de huecos, con adaptadores de identidad EXACTA.

Solo puede recuperar una fila el adaptador registrado para su
feed/exchange/market/granularity exactos. Para los flujos de sucesos en tiempo real y
para el libro no hay fuente historica con la misma semantica, asi que esos huecos se
clasifican como irrecuperables en vez de sintetizarlos o sustituirlos de otra bolsa.

NO HAY --limit NI --all, Y ES LA LECCION MAS CARA DE ESTE FICHERO. La cabecera de
harness/checks/K04-huecos.sh ya lo decia: un simple `recover_gaps.py --limit 1000` habria
marcado 265 huecos como irrecuperables, habria puesto el check en VERDE EN EL ACTO, no
habria recuperado un solo dato y habria dejado la fuga invisible. La noche del 2026-08-29
un --limit dejo 10 filas 'unrecoverable' con recovery_metadata='{}' -- sin prueba --, que
es justo lo que K04 v3 rechaza y lo que costo la sesion del 30 en repararlo. El unico modo
es nombrar los huecos uno a uno. Que la lista sea larga no es una molestia: es la
propiedad. Nadie decide por barrido a quien tocar.

LA IDENTIDAD SE TRADUCE EN LOS DOS SENTIDOS, y equivocar el segundo es la trampa de #108
una capa mas abajo. data_gap guarda el simbolo CANONICO para las dos bolsas; el proveedor
quiere BTCUSDT_PERP.A para binance y BTCUSDT.6 para bybit EN EL MISMO endpoint. Asi que:
  canonico -> proveedor   para PEDIR      (simbolo_de_proveedor, lo de #108)
  proveedor -> canonico   para GUARDAR    (aqui se hace re-etiquetando en fetch)
El ciclo vivo hace lo mismo con dos mapas distintos: `identity` para open_interest,
funding_rate y predicted_funding_rate, y `bybit_inverse` para oi_bybit (ingest.py:792-794,
:840). Aqui se traduce UNA vez, al pedir, y a partir de ahi todo es canonico -- que es
ademas lo que exige validate_recovery, que compara la identidad de cada observacion contra
la del hueco y revienta si no coinciden.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.data_gaps import (
    DataGap,
    RecoveryAdapter,
    RecoveryObservation,
    RecoveryValidationError,
    recover_unresolved_gaps,
)
from app.db import create_pool
from app.ingest import upsert_long_short, upsert_ohlc_metric, upsert_ohlcv

# La traduccion canonico -> proveedor vive en UN solo sitio y se importa, no se copia:
# harness/checks/K71 la EJECUTA, asi que una segunda copia seria una que nadie vigila.
from scripts.archive_beyond_horizon import simbolo_de_proveedor


class CoinalyzeOhlcv1mAdapter:
    """Exact Binance perpetual 1-minute OHLCV recovery from the existing provider."""

    name = "coinalyze.ohlcv-history"
    feed = "ohlcv_1min"
    exchange = "binance"
    market = "perpetual"
    granularity = "1min"

    def __init__(self, client: CoinalyzeClient) -> None:
        self.client = client

    async def fetch(self, gap: DataGap) -> list[RecoveryObservation]:
        payload = await self.client.history(
            "ohlcv-history",
            [gap.symbol],
            interval="1min",
            start_ts=int(gap.start.timestamp()),
            end_ts=int(gap.end.timestamp()) - 1,
        )
        observations: list[RecoveryObservation] = []
        for row in payload.get(gap.symbol, []):
            try:
                timestamp = datetime.fromtimestamp(int(row["t"]), UTC)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RecoveryValidationError("invalid OHLCV recovery timestamp") from exc
            observations.append(
                RecoveryObservation(
                    timestamp=timestamp,
                    key=f"{gap.symbol}:1min:{int(timestamp.timestamp())}",
                    feed=self.feed,
                    exchange=self.exchange,
                    market=self.market,
                    symbol=gap.symbol,
                    granularity=self.granularity,
                    payload=row,
                )
            )
        return sorted(observations, key=lambda item: item.timestamp)

    async def persist(self, conn, observations) -> None:
        if not observations:
            raise RecoveryValidationError("no validated OHLCV observations to persist")
        symbol = observations[0].symbol
        payload = {symbol: [item.payload for item in observations]}
        count = await upsert_ohlcv(
            conn,
            payload,
            {symbol: symbol},
            int(observations[0].timestamp.timestamp()),
            int(observations[-1].timestamp.timestamp()),
            "1min",
        )
        if count != len(observations):
            raise RecoveryValidationError("validated OHLCV rows were not all persistable")


@dataclass(frozen=True)
class PlanMetrica:
    """Todo lo que distingue a un feed de metricas de otro. Declarado, nunca deducido.

    convert_to_usd NO ES UN DETALLE: el ciclo vivo pide open-interest-history con
    convert_to_usd=True (ingest.py:796-805) y funding/predicted SIN el. Recuperar el
    interes abierto sin la conversion guardaria OTRA UNIDAD en la misma columna, y nada
    reventaria: seria una fila que parece buena y no lo es. Por eso viaja con el plan y no
    con un default.
    """

    feed: str
    exchange: str
    endpoint: str
    table: str
    prefix: str
    convert_to_usd: bool | None


# Los cuatro feeds de metricas de 5 min que el ciclo vivo escribe. Las tablas y los
# prefijos son los que valida upsert_ohlc_metric (ingest.py:250) contra su lista blanca de
# cuatro parejas: si aqui se pusiera otra, revienta ahi en vez de escribir en la tabla
# equivocada. long_short_ratio SIGUE SIN ESTAR aqui, y ya no por falta de medida: su
# tabla no es (o,h,l,c) sino long_pct/short_pct/ratio, o sea otro escritor, asi que vive
# en CoinalyzeLongShortAdapter y no en este plan.
PLANES_METRICA: tuple[PlanMetrica, ...] = (
    PlanMetrica("open_interest_5min", "binance", "open-interest-history",
                "open_interest", "oi", True),
    PlanMetrica("open_interest_5min", "bybit", "open-interest-history",
                "oi_bybit", "oi", True),
    PlanMetrica("funding_rate", "binance", "funding-rate-history",
                "funding_rate", "fr", None),
    PlanMetrica("predicted_funding_rate", "binance", "predicted-funding-rate-history",
                "predicted_funding_rate", "pfr", None),
)


class CoinalyzeMetricAdapter:
    """Recuperacion exacta de un feed de metricas de 5 min desde el mismo proveedor."""

    market = "perpetual"
    granularity = "5min"

    def __init__(self, client: CoinalyzeClient, plan: PlanMetrica) -> None:
        self.client = client
        self.plan = plan
        self.name = f"coinalyze.{plan.endpoint}@{plan.exchange}"
        self.feed = plan.feed
        self.exchange = plan.exchange

    async def fetch(self, gap: DataGap) -> list[RecoveryObservation]:
        # PEDIR con el simbolo del proveedor y RE-ETIQUETAR a canonico en el acto. A
        # partir de aqui nada vuelve a ver el simbolo del proveedor, que es lo que impide
        # que se cuele en la tabla o en la comparacion de identidad.
        pedido = simbolo_de_proveedor(gap.feed, gap.exchange, gap.symbol)
        payload = await self.client.history(
            self.plan.endpoint,
            [pedido],
            interval=self.granularity,
            start_ts=int(gap.start.timestamp()),
            end_ts=int(gap.end.timestamp()) - 1,
            convert_to_usd=self.plan.convert_to_usd,
        )
        observations: list[RecoveryObservation] = []
        for row in payload.get(pedido, []):
            try:
                timestamp = datetime.fromtimestamp(int(row["t"]), UTC)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RecoveryValidationError("invalid metric recovery timestamp") from exc
            observations.append(
                RecoveryObservation(
                    timestamp=timestamp,
                    key=f"{gap.symbol}:{self.granularity}:{int(timestamp.timestamp())}",
                    feed=self.feed,
                    exchange=self.exchange,
                    market=self.market,
                    symbol=gap.symbol,
                    granularity=self.granularity,
                    payload=row,
                )
            )
        return sorted(observations, key=lambda item: item.timestamp)

    async def persist(self, conn, observations) -> None:
        if not observations:
            raise RecoveryValidationError("no validated metric observations to persist")
        symbol = observations[0].symbol
        payload = {symbol: [item.payload for item in observations]}
        count = await upsert_ohlc_metric(
            conn,
            self.plan.table,
            self.plan.prefix,
            payload,
            # Identidad: ya se re-etiqueto a canonico al pedir. Volver a traducir aqui
            # seria traducir dos veces y dejar el simbolo del proveedor en la tabla.
            {symbol: symbol},
            int(observations[0].timestamp.timestamp()),
            int(observations[-1].timestamp.timestamp()),
        )
        if count != len(observations):
            raise RecoveryValidationError(
                "validated metric rows were not all persistable"
            )


class CoinalyzeLongShortAdapter:
    """Recuperacion exacta de long_short_ratio, que NO cabe en PLANES_METRICA.

    Y no cabe por una razon de forma, no de gusto: upsert_ohlc_metric (ingest.py:250)
    valida su tabla contra una lista blanca de cuatro parejas y escribe columnas
    (o,h,l,c). long_short_ratio guarda long_pct/short_pct/ratio, o sea OTRO escritor --
    upsert_long_short, ingest.py:326 --. Meterlo en el plan habria reventado alli en vez
    de escribir en la tabla equivocada, que es justo para lo que sirve aquella lista
    blanca, pero no habria recuperado nada.

    upsert_long_short DESCARTA en silencio la fila incoherente (l+s lejos de 100, o
    ratio negativo) en vez de normalizarla. Ese silencio es correcto en el ciclo vivo y
    seria veneno aqui: dejaria el hueco marcado 'recovered' con menos buckets de los que
    validate_recovery acaba de exigir. La comparacion count != len(observations) lo
    convierte en un fallo duro, y es la misma guarda que llevan los otros dos
    adaptadores por el mismo motivo.
    """

    name = "coinalyze.long-short-ratio-history"
    feed = "long_short_ratio"
    exchange = "binance"
    market = "perpetual"
    granularity = "5min"

    def __init__(self, client: CoinalyzeClient) -> None:
        self.client = client

    async def fetch(self, gap: DataGap) -> list[RecoveryObservation]:
        pedido = simbolo_de_proveedor(gap.feed, gap.exchange, gap.symbol)
        payload = await self.client.history(
            "long-short-ratio-history",
            [pedido],
            interval=self.granularity,
            start_ts=int(gap.start.timestamp()),
            end_ts=int(gap.end.timestamp()) - 1,
        )
        observations: list[RecoveryObservation] = []
        for row in payload.get(pedido, []):
            try:
                timestamp = datetime.fromtimestamp(int(row["t"]), UTC)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise RecoveryValidationError(
                    "invalid long/short recovery timestamp"
                ) from exc
            observations.append(
                RecoveryObservation(
                    timestamp=timestamp,
                    key=f"{gap.symbol}:{self.granularity}:{int(timestamp.timestamp())}",
                    feed=self.feed,
                    exchange=self.exchange,
                    market=self.market,
                    symbol=gap.symbol,
                    granularity=self.granularity,
                    payload=row,
                )
            )
        return sorted(observations, key=lambda item: item.timestamp)

    async def persist(self, conn, observations) -> None:
        if not observations:
            raise RecoveryValidationError("no validated long/short observations to persist")
        symbol = observations[0].symbol
        payload = {symbol: [item.payload for item in observations]}
        count = await upsert_long_short(
            conn,
            payload,
            {symbol: symbol},
            int(observations[0].timestamp.timestamp()),
            int(observations[-1].timestamp.timestamp()),
        )
        if count != len(observations):
            raise RecoveryValidationError(
                "validated long/short rows were not all persistable"
            )


def construir_adaptadores(client: CoinalyzeClient) -> dict[tuple[str, ...], RecoveryAdapter]:
    """Registro indexado por la identidad EXACTA que compara validate_recovery."""
    adaptadores: dict[tuple[str, ...], RecoveryAdapter] = {}
    ohlcv = CoinalyzeOhlcv1mAdapter(client)
    adaptadores[(ohlcv.feed, ohlcv.exchange, ohlcv.market, ohlcv.granularity)] = ohlcv
    ls = CoinalyzeLongShortAdapter(client)
    adaptadores[(ls.feed, ls.exchange, ls.market, ls.granularity)] = ls
    for plan in PLANES_METRICA:
        adaptador = CoinalyzeMetricAdapter(client, plan)
        clave = (adaptador.feed, adaptador.exchange, adaptador.market, adaptador.granularity)
        if clave in adaptadores:
            raise ValueError(f"dos adaptadores para la misma identidad: {clave}")
        adaptadores[clave] = adaptador
    return adaptadores


def exact_adapter_for(
    gap: DataGap,
    adapters: dict[tuple[str, ...], RecoveryAdapter],
    allowed_symbols: frozenset[str],
) -> RecoveryAdapter | None:
    """Devolver SOLO un adaptador con la misma semantica de fuente y el mismo simbolo.

    Caer a ``None`` marca el hueco irrecuperable; nunca sustituye OHLCV por trades, ni
    otra bolsa, ni otro mercado, ni otra granularidad, ni sintetiza el libro.
    """
    if gap.symbol not in allowed_symbols:
        return None
    return adapters.get((gap.feed, gap.exchange, gap.market, gap.granularity))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover explicit market-data gaps safely")
    # A PROPOSITO NO HAY --limit NI --all: ver la cabecera. Marcar 'unrecoverable' sin
    # prueba es una escritura tan definitiva como cualquier otra, y por barrido no se
    # hace. `recover_unresolved_gaps` solo se llama desde aqui -- no hay caller en el
    # ciclo vivo --, asi que cerrar esta puerta la cierra entera.
    parser.add_argument("--gap-id", type=int, action="append", required=True)
    return parser.parse_args()


async def run(gap_ids: list[int]) -> list[dict[str, object]]:
    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-recover-gaps")
    limiter = PostgresSlidingWindowRateLimiter(
        pool,
        settings.COINALYZE_RATE_LIMIT_UNITS,
    )
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL,
            settings.API_KEY,
            limiter,
        ) as client:
            adaptadores = construir_adaptadores(client)
            allowed_symbols = frozenset(settings.SYMBOLS)
            salidas: list[dict[str, object]] = []
            async with pool.acquire() as conn:
                for gap_id in gap_ids:
                    counts = await recover_unresolved_gaps(
                        conn,
                        lambda gap: exact_adapter_for(gap, adaptadores, allowed_symbols),
                        gap_id=gap_id,
                        limit=1,
                    )
                    salidas.append({"gap": gap_id, **dict(counts)})
            return salidas
    finally:
        await pool.close()


def main() -> None:
    args = parse_args()
    print(json.dumps(asyncio.run(run(args.gap_id)), sort_keys=True, default=str))


if __name__ == "__main__":
    main()
