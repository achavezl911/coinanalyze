#!/bin/bash
# K42  EL PRIMER CHECK DEL ESLABON 6: que el numero sea CORRECTO.
#
# Los otros 19 checks verifican que el dato exista, este fresco, se declare y se sirva.
# Ninguno recalcula un indicador desde su definicion y lo compara. Este si, y por eso
# es el patron: ninguna ruta se cablea al panel sin uno.
#
# EL ORACULO. /api/liquidation-map dice ser "densidad de liquidaciones YA EJECUTADAS
# en las ultimas 3 h agregadas por precio" (scalp_logic.py:3326). Se recalcula desde
# los eventos crudos de liquidations_realtime y se compara cifra a cifra. El bucketeo
# -que es la parte que puede estar mal- se implementa AQUI en python, no se reusa el
# GROUP BY del endpoint: si se copiara la consulta, el check diria que si a cualquier
# cosa que el endpoint calcule.
#
# LO QUE NO SE PUEDE COMPARAR, Y POR QUE ESTE CHECK EXIGE LA VENTANA DECLARADA.
# La consulta del endpoint filtra ts >= now()-180min DENTRO de la propia consulta, y
# asyncpg abre una transaccion por consulta, asi que ni siquiera el endpoint usa el
# mismo now() en todas. Desde fuera es peor: entre la respuesta y el recalculo pasan
# segundos y la ventana se desliza por los dos bordes. Medido en 140 el 2026-08-26:
# 117 eventos en 3 h -0.65 por minuto, casi siempre cero en 60 s- PERO el evento mayor
# de la ventana vale 237426 USD, el 18 % del total. O sea: el desajuste es cero el 99 %
# del tiempo y catastrofico el 1 %. Un check asi pasa una semana y luego enrojece por
# algo que no es un fallo, que es la peor clase de check. Por eso la respuesta tiene
# que DECLARAR la ventana que uso, y el recalculo va contra ESA ventana cerrada.
# Es la misma leccion de K13 y K38: una cifra que no dice de donde sale no se puede
# verificar desde fuera.
#
# LO QUE TAMBIEN SE COMPRUEBA, Y NACIO DE UN ERROR AL ENCARGAR ESTE CHECK.
# "la suma de total_notional de los levels tiene que cuadrar con la suma de
# notional_usd de la ventana" es FALSO por diseno: levels es rows[:12] y el 2026-08-26
# habia 16 buckets, asi que los 12 mostrados sumaban 1324507.75 de 1330540.05 y
# faltaban 6032.30 que no son ningun fallo. Un consumidor que sume levels creyendo que
# tiene el mapa entero se equivoca en silencio. Asi que la truncacion se DECLARA
# (buckets_total, levels_shown, window_notional) y el check exige que la suma de lo
# mostrado cuadre con lo mostrado, no con el total.
set -uo pipefail
B=/srv/coinanalyze/harness; . "$B/env"
SIM=${K42_SIMBOLO:-BTCUSDT_PERP.A}
TOPE=12          # scalp_logic.py:3348, rows[:12]
BPS=10           # bucket_bps por defecto

cuerpo=$(curl -sS -k --netrc-file "$NETRC" --max-time 20 \
         "$API_PROD/api/liquidation-map?symbol=$SIM" 2>/dev/null)
[ -n "$cuerpo" ] || { echo "NO MEDIDO: /api/liquidation-map no respondio"; exit 2; }

# Paso 1: la declaracion. Sin ventana declarada no hay nada que verificar y se dice.
lectura=$(printf '%s' "$cuerpo" | python3 -c '
import sys, json
from datetime import datetime
try:
    d = json.load(sys.stdin)
except Exception:
    print("NOMED json ilegible"); raise SystemExit(0)
if d.get("available") is not True:
    print("NOMED available=%s" % d.get("available")); raise SystemExit(0)
faltan = [k for k in ("window_start", "window_end", "window_minutes", "bucket_size",
                      "buckets_total", "levels_shown", "window_notional")
          if d.get(k) is None]
if faltan:
    print("ROJO la respuesta no declara la ventana que uso: falta %s" % " ".join(faltan))
    raise SystemExit(0)
try:
    ini = datetime.fromisoformat(d["window_start"]); fin = datetime.fromisoformat(d["window_end"])
except Exception:
    print("ROJO window_start/window_end no son fechas ISO"); raise SystemExit(0)
dur = (fin - ini).total_seconds()
if dur != d["window_minutes"] * 60:
    print("ROJO la ventana declarada dura %.0f s y dice window_minutes=%s"
          % (dur, d["window_minutes"])); raise SystemExit(0)
esperado = round(d["current_price"] * '"$BPS"' / 10000.0, 6)
if abs(d["bucket_size"] - esperado) > 1e-6:
    print("ROJO bucket_size=%s y '"$BPS"' bps de %s son %s"
          % (d["bucket_size"], d["current_price"], esperado)); raise SystemExit(0)
print("OK %s %s %.10f %d" % (d["window_start"], d["window_end"], d["bucket_size"],
                             d["buckets_total"]))
')
case "$lectura" in
  NOMED*) echo "NO MEDIDO: ${lectura#NOMED }"; exit 2 ;;
  ROJO*)  echo "${lectura#ROJO }"; exit 1 ;;
  OK*)    ;;
  *)      echo "NO MEDIDO: lectura sin veredicto"; exit 2 ;;
