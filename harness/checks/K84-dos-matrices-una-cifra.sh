#!/bin/bash
# K84  LAS DOS RUTAS QUE PUBLICAN LA MISMA PATA NO DICEN LA MISMA COSA.
#
# EL CRITERIO VA SOBRE PRESENCIA, NUNCA SOBRE IMPORTES, y no es una preferencia de estilo:
# es un falso positivo que ya ocurrio. Comparando MAGNITUDES entre las dos rutas aparecen
# desfases con forma de regla -una constante repetida en 5m..8h y 0 en 1m- que un control de
# tres rondas intercaladas deshace: ronda 1 el mismo numero en las siete ventanas, ronda 2
# siete numeros distintos, ronda 3 ceros. Es DERIVA entre dos peticiones que no son
# simultaneas, no un defecto. Un check que compare importes sale rojo por deriva y enseña a
# ignorarlo. Aqui solo se compara SI HAY CIFRA o NO LA HAY.
#
# Y LAS DOS PETICIONES SALEN EN PARALELO, con el hueco entre ambas MEDIDO Y DECLARADO en la
# salida. Sin eso, el que lea el rojo tiene que repetir el control de deriva por su cuenta.
# Medido hoy: 0.7-1.0 s con las dos en paralelo.
#
# LA CELDA NO SE FIJA. Se deriva en cada pasada, y hay dos razones MEDIDAS para no clavarla:
#   1 · MIGRA CON EL RELOJ. El hueco interno esta en un instante fijo, asi que va saliendo de
#       las ventanas cortas antes que de las largas: a las 04:2xZ discrepaban SOL 4h y 8h, y
#       una hora despues ya solo la 8h. La misma causa, otra celda.
#   2 · NO ES DE SOL. Medido en 140 el 2026-09-01 sobre 8 h, el mayor hueco entre buckets
#       consecutivos es de 30-35 s EN TODAS las series, no solo en la fina:
#          futures  BTC p99 15 s / peor 30.0   ETH p99 15 / peor 30.0   SOL p99 20 / peor 35.0
#          spot     BTC p99 15 s / peor 35.0   ETH p99 20 / peor 35.0   SOL p99 15 / peor 35.0
#       O sea que el umbral de 30 s cae DENTRO de la cola natural de todas ellas y cual celda
#       se apaga es cara o cruz. Hoy toca a los futuros de SOL; manana, al spot de BTC.
#
# LA VIA, y esta vez el encargo la traia acotada: BTC y ETH limpios, SOL 8h con valor en
# cvd-matrix y null en delta-matrix las tres rondas. Reproducido aqui en tres rondas propias,
# 8 ventanas comunes por simbolo, y sale lo mismo.
#   cvd_matrix   (scalp_logic.py:2653) NO aplica guarda de hueco interno a la pata de futuros.
#   delta_matrix (scalp_logic.py:4092) SI: _realtime_flow marca complete=false cuando
#                max_internal_gap > REALTIME_STALE_SECONDS = 30 s (:184, :3933, :4123).
# Y las DOS viajan en el mismo /api/ai/context, asi que la IA recibe un numero y un nulo para
# la misma cifra en el mismo instante, sin nada que le diga cual es cual. El humano solo ve
# delta_matrix (app.js:1551), o sea que ve el hueco y no ve el numero.
#
# EL HUECO NO ES DATO PERDIDO, Y ESTO ES LO QUE DECIDE HACIA DONDE SE ARREGLA. Medido en 140
# sobre 8 h de SOL combined: 4804 filas, CERO con trade_count=0 y CERO con volumen 0, cadencia
# media 5.99 s. El colector NO escribe buckets vacios: escribe cuando hay operaciones. Luego
# un "hueco" de 35 s significa QUE NO SE OPERO durante 35 s -o que un venue callo, porque
# combined exige venue_count=2-, no que se perdiera nada. Blanquear una cifra de OCHO HORAS
# porque hubo 35 s sin operaciones es un falso "no lo se", y propagarlo a cvd_matrix lo
# empeoraria en vez de arreglarlo.
#
# LO QUE NO ES, para que nadie lo arregle donde no duele:
#   · NO es el defecto de K83. Alli el realtime NO alcanzaba la ventana y faltaba el empalme
#     con el agregado. Aqui el realtime SI la alcanza; lo que falla es la guarda.
#   · NO se toca la guarda del spot largo: delta_matrix solo la evalua cuando spot viene de
#     'realtime', y en 4h/8h/1d viene de 'agg_1min+realtime'.
#   · NO se compara contra un tercero. No hay una tercera ruta que arbitre, asi que este check
#     NO dice cual de las dos tiene razon: dice que no pueden decir cosas distintas.
#
# LOS CUATRO BRAZOS:
#   A · PRESENCIA EMPAREJADA POR SEGUNDOS, no por etiqueta. Las dos rutas nombran distinto la
#       misma ventana -24h contra 1d- y emparejar por nombre dejaria fuera justo la mas
#       larga. Se empareja por window_seconds.
#   B · HUECO ENTRE PETICIONES MEDIDO Y ACOTADO. Las dos salen en paralelo; si el hueco se
#       dispara, la presencia pudo cambiar entre una y otra y la atribucion no es segura:
#       NOMED, no ROJO.
#   C · CONTROL POSITIVO. Alguna ventana comun tiene que traer cifra en LAS DOS rutas. Si
#       ninguna coincidiera, el check no distingue "discrepan" de "una ruta esta muda".
#   D · CASO VACIO. Si no hay ventanas comunes, no hay nada que comparar: NOMED.
#
# DE QUE ARBOL: los cuatro brazos miden 140 por la API. El VERDE exige A con B, C y D vivos.
#
# Se comprueba con: bash harness/checks/K84-dos-matrices-una-cifra.sh

