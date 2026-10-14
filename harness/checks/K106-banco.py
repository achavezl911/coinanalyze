#!/usr/bin/env python3
"""K106-banco · sirve la mesa del ARBOL con una respuesta de entradas PLANTADA (campana 137).

No aplica ninguna regla: sirve lo que se le da. Lo usan K106-control (los plantados) y las capturas.

    /  y  /mesa            static/mesa.html del arbol (o el de --sobre, si lo trae)
    /static/*              static/ del arbol; si --sobre <dir> trae el fichero, ese gana (asi se
                           planta una pantalla que pinta mal SIN tocar el arbol)
    <RUTA>                 el JSON de --respuesta, RELEIDO en cada peticion: el control cambia el
                           escenario cambiando el fichero. Si el fichero no esta, 503 (la ruta caida)
    cualquier otra /api/*  503 «banco»: aqui no hay mercado

Con --produccion la respuesta no se lee de un fichero: se COMPONE en cada peticion con
vista.componer del arbol sobre lo que sirve produccion hoy (su registro con foto, su DECIDE y su
ultima vela de 1 min), por los canales de solo lectura del arnes. Es la forma de ver datos de
produccion en una ruta que produccion todavia no tiene.

Cada peticion se apunta en --diario (una linea: epoch, estado, bytes, camino).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
RUTA = "/api" + "/mesa/entradas"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json"}
ARNES = Path("/srv/coinanalyze/harness/bin")


def de_produccion(symbol: str) -> dict:
    """La respuesta que el ARBOL compondria con los datos que PRODUCCION sirve ahora."""
    sys.path.insert(0, str(REPO))
    from app.entradas import reglamento as R
    from app.entradas import ruta as RT
    from app.entradas import vista as V

    def api(camino: str) -> dict:
        salida = subprocess.run(["sh", str(ARNES / "api"), camino], capture_output=True, text=True,
                                env={"TODO": "1", "PATH": "/usr/bin:/bin"}, timeout=90, check=True).stdout
        return json.loads(salida)

    registro = api(f"/api/entradas?symbol={symbol}&foto=true&limite={V.LIMITE}")
    registro["faltan"] = RT.FALTAN  # lo que el arbol sirve, no lo que produccion aun dice que falta
    decide, error = None, None
    try:
        decide = api(f"/api/mesa/decide?symbol={symbol}&frame=swing")
    except Exception as exc:  # noqa: BLE001 - es justo el caso «sin respuesta»
        error = f"DECIDE fallo al pedirse ({type(exc).__name__})"
    fila = subprocess.run(
        ["sh", str(ARNES / "prodsql"),
         f"SELECT ts, close FROM ohlcv WHERE symbol='{symbol}' AND interval='1min' "
         "AND ts >= now() - interval '1 hour' ORDER BY ts DESC LIMIT 1"],
        capture_output=True, text=True, timeout=60, check=True).stdout.strip().splitlines()
    if fila and "|" in fila[0]:
        ts, cierre = fila[0].split("|")
        ts = datetime.fromisoformat(ts.replace(" ", "T").replace("+00", "+00:00"))
        precio = {"valor": V._precio(cierre), "instante": (ts + timedelta(minutes=1)).isoformat(),
                  "fuente": V.PRECIO_FUENTE, "motivo": None}
    else:
        precio = {"valor": None, "instante": None, "fuente": V.PRECIO_FUENTE,
                  "motivo": "no hay ninguna vela de 1 min de este activo en la ultima hora"}
    return V.componer(registro, symbol=symbol, activo=symbol.split("USDT")[0], precio=precio,
                      decide=decide, decide_error=error, doc=R.cargar_valido())


class Banco(BaseHTTPRequestHandler):
    cfg: argparse.Namespace

    def log_message(self, *_a) -> None:  # el diario propio basta
        pass

    def _manda(self, estado: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(estado)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)
        if self.cfg.diario:
            with open(self.cfg.diario, "a", encoding="utf-8") as f:
                f.write(f"{time.time():.3f}\t{estado}\t{len(cuerpo)}\t{self.path}\n")

    def do_GET(self) -> None:  # noqa: N802 - nombre de http.server
        url = urlparse(self.path)
        camino = url.path
        if camino in ("/", "/mesa"):
            sobre = Path(self.cfg.sobre) / "mesa.html" if self.cfg.sobre else None
            return self._fichero(sobre if sobre and sobre.is_file() else REPO / "static" / "mesa.html")
        if camino.startswith("/static/"):
            relativo = camino[len("/static/"):]
            if ".." in relativo:
                return self._manda(400, b"no", "text/plain")
            sobre = Path(self.cfg.sobre) / relativo if self.cfg.sobre else None
            return self._fichero(sobre if sobre and sobre.is_file() else REPO / "static" / relativo)
        if camino == RUTA:
            try:
                if self.cfg.produccion:
                    cuerpo = json.dumps(de_produccion(parse_qs(url.query)["symbol"][0]),
                                        ensure_ascii=False).encode()
                else:
                    cuerpo = Path(self.cfg.respuesta).read_bytes()
            except Exception as exc:  # noqa: BLE001 - el banco dice por que no sirve
                return self._manda(503, json.dumps({"detail": f"banco: {exc}"[:200]}).encode(),
                                   "application/json")
            return self._manda(200, cuerpo, "application/json")
        if camino.startswith("/api/"):
            return self._manda(503, b'{"detail":"banco: aqui no hay mercado"}', "application/json")
        return self._manda(404, b"no", "text/plain")

    def _fichero(self, ruta: Path) -> None:
        if not ruta.is_file():
            return self._manda(404, b"no", "text/plain")
        self._manda(200, ruta.read_bytes(), TIPOS.get(ruta.suffix, "application/octet-stream"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=8106)
    ap.add_argument("--respuesta", help="fichero JSON que se sirve en la ruta de entradas")
    ap.add_argument("--produccion", action="store_true", help="componer con lo que sirve produccion")
    ap.add_argument("--sobre", help="directorio cuyos ficheros ganan a static/ (pantallas plantadas)")
    ap.add_argument("--diario", help="fichero donde se apunta cada peticion")
    cfg = ap.parse_args()
    if not cfg.produccion and not cfg.respuesta:
        ap.error("hace falta --respuesta o --produccion")
    Banco.cfg = cfg
    ThreadingHTTPServer(("127.0.0.1", cfg.puerto), Banco).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
