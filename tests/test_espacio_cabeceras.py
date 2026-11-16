"""EL ESPACIO (campana OF-6b): /flujo se deja enmarcar por el mismo origen y NINGUNA otra ruta.

/espacio pinta 1, 2 o 4 <iframe> de /flujo; hasta la OF-6b el middleware de app/api.py (response_headers) ponia a toda
respuesta frame-ancestors 'none' y X-Frame-Options DENY y el marco no cargaba. Se llama al middleware de verdad con
una peticion construida a mano (sin base, sin arranque de la aplicacion) y una respuesta vacia detras.
"""

from __future__ import annotations

import asyncio
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from starlette.requests import Request
from starlette.responses import Response

import app.api as api

STATIC = Path(__file__).resolve().parents[1] / "static"

CSP_CERRADA = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
    "font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
    "form-action 'none'"
)


def _cabeceras(camino: str) -> dict[str, str]:
    scope = {
        "type": "http", "method": "GET", "path": camino, "raw_path": camino.encode(), "query_string": b"",
        "headers": [(b"host", b"banco"), (b"x-internal-token", b"t")], "client": ("127.0.0.1", 1),
        "server": ("banco", 80), "scheme": "http", "root_path": "",
    }

    async def detras(_request):
        return Response("x")

    respuesta = asyncio.run(api.response_headers(Request(scope), detras))
    assert respuesta.status_code == 200, (camino, respuesta.status_code)
    return dict(respuesta.headers)


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    # una /api pasa la puerta del token: la respuesta que importa es la que sale de call_next
    monkeypatch.setattr(api, "SETTINGS", SimpleNamespace(API_INTERNAL_TOKEN="t", API_INTERNAL_ALLOWED_CIDRS=()))


def test_flujo_se_deja_enmarcar_solo_por_el_mismo_origen():
    h = _cabeceras("/flujo")
    assert h["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self';" in h["content-security-policy"]
    # el resto de la CSP no cambia
    assert h["content-security-policy"] == CSP_CERRADA.replace("frame-ancestors 'none'", "frame-ancestors 'self'")


@pytest.mark.parametrize(
    "camino",
    ["/", "/espacio", "/mesa", "/libro", "/panel", "/flujo/", "/flujox", "/api/orderflow/footprint", "/metrics"],
)
def test_las_demas_rutas_no_se_dejan_enmarcar(camino):
    h = _cabeceras(camino)
    assert h["x-frame-options"] == "DENY", camino
    assert h["content-security-policy"] == CSP_CERRADA, camino


def test_espacio_es_una_ruta_que_sirve_su_pagina():
    rutas = [r for r in api.app.routes if getattr(r, "path", None) == "/espacio"]
    assert len(rutas) == 1 and "GET" in rutas[0].methods
    assert (rutas[0].endpoint.__doc__ or "").strip(), "la ruta /espacio sin docstring"
    respuesta = asyncio.run(rutas[0].endpoint())
    assert Path(respuesta.path) == STATIC / "espacio.html"


class _Etiquetas(HTMLParser):
    def __init__(self):
        super().__init__()
        self.en_linea: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "style" or (tag == "script" and not a.get("src")):
            self.en_linea.append(tag)
        if any(k.startswith("on") for k in a):
            self.en_linea.append(f"{tag}[on*]")


def test_espacio_html_sin_script_ni_style_en_linea():
    p = _Etiquetas()
    p.feed((STATIC / "espacio.html").read_text(encoding="utf-8"))
    assert p.en_linea == []
