#!/bin/bash
# K81  EL BLOQUE DE LIQUIDACIONES DE LA SESION DIARIA NO PUEDE ESTAR OSCURO EN SILENCIO,
#      NI DESAPARECER DESPUES DE HABERSE ESCRITO.
#
# LA VIA, REPRODUCIDA ANTES QUE LA CIFRA. Es la quinta vez seguida y las cuatro anteriores
# decidieron donde gatea el check.
#   · long_liq_usd/short_liq_usd NO llegan a la pantalla -- grep en static/app.js: 0 hits --
#     pero SI llegan a ai_context.py:332, o sea al contexto que lee la IA. No es solo dato.
#   · El bloque es FAIL-CLOSED POR DISENO y no un fallo de escritura: daily_agg.py:198-202
#     escribe las sumas y las cuatro columnas de procedencia SOLO si
#     liquidation_history_observation (metrics.py:252) devuelve algo.
#
# LA CAUSA ES UNA SOLA Y ESTA EN GIT, no dos como parecia, y son TRES COMMITS EN SECUENCIA en
# 24 h -- medido con git y corregido dos veces, porque la primera version de esta cabecera
# fechaba la migracion por el NOMBRE del fichero, que es un error de instrumento de manual:
#   0df80b2  2026-08-11  introduce liquidation_history_observation
#   610f27b  2026-08-11 23:51 -0600 (= 08-12 05:51Z)  anade sql/migrations/20260814_pr24_*.sql
#            -el 20260814 es el NOMBRE, no la fecha- y un complete_liquidations con OTRA
#            definicion: liquidation_start is not None and liquidation_end is not None
#   4e61265  2026-08-12  lo cambia a "liquidation_observation is not None", QUE ES LA FORMA
#            QUE CORRE HOY
# La ultima sesion con dato es la 2026-08-10: UN DIA antes, no cuatro.
#   Y LO QUE PARECIA UN SEGUNDO FALLO NO LO ES: las cuatro columnas de procedencia
#   -liquidation_coverage_version, _observed_at, _source_start_at, _source_cutoff_at- estan
#   CONECTADAS y se escriben en el mismo INSERT (daily_agg.py:214-215 y 280-283). Llegaron con
#   610f27b, o sea UN DIA despues de que el dato parara y en el MISMO endurecimiento que puso
#   el gate. Nunca tuvieron ocasion. "NUNCA escrito" y "dejo de escribirse" son aqui EL MISMO
#   suceso visto por columnas de distinta edad, y no hacen falta dos causas.
#
# EL REPARTO QUE MANDA, y es el que este check habia leido MAL hasta el 2026-09-01T17:xxZ.
# daily_agg.py:302-308, medido en el release de 140:
#       for offset in range(lookback):            # lookback = DAILY_LOOKBACK_DAYS = 13
#           ...
#           if exists and offset >= 2: continue
# O sea: de las trece sesiones del backfill, SOLO LAS DOS MAS RECIENTES -offset 0 y 1- se
# REESCRIBEN cuando ya existen; de la tercera hacia atras la fila EXISTENTE se salta y queda
# CONGELADA con el valor que tuviera. La version anterior de esta cabecera afirmaba que "las
# otras DOCE se reescriben a NULL en cada pasada, para siempre", y es FALSO. La consecuencia
# es mas dura, no mas blanda: lo que una sesion tenga en su ULTIMA reescritura es lo que
# tendra PARA SIEMPRE, porque nadie la vuelve a mirar.
#   Comprobado con: bin/prod "sed -n '299,313p' /opt/coinalyze/current/app/daily_agg.py"
#   Y EN LOS DATOS, que es donde se ve el reparto sin leer codigo: cada sesion lleva como
#   ultima escritura la ultima pasada horaria antes de su tercer dia --
#     08-30 -> updated_at 2026-09-01 13:00:49Z      08-29 -> updated_at 2026-08-31 13:00:49Z
#   que son las 13:00:45 de la pasada horaria justo antes de las 13:30Z en que cambia el
#   cierre de sesion. Comprobado con: prodsql sobre daily_session_agg agrupando por updated_at
#
# LA ARITMETICA COMPLETA, que es lo que hacia falta y no estaba escrito en ningun sitio.
#   session_bounds (metrics.py) va de 09:30 Nueva York a 09:30 NY: la sesion D ocupa
#   [D-1 13:30Z, D 13:30Z] en verano. NO es de medianoche a medianoche, y suponerlo es el
#   error de instrumento que ya esta escrito en el BLOQUE 19.
#   La pasada de daily es HORARIA y alineada: daily_agg.py:975-978,
#   seconds_until_aligned_run(now, 3600, 45) -> corre a HH:00:45. Los updated_at a HH:00:49
#   son esa pasada con ~4 s de trabajo.
#   El gate exige source_start <= inicio_de_sesion Y source_cutoff >= fin_de_sesion, y el
#   latido publica source_start = cutoff - LIQUIDATION_HISTORY_LOOKBACK_HOURS (ingest.py:450;
#   ingest.py:827). La anchura que este check informa NO se lee de ahi: se lee de lo que el
#   pipeline declaro en produccion, en liquidation_source_start_at/_cutoff_at.
#   ENTONCES, para que la sesion D sobreviva a su ULTIMA reescritura -- la pasada de las
#   (D+2) 13:00:45, justo antes de que caiga a offset 2 y se congele -- hace falta
#       W >= (D+2) 13:00:45 - (D-1) 13:30:00 = 71 h 30 min 45 s
#   y en la sesion de 25 h del cambio de hora de otono -- la que empieza en EDT y acaba en
#   EST, 2026-11-01 -- el mismo calculo da 72 h 30 min 45 s, que es el peor caso del ano.
#   CON W = 50 h NO SE LLEGA: la sesion D se escribe con bloque mientras la pasada cae en
#   [D 13:30Z, (D+1) 15:30Z], y la PRIMERA pasada posterior -- las (D+1) 16:00:45 -- la
#   reescribe a NULL con el mismo ON CONFLICT DO UPDATE. Cuando a las (D+2) 13:30Z se congela,
#   se congela en NULL. Por eso el corpus NO CRECE: en todo momento hay exactamente UNA sesion
#   con bloque, la de offset 0, y ninguna historia detras.
#   El 74 que arreglaria esto no es prudencia: es el primer numero redondo por encima de las
#   72 h 30 min del peor caso, con 1 h 29 min de margen para que un desplazamiento del
#   planificador no devuelva el fallo.
#
# LO QUE NO ES, medido para no arreglar donde no duele:
#   · NO es el colector. liquidations(5min) esta viva y al dia y el latido sale 'ok' cada
#     ciclo. Lo que murio es el CONTRATO, no el dato.
#   · NO comparte causa con cvd_swing_90d, aunque comparta fecha. Las dos series se cruzan el
#     2026-08-10 EN DIRECCIONES OPUESTAS: long_liq_usd deja de escribirse ese dia y
#     session_coverage_version EMPIEZA ese dia (22 sesiones, 66 filas). Disparador comun -el
#     mismo endurecimiento- y DOS mecanismos. Ademas cvd_swing_90d se cura SOLO: exige
#     CVD_LOOKBACK_SESSIONS+CVD_SIGNAL_WINDOW = 93 sesiones completas y solo hay 22, asi que
#     se enciende hacia el 2026-11-11. Escribirle codigo seria trabajar contra el calendario.
#
# LOS BRAZOS, Y POR QUE EL SUJETO YA NO ES UNA FECHA. Las dos versiones anteriores de este
# check se corrigieron a si mismas y esta es la tercera correccion, la que mas importa:
#   1a  exigia el bloque a las 30 sesiones de los ultimos 30 dias -> ROJO INARREGLABLE, porque
#       rellenar filas viejas es mutar produccion (PUERTA 1). Un rojo que no se puede apagar
#       ensena a ignorar los que si.
#   2a  exigia el bloque a "la sesion elegible MAS RECIENTE" derivada de la tabla cruda. Eso
#       la dejaba UNA SESION POR DETRAS de la que daily_agg alcanza a llenar, asi que el
#       veredicto CAMBIABA CON LA HORA DEL DIA: VERDE de 00:00Z a 15:30Z y ROJO despues, sin
#       que nada del sistema hubiera cambiado. Un rojo que va y viene con el reloj es la misma
#       enfermedad que el rojo inapagable: ensena a ignorar los rojos.
#   3a  EL SUJETO SALE DEL REPARTO DE daily_agg, NO DE UNA FECHA NI DEL RELOJ. Las dos
#       preguntas se hacen sobre posiciones -- offset 0 y offset 2 del cierre de sesion -- que
#       se mueven CON el sistema, no contra el. El veredicto no puede oscilar porque el sujeto
#       y el que lo llena avanzan al mismo paso.
#
#   A1 · EL MECANISMO VIVO (offset 0, la sesion que acaba de cerrar). Si daily ya la visito
#        desde que cerro -- updated_at >= fin de sesion -- tiene que traer el bloque en TODAS
#        sus filas. Si aun no la ha visitado, se DECLARA y no se juzga: no hay nada que
#        exigirle todavia. Este brazo es el CONTROL POSITIVO: con el diseno actual la sesion
#        de offset 0 SIEMPRE esta cubierta, asi que si se pone rojo es que el ingest se rompio
#        de verdad.
#   A2 · LA PERMANENCIA (offset 2, la primera que daily_agg YA NO REESCRIBE). Es la pregunta
#        de producto y la que hoy esta roja: si la sesion que acaba de congelarse no lleva su
#        bloque, el corpus la perdio PARA SIEMPRE y no habra historia diaria de liquidaciones.
#        No se juzga si es anterior al 2026-08-14 -- ahi no habia contrato -- ni si la tabla
#        CRUDA no cubre su arco entero.
#   B  · PROCEDENCIA, y solo donde hubo contrato. Una fila con sumas y sin las cuatro columnas
#        afirma un total sin decir de donde salio ni que arco cubre. Se exige del 2026-08-14
#        en adelante. Las 30 filas de 08-01..08-10 se INFORMAN como deuda parada y no gatean.
#   C  · CASO VACIO. Si la tabla cruda no cubre entera ninguna de las dos sesiones del foco, no
#        hay inventario externo con el que exigir nada y esto sale NOMED, no VERDE ni ROJO.
#
# EL INVENTARIO SALE DE UN INSTRUMENTO EXTERNO -leccion de K25-: la tabla CRUDA liquidations,
# que este check no audita, y NO de daily_session_agg, que es el sujeto.
#
# LO QUE NO SE TOCA Y VA A LA MESA DE ALEJANDRO: la constraint
# daily_session_agg_pr24_liquidation_coverage_check sigue NOT VALID, y validarla es ALTER
# TABLE sobre la base viva -PUERTA 1- y ADEMAS FALLARIA HOY, porque esas 30 filas viejas la
# incumplen. El orden correcto es arreglar las filas primero y validar despues; las dos
# mitades juntas, como en K75. Aqui solo se MIDE y se declara.
#
# DE QUE ARBOL: todo lo que gatea sale de 140 por prodsql. La anchura de ventana que se
# informa NO se lee del arbol: se lee de lo que el propio pipeline DECLARO en
# liquidation_source_start_at/_cutoff_at, o sea de produccion.
#
# Se comprueba con: bash harness/checks/K81-el-bloque-oscuro-de-la-sesion.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"

