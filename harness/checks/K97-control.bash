#!/usr/bin/env bash
# K97-control · ¿el censo CAZA a un check que vota, o solo sabe contar?
#
# K97 es un check cuyo sujeto son los demas checks, asi que tiene el modo de fallo de todos los
# instrumentos que clasifican: **marcar a todos o no marcar a ninguno**. Los dos son la misma
# averia y ninguno se nota mirando su salida. Aqui se le da un directorio de checks DE MENTIRA,
# con casos de respuesta conocida, y se exige el veredicto de cada uno.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto de este fichero es el
# criterio, no produccion. Corre sin red, sin ssh y sin base de datos.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K97-el-verde-sin-sujeto.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K97_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0; nocorren=""; nocorren_criticos=""

# EL TOTAL DE BRAZOS SE DECLARA POR ADELANTADO, y esto es el arreglo de un defecto medido por el
# operador: el titular salia de `pasan+fallos`, o sea SOLO de los que corrieron. Cuando el brazo
# de regresion no podia correr -por ejemplo en un arbol sin `.git`- el denominador encogia con el
# y la ultima linea decia **«15 de 15 pasan · 0 fallan»** sin mencionar que habia perdido tres.
# Y `bin/_corta` trunca a 8000 B, asi que ese titular es justo lo que sobrevive a un corte: la
# unica linea que alguien lee podia ser la que mas mentia.
# N1 N1b · P1 P2 P3 · C1 · S1 S2 · V1 V1b · D1 D2 · R1 R1b R2 · G1..G8 · F1 F2 F3
TOTAL_BRAZOS=26
# LOS CRITICOS son los que, si no corren, dejan al control sin poder AFIRMAR nada. Hoy es solo el
# de regresion: es el que prueba que el verde de K97 se debe a los arreglos y no a que el
# instrumento haya dejado de mirar. Sin el, «pasan» no significa nada y el veredicto es NOMED.
BRAZOS_CRITICOS="R1 R1b R2"

nocorre() {  # $1 = etiqueta del brazo   $2 = motivo
  nocorren="$nocorren $1"
  case " $BRAZOS_CRITICOS " in *" $1 "*) nocorren_criticos="$nocorren_criticos $1" ;; esac
  printf '  [....] %-56s %s\n' "$1" "$2"
}

caso() {  # <nombre> <rc esperado> <patron> [VAR=val ...]
  local nombre="$1" esperado="$2" patron="$3"; shift 3
  local out rc ok=1
  out=$(env "$@" bash "$CHK" 2>&1); rc=$?
  [ "$rc" = "$esperado" ] || ok=0
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-56s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-56s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | tail -3 | tr '\n' ' ' | cut -c1-160)"
  fi
}

# --- LOS SUJETOS DE MENTIRA ----------------------------------------------------------------
# Cada uno lleva `DIAS=7` para que case el criterio de ventana movil, y `B=/srv/coinanalyze/harness`
# para que K97 le reescriba el canal. Son los cuatro comportamientos que hay que distinguir.
mk() { mkdir -p "$1"; }

# VOTA · ignora lo que le devuelva el canal y dice VERDE. Es la enfermedad.
sujeto_vota() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
filas=$("$B/bin/prodsql" "SELECT ts FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null)
echo "VERDE: todo en orden"
exit 0
EOF
chmod 755 "$1"; }

# DECLARA · cuenta su poblacion y dice NO MEDIDO si esta vacia. Es lo sano.
sujeto_declara() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
filas=$("$B/bin/prodsql" "SELECT ts FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null)
n=$(printf '%s' "$filas" | grep -c . || true)
[ "$n" -gt 0 ] || { echo "NO MEDIDO: cero filas elegibles, no hay sujeto"; exit 2; }
echo "VERDE: $n filas y ninguna mal"
exit 0
EOF
chmod 755 "$1"; }

# CUENTA · su consulta es un count(*), asi que con la base vacia recibe la linea '0'. El doble
# MUDO no lo pilla -para el, cero lineas es "no contesto"- y hace falta el doble CERO.
sujeto_cuenta() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
malas=$("$B/bin/prodsql" "SELECT count(*) FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null | tr -d ' ')
[ "${malas:-x}" = 0 ] && { echo "VERDE: ninguna mal"; exit 0; }
echo "ROJO: $malas mal"; exit 1
EOF
chmod 755 "$1"; }

