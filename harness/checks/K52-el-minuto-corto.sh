#!/bin/bash
# K52  EL MINUTO DEL ARRANQUE SE ESCRIBE CORTO, Y PASA POR COMPLETO.
#
# El drenaje de 717eb61 quito el bucket AUSENTE. No quita el bucket CORTO, y el corto es
# peor porque no se ve: la fila existe, K37 la cuenta como presente, data_gap no la mira,
# y el CVD, el delta y la absorcion derivados de ese minuto no saben que van cortos.
#
# LA CIFRA QUE LO JUSTIFICA, medida por el operador y REPRODUCIDA por mi via distinta
# (prodsql contra 140, ventana 2026-08-26 00:00Z-24:00Z, bordes UTC explicitos):
#   minuto de arranque   mediana 0.221 de trade_count contra sus vecinos · 21 presentes
#   control, ultimo minuto ANTES de la isla   0.910 sobre 23 bordes
#   linea base, todos los minutos del dia     0.923 sobre 1328 minutos
#   spot BTC combined: 6102865 USD observados contra 24386088 esperados en esos 21
#   minutos. El operador midio 0.221 / 0.973 / 0.933 y 22689555 esperados: la diferencia
#   sale de como cada uno define los vecinos, no de la conclusion. El efecto es de UN
#   SOLO LADO, que es lo que lo separa de un artefacto del metodo.
# Y NO ES DEL COLECTOR RECIEN ARREGLADO: futures_trades_agg, con drenaje desde las
#   00:26Z del 08-26, da los mismos ratios en los mismos arranques. Es el coste de
#   reconectar y lo pagan los dos colectores.
#
# QUE EXIGE ESTE CHECK, y de que NO habla.
#   EXIGE que ningun bucket de 1 minuto cuyo intervalo solape una ventana de
#     indisponibilidad del colector -de "Stopping" a la primera escritura tras "Started",
#     leida del journal de 140- aparezca en la tabla como una fila INDISTINGUIBLE de una
#     completa. O no esta -y entonces lo cuenta K37- o lleva una marca legible POR LA API
#     sin conocer el journal. La marca es covered_seconds: segundos del minuto que el
#     colector estuvo escuchando; 60 es completo y NULL es legado.
#   CONTROL POSITIVO, en el mismo check y obligatorio: un minuto SIN reinicio no puede
#     salir marcado. Un guardia que marca todo esta tan roto como el que no marca nada, y
#     ese brazo es el que nadie prueba.
#   NO habla de si el minuto corto debe escribirse o no. Si se decidiera NO escribirlo,
#     K37 SUBIRIA, y eso no seria una regresion: es la misma perdida hecha visible.
#     Queda dicho aqui con fecha, 2026-08-26, para que nadie lo lea como empeoramiento.
#   NOMED si el journal no cubre la ventana entera: la ventana de indisponibilidad es el
#     instrumento, y sin instrumento no hay cifra.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
UNIDAD=coinalyze-ws.service
TABLA=spot_trades_agg
HORAS=6

