#!/bin/bash
# K08  la aplicacion tiene que saber -y decir- a que base se conecto. Hoy no lo sabe:
# en app/db.py create_pool, lo PRIMERO que ocurre tras conectar es sync_market_catalog
# (que ESCRIBE en market_assets y symbols) y despues ensure_temporal_partitions (que
# crea particiones por DDL). No hay ninguna lectura de verificacion antes de escribir.
#
# Medido el 2026-08-25: app/db.py no menciona current_database() ni current_setting
# NI UNA VEZ, y /api/healthz no publica ninguna identidad de base. O sea que un
# despliegue apuntando a la base equivocada no se distingue de uno bueno: escribe
# igual, y encima escribe ANTES de que nadie pueda mirar.
#
# Dos senales, y la segunda es la que importa de verdad:
#   1. app/db.py consulta la identidad de la base en algun sitio.
#   2. La identidad es OBSERVABLE DESDE FUERA. Que el codigo la consulte y se la
#      guarde no sirve de nada: si no sale por la API, nadie puede comprobar a que
#      base esta enganchado lo que corre. Esta es la que convierte K08 en verificable
#      sin leerse el arbol, y es la unica que sobrevive a un despliegue mal apuntado.
#
# El check NO exige que la huella coincida con nada: exige que EXISTA y se publique.
# Comparar contra lo esperado es el arreglo, no la medicion.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
API="$REPO/app/db.py"

[ -r "$API" ] || { echo "NO MEDIDO: no se puede leer app/db.py"; exit 2; }

fallos=""
[ "$(grep -c 'current_database()\|current_setting' "$API")" -ge 1 ] \
  || fallos="$fallos app/db.py no consulta nunca la identidad de la base"

cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 20 "$API_PROD/api/healthz" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/healthz no respondio"; exit 2; }

publicada=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("nojson"); raise SystemExit(0)
marcas = ("database", "dbname", "db_host", "schema_fingerprint", "schema_hash", "pg_host")
def busca(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if any(m in k.lower() for m in marcas):
                return k
            r = busca(v)
            if r: return r
    elif isinstance(o, list):
        for x in o[:5]:
            r = busca(x)
            if r: return r
    return ""
print(busca(d) or "ausente")
' 2>/dev/null)

case "$publicada" in
  nojson)  echo "NO MEDIDO: healthz no devolvio JSON"; exit 2 ;;
  ausente) fallos="$fallos; la API no publica a que base esta conectada" ;;
esac

[ -z "${fallos# }" ] || { printf '%s\n' "${fallos#; }" | sed 's/^ //' | cut -c1-200; exit 1; }
echo "la base se verifica en db.py y se publica en la API (campo $publicada)"
