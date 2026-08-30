#!/bin/bash
# K68  UN HUECO QUE EL DETECTOR NUNCA VIO NO ES UN HUECO SIN RESOLVER: ES PERDIDA MUDA.
#
# LO QUE PASO, y por eso existe este check. El 2026-08-28 el nodo estuvo caido 37.4 h.
# Cuando volvio, el detector de cadencia dejo 162 filas en data_gap, se recuperaron las
# 162 y todo parecia cerrado. No lo estaba: faltaban 2388 buckets de ohlcv 1min -796 por
# simbolo, de 07:46Z a 21:01Z del 28- que NO TENIAN NI UNA FILA. El detector mira 24 h
# atras y el apagon duro 37.4, asi que ese tramo nacio ya fuera de su ventana. No fue un
# hueco mal resuelto: fue un hueco que para el sistema NUNCA EXISTIO. Se descubrio a
# mano, mirando la serie, y no habia una sola cifra en todo el arnes que lo delatara.
#
# LA REGLA QUE ESTE CHECK SOSTIENE, y es K25 un piso mas abajo:
#   EL ELEGIBLE SE DERIVA DEL DATO, NUNCA DE LA TABLA DE HUECOS.
# El detector es un instrumento y un instrumento puede callarse; la serie no. Preguntarle
# a data_gap "que huecos hay" es preguntarle al instrumento por su propio punto ciego, y
# la respuesta siempre sera tranquilizadora. Aqui se recorre la serie bucket a bucket y
# se exige que TODA discontinuidad real este cubierta por alguna fila, EN CUALQUIER
# ESTADO -unresolved, recovered o unrecoverable-, porque lo que se juzga no es si se
# arreglo sino si el sistema LLEGO A VERLO. Un hueco sin fila que lo cubra es ROJO, se
# llame como se llame el detector que no lo vio, y tambien si no existe detector alguno.
#
# EL BORDE VIVO NO SE JUZGA, Y EL NUMERO NO ES INVENTADO. El ciclo de ohlcv del ingest
# pide una ventana de 40 MINUTOS -to menos from = 2399 s, medido en el journal de
# coinalyze-ingest el 2026-08-30-, asi que un bucket de hace menos de 40 min todavia
# puede rellenarse solo y contarlo seria un ROJO falso. Se deja fuera el ultimo BORDE=45,
# que da cinco minutos de margen sobre esa cifra medida. Y al reves: un bucket mas viejo
# de 40 min NO se cura nunca por si solo, luego a partir de ahi contarlo es legitimo.
#
# LOS SIMBOLOS SE DECLARAN POR PLAN Y NO SE DEDUCEN DEL FEED. Es la leccion de K66:
# deducirlos de lo que hay en la tabla devolveria el conjunto vacio cuando la tabla este
# vacia, que es justo el momento en que mas falta hace mirar, y el check pasaria a VERDE
# EN SILENCIO. Si el plan y la realidad se separan, el check saca NOMED y lo dice.
#
# TRES DIENTES DE NOMED, porque "no pude medir" no es "no hay problema":
#   1. la consulta no devuelve la forma esperada (5 numeros)
#   2. no hay ni un bucket juzgado, o no hay ni uno presente -el join esta muerto-
#   3. data_gap SI tiene filas que solapan la ventana y sin embargo el predicado de
#      cobertura no marca NI UN bucket como cubierto. Eso es una contradiccion: o el
#      predicado esta roto o los datos lo estan, y en ninguno de los dos casos se puede
#      emitir veredicto. Este es el CONTROL POSITIVO, y no es adorno: sin el, un
#      predicado muerto diria "0 cubiertos, todo mudo" o "0 mudos" segun el signo del
#      fallo, y las dos cifras son indistinguibles de la realidad.
# Si data_gap NO tiene filas que solapen la ventana no hay contradiccion que detectar:
# entonces cualquier ausencia es muda por definicion, y ROJO es la respuesta correcta.
#
# SE JUZGAN LAS DOS SERIES DE ohlcv, y la de 5min no es un anadido: el 2026-08-30 se
# midio que data_gap solo contiene dos pares feed/granularidad -long_short_ratio/5min y
# ohlcv_1min/1min-, o sea que PARA EL 5min NO EXISTE DETECTOR NINGUNO. Es la version
# extrema del mismo fallo y la que peor se ve, porque no hay nada que pueda fallar: no
# hay instrumento. Sus mudos se parten en dos porque la accion es distinta y conviene
# no confundirlas: los que tienen sus cinco 1min ya guardados se reconstruyen EN LOCAL
# sin proveedor y sin fecha limite; los demas necesitan al proveedor y caducan con su
# horizonte de 48 h.
# LA VENTANA ES LA VIDA DE LA SERIE, NO UNA VENTANA RODANTE, y esta es la decision de
# diseno que mas importa de todo el fichero. La primera version miraba 7 dias. Con eso,
# el 2026-09-04 el apagon del 28 se habria salido por detras y EL CHECK SE HABRIA PUESTO
# VERDE SOLO POR EL PASO DEL TIEMPO, sin que nadie recuperara ni declarara nada: un check
# que se cura olvidando es peor que no tenerlo, porque ademas tranquiliza. Se cambio en
# cuanto se midio que la ventana ancha cuesta 8 s, o sea que no habia nada que ahorrar.
# SOLO HAY DOS CAMINOS A VERDE, y los dos exigen que alguien haga algo: RECUPERAR el dato
# o DECLARAR la perdida con una fila de data_gap. El tiempo no es ninguno de los dos.
# Y NO ES TEORICO: al ensanchar aparecieron 570 buckets mudos de CUATRO incidentes
# anteriores que nadie sabia que existian -489 el 07-28, 36 el 07-30, 3 el 08-06 y 42 el
# 08-07-, todos ya fuera del horizonte de 48 h del proveedor y ninguno declarado. La
# version de 7 dias los habria escondido para siempre.
# El limite por detras se toma de la PROPIA SERIE -su min(ts)- y no de una constante:
# antes de que la serie exista no hay ausencia que reprochar, y contarlo daria un ROJO
# gigante y falso. Se topa en RETENCION_DIAS porque apply_retention borra por ahi y lo
# borrado por politica no es un hueco.
set -uo pipefail
B=/srv/coinanalyze/harness

