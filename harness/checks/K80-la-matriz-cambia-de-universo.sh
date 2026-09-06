#!/bin/bash
# K80  LA MATRIZ DE LIQUIDACIONES NO PUEDE CAMBIAR DE UNIVERSO A MITAD DE TABLA.
#
# LA VIA, REPRODUCIDA ANTES QUE LA CIFRA, que es lo que las tres veces anteriores decidio el
# check (K77 no era db.py:151, K79 no era el 616x). scalp_liquidations (scalp_logic.py:5092,
# y su docstring dice "tal como las pinta el panel") construye UNA SOLA lista `matrix` con
# DOS fuentes distintas:
#     1m · 5m · 15m   <- liquidations_realtime   tiene columna exchange: LOS DOS VENUES
#     30m · 1h · 4h   <- liquidations            SIN columna exchange: BINANCE SOLO
# y renderLiquidations (static/app.js:593) pinta las seis filas en la MISMA tabla, con las
# MISMAS columnas y sin distinguirlas. El lector que compara la fila 15m con la 30m esta
# comparando dos universos de mercado, y nada en la pantalla se lo dice.
#
# EL COMENTARIO DEL CODIGO AFIRMA LO CONTRARIO DEL DATO, que es el patron de K77 otra vez:
# scalp_logic.py:5110 dice "Ventanas largas: historico multi-exchange del API de Coinalyze"
# justo encima del SELECT contra la tabla que no tiene la dimension.
#
# EL DANO, MEDIDO EN 140 EL 2026-08-31 SOBRE LAS VENTANAS QUE PINTA EL PANEL -no sobre una
# ventana comoda-, comparando lo que pinta contra el total de los dos venues:
#     30m BTC  119644 vs  199113   falta 40.1 %      30m ETH  439775 vs  563158   22.2 %
#     1h  BTC  326241 vs  520036   falta 39.5 %      1h  ETH  470066 vs  599255   21.8 %
#     4h  BTC 1207125 vs 1629044   falta 26.9 %      4h  ETH  861503 vs 1019979   15.7 %
#     30m SOL    7525 vs   26457   falta 71.7 %  <- 3.5 veces, y dos filas debajo del 15m
#     1h  SOL   13831 vs   37527   falta 63.3 %      4h  SOL  110154 vs  157178   30.2 %
# CUANTO MAS CORTA LA VENTANA, PEOR, que es justo al reves de lo que uno supondria.
#
# LO QUE NO ES, y se dice para que nadie lo "arregle" donde no duele:
#   · la fila 'Liquidaciones 5m (L/S)' de app.js:375 esta SANA: sale del stream y
#     _liquidation_window_measured (scalp_logic.py:514) exige binance Y bybit vivos.
#   · liquidation_map SI sirve los dos venues, pero NO LLEGA A LA PANTALLA: solo lo consume
#     ai_context.py:876. El panel no pide /api/liquidation-map.
#   · el componente de puntuacion components["liquidations"] (metrics.py:190-196) tambien
#     sale de la tabla binance-only, pero NO se gatea aqui y el motivo es MEDIDO: es
#     (short-long)/(short+long), que SATURA cuando un lado domina, y anadir el venue lo mueve
#     entre 0.010 y 0.047 sobre un rango de 2. Gatear ahi seria teatro. Se declara y ya.
#
# EL SESGO POR VENUE ES ESTRUCTURAL POR SIMBOLO, no ruido, y esto es lo que impide
# "corregirlo con un factor": medido en DOS regimenes opuestos -el del bloque 19, con el
# ratio long/short entre 9 y 17, y el de hoy, entre 0.08 y 0.49- la DIRECCION del cambio al
# anadir bybit es la misma en los dos: BTC baja, ETH sube, SOL sube.
#
# LOS CUATRO BRAZOS:
#   A · CONSECUENCIA. Para cada ventana larga y cada simbolo, lo que la ruta sirve contra el
#       total de los dos venues sobre EL MISMO arco. Se re-mide en cada pasada y no se cita
#       de aqui: si algun dia bybit dejara de aportar, este check tiene que DECIRLO en vez de
#       seguir presumiendo de un peligro que ya no existe (leccion de K71).
#   B · LA MEZCLA ES INDISTINGUIBLE. La respuesta tiene que permitir saber QUE VENUES cubre
#       cada fila. Hoy el unico campo que difiere entre las dos familias es `events`, que
#       viene NULL en las largas -- y eso significa "sin conteo de eventos", NO "otro
#       universo". Una senal que existe pero dice otra cosa es peor que ninguna.
#   C · CONTROL POSITIVO Y CASO VACIO. Las ventanas cortas tienen que traer los DOS venues de
#       verdad: si bybit no publico NADA en el arco, la comparacion entera es vacua y esto
#       sale NOMED, no VERDE. Un check sobre cero importe no ha comprobado nada.
#   D · CONTROL NEGATIVO DEL INSTRUMENTO. La tabla binance-only tiene que seguir cuadrando
#       con el binance del stream (99-100 %). Si dejara de cuadrar, la diferencia que mide el
#       brazo A ya no seria "el venue que falta" sino dos feeds que discrepan, y este check
#       estaria atribuyendo el hueco a la causa equivocada.
#
# EL ARREGLO NO NECESITA PUERTA, y la pregunta se contesto midiendo: anadir exchange a la
# clave de liquidations -- hoy PRIMARY KEY (symbol, interval, ts), medido en 140 -- NO seria
# aditivo y si seria puerta 1. Pero no hace falta: la dimension YA EXISTE en
# liquidations_realtime, cuya retencion es SCALP_TRADE_RETENTION_HOURS=12 h contra una
# ventana maxima de 4 h, y cuyo binance CUADRA con el agregado del API al 99.0-99.9 %. O sea
# que la realtime no es una fuente mas pobre: trae el mismo binance y ademas bybit.
#
# DE QUE ARBOL: los cuatro brazos miden 140 -- el A y el C por la API y por prodsql, el B
# sobre el payload de la ruta. El VERDE exige los cuatro.
#
# Se comprueba con: bash harness/checks/K80-la-matriz-cambia-de-universo.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"
SIMBOLOS="BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A"
UMBRAL=5          # % de hueco a partir del cual la fila miente de forma visible

