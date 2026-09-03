#!/bin/bash
# K85  EL RECICLADO PROGRAMADO FABRICA HANDSHAKES QUE NO NECESITA, Y CUANDO EL NUEVO NO
#      ENTRA EL LOG NO DICE POR QUE.
#
# POR QUE EXISTE. El 2026-09-02 hacia las 13:00Z el laboratorio empezo a perder el 35-50 %
# de los handshakes hacia AWS ap-northeast-1 (fstream.binance.com), medido desde 140, 143 y
# el host Proxmox, en todas las IPs y tambien contra ec2.ap-northeast-1.amazonaws.com, con
# api.binance.com -otro edge- yendo 4/4 (hechos.tsv:1289). ESO ES DEL ISP Y NO ES MIO.
# LO QUE SI ES DE LA APP es cuantos handshakes le pide a esa red: binance_loop tira una
# conexion VIVA Y SANA cada 300 s por reloj y abre otra (scalp_collector.py:1005-1009).
# Medido en 140 el 2026-09-03, ventana de 3 h cerrada a las 04:45Z: 31 reciclados
# programados -10.3/h- y 33 binance_futures_disconnected, los tres ultimos TimeoutError con
# retry=10.0s. A 30 dias el operador midio 7577 reciclados y 290 TimeoutError, de los que
# 177 caen en el 09-02/03 y CERO en los 13 dias previos.
#
# Y EL RECICLADO NO HACE FALTA. depth10@100ms es un stream de SNAPSHOT PARCIAL: cada mensaje
# trae el top-10 entero y handle_binance lo aplica con BOOK_STORE.set_snapshot (:1066), que
# REEMPLAZA el libro. apply_delta (:391) solo lo usa bybit, que si reconstruye por deltas y
# por eso resincroniza por hueco de update ID (:1289). No hay estado incremental que
# desincronizar. El modo de fallo real -libro rancio o retrasado- ya lo cubren
# BINANCE_BOOK_MAX_EVENT_LAG_SECONDS=10 y BINANCE_BOOK_STALE_SECONDS=15, que actuan sobre
# EVIDENCIA y no sobre un reloj; y los 301 resyncs por evidencia de 30 dias ocurren solos.
# El parametro entro con la semilla del repo -472e357, unico commit que lo toca- sin
# comentario y sin historia detras.
#
# LOS CUATRO BRAZOS, Y POR QUE DOS PREGUNTAN POR EL RELEASE Y NO POR EL REPO.
#   A · CAUSA. El valor que gobierna NO es el default de config.py: es el que el proceso
#       tiene en su entorno. install.sh:145 escribio 300 en /etc/coinalyze/coinalyze.env UNA
#       vez, en la instalacion, y el desplegador NO reescribe ese fichero -deploy-coinalyze
#       solo lo lee, :56 y :75-. Cambiar el default de config.py sin tocar el env de 140 es
#       un NO-OP en produccion. Por eso A lee /proc/<MainPID>/environ, no el fichero ni el
#       repo; si la variable no esta en el entorno, entonces si manda el default del
#       release y es ahi donde A la busca.
#   B · EFECTO. Reciclados programados por hora en el journal, dentro de la ventana de
#       uptime. Es INSENSIBLE AL ISP: un handshake que falla escribe _disconnected, no
#       _resync, asi que esta cifra mide lo que hace la app y no lo que hace la red. Es el
#       brazo que no puedo aprobar cambiando una constante.
#   C · El release desplegado abre con open_timeout por encima del default de 10 s de
#       websockets. La conexion de 4.2 s medida desde el host Proxmox prueba que la
#       retransmision de SYN recupera; con 10 s la reconexion se rinde antes que el kernel,
#       que reintenta a 1, 3, 7, 15 y 31 s.
#   D · El release desplegado escribe el CODIGO de cierre. Hoy :1016 loguea
#       type(exc).__name__ y nada mas, y por eso una prediccion de 1008 sobre cinco
#       ConnectionClosedError quedo INMEDIBLE, no refutada (hechos.tsv:1280).
#   C y D preguntan por /opt/coinalyze/current A PROPOSITO: mergeado no es desplegado, y
#   sobre mi propia rama las dos saldrian VERDE sin que 140 hubiera cambiado.
#
# CONTROL, corrido el 2026-09-03 antes de tocar nada. Con los listones de casa los CUATRO
# brazos fallan: 300 s de reciclado en el entorno del proceso 565617 · 64 reciclados
# programados en 21600 s = 10.66/h · open_timeout=10 s · sin code=. Con
# K85_MINIMO=100 K85_LISTON_HORA=20 el mensaje se queda en C y D, o sea que A y B SI se
# apagan. C y D se probaron por su lado contra el fichero de la rama con el mismo awk y el
# mismo grep -> open_timeout=30 y la linea con code=%s: los dos brazos saben ponerse verdes.
# K85_RELEASE apunta a otro arbol de 140 si hace falta interrogar uno distinto del release.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
MINIMO=${K85_MINIMO:-3600}              # segundos de reciclado programado exigidos
LISTON=${K85_LISTON_HORA:-2}            # reciclados programados por hora admitidos
ABIERTO=${K85_OPEN_TIMEOUT_MIN:-10}     # open_timeout tiene que SUPERAR este valor
VENTANA_MAX=21600                       # 6 h; mas atras no hace falta para medir una tasa
UPTIME_MIN=1200                         # por debajo de 20 min la tasa es ruido, no medida
RELEASE=${K85_RELEASE:-/opt/coinalyze/current}   # arbol que C y D interrogan, en 140

