#!/usr/bin/env python3
"""K111-banco · sirve la pagina del LIBRO del ARBOL sobre una base local con fotos de produccion (campana 145).

    K111-banco.py carga <dsn>   crea en <dsn> las tablas que lee el libro (libro_foto, orderflow_paso) y las llena con
                                K111-fotos.tsv.xz (fotos de produccion bajadas una vez)
    K111-banco.py sirve --puerto P --db <dsn> [--sobre DIR] [--plantado F] [--avisos K111-avisos.jsonl.xz]

Lo que sirve (uvicorn, con la CSP de produccion copiada de app/api.py):
    /libro                       static/libro.html del arbol
    /static/*                    static/ del arbol; si --sobre DIR trae el fichero, ese gana (asi se planta una pagina
                                 que pinta mal SIN tocar el arbol)
    /api/libro/fotos, /ultimo    app/libro_lectura.py DEL ARBOL sobre <dsn>, con el `as_of` de la API
    /api/libro/vivo (websocket)  el del arbol: su relevo escucha NOTIFY libro en <dsn>
    cualquier otra /api/*        503 «banco»
Con --avisos, un ALIMENTADOR publica en <dsn>, por NOTIFY libro, los avisos GRABADOS del relevo de verdad (el colector
del arbol contra los venues, x1-tmp/c145/p3), en bucle y a su ritmo: el relevo del arbol los oye como los del colector.
--plantado F se RELEE en cada peticion (el control cambia el escenario sin reiniciar el banco):
    cantidad           una cantidad de /api/libro/fotos +1 DESPUES de calcularla: lo servido no es lo guardado
    sin_pagina         /libro da 404 (el sujeto sin desplegar)
    sin_ws             el websocket se rechaza (403): la pagina tiene que irse al sondeo de /api/libro/ultimo
    sin_libro:<venue>  el alimentador publica ese venue como libro NO valido, con su motivo
No aplica ninguna regla de K111: sirve. Lo usan K111-control.bash y las capturas de la entrega.
"""

import argparse
import asyncio
import contextlib
import json
import lzma
import subprocess
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "K111-fotos.tsv.xz"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
       "form-action 'none'")
DDL = """
CREATE TABLE orderflow_paso (symbol text PRIMARY KEY, paso numeric NOT NULL);
CREATE TABLE libro_foto (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL, ts_libro timestamptz NOT NULL,
    compra numeric NOT NULL, venta numeric NOT NULL, paso numeric NOT NULL, compra_nivel numeric NOT NULL,
    compras numeric[] NOT NULL, venta_nivel numeric NOT NULL, ventas numeric[] NOT NULL,
    alcance_compra numeric NOT NULL, alcance_venta numeric NOT NULL, PRIMARY KEY (symbol, ts, venue));
"""


def carga(dsn: str) -> int:
    filas: dict[str, list[str]] = {"orderflow_paso": [], "libro_foto": []}
    with lzma.open(FIXTURE, "rt", encoding="utf-8") as f:
        for linea in f:
            tabla, _, resto = linea.rstrip("\n").partition("|")
            filas[tabla].append(resto)
    guion = DDL + "".join(f"COPY {t} FROM STDIN WITH (DELIMITER '|');\n" + "\n".join(xs) + "\n\\.\n"
                          for t, xs in filas.items())
    r = subprocess.run(["psql", dsn, "-X", "-q", "-v", "ON_ERROR_STOP=1"], input=guion, text=True,
                       capture_output=True, timeout=300)
    if r.returncode:
        print(f"carga rc={r.returncode}: {r.stderr[:300]}", file=sys.stderr)
        return 2
    print(" · ".join(f"{t} {len(xs)}" for t, xs in filas.items()))
    return 0


def altera(d: dict) -> dict:
    """Tuerce UNA cantidad de lo servido (la primera compra de la ultima foto que tiene compras), despues de calcularlo."""
    f = next((x for x in reversed(d.get("fotos") or []) if x.get("compras")), None)
    if f is not None:
        q = f["compras"]["cantidades"]
        q[0] = format((Decimal(q[0]) + 1).normalize(), "f")
    return d


