#!/bin/bash
# K115 · EL ARCHIVO · campana 147
#
# QUE JUZGA. El MANIFIESTO del archivo del historial fino (tools/archivo/archiva.sh, que corre en el nodo prox y
# guarda cada hora cerrada de ocho tablas en /mnt/archivo) contra la base de la que sale:
#   (a) ninguna hora que la base aun tiene y que cerro hace mas de 75 min falta en el manifiesto;
#   (b) las filas de cada linea == count(*) de su hora en la base, mientras la base la tenga entera;
#   (c) el archivador vive: la ultima linea de la copia del manifiesto se escribio hace menos de 75 min;
#   (d) la continuidad: desde la primera hora archivada, ninguna que la base ya borro falta en el manifiesto.
# Los brazos los juzga harness/checks/K115-archivo.py; este guion elige el sujeto y llama.
#
# SUJETOS. K115_SUJETO=produccion (por defecto: la copia que el archivador deja en 140 por bin/prod, y la base por
# bin/prodsql, solo lectura) o local (K115_MANIFIESTO fichero, K115_BASE dsn de psql, K115_AHORA instante plantado;
# la retencion, la del config.py del arbol). NO MEDIDO sin manifiesto en 140. No mira el nodo: no hay canal.
#
# rc: 0 VERDE · 1 ROJO · 2 NO MEDIDO.
set -u

REPO=${K115_REPO:-/srv/coinanalyze/repo}
B=${K115_HARNESS:-/srv/coinanalyze/harness}
PY=${K115_PY:-$REPO/.venv/bin/python}
AYUDANTE="$REPO/harness/checks/K115-archivo.py"
[ -r "$AYUDANTE" ] || { echo "NO MEDIDO: no encuentro $AYUDANTE"; exit 2; }
[ -x "$PY" ] || { echo "NO MEDIDO: sin python del arbol en $PY"; exit 2; }
case "${K115_SUJETO:-produccion}" in
  produccion) ;;
  local) [ -n "${K115_BASE:-}" ] || { echo "NO MEDIDO: K115_SUJETO=local pide K115_BASE"; exit 2; } ;;
  *) echo "NO MEDIDO: K115_SUJETO=${K115_SUJETO} no es produccion ni local"; exit 2 ;;
esac

D=$(mktemp -d) || { echo "NO MEDIDO: sin directorio temporal"; exit 2; }
trap 'rm -rf "$D"' EXIT
K115_HARNESS="$B" K115_REPO="$REPO" "$PY" "$AYUDANTE" > "$D/juicio" 2>&1
rc=$?
case "$rc" in
  0|1|2) cat "$D/juicio"; exit "$rc" ;;
esac
# un ayudante que revienta no midio: NO MEDIDO con su ultima linea, nunca un ROJO por un traceback
echo "NO MEDIDO: el ayudante de K115 cayo con rc=$rc: $(tail -1 "$D/juicio" | cut -c1-160)"
exit 2