# --- C · el arco tiene que traer los dos venues, o no hay nada que comparar.
VENUES=$("$B/bin/prodsql" "
  SELECT count(DISTINCT exchange),
         coalesce(sum(notional_usd) FILTER (WHERE exchange='bybit'),0)::bigint
  FROM liquidations_realtime WHERE ts >= now()-interval '4 hours'" 2>/dev/null | tr -d ' ' | head -1)
case "$VENUES" in
  [0-9]*\|[0-9]*) : ;;
  *) echo "NO MEDIDO: 140 no contesto por liquidations_realtime: $(printf '%s' "$VENUES" | head -c 100)"; exit 2 ;;
esac
IFS='|' read -r NVENUES BYBIT <<EOF
$VENUES
EOF
[ "$NVENUES" -ge 2 ] && [ "$BYBIT" -gt 0 ] || {
  echo "NO MEDIDO: en las ultimas 4 h el stream trae $NVENUES venue(s) y bybit suma $BYBIT USD. Sin segundo venue con importe, la diferencia que este check mide no puede existir y un VERDE no probaria nada"
  exit 2
}

# --- D · control negativo: la tabla binance-only tiene que seguir siendo binance.
#
# LA VERSION ANTERIOR COMPARABA DOS COSAS QUE NO ERAN COMPARABLES, y se rompio el
# 2026-09-06 publicando 79.7 % con un mensaje que culpaba a los feeds. Cortaba los dos
# lados por el MISMO `now()`:
#     t = liquidations        WHERE interval='5min' AND ts >= now()-interval '4 hours'
#     r = liquidations_realtime WHERE exchange='binance' AND ts >= now()-...
# pero `liquidations` es un AGREGADO QUE VA CON RETRASO -medido el 2026-09-06 a las
# 10:00:16Z: ultimo cubo 09:45, o sea 10.3 min- y `liquidations_realtime` es el stream
# VIVO. Todo lo que el stream ve en esos minutos y el agregado aun no ha escrito contaba
# como discrepancia de feeds.
#
# MEDIDO, Y REPRODUCE EL NUMERO A LA DECIMA (entregas/ic-instrumentos/k80-causa2-*.out,
# 9 ventanas de 4 h dentro del horizonte de retencion):
#     los dos lados cortados en el MISMO borde   ->  99.5 a 100.2 %, 0 de 9 fuera de banda
#     la tabla cortada 20 min antes              ->  peor caso 79.6 %, 1 de 9 fuera
#     la tabla cortada 30 min antes              ->  peor caso 62.3 %, 4 de 9 fuera
# La ventana que lo produce es la de las 05:00, la unica del horizonte con el 12.6 % de su
# importe en los ultimos 15 minutos y el 20.1 % en los ultimos 20. Las demas, por debajo
# del 3 %. O sea: hace falta una RAFAGA en el borde, y por eso pasa de vez en cuando.
#
# Y HAY UNA SEGUNDA CAUSA QUE EL MENSAJE VIEJO TAMPOCO NOMBRABA, en la direccion contraria:
# `liquidations_realtime` retiene 12 h (SCALP_TRADE_RETENTION_HOURS). Si la ventana de 4 h
# se saliera de ese horizonte, el stream vendria recortado y la tabla entera, y el cociente
# se dispararia por encima de 100. Medido al salirme yo: 262 %, 596 %, 764 % y 1327 %.
#
# EL ARREGLO ES QUE LA VENTANA SEA COMPLETA EN LOS DOS LADOS, no que el umbral sea mas
# ancho. El borde derecho se toma del ULTIMO CUBO COMPLETO de la tabla, que es el ultimo
# instante sobre el que los dos lados pueden hablar; y el izquierdo se comprueba contra la
# retencion del stream. Un control negativo que se rompe por el reloj enseña a ignorar al
# que se rompe por un defecto.
DCTRL=$("$B/bin/prodsql" "
  WITH fin AS (
    SELECT max(ts) + interval '5 minutes' AS f FROM liquidations WHERE interval='5min'
  ), ret AS (
    SELECT min(ts) AS m FROM liquidations_realtime WHERE exchange='binance'
  ), t AS (
    SELECT (SUM(long_liq)+SUM(short_liq))::numeric v FROM liquidations, fin
    WHERE interval='5min' AND ts >= fin.f - interval '4 hours' AND ts < fin.f
  ), r AS (
    SELECT (SUM(notional_usd))::numeric v FROM liquidations_realtime, fin
    WHERE exchange='binance' AND ts >= fin.f - interval '4 hours' AND ts < fin.f
  )
  SELECT round(100*t.v/NULLIF(r.v,0),1)
         || '|' || round(extract(epoch FROM (now()-fin.f))/60.0, 1)
         -- TOKEN EXPLICITO, NO EL CASTEO POR DEFECTO DEL BOOLEANO. Escrito asi porque me
         -- mordio: dentro de una concatenacion, un boolean da 'true'/'false', y yo compare
         -- contra 't'/'f' -que es lo que psql imprime en una COLUMNA booleana-. Mi propio
         -- arreglo publico un NOMED falso a las 10:07Z, cazado por K80-control.bash. Es la
         -- enfermedad de esta campana cometida al curarla.
         || '|' || CASE WHEN fin.f - interval '4 hours' >= ret.m THEN 'CUBRE' ELSE 'NO_CUBRE' END
         || '|' || round(t.v,0) || '|' || round(r.v,0)
  FROM t, r, fin, ret" 2>/dev/null | tr -d ' ' | head -1)
CUADRE=$(printf '%s' "$DCTRL" | cut -d'|' -f1)
DRETRASO=$(printf '%s' "$DCTRL" | cut -d'|' -f2)
DCUBRE=$(printf '%s' "$DCTRL" | cut -d'|' -f3)
DTABLA=$(printf '%s' "$DCTRL" | cut -d'|' -f4)
DSTREAM=$(printf '%s' "$DCTRL" | cut -d'|' -f5)
case "$CUADRE" in
  ''|*[!0-9.]*) echo "NO MEDIDO: no se pudo comparar la tabla contra el binance del stream (salio '$DCTRL')"; exit 2 ;;
