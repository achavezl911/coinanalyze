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
# Y ESA FRASE FUE FALSA DURANTE UN MES POR EL BORDE DE ABAJO, no por el de arriba. El
# suelo de cada serie era min(ts), y en un feed al que una PODA le come el borde inferior
# eso no es su nacimiento: es la poda, que se mueve. MEDIDO el 2026-09-19T04:59:07Z:
# futures_trades_agg, 88 buckets perdidos en los dos casos, 0.895 % con el suelo en
# 09-12 04:07 y 1.019 % con el suelo en 09-13 00:00. La MISMA perdida, dos veredictos.
#
# LA VENTANA NO PUEDE SALIR DEL DATO, Y ESA ES LA CORRECCION ENTERA (COLA 128, remate).
# El primer arreglo subio el suelo al primer dia UTC entero que empieza despues de min(ts).
# Quita la dependencia de la hora SOLO si la poda es exacta, Y NO LO ES. La poda real es
# `cleanup()` de app/scalp_collector.py:1570-1583: un `sleep(3600)` y luego el DELETE de
# `cleanup_expired_rows` (:1549, `ts < now()-168h`). O sea que corre una vez por hora
# CONTADA DESDE QUE ARRANCA EL COLECTOR, la primera una hora despues de arrancar, y
# ninguna mientras esta caido. min(ts) va por DETRAS de now()-168h en una cantidad que va
# de cero a una hora en marcha normal, y de HORAS tras un reinicio o un apagon.
# Con ese retraso L, a la hora h del dia UTC, min(ts) cae en el dia de ayer si h < L: el
# suelo baja un dia entero y la misma perdida se mide sobre 7 dias en vez de 6. Medido por
# el operador sobre este mismo montaje: 00:30Z con 55 min de retraso da VERDE y 12:00Z con
# el mismo retraso da ROJO.
#
# Y NO SE ARREGLA PROYECTANDO min(ts) AL FINAL DEL DIA, que fue lo siguiente que probe:
# esa forma es estable mientras la poda corre, pero con la poda PARADA min(ts) se queda
# quieto y la proyeccion barre un dia entero a lo largo de la jornada. No es una medida,
# es aritmetica: cualquier criterio que mire el borde inferior del DATO se mueve, porque
# lo que se mueve es el borde -la poda se come el dia mas viejo DURANTE la jornada-.
#
# POR ESO LA VENTANA ES UN NUMERO DE DIAS UTC **DECLARADO** por feed, y el dato solo sirve
# para COMPROBAR que llega. 7 para los ocho feeds que se guardan enteros; 6 para
# futures_trades_agg, porque con 168 h de retencion y una poda que va por detras el
# septimo dia no esta garantizado. Si min(ts) no cubre los dias declarados, esa serie sale
# NO MEDIDO con su nombre -nunca VERDE-: es la guarda que impide que el numero declarado
# envejezca en silencio el dia que alguien cambie SCALP_MINUTE_RETENTION_HOURS.
#
# LO QUE ESTO CUESTA, Y SE DECLARA: un simbolo RECIEN NACIDO -con menos dias que los
# declarados- pasa de medirse desde su nacimiento a salir NO MEDIDO hasta que cumple la
# ventana. Es a proposito y se cura solo. El check no puede distinguir un nacimiento de
# verdad de un borde que la poda acaba de mover, y medir «desde donde empiece el dato» es
# justo lo que hacia que el veredicto dependiera de la hora. Lo que NO se pierde es lo que
# ese universo de 30 dias vino a proteger: un simbolo que se CALLA sigue teniendo su nac
# viejo, cubre la ventana y sale al 100 % de perdida, que es lo que tiene que pasar.
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
# feed | tabla | interval | cadencia_s | techo_%_dia | excepciones | dias | por que ese techo
#
# DIAS = cuantos dias UTC CERRADOS mide este feed, contados hacia atras desde la medianoche
# de hoy. Es un numero DECLARADO y no sale del dato, y esa es la correccion entera de la
# COLA 128 (ver el bloque LA VENTANA arriba). 7 para todo lo que se guarda entero; menos
# para un feed al que una PODA le come el borde inferior, porque entonces el ultimo dia de
# los 7 no esta garantizado. Lo protege la guarda de COBERTURA de mas abajo: si min(ts) no
# llega a cubrir los dias declarados, la serie sale NO MEDIDO con su nombre, nunca VERDE.
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
long_short_ratio|long_short_ratio|5min|300|1.00|SOLUSDT_PERP.A=10.00|7|BTC 0.50 y ETH 0.55 en la MISMA ventana y el mismo proveedor: el techo es el doble de lo que este feed ya consigue. SOL va aparte porque LA FUENTE lo publica mas escaso, y esta medido pidiendole a la API las MISMAS 24 h para los dos en UNA sola peticion el 2026-08-26T00:55Z: devolvio 288 de 289 buckets para BTC y 266 de 289 para SOL, 23 que trae para BTC y no para SOL. Nuestra base tenia 266 de SOL y 287 de BTC, o sea EXACTAMENTE lo que llego (a BTC le faltaba el bucket de las 00:55 que el proveedor acababa de publicar): no tiramos nada. Techo 10.00 sobre un 8.04 medido en 7 dias y un maximo diario de 8.68
funding_rate|funding_rate|5min|300|1.00||7|mide 0.00 en los tres simbolos
open_interest|open_interest|5min|300|1.00||7|mide 0.00 en los tres simbolos
oi_bybit|oi_bybit|5min|300|1.00||7|mide 0.00 en los tres simbolos
predicted_funding_rate|predicted_funding_rate|5min|300|1.00||7|mide 0.00 en los tres simbolos
ohlcv_1min|ohlcv|1min|60|1.00||7|mide 0.00 en los tres simbolos
spot_trades_agg|spot_trades_agg|1min|60|1.00||7|mide 0.00 en la ventana; los 13 minutos que le faltan HOY son los MISMOS en los tres simbolos a la vez, o sea que la ausencia es nuestra y no del mercado: mismo defecto que futures_trades_agg, arreglado en K40
futures_trades_agg|futures_trades_agg|1min|60|1.00||6|SEIS Y NO SIETE porque a esta tabla la PODA le come el borde inferior. La retencion es SCALP_MINUTE_RETENTION_HOURS=168 -y desde el 2026-09-10 el default de app/config.py dice 168 tambien: hasta ese dia decia 36 y NO era el que aplicaba, que es justo lo que se arreglo-, pero quien la aplica es cleanup() (app/scalp_collector.py:1570-1583), un sleep(3600) en bucle desde que ARRANCA el colector: min(ts) va por detras del corte teorico entre 0 y 60 min en marcha normal, y HORAS tras un reinicio o un apagon. MEDIDO el 2026-09-19T15:01:19Z contra 140: min(ts) 09-12 14:07 contra un corte de 09-12 15:01, o sea 54.3 min de retraso, con el colector arrancado a las 03:06:08Z -poda al minuto :06, dato desde el :07-. Por eso el septimo dia de la ventana no esta garantizado y no se cuenta: si se contara, la misma perdida daria VERDE en los primeros minutos de cada dia UTC y ROJO el resto. Que los SEIS sigan estandolo lo vigila la guarda de cobertura. Lo que pierde son nuestros DESPLIEGUES: el 2026-08-25, 19 despliegues y 33 minutos ausentes en 14 rachas, una por despliegue, iguales en los tres simbolos y los tres exchanges. Causa cerrada en K40; la perdida ya hecha se seguira contando 168 h
liquidations|liquidations|5min|300|NA||7|NO SE SABE si vacio es perdida: no escribe NUNCA una fila 0/0 (0 de 1172 filas en 2 dias) y la ausencia va del 26 al 48 por ciento segun el simbolo, o sea que sigue a la actividad del mercado y no a un fallo
'

