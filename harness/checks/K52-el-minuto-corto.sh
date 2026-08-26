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
"$B/bin/prod" "journalctl -u $UNIDAD --since '$HORAS hours ago' --no-pager -o short-iso --utc -n 400 2>/dev/null | grep -E 'Stopping $UNIDAD|Started $UNIDAD|binance_connected'" 2>/dev/null > "$JOURNAL"
[ -s "$JOURNAL" ] || { echo "NO MEDIDO: el journal de 140 no devolvio nada para $UNIDAD en $HORAS h"; exit 2; }

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
if not paradas or not arranques:
    print(f"NO MEDIDO: el journal no trae paradas y arranques emparejables ({len(paradas)}/{len(arranques)})"); sys.exit(2)

ventanas = []
for parada in paradas:
    siguientes = [a for a in arranques if a > parada]
    if siguientes:
        ventanas.append((parada, min(siguientes)))
if not ventanas:
    print("NO MEDIDO: ninguna parada del journal tiene arranque despues; la ventana esta cortada"); exit(2)

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

# --- LO QUE SE EXIGE: el que solapa, ausente o marcado ---------------------------------
sin_marcar, marcados, control_malo, control_bueno, legado = [], 0, [], 0, 0
for ts, simbolo, cubierto, _n in filas:
    if cubierto == "NULO":
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

if legado and not marcados and not control_bueno:
    print(f"NO MEDIDO: las {legado} filas de la ventana tienen covered_seconds NULO; la marca aun no la escribe el productor"); sys.exit(2)
if sin_marcar:
    print(f"{len(sin_marcar)} buckets que solapan un reinicio pasan por completos: " + " · ".join(sin_marcar[:3])); sys.exit(1)
if control_malo:
    print(f"CONTROL POSITIVO ROTO: {len(control_malo)} buckets marcados sin reinicio que los explique: " + " · ".join(control_malo[:3])); sys.exit(1)
if control_bueno == 0:
    print("NO MEDIDO: ningun minuto sin reinicio en la ventana; el control positivo no se pudo correr"); sys.exit(2)
if marcados == 0 and len(ventanas) > 0:
    ausentes = sum(1 for ini, fin in ventanas if not any(solapa(ts) for ts, _, _, _ in filas))
    print(f"{len(ventanas)} ventanas de indisponibilidad y NINGUN bucket marcado ni ausente en ellas: o la marca no se escribe o las ventanas no se emparejan"); sys.exit(1)

print(f"{marcados} buckets que solapan un reinicio llevan marca legible y ninguno pasa por completo, sobre {len(ventanas)} ventanas de indisponibilidad del journal; y el CONTROL POSITIVO: {control_bueno} minutos sin reinicio, ninguno marcado. {legado} filas de legado con covered_seconds NULO")
' "$JOURNAL" "$DATOS" "$hay_columna" "$TABLA"
exit $?
