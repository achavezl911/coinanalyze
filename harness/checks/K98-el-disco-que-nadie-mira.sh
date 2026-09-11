#!/usr/bin/env bash
# K98 · EL DISCO QUE NADIE MIRA
#
# SUJETO   los sitios que pueden llenarse hasta PARAR este laboratorio, y cuanto les queda.
# VERDE    los pisos medibles tienen por encima de su suelo MEDIDO, y los no medibles quedan
#          nombrados con su motivo.
# ROJO     algun piso medible esta por debajo de un suelo que se puede DEFENDER con una medida.
# NOMED    un canal no contesto. No se juzga lo que no se pudo leer.
#
# POR QUE EXISTE. De los 58 checks que habia antes de este, **CERO ejecutaban `df`** -y cero de
# los binarios de harness/bin-. Nadie miraba cuanto disco queda en ningun sitio. Control positivo
# de ese censo: SEIS usan `systemctl` (K09, K18, K19, K40, K49, K85), asi que el censo sabia
# encontrar cosas y el cero no era del instrumento. La noche del 2026-09-11 al laboratorio le
# faltaba espacio y **se supo porque un humano fue a mirar**.
#
# ---------------------------------------------------------------------------------
# LOS PISOS, ENUMERADOS DESDE EL SISTEMA Y NO HEREDADOS DE NINGUNA LISTA
#
# Medido el 2026-09-11T08:35Z. `CLAUDE.md` decia «140: 32 G, 21 G libres» y «143: 30 G, 18 G
# libres»: **lo de 140 ya no es cierto** -son 63 G-, que es justo por lo que esta lista se mide
# cada vez en vez de escribirse.
#
#   P1 · 143 `/`   MEDIBLE aqui mismo. 29.4 G · 17.2 G usados · 10.7 G libres · 62 %
#        Aqui viven el repo, el arnes, el ESPEJO de Postgres (571 MB) y /opt/actions-runner
#        (2.5 G), que es el runner de CI.
#
#   P2 · 140 `/`   MEDIBLE por `bin/prod`, que SI deja correr `df` -su lista de denegados es de
#        verbos que MUTAN: ln, sed -i, tee, systemctl start/stop/restart, apt, pip, psql,
#        dropdb, createdb, update.sh, backup.sh, rsync-. 63 G · 15 G usados · 45 G libres · 25 %.
#
#   P3 · EL ALMACEN DEL NODO donde vive el disco de 143.  **NO MEDIBLE — se declara.**
#        El `/` de 143 NO es un volumen: es `/dev/loop0`, y su respaldo es el FICHERO
#        `/var/lib/vz/images/143/vm-143-disk-0.raw`, que vive en el nodo 150.1.7.13. Ese camino
#        **no existe dentro de 143** (`ls /var/lib/vz` -> No such file or directory), asi que
#        desde aqui se puede saber COMO SE LLAMA y no CUANTO LE QUEDA.
#        **Y esto importa mas que los otros dos juntos:** si ese fichero es *sparse*, 143 puede
#        ver 10.7 G libres mientras el nodo no tiene ni uno, y las escrituras fallan con ENOSPC
#        sin que ningun `df` de aqui lo haya visto venir.
#
#   P4 · EL GRUPO DE VOLUMENES `pve` donde vive el disco de 140. **NO MEDIBLE — se declara.**
#        El `/` de 140 es `/dev/mapper/pve-vm--140--disk--0`, un volumen logico del nodo. Si el
#        grupo esta en modo *thin*, puede estar sobreaprovisionado y agotarse aunque el `df` de
#        140 diga 25 %.
#
#   **LOS DOS CONTENEDORES NO COMPARTEN ALMACEN, y eso se midio:** 140 cuelga de LVM y 143 de un
#   fichero en `/var/lib/vz`. Si comparten sustrato fisico o no, **desde aqui no se puede saber**,
#   y por eso no se afirma.
#
# POR QUE NO SE ABRE UN CANAL AL NODO. Medir P3 y P4 exige entrar en 150.1.7.13, y el arnes no
# cruza esa frontera hoy: `bin/prod` llega a 140 y `bin/prodsql`/`espejosql` hablan con bases de
# datos. Darle a un check una credencial del nodo es una decision de Alejandro y otra campana.
# **Un piso NO MEDIDO y declarado vale mas que un piso medido por un camino que nadie autorizo.**
#
# ---------------------------------------------------------------------------------
# QUE LE PASA A ESTE CHECK SI SE LLENA EL PISO SOBRE EL QUE SE APOYA · LA RESPUESTA INCOMODA
#
# Este check corre EN 143, o sea sobre P1. **No puede garantizar que avisara del llenado del
# piso que lo sostiene**, y conviene que esto quede escrito en vez de fingir lo contrario:
#
#   · `verify` escribe su log y su `estado/verify.tsv` en 143. Con el disco lleno, el marcador
#     puede no llegar a escribirse aunque el check haya hablado.
#   · Cualquier `mktemp` o redireccion a fichero falla, y en bash **un `$(...)` que falla
#     devuelve CADENA VACIA**, que aguas abajo se lee como cero. Es A26: un vacio pasando por
#     una cifra.
#
# LO QUE SE HACE PARA MITIGARLO, y mitigar no es resolver:
#   1 · este check NO escribe NADA en disco: ni mktemp, ni ficheros temporales, ni redirecciones.
#       Todo va por variables. Asi puede seguir hablando con el disco al 100 %.
#   2 · toda lectura que puede venir vacia se comprueba ANTES de compararla, y si viene vacia se
#       declara NO MEDIDO en vez de convertirse en un cero tranquilizador.
# Lo que NO se puede mitigar desde aqui es que `verify` escriba su marcador. Queda dicho.
#
# ---------------------------------------------------------------------------------
# EL UMBRAL NO ES UN NUMERO REDONDO · de donde sale cada suelo
#
# Un porcentaje no dice cuanto FALTA: el 10 % de 30 G son 3 G y el 10 % de 500 G son 50 G. Lo
# que para este laboratorio es quedarse sin gigas, no sin porcentaje. Asi que los suelos son
# BYTES y **se miden del propio sistema en cada pasada**, no se escriben aqui:
#
#   SUELO DE P2 (140) = el respaldo pre-despliegue MAYOR que hay hoy en /var/backups/coinalyze.
#       Es defendible sin opinar: `deploy-production.yml` respalda ANTES de mover `current`, asi
#       que por debajo de esa cifra **el proximo despliegue no puede escribir su respaldo**.
#       Medido el 2026-09-11: el mayor son 510 116 410 B (486 MiB) y hay 45 G libres, o sea 88
#       veces el suelo.
#
#   SUELO DE P1 (143) = el tamano del ESPEJO, que es la pieza mayor que este laboratorio tiene
#       que poder ESCRIBIR para seguir siendolo: reconstruirlo es un `zcat | psql` y sin sitio
#       para el se quedan mudos todos los checks que leen por `espejosql`.
#       **Se comparo contra la otra candidata antes de elegirla, midiendo las dos** el
#       2026-09-11 en 143:
#           una corrida de CI entera (1615 tests) ..... 234 074 112 B libres consumidos
#                                                       y su base desechable acaba en 221 MiB
#           el espejo coinalyze_espejo ................ 571 MB
#       El espejo es 2.4 veces la corrida de CI, asi que es el suelo conservador de los dos: por
#       encima de el caben las dos cosas. `K98_SUELO_143` lo sustituye para el control.
#
# NO SE CONDENA LO QUE NO SE SABE DEFENDER. Las cifras de los cuatro pisos se publican SIEMPRE
# con su denominador y su instante; el rojo solo sale de un suelo medido.
#
# CONTROL: harness/checks/K98-control.bash. No lleva .sh a proposito: bin/verify globea *.sh.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
AHORA=$(TZ=UTC date -u +%Y-%m-%dT%H:%M:%SZ)

