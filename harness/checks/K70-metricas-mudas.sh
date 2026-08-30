#!/bin/bash
# K70  LOS CINCO FEEDS DE METRICAS NO TIENEN DETECTOR SOBRE NUESTRO ALMACEN.
#
# ES K68 UN PISO AL LADO, no un piso mas abajo: la misma regla -EL ELEGIBLE SE DERIVA
# DEL DATO, NUNCA DE LA TABLA DE HUECOS- aplicada a las cinco series de 5min que no son
# ohlcv. K68 juzga ohlcv 1min y 5min y ahi se para; estas cinco no las mira nadie.
#
# LO QUE SE MIDIO EL 2026-08-30 EN 140, y es el motivo de que este fichero exista:
#   data_gap ENTERA contiene DOS pares feed/granularidad y ninguno es de metricas.
#   open_interest, oi_bybit, funding_rate y predicted_funding_rate suman CERO filas en
#   toda la vida de la tabla, en cualquier estado. Y sin embargo, en la ventana del
#   25 al 30 de agosto les faltan 408 buckets a cada uno de los cuatro, de 4320.
#
# Y AQUI ESTA LO QUE HACE ESTO PEOR QUE "NO HAY DETECTOR": SI LO HAY. ingest.py:765
# llama a _reconcile_response_cadence para los cinco feeds en cada ciclo. Lleva
# semanas corriendo y no ha escrito ni una fila para cuatro de ellos. Un detector que
# corre y nunca dispara no se distingue de un feed sano: es peor que la ausencia de
# instrumento, porque la ausencia al menos se nota.
#
# POR QUE NO DISPARA, y la explicacion tiene que ser la del mecanismo o no vale:
# hay DOS detectores distintos y solo uno mira nuestras filas.
#   _reconcile_response_cadence  compara contra LO QUE LA FUENTE DEVOLVIO en la pasada.
#     Solo ve lo que la fuente se salto DENTRO de un tramo que contesto. Si estuvimos
#     caidos y al volver pedimos 26 h, lo anterior a esas 26 h no se le pregunto a
#     nadie: no esta en la respuesta, no esta en la ventana, y no existe.
#   _reconcile_persisted_cadence compara contra LA TABLA. Ese si ve un bucket que no
#     tenemos, se pregunte a quien se pregunte.
# La funcion persistida acepta las SEIS tablas de cadencia -_CADENCE_TABLES en
# ingest.py:409- y se la llama con UNA, ohlcv/1min, en ingest.py:608. Por eso
# ohlcv_1min tiene 420 filas de hueco y las metricas cero. Es K69 otra vez: una
# funcion honesta a la que casi nadie llama no protege de casi nada.
#
# LAS LIQUIDACIONES NO SE JUZGAN AQUI, Y NO ES UN OLVIDO. liquidations es un feed de
# SUCESOS: que no haya filas en un tramo puede significar que no hubo liquidaciones.
# Inventarle cadencia al silencio es fabricar huecos, y el codigo ya lo dice donde
# toca -_liquidation_history_observation, ingest.py:481-. Su vigilancia es el latido
# ingest:liquidations_history y esa es la correcta para un feed de sucesos.
#
# EL BORDE ES DE 27 h Y NO DE 45 MINUTOS COMO EN K68, porque la ventana que se cura
# sola es otra: el ciclo de metricas pide 26 h en cada pasada -start_history =
# boundary_ts - 26*60*60, ingest.py:657- asi que cualquier ausencia mas joven que eso
# todavia puede rellenarse sola en el proximo ciclo y contarla seria un ROJO falso.
# 27 h da una hora de margen sobre esa cifra. Al reves tambien vale: pasadas las 26 h
# nadie vuelve a preguntar por ese bucket nunca, luego contarlo es legitimo.
#
# LA VENTANA ES LA VIDA DE LA SERIE, NO UNA VENTANA RODANTE. Es la decision de K68 y se
# repite por el mismo motivo: con una ventana de 7 dias, el apagon del 28 se saldria por
# detras el 09-04 y el check se pondria VERDE SOLO POR EL PASO DEL TIEMPO. Un check que
# se cura olvidando es peor que no tenerlo, porque ademas tranquiliza. El limite por
# detras sale del min(ts) de la PROPIA tabla -antes de que la serie exista no hay
# ausencia que reprochar- y se topa en RETENCION_DIAS, que es por donde borra
# apply_retention: lo borrado por politica no es un hueco.
#
# TRES DIENTES DE NOMED, los de K68 y por las mismas razones:
#   1. la consulta no devuelve la forma esperada (5 numeros)
#   2. no hay ni un bucket juzgado, o no hay ni uno presente -el join esta muerto-
#   3. CONTROL POSITIVO: data_gap SI tiene filas que solapan la ventana y aun asi el
#      predicado de cobertura no marca NI UNO cubierto. Sin este diente, un predicado
#      muerto diria "todo mudo" o "nada mudo" segun el signo del fallo, y las dos cifras
#      son indistinguibles de la realidad. Si NO hay filas solapantes no hay
#      contradiccion posible: entonces toda ausencia es muda por definicion y ROJO es la
#      respuesta correcta, que es justo el estado de los cuatro feeds sin una sola fila.
#
# DOS CAMINOS A VERDE Y NINGUNO ES ESPERAR: RECUPERAR el bucket, o DECLARAR la perdida
# con una fila de data_gap que la cubra, en el estado que sea. Se juzga si el sistema
# LLEGO A VER el hueco, no si lo arreglo.
set -uo pipefail
B=/srv/coinanalyze/harness

RETENCION_DIAS=90
BORDE_HORAS=27
SIMBOLOS="'BTCUSDT_PERP.A','ETHUSDT_PERP.A','SOLUSDT_PERP.A'"

