#!/usr/bin/env bash
# K44-control · ¿sabe K44 decir en cual de los SEIS estados esta el mundo?
#
#     bash harness/checks/K44-control.bash
#
# POR QUE ESTE CONTROL Y NO OTRO. K44 mira lo que pidio un NAVEGADOR, y un instrumento asi
# **solo ve algo si alguien abrio el panel**. En una ventana sin visitas da cero exactamente
# igual que si el panel no pidiera el sobre, **y solo uno de los dos es un defecto**. Si K44 no
# separa esos dos, nace roto de una forma que no se ve: se pone rojo un domingo por la tarde y
# alguien lo «arregla» sin que hubiera nada que arreglar. Aqui se plantan los seis y se comparan
# las SALIDAS, no los `rc` -tres de los seis comparten rc=2 a proposito-.
#
# EL CONTROL POSITIVO ES E4 Y HAY QUE VERLO DISPARAR: un instrumento que nunca marca verde esta
# tan roto como el que marca siempre. E4 planta un panel que SI pide el sobre y no pide ninguna
# parte, y exige rc=0. Sin ese brazo, «K44 esta rojo» no distingue un defecto de un check que no
# sabe decir que si.
#
# CADA PLANTADO DEJA SU PRUEBA: el `bin/prod` de mentira escribe en un fichero senal cuando lo
# llaman, y el brazo la comprueba. Sin llamada NO SE JUZGA.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K44-el-sobre-que-nadie-pide.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
DIR=$(mktemp -d) || exit 2
[ "${K44_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0; pasan=0
declare -A SALIDA

comprueba() {  # $1 = etiqueta   $2 = si|no
  if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-58s\n' "$1"
  else fallos=$((fallos+1)); printf '  [FALLA] %-58s\n' "$1"; fi
}

# K44 solo usa dos cosas del arnes: `$B/env` (para el entorno) y `$B/bin/prod` (el log).
# Se monta un arnes de mentira con esas dos y se apunta una COPIA del check con un `sed`,
# comprobando que el sed MORDIO: si no muerde, se compararia el check consigo mismo.
monta() {  # $1 = dir   $2 = rc del prod falso   $3 = lo que escribe en stdout
  rm -rf "$1"; mkdir -p "$1/bin"
  printf '%s\n' ". /srv/coinanalyze/harness/env" > "$1/env"
  {
    printf '%s\n' "#!/bin/bash"
    printf '%s\n' "printf 'LLAMADO\\n' >> $1/senal"
    printf "cat <<'FIN'\n%s\nFIN\n" "$3"
    printf '%s\n' "exit $2"
  } > "$1/bin/prod"
  chmod +x "$1/bin/prod"
  : > "$1/senal"
  # LOS PAYLOADS DE LAS EXCEPCIONES. El check baja el sobre y las rutas excusadas para volver a
  # comprobar cada excusa; aqui se le inyectan con K44_PAYLOADS para no tocar la red. El sobre
  # de serie trae SOLO los cuatro testigos del buscador -si faltaran, el check saldria NO MEDIDO
  # diciendo que su buscador esta roto, y ese es justo el brazo que lo protege-.
  mkdir -p "$1/payloads"
  printf '%s\n' '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}' > "$1/payloads/_sobre.json"
}
# `plantada` sobreescribe un payload concreto del arnes de mentira.
plantada() {  # $1 = dir   $2 = nombre de fichero   $3 = json
  printf '%s\n' "$3" > "$1/payloads/$2"
}
copia() {  # $1 = dir del arnes falso -> imprime la ruta de la copia
  local f="$1/K44.sh"
  sed "s#^B=/srv/coinanalyze/harness; . \"\$B/env\"#B=$1; . \"\$B/env\"#" "$CHK" > "$f"
  if cmp -s "$CHK" "$f"; then echo "SED-NO-MORDIO" >&2; return 1; fi
  printf '%s\n' "$f"
}
# `corre` deja el resultado en DOS GLOBALES y no lo imprime. La primera version lo llamaba
# dentro de una sustitucion de mandato, o sea en un SUBSHELL, y ahi la asignacion al array se
# pierde: los rc salian bien y las salidas llegaban VACIAS, asi que los diez brazos de texto
# fallaban todos por el instrumento y no por el sujeto. Lo canto el propio control.
corre() {  # $1 = etiqueta  $2 = fichero  resto = VAR=valor   -> deja RC y OUT
  local etq="$1" f="$2"; shift 2
  OUT=$(env "$@" timeout -k 5 200 bash "$f" 2>&1); RC=$?
  SALIDA["$etq"]="$OUT"
}

echo "K44-control · sujeto: $CHK"
echo

# ── E1 · EL CANAL NO CONTESTO ────────────────────────────────────────────────────────────────
echo "E1 · el canal no pudo contestar (bin/prod rc=3)"
monta "$DIR/e1" 3 ""
f=$(copia "$DIR/e1") || exit 2
corre E1 "$f"; rc=$RC
comprueba "E1a el plantado OCURRIO: el prod de mentira se llamo" \
  "$([ -s "$DIR/e1/senal" ] && echo si || echo no)"
comprueba "E1b NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E1c y dice que fue el CANAL, con su rc" \
  "$(printf '%s' "${SALIDA[E1]}" | grep -q 'no se pudo leer (bin/prod rc=3)' && echo si || echo no)"
comprueba "E1d y NO afirma nada sobre lo que el panel pide" \
  "$(printf '%s' "${SALIDA[E1]}" | grep -q 'NO dice nada sobre lo que el panel pide' && echo si || echo no)"

# ── E2 · NO CONSTA QUE NADIE MIRARA ──────────────────────────────────────────────────────────
echo
echo "E2 · el canal contesta y NO CONSTA que nadie mirara"
monta "$DIR/e2" 0 "VISITAS 0"
f=$(copia "$DIR/e2") || exit 2
corre E2 "$f"; rc=$RC
comprueba "E2a el plantado OCURRIO" "$([ -s "$DIR/e2/senal" ] && echo si || echo no)"
comprueba "E2b NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E2c y lo dice: 'no consta que nadie mirara'" \
  "$(printf '%s' "${SALIDA[E2]}" | grep -q 'no consta que nadie mirara' && echo si || echo no)"
comprueba "E2d y explica por que eso NO es el defecto" \
  "$(printf '%s' "${SALIDA[E2]}" | grep -q 'solo uno de los dos es un defecto' && echo si || echo no)"

# ── E3 · NO SE PUDO LEER LA LISTA FOTO ───────────────────────────────────────────────────────
echo
echo "E3 · el conjunto FOTO no se puede leer (la lista no es de este check)"
monta "$DIR/e3" 0 "VISITAS 100"
f=$(copia "$DIR/e3") || exit 2
corre E3 "$f" K44_K43=/dev/null; rc=$RC
comprueba "E3a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E3b y nombra el fichero del que no pudo leerla" \
  "$(printf '%s' "${SALIDA[E3]}" | grep -q 'familia FOTO en /dev/null' && echo si || echo no)"
comprueba "E3c y NO juzga: un criterio sobre cero rutas se cumple solo" \
  "$(printf '%s' "${SALIDA[E3]}" | grep -q 'se cumpliria solo sobre cero rutas' && echo si || echo no)"

# ── E4 · EL CONTROL POSITIVO · el VERDE, visto disparar ──────────────────────────────────────
echo
echo "E4 · CONTROL POSITIVO · el panel pide el sobre y CERO partes"
monta "$DIR/e4" 0 "VISITAS 900
450 /api/ai/context
450 /api/ohlcv"
f=$(copia "$DIR/e4") || exit 2
corre E4 "$f"; rc=$RC
comprueba "E4a el plantado OCURRIO" "$([ -s "$DIR/e4/senal" ] && echo si || echo no)"
comprueba "E4b VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E4c y dice cuantas veces lo pidio y cuantas partes (0)" \
  "$(printf '%s' "${SALIDA[E4]}" | grep -qE 'pide el sobre 450 veces y CERO de las [0-9]+ rutas' && echo si || echo no)"
printf '        %s\n' "$(printf '%s' "${SALIDA[E4]}" | head -1 | cut -c1-125)"

# ── E5 · NO PIDE EL SOBRE ────────────────────────────────────────────────────────────────────
echo
echo "E5 · hubo visitas y el panel NO pide el sobre"
monta "$DIR/e5" 0 "VISITAS 900
600 /api/dashboard/state
300 /api/ohlcv"
f=$(copia "$DIR/e5") || exit 2
corre E5 "$f"; rc=$RC
comprueba "E5a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E5b y NOMBRA las partes que si pide, con su cuenta" \
  "$(printf '%s' "${SALIDA[E5]}" | grep -q '/api/dashboard/state(600)' && echo si || echo no)"
comprueba "E5c y dice 0 peticiones al sobre" \
  "$(printf '%s' "${SALIDA[E5]}" | grep -q '0 peticiones a /api/ai/context' && echo si || echo no)"

# ── E6 · LA REFORMA A MEDIAS ─────────────────────────────────────────────────────────────────
echo
echo "E6 · pide el sobre Y ADEMAS sigue pidiendo las partes"
# LA RUTA DE E6 NO PUEDE TENER EXCEPCION, o dejaria de medir lo que dice medir. Antes plantaba
# /api/dashboard/state, que desde COLA 124 esta excusada: el brazo habria pasado a VERDE y
# «E6 falla» habria parecido una regresion del estado 6 cuando era su sujeto mal elegido.
# /api/wyckoff es FOTO y no tiene excusa, que es exactamente lo que este brazo necesita.
monta "$DIR/e6" 0 "VISITAS 900
450 /api/ai/context
200 /api/wyckoff"
f=$(copia "$DIR/e6") || exit 2
corre E6 "$f" K44_PAYLOADS="$DIR/e6/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E6a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E6b y lo llama REFORMA A MEDIAS, no lo mismo que E5" \
  "$(printf '%s' "${SALIDA[E6]}" | grep -q 'REFORMA A MEDIAS' && echo si || echo no)"
comprueba "E6c y dice las DOS cifras: las del sobre y las de las partes" \
  "$(printf '%s' "${SALIDA[E6]}" | grep -q 'pide el sobre 450 veces Y ADEMAS sigue pidiendo 200' && echo si || echo no)"

# ── LA EXCEPCION FALSABLE (COLA 124) · cuatro brazos ─────────────────────────────────────────
# Lo que se prueba aqui no es que la excusa exista: es que SE CAE SOLA. Una excusa que solo
# alguien puede retirar a mano es una lista de nombres con otro nombre.
SOBRE_SIN='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[1,2]}'
SOBRE_CON='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[1,2,3,4,5,6,7,8,9,10,11,12]}'
RUTA_DM='[1,2,3,4,5,6,7,8,9,10,11,12]'

echo
echo "E7 · una ruta EXCUSADA con su razon CIERTA no condena"
monta "$DIR/e7" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e7" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e7" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e7") || exit 2
corre E7 "$f" K44_PAYLOADS="$DIR/e7/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E7a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E7b NOMBRA la excusa y CONTRA QUE se comprobo" \
  "$(printf '%s' "${SALIDA[E7]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 2' && echo si || echo no)"

echo
echo "E8 · LA MISMA ruta con la razon hecha FALSA vuelve a condenar, sin que nadie toque la tabla"
monta "$DIR/e8" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e8" _sobre.json "$SOBRE_CON"
plantada "$DIR/e8" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e8") || exit 2
corre E8 "$f" K44_PAYLOADS="$DIR/e8/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E8a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E8b y dice EXCEPCION ANULADA con la cifra que la mato" \
  "$(printf '%s' "${SALIDA[E8]}" | grep -q 'EXCEPCION ANULADA: el sobre trae 12 y la ruta 12' && echo si || echo no)"
comprueba "E8c mismo plantado que E7 salvo el sobre, y veredicto CONTRARIO" \
  "$([ "${SALIDA[E7]}" != "${SALIDA[E8]}" ] && echo si || echo no)"

echo
echo "E9 · una ruta SIN excusa junto a una excusada: condena, y solo por la que no tiene"
monta "$DIR/e9" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e9" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e9" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e9") || exit 2
corre E9 "$f" K44_PAYLOADS="$DIR/e9/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E9a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E9b condena SOLO 1 ruta, la que no tiene excusa" \
  "$(printf '%s' "${SALIDA[E9]}" | grep -q 'sigue pidiendo 77 veces 1 de las' && echo si || echo no)"
comprueba "E9c y nombra a wyckoff, no a delta-matrix, como la condenada" \
  "$(printf '%s' "${SALIDA[E9]}" | grep -q '· /api/wyckoff(77) ·' && echo si || echo no)"

echo
echo "E10 · la excusa de una ruta que el panel YA NO PIDE sobra, y se dice"
monta "$DIR/e10" 0 "VISITAS 900
450 /api/ai/context"
f=$(copia "$DIR/e10") || exit 2
corre E10 "$f" K44_PAYLOADS="$DIR/e10/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E10a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E10b y declara las excepciones HUERFANAS por su nombre" \
  "$(printf '%s' "${SALIDA[E10]}" | grep -q 'HUERFANAS.*dashboard/state.*delta-matrix.*liquidation-levels' && echo si || echo no)"

echo
echo "E11 · el sobre no se pudo leer: NO se excusa a nadie por defecto"
monta "$DIR/e11" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
rm -f "$DIR/e11/payloads/_sobre.json"
f=$(copia "$DIR/e11") || exit 2
corre E11 "$f" K44_PAYLOADS="$DIR/e11/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E11a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E11b y dice que sin reverificar NO se excusa" \
  "$(printf '%s' "${SALIDA[E11]}" | grep -q 'excusar en silencio' && echo si || echo no)"

echo
echo "E12 · el BUSCADOR roto no puede excusar a nadie: sobre sin los testigos"
monta "$DIR/e12" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e12" _sobre.json '{"delta_matrix":[1,2]}'
plantada "$DIR/e12" _api_scalp_delta-matrix.json "$RUTA_DM"
f=$(copia "$DIR/e12") || exit 2
corre E12 "$f" K44_PAYLOADS="$DIR/e12/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E12a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E12b y nombra los testigos que no encuentra" \
  "$(printf '%s' "${SALIDA[E12]}" | grep -q 'buscador de claves no encuentra' && echo si || echo no)"

# ── LOS SEIS, DOS A DOS ──────────────────────────────────────────────────────────────────────
echo
echo "LOS SEIS ESTADOS · si dos dan la MISMA salida, no distingue lo que dice distinguir"
iguales=""
for a in E1 E2 E3 E4 E5 E6; do
  for b in E1 E2 E3 E4 E5 E6; do
    [ "$a" \< "$b" ] || continue
    [ "${SALIDA[$a]}" = "${SALIDA[$b]}" ] && iguales="$iguales $a=$b"
  done
done
comprueba "S1 los 6 dan 6 salidas DISTINTAS (repetidas:${iguales:- ninguna})" \
  "$([ -z "$iguales" ] && echo si || echo no)"
# y el reparto de rc, que NO es el criterio: tres comparten rc a proposito
printf '        rc: E1=2 E2=2 E3=2 (NOMED) · E4=0 (VERDE) · E5=1 E6=1 (ROJO)\n'
printf '        por eso se comparan SALIDAS y no rc: dos estados con el mismo rc\n'
printf '        son indistinguibles para quien solo mire el marcador.\n'

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
