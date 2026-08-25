#!/bin/bash
# K20  ningun endpoint puede devolver 5xx. ROJO hoy: /api/external-macro responde 500
# el 100% de las veces (1712 de 1712 en el access.log de 140) porque
# app/external_macro.py:319 hace float(row["price_close"]) sobre un NULL. Un hueco ni
# se declara ni se enmascara: tumba la peticion entera.
#
# Las rutas se ENUMERAN DEL CODIGO, no de una lista escrita a mano: se importa
# app.api y se lee su propio openapi(). Si manana alguien anade un endpoint, entra
# solo en el barrido. Una lista a mano es como K05 se paso 15 dias sin ver dos
# websockets muertos. Importar app.api NO abre la base: create_pool solo corre en el
# arranque de la aplicacion, y aqui no se arranca.
#
# Falla CERRADO en tres casos distintos, y los distingue en la salida:
#   5xx   -> el endpoint esta roto. Es el fallo que persigue K20.
#   4xx   -> el barrido no sabe llamar a esa ruta (parametro nuevo, o mal valor).
#            Tambien es fallo: un check que se salta lo que no entiende pasa a verde
#            sin haber probado nada.
#   parametro obligatorio desconocido -> se para y lo dice, en vez de omitirlo.
#
# Salida 2 = NO MEDIDO: solo si no hay repo/venv o si la API no contesta a nada.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
# El interprete puede venir de fuera: el gate de K15 corre estos checks contra el
# arbol de origin/main, que no tiene .venv propio. El venv solo aporta dependencias;
# el arbol que se mide lo fija REPO.
PY="${VENV_PY:-$REPO/.venv/bin/python}"

[ -x "$PY" ] || { echo "NO MEDIDO: falta $PY"; exit 2; }

salida=$(cd "$REPO" && "$PY" - "$API_PROD" "$NETRC" <<'PY' 2>&1
import json, subprocess, sys, urllib.parse

base, netrc = sys.argv[1], sys.argv[2]

def pedir(ruta, max_time="20"):
    """Devuelve el codigo HTTP como cadena. curl -w lo imprime aunque expire."""
    cmd = ["curl", "-sS", "-k", "--netrc-file", netrc, "--max-time", max_time,
           "-o", "/dev/null", "-w", "%{http_code}", base + ruta]
    p = subprocess.run(cmd, capture_output=True, text=True)
    return (p.stdout or "000").strip()[-3:]

try:
    from app.api import app
except Exception as exc:
    print("NOMED no se pudo importar app.api: %s" % exc)
    raise SystemExit(0)

spec = app.openapi()

# El unico valor que no es constante: los numericos se sacan del precio de verdad,
# para no dejar una cifra fija que envejezca en el propio check.
cierre = None
try:
    crudo = subprocess.run(
        ["curl", "-sS", "-k", "--netrc-file", netrc, "--max-time", "20",
         base + "/api/ohlcv?symbol=BTCUSDT_PERP.A"],
        capture_output=True, text=True,
    ).stdout
    cuerpo = json.loads(crudo)
    # K03 · la serie ya no es un array pelado sino un sobre {rows, coverage, data_gaps}.
    # Y se coge el ultimo cierre NO NULO: desde K02 la ultima barra puede venir
    # enmascarada, y un null aqui dejaria este check en NOMED por un motivo que no es
    # el suyo -aqui solo se necesita un precio plausible para construir peticiones-.
    barras = cuerpo["rows"] if isinstance(cuerpo, dict) else cuerpo
    cierre = next(
        float(b["close"]) for b in reversed(barras) if b.get("close") is not None
    )
except Exception:
    cierre = None
if not cierre:
    print("NOMED /api/ohlcv no dio un cierre con el que construir low/high/level")
    raise SystemExit(0)

VALORES = {
    "symbol": "BTCUSDT_PERP.A",
    "level": "%.2f" % cierre,
    "low": "%.2f" % (cierre * 0.98),
    "high": "%.2f" % (cierre * 1.02),
}

rotos, sin_saber, desconocidos, total = [], [], [], 0
for ruta, metodos in sorted(spec["paths"].items()):
    op = metodos.get("get")
    if op is None:
        continue
    query = {}
    falta = False
    for p in op.get("parameters", []):
        if not p.get("required"):
            continue
        nombre = p["name"]
        if nombre not in VALORES:
            desconocidos.append("%s(%s)" % (ruta, nombre))
            falta = True
            break
        query[nombre] = VALORES[nombre]
    if falta:
        continue
    destino = ruta + ("?" + urllib.parse.urlencode(query) if query else "")
    # /api/stream es SSE: no termina nunca. Con max-time corto curl igualmente
    # devuelve el codigo de la cabecera, que es lo unico que mira K20.
    codigo = pedir(destino, "5" if ruta == "/api/stream" else "20")
    total += 1
    if codigo.startswith("5"):
        rotos.append("%s=%s" % (ruta, codigo))
    elif codigo.startswith("4"):
        sin_saber.append("%s=%s" % (ruta, codigo))
    elif codigo == "000":
        sin_saber.append("%s=sin_respuesta" % ruta)

if desconocidos:
    print("PARAM %s" % " ".join(sorted(set(desconocidos))))
elif rotos:
    print("ROTO %d/%d con 5xx: %s" % (len(rotos), total, " ".join(rotos)))
elif sin_saber:
    print("LLAMADA %s" % " ".join(sin_saber))
else:
    print("OK %d rutas barridas, ninguna 5xx" % total)
PY
)

case "$salida" in
  NOMED*)    echo "NO MEDIDO: ${salida#NOMED }"; exit 2 ;;
  PARAM*)    echo "el barrido no sabe rellenar un parametro obligatorio nuevo: ${salida#PARAM }"; exit 1 ;;
  ROTO*)     echo "${salida#ROTO }"; exit 1 ;;
  LLAMADA*)  echo "el barrido no supo llamar a: ${salida#LLAMADA }"; exit 1 ;;
  OK*)       echo "${salida#OK }"; exit 0 ;;
  *)         echo "NO MEDIDO: barrido sin veredicto -> $(printf '%s' "$salida" | head -3)"; exit 2 ;;
esac
