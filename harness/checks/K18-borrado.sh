#!/bin/bash
# K18  que borra el sistema, y si debe.
#
# Lo que se descubrio al medirlo (2026-08-25) y que la unidad no decia: NO hay un
# sitio que declare que borra el sistema. Hay CINCO mecanismos en cinco ficheros:
#   apply_temporal_retention (funcion SQL, tira PARTICIONES enteras)
#       futures_trades_realtime  6 h   scalp_collector.py:1452  config.py:181
#       orderbook_snapshot       6 h   scalp_collector.py:1465  config.py:187
#       liquidations_realtime    6 h   scalp_collector.py:1470  config.py:181
#       scalp_signal_snapshot   72 h   scalp_collector.py:1475  config.py:189
#       spot_trades_realtime     2 h   daily_agg.py:594         config.py:199
#   DELETE directo
#       futures_trades_agg      36 h   scalp_collector.py:1459  config.py:186
#       metrics_snapshot     N dias    daily_agg.py:583
#       macro_event         30 dias    external_macro.py:576
#       external_api_rate_event        coinalyze.py:68
#
# DOS cosas se comprueban, y las dos EJECUTAN:
# 1. Cada tabla con ventana declarada mantiene una ventana coherente. Coherente NO
#    es "igual": las cinco primeras borran particiones DIARIAS enteras, asi que
#    retienen legitimamente hasta ventana+24 h. Medido: futures_trades_realtime
#    declara 6 h y tiene 14.8 h, y no es un fallo, es la granularidad.
# 2. Que no encoja NINGUNA tabla sin borrador declarado, comparando contra el
#    espejo. Se prefiltra con reltuples -que es barato- y se CONFIRMA contando
#    exacto: reltuples daba 7% de perdida en las _unpartitioned_backup y era ruido,
#    las tres fuentes dan 79978 clavados. Un check que se creyera reltuples estaria
#    inventando rojos.
#
# NO cubre el ritmo de ESCRITURA. Medido: scalp_signal_snapshot pasa de 1005 filas/h
# en el espejo a 480/h hoy. Eso NO es borrado -su ventana esta sana- asi que la
# atribucion "lo hace app/partitioning.py" del ROJO de K18 es falsa. Vigilar que un
# escritor no baje el ritmo es la familia de K05/K06/K19, no esta.
set -uo pipefail
B=${K18_HARNESS:-/srv/coinanalyze/harness}; . "$B/env"

# tabla:horas:gracia   gracia 27 = 24 de particion diaria + 3 de cadencia
# futures_trades_agg lleva gracia 6 y no 3 por un motivo medido: la limpieza corre
# con asyncio.sleep(3600) (scalp_collector.py:1487), o sea una vez por hora, y CADA
# REINICIO DEL COLECTOR REINICIA ESE CONTADOR DESDE CERO. El 2026-08-25, con cuatro
# despliegues en el dia, el span llego a 39.18 h con 36 declaradas sin que hubiera
# ningun fallo de retencion: simplemente la limpieza no habia llegado a correr. Con
# gracia 3 el check oscilaba en el borde, y un check que parpadea es ruido. Con 6
# tolera seis ciclos perdidos y sigue cazando un atasco de verdad (42 h o mas).
VENTANAS="futures_trades_realtime:6:27 orderbook_snapshot:6:27 liquidations_realtime:6:27 scalp_signal_snapshot:72:27 spot_trades_realtime:2:27 futures_trades_agg:36:6"
# Tablas sin retencion automatica y su suelo de filas esperado.
SUELOS="pipeline_heartbeat:12"

vivo=$("$B/bin/prodsql" "SELECT 'canal_ok'" 2>/dev/null | tr -d ' ' | head -1)
[ "$vivo" = "canal_ok" ] || { echo "NO MEDIDO: prodsql no responde"; exit 2; }

