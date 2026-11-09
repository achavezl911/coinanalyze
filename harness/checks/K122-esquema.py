#!/usr/bin/env python3
"""K122-esquema · las tablas de order-flow de los bancos SALEN de sql/schema.sql, y el juez que mira que no falte ninguna.

Lo usan K109-banco.py y K112-banco.py al cargar (ddl), y K122-los-bancos-siguen-al-esquema.sh (juzga):

    ddl(tablas)              el CREATE TABLE de cada tabla tal cual esta en sql/schema.sql (columnas, tipos, CHECK, clave),
                             sus CREATE INDEX y sus ALTER TABLE .. ADD COLUMN; a las particionadas, una particion DEFAULT
                             (el banco no corre ensure_temporal_partitions). Si schema.sql cambia una columna, el banco la
                             sigue; si no define la tabla una vez y solo una, se cae diciendolo.
    lee(funciones)           las tablas de sql/schema.sql que leen esas funciones de app/orderflow_lectura.py: los nombres
                             de tabla en las cadenas (SQL, f-strings, y los `{tabla}` que salen de tuplas) que alcanzan
                             por el grafo de nombres del modulo (funciones y constantes; sin docstrings).
    K122-esquema.py juzga <banco.py>...   por banco: las tablas que leen las funciones de su RUTAS contra las que crea
                             su DDL (`ddl_banco()`). Sale 1 nombrando cada tabla que falta, 0 si estan todas.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CREA = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z_][a-z0-9_]*)\b(?!\s+PARTITION\s+OF)", re.I)


def _sentencia(sql: str, i: int) -> str:
    """La sentencia que empieza en i, hasta su `;` fuera de parentesis, comillas y comentarios (sin los comentarios)."""
    out, nivel, j = [], 0, i
    while j < len(sql):
        if sql.startswith("--", j):
            k = sql.find("\n", j)
            j = len(sql) if k < 0 else k
            continue
        c = sql[j]
        if c == "'":
            k = j + 1
            while True:
                k = sql.find("'", k)
                if k < 0 or not sql.startswith("''", k):
                    break
                k += 2
            k = len(sql) - 1 if k < 0 else k
            out.append(sql[j:k + 1])
            j = k + 1
            continue
        nivel += (c == "(") - (c == ")")
        out.append(c)
        if c == ";" and nivel == 0:
            return "".join(out)
        j += 1
    raise SystemExit(f"K122-esquema: sentencia sin `;` desde el caracter {i} de sql/schema.sql")


def ddl(tablas: tuple[str, ...], schema: Path | None = None) -> str:
    sql = (schema or REPO / "sql" / "schema.sql").read_text(encoding="utf-8")
    partes = []
    for t in tablas:
        sitios = [m.start() for m in CREA.finditer(sql) if m.group(1) == t]
        if len(sitios) != 1:
            raise SystemExit(f"K122-esquema: sql/schema.sql define {t} {len(sitios)} veces (el banco necesita una)")
        crea = _sentencia(sql, sitios[0])
        partes.append(crea)
        if re.search(r"\)\s*PARTITION\s+BY", crea, re.I):
            partes.append(f"CREATE TABLE {t}_banco PARTITION OF {t} DEFAULT;")
        for m in re.finditer(rf"CREATE\s+(?:UNIQUE\s+)?INDEX\b[^;]*?\bON\s+(?:ONLY\s+)?{t}\b", sql, re.I):
            partes.append(_sentencia(sql, m.start()))
        for m in re.finditer(rf"ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?{t}\b", sql, re.I):
            s = _sentencia(sql, m.start())
            if re.search(r"\bADD\s+COLUMN\b", s, re.I):
                partes.append(s)
    return "\n".join(partes) + "\n"


def tablas_del_esquema(schema: Path | None = None) -> set[str]:
    return {m.group(1) for m in CREA.finditer((schema or REPO / "sql" / "schema.sql").read_text(encoding="utf-8"))}


def lee(funciones: set[str], fuente: Path | None = None, schema: Path | None = None) -> dict[str, set[str]]:
    """{tabla: {funcion servida que la alcanza}} para las tablas de schema.sql que nombran las cadenas alcanzadas."""
    arbol = ast.parse((fuente or REPO / "app" / "orderflow_lectura.py").read_text(encoding="utf-8"))
    defs: dict[str, ast.AST] = {}
    for n in arbol.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[n.name] = n
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        defs[x.id] = n
    faltan = sorted(f for f in funciones if f not in defs)
    if faltan:
        raise SystemExit(f"K122-esquema: app/orderflow_lectura.py no define {', '.join(faltan)}")
    esquema = tablas_del_esquema(schema)
    out: dict[str, set[str]] = {}
    for raiz in sorted(funciones):
        vistos, pila, cadenas = set(), [raiz], []
        while pila:
            nombre = pila.pop()
            if nombre in vistos or nombre not in defs:
                continue
            vistos.add(nombre)
            docs = {id(b[0].value) for b in [getattr(x, "body", None) for x in ast.walk(defs[nombre])]
                    if isinstance(b, list) and b and isinstance(b[0], ast.Expr)}
            for x in ast.walk(defs[nombre]):
                if isinstance(x, ast.Name):
                    pila.append(x.id)
                elif isinstance(x, ast.Constant) and isinstance(x.value, str) and id(x) not in docs:
                    cadenas.append(x.value)
        for palabra in set(re.findall(r"[a-z_][a-z0-9_]*", "\n".join(cadenas))) & esquema:
            out.setdefault(palabra, set()).add(raiz)
    return out


def carga_banco(ruta: Path):
    spec = importlib.util.spec_from_file_location(f"banco_{ruta.stem.replace('-', '_')}", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def juzga(bancos: list[Path]) -> int:
    malos, lineas = [], []
    for ruta in bancos:
        b = carga_banco(ruta)
        servidas = {nombre for nombre, _ in b.RUTAS.values()}
        crea = {m.group(1) for m in CREA.finditer(b.ddl_banco())}
        leidas = lee(servidas)
        for t in sorted(set(leidas) - crea):
            malos.append(f"{ruta.name} no crea {t}, que leen {', '.join(sorted(leidas[t]))} (app/orderflow_lectura.py)")
        lineas.append(f"  {ruta.name}: sirve {len(servidas)} rutas, que leen {len(leidas)} tablas: "
                      + " ".join(f"{t}{'' if t in crea else '[FALTA]'}" for t in sorted(leidas)))
    print(("ROJO: " + malos[0] + (f" (y {len(malos) - 1} mas)" if len(malos) > 1 else "")) if malos
          else f"VERDE: los {len(bancos)} bancos crean todas las tablas que leen sus rutas")
    print("\n".join(["  " + m for m in malos[1:]] + lineas))
    return 1 if malos else 0


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "juzga":
        sys.exit(juzga([Path(p) for p in sys.argv[2:]]))
    print(__doc__)
    sys.exit(2)