def sirve(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(REPO))
    import app as paquete

    if not Path(paquete.__file__).resolve().is_relative_to(REPO):
        raise SystemExit(f"el banco importo app/ de {paquete.__file__}, no del arbol {REPO}")
    import asyncpg
    import uvicorn
    from fastapi import FastAPI, Request, WebSocket
    from fastapi.responses import JSONResponse, Response

    from app import libro_lectura as lec
    from app.orderflow_lectura import Peticion

    sobre = Path(a.sobre) if a.sobre else None
    estado: dict = {}

    def plantado() -> str:
        try:
            return Path(a.plantado).read_text().strip() if a.plantado else ""
        except OSError:
            return ""

    async def alimenta() -> None:
        """Los avisos grabados, en bucle y a su ritmo, por NOTIFY libro en la base del banco."""
        avisos = [json.loads(x) for x in lzma.open(a.avisos, "rt")]
        conn = await asyncpg.connect(a.db)
        try:
            while True:
                t0, r0 = time.time(), avisos[0]["rx"]
                for x in avisos:
                    espera = (x["rx"] - r0) / 1000 - (time.time() - t0)
                    if espera > 0:
                        await asyncio.sleep(espera)
                    carga_ = x["aviso"]
                    p = plantado()
                    if p.startswith("sin_libro:"):
                        d = json.loads(carga_)
                        if d.get("v") == p.split(":", 1)[1]:
                            carga_ = json.dumps({"v": d["v"], "s": d["s"], "x": "plantado por K111-control: libro no valido",
                                                 "e": int(time.time() * 1000)}, separators=(",", ":"))
                    await conn.execute("SELECT pg_notify('libro', $1)", carga_)
                await asyncio.sleep(1)
        finally:
            await conn.close()

    @contextlib.asynccontextmanager
    async def vida(_app):
        estado["pool"] = await asyncpg.create_pool(a.db, min_size=1, max_size=4, server_settings={"timezone": "UTC"})
        tarea = asyncio.create_task(alimenta()) if a.avisos else None
        try:
            yield
        finally:
            if tarea:
                tarea.cancel()
            await estado["pool"].close()

    api = FastAPI(lifespan=vida, openapi_url=None, docs_url=None, redoc_url=None)

    @api.middleware("http")
    async def cabeceras(request: Request, call_next):
        r = await call_next(request)
        r.headers["Content-Security-Policy"] = CSP
        r.headers["Cache-Control"] = "no-store"
        return r

    def fichero(rel: str) -> Response:
        for raiz in ([sobre] if sobre else []) + [REPO / "static"]:
            f = (raiz / rel).resolve()
            if f.is_relative_to(raiz.resolve()) and f.is_file():
                return Response(f.read_bytes(), media_type=TIPOS.get(f.suffix, "application/octet-stream"))
        return JSONResponse({"detail": "Not Found"}, status_code=404)

    def as_of() -> str:
        return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @api.get("/libro")
    async def pagina() -> Response:
        if plantado() == "sin_pagina":
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        return fichero("libro.html")

    @api.get("/static/{rel:path}")
    async def estatico(rel: str) -> Response:
        return fichero(rel)

    @api.get("/api/libro/fotos")
    async def fotos(request: Request) -> Response:
        q = dict(request.query_params)
        try:
            async with estado["pool"].acquire() as conn:
                d = await lec.fotos(conn, symbol=q.get("symbol") or "", desde=q.get("desde"), hasta=q.get("hasta"),
                                    venues=q.get("venues"), paso=q.get("paso"),
                                    cada=int(q["cada"]) if q.get("cada") else None)
        except Peticion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        if plantado() == "cantidad":
            d = altera(d)
        return JSONResponse({**d, "as_of": as_of()})

    @api.get("/api/libro/ultimo")
    async def ultimo(request: Request) -> Response:
        try:
            d = await lec.ultimo(estado["pool"], a.db, dict(request.query_params))
        except Peticion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        return JSONResponse({**d, "as_of": as_of()})

    @api.websocket("/api/libro/vivo")
    async def vivo(ws: WebSocket) -> None:
        prohibido = "plantado por K111-control: el websocket no pasa" if plantado() == "sin_ws" else None
        await lec.vivo(ws, estado["pool"], a.db, prohibido)

    @api.get("/api/{resto:path}")
    async def otra(resto: str) -> Response:
        return JSONResponse({"detail": f"banco: aqui no se sirve /api/{resto}"}, status_code=503)

    uvicorn.run(api, host="127.0.0.1", port=a.puerto, log_level="warning")
    return 0


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "carga":
        return carga(sys.argv[2])
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=("sirve",))
    ap.add_argument("--puerto", type=int, required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--sobre")
    ap.add_argument("--plantado")
    ap.add_argument("--avisos")
    return sirve(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
