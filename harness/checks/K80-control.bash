#!/usr/bin/env bash
# K80-control · ¿el control D distingue un DEFECTO de un RELOJ?
#
# EL DEFECTO QUE ESTE CONTROL EXISTE PARA QUE NO VUELVA. El 2026-09-06 el control D de K80
# publico «CONTROL NEGATIVO ROTO -- la tabla liquidations ya NO cuadra con el binance del
# stream (79.7 % en 4 h)» y llevo el check entero a NOMED. No habia ninguna discrepancia de
# feeds: cortaba un AGREGADO CON RETRASO y un STREAM VIVO por el mismo `now()`, y una rafaga
# de liquidaciones en los ultimos minutos hacia el resto.
#
# LO QUE HAY QUE PROBAR NO ES QUE HOY DE VERDE. Es que el criterio nuevo:
#   1  da el mismo numero que el viejo cuando NO hay retraso        -> no cambia la medida
#   2  NO se rompe con un retraso que SI rompia al viejo            -> es el arreglo
#   3  SIGUE rompiendose si los dos lados discrepan de verdad       -> no lo aflojo
# El caso 3 es el que importa: un control que ya no puede fallar no controla nada, y
# ensanchar el umbral habria sido exactamente eso.
#
# COMO SE MIDE. Los tres casos se calculan EN LA MISMA CONSULTA contra 140, sobre los mismos
# datos y el mismo instante, y la discrepancia del caso 3 se INYECTA en SQL (se multiplica un
# lado por 0.80), que es la unica forma de tener un defecto conocido sin tocar produccion.
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh y el sujeto es el criterio, no
# produccion. Necesita prodsql; sin el, NOMED.
set -uo pipefail
B=${K80_HARNESS:-/srv/coinanalyze/harness}
[ -x "$B/bin/prodsql" ] || { echo "NO MEDIDO: no encuentro $B/bin/prodsql"; exit 2; }

fallos=0; pasan=0
caso() {  # <nombre> <esperado> <obtenido>
  if [ "$3" = "$2" ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-56s %s\n' "$1" "$3"
  else
    fallos=$((fallos+1)); printf '  [FALLA] %-56s esperaba %s, dio %s\n' "$1" "$2" "$3"
  fi
}

# EL CASO DEL RETRASO NO SE MIDE SOBRE "AHORA", Y ESA FUE MI PRIMERA VERSION MAL. Con el
# borde de hoy, 20 min de retraso dan 98.4 % -en banda- porque en este momento no hay ninguna
# rafaga en el borde: medido, el 0.1 % del importe de 4 h esta en los ultimos 15 min. Un caso
# que pasa o falla segun lo que este haciendo el mercado no prueba nada del criterio.
# Se mide sobre TODAS las ventanas de 4 h del horizonte de retencion y se coge la PEOR, que
# es un hecho de los datos y no del instante en que corra el control.
SQL="
WITH fin AS (SELECT max(ts) + interval '5 minutes' AS f FROM liquidations WHERE interval='5min'),
     ret AS (SELECT min(ts) AS m, max(ts) AS x FROM liquidations_realtime WHERE exchange='binance'),
-- NUEVO: los dos lados hasta el ultimo cubo cerrado
n_t AS (SELECT (SUM(long_liq)+SUM(short_liq))::numeric v FROM liquidations, fin
        WHERE interval='5min' AND ts >= fin.f-interval '4 hours' AND ts < fin.f),
n_r AS (SELECT (SUM(notional_usd))::numeric v FROM liquidations_realtime, fin
        WHERE exchange='binance' AND ts >= fin.f-interval '4 hours' AND ts < fin.f),
-- VIEJO: los dos lados hasta now(), que es donde entra el retraso
v_t AS (SELECT (SUM(long_liq)+SUM(short_liq))::numeric v FROM liquidations
        WHERE interval='5min' AND ts >= now()-interval '4 hours'),
v_r AS (SELECT (SUM(notional_usd))::numeric v FROM liquidations_realtime
        WHERE exchange='binance' AND ts >= now()-interval '4 hours'),
-- TODAS las ventanas de 4 h que caben ENTERAS en el horizonte de retencion
bordes AS (SELECT generate_series(date_trunc('hour',(SELECT m FROM ret))+interval '5 hours',
                                  date_trunc('hour',(SELECT x FROM ret)), interval '1 hour') e),
par AS (
  SELECT b.e,
    (SELECT SUM(long_liq)+SUM(short_liq) FROM liquidations
     WHERE interval='5min' AND ts >= b.e-interval '4 hours' AND ts < b.e)::numeric tc,
    (SELECT SUM(long_liq)+SUM(short_liq) FROM liquidations
     WHERE interval='5min' AND ts >= b.e-interval '4 hours'
       AND ts < b.e-interval '20 minutes')::numeric tv,
    (SELECT SUM(notional_usd) FROM liquidations_realtime
     WHERE exchange='binance' AND ts >= b.e-interval '4 hours' AND ts < b.e)::numeric s
  FROM bordes b),
peor AS (SELECT count(*) n, min(100*tc/NULLIF(s,0)) pc, max(100*tc/NULLIF(s,0)) mc,
                min(100*tv/NULLIF(s,0)) pv FROM par WHERE s > 0)
SELECT round(100*n_t.v/NULLIF(n_r.v,0),1)                    -- 1 nuevo, ahora
    || '|' || round(100*v_t.v/NULLIF(v_r.v,0),1)             -- 2 viejo, ahora
    || '|' || round(peor.pv::numeric,1)                      -- 3 PEOR con 20 min de retraso
    || '|' || round(100*(n_t.v*0.80)/NULLIF(n_r.v,0),1)      -- 4 discrepancia INYECTADA
    || '|' || CASE WHEN fin.f-interval '4 hours' >= ret.m THEN 'CUBRE' ELSE 'NO_CUBRE' END
    || '|' || round(extract(epoch FROM (now()-fin.f))/60.0,1)-- 6 retraso real ahora
    || '|' || peor.n                                         -- 7 ventanas utiles
    || '|' || round(peor.pc::numeric,1) || '|' || round(peor.mc::numeric,1)  -- 8,9 sin retraso
FROM n_t,n_r,v_t,v_r,fin,ret,peor"

OUT=$(TODO=1 "$B/bin/prodsql" "$SQL" 2>/dev/null | tr -d ' ' | head -1)
case "$OUT" in
  *'|'*'|'*'|'*'|'*'|'*'|'*'|'*'|'*) ;;
  *) echo "NO MEDIDO: 140 no contesto la consulta del control (salio '$OUT')"; exit 2 ;;
