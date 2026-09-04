#!/bin/bash
# K05-control · LOS BRAZOS DE LA REGLA DE SERIE, INDUCIDOS FUERA DE LINEA.
#
# Un guardia que caza todo esta tan roto como el que no caza nada, y el brazo que casi nadie
# prueba es el que convierte un check en fail-closed: SERIE CORTA O AUSENTE -> NO MEDIDO.
# Aqui se prueban los cuatro: positivo, negativo, borde (23 contra 24) y no-medido.
#
# NO LLEVA .sh A PROPOSITO. bin/verify globea checks/*.sh y su marcador es del operador; el
# sujeto de este fichero es EL ARBOL, no produccion. Mismo patron que K86-control.bash.
# Corre sin red, sin ssh y sin base de datos: la tabla entra por K05_TABLA, el minuto vivo
# por K05_CAPTURA y la ventana por K05_SERIE.
#
# LOS FIXTURES SE GENERAN, NO SE GUARDAN, y por la misma razon medida en K86: el sujeto de
# K05 es una ventana de los ULTIMOS 30 minutos, con guardia de frescura. Un fixture con
# fechas absolutas caduca en cinco minutos y a partir de ahi el control PASA declarando
# NO MEDIDO por rancio, o sea que el brazo que creias probando esta apagado. Las marcas de
# tiempo se calculan desde el reloj de la corrida.
#
# EL CONTROL DEL CONTROL (C2b, heredado de K86): el brazo positivo y el negativo llevan
# EXACTAMENTE el mismo numero de muestras no-ok -24 de 120- repartidas distinto. Si no
# fueran iguales, lo que separa ROJO de VERDE podria ser el VOLUMEN y no la CONCENTRACION,
# y entonces el control negativo no prueba lo que dice probar.
set -uo pipefail
B=/srv/coinanalyze/harness
CHK="$(cd "$(dirname "$0")" && pwd)/K05-latidos.sh"
[ -r "$CHK" ] || { echo "no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K05_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
fallos=0
N=24
M=30

# --- GENERADOR DE FIXTURES ---------------------------------------------------------
# Una muestra de la serie es exactamente lo que escribe bin/capta-healthz:
#   {"t":"<iso>","h":<healthz entero>}
# El detail de scalp va LITERAL y se comprueba mas abajo: si el mensaje del check deja de
# citarlo, el operador pierde lo unico que dice QUE paso, y eso es la mitad que en K43 se
# cayo sin que nadie lo notara.
DETALLE="scalp stale: last_bar lag 245s dropped_buckets=3 sesion_con_minuto_cerrado=1"
python3 - "$DIR" "$DETALLE" <<'PY'
import json, sys, time

DIR, DETALLE = sys.argv[1], sys.argv[2]
AHORA = int(time.time())
GOB = ["api", "daily", "ingest", "ingest:liquidations_history", "ingest:metrics_5m",
       "ingest:ohlcv_1m", "scalp", "scalp:0/1", "ws", "ws-binance:0/1", "ws-bybit:0/1", "ws:0/1"]


def muestra(edad, malo=False, global_malo=None, ausente=False):
    """edad = segundos hacia atras desde ahora. malo = scalp publica degraded."""
    t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(AHORA - edad))
    servicios = []
    for n in GOB:
        if n in ("scalp", "scalp:0/1") and ausente:
            continue
        degradado = malo and n in ("scalp", "scalp:0/1")
        servicios.append({"service": n, "status": "degraded" if degradado else "ok",
                          "detail": DETALLE if degradado else None,
                          "lag_seconds": 245.0 if degradado else 1.5})
    if global_malo is None:
        global_malo = malo
    h = {"status": "degraded" if global_malo else "ok",
         "missing_services": ["scalp"] if ausente else [],
         "governed_services": GOB,
         "services": servicios,
         "symbols": [{"symbol": "BTCUSDT_PERP.A", "lag_seconds": 12.0}]}
    # Se arma EXACTAMENTE como lo escribe bin/capta-healthz:
    #   printf {"t":"%s","h":%s}   ·   sin espacio detras de los dos puntos.
    # Con json.dumps({...}) saldria {"t": "..."} con espacio, o sea un fixture que no es del
    # formato que el check va a encontrar en 143, y el control probaria otra cosa.
    return chr(123) + chr(34) + "t" + chr(34) + ":" + json.dumps(t) + "," \
        + chr(34) + "h" + chr(34) + ":" + json.dumps(h) + chr(125)


def escribe(nombre, lineas):
    with open(DIR + "/" + nombre, "w") as f:
        f.write("\n".join(lineas) + "\n")


