#!/usr/bin/env bash
# K98-control · ¿ve K98 un disco lleno, o solo sabe leer la cadena que `df` habria dicho?
#
#     bash harness/checks/K98-control.bash
#
# EL CONTROL POSITIVO ES REAL Y NO INYECTADO, y esa es la diferencia que importa. Inyectar la
# salida de `df` prueba que el check sabe LEER; apuntarlo a un sistema de ficheros que esta
# LLENO DE VERDAD prueba que sabe VER. Aqui se monta un `tmpfs` de 1 MiB, se rellena hasta
# ENOSPC y se le pide a K98 que lo mire.
#
# SE INTENTO PRIMERO CON UN LOOPBACK Y NO SE PUDO, y queda escrito porque es una trampa:
# `mount -o loop` falla dentro de un LXC -«failed to setup loop device»-, y entonces
# `df /mnt/...` NO falla: contesta por el sistema de ficheros de ARRIBA, o sea el `/` de 143, con
# una cifra perfectamente creible. Un plantado que no ocurre y una medida que sale igual es la
# forma exacta en que este laboratorio se ha equivocado antes. **Por eso la prueba del plantado
# comprueba el DISPOSITIVO que `df` devuelve, no se limita a imprimirlo.**
#
# LO QUE ESTE CONTROL NO PUEDE HACER, dicho: no puede llenar el `/` de 143 ni el de 140 de
# verdad, porque eso pararia el laboratorio. Esos dos se plantan inyectando la salida de `df`, y
# lo que prueban es la aritmetica del umbral, no la vista.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K98-el-disco-que-nadie-mira.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
PUNTO=${K98C_PUNTO:-/mnt/k98-control}
fallos=0; pasan=0
declare -A SALIDA

limpia() { umount "$PUNTO" 2>/dev/null || true; rmdir "$PUNTO" 2>/dev/null || true; }
trap limpia EXIT

comprueba() {
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-60s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-60s\n' "$1"; fi
}
corre() {  # $1 = etiqueta, resto = VAR=valor  -> deja RC y OUT (globales: en un $(...) se pierden)
  local etq="$1"; shift
  OUT=$(env "$@" timeout -k 5 200 bash "$CHK" 2>&1); RC=$?
  SALIDA["$etq"]="$OUT"
}

echo "K98-control · sujeto: $CHK"
echo

# ── C1 · EL POSITIVO, CON UN DISCO LLENO DE VERDAD ──────────────────────────────────────────
echo "C1 · POSITIVO REAL · un tmpfs de 1 MiB lleno hasta ENOSPC"
limpia; mkdir -p "$PUNTO"
mount -t tmpfs -o size=1M tmpfs "$PUNTO" 2>/dev/null
DEV=$(df --output=source "$PUNTO" 2>/dev/null | tail -1)
if [ "$DEV" != "tmpfs" ]; then
  echo "  NO MEDIDO: el tmpfs no se monto (df contesta '$DEV', que es el sistema de arriba)."
  echo "  Sin plantado no se juzga: seria medir el / de 143 creyendo medir un disco lleno."
  exit 2
fi
dd if=/dev/zero of="$PUNTO/relleno" bs=64k count=64 >/dev/null 2>&1 || true
LIBRE=$(df -B1 --output=avail "$PUNTO" | tail -1 | tr -d ' ')
comprueba "C1a el plantado OCURRIO: dispositivo=$DEV y quedan $LIBRE B libres" \
  "$([ "$DEV" = tmpfs ] && [ "$LIBRE" -lt 65536 ] && echo si || echo no)"
corre C1 K98_RUTA_143="$PUNTO" K98_SUELO_143=1048576
comprueba "C1b K98 lo CONDENA: ROJO, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "C1c y dice las dos cifras: lo libre y el suelo" \
  "$(printf '%s' "${SALIDA[C1]}" | grep -qE '143 / tiene .* libres y el suelo medido son' && echo si || echo no)"
printf '        %s\n' "$(printf '%s' "${SALIDA[C1]}" | head -1 | cut -c1-120)"

# ── C2 · EL NEGATIVO · todo holgado, y SE VE QUE MIRO ───────────────────────────────────────
echo
echo "C2 · NEGATIVO · el mismo tmpfs pero con sitio de sobra"
dd if=/dev/zero of="$PUNTO/relleno" bs=1k count=1 >/dev/null 2>&1
LIBRE2=$(df -B1 --output=avail "$PUNTO" | tail -1 | tr -d ' ')
comprueba "C2a el plantado OCURRIO: ahora quedan $LIBRE2 B libres" \
  "$([ "$LIBRE2" -gt 65536 ] && echo si || echo no)"