# --- A · CAUSA · el valor que el proceso tiene de verdad ---------------------------------
pid=$("$B/bin/prod" 'systemctl show -p MainPID --value coinalyze-scalp.service' 2>/dev/null | tr -d ' \n')
case "$pid" in ''|0|*[!0-9]*) echo "NO MEDIDO: no se pudo leer el MainPID de coinalyze-scalp"; exit 2 ;; esac

linea=$("$B/bin/prod" "tr '\\0' '\\n' < /proc/$pid/environ | grep '^BINANCE_BOOK_FORCE_RECONNECT_SECONDS=' || true" 2>/dev/null | head -1)
if [ -n "$linea" ]; then
  valor=${linea#*=}; origen="entorno del proceso $pid"
else
  # Sin variable en el entorno manda el default del release, no el del repo.
  valor=$("$B/bin/prod" "grep -o 'BINANCE_BOOK_FORCE_RECONNECT_SECONDS: int = Field(default=[0-9]*' $RELEASE/app/config.py || true" 2>/dev/null | grep -o '[0-9]*$' | head -1)
  origen="default de config.py del release (no hay variable en el entorno)"
fi
case "$valor" in ''|*[!0-9]*) echo "NO MEDIDO: BINANCE_BOOK_FORCE_RECONNECT_SECONDS ilegible ($origen)"; exit 2 ;; esac

# --- B · EFECTO · reciclados por hora en el journal ---------------------------------------
arranque=$("$B/bin/prod" 'date -u -d "$(systemctl show coinalyze-scalp -p ActiveEnterTimestamp --value)" +%FT%TZ' 2>/dev/null | tr -d ' \n')
case "$arranque" in
  20[0-9][0-9]-*T*Z) ;;
  *) echo "NO MEDIDO: no se pudo leer el ultimo arranque de coinalyze-scalp"; exit 2 ;;
