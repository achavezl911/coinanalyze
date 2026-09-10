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
#       futures_trades_agg     168 h   scalp_collector.py:1459  config.py:186
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

# ═══ LA VENTANA NO SE COPIA: SE PREGUNTA ════════════════════════════════════════════
#
# QUE ESTABA MAL, medido el 2026-09-08. Este check llevaba las seis ventanas escritas a
# mano -`futures_trades_agg:36`- y produccion aplicaba otra cosa. TRES DE LAS SEIS
# discrepaban, no una:
#     futures_trades_realtime   K18 decia  6 h   produccion aplica  12 h
#     liquidations_realtime     K18 decia  6 h   produccion aplica  12 h
#     futures_trades_agg        K18 decia 36 h   produccion aplica 168 h
#     orderbook_snapshot, scalp_signal_snapshot, spot_trades_realtime: coincidian
# Solo la tercera estaba ROJA porque su span (54.6 h) pasaba el techo 36+6. Las otras dos
# pasaban POR SUERTE: con span 13.5 h y techo 6+27=33 todavia entraban. El dia que
# llegaran a 33 h -legitimamente, porque su ventana es 12- habrian acusado igual de falso.
# UNA COPIA NO TIENE FORMA DE SABER QUE QUEDO VIEJA: ese es el defecto, no el numero.
#
# DE DONDE SALE AHORA, y es la misma fuente de la que la toma el podador:
#   1 · el ENTORNO EFECTIVO del proceso que poda, leido de /proc/<pid>/environ. No el
#       fichero de entorno: si el fichero cambio y el servicio no se reinicio, lo que se
#       APLICA es lo que el proceso tiene cargado.
#   2 · si la variable no esta puesta, el `Field(default=...)` del config.py DEL RELEASE
#       DESPLEGADO, que es el codigo que corre. No el del repo de 143: pueden diferir.
#   3 · si no se puede leer ninguna de las dos, NO MEDIDO. Un check que no sabe contra
#       que juzga no juzga.
#
# NO ES TAUTOLOGICO, y es el riesgo real de este arreglo: lo que se compara NO son dos
# configuraciones, sino UNA CONFIGURACION contra UN HECHO MEDIDO EN LA BASE. El podador
# puede estar muerto, mal apuntado o filtrando otra columna, y entonces el span crece por
# encima de la ventana configurada y esto condena. Comprobado plantando el defecto: con la
# ventana de produccion intacta y el span forzado por encima del techo, sale rc=1.
#
# LO QUE SIGUE ESCRITO A MANO, Y POR QUE:
#   · LA GRACIA. No es configuracion de produccion: es la tolerancia de ESTE check, y
#     tiene que decidirla el check. gracia 27 = 24 de particion diaria + 3 de cadencia.
#     futures_trades_agg lleva 6 y no 3 por un motivo medido: la limpieza corre con
#     asyncio.sleep(3600) (scalp_collector.py:1487) y CADA REINICIO DEL COLECTOR REINICIA
#     ESE CONTADOR. El 2026-08-25, con cuatro despliegues en el dia, el span llego a
#     39.18 h con 36 declaradas sin que hubiera fallo: la limpieza no habia llegado a
#     correr. Con gracia 3 el check parpadeaba, y un check que parpadea es ruido.
#   · EL MAPA tabla -> variable. Es CABLEADO, no un valor: dice que podador cubre que
#     tabla, y sale de las lineas que la cabecera de arriba ya cita una por una. Derivarlo
#     parseando scalp_collector.py seria mas fragil que escribirlo, y un cambio de cableado
#     es un cambio de codigo que se ve en la revision, no una deriva silenciosa.
#
# EL SUELO `borra_de_mas` SE RETIRA COMO CONDENA, y hay que decir que se pierde. Con la
# ventana de verdad, futures_trades_agg tiene 54.6 h de span sobre 168 declaradas: esta
# LEGITIMAMENTE por debajo porque su ventana se amplio hace poco y aun no ha acumulado su
# regimen. El check NO PUEDE SABER cuando cambio una ventana, asi que no puede distinguir
# «se esta llenando» de «lo han vaciado», y condenar por estar debajo convierte una
# ampliacion legitima en un rojo. Se queda como OBSERVACION en la salida, visible y sin
# condenar. LO QUE SE PIERDE, dicho: si una de estas seis tablas se vaciara, este brazo ya
# no lo dice; el barrido contra el espejo tampoco, porque salta las que estan aqui
# (linea del `case` mas abajo). Una tabla sin `min(ts)` SI sigue condenando.
#
# tabla:variable_de_entorno:gracia
VENTANAS="futures_trades_realtime:SCALP_TRADE_RETENTION_HOURS:27 orderbook_snapshot:SCALP_ORDERBOOK_RETENTION_HOURS:27 liquidations_realtime:SCALP_TRADE_RETENTION_HOURS:27 scalp_signal_snapshot:SCALP_SIGNAL_RETENTION_HOURS:27 spot_trades_realtime:REALTIME_RETENTION_HOURS:27 futures_trades_agg:SCALP_MINUTE_RETENTION_HOURS:6"
VARS_RETENCION='^(SCALP_(TRADE|MINUTE|ORDERBOOK|SIGNAL)_RETENTION_HOURS|REALTIME_RETENTION_HOURS)='

