#!/usr/bin/env python3
"""Traer una ventana historica de ohlcv del proveedor y guardarla.

EL HUECO EN LA CAJA DE HERRAMIENTAS. Hasta hoy solo habia dos formas de que entrara un
ohlcv: el ciclo vivo del ingest, que pide una ventana de 40 MINUTOS, y recover_gaps.py,
que solo sabe ir donde le señala una fila de data_gap. Para ohlcv 5min NO EXISTE
DETECTOR -- data_gap solo contiene long_short_ratio/5min y ohlcv_1min/1min --, asi que no
hay fila que señale y su historico no tenia NINGUNA via de entrada. El 5min del apagon
del 28 estaba servido por el proveedor y era inalcanzable por falta de herramienta.

POR QUE NO SE DECLARA UNA FILA DE data_gap PARA ENTRAR POR recover_gaps.py. Seria usar la
tabla de huecos como cola de trabajo en vez de como registro de lo detectado, y dejaria
el 5min con aspecto de feed vigilado sin estarlo. El detector de cadencia que le falta es
otro trabajo; adelantarle tres filas a mano no lo hace y sí ensucia lo que ese detector
tendra que reconciliar despues.

LO QUE SE VALIDA, Y LO QUE NO. Cada vela pasa por upsert_ohlcv, que ya rechaza precios no
finitos o incoherentes, volumenes negativos, buy_volume mayor que volume, y -- esto es lo
que importa hoy -- marcas FUERA de la ventana pedida (valid_ts). Contar velas sin mirar
sus marcas es como una respuesta fuera de rango pasa por buena, y asi se publico un
horizonte de 48 h que eran 29.

NO ES TODO O NADA, Y LA DISTINCION IMPORTA. Si el proveedor sirve 159 de 160 buckets se
guardan los 159 y se dice que falta uno. Guardar 159 velas reales no fabrica nada: cada
bucket es un dato independiente. La exigencia de completitud es de la AGREGACION -- una
vela de 5min hecha con 4 minutos es una mentira, y esa guarda vive en rollup_ohlcv_5m --,
no del almacenamiento de crudo. Confundir las dos reglas lleva a abortar un rescate
entero por un bucket, o peor, a rellenar el que falta.

LA PRUEBA DE LO QUE SE TRAJO SE RELEE DE LA BASE, no del valor que devolvio la escritura:
al terminar se cuenta lo que hay ALMACENADO en la ventana y eso es lo que se informa.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime

from app.coinalyze import CoinalyzeClient, PostgresSlidingWindowRateLimiter
from app.config import get_settings
from app.db import create_pool
from app.ingest import upsert_ohlcv

# Declarados por plan, nunca deducidos. Cada intervalo que se anada aqui exige haber
# medido ANTES el horizonte del proveedor PARA ESE INTERVALO: el de 1min ronda las 29 h
# y el de 5min pasa de 96, y tratarlos como el mismo numero ya costo un tramo de datos.
CADENCIA_SEGUNDOS: dict[str, int] = {"1min": 60, "5min": 300}


def buckets_esperados(inicio: datetime, fin: datetime, interval: str) -> int:
    """Cuantos buckets caben en [inicio, fin). Sirve para medir la cobertura, no para
    exigirla."""
    paso = CADENCIA_SEGUNDOS[interval]
    return max(0, int((fin.timestamp() - inicio.timestamp()) // paso))


def _instante(texto: str) -> datetime:
    momento = datetime.fromisoformat(texto)
    if momento.tzinfo is None:
        raise argparse.ArgumentTypeError("la marca tiene que llevar zona horaria explicita")
    return momento.astimezone(UTC)


async def _almacenados(conn, symbol: str, interval: str, inicio: datetime, fin: datetime) -> int:
    return int(
        await conn.fetchval(
            "SELECT count(*) FROM ohlcv WHERE symbol=$1 AND interval=$2 AND ts >= $3 AND ts < $4",
            symbol,
            interval,
            inicio,
            fin,
        )
    )


async def run(
    interval: str, inicio: datetime, fin: datetime, symbols: list[str]
) -> list[dict[str, object]]:
    if interval not in CADENCIA_SEGUNDOS:
        raise SystemExit(f"intervalo '{interval}' no declarado en CADENCIA_SEGUNDOS")
    if fin <= inicio:
        raise SystemExit("la ventana esta vacia o invertida")

    settings = get_settings()
    pool = await create_pool(settings, application_name="coinalyze-backfill-ohlcv")
    limiter = PostgresSlidingWindowRateLimiter(pool, settings.COINALYZE_RATE_LIMIT_UNITS)
    esperados = buckets_esperados(inicio, fin, interval)
    salida: list[dict[str, object]] = []
    try:
        async with CoinalyzeClient(
            settings.COINALYZE_BASE_URL, settings.API_KEY, limiter
        ) as client:
            for symbol in symbols:
                async with pool.acquire() as conn:
                    antes = await _almacenados(conn, symbol, interval, inicio, fin)
                    payload = await client.history(
                        "ohlcv-history",
                        [symbol],
                        interval=interval,
                        start_ts=int(inicio.timestamp()),
                        end_ts=int(fin.timestamp()) - 1,
                    )
                    devueltas = len(payload.get(symbol, []))
                    escritas = await upsert_ohlcv(
                        conn,
                        payload,
                        {symbol: symbol},
                        int(inicio.timestamp()),
                        int(fin.timestamp()),
                        interval,
                    )
                    despues = await _almacenados(conn, symbol, interval, inicio, fin)
                salida.append(
                    {
                        "symbol": symbol,
                        "esperados": esperados,
                        "devueltas": devueltas,
                        "escritas": escritas,
                        "almacenados_antes": antes,
                        "almacenados_despues": despues,
                        "siguen_ausentes": esperados - despues,
                    }
                )
    finally:
        await pool.close()
    return salida


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Traer ohlcv historico del proveedor")
    parser.add_argument("--interval", required=True, choices=sorted(CADENCIA_SEGUNDOS))
    parser.add_argument("--start", required=True, type=_instante, help="ISO con zona, inclusive")
    parser.add_argument("--end", required=True, type=_instante, help="ISO con zona, exclusivo")
    parser.add_argument("--symbol", action="append", help="por defecto, los de settings.SYMBOLS")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    symbols = args.symbol or list(get_settings().SYMBOLS)
    print(json.dumps(asyncio.run(run(args.interval, args.start, args.end, symbols)), sort_keys=True))


if __name__ == "__main__":
    main()