esac
edad=$(( $(date -u +%s) - $(date -u -d "$arranque" +%s) ))
[ "$edad" -ge "$UPTIME_MIN" ] || { echo "NO MEDIDO: el colector arranco hace ${edad}s; hacen falta $UPTIME_MIN para una tasa"; exit 2; }
ventana=$edad; [ "$ventana" -gt "$VENTANA_MAX" ] && ventana=$VENTANA_MAX
# La ventana se pide RELATIVA. journalctl lee un --since absoluto en la zona LOCAL de 140,
# que es America/Mexico_City: pasarle una marca UTC adelanta la ventana seis horas y
# devuelve una linea. Salio asi la primera vez que lo corri.
desde="${ventana} seconds ago"

cuentas=$("$B/bin/prod" "journalctl -u coinalyze-scalp --utc -o short-iso --since '$desde' --no-pager | awk '{n++} /binance_futures_resync reason=scheduled/{r++} /binance_futures_disconnected/{d++} END{printf \"%d %d %d\\n\", n+0, r+0, d+0}'" 2>/dev/null | tr -d '\r')
set -- $cuentas
[ $# -eq 3 ] || { echo "NO MEDIDO: el journal de 140 no devolvio cuentas legibles"; exit 2; }
total=$1; reciclados=$2; caidas=$3
# Journal vacio no es cero reciclados: es un canal que no midio. La leccion es de K52.
[ "$total" -gt 0 ] || { echo "NO MEDIDO: el journal de coinalyze-scalp no trae ninguna linea en ${ventana}s"; exit 2; }
tasa_x100=$(( reciclados * 360000 / ventana ))   # reciclados/hora, con dos decimales enteros

# --- C y D · lo que hay DESPLEGADO en /opt/coinalyze/current -------------------------------
cuerpo=$("$B/bin/prod" "awk '/^async def binance_loop/,/^async def handle_binance/' $RELEASE/app/scalp_collector.py" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: no se pudo leer binance_loop del release desplegado"; exit 2; }
printf '%s\n' "$cuerpo" | grep -q 'websockets.connect(' || { echo "NO MEDIDO: binance_loop del release no trae websockets.connect"; exit 2; }
abierto=$(printf '%s\n' "$cuerpo" | grep -o 'open_timeout=[0-9]*' | head -1 | cut -d= -f2)
[ -n "$abierto" ] || abierto=10                  # sin el argumento, el default de websockets
# Se pide la linea del FORMATO -la que empieza por comilla-, no cualquiera que nombre el
# evento: un comentario tambien lo nombraria. Es la trampa 3 del ESTADO.
formato=$(printf '%s\n' "$cuerpo" | grep '"binance_futures_disconnected' | head -1)
[ -n "$formato" ] || { echo "NO MEDIDO: el release no trae el formato de binance_futures_disconnected"; exit 2; }

# --- veredicto ----------------------------------------------------------------------------
fallos=""
[ "$valor" -ge "$MINIMO" ] || fallos="${fallos:+$fallos · }A: recicla cada ${valor}s (<$MINIMO) segun el $origen"
[ "$tasa_x100" -le $(( LISTON * 100 )) ] || fallos="${fallos:+$fallos · }B: $reciclados reciclados programados en ${ventana}s = $(( tasa_x100 / 100 )).$(printf '%02d' $(( tasa_x100 % 100 )))/h (liston $LISTON/h)"
[ "$abierto" -gt "$ABIERTO" ] || fallos="${fallos:+$fallos · }C: el release abre con open_timeout=${abierto}s (hace falta >$ABIERTO)"
case "$formato" in *code=*) ;; *) fallos="${fallos:+$fallos · }D: el release loguea la caida sin el codigo de cierre" ;; esac

resumen="reciclado ${valor}s · $(( tasa_x100 / 100 )).$(printf '%02d' $(( tasa_x100 % 100 )))/h en ${ventana}s · $caidas caidas · open_timeout=${abierto}s"
if [ -n "$fallos" ]; then
  echo "$fallos"
  echo "  medido en 140 desde $desde ($resumen; $total lineas de journal)"
  exit 1
fi
echo "binance no se recicla por reloj y la caida se loguea con codigo: $resumen"
exit 0
