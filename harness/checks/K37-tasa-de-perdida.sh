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
REPO_LOCAL=${REPO:-/srv/coinanalyze/repo}

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
long_short_ratio|long_short_ratio|5min|300|1.00|SOLUSDT_PERP.A=10.00|7||BTC 0.50 y ETH 0.55 en la MISMA ventana y el mismo proveedor: el techo es el doble de lo que este feed ya consigue. SOL va aparte porque LA FUENTE lo publica mas escaso, y esta medido pidiendole a la API las MISMAS 24 h para los dos en UNA sola peticion el 2026-08-26T00:55Z: devolvio 288 de 289 buckets para BTC y 266 de 289 para SOL, 23 que trae para BTC y no para SOL. Nuestra base tenia 266 de SOL y 287 de BTC, o sea EXACTAMENTE lo que llego (a BTC le faltaba el bucket de las 00:55 que el proveedor acababa de publicar): no tiramos nada. Techo 10.00 sobre un 8.04 medido en 7 dias y un maximo diario de 8.68
funding_rate|funding_rate|5min|300|1.00||7||mide 0.00 en los tres simbolos
open_interest|open_interest|5min|300|1.00||7||mide 0.00 en los tres simbolos
oi_bybit|oi_bybit|5min|300|1.00||7||mide 0.00 en los tres simbolos
predicted_funding_rate|predicted_funding_rate|5min|300|1.00||7||mide 0.00 en los tres simbolos
ohlcv_1min|ohlcv|1min|60|1.00||7||mide 0.00 en los tres simbolos
spot_trades_agg|spot_trades_agg|1min|60|1.00||7||mide 0.00 en la ventana; los 13 minutos que le faltan HOY son los MISMOS en los tres simbolos a la vez, o sea que la ausencia es nuestra y no del mercado: mismo defecto que futures_trades_agg, arreglado en K40
futures_trades_agg|futures_trades_agg|1min|60|1.00||6|ohlcv:SCALP_MINUTE_RETENTION_HOURS|SEIS Y NO SIETE porque a esta tabla la PODA le come el borde inferior. La retencion es SCALP_MINUTE_RETENTION_HOURS=168 -y desde el 2026-09-10 el default de app/config.py dice 168 tambien: hasta ese dia decia 36 y NO era el que aplicaba, que es justo lo que se arreglo-, pero quien la aplica es cleanup() (app/scalp_collector.py:1570-1583), un sleep(3600) en bucle desde que ARRANCA el colector: min(ts) va por detras del corte teorico entre 0 y 60 min en marcha normal, y HORAS tras un reinicio o un apagon. MEDIDO el 2026-09-19T15:01:19Z contra 140: min(ts) 09-12 14:07 contra un corte de 09-12 15:01, o sea 54.3 min de retraso, con el colector arrancado a las 03:06:08Z -poda al minuto :06, dato desde el :07-. Por eso el septimo dia de la ventana no esta garantizado y no se cuenta: si se contara, la misma perdida daria VERDE en los primeros minutos de cada dia UTC y ROJO el resto. Que los SEIS sigan estandolo lo vigila la guarda de cobertura. Lo que pierde son nuestros DESPLIEGUES: el 2026-08-25, 19 despliegues y 33 minutos ausentes en 14 rachas, una por despliegue, iguales en los tres simbolos y los tres exchanges. Causa cerrada en K40; la perdida ya hecha se seguira contando 168 h
liquidations|liquidations|5min|300|NA||7||NO SE SABE si vacio es perdida: no escribe NUNCA una fila 0/0 (0 de 1172 filas en 2 dias) y la ausencia va del 26 al 48 por ciento segun el simbolo, o sea que sigue a la actividad del mercado y no a un fallo
'

