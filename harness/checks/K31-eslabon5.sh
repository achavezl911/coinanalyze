#!/bin/bash
# K31  eslabon 5 de la cadena: el panel LLAMA a lo que existe. El alcance de 29
# capacidades se evaluo por un solo eslabon -si existe el productor- y por eso casi
# todo salia "MUY ALTA". Entre el modulo y el operador hay seis, y este es el que
# nadie habia contado.
#
# Medido el 2026-08-25: 23 de las 61 rutas de /api/ no aparecen NI UNA VEZ en
# static/app.js. Varias responden 200 con datos: /api/scalp/signals devuelve 106 KB
# y el panel no lo menciona. Eso no es una capacidad que falte construir: es una
# capacidad construida que nadie ha cableado. Por eso K31 va ANTES del bloque 5.
#
# Este check NO llama a la API: eso ya lo hace K20, que barre las 63 rutas buscando
# 5xx. Aqui solo se mide la referencia desde el panel. Los dos juntos dan los
# eslabones 4 y 5; el 6 -que el numero sea correcto- no lo verifica nadie todavia.
#
# app.js son 182 KB y NO se lee: se grepea ruta por ruta (regla C1).
#
# EXCEPCIONES declaradas, con su motivo medido. No es una lista de conveniencia: si
# se anade una sin cita, el proximo que la lea no sabra si es real.
#   /api/ai/context y /api/ai/context/bundle  los consume el ai-bridge
#       (coinalyze_client.py:34,:42 en /opt/coinalyze-ai-bridge)
#   /api/ai/profiles  lo llama la smoke() del desplegador (deploy-coinalyze:73-88)
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
PANEL="$REPO/static/app.js"
# El interprete puede venir de fuera: el gate de K15 corre estos checks contra el
# arbol de origin/main, que no tiene .venv propio. El venv solo aporta dependencias;
# el arbol que se mide lo fija REPO.
PY="${VENV_PY:-$REPO/.venv/bin/python}"
EXCEPCIONES="/api/ai/context /api/ai/context/bundle /api/ai/profiles"

[ -r "$PANEL" ] || { echo "NO MEDIDO: no se puede leer static/app.js"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: falta el venv del repo"; exit 2; }

rutas=$(cd "$REPO" && "$PY" -c "
from app.api import app
print('\n'.join(sorted(r for r in app.openapi()['paths'] if r.startswith('/api/'))))
" 2>/dev/null)
[ -n "$rutas" ] || { echo "NO MEDIDO: no se pudieron enumerar las rutas"; exit 2; }

total=0; sin_cablear=""
for r in $rutas; do
  total=$((total+1))
  case " $EXCEPCIONES " in *" $r "*) continue ;; esac
  grep -qF "$r" "$PANEL" || sin_cablear="$sin_cablear $r"
done

n=$(printf '%s' "$sin_cablear" | wc -w)
[ "$n" -eq 0 ] || {
  echo "$n de $total rutas existen y el panel no las llama:$sin_cablear" | cut -c1-260
  exit 1
}
echo "las $total rutas de /api/ estan cableadas al panel o declaradas como no-panel"
