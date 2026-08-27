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
# --- LAS TRES COSTURAS QUE EL OPERADOR CAZO EN LA PRIMERA VERSION (K52c) --------------
# 1 · EL ELEGIBLE SALIA DE LO SERVIDO. El bucle recorria "for f in filas", o sea lo que la
#     ruta DEVUELVE, asi que un bucket que no existe no se juzgaba: borrando del cuerpo el
#     de 23:45 -que declaraba short_minutes=1- salia VERDE y el contador bajaba de 2 a 1
#     sin decir nada. UN VERDE CUYA EVIDENCIA ES UN CONTEO SOBRE LO PRESENTE NUNCA PUEDE
#     NOTAR QUE EL CONTEO ENCOGIO: es la puerta del NULO un nivel mas arriba, y van dos
#     instancias en dos rondas. AHORA el elegible sale del JOURNAL: por cada arranque
#     posterior al corte y asentado tiene que EXISTIR un bucket que lo cubra y lo declare.
# 2 · LAS DOS VENTANAS NO CASABAN, Y ESO TENIA FECHA. El journal se pedia con 6 h fijas y
#     la ruta sirve 96 buckets de 15 min, o sea 24 h -medido por mi via: de
#     2026-08-26T00:30:00Z a 2026-08-27T00:15:00Z-. Mientras la era marcada cupiera en 6 h
#     no se notaba. El operador lo indujo quitando del journal el arranque de las
#     23:13:41Z, que es literalmente lo que hace el reloj, y salio "CONTROL POSITIVO ROTO"
#     sin que nada estuviera roto; su prediccion era que enrojeceria solo a partir de
#     2026-08-27T05:13:41Z. AHORA el journal se pide con EL MISMO ARCO que la ruta -la
#     ruta va primero y ella fija el arco- y ademas un bucket que caiga fuera del alcance
#     REAL del journal no se juzga: se declara, nunca ROJO. Un rojo falso repetido es lo
#     que ensena a ignorar el que si lo es: la leccion del RuntimeError de ingest.
# 3 · EL BUCKET A CABALLO DEL CORTE. El de 23:00Z lleva 13 minutos de legado y 2 marcados
#     y sirve unknown=13 y short=1 A LA VEZ. No es legado ni es era marcada, asi que no se
#     le puede aplicar ninguna de las dos varas: se declara no medido y se dice.
#
# ESTE CHECK EJECUTA LA RUTA. No lee app/api.py ni static/app.js: lo que se comprueba es
# lo que un llamante recibe, porque es lo unico que el llamante puede ver.
#
# LO QUE EXIGE
#   1 · cada fila servida trae unknown_minutes, que dice cuantos minutos del bucket no
#       tienen marca. Sin ese campo, "no lo se" no es expresable.
#   2 · ninguna fila puede estar en el estado que fallaba abierto: covered_seconds_min
#       nulo Y unknown_minutes en 0. Eso es exactamente "no lo se disfrazado de completo".
#   3 · por cada ARRANQUE del journal posterior al corte, asentado y dentro del alcance
#       del journal, EXISTE un bucket que lo cubre y lo declara con short_minutes >= 1.
#   CONTROL POSITIVO, obligatorio: un bucket juzgable y SIN arranque no puede salir ni
#       marcado ni desconocido. Un guardia que marca todo esta tan roto como el que no
#       marca nada.
#   NOMED si falta cualquiera de los dos brazos, y se dice CUANTOS quedaron sin juzgar y
#       por que motivo: legado, a caballo del corte, sin asentar o fuera del journal.
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

JOURNAL=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero del journal"; exit 2; }
CUERPO=$(mktemp) || { echo "NO MEDIDO: no se pudo crear el fichero de respuesta"; exit 2; }
trap 'rm -f "$JOURNAL" "$CUERPO"' EXIT