# `df` de un sistema de ficheros, en BYTES. Devuelve "total usado libre pct dispositivo".
# Se permite inyectar la salida cruda para el control: un disco lleno no se puede plantar de
# verdad sin romper el laboratorio, y eso se dice en la entrega.
# K98_RUTA_143 apunta el `df` de P1 a otro sistema de ficheros. Existe para que el control
# positivo pueda plantar un disco LLENO DE VERDAD -un loopback pequeno, montado y rellenado
# hasta ENOSPC- en vez de limitarse a inyectar la cadena que `df` habria dicho. Inyectar la
# cadena prueba que el check sabe LEER; apuntarlo a un disco lleno prueba que sabe VER.
df_local() {
  if [ "${K98_DF_143+puesta}" = puesta ]; then printf '%s\n' "$K98_DF_143"; return 0; fi
  df -B1 --output=size,used,avail,pcent,source "${K98_RUTA_143:-/}" 2>/dev/null | tail -1
}
df_remoto() {
  if [ "${K98_DF_140+puesta}" = puesta ]; then printf '%s\n' "$K98_DF_140"; return 0; fi
  "$B/bin/prod" "df -B1 --output=size,used,avail,pcent,source / | tail -1" 2>/dev/null
}

pisos=""; fallos=""; nomed=""