# SONDA · abre con una sonda de vida SIN FROM y despues vota. Es el caso que la primera version
# del doble dejaba escapar: la sonda volvia vacia, el check decia "canal caido" y se apuntaba
# SANO por la razon equivocada. Asi salia sano K06-visibilidad, que el operador tenia medido
# como enfermo. El doble tiene que contestar la sonda -vaciar tablas no tumba el canal-.
sujeto_sonda() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
vivo=$("$B/bin/prodsql" "SELECT 'canal_ok'" 2>/dev/null | tr -d ' ' | head -1)
[ "$vivo" = "canal_ok" ] || { echo "NO MEDIDO: prodsql no responde"; exit 2; }
viejas=$("$B/bin/prodsql" "SELECT 1 FROM inventada HAVING max(ts) < now() - interval '6 hours'" 2>/dev/null)
[ -z "$viejas" ] || { echo "paradas: $viejas"; exit 1; }
echo "las tablas escriben dentro de 6 h"
exit 0
EOF
chmod 755 "$1"; }

# SEPARA · mira el rc del canal ANTES de mirar las filas, asi que sabe decir cual de las dos
# cosas le paso. Es lo que hace K06-visibilidad desde ayer y lo que NO hace K04-huecos.
sujeto_separa() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
filas=$("$B/bin/prodsql" "SELECT ts FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null); rc=$?
[ "$rc" = 0 ] || { echo "NO MEDIDO: el canal no responde (rc=$rc)"; exit 2; }
n=$(printf '%s' "$filas" | grep -c . || true)
[ "$n" -gt 0 ] || { echo "NO MEDIDO: el canal contesto y no habia ni una fila elegible"; exit 2; }
echo "VERDE: $n filas y ninguna mal"
exit 0
EOF
chmod 755 "$1"; }

# SOLO CON CERO · cuenta sus filas con un `count(*)`, asi que ante el doble MUDO recibe VACIO
# -que para el es "no contesto"- y ante el CERO recibe la linea `0` y sabe decir que no habia
# nada. **Solo distingue con UNO de los dos dobles.** Es exactamente el caso que la particion
# anterior perdia: comparaba unicamente contra MUDO y lo mandaba a PRESTADO sin serlo.
sujeto_solo_cero() { cat > "$1" <<'EOF'
#!/bin/bash
DIAS=7
B=/srv/coinanalyze/harness
n=$("$B/bin/prodsql" "SELECT count(*) FROM inventada WHERE ts > now() - interval '7 days'" 2>/dev/null | tr -d ' ')
case "${n:-}" in
  '')  echo "NO MEDIDO: la consulta no devolvio un numero"; exit 2 ;;
  0)   echo "NO MEDIDO: el canal contesto y no habia ni una fila"; exit 2 ;;
esac
echo "VERDE: $n filas y ninguna mal"
exit 0
EOF
chmod 755 "$1"; }

# SIN VENTANA · no tiene ventana movil -ni DIAS=, ni --since, ni now()-, asi que NO es sujeto
# de K97 aunque vote. Es el brazo que delimita a quien se juzga.
sujeto_sin_ventana() { cat > "$1" <<'EOF'
#!/bin/bash
B=/srv/coinanalyze/harness
echo "VERDE: no miro ninguna ventana"
exit 0
EOF
chmod 755 "$1"; }

echo "K97-control · sujeto: $CHK"
echo

# El control POSITIVO de K97 exige que existan K92 y K52 en el directorio que juzga. En los
# arboles de mentira se enlazan los de verdad: son sujetos legitimos y ademas son la prueba de
# que el instrumento no marca a todo el mundo.
puebla() {  # $1 = dir
  mk "$1"
  ln -sf "$ORIG/harness/checks/K92-el-minuto-que-miente.sh" "$1/K92-el-minuto-que-miente.sh"
  ln -sf "$ORIG/harness/checks/K52-el-minuto-corto.sh"      "$1/K52-el-minuto-corto.sh"
}

echo "NEGATIVO · un directorio de checks SANOS no puede enrojecer"
D1="$DIR/sano"; puebla "$D1"
sujeto_declara "$D1/Z01-declara.sh"
caso "N1 solo checks que declaran su vacio: VERDE" 0 "VERDE: ninguno de los" "K97_CHECKS=$D1"
caso "N1b y el control positivo pasa 2 de 2"       0 "control POSITIVO: 2 de 2" "K97_CHECKS=$D1"

