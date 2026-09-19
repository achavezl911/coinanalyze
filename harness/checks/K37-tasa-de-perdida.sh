#!/bin/bash
# K37  LA FUGA SE MIDE POR TASA, NO POR SALDO.
#
# POR QUE EXISTE, Y POR QUE NACE ANTES DE QUE K04 SE PONGA VERDE.
# K04 mide CONTABILIDAD: que todo hueco o se cierre o quede archivado con prueba
# re-derivable. Es correcto y hace falta. Pero tiene una propiedad peligrosa: los
# 17 'unresolved' que quedan tienen entre 1 y 9 dias y estan justo por debajo del
# horizonte del proveedor. Cuando lo crucen, archive_beyond_source_horizon los
# archivara CON prueba y del todo legitimamente, y K04 se pondra VERDE mientras la
# entrada de huecos sigue exactamente igual. Verde, con prueba, y perdiendo buckets
# todos los dias. Es la misma trampa del 2026-08-25 por la otra cara: entonces se
# archivaba SIN prueba, ahora se archivara CON ella, y el resultado visible -el
# silencio- seria el mismo.
#
# Esta unidad mide la OTRA magnitud: cuanto se pierde por dia. Ni un hueco archivado
# ni un hueco recuperado la mueven, porque no cuenta huecos: cuenta BUCKETS QUE NO
# ESTAN EN LA TABLA DEL FEED.
#
# DE DONDE SALE EL NUMERO, y por que no de data_gap.
# Contar filas de data_gap seria contabilidad otra vez, y ademas se puede silenciar
# de tres formas sin tocar un dato: apagando el detector, relajando la cadencia
# esperada -propuesto y refutado el 2026-08-25, hechos.tsv K04b.NO_hay_cadencia_por_
# simbolo- o archivando. Se mide contra la tabla del feed: esperados segun la
# cadencia, observados de verdad, y la diferencia es la perdida. Solo baja si el dato
# aparece. Ademas data_gap MIENTE por exceso: el 2026-08-24 tiene 49 filas y 30
# buckets distintos, porque dos detection_source apuntan al mismo bucket.
#
# EL TECHO, DECLARADO Y JUSTIFICADO.  1.00 % de buckets por dia, por feed, y se
# evalua CONTRA CADA SIMBOLO, no contra el promedio de los simbolos: un promedio
# sobre una ventana con huecos esconde justo lo que hay que ver -SOL se lleva el 86 %
# de la perdida de long_short_ratio y la media de los tres la diluiria a un tercio-.
# No es una cifra de deseo. Medido el 2026-08-25 contra 140, ventana de 7 dias UTC
# completos (2026-08-18 00:00Z a 2026-08-25 00:00Z):
#     funding_rate, open_interest, oi_bybit, predicted_funding_rate, ohlcv 1min y
#         spot_trades_agg   0.00 % en los tres simbolos   <- el 0 % es alcanzable HOY
#     long_short_ratio  BTC 0.50 %  ETH 0.55 %   <- mismo proveedor, mismo feed,
#         misma cadencia y misma ventana que SOL, que pierde el 7.74 %
# O sea que el techo esta al doble del peor feed que se porta bien, y muy por encima
# del 0.00 % que seis feeds ya cumplen. Deja holgura para el temblor del proveedor y
# no deja holgura para una fuga.
#
# LA VENTANA ES DE DIAS CERRADOS, asi que lo que se pierda hoy se ve manana. Es a
# proposito -una tasa sobre el dia en curso sube y baja con la hora a la que mires-
# y tiene un coste que conviene saber: los 13 minutos que spot_trades_agg perdio hoy
# 2026-08-25 entre las 04:17 y las 05:58Z no entran en esta pasada, entran en la de
# manana. La deteccion NO tiene retraso, la ventana si.
#
# Y ESTA FRASE ERA FALSA DURANTE UN MES POR EL BORDE DE ABAJO, no por el de arriba. El
# suelo de cada serie era min(ts), y en un feed acotado por RETENCION eso es now() menos
# la retencion: avanzaba con el reloj, encogia los esperados y dejaba los buckets
# perdidos quietos, asi que la MISMA perdida daba VERDE por la manana y ROJO por la
# noche. MEDIDO el 2026-09-19T04:59:07Z: futures_trades_agg, 88 buckets perdidos en los
# dos casos, 0.895 % con el suelo en 09-12 04:07 y 1.019 % con el suelo en 09-13 00:00.
# Hoy el suelo de cada serie se sube al PRIMER DIA UTC ENTERO, y el dia parcial no entra
# ni en los esperados ni en los observados. La ventana efectiva de cada feed se DICE en
# la linea del veredicto. Medido el mismo dia: de los 9 feeds declarados, el unico con
# el suelo dentro de la ventana es futures_trades_agg (09-12 04:07); los otros ocho
# nacen 547 h por debajo y no cambian ni un bucket.
#     bash harness/checks/K37-control.bash
#
# SUBIR UN TECHO ES LA SALIDA PREVISTA, Y ESE ES EL PUNTO. Si se decide que el 8 % de
# SOL es aceptable porque el proveedor no publica esos buckets -medido: no perdemos ni
# una fila de las que entrega, hechos.tsv K04b.cadencia_real_de_la_fuente_7_dias- se
# sube el techo AQUI, con su medicion y su fecha. La perdida deja de ser silencio y
# pasa a ser un numero firmado que cualquier empeoramiento vuelve a poner en ROJO.
# Lo que esta unidad prohibe no es perder: es perder sin que se vea.
#
# TRES COSAS LO PONEN EN ROJO:
#   1. un simbolo de un feed declarado por encima del techo de su feed
#   2. una tabla de cadencia en la base que no este declarada aqui: un feed nuevo no
#      entra en silencio (futures_trades_agg nacio el 2026-08-24 y nadie lo vigilaba)
#   3. un feed declarado del que ya no queda ni un simbolo con datos en 30 dias
# Y NO se mide (rc=2, NOMED) si alguna consulta no devuelve numero. No poder medir no
# es estar sano.
set -uo pipefail
B=/srv/coinanalyze/harness