# ------------------------------------------------------------------- LA CONSULTA
# La ventana es de 7 dias UTC COMPLETOS. UTC explicito y no now()-7d porque la sesion
# de psql viene en CST: date_trunc('day', now()) partiria el dia por las 06:00Z y la
# cifra no seria repetible.
# LA VENTANA DE CADA FEED SON SUS `dias` DECLARADOS, contados hacia atras desde la
# medianoche UTC de hoy. NO sale de `min(ts)`: ese borde se mueve con la poda y por ahi
# se colaba la hora en el veredicto (ver LA VENTANA, arriba). `min(ts)` solo se lee para
# COMPROBAR que el dato cubre lo declarado -la guarda de cobertura-. El universo de
# simbolos sale de 30 dias, no de la ventana, para que un simbolo que se calla
# aparezca al 100 % de perdida en vez de desaparecer del conteo.
ramas=""; tablas_declaradas=""; feeds_declarados=""
while IFS='|' read -r feed tabla ivl cad techo excepciones dias _motivo; do
  [ -n "${feed:-}" ] || continue
  tablas_declaradas="${tablas_declaradas:+$tablas_declaradas,}'$tabla'"
  [ "$techo" = "NA" ] && continue
  # LA DECLARACION SE VALIDA ANTES DE CONSTRUIR NADA. Un `dias` vacio o no numerico haria
  # una consulta con `interval ' days'` y el check saldria NO MEDIDO por el canal, que es
  # el sitio equivocado para enterarse de que la tabla de arriba esta mal escrita.
  case "${dias:-}" in
    ''|*[!0-9]*) echo "NO MEDIDO: el feed '$feed' no declara un numero de dias valido ('${dias:-}')"; exit 2 ;;
  esac
  [ "$dias" -ge 1 ] || { echo "NO MEDIDO: el feed '$feed' declara $dias dias de ventana"; exit 2; }
  feeds_declarados="${feeds_declarados:+$feeds_declarados,}('$feed')"
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
  # ESPERADOS Y OBSERVADOS, LOS DOS SOBRE EL MISMO INTERVALO CERRADO [fin - dias, fin).
  # `esp` es ahora una CONSTANTE del feed -dias x 86400 / cadencia- y no una resta contra un
  # borde que se mueve; `obs` barre exactamente ese intervalo. Que los dos salgan del mismo
  # sitio es lo que impide que `perdidos` salga negativo.
  # `nac` viaja SOLO para la guarda de cobertura: si el dato no llega al suelo declarado, esa
  # serie no se puede medir y sale NO MEDIDO con su nombre.
  ramas="${ramas:+$ramas
  UNION ALL}
  SELECT '$feed'::text feed, b.symbol, coalesce(o.obs,0)::int obs,
         ($dias * 86400 / $cad)::int esp,
         $cad::int cad, $techo_sql::numeric techo, $techo::numeric techo_base,
         (b.symbol IN ($lista_exc)) exceptuado,
         (w.fin - interval '$dias days') desde, b.nac,
         (b.nac > w.fin - interval '$dias days') descubierta
    FROM w,
         (SELECT symbol, min(ts) nac FROM $tabla
           WHERE interval='$ivl' AND ts >= now()-interval '30 days' GROUP BY 1) b
    LEFT JOIN (SELECT t.symbol, count(DISTINCT t.ts) obs
                 FROM $tabla t, w w2
                WHERE t.interval='$ivl'
                  AND t.ts >= w2.fin - interval '$dias days' AND t.ts < w2.fin
                GROUP BY 1) o
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
             round((esp-obs)/nullif(esp*cad/86400.0, 0), 1) por_dia, techo,
             techo_base, exceptuado, desde, nac, descubierta
        FROM m)
