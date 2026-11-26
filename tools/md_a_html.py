#!/usr/bin/env python3
"""Markdown minimo -> HTML imprimible, solo stdlib.

Cubre lo que usa docs/USO_DASHBOARD.md: titulos (#), parrafos, listas (- / 1.),
bloques ``` y, en linea, `codigo` y **negrita**. Lo demas sale como texto.

La guia del panel (static/guia_uso_dashboard.pdf) se regenera asi, en 143:
  python3 tools/md_a_html.py docs/USO_DASHBOARD.md /tmp/guia.html
  chromium --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
    --print-to-pdf=static/guia_uso_dashboard.pdf file:///tmp/guia.html
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; margin: 0 1.5cm; color: #111; }
h1 { font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 4pt; }
h2 { font-size: 14pt; margin-top: 18pt; border-bottom: 1px solid #999; page-break-after: avoid; }
h3 { font-size: 12pt; page-break-after: avoid; }
code { font-family: monospace; background: #eee; padding: 0 2pt; }
pre { background: #f4f4f4; padding: 6pt; white-space: pre-wrap; }
li { margin: 2pt 0; }
"""


def en_linea(texto: str) -> str:
    partes = re.split(r"(`[^`]+`)", texto)
    out = []
    for p in partes:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            out.append(f"<code>{html.escape(p[1:-1])}</code>")
        else:
            out.append(re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(p)))
    return "".join(out)


def convertir(md: str) -> str:
    cuerpo: list[str] = []
    parrafo: list[str] = []
    lista: str | None = None
    pre: list[str] | None = None

    def cerrar_parrafo() -> None:
        if parrafo:
            cuerpo.append(f"<p>{en_linea(' '.join(parrafo))}</p>")
            parrafo.clear()

    def cerrar_lista() -> None:
        nonlocal lista
        if lista:
            cuerpo.append(f"</{lista}>")
            lista = None

    for linea in md.splitlines():
        if pre is not None:
            if linea.startswith("```"):
                cuerpo.append(f"<pre>{html.escape(chr(10).join(pre))}</pre>")
                pre = None
            else:
                pre.append(linea)
            continue
        if linea.startswith("```"):
            cerrar_parrafo()
            cerrar_lista()
            pre = []
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            cerrar_lista()
            n = len(m.group(1))
            cuerpo.append(f"<h{n}>{en_linea(m.group(2))}</h{n}>")
            continue
        m = re.match(r"^\s*(?:([-*])|\d+\.)\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            tipo = "ul" if m.group(1) else "ol"
            if lista != tipo:
                cerrar_lista()
                cuerpo.append(f"<{tipo}>")
                lista = tipo
            cuerpo.append(f"<li>{en_linea(m.group(2))}</li>")
            continue
        if not linea.strip():
            cerrar_parrafo()
            cerrar_lista()
            continue
        if lista and linea[:1].isspace():
            # continuacion sangrada del ultimo elemento de la lista
            cuerpo[-1] = cuerpo[-1][: -len("</li>")] + " " + en_linea(linea.strip()) + "</li>"
            continue
        cerrar_lista()
        parrafo.append(linea.strip())
    if pre is not None:
        cuerpo.append(f"<pre>{html.escape(chr(10).join(pre))}</pre>")
    cerrar_parrafo()
    cerrar_lista()
    titulo = next((ln.lstrip("# ").strip() for ln in md.splitlines() if ln.startswith("# ")), "Documento")
    return (
        "<!DOCTYPE html>\n<html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<title>{html.escape(titulo)}</title><style>{CSS}</style></head><body>\n"
        + "\n".join(cuerpo)
        + "\n</body></html>\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("uso: md_a_html.py ENTRADA.md SALIDA.html", file=sys.stderr)
        return 2
    Path(argv[2]).write_text(convertir(Path(argv[1]).read_text(encoding="utf-8")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