esac
# LA RETENCION SE NOMBRA APARTE, porque es una causa distinta con su propio remedio.
if [ "$DCUBRE" != "CUBRE" ]; then
  echo "NO MEDIDO: la ventana de 4 h que termina en el ultimo cubo completo se sale de lo que retiene liquidations_realtime (SCALP_TRADE_RETENTION_HOURS). No es que los feeds discrepen: es que el stream ya no guarda esas horas y la comparacion no se puede hacer"
  exit 2
fi
DESVIO=$(python3 -c "print(round(abs(100.0-float('$CUADRE')),1))")
python3 -c "import sys; sys.exit(0 if float('$DESVIO')<=15 else 1)" || {
  echo "NO MEDIDO: CONTROL NEGATIVO ROTO -- la tabla liquidations no cuadra con el binance del stream ($CUADRE %) SOBRE UNA VENTANA COMPLETA EN LOS DOS LADOS: 4 h que acaban en el ultimo cubo completo de la tabla ($DRETRASO min por detras de now), tabla $DTABLA USD contra stream $DSTREAM USD, retencion del stream cubierta. Descartados el retraso de escritura y la retencion, lo que queda SI es que los dos feeds discrepan, y el hueco que mide el brazo A dejaria de ser 'el venue que falta'"
  exit 2
}

