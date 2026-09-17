#!/bin/bash
# barre-bases-ci-control · ¿recoge lo de las corridas anteriores SIN tocar lo que no es suyo?
#
#     bash harness/checks/barre-bases-ci-control.bash
#
# POR QUE ESTE CONTROL. Un barrido de bases es de los pocos sitios del arnes donde equivocarse
# BORRA algo. Las dos direcciones importan igual: si no recoge, 143 se llena -siete bases
# muertas el 2026-09-16-; si recoge de mas, se lleva por delante `coinalyze_espejo` o
# `coinalyze_k01b`. Por eso el brazo N1 -lo que NO es de CI sobrevive- vale tanto como el P1.
#
# NO BARRE LAS DE VERDAD. Se ejercitan LOS MISMOS BYTES que corre CI -`harness/bin/barre-bases-ci`-
# con `CI_DB_PREFIX` apuntando a un prefijo propio, y el propio script avisa en su salida de que
# ese prefijo no es el de produccion. Las `ci_*` reales las recoge CI en su corrida, que es la
# prueba de verdad; aqui se prueba el CRITERIO.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
BARRE="$ORIG/harness/bin/barre-bases-ci"
[ -r "$BARRE" ] || { echo "NO MEDIDO: no encuentro $BARRE"; exit 2; }
command -v psql >/dev/null || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }

P="cizz${$}_"                     # prefijo propio: NUNCA casa con `ci_`
MIA="${P}mia"
VIEJA1="${P}vieja1"
VIEJA2="${P}vieja2"
AJENA="zznoesci_${$}"             # no empieza por el prefijo: tiene que sobrevivir
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-58s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-58s\n' "$1"; fi; }
existe() { psql --host=/var/run/postgresql -d postgres -X -A -t \
             -c "SELECT 1 FROM pg_database WHERE datname='$1'" 2>/dev/null | grep -q 1; }
limpia() { for d in "$MIA" "$VIEJA1" "$VIEJA2" "$AJENA"; do
             dropdb --host=/var/run/postgresql --if-exists "$d" >/dev/null 2>&1; done; }
trap limpia EXIT

for d in "$MIA" "$VIEJA1" "$VIEJA2" "$AJENA"; do
  createdb --host=/var/run/postgresql "$d" || { echo "NO MEDIDO: no pude crear $d"; exit 2; }
done
echo "barre-bases-ci-control · sujeto: $BARRE · prefijo de prueba: $P"
echo "   plantadas: $MIA (la de esta corrida) · $VIEJA1 · $VIEJA2 · $AJENA (no es de CI)"
echo

out=$(CI_DB_PREFIX="$P" bash "$BARRE" "$MIA" 2>&1); rc=$?
printf '%s\n' "$out" | sed 's/^/      /'
echo

comprueba "B0 el script corrio (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "B1 avisa de que el prefijo NO es el de produccion" \
  "$(printf '%s' "$out" | grep -q 'PREFIJO CAMBIADO' && echo si || echo no)"
comprueba "B2 la base de OTRA corrida desaparece ($VIEJA1)" \
  "$(existe "$VIEJA1" && echo no || echo si)"
comprueba "B3 y la segunda tambien ($VIEJA2)" \
  "$(existe "$VIEJA2" && echo no || echo si)"
comprueba "B4 la de ESTA corrida NO se toca ($MIA)" \
  "$(existe "$MIA" && echo si || echo no)"
comprueba "B5 la que NO es de CI SOBREVIVE ($AJENA)" \
  "$(existe "$AJENA" && echo si || echo no)"
comprueba "B6 y lo dice: la nombra como intacta" \
  "$(printf '%s' "$out" | grep -q "intacta: $AJENA" && echo si || echo no)"
comprueba "B7 publica CUANTAS recogio, no solo que recogio" \
  "$(printf '%s' "$out" | grep -q 'recogidas: 2' && echo si || echo no)"

# EL CONTROL DEL CONTROL · las bases REALES de CI siguen ahi: este control no las toca.
echo
reales=$(psql --host=/var/run/postgresql -d postgres -X -A -t \
  -c "SELECT count(*) FROM pg_database WHERE datname LIKE 'ci\\_%'" 2>/dev/null)
echo "   bases \`ci_*\` REALES en 143 ahora mismo: ${reales:-?} (este control NO las toca;"
echo "   las recoge CI en su corrida, y esa corrida es la prueba)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
