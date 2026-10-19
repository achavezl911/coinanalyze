#!/usr/bin/env python3
"""K112-banco · sirve /flujo del ARBOL con sus indicadores sobre una base local con datos de produccion (campana 146).

    K112-banco.py carga <dsn> [--ahora ISO] [--mas F]   crea en <dsn> las tablas que leen el footprint, las grandes, los
                                              indicadores y la cinta, y las llena con K112-sujeto.tsv.xz (bajado UNA vez
                                              de 140) DESPLAZADO A AHORA: su T1 pasa a la hora entera de ahora + 2 h
                                              (asi la vista del pasado de K112, la hora que acabo hace una hora, y el
                                              vivo tienen dato), y su bloque de cinta VIVA empieza 10 min antes de ahora
                                              (y el vivo recibe ordenes nuevas mientras corre). Imprime la hora del
                                              pasado que hay que fijarle a K112 (K112_HASTA). Con --mas F (OF-6a,
                                              campana 148: K113-celdas.tsv.xz), mas filas del mismo formato, que se
                                              desplazan igual (el CVD de sesion necesita horas de celdas antes)
    K112-banco.py sirve --puerto P --db <dsn> [--sobre DIR] [--plantado F]

Lo que sirve:
    /flujo, /static/*     del arbol; si --sobre DIR trae el fichero, ese gana (una pagina que pinta mal SIN tocar el arbol)
    /api/orderflow/{footprint,grandes,indicadores,ordenes}   app/orderflow_lectura.py DEL ARBOL sobre <dsn>, con as_of
    /api/orderflow/{sesiones,perfil,vwap,tpo}   lo mismo (OF-6a, campana 148: el CVD de sesion, la regla y el TPO de K113)
    cualquier otra /api/* 503 «banco»
--plantado F se RELEE en cada peticion: `serie` (el ultimo cubo con dato del OI de Binance, +1 despues de calcularlo:
lo servido no es lo de las tablas), `orden` (la primera orden servida, +1 USD), `sin_pagina` (/flujo da 404) o `sin_of5a`
(indicadores y ordenes dan 404: un sujeto anterior a la campana 146). Con la CSP de produccion (copiada de app/api.py).
No aplica ninguna regla de K112: sirve. Lo usan K112-control.bash y las capturas de la entrega.
"""

import argparse
import asyncio
import json
import lzma
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
SUJETO = Path(__file__).resolve().parent / "K112-sujeto.tsv.xz"
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
CREATE TABLE orderflow_cinta (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL, precio numeric NOT NULL,
    base numeric NOT NULL, usd numeric NOT NULL, compra boolean NOT NULL, id text NOT NULL);
CREATE INDEX ON orderflow_cinta (symbol, ts DESC);
CREATE TABLE orderflow_grande (ts timestamptz NOT NULL, venue text NOT NULL, symbol text NOT NULL, precio numeric NOT NULL,
    base numeric NOT NULL, usd numeric NOT NULL, compra boolean NOT NULL, id text NOT NULL, umbral_usd numeric NOT NULL,
    PRIMARY KEY (venue, symbol, id));
CREATE TABLE open_interest (ts timestamptz, symbol text, interval text, oi_open float8, oi_high float8, oi_low float8,
    oi_close float8, PRIMARY KEY (symbol, interval, ts));
CREATE TABLE oi_bybit (LIKE open_interest INCLUDING ALL);
CREATE TABLE funding_rate (ts timestamptz, symbol text, interval text, fr_open float8, fr_high float8, fr_low float8,
    fr_close float8, PRIMARY KEY (symbol, interval, ts));
CREATE TABLE predicted_funding_rate (ts timestamptz, symbol text, interval text, pfr_open float8, pfr_high float8,
    pfr_low float8, pfr_close float8, PRIMARY KEY (symbol, interval, ts));
CREATE TABLE long_short_ratio (ts timestamptz, symbol text, interval text, long_pct float8, short_pct float8,
    ratio float8, PRIMARY KEY (symbol, interval, ts));
CREATE TABLE liquidations (ts timestamptz, symbol text, interval text, long_liq float8, short_liq float8,
    PRIMARY KEY (symbol, interval, ts));
CREATE TABLE liquidations_realtime (ts timestamptz, symbol text, exchange text, side text, notional_usd float8,
    price float8, qty float8, event_id text, PRIMARY KEY (exchange, event_id, ts));
