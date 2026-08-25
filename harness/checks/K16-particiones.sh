#!/bin/bash
# K16  particiones y retencion con red. app/partitioning.py es lo UNICO del arbol que
# borra datos por diseno y no lo importa ningun test; y ensure_temporal_partitions
# esta declarada DOS veces en sql/schema.sql (:1422 y :1980).
#
# Por que la duplicacion importa, medido el 2026-08-25: en 140 hay UNA sola funcion
# con ese nombre. O sea que la segunda declaracion pisa a la primera en silencio y
# desde la base NO se puede saber cual de los dos bloques esta vivo. Editar el
# equivocado no da ningun error: simplemente no hace nada. Y el desplegador aplica
# schema.sql entero contra la base viva, asi que esto no es cosmetica.
#
# Tres comprobaciones. Las dos primeras miran el arbol -que es donde vive el defecto,
# no un proxy de el- y la tercera es un oraculo VIVO contra 140: la funcion existe y
# gestiona las cinco tablas que dice gestionar.
set -uo pipefail
_REPO_LLAMANTE=${REPO:-}
B=/srv/coinanalyze/harness; . "$B/env"
REPO=${_REPO_LLAMANTE:-${REPO:-/srv/coinanalyze/repo}}
GESTIONADAS="futures_trades_realtime spot_trades_realtime orderbook_snapshot liquidations_realtime scalp_signal_snapshot"

[ -r "$REPO/sql/schema.sql" ] || { echo "NO MEDIDO: no se puede leer sql/schema.sql"; exit 2; }

fallos=""

decls=$(grep -c 'CREATE OR REPLACE FUNCTION ensure_temporal_partitions' "$REPO/sql/schema.sql")
[ "$decls" -eq 1 ] || fallos="$fallos ensure_temporal_partitions declarada $decls veces en schema.sql"

cubierto=$(grep -rl 'app\.partitioning\|from app import partitioning' "$REPO/tests/" 2>/dev/null | wc -l)
[ "$cubierto" -ge 1 ] || fallos="$fallos; ningun test importa app/partitioning, que es lo unico que borra por diseno"

vivas=$("$B/bin/prodsql" "SELECT count(*) FROM pg_proc WHERE proname='ensure_temporal_partitions'" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
[ -n "$vivas" ] || { echo "NO MEDIDO: prodsql no respondio (${fallos:-canal})"; exit 2; }
[ "$vivas" -eq 1 ] || fallos="$fallos; en 140 hay $vivas funciones ensure_temporal_partitions"

# Oraculo vivo: el cuerpo instalado tiene que nombrar las cinco tablas gestionadas.
# Si manana alguien anade una tabla particionada y no entra aqui, se queda sin
# particiones nuevas y sin retencion, en silencio.
cuerpo=$("$B/bin/prodsql" "SELECT replace(pg_get_functiondef(oid), E'\n', ' ') FROM pg_proc WHERE proname='ensure_temporal_partitions' LIMIT 1" 2>/dev/null)
for t in $GESTIONADAS; do
  case "$cuerpo" in *"$t"*) ;; *) fallos="$fallos; la funcion viva no gestiona $t" ;; esac
done

[ -z "${fallos# }" ] || { printf '%s\n' "${fallos#; }" | sed 's/^ //'; exit 1; }
echo "una sola declaracion, $cubierto test(s) sobre partitioning, y la funcion viva gestiona las 5 tablas"