fallos=""
for item in $VENTANAS; do
  t=${item%%:*}; resto=${item#*:}; w=${resto%%:*}; gracia=${resto#*:}
  span=$("$B/bin/prodsql" "SELECT round(extract(epoch FROM now()-min(ts))/3600,1) FROM $t" 2>/dev/null | grep -E '^[0-9.]+$' | head -1)
  [ -n "$span" ] || { fallos="$fallos $t(sin_min_ts)"; continue; }
  techo=$((w + gracia))
  # awk porque span lleva decimales. Suelo: la mitad de la ventana; por debajo,
  # algo esta borrando de mas o la tabla se acaba de vaciar.
  veredicto=$(awk -v s="$span" -v w="$w" -v techo="$techo" 'BEGIN{ if (s > techo) print "retiene_de_mas"; else if (s < w/2) print "borra_de_mas"; else print "ok" }')
  [ "$veredicto" = "ok" ] || fallos="$fallos $t($veredicto:${span}h_vs_${w}h)"
done

for item in $SUELOS; do
  t=${item%%:*}; suelo=${item#*:}
  n=$("$B/bin/prodsql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  [ -n "$n" ] && [ "$n" -ge "$suelo" ] || fallos="$fallos $t(${n:-?}_bajo_de_$suelo)"
done

# Barrido: prefiltro barato con reltuples, confirmacion exacta de lo que salga.
sospechosas=$(join \
  <("$B/bin/espejosql" "SELECT relname||' '||reltuples::bigint FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND relname !~ '_p[0-9]{8}\$' AND reltuples > 0 ORDER BY relname" 2>/dev/null | grep -E '^[a-z_]+ [0-9]+$' | sort) \
  <("$B/bin/prodsql" "SELECT relname||' '||reltuples::bigint FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND relname !~ '_p[0-9]{8}\$' AND reltuples > 0 ORDER BY relname" 2>/dev/null | grep -E '^[a-z_]+ [0-9]+$' | sort) \
  2>/dev/null | awk '$3 < $2*0.9 {print $1}')
# UN REEMPLAZO COMPLETO NO ES UN BORRADO, Y ESTE BRAZO NO SABIA DISTINGUIRLOS.
#
# EL HECHO QUE LO MOTIVA, medido el 2026-09-06. K18 se puso ROJO con
# `macro_event(encoge_sin_declarar:33->29)`. Y lo que compara este brazo NO es produccion
# antes contra produccion ahora: es EL ESPEJO contra PRODUCCION.
#     a = espejosql   -> el espejo de 143, congelado el 2026-08-13 17:47Z
#     b = prodsql     -> 140, ahora
# `macro_event` es un CALENDARIO que se reemplaza entero en cada refresco: las 33 filas del
# espejo comparten UN solo `fetched_at` (2026-08-13 17:10) y las 29 de produccion comparten
# otro (2026-09-06 16:30). No falta ninguna fila: son DOS FOTOS distintas, con 24 dias entre
# ellas, de una tabla que se sustituye. Y salto hoy y no antes por el prefiltro -b < a*0.9-:
# a 30 filas no disparaba y a 29 si. Un umbral cruzado sobre una comparacion que no procede.
#
# ES EL PATRON DE K80: el mensaje nombraba una causa -«borrado sin declarar»- que no era la
# real. El arreglo va donde fue el de K80 -que el check sepa DISTINGUIR- y no en ensanchar el
# umbral ni en exentar la tabla por su nombre.
#
# EL DISCRIMINANTE SALE DEL DATO, no de una lista: una tabla cuyo contenido se reemplaza
# entero tiene TODAS sus filas con un unico sello de carga. Si existe una columna de tiempo
# con UN SOLO valor distinto en los DOS lados, y esos dos valores DIFIEREN, lo que hay son dos
# instantaneas de una tabla sustituida, y su diferencia de filas no es un borrado.
#   · se exige >= 2 filas en los dos lados: con una fila, "un solo valor distinto" es trivial;
#   · se exige que los dos sellos DIFIERAN: si fueran el mismo, es la misma foto y una
#     diferencia de filas si seria un borrado;
#   · `pipeline_heartbeat`, la otra tabla que marca el prefiltro hoy, tiene 11 y 9 valores
#     distintos de `updated_at`: NO se lleva la exencion, y si algun dia llega aqui, enrojece.
# Los reemplazos NO se callan: se publican en el mensaje verde con sus dos sellos.
reemplazos=""; n_reemplazos=0
for t in $sospechosas; do
  case " $VENTANAS $SUELOS " in *" $t:"*) continue ;; esac
  a=$("$B/bin/espejosql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  b=$("$B/bin/prodsql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  [ -n "$a" ] && [ -n "$b" ] && [ "$b" -lt "$a" ] || continue

  clasif=encoge
  if [ "$a" -ge 2 ] && [ "$b" -ge 2 ]; then
    cols=$("$B/bin/prodsql" "SELECT string_agg(column_name, ' ') FROM information_schema.columns
      WHERE table_name='$t' AND table_schema='public' AND data_type LIKE 'timestamp%'" \
      2>/dev/null | tr -d '\r' | head -1)
    for c in $cols; do
      se=$("$B/bin/espejosql" "SELECT count(DISTINCT $c)||'|'||coalesce(max($c)::text,'-') FROM $t" 2>/dev/null | head -1)
      sp=$("$B/bin/prodsql"   "SELECT count(DISTINCT $c)||'|'||coalesce(max($c)::text,'-') FROM $t" 2>/dev/null | head -1)
      [ "${se%%|*}" = "1" ] && [ "${sp%%|*}" = "1" ] && [ "${se#*|}" != "${sp#*|}" ] || continue
      clasif=reemplazo
      # EL CONTADOR VA APARTE Y NO SE DEDUCE DEL TEXTO. La primera version contaba con
      # `wc -w` sobre la cadena y publico «3 tabla(s)» listando UNA: los sellos llevan un
      # espacio entre fecha y hora, asi que cada entrada son tres palabras. Un recuento
      # derivado del formato de su propio mensaje se rompe cuando el mensaje cambia.
      clasif=reemplazo
      n_reemplazos=$((n_reemplazos + 1))
      reemplazos="$reemplazos $t($c:${se#*|}->${sp#*|},${a}->${b}filas)"
      break
    done
  fi
  [ "$clasif" = "reemplazo" ] || fallos="$fallos $t(encoge_sin_declarar:$a->$b)"
done

[ -z "${fallos// /}" ] || { echo "borrado sin declarar o fuera de ventana:$fallos"; exit 1; }
printf '9 borradores declarados, 6 ventanas dentro de rango, nada encoge sin declarar'
[ "$n_reemplazos" -gt 0 ] && printf ' · %d tabla(s) se REEMPLAZAN enteras y por eso su diferencia de filas contra el espejo no es un borrado:%s' \
  "$n_reemplazos" "$reemplazos"
printf '\n'
