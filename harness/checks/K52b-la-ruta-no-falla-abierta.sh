#!/bin/bash
# K52b  "NO FALTA NADA" Y "NO LO SE" NO PUEDEN SER EL MISMO JSON.
#
# K52 cierra que la marca se escriba. Esto cierra la otra mitad, la que toca al
# consumidor: que la ruta la SIRVA de forma que un bucket sin marca no se confunda con
# uno completo. Lo cazo el operador ejecutando /api/whale/delta, no leyendo api.py:
# short_minutes era count(*) FILTER (WHERE covered_seconds < 60) y una fila NULA no
# satisface ese filtro, asi que contaba como completa. Los buckets de 21:45 y 22:00
# -que contienen minutos que sabemos perdidos- devolvian covered_seconds_min=null y
# short_minutes=0, salida IDENTICA a la de un bucket completo de verdad. Es la regla de
# K03 -el hueco no se infiere de los nulos- incumplida por el codigo que anadio la marca.
#
# ESTE CHECK EJECUTA LA RUTA. No lee app/api.py ni static/app.js: lo que se comprueba es
# lo que un llamante recibe, porque es lo unico que el llamante puede ver.
#
# LO QUE EXIGE
#   1 · cada fila servida trae unknown_minutes, que dice cuantos minutos del bucket no
#       tienen marca. Sin ese campo, "no lo se" no es expresable.
#   2 · ninguna fila puede estar en el estado que fallaba abierto: covered_seconds_min
#       nulo Y unknown_minutes en 0. Eso es exactamente "no lo se disfrazado de completo".
#   3 · un bucket POSTERIOR al corte que contenga un reinicio del journal tiene que
#       declararlo: short_minutes >= 1.
#   CONTROL POSITIVO, obligatorio: un bucket posterior al corte y SIN reinicio no puede
#       salir ni marcado ni desconocido -short_minutes y unknown_minutes en 0-. Un
#       guardia que marca todo esta tan roto como el que no marca nada.
#   NOMED si falta cualquiera de los dos brazos: sin bucket con reinicio y sin bucket sin
#       el, no hay medicion, y decir VERDE seria decirlo sobre una sola mitad.
#
# LA MARCA NO ES UN FACTOR DE ESCALA, y el check NO la usa como tal. Medido sobre los 21
# arranques del 2026-08-26 con bucket presente: fraccion declarada 0.367 de mediana
# contra 0.182 de volumen observado, razon 0.452, y 17 de 21 por debajo de lo declarado.
# Los primeros segundos tras reconectar no son productivos. Dice QUE falta, no CUANTO.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
RUTA=/api/whale/delta
UNIDAD=coinalyze-ws.service
SIMBOLO=BTCUSDT_PERP.A
HORAS=6

JOURNAL=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero del journal"; exit 2; }
CUERPO=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de respuesta"; exit 2; }
trap 'rm -f "$JOURNAL" "$CUERPO"' EXIT

"$B/bin/prod" "journalctl -u $UNIDAD --since '$HORAS hours ago' --no-pager -o short-iso --utc -n 400 2>/dev/null | grep -E 'Started $UNIDAD'" 2>/dev/null > "$JOURNAL"
[ -s "$JOURNAL" ] || { echo "NO MEDIDO: el journal de 140 no trae arranques de $UNIDAD en $HORAS h"; exit 2; }

