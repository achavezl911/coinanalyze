#!/bin/bash
# restaura.sh · UNA HORA DEL ARCHIVO DE VUELTA A UNA BASE: zcat | COPY FROM STDIN, en una transaccion.
#   restaura.sh <fichero .tsv.gz del archivo> <dsn de la base destino> [MANIFIESTO.tsv]
# La tabla y la hora salen del nombre (<tabla>-AAAAMMDDTHHZ.tsv.gz, como lo escribe archiva.sh). Con el manifiesto,
# antes de cargar: su linea existe, el sha256 del fichero es el suyo y sus filas las del fichero.
# LA BASE DESTINO tiene que traer la tabla con las columnas EN EL ORDEN EN QUE 140 LAS TENIA AL ARCHIVAR: el fichero es
# COPY de `SELECT *`, sin cabecera. Una base nueva sale de sql/schema.sql del commit que 140 tenia desplegado ese dia
# (el sha esta en el deploy.log de 140); el guion compara el numero de columnas y para si no cuadra, pero un ORDEN
# distinto con el mismo numero solo lo caza un tipo que no casa. Si la tabla es particionada y falta la particion del
# dia, la crea ensure_temporal_partitions() de esa misma base. No borra nada: si la hora ya estaba, la clave primaria
# rechaza la carga entera y no entra ni una fila.
set -euo pipefail
[ $# -ge 2 ] || { echo "uso: restaura.sh <fichero.tsv.gz> <dsn> [MANIFIESTO.tsv]" >&2; exit 2; }
f=$1; dsn=$2; m=${3:-}
n=$(basename "$f" .tsv.gz); tabla=${n%-*}; s=${n##*-}
[[ $s =~ ^[0-9]{8}T[0-9]{2}Z$ ]] || { echo "el nombre no es <tabla>-AAAAMMDDTHHZ.tsv.gz: $f" >&2; exit 2; }
hora="${s:0:4}-${s:4:2}-${s:6:2}T${s:9:2}:00:00Z"
gzip -t "$f"
filas=$(zcat "$f" | wc -l)
if [ -n "$m" ]; then
  linea=$(grep -P "^$tabla\t$hora\t" "$m") || { echo "$tabla $hora no esta en $m" >&2; exit 1; }
  [ "$(cut -f5 <<< "$linea")" = "$(sha256sum < "$f" | cut -c1-64)" ] || { echo "el sha256 no es el del manifiesto" >&2; exit 1; }
  [ "$(cut -f3 <<< "$linea")" = "$filas" ] || { echo "el fichero trae $filas filas y el manifiesto $(cut -f3 <<< "$linea")" >&2; exit 1; }
fi
sql() { psql "$dsn" -X -A -t -q -v ON_ERROR_STOP=1 -c "SET TIME ZONE 'UTC'" -c "$1"; }
cols=$(sql "SELECT count(*) FROM pg_attribute WHERE attrelid = '$tabla'::regclass AND attnum > 0 AND NOT attisdropped")
[ "$filas" = 0 ] || [ "$(zcat "$f" | head -1 | awk -F'\t' '{print NF}')" = "$cols" ] \
  || { echo "el fichero no trae las $cols columnas de $tabla en la base destino" >&2; exit 1; }
antes=$(sql "SELECT count(*) FROM $tabla WHERE ts >= '$hora' AND ts < timestamptz '$hora' + interval '1 hour'")
zcat "$f" | psql "$dsn" -X -q -v ON_ERROR_STOP=1 -1 \
  -c "SET TIME ZONE 'UTC'" \
  -c "SELECT ensure_temporal_partitions('$hora', 0, 0) FROM pg_class WHERE oid = '$tabla'::regclass AND relkind = 'p'" \
  -c "COPY $tabla FROM STDIN" > /dev/null
despues=$(sql "SELECT count(*) FROM $tabla WHERE ts >= '$hora' AND ts < timestamptz '$hora' + interval '1 hour'")
[ $((despues - antes)) = "$filas" ] || { echo "entraron $((despues - antes)) filas y el fichero trae $filas" >&2; exit 1; }
echo "restaurada $tabla $hora: $filas filas (la hora tenia $antes en la base y ahora $despues)"