# LA RUTA VA PRIMERO y ella fija el arco; el journal se pide para ESE arco. Al reves -que
# era como estaba, con 6 h fijas contra 24 h servidas- las dos ventanas se separan solas
# con el reloj, y el operador puso fecha exacta a cuando eso habria enrojecido.
TODO=1 "$B/bin/api" "$RUTA?symbol=$SIMBOLO&interval=15min&limit=96" > "$CUERPO" 2>/dev/null
[ -s "$CUERPO" ] || { echo "NO MEDIDO: $RUTA no devolvio nada (canal)"; exit 2; }

horas=$(python3 -c '
import json, sys, math
from datetime import datetime, UTC
try:
    d = json.load(open(sys.argv[1]))
    b = [datetime.fromisoformat(str(f["bucket"]).replace("Z", "+00:00")) for f in d["rows"]]
except Exception:
    print(""); sys.exit(0)
print(max(1, math.ceil((datetime.now(UTC) - min(b)).total_seconds() / 3600) + 1))
' "$CUERPO")
[ -n "$horas" ] || { echo "NO MEDIDO: $RUTA no sirve buckets con los que fijar el arco"; exit 2; }

# Dos consultas en una: la PRIMERA linea del journal es su suelo real -si roto, el suelo
# sube y hay buckets que no se pueden juzgar- y despues los arranques.
"$B/bin/prod" "journalctl -u $UNIDAD --since '$horas hours ago' --no-pager -o short-iso --utc -n 3000 2>/dev/null | head -1; journalctl -u $UNIDAD --since '$horas hours ago' --no-pager -o short-iso --utc -n 3000 2>/dev/null | grep -E 'Started $UNIDAD'" 2>/dev/null > "$JOURNAL"
[ -s "$JOURNAL" ] || { echo "NO MEDIDO: el journal de 140 no devolvio nada para $UNIDAD en $horas h"; exit 2; }

python3 -c '
import json, sys
from datetime import datetime, timedelta, UTC

camino_journal, camino_cuerpo, ruta, horas = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
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

lineas = [l for l in open(camino_journal).read().splitlines() if l.strip()]
if not lineas:
    print("NO MEDIDO: el journal vino vacio"); sys.exit(2)
try:
    suelo = hora(lineas[0].split()[0])
except (IndexError, ValueError):
    print(f"NO MEDIDO: no se pudo leer el suelo del journal de {lineas[0][:60]!r}"); sys.exit(2)
arranques = []
for l in lineas[1:]:
    try:
        arranques.append(hora(l.split()[0]))
    except (IndexError, ValueError):
        continue

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

ahora = datetime.now(UTC)
ASIENTO = timedelta(minutes=6)   # el minuto vive en RAM hasta M+185 s; ver K52
por_inicio = {hora(f["bucket"]): f for f in filas}

def juzgable(inicio):
    """Por que un bucket NO se puede juzgar. None = se juzga."""
    if inicio < corte:
        return "legado"
    if inicio <= corte < inicio + ancho:
        return "a caballo del corte"      # costura 3: ni legado ni era marcada
    if inicio + ancho > ahora - ASIENTO:
        return "sin asentar"              # el minuto aun vive en RAM
    if inicio < suelo:
        return "fuera del journal"        # costura 2: sin instrumento no hay veredicto
    return None

# --- 3 · EL ELEGIBLE SALE DEL JOURNAL, no de lo servido (costura 1) -------------------
sin_declarar, cubiertos = [], 0
for a in arranques:
    if a < corte or a + ancho > ahora - ASIENTO or a < suelo:
        continue
    inicio = next((b for b in sorted(por_inicio) if b <= a < b + ancho), None)
    if inicio is None:
        sin_declarar.append(f"el arranque de {a:%H:%M:%SZ} no tiene NINGUN bucket que lo cubra en lo servido")
        continue
    if juzgable(inicio) is not None:
        continue
    cortos = por_inicio[inicio].get("short_minutes") or 0
    if cortos < 1:
        sin_declarar.append(f"el arranque de {a:%H:%M:%SZ} cae en el bucket {inicio:%H:%M}, que sirve short_minutes={cortos}")
    else:
        cubiertos += 1

# --- CONTROL POSITIVO: el bucket tranquilo no se marca --------------------------------
exentos, tranquilos, control_malo, marcados_sin_arranque = {}, 0, [], []
for inicio, f in sorted(por_inicio.items()):
    motivo = juzgable(inicio)
    if motivo:
        exentos[motivo] = exentos.get(motivo, 0) + 1
        continue
    if any(inicio <= a < inicio + ancho for a in arranques):
        continue
    cortos, desconocidos = f.get("short_minutes") or 0, f.get("unknown_minutes") or 0
    if cortos:
        # DOS INSTRUMENTOS QUE DISCREPAN NO SON UN FALLO DEL SUJETO. La fila dice que
        # hubo un arranque y el journal no lo lista: puede ser un productor que sobre-
        # marca, o puede ser el journal incompleto -rotacion, o un arranque que el grep
        # no reconoce-. No se puede decidir cual, asi que no se juzga y se DECLARA. Sin
        # esto, recortar el journal producia un "CONTROL POSITIVO ROTO" sin que nada
        # estuviera roto, que es la costura 2 del operador vista desde dentro.
        marcados_sin_arranque.append(f"{inicio:%H:%M}")
        continue
    tranquilos += 1
    if desconocidos:
        # Esto SI es del sujeto: unknown_minutes son filas sin marca, y el journal no
        # tiene nada que ver con que el productor deje de escribirla.
        control_malo.append(f"{inicio:%H:%M} sin arranque y sirve unknown={desconocidos}")

if sin_declarar:
    print(f"{len(sin_declarar)} arranques del journal no los declara ningun bucket servido: " + " · ".join(sin_declarar[:3])); sys.exit(1)
if control_malo:
    print(f"CONTROL POSITIVO ROTO: {len(control_malo)} buckets sin arranque salen desconocidos: " + " · ".join(control_malo[:3])); sys.exit(1)

if cubiertos == 0:
    print(f"NO MEDIDO: ningun arranque del journal es juzgable -posterior al corte {corte:%H:%MZ}, asentado y dentro del journal-; falta el brazo que prueba que se declara. Sin juzgar: {exentos}"); sys.exit(2)
if tranquilos == 0:
    pista = f" y {len(marcados_sin_arranque)} se declaran cortos sin que el journal lo explique -{marcados_sin_arranque[:4]}-, que es lo que pareceria un productor que marca de mas" if marcados_sin_arranque else ""
    print(f"NO MEDIDO: ningun bucket juzgable esta libre de arranques, asi que el control positivo no se puede correr{pista}. Sin juzgar: {exentos}"); sys.exit(2)

legado = sum(1 for f in filas if (f.get("unknown_minutes") or 0) > 0)
if marcados_sin_arranque:
    exentos["cortos que el journal no explica"] = len(marcados_sin_arranque)
detalle = ", ".join(f"{n} {m}" for m, n in sorted(exentos.items())) or "ninguno"
print(f"la ruta distingue las tres cosas EJECUTANDOLA, y el ELEGIBLE SALE DEL JOURNAL: los {cubiertos} arranques juzgables tienen un bucket que los declara, {tranquilos} buckets sin arranque salen limpios -control positivo- y {legado} de legado dicen unknown_minutes en vez de pasar por completos. Corte {corte:%m-%d %H:%MZ}, suelo del journal {suelo:%m-%d %H:%MZ}, arco de {horas} h sobre {len(filas)} buckets. NO JUZGADOS y declarados: {detalle}. La marca dice QUE falta, no CUANTO")
' "$JOURNAL" "$CUERPO" "$RUTA" "$horas"
exit $?