set -u
B=/srv/coinanalyze/harness
. "$B/env"
SIMBOLOS="BTCUSDT_PERP.A ETHUSDT_PERP.A SOLUSDT_PERP.A"
HUECO_MAX=${K84_HUECO_MAX_S:-5}   # segundos entre las dos peticiones; hoy salen 0.7-1.0

# bin/api corta a 8000 bytes y eso ROMPE el JSON de estas dos rutas por la mitad.
export TODO=1
TMP=$(mktemp -d) || { echo "NO MEDIDO: no se pudo crear el temporal"; exit 2; }
trap 'rm -rf "$TMP"' EXIT

FALLOS=""; COMUNES=0; COINCIDEN=0; HUECO_PEOR=0

for S in $SIMBOLOS; do
  CORTO=${S%%USDT*}
  T0=$(date -u +%s.%N)
  "$B/bin/api" "/api/cvd-matrix?symbol=$S"         > "$TMP/cvd.json"   2>/dev/null &
  P1=$!
  "$B/bin/api" "/api/scalp/delta-matrix?symbol=$S" > "$TMP/delta.json" 2>/dev/null &
  P2=$!
  wait $P1 $P2
  T1=$(date -u +%s.%N)
  HUECO=$(python3 -c "print(round($T1-$T0,2))")
  [ -s "$TMP/cvd.json" ] || { echo "NO MEDIDO: /api/cvd-matrix no contesto para $CORTO"; exit 2; }
  [ -s "$TMP/delta.json" ] || { echo "NO MEDIDO: /api/scalp/delta-matrix no contesto para $CORTO"; exit 2; }

  # --- B · el hueco entre las dos peticiones acota lo que este check puede afirmar.
  python3 -c "import sys; sys.exit(0 if float('$HUECO') <= $HUECO_MAX else 1)" || {
    echo "NO MEDIDO: entre las dos peticiones de $CORTO pasaron $HUECO s (tope $HUECO_MAX). Con ese hueco la presencia pudo cambiar por DERIVA entre una respuesta y otra, y una discrepancia no se podria atribuir a las rutas"
    exit 2
  }
  python3 -c "import sys; sys.exit(0 if float('$HUECO') > float('$HUECO_PEOR') else 1)" && HUECO_PEOR=$HUECO

  VER=$(python3 - "$TMP" <<'PY' 2>/dev/null
import json, sys
d = sys.argv[1]
SEG = {'15s':15,'30s':30,'1m':60,'3m':180,'5m':300,'15m':900,'18m':1080,'30m':1800,
       '1h':3600,'4h':14400,'8h':28800,'1d':86400,'24h':86400,'3d':259200,'7d':604800}
try:
    cvd = json.load(open(d + '/cvd.json'))
    delta = json.load(open(d + '/delta.json'))
except Exception as e:
    print('NOMED|no se pudo parsear una de las dos respuestas: %s' % e); raise SystemExit
if not isinstance(delta, list):
    print('NOMED|delta-matrix no devolvio una lista'); raise SystemExit
# A · emparejado por SEGUNDOS: las dos rutas llaman 24h y 1d a la misma ventana.
c = {}
for lab, w in (cvd.get('windows') or {}).items():
    sec = w.get('window_seconds') or SEG.get(lab)
    if sec:
        c[sec] = (lab, w.get('futures') is not None,
                  (w.get('futures_status') or {}).get('source'))
dd = {}
for r in delta:
    sec = SEG.get(r.get('window'))
    if sec:
        dd[sec] = (r.get('window'), r.get('fut_delta') is not None,
                   r.get('futures_source'), r.get('futures_max_gap_seconds'))
comunes = sorted(set(c) & set(dd))
disc, coinciden = [], 0
for sec in comunes:
    cl, cp, cs = c[sec]
    dl, dp, ds, mg = dd[sec]
    if cp and dp:
        coinciden += 1
    elif cp != dp:
        disc.append('%s/%s (%ds) cvd=%s[%s] delta=%s[%s] max_gap=%s'
                    % (cl, dl, sec, 'CIFRA' if cp else 'null', cs,
                       'CIFRA' if dp else 'null', ds, mg))
print('OK|%d|%d|%s' % (len(comunes), coinciden, ' · '.join(disc)))
PY
)
  case "$VER" in
    NOMED\|*) echo "NO MEDIDO: ${VER#NOMED|} ($CORTO)"; exit 2 ;;
    OK\|*) : ;;
    *) echo "NO MEDIDO: la comparacion de $CORTO no produjo veredicto ('$VER')"; exit 2 ;;
  esac
  IFS='|' read -r _ NCOM NCOI DISC <<EOF