echo
echo "POSITIVO · el check que vota"
D2="$DIR/vota"; puebla "$D2"
sujeto_declara "$D2/Z01-declara.sh"
sujeto_vota    "$D2/Z02-vota.sh"
caso "P1 un check que vota VERDE sobre cero: ROJO" 1 "salen VERDE con la poblacion vacia" "K97_CHECKS=$D2"
caso "P2 y lo NOMBRA"                              1 "Z02-vota" "K97_CHECKS=$D2"
# P3 VA AL REVES y por eso no usa `caso`: se exige que Z01 NO aparezca como enfermo mientras Z02
# SI. Un instrumento que marcara a los dos estaria tan roto como uno que no marcara a ninguno, y
# ese es EL modo de fallo de todo clasificador. `caso` solo sabe exigir que un patron ESTE.
out=$(K97_CHECKS="$D2" bash "$CHK" 2>&1)
if printf '%s' "$out" | grep -q 'Z02-vota ENFERMO' && ! printf '%s' "$out" | grep -q 'Z01-declara ENFERMO'; then
  pasan=$((pasan+1)); printf '  [ok   ] %-56s\n' "P3 marca a Z02 y NO a Z01"
else
  fallos=$((fallos+1)); printf '  [FALLA] %-56s\n' "P3 marca a Z02 y NO a Z01"
fi

echo
echo "EL DOBLE CERO · sin el, un check de recuento se escapa"
# Un `count(*)` sobre una tabla vacia NO devuelve cero lineas: devuelve la linea '0'. Con solo
# el doble mudo, Z03 recibiria vacio, su `[ "$malas" = 0 ]` fallaria y saldria ROJO -o sea SANO
# para el censo-, escondiendo que con la base vacia dice "ninguna mal".
D3="$DIR/cuenta"; puebla "$D3"
sujeto_cuenta "$D3/Z03-cuenta.sh"
caso "C1 un check de recuento tambien se caza"     1 "Z03-cuenta ENFERMO \(sale VERDE con el doble cero\)" "K97_CHECKS=$D3"

echo
echo "LA SONDA DE VIDA · el fallo que tuvo la PRIMERA version de este instrumento"
# Con el doble mudo a secas, Z04 decia "prodsql no responde" y se apuntaba SANO. Es exactamente
# como se me escapo K06-visibilidad en la primera corrida. Una poblacion vacia NO es un canal
# caido, y el doble tiene que contestar lo que el motor contestaria: las consultas sin FROM se
# responden, las que tocan tablas vuelven vacias.
D4="$DIR/sonda"; puebla "$D4"
sujeto_sonda "$D4/Z04-sonda.sh"
caso "S1 el que sondea y luego vota: ENFERMO"      1 "Z04-sonda ENFERMO" "K97_CHECKS=$D4"
caso "S2 y NO por 'el canal no responde'"          1 "control POSITIVO: 2 de 2" "K97_CHECKS=$D4"

echo
echo "EL SUJETO · quien entra en el censo y quien no"
D5="$DIR/sinventana"; puebla "$D5"
sujeto_sin_ventana "$D5/Z05-sin-ventana.sh"
caso "V1 un check SIN ventana movil no es sujeto"  0 "VERDE: ninguno de los" "K97_CHECKS=$D5"
# V1b · y se nota en el recuento: solo cuenta los dos enlazados, no el tercero.
caso "V1b y el recuento lo refleja: 2 con ventana" 0 "2 check\(s\) con ventana movil" "K97_CHECKS=$D5"

echo
echo "LAS DISPOSICIONES · el que no se arregla se dispone CON SU CITA"
DISP="$DIR/disp.tsv"
printf 'Z02-vota\tPENDIENTE\tmedido el 2026-09-06, se arregla en la vuelta siguiente\n' > "$DISP"
caso "D1 un enfermo dispuesto no enrojece"         0 "1 dispuesto" "K97_CHECKS=$D2" "K97_DISPOSICIONES=$DISP"
caso "D2 pero sigue saliendo en la lista"          0 "Z02-vota ENFERMO" "K97_CHECKS=$D2" "K97_DISPOSICIONES=$DISP"