# Tablas sin retencion automatica y su suelo de filas esperado.
SUELOS="pipeline_heartbeat:12"
# RETENCION DECLARADA, subida de la cabecera a DATO porque el check LA USA -no por ordenar-.
# tabla:columna:dias. La ventana es la del borrador que la cabecera ya lista:
#   macro_event 30 dias · app/external_macro.py:576
#     DELETE FROM macro_event WHERE event_at < now() - interval '30 days'
RETENCIONES="macro_event:event_at:30"

vivo=$("$B/bin/prodsql" "SELECT 'canal_ok'" 2>/dev/null | tr -d ' ' | head -1)
[ "$vivo" = "canal_ok" ] || { echo "NO MEDIDO: prodsql no responde"; exit 2; }

# --- LAS VENTANAS QUE PRODUCCION APLICA -------------------------------------------------------
# Se leen de los DOS servicios que podan y se exige que coincidan: si uno arranco con un
# entorno y el otro con otro, no hay «la ventana», hay dos, y eso hay que verlo.
leer_entorno() {
  "$B/bin/prod" "tr '\0' '\n' < /proc/\$(systemctl show $1 -p MainPID --value)/environ 2>/dev/null | grep -E '$VARS_RETENCION' | sort" 2>/dev/null \
    | grep -E "$VARS_RETENCION" | sort
}
ENV_SCALP=$(leer_entorno coinalyze-scalp)
ENV_DAILY=$(leer_entorno coinalyze-daily)
# Los `Field(default=...)` del RELEASE DESPLEGADO, para las variables que no esten puestas.
DEFECTOS=$("$B/bin/prod" "grep -oE '(SCALP_(TRADE|MINUTE|ORDERBOOK|SIGNAL)_RETENTION_HOURS|REALTIME_RETENTION_HOURS): int = Field\(default=[0-9]+' /opt/coinalyze/current/app/config.py | sed 's/: int = Field(default=/=/'" 2>/dev/null \
  | grep -E "$VARS_RETENCION" | sort)

[ -n "$ENV_SCALP$ENV_DAILY$DEFECTOS" ] || {
  echo "NO MEDIDO: no se pudo leer de 140 ninguna ventana de retencion aplicada"
  exit 2
}
if [ -n "$ENV_SCALP" ] && [ -n "$ENV_DAILY" ] && [ "$ENV_SCALP" != "$ENV_DAILY" ]; then
  echo "NO MEDIDO: coinalyze-scalp y coinalyze-daily corren con ventanas distintas; no hay UNA ventana que juzgar"
  exit 2
fi

# valor efectivo de una variable: entorno del proceso, y si no, el default del release.
ventana_de() {
  local v
  v=$(printf '%s\n' "$ENV_SCALP" "$ENV_DAILY" | grep -m1 "^$1=" | cut -d= -f2)
  [ -n "$v" ] || v=$(printf '%s\n' "$DEFECTOS" | grep -m1 "^$1=" | cut -d= -f2)
  printf '%s' "$v"
}

fallos=""
observaciones=""
for item in $VENTANAS; do
  t=${item%%:*}; resto=${item#*:}; var=${resto%%:*}; gracia=${resto#*:}
  w=$(ventana_de "$var")
  # SIN VENTANA NO SE JUZGA. Suponer un valor aqui es volver a la copia a mano por la
  # puerta de atras, y ademas con un numero que nadie ha decidido.
  case "$w" in ''|*[!0-9]*) fallos="$fallos $t(sin_ventana_aplicada:$var)"; continue ;; esac
  span=$("$B/bin/prodsql" "SELECT round(extract(epoch FROM now()-min(ts))/3600,1) FROM $t" 2>/dev/null | grep -E '^[0-9.]+$' | head -1)
  [ -n "$span" ] || { fallos="$fallos $t(sin_min_ts)"; continue; }
  techo=$((w + gracia))
  # Solo el TECHO condena. Estar por debajo de la ventana no es un defecto: una ventana
  # recien ampliada tarda dias en llenarse, y este check no puede saber cuando cambio.
  if awk -v s="$span" -v techo="$techo" 'BEGIN{ exit !(s > techo) }'; then
    fallos="$fallos $t(retiene_de_mas:${span}h_vs_${w}h+${gracia}h)"
  elif awk -v s="$span" -v w="$w" 'BEGIN{ exit !(s < w/2) }'; then
    observaciones="$observaciones $t(${span}h_de_${w}h:aun_por_debajo_de_su_regimen)"
  fi
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
usadas=""
for item in $VENTANAS; do
  t=${item%%:*}; resto=${item#*:}; var=${resto%%:*}
  usadas="$usadas $t=$(ventana_de "$var")h"
done
printf '9 borradores declarados, 6 ventanas dentro de rango LEIDAS DE PRODUCCION (%s ), nada encoge sin declarar' "$usadas"
[ -z "${observaciones// /}" ] || printf ' · por debajo de su regimen y NO es defecto:%s' "$observaciones"
[ "$n_retenidos" -gt 0 ] && printf ' · %d tabla(s) encogen SOLO por su retencion declarada: dentro de la ventana los dos lados tienen las MISMAS filas:%s' \
  "$n_retenidos" "$retenidos"
printf '\n'
