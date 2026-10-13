#!/bin/bash
# K01a-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K01a PROMETE (campana 137, C0)
#
# K01a juzga dos cosas del espejo: que no le FALTE ninguna tabla de sql/schema.sql, y que no este
# restaurado a medias. Todo aqui va en bases DESECHABLES k01a_ctl_<pid>* que se borran al salir; el
# espejo de verdad solo se LEE (un brazo, el ultimo).
#
#   base          schema.sql de este arbol + una fila en signal_outcome                  VERDE
#   falta_una     la misma sin UNA tabla declarada                                       ROJO, y la NOMBRA
#   a_medias      la misma con signal_outcome vacia                                      ROJO
#   doble         la misma con 600 tablas de MAS (el espejo tiene 285 el 2026-10-13)     VERDE
#     y su gemelo: el K01a de ANTES (aa5ad6f) sobre esa base                             NO MEDIDO
#                  -si el de antes midiera ahi, el plantado no produciria el fenomeno-
#   lista_cortada un schema.sql de control con 160 tablas DECLARADAS de 60 letras, todas
#                 creadas: su listado no cabe en el corte del canal                      NO MEDIDO, nunca VERDE
#     y su gemelo: el mismo con 100 (cabe)                                               VERDE
#                  -lo que decide es el corte, no lo largo del nombre-
#   sin_base      una base que no existe                                                 NO MEDIDO
#   espejo_hoy    el espejo real, tal como esta, sin tocarlo                             VERDE
#
# El check se corre de las tres formas (A56) y en los dos modos de SIGPIPE (A89).
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO_ARBOL=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K01a-espejo.sh"
H=/var/run/postgresql
[ -r "$CHK" ] && [ -r "$REPO_ARBOL/sql/schema.sql" ] || { echo "control: falta $CHK o sql/schema.sql"; exit 2; }
PID=$$
BASE="k01a_ctl_${PID}"
T=$(mktemp -d) || exit 2

limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k01a_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  quedan=$(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k01a_ctl_${PID}%'")
  echo "bases k01a_ctl_${PID}* que quedan: $quedan"
  rm -rf "$T"
}
trap limpia EXIT
trap 'limpia; trap - EXIT; exit 143' INT TERM

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-22s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-22s %s\n' "$1" "$3"; fi
}
corre() {  # base [check] [repo] -> rc; la salida queda en $T/salida
  env ESPEJO_DB="$1" REPO="${3:-$REPO_ARBOL}" bash "${2:-$CHK}" > "$T/salida" 2>&1
  echo $?
}
primera() { head -1 "$T/salida" | cut -c1-150; }
es() { [ "$1" = "$2" ] && echo 0 || echo 1; }  # rc esperado
sql() { psql -h "$H" -d "$1" -X -q -v ON_ERROR_STOP=1 -c "$2" > /dev/null 2>"$T/err" || { echo "control: fallo el SQL de siembra en $1: $(head -1 "$T/err")"; exit 2; }; }
copia() { createdb -h "$H" -T "$BASE" "$1" > /dev/null 2>&1 || { echo "control: no pude copiar $BASE a $1"; exit 2; }; }
# Una fila en signal_outcome sin sembrar su observacion: la FK no se dispara en modo replica.
FILA="SET session_replication_role = replica; INSERT INTO signal_outcome (observation_id, horizon_minutes, window_start, window_end, due_at, next_attempt_at, path_start_delay_seconds, bars_expected) VALUES (1, 1, '2026-01-01T00:00Z', '2026-01-01T00:01Z', '2026-01-01T00:02Z', '2026-01-01T00:02Z', 0, 1)"