RETENCION_DIAS=90
BORDE=45
SIMBOLOS="'BTCUSDT_PERP.A','ETHUSDT_PERP.A','SOLUSDT_PERP.A'"

# Devuelve  juzgados|presentes|ausentes|cubiertos|mudos  para una serie de ohlcv.
# La cobertura mira data_gap en CUALQUIER estado a proposito: se juzga si el sistema
# vio el hueco, no si lo arreglo.
serie() {
  local intervalo="$1" feed="$2" cadencia="$3" secs="$4"
  "$B/bin/prodsql" "
    WITH lim AS (
      SELECT to_timestamp(floor(extract(epoch from greatest(
               (SELECT min(ts) FROM ohlcv WHERE interval='$intervalo'),
               now() - interval '$RETENCION_DIAS days'))/$secs)*$secs) AS ini,
             to_timestamp(floor(extract(epoch from now() - interval '$BORDE minutes')/$secs)*$secs) AS fin),
         ventana AS (
      SELECT generate_series((SELECT ini FROM lim), (SELECT fin FROM lim),
                             interval '$cadencia') AS ts),
         sym AS (SELECT unnest(ARRAY[$SIMBOLOS]) AS symbol),
         j AS (
      SELECT (o.ts IS NULL) AS ausente,
             EXISTS (SELECT 1 FROM data_gap g
                     WHERE g.feed='$feed' AND g.granularity='$intervalo'
                       AND g.symbol=s.symbol
                       AND g.start_ts <= v.ts AND g.end_ts > v.ts) AS cubierto
      FROM ventana v CROSS JOIN sym s
      LEFT JOIN ohlcv o ON o.ts=v.ts AND o.symbol=s.symbol AND o.interval='$intervalo')
    SELECT count(*) ||'|'|| count(*) FILTER (WHERE NOT ausente)
        ||'|'|| count(*) FILTER (WHERE ausente)
        ||'|'|| count(*) FILTER (WHERE cubierto)
        ||'|'|| count(*) FILTER (WHERE ausente AND NOT cubierto)
    FROM j" 2>/dev/null | tr -d ' ' | grep -E '^[0-9]+(\|[0-9]+){4}$' | head -1
}

# Filas de data_gap que solapan la ventana juzgada. Es el otro lado del control
# positivo: solo hay contradiccion si estas existen y aun asi no se cubre nada.
solapan() {
  "$B/bin/prodsql" "
    SELECT count(*) FROM data_gap
    WHERE feed='$2' AND granularity='$1' AND symbol IN ($SIMBOLOS)
      AND start_ts < now() - interval '$BORDE minutes'
      AND end_ts   > greatest((SELECT min(ts) FROM ohlcv WHERE interval='$1'),
                              now() - interval '$RETENCION_DIAS days')" 2>/dev/null \
    | tr -d ' ' | grep -E '^[0-9]+$' | head -1
}

