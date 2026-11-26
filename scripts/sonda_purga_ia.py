#!/usr/bin/env python3
"""Sonda de solo lectura: nombres de asistentes ajenos en el arbol versionado.

Recorre los ficheros de `git ls-files` del repo dado (por defecto el directorio
actual) y busca, sin distinguir mayusculas, los cinco patrones de PATRONES. Los
.xz y .gz se descomprimen antes de buscar. Los PDF no se pueden leer como texto
sin dependencias nuevas: se buscan en sus bytes y en sus flujos Flate inflados
con zlib; si no casan, se listan por nombre como NO LEIDO (no cuentan).

Imprime fichero:linea: texto y el total. rc=1 si el total es mayor que 0.
Se excluye a si misma.

Uso: python3 scripts/sonda_purga_ia.py [--repo RUTA]
"""
from __future__ import annotations

import argparse
import gzip
import lzma
import re
import subprocess
import sys
import zlib
from pathlib import Path

# Los nombres se arman por piezas para que esta fuente no los contenga enteros.
_G = "g" + "pt"
PATRONES = [
    "chat" + _G,
    "open" + "ai",
    "co" + "dex",
    _G + r"-\d",
    r"\b" + _G + r"\b",
]
RX = re.compile("|".join(f"(?:{p})" for p in PATRONES), re.IGNORECASE)
YO = "scripts/sonda_purga_ia.py"
FLUJO = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)


def versionados(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z"],
        check=True, capture_output=True,
    ).stdout
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def leer(ruta: Path) -> bytes:
    datos = ruta.read_bytes()
    if ruta.suffix == ".xz":
        return lzma.decompress(datos)
    if ruta.suffix == ".gz":
        return gzip.decompress(datos)
    return datos


def pdf_casa(datos: bytes) -> bool:
    if RX.search(datos.decode("latin-1")):
        return True
    for m in FLUJO.finditer(datos):
        try:
            if RX.search(zlib.decompress(m.group(1)).decode("latin-1")):
                return True
        except zlib.error:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    repo = Path(ap.parse_args().repo).resolve()
    total = 0
    no_leidos = []
    for rel in versionados(repo):
        if rel == YO:
            continue
        ruta = repo / rel
        if not ruta.is_file():
            continue
        try:
            datos = leer(ruta)
        except (OSError, lzma.LZMAError, EOFError, gzip.BadGzipFile) as e:
            print(f"{rel}:0: NO LEIDO ({e.__class__.__name__})")
            continue
        if ruta.suffix.lower() == ".pdf":
            if pdf_casa(datos):
                total += 1
                print(f"{rel}:0: PDF (bytes o flujo inflado)")
            else:
                no_leidos.append(rel)
            continue
        texto = datos.decode("utf-8", "replace")
        for n, linea in enumerate(texto.splitlines(), 1):
            if RX.search(linea):
                total += 1
                print(f"{rel}:{n}: {linea.strip()[:160]}")
    for rel in no_leidos:
        print(f"{rel}:0: PDF sin coincidencia en bytes ni flujos; texto NO LEIDO")
    print(f"TOTAL {total}")
    return 1 if total > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