# ── P1 · 143 ────────────────────────────────────────────────────────────────────────────────
L1=$(df_local)
set -- $L1
if [ $# -lt 5 ] || [ -z "${3:-}" ]; then
  echo "NO MEDIDO: no se pudo leer el df del / de 143. Un df vacio NO es un disco holgado:" \
       "es una no-medida, y convertirla en cero seria la trampa que este check existe para no" \
       "cometer. ($AHORA)"
  exit 2
fi
T1=$1; U1=$2; A1=$3; P1=$4; D1=$5

# el suelo de 143: inyectable, y si no el tamano del espejo
SUELO1=${K98_SUELO_143:-}
if [ -z "$SUELO1" ]; then
  SUELO1=$(psql --host=/var/run/postgresql -d "${ESPEJO_DB:-coinalyze_espejo}" \
            -tAc "SELECT pg_database_size('${ESPEJO_DB:-coinalyze_espejo}')" 2>/dev/null | tr -d ' ')
fi
case "$SUELO1" in ''|*[!0-9]*) SUELO1="" ;; esac

# ── P2 · 140 ────────────────────────────────────────────────────────────────────────────────
L2=$(df_remoto); rc2=$?
set -- $L2
if [ "$rc2" -ne 0 ] || [ $# -lt 5 ] || [ -z "${3:-}" ]; then
  nomed="$nomed · P2 (140): el canal no contesto o el df vino vacio (bin/prod rc=$rc2),"
  nomed="$nomed asi que NO se dice nada de su disco"
  T2=""; U2=""; A2=""; P2=""; D2=""
else
  T2=$1; U2=$2; A2=$3; P2=$4; D2=$5
fi

# el suelo de 140: el respaldo pre-despliegue mayor que hay hoy
SUELO2=${K98_SUELO_140:-}
if [ -z "$SUELO2" ] && [ -n "$T2" ]; then
  SUELO2=$("$B/bin/prod" "ls -l /var/backups/coinalyze/predeploy-*.sql.gz 2>/dev/null | awk '{print \$5}' | sort -n | tail -1" 2>/dev/null | tr -d ' ')
fi
case "$SUELO2" in ''|*[!0-9]*) SUELO2="" ;; esac

# Una cifra que se redondea a cero no informa: se escala a la unidad que la hace legible.
g() {
  awk -v b="$1" 'BEGIN{
    if (b >= 1073741824) printf "%.1f G", b/1073741824;
    else if (b >= 1048576) printf "%.1f M", b/1048576;
    else printf "%d B", b }'
}

pisos="P1 143 / : $(g "$A1") libres de $(g "$T1") ($P1 usado, $D1)"
if [ -n "$T2" ]; then
  pisos="$pisos · P2 140 / : $(g "$A2") libres de $(g "$T2") ($P2 usado, $D2)"
fi

# ── P3 y P4 · los que no se pueden medir, nombrados desde el sistema ────────────────────────
# P3 y P4 SE DERIVAN DEL DISPOSITIVO DE `/`, NO DEL QUE SE ESTE MIRANDO. Antes salian de $D1,
# que con K98_RUTA_143 puesto -o el dia que el / de 143 deje de ser un loop- apunta a otra cosa,
# y entonces el piso NO MEDIBLE desaparecia de la salida en silencio. Un piso que solo se declara
# cuando se cumple una condicion no esta declarado: lo cazo el brazo C6a de su control.
RAIZ=$(df --output=source / 2>/dev/null | tail -1 | tr -d ' ')
RESPALDO=""
case "$RAIZ" in
  /dev/loop*) RESPALDO=$(cat /sys/block/"$(basename "$RAIZ")"/loop/backing_file 2>/dev/null) ;;