$VER
EOF
  COMUNES=$((COMUNES+NCOM)); COINCIDEN=$((COINCIDEN+NCOI))
  [ -n "$DISC" ] && FALLOS="${FALLOS:+$FALLOS · }$CORTO: $DISC"
done

# --- D · caso vacio.
[ "$COMUNES" -gt 0 ] || {
  echo "NO MEDIDO: 0 ventanas comunes entre las dos rutas. Si dejaran de compartir ventanas no habria nada que comparar y un VERDE no probaria nada"
  exit 2
}
# --- C · control positivo.
[ "$COINCIDEN" -gt 0 ] || {
  echo "NO MEDIDO: NINGUNA de las $COMUNES ventanas comunes trae cifra en LAS DOS rutas. Sin un solo acuerdo no se distingue 'discrepan' de 'una ruta esta muda'"
  exit 2
}

# El ROJO distingue "el arreglo no funciona" de "falta desplegar" (nota de K77, K80 y K83).
ARBOL_OK=0
grep -q '_gap_and_baseline' "$REPO/app/scalp_logic.py" 2>/dev/null && ARBOL_OK=1

if [ -n "$FALLOS" ]; then
  [ "$ARBOL_OK" = 1 ] && FALLOS="$FALLOS · EL ARBOL YA LO TIENE ARREGLADO (existe _gap_and_baseline): falta DESPLEGAR"
  printf 'ROJO: las dos rutas publican la misma pata y no dicen lo mismo. %s · %d de %d ventanas comunes SI coinciden, y el hueco entre las dos peticiones fue de %s s como mucho, asi que esto NO es deriva\n' \
    "$FALLOS" "$COINCIDEN" "$COMUNES" "$HUECO_PEOR"
  exit 1
fi

printf 'las %d ventanas comunes de las dos rutas coinciden en PRESENCIA (%d con cifra en ambas), emparejadas por segundos y no por etiqueta. Hueco maximo entre las dos peticiones: %s s (tope %s), asi que la comparacion no la pudo mover la deriva\n' \
  "$COMUNES" "$COINCIDEN" "$HUECO_PEOR" "$HUECO_MAX"
