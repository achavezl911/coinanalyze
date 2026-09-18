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
# 2026-09-18 · ESTE BRAZO SE RE-APUNTA, Y NO SE AFLOJA. Casaba la frase «excusar en silencio»,
# que vivia en el `exit 2` que apagaba el check entero en la primera linea del bloque; ese
# camino se fue con COLA 125 (A54: lo decidible va antes que lo que falta). Lo que E11 tiene que
# sostener no es una frase: es que NADIE salga excusado cuando no se pudo reverificar, y que lo
# que no se pudo leer se DIGA. Las dos cosas se comprueban ahora, que es mas que antes.
comprueba "E11b y NADIE sale excusado" \
  "$(printf '%s' "${SALIDA[E11]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"
comprueba "E11c y NOMBRA lo que no pudo leer" \
  "$(printf '%s' "${SALIDA[E11]}" | grep -q 'no se pudo leer el sobre' && echo si || echo no)"

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

# ── LA AFIRMACION ES LO QUE EL PANEL LEE (COLA 124, remate) ──────────────────────────────────
# De /api/scalp/liquidation-levels el panel pinta TODAS las filas y publica su cuenta; de los
# metadatos solo usa `minutes`, con reserva de 60. La primera version de esta excepcion
# afirmaba que la ruta declara minutes/bucket_bps/window_start/window_end y el sobre no, y eso
# se refuta por algo que el panel NO LEE: los dos brazos de abajo salian AL REVES.
LIQ_RUTA='{"minutes":60,"bucket_bps":10,"window_start":"a","window_end":"b","rows":[1,2,3,4,5,6,7,8,9]}'
TESTIGOS='"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"profile":"default"'
# A · los cuatro metadatos DENTRO del sobre, y el tope del sobre INTACTO (8 de 9 filas).
# Los metadatos entran DONDE ENTRARIAN de verdad: dentro del propio bloque del sobre, junto a
# sus filas -que siguen topadas en 8 de 9-. Ponerlos al nivel alto del sobre no reproduce nada:
# la version de 333b359b ya buscaba ACOTADA dentro de `liquidation_levels` y no los veria.
SOBRE_META="{$TESTIGOS,\"liquidation_levels\":{\"minutes\":60,\"bucket_bps\":10,\"window_start\":\"a\",\"window_end\":\"b\",\"rows\":[1,2,3,4,5,6,7,8]}}"
# B · TODAS las filas de la ruta dentro del sobre: NUEVE, por encima del tope de 8.
SOBRE_FILAS="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8,9]}"
# C · HORA TRANQUILA: las dos cuentas iguales y por DEBAJO del tope.
LIQ_CORTA='{"minutes":60,"rows":[1,2,3]}'
SOBRE_CORTA="{$TESTIGOS,\"liquidation_levels\":[1,2,3]}"
# D · HORA AGITADA: la ruta trae 16 y el sobre sus 8. Mismo panel, otra hora.
LIQ_LARGA='{"minutes":60,"rows":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}'
SOBRE_OCHO="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8]}"

# EL TOPE SE INYECTA, en vez de leerlo de 140: asi el control no depende del canal ni del
# release, y puede plantar un tope SUBIDO para ver caer la excusa.
LIMITS_OK="$DIR/limits-ok.py"
LIMITS_SUBIDO="$DIR/limits-subido.py"
printf '%s\n' 'PROFILE_LIMITS = {"lite": {"liq_levels": 5}, "default": {"liq_levels": 8}, "max": {"liq_levels": 25}}' > "$LIMITS_OK"
printf '%s\n' 'PROFILE_LIMITS = {"lite": {"liq_levels": 5}, "default": {"liq_levels": 50}, "max": {"liq_levels": 80}}' > "$LIMITS_SUBIDO"

liqmonta() {  # $1 = dir   $2 = json del sobre   $3 = json de la ruta
  # El log lleva la QUERY con el `limit` del panel: el check lo saca de ahi, no de una copia.
  monta "$1" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels
QUERY 101 /api/scalp/liquidation-levels?symbol=TEST&minutes=60&bucket_bps=10&limit=50"
  plantada "$1" _sobre.json "$2"
  plantada "$1" "_api_scalp_liquidation-levels.json" "$3"
}
liqcorre() {  # $1 = etiqueta  $2 = dir  $3 = fichero de topes (o vacio)
  local f; f=$(copia "$2") || exit 2
  if [ -n "$3" ]; then
    corre "$1" "$f" K44_PAYLOADS="$2/payloads" K44_SIMBOLO=TEST K44_LIMITS="$3"
  else
    corre "$1" "$f" K44_PAYLOADS="$2/payloads" K44_SIMBOLO=TEST K44_LIMITS=/no/existe
  fi
}

echo
echo "E13 · los CUATRO METADATOS en el sobre y el tope intacto: sigue EXCUSADA"
liqmonta "$DIR/e13" "$SOBRE_META" "$LIQ_RUTA"
liqcorre E13 "$DIR/e13" "$LIMITS_OK"; rc=$RC
comprueba "E13a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E13b y la razon es el TOPE del perfil contra el limit del panel" \
  "$(printf '%s' "${SALIDA[E13]}" | grep -q 'topa `liquidation_levels` en 8 .* y el panel pide limit=50' && echo si || echo no)"

echo
echo "E14 · el sobre sirve MAS filas que su propio tope: ese tope ya no lo describe, CONDENA"
liqmonta "$DIR/e14" "$SOBRE_FILAS" "$LIQ_RUTA"
liqcorre E14 "$DIR/e14" "$LIMITS_OK"; rc=$RC
comprueba "E14a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E14b y dice ANULADA con las dos cifras que la matan" \
  "$(printf '%s' "${SALIDA[E14]}" | grep -q 'el sobre sirve 9 filas y el perfil `default` topa en 8' && echo si || echo no)"
comprueba "E14c E13 y E14 dan veredictos CONTRARIOS con la misma ruta" \
  "$([ "${SALIDA[E13]}" != "${SALIDA[E14]}" ] && echo si || echo no)"

# ── EL VEREDICTO NO DEPENDE DE LA HORA ───────────────────────────────────────────────────────
# Este par es el punto entero del segundo remate. Mismo panel, mismo tope, mismo `limit`: lo
# UNICO que cambia entre E15 y E16 es cuantas liquidaciones hubo en la ultima hora. Con el
# criterio anterior -contar filas- la hora tranquila CONDENABA y la agitada excusaba.
echo
echo "E15 · HORA TRANQUILA: cuentas iguales por debajo del tope (3 y 3) NO condena"
liqmonta "$DIR/e15" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E15 "$DIR/e15" "$LIMITS_OK"; rc=$RC
comprueba "E15a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E15b y DICE que las cuentas de esta hora no son lo que sostiene la excusa" \
  "$(printf '%s' "${SALIDA[E15]}" | grep -q 'por debajo del tope, asi que las cuentas de esta hora no lo ensenan' && echo si || echo no)"

echo
echo "E16 · HORA AGITADA: la ruta trae 16 y el sobre 8. MISMO veredicto que la tranquila"
liqmonta "$DIR/e16" "$SOBRE_OCHO" "$LIQ_LARGA"
liqcorre E16 "$DIR/e16" "$LIMITS_OK"; rc=$RC
comprueba "E16a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E16b MISMO veredicto que E15 con 5 veces mas filas: la hora NO manda" \
  "$([ "$RC" = 0 ] && printf '%s' "${SALIDA[E16]}" | grep -q 'topa `liquidation_levels` en 8' && echo si || echo no)"

echo
echo "E17 · LA EXCUSA CAE SOLA: alguien sube liq_levels hasta el limit del panel"
liqmonta "$DIR/e17" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E17 "$DIR/e17" "$LIMITS_SUBIDO"; rc=$RC
comprueba "E17a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E17b y dice que el sobre YA puede darle todo lo que lee" \
  "$(printf '%s' "${SALIDA[E17]}" | grep -q 'topa en 50 .* y el panel pide limit=50: el sobre ya puede darle TODO' && echo si || echo no)"
comprueba "E17c mismos payloads que E15 y veredicto CONTRARIO: lo que cambia es el tope" \
  "$([ "${SALIDA[E15]}" != "${SALIDA[E17]}" ] && echo si || echo no)"

# ── LO QUE NO SE PUEDE VERIFICAR NO ES UN VERDE (COLA 124, tercer remate) ────────────────────
# Antes estos casos salian VIVA y K44 daba VERDE. Decirlo en la linea no lo convierte en medida:
# el marcador cuenta VERDE, y esta campana vino justo a quitar las redes que dicen lo que no
# midieron. Ahora la ruta queda en un tercer cubo: ni excusa ni condena.
SOBRE_SINPERFIL='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"liquidation_levels":[1,2,3]}'
SOBRE_50="{$TESTIGOS,\"liquidation_levels\":[$(seq -s, 1 50)]}"
LIQ_50="{\"minutes\":60,\"rows\":[$(seq -s, 1 50)]}"
LIQ_16='{"minutes":60,"rows":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}'
SOBRE_16="{$TESTIGOS,\"liquidation_levels\":[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]}"
# Un log SIN la query del panel: el `limit` no se puede leer.
liqmonta_sinlimit() {  # $1 = dir   $2 = sobre   $3 = ruta
  monta "$1" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels"
  plantada "$1" _sobre.json "$2"
  plantada "$1" "_api_scalp_liquidation-levels.json" "$3"
}

echo
echo "E18 · sin fuente para el tope: NO MEDIDO. No condena, pero TAMPOCO da verde"
liqmonta "$DIR/e18" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E18 "$DIR/e18" ""; rc=$RC
comprueba "E18a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E18b y lo declara NO VERIFICABLE EN ESTA CORRIDA" \
  "$(printf '%s' "${SALIDA[E18]}" | grep -q 'NO VERIFICABLE EN ESTA CORRIDA' && echo si || echo no)"
comprueba "E18c y dice por que no basta con decirlo" \
  "$(printf '%s' "${SALIDA[E18]}" | grep -q 'contar como medida lo que no se midio' && echo si || echo no)"

echo
echo "E19 · MAS filas que su tope y un log SIN limit: se decide igual, y CONDENA"
liqmonta_sinlimit "$DIR/e19" "$SOBRE_50" "$LIQ_50"
liqcorre E19 "$DIR/e19" "$LIMITS_OK"; rc=$RC
comprueba "E19a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E19b y dice que se decide SIN el limit del panel" \
  "$(printf '%s' "${SALIDA[E19]}" | grep -q 'se decide SIN el `limit` del panel' && echo si || echo no)"
comprueba "E19c con 16 y 16 y sin limit, tambien condena" \
  "$(liqmonta_sinlimit "$DIR/e19b" "$SOBRE_16" "$LIQ_16"; liqcorre E19b "$DIR/e19b" "$LIMITS_OK"; [ "$RC" = 1 ] && echo si || echo no)"

echo
echo "E20 · un sobre SIN \`profile\`: no hay tope que leer, NO MEDIDO"
liqmonta "$DIR/e20" "$SOBRE_SINPERFIL" "$LIQ_CORTA"
liqcorre E20 "$DIR/e20" "$LIMITS_OK"; rc=$RC
comprueba "E20a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E20b y nombra lo que falta" \
  "$(printf '%s' "${SALIDA[E20]}" | grep -q 'el sobre no declara su `profile`' && echo si || echo no)"

echo
echo "E21 · log SIN limit y filas POR DEBAJO del tope: no se puede decidir, NO MEDIDO"
liqmonta_sinlimit "$DIR/e21" "$SOBRE_CORTA" "$LIQ_CORTA"
liqcorre E21 "$DIR/e21" "$LIMITS_OK"; rc=$RC
comprueba "E21a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E21b y nombra que falta el limit del log" \
  "$(printf '%s' "${SALIDA[E21]}" | grep -q 'el log no trae el `limit`' && echo si || echo no)"

echo
echo "E22 · una no verificable JUNTO a una ruta sin excusa: manda la condena"
monta "$DIR/e22" 0 "VISITAS 900
450 /api/ai/context
101 /api/scalp/liquidation-levels
77 /api/wyckoff"
plantada "$DIR/e22" _sobre.json "$SOBRE_CORTA"
plantada "$DIR/e22" "_api_scalp_liquidation-levels.json" "$LIQ_CORTA"
liqcorre E22 "$DIR/e22" ""; rc=$RC
comprueba "E22a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E22b condena por wyckoff, que es la que no tiene excusa" \
  "$(printf '%s' "${SALIDA[E22]}" | grep -q '· /api/wyckoff(77)' && echo si || echo no)"
comprueba "E22c y la no verificable sale NOMBRADA, no callada" \
  "$(printf '%s' "${SALIDA[E22]}" | grep -q 'NO SE HAN PODIDO VERIFICAR' && echo si || echo no)"

# ── E23-E26 · UN PAYLOAD QUE NO SE PUDO LEER NO SE COME LA CONDENA DE OTRA RUTA (COLA 125) ──
# EL PUNTO. Hasta hoy, si UNA de las tres rutas con excepcion no se podia leer en la corrida,
# K44 salia NO MEDIDO ENTERO -y lo hacia ANTES de mirar `partes`-. En esa misma corrida el panel
# podia estar pidiendo suelta otra ruta de FOTO SIN NINGUNA EXCUSA, que es un hecho sobre el
# panel que no necesita ese payload para nada. Lo que faltaba de una se comia la condena de otra,
# que es A54 otra vez y por otra puerta.
# COMO SE PLANTA «ILEGIBLE»: el fichero EXISTE y no es JSON, que es lo que deja `bin/api` cuando
# la ruta no contesta -no se borra el fichero, se queda vacio-. Asi el plantado se ve.
echo
echo "E23 · la ruta con excusa ILEGIBLE y NADA MAS: no hay nada que condenar -> NO MEDIDO"
monta "$DIR/e23" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e23" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e23" "_api_scalp_delta-matrix.json" ""
f=$(copia "$DIR/e23") || exit 2
corre E23 "$f" K44_PAYLOADS="$DIR/e23/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E23a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E23b y NOMBRA la ruta que no se pudo leer" \
  "$(printf '%s' "${SALIDA[E23]}" | grep -q '/api/scalp/delta-matrix(200): no se pudo leer su payload' && echo si || echo no)"
comprueba "E23c y NO la da por excusada" \
  "$(printf '%s' "${SALIDA[E23]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"

echo
echo "E24 · EL PUNTO · la MISMA ruta ilegible MAS una suelta sin excusa -> ROJO, y nombra las dos"
monta "$DIR/e24" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e24" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e24" "_api_scalp_delta-matrix.json" ""
f=$(copia "$DIR/e24") || exit 2
corre E24 "$f" K44_PAYLOADS="$DIR/e24/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E24a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E24b condena por /api/wyckoff, que no necesita ese payload" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '· /api/wyckoff(77)' && echo si || echo no)"
comprueba "E24c y NOMBRA ademas la que no se pudo leer" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '/api/scalp/delta-matrix(200): no se pudo leer su payload' && echo si || echo no)"
comprueba "E24d y NO condena a la ilegible: no entra en las partes" \
  "$(printf '%s' "${SALIDA[E24]}" | grep -q '· /api/scalp/delta-matrix(200) ' && echo no || echo si)"