esac
if [ -z "$RESPALDO" ]; then
  nomed="$nomed · P3 (el almacen del nodo): el / de 143 cuelga de $RAIZ y desde aqui NO se pudo"
  nomed="$nomed averiguar sobre que fichero o volumen del nodo se apoya, asi que tampoco se sabe"
  nomed="$nomed cuanto le queda a ese sustrato"
fi
if [ -n "$RESPALDO" ]; then
  nomed="$nomed · P3 (el almacen del nodo): el / de 143 cuelga de $RAIZ, cuyo fichero de"
  nomed="$nomed respaldo es $RESPALDO en 150.1.7.13. Ese camino NO existe dentro de 143, asi"
  nomed="$nomed que se sabe COMO SE LLAMA y no CUANTO LE QUEDA: si es sparse, aqui se veran"
  nomed="$nomed $(g "$A1") libres con el nodo a cero"
fi
case "${D2:-}" in
  "")
    nomed="$nomed · P4 (el grupo de volumenes del nodo): no se pudo leer el dispositivo de 140," ;;
  /dev/mapper/*|/dev/pve*)
    nomed="$nomed · P4 (el grupo de volumenes del nodo): el / de 140 es $D2, un volumen"
    nomed="$nomed logico de 150.1.7.13; si el grupo es thin puede agotarse aunque el df de"
    nomed="$nomed 140 diga $P2" ;;
esac
nomed="$nomed · los dos contenedores NO comparten almacen -140 cuelga de LVM y 143 de un"
nomed="$nomed fichero-, y si comparten sustrato fisico desde aqui no se puede saber"

# ── EL VEREDICTO · solo se condena lo que se sabe defender ──────────────────────────────────
if [ -n "$SUELO1" ] && [ "$A1" -lt "$SUELO1" ]; then
  fallos="$fallos; 143 / tiene $(g "$A1") libres y el suelo medido son $(g "$SUELO1")"
  fallos="$fallos -lo que el laboratorio tiene que poder escribir para reconstruir su espejo-"
fi
if [ -n "$T2" ] && [ -n "$SUELO2" ] && [ "$A2" -lt "$SUELO2" ]; then
  fallos="$fallos; 140 / tiene $(g "$A2") libres y el suelo medido son $(g "$SUELO2")"
  fallos="$fallos -el respaldo pre-despliegue mayor que hay hoy-, asi que el proximo"
  fallos="$fallos despliegue no podria escribir el suyo"
fi

SUELOS="suelos MEDIDOS: 143 $( [ -n "$SUELO1" ] && g "$SUELO1" || echo 'NO MEDIDO' )"
SUELOS="$SUELOS · 140 $( [ -n "$SUELO2" ] && g "$SUELO2" || echo 'NO MEDIDO' )"

if [ -n "$fallos" ]; then
  printf '%s · %s · %s · NO MEDIBLES%s · %s\n' "${fallos#; }" "$pisos" "$SUELOS" "$nomed" "$AHORA"
  exit 1
fi
# UN PISO QUE NORMALMENTE SE MIDE Y HOY NO SE PUDO LEER NO ES UN PISO HOLGADO. La frase «los
# pisos medibles estan por encima de su suelo» habla de TODOS; con uno sin leer seria cierta
# sobre menos pisos de los que nombra, y eso es estrechar la afirmacion en silencio.
if [ -z "$T2" ]; then
  printf 'NO MEDIDO: el piso de 140 no se pudo leer, asi que no se puede decir que los pisos esten por encima de su suelo -la frase habla de todos-. Lo que SI se leyo: %s · %s · NO MEDIBLES%s · %s\n' \
    "$pisos" "$SUELOS" "$nomed" "$AHORA"
  exit 2
fi
if [ -z "$SUELO1" ] && [ -z "$SUELO2" ]; then
  printf 'NO MEDIDO: se leyeron los pisos pero NO se pudo medir ningun suelo, asi que no hay con que juzgarlos · %s · NO MEDIBLES%s · %s\n' \
    "$pisos" "$nomed" "$AHORA"
  exit 2
fi
printf 'los pisos medibles estan por encima de su suelo · %s · %s · NO MEDIBLES%s · %s\n' \
  "$pisos" "$SUELOS" "$nomed" "$AHORA"
exit 0
