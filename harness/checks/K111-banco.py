#!/usr/bin/env python3
"""K111-banco · sirve la pagina del LIBRO del ARBOL sobre una base local con fotos de produccion (campana 145).

    K111-banco.py carga <dsn> [sujeto]   crea en <dsn> las tablas que lee el libro (libro_foto, orderflow_paso) y las
                                         llena con K111-fotos.tsv.xz (fotos de produccion bajadas una vez: las de las
                                         vistas de 03:30Z y, del remate, las de R1 hasta 06:00Z) u otro sujeto del mismo
                                         formato
    K111-banco.py sirve --puerto P --db <dsn> [--sobre DIR] [--plantado F] [--avisos K111-avisos.jsonl.xz]

Lo que sirve (uvicorn, con la CSP de produccion copiada de app/api.py):
    /libro                       static/libro.html del arbol
    /static/*                    static/ del arbol; si --sobre DIR trae el fichero, ese gana (asi se planta una pagina
                                 que pinta mal SIN tocar el arbol)
    /api/libro/fotos, /ultimo    app/libro_lectura.py DEL ARBOL sobre <dsn>, con el `as_of` de la API
    /api/libro/vivo (websocket)  el del arbol: su relevo escucha NOTIFY libro en <dsn>
    /api/libro/honda             (149 B) la capa honda DE MENTIRA, determinista, sacada de las fotos de <dsn>: una foto
                                 cada 30 s por venue de libro_honda (okx_swap, okx_spot, bitget_usdt; bitget solo
                                 compra) que arranca TRES pasos dentro del libro vivo (la pagina tiene que dejar mandar
                                 al vivo) y llega al 1 % (ETH al 2 %), con muros cada 37 niveles; okx_swap calla 2 min
                                 de cada 20 (mas de 75 s: la pagina no puede estirar la de antes) y sirve una rancia
                                 de cada 40. En vivo (149 B r1), las de los ultimos 150 s, alrededor de la mejor
                                 compra / venta del relevo del banco por ese venue, memorizadas
    /api/orderflow/footprint     (149 B) el footprint 1m DE MENTIRA: por minuto, nueve niveles alrededor del medio de la
                                 primera foto del minuto, compra y venta deterministas; desde/hasta con la regla de
                                 la ruta real (app.orderflow_lectura.instante y ventana): fuera del borde de vela, 422
    cualquier otra /api/*        503 «banco»
Con --avisos, un ALIMENTADOR publica en <dsn>, por NOTIFY libro, los avisos GRABADOS del relevo de verdad (el colector
del arbol contra los venues, x1-tmp/c145/p3), en bucle y a su ritmo: el relevo del arbol los oye como los del colector.
--plantado F se RELEE en cada peticion (el control cambia el escenario sin reiniciar el banco):
    cantidad           una cantidad de /api/libro/fotos +1 DESPUES de calcularla: lo servido no es lo guardado
    sin_pagina         /libro da 404 (el sujeto sin desplegar)
    sin_ws             el websocket se rechaza (403): la pagina tiene que irse al sondeo de /api/libro/ultimo
    sin_libro:<venue>  desde 1.5 s despues de la ultima carga de /libro, el alimentador publica ese venue como libro NO
                       valido, con su motivo (antes, sus avisos de verdad: la pagina llega a tener su libro)
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
HONDA = {"okx_swap": True, "okx_spot": True, "bitget_usdt": False}  # venue -> sirve ventas
HONDA_PASO = {"BTC": Decimal("10"), "ETH": Decimal("0.5"), "SOL": Decimal("0.02")}  # el paso guardado (libro_honda)
HONDA_ALCANCE = {"BTC": Decimal("0.01"), "ETH": Decimal("0.02"), "SOL": Decimal("0.011")}
DDL = """
CREATE TABLE orderflow_paso (symbol text PRIMARY KEY, paso numeric NOT NULL);
CREATE TABLE libro_foto (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL, ts_libro timestamptz NOT NULL,
    compra numeric NOT NULL, venta numeric NOT NULL, paso numeric NOT NULL, compra_nivel numeric NOT NULL,
    compras numeric[] NOT NULL, venta_nivel numeric NOT NULL, ventas numeric[] NOT NULL,
    alcance_compra numeric NOT NULL, alcance_venta numeric NOT NULL, PRIMARY KEY (symbol, ts, venue));
