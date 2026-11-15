"""A9 (DATOS A, F7-H1): repone desde los aggTrades PUBLICOS de Binance (REST, sin claves) los minutos del footprint de
binance_spot y binance_usdm que quedaron PARCIALES (orderflow_cobertura.segundos < 60).

USO:  python3 scripts/orderflow_repone_binance.py --dsn DSN --desde 2026-11-14T00:00Z --hasta 2026-11-14T06:00Z
          [--venue binance_usdm] [--escribe] [--contraste 5]

Sin --escribe solo LISTA lo que haria (minuto, operaciones que trae el REST, segundos que tenia). Con --escribe, por
minuto y en UNA transaccion, con el cerrojo de la suma horaria (app.orderflow.HORA_CERROJO):
  - quita la marca de su hora (orderflow_hora_hecha): la suma la rehace el servicio, como cuando reescribe un minuto;
  - DELETE + INSERT de las celdas de ESE (minuto, venue, activo) y nada mas (la cinta no se toca);
  - su cobertura a 60 s con las operaciones del REST;
  - lo deja escrito: una fila 'recovered' en data_gap (detection_source scripts.orderflow_repone_binance, el numero
    de operaciones y el rango de ids de agregado en recovery_metadata).
Idempotente: solo elige minutos con segundos < 60 y ya definitivos; uno repuesto sale con 60 y no se vuelve a elegir,
y la fila de data_gap entra con ON CONFLICT DO NOTHING.
--contraste N reconstruye N minutos ENTEROS (60 s) del rango y los compara con sus celdas, sin escribir: lo primero que
se corre, para saber si el REST da lo mismo que el websocket (no esta medido).
Las celdas salen con la definicion del servicio: app.orderflow.interpreta (el mismo mensaje aggTrade) y nivel_de.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import orderflow as OF  # noqa: E402

FUENTE = "scripts.orderflow_repone_binance"
URL = {"binance_spot": "https://api.binance.com/api/v3/aggTrades",
       "binance_usdm": "https://fapi.binance.com/fapi/v1/aggTrades"}
LIMITE = 1000          # el maximo de aggTrades por peticion en los dos
PAUSA_S = 0.25         # entre peticiones: peso 20 (fapi) de 2400/min, holgado

PARCIALES_SQL = """
SELECT ts, venue, symbol, segundos FROM orderflow_cobertura
 WHERE venue = ANY($1::text[]) AND ts >= $2 AND ts < $3 AND definitivo AND segundos {op} 60
 ORDER BY ts, venue, symbol"""
CELDAS_SQL = """INSERT INTO orderflow_celda(ts,venue,symbol,nivel,compra_base,venta_base,compra_usd,venta_usd,
                                            compras,ventas)
   SELECT * FROM unnest($1::timestamptz[],$2::text[],$3::text[],$4::numeric[],$5::numeric[],
                        $6::numeric[],$7::numeric[],$8::numeric[],$9::int[],$10::int[])"""
COBERTURA_SQL = """UPDATE orderflow_cobertura SET segundos = 60, operaciones = $4, definitivo = true, escrito = now()
                    WHERE symbol = $1 AND ts = $2 AND venue = $3 AND segundos < 60"""
RECUPERADO_SQL = """
INSERT INTO data_gap(feed,feed_class,exchange,market,symbol,granularity,start_ts,end_ts,evidence_type,
                     detection_reason,detection_source,status,resolved_at,recovered_at,recovered_by,
                     resolution_reason,recovery_metadata)
VALUES ('orderflow','event_stream',$1,$2,$3,'event',$4::timestamptz,$4::timestamptz + interval '1 minute','disconnect',$5,$6,'recovered',
        now(),now(),$6,'repuesto desde los aggTrades publicos de Binance (REST)',$7::jsonb)
