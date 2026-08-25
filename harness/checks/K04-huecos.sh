#!/bin/bash
# K04  un hueco o se resuelve o queda escrito por que no. ROJO hoy: 508 unresolved,
# ninguno cambio nunca de estado desde el 2026-08-10, +29 al dia.
# Salida 2 = NO MEDIDO. Si la respuesta no es un numero, no es una medicion.
set -uo pipefail
B=/srv/coinanalyze/harness
n=$("$B/bin/prodsql" "SELECT count(*) FROM data_gap
     WHERE status='unresolved' AND start_ts < now()-interval '24 hours'" 2>/dev/null \
     | tr -d ' ' | head -1)
case "$n" in
  ''|*[!0-9]*) echo "NO MEDIDO: prodsql devolvio '$n', que no es un numero"; exit 2 ;;
esac
[ "$n" -eq 0 ] || { echo "$n huecos sin resolver de mas de 24 h"; exit 1; }
echo "0 huecos sin resolver de mas de 24 h"
