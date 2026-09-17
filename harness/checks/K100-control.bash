#!/bin/bash
# K100-control · K100 nace VERDE, asi que sin este fichero no probaria nada.
#
#     bash harness/checks/K100-control.bash
#
# LOS TRES ESTADOS QUE EL ENCARGO PIDE, y uno mas que sostiene a los otros:
#   W1  otra huella en 140 (doble del canal)        -> ROJO, y con el diff
#   W2  el REPO cambiado, 140 quieto                -> ROJO tambien: no importa quien se movio
#   W3  140 mudo                                    -> NO MEDIDO, y no VERDE
#   W4  falta la copia del repo                     -> NO MEDIDO
#   W5  140 contesta VACIO                          -> NO MEDIDO: un fichero vacio y un canal
#                                                      mudo se parecen demasiado
#   W0  EL CONTROL POSITIVO: con los dos lados iguales, VERDE. Sin verlo disparar, «K100 esta
#       rojo» no distingue un defecto de un check que no sabe decir que si.
#
# NO SE TOCA 140. El lado remoto se inyecta con `K100_REMOTO`, y el check DICE en su linea que
# lo hizo: esa marca es lo que impide que la puerta de pruebas se convierta en la puerta por la
# que alguien fuerza un verde.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K100-el-wrapper-que-nadie-mira.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
LOCAL="$ORIG/deploy/140/deploy-coinalyze"
[ -r "$LOCAL" ] || { echo "NO MEDIDO: no encuentro la copia del repo en $LOCAL"; exit 2; }

DIR=$(mktemp -d) || exit 2
trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-58s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-58s\n' "$1"; fi; }

cp "$LOCAL" "$DIR/igual"
sed '1a # LINEA PLANTADA POR EL CONTROL' "$LOCAL" > "$DIR/distinto"
: > "$DIR/vacio"

echo "K100-control · sujeto: $CHK"
echo

echo "W0 · CONTROL POSITIVO · los dos lados iguales: VERDE"
out=$(REPO="$ORIG" K100_REMOTO="$DIR/igual" bash "$CHK" 2>&1); rc=$?
comprueba "W0a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "W0b y AVISA de que el remoto venia inyectado" \
  "$(printf '%s' "$out" | grep -q 'REMOTO INYECTADO' && echo si || echo no)"

echo
echo "W1 · otra huella en 140: ROJO, y dice QUE cambio"
out=$(REPO="$ORIG" K100_REMOTO="$DIR/distinto" bash "$CHK" 2>&1); rc=$?
comprueba "W1a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "W1b da las DOS huellas y las dos cuentas de lineas" \
  "$(printf '%s' "$out" | grep -qE 'md5 [0-9a-f]{32}.*md5 [0-9a-f]{32}' && echo si || echo no)"
comprueba "W1c y trae el diff, no solo «cambio algo»" \
  "$(printf '%s' "$out" | grep -q 'LINEA PLANTADA POR EL CONTROL' && echo si || echo no)"

echo
echo "W2 · el REPO cambiado y 140 quieto: ROJO igual. No importa quien se movio"
cp "$LOCAL" "$DIR/repo-mov"; sed -i '1a # EL REPO SE MOVIO' "$DIR/repo-mov"
out=$(REPO="$ORIG" K100_LOCAL="$DIR/repo-mov" K100_REMOTO="$DIR/igual" bash "$CHK" 2>&1); rc=$?
comprueba "W2a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "W2b y dice que no sabe cual de los dos se movio" \
  "$(printf '%s' "$out" | grep -q 'este check no sabe cual' && echo si || echo no)"

echo
echo "W3 · 140 mudo: NO MEDIDO, y no VERDE"
mkdir -p "$DIR/arnes/bin"
printf '%s\n' ". /srv/coinanalyze/harness/env" > "$DIR/arnes/env"
printf '%s\n' '#!/bin/bash' 'exit 3' > "$DIR/arnes/bin/prod"
chmod +x "$DIR/arnes/bin/prod"
sed "s#^B=/srv/coinanalyze/harness\$#B=$DIR/arnes#" "$CHK" > "$DIR/K100.sh"
if cmp -s "$CHK" "$DIR/K100.sh"; then echo "NO MEDIDO: el sed no mordio"; exit 2; fi
out=$(REPO="$ORIG" bash "$DIR/K100.sh" 2>&1); rc=$?
comprueba "W3a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "W3b y dice que no afirma nada sobre el wrapper" \
  "$(printf '%s' "$out" | grep -q 'ni que coincida ni que no' && echo si || echo no)"

echo
echo "W4 · falta la copia del repo: NO MEDIDO"
out=$(REPO="$ORIG" K100_LOCAL="$DIR/no-existe" K100_REMOTO="$DIR/igual" bash "$CHK" 2>&1); rc=$?
comprueba "W4a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "W4b y dice que sin elegible no hay con que comparar" \
  "$(printf '%s' "$out" | grep -q 'coincide con nada' && echo si || echo no)"

echo
echo "W5 · 140 contesta VACIO: NO MEDIDO, no VERDE por parecido"
out=$(REPO="$ORIG" K100_REMOTO="$DIR/vacio" bash "$CHK" 2>&1); rc=$?
comprueba "W5a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"

echo
echo "W6 · LO QUE SE COPIO NO LLEVA SECRETOS, y se vuelve a medir aqui"
lit=$(grep -cEi '(pass|secret|token|key)[a-z_]*=[^$"]{6,}' "$LOCAL" || true)
blob=$(grep -cE '[A-Za-z0-9+/]{32,}={0,2}' "$LOCAL" || true)
comprueba "W6a cero asignaciones con valor literal ($lit)" "$([ "$lit" = 0 ] && echo si || echo no)"
comprueba "W6b cero blobs de alta entropia ($blob)" "$([ "$blob" = 0 ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