# POSITIVA · 120 muestras, 24 no-ok, TODAS dentro de las ultimas 30. Cuenta exacta 24 = N.
pos = []
for i in range(120):
    edad = (119 - i) * 60
    pos.append(muestra(edad, malo=(90 <= i < 114)))
escribe("serie-positiva.jsonl", pos)

# NEGATIVA · 120 muestras, LAS MISMAS 24 no-ok, repartidas 1 de cada 5: en ninguna ventana
# de 30 pasan de 6. Mismo volumen, distinta concentracion. Este es el brazo que casi nadie
# prueba y el control del control esta en que los dos ficheros tienen 24.
neg = []
for i in range(120):
    neg.append(muestra((119 - i) * 60, malo=(i % 5 == 0)))
escribe("serie-negativa.jsonl", neg)

# RUIDO REAL · el PEOR ruido de fondo medido sobre la serie de verdad: 17 no-ok en una
# ventana de 30 (x1-tmp/k05-rejuego.py, 3003 ventanas, maximo 17, ventana que acaba en
# 2026-09-02T22:06:01Z). Reproducido con la forma de rachas que se midio: cortas y sueltas.
# Tiene que dar VERDE y tiene que DECIR 17, no solo el veredicto.
# El patron se DERIVA (reparto de Bresenham de 17 en 30) en vez de escribirse a mano: una
# lista literal con 19 unos y un comentario que dice 17 es exactamente la clase de mentira
# en voz baja que este control existe para no tener. El assert la caza igual.
patron = [1 if (i * 17) // 30 != ((i - 1) * 17) // 30 else 0 for i in range(30)]
assert sum(patron) == 17, sum(patron)
escribe("serie-ruido.jsonl",
        [muestra((29 - i) * 60, malo=bool(patron[i])) for i in range(30)])

# BORDE · 23 de 30 -> VERDE   y   24 de 30 -> ROJO. Donde un umbral se rompe.
escribe("serie-borde23.jsonl", [muestra((29 - i) * 60, malo=(i < 23)) for i in range(30)])
escribe("serie-borde24.jsonl", [muestra((29 - i) * 60, malo=(i < 24)) for i in range(30)])

# LIMPIA · 30 muestras todo ok. Sirve de fondo para probar el criterio 1.
escribe("serie-limpia.jsonl", [muestra((29 - i) * 60) for i in range(30)])

# CORTA · 29 muestras. Una menos que M.
escribe("serie-corta.jsonl", [muestra((28 - i) * 60) for i in range(29)])

# RANCIA · 30 muestras contiguas, pero la ultima es de hace una hora. El cron murio.
escribe("serie-rancia.jsonl", [muestra(3600 + (29 - i) * 60) for i in range(30)])

# HUECO · 30 muestras frescas con un salto de 10 minutos en medio: la ventana NO cubre 30
# minutos contiguos aunque tenga 30 lineas.
edades = [(29 - i) * 60 + (600 if i < 15 else 0) for i in range(30)]
escribe("serie-hueco.jsonl", [muestra(e) for e in edades])

# 502 · UNA MUESTRA NO ES UNA LINEA. El 2026-09-04T17:17:01Z nginx devolvio una pagina HTML
# de 502 durante el despliegue y capta-healthz la escribio CRUDA: ese minuto ocupa 8 lineas
# del fichero. Contando lineas, ese minuto se come 8 de los 30 huecos de la ventana y empuja
# fuera 7 muestras buenas.
# EL FIXTURE ESTA HECHO PARA QUE LAS DOS FORMAS DE CONTAR DEN NUMEROS DISTINTOS, que es lo
# unico que convierte esto en un control y no en un adorno: las 7 muestras no-ok son las mas
# VIEJAS de la ventana. Contando MUESTRAS la ventana las incluye -> peor 7. Contando LINEAS,
# las 8 lineas del 502 las expulsan -> peor 0. La asercion pide 7.
b502 = [muestra((30 - i) * 60, malo=(1 <= i <= 7)) for i in range(30)]
t502 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(AHORA))
b502.append('{"t":"' + t502 + '","h":<html>\n<head><title>502 Bad Gateway</title></head>\n'
            '<body>\n<center><h1>502 Bad Gateway</h1></center>\n<hr><center>nginx</center>\n'
            '</body>\n</html>\n}')
escribe("serie-502.jsonl", b502)

# SIN RELOJ · 30 muestras de las que una empieza por la marca pero no trae hora entre
# comillas. Sin hora no hay forma de saber si la ventana cubre 30 minutos contiguos, y sin
# eso el guardia de frescura es decorativo. Es la ultima rama fail-closed de la familia.
reloj = [muestra((29 - i) * 60) for i in range(30)]
reloj[10] = chr(123) + chr(34) + "t" + chr(34) + ":null," + chr(34) + "h" + chr(34) + ":null" + chr(125)
escribe("serie-sinreloj.jsonl", reloj)

