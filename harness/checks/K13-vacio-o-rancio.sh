#!/bin/bash
# K13  vacio y rancio no se pueden ver igual. /api/scalp/orderbook filtra
# ts >= now()-30s (app/api.py:1129-1134): cuando el libro se queda viejo la consulta
# devuelve CERO filas y la respuesta es {"rows": [], "symbol": ...}, que es
# indistinguible de "no hay datos". El operador ve una tabla vacia en los dos casos.
#
# Medido el 2026-08-25 con el libro fresco: la respuesta trae exactamente dos claves,
# rows y symbol. Ni edad, ni as_of, ni estado.
#
# LA SENYAL TIENE QUE IR FUERA DE rows, y este es el punto entero de la unidad: con
# cero filas no queda NADA de donde inferir la edad. Un ts por fila no sirve, porque
# el caso que hay que distinguir es justo aquel en el que no hay filas. Por eso el
# check exige la marca en el nivel de arriba y no acepta que este dentro de rows.
#
# No hace falta esperar a que el libro se ponga rancio para medir esto: si la clave
# no existe estando fresco, tampoco existira estando viejo.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SIM=${K13_SIMBOLO:-BTCUSDT_PERP.A}

cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 20 "$API_PROD/api/scalp/orderbook?symbol=$SIM" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/scalp/orderbook no respondio"; exit 2; }

veredicto=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    print("NOMED json ilegible"); raise SystemExit(0)
if not isinstance(d, dict):
    print("NOMED la respuesta no es un objeto"); raise SystemExit(0)
# Marcas validas de frescura, siempre en el nivel de arriba.
marcas = ("age_seconds", "lag_seconds", "as_of", "observed_at", "stale", "freshness", "status")
tiene = sorted(k for k in d if any(m in k.lower() for m in marcas))
filas = d.get("rows")
n = len(filas) if isinstance(filas, list) else -1
if tiene:
    print("OK %s filas=%d" % (",".join(tiene), n))
else:
    print("FALTA claves=%s filas=%d" % (",".join(sorted(d)), n))
' 2>/dev/null)

case "$veredicto" in
  NOMED*) echo "NO MEDIDO: ${veredicto#NOMED }"; exit 2 ;;
  FALTA*)
    echo "/api/scalp/orderbook no distingue vacio de rancio: ${veredicto#FALTA }"; exit 1 ;;
  OK*)
    echo "/api/scalp/orderbook declara frescura: ${veredicto#OK }"; exit 0 ;;
  *) echo "NO MEDIDO: sin veredicto"; exit 2 ;;
esac