TODO=1 "$B/bin/api" "$RUTA?symbol=$SIMBOLO&interval=15min&limit=96" > "$CUERPO" 2>/dev/null
[ -s "$CUERPO" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

python3 -c '
import json, sys
from datetime import datetime, timedelta, UTC

camino_journal, camino_cuerpo, ruta, horas = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
crudo = open(camino_cuerpo).read()
try:
    d = json.loads(crudo)
except Exception as e:
    print(f"NO MEDIDO: {ruta} no devolvio JSON ({e}): {crudo[:80]!r}"); sys.exit(2)
filas = d.get("rows") if isinstance(d, dict) else None
if not filas:
    print(f"NO MEDIDO: {ruta} no sirve filas: claves {list(d)[:6] if isinstance(d, dict) else type(d).__name__}"); sys.exit(2)

def hora(t):
    return datetime.fromisoformat(str(t).replace("Z", "+00:00")).astimezone(UTC)

arranques = []
for linea in open(camino_journal):
    try:
        arranques.append(hora(linea.split()[0]))
    except (IndexError, ValueError):
        continue
if not arranques:
    print("NO MEDIDO: no se pudo leer ningun arranque del journal"); sys.exit(2)
desde = min(hora(f["bucket"]) for f in filas)
arranques = [a for a in arranques if a >= desde]

# --- 1 · el campo tiene que existir ---------------------------------------------------
if any("unknown_minutes" not in f for f in filas):
    print(f"{ruta} no sirve unknown_minutes: un bucket sin marca no se puede distinguir de uno completo, que es como fallaba abierto"); sys.exit(1)

# --- 2 · nadie puede estar en el estado que fallaba abierto ---------------------------
abiertos = [str(f["bucket"])[11:16] for f in filas
            if f.get("covered_seconds_min") is None and not f.get("unknown_minutes")]
if abiertos:
    print(f"{len(abiertos)} buckets dicen covered_seconds_min=null con unknown_minutes=0, que es \"no lo se\" disfrazado de completo: {abiertos[:4]}"); sys.exit(1)

# --- el corte: el primer bucket con marca ---------------------------------------------
con_marca = [hora(f["bucket"]) for f in filas if f.get("covered_seconds_min") is not None]
if not con_marca:
    print(f"NO MEDIDO: ningun bucket servido lleva marca; el productor aun no la escribe o la ventana es toda de legado"); sys.exit(2)
corte = min(con_marca)

def tiene_arranque(inicio, ancho):
    return any(inicio <= a < inicio + ancho for a in arranques)

anchos = sorted({(hora(b["bucket"]) - hora(a["bucket"])).total_seconds()
                 for a, b in zip(filas, filas[1:])})
ancho = timedelta(seconds=anchos[0]) if anchos else timedelta(minutes=15)

con_reinicio, sin_reinicio, mudos, control_malo = 0, 0, [], []
for f in filas:
    inicio = hora(f["bucket"])
    if inicio < corte:
        continue
    cortos = f.get("short_minutes") or 0
    desconocidos = f.get("unknown_minutes") or 0
    if tiene_arranque(inicio, ancho):
        con_reinicio += 1
        # --- 3 · el que contiene un reinicio tiene que declararlo ---
        if cortos < 1:
            mudos.append(f"{str(f["bucket"])[11:16]} contiene un arranque y sirve short_minutes={cortos}")
    else:
        sin_reinicio += 1
        # --- CONTROL POSITIVO ---
        if cortos or desconocidos:
            control_malo.append(f"{str(f["bucket"])[11:16]} sin arranque y sirve short={cortos} unknown={desconocidos}")

if mudos:
    print(f"{len(mudos)} buckets con reinicio no lo declaran: " + " · ".join(mudos[:3])); sys.exit(1)
if control_malo:
    print(f"CONTROL POSITIVO ROTO: {len(control_malo)} buckets sin reinicio salen marcados: " + " · ".join(control_malo[:3])); sys.exit(1)
if con_reinicio == 0:
    print(f"NO MEDIDO: ningun bucket posterior al corte {corte:%H:%MZ} contiene un arranque; falta el brazo que prueba que se declara"); sys.exit(2)
if sin_reinicio == 0:
    print(f"NO MEDIDO: ningun bucket posterior al corte {corte:%H:%MZ} esta libre de arranques; falta el control positivo"); sys.exit(2)

legado = sum(1 for f in filas if (f.get("unknown_minutes") or 0) > 0)
print(f"la ruta distingue las tres cosas EJECUTANDOLA: {con_reinicio} buckets con reinicio lo declaran con short_minutes, {sin_reinicio} sin reinicio salen limpios -control positivo- y {legado} de legado dicen unknown_minutes en vez de pasar por completos. Corte {corte:%H:%MZ}, {len(filas)} buckets de {horas} h. La marca dice QUE falta, no CUANTO: no la uses como factor de escala")
' "$JOURNAL" "$CUERPO" "$RUTA" "$HORAS"
exit $?
