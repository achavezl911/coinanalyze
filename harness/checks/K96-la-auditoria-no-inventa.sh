#!/usr/bin/env bash
# K96 · la capa de auditoria no puede pintar un campo que la ruta no publica.
#
# EL DEFECTO QUE CAZA: el panel lee `x.spread_bps` de una fila de /api/signals/execution. Si
# manana alguien renombra la columna en app/api.py, o si hoy alguien escribe `x.spread` de
# memoria, el navegador NO se queja: `undefined` se pinta como 'N/D' y el hueco parece un dato
# que falta en la base. Esa es la forma barata de mentir en un panel, y es la que este proyecto
# ya cometio antes: rellenar con lo plausible.
#
# LO QUE COMPARA, y de que arbol sale cada lado:
#   izquierda  los nombres que static/app.js LEE de los sobres de las cinco rutas (repo)
#   derecha    los nombres que app/api.py PUBLICA: columnas del SELECT + claves del return (repo)
# Los dos lados salen del MISMO arbol a proposito: esto no mide produccion, mide coherencia
# interna, y por eso puede correr sin canal. Que 140 sirva lo mismo lo miden K21/K23/K24/K25.
#
# NO comprueba que el campo tenga el valor correcto -eso no lo puede saber un lector de texto-.
# Comprueba lo unico que se puede comprobar sin canal: que el nombre exista en el origen.
set -uo pipefail
REPO=${K96_REPO:-/srv/coinanalyze/repo}
JS="$REPO/static/app.js"
PY="$REPO/app/api.py"
for f in "$JS" "$PY"; do
  [ -r "$f" ] || { echo "NO MEDIDO: no se puede leer $f"; exit 2; }
done

python3 - "$JS" "$PY" <<'PYEOF'
import re, sys

js = open(sys.argv[1], encoding="utf-8").read()
py = open(sys.argv[2], encoding="utf-8").read()

# --- IZQUIERDA · la capa de auditoria de app.js, delimitada por sus propias funciones.
ini = js.find("async function pedir(")
fin = js.find("const LEGACY_HYPOTHESIS")
if ini < 0 or fin < 0 or fin <= ini:
    print("NO MEDIDO: no encuentro la capa de auditoria en app.js"); sys.exit(2)
capa = js[ini:fin]

# Los accesos a los campos de una fila: `o.observed_at`, `s.spread_bps`, `c.horizon_minutes`,
# `f.context_hash`, `r.long_score`. Se toman los sufijos con guion bajo o conocidos, que es lo
# que distingue un campo del payload de un metodo de JS (`.length`, `.slice`, `.map`).
JS_PROPIAS = {"length", "slice", "map", "data", "ok", "error", "message", "at", "push", "get",
              "has", "set", "size", "replaceChildren", "append", "addEventListener", "key",
              "className", "textContent", "tabIndex", "preventDefault", "toFixed", "join",
              "filter", "flatMap", "entries", "hidden", "id", "symbol"}
leidos = set()
for var, campo in re.findall(r"\b([a-z]{1,10})\.([a-z][a-z0-9_]{2,})\b", capa):
    if campo in JS_PROPIAS or var in ("state", "auditoria", "document", "console", "Object",
                                      "JSON", "Promise", "Math", "Number", "String", "Array"):
        continue
    leidos.add(campo)

# --- DERECHA · lo que api.py publica. Columnas de los SELECT de las cinco rutas, con alias
# resuelto (`so.horizon_minutes` se publica como `horizon_minutes`), mas las claves del return.
publicados = set()
for bloque in ("LEDGER_COLUMNS", "OUTCOME_COLUMNS", "EXECUTION_COLUMNS", "REPLAY_COLUMNS",
               "VISIBILITY_COLUMNS"):
    m = re.search(bloque + r' = """(.*?)"""', py, re.S)
    if not m:
        print(f"NO MEDIDO: no encuentro {bloque} en app/api.py"); sys.exit(2)
    for trozo in m.group(1).replace("\n", " ").split(","):
        trozo = trozo.strip()
        if trozo:
            publicados.add(trozo.split(".")[-1])
# La de scalp/signals va inline, no en constante.
m = re.search(r"SELECT ts,symbol,(.*?)\s+FROM scalp_signal_snapshot", py, re.S)
if not m:
    print("NO MEDIDO: no encuentro el SELECT de /api/scalp/signals"); sys.exit(2)
publicados.update({"ts", "symbol"} | {c.strip() for c in m.group(1).replace("\n", " ").split(",") if c.strip()})
# Y las claves de los sobres: "count", "truncated", "ventana_maxima_h", "servida_desde"...
publicados.update(re.findall(r'^\s{8}"([a-z][a-z0-9_]+)":', py, re.M))

huerfanos = sorted(leidos - publicados)
if huerfanos:
    print(f"la capa de auditoria lee {len(huerfanos)} campo(s) que app/api.py NO publica: "
          + ", ".join(huerfanos))
    sys.exit(1)

# ANTI-FANTASMA · si la extraccion no encontro nada, un VERDE no probaria nada.
if len(leidos) < 15:
    print(f"NO MEDIDO: solo he sabido extraer {len(leidos)} campos leidos; la extraccion esta rota")
    sys.exit(2)
print(f"los {len(leidos)} campos que la capa de auditoria lee estan los {len(leidos)} entre "
      f"los {len(publicados)} que app/api.py publica: no pinta ninguno inventado")
sys.exit(0)
PYEOF