# --- A · consecuencia: lo que la ruta SIRVE contra el total de los dos venues.
FALLOS=""; COMPARADAS=0; PEOR=0; PEOR_TXT=""
for S in $SIMBOLOS; do
  PAYLOAD=$("$B/bin/api" "/api/scalp/liquidations?symbol=$S" 2>/dev/null)
  [ -n "$PAYLOAD" ] || { echo "NO MEDIDO: /api/scalp/liquidations no contesto para $S"; exit 2; }
  for VENTANA in 30m 1h 4h; do
    SEG=$(case "$VENTANA" in 30m) echo 1800;; 1h) echo 3600;; 4h) echo 14400;; esac)
    SERVIDO=$(printf '%s' "$PAYLOAD" | python3 -c "
import json,sys
try: m = json.load(sys.stdin).get('matrix') or []
except Exception: sys.exit(0)
for f in m:
    if f.get('window') == '$VENTANA':
        l, s = f.get('long_liq'), f.get('short_liq')
        print('' if l is None or s is None else round(float(l)+float(s), 2)); break
" 2>/dev/null)
    REAL=$("$B/bin/prodsql" "
      SELECT round((SUM(notional_usd))::numeric,2) FROM liquidations_realtime
      WHERE symbol='$S' AND ts >= now()-($SEG * interval '1 second')" 2>/dev/null | tr -d ' ' | head -1)
    case "$REAL" in ''|*[!0-9.]*) continue ;; esac
    python3 -c "import sys; sys.exit(0 if float('$REAL')>1000 else 1)" || continue  # rafagas: arco sin importe no prueba nada
    COMPARADAS=$((COMPARADAS+1))
    # EL SEGUNDO SINTOMA, Y ES PEOR QUE INFRAVALORAR. La tabla binance-only puede venir VACIA
    # en la ventana -SUM sobre cero filas es NULL-, y entonces la ruta sirve long/short a null
    # y app.js:604-606 pinta "Sin dato" sobre un arco en el que SI se liquido dinero. Medido:
    # la fila 30m de BTC salia null con ~199k USD liquidados en los dos venues. Saltarse este
    # caso -que es lo que hacia la primera version de este check- deja fuera precisamente la
    # forma en que el defecto se ve mas grave en pantalla.
    [ -n "$SERVIDO" ] || {
      FALLOS="${FALLOS:+$FALLOS · }$VENTANA de ${S%%USDT*} sirve SIN DATO con $REAL USD liquidados en los dos venues"
      PEOR=100; PEOR_TXT="$VENTANA de ${S%%USDT*} (sin dato sobre $REAL USD)"
      continue
    }
    HUECO=$(python3 -c "print(round(100.0*(float('$REAL')-float('$SERVIDO'))/float('$REAL'),1))")
    python3 -c "import sys; sys.exit(0 if float('$HUECO')>$UMBRAL else 1)" && {
      FALLOS="${FALLOS:+$FALLOS · }$VENTANA de ${S%%USDT*} sirve $SERVIDO con $REAL en los dos venues (falta $HUECO %)"
      python3 -c "import sys; sys.exit(0 if float('$HUECO')>float('$PEOR') else 1)" && { PEOR=$HUECO; PEOR_TXT="$VENTANA de ${S%%USDT*}"; }
    }
  done
done
[ "$COMPARADAS" -gt 0 ] || {
  echo "NO MEDIDO: 0 ventanas comparables -- ninguna llego a 1000 USD en los dos venues. Las liquidaciones van a rafagas y un arco sin importe no distingue una matriz sana de una rota"
  exit 2
}

# --- B · la respuesta tiene que declarar QUE VENUES cubre cada fila.
DECLARA=$("$B/bin/api" "/api/scalp/liquidations?symbol=BTCUSDT_PERP.A" 2>/dev/null | python3 -c "
import json,sys
try: m = json.load(sys.stdin).get('matrix') or []
except Exception: sys.exit(0)
# Vale cualquier campo que nombre la cobertura; lo que NO vale es 'events', que ya existe y
# significa otra cosa -sin conteo de eventos-, ni deducirlo del nombre de la ventana.
claves = {k for f in m for k in f}
print(1 if ({'venues','exchanges','venue_coverage','exchange_coverage'} & claves) else 0)
" 2>/dev/null)
[ -n "$DECLARA" ] || DECLARA=0

# El ROJO distingue "el arreglo no funciona" de "falta desplegar", que es la lectura facil y
# equivocada mientras el arbol va por delante de 140 (misma nota que en K77).
ARBOL_OK=0
grep -q '"venues": list(LIQUIDATION_VENUES)' "$REPO/app/scalp_logic.py" 2>/dev/null &&
  ! grep -q 'Ventanas largas: historico multi-exchange' "$REPO/app/scalp_logic.py" 2>/dev/null &&
  ARBOL_OK=1

if [ -n "$FALLOS" ] || [ "$DECLARA" = 0 ]; then
  [ "$ARBOL_OK" = 1 ] && FALLOS="${FALLOS:+$FALLOS · }EL ARBOL YA LO TIENE ARREGLADO (las seis ventanas salen de liquidations_realtime y declaran venues): falta DESPLEGAR"
  printf 'ROJO: la matriz cambia de universo a mitad de tabla. %s%s%s\n' \
    "${FALLOS:-las $COMPARADAS ventanas comparadas cuadran hoy}" \
    "$([ "$DECLARA" = 0 ] && printf '%s' ' · y NINGUNA fila declara que venues cubre: el unico campo que difiere entre las dos familias es events=NULL, que significa "sin conteo de eventos" y no "otro universo"')" \
    "$([ -n "$PEOR_TXT" ] && printf ' · la peor es %s con %s %%' "$PEOR_TXT" "$PEOR")"
  exit 1
fi

printf 'las %d ventanas comparables de la matriz cuadran con el total de los DOS venues dentro del %d %%, y cada fila declara que venues cubre. Control negativo vivo: la tabla liquidations sigue siendo el binance del stream al %s %% sobre una ventana COMPLETA EN LOS DOS LADOS (4 h hasta el ultimo cubo cerrado, %s min por detras de now). Control positivo: %d venues en el arco con %s USD de bybit\n' \
  "$COMPARADAS" "$UMBRAL" "$CUADRE" "$DRETRASO" "$NVENUES" "$BYBIT"
