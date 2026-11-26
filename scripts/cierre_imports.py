#!/usr/bin/env python3
"""REINICIO R1: que servicio hay que reiniciar en un despliegue, por el cierre de imports de su punto de entrada.

Solo stdlib y solo AST: no importa nada de app/ (importar app.db escribe en la base). Lo corre deploy-coinalyze como
root, con el python3 del sistema, desde el release CANDIDATO (`python3 -I <cand>/scripts/cierre_imports.py`).

  closure <arbol> <modulo>                 los ficheros de app/ que <modulo> importa, transitivo, uno por linea
  decide <cand> <unidad>=<modulo>=<base>...  por unidad, una linea «<unidad> restart|keep <motivo>»: <base> es el
                                           release del que corre hoy esa unidad

El cierre cuenta TODO import de app.*: los de cabecera, los relativos y los perezosos (dentro de una funcion: un proceso
vivo los carga despues, de su release). Un modulo arrastra los __init__.py de sus paquetes; un paquete corrido con -m,
su __main__.py. Lo que el AST no ve (importlib con una cadena) no cuenta: por eso los datos (config/ y lo que no es .py
en app/) y requirements.lock/pyproject.toml, si cambian, reinician a todos. Un error aqui sale con rc != 0 y
deploy-coinalyze lo toma como «reinicia todo», que es lo de antes.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

RAIZ_PAQUETE = "app"
TODOS = ("requirements.lock", "pyproject.toml")


def _fichero(arbol: Path, modulo: str) -> Path | None:
    partes = modulo.split(".")
    if partes[0] != RAIZ_PAQUETE:
        return None
    base = arbol.joinpath(*partes)
    for p in (base.with_suffix(".py"), base / "__init__.py"):
        if p.is_file():
            return p
    return None


def _paquete(arbol: Path, f: Path) -> str:
    """El paquete de un fichero: el suyo si es un __init__.py, el padre si no."""
    rel = f.relative_to(arbol).with_suffix("")
    partes = list(rel.parts)
    return ".".join(partes[:-1])


def _importados(arbol: Path, f: Path) -> set[str]:
    nombres: set[str] = set()
    for nodo in ast.walk(ast.parse(f.read_bytes(), filename=str(f))):
        if isinstance(nodo, ast.Import):
            nombres.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                partes = _paquete(arbol, f).split(".")
                partes = partes[: len(partes) - (nodo.level - 1)] if nodo.level > 1 else partes
                base = ".".join(partes + ([nodo.module] if nodo.module else []))
            else:
                base = nodo.module or ""
            nombres.add(base)
            nombres.update(f"{base}.{a.name}" for a in nodo.names if a.name != "*")
    return nombres


def cierre(arbol: Path, entrada: str) -> set[str]:
    """Rutas relativas a <arbol>. Vacio si la entrada no existe en ese arbol."""
    arbol = arbol.resolve()
    inicio = _fichero(arbol, entrada)
    if inicio is None:
        return set()
    pendientes = [inicio]
    if inicio.name == "__init__.py" and (inicio.parent / "__main__.py").is_file():
        pendientes.append(inicio.parent / "__main__.py")
    vistos: set[Path] = set()
    while pendientes:
        f = pendientes.pop()
        if f in vistos:
            continue
        vistos.add(f)
        for nombre in _importados(arbol, f):
            partes = nombre.split(".")
            for i in range(1, len(partes) + 1):  # app.a.b importa app, app.a y app.a.b
                g = _fichero(arbol, ".".join(partes[:i]))
                if g is not None and g not in vistos:
                    pendientes.append(g)
    return {str(f.relative_to(arbol)) for f in vistos}


def _datos(arbol: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for sub, solo_no_py in (("config", False), (RAIZ_PAQUETE, True)):
        d = arbol / sub
        if not d.is_dir():
            continue
        for f in d.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts or (solo_no_py and f.suffix == ".py"):
                continue
            out[str(f.relative_to(arbol))] = f.read_bytes()
    return out


def _leer(f: Path) -> bytes | None:
    return f.read_bytes() if f.is_file() else None


def _distintos(base: Path, cand: Path, rutas) -> list[str]:
    return sorted(r for r in rutas if _leer(base / r) != _leer(cand / r))


def _resumen(cambiados: list[str]) -> str:
    return ", ".join(cambiados[:3]) + (f" +{len(cambiados) - 3}" if len(cambiados) > 3 else "")


def decide(cand: Path, unidad: str, entrada: str, base: Path) -> tuple[str, str]:
    cambiados = _distintos(base, cand, TODOS)
    if cambiados:
        return "restart", f"changed for every service: {_resumen(cambiados)}"
    datos_b, datos_c = _datos(base), _datos(cand)
    cambiados = sorted(r for r in datos_b.keys() | datos_c.keys() if datos_b.get(r) != datos_c.get(r))
    if cambiados:
        return "restart", f"data file changed: {_resumen(cambiados)}"
    nuevo, viejo = cierre(cand, entrada), cierre(base, entrada)
    if not nuevo or not viejo:
        return "restart", f"entry point {entrada} not found in {'the candidate' if not nuevo else base.name}"
    cambiados = _distintos(base, cand, nuevo | viejo)
    if cambiados:
        return "restart", f"import closure of {entrada} changed: {_resumen(cambiados)}"
    return "keep", f"import closure of {entrada} unchanged ({len(nuevo)} files) vs running release {base.name[:12]}"


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "closure":
        print("\n".join(sorted(cierre(Path(argv[1]), argv[2]))))
        return 0
    if len(argv) >= 3 and argv[0] == "decide":
        cand = Path(argv[1])
        lineas = []
        for spec in argv[2:]:
            unidad, entrada, base = spec.split("=", 2)
            veredicto, motivo = decide(cand, unidad, entrada, Path(base))
            lineas.append(f"{unidad} {veredicto} ({motivo})")
        print("\n".join(lineas))  # todo o nada: un error a mitad no deja medio plan
        return 0
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
