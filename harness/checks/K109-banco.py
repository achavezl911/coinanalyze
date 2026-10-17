#!/usr/bin/env python3
"""K109-banco · sirve la pagina del FOOTPRINT del ARBOL sobre una base local con celdas de produccion (campana 142).

    K109-banco.py carga <dsn>      crea en <dsn> las tres tablas que lee el footprint y las llena con
                                   K109-celdas.tsv.gz (celdas, cobertura y pasos de produccion bajados una vez)
    K109-banco.py sirve --puerto P --db <dsn> [--sobre DIR] [--plantado FICHERO] [--diario F]

Lo que sirve:
    /flujo                  static/flujo.html del arbol
    /static/*               static/ del arbol; si --sobre DIR trae el fichero, ese gana (asi se planta una pagina que
                            pinta mal SIN tocar el arbol)
    /api/orderflow/footprint  lo que calcula app/orderflow_lectura.py DEL ARBOL sobre <dsn>, con el `as_of` de la ruta
    cualquier otra /api/*   503 «banco»
--plantado FICHERO se RELEE en cada peticion (el control cambia el escenario sin reiniciar el banco): si existe, dice
`nivel` o `va` (lo servido se tuerce DESPUES de calcularlo: «lo servido no es lo de las celdas») o `sin_pagina` (/flujo
da 404: el sujeto sin desplegar).
Con la CSP de produccion (copiada de app/api.py): un <script> o un <style> en linea fallaria aqui igual que alli.
No aplica ninguna regla de K109: sirve. Lo usan K109-control.bash y las capturas de la entrega.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "K109-celdas.tsv.gz"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json"}
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
       "form-action 'none'")
DDL = """
CREATE TABLE orderflow_paso (symbol text PRIMARY KEY, paso numeric NOT NULL);
CREATE TABLE orderflow_celda (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL, nivel numeric NOT NULL,
    compra_base numeric NOT NULL, venta_base numeric NOT NULL, compra_usd numeric NOT NULL, venta_usd numeric NOT NULL,
    compras integer NOT NULL, ventas integer NOT NULL, PRIMARY KEY (symbol, ts, venue, nivel));
CREATE TABLE orderflow_cobertura (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL,
    segundos smallint NOT NULL, operaciones integer NOT NULL, tardias integer NOT NULL, fuera integer NOT NULL,
    reconexiones smallint NOT NULL, definitivo boolean NOT NULL, PRIMARY KEY (symbol, ts, venue));
"""


def carga(dsn: str) -> int:
    filas: dict[str, list[str]] = {"orderflow_paso": [], "orderflow_celda": [], "orderflow_cobertura": []}
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as f:
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


def _footprint(dsn: str, q: dict[str, str]) -> tuple[int, dict]:
    sys.path.insert(0, str(REPO))
    import app as paquete
    from app import orderflow_lectura as lec

    if not Path(paquete.__file__).resolve().is_relative_to(REPO):
        raise SystemExit(f"el banco importo app/ de {paquete.__file__}, no del arbol {REPO}")

    async def corre():
        import asyncpg

        conn = await asyncpg.connect(dsn)
        try:
            return await lec.footprint(conn, symbol=q.get("symbol", ""), desde=q.get("desde"), hasta=q.get("hasta"),
                                       marco=q.get("marco", "1m"), paso=q.get("paso"), venues=q.get("venues"),
                                       unidad=q.get("unidad"))
        finally:
            await conn.close()

    try:
        d = asyncio.run(corre())
    except lec.Peticion as exc:
        return 422, {"detail": str(exc)}
    return 200, {**d, "as_of": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")}


def altera(d: dict, como: str) -> dict:
    """Tuerce la ULTIMA vela con niveles de lo servido, de forma CONSISTENTE (la vela sigue cuadrando consigo misma):
    solo el contraste con las celdas puede verlo."""
    v = next((x for x in reversed(d.get("velas") or []) if x["niveles"]), None)
    if v is None:
        return d
    if como == "nivel":
        n = v["niveles"][-1]
        extra = Decimal(1) if d.get("unidad") == "usd" else Decimal("0.5")
        for k in ("compra", "total", "delta"):
            n[k] = format((Decimal(n[k]) + extra).normalize(), "f")
            v[k] = format((Decimal(v[k]) + extra).normalize(), "f")
    elif como == "va" and v.get("value_area"):
        v["value_area"]["vah"] = v["value_area"]["val"]
    return d


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "carga":
        return carga(sys.argv[2])
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=("sirve",))
    ap.add_argument("--puerto", type=int, required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--sobre")
    ap.add_argument("--plantado")
    ap.add_argument("--diario")
    a = ap.parse_args()
    sobre = Path(a.sobre) if a.sobre else None

    def plantado() -> str:
        try:
            return Path(a.plantado).read_text().strip() if a.plantado else ""
        except OSError:
            return ""

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def manda(self, estado: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(estado)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Content-Security-Policy", CSP)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)
            if a.diario:
                with open(a.diario, "a") as f:
                    f.write(f"{datetime.now(UTC).timestamp():.3f} {estado} {len(cuerpo)} {self.path}\n")

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path == "/flujo" or u.path.startswith("/static/"):
                rel = "flujo.html" if u.path == "/flujo" else u.path[len("/static/"):]
                if u.path == "/flujo" and plantado() == "sin_pagina":
                    return self.manda(404, b'{"detail":"Not Found"}', TIPOS[".json"])
                for raiz in ([sobre] if sobre else []) + [REPO / "static"]:
                    f = (raiz / rel).resolve()
                    if f.is_relative_to(raiz.resolve()) and f.is_file():
                        return self.manda(200, f.read_bytes(), TIPOS.get(f.suffix, "application/octet-stream"))
                return self.manda(404, b'{"detail":"Not Found"}', TIPOS[".json"])
            if u.path == "/api/orderflow/footprint":
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                estado, d = _footprint(a.db, q)
                if estado == 200 and plantado() in ("nivel", "va"):
                    d = altera(d, plantado())
                return self.manda(estado, json.dumps(d).encode(), TIPOS[".json"])
            return self.manda(503, b'{"detail":"banco: aqui solo se sirve el footprint"}', TIPOS[".json"])

    ThreadingHTTPServer(("127.0.0.1", a.puerto), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
