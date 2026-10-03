#!/bin/bash
# K105-control · UN PLANTADO QUE TIENE QUE FALLAR POR CADA COSA QUE K105 PROMETE (campana 135, C5)
#
# Todo en bases DESECHABLES k105_ctl_<pid>* que se borran al salir (y se comprueba que se borraron).
# Base: schema.sql de este arbol, reglamento de control registrado, BTC y ETH sembrados en la vela
# T actual y evaluados con el generador REAL: un DISPARADO y una SOMBRA «solo perpetuo». Su gemelo
# tiene que salir VERDE; cada plantado, en una COPIA de la base, tiene que salir ROJO por su brazo:
#
#   sin_stop       un DISPARADO sin stop                              c
#   posterior      un insumo con hora posterior a su registro         d
#   sin_spot       un DISPARADO sin la pata spot completa (MC12)      c
#   dos_vivos      dos DISPARADOS vivos en zonas que se solapan       e
#   disparador     el BEFORE UPDATE OR DELETE desactivado             b
#   evento_ajeno   una SOMBRA de evento con un calendario que no es el de su registro   f
#   evento_atras   un evento con hora anterior a la revision que lo trae (release)      f
#   vacio          cero DISPARADOS y SOMBRAS: NO MEDIDO, nunca VERDE
#   main           los BYTES de main (esquema y release sin registro): sus brazos CAEN
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

echo "== los BYTES de main"
mkdir -p "$T/main"
git -C "$REPO" archive main sql/schema.sql config 2>/dev/null | tar -x -C "$T/main"
createdb -h "$H" "${BASE}_main" > /dev/null
psql -h "$H" -d "${BASE}_main" -q -f "$T/main/sql/schema.sql" > /dev/null 2>&1
rc=$(corre "${BASE}_main" "$T/main")
caen=$(grep -cE '^  [a-f] .* ROJO' "$T/salida")
cuales=$(grep -E '^  [a-f] .* ROJO' "$T/salida" | awk '{print $1}' | tr '\n' ' ')
comprueba main_caen "$([ "$rc" = 1 ] && [ "$caen" -ge 4 ] && echo 0 || echo 1)" "rc=$rc · caen $caen: $cuales· $(primera)"
rc=$(corre "$BASE" "$T/main")
comprueba main_release_sin_reglamento "$([ "$rc" = 1 ] && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo "== restaurado: la base de control sigue saliendo VERDE"
rc=$(corre "$BASE" "$T/release")
comprueba restaurado "$([ "$rc" = 0 ] && echo 0 || echo 1)" "rc=$rc · $(primera)"

echo
echo "$pasan de $total pasan · fallan:${fallan:- ninguno}"
[ "$pasan" = "$total" ]
