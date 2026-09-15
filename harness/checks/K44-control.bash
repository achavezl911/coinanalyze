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