-- LA SERIE DESCUBIERTA NO ENTRA EN LA CONDENA. Si el dato no llega al suelo declarado, su tasa
-- contaria como perdidos unos buckets que nunca estuvieron: seria un ROJO falso. Sale aparte.
SELECT 'SERIE|'||feed||'|'||symbol||'|'||pct||'|'||techo||'|'||por_dia
  FROM c WHERE NOT descubierta AND pct > techo
UNION ALL SELECT 'MUERTA|'||feed||'|'||symbol||'|'||pct||'|'||techo_base
  FROM c WHERE NOT descubierta AND exceptuado AND pct <= techo_base
UNION ALL SELECT 'DESCUBIERTA|'||feed||'|'||symbol||'|'
                 ||to_char(nac AT TIME ZONE 'UTC','MM-DD HH24:MI')||'|'
                 ||to_char(desde AT TIME ZONE 'UTC','MM-DD HH24:MI')
  FROM c WHERE descubierta
UNION ALL SELECT 'TOTAL|'||count(*) FROM c
-- UN FEED DECLARADO QUE NO PRODUCE NI UNA SERIE (razon 3 de las tres de arriba). Antes lo
-- llevaba la rama VACIO (esp <= 0), que con la ventana declarada ya no puede dispararse -esp es
-- una constante positiva-; y ademas VACIO no cubria el caso de verdad, porque un feed sin NI UNA
-- fila en 30 dias no llegaba siquiera a producir un renglon que mirar. Esto si lo cubre.
UNION ALL SELECT 'SINSERIE|'||f FROM (VALUES $feeds_declarados) v(f)
 WHERE f NOT IN (SELECT feed FROM c)