# INCOGNITAS · 8 ilegibles + 20 no-ok + 2 ok. 20 < 24, o sea que por si solo seria VERDE;
# pero 20 + 8 = 28 >= 24, o sea que si las ilegibles fueran fallos el veredicto cambiaria.
# No hay veredicto: NO MEDIDO. Es la diferencia entre "no pasa nada" y "no lo se".
inc = []
for i in range(30):
    if i < 8:
        inc.append('{"t":"' + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(AHORA - (29 - i) * 60))
                   + '","h":<html>502</html>}')
    else:
        inc.append(muestra((29 - i) * 60, malo=(i < 28)))
escribe("serie-incognitas.jsonl", inc)

# SOLO GLOBAL · las tres formas que el operador indujo el 2026-09-03: ninguna FILA publica
# no-ok -filas_no_ok VACIO- y sin embargo el status global dice degraded con scalp en
# missing_services. El criterio 2 no puede verlo; el 3 si. Prueba que siguen siendo DOS.
escribe("serie-global.jsonl",
        [muestra((29 - i) * 60, malo=False, global_malo=(i < 24), ausente=(i < 24))
         for i in range(30)])

# --- EL MINUTO VIVO Y LA TABLA, para el criterio 1 ---------------------------------
vivo = json.loads(muestra(0))["h"]
open(DIR + "/captura-ok.json", "w").write(json.dumps({"t": "ahora", "h": vivo}))
sin = dict(vivo)
sin.pop("governed_services")
open(DIR + "/captura-sincampo.json", "w").write(json.dumps({"t": "ahora", "h": sin}))
open(DIR + "/captura-rota.json", "w").write("no soy json")
# CORTADA · lo que bin/api entrega cuando el cuerpo pasa de MAX_BYTES: el JSON a medias mas
# la marca que pone bin/_corta. El cuerpo real mide hoy 5261 B de un techo de 8000, o sea que
# esto no es hipotetico, es lo que pasara el dia que healthz crezca 2739 B.
open(DIR + "/captura-cortada.json", "w").write(
    json.dumps({"t": "ahora", "h": vivo})[:4000]
    + "\n[CORTADO: 8000 bytes de 9312. Acota la consulta; no pongas TODO=1 por inercia]\n")
open(DIR + "/tabla-ok.txt", "w").write("\n".join(sorted(GOB)) + "\n")
open(DIR + "/tabla-falta.txt", "w").write("\n".join(sorted(GOB)) + "\nws-kraken:0/1\n")
PY
[ -r "$DIR/serie-positiva.jsonl" ] || { echo "el generador de fixtures no escribio nada"; exit 2; }

# --- ARNES DE ASERCION -------------------------------------------------------------
corre() {  # $1 = serie   $2 = tabla   $3 = captura   -> rc en la primera linea, salida detras
  local out rc
  out=$(env K05_SERIE="$DIR/$1" K05_TABLA="$DIR/$2" K05_CAPTURA="$DIR/$3" \
            K05_N="$N" K05_M="$M" bash "$CHK" 2>&1); rc=$?
  printf '%s\n%s\n' "$rc" "$out"
}

juzga() {  # $1 = etiqueta   $2 = rc esperado   $3 = rc real   $4 = patron   $5 = salida
  local est
  if [ "$3" = "$2" ] && printf '%s\n' "$5" | grep -qF -- "$4"; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
  printf '%-44s rc=%s (esperado %s)  %-5s  %s\n' "$1" "$3" "$2" "$est" "$(printf '%s' "$5" | head -1 | cut -c1-72)"
  [ "$est" = FALLA ] && printf '   esperaba encontrar: %s\n' "$4"
  return 0
}

echo "K05 · controles fuera de linea   ·   $(date -u +%FT%TZ)   ·   N=$N M=$M   ·   $DIR"
echo "check: $CHK"
echo

# --- C0 · EL CONSTRUCTOR, ESTATICO -------------------------------------------------
# El evaluador entero viaja dentro de python3 -c '...'. Una comilla simple ahi dentro parte
# la orden en dos y el check pasa a hacer otra cosa. Se comprueba en estatico, que es donde
# se puede, y ademas que el fichero es bash valido.
c0=PASA
prog=$(awk '/python3 -c .$/{f=1; next} f && /^. "\$SERIE"/{exit} f{print}' "$CHK")
[ -n "$prog" ] || { c0=FALLA; echo "   C0: no pude extraer el programa de python del check"; }
printf '%s\n' "$prog" | grep -q "'" && c0=FALLA
bash -n "$CHK" 2>/dev/null || c0=FALLA
[ "$c0" = FALLA ] && fallos=$((fallos + 1))
printf '%-44s %-18s %-5s  %s\n' "C0 constructor: python sin comilla simple" \
  "$(printf '%s\n' "$prog" | grep -c '') lin" "$c0" "bash -n y el literal de python3 -c"

