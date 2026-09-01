#!/bin/bash
# K81  EL BLOQUE DE LIQUIDACIONES DE LA SESION DIARIA NO PUEDE ESTAR OSCURO EN SILENCIO.
#
# LA VIA, REPRODUCIDA ANTES QUE LA CIFRA. Es la quinta vez seguida y las cuatro anteriores
# decidieron donde gatea el check.
#   · long_liq_usd/short_liq_usd NO llegan a la pantalla -- grep en static/app.js: 0 hits --
#     pero SI llegan a ai_context.py:332, o sea al contexto que lee la IA. No es solo dato.
#   · El bloque es FAIL-CLOSED POR DISENO y no un fallo de escritura: daily_agg.py:198-202
#     escribe las sumas y las cuatro columnas de procedencia SOLO si
#     liquidation_history_observation (metrics.py:252) devuelve algo.
#
# LA CAUSA ES UNA SOLA Y ESTA EN GIT, no dos como parecia. El commit 4e61265 del 2026-08-12
# -"fix: make daily evidence historically reproducible"- introdujo A LA VEZ la funcion
# liquidation_history_observation y el gate complete_liquidations. La ultima sesion con dato
# es la 2026-08-10, escrita antes de que eso llegara.
#   Y LO QUE PARECIA UN SEGUNDO FALLO NO LO ES: las cuatro columnas de procedencia
#   -liquidation_coverage_version, _observed_at, _source_start_at, _source_cutoff_at- estan
#   CONECTADAS y se escriben en el mismo INSERT (daily_agg.py:214-215 y 280-283). Las anadio
#   sql/migrations/20260814_pr24_...sql, del 2026-08-14, CUATRO DIAS DESPUES de que el dato
#   parara. Nunca tuvieron ocasion. "NUNCA escrito" y "dejo de escribirse" son aqui EL MISMO
#   suceso visto por columnas de distinta edad, y no hacen falta dos causas.
#
# POR QUE EL GATE NO PASA NUNCA, y no es una carrera: es aritmetica.
#   session_bounds (metrics.py) va de 09:30 Nueva York a 09:30 NY, o sea 24 h que en verano
#   son [D-1 13:30Z, D 13:30Z]. NO es de medianoche a medianoche, y suponerlo es el error de
#   instrumento que ya esta escrito en el BLOQUE 19.
#   El latido publica la ventana del ULTIMO barrido: ingest.py:790 fija
#   start_history = cutoff - 26 h, y metrics.py exige source_start <= required_start Y
#   source_cutoff >= required_end. Una ventana de 26 h solo cubre una sesion de 24 h si el
#   cutoff cae en [D 13:30Z, D 15:30Z] -- dos horas al dia.
#   MEDIDO el 2026-09-01: el latido esta PERFECTO -status ok, fresco, missing_symbols vacio,
#   accepted==returned=559, reason=complete_observation, los 3 simbolos- y aun asi cubre
#   [08-30 22:30Z, 09-01 00:30Z] contra una sesion que empieza el 08-30 a las 13:30Z:
#   cubre_inicio = FALSO. Y el servicio daily corrio a las 00:06:44Z, que no cae en la banda.
#   O sea: con la planificacion actual el gate NO PUEDE pasar, no es que falle a veces.
#
# LO QUE NO ES, medido para no arreglar donde no duele:
#   · NO es el colector. liquidations(5min) esta viva y al dia -max(ts) del 2026-08-31 23:00Z-
#     y el latido sale 'ok' cada ciclo. Lo que murio es el CONTRATO, no el dato.
#   · NO comparte causa con cvd_swing_90d, aunque comparta fecha. Las dos series se cruzan el
#     2026-08-10 EN DIRECCIONES OPUESTAS: long_liq_usd deja de escribirse ese dia y
#     session_coverage_version EMPIEZA ese dia (22 sesiones, 66 filas). Disparador comun -el
#     mismo endurecimiento- y DOS mecanismos. Ademas cvd_swing_90d se cura SOLO: exige
#     CVD_LOOKBACK_SESSIONS+CVD_SIGNAL_WINDOW = 93 sesiones completas y solo hay 22, asi que
#     se enciende hacia el 2026-11-11. Escribirle codigo seria trabajar contra el calendario.
#
# LOS TRES BRAZOS. Y ANTES, LA CORRECCION QUE ESTE CHECK SE HIZO A SI MISMO, porque es la
# parte que mas cuesta reaprender: su PRIMERA version exigia el bloque a las 30 sesiones
# elegibles de los ultimos 30 dias y las 4 columnas a las 30 filas viejas. Eso era un ROJO
# INARREGLABLE: daily_agg no recalcula una sesion ya escrita, asi que las 21 en NULL no se
# llenan solas, y rellenarlas o borrarlas seria mutar produccion -PUERTA 1-. Un rojo que no
# se puede apagar ensena a ignorar los que si, que es la enfermedad que este arnes combate.
# La regla correcta la dio K25: separar lo ELEGIBLE DENTRO DE UN CONTRATO VIGENTE de la
# DEUDA PARADA que nunca tuvo contrato. Aqui el corte no se inventa, se lee del repo: las
# cuatro columnas nacieron el 2026-08-14 con sql/migrations/20260814_pr24_*.sql.
#   A · EL MECANISMO VIVO, no el residuo. La sesion elegible MAS RECIENTE tiene que traer su
#       bloque. Es la unica pregunta que el pipeline puede contestar hoy y la que se pone
#       VERDE al dia siguiente de desplegar el arreglo. El ELEGIBLE SALE DE UN INSTRUMENTO
#       EXTERNO -leccion de K25-: NO "de las filas que llegaron, cuantas traen el bloque"
#       -eso mide el conjunto que SOBREVIVE- sino "de las sesiones que la tabla CRUDA de
#       liquidaciones cubre entera, cual es la ultima". El inventario sale de liquidations,
#       que este check no audita, y no de daily_session_agg, que es el sujeto.
#   B · PROCEDENCIA, y solo donde hubo contrato. Una fila con sumas y sin las cuatro columnas
#       afirma un total sin decir de donde salio ni que arco cubre. Se exige a las sesiones
#       del 2026-08-14 en adelante, que es cuando las columnas existen. Las 30 filas de
#       08-01..08-10 se INFORMAN como deuda parada en cada pasada y no gatean: son anteriores
#       a las columnas y son, exactamente, las que impiden validar la constraint.
#   C · CONTROL POSITIVO Y CASO VACIO. Si la tabla cruda no cubre entera NI UNA sesion
#       elegible, no hay nada que exigir y esto sale NOMED, no VERDE ni ROJO.
#
# LO QUE NO SE TOCA Y VA A LA MESA DE ALEJANDRO: la constraint
# daily_session_agg_pr24_liquidation_coverage_check sigue NOT VALID, y validarla es ALTER
# TABLE sobre la base viva -PUERTA 1- y ADEMAS FALLARIA HOY, porque esas 30 filas viejas la
# incumplen. El orden correcto es arreglar las filas primero y validar despues; las dos
# mitades juntas, como en K75. Aqui solo se MIDE y se declara.
#
# DE QUE ARBOL: los tres brazos miden 140 por prodsql.
#
# Se comprueba con: bash harness/checks/K81-el-bloque-oscuro-de-la-sesion.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"

