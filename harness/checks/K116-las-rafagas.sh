#!/bin/bash
# K116 · LAS RAFAGAS · campana BOT-1
#
# QUE JUZGA. Que el detector y el clasificador de app/rafagas.py, con sus umbrales CONGELADOS, sobre la muestra fija
# de la prueba (K116-muestra.tsv.xz: barras de 1 min de Binance BTC/ETH/SOL del 2026-08-31 al 10-22 y los bloques de
# liquidaciones de 140, con su huella), dan LOS MISMOS eventos, clases, controles y tablas que la entrega
# (K116-esperado.json, la salida de `scripts/rafagas_estudio.py prueba` que cita la entrega):
#   un umbral movido, una rafaga que falta o sobra, una clase cambiada, un control que deja de verse o una cifra de
#   las tablas que no cuadra -> ROJO con la primera diferencia; la muestra cambiada (otra huella) -> ROJO.
# Los juzga harness/checks/K116-rafagas.py; este guion elige el sujeto y llama.
#
# SUJETOS. K116_REPO (el arbol del codigo; por defecto el de este check), K116_MUESTRA y K116_ESPERADO (por defecto
# los de este directorio). NO MEDIDO sin la muestra. No mira produccion: no tiene canal.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u

AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "NO MEDIDO: K116 no resuelvo mi directorio"; exit 2; }
REPO=${K116_REPO:-$(cd -- "$AQUI/../.." && pwd -P)}
PY=${K116_PY:-$REPO/.venv/bin/python}
[ -x "$PY" ] || PY=$(command -v python3)
AYUDANTE="$AQUI/K116-rafagas.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: K116 no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: K116 sin python"; exit 2; }

D=$(mktemp -d) || { echo "NO MEDIDO: K116 sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT
# -S: sin site, para que el .venv editable no cambie el arbol que se importa (se comprueba dentro)
K116_REPO="$REPO" K116_MUESTRA="${K116_MUESTRA:-$AQUI/K116-muestra.tsv.xz}" \
  K116_ESPERADO="${K116_ESPERADO:-$AQUI/K116-esperado.json}" "$PY" -S "$AYUDANTE" > "$D/juicio" 2>&1
rc=$?
case "$rc" in
  0|1|2) cat "$D/juicio"; exit "$rc" ;;
esac
# un ayudante que revienta no midio: NO MEDIDO con su ultima linea, nunca un ROJO por un traceback
echo "NO MEDIDO: K116 el ayudante cayo con rc=$rc: $(tail -1 "$D/juicio" | cut -c1-160)"
exit 2
