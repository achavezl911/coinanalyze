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
# RETENCION DECLARADA, subida de la cabecera a DATO porque el check LA USA -no por ordenar-.
# tabla:columna:dias. La ventana es la del borrador que la cabecera ya lista:
#   macro_event 30 dias · app/external_macro.py:576
#     DELETE FROM macro_event WHERE event_at < now() - interval '30 days'
RETENCIONES="macro_event:event_at:30"

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
# EL BORRADOR DECLARADO NO PUEDE SER EL ACUSADO, Y ESTE BRAZO LO ACUSABA.
#
# EL HECHO, medido el 2026-09-06. K18 se puso ROJO con `macro_event(encoge_sin_declarar:33->29)`.
# Lo que este brazo compara NO es produccion antes contra produccion ahora: es EL ESPEJO
# -congelado el 2026-08-13 17:47Z- contra PRODUCCION viva. Y las cuatro filas que faltan tienen
# NOMBRE y estan las cuatro por debajo del corte de la retencion declarada:
#     bls-ppi-202607151230 (2026-07-15) · fomc-20260729 (2026-07-29)
#     bls-jolts-202608041400 (2026-08-04) · bls-nfp-202608071230 (2026-08-07 12:30)
#     corte now()-30d = 2026-08-07 17:41Z · en PROD y no en el espejo: CERO
# O sea que las borro `app/external_macro.py:576`, que es UNO DE LOS NUEVE BORRADORES QUE LA
# CABECERA DE ESTE CHECK YA LISTA. El check documentaba el borrador y despues lo acusaba.
#
# Y LA TABLA NO SE REEMPLAZA, que fue mi primera explicacion y era falsa: en TODO el repo solo
# hay dos sentencias que la toquen -`INSERT ... ON CONFLICT DO UPDATE` en external_macro.py:564
# y ese DELETE con WHERE en :576-. No hay TRUNCATE ni DELETE sin WHERE. El `fetched_at` unico
# es el UPSERT sellando el calendario vigente, que es la firma de un refresco, no de una
# sustitucion.
#
# POR QUE EL DISCRIMINANTE ANTERIOR -«un solo sello distinto en cada lado»- NO VALE, medido
# sobre el propio check que lo llevaba (485cdc4), con canales de mentira:
#     espejo 33 -> prod 29   VERDE      <- el caso real, acertado por la razon equivocada
#     espejo 33 -> prod  5   VERDE      <- PERDIDA DEL 85 % QUE PASA POR VERDE
#     espejo 33 -> prod  1   ROJO       <- solo por el guardia de >= 2 filas
# La magnitud de la perdida no entraba en la decision. Un falso positivo cambiado por un falso
# negativo es peor en este proyecto: un rojo se ve.
#
# EL DISCRIMINANTE QUE SI FUNCIONA: no comparar los TOTALES, sino SOLO LO QUE DEBERIA SEGUIR
# VIVO segun la retencion declarada. Si el borrador es el que explica la diferencia, las filas
# de dentro de la ventana tienen que estar en los dos lados.
#     medido hoy 17:41Z:  espejo con event_at >= now()-30d = 29  ==  prod = 29   -> VERDE
#     con un dedazo de `interval '3 days'`:  espejo 29  vs  prod ~5              -> ROJO
# La ventana sale de RETENCIONES, que es la misma que la cabecera declara, ahora como dato.
#   · si los dos lados dan CERO, no se exime: cero filas dentro de la ventana no prueba que el
#     borrador sea la causa, prueba que no hay nada que comparar.
#   · una tabla que encoge y NO tiene retencion declarada sigue enrojeciendo, como siempre.
retenidos=""; n_retenidos=0
for t in $sospechosas; do
  case " $VENTANAS $SUELOS " in *" $t:"*) continue ;; esac
  a=$("$B/bin/espejosql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  b=$("$B/bin/prodsql" "SELECT count(*) FROM $t" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  [ -n "$a" ] && [ -n "$b" ] && [ "$b" -lt "$a" ] || continue

  ret=""
  for r in $RETENCIONES; do case "$r" in "$t:"*) ret="$r" ;; esac; done
  if [ -z "$ret" ]; then
    fallos="$fallos $t(encoge_sin_declarar:$a->$b)"
    continue
  fi
  resto=${ret#*:}; col=${resto%%:*}; dias=${resto#*:}
  va=$("$B/bin/espejosql" "SELECT count(*) FROM $t WHERE $col >= now() - interval '$dias days'" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  vb=$("$B/bin/prodsql"   "SELECT count(*) FROM $t WHERE $col >= now() - interval '$dias days'" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
  if [ -z "$va" ] || [ -z "$vb" ]; then
    fallos="$fallos $t(no_se_pudo_contar_dentro_de_la_ventana)"
  elif [ "$va" -lt 1 ]; then
    fallos="$fallos $t(cero_filas_dentro_de_${dias}d_en_el_espejo:no_se_puede_atribuir:$a->$b)"
  elif [ "$va" = "$vb" ]; then
    n_retenidos=$((n_retenidos + 1))
    retenidos="$retenidos $t($col>=now()-${dias}d:$va==$vb,total_$a->$b)"
  else
    fallos="$fallos $t(pierde_filas_DENTRO_de_la_ventana_de_${dias}d:$va->$vb,total_$a->$b)"
  fi
done

[ -z "${fallos// /}" ] || { echo "borrado sin declarar o fuera de ventana:$fallos"; exit 1; }
printf '9 borradores declarados, 6 ventanas dentro de rango, nada encoge sin declarar'
[ "$n_retenidos" -gt 0 ] && printf ' · %d tabla(s) encogen SOLO por su retencion declarada: dentro de la ventana los dos lados tienen las MISMAS filas:%s' \
  "$n_retenidos" "$retenidos"
printf '\n'
