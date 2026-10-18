#!/bin/bash
# archiva.sh · operador · EL ARCHIVO DEL HISTORIAL FINO de Coinalyze (pedido de Alejandro, 2026-10-18), en el NODO prox:
# cada HORA CERRADA de las tablas finas de 140, exportada por `pct exec 140` con COPY de SOLO LECTURA (la credencial no sale
# de 140: la lee el propio 140 de /etc/coinalyze/coinalyze.env, como bin/prodsql), comprimida con gzip -6, VERIFICADA (filas
# del fichero == count(*) de la misma hora; gzip -t) y escrita de forma ATOMICA en /mnt/archivo/coinalyze/<dir>/<dia>/, con
# su linea en el MANIFIESTO (tabla, hora, filas, bytes, sha256, escrito). IDEMPOTENTE: una hora con su linea en el manifiesto
# no se repite. NO escribe si falta el testigo del disco (/mnt/archivo/.DISCO-ARCHIVO): escribiria en la raiz del nodo.
#   archiva.sh                 todas las horas cerradas que aun estan en 140 y no estan en el manifiesto (hasta MAX_HORAS)
#   archiva.sh <tabla> <hora>  una (hora = AAAA-MM-DDTHH:00:00Z)
# Solo lee 140; no borra nada en ningun sitio.
set -u
export TZ=UTC LC_ALL=C
D=/mnt/archivo; R=$D/coinalyze; M=$R/MANIFIESTO.tsv; MAX_HORAS=${MAX_HORAS:-400}; CT=140
[ -f "$D/.DISCO-ARCHIVO" ] || { echo "ABORTO: no esta el testigo $D/.DISCO-ARCHIVO (el disco no esta montado): no escribo"; exit 3; }
exec 9>"$R/.archiva.lock"; flock -n 9 || { echo "ABORTO: ya hay un archiva.sh corriendo"; exit 4; }
declare -A DIR=([orderflow_cinta]=cinta [libro_foto]=libro [orderflow_celda]=celdas [scalp_signal_snapshot]=decide
                [futures_trades_realtime]=futuros-realtime [orderbook_snapshot]=libro-l1 [libro_cobertura]=libro
                [orderflow_cobertura]=celdas)
TABLAS=(scalp_signal_snapshot orderbook_snapshot futures_trades_realtime orderflow_cinta libro_foto orderflow_celda libro_cobertura orderflow_cobertura)
[ -f "$M" ] || printf 'tabla\thora\tfilas\tbytes\tsha256\tescrito\n' > "$M"

sql140() {  # $1 = SQL; salida por stdout (texto plano, sin cabeceras)
  local enc; enc=$(printf '%s' "$1" | base64 -w0)
  pct exec $CT -- sh -c "if [ -r /etc/coinalyze/coinalyze.env ]; then set -a; . /etc/coinalyze/coinalyze.env; set +a; fi
    export PGHOST=\${PG_HOST:-127.0.0.1} PGPORT=\${PG_PORT:-5432} PGUSER=coinalyze PGDATABASE=coinalyze PGPASSWORD=\${PG_PASSWORD:-}
    export PGOPTIONS='-c default_transaction_read_only=on -c statement_timeout=600000 -c timezone=UTC'
    printf %s '$enc' | base64 -d | psql -X -A -t -q -v ON_ERROR_STOP=1 -f -"
}

