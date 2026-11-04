#!/bin/bash
# K118 · LA CAPA HONDA DEL LIBRO · campana 151-A
#
# QUE JUZGA. Que la escalera honda (libro_honda, app/libro_honda.py) es la que sale de RECONTAR A MANO la respuesta
# cruda del venue (books-full de OKX, merge-depth de Bitget), sobre una muestra de la corrida de 16 min contra una
# base desechable de 143 (2026-11-03): la fila GUARDADA y la que el arbol RECALCULA del mismo crudo, nivel a nivel;
# un lado cuyo cubo no parte el paso, o la venta de merge-depth (agrupa por techo), con niveles -> ROJO; una foto
# servida pasados 75 s de la hora del venue que cuenta como conocida -> ROJO. Juzga harness/checks/K118-honda.py.
#
# SUJETOS. K118_REPO (el arbol; por defecto el de este check) y K118_MUESTRA (por defecto la evidencia de 143, FUERA
# del repo: /srv/coinanalyze/evidencia/c151-libro-honda-muestra.json.xz). Sin la muestra: NO MEDIDO (asi en el CI).
# No mira produccion: no tiene canal.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u

AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "NO MEDIDO: K118 no resuelvo mi directorio"; exit 2; }
REPO=${K118_REPO:-$(cd -- "$AQUI/../.." && pwd -P)}
PY=${K118_PY:-$(cd -- "$AQUI/../.." && pwd -P)/.venv/bin/python}
[ -x "$PY" ] || PY=$(command -v python3)
AYUDANTE="$AQUI/K118-honda.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: K118 no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: K118 sin python"; exit 2; }

D=$(mktemp -d) || { echo "NO MEDIDO: K118 sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT
# -S: sin site, para que el .venv editable no cambie el arbol que se importa (se comprueba dentro)
K118_REPO="$REPO" K118_MUESTRA="${K118_MUESTRA:-/srv/coinanalyze/evidencia/c151-libro-honda-muestra.json.xz}" \
  "$PY" -S "$AYUDANTE" > "$D/juicio" 2>&1
rc=$?
case "$rc" in
  0|1|2) cat "$D/juicio"; exit "$rc" ;;
esac
echo "NO MEDIDO: K118 el ayudante cayo con rc=$rc: $(tail -1 "$D/juicio" | cut -c1-300)"
exit 2