hay_columna=$("$B/bin/prodsql" "
  SELECT count(*) FROM information_schema.columns
  WHERE table_schema='public' AND table_name='$TABLA' AND column_name='covered_seconds'" 2>/dev/null | grep -E '^[0-9]+$' | head -1)
[ -n "$hay_columna" ] || { echo "NO MEDIDO: no se pudo consultar el esquema de $TABLA"; exit 2; }

JOURNAL=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero del journal"; exit 2; }
DATOS=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de datos"; exit 2; }
trap 'rm -f "$JOURNAL" "$DATOS"' EXIT

# La ventana de indisponibilidad sale del journal, que es la unica fuente que sabe
# cuando el proceso NO estaba. Se piden las dos puntas y se emparejan en python.
# LA MARCA DE CANAL NO ES ADORNO. Un journal vacio y una lectura que fallo se veian IGUAL:
# ambos daban fichero vacio. Al dejar de ser fatal el vacio -que es lo que permite juzgar un
# dia tranquilo- esa ambiguedad se convertiria en FALLO ABIERTO: un canal roto se leeria como
# "no hubo reinicios" y el check aprobaria. Por eso el comando remoto emite una marca al
# final: sin marca, no hubo lectura. Es la leccion de K52b aplicada a su hermano.
"$B/bin/prod" "journalctl -u $UNIDAD --since '$HORAS hours ago' --no-pager -o short-iso --utc -n 400 2>/dev/null | grep -E 'Stopping $UNIDAD|Started $UNIDAD|binance_connected'; echo __CANAL_OK__" 2>/dev/null > "$JOURNAL"
grep -q '^__CANAL_OK__$' "$JOURNAL" || {
  echo "NO MEDIDO: el canal del journal de 140 no contesto para $UNIDAD -no llego la marca de canal-. Esto NO es un dia sin reinicios: es una lectura que fallo, y confundirlas seria fallar ABIERTO"
  exit 2
}
EVENTOS=$(grep -cE "Stopping $UNIDAD|Started $UNIDAD|binance_connected" "$JOURNAL" 2>/dev/null || true)
[ -n "$EVENTOS" ] || EVENTOS=0

# CUANTO HACE DEL ULTIMO REINICIO. NO ensancha la ventana de JUICIO -- que sigue siendo
# $HORAS h y no se toca -- sino que da el dato para DECLARAR el silencio en la salida. Sin
# el, un brazo que lleva dos dias sin sujeto se lee igual que uno que lo tuvo hace una hora.
# MEDIDO: en 29.5 dias el sujeto solo existe el 44.2 % del tiempo, con 32 huecos de mas de
# 6 h y los mayores de casi 49 h. El silencio es la norma, no la excepcion, y tiene que verse.
# SE MIRA POR REINICIOS DE LA UNIDAD, NO POR EVENTOS, y por el mismo motivo que el veredicto
# de abajo: con EVENTOS estaban dentro las reconexiones de binance, asi que en reposo -- que
# es cuando este dato hace falta -- EVENTOS>0 y el silencio salia "desconocido" justo en el
# caso que hay que declarar. Medido el 2026-09-02: 0 reinicios y aun asi "ultimo hace
# desconocido". Y la busqueda de 30 dias tampoco puede mirar binance_connected: preguntamos
# cuando se reinicio la UNIDAD, no cuando reconecto el feed.
REINICIOS=$(grep -cE "Stopping $UNIDAD|Started $UNIDAD" "$JOURNAL" 2>/dev/null || true)
[ -n "$REINICIOS" ] || REINICIOS=0
SILENCIO="desconocido"
if [ "$REINICIOS" = "0" ]; then
  ULTIMO=$("$B/bin/prod" "journalctl -u $UNIDAD --since '30 days ago' --no-pager -o short-iso --utc 2>/dev/null | grep -E 'Started $UNIDAD' | tail -1 | cut -c1-19" 2>/dev/null | tr -d " \n")
  case "$ULTIMO" in
    20[0-9][0-9]-*T*)
      SILENCIO="$(python3 -c "
import sys
from datetime import datetime, UTC
t = datetime.fromisoformat('$ULTIMO' + '+00:00')
print('%.1f h' % ((datetime.now(UTC) - t).total_seconds() / 3600.0))
" 2>/dev/null || echo desconocido)" ;;
    *) SILENCIO="mas de 30 dias o ilegible" ;;
  esac
fi

# La marca puede no existir todavia: se pide solo si la columna esta, y si no se pide
# 'NULO', que es lo que el python interpreta como legado. Preguntar por una columna
# ausente haria fallar la consulta entera y el check saldria NO MEDIDO por el canal
# cuando en realidad el fallo es el que viene a cazar.
if [ "$hay_columna" = "0" ]; then MARCA="'NULO'"; else MARCA="coalesce(covered_seconds::text,'NULO')"; fi
TODO=1 "$B/bin/prodsql" "
  SELECT to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SSZ'), symbol,
         $MARCA, trade_count
  FROM $TABLA
  WHERE exchange='combined' AND interval='1min'
    AND ts >= now() - interval '$HORAS hours' AND ts < date_trunc('minute', now()) - interval '4 minutes'
  ORDER BY ts" 2>/dev/null | grep -E '^2026-' > "$DATOS"
[ -s "$DATOS" ] || { echo "NO MEDIDO: $TABLA no devolvio filas en las ultimas $HORAS h"; exit 2; }

python3 -c '
import sys
from datetime import datetime, timedelta, UTC