# ---------------------------------------------------------------- LA DECLARACION
# feed | tabla | interval | cadencia_s | techo_%_dia | excepciones | por que ese techo
#
# NA = la ausencia de fila NO es atribuible en este feed, asi que no hay tasa que
# medir. NA no es "no lo miro": es una afirmacion medida, y esta escrita. Pasar de NA
# a una cifra es lo que cierra el feed, y necesita una medicion en hechos.tsv.
#
# EXCEPCIONES = SIMBOLO=techo;SIMBOLO=techo, para cuando la FUENTE publica un simbolo
# mas escaso que los demas. Es por (feed, simbolo) y NUNCA por feed entero: subir el
# techo del feed dejaria a los simbolos sanos con una holgura que taparia su propia
# degradacion. Toda excepcion lleva su medicion y su FECHA en el motivo, y CADUCA
# SOLA: si el simbolo baja al techo base, el check falla pidiendo que se quite, para
# que una excepcion vieja no siga cubriendo un fallo nuevo.
DECLARACION='
long_short_ratio|long_short_ratio|5min|300|1.00|SOLUSDT_PERP.A=10.00|BTC 0.50 y ETH 0.55 en la MISMA ventana y el mismo proveedor: el techo es el doble de lo que este feed ya consigue. SOL va aparte porque LA FUENTE lo publica mas escaso, y esta medido pidiendole a la API las MISMAS 24 h para los dos en UNA sola peticion el 2026-08-26T00:55Z: devolvio 288 de 289 buckets para BTC y 266 de 289 para SOL, 23 que trae para BTC y no para SOL. Nuestra base tenia 266 de SOL y 287 de BTC, o sea EXACTAMENTE lo que llego (a BTC le faltaba el bucket de las 00:55 que el proveedor acababa de publicar): no tiramos nada. Techo 10.00 sobre un 8.04 medido en 7 dias y un maximo diario de 8.68
funding_rate|funding_rate|5min|300|1.00||mide 0.00 en los tres simbolos
open_interest|open_interest|5min|300|1.00||mide 0.00 en los tres simbolos
oi_bybit|oi_bybit|5min|300|1.00||mide 0.00 en los tres simbolos
predicted_funding_rate|predicted_funding_rate|5min|300|1.00||mide 0.00 en los tres simbolos
ohlcv_1min|ohlcv|1min|60|1.00||mide 0.00 en los tres simbolos
spot_trades_agg|spot_trades_agg|1min|60|1.00||mide 0.00 en la ventana; los 13 minutos que le faltan HOY son los MISMOS en los tres simbolos a la vez, o sea que la ausencia es nuestra y no del mercado: mismo defecto que futures_trades_agg, arreglado en K40
futures_trades_agg|futures_trades_agg|1min|60|1.00||la ventana se le acota por abajo a min(ts), que en esta tabla NO es su nacimiento sino su RETENCION -SCALP_MINUTE_RETENTION_HOURS=168, y desde el 2026-09-10 el default de app/config.py dice 168 tambien: hasta ese dia decia 36 y NO era el que aplicaba, que es justo lo que se arreglo-, y min(ts) avanza cada dia-, asi que no se le imputan buckets borrados a proposito. Lo que pierde son nuestros DESPLIEGUES: el 2026-08-25, 19 despliegues y 33 minutos ausentes en 14 rachas, una por despliegue, iguales en los tres simbolos y los tres exchanges. Causa cerrada en K40; la perdida ya hecha se seguira contando 168 h, que es la misma retencion y por eso se mueve con ella
liquidations|liquidations|5min|300|NA||NO SE SABE si vacio es perdida: no escribe NUNCA una fila 0/0 (0 de 1172 filas en 2 dias) y la ausencia va del 26 al 48 por ciento segun el simbolo, o sea que sigue a la actividad del mercado y no a un fallo
'

