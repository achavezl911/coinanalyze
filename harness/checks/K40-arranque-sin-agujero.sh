#!/bin/bash
# K40  reiniciar el colector no puede costar tres minutos de operativa.
#
# El colector guarda los buckets de minuto en RAM y solo los escribe cuando han pasado
# LATE_TRADE_GRACE_SECONDS=125 s desde que el minuto cerro (scalp_collector.py:64 y
# 192-196), o sea en M+185 s. main() no instala manejador de SIGTERM, asi que systemd
# mata el proceso en el acto -Stopping y Deactivated en el MISMO segundo- y todo lo que
# no llego a M+185 se pierde: los minutos con M > T-185, que son TRES.
#
# Medido el 2026-08-25: 19 despliegues, 33 minutos ausentes de futures_trades_agg en 14
# rachas, las 14 empezando en un despliegue, iguales en los TRES simbolos y en los TRES
# exchanges. Eso es lo que puso a K37 en "4 de 24".
#
# EL SUJETO ES EL ULTIMO ARRANQUE, no el historico: asi el check mide lo que hace el
# codigo que corre AHORA y no lo que hizo el de antes. Por eso el arreglo se observa en
# el SEGUNDO despliegue: el primero mata al codigo viejo, que aun no sabe vaciar.
#
# EL LISTON ES UNO, Y UNO NO ES AFLOJAR. El minuto en curso al morir esta a medias:
# escribirlo entero lo convertiria de ausencia declarable en cifra silenciosamente
# incompleta, que es peor. Los minutos YA CERRADOS que siguen en RAM no tienen ese
# problema y no hay excusa para perderlos.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
LISTON=${K40_LISTON:-1}

arranque=$("$B/bin/prod" 'date -u -d "$(systemctl show coinalyze-scalp -p ActiveEnterTimestamp --value)" +%FT%TZ' 2>/dev/null | tr -d ' \n')
case "$arranque" in
  20[0-9][0-9]-*T*Z) ;;
  *) echo "NO MEDIDO: no se pudo leer el ultimo arranque de coinalyze-scalp"; exit 2 ;;
esac

# Un arranque de hace menos de 6 min no se puede juzgar: los ultimos buckets todavia no
# son elegibles para escribirse (M+185 s) y saldrian como ausentes sin serlo.
edad=$(( $(date -u +%s) - $(date -u -d "$arranque" +%s) ))
[ "$edad" -ge 360 ] || { echo "NO MEDIDO: el colector arranco hace ${edad}s; hacen falta 360 para juzgarlo"; exit 2; }

# Ventana: los cuatro minutos anteriores al arranque y el del arranque. Ahi caen los
# tres que el colchon de 125 s se lleva, y sobra margen por si la parada se adelanta.
#
# PERO la ventana se recorta al ARRANQUE ANTERIOR. Un proceso no puede haber perdido
# minutos de antes de nacer, y con dos despliegues seguidos el agujero del primero cae
# dentro de los cuatro minutos del segundo. Medido el 2026-08-26: arranques a las
# 00:26:38 y 00:28:27, faltan 00:24 y 00:25 -del apagado del codigo VIEJO, que aun no
# drenaba- y estan 00:26, 00:27 y 00:28, o sea que el apagado ordenado de las 00:28:16
# no perdio NADA. Sin este recorte el check le imputaba al segundo lo del primero.
# El criterio no se toca: sigue siendo "el ultimo apagado no perdio mas de un minuto".
ini=$(date -u -d "$arranque -4 minutes" +%FT%T)
anteriores=$("$B/bin/prod" "journalctl -u coinalyze-scalp --utc -o short-iso --since '2 days ago' --no-pager | grep 'Started coinalyze-scalp' | tail -6 | cut -d' ' -f1" 2>/dev/null)
for previo in $anteriores; do
  p=$(date -u -d "$previo" +%FT%T 2>/dev/null) || continue
  [ "$p" \< "$(date -u -d "$arranque" +%FT%T)" ] || continue
  [ "$p" \> "$ini" ] && ini=$p
done
fin=$(date -u -d "$arranque +1 minutes" +%FT%T)

filas=$("$B/bin/prodsql" "WITH g AS (SELECT generate_series(date_trunc('minute', timestamptz '$ini+00'), date_trunc('minute', timestamptz '$fin+00'), interval '1 minute') AS ts) SELECT s.symbol, count(*) FILTER (WHERE f.ts IS NULL) AS ausentes FROM (VALUES ('BTCUSDT_PERP.A'),('ETHUSDT_PERP.A'),('SOLUSDT_PERP.A')) AS s(symbol) CROSS JOIN g LEFT JOIN futures_trades_agg f ON f.symbol=s.symbol AND f.exchange='binance' AND f.interval='1min' AND f.ts=g.ts GROUP BY 1 ORDER BY 1" 2>/dev/null)
[ -n "$filas" ] || { echo "NO MEDIDO: la consulta de futures_trades_agg no devolvio nada"; exit 2; }

peor=0; detalle=""
while IFS='|' read -r sim ausentes; do
  [ -n "$sim" ] || continue
  case "$ausentes" in ''|*[!0-9]*) echo "NO MEDIDO: cuenta ilegible para $sim"; exit 2 ;; esac
  [ "$ausentes" -gt "$peor" ] && peor=$ausentes
  detalle="${detalle:+$detalle }${sim%%USDT*}=$ausentes"
done <<EOF
$filas
EOF

[ -n "$detalle" ] || { echo "NO MEDIDO: ningun simbolo medido"; exit 2; }

if [ "$peor" -gt "$LISTON" ]; then
  echo "el arranque de $arranque dejo $peor minutos ausentes (liston $LISTON): $detalle"
  exit 1
fi
echo "el arranque de $arranque dejo como mucho $peor minuto ausente: $detalle"
exit 0