esac
set -- $lectura
INI=$2; FIN=$3; BSIZE=$4; NBUCKETS=$5

[ "$NBUCKETS" -gt 0 ] || { echo "NO MEDIDO: 0 buckets en la ventana, no hay cifra que recalcular"; exit 2; }

# Paso 2: los eventos crudos de ESA ventana, agregados por (precio, lado) para que la
# salida quepa. El bucketeo NO se hace aqui: se hace en python, que es el punto.
# Se pide ademas el conteo por separado para detectar el corte de 8 KB de _corta y
# fallar CERRADO en vez de dar un ROJO falso por filas que no llegaron.
esperadas=$("$B/bin/prodsql" "SELECT count(DISTINCT (price,side)) FROM liquidations_realtime
  WHERE symbol='$SIM' AND ts >= '$INI'::timestamptz AND ts < '$FIN'::timestamptz" 2>/dev/null)
eventos=$("$B/bin/prodsql" "SELECT price, side, sum(notional_usd) FROM liquidations_realtime
  WHERE symbol='$SIM' AND ts >= '$INI'::timestamptz AND ts < '$FIN'::timestamptz
  GROUP BY 1,2 ORDER BY 1" 2>/dev/null)
recibidas=$(printf '%s\n' "$eventos" | grep -c '|')
[ "$recibidas" = "$esperadas" ] || {
  echo "NO MEDIDO: llegaron $recibidas de $esperadas filas (corte de salida); repite con TODO=1"
  exit 2
}

# Paso 3: el recalculo y la comparacion.
printf '%s' "$cuerpo" | python3 -c '
import sys, json
d = json.load(sys.stdin)
bsize = float("'"$BSIZE"'")
TOPE = '"$TOPE"'

crudo = {}
for linea in open("/dev/fd/3"):
    linea = linea.strip()
    if not linea or "|" not in linea:
        continue
    precio, lado, notional = linea.split("|")
    b = round(float(precio) / bsize) * bsize
    largo, corto = crudo.get(b, (0.0, 0.0))
    if lado == "long":
        largo += float(notional)
    else:
        corto += float(notional)
    crudo[b] = (largo, corto)

def cerca(a, b):
    return abs(a - b) <= max(0.01, abs(b) * 1e-9)

fallos = []
if len(crudo) != d["buckets_total"]:
    fallos.append("buckets: declara %d y recalculando salen %d" % (d["buckets_total"], len(crudo)))

total_ventana = sum(l + c for l, c in crudo.values())
if not cerca(d["window_notional"], total_ventana):
    fallos.append("window_notional: declara %.2f y recalculando sale %.2f"
                  % (d["window_notional"], total_ventana))

niveles = d["levels"]
if d["levels_shown"] != len(niveles):
    fallos.append("levels_shown=%s y vienen %d" % (d["levels_shown"], len(niveles)))
if len(niveles) != min(TOPE, len(crudo)):
    fallos.append("vienen %d niveles y con %d buckets deberian ser %d"
                  % (len(niveles), len(crudo), min(TOPE, len(crudo))))

# los mostrados tienen que ser los TOPE mayores por total
mayores = sorted(crudo, key=lambda b: -(crudo[b][0] + crudo[b][1]))[:len(niveles)]
if sorted(round(b, 2) for b in mayores) != sorted(n["price"] for n in niveles):
    fallos.append("los %d niveles servidos no son los %d buckets mayores de la ventana"
                  % (len(niveles), len(niveles)))

comparadas = 0
for n in niveles:
    b = next((k for k in crudo if abs(round(k, 2) - n["price"]) < 1e-6), None)
    if b is None:
        fallos.append("nivel %s no existe recalculando" % n["price"]); continue
    largo, corto = crudo[b]
    for etiqueta, servido, propio in (("long_liq", n["long_liq"], largo),
                                      ("short_liq", n["short_liq"], corto),
                                      ("total_notional", n["total_notional"], largo + corto)):
        comparadas += 1
        if not cerca(servido, propio):
            fallos.append("%s@%s: sirve %.4f y recalculando sale %.4f"
                          % (etiqueta, n["price"], servido, propio))
    if not cerca(n["long_liq"] + n["short_liq"], n["total_notional"]):
        fallos.append("nivel %s: long+short no da total_notional" % n["price"])

if fallos:
    print("el mapa no cuadra con sus eventos: %s" % " | ".join(fallos[:4]))
    raise SystemExit(1)
print("%d cifras recalculadas desde liquidations_realtime cuadran al centimo sobre la "
      "ventana declarada [%s, %s): %d niveles de %d buckets, %.2f USD de %.2f mostrados"
      % (comparadas, d["window_start"][11:19], d["window_end"][11:19], len(niveles),
         d["buckets_total"], sum(n["total_notional"] for n in niveles), d["window_notional"]))
' 3<<< "$eventos"
