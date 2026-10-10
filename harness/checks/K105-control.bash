#!/bin/bash
# K105-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K105 PROMETE (campana 135, C5)
#
# Todo en bases DESECHABLES k105_ctl_<pid>* que se borran al salir (y se comprueba que se borraron).
# Base: schema.sql de este arbol, reglamento de control registrado (v1 y v2 del arbol, cada una con
# SU tope), BTC y ETH sembrados en la vela T actual y evaluados con el generador REAL: en cada
# version un DISPARADO y una SOMBRA «solo perpetuo». Su gemelo tiene que salir VERDE; cada
# plantado, en una COPIA de la base, tiene que salir ROJO por su brazo:
#
#   sin_stop       un DISPARADO sin stop                              c
#   posterior      un insumo con hora posterior a su registro         d
#   sin_spot       un DISPARADO sin la pata spot completa (MC12)      c
#   dos_vivos      dos DISPARADOS vivos en zonas que se solapan       e
#   disparador     el BEFORE UPDATE OR DELETE desactivado             b
#   evento_ajeno   una SOMBRA de evento con un calendario que no es el de su registro   f
#   evento_atras   un evento con hora anterior a la revision que lo trae (release)      f
#   vacio          cero DISPARADOS y SOMBRAS: NO MEDIDO, nunca VERDE
#   antes          los BYTES de antes del registro (82ae7e2: esquema y release sin el): sus brazos CAEN
#
# DOS VERSIONES A LA VEZ (campana 136). La base solo conoce el tope que la fila TRAE; K105 juzga
# cada fila con el tope y las huellas de SU version en el release:
#   tope_gemelo    un DISPARADO de v2 por encima del tope de v1 y dentro del suyo: VERDE (un K105
#                  que juzgara todo con el tope de v1 lo condenaria)
#   tope_ajeno     un DISPARADO de v1 con ese mismo retraso, que la base acepto porque trae el tope
#                  de v2: ROJO por d, y la condenada es la de v1, no su gemela               d
#   huella_ajena   una fila de v1 con la huella de comun de v2                                a
#   release_135    el release de la 135 (191c2fb: solo v1 y cal-1) sobre una base donde v2 ya
#                  registro: ROJO por a (lo registrado no esta en el fichero)                 a
#
# Y el intento real de UPDATE/DELETE/TRUNCATE: lo rechaza el DISPARADOR (55000, su texto), y en una
# transaccion de solo lectura el error es otro (25006): el control distingue los dos.
# El check se corre de las tres formas (A56) y en los dos modos de SIGPIPE (A89).
set -u
AQUI=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P) || { echo "control: no resuelvo mi directorio"; exit 2; }
REPO=$(cd -- "$AQUI/../.." && pwd -P)
CHK="$AQUI/K105-el-registro-antes-del-resultado.sh"
SIEMBRA="$AQUI/K105-control-siembra.py"
PY="$REPO/.venv/bin/python"
H=/var/run/postgresql
[ -x "$CHK" ] && [ -r "$SIEMBRA" ] && [ -x "$PY" ] || { echo "control: falta $CHK, $SIEMBRA o $PY"; exit 2; }
CARGADO=1
PID=$$
BASE="k105_ctl_${PID}"
T=$(mktemp -d) || exit 2

