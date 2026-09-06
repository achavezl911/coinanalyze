#!/usr/bin/env bash
# verify-control · EL INSTRUMENTO CON EL QUE SE MIDE TODO, CONTROLADO POR FIN.
#
# EL HECHO QUE LO MOTIVA, medido el 2026-09-06 y encontrado por el operador, no por el arnes:
# K93-el-camino-de-actualizacion.sh entro en el indice de git como 100644 -el UNICO 100644 de
# los 53 `.sh` de harness/checks-, y `verify:10` decia `[ -x "$c" ] || continue`. Resultado:
# el check NO se ejecuto ni una vez dentro de verify aunque a mano diera VERDE, el marcador
# publico 52 lineas en vez de 53, y **nadie podia saber que faltaba una**. No era este arbol:
# el modo esta en el indice, asi que un clon nuevo en cualquier sitio tambien lo saltaba.
#
# LA FAMILIA ES LA DE SIEMPRE: un instrumento que no puede fallar no controla nada. Un
# `chmod -x` neutralizaba CUALQUIER check del arnes y la unica cifra del proyecto no decia ni
# una palabra. Es peor que un rojo: es un check que desaparece.
#
# EL BRAZO QUE HACE VALER A LOS DEMAS es V3: el MISMO fixture contra el verify VIEJO -sacado
# de git, no escrito a mano- tiene que pasar inadvertido. Si el control no puede ensenar que
# el verify de ayer se comia el check, no esta controlando nada.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y este fichero prueba al arnes, no
# a produccion. Mismo patron que K88-control.bash. Corre sin red y sin base de datos.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
VERIFY="$ORIG/harness/bin/verify"
[ -r "$VERIFY" ] || { echo "NO MEDIDO: no encuentro bin/verify en $VERIFY"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${VERIFY_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0

# --- EL VERIFY VIEJO, SACADO DE GIT ------------------------------------------------------
# No se transcribe a mano: se pide el de origin/main. Una copia escrita por mi podria diferir
# justo en la linea que se quiere contrastar, y entonces V3 no probaria nada.
VIEJO="$DIR/verify-viejo"
# EL COMMIT NO SE TECLEA NI SE FIJA A origin/main: SE BUSCA. La version anterior pedia
# `origin/main:harness/bin/verify`, y en cuanto el arreglo se fusiono a main el contraste se
# quedo sin sujeto: este control salia NO MEDIDO entero y dejaba de probar los trece casos.
# Un control que se invalida a si mismo al fusionarse su propio arreglo es la enfermedad que
# vigila, en su version mas tonta. Medido el 2026-09-06 a las 10:23Z.
# Ahora se recorre el historial de bin/verify y se coge el ULTIMO commit en que el fichero
# TODAVIA NO tenia el arreglo. Eso sigue existiendo aunque main avance.
VIEJO_SHA=""
for h in $(cd "$ORIG" && git log --format=%H -- harness/bin/verify 2>/dev/null); do
  if ! (cd "$ORIG" && git show "$h:harness/bin/verify" 2>/dev/null) | grep -q 'VERIFY_HARNESS'; then
    VIEJO_SHA="$h"; break
  fi
done
[ -n "$VIEJO_SHA" ] || { echo "NO MEDIDO: no hay ningun commit de bin/verify anterior a VERIFY_HARNESS; sin el no hay contraste"; exit 2; }
if ! (cd "$ORIG" && git show "$VIEJO_SHA:harness/bin/verify") > "$VIEJO" 2>/dev/null; then
  echo "NO MEDIDO: no se pudo sacar bin/verify de $VIEJO_SHA"; exit 2
fi
chmod +x "$VIEJO" 2>/dev/null || true
grep -q 'VERIFY_HARNESS' "$VIEJO" && { echo "NO MEDIDO: el verify de $VIEJO_SHA ya trae VERIFY_HARNESS: el contraste no distingue nada"; exit 2; }
# El viejo tiene B clavado. Se le inyecta el arnes de mentira con un sed sobre la copia, que es
# el unico modo de correrlo contra otro arbol sin reescribirlo.
sed -i 's|^B=/srv/coinanalyze/harness$|B=${VERIFY_HARNESS:-/srv/coinanalyze/harness}|' "$VIEJO"
grep -q 'VERIFY_HARNESS' "$VIEJO" || { echo "NO MEDIDO: no se pudo apuntar el verify viejo al arnes de mentira"; exit 2; }

# --- EL ARNES DE MENTIRA ------------------------------------------------------------------
# Tres checks de juguete con veredictos conocidos, para que la cuenta sea comprobable a mano.
monta() {  # <dir>
  rm -rf "$1"; mkdir -p "$1/checks" "$1/estado" "$1/bin"
  printf '#!/bin/sh\necho "verde de juguete"\nexit 0\n'  > "$1/checks/Z01-verde.sh"
  printf '#!/bin/sh\necho "rojo de juguete"\nexit 1\n'   > "$1/checks/Z02-rojo.sh"
  printf '#!/bin/sh\necho "nomed de juguete"\nexit 2\n'  > "$1/checks/Z03-nomed.sh"
  chmod +x "$1"/checks/*.sh
}

corre() {  # <binario de verify> <arnes>  -> imprime la salida entera
  VERIFY_HARNESS="$2" sh "$1" 2>&1
}
lineas_check() { grep -cE '^Z[0-9]+' <<<"$1" || true; }

caso() {  # <nombre> <esperado> <obtenido>
  if [ "$3" = "$2" ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-56s %s\n' "$1" "$3"
  else
    fallos=$((fallos+1)); printf '  [FALLA] %-56s esperaba %s, dio %s\n' "$1" "$2" "$3"
  fi
}

echo "verify-control · sujeto: $VERIFY"
echo

echo "NEGATIVO · con todo en orden, verify no cambia de comportamiento"
A="$DIR/sano"; monta "$A"
out=$(corre "$VERIFY" "$A")
caso "V1 los 3 checks salen, con su veredicto"        "3" "$(lineas_check "$out")"
caso "V1b la cuenta es 1 VERDE 1 ROJO 1 NOMED"        "si" \
     "$(grep -qE '^1 VERDE +1 ROJO +1 NOMED' <<<"$out" && echo si || echo no)"

echo
echo "POSITIVO · un check sin bit de ejecucion APARECE"
B2="$DIR/sinbit"; monta "$B2"; chmod -x "$B2/checks/Z01-verde.sh"
out=$(corre "$VERIFY" "$B2")
caso "V2 siguen saliendo 3 lineas de check"           "3" "$(lineas_check "$out")"
caso "V2b el que perdio el bit sale NOMED"            "si" \
     "$(grep -qE '^Z01-verde +NOMED' <<<"$out" && echo si || echo no)"
caso "V2c y dice POR QUE, no solo que no pudo"        "si" \
     "$(grep -q 'sin bit de ejecucion' <<<"$out" && echo si || echo no)"
caso "V2d la cuenta lo refleja: 0 VERDE 1 ROJO 2 NOMED" "si" \
     "$(grep -qE '^0 VERDE +1 ROJO +2 NOMED' <<<"$out" && echo si || echo no)"

echo
echo "EL BRAZO QUE HACE VALER A LOS DEMAS · el verify VIEJO se lo comia en silencio"
# V3 · MISMO fixture, verify de origin/main. Si esto no ensena la diferencia, V2 no prueba
# nada: podria estar pasando porque el fixture no ejercita lo que dice.
outv=$(corre "$VIEJO" "$B2")
caso "V3 el verify VIEJO solo saca 2 de los 3"        "2" "$(lineas_check "$outv")"
caso "V3b y el check desaparecido no se nombra"       "si" \
     "$(grep -q 'Z01-verde' <<<"$outv" && echo no || echo si)"
caso "V3c el viejo publica 0 VERDE 1 ROJO 1 NOMED"    "si" \
     "$(grep -qE '^0 VERDE +1 ROJO +1 NOMED' <<<"$outv" && echo si || echo no)"

echo
echo "ANTI-FANTASMA · sin sujeto no hay veredicto"
C="$DIR/vacio"; rm -rf "$C"; mkdir -p "$C/checks" "$C/estado"
out=$(corre "$VERIFY" "$C")
caso "V4 checks/ sin ningun .sh: se dice, no 0-0-0"   "si" \
     "$(grep -q 'no hay ningun .sh' <<<"$out" && echo si || echo no)"
caso "V4b y cuenta como NOMED"                        "si" \
     "$(grep -qE '^0 VERDE +0 ROJO +1 NOMED' <<<"$out" && echo si || echo no)"
outv=$(corre "$VIEJO" "$C")
caso "V4c el viejo publicaba 0 VERDE 0 ROJO 0 NOMED"  "si" \
     "$(grep -qE '^0 VERDE +0 ROJO +0 NOMED' <<<"$outv" && echo si || echo no)"

echo
echo "EL RELOJ · un check que no termina no puede llevarse el marcador entero"
# EL HUECO QUE ESTO CIERRA, medido el 2026-09-06: `verify` no tenia tope por check, asi que
# un check colgado colgaba verify y NO SE PUBLICABA NINGUNA CIFRA. De los tres huecos que se
# midieron aquel dia es el unico de esta clase: los otros dos pierden UN check y el resto del
# marcador sale igual.
# Se prueba con un tope de 2 s y un check que duerme 30. Si el tope no funcionara, este
# control se colgaria 30 s: el propio caso tiene un `timeout` de 20 s por encima para que un
# fallo se vea como fallo y no como una sesion parada.
D2="$DIR/colgado"; monta "$D2"
printf '#!/bin/sh\nsleep 30\n' > "$D2/checks/Z04-colgado.sh"
chmod +x "$D2/checks/Z04-colgado.sh"
t0=$(date +%s)
out=$(VERIFY_TIMEOUT=2 timeout 20 sh -c "VERIFY_HARNESS='$D2' sh '$VERIFY' 2>&1")
dur=$(( $(date +%s) - t0 ))
caso "V6 verify TERMINA aunque un check no termine"   "si" \
     "$([ "$dur" -lt 20 ] && echo si || echo no)"
caso "V6b salen las 4 lineas de check"                "4" "$(lineas_check "$out")"
caso "V6c el colgado sale NOMED, no ROJO"             "si" \
     "$(grep -qE '^Z04-colgado +NOMED' <<<"$out" && echo si || echo no)"
caso "V6d y dice que agoto el tope"                   "si" \
     "$(grep -q 'agoto el tope' <<<"$out" && echo si || echo no)"
# V6e · SIN ESTE CASO, V6c NO PRUEBA NADA: si el tope matara tambien a los que terminan,
# todo saldria NOMED y V6c pasaria igual.
caso "V6e los otros tres conservan su veredicto"      "si" \
     "$(grep -qE '^Z01-verde +VERDE' <<<"$out" && grep -qE '^Z02-rojo +ROJO' <<<"$out" && echo si || echo no)"

echo
echo "LOS DOS HUECOS DEL GLOB · un check que no casa el patron APARECE"
# LOS DOS QUE QUEDABAN, cerrados el 2026-09-06. Ninguno habia mordido nunca, y los dos fallaban
# EN SILENCIO. El caso que hace valer a los otros dos es N7: los ficheros que NO son checks
# -los `.bash` de control, un `.tsv`, un `.py`- NO pueden disparar, o el aviso seria ruido.
D3="$DIR/glob"; monta "$D3"
cp "$D3/checks/Z01-verde.sh" "$D3/checks/Z05-olvidado.sh.bak"
mkdir -p "$D3/checks/sub"
cp "$D3/checks/Z01-verde.sh" "$D3/checks/sub/Z06-escondido.sh"
printf '#!/bin/sh\nexit 0\n' > "$D3/checks/Z07-control.bash"
printf 'ruta\tgrupo\n'                                    > "$D3/checks/Z08-datos.tsv"
printf 'x = 1\n'                                          > "$D3/checks/Z09-ayuda.py"
out=$(corre "$VERIFY" "$D3")
caso "V7 el .sh.bak APARECE y sale NOMED"             "si" \
     "$(grep -qE '^Z05-olvidado.sh.bak +NOMED' <<<"$out" && echo si || echo no)"
caso "V7b y dice que el glob no lo ve"                "si" \
     "$(grep -q 'no termina en .sh' <<<"$out" && echo si || echo no)"
caso "V8 el .sh del subdirectorio APARECE y sale NOMED" "si" \
     "$(grep -qE '^Z06-escondido.sh +NOMED' <<<"$out" && echo si || echo no)"
caso "V8b y dice en que subdirectorio esta"           "si" \
     "$(grep -q 'esta en un subdirectorio (sub)' <<<"$out" && echo si || echo no)"
# N7 · SIN ESTE CASO, V7 Y V8 SERIAN UNA MAQUINA DE RUIDO: hoy hay 18 ficheros legitimos en
# checks/ que no casan *.sh, y quejarse de ellos enseniaria a ignorar el aviso.
caso "N7 el .bash, el .tsv y el .py NO disparan"      "si" \
     "$(grep -qE '^Z0[789]' <<<"$out" && echo no || echo si)"
caso "N7b y los 3 checks de verdad conservan su veredicto" "si" \
     "$(grep -qE '^Z01-verde +VERDE' <<<"$out" && grep -qE '^Z02-rojo +ROJO' <<<"$out" && echo si || echo no)"
caso "V9 la cuenta suma los dos huerfanos: 1V 1R 3N"  "si" \
     "$(grep -qE '^1 VERDE +1 ROJO +3 NOMED' <<<"$out" && echo si || echo no)"

echo
echo "EL TERCER HUECO · un fichero SIN EXTENSION NINGUNA"
# EL RESIDUO que el operador midio con su banco contra 485cdc4 el 2026-09-06: los dos brazos de
# arriba cazan lo que LLEVA `.sh` sin terminar en `.sh`, pero un `K97-algo` a secas no lleva `.sh`
# en el nombre y seguia desapareciendo en silencio. Se usa un arbol aparte para no mover V9.
D4="$DIR/sinext"; monta "$D4"
cp "$D4/checks/Z01-verde.sh" "$D4/checks/K97-algo"
printf 'nada\n' > "$D4/checks/LEEME"
out=$(corre "$VERIFY" "$D4")
caso "V10 el K97 sin extension APARECE y sale NOMED"  "si" \
     "$(grep -qE '^K97-algo +NOMED' <<<"$out" && echo si || echo no)"
caso "V10b y dice por que: no tiene extension"        "si" \
     "$(grep -q 'no tiene extension' <<<"$out" && echo si || echo no)"
# N8 · EL LIMITE DECLARADO, probado para que no sorprenda: la regla es ESTRECHA a proposito y
# solo mira los que empiezan por K. Un `LEEME` sin punto NO dispara. Si algun dia alguien llama
# a un check `deuda`, se perdera igual; queda dicho aqui y en el comentario de bin/verify.
caso "N8 un LEEME sin extension NO dispara (el limite)" "si" \
     "$(grep -qE '^LEEME' <<<"$out" && echo no || echo si)"
# N9 · Y LO QUE HACE VALER A V10: sobre el arbol DE VERDAD, la regla no toca a nadie. Se aplica
# el predicado a checks/ real en vez de correr verify entero, que son minutos.
n_reales=0; n_mudos=0
for f in "$ORIG"/harness/checks/K*; do
  [ -f "$f" ] || continue
  bn=$(basename "$f"); case "$bn" in *.sh) continue ;; esac
  n_reales=$((n_reales+1))
  case "$bn" in *.*) n_mudos=$((n_mudos+1)) ;; esac
done
caso "N9 los $n_reales acompaniantes K* de verdad siguen mudos" "si" \
     "$([ "$n_reales" -gt 0 ] && [ "$n_mudos" = "$n_reales" ] && echo si || echo no)"

echo
echo "EL rc · un NOMED no puede salir como exito"
monta "$B2"; chmod -x "$B2/checks/Z01-verde.sh"
VERIFY_HARNESS="$B2" sh "$VERIFY" >/dev/null 2>&1; rc=$?
caso "V5 con un check sin bit, verify sale != 0"      "si" "$([ "$rc" -ne 0 ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
