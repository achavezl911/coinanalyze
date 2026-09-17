#!/bin/bash
# barre-bases-ci-control · ¿recoge lo de las corridas anteriores SIN tocar lo que no es suyo,
#                          y SIN tumbar la corrida cuando una base no se deja borrar?
#
#     bash harness/checks/barre-bases-ci-control.bash
#
# POR QUE ESTE CONTROL. Un barrido de bases es de los pocos sitios del arnes donde equivocarse
# BORRA algo. Las dos direcciones importan igual: si no recoge, 143 se llena -siete bases
# muertas el 2026-09-16-; si recoge de mas, se lleva por delante `coinalyze_espejo` o
# `coinalyze_k01b`. Por eso el brazo N1 -lo que NO es de CI sobrevive- vale tanto como el P1.
#
# LO QUE ESTE CONTROL NO PODIA CAZAR, Y POR ESO SE AMPLIA (2026-09-17, COLA 125). Daba 8 de 8
# mientras el barrido tumbaba el CI entero en CADA corrida del PR #191: fabricaba TODAS sus
# bases como el usuario que lo corre, asi que EL DUENO NUNCA VARIABA -y el dueno era lo unico
# que decidia-. Un control cuyos sujetos son todos iguales en la variable que importa no mide
# esa variable. Los brazos C, D y E existen para eso.
#
# NO BARRE LAS DE VERDAD. Se ejercitan LOS MISMOS BYTES que corre CI -`harness/bin/barre-bases-ci`-
# con `CI_DB_PREFIX` apuntando a un prefijo propio, y el propio script avisa en su salida de que
# ese prefijo no es el de produccion. Las `ci_*` reales las recoge CI en su corrida, que es la
# prueba de verdad; aqui se prueba el CRITERIO. Las dos `ci_prosa_*` de root NO se tocan: no son
# nuestras, y borrarlas es de Alejandro.
#
# EL CONTROL POSITIVO NO VA DENTRO, VA CON SU COMANDO -porque lo que hay que ver disparar son
# LOS BYTES VIEJOS, no una imitacion suya:
#
#     mkdir -p /tmp/viejo/harness/bin
#     git show 3f3b23b:harness/bin/barre-bases-ci > /tmp/viejo/harness/bin/barre-bases-ci
#     REPO=/tmp/viejo bash harness/checks/barre-bases-ci-control.bash
#
# Medido el 2026-09-17: 15 de 22 · FALLAN C1 C3 C5 C7 C8 D2 E2, y el bloque B sigue en 8 de 8
# con el defecto delante, que era justo la ceguera.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
BARRE="$ORIG/harness/bin/barre-bases-ci"
[ -r "$BARRE" ] || { echo "NO MEDIDO: no encuentro $BARRE"; exit 2; }
command -v psql >/dev/null || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }
DROPDB_REAL=$(command -v dropdb) || { echo "NO MEDIDO: no hay dropdb en esta maquina"; exit 2; }

H=--host=/var/run/postgresql
P="cizz${$}_"                     # prefijo propio: NUNCA casa con `ci_`
MIA="${P}mia"
VIEJA1="${P}vieja1"
VIEJA2="${P}vieja2"
AJENA="zznoesci_${$}"             # no empieza por el prefijo: tiene que sobrevivir
# Cada bloque lleva SU PROPIO prefijo: si compartieran uno, lo que un bloque deja en pie
# -la base de «esta corrida»- aparecerian en el censo del siguiente y le cambiarian las cuentas.
PC="cizz${$}c_"; C_MIA="${PC}mia"; C_V1="${PC}v1"; C_V2="${PC}v2"; C_AJENA="${PC}deotro"
PE="cizz${$}e_"; E_RARA="${PE}rara"
YO=$(id -un)
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-64s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-64s\n' "$1"; fi; }
existe() { psql $H -d postgres -X -A -t \
             -c "SELECT 1 FROM pg_database WHERE datname='$1'" 2>/dev/null | grep -q 1; }
DIR=$(mktemp -d) || exit 2
limpia() { for d in "$MIA" "$VIEJA1" "$VIEJA2" "$AJENA" "$C_MIA" "$C_V1" "$C_V2" "$C_AJENA" "$E_RARA"; do
             dropdb $H --if-exists "$d" >/dev/null 2>&1; done
           rm -rf "$DIR"; }
trap limpia EXIT