corre C2 K98_RUTA_143="$PUNTO" K98_SUELO_143=65536
comprueba "C2b VERDE, rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
# «se ve que llego a mirar» = publica la cifra del piso que miro, no se calla
comprueba "C2c y SE VE QUE MIRO: publica el tamano y el dispositivo que leyo" \
  "$(printf '%s' "${SALIDA[C2]}" | grep -q 'tmpfs' && echo si || echo no)"
comprueba "C2d y el instante en que lo miro" \
  "$(printf '%s' "${SALIDA[C2]}" | grep -qE '2[0-9]{3}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' && echo si || echo no)"
printf '        %s\n' "$(printf '%s' "${SALIDA[C2]}" | head -1 | cut -c1-120)"

# ── C3 · EL BORDE · un byte a cada lado del suelo ───────────────────────────────────────────
echo
echo "C3 · EL BORDE · el suelo es una raya, y se prueba a los dos lados"
corre C3justo K98_DF_143="1000 900 100 90% /dev/prueba" K98_SUELO_143=100
comprueba "C3a libre == suelo: NO condena (rc=$RC)" "$([ "$RC" != 1 ] && echo si || echo no)"
corre C3bajo K98_DF_143="1000 901 99 91% /dev/prueba" K98_SUELO_143=100
comprueba "C3b libre == suelo-1: CONDENA (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"

# ── C4 · UN df ILEGIBLE NO ES UN DISCO HOLGADO ──────────────────────────────────────────────
echo
echo "C4 · el df de 143 viene vacio"
corre C4 K98_DF_143=""
comprueba "C4a NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "C4b y lo dice: un df vacio NO es un disco holgado" \
  "$(printf '%s' "${SALIDA[C4]}" | grep -q 'Un df vacio NO es un disco holgado' && echo si || echo no)"

# ── C5 · EL PISO DE 140 NO SE PUDO LEER ─────────────────────────────────────────────────────
echo
echo "C5 · el canal de 140 no contesta"
corre C5 K98_DF_140=""
comprueba "C5a NO MEDIDO, rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "C5b y publica lo que SI leyo en vez de callarse" \
  "$(printf '%s' "${SALIDA[C5]}" | grep -q 'Lo que SI se leyo' && echo si || echo no)"
comprueba "C5c y NO dice que los pisos esten por encima de su suelo" \
  "$(printf '%s' "${SALIDA[C5]}" | grep -q 'los pisos medibles estan por encima' && echo no || echo si)"

# ── C6 · LOS NO MEDIBLES SE NOMBRAN SIEMPRE ─────────────────────────────────────────────────
echo
echo "C6 · los pisos que el arnes no puede medir salen nombrados, pase lo que pase"
corre C6 K98_RUTA_143="$PUNTO" K98_SUELO_143=65536
comprueba "C6a nombra el fichero de respaldo del disco de 143 en el nodo" \
  "$(printf '%s' "${SALIDA[C6]}" | grep -q 'vm-143-disk-0.raw' && echo si || echo no)"
comprueba "C6b nombra el volumen logico de 140" \
  "$(printf '%s' "${SALIDA[C6]}" | grep -q 'pve-vm--140--disk--0' && echo si || echo no)"
comprueba "C6c y dice que los dos contenedores NO comparten almacen" \
  "$(printf '%s' "${SALIDA[C6]}" | grep -q 'NO comparten almacen' && echo si || echo no)"

# ── LAS SALIDAS, DOS A DOS ──────────────────────────────────────────────────────────────────
echo
echo "SI DOS SITUACIONES DAN LA MISMA SALIDA, no distingue lo que dice distinguir"
iguales=""
for a in C1 C2 C3justo C3bajo C4 C5; do
  for b in C1 C2 C3justo C3bajo C4 C5; do
    [ "$a" \< "$b" ] || continue
    [ "${SALIDA[$a]}" = "${SALIDA[$b]}" ] && iguales="$iguales $a=$b"
  done
done
comprueba "S1 las 6 situaciones dan 6 salidas distintas (repetidas:${iguales:- ninguna})" \
  "$([ -z "$iguales" ] && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