echo
echo "EL ARBOL DE VERDAD · el censo sale VERDE hoy, y hay que probar que es por los arreglos"
# EL BRAZO QUE HACE VALER A TODOS LOS DEMAS. Con el arbol de hoy K97 sale VERDE. Eso puede
# significar dos cosas que no se parecen: que los checks estan sanos, o que el instrumento dejo
# de mirar. Se le da un directorio identico al de hoy SALVO que K04 y K06 vuelven a su version
# de `main` en 478b7fd -las que el censo midio enfermas- y tiene que cazar a las dos.
# Es el mismo contraste contra git que K95-control usa con 64704d4.
BASE=478b7fd
D8="$DIR/arbol-real"; mkdir -p "$D8"
for f in "$ORIG"/harness/checks/*.sh "$ORIG"/harness/checks/*.tsv; do
  [ -e "$f" ] || continue
  ln -sf "$f" "$D8/$(basename "$f")"
done
viejos_ok=si
for c in K04-huecos K06-visibilidad; do
  rm -f "$D8/$c.sh"
  (cd "$ORIG" && git show "$BASE:harness/checks/$c.sh") > "$D8/$c.sh" 2>/dev/null || viejos_ok=no
  [ -s "$D8/$c.sh" ] || viejos_ok=no
done
if [ "$viejos_ok" = si ]; then
  caso "R1 con el K04 y el K06 de $BASE: ROJO"        1 "K04-huecos ENFERMO" "K97_CHECKS=$D8"
  caso "R1b y caza tambien a K06"                     1 "K06-visibilidad ENFERMO" "K97_CHECKS=$D8"
  # R2 · y con el arbol de HOY, verde. Los dos juntos son la prueba: el instrumento distingue.
  caso "R2 con el arbol de hoy: VERDE"                0 "VERDE: ninguno de los" "K97_CHECKS=$ORIG/harness/checks"
else
  # LOS TRES SE DECLARAN UNO A UNO, no como una linea suelta: el recuento final tiene que poder
  # contarlos, y ademas son criticos, asi que el control saldra NOMED.
  nocorre R1  "no se pudo sacar $BASE de git (¿arbol sin .git?)"
  nocorre R1b "no se pudo sacar $BASE de git (¿arbol sin .git?)"
  nocorre R2  "no se pudo sacar $BASE de git (¿arbol sin .git?)"
fi

echo
echo "LA PARTICION DEL SANO · «no salio verde» no dice POR QUE"
# EL CRITERIO TIENE QUE PODER MOVERSE. Estos dos sujetos no salen VERDE ninguno de los dos -los
# dos son SANOS para el censo- pero uno SABE cual de las dos cosas le paso y el otro no. Si K97
# los metiera en el mismo cubo, su particion no seria una particion: seria una etiqueta.
D9="$DIR/particion"; puebla "$D9"
sujeto_declara "$D9/Z01-declara.sh"     # mira SOLO si le llegaron filas -> no puede distinguir
sujeto_separa  "$D9/Z06-separa.sh"      # mira el rc del canal ANTES     -> distingue
out=$(K97_CHECKS="$D9" bash "$CHK" 2>&1)
gan=$(printf '%s\n' "$out" | sed -n 's/.*GANADO *([0-9]*) [^:]*://p')
pre=$(printf '%s\n' "$out" | sed -n 's/.*PRESTADO *([0-9]*) [^:]*://p')
comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-56s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-56s\n' "$1"; fi
}
comprueba "G1 el que separa el canal de las filas cae en GANADO" \
  "$(printf '%s' "$gan" | grep -qw Z06-separa && echo si || echo no)"
comprueba "G2 el que solo mira las filas cae en PRESTADO" \
  "$(printf '%s' "$pre" | grep -qw Z01-declara && echo si || echo no)"
# G3 · EL BRAZO QUE HACE QUE ESTO SEA UNA PARTICION Y NO UNA ETIQUETA: los dos plantados, que
# para el censo son igual de SANOS, caen en cubos DISTINTOS. Un clasificador que los junte esta
# tan roto como uno que marcara a todos.
comprueba "G3 los dos SANOS caen en cubos DISTINTOS" \
  "$(printf '%s' "$gan" | grep -qw Z06-separa && printf '%s' "$pre" | grep -qw Z01-declara && echo si || echo no)"
comprueba "G4 y ninguno de los dos aparece en el cubo del otro" \
  "$(printf '%s' "$gan" | grep -qw Z01-declara || printf '%s' "$pre" | grep -qw Z06-separa; [ $? -ne 0 ] && echo si || echo no)"
# G5 · la particion suma: GANADO + PRESTADO + SIN COMPARAR = sanos. Un cubo que se pierda por el
# camino seria la misma enfermedad que este control acaba de arreglar en su propio titular.
s_tot=$(printf '%s\n' "$out" | sed -n 's/.*· sanos: \([0-9]*\) .*/\1/p' | head -1)
s_sum=$(( $(printf '%s' "$gan" | wc -w) + $(printf '%s' "$pre" | wc -w) ))
comprueba "G5 la particion suma: $s_sum de $s_tot sanos" \
  "$([ "${s_tot:-0}" = "$s_sum" ] && echo si || echo no)"