# EL FOCO son las posiciones del reparto de daily_agg.py:302-308 respecto del cierre de sesion
# (latest_closed_session_date, daily_agg.py:45-49): offset 0 se reescribe, offset 2 ya no.
SALIDA=$("$B/bin/prodsql" "
WITH cierre AS (
  SELECT CASE WHEN (now() AT TIME ZONE 'America/New_York')::time >= time '09:30'
              THEN (now() AT TIME ZONE 'America/New_York')::date
              ELSE (now() AT TIME ZONE 'America/New_York')::date - 1 END AS l
), crudo AS (
  SELECT min(ts) AS desde, max(ts) AS hasta FROM liquidations WHERE interval='5min'
), foco AS (
  SELECT off, (SELECT l FROM cierre) - off AS sd FROM generate_series(0,2) off
), arcos AS (
  SELECT f.off, f.sd,
         (f.sd - 1 + time '09:30') AT TIME ZONE 'America/New_York' AS ini,
         (f.sd     + time '09:30') AT TIME ZONE 'America/New_York' AS fin
  FROM foco f
), juicio AS (
  SELECT a.off, a.sd, a.fin,
         (c.desde <= a.ini AND c.hasta >= a.fin)::int AS cubre,
         (SELECT count(*) FROM daily_session_agg d WHERE d.session_date=a.sd) AS filas,
         (SELECT count(d.long_liq_usd) FROM daily_session_agg d WHERE d.session_date=a.sd) AS bloque,
         coalesce((SELECT (max(d.updated_at) >= a.fin)::int FROM daily_session_agg d
                   WHERE d.session_date=a.sd), 0) AS visto
  FROM arcos a, crudo c
)
SELECT (SELECT l FROM cierre),
       (SELECT cubre FROM juicio WHERE off=0), (SELECT filas FROM juicio WHERE off=0),
       (SELECT bloque FROM juicio WHERE off=0), (SELECT visto FROM juicio WHERE off=0),
       (SELECT sd FROM juicio WHERE off=2), (SELECT cubre FROM juicio WHERE off=2),
       (SELECT filas FROM juicio WHERE off=2), (SELECT bloque FROM juicio WHERE off=2),
       (SELECT count(*) FROM daily_session_agg
          WHERE session_date >= date '2026-08-14'
            AND long_liq_usd IS NOT NULL AND liquidation_coverage_version IS NULL),
       (SELECT count(*) FROM daily_session_agg
          WHERE session_date < date '2026-08-14'
            AND long_liq_usd IS NOT NULL AND liquidation_coverage_version IS NULL),
       coalesce((SELECT round((extract(epoch FROM max(liquidation_source_cutoff_at
                   - liquidation_source_start_at))/3600)::numeric, 2)::text
                 FROM daily_session_agg WHERE liquidation_source_start_at IS NOT NULL), '-')
" 2>/dev/null | tr -d ' ' | head -1)

[ "$(printf '%s' "$SALIDA" | tr -cd '|' | wc -c)" = "11" ] || {
  echo "NO MEDIDO: 140 no contesto al foco de sesiones: $(printf '%s' "$SALIDA" | head -c 120)"
  exit 2
}
IFS='|' read -r L S0_CUBRE S0_FILAS S0_BLOQUE S0_VISTO S2 S2_CUBRE S2_FILAS S2_BLOQUE \
                SIN_PROC_VIVAS DEUDA_PARADA VENTANA <<EOF
$SALIDA
EOF

# --- C · sin inventario externo no hay nada que exigir.
[ "$S0_CUBRE" = 1 ] || [ "$S2_CUBRE" = 1 ] || {
  echo "NO MEDIDO: la tabla cruda liquidations no cubre entero el arco -09:30 NY a 09:30 NY- ni de la sesion viva ($L) ni de la recien congelada ($S2). Sin inventario externo no hay nada que exigir, y contar sobre el conjunto que sobrevive seria medir el sujeto contra si mismo"
  exit 2
}

# El texto del VERDE se compone SOLO con los brazos que de verdad se juzgaron. Un brazo que
# no tuvo sujeto se DECLARA; afirmar de el que paso seria decir algo que no se midio.
FALLOS=""; DECLARA=""; VERDES=""; JUZGADO=0

# --- A1 · el mecanismo vivo. Control positivo: con el diseno actual esto SIEMPRE esta cubierto.
if [ "$S0_CUBRE" = 1 ]; then
  if [ "$S0_FILAS" = 0 ] || [ "$S0_VISTO" = 0 ]; then
    DECLARA="${DECLARA} · A1 NO JUZGADO: la pasada horaria de daily aun no ha visitado la sesion viva ($L) desde que cerro"
  else
    JUZGADO=1
    if [ "$S0_BLOQUE" = "$S0_FILAS" ]; then
      VERDES="la sesion viva ($L) trae su bloque en $S0_BLOQUE de $S0_FILAS filas"
    else
      FALLOS="la sesion VIVA ($L, offset 0, la que daily reescribe cada hora) trae el bloque en $S0_BLOQUE de $S0_FILAS filas: el contexto de la IA recibe NULL donde hubo liquidaciones medidas"
    fi
  fi
fi

# --- A2 · la permanencia. Lo que esta sesion tenga ya no lo cambia nadie.
if [ "$S2_CUBRE" = 1 ] && [[ "$S2" > "2026-08-13" ]]; then
  if [ "$S2_FILAS" = 0 ]; then
    DECLARA="${DECLARA} · A2 NO JUZGADO: la sesion recien congelada ($S2) no tiene ninguna fila"
  else
    JUZGADO=1
    if [ "$S2_BLOQUE" = "$S2_FILAS" ]; then
      VERDES="${VERDES:+$VERDES y }la recien congelada ($S2) lo conserva en $S2_BLOQUE de $S2_FILAS"
    else
      FALLOS="${FALLOS:+$FALLOS · }la sesion $S2 acaba de salir de la ventana de reescritura de daily_agg -offset 2, daily_agg.py:307- con el bloque en $S2_BLOQUE de $S2_FILAS filas: NADIE la volvera a calcular, o sea que el corpus la perdio PARA SIEMPRE. La ventana que el pipeline DECLARA haber cubierto es de $VENTANA h y para sobrevivir a su ultima reescritura hacian falta 71.51 h -72.51 h en la sesion de 25 h del cambio de hora-"
    fi
  fi
elif [ "$S2_CUBRE" = 1 ]; then
  DECLARA="${DECLARA} · A2 NO JUZGADO: la sesion congelada ($S2) es anterior al 2026-08-14 y no tuvo contrato"
fi

[ "$SIN_PROC_VIVAS" -gt 0 ] &&
  FALLOS="${FALLOS:+$FALLOS · }$SIN_PROC_VIVAS filas del 2026-08-14 en adelante tienen sumas SIN procedencia: afirman un total sin decir de donde salio ni que arco cubre"

DEUDA=""
[ "$DEUDA_PARADA" -gt 0 ] && DEUDA=" · DEUDA PARADA, informada y NO gateada: $DEUDA_PARADA filas anteriores al 2026-08-14 tienen sumas sin procedencia porque las columnas aun no existian. Son las que impiden validar daily_session_agg_pr24_liquidation_coverage_check, que sigue NOT VALID; arreglarlas es escribir en produccion, o sea PUERTA de Alejandro"

[ -n "$FALLOS" ] && { echo "ROJO: $FALLOS$DECLARA$DEUDA"; exit 1; }
[ "$JUZGADO" = 1 ] || { echo "NO MEDIDO: ningun brazo tuvo sujeto que juzgar$DECLARA"; exit 2; }

echo "$VERDES, con la tabla CRUDA cubriendo el arco entero y una ventana declarada de $VENTANA h; ninguna fila con contrato vigente afirma un total sin procedencia$DECLARA$DEUDA"