# --- C1 · POSITIVO · 24 de las ultimas 30 ------------------------------------------
sal=$(corre serie-positiva.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); pos_out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C1 positivo: scalp no-ok en 24 de 30" 1 "$rc" "criterio 2, 24 de 30: scalp=24/30" "$pos_out"

# C1b · EL DETAIL LITERAL SIGUE SALIENDO. Es lo unico del mensaje que dice QUE paso, y es
# exactamente la clase de cosa que se cae al reescribir un criterio sin que nadie lo note.
juzga "C1b positivo: cita el detail LITERAL" 1 "$rc" "dropped_buckets=3" "$pos_out"

# C1c · y los dos criterios se siguen diciendo POR SEPARADO, no fundidos en uno.
juzga "C1c positivo: criterios 2 y 3, los dos" 1 "$rc" "criterio 3, 24 de 30: status no-ok en 24/30" "$pos_out"

# --- C2 · NEGATIVO · mismo volumen, repartido --------------------------------------
sal=$(corre serie-negativa.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); neg_out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C2 negativo: 24 repartidas en 120 -> VERDE" 0 "$rc" "peor 6/24" "$neg_out"

# C2b · EL CONTROL DEL CONTROL: los dos brazos con el MISMO numero de muestras no-ok.
n_pos=$(grep -c 'degraded' "$DIR/serie-positiva.jsonl")
n_neg=$(grep -c 'degraded' "$DIR/serie-negativa.jsonl")
if [ "$n_pos" = "$n_neg" ] && [ "$n_pos" = "24" ]; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
printf '%-44s %-18s %-5s  %s\n' "C2b volumen pareado" "pos=$n_pos neg=$n_neg" "$est" \
  "lo que separa los brazos es la concentracion, no el volumen"