juzga() {
  local intervalo="$1" feed="$2" cadencia="$3" secs="$4" fila n_solapan
  fila=$(serie "$intervalo" "$feed" "$cadencia" "$secs")
  [ -n "$fila" ] || { echo "NO MEDIDO: la consulta de ohlcv $intervalo no devolvio cinco numeros" >&2; return 2; }
  IFS='|' read -r juzgados presentes ausentes cubiertos mudos <<<"$fila"

  [ "$juzgados" -gt 0 ] || { echo "NO MEDIDO: cero buckets juzgados en ohlcv $intervalo" >&2; return 2; }
  [ "$presentes" -gt 0 ] || { echo "NO MEDIDO: ni un bucket presente en ohlcv $intervalo; el join no mide" >&2; return 2; }

  n_solapan=$(solapan "$intervalo" "$feed")
  [ -n "$n_solapan" ] || { echo "NO MEDIDO: no pude contar las filas de data_gap que solapan" >&2; return 2; }
  if [ "$n_solapan" -gt 0 ] && [ "$cubiertos" -eq 0 ]; then
    echo "NO MEDIDO: $n_solapan filas de data_gap solapan la ventana de ohlcv $intervalo y aun asi 0 buckets salen cubiertos; el predicado o los datos estan rotos" >&2
    return 2
  fi

  printf '%s %s %s %s\n' "$juzgados" "$ausentes" "$cubiertos" "$mudos"
}

r1=$(juzga 1min ohlcv_1min '1 min' 60) || exit 2
r5=$(juzga 5min ohlcv_5min '5 min' 300) || exit 2
read -r j1 a1 c1 m1 <<<"$r1"
read -r j5 a5 c5 m5 <<<"$r5"

total=$((m1 + m5))
if [ "$total" -eq 0 ]; then
  # SE DICE CUAL DE LOS DOS VERDES ES. "No habia ni un hueco" y "los huecos que habia
  # estaban todos declarados" son estados distintos y el segundo es el unico que prueba
  # algo sobre el detector. Fundirlos en una frase es como se lee de mas en un VERDE.
  if [ "$((a1 + a5))" -eq 0 ]; then
    echo "VERDE: ohlcv 1min y 5min SIN NI UNA discontinuidad en $((j1 + j5)) buckets juzgados -toda la serie retenida-, luego no hay nada que declarar"
  else
    echo "VERDE: $((a1 + a5)) discontinuidades de ohlcv 1min y 5min en $((j1 + j5)) buckets juzgados -toda la serie retenida-, y las $((a1 + a5)) tienen fila de data_gap que las cubre; 0 mudas"
  fi
  exit 0
fi

# El desglose del 5min solo se paga cuando hay algo que desglosar, y cambia la accion:
# lo reconstruible no necesita proveedor ni tiene fecha; lo demas caduca a las 48 h.
local_5=0
if [ "$m5" -gt 0 ]; then
  local_5=$("$B/bin/prodsql" "
    WITH lim AS (
      SELECT to_timestamp(floor(extract(epoch from greatest(
               (SELECT min(ts) FROM ohlcv WHERE interval='5min'),
               now() - interval '$RETENCION_DIAS days'))/300)*300) AS ini,
             to_timestamp(floor(extract(epoch from now() - interval '$BORDE minutes')/300)*300) AS fin),
         ventana AS (
      SELECT generate_series((SELECT ini FROM lim), (SELECT fin FROM lim),
                             interval '5 min') AS ts),
         sym AS (SELECT unnest(ARRAY[$SIMBOLOS]) AS symbol)
    SELECT count(*) FROM ventana v CROSS JOIN sym s
    LEFT JOIN ohlcv o ON o.ts=v.ts AND o.symbol=s.symbol AND o.interval='5min'
    WHERE o.ts IS NULL
      AND NOT EXISTS (SELECT 1 FROM data_gap g WHERE g.feed='ohlcv_5min'
                        AND g.granularity='5min' AND g.symbol=s.symbol
                        AND g.start_ts <= v.ts AND g.end_ts > v.ts)
      AND (SELECT count(*) FROM ohlcv m WHERE m.symbol=s.symbol AND m.interval='1min'
             AND m.ts >= v.ts AND m.ts < v.ts + interval '5 min') = 5" 2>/dev/null \
    | tr -d ' ' | grep -E '^[0-9]+$' | head -1)
  [ -n "$local_5" ] || { echo "NO MEDIDO: no pude partir los mudos de 5min" >&2; exit 2; }
fi

echo "$total buckets MUDOS -discontinuidad real sin ninguna fila de data_gap que la cubra-: $m1 de ohlcv 1min y $m5 de ohlcv 5min, de $((j1 + j5)) juzgados; de los de 5min, $local_5 se reconstruyen en local porque sus cinco 1min ya estan guardados y $((m5 - local_5)) necesitan al proveedor"
exit 1