# tabla|feed|exchange  ·  el par (feed,exchange) es la identidad con la que el ingest
# escribiria la fila, y open_interest_5min aparece DOS VECES con exchange distinto:
# cruzarlos daria a bybit por cubierta con las filas de binance.
FUENTES="open_interest|open_interest_5min|binance
oi_bybit|open_interest_5min|bybit
funding_rate|funding_rate|binance
predicted_funding_rate|predicted_funding_rate|binance
long_short_ratio|long_short_ratio|binance"

# Devuelve  juzgados|presentes|ausentes|cubiertos|mudos  para una serie de 5min.
serie() {
  local tabla="$1" feed="$2" exch="$3"
  "$B/bin/prodsql" "
    WITH lim AS (
      SELECT to_timestamp(floor(extract(epoch from greatest(
               (SELECT min(ts) FROM $tabla WHERE interval='5min'),
               now() - interval '$RETENCION_DIAS days'))/300)*300) AS ini,
             to_timestamp(floor(extract(epoch from
               now() - interval '$BORDE_HORAS hours')/300)*300) AS fin),
         ventana AS (
      SELECT generate_series((SELECT ini FROM lim), (SELECT fin FROM lim),
                             interval '5 min') AS ts),
         sym AS (SELECT unnest(ARRAY[$SIMBOLOS]) AS symbol),
         j AS (
      SELECT (m.ts IS NULL) AS ausente,
             EXISTS (SELECT 1 FROM data_gap g
                     WHERE g.feed='$feed' AND g.exchange='$exch'
                       AND g.granularity='5min' AND g.symbol=s.symbol
                       AND g.start_ts <= v.ts AND g.end_ts > v.ts) AS cubierto
      FROM ventana v CROSS JOIN sym s
      LEFT JOIN $tabla m ON m.ts=v.ts AND m.symbol=s.symbol AND m.interval='5min')
    SELECT count(*) ||'|'|| count(*) FILTER (WHERE NOT ausente)
        ||'|'|| count(*) FILTER (WHERE ausente)
        ||'|'|| count(*) FILTER (WHERE cubierto)
        ||'|'|| count(*) FILTER (WHERE ausente AND NOT cubierto)
    FROM j" 2>/dev/null | tr -d ' ' | grep -E '^[0-9]+(\|[0-9]+){4}$' | head -1
}

# Filas de data_gap que solapan la ventana juzgada: el otro lado del control positivo.
solapan() {
  local tabla="$1" feed="$2" exch="$3"
  "$B/bin/prodsql" "
    SELECT count(*) FROM data_gap
    WHERE feed='$feed' AND exchange='$exch' AND granularity='5min'
      AND symbol IN ($SIMBOLOS)
      AND start_ts < now() - interval '$BORDE_HORAS hours'
      AND end_ts   > greatest((SELECT min(ts) FROM $tabla WHERE interval='5min'),
                              now() - interval '$RETENCION_DIAS days')" 2>/dev/null \
    | tr -d ' ' | grep -E '^[0-9]+$' | head -1
}

juzgados_tot=0; ausentes_tot=0; mudos_tot=0
detalle=""
while IFS='|' read -r tabla feed exch; do
  [ -n "$tabla" ] || continue
  fila=$(serie "$tabla" "$feed" "$exch")
  [ -n "$fila" ] || { echo "NO MEDIDO: la consulta de $tabla no devolvio cinco numeros" >&2; exit 2; }
  IFS='|' read -r juzgados presentes ausentes cubiertos mudos <<<"$fila"

  [ "$juzgados" -gt 0 ] || { echo "NO MEDIDO: cero buckets juzgados en $tabla" >&2; exit 2; }
  [ "$presentes" -gt 0 ] || { echo "NO MEDIDO: ni un bucket presente en $tabla; el join no mide" >&2; exit 2; }

  n_solapan=$(solapan "$tabla" "$feed" "$exch")
  [ -n "$n_solapan" ] || { echo "NO MEDIDO: no pude contar las filas de data_gap que solapan $tabla" >&2; exit 2; }
  if [ "$n_solapan" -gt 0 ] && [ "$cubiertos" -eq 0 ]; then
    echo "NO MEDIDO: $n_solapan filas de data_gap solapan la ventana de $tabla y aun asi 0 buckets salen cubiertos; el predicado o los datos estan rotos" >&2
    exit 2
  fi

  juzgados_tot=$((juzgados_tot + juzgados))
  ausentes_tot=$((ausentes_tot + ausentes))
  mudos_tot=$((mudos_tot + mudos))
  [ "$mudos" -gt 0 ] && detalle="$detalle $feed@$exch=$mudos"
done <<<"$FUENTES"

if [ "$mudos_tot" -eq 0 ]; then
  # SE DICE CUAL DE LOS DOS VERDES ES: "no habia ni un hueco" y "los huecos que habia
  # estaban todos declarados" son estados distintos, y solo el segundo prueba algo
  # sobre el detector.
  if [ "$ausentes_tot" -eq 0 ]; then
    echo "VERDE: los 5 feeds de metricas SIN NI UNA discontinuidad en $juzgados_tot buckets juzgados -toda la serie retenida-, luego no hay nada que declarar"
  else
    echo "VERDE: $ausentes_tot discontinuidades en los 5 feeds de metricas de $juzgados_tot buckets juzgados -toda la serie retenida-, y todas tienen fila de data_gap que las cubre; 0 mudas"
  fi
  exit 0
fi

echo "$mudos_tot buckets MUDOS de metricas -discontinuidad real sin ninguna fila de data_gap que la cubra- de $ausentes_tot ausentes y $juzgados_tot juzgados:$detalle"
exit 1
