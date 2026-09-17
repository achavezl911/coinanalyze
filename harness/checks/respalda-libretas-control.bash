#!/bin/bash
# respalda-libretas-control · ¿viaja el metodo, se queda la foto, y se niega ante un secreto?
#
#     bash harness/checks/respalda-libretas-control.bash
#
# POR QUE ESTE CONTROL. Desde COLA 124 el respaldo lleva tambien `entregas/`, y eso mete tres
# promesas nuevas que hay que ver disparar:
#
#   R1  un fichero de `entregas/` vuelve del remoto IDENTICO
#   R2  una foto de payload -por encima del umbral- NO viaja
#   R3  un secreto plantado NIEGA el push, y el remoto se queda como estaba
#
# R3 ES EL QUE SOSTIENE A LOS OTROS DOS: el destino es un repo APARTE y un repo es para
# siempre. Un secreto que llega ahi no se quita borrandolo, hay que rotarlo.
#
# NO SE TOCA EL REMOTO DE VERDAD. Se monta un `git init --bare` local y se le pasa por
# `LIBRETAS_REMOTO`, con su propia copia y su propio `entregas/` de mentira.
#
# LA REGLA QUE ESTE CONTROL NO PUEDE HACER CUMPLIR, Y POR ESO SE ESCRIBE: en `entregas/` no
# se escribe un secreto CON SU FORMA, ni de ejemplo; se enmascara. El candado no distingue
# un ejemplo de una fuga -y hace bien-, asi que un ejemplo literal para el respaldo de
# todos. Paso el 2026-09-17 y lo escribi yo.
#
# Y ESTE CONTROL NO JUZGA `entregas/`: juzga el CANDADO, con plantados. Lo vivo lo dicen
# K49 y la unit.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
BK="$ORIG/harness/bin/respalda-libretas"
[ -x "$BK" ] || { echo "NO MEDIDO: no encuentro $BK"; exit 2; }
command -v git >/dev/null || { echo "NO MEDIDO: no hay git"; exit 2; }

DIR=$(mktemp -d) || exit 2
trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-60s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-60s\n' "$1"; fi; }

REMOTO="$DIR/remoto.git"; git init --quiet --bare "$REMOTO"
COPIA="$DIR/copia"
ENT="$DIR/entregas"
mkdir -p "$ENT/sub"
MARCA="zzMETODO-$$-zz"
printf 'una receta con su marca %s\n' "$MARCA" > "$ENT/receta.md"
printf 'un traspaso\n' > "$ENT/sub/traspaso.md"
# LA FOTO DE PAYLOAD: por encima del umbral por CONSTRUCCION, no por su nombre.
head -c 300000 /dev/zero | tr '\0' 'x' > "$ENT/foto-de-payload.json"

corre() { LIBRETAS_REMOTO="$REMOTO" LIBRETAS_COPIA="$COPIA" LIBRETAS_ENTREGAS="$ENT" \
          timeout -k 5 180 bash "$BK" 2>&1; }

echo "respalda-libretas-control · sujeto: $BK"
echo "   entregas de mentira: $(find "$ENT" -type f | wc -l) ficheros · la foto pesa $(wc -c < "$ENT/foto-de-payload.json") B"
echo

out=$(corre); rc=$?
comprueba "R0 el respaldo corrio y empujo (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"

# Se clona del remoto: lo que se comprueba es lo que VOLVIO, no lo que se mando.
VUELTA="$DIR/vuelta"
git clone --quiet "$REMOTO" "$VUELTA" 2>/dev/null
comprueba "R1a el directorio entregas/ llego al remoto" "$([ -d "$VUELTA/entregas" ] && echo si || echo no)"
comprueba "R1b y el fichero del metodo vuelve IDENTICO (su marca esta)" \
  "$(grep -qs "$MARCA" "$VUELTA/entregas/receta.md" && echo si || echo no)"
comprueba "R1c tambien lo de los subdirectorios" \
  "$([ -s "$VUELTA/entregas/sub/traspaso.md" ] && echo si || echo no)"
comprueba "R2 la FOTO DE PAYLOAD no viaja" \
  "$([ -e "$VUELTA/entregas/foto-de-payload.json" ] && echo no || echo si)"
comprueba "R1d y el manifiesto la cubre: sha256sum -c cuadra" \
  "$( ( cd "$VUELTA" && sha256sum --quiet -c SHA256SUMS >/dev/null 2>&1 ) && echo si || echo no)"
n_man=$(grep -c ' entregas/' "$VUELTA/SHA256SUMS" 2>/dev/null || echo 0)
comprueba "R1e el manifiesto nombra los de entregas/ ($n_man)" "$([ "$n_man" -ge 2 ] && echo si || echo no)"

echo
echo "R3 · UN SECRETO PLANTADO NIEGA EL PUSH"
antes=$(git -C "$REMOTO" rev-parse HEAD)
# SE CONSTRUYE EN EJECUCION, no se escribe literal aqui. Este fichero no viaja en el respaldo
# -solo viajan las libretas y `entregas/`-, pero la cabecera de arriba dice que los ejemplos van
# enmascarados o construidos, y una regla que su propio autor no cumple no la cumple nadie.
printf -- '%s%s\nb3BlbnNzaC1rZXktdjEAAAAA\n' '-----BEGIN OPENSSH ' 'PRIVATE KEY-----' \
  > "$ENT/se-colo-una-clave.txt"