# EL INVENTARIO ELEGIBLE, derivado de la tabla CRUDA y no del sujeto. Una sesion es elegible
# si liquidations(5min) cubre su ventana ENTERA -de 09:30 NY a 09:30 NY-, medido por que la
# serie cruda empieza antes del inicio y acaba despues del final.
SALIDA=$("$B/bin/prodsql" "
WITH crudo AS (
  SELECT min(ts) AS desde, max(ts) AS hasta FROM liquidations WHERE interval='5min'
), sesiones AS (
  SELECT d::date AS session_date,
         (d::date - 1 + time '09:30') AT TIME ZONE 'America/New_York' AS ini,
         (d::date     + time '09:30') AT TIME ZONE 'America/New_York' AS fin
  FROM generate_series(
         ((now() AT TIME ZONE 'UTC')::date - 30),
         ((now() AT TIME ZONE 'UTC')::date - 1),
         interval '1 day') d
), elegibles AS (
  SELECT s.session_date FROM sesiones s, crudo c
  WHERE c.desde <= s.ini AND c.hasta >= s.fin AND s.fin <= now()
), ultima AS (SELECT max(session_date) AS d FROM elegibles)
SELECT
  (SELECT count(*) FROM elegibles),
  coalesce((SELECT d::text FROM ultima), '-'),
  coalesce((SELECT count(*) FROM daily_session_agg a, ultima u
            WHERE a.session_date = u.d AND a.long_liq_usd IS NOT NULL), 0),
  coalesce((SELECT count(*) FROM daily_session_agg a, ultima u WHERE a.session_date = u.d), 0),
  (SELECT count(*) FROM daily_session_agg
     WHERE session_date >= date '2026-08-14'
       AND long_liq_usd IS NOT NULL AND liquidation_coverage_version IS NULL),
  (SELECT count(*) FROM daily_session_agg
     WHERE session_date < date '2026-08-14'
       AND long_liq_usd IS NOT NULL AND liquidation_coverage_version IS NULL)
" 2>/dev/null | tr -d ' ' | head -1)

case "$SALIDA" in
  [0-9]*\|*\|[0-9]*\|[0-9]*\|[0-9]*\|[0-9]*) : ;;
  *) echo "NO MEDIDO: 140 no contesto al inventario de sesiones: $(printf '%s' "$SALIDA" | head -c 120)"; exit 2 ;;