limpia() {
  for db in $(psql -h "$H" -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'k105_ctl_${PID}%'"); do
    psql -h "$H" -d postgres -qc "DROP DATABASE IF EXISTS \"$db\" WITH (FORCE)" > /dev/null 2>&1
  done
  quedan=$(psql -h "$H" -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname LIKE 'k105_ctl_${PID}%'")
  echo "bases k105_ctl_${PID}* que quedan: $quedan"
  rm -rf "$T"
}
trap limpia EXIT
# Parado con una senal (TaskStop, Ctrl-C), el EXIT solo no corre y las bases se quedan: medido el
# 2026-10-03, ocho k105_ctl_* huerfanas tras parar una corrida a medias.
trap 'limpia; trap - EXIT; exit 143' INT TERM
[ "$CARGADO" = "1" ] || exit 2

pasan=0; total=0; fallan=""
comprueba() {  # nombre condicion(0/1) detalle
  total=$((total + 1))
  if [ "$2" = "0" ]; then pasan=$((pasan + 1)); printf '  PASA  %-26s %s\n' "$1" "$3"
  else fallan="$fallan $1"; printf '  FALLA %-26s %s\n' "$1" "$3"; fi
}
corre() {  # base release [extra env...] -> rc, salida en $T/salida
  local db="$1" rel="$2"; shift 2
  env K105_SUJETO=local K105_BASE="postgresql:///$db?host=$H" K105_RELEASE="$rel" \
    K105_RETENCION_DIAS=90 K105_REPO="$REPO" "$@" timeout -k 5 300 bash "$CHK" > "$T/salida" 2>&1
  echo $?
}
primera() { head -1 "$T/salida" | cut -c1-110; }
brazo() { grep -E "^  $1 " "$T/salida" | head -1 | awk '{print $3}'; }
copia() { createdb -h "$H" -T "$BASE" "$1" > /dev/null 2>&1; }

echo "== base de control $BASE"
createdb -h "$H" "$BASE" || exit 2
psql -h "$H" -d "$BASE" -q -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" > /dev/null 2>&1 || { echo "schema.sql no aplica"; exit 2; }
"$PY" "$SIEMBRA" escenario "postgresql:///$BASE?host=$H" "$T/release" || { echo "la siembra fallo"; exit 2; }
cp -a "$T/release" "$T/release_limpio"

echo "== el gemelo correcto"
rc=$(corre "$BASE" "$T/release")
comprueba gemelo_verde "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo "== A89 · los dos modos de SIGPIPE, y A56 · las tres invocaciones del check"
for modo in --ignore-signal=PIPE --default-signal=PIPE; do
  env $modo K105_SUJETO=local K105_BASE="postgresql:///$BASE?host=$H" K105_RELEASE="$T/release" \
    K105_RETENCION_DIAS=90 K105_REPO="$REPO" bash "$CHK" > "$T/s" 2>&1
  rc=$?; comprueba "sigpipe$modo" "$([ "$rc" = 0 ] && head -1 "$T/s" | grep -q '^VERDE' && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/s" | cut -c1-60)"
done
for forma in absoluta relativa ajena; do
  case $forma in
    absoluta) (env K105_SUJETO=local K105_BASE="postgresql:///$BASE?host=$H" K105_RELEASE="$T/release" K105_RETENCION_DIAS=90 bash "$CHK" > "$T/s" 2>&1); rc=$? ;;
    relativa) (cd "$REPO" && env K105_SUJETO=local K105_BASE="postgresql:///$BASE?host=$H" K105_RELEASE="$T/release" K105_RETENCION_DIAS=90 bash harness/checks/K105-el-registro-antes-del-resultado.sh > "$T/s" 2>&1); rc=$? ;;
    ajena)    (cd /tmp && env K105_SUJETO=local K105_BASE="postgresql:///$BASE?host=$H" K105_RELEASE="$T/release" K105_RETENCION_DIAS=90 bash "$CHK" > "$T/s" 2>&1); rc=$? ;;
  esac
  comprueba "invocacion_$forma" "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(head -1 "$T/s" | cut -c1-60)"
done

echo "== el intento real: UPDATE, DELETE y TRUNCATE en la base desechable"
for sentencia in "UPDATE entrada_registro SET motivo = 'x'" "DELETE FROM entrada_registro" "TRUNCATE entrada_registro" \
                 "UPDATE entrada_reglamento SET bloque = 'x'" "DELETE FROM entrada_latido"; do
  err=$(psql -h "$H" -d "$BASE" -X -q -c "\\set VERBOSITY verbose" -c "$sentencia" 2>&1 >/dev/null)
  comprueba "rechaza: ${sentencia%% *} ${sentencia##* }" \
    "$(printf '%s' "$err" | grep -q '55000' && printf '%s' "$err" | grep -q 'append-only' && echo 0 || echo 1)" \
    "$(printf '%s' "$err" | grep -m1 ERROR | cut -c1-80)"