una() {  # $1 tabla, $2 hora (AAAA-MM-DDTHH:00:00Z)
  local t=$1 h=$2 dia carpeta f tmp n_db n_f bytes sha
  grep -q -P "^$t\t$h\t" "$M" && return 0
  dia=${h:0:10}; carpeta="$R/${DIR[$t]}/$dia"; mkdir -p "$carpeta"
  f="$carpeta/$t-$(echo "$h" | tr -d ':-' | cut -c1-11)Z.tsv.gz"; tmp="$f.tmp.$$"
  n_db=$(sql140 "SELECT count(*) FROM $t WHERE ts >= '$h' AND ts < timestamptz '$h' + interval '1 hour'") || { echo "FALLO count $t $h"; return 1; }
  sql140 "COPY (SELECT * FROM $t WHERE ts >= '$h' AND ts < timestamptz '$h' + interval '1 hour' ORDER BY ts) TO STDOUT" | gzip -6 > "$tmp"
  if [ "${PIPESTATUS[0]}" != 0 ] || ! gzip -t "$tmp" 2>/dev/null; then echo "FALLO copy $t $h"; rm -f "$tmp"; return 1; fi
  n_f=$(zcat "$tmp" | wc -l)
  if [ "$n_f" != "$n_db" ]; then echo "FALLO filas $t $h: fichero $n_f, base $n_db"; rm -f "$tmp"; return 1; fi
  bytes=$(stat -c %s "$tmp"); sha=$(sha256sum "$tmp" | cut -d' ' -f1)
  mv -f "$tmp" "$f" && sync -f "$f"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$t" "$h" "$n_f" "$bytes" "$sha" "$(date -u +%FT%TZ)" >> "$M"
  echo "ok $t $h $n_f filas $bytes B"
}

if [ $# -eq 2 ]; then una "$1" "$2"; exit $?; fi
ahora=$(date -u -d '-10 min' +%Y-%m-%dT%H:00:00Z); hechas=0; fallos=0   # solo horas cerradas hace >= 10 min (minutos escritos tarde)
for t in "${TABLAS[@]}"; do
  # min(ts) POR SIMBOLO: cinta, celdas, libro y DECIDE no tienen indice que empiece por ts y el min(ts) plano barria
  # todas sus particiones en cada pase (la cinta, 1865 MB); asi va por (symbol, ...) en ~1 ms (campana 147, P2)
  primera=$(sql140 "WITH RECURSIVE s AS (SELECT min(symbol) AS v FROM $t UNION ALL SELECT (SELECT min(symbol) FROM $t WHERE symbol > s.v) FROM s WHERE s.v IS NOT NULL)
    SELECT to_char(date_trunc('hour', min(m)), 'YYYY-MM-DD\"T\"HH24:00:00\"Z\"') FROM (SELECT (SELECT min(ts) FROM $t WHERE symbol = s.v) AS m FROM s WHERE s.v IS NOT NULL) x") \
    || { echo "FALLO min $t"; fallos=$((fallos+1)); continue; }
  [ -n "$primera" ] || continue
  h=$primera
  while [ "$h" \< "$ahora" ] && [ $hechas -lt "$MAX_HORAS" ]; do
    if ! grep -q -P "^$t\t$h\t" "$M"; then
      if una "$t" "$h"; then hechas=$((hechas+1)); else fallos=$((fallos+1)); fi
    fi
    h=$(date -u -d "${h/T/ } +1 hour" +%Y-%m-%dT%H:00:00Z)
  done
done
# el MANIFIESTO, copiado DENTRO de 140 (solo lectura para el arnes, que lo lee por el canal que ya tiene: bin/prod)
pct exec $CT -- mkdir -p /var/lib/coinalyze/archivo && pct push $CT "$M" /var/lib/coinalyze/archivo/MANIFIESTO.tsv && pct exec $CT -- chmod 0644 /var/lib/coinalyze/archivo/MANIFIESTO.tsv \
  && echo "manifiesto copiado a 140:/var/lib/coinalyze/archivo/MANIFIESTO.tsv" || { echo "FALLO al copiar el manifiesto a 140"; fallos=$((fallos+1)); }
echo "fin $(date -u +%FT%TZ) · horas archivadas en esta pasada $hechas · fallos $fallos · manifiesto $(($(wc -l < "$M") - 1)) lineas · disco $(df -h $D | tail -1 | awk '{print $4}') libres"
[ $fallos -eq 0 ]