# --- G6/G7 · EL DOBLE FIEL. Anadido el 2026-09-07 -----------------------------------------
# NINGUNO DE LOS DOS DOBLES ES FIEL PARA TODOS: para `SELECT ts FROM t` lo es MUDO -cero lineas-
# y para `count(*)` lo es CERO -la linea `0`-. La particion tomaba la firma SOLO de MUDO, asi que
# a un check que CUENTA le parecia que el canal estaba roto y lo mandaba a PRESTADO. Estos dos
# brazos son la prueba de que el criterio se mueve: uno distingue solo con CERO y tiene que salir
# GANADO; el otro no distingue con ninguno y tiene que salir PRESTADO.
D10="$DIR/dobles"; puebla "$D10"
sujeto_solo_cero "$D10/Z07-solo-cero.sh"
sujeto_declara   "$D10/Z01-declara.sh"
out=$(K97_CHECKS="$D10" bash "$CHK" 2>&1)
gan=$(printf '%s\n' "$out" | sed -n 's/.*GANADO *([0-9]*) [^:]*://p')
pre=$(printf '%s\n' "$out" | sed -n 's/.*PRESTADO *([0-9]*) [^:]*-://p')
comprueba "G6 el que solo distingue con el doble CERO: GANADO" \
  "$(printf '%s' "$gan" | grep -qw Z07-solo-cero && echo si || echo no)"
comprueba "G7 y el que no distingue con ninguno sigue PRESTADO" \
  "$(printf '%s' "$pre" | grep -qw Z01-declara && echo si || echo no)"
# G8 · y la salida publica CUANTOS se mueven, que es lo que hace auditable el cambio de criterio.
comprueba "G8 publica cuantos se mueven de PRESTADO a GANADO" \
  "$(printf '%s' "$out" | grep -q 'se mueven de PRESTADO a GANADO' && echo si || echo no)"

echo
echo "ANTI-FANTASMA · el instrumento tiene que probarse a si mismo"
caso "F1 sin directorio de checks: NOMED"          2 "no encuentro los checks" "K97_CHECKS=$DIR/no-existe"
D6="$DIR/vacio"; mk "$D6"
caso "F2 directorio sin checks de ventana: NOMED"  2 "cero checks con ventana movil" "K97_CHECKS=$D6"
# F3 · SIN EL CONTROL POSITIVO NO HAY VEREDICTO. Un directorio donde no estan K92 ni K52 no
# permite comprobar que el instrumento no marca a todos, y entonces su VERDE no vale nada.
D7="$DIR/sinpos"; mk "$D7"
sujeto_declara "$D7/Z01-declara.sh"
caso "F3 sin los checks del control positivo: NOMED" 2 "los controles del propio instrumento no cuadran" "K97_CHECKS=$D7"

echo
corridos=$((pasan+fallos))
n_nc=$(printf '%s' "$nocorren" | wc -w)
# EL DENOMINADOR ES EL DECLARADO, NO EL QUE SOBREVIVIO. Y los que no corrieron se nombran en la
# MISMA linea, porque es la unica que sobrevive a un corte de bin/_corta.
printf '%s de %s brazos declarados pasan · %s fallan · %s no corrieron%s\n' \
  "$pasan" "$TOTAL_BRAZOS" "$fallos" "$n_nc" "${nocorren:+:$nocorren}"
if [ "$corridos" -ne "$TOTAL_BRAZOS" ] && [ "$n_nc" -eq 0 ]; then
  # Ni fallaron ni se declararon como no corridos: entonces el TOTAL_BRAZOS de arriba esta mal.
  # Un control que no sabe cuantos brazos tiene no puede afirmar que estan todos.
  echo "NO MEDIDO: declaro $TOTAL_BRAZOS brazos y corrieron $corridos sin que ninguno se declarara ausente."
  echo "  el recuento del propio control esta mal: se arregla TOTAL_BRAZOS, no se ignora."
  exit 2
fi
if [ -n "${nocorren_criticos// /}" ]; then
  echo "NO MEDIDO: no corrio el brazo de REGRESION ($nocorren_criticos), que es el que prueba que"
  echo "  el verde de K97 se debe a los arreglos y no a que el instrumento haya dejado de mirar."
  echo "  Sin el, «pasan» no significa nada. Esto es NOMED, no un aprobado."
  exit 2
fi
[ "$fallos" -eq 0 ] || exit 1
exit 0