# --- C3 · EL RUIDO DE FONDO REAL, EN SU PEOR VENTANA MEDIDA ------------------------
# 17 de 30 es el maximo que el ruido alcanzo en 3003 ventanas reales. Tiene que dar VERDE
# Y tiene que IMPRIMIR el 17: un VERDE que no dice cuanto se acerco no deja auditar el margen.
sal=$(corre serie-ruido.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C3 ruido real 17/30 -> VERDE y lo dice" 0 "$rc" "peor 17/24" "$out"

# --- C4 · EL BORDE, QUE ES DONDE UN UMBRAL SE ROMPE --------------------------------
sal=$(corre serie-borde23.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C4a borde: 23 de 30 -> VERDE" 0 "$rc" "peor 23/24" "$out"
sal=$(corre serie-borde24.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C4b borde: 24 de 30 -> ROJO" 1 "$rc" "scalp=24/30" "$out"

# --- C5 · FAIL-CLOSED · SERIE QUE NO SE PUEDE JUZGAR -> NO MEDIDO, NUNCA VERDE -----
sal=$(corre serie-que-no-existe.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C5a serie AUSENTE -> NO MEDIDO" 2 "$rc" "serie ausente" "$out"
sal=$(corre serie-corta.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C5b serie CORTA (29) -> NO MEDIDO" 2 "$rc" "serie corta 29 muestras, hacen falta 30" "$out"
sal=$(corre serie-rancia.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C5c serie RANCIA (cron muerto) -> NO MEDIDO" 2 "$rc" "serie rancia la ultima muestra tiene" "$out"
sal=$(corre serie-hueco.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C5d HUECO de 10 min dentro -> NO MEDIDO" 2 "$rc" "serie hueco de 660 s" "$out"

sal=$(corre serie-sinreloj.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C5e muestra SIN hora legible -> NO MEDIDO" 2 "$rc" "serie sinreloj" "$out"

# --- C6 · UNA MUESTRA NO ES UNA LINEA ----------------------------------------------
# El 502 de 8 lineas tiene que contar como UNA muestra ilegible. Si el check contara lineas,
# la ventana se comeria 7 muestras buenas y el arco lo delataria.
sal=$(corre serie-502.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C6 el 502 de 8 lineas = UNA muestra" 0 "$rc" "peor 7/24" "$out"

# --- C7 · LAS ILEGIBLES SON INCOGNITAS, NO CEROS -----------------------------------
sal=$(corre serie-incognitas.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C7 20 no-ok + 8 ilegibles -> NO MEDIDO" 2 "$rc" "8 muestras ilegibles en la ventana" "$out"

# --- C8 · EL CRITERIO 3 SIGUE SIENDO OTRO CRITERIO ---------------------------------
# Ninguna FILA publica no-ok y aun asi el status global dice degraded 24 de 30, con scalp en
# missing_services. Si al pasar a serie se hubiera fundido el 3 dentro del 2, esto saldria
# VERDE y las tres formas del 2026-09-03 volverian a ser invisibles.
sal=$(corre serie-global.jsonl tabla-ok.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C8a solo global: criterio 3 dispara solo" 1 "$rc" "criterio 3, 24 de 30" "$out"
juzga "C8b solo global: conserva el PORQUE" 1 "$rc" "missing_services: scalp" "$out"

# --- C9 · EL CRITERIO 1 NO SE HA TOCADO --------------------------------------------
# Con la serie LIMPIA -o sea, criterios 2 y 3 en verde- la cobertura tiene que seguir
# gateando ella sola. Es la prueba de que no se ha caido media mitad al reescribir.
sal=$(corre serie-limpia.jsonl tabla-falta.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9a criterio 1 sigue gateando solo" 1 "$rc" "sin vigilar: ws-kraken:0/1" "$out"
sal=$(corre serie-limpia.jsonl tabla-ok.txt captura-sincampo.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9b sin governed_services sigue ROJO" 1 "$rc" "healthz no declara que vigila" "$out"
sal=$(corre serie-limpia.jsonl tabla-ok.txt captura-rota.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9c healthz ilegible -> NO MEDIDO, no VERDE" 2 "$rc" "criterio 1: /api/healthz no respondio" "$out"

# C9d · EL GUARDIA DEL CORTE. bin/api pasa por bin/_corta y trunca a 8000 B; el cuerpo de
# healthz mide hoy 5261 B como mucho. Si un dia cruza, el check tiene que decir QUE fue el
# transporte, no "no respondio": esa frase manda a mirar produccion cuando el problema es del
# arnes, y es exactamente la trampa 1 que casi hunde a K86.
sal=$(corre serie-limpia.jsonl tabla-ok.txt captura-cortada.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C9d respuesta CORTADA -> NO MEDIDO y lo dice" 2 "$rc" "el transporte corto la respuesta" "$out"

# --- C10 · LA PRECEDENCIA · UN ROJO MEDIDO MANDA SOBRE UN NO MEDIDO ----------------
# Cobertura ROJA y serie ausente a la vez. El fallo esta MEDIDO, asi que el veredicto es
# ROJO, y lo que no se pudo mirar se dice al lado en vez de taparse.
sal=$(corre serie-que-no-existe.jsonl tabla-falta.txt captura-ok.json)
rc=$(printf '%s\n' "$sal" | head -1); out=$(printf '%s\n' "$sal" | tail -n +2)
juzga "C10 ROJO medido + serie ausente -> ROJO" 1 "$rc" "SIN MEDIR: criterios 2 y 3: serie ausente" "$out"

# --- C11 · LA SERIE DE VERDAD ------------------------------------------------------
# Los diez anteriores son fixtures. Este corre contra la serie REAL de 143, que es el sujeto,
# y comprueba que hoy da VERDE por los criterios 2 y 3 -o sea, que el ruido de fondo ya no
# rojea-. Si la serie no esta o esta rancia, se DICE y no se cuenta como PASA silencioso.
real=$B/estado/healthz-serie.jsonl
if [ -r "$real" ]; then
  out=$(env K05_SERIE="$real" K05_TABLA="$DIR/tabla-ok.txt" K05_CAPTURA="$DIR/captura-ok.json" \
            K05_N="$N" K05_M="$M" bash "$CHK" 2>&1); rc=$?
  # LA MISMA AUDITORIA QUE A UN HALLAZGO: lo que se juzga aqui NO es el veredicto -ese es del
  # marcador, y si produccion esta de verdad caida este control no debe fallar por ello- sino
  # que la serie real SE PUDO EVALUAR. Un "PASA" porque el check ni llego a mirar es
  # exactamente el control fantasma que este arnes persigue, asi que se exige huella positiva.
  huella=$(printf '%s\n' "$out" | grep -oE 'peor [0-9]+/[0-9]+|criterio [23], [0-9]+ de [0-9]+' | head -1)
  if printf '%s\n' "$out" | grep -qE 'serie (ausente|corta|rancia|hueco|sinreloj)|no dijo nada' \
     || [ -z "$huella" ]; then est=FALLA; fallos=$((fallos + 1)); else est=PASA; fi
  printf '%-44s %-18s %-5s  %s\n' "C11 la serie REAL se evalua de verdad" "rc=$rc ${huella:-sin huella}" "$est" \
    "$(printf '%s' "$out" | head -1 | cut -c1-72)"
else
  printf '%-44s %-18s %-5s  %s\n' "C11 la serie REAL" "no esta" "AVISO" \
    "$real no existe: este control NO se ha ejercitado"
fi

# --- C13 · LOS VALORES POR DEFECTO, QUE ES LO QUE VA A CORRER DE VERDAD ------------
# Los doce controles de arriba pasan K05_N=24 y K05_M=30 a mano, o sea que prueban la REGLA
# pero no el UMBRAL que verify usara. Si alguien deja el defecto en 2, todos seguirian
# pasando y el marcador parpadearia igual que antes. Aqui se corre SIN entorno.
out=$(env K05_SERIE="$DIR/serie-borde23.jsonl" K05_TABLA="$DIR/tabla-ok.txt" \
          K05_CAPTURA="$DIR/captura-ok.json" bash "$CHK" 2>&1); rc=$?
juzga "C13a por defecto: 23 de 30 -> VERDE" 0 "$rc" "ventana 30: peor 23/24" "$out"
out=$(env K05_SERIE="$DIR/serie-borde24.jsonl" K05_TABLA="$DIR/tabla-ok.txt" \
          K05_CAPTURA="$DIR/captura-ok.json" bash "$CHK" 2>&1); rc=$?
juzga "C13b por defecto: 24 de 30 -> ROJO" 1 "$rc" "criterio 2, 24 de 30" "$out"

# --- C12 · LA PEOR VENTANA REAL, RE-JUGADA CON EL RELOJ ANCLADO --------------------
# Los once primeros son fixtures que YO fabrico, o sea que prueban el check contra mi propia
# idea de la serie. Este lo prueba contra la serie DE VERDAD y en su punto mas dificil: se
# busca la ventana de M muestras con MAS no-ok de todo el arco guardado, se extrae, y se le
# pasa al check con K05_AHORA anclado a su ultimo minuto.
# Y el recuento se hace DOS VECES con dos implementaciones distintas -la de aqui y la del
# check-: si no coinciden, una de las dos esta mal y no hay forma de saber cual sin esto.
# No caduca: la peor ventana se busca en cada corrida sobre lo que haya.
if [ -r "$real" ]; then
  info=$(python3 - "$real" "$M" "$DIR/serie-peor-real.jsonl" <<'PY'
import calendar, json, sys, time
RUTA, M, SALIDA = sys.argv[1], int(sys.argv[2]), sys.argv[3]
MARCA = '{"t":'
trozos = []
for ln in open(RUTA, encoding="utf-8", errors="replace"):
    ln = ln.strip()
    if not ln:
        continue
    if ln.startswith(MARCA):
        trozos.append(ln)
    elif trozos:
        trozos[-1] += ln
ms = []
for s in trozos:
    try:
        h = json.loads(s).get("h")
        if not isinstance(h, dict) or "status" not in h:
            raise ValueError
    except Exception:
        ms.append((s, None, None))
        continue
    gob = {x["service"] if isinstance(x, dict) else str(x) for x in (h.get("governed_services") or [])}
    malos = {str(x.get("service")) for x in (h.get("services") or [])
             if isinstance(x, dict) and str(x.get("service")) in gob and str(x.get("status") or "") != "ok"}
    ms.append((s, malos, str(h.get("status") or "") != "ok"))
if len(ms) < M:
    print("CORTA " + str(len(ms)))
    raise SystemExit(0)
mejor, donde = -1, 0
for i in range(M - 1, len(ms)):
    v = ms[i - M + 1:i + 1]
    cuenta = sum(1 for x in v if x[2])
    for s in {n for x in v if x[1] for n in x[1]}:
        cuenta = max(cuenta, sum(1 for x in v if x[1] and s in x[1]))
    if cuenta > mejor:
        mejor, donde = cuenta, i
ven = ms[donde - M + 1:donde + 1]
open(SALIDA, "w").write("\n".join(x[0] for x in ven) + "\n")
t = json.loads(ven[-1][0])["t"] if ven[-1][1] is not None else None
if t is None:
    t = ven[-1][0][6:ven[-1][0].find('"', 7)]
print(str(mejor) + " " + str(calendar.timegm(time.strptime(t, "%Y-%m-%dT%H:%M:%SZ"))) + " " + t)
PY
)
  peor_real=$(printf '%s' "$info" | awk '{print $1}')
  epoca=$(printf '%s' "$info" | awk '{print $2}')
  cuando=$(printf '%s' "$info" | awk '{print $3}')
  if [ "$peor_real" = "CORTA" ]; then
    printf '%-44s %-18s %-5s  %s\n' "C12 la peor ventana REAL" "serie corta" "AVISO" \
      "la serie no tiene $M muestras: este control NO se ha ejercitado"
  else
    esperado=0; [ "$peor_real" -ge "$N" ] && esperado=1
    out=$(env K05_SERIE="$DIR/serie-peor-real.jsonl" K05_TABLA="$DIR/tabla-ok.txt" \
              K05_CAPTURA="$DIR/captura-ok.json" K05_N="$N" K05_M="$M" K05_AHORA="$epoca" \
              bash "$CHK" 2>&1); rc=$?
    # El numero se busca donde el check lo publica en cada caso: en la linea de VERDE es
    # "peor X/N"; si dispara, sale como "X/M" dentro del mensaje del criterio que gateo.
    if [ "$esperado" = 0 ]; then patron="peor $peor_real/$N"; else patron="$peor_real/$M"; fi
    if [ "$rc" = "$esperado" ] && printf '%s\n' "$out" | grep -qF "$patron"; then
      est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
    printf '%-44s %-18s %-5s  %s\n' "C12 peor ventana REAL: $peor_real de $M no-ok" "rc=$rc esp=$esperado" "$est" \
      "acaba en $cuando · las dos cuentas coinciden en $peor_real"
    [ "$est" = FALLA ] && printf '   el check dijo: %s\n' "$(printf '%s' "$out" | head -1 | cut -c1-100)"
  fi
else
  printf '%-44s %-18s %-5s  %s\n' "C12 la peor ventana REAL" "no esta" "AVISO" \
    "$real no existe: este control NO se ha ejercitado"
fi

# --- C14 · EL ESCRITOR DE LA SERIE, EJERCITADO POR SU CAMINO -----------------------
# HUECO QUE ME ENCONTRO EL OPERADOR el 2026-09-04, y tiene razon: los controles de arriba
# prueban el CHECK, y el arreglo del 2026-09-04T18:49Z no vive ahi sino en bin/capta-healthz,
# o sea en el ESCRITOR. "Verificado en vivo" NO lo ejercita: un healthz normal no trae saltos
# de linea, asi que el minuto bueno de las 18:50:01Z habria salido identico con el arreglo
# puesto o quitado. El invariante que sostiene la ventana de 30 -UNA MUESTRA = UNA LINEA-
# solo se prueba conduciendo el escritor con respuestas fabricadas.
#
# SE EJERCITA EL FICHERO INSTALADO. La copia se deriva a mano con un solo sed sobre la linea
# S= -a donde escribe- y C14a COMPRUEBA que la diferencia es EXACTAMENTE esa: si fuese otro
# programa, los cinco brazos siguientes no dirian nada de lo que corre en el cron.
#
# MI PROPIO C14 NACIO FANTASMA Y LO CACE EN SU PRIMERA CORRIDA (2026-09-04T19:50Z): puse el
# curl de mentira en un fichero SIN permiso de ejecucion, capta-healthz cayo al curl de
# verdad y escribio un healthz REAL de 140. C14c y C14d PASARON con el -una respuesta real
# tambien es una linea y tambien es JSON valido-, o sea que dos brazos estaban aprobando sin
# tocar el fixture. Dos consecuencias, y las dos estan puestas: el curl falso ahora es una
# FUNCION EXPORTADA -no depende de permisos ni de PATH- y CADA brazo exige una marca que
# solo existe en su fixture, asi que una caida al curl real no puede volver a pasar en verde.
CAP="$B/bin/capta-healthz"
if [ -r "$CAP" ]; then
  CD="$DIR/cap"; mkdir -p "$CD"; SER="$CD/serie.jsonl"
  sed "s#^S=.*#S=$SER#" "$CAP" > "$CD/capta"
  eval "curl() { cat '$CD/payload' 2>/dev/null; return 0; }"
  export -f curl

  juzgal() {  # $1 = etiqueta   $2 = lineas esperadas   $3 = lineas reales   $4 = patron   $5 = salida
    local est
    if [ "$3" = "$2" ] && printf '%s\n' "$5" | grep -qF -- "$4"; then est=PASA; else est=FALLA; fallos=$((fallos + 1)); fi
    printf '%-44s lineas=%s (esperado %s)  %-5s  %s\n' "$1" "$3" "$2" "$est" "$(printf '%s' "$5" | head -1 | cut -c1-58)"
    [ "$est" = FALLA ] && printf '   esperaba encontrar: %s\n' "$4"
    return 0
  }
  captura() {  # deja en $CAPN las lineas escritas y en $CAPL la ultima linea
    : > "$SER"
    bash "$CD/capta" >/dev/null 2>&1
    CAPN=$(wc -l < "$SER"); CAPL=$(tail -n 1 "$SER" 2>/dev/null)
  }
  # Devuelve OK:<campo> SOLO si la linea entera parsea como JSON. Un solo patron prueba tres
  # cosas a la vez: que es JSON valido, que el cuerpo salio del FIXTURE y que el campo llego
  # entero. Es lo que impide que un brazo pase por haber medido otra cosa.
  campo() { printf '%s' "$1" | python3 -c 'import json,sys
d = json.loads(sys.stdin.read())
c = d["h"].get("control") or d["h"].get("detail") or ""
print("OK:" + str(c).replace(chr(10), "<LF>"))' 2>/dev/null; }

  # C14a · el control del control: la copia es el mismo programa menos la ruta de salida.
  difs=$(diff "$CAP" "$CD/capta" | grep -c '^[<>]')
  soloS=$(diff "$CAP" "$CD/capta" | grep '^[<>]' | grep -cv '^[<>] S=')
  juzgal "C14a la copia solo cambia la linea S=" 2 "$difs" "0" "$soloS"

  # C14b · EL CASO QUE LO ORIGINO: pagina HTML de 502, ocho lineas -> UNA muestra.
  printf '<html>\n<head><title>502 Bad Gateway</title></head>\n<body>\n<center><h1>502 C14B-MARCA</h1></center>\n<hr>\n<center>nginx</center>\n</body>\n</html>\n' > "$CD/payload"
  captura
  juzgal "C14b 502 de 8 lineas -> UNA linea" 1 "$CAPN" "502 C14B-MARCA" "$CAPL"

  # C14c · el caso normal no se toca: el cuerpo compacto llega entero y la linea es JSON.
  printf '{"status":"ok","control":"C14C-MARCA","services":[{"service":"scalp"}]}' > "$CD/payload"
  captura
  juzgal "C14c JSON compacto: intacto y valido" 1 "$CAPN" "OK:C14C-MARCA" "$(campo "$CAPL")"

  # C14d · pretty-printed: el saneado quita los saltos y lo que queda SIGUE siendo JSON.
  # Es el brazo que separa "quito bytes" de "rompo el cuerpo": la sangria sobrevive.
  printf '{\n  "status": "ok",\n  "control": "C14D-MARCA",\n  "services": [\n    {"service": "ws"}\n  ]\n}\n' > "$CD/payload"
  captura
  juzgal "C14d pretty -> 1 linea y sigue siendo JSON" 1 "$CAPN" "OK:C14D-MARCA" "$(campo "$CAPL")"

  # C14e · LA DISTINCION QUE IMPORTA: tr -d borra los BYTES CR y LF, no la secuencia de dos
  # caracteres \n dentro de una cadena. Si el saneado se hiciera con sed sobre el escape, el
  # detail de un servicio degradado se corromperia y el check citaria basura. Se juzga sobre
  # el valor PARSEADO: si el escape se hubiera borrado saldria C14E-MARCAsegunda sin <LF>.
  printf '{"status":"degraded","detail":"C14E-MARCA\\nsegunda"}' > "$CD/payload"
  captura
  juzgal "C14e el salto ESCAPADO se conserva" 1 "$CAPN" "OK:C14E-MARCA<LF>segunda" "$(campo "$CAPL")"

  # C14f · sin respuesta: el respaldo del escritor tambien tiene que ser UNA linea y JSON,
  # porque el check lo va a leer igual que a una muestra buena.
  : > "$CD/payload"
  captura
  juzgal "C14f sin respuesta -> 1 linea y JSON" 1 "$CAPN" "sin respuesta" "$(campo "$CAPL")$CAPL"
else
  printf '%-44s %-18s %-5s  %s\n' "C14 el escritor de la serie" "no esta" "AVISO" \
    "$CAP no existe: estos brazos NO se han ejercitado"
fi

echo
if [ "$fallos" -eq 0 ]; then
  echo "29 de 29 controles PASAN. Los dos brazos juzgan, el borde 23/24 esta donde se dijo,"
  echo "la serie que no se puede juzgar da NO MEDIDO, el criterio 1 sigue entero y el"
  echo "ESCRITOR de la serie mantiene una muestra = una linea (C14)."
  exit 0
fi
echo "$fallos controles FALLAN."
exit 1