for d in "$MIA" "$VIEJA1" "$VIEJA2" "$AJENA"; do
  createdb $H "$d" || { echo "NO MEDIDO: no pude crear $d"; exit 2; }
done
echo "barre-bases-ci-control · sujeto: $BARRE · prefijo de prueba: $P · corro como: $YO"
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

echo
echo "C · UNA BASE DEL PREFIJO QUE NO SE PUEDE BORRAR NO MATA LA CORRIDA"
# ESTE ES EL BLOQUE QUE FALTABA. Se intenta REPRODUCIRLO CON UN DUENO DE VERDAD: `github-runner`
# es el usuario con el que corre CI y tiene rol propio en postgres por peer auth, asi que
# bajando de privilegio con `su` el `dropdb` falla EXACTAMENTE como fallo en la corrida real.
# Si no se puede bajar -no soy root, no existe el usuario, no contesta su psql- se SIMULA con
# un `dropdb` de mentira en el PATH y SE DICE EN LA SALIDA. No hay tercera via: `devops` no
# puede crear roles (rolcreaterole=f, medido el 2026-09-17), asi que no me puedo fabricar un
# dueno a medida desde dentro de postgres.
OTRO=github-runner
MODO=simulado
if [ "$(id -u)" = 0 ] && id "$OTRO" >/dev/null 2>&1 \
   && su -s /bin/bash "$OTRO" -c "cd /tmp && psql $H -d postgres -X -A -t -c 'SELECT 1'" >/dev/null 2>&1 \
   && su -s /bin/bash "$OTRO" -c "test -r $BARRE" ; then
  MODO=real
fi

if [ "$MODO" = real ]; then
  # Las tres que SI son suyas se crean A NOMBRE DE $OTRO; la cuarta se queda a mi nombre.
  for d in "$C_MIA" "$C_V1" "$C_V2"; do
    createdb $H -O "$OTRO" "$d" || { echo "NO MEDIDO: no pude crear $d a nombre de $OTRO"; exit 2; }
  done
  createdb $H "$C_AJENA" || { echo "NO MEDIDO: no pude crear $C_AJENA"; exit 2; }
  echo "   [REPRODUCIDO CON UN DUENO DE VERDAD] barre $OTRO; $C_AJENA es de $YO"
  outc=$(su -s /bin/bash "$OTRO" -c \
         "cd /tmp && CI_DB_PREFIX='$PC' bash '$BARRE' '$C_MIA'" 2>&1); rcc=$?
else
  for d in "$C_MIA" "$C_V1" "$C_V2" "$C_AJENA"; do
    createdb $H "$d" || { echo "NO MEDIDO: no pude crear $d"; exit 2; }
  done
  mkdir -p "$DIR/shimc"
  { printf '#!/bin/bash\n'
    printf 'for a in "$@"; do [ "$a" = "%s" ] && {\n' "$C_AJENA"
    printf '  echo "dropdb: error: database removal failed: ERROR:  must be owner of database %s" >&2\n' "$C_AJENA"
    printf '  exit 1; }\ndone\nexec %s "$@"\n' "$DROPDB_REAL"
  } > "$DIR/shimc/dropdb"; chmod +x "$DIR/shimc/dropdb"
  echo "   [SIMULADO Y DECLARADO] no puedo bajar de privilegio a $OTRO (soy $YO), asi que el"
  echo "   «no soy el dueno» lo da un dropdb de mentira en el PATH con el mensaje literal del"
  echo "   servidor. No es una reproduccion: es una imitacion, y queda dicho."
  outc=$(PATH="$DIR/shimc:$PATH" CI_DB_PREFIX="$PC" bash "$BARRE" "$C_MIA" 2>&1); rcc=$?
fi
printf '%s\n' "$outc" | sed 's/^/      /'
echo

comprueba "C1 el paso NO muere: sale 0 con una base que no puede borrar (rc=$rcc)" \
  "$([ "$rcc" = 0 ] && echo si || echo no)"
comprueba "C2 y esa base SIGUE EXISTIENDO: no la fuerza ($C_AJENA)" \
  "$(existe "$C_AJENA" && echo si || echo no)"
comprueba "C3 la NOMBRA, y dice de quien es (dueno: $YO)" \
  "$(printf '%s' "$outc" | grep -q "$C_AJENA · dueno: $YO" && echo si || echo no)"