# ------------------------------------------------------------------- LA CONSULTA
# La ventana es de 7 dias UTC COMPLETOS. UTC explicito y no now()-7d porque la sesion
# de psql viene en CST: date_trunc('day', now()) partiria el dia por las 06:00Z y la
# cifra no seria repetible.
# El nacimiento del feed acota la ventana por abajo: a un feed que empezo anteayer no
# se le imputa el tiempo en que no existia. Ese suelo ya NO es `greatest(nac, ini)`
# -eso metia un borde a media hora del dia y por ahi se colaba la hora en el veredicto-
# sino el primer dia UTC entero que empieza despues de nac, y los OBSERVADOS se cuentan
# desde el mismo sitio: ver el bloque EL SUELO, unas lineas mas abajo. El universo de
# simbolos sale de 30 dias, no de la ventana, para que un simbolo que se calla
# aparezca al 100 % de perdida en vez de desaparecer del conteo.
ramas=""; tablas_declaradas=""; suelos=""
while IFS='|' read -r feed tabla ivl cad techo excepciones _motivo; do
  [ -n "${feed:-}" ] || continue
  tablas_declaradas="${tablas_declaradas:+$tablas_declaradas,}'$tabla'"
  [ "$techo" = "NA" ] && continue
  # ---------------------------------------------------- EL SUELO, SUBIDO A UN DIA UTC ENTERO
  # EL MISMO NUMERO DE BUCKETS PERDIDOS DABA VERDE O ROJO SEGUN LA HORA A LA QUE SE CORRIERA.
  # MEDIDO el 2026-09-19T04:59:07Z contra 140, futures_trades_agg, los tres simbolos iguales:
  #     suelo = min(ts) = 09-12 04:07   esp 9833   obs 9745   perdidos 88   0.895 %  VERDE
  #     suelo = 09-13 00:00 (dia entero) esp 8640  obs 8552   perdidos 88   1.019 %  ROJO
  # Los PERDIDOS son los mismos 88 en las dos: lo unico que se movia era el denominador. Para
  # esta tabla min(ts) no es el nacimiento sino la RETENCION -SCALP_MINUTE_RETENTION_HOURS=168-,
  # o sea now() menos 7 dias, que avanza con el reloj.
  # Y NO ES LA PRIMERA VEZ QUE SE VE, aunque si la primera que se arregla: la COLA 127 lo anoto
  # en su premisa -los MISMOS 88 minutos del apagon del 09-16 por debajo del techo a las 21:21Z
  # y 1.006 % a las 23:11Z del 2026-09-18-, y se cerro como «cruza cada dia hacia las 22:15Z».
  # Esa medida es de ahi y no de aqui; la de arriba si es de esta corrida.
  # La cabecera de este check dice desde agosto que la ventana es de dias cerrados justo para
  # que eso no pase, y este `greatest` volvia a meter un borde a media hora del dia.
  #
  # EL ARREGLO ES SUBIR EL SUELO, NO BAJARLO. Bajarlo a date_trunc('day', nac) imputaria buckets
  # que la retencion borro a proposito, que es lo que ese suelo existe para evitar. Se sube al
  # PRIMER DIA UTC QUE EMPIEZA DESPUES de nac: el dia parcial no se mide en ningun lado -ni en
  # los esperados ni en los observados, que es la otra mitad-, y lo que queda son dias enteros.
  #
  # POR QUE `date_trunc + 1 dia` Y NO EL TECHO EXACTO (nac - 1 us). Los dos dan lo mismo salvo si
  # nac cae CLAVADO en una medianoche; ahi el techo exacto devolveria ese mismo dia, y si el
  # barrido de retencion moviera nac de 00:00 a 00:05 a media tarde, el suelo saltaria un dia
  # entero y volveriamos a tener un veredicto que depende de la hora, que es lo que se vino a
  # quitar. Con esta forma el suelo solo depende del DIA de nac, y para un feed acotado por una
  # retencion de un numero entero de dias ese dia es el mismo durante toda la jornada UTC. Lo
  # que cuesta: si un feed naciera exactamente a las 00:00:00, se tira un dia que estaba entero.
  # Hoy no le pasa a ninguno (medido: el unico nac dentro de la ventana es 09-12 04:07).
  suelos="${suelos:+$suelos,}
  e_$feed AS (SELECT n.symbol,
                     greatest(w.ini, date_trunc('day', n.nac AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
                                     + interval '1 day') ini
                FROM (SELECT symbol, min(ts) nac FROM $tabla
                       WHERE interval='$ivl' AND ts >= now()-interval '30 days' GROUP BY 1) n, w)"
  # El techo es una columna, no una constante: con excepciones se vuelve un CASE por
  # simbolo. techo_base viaja aparte para poder decir cuando una excepcion ya sobra.
  techo_sql="$techo"; lista_exc="NULL"
  if [ -n "${excepciones:-}" ]; then
    casos=""; simbolos=""; guardado=$IFS; IFS=';'
    for par in $excepciones; do
      sim=${par%%=*}; val=${par#*=}
      [ -n "$sim" ] && [ -n "$val" ] && [ "$sim" != "$val" ] || continue
      casos="$casos WHEN '$sim' THEN $val"
      simbolos="${simbolos:+$simbolos,}'$sim'"
    done
    IFS=$guardado
    if [ -n "$casos" ]; then
      techo_sql="(CASE b.symbol$casos ELSE $techo END)"
      lista_exc="$simbolos"
    fi
  fi
  # LOS OBSERVADOS SE CUENTAN DESDE EL MISMO SUELO QUE LOS ESPERADOS, y esa es la otra mitad del
  # arreglo. Antes `obs` barria [w.ini, w.fin) para todos y daba igual porque no habia filas por
  # debajo de min(ts); con el suelo subido SI las hay, asi que contarlas sin esperarlas pondria
  # `perdidos` en NEGATIVO y este check daria VERDE por debajo de cero.
  ramas="${ramas:+$ramas
  UNION ALL}
  SELECT '$feed'::text feed, b.symbol, coalesce(o.obs,0)::int obs,
         floor(EXTRACT(EPOCH FROM (w.fin - b.ini))/$cad)::int esp,
         $cad::int cad, $techo_sql::numeric techo, $techo::numeric techo_base,
         (b.symbol IN ($lista_exc)) exceptuado, b.ini desde
    FROM w, e_$feed b
    LEFT JOIN (SELECT t.symbol, count(DISTINCT t.ts) obs
                 FROM $tabla t JOIN e_$feed e ON e.symbol = t.symbol, w w2
                WHERE t.interval='$ivl' AND t.ts >= e.ini AND t.ts < w2.fin
                GROUP BY 1) o
      ON o.symbol = b.symbol"
done <<EOF
$DECLARACION
EOF

SQL="
WITH w AS (SELECT (date_trunc('day', now() AT TIME ZONE 'UTC') - interval '7 days') AT TIME ZONE 'UTC' ini,
                   date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' fin),$suelos,
m AS ($ramas),
c AS (SELECT feed, symbol, esp, esp-obs perdidos,
             round(100.0*(esp-obs)/nullif(esp,0), 2) pct,
             round((esp-obs)/nullif(esp*cad/86400.0, 0), 1) por_dia, techo,
             techo_base, exceptuado, desde
        FROM m)
SELECT 'SERIE|'||feed||'|'||symbol||'|'||pct||'|'||techo||'|'||por_dia
  FROM c WHERE esp > 0 AND pct > techo
UNION ALL SELECT 'MUERTA|'||feed||'|'||symbol||'|'||pct||'|'||techo_base
  FROM c WHERE esp > 0 AND exceptuado AND pct <= techo_base
UNION ALL SELECT 'VACIO|'||feed FROM c WHERE esp <= 0
UNION ALL SELECT 'TOTAL|'||count(*) FROM c
-- SOBRE QUE DIAS SE CALCULO. La ventana nominal, y los feeds a los que su suelo se la recorta.
UNION ALL SELECT 'VENTANA|'||to_char((SELECT ini FROM w) AT TIME ZONE 'UTC','YYYY-MM-DD')||'|'
                           ||to_char((SELECT fin FROM w) AT TIME ZONE 'UTC','YYYY-MM-DD')
UNION ALL SELECT 'DESDE|'||feed||'|'||to_char(min(desde) AT TIME ZONE 'UTC','YYYY-MM-DD')||'|'
                         ||round(EXTRACT(EPOCH FROM ((SELECT fin FROM w)-min(desde)))/86400.0,0)
  FROM c WHERE desde > (SELECT ini FROM w) GROUP BY feed
UNION ALL SELECT 'SINTECHO|'||table_name
  FROM information_schema.columns
 WHERE table_schema='public' AND column_name IN ('ts','symbol','interval')
   AND table_name NOT IN ($tablas_declaradas)
   AND table_name !~ '_p[0-9]{8}\$' AND table_name !~ '_unpartitioned_backup\$'
 GROUP BY table_name HAVING count(DISTINCT column_name)=3
ORDER BY 1"

# EL rc DEL CANAL YA LLEGABA Y NO SE MIRABA. Una linea: con `bin/prodsql` propagando el
# fallo desde el 2026-09-05, distinguir «no habia nada» de «no pude preguntar» es esto.
salida=$("$B/bin/prodsql" "$SQL" 2>/dev/null) || { rc=$?; echo "NO MEDIDO (CANAL): prodsql no contesto (rc=$rc). NO es una poblacion vacia: es que no se pudo preguntar."; exit 2; }
total=$(printf '%s\n' "$salida" | sed -n 's/^TOTAL|//p' | head -1)
case "${total:-}" in
  ''|*[!0-9]*) echo "NO MEDIDO: la consulta de tasa no devolvio conteo" >&2; exit 2 ;;
esac
[ "$total" -gt 0 ] || { echo "NO MEDIDO: 0 series evaluadas, la declaracion no caso con ninguna tabla" >&2; exit 2; }

series=$(printf '%s\n' "$salida" | grep -c '^SERIE|')
vacios=$(printf '%s\n' "$salida" | grep -c '^VACIO|')
sintecho=$(printf '%s\n' "$salida" | sed -n 's/^SINTECHO|//p' | tr '\n' ' ')
peor=$(printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r | head -1)

# SOBRE QUE DIAS SE CALCULO, EN LA LINEA. Un veredicto de tasa sin su ventana no se puede
# comparar con el de ayer, y cuando un feed mide sobre menos dias que los demas -porque su suelo
# es una retencion- eso es justo lo que hay que poder leer sin abrir el check.
ventana=$(printf '%s\n' "$salida" | sed -n 's/^VENTANA|//p' | head -1 |
  awk -F'|' '{printf "%s a %s", $1, $2}')
recortes=$(printf '%s\n' "$salida" | sed -n 's/^DESDE|//p' |
  awk -F'|' '{printf "%s%s desde %s (%s dias)", (NR>1 ? ", " : ""), $1, $2, $3}')
DIAS="7 dias UTC cerrados, ${ventana:-ventana no declarada}"
[ -z "$recortes" ] || DIAS="$DIAS · con el suelo en un dia entero: $recortes"

fallos=""
if [ "$series" -gt 0 ]; then
  fallos="$series de $total series sobre techo: $(printf '%s' "$peor" | awk -F'|' '{printf "%s/%s %s%%/dia (techo %s%%, %s buckets/dia)", $2,$3,$4,$5,$6}')"
fi
muertas=$(printf '%s\n' "$salida" | sed -n 's/^MUERTA|//p' |
  awk -F'|' '{printf "%s%s/%s (%s%% <= techo base %s%%)", (NR>1 ? ", " : ""), $1, $2, $3, $4}')
[ -z "$muertas" ] || fallos="${fallos:+$fallos; }excepciones de techo que ya no hacen falta y hay que quitar: $muertas"
# EL MENSAJE COGE LAS DOS LECTURAS, PORQUE AHORA HAY DOS. `esp <= 0` significaba «el feed no
# tiene datos en la ventana»; con el suelo en un dia entero tambien lo dispara un feed cuyo
# unico dato cabe en el dia parcial, que no es lo mismo y no se puede decir con la frase vieja.
[ "$vacios" -eq 0 ] || fallos="${fallos:+$fallos; }$vacios series sin NINGUN dia UTC entero que medir (o el feed se quedo sin datos, o lo que le queda cabe entero en el dia parcial de su suelo)"
[ -z "${sintecho% }" ] || fallos="${fallos:+$fallos; }tablas de cadencia sin techo declarado: ${sintecho% }"

if [ -n "$fallos" ]; then
  echo "$fallos · $DIAS"
  printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r |
    awk -F'|' '{printf "   %-22s %-18s %6s %%/dia   techo %5s %%   %6s buckets/dia\n", $2,$3,$4,$5,$6}'
  exit 1
fi
echo "$total series por debajo de su techo declarado · $DIAS"