out=$(corre); rc=$?
despues=$(git -C "$REMOTO" rev-parse HEAD)
comprueba "R3a rc distinto de 0 (rc=$rc)" "$([ "$rc" != 0 ] && echo si || echo no)"
comprueba "R3b lo dice, y NOMBRA el fichero" \
  "$(printf '%s' "$out" | grep -q 'se-colo-una-clave.txt' && echo si || echo no)"
comprueba "R3c y dice que hay que rotar, no borrar" \
  "$(printf '%s' "$out" | grep -q 'rota lo que se haya expuesto' && echo si || echo no)"
comprueba "R3d EL REMOTO NO SE MOVIO ($antes)" "$([ "$antes" = "$despues" ] && echo si || echo no)"

echo
echo "R4 · quitado el secreto, vuelve a empujar: el candado no se queda cerrado"
# SE ANADE ALGO NUEVO A PROPOSITO. Quitando solo el secreto, el arbol vuelve a ser EXACTAMENTE
# el que ya esta en el remoto, y entonces el respaldo sale 0 sin empujar -es su control
# positivo de siempre: «si el remoto ya tiene esto, silencio»-. Sin algo nuevo, este brazo no
# distinguiria «volvio a empujar» de «no hizo nada», que es justo la confusion que el propio
# respaldo arreglo en agosto.
rm -f "$ENT/se-colo-una-clave.txt"
printf 'una prediccion nueva\n' > "$ENT/prediccion.md"
out=$(corre); rc=$?
comprueba "R4a rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "R4b y el remoto AVANZO" \
  "$([ "$(git -C "$REMOTO" rev-parse HEAD)" != "$antes" ] && echo si || echo no)"
rm -rf "$DIR/vuelta2"; git clone --quiet "$REMOTO" "$DIR/vuelta2" 2>/dev/null
comprueba "R4c y lo nuevo esta en el remoto, no solo el commit" \
  "$([ -s "$DIR/vuelta2/entregas/prediccion.md" ] && echo si || echo no)"

echo
echo "R5 · EL CANDADO SE JUZGA CON PLANTADOS, NO CON EL ESTADO VIVO"
# ESTE BRAZO MEDIA EL DIA, NO EL INSTRUMENTO. Hasta COLA 125 escaneaba el `entregas/` REAL y
# exigia que saliera limpio, asi que se ponia ROJO por lo que hubiera ahi ese dia -y el
# 2026-09-17 se puso: `entregas/20260916-2330-canales.md` trae un token de EJEMPLO escrito con
# su forma real, el candado lo caza y el respaldo se niega, que es EXACTAMENTE lo que promete-.
# Un control que enrojece porque el sujeto funciona no mide el sujeto: mide el calendario.
# El estado vivo ya lo dicen K49 y la unit, que es donde tiene que decirse.
#
# LA REGLA, PARA QUIEN ESCRIBA LA PROXIMA ENTREGA: en `entregas/` NO SE ESCRIBE UN SECRETO CON
# SU FORMA, ni de ejemplo. Se enmascara -«ghp_<...>», «BEGIN ... PRIVATE KEY» partido, o la
# palabra sin el valor-. El candado no distingue un ejemplo de una fuga, y hace bien: quien lo
# lea desde el repo remoto tampoco podria.
CORPUS="$DIR/corpus"; mkdir -p "$CORPUS"
# NEGATIVO: lo que hay de verdad en `entregas/` y NO es un secreto. Si algo de esto disparara,
# el candado seria ruido y alguien lo apagaria.
printf 'la prosa habla de password, token y secret sin dar ninguno\n' > "$CORPUS/prosa.md"
printf 'md5 01b4b06786a7e5572487c97643808db5 publicado como prueba\n' > "$CORPUS/huella.md"
printf 'PGPASSWORD="$PG_PASSWORD" pg_dump\nAPI_TOKEN=${TOKEN}\n' > "$CORPUS/referencias.sh"
printf 'un token enmascarado: ghp_<treinta-y-seis-caracteres>\n' > "$CORPUS/enmascarado.md"
"$ORIG/harness/bin/busca-secretos" "$CORPUS" >/dev/null 2>&1; rc_neg=$?
comprueba "R5a NEGATIVO: prosa, huella publicada, referencias y enmascarado NO disparan (rc=$rc_neg)" \
  "$([ "$rc_neg" = 0 ] && echo si || echo no)"

# POSITIVO: el MISMO corpus con UN secreto de forma real. La unica diferencia es ese fichero.
printf 'GH=ghp_%s\n' "$(printf 'a%.0s' $(seq 1 36))" > "$CORPUS/se-colo.txt"
salida_pos=$("$ORIG/harness/bin/busca-secretos" "$CORPUS" 2>&1); rc_pos=$?
comprueba "R5b POSITIVO: el mismo corpus con UN secreto SI dispara (rc=$rc_pos)" \
  "$([ "$rc_pos" = 1 ] && echo si || echo no)"
comprueba "R5c y NOMBRA el fichero, no dice solo que hay algo" \
  "$(printf '%s' "$salida_pos" | grep -q 'se-colo.txt' && echo si || echo no)"
comprueba "R5d y NO arrastra a los cuatro inocentes" \
  "$(printf '%s' "$salida_pos" | grep -qE 'prosa.md|huella.md|referencias.sh|enmascarado.md' && echo no || echo si)"
rm -f "$CORPUS/se-colo.txt"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
