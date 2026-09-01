#!/bin/bash
# K82  EL ESPEJO SE COMPARA CONTRA EL VOLCADO DEL QUE SALIO, TABLA POR TABLA.
#
# LA VIA, REPRODUCIDA ANTES QUE LA CIFRA. Es la sexta vez y las cinco anteriores decidieron
# donde gatea el check.
#   · NO HAY MANIFIESTO QUE ENSANCHAR. K01a:69 es [ filas -gt 0 ] sobre signal_outcome: exige
#     NO-VACIA, ni siquiera un conteo fijado. La COLA cita "180696 filas" pero el check no las
#     pide: una restauracion que trajera UNA fila pasaria igual.
#   · EL ESPEJO SE RESTAURA A MANO Y UNA VEZ -el 2026-08-25, del volcado del 08-13; no hay
#     timer ni script-. O sea que esto no es un defecto vivo: es una trampa armada para LA
#     PROXIMA restauracion, incluido el "refrescarlo con cada despliegue" que propone la COLA.
#
# EL CRUCE QUE YA EXISTIA ESTA ANTI-CORRELACIONADO, y es lo que convierte esto en necesario.
# K18:69-79 ya compara espejo contra 140 con reltuples sobre TODAS las tablas y confirma con
# count(*) exacto -- pero en la direccion PROD < ESPEJO, porque vigila borrados en produccion.
# Una restauracion corta baja el lado del espejo, o sea que hace a K18 MAS SILENCIOSO. El
# unico cruce que hay no es solo ciego a este fallo: se calla mas cuanto peor es.
#
# EL INSTRUMENTO EXTERNO ES EL VOLCADO, y por eso el manifiesto NO se escribe a mano ni se
# deduce del espejo -deducirlo del espejo seria derivar la expectativa del SUJETO, que es el
# error de K25 exacto-. El fichero del que salio la restauracion sigue en disco y es la verdad
# de lo que esa restauracion DEBIA producir. Recorrerlo entero cuesta 3.1 s medidos sobre
# 118 MB y da 46 tablas con datos y 1533709 filas, que es el manifiesto completo.
#
# ESTE CHECK NO SUSTITUYE A K01a, SE SUMA, y la comparacion conjunto a conjunto es
# obligatoria porque es la que se cayo en K43:
#     K01a exige   las 40 tablas DECLARADAS presentes POR NOMBRE  +  signal_outcome > 0
#     K82  exige   las tablas CON DATOS del volcado, con su CONTEO EXACTO
#   LO QUE K82 NO CUBRE Y K01a SI: la PRESENCIA de tablas declaradas que el volcado trae
#   VACIAS. K82 solo mira bloques COPY, asi que una restauracion que perdiera el DDL de una
#   tabla vacia pasaria K82 y fallaria K01a. Retirar K01a dejaria ese hueco sin vigilar.
#
# LO QUE NO ES, medido para no arreglar donde no duele:
#   · signal_outcome no es la tabla mayor -es la 2a, 180696 de 1533709 = 11.8 %- pero elegir
#     otra no arreglaria nada: el reparto es PLANO. Las tres mayores suman el 37.6 %, asi que
#     vigilar UNA tabla vigila poco se elija la que se elija.
#   · 13 tablas salen pobladas en 140 y vacias en el espejo, pero 12 son PARTICIONES fechadas
#     posteriores al volcado -legitimamente ausentes-. La unica base real es
#     open_interest_daily, y tambien es legitima: entro en schema.sql el 2026-08-28 (03bc570,
#     K67), o sea DESPUES del volcado. OJO A LA TRAMPA: su min(day) en 140 es 2026-07-23,
#     ANTERIOR al volcado, porque K67 la rellena recalculando desde los 5min. Derivar la
#     excepcion por "fecha de la fila mas vieja" daria FALSO; hay que mirar cuando nacio la
#     TABLA, no cuando son sus datos. Por eso este check compara contra el VOLCADO y no
#     contra 140: el volcado no tiene ese problema, porque lo que no estaba, no esta.
#
# LOS TRES BRAZOS:
#   A · FIDELIDAD. Cada tabla con bloque COPY en el volcado tiene que tener en el espejo
#       EXACTAMENTE las filas que el volcado trae. Menos es una restauracion corta; MAS
#       tambien se informa, porque significa que el espejo se escribio despues y ya no es una
#       copia -los tests de persistencia escriben en el, asi que no es hipotetico-.
#   B · EL VOLCADO TIENE QUE SER EL DE ESTE ESPEJO. Si la fecha del fichero no coincide con
#       el horizonte de datos del espejo, se estaria comparando contra el artefacto
#       equivocado y eso es NOMED, no ROJO. Es la misma regla de K63: el veredicto no es una
#       propiedad del sujeto solo, sino del par sujeto-instrumento.
#   C · CONTROL POSITIVO Y CASO VACIO. El volcado tiene que rendir un manifiesto con sustancia
#       -al menos 30 tablas- y al menos una tabla tiene que CUADRAR exacta: si ninguna cuadra,
#       lo roto es la comparacion y no el espejo, y decir ROJO seria acusar al sujeto de un
#       fallo del instrumento.
#
# DE QUE ARBOL: el volcado y el espejo son de 143. No se toca 140.
#
# Se comprueba con: bash harness/checks/K82-el-espejo-contra-su-volcado.sh

set -uo pipefail
B=/srv/coinanalyze/harness
. "$B/env"

