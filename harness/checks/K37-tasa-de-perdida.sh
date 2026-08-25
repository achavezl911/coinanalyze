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
# feed | tabla | interval | cadencia_s | techo_%_dia | por que ese techo
#
# NA = la ausencia de fila NO es atribuible en este feed, asi que no hay tasa que
# medir. NA no es "no lo miro": es una afirmacion medida, y esta escrita. Pasar de NA
# a una cifra es lo que cierra el feed, y necesita una medicion en hechos.tsv.
DECLARACION='
long_short_ratio|long_short_ratio|5min|300|1.00|BTC 0.50 y ETH 0.55 en la MISMA ventana y el mismo proveedor: el techo es el doble de lo que este feed ya consigue
funding_rate|funding_rate|5min|300|1.00|mide 0.00 en los tres simbolos
open_interest|open_interest|5min|300|1.00|mide 0.00 en los tres simbolos
oi_bybit|oi_bybit|5min|300|1.00|mide 0.00 en los tres simbolos
predicted_funding_rate|predicted_funding_rate|5min|300|1.00|mide 0.00 en los tres simbolos
ohlcv_1min|ohlcv|1min|60|1.00|mide 0.00 en los tres simbolos
spot_trades_agg|spot_trades_agg|1min|60|1.00|mide 0.00 en la ventana; los 13 minutos que le faltan HOY son los MISMOS en los tres simbolos a la vez, o sea que la ausencia es nuestra y no del mercado
futures_trades_agg|futures_trades_agg|1min|60|1.00|nacio el 2026-08-24 08:00Z y la ventana se le acota a su vida: 960 de 960. Los 28 minutos que le faltan HOY son los mismos en los tres simbolos, nunca 1 ni 2, o sea escritor y no mercado
liquidations|liquidations|5min|300|NA|NO SE SABE si vacio es perdida: no escribe NUNCA una fila 0/0 (0 de 1172 filas en 2 dias) y la ausencia va del 26 al 48 por ciento segun el simbolo, o sea que sigue a la actividad del mercado y no a un fallo
'

# ------------------------------------------------------------------- LA CONSULTA
# La ventana es de 7 dias UTC COMPLETOS. UTC explicito y no now()-7d porque la sesion
# de psql viene en CST: date_trunc('day', now()) partiria el dia por las 06:00Z y la
# cifra no seria repetible.
# El nacimiento del feed acota la ventana por abajo -greatest(nac, ini)-: a un feed
# que empezo anteayer no se le imputa el tiempo en que no existia. El universo de
# simbolos sale de 30 dias, no de la ventana, para que un simbolo que se calla
# aparezca al 100 % de perdida en vez de desaparecer del conteo.
ramas=""; tablas_declaradas=""
while IFS='|' read -r feed tabla ivl cad techo _motivo; do
  [ -n "${feed:-}" ] || continue
  tablas_declaradas="${tablas_declaradas:+$tablas_declaradas,}'$tabla'"
  [ "$techo" = "NA" ] && continue
  ramas="${ramas:+$ramas
  UNION ALL}
  SELECT '$feed'::text feed, b.symbol, coalesce(o.obs,0)::int obs,
         floor(EXTRACT(EPOCH FROM (w.fin - greatest(b.nac, w.ini)))/$cad)::int esp,
         $cad::int cad, $techo::numeric techo
    FROM w
    JOIN (SELECT symbol, min(ts) nac FROM $tabla
           WHERE interval='$ivl' AND ts >= now()-interval '30 days' GROUP BY 1) b ON true
    LEFT JOIN (SELECT symbol, count(DISTINCT ts) obs FROM $tabla, w
                WHERE interval='$ivl' AND ts >= w.ini AND ts < w.fin GROUP BY 1) o
      ON o.symbol = b.symbol"
done <<EOF
$DECLARACION
EOF

SQL="
WITH w AS (SELECT (date_trunc('day', now() AT TIME ZONE 'UTC') - interval '7 days') AT TIME ZONE 'UTC' ini,
                   date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' fin),
m AS ($ramas),
c AS (SELECT feed, symbol, esp, esp-obs perdidos,
             round(100.0*(esp-obs)/nullif(esp,0), 2) pct,
             round((esp-obs)/nullif(esp*cad/86400.0, 0), 1) por_dia, techo
        FROM m)
SELECT 'SERIE|'||feed||'|'||symbol||'|'||pct||'|'||techo||'|'||por_dia
  FROM c WHERE esp > 0 AND pct > techo
UNION ALL SELECT 'VACIO|'||feed FROM c WHERE esp <= 0
UNION ALL SELECT 'TOTAL|'||count(*) FROM c
UNION ALL SELECT 'SINTECHO|'||table_name
  FROM information_schema.columns
 WHERE table_schema='public' AND column_name IN ('ts','symbol','interval')
   AND table_name NOT IN ($tablas_declaradas)
   AND table_name !~ '_p[0-9]{8}\$' AND table_name !~ '_unpartitioned_backup\$'
 GROUP BY table_name HAVING count(DISTINCT column_name)=3
ORDER BY 1"

salida=$("$B/bin/prodsql" "$SQL" 2>/dev/null)
total=$(printf '%s\n' "$salida" | sed -n 's/^TOTAL|//p' | head -1)
case "${total:-}" in
  ''|*[!0-9]*) echo "NO MEDIDO: la consulta de tasa no devolvio conteo" >&2; exit 2 ;;
esac
[ "$total" -gt 0 ] || { echo "NO MEDIDO: 0 series evaluadas, la declaracion no caso con ninguna tabla" >&2; exit 2; }

series=$(printf '%s\n' "$salida" | grep -c '^SERIE|')
vacios=$(printf '%s\n' "$salida" | grep -c '^VACIO|')
sintecho=$(printf '%s\n' "$salida" | sed -n 's/^SINTECHO|//p' | tr '\n' ' ')
peor=$(printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r | head -1)

fallos=""
if [ "$series" -gt 0 ]; then
  fallos="$series de $total series sobre techo: $(printf '%s' "$peor" | awk -F'|' '{printf "%s/%s %s%%/dia (techo %s%%, %s buckets/dia)", $2,$3,$4,$5,$6}')"
fi
[ "$vacios" -eq 0 ] || fallos="${fallos:+$fallos; }$vacios feeds declarados sin ningun simbolo con datos"
[ -z "${sintecho% }" ] || fallos="${fallos:+$fallos; }tablas de cadencia sin techo declarado: ${sintecho% }"

if [ -n "$fallos" ]; then
  echo "$fallos"
  printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r |
    awk -F'|' '{printf "   %-22s %-18s %6s %%/dia   techo %5s %%   %6s buckets/dia\n", $2,$3,$4,$5,$6}'
  exit 1
fi
echo "$total series por debajo de su techo declarado en 7 dias UTC completos"
