#!/bin/bash
# K06  las tablas de visibilidad tienen que seguir ESCRIBIENDO. ROJO hoy: dos pararon
# el 2026-08-20 y nadie se entero. Umbral: 6 h sin escribir es paro.
#
# Las dos columnas son verified_visible_at, que es CUANDO SE ESCRIBIO el certificado.
# Antes esta consulta miraba source_finalized_at en outcome_final, que es cuando se
# finalizo el outcome de origen, no cuando se certifico. Medido el 2026-08-25 justo
# despues de desplegar 5d90ee7: verified_visible_at iba 9 segundos por detras de
# now() -la tabla escribia 500 filas cada 40 s- mientras source_finalized_at seguia
# en el 21-ago porque estaba drenando 206884 outcomes atrasados. Con la columna
# vieja el check decia "parada 116h" de una tabla que estaba escribiendo delante de
# sus narices: medir el avance del atasco no es medir si la tabla escribe.
# Salida 2 = NO MEDIDO. Se comprueba PRIMERO que el canal responde: si no, un error
# de transporte se leeria como "tabla parada", que es una medicion falsa.
#
# ---------------------------------------------------------------------------------
# LO QUE SE ARREGLO EL 2026-09-07, medido por K97 y confirmado a mano.
#
# 1 · UNA TABLA VACIA PASABA POR SANA. La consulta era un `HAVING max(...) < now()-6h`.
#     Sobre una tabla SIN NI UNA FILA, `max()` es NULL, el HAVING no casa, no vuelve
#     ninguna fila... y eso era exactamente lo mismo que devuelve una tabla que escribe
#     al dia. O sea: **una tabla que no ha escrito NUNCA salia VERDE**, que es justo el
#     estado que este check existe para cazar, llevado al extremo.
#     Hoy es LATENTE y no vivo -medido: 1 194 975 y 100 452 filas, ultima escritura hace
#     0 h-, asi que el verde de hoy esta GANADO. Se arregla igual: un check que solo dice
#     la verdad mientras el sistema funcione no es un check.
#
# 2 · SU LINEA DE VERDE NO LLEVABA DENOMINADOR. Decia «las tablas de visibilidad escriben
#     dentro de 6 h», la MISMA frase sobre 1.19 M filas que sobre cero, y desde fuera no
#     se distinguen. Ahora publica, POR TABLA, cuantas filas tiene y de cuando es su
#     ultima escritura. La regla de la casa: toda cifra dice sobre cuantos elementos corrio.
#
# La consulta pasa a devolver UNA FILA POR TABLA -siempre, tenga datos o no- en vez de solo
# las que fallan. Asi el vacio es una respuesta y no un silencio: `filas=0` se ve.
set -uo pipefail
B=/srv/coinanalyze/harness
UMBRAL_H=${K06_UMBRAL_H:-6}
TABLAS="signal_outcome_final_visibility signal_research_bundle_visibility"

vivo=$("$B/bin/prodsql" "SELECT 'canal_ok'" 2>/dev/null | tr -d ' ' | head -1)
[ "$vivo" = "canal_ok" ] || { echo "NO MEDIDO: prodsql no responde"; exit 2; }

# UNA FILA POR TABLA, siempre: nombre|filas|horas desde la ultima escritura (-1 si no hay).
sql=""
for t in $TABLAS; do
  [ -n "$sql" ] && sql="$sql
UNION ALL"
  sql="$sql
SELECT '$t'||'|'||count(*)||'|'||COALESCE(round(extract(epoch FROM now()-max(verified_visible_at))/3600)::text,'-1')
  FROM $t"
done
salida=$("$B/bin/prodsql" "$sql" 2>/dev/null | sed 's/^ *//' | grep -E '^[a-z_]+\|[0-9]+\|' || true)

# CERO FILAS DE RESPUESTA NO ES CERO DEFECTOS: es que no se pudo preguntar. Un `count(*)`
# siempre contesta -aunque sea 0-, asi que si no vuelve una fila por tabla, la medicion no
# se hizo. Antes esto no se distinguia del caso sano y era la mitad del defecto.
n_resp=$(printf '%s\n' "$salida" | grep -c . || true)
n_tab=$(printf '%s\n' "$TABLAS" | wc -w)
if [ "$n_resp" -ne "$n_tab" ]; then
  echo "NO MEDIDO: pedi una fila por cada una de las $n_tab tablas y volvieron $n_resp."
  echo "  un count(*) siempre contesta, asi que esto no es una tabla vacia: es que la consulta no se hizo."
  exit 2
fi

paradas=""; vacias=""; detalle=""
while IFS='|' read -r t filas horas; do
  [ -n "$t" ] || continue
  detalle="$detalle $t($filas filas, ultima escritura hace ${horas}h)"
  if [ "$filas" -eq 0 ]; then
    # UNA TABLA VACIA NO ESCRIBE. Antes salia por el mismo sitio que una tabla al dia.
    vacias="$vacias $t"
  elif [ "${horas:--1}" -ge "$UMBRAL_H" ]; then
    paradas="$paradas $t(${horas}h)"
  fi
done <<EOF
$salida
EOF

echo "medido sobre $n_tab tabla(s), umbral $UMBRAL_H h:$detalle"
if [ -n "${vacias// /}" ]; then
  echo "ROJO: tabla(s) de visibilidad SIN NI UNA FILA:$vacias"
  echo "  una tabla que no ha escrito nunca no es una tabla al dia. Antes las dos salian por el mismo sitio."
  exit 1
fi
[ -z "${paradas// /}" ] || { echo "ROJO: paradas:$paradas"; exit 1; }
echo "VERDE: las $n_tab tablas de visibilidad escriben dentro de $UMBRAL_H h"
exit 0