esac
IFS='|' read -r ELEGIBLES ULTIMA ULT_CON_BLOQUE ULT_FILAS SIN_PROC_VIVAS DEUDA_PARADA <<EOF
$SALIDA
EOF

# --- C · control positivo y caso vacio, ANTES del veredicto.
[ "$ELEGIBLES" -gt 0 ] || {
  echo "NO MEDIDO: 0 sesiones elegibles en los ultimos 30 dias -- la tabla cruda liquidations no cubre entera ninguna ventana de 09:30 NY a 09:30 NY. Sin inventario externo no hay nada que exigir, y contar sobre el conjunto que sobrevive seria medir el sujeto contra si mismo"
  exit 2
}

# --- VEREDICTO
FALLOS=""
[ "$ULT_FILAS" -gt 0 ] || {
  echo "NO MEDIDO: la sesion elegible mas reciente ($ULTIMA) todavia no tiene NI UNA fila en daily_session_agg. El servicio daily aun no la ha calculado, asi que no hay nada que exigirle"
  exit 2
}
[ "$ULT_CON_BLOQUE" -gt 0 ] ||
  FALLOS="la sesion elegible mas reciente ($ULTIMA) tiene $ULT_FILAS filas y NINGUNA con long_liq_usd, con la tabla cruda cubriendo su ventana entera: el contexto de la IA recibe NULL donde hubo liquidaciones medidas"
[ "$SIN_PROC_VIVAS" -gt 0 ] &&
  FALLOS="${FALLOS:+$FALLOS · }$SIN_PROC_VIVAS filas del 2026-08-14 en adelante tienen sumas SIN procedencia: afirman un total sin decir de donde salio ni que arco cubre"

DEUDA=""
[ "$DEUDA_PARADA" -gt 0 ] && DEUDA=" · DEUDA PARADA, informada y NO gateada: $DEUDA_PARADA filas anteriores al 2026-08-14 tienen sumas sin procedencia porque las columnas aun no existian. Son las que impiden validar daily_session_agg_pr24_liquidation_coverage_check, que sigue NOT VALID; arreglarlas es escribir en produccion, o sea PUERTA de Alejandro"

# Igual que en K77 y K80: el ROJO distingue "el arreglo no funciona" de "aun no le ha tocado".
# Aqui hay un dia de espera INEVITABLE aunque se despliegue ya, porque la sesion mas reciente
# se escribio ANTES y daily_agg no la recalcula. Decirlo evita que manana se lea como fallo.
ARBOL_OK=0
grep -q 'liq_start_history' "$REPO/app/ingest.py" 2>/dev/null && ARBOL_OK=1
if [ -n "$FALLOS" ]; then
  [ "$ARBOL_OK" = 1 ] && FALLOS="$FALLOS · EL ARBOL YA LLEVA LA VENTANA PROPIA (liq_start_history): esta sesion se escribio antes y daily_agg no la recalcula, asi que esto se apaga solo con la PRIMERA sesion que se cierre despues de desplegar"
  echo "ROJO: $FALLOS$DEUDA"
  exit 1
fi

echo "la sesion elegible mas reciente ($ULTIMA, de $ELEGIBLES cubiertas enteras por la tabla CRUDA) trae su bloque de liquidaciones en $ULT_CON_BLOQUE de $ULT_FILAS filas, y ninguna fila con contrato vigente afirma un total sin procedencia$DEUDA"