ON CONFLICT DO NOTHING"""


def trae_http(url: str, params: dict) -> list[dict]:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        datos = json.loads(r.read())
    time.sleep(PAUSA_S)
    if not isinstance(datos, list):
        raise RuntimeError(f"respuesta inesperada de {url}: {str(datos)[:200]}")
    return datos


def ops_del_minuto(trae, venue: str, activo: str, minuto: int) -> list[OF.Op]:
    """Las operaciones de [minuto, minuto+60) por paginas de LIMITE (fromId tras la primera)."""
    inst = OF.MERCADOS[venue].instrumentos[activo]
    ini, fin = minuto * 1000, minuto * 1000 + 59_999
    lote = trae(URL[venue], {"symbol": inst, "startTime": ini, "endTime": fin, "limit": LIMITE})
    ops: list[OF.Op] = []
    while True:
        for x in lote:
            if not ini <= int(x["T"]) <= fin:
                return ops
            ops.extend(OF.interpreta(venue, json.dumps({"data": {**x, "e": "aggTrade", "s": inst}})))
        if len(lote) < LIMITE:
            return ops
        lote = trae(URL[venue], {"symbol": inst, "fromId": int(lote[-1]["a"]) + 1, "limit": LIMITE})


def celdas(ops: list[OF.Op], paso: Decimal) -> dict[Decimal, list]:
    """nivel -> [compra_base, venta_base, compra_usd, venta_usd, compras, ventas], como Almacen.anota."""
    out: dict[Decimal, list] = {}
    vistos: set[str] = set()
    for op in ops:
        if op.precio <= 0 or op.base <= 0 or op.usd <= 0 or op.id in vistos:
            continue
        vistos.add(op.id)
        c = out.setdefault(OF.nivel_de(op.precio, paso), [OF.ZERO, OF.ZERO, OF.ZERO, OF.ZERO, 0, 0])
        k = 0 if op.compra else 1
        c[k] += op.base
        c[2 + k] += op.usd
        c[4 + k] += 1
    return out


async def _pasos(conn) -> dict[str, Decimal]:
    return {r["symbol"]: Decimal(r["paso"]) for r in await conn.fetch("SELECT symbol, paso::text AS paso FROM "
                                                                      "orderflow_paso")}


async def repone(conn, desde: datetime, hasta: datetime, trae=trae_http, venues=tuple(URL), escribe: bool = False,
                 log=print) -> list[dict]:
    """Un informe por minuto parcial: {ts, venue, symbol, segundos, operaciones, niveles, escrito}."""
    pasos = await _pasos(conn)
    informe = []
    for r in await conn.fetch(PARCIALES_SQL.format(op="<"), list(venues), desde, hasta):
        ts, venue, activo = r["ts"], r["venue"], r["symbol"]
        ops = ops_del_minuto(trae, venue, activo, int(ts.timestamp()))
        cs = celdas(ops, pasos[activo])
        n = sum(c[4] + c[5] for c in cs.values())
        fila = {"ts": ts.isoformat(), "venue": venue, "symbol": activo, "segundos": r["segundos"],
                "operaciones": n, "niveles": len(cs), "escrito": False}
        if escribe:
            ids = sorted(int(o.id) for o in ops)
            meta = {"method": "binance_aggtrades_rest", "url": URL[venue], "operaciones": n,
                    "segundos_antes": r["segundos"], "agg_id": [ids[0], ids[-1]] if ids else None}
            async with conn.transaction():
                await conn.execute(OF.HORA_CERROJO)
                await conn.execute(OF.DESMARCA_SQL, [activo], [ts], [venue])
                await conn.execute("DELETE FROM orderflow_celda WHERE symbol=$1 AND ts=$2 AND venue=$3",
                                   activo, ts, venue)
                if cs:
                    await conn.execute(CELDAS_SQL, *map(list, zip(*[
                        (ts, venue, activo, nivel, *c) for nivel, c in sorted(cs.items())], strict=True)))
                await conn.execute(COBERTURA_SQL, activo, ts, venue, n)
                await conn.execute(RECUPERADO_SQL, venue, OF.MERCADOS[venue].mercado, activo, ts,
                                   f"orderflow: minuto con {r['segundos']} s de 60 en orderflow_cobertura", FUENTE,
                                   json.dumps(meta))
            fila["escrito"] = True
        log(json.dumps(fila))
        informe.append(fila)
    return informe


async def contraste(conn, desde: datetime, hasta: datetime, n: int, trae=trae_http, venues=tuple(URL),
                    log=print) -> list[dict]:
    """Reconstruye n minutos ENTEROS y los compara con sus celdas escritas por el websocket. No escribe."""
    pasos = await _pasos(conn)
    out = []
    for r in (await conn.fetch(PARCIALES_SQL.format(op="="), list(venues), desde, hasta))[:n]:
        ts, venue, activo = r["ts"], r["venue"], r["symbol"]
        rest = celdas(ops_del_minuto(trae, venue, activo, int(ts.timestamp())), pasos[activo])
        ws = {x["nivel"]: [x["compra_base"], x["venta_base"], x["compra_usd"], x["venta_usd"], x["compras"],
                           x["ventas"]]
              for x in await conn.fetch("SELECT * FROM orderflow_celda WHERE symbol=$1 AND ts=$2 AND venue=$3",
                                        activo, ts, venue)}
        distintos = sorted(str(k) for k in set(rest) | set(ws) if rest.get(k) != ws.get(k))
        fila = {"ts": ts.isoformat(), "venue": venue, "symbol": activo, "niveles": len(ws),
                "iguales": not distintos, "distintos": distintos[:10]}
        log(json.dumps(fila))
        out.append(fila)
    return out


def _momento(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


async def _main(a) -> int:
    import asyncpg

    conn = await asyncpg.connect(a.dsn)
    try:
        venues = tuple(a.venue) if a.venue else tuple(URL)
        if a.contraste:
            filas = await contraste(conn, _momento(a.desde), _momento(a.hasta), a.contraste, venues=venues)
            return 0 if all(f["iguales"] for f in filas) else 1
        await repone(conn, _momento(a.desde), _momento(a.hasta), venues=venues, escribe=a.escribe)
        return 0
    finally:
        await conn.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--dsn", required=True)
    p.add_argument("--desde", required=True)
    p.add_argument("--hasta", required=True)
    p.add_argument("--venue", action="append", choices=sorted(URL))
    p.add_argument("--escribe", action="store_true")
    p.add_argument("--contraste", type=int, default=0, metavar="N")
    return asyncio.run(_main(p.parse_args(argv)))


if __name__ == "__main__":
    sys.exit(main())