echo
echo "E25 · CONTROL DE E24 · el MISMO log con el payload LEGIBLE: sigue ROJO, y sin nada sin leer"
# Sin este brazo, E24 pasaria igual si el check condenara SIEMPRE a wyckoff: lo unico que
# cambia entre los dos es si ese payload se puede leer.
monta "$DIR/e25" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix
77 /api/wyckoff"
plantada "$DIR/e25" _sobre.json "$SOBRE_SIN"
plantada "$DIR/e25" "_api_scalp_delta-matrix.json" "$RUTA_DM"
f=$(copia "$DIR/e25") || exit 2
corre E25 "$f" K44_PAYLOADS="$DIR/e25/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E25a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E25b y NADA queda sin leer" \
  "$(printf '%s' "${SALIDA[E25]}" | grep -q 'no se pudo leer su payload' && echo no || echo si)"
comprueba "E25c y delta-matrix SI sale excusada y reverificada" \
  "$(printf '%s' "${SALIDA[E25]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 2' && echo si || echo no)"

echo
echo "E26 · el SOBRE ilegible tampoco apaga la condena de una suelta sin excusa"
# La otra mitad del mismo punto: sin sobre NINGUNA excusa se puede reverificar -y las tres salen
# nombradas en el tercer cubo- pero `/api/wyckoff` sigue sin tener excusa, y eso se decide con el
# log. Antes esto era un `exit 2` en la primera linea del bloque.
monta "$DIR/e26" 0 "VISITAS 900
450 /api/ai/context
77 /api/wyckoff"
plantada "$DIR/e26" _sobre.json ""
f=$(copia "$DIR/e26") || exit 2
corre E26 "$f" K44_PAYLOADS="$DIR/e26/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E26a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E26b y dice que el sobre no se pudo leer" \
  "$(printf '%s' "${SALIDA[E26]}" | grep -q 'no se pudo leer el sobre' && echo si || echo no)"
comprueba "E26c y las tres excepciones salen como HUERFANAS o sin verificar, no excusadas" \
  "$(printf '%s' "${SALIDA[E26]}" | grep -q 'EXCUSADAS Y REVERIFICADAS' && echo no || echo si)"

echo
echo "E27 · y sin sobre y sin nada que condenar, NO MEDIDO (no VERDE)"
monta "$DIR/e27" 0 "VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"
plantada "$DIR/e27" _sobre.json ""
f=$(copia "$DIR/e27") || exit 2
corre E27 "$f" K44_PAYLOADS="$DIR/e27/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E27a NO MEDIDO, rc=2 (rc=$rc)" "$([ "$rc" = 2 ] && echo si || echo no)"
comprueba "E27b y dice lo que no pudo leer" \
  "$(printf '%s' "${SALIDA[E27]}" | grep -q 'LO QUE NO SE PUDO LEER EN ESTA CORRIDA' && echo si || echo no)"

# ── E28-E33 · LAS OTRAS DOS EXCUSAS CONTRA LA HORA (A53) ────────────────────────────────────
# COLA 124 rehizo la excusa de liquidation-levels porque su veredicto dependia de la hora: en
# una hora tranquila las cuentas coincidian, la excusa moria y K44 condenaba un diseno correcto.
# E15/E16 lo fijan para TOPE. Aqui se hace lo mismo con las OTRAS DOS, que nadie habia atacado.
#
# LOS PLANTADOS SON FIJOS Y SE DIFERENCIAN SOLO EN EL DATO DE MERCADO: misma forma, mismas
# claves, mismo numero de ventanas. Si el veredicto cambiara entre los dos, el check estaria
# juzgando el mercado y no el panel.
#
# DE DONDE SALE LA FORMA, medido el 2026-09-18 sobre el RELEASE DESPLEGADO en 140
# (/opt/coinalyze/releases/582459337bc7167317b4abca3b9841a3cf65b2cb):
#   · la ruta delta-matrix devuelve SIEMPRE 12 ventanas: la lista es un literal (api.py:1311-1323)
#     y el bucle que las recorre hace `rows.append` INCONDICIONAL, sin un solo `continue`
#     (scalp_logic.py:4319-4458). El numero es una constante del codigo, no de la hora.
#   · el sobre trae 5: `delta_windows` del perfil (ai_context.py:76), otra constante.
#   · `scalp_persistence` y `signal_base_rate` son claves LITERALES del dict que devuelve
#     /api/dashboard/state (api.py:3500-3502): no pueden faltar por falta de dato.
#   · `delta_matrix` y `liquidation_levels` son entradas literales del sobre (ai_context.py:861
#     y :925): tampoco pueden faltar por falta de dato.
# Conclusion MEDIDA: la UNICA ausencia que produccion puede dar hoy sin cambiar codigo es que el
# payload NO LLEGUE, y eso ya es el tercer cubo (E23-E27). Las ausencias de E30 y E33 SOLO las
# puede producir un cambio de codigo, y por eso ahi la excusa DEBE morir: es su diseno.
dm_ruta() {  # $1 = valor del delta en cada ventana. Las 12 del release, siempre las 12.
  local v="$1" w out=""
  for w in 15s 30s 1m 3m 5m 15m 18m 30m 1h 4h 8h 1d; do
    out="$out,{\"window\":\"$w\",\"delta\":$v}"
  done
  printf '[%s]' "${out#,}"
}
dm_sobre() {  # $1 = valor  $2..= ventanas. El sobre trae las 5 del perfil.
  local v="$1"; shift
  local w out=""
  for w in "$@"; do out="$out,{\"window\":\"$w\",\"delta\":$v}"; done
  printf '{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"delta_matrix":[%s]}' "${out#,}"
}
LOG_DM="VISITAS 900
450 /api/ai/context
200 /api/scalp/delta-matrix"

echo
echo "E28 · MENOS · HORA TRANQUILA (12 ventanas, todas sin dato): EXCUSADA"
monta "$DIR/e28" 0 "$LOG_DM"
plantada "$DIR/e28" _sobre.json "$(dm_sobre null 15s 1m 3m 5m 15m)"
plantada "$DIR/e28" "_api_scalp_delta-matrix.json" "$(dm_ruta null)"
f=$(copia "$DIR/e28") || exit 2
corre E28 "$f" K44_PAYLOADS="$DIR/e28/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E28a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E28b la excusa VIVE, con sus dos cifras (12 y 5)" \
  "$(printf '%s' "${SALIDA[E28]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 5' && echo si || echo no)"

echo
echo "E29 · MENOS · HORA AGITADA (las MISMAS 12 ventanas, con dato): MISMO VEREDICTO"
monta "$DIR/e29" 0 "$LOG_DM"
plantada "$DIR/e29" _sobre.json "$(dm_sobre 91400.5 15s 1m 3m 5m 15m)"
plantada "$DIR/e29" "_api_scalp_delta-matrix.json" "$(dm_ruta 91400.5)"
f=$(copia "$DIR/e29") || exit 2
corre E29 "$f" K44_PAYLOADS="$DIR/e29/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E29a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E29b EL PUNTO: la hora no cambia el veredicto de MENOS (E28=$rc)" \
  "$([ "$rc" = 0 ] && printf '%s' "${SALIDA[E29]}" | grep -q 'la ruta sirve 12 elementos y el sobre `delta_matrix` solo 5' && echo si || echo no)"

echo
echo "E30 · MENOS · y SI CAMBIA EL CODIGO -la ruta baja a 5 ventanas- la excusa MUERE"
# Esta ausencia produccion NO la puede dar: las 12 son un literal. Si un dia la ruta sirve 5,
# el sobre ya le da todo y la peticion suelta sobra. Sin este brazo, E28/E29 pasarian igual con
# una excusa que no supiera morir.
monta "$DIR/e30" 0 "$LOG_DM"
plantada "$DIR/e30" _sobre.json "$(dm_sobre 91400.5 15s 1m 3m 5m 15m)"
plantada "$DIR/e30" "_api_scalp_delta-matrix.json" '[{"window":"15s","delta":1},{"window":"1m","delta":1},{"window":"3m","delta":1},{"window":"5m","delta":1},{"window":"15m","delta":1}]'
f=$(copia "$DIR/e30") || exit 2
corre E30 "$f" K44_PAYLOADS="$DIR/e30/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E30a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E30b y dice EXCEPCION ANULADA con la cifra que la mato" \
  "$(printf '%s' "${SALIDA[E30]}" | grep -q 'EXCEPCION ANULADA: el sobre trae 5 y la ruta 5' && echo si || echo no)"

# --- FALTAN · lo mismo con la otra excusa -------------------------------------------------
DS_TRANQUILA='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":false,"episodios":0},"signal_base_rate":{"available":false,"n":0}}'
DS_AGITADA='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":true,"episodios":6146,"p90_min":4},"signal_base_rate":{"available":true,"n":812,"tasa":0.37}}'
DS_SIN='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{},"scalp_persistence":{"available":true,"episodios":6146}}'
SOBRE_TESTIGOS='{"symbol":"TEST","snapshot":{},"scalp":{},"setup":{}}'
LOG_DS="VISITAS 900
450 /api/ai/context
200 /api/dashboard/state"

echo
echo "E31 · FALTAN · HORA TRANQUILA (las dos claves presentes y VACIAS): EXCUSADA"
monta "$DIR/e31" 0 "$LOG_DS"
plantada "$DIR/e31" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e31" "_api_dashboard_state.json" "$DS_TRANQUILA"
f=$(copia "$DIR/e31") || exit 2
corre E31 "$f" K44_PAYLOADS="$DIR/e31/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E31a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E31b la excusa VIVE y dice DONDE busco" \
  "$(printf '%s' "${SALIDA[E31]}" | grep -q 'la ruta sirve scalp_persistence signal_base_rate y NO estan en TODO el sobre' && echo si || echo no)"

echo
echo "E32 · FALTAN · HORA AGITADA (las MISMAS claves con dato): MISMO VEREDICTO"
monta "$DIR/e32" 0 "$LOG_DS"
plantada "$DIR/e32" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e32" "_api_dashboard_state.json" "$DS_AGITADA"
f=$(copia "$DIR/e32") || exit 2
corre E32 "$f" K44_PAYLOADS="$DIR/e32/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E32a VERDE, rc=0 (rc=$rc)" "$([ "$rc" = 0 ] && echo si || echo no)"
comprueba "E32b EL PUNTO: la hora no cambia el veredicto de FALTAN" \
  "$([ "$rc" = 0 ] && [ "${SALIDA[E31]}" = "${SALIDA[E32]}" ] && echo si || echo no)"

echo
echo "E33 · FALTAN · y SI CAMBIA EL CODIGO -la ruta deja de servir una clave- la excusa MUERE"
# `signal_base_rate` es una clave LITERAL del dict de /api/dashboard/state (api.py:3502): esta
# ausencia solo la produce un cambio de codigo, y entonces la excusa TIENE que morir.
monta "$DIR/e33" 0 "$LOG_DS"
plantada "$DIR/e33" _sobre.json "$SOBRE_TESTIGOS"
plantada "$DIR/e33" "_api_dashboard_state.json" "$DS_SIN"
f=$(copia "$DIR/e33") || exit 2
corre E33 "$f" K44_PAYLOADS="$DIR/e33/payloads" K44_SIMBOLO=TEST; rc=$RC
comprueba "E33a ROJO, rc=1 (rc=$rc)" "$([ "$rc" = 1 ] && echo si || echo no)"
comprueba "E33b y NOMBRA la clave que la ruta dejo de servir" \
  "$(printf '%s' "${SALIDA[E33]}" | grep -q 'la RUTA ya no sirve signal_base_rate' && echo si || echo no)"

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