"""


BORDE_S = 4  # el borde del libro vivo late con este semiperiodo (borde_que_late)
CINTA_CICLO_MS = 8000  # la cinta del banco: CINTA_POR_CICLO operaciones cada 8 s
CINTA_POR_CICLO = 14


def carga(dsn: str, sujeto: Path = FIXTURE) -> int:
    filas: dict[str, list[str]] = {"orderflow_paso": [], "libro_foto": []}
    with lzma.open(sujeto, "rt", encoding="utf-8") as f:
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
    from app.orderflow_lectura import MARCOS, RANGO_MAXIMO, Peticion, instante, ventana

    sobre = Path(a.sobre) if a.sobre else None
    estado: dict = {"carga": 0.0, "ref": {}, "ops": {}, "mejor": {}, "honda_viva": {}}

    def plantado() -> str:
        try:
            return Path(a.plantado).read_text().strip() if a.plantado else ""
        except OSError:
            return ""

    def borde_que_late(carga_: str) -> str:
        """Cuatro segundos si, cuatro no, cada libro pierde su 40 % mas lejano por los dos lados: el borde se mueve
        siempre durante los 20 s de raton quieto, y la rejilla se ejercita por construccion, no por el mercado."""
        if int(time.time() / BORDE_S) % 2 == 0:
            return carga_
        try:
            d = json.loads(carga_)
            for lado, k in (("c", "kc"), ("v", "kv")):
                if isinstance(d.get(lado), list) and len(d[lado]) > 4:
                    d[lado] = d[lado][: max(2, len(d[lado]) * 6 // 10)]
                    d[k] = len(d[lado])
        except (TypeError, ValueError):
            return carga_
        return json.dumps(d, separators=(",", ":"))

    async def alimenta() -> None:
        """Los avisos grabados, en bucle y a su ritmo, por NOTIFY libro en la base del banco."""
        with lzma.open(a.avisos, "rt") as f:
            avisos = [json.loads(x) for x in f]
        conn = await asyncpg.connect(a.db)
        try:
            while True:
                t0, r0 = time.time(), avisos[0]["rx"]
                for x in avisos:
                    espera = (x["rx"] - r0) / 1000 - (time.time() - t0)
                    if espera > 0:
                        await asyncio.sleep(espera)
                    carga_ = x["aviso"]
                    with contextlib.suppress(KeyError, TypeError, ValueError):
                        d = json.loads(carga_)
                        estado["ref"][d["s"]] = ((float(d["b"]) + float(d["a"])) / 2, float(d.get("p") or 1))
                        estado["mejor"][(d["s"], d["v"])] = (str(d["b"]), str(d["a"]))
                    carga_ = borde_que_late(carga_)
                    p = plantado()
                    if p.startswith("sin_libro:") and time.time() - estado["carga"] > 1.5:
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
        estado["carga"] = time.time()
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

    def ops_ciclo(sym: str, venues: list[str], c: int) -> list[dict]:
        """Las operaciones de un ciclo de CINTA_CICLO_MS, una vez y para siempre (el mismo id, el mismo precio)."""
        clave = (sym, ",".join(venues), c)
        if clave not in estado["ops"]:
            ref = estado["ref"].get(sym)
            out = []
            for j in range(CINTA_POR_CICLO if ref and venues else 0):
                mid, paso = ref
                precio = round(mid + (((c * 7 + j * 5) % 9) - 4) * paso * 5, 2)
                base = round(0.001 * (1 + (c * 13 + j * 29) % 50), 3)
                ms = c * CINTA_CICLO_MS + (j * 571 + c * 37) % CINTA_CICLO_MS
                out.append({"ts": datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds")
                            .replace("+00:00", "Z"), "venue": venues[(c + j) % len(venues)], "precio": str(precio),
                            "base": base, "usd": round(base * precio, 2), "agresor": "compra" if (c + j) % 3 else "venta",
                            "id": f"{c}-{j}", "_ms": ms})
            estado["ops"][clave] = out
            if len(estado["ops"]) > 4000:
                estado["ops"].pop(next(iter(estado["ops"])))
        return estado["ops"][clave]

    @api.get("/api/orderflow/cinta")
    async def cinta(symbol: str, venues: str = "", minutos: int = 1, limit: int = 1000) -> Response:
        """La cinta de un fixture pequeno RE-FECHADO a la hora de la peticion: ciclos fijos, ids estables."""
        if plantado() == "sin_cinta":
            return JSONResponse({"detail": "banco: cinta plantada como caida por K111-control"}, status_code=503)
        vs = [v for v in venues.split(",") if v]
        ahora = int(time.time() * 1000)
        desde = ahora - minutos * 60000
        ops = [o for c in range(desde // CINTA_CICLO_MS, ahora // CINTA_CICLO_MS + 1) for o in ops_ciclo(symbol, vs, c)
               if desde < o["_ms"] <= ahora]
        ops.sort(key=lambda o: (o["_ms"], o["id"]), reverse=True)
        return JSONResponse({"symbol": symbol, "venues": vs, "minutos": minutos, "limit": limit,
                             "truncada": len(ops) > limit,
                             "operaciones": [{k: v for k, v in o.items() if k != "_ms"} for o in ops[:limit]],
                             "as_of": as_of()})

    @api.get("/api/orderflow/perfil")
    async def perfil(symbol: str, paso: str, desde: str = "", hasta: str = "", venues: str = "",
                     unidad: str = "base") -> Response:
        """Lo negociado por nivel desde las 00:00Z, de mentira: trece niveles alrededor del precio del relevo."""
        ref = estado["ref"].get(symbol)
        P = Decimal(paso)
        k0 = int(Decimal(str(ref[0])) // P) if ref else 0
        niveles = [{"nivel": str((k0 + j) * P), "compra": 1.0, "venta": 1.0, "delta": 0.0, "total": 2.0, "operaciones": 2}
                   for j in range(-6, 7)] if ref else []
        return JSONResponse({"symbol": symbol, "desde": desde, "hasta": hasta, "paso": paso, "unidad": unidad,
                             "niveles": niveles, "as_of": as_of()})

    def q_honda(ks: int, t: int) -> str:
        q = Decimal(5 + (ks * 7 + t // 30) % 13) / 10
        return format((q * 25 if ks % 37 == 0 else q).normalize(), "f")

    async def fotos_de(symbol: str, venues: list[str], desde: datetime, hasta: datetime, paso: str, cada: int) -> list:
        async with estado["pool"].acquire() as conn:
            d = await lec.fotos(conn, symbol=symbol, desde=desde.isoformat(), hasta=hasta.isoformat(),
                                venues=",".join(venues), paso=paso, cada=cada)
        return d.get("fotos") or []

    @api.get("/api/libro/honda")
    async def honda(symbol: str, venues: str = "", desde: str = "", hasta: str = "") -> Response:
        activo = symbol.upper().replace("USDT", "")
        P = HONDA_PASO.get(activo)
        vs = [v for v in venues.split(",") if v in HONDA]
        if P is None or not desde or not hasta:
            return JSONResponse({"detail": "banco: la capa honda solo con desde y hasta, de BTC, ETH o SOL"},
                                status_code=422)
        d0 = datetime.fromisoformat(desde.replace("Z", "+00:00"))
        d1 = datetime.fromisoformat(hasta.replace("Z", "+00:00"))
        d0 = datetime.fromtimestamp((int(d0.timestamp()) + 29) // 30 * 30, UTC)
        salida = []
        try:
            fs = await fotos_de(symbol, vs, d0, d1, str(P), 30) if vs and d1 > d0 else []
        except Peticion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        # (149 B r1) EN VIVO: las fotos de los ultimos 150 s, que la base del banco no tiene (las suyas son de otro dia):
        # cada 30 s por venue, alrededor de la mejor compra / venta que el relevo del banco mando por ese venue al
        # pedirse por primera vez, y memorizadas (otra peticion del mismo instante trae la misma foto)
        ahora_s = int(time.time())
        viva = estado["honda_viva"]
        for t in range(max(int(d0.timestamp()), ahora_s - 150) // 30 * 30, min(int(d1.timestamp()), ahora_s + 1), 30):
            if t < int(d0.timestamp()):
                continue
            for v in vs:
                if (activo, v, t) not in viva and (activo, v) in estado["mejor"]:
                    b_, a_ = estado["mejor"][(activo, v)]
                    viva[(activo, v, t)] = {"ts": datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                            "venue": v, "compra": b_, "venta": a_}
                if (activo, v, t) in viva:
                    fs.append(viva[(activo, v, t)])
        for k in [k for k in viva if k[2] < ahora_s - 3600]:
            del viva[k]
        for f in fs:
            t = int(datetime.fromisoformat(f["ts"].replace("Z", "+00:00")).timestamp())
            if f["venue"] == "okx_swap" and (t // 30) % 40 in (10, 11, 12, 13):
                continue
            rancia = (t // 30) % 40 == 25
            mid = (Decimal(f["compra"]) + Decimal(f["venta"])) / 2
            n = int(mid * HONDA_ALCANCE[activo] / P)
            kc = int(Decimal(f["compra"]) // P) - 3
            kv = -(-Decimal(f["venta"]) // P) + 3
            compras = {"desde": format((kc * P).normalize(), "f"), "cantidades": [q_honda(kc - i, t) for i in range(n)]}
            ventas = {"desde": format((int(kv) * P).normalize(), "f"),
                      "cantidades": [q_honda(int(kv) + i, t) for i in range(n)]} if HONDA[f["venue"]] else None
            salida.append({"ts": f["ts"], "venue": f["venue"], "ts_libro": f["ts"], "edad_s": 0.0, "rancia": rancia,
                           "fuente": "banco", "paso": format(P.normalize(), "f"), "cubo": None, "precio": str(mid),
                           "vivo": {"compra": f["compra"], "venta": f["venta"]},
                           "alcance": {"compra": compras["desde"], "venta": ventas["desde"] if ventas else None},
                           "compras": None if rancia else compras, "ventas": None if rancia else ventas})
        salida.sort(key=lambda x: (x["ts"], x["venue"]))
        return JSONResponse({"que": "la capa honda DE MENTIRA del banco", "symbol": symbol, "venues": vs,
                             "rancia_s": 75, "nivel": "precio", "orden": "desde el borde vivo hacia fuera",
                             "unidad": "base", "frontera": None, "fotos": salida, "as_of": as_of()})

    @api.get("/api/orderflow/footprint")
    async def footprint(symbol: str, paso: str, desde: str = "", hasta: str = "", venues: str = "", marco: str = "1m",
                        unidad: str = "base") -> Response:
        # desde/hasta con la MISMA regla que la ruta real (149 B r1): app.orderflow_lectura, importada, no copiada
        try:
            if marco not in MARCOS:
                raise Peticion(f"marco tiene que ser uno de {', '.join(MARCOS)}")
            d0, d1 = instante(desde, "desde"), instante(hasta, "hasta")
            ventana(d0, d1, RANGO_MAXIMO, MARCOS[marco])
        except Peticion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        if marco != "1m":
            return JSONResponse({"detail": "banco: el footprint solo 1m"}, status_code=422)
        P = Decimal(paso)
        vs = [v for v in venues.split(",") if v]
        try:
            fs = await fotos_de(symbol, vs, d0, d1, paso, 60) if vs and d1 > d0 else []
        except Peticion as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        velas = []
        for ts in sorted({f["ts"] for f in fs}):
            f = next(x for x in fs if x["ts"] == ts)
            t = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
            mid = (Decimal(f["compra"]) + Decimal(f["venta"])) / 2
            k0 = int(mid // P)
            niveles = []
            for j in range(-4, 5):
                c = round(0.1 * (1 + ((k0 + j) * 3 + t // 60) % 9), 3)
                v = round(0.1 * (1 + ((k0 + j) * 5 + t // 60 * 2) % 7), 3)
                niveles.append({"nivel": format(((k0 + j) * P).normalize(), "f"), "compra": c, "venta": v,
                                "delta": round(c - v, 3), "total": round(c + v, 3), "operaciones": 3})
            c = round(sum(x["compra"] for x in niveles), 3)
            v = round(sum(x["venta"] for x in niveles), 3)
            velas.append({"ts": ts, "apertura": str(mid), "cierre": str(mid), "compra": c, "venta": v,
                          "delta": round(c - v, 3), "total": round(c + v, 3), "operaciones": 27, "niveles": niveles})
        return JSONResponse({"symbol": symbol, "marco": marco, "paso": paso, "unidad": unidad, "venues": vs,
                             "desde": desde, "hasta": hasta, "velas": velas, "tope_velas": 1500, "tope_celdas": 50000,
                             "as_of": as_of()})

    @api.get("/api/{resto:path}")
    async def otra(resto: str) -> Response:
        return JSONResponse({"detail": f"banco: aqui no se sirve /api/{resto}"}, status_code=503)

    uvicorn.run(api, host="127.0.0.1", port=a.puerto, log_level="warning")
    return 0


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "carga":
        return carga(sys.argv[2], *(Path(x) for x in sys.argv[3:4]))
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