camino_journal, camino_datos, hay_columna, tabla = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
eventos, silencio = int(sys.argv[5] or 0), sys.argv[6]

def hora(t):
    return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(UTC)

# --- las ventanas de indisponibilidad, emparejando Stopping con la primera escritura ---
paradas, arranques = [], []
for linea in open(camino_journal):
    partes = linea.split()
    if len(partes) < 2:
        continue
    try:
        t = hora(partes[0])
    except ValueError:
        continue
    if "Stopping" in linea:
        paradas.append(t)
    elif "Started" in linea or "binance_connected" in linea:
        arranques.append(t)
# EL VEREDICTO PARTIDO. Antes, un journal sin eventos hacia INMEDIBLE el check entero, y
# eso es mas de la mitad del tiempo: medido sobre 29.5 dias, el sujeto del brazo del solape
# solo existe el 44.2 % del tiempo -- 394.6 h de 707 sin ningun reinicio en 6 h, con 32
# huecos por encima de la ventana y los mayores cerca de 49 h.
# Dejarlo en NOMED = el arnes sin medir el 55.8 % del tiempo. Ponerlo en VERDE = aprobar la
# nada el 55.8 % del tiempo. NINGUNA DE LAS DOS: el veredicto lo dan los brazos que SIEMPRE
# tienen sujeto -los nulos posteriores al corte y el control positivo sobre los minutos SIN
# reinicio- y el del solape DECLARA que hoy no se juzgo, con cuanto lleva sin sujeto.
# No se toca $HORAS. Un umbral que se ensancha hasta dejar de quejarse es indistinguible de
# aflojar el criterio, y ademas aqui no arreglaria nada: ninguna anchura FABRICA reinicios.
# SIN SUJETO SE DECIDE POR "NINGUNA PARADA", NO POR "NINGUN EVENTO". La particion anterior
# usaba eventos==0 y dejaba fuera el caso MAS COMUN en reposo: el grep de :58 tambien recoge
# binance_connected, y :122 lo mete en ARRANQUES. Dos reconexiones de websocket sin ningun
# reinicio dan eventos=2, paradas=0, arranques=2 -- el journal NO esta vacio, la rama de
# "dia tranquilo" no disparaba, y el elif de abajo tiraba un exit 2. Medido el 2026-09-02:
# el ultimo reinicio real fue 17 h antes, o sea reposo puro, y el check salia NO MEDIDO
# diciendo "2 eventos pero ninguna pareja (0/2)". Una reconexion de feed NO es un reinicio
# de unidad: sin parada no hay nada que solapar, y eso es no tener sujeto, no un fallo.
#
# LO QUE SIGUE SIENDO NO MEDIDO, y por eso no basta con "ninguna pareja": una parada SIN
# arranque posterior es una VENTANA ABIERTA -el servicio se fue y no ha vuelto dentro de la
# ventana-. Declarar eso VERDE esconderia un servicio caido, que es justo lo contrario de
# lo que este check existe para ver.
ventanas = []
if not paradas:
    juzga_solape = False
else:
    for parada in paradas:
        siguientes = [a for a in arranques if a > parada]
        if siguientes:
            ventanas.append((parada, min(siguientes)))
    if not ventanas:
        print(f"NO MEDIDO: las {len(paradas)} paradas del journal no tienen arranque despues; la ventana esta cortada"); sys.exit(2)
    juzga_solape = True

def solapa(ts):
    fin = ts + timedelta(minutes=1)
    return any(ini < fin and fin_v > ts for ini, fin_v in ventanas)

filas = []
for linea in open(camino_datos):
    p = linea.rstrip("\n").split("|")
    if len(p) < 4:
        continue
    filas.append((hora(p[0]), p[1], p[2], int(p[3])))
if not filas:
    print(f"NO MEDIDO: no se pudieron leer filas de {tabla}"); sys.exit(2)

if hay_columna == "0":
    afectados = sorted({ts.strftime("%H:%M") for ts, _, _, _ in filas if solapa(ts)})
    print(f"{tabla} no tiene covered_seconds: {len(afectados)} minutos que solapan un reinicio estan guardados como filas indistinguibles de una completa -{afectados[:4]}- y {len(ventanas)} ventanas de indisponibilidad en el journal"); sys.exit(1)