esac
NUEVO=$(printf '%s' "$OUT" | cut -d'|' -f1)
VIEJO=$(printf '%s' "$OUT" | cut -d'|' -f2)
RETR=$(printf  '%s' "$OUT" | cut -d'|' -f3)
INYEC=$(printf '%s' "$OUT" | cut -d'|' -f4)
CUBRE=$(printf '%s' "$OUT" | cut -d'|' -f5)
LAG=$(printf   '%s' "$OUT" | cut -d'|' -f6)
NVEN=$(printf  '%s' "$OUT" | cut -d'|' -f7)
PEORC=$(printf '%s' "$OUT" | cut -d'|' -f8)
MEJORC=$(printf '%s' "$OUT" | cut -d'|' -f9)

# el criterio del check, replicado aqui en una funcion y no tecleado en cada caso
banda() { python3 -c "print('dentro' if abs(100.0-float('$1'))<=15 else 'fuera')"; }

echo "K80-control · sujeto: el criterio del control D"
echo "  ahora: nuevo=$NUEVO%  viejo=$VIEJO%  inyectado=$INYEC%  retraso=$LAG min  retencion=$CUBRE"
echo "  sobre $NVEN ventana(s) de 4 h del horizonte de retencion:"
echo "    sin retraso        peor $PEORC%  mejor $MEJORC%"
echo "    con 20 min         peor $RETR%"
echo

# CERO VENTANAS UTILES NO ES CERO DEFECTOS: si la retencion se hubiera comido el horizonte,
# "no encontre ninguna fuera de banda" seria indistinguible de "no he mirado nada".
if [ "${NVEN:-0}" -lt 4 ]; then
  echo "NO MEDIDO: solo $NVEN ventana(s) de 4 h caben en el horizonte de retencion; con menos de 4 los casos P1 y N4 no prueban nada"
  exit 2
fi

echo "NEGATIVO · con la ventana completa en los dos lados, los feeds cuadran"
caso "N1 el cuadre de AHORA esta en banda"                "dentro" "$(banda "$NUEVO")"
caso "N2 y la retencion cubre la ventana"                 "CUBRE"  "$CUBRE"
caso "N4 y NINGUNA de las $NVEN ventanas se sale (peor)"  "dentro" "$(banda "$PEORC")"
caso "N4b tampoco por arriba (mejor)"                     "dentro" "$(banda "$MEJORC")"
# N3 · SIN ESTE CASO, N1 NO PRUEBA NADA: si el nuevo y el viejo dieran siempre lo mismo, el
# cambio no habria cambiado nada y N1 estaria pasando por casualidad.
caso "N3 con el retraso de hoy los dos criterios coinciden" "si" \
     "$(python3 -c "print('si' if abs(float('$NUEVO')-float('$VIEJO'))<=2 else 'no')")"

echo
echo "EL ARREGLO · el retraso rompia al viejo y no puede romper al nuevo"
# La reproduccion del 79.7 %: sobre la PEOR ventana del horizonte, cortar la tabla 20 min
# antes saca el cociente de banda. El criterio nuevo no puede llegar a ese estado porque su
# borde es el ultimo cubo cerrado, no `now()`.
caso "P1 la peor ventana con 20 min de retraso se sale"   "fuera"  "$(banda "$RETR")"
caso "P2 y sin retraso, esa misma peor ventana no"        "dentro" "$(banda "$PEORC")"

echo
echo "NO LO AFLOJO · una discrepancia de verdad sigue rompiendo el control"
# 80 % inyectado a mano sobre el lado de la tabla: es lo que se veria si el agregado
# empezara a perder eventos de binance. Tiene que salirse de banda.
caso "P3 una discrepancia real del 20 % se sale de banda" "fuera" "$(banda "$INYEC")"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