comprueba "C4 y da el motivo que dio el servidor (must be owner)" \
  "$(printf '%s' "$outc" | grep -q 'must be owner' && echo si || echo no)"
comprueba "C5 y SIGUE BARRIENDO las que si son suyas ($C_V1 y $C_V2)" \
  "$( { existe "$C_V1" || existe "$C_V2"; } && echo no || echo si)"
comprueba "C6 la de esta corrida sigue en pie ($C_MIA)" \
  "$(existe "$C_MIA" && echo si || echo no)"
comprueba "C7 el resumen dice cuantas barrio Y cuantas no pudo" \
  "$(printf '%s' "$outc" | grep -q 'recogidas: 2 · no se pudo con: 1' && echo si || echo no)"
comprueba "C8 y al final repite POR QUE no pudo" \
  "$(printf '%s' "$outc" | grep -q 'por que no se pudo' && echo si || echo no)"

echo
echo "D · EL CANAL CAIDO SIGUE SIENDO UN FALLO DEL PASO"
# AQUI NO SE SIMULA NADA: se apunta el canal a un directorio de socket que no existe, que es
# lo que ve un paso cuando postgres no esta levantado. Si esto saliera 0 -«0 recogidas, todo
# en orden»-, el barrido dejaria de barrer el dia que el servidor se cayera y nadie lo sabria.
outd=$(CI_DB_HOST="--host=$DIR/no-hay-socket" CI_DB_PREFIX="$P" bash "$BARRE" "$MIA" 2>&1); rcd=$?
printf '%s\n' "$outd" | sed 's/^/      /'
comprueba "D1 el paso FALLA (rc=$rcd, distinto de 0)" "$([ "$rcd" != 0 ] && echo si || echo no)"
comprueba "D2 y lo dice: FALLO DEL PASO, el canal no contesta" \
  "$(printf '%s' "$outd" | grep -q 'FALLO DEL PASO' && echo si || echo no)"
comprueba "D3 y NO se apunta ningun barrido" \
  "$(printf '%s' "$outd" | grep -q 'recogidas:' && echo no || echo si)"

echo
echo "E · UN ERROR QUE NO ESTA EN LA LISTA BLANCA TAMPOCO SE TRAGA"
# SIMULADO Y DECLARADO: no puedo tirar postgres en mitad del barrido, asi que un `dropdb` de
# mentira devuelve el mensaje de conexion perdida. Es la otra direccion de C: si la tolerancia
# fuera «todo lo que falle, se nombra y se sigue», el barrido dejaria de barrer EN SILENCIO,
# que es peor que el `set -e` de ayer.
createdb $H "$E_RARA" || { echo "NO MEDIDO: no pude crear $E_RARA"; exit 2; }
mkdir -p "$DIR/shime"
{ printf '#!/bin/bash\n'
  printf 'for a in "$@"; do [ "$a" = "%s" ] && {\n' "$E_RARA"
  printf '  echo "dropdb: error: connection to server on socket \\"/var/run/postgresql/.s.PGSQL.5432\\" failed: No such file or directory" >&2\n'
  printf '  exit 1; }\ndone\nexec %s "$@"\n' "$DROPDB_REAL"
} > "$DIR/shime/dropdb"; chmod +x "$DIR/shime/dropdb"
oute=$(PATH="$DIR/shime:$PATH" CI_DB_PREFIX="$PE" bash "$BARRE" 2>&1); rce=$?
printf '%s\n' "$oute" | sed 's/^/      /'
comprueba "E1 el paso FALLA (rc=$rce, distinto de 0)" "$([ "$rce" != 0 ] && echo si || echo no)"
comprueba "E2 y dice que ese motivo NO esta en la lista blanca" \
  "$(printf '%s' "$oute" | grep -q 'lista' && echo si || echo no)"
comprueba "E3 y la base sigue ahi: no se la lleva por delante ($E_RARA)" \
  "$(existe "$E_RARA" && echo si || echo no)"

# EL CONTROL DEL CONTROL · las bases REALES de CI siguen ahi: este control no las toca.
echo
echo "   bases \`ci_*\` REALES en 143 ahora mismo, con su dueno (este control NO las toca;"
echo "   las dos \`ci_prosa_*\` son de root y borrarlas es de Alejandro):"
psql $H -d postgres -X -A -t -F'|' \
  -c "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE datname LIKE 'ci\\_%' ORDER BY 1" \
  2>/dev/null | sed 's/^/      /'

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