done
err=$(psql -h "$H" -d "$BASE" -X -q -c "\\set VERBOSITY verbose" -c "BEGIN READ ONLY" -c "UPDATE entrada_registro SET motivo = 'x'" 2>&1 >/dev/null)
comprueba "solo_lectura_es_otro_error" \
  "$(printf '%s' "$err" | grep -q '25006' && ! printf '%s' "$err" | grep -q 'append-only' && echo 0 || echo 1)" \
  "$(printf '%s' "$err" | grep -m1 ERROR | cut -c1-80)"

echo "== los plantados, cada uno en su copia"
for caso in sin_stop:c posterior:d sin_spot:c dos_vivos:e evento_ajeno:f; do
  nombre=${caso%%:*}; b=${caso##*:}
  copia "${BASE}_$nombre"
  "$PY" "$SIEMBRA" planta "$nombre" "postgresql:///${BASE}_$nombre?host=$H" | sed 's/^/    /'
  rc=$(corre "${BASE}_$nombre" "$T/release")
  comprueba "$nombre" "$([ "$rc" = 1 ] && [ "$(brazo "$b")" = ROJO ] && echo 0 || echo 1)" "rc=$rc brazo $b=$(brazo "$b") · $(primera)"
done
copia "${BASE}_disparador"
antes=$(psql -h "$H" -d "${BASE}_disparador" -Atc "SELECT tgenabled FROM pg_trigger WHERE tgname = 'entrada_registro_no_update_delete'")
psql -h "$H" -d "${BASE}_disparador" -qc "ALTER TABLE entrada_registro DISABLE TRIGGER entrada_registro_no_update_delete" > /dev/null
despues=$(psql -h "$H" -d "${BASE}_disparador" -Atc "SELECT tgenabled FROM pg_trigger WHERE tgname = 'entrada_registro_no_update_delete'")
echo "    plantado disparador: tgenabled $antes -> $despues"
rc=$(corre "${BASE}_disparador" "$T/release")
comprueba disparador "$([ "$rc" = 1 ] && [ "$(brazo b)" = ROJO ] && echo 0 || echo 1)" "rc=$rc brazo b=$(brazo b) · $(primera)"
cp -a "$T/release_limpio" "$T/release_evento"
"$PY" "$SIEMBRA" release_evento "$T/release_evento" | sed 's/^/    /'
rc=$(corre "$BASE" "$T/release_evento")
comprueba evento_atras "$([ "$rc" = 1 ] && [ "$(brazo f)" = ROJO ] && echo 0 || echo 1)" "rc=$rc brazo f=$(brazo f) · $(primera)"

echo "== vacio: cero DISPARADOS y SOMBRAS"
createdb -h "$H" "${BASE}_vacio" > /dev/null
psql -h "$H" -d "${BASE}_vacio" -q -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" > /dev/null 2>&1
"$PY" "$SIEMBRA" reglamento "postgresql:///${BASE}_vacio?host=$H" "$T/release" | sed 's/^/    /'
rc=$(corre "${BASE}_vacio" "$T/release")
comprueba vacio_no_medido "$([ "$rc" = 2 ] && primera | grep -q 'NO MEDIDO' && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo "== los BYTES de antes del registro"
# «main» se mueve: desde que la 135 se fusiono ya trae el registro, y este brazo dejo de medir lo
# que decia (el 2026-10-09 caian 2 brazos de 4 con los bytes de main@191c2fb). Los bytes de ANTES
# del registro son un commit fijo.
ANTES=82ae7e2
mkdir -p "$T/main"
git -C "$REPO" archive "$ANTES" sql/schema.sql config 2>/dev/null | tar -x -C "$T/main"
[ -s "$T/main/sql/schema.sql" ] || echo "    sin el commit $ANTES en este clon: los dos brazos siguientes no miden"
createdb -h "$H" "${BASE}_main" > /dev/null
psql -h "$H" -d "${BASE}_main" -q -f "$T/main/sql/schema.sql" > /dev/null 2>&1
rc=$(corre "${BASE}_main" "$T/main")
caen=$(grep -cE '^  [a-f] .* ROJO' "$T/salida")
cuales=$(grep -E '^  [a-f] .* ROJO' "$T/salida" | awk '{print $1}' | tr '\n' ' ')
comprueba antes_caen "$([ -s "$T/main/sql/schema.sql" ] && [ "$rc" = 1 ] && [ "$caen" -ge 4 ] && echo 0 || echo 1)" "rc=$rc · caen $caen: $cuales· $(primera)"
rc=$(corre "$BASE" "$T/main")
comprueba antes_release_sin_reglamento "$([ -s "$T/main/sql/schema.sql" ] && [ "$rc" = 1 ] && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo "== dos versiones a la vez: cada fila con el tope y las huellas de SU version"
copia "${BASE}_tope_gemelo"
"$PY" "$SIEMBRA" planta tope_gemelo "postgresql:///${BASE}_tope_gemelo?host=$H" | sed 's/^/    /'
rc=$(corre "${BASE}_tope_gemelo" "$T/release")
comprueba tope_gemelo "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc brazo d=$(brazo d) · $(primera)"
copia "${BASE}_tope_ajeno"
"$PY" "$SIEMBRA" planta tope_gemelo "postgresql:///${BASE}_tope_ajeno?host=$H" | sed 's/^/    /'
"$PY" "$SIEMBRA" planta tope_ajeno "postgresql:///${BASE}_tope_ajeno?host=$H" | sed 's/^/    /'
rc=$(corre "${BASE}_tope_ajeno" "$T/release")
de_v1=$(grep -c 'DISPARADO de v1 a .* sobre el tope de su version' "$T/salida")
de_v2=$(grep -c 'DISPARADO de v2 a .* sobre el tope de su version' "$T/salida")
comprueba tope_ajeno "$([ "$rc" = 1 ] && [ "$(brazo d)" = ROJO ] && [ "$de_v1" = 1 ] && [ "$de_v2" = 0 ] && echo 0 || echo 1)" \
  "rc=$rc brazo d=$(brazo d) · condenadas por su tope: v1 $de_v1, v2 $de_v2 · $(primera)"
copia "${BASE}_huella_ajena"
"$PY" "$SIEMBRA" planta huella_ajena "postgresql:///${BASE}_huella_ajena?host=$H" | sed 's/^/    /'
rc=$(corre "${BASE}_huella_ajena" "$T/release")
comprueba huella_ajena "$([ "$rc" = 1 ] && [ "$(brazo a)" = ROJO ] && grep -q 'huella_comun no es la de v1' "$T/salida" && echo 0 || echo 1)" "rc=$rc brazo a=$(brazo a) · $(primera)"
# el release de la 135 (solo v1 y cal-1) sobre una base donde el reglamento de ESTE arbol ya se
# registro (v2 y cal-2 incluidos): una vuelta atras se VE, y se ve por lo que es
LA135=191c2fb
mkdir -p "$T/la135"
git -C "$REPO" archive "$LA135" config 2>/dev/null | tar -x -C "$T/la135"
createdb -h "$H" "${BASE}_la135" > /dev/null
psql -h "$H" -d "${BASE}_la135" -q -v ON_ERROR_STOP=1 -f "$REPO/sql/schema.sql" > /dev/null 2>&1
"$PY" "$SIEMBRA" reglamento "postgresql:///${BASE}_la135?host=$H" "$REPO" | sed 's/^/    /'
rc=$(corre "${BASE}_la135" "$T/la135")
comprueba release_135 "$([ -s "$T/la135/config/entradas/reglamento.json" ] && [ "$rc" = 1 ] && [ "$(brazo a)" = ROJO ] && grep -q 'v2\.[A-Za-z0-9]* registrado y AUSENTE del fichero del release' "$T/salida" && echo 0 || echo 1)" "rc=$rc brazo a=$(brazo a) · $(primera)"

echo "== restaurado: la base de control sigue saliendo VERDE"
rc=$(corre "$BASE" "$T/release")
comprueba restaurado "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo
echo "$pasan de $total pasan · fallan:${fallan:- ninguno}"
[ "$pasan" = "$total" ]
