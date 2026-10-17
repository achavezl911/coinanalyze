"""K108-control · reproduce 15 min de flujo REAL (K108-flujo.jsonl.gz, grabado el 2026-10-17 04:02-04:17Z) por el
codigo REAL del colector (app/orderflow.py: interpreta, Almacen, Cobertura, vuelca) contra una base, con el reloj de
la grabacion. Es el sujeto del control: lo que el servicio habria escrito con esos mensajes.

Con --planta se reproduce con UN defecto inyectado en el proceso (el arbol no se toca):
  agresor_okx_swap   el lado de okx_swap al reves (un venue que (a) no puede triangular)
  nivel_float        el nivel calculado en float: floor(float(precio)/float(paso))*paso
  doble_escritura    la reescritura del minuto SUMA en vez de sustituir
  minuto_partido     tras la primera escritura el minuto se vacia, y la reescritura solo lleva lo que llego despues

Uso: K108-reproduce.py <dsn> <flujo.jsonl.gz> [--planta X]
"""

from __future__ import annotations

import asyncio
import gzip
import json
import math
import sys
from decimal import Decimal

import asyncpg

import app.orderflow as of


class _Una:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Una(self.conn)


class _SumaAlReescribir:
    """La conexion vista por un escritor que no borra antes de reescribir y suma en el conflicto."""

    def __init__(self, conn):
        self.conn = conn

    async def executemany(self, q, args):
        if q.lstrip().startswith("DELETE FROM orderflow_celda"):
            return None
        return await self.conn.executemany(q, args)

    async def execute(self, q, *args):
        if "INSERT INTO orderflow_celda" in q:
            q += (" ON CONFLICT (symbol, ts, venue, nivel) DO UPDATE SET"
                  " compra_base = orderflow_celda.compra_base + EXCLUDED.compra_base,"
                  " venta_base = orderflow_celda.venta_base + EXCLUDED.venta_base,"
                  " compra_usd = orderflow_celda.compra_usd + EXCLUDED.compra_usd,"
                  " venta_usd = orderflow_celda.venta_usd + EXCLUDED.venta_usd,"
                  " compras = orderflow_celda.compras + EXCLUDED.compras,"
                  " ventas = orderflow_celda.ventas + EXCLUDED.ventas")
        return await self.conn.execute(q, *args)


def planta(nombre: str) -> None:
    if nombre == "agresor_okx_swap":
        original = of.interpreta

        def torcida(venue, raw):
            ops = original(venue, raw)
            if venue == "okx_swap":
                return [of.Op(o.activo, o.ts_ms, o.precio, o.base, o.usd, not o.compra, o.id) for o in ops]
            return ops

        of.interpreta = torcida
    elif nombre == "nivel_float":
        def en_float(precio, paso):
            return Decimal(repr(math.floor(float(precio) / float(paso)) * float(paso)))

        of.nivel_de = en_float
    elif nombre in ("doble_escritura", "minuto_partido"):
        original = of.escribe_minutos

        async def torcida(conn, alm, minutos, ahora, final, inicio):
            if final:  # la reescritura se hace SIEMPRE: el defecto tiene que verse en todos los minutos
                for (_v, _a, m), mi in alm.minutos.items():
                    if m in minutos:
                        mi.sucio = True
            r = await original(_SumaAlReescribir(conn) if nombre == "doble_escritura" else conn, alm, minutos,
                               ahora, final, inicio)
            if nombre == "minuto_partido" and not final:
                for (_v, _a, m), mi in alm.minutos.items():
                    if m in minutos:
                        mi.celdas, mi.ops = {}, 0
            return r

        of.escribe_minutos = torcida
    elif nombre:
        raise SystemExit(f"planta desconocida: {nombre}")


async def reproduce(dsn: str, fichero: str) -> None:
    with gzip.open(fichero, "rt") as g:
        lineas = [json.loads(x) for x in g]
    lineas.sort(key=lambda d: d["rx"])
    conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
    try:
        inicio = lineas[0]["rx"] / 1000
        pasos = {r["symbol"]: Decimal(r["paso"]) for r in await conn.fetch(
            "SELECT symbol, paso::text AS paso FROM orderflow_paso")}
        # Las particiones de los dias de la grabacion: la base nace hoy y la grabacion es del 2026-10-17.
        await conn.execute("SELECT ensure_temporal_partitions(to_timestamp($1), 1, 2)", inicio)
        alm = of.Almacen(pasos, of.carga_config()["grandes_usd"], inicio)
        pool = _Pool(conn)
        segundo = int(inicio)
        for d in lineas:
            ahora = d["rx"] / 1000
            while segundo < int(ahora):
                segundo += 1
                await of.vuelca(pool, None, alm, float(segundo), inicio)
            cob = alm.coberturas[d["v"]]
            ev = d.get("ev", "")
            if ev.startswith("close") or ev == "fin":
                cob.cierra(ahora)
            elif "raw" in d:
                cob.abre(ahora)
                alm.anade(d["v"], of.interpreta(d["v"], d["raw"]), ahora)
        fin = lineas[-1]["rx"] / 1000
        for cob in alm.coberturas.values():
            cob.cierra(fin)
        await of.vuelca(pool, None, alm, fin, inicio, apagando=True)
        n = await conn.fetchval("SELECT count(*) FROM orderflow_cinta")
        print(f"reproducido: {len(lineas)} mensajes, {n} operaciones en la cinta, app de {of.__file__}")
    finally:
        await conn.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    nombre = ""
    if "--planta" in args:
        i = args.index("--planta")
        nombre = args[i + 1]
        del args[i:i + 2]
    planta(nombre)
    asyncio.run(reproduce(args[0], args[1]))