# ------------------------------------------------------------------- LA CONSULTA
# La ventana es de 7 dias UTC COMPLETOS. UTC explicito y no now()-7d porque la sesion
# de psql viene en CST: date_trunc('day', now()) partiria el dia por las 06:00Z y la
# cifra no seria repetible.
# LA VENTANA DE CADA FEED SON SUS `dias` DECLARADOS, contados hacia atras desde la
# medianoche UTC de hoy. NO sale de `min(ts)`: ese borde se mueve con la poda y por ahi
# se colaba la hora en el veredicto (ver LA VENTANA, arriba).
#
# Y NI EL UNIVERSO DE SIMBOLOS NI EL NACIMIENTO SALEN DE UNA TABLA PODADA. En una tabla
# sin poda `min(ts)` ES el nacimiento y sirve para las dos cosas; en una podada no es
# ninguna de las dos, y usarlo dejaba dos agujeros (COLA 128, remate 2):
#   · un simbolo callado MAS que la retencion se queda sin filas, desaparece del universo
#     y el feed sale VERDE por haberse callado mas tiempo;
#   · cuando la poda entra en un hueco, es el HUECO el que se vuelve `min(ts)`, asi que
#     una perdida pegada al suelo se leia como «el dato no llega» segun la hora.
# Por eso un feed podado DECLARA de que tabla sin poda salen su universo y su nacimiento
# (columna `poda`), y el de aqui es el unico `min(ts)` que se lee.
ramas=""; tablas_declaradas=""; feeds_declarados=""; podados=""; univ_sql=""
while IFS='|' read -r feed tabla ivl cad techo excepciones dias poda _motivo; do
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
  # DE DONDE SALE EL UNIVERSO Y EL NACIMIENTO. Sin `poda` declarada, de la propia tabla: ahi
  # nadie borra, asi que su `min(ts)` es el nacimiento de verdad. Con `poda`, de la tabla que
  # se declare -que tiene que guardar los 30 dias del universo, y se comprueba-.
  univ_tabla=$tabla; ajuste=""
  if [ -n "${poda:-}" ]; then
    univ_tabla=${poda%%:*}; ajuste=${poda#*:}
    case "$univ_tabla" in
      ''|*[!a-z0-9_]*) echo "NO MEDIDO: el feed '$feed' declara una tabla de universo rara ('$univ_tabla')"; exit 2 ;;
    esac
    podados="${podados:+$podados }$feed:$univ_tabla:$ajuste:$dias"
    # LA FUENTE DEL UNIVERSO TIENE QUE GUARDAR LOS 30 DIAS QUE EL UNIVERSO DICE MIRAR. Si un dia
    # alguien la poda tambien, un simbolo mudo volveria a desaparecer del conteo en silencio, que
    # es justo el defecto que esta columna vino a quitar. Solo emite fila cuando se queda corta.
    univ_sql="${univ_sql:+$univ_sql
}UNION ALL SELECT 'UNIVCORTO|$feed|$univ_tabla|'||to_char(min(ts) AT TIME ZONE 'UTC','YYYY-MM-DD')
  FROM $univ_tabla WHERE interval='$ivl'
 HAVING min(ts) > (SELECT fin FROM w) - interval '30 days'"
  fi
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
  # `nac` viaja para la guarda de RECIEN NACIDO: un simbolo que aun no ha vivido la ventana no
  # se puede medir sobre ella. Sale de `$univ_tabla`, que para un feed podado NO es la suya:
  # asi ni la poda ni un hueco pueden moverlo, que es lo que hacia que la misma perdida saliera
  # NO MEDIDO a una hora y ROJO a otra.
  ramas="${ramas:+$ramas
  UNION ALL}
  SELECT '$feed'::text feed, b.symbol, coalesce(o.obs,0)::int obs,
         ($dias * 86400 / $cad)::int esp,
         $cad::int cad, $techo_sql::numeric techo, $techo::numeric techo_base,
         (b.symbol IN ($lista_exc)) exceptuado,
         (w.fin - interval '$dias days') desde, b.nac,
         (b.nac > w.fin - interval '$dias days') descubierta
    FROM w,
         (SELECT symbol, min(ts) nac FROM $univ_tabla
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
-- UNA SERIE RECIEN NACIDA NO ENTRA EN LA CONDENA. Si el simbolo aun no ha vivido la ventana, su
-- tasa contaria como perdidos unos buckets anteriores a su nacimiento: seria un ROJO falso. Sale
-- aparte. El nacimiento viene de la tabla SIN PODA, asi que esto ya no lo mueve ni un hueco.
SELECT 'SERIE|'||feed||'|'||symbol||'|'||pct||'|'||techo||'|'||por_dia
  FROM c WHERE NOT descubierta AND pct > techo
UNION ALL SELECT 'MUERTA|'||feed||'|'||symbol||'|'||pct||'|'||techo_base
  FROM c WHERE NOT descubierta AND exceptuado AND pct <= techo_base
UNION ALL SELECT 'NACIENDO|'||feed||'|'||symbol||'|'
                 ||to_char(nac AT TIME ZONE 'UTC','MM-DD HH24:MI')||'|'
                 ||to_char(desde AT TIME ZONE 'UTC','MM-DD HH24:MI')
  FROM c WHERE descubierta
UNION ALL SELECT 'TOTAL|'||count(*) FROM c
$univ_sql
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

# LA GUARDA DE RECIEN NACIDO. Un simbolo que aun no ha vivido la ventana no se puede medir sobre
# ella: su tasa contaria como perdidos unos buckets anteriores a su nacimiento. No es un ROJO, es
# que no se puede medir, y se dice con su nombre y las dos fechas. El nacimiento sale de la tabla
# SIN PODA declarada en `poda`, asi que ni la poda ni un hueco pegado al suelo lo mueven.
naciendo=$(printf '%s\n' "$salida" | sed -n 's/^NACIENDO|//p' |
  awk -F'|' '{printf "%s%s/%s (nacio el %s y la ventana empieza el %s)", (NR>1 ? ", " : ""), $1, $2, $3, $4}')

# LA FUENTE DEL UNIVERSO, COMPROBADA. Si la tabla de la que salen los simbolos de un feed podado
# dejara de guardar los 30 dias, un simbolo mudo volveria a desaparecer del conteo y el feed
# saldria VERDE por haberse callado mas tiempo. Solo emite fila cuando se queda corta.
univcorto=$(printf '%s\n' "$salida" | sed -n 's/^UNIVCORTO|//p' |
  awk -F'|' '{printf "%s%s (su universo sale de %s, que solo llega al %s)", (NR>1 ? ", " : ""), $1, $2, $3}')

# LA RETENCION, LEIDA DE QUIEN LA APLICA Y NO COPIADA. El numero de `dias` es una copia de lo que
# la poda garantiza, y una ventana copiada a mano es lo que hizo que K18 acusara en falso durante
# semanas. Se lee en CADA CORRIDA: primero del entorno de 140 -que es lo que de verdad aplica, y
# gana al default del codigo-, si no del release desplegado, si no del arbol local; y se DICE de
# cual salio. Un feed podado no puede declarar mas dias enteros de los que su retencion sostiene:
# con la poda yendo por detras, de R horas salen floor(R/24)-1 dias garantizados.
#
# SI NO SE PUEDE LEER DE NINGUN SITIO NO SE BLOQUEA EL VEREDICTO, y es deliberado: la medida del
# dato sigue siendo valida, y el unico riesgo -que la retencion se hubiera acortado sin que nadie
# lo viera- ya lo caza el propio dato, porque entonces faltarian dias enteros y la tasa se
# dispararia. Lo que no se hace es callarlo: la fuente va en la linea, siempre.
RETEN_DICE=""; reten_falla=""
for p in $podados; do
  p_feed=${p%%:*}; p_resto=${p#*:}; p_ajuste=${p_resto#*:}; p_ajuste=${p_ajuste%:*}; p_dias=${p##*:}
  r_val=""; r_de=""
  _env=$("$B/bin/prod" "grep -hE '^ *$p_ajuste *=' /etc/coinalyze/coinalyze.env" 2>/dev/null |
         sed -n "s/^ *$p_ajuste *= *\([0-9][0-9]*\).*/\1/p" | head -1)
  if [ -n "$_env" ]; then r_val=$_env; r_de="el entorno de 140";
  else
    _rel=$("$B/bin/prod" "grep -hE '^ *$p_ajuste *:' /opt/coinalyze/current/app/config.py" 2>/dev/null |
           sed -n 's/.*default=\([0-9][0-9]*\).*/\1/p' | head -1)
    if [ -n "$_rel" ]; then r_val=$_rel; r_de="el default del release desplegado";
    elif [ -r "$REPO_LOCAL/app/config.py" ]; then
      _loc=$(grep -hE "^ *$p_ajuste *:" "$REPO_LOCAL/app/config.py" 2>/dev/null |
             sed -n 's/.*default=\([0-9][0-9]*\).*/\1/p' | head -1)
      [ -n "$_loc" ] && { r_val=$_loc; r_de="el default del arbol local (140 no contesto)"; }
    fi
  fi
  if [ -z "$r_val" ]; then
    RETEN_DICE="${RETEN_DICE:+$RETEN_DICE; }$p_feed: $p_ajuste NO SE PUDO LEER de ningun sitio"
  else
    soporta=$(( r_val / 24 - 1 ))
    RETEN_DICE="${RETEN_DICE:+$RETEN_DICE; }$p_feed: $p_ajuste=$r_val h leido de $r_de, sostiene $soporta dias y declara $p_dias"
    [ "$soporta" -ge "$p_dias" ] || reten_falla="${reten_falla:+$reten_falla, }$p_feed ($p_ajuste=$r_val h sostiene $soporta dias enteros y la declaracion pide $p_dias, leido de $r_de)"
  fi
done

# TODO LO QUE NO SE PUDO MEDIR, JUNTO Y CON NOMBRES.
sinmedir=""
[ -z "$naciendo" ]  || sinmedir="${sinmedir:+$sinmedir; }simbolos que aun no han vivido la ventana: $naciendo"
[ -z "$univcorto" ] || sinmedir="${sinmedir:+$sinmedir; }la fuente del universo se quedo corta: $univcorto"
[ -z "$reten_falla" ] || sinmedir="${sinmedir:+$sinmedir; }la retencion desplegada no sostiene los dias declarados: $reten_falla"

# LO DECIDIBLE VA ANTES QUE LO QUE FALTA (A54). Una serie que no se puede medir NO puede comerse
# la condena de otra que si: si hay algo que condenar, manda la condena y lo que no se pudo medir
# va NOMBRADO dentro de la misma linea.
if [ -n "$fallos" ]; then
  echo "$fallos${sinmedir:+; y sin poder medir: $sinmedir} · $DIAS${RETEN_DICE:+ · retencion: $RETEN_DICE}"
  printf '%s\n' "$salida" | grep '^SERIE|' | sort -t'|' -k4 -g -r |
    awk -F'|' '{printf "   %-22s %-18s %6s %%/dia   techo %5s %%   %6s buckets/dia\n", $2,$3,$4,$5,$6}'
  exit 1
fi
if [ -n "$sinmedir" ]; then
  echo "NO MEDIDO: $sinmedir. No es VERDE -no se ha comprobado nada sobre esas series- y no es" \
       "ROJO -no hay nada que imputarles-. · $DIAS${RETEN_DICE:+ · retencion: $RETEN_DICE}"
  exit 2
fi
echo "$total series por debajo de su techo declarado · $DIAS${RETEN_DICE:+ · retencion: $RETEN_DICE}"