CREATE TABLE pipeline_heartbeat (service text PRIMARY KEY, updated_at timestamptz, status text, detail text);
CREATE TABLE data_gap (feed text, exchange text, symbol text, start_ts timestamptz, end_ts timestamptz,
    evidence_type text, status text);
"""
# por tabla: las columnas que son instantes (en epoch ms en el sujeto)
INSTANTES = {"orderflow_celda": (0,), "orderflow_cobertura": (0,), "orderflow_cinta": (0,), "orderflow_grande": (0,),
             "open_interest": (0,), "oi_bybit": (0,), "funding_rate": (0,), "predicted_funding_rate": (0,),
             "long_short_ratio": (0,), "liquidations": (0,), "liquidations_realtime": (0,), "pipeline_heartbeat": (1,),
             "data_gap": (3, 4)}


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).isoformat(timespec="milliseconds")


def carga(dsn: str, ahora: datetime, sujeto: Path = SUJETO, mas: Path | None = None) -> int:
    filas: dict[str, list[list[str]]] = {}
    with lzma.open(sujeto, "rt", encoding="utf-8") as f:
        cab = f.readline().rstrip("\n").split("|")
        t1, vivo0 = int(cab[1]), int(cab[3])
        for linea in f:
            tabla, _, resto = linea.rstrip("\n").partition("|")
            filas.setdefault(tabla, []).append(resto.split("|"))
    if mas:
        with lzma.open(mas, "rt", encoding="utf-8") as f:
            for linea in f:
                if not linea.startswith("#"):
                    tabla, _, resto = linea.rstrip("\n").partition("|")
                    filas.setdefault(tabla, []).append(resto.split("|"))
    hora = ahora.replace(minute=0, second=0, microsecond=0)
    s = int((hora + timedelta(hours=2)).timestamp() * 1000)
    dh = s - t1  # horas enteras: las velas, las sesiones de 5 min y los cubos siguen alineados
    dv = int((ahora - timedelta(minutes=10)).timestamp() * 1000) - vivo0
    lineas = []
    for tabla, xs in filas.items():
        destino = "orderflow_cinta" if tabla == "orderflow_cinta_vivo" else tabla
        d = dv if tabla == "orderflow_cinta_vivo" else dh
        bloque = []
        for x in xs:
            x = list(x)
            for i in INSTANTES.get(destino, ()):
                x[i] = _iso(int(x[i]) + d)
            if destino == "pipeline_heartbeat":  # su ventana certificada, en epoch s dentro del JSON
                det = json.loads("|".join(x[3:]))
                for k in ("source_start_ts", "source_cutoff_ts"):
                    det[k] = int(det[k]) + dh // 1000
                x = x[:3] + [json.dumps(det, separators=(",", ":"), sort_keys=True)]
            bloque.append("\t".join(x))
        lineas.append(f"COPY {destino} FROM STDIN;\n" + "\n".join(bloque) + "\n\\.\n")
    r = subprocess.run(["psql", dsn, "-X", "-q", "-v", "ON_ERROR_STOP=1"], input=DDL + "".join(lineas), text=True,
                       capture_output=True, timeout=600)
    if r.returncode:
        print(f"carga rc={r.returncode}: {r.stderr[:400]}", file=sys.stderr)
        return 2
    print(f"K112_HASTA={(hora - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')} · "
          + " · ".join(f"{t} {len(xs)}" for t, xs in filas.items()))
    return 0


RUTAS = {"/api/orderflow/footprint": ("footprint", ("symbol", "desde", "hasta", "marco", "paso", "venues", "unidad")),
         "/api/orderflow/grandes": ("grandes", ("symbol", "desde", "hasta", "venues", "limit")),
         "/api/orderflow/indicadores": ("indicadores", ("symbol", "desde", "hasta", "marco")),
         "/api/orderflow/ordenes": ("ordenes", ("symbol", "venues", "min_usd", "desde", "hasta", "limit")),
         # OF-6a (campana 148): las de OF-3, con los parametros de app/api.py (como K109-banco.py)
         "/api/orderflow/sesiones": ("sesiones", ("symbol", "desde", "hasta", "sesion", "paso", "venues", "unidad")),
         "/api/orderflow/perfil": ("perfil", ("symbol", "desde", "hasta", "paso", "venues", "unidad")),
         "/api/orderflow/vwap": ("vwap", ("symbol", "desde", "hasta", "marco", "sesion", "venues")),
         "/api/orderflow/tpo": ("tpo", ("symbol", "desde", "hasta", "sesion", "paso", "venues"))}


def _sirve_ruta(dsn: str, ruta: str, q: dict[str, str]) -> tuple[int, dict]:
    sys.path.insert(0, str(REPO))
    import app as paquete
    from app import orderflow_lectura as lec

    if not Path(paquete.__file__).resolve().is_relative_to(REPO):
        raise SystemExit(f"el banco importo app/ de {paquete.__file__}, no del arbol {REPO}")
    nombre, params = RUTAS[ruta]

    async def corre():
        import asyncpg

        conn = await asyncpg.connect(dsn, server_settings={"timezone": "UTC"})
        try:
            kw = {k: q.get(k) for k in params}
            kw["symbol"] = kw["symbol"] or ""
            if "marco" in params:
                kw["marco"] = kw["marco"] or "1m"
            if "limit" in params:
                kw["limit"] = int(kw["limit"] or (500 if nombre == "grandes" else 200))
            return await getattr(lec, nombre)(conn, **kw)
        finally:
            await conn.close()

    try:
        d = asyncio.run(corre())
    except lec.Peticion as exc:
        return 422, {"detail": str(exc)}
    return 200, {**d, "as_of": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")}


def altera(nombre: str, d: dict, como: str) -> dict:
    """Tuerce lo servido DESPUES de calcularlo: solo el contraste con las tablas lo puede ver."""
    if como == "serie" and nombre == "indicadores":
        c = next((x for x in reversed(d["series"]["oi_binance"]["cubos"]) if x["valores"]), None)
        if c is not None:
            c["valores"]["oi"] = format((Decimal(c["valores"]["oi"]) + 1).normalize(), "f")
    if como == "orden" and nombre == "ordenes" and d["ordenes"]:
        o = d["ordenes"][0]
        o["usd"] = format((Decimal(o["usd"]) + 1).normalize(), "f")
    return d


def main() -> int:
    if len(sys.argv) > 2 and sys.argv[1] == "carga":
        ahora = datetime.now(UTC)
        if "--ahora" in sys.argv:
            ahora = datetime.fromisoformat(sys.argv[sys.argv.index("--ahora") + 1].replace("Z", "+00:00"))
        mas = Path(sys.argv[sys.argv.index("--mas") + 1]) if "--mas" in sys.argv else None
        return carga(sys.argv[2], ahora, mas=mas)
    ap = argparse.ArgumentParser()
    ap.add_argument("modo", choices=("sirve",))
    ap.add_argument("--puerto", type=int, required=True)
    ap.add_argument("--db", required=True)
    ap.add_argument("--sobre")
    ap.add_argument("--plantado")
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

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            p = plantado()
            if u.path == "/flujo" or u.path.startswith("/static/"):
                rel = "flujo.html" if u.path == "/flujo" else u.path[len("/static/"):]
                if u.path == "/flujo" and p == "sin_pagina":
                    return self.manda(404, b'{"detail":"Not Found"}', TIPOS[".json"])
                for raiz in ([sobre] if sobre else []) + [REPO / "static"]:
                    f = (raiz / rel).resolve()
                    if f.is_relative_to(raiz.resolve()) and f.is_file():
                        return self.manda(200, f.read_bytes(), TIPOS.get(f.suffix, "application/octet-stream"))
                return self.manda(404, b'{"detail":"Not Found"}', TIPOS[".json"])
            if u.path in RUTAS:
                nombre = RUTAS[u.path][0]
                if p == "sin_of5a" and nombre in ("indicadores", "ordenes"):
                    return self.manda(404, b'{"detail":"Not Found"}', TIPOS[".json"])
                estado, d = _sirve_ruta(a.db, u.path, {k: v[0] for k, v in parse_qs(u.query).items()})
                if estado == 200 and p in ("serie", "orden"):
                    d = altera(nombre, d, p)
                return self.manda(estado, json.dumps(d).encode(), TIPOS[".json"])
            return self.manda(503, b'{"detail":"banco: aqui no se sirve esta ruta"}', TIPOS[".json"])

    ThreadingHTTPServer(("127.0.0.1", a.puerto), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
