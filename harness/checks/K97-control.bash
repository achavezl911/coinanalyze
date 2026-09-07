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
fallos=0; pasan=0

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
  printf '  [....] %-56s\n' "R1/R2 no se pudo sacar $BASE de git"
fi

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
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