-- SOBRE QUE DIAS SE CALCULO. La ventana nominal, y los feeds que declaran menos dias.
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
sintecho=$(printf '%s\n' "$salida" | sed -n 's/^SINTECHO|//p' | tr '\n' ' ')
peor=$(printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r | head -1)

# SOBRE QUE DIAS SE CALCULO, EN LA LINEA. Un veredicto de tasa sin su ventana no se puede
# comparar con el de ayer, y cuando un feed declara menos dias que los demas eso es justo lo que
# hay que poder leer sin abrir el check.
ventana=$(printf '%s\n' "$salida" | sed -n 's/^VENTANA|//p' | head -1 |
  awk -F'|' '{printf "%s a %s", $1, $2}')
recortes=$(printf '%s\n' "$salida" | sed -n 's/^DESDE|//p' |
  awk -F'|' '{printf "%s%s desde %s (%s dias declarados)", (NR>1 ? ", " : ""), $1, $2, $3}')
DIAS="7 dias UTC cerrados, ${ventana:-ventana no declarada}"
[ -z "$recortes" ] || DIAS="$DIAS · ventana declarada mas corta: $recortes"

fallos=""
if [ "$series" -gt 0 ]; then
  fallos="$series de $total series sobre techo: $(printf '%s' "$peor" | awk -F'|' '{printf "%s/%s %s%%/dia (techo %s%%, %s buckets/dia)", $2,$3,$4,$5,$6}')"
fi
muertas=$(printf '%s\n' "$salida" | sed -n 's/^MUERTA|//p' |
  awk -F'|' '{printf "%s%s/%s (%s%% <= techo base %s%%)", (NR>1 ? ", " : ""), $1, $2, $3, $4}')
[ -z "$muertas" ] || fallos="${fallos:+$fallos; }excepciones de techo que ya no hacen falta y hay que quitar: $muertas"
sinserie=$(printf '%s\n' "$salida" | sed -n 's/^SINSERIE|//p' | tr '\n' ' ')
[ -z "${sinserie% }" ] || fallos="${fallos:+$fallos; }feeds declarados sin NI UNA serie con datos en 30 dias: ${sinserie% }"
[ -z "${sintecho% }" ] || fallos="${fallos:+$fallos; }tablas de cadencia sin techo declarado: ${sintecho% }"

# LA GUARDA DE COBERTURA. Si el dato de una serie no llega al suelo DECLARADO, su tasa contaria
# como perdidos unos buckets que nunca estuvieron ahi. Eso no es un ROJO: es que no se puede
# medir, y se dice con su nombre y con las dos fechas. Es tambien lo que impide que el numero
# de dias de la declaracion envejezca en silencio el dia que alguien toque la retencion.
descubiertas=$(printf '%s\n' "$salida" | sed -n 's/^DESCUBIERTA|//p' |
  awk -F'|' '{printf "%s%s/%s (su dato empieza en %s y la ventana declarada en %s)", (NR>1 ? ", " : ""), $1, $2, $3, $4}')

# LO DECIDIBLE VA ANTES QUE LO QUE FALTA (A54). Una serie que no se puede medir NO puede comerse
# la condena de otra que si: si hay algo que condenar, manda la condena y las descubiertas van
# NOMBRADAS dentro de la misma linea.
if [ -n "$fallos" ]; then
  echo "$fallos${descubiertas:+; y sin poder medir: $descubiertas} · $DIAS"
  printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r |
    awk -F'|' '{printf "   %-22s %-18s %6s %%/dia   techo %5s %%   %6s buckets/dia\n", $2,$3,$4,$5,$6}'
  exit 1
fi
if [ -n "$descubiertas" ]; then
  echo "NO MEDIDO: el dato no cubre la ventana declarada en $descubiertas. Dar VERDE aqui seria" \
       "dar por buena una tasa sobre buckets que nunca estuvieron; darle ROJO seria imputarselos." \
       "· $DIAS"
  exit 2
fi
echo "$total series por debajo de su techo declarado · $DIAS"