echo "== base de control $BASE"
createdb -h "$H" "$BASE" || exit 2
psql -h "$H" -d "$BASE" -X -q -v ON_ERROR_STOP=1 -f "$REPO_ARBOL/sql/schema.sql" > /dev/null 2>&1 || { echo "control: schema.sql no aplica"; exit 2; }
sql "$BASE" "$FILA"
n_decl=$(grep -cE '^CREATE TABLE( IF NOT EXISTS)? [a-z_]+' "$REPO_ARBOL/sql/schema.sql")
n_base=$(psql -h "$H" -d "$BASE" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
echo "   schema.sql declara $n_decl tablas; la base recien creada tiene $n_base"

echo "== el gemelo correcto"
rc=$(corre "$BASE"); comprueba base_verde "$(es "$rc" 0)" "rc=$rc · $(primera)"

echo "== A89 · los dos modos de SIGPIPE, y A56 · las tres invocaciones del check"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo ESPEJO_DB="$BASE" REPO="$REPO_ARBOL" bash "$CHK" > "$T/salida" 2>&1; rc=$?
  comprueba "sigpipe$modo" "$(es "$rc" 0)" "rc=$rc · $(primera)"
done
(env ESPEJO_DB="$BASE" REPO="$REPO_ARBOL" bash "$CHK" > "$T/salida" 2>&1); rc=$?
comprueba invocacion_absoluta "$(es "$rc" 0)" "rc=$rc · $(primera)"
(cd "$REPO_ARBOL" && env ESPEJO_DB="$BASE" REPO="$REPO_ARBOL" bash harness/checks/K01a-espejo.sh > "$T/salida" 2>&1); rc=$?
comprueba invocacion_relativa "$(es "$rc" 0)" "rc=$rc · $(primera)"
(cd /tmp && env ESPEJO_DB="$BASE" REPO="$REPO_ARBOL" bash "$CHK" > "$T/salida" 2>&1); rc=$?
comprueba invocacion_ajena "$(es "$rc" 0)" "rc=$rc · $(primera)"

echo "== falta UNA tabla declarada"
copia "${BASE}_falta"
sql "${BASE}_falta" "DROP TABLE entrada_latido CASCADE"
rc=$(corre "${BASE}_falta")
comprueba falta_una_rojo "$(es "$rc" 1)" "rc=$rc · $(primera)"
comprueba falta_una_la_nombra "$(grep -q 'faltan 1 de .*entrada_latido' "$T/salida" && echo 0 || echo 1)" "$(primera)"

echo "== restaurada a medias: signal_outcome vacia"
copia "${BASE}_medias"
sql "${BASE}_medias" "SET session_replication_role = replica; DELETE FROM signal_outcome"
rc=$(corre "${BASE}_medias")
comprueba a_medias_rojo "$(es "$rc" 1)" "rc=$rc · $(primera)"

echo "== el DOBLE de tablas que el espejo de hoy, y completo"
copia "${BASE}_doble"
sql "${BASE}_doble" "DO \$\$ BEGIN FOR i IN 1..600 LOOP EXECUTE format('CREATE TABLE zz_de_mas_p%s (id int)', i); END LOOP; END \$\$"
n_doble=$(psql -h "$H" -d "${BASE}_doble" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname='public'")
b_doble=$(psql -h "$H" -d "${BASE}_doble" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1" | wc -c)
rc=$(corre "${BASE}_doble")
comprueba doble_verde "$([ "$rc" = 0 ] && [ "$n_doble" -ge 570 ] && echo 0 || echo 1)" "rc=$rc · $n_doble tablas, $b_doble bytes de listado · $(primera)"
if git -C "$REPO_ARBOL" show aa5ad6f:harness/checks/K01a-espejo.sh > "$T/K01a-antes.sh" 2>/dev/null; then
  rc=$(corre "${BASE}_doble" "$T/K01a-antes.sh")
  comprueba doble_antes_no_media "$(es "$rc" 2)" "rc=$rc · el K01a de aa5ad6f: $(primera)"
else
  comprueba doble_antes_no_media 1 "no pude leer el K01a de aa5ad6f del historial"
fi

echo "== una lista que de verdad NO llega entera"
letras() { printf '%s' "$1" | tr '0-9' 'a-j'; }   # la regex de declaradas no admite digitos
fabrica() {  # n -> un repo de control con n tablas declaradas de 60 letras, y su base con todas creadas
  local n="$1" dir="$T/repo_$1" db="${BASE}_largo$1" i nombre
  mkdir -p "$dir/sql"
  echo "CREATE TABLE IF NOT EXISTS signal_outcome (id int);" > "$dir/sql/schema.sql"
  for i in $(seq -w 1 "$n"); do
    nombre="tabla_declarada_de_control_con_un_nombre_bien_largo_$(letras "$i")_zzz"
    echo "CREATE TABLE IF NOT EXISTS $nombre (id int);" >> "$dir/sql/schema.sql"
  done
  createdb -h "$H" "$db" || exit 2
  psql -h "$H" -d "$db" -X -q -v ON_ERROR_STOP=1 -f "$dir/sql/schema.sql" > /dev/null 2>&1 || { echo "control: el esquema de control no aplica"; exit 2; }
  sql "$db" "INSERT INTO signal_outcome VALUES (1)"
}
fabrica 160
b_largo=$(psql -h "$H" -d "${BASE}_largo160" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1" | wc -c)
rc=$(corre "${BASE}_largo160" "$CHK" "$T/repo_160")
comprueba lista_cortada_nomed "$([ "$rc" = 2 ] && [ "$b_largo" -gt 8000 ] && echo 0 || echo 1)" "rc=$rc · $b_largo bytes de listado · $(primera)"
comprueba lista_cortada_no_verde "$(grep -q '^espejo con las' "$T/salida" && echo 1 || echo 0)" "no dice «espejo con las ...»"
fabrica 100
b_corto=$(psql -h "$H" -d "${BASE}_largo100" -Atc "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1" | wc -c)
rc=$(corre "${BASE}_largo100" "$CHK" "$T/repo_100")
comprueba lista_que_cabe_verde "$([ "$rc" = 0 ] && [ "$b_corto" -lt 8000 ] && echo 0 || echo 1)" "rc=$rc · $b_corto bytes de listado · $(primera)"

echo "== una base que no existe"
rc=$(corre "${BASE}_no_existe")
comprueba sin_base_nomed "$(es "$rc" 2)" "rc=$rc · $(primera)"

echo "== el espejo de hoy, sin tocarlo (solo lectura)"
n_espejo=$(psql -h "$H" -d coinalyze_espejo -Atc "SELECT count(*) FROM pg_tables WHERE schemaname='public'" 2>/dev/null)
env -u ESPEJO_DB REPO="$REPO_ARBOL" bash "$CHK" > "$T/salida" 2>&1; rc=$?
comprueba espejo_hoy_verde "$(es "$rc" 0)" "rc=$rc · ${n_espejo:-?} tablas · $(primera)"

echo
echo "K01a-control: $pasan de $total${fallan:+ · FALLAN:$fallan}"
[ "$pasan" = "$total" ]