# --- EL LEGADO SE SEPARA POR TIEMPO, NO POR NULIDAD -----------------------------------
# El operador lo cazo induciendolo: con "si es NULO, legado" ANTES de mirar el solape, un
# simbolo -o un venue, o un feed nuevo- que NUNCA escriba la marca pasa para siempre,
# porque su nulo se lee como legado. Cazaba la regresion TOTAL y la mentira, y no la
# PARCIAL. El discriminador tiene que ser el CORTE: el primer ts con marca. Antes de el,
# legado declarado; a partir de el, un nulo es un productor que dejo de marcar.
marcados_ts = [ts for ts, _s, cubierto, _n in filas if cubierto != "NULO"]
if not marcados_ts:
    print(f"NO MEDIDO: ninguna fila de la ventana lleva marca; el productor aun no la escribe"); sys.exit(2)
corte = min(marcados_ts)

sin_marcar, marcados, control_malo, control_bueno, legado, nulos_tarde = [], 0, [], 0, 0, []
for ts, simbolo, cubierto, _n in filas:
    if cubierto == "NULO":
        if ts >= corte:
            nulos_tarde.append(f"{ts.strftime("%H:%M")}/{simbolo}" + (" (solapa un reinicio)" if solapa(ts) else ""))
        else:
            legado += 1
        continue
    segundos = int(cubierto)
    if solapa(ts):
        if segundos >= 60:
            sin_marcar.append(f"{ts.strftime("%H:%M")}/{simbolo} dice {segundos}s")
        else:
            marcados += 1
    else:
        # --- CONTROL POSITIVO: sin reinicio no se marca ---
        if segundos < 60:
            control_malo.append(f"{ts.strftime("%H:%M")}/{simbolo} marcado {segundos}s SIN reinicio")
        else:
            control_bueno += 1

if nulos_tarde:
    print(f"{len(nulos_tarde)} buckets POSTERIORES al corte {corte.strftime("%H:%MZ")} sin marca: alguien dejo de escribirla y su nulo se leeria como legado -> " + " · ".join(nulos_tarde[:3])); sys.exit(1)
if legado and not marcados and not control_bueno:
    print(f"NO MEDIDO: las {legado} filas de la ventana tienen covered_seconds NULO; la marca aun no la escribe el productor"); sys.exit(2)
if sin_marcar:
    print(f"{len(sin_marcar)} buckets que solapan un reinicio pasan por completos: " + " · ".join(sin_marcar[:3])); sys.exit(1)
if control_malo:
    print(f"CONTROL POSITIVO ROTO: {len(control_malo)} buckets marcados sin reinicio que los explique: " + " · ".join(control_malo[:3])); sys.exit(1)
if control_bueno == 0:
    print("NO MEDIDO: ningun minuto sin reinicio en la ventana; el control positivo no se pudo correr"); sys.exit(2)
if juzga_solape and marcados == 0 and len(ventanas) > 0:
    ausentes = sum(1 for ini, fin in ventanas if not any(solapa(ts) for ts, _, _, _ in filas))
    print(f"{len(ventanas)} ventanas de indisponibilidad y NINGUN bucket marcado ni ausente en ellas: o la marca no se escribe o las ventanas no se emparejan"); sys.exit(1)

cola = (f"CONTROL POSITIVO: {control_bueno} minutos sin reinicio, ninguno marcado; y CERO nulos "
        f"posteriores al corte {corte.strftime("%H:%MZ")}, que es lo que separa el legado "
        f"-{legado} filas- de un productor que dejo de marcar")
if juzga_solape:
    print(f"{marcados} buckets que solapan un reinicio llevan marca legible y ninguno pasa por "
          f"completo, sobre {len(ventanas)} ventanas de indisponibilidad del journal; {cola}")
else:
    # NO se cuenta como aprobado: se dice que no se juzgo, y cuanto lleva sin poder juzgarse.
    print(f"BRAZO DEL SOLAPE SIN SUJETO Y DECLARADO: 0 reinicios de la unidad en la ventana "
          f"-ultimo hace {silencio}-, asi que hoy NO se juzga y NO se cuenta como aprobado. "
          f"Lo que SI se juzgo, con sujeto: {cola}")
' "$JOURNAL" "$DATOS" "$hay_columna" "$TABLA" "$EVENTOS" "$SILENCIO"
exit $?
