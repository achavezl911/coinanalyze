#!/usr/bin/env python3
"""K123-banco · sirve /espacio y /flujo del ARBOL, con las cabeceras POR RUTA de app/api.py (campana OF-6b).

    K123-banco.py sirve --puerto P --db <dsn> [--sobre DIR] [--plantado F]

Envuelve K112-banco.py SIN cambiarlo: sus RUTAS de /api/orderflow/* (app/orderflow_lectura.py del arbol sobre <dsn>,
cargada con `K112-banco.py carga`) y su CSP. Lo que anade es lo que K112-banco no puede servir: /espacio enmarca /flujo,
y K112-banco manda a todo `frame-ancestors 'none'` (con eso los marcos de /espacio salen en blanco).

LAS CABECERAS SON LAS DE app/api.py, middleware `response_headers` (app/api.py:220-246, OF-6b): SOLO /flujo se deja
enmarcar, y solo por el mismo origen (`frame-ancestors 'self'` + `X-Frame-Options: SAMEORIGIN`); toda otra ruta
`frame-ancestors 'none'` + `DENY`. El resto de la CSP es la de K112-banco.CSP. Si app/api.py cambia, esto se cambia con el.

    /flujo /espacio /mesa /libro   static/<ruta>.html del arbol (--sobre DIR gana, como en K112-banco)
    /static/*                      static/ del arbol (--sobre DIR gana)
    /api/orderflow/*               las RUTAS de K112-banco
    cualquier otra                 503 «banco»
--plantado F se relee en cada peticion: `enmarca_mesa` (/mesa tambien con 'self' + SAMEORIGIN: un banco que deja
enmarcar lo que produccion no) o `sin_espacio` (/espacio 404: el sujeto sin desplegar). No juzga nada: sirve.
Lo usa K123-control.bash.
"""

import argparse
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parents[1]
PAGINAS = {"/flujo": "flujo.html", "/espacio": "espacio.html", "/mesa": "mesa.html", "/libro": "libro.html"}


def _k112():
    spec = importlib.util.spec_from_file_location("k112_banco", AQUI / "K112-banco.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cabeceras(ruta: str, plantado: str, csp_base: str) -> dict[str, str]:
    """Las de app/api.py:234-246 que deciden el enmarcado (y nosniff, como alli)."""
    enmarcable = ruta == "/flujo" or (plantado == "enmarca_mesa" and ruta == "/mesa")
    csp = csp_base.replace("frame-ancestors 'none'", "frame-ancestors 'self'") if enmarcable else csp_base
    return {"Content-Security-Policy": csp, "X-Frame-Options": "SAMEORIGIN" if enmarcable else "DENY",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}


def main() -> int:
    K = _k112()
    if "frame-ancestors 'none'" not in K.CSP:
        print("K123-banco: la CSP de K112-banco ya no dice frame-ancestors 'none'", file=sys.stderr)
        return 2
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

        def manda(self, ruta: str, estado: int, cuerpo: bytes, tipo: str) -> None:
            self.send_response(estado)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            for k, v in cabeceras(ruta, plantado(), K.CSP).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            no = (b'{"detail":"Not Found"}', K.TIPOS[".json"])
            if u.path in PAGINAS or u.path.startswith("/static/"):
                rel = PAGINAS.get(u.path) or u.path[len("/static/"):]
                if u.path == "/espacio" and plantado() == "sin_espacio":
                    return self.manda(u.path, 404, *no)
                for raiz in ([sobre] if sobre else []) + [REPO / "static"]:
                    f = (raiz / rel).resolve()
                    if f.is_relative_to(raiz.resolve()) and f.is_file():
                        return self.manda(u.path, 200, f.read_bytes(), K.TIPOS.get(f.suffix, "application/octet-stream"))
                return self.manda(u.path, 404, *no)
            if u.path in K.RUTAS:
                estado, d = K._sirve_ruta(a.db, u.path, {k: v[0] for k, v in parse_qs(u.query).items()})
                return self.manda(u.path, estado, json.dumps(d).encode(), K.TIPOS[".json"])
            return self.manda(u.path, 503, b'{"detail":"banco: aqui no se sirve esta ruta"}', K.TIPOS[".json"])

    ThreadingHTTPServer(("127.0.0.1", a.puerto), H).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