# --- B · elegir el volcado y comprobar que es el de ESTE espejo.
VOLCADO=$(ls -1t /srv/coinanalyze/espejo-*.sql.gz 2>/dev/null | head -1)
[ -n "${VOLCADO:-}" ] && [ -r "$VOLCADO" ] || {
  echo "NO MEDIDO: no hay ningun /srv/coinanalyze/espejo-*.sql.gz legible del que derivar el manifiesto"
  exit 2
}
FECHA_VOLCADO=$(basename "$VOLCADO" | grep -oE '[0-9]{8}' | head -1)
[ -n "$FECHA_VOLCADO" ] || { echo "NO MEDIDO: el nombre de $VOLCADO no lleva fecha AAAAMMDD y no se puede emparejar con el espejo"; exit 2; }
FECHA_FMT="${FECHA_VOLCADO:0:4}-${FECHA_VOLCADO:4:2}-${FECHA_VOLCADO:6:2}"

HORIZONTE=$("$B/bin/espejosql" "SELECT max(ts)::date FROM ohlcv WHERE interval='1min'" 2>&1 | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' | head -1)
[ -n "$HORIZONTE" ] || { echo "NO MEDIDO: el espejo no devolvio su horizonte de datos (max(ts) de ohlcv 1min)"; exit 2; }
[ "$HORIZONTE" = "$FECHA_FMT" ] || {
  echo "NO MEDIDO: el espejo acaba el $HORIZONTE y el volcado disponible es del $FECHA_FMT. Compararlos mediria el par equivocado, y un ROJO ahi acusaria al espejo de un fallo del instrumento"
  exit 2
}

# --- el MANIFIESTO, derivado del volcado en cada pasada. 3.1 s medidos sobre 118 MB.
MANIF=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero del manifiesto"; exit 2; }
trap 'rm -f "$MANIF"' EXIT
zcat "$VOLCADO" 2>/dev/null | awk '
  /^COPY public\./ { t=$2; sub(/^public\./,"",t); n=0
                     while ((getline line) > 0) { if (line == "\\.") break; n++ }
                     if (n > 0) print t, n }
' > "$MANIF"
N_TABLAS=$(grep -c . "$MANIF" || true)
[ "${N_TABLAS:-0}" -ge 30 ] || {
  echo "NO MEDIDO: el volcado $VOLCADO solo rindio ${N_TABLAS:-0} tablas con datos. Un manifiesto asi de corto no distingue un espejo sano de uno roto"
  exit 2
}

# --- A · fidelidad, tabla por tabla, con count(*) exacto y no con reltuples.
CONSULTA=$(awk '{printf "%sSELECT %s%s%s AS t, count(*) AS n FROM %s", (NR>1 ? " UNION ALL " : ""), "'"'"'", $1, "'"'"'", $1}' "$MANIF")
CRUDO=$("$B/bin/espejosql" "$CONSULTA" 2>&1)
REAL=$(printf '%s\n' "$CRUDO" | grep -E '^[a-z_][a-z0-9_]*\|[0-9]+$' | sort)
N_REAL=$(printf '%s\n' "$REAL" | grep -c . || true)
[ "${N_REAL:-0}" -eq "$N_TABLAS" ] || {
  echo "NO MEDIDO: se pidieron $N_TABLAS conteos al espejo y volvieron ${N_REAL:-0}. La lista llego incompleta y juzgar sobre ella seria inventar: $(printf '%s' "$CRUDO" | head -1 | cut -c1-100)"
  exit 2
}

CORTAS=""; SOBRAN=""; CUADRAN=0; FALTAN_FILAS=0
while read -r t esperadas; do
  reales=$(printf '%s\n' "$REAL" | awk -F'|' -v k="$t" '$1==k {print $2}')
  [ -n "$reales" ] || continue
  if [ "$reales" -eq "$esperadas" ]; then CUADRAN=$((CUADRAN+1))
  elif [ "$reales" -lt "$esperadas" ]; then
    CORTAS="${CORTAS:+$CORTAS }$t($reales/$esperadas)"
    FALTAN_FILAS=$((FALTAN_FILAS + esperadas - reales))
  else
    SOBRAN="${SOBRAN:+$SOBRAN }$t($reales/$esperadas)"
  fi
done < "$MANIF"

# --- C · control positivo: si NINGUNA cuadra, lo roto es la comparacion.
[ "$CUADRAN" -gt 0 ] || {
  echo "NO MEDIDO: CONTROL POSITIVO ROTO -- ninguna de las $N_TABLAS tablas cuadra con el volcado. Antes de acusar al espejo hay que descartar que lo roto sea la comparacion"
  exit 2
}

TOTAL=$(awk '{s+=$2} END {print s+0}' "$MANIF")
if [ -n "$CORTAS" ]; then
  echo "ROJO: la restauracion del espejo es CORTA en $(printf '%s' "$CORTAS" | wc -w) de $N_TABLAS tablas, $FALTAN_FILAS filas menos que el volcado $(basename "$VOLCADO"): $CORTAS" | cut -c1-400
  exit 1
fi

AVISO=""
[ -n "$SOBRAN" ] && AVISO=" · CON MAS FILAS QUE EL VOLCADO, informado y no gateado -- el espejo se ESCRIBE (los tests de persistencia corren contra el), asi que esto dice que ya no es una copia: $(printf '%s' "$SOBRAN" | wc -w) tablas"
echo "el espejo reproduce el volcado $(basename "$VOLCADO"): $CUADRAN de $N_TABLAS tablas cuadran al bit y $TOTAL filas en total, con el manifiesto DERIVADO del volcado en esta misma pasada y no escrito a mano$AVISO"
